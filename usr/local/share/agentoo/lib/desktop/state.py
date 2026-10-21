"""One appearance file and transaction for desktop commands; wallpaper is separate."""
import argparse
import ast
import math
import fcntl
import os
import subprocess
from pathlib import Path
import sys

from desktop.common import atomic_write, xdg_directory

SECTIONS = ('transparency', 'blur', 'corners', 'gaps', 'borders', 'animations', 'shadows', 'dimming')


def state_path():
    return xdg_directory('XDG_CONFIG_HOME', '.config') / 'hypr/agentoo-desktop.lua'


def _lua(value):
    """Quote transient CLI data for Lua; Lua owns the saved-file serializer."""
    if isinstance(value, (dict, list)):
        items = value.items() if isinstance(value, dict) else enumerate(value)
        return '{' + ','.join(f'[{_lua(key)}]={_lua(item)}' for key, item in items) + '}'
    if isinstance(value, str):
        escaped = ''.join('\\' + ch if ch in ('"', '\\') else f'\\{ord(ch):03d}' if ord(ch) < 32 else ch for ch in value)
        return '"' + escaped + '"'
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)) and math.isfinite(value):
        return repr(value)
    raise RuntimeError('Preferences support only tables, strings, finite numbers and booleans')


def native(operation, *args, data=None, decode=False):
    helper = Path(__file__).with_name('preferences.lua')
    try:
        result = subprocess.run(['lua5.4', str(helper), operation, *map(str, args)],
            input='return ' + _lua(data) if data is not None else None,
            text=True, encoding='utf-8', errors='replace', capture_output=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f'Cannot run Lua preferences helper: {error}') from error
    if result.returncode:
        message = result.stderr.strip()
        if operation == 'read':
            message = f'Cannot read appearance file {args[0]}: {message}'
        raise RuntimeError(message)
    # Lua emits a Python literal of validated values for command-side queries.
    # literal_eval reads data only; it does not parse Lua or execute Python code.
    return ast.literal_eval(result.stdout) if decode else result.stdout


def dumps(data):
    return native('encode', data=data)


def validate_sections(data, *, partial=False):
    return native('validate', 'partial' if partial else '', data=data, decode=True)


def read(path=None, *, selected=None, omit=None):
    path = state_path() if path is None else Path(path)
    if not path.exists():
        return {}
    return native('read', path, selected or '', '', omit or '', decode=True)


def section(name, path=None):
    return read(path, selected=name).get(name, {})


def file_option(parser, *, required=False):
    parser.add_argument('--file', dest='appearance_file', metavar='FILE',
                        required=required,
                        help='Apply and remember supplied appearance settings from a Lua preset; omitted settings stay unchanged').completion = 'files'


def window_option(parser, *, child=False):
    parser.add_argument('--window', choices=('all', 'kitty', 'browser'),
                        default=argparse.SUPPRESS if child else 'all',
                        help='Window category (default: all)')


def imported(path, command=None):
    path = Path(path)
    data = native('read', path, command or '', 'partial', decode=True)
    if command and command not in data:
        raise RuntimeError(f'Appearance file {path} has no {command} section')
    return data


def merged(previous, patch):
    return native('merge', data={'previous': previous, 'patch': patch}, decode=True)


def update(args, directory, write=atomic_write, parser=None):
    from desktop import blur
    from desktop import effects
    from desktop import transparency

    command = getattr(args, 'command', None)
    file = getattr(args, 'appearance_file', None)
    patch = imported(file, command) if file is not None else None
    if patch is not None:
        changed = set(patch)
    else:
        changed = set(SECTIONS) if command is None else {command}
    if not changed:
        raise RuntimeError('Appearance file contains no settings to apply')
    clearing = args.action == 'clear'
    values = effects.validate(args, parser) if not clearing and file is None and command in effects.COMMANDS else None
    if 'transparency' in changed:
        transparency.require_integration(recover=clearing and args.window == 'all')
        if not clearing and transparency.conflicts():
            raise RuntimeError('Conflicting transparency rules; edit them before adjusting')
    if 'blur' in changed:
        blur.require_integration(recover=clearing and args.window == 'all')
    if changed & set(effects.COMMANDS):
        if not os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
            raise RuntimeError('A running Hyprland session is required to change desktop effects')
        if not clearing and effects.hyprctl('repl', 'return agentoo_effects_report and "ready" or "missing"') != 'ready':
            raise RuntimeError('Load the shared Agentoo effects.lua integration before changing effects')
    path = directory / 'agentoo-desktop.lua'
    previous_umask = os.umask(0o077)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        lock_path = xdg_directory('XDG_RUNTIME_DIR', '.cache') / 'agentoo/appearance.lock'
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            original = path.read_bytes() if path.exists() else None
            discard = clearing and command is not None and (command not in ('blur', 'transparency') or args.window == 'all')
            data = {} if clearing and command is None else read(path, omit=command if discard else None)
            if clearing:
                if command is None:
                    data = {}
                elif command in ('blur', 'transparency') and args.window != 'all':
                    values = data.get(command, {})
                    data[command] = {group: fields for group, fields in values.items() if group != args.window}
                else:
                    data.pop(command, None)
            elif patch is not None:
                data = merged(data, patch)
            elif command == 'blur':
                data[command] = blur.adjusted(data.get(command, {}), args)
            elif command == 'transparency':
                data[command] = transparency.adjusted(data.get(command, {}),
                                                      args.window, args.focused, args.unfocused)
            else:
                data = merged(data, {command: values})
            data = validate_sections(data)
            if 'blur' in changed:
                blur.check_conflicts(data.get('blur', {}))
            if 'transparency' in changed:
                selected = data.get('transparency', {})
                if any(transparency.effective(selected, 'kitty', focus) is not None for focus in transparency.STATES):
                    kitty = transparency.kitty_defaults()
                    watcher = str(Path(transparency.__file__).parents[1] / 'kitty/transparency.py')
                    if not kitty or not kitty[1] or watcher not in kitty[2]:
                        raise RuntimeError('Kitty needs the Agentoo watcher and dynamic_background_opacity yes; restart older Kitty processes')
            # Validate duration against the receiving desktop without saving curves.
            if 'animations' in changed and 'duration' in data.get('animations', {}):
                if any(branch['bezier'].startswith('spring:') for branch in effects.live_animations().values()):
                    raise RuntimeError('Spring curves control their own timing; configure a bezier curve before using --duration')
            if data:
                write(path, dumps(data))
            else:
                path.unlink(missing_ok=True)
            report = None
            try:
                if 'blur' in changed:
                    report = blur.reload_saved(data.get('blur', {}))
                else:
                    effects.reload_settings()
            except BaseException:
                if original is None:
                    path.unlink(missing_ok=True)
                else:
                    write(path, original)
                try:
                    effects.reload_settings()
                except RuntimeError as error:
                    print(f'agentoo desktop: could not reload restored preferences: {error}', file=sys.stderr)
                raise
    finally:
        os.umask(previous_umask)
    subject = command.capitalize() if command else 'Appearance'
    message = f'{subject} ' + ('overrides cleared.' if clearing else 'updated.')
    if command == 'blur' and file is None and not clearing and args.focused is None and args.unfocused is None:
        message = 'Blur strength saved.'
        if report and report['option.enabled'] == 'off':
            message += ' Blur remains off; enable it with --focused on and/or --unfocused on.'
    print(message, file=sys.stderr)
    return 0
