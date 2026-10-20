"""Kitty 0.48 watcher: saved focused/unfocused background transparency.

Uses Kitty's in-process remote-control API. A small timer notices CLI changes
even when no focus event occurs. No sockets, terminal escapes, or shell code.
"""
from pathlib import Path
import runpy
import sys

_share = str(Path(__file__).resolve().parents[1])
# Kitty does not add the watcher's parent directory to its Python search path.
# Allow the state module's shared imports, without changing Kitty's lasting path.
sys.path.insert(0, _share)
try:
    _state = runpy.run_path(str(Path(_share) / 'desktop_transparency.py'),
                           run_name='agentoo_transparency_state')
finally:
    sys.path.remove(_share)
_applied = {}
_last_error = None
_previous_state = None


def refresh(boss):
    global _last_error, _previous_state
    from kitty.fast_data_types import current_focused_os_window_id, get_options
    from kitty.utils import log_error
    try:
        data = _state['read_state'](_state['state_path']())
        if _previous_state is not None and data != _previous_state and any(
            _state['effective'](_previous_state, 'kitty', focus) is not None
            and _state['effective'](data, 'kitty', focus) is None
            for focus in ('focused', 'unfocused')
        ):
            # Reset re-reads authored includes too: ~/.config may have changed
            # since this Kitty process started. Its command-line overrides stay.
            boss.load_config_file()
        _previous_state = data
        options = get_options()
        focused = current_focused_os_window_id()
        windows = {window.os_window_id: window for window in boss.all_windows}
        for identifier in tuple(_applied):
            if identifier not in windows:
                del _applied[identifier]
        for identifier, window in windows.items():
            focus = 'focused' if identifier == focused else 'unfocused'
            value = _state['effective'](data, 'kitty', focus)
            managed = value is not None
            if not managed and identifier not in _applied:
                continue
            opacity = 1 - value / 100 if managed else options.background_opacity
            if _applied.get(identifier) == opacity:
                if not managed:
                    _applied.pop(identifier, None)
                continue
            if not options.dynamic_background_opacity:
                raise RuntimeError('Kitty dynamic_background_opacity must be yes; restart older Kitty processes')
            boss.call_remote_control(window, ('set-background-opacity', f'--match=id:{window.id}', str(opacity)))
            if managed:
                _applied[identifier] = opacity
            else:
                _applied.pop(identifier, None)
        _last_error = None
    except Exception as error:
        # Keep the last good appearance and report once, rather than spamming a
        # terminal every timer tick if the saved file/configuration is damaged.
        message = f'Agentoo transparency: {error}'
        if message != _last_error:
            log_error(message)
            _last_error = message


def on_load(boss, data):
    from kitty.fast_data_types import add_timer
    add_timer(lambda timer: refresh(boss), 0.25, True)


def on_focus_change(boss, window, data):
    refresh(boss)


def on_resize(boss, window, data):
    refresh(boss)
