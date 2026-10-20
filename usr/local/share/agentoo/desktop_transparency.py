"""Transparency state and CLI operations; imported without effects for completion.

The private `rules` entry point supplies validated numeric data to Hyprland.
It is not a public Agentoo command. JSON is the only authoritative saved state.
"""
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

GROUPS = ('all', 'kitty', 'browser')
STATES = ('focused', 'unfocused')


def percentage(value):
    try:
        number = float(value)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError('transparency must be a number from 0 to 90') from None
    if not math.isfinite(number) or not 0 <= number <= 90:
        raise argparse.ArgumentTypeError('transparency must be a number from 0 to 90')
    return number


def xdg_directory(variable, fallback):
    value = os.environ.get(variable, '')
    return Path(value) if value and Path(value).is_absolute() else Path.home() / fallback


def state_path():
    return xdg_directory('XDG_STATE_HOME', '.local/state') / 'agentoo/transparency.json'


def read_state(path):
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except (ValueError, UnicodeError) as error:
        raise RuntimeError(f'Invalid transparency state in {path}: {error}') from error
    if not isinstance(data, dict) or set(data) - set(GROUPS):
        raise RuntimeError(f'Invalid transparency groups in {path}')
    for group, values in data.items():
        if not isinstance(values, dict) or set(values) - set(STATES):
            raise RuntimeError(f'Invalid transparency settings for {group} in {path}')
        for value in values.values():
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 90:
                raise RuntimeError(f'Invalid transparency percentage in {path}')
    return data


def effective(data, group, focus):
    return data.get(group, {}).get(focus, data.get('all', {}).get(focus))


def adjusted(data, group, focused=None, unfocused=None, reset=False):
    data = {key: dict(values) for key, values in data.items()}
    if reset:
        if group == 'all':
            return {}
        data.pop(group, None)
    else:
        for focus, value in zip(STATES, (focused, unfocused)):
            if value is None:
                continue
            data.setdefault(group, {})[focus] = value
            if group == 'all':
                for child in ('kitty', 'browser'):
                    data.get(child, {}).pop(focus, None)
    return {key: values for key, values in data.items() if values}


def conflicts():
    # Conservative inspection, not a Lua evaluator. Never modify authored files.
    # Includes anywhere beneath these roots are covered; opaque/dynamic includes
    # outside them require manual inspection (documented).
    config = xdg_directory('XDG_CONFIG_HOME', '.config')
    roots = (config / 'hypr',)
    paths = []
    selector = Path('/etc/agentoo/target-host')
    if selector.exists():
        selected = re.fullmatch(r'\s*GENTOO_TARGET_HOST\s*=\s*"([\w-]+)"\s*', selector.read_text(), re.ASCII)
        if selected:
            host = Path('/etc/xdg/hypr/hosts') / (selected[1] + '.lua')
            if host.is_file():
                paths.append(host)
    found = []
    for root in roots:
        if not root.exists():
            continue
        paths.extend(path for path in sorted(root.rglob('*'))
                     if path.suffix in ('.lua', '.conf') and path.is_file())
    for path in paths:
        for number, line in enumerate(path.read_text().splitlines(), 1):
            line = re.split(r'--|#', line, maxsplit=1)[0]
            if re.search(r'\b(opacity|opaque|force_rgbx)\s*[= ]', line):
                found.append(f'{path}:{number}')
    return found


def hyprctl(*arguments):
    try:
        result = subprocess.run(['hyprctl', *arguments], text=True, capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f'Cannot contact Hyprland: {error}') from error
    if result.returncode:
        raise RuntimeError('Hyprland: ' + (result.stderr or result.stdout).strip())
    return result.stdout.strip()


def require_integration(recover=False):
    if not os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
        raise RuntimeError('A running Hyprland session is required to change transparency')
    if recover:
        # A full reset must also recover from malformed saved state or authored
        # rules added since the last successful load.
        hyprctl('version')
        return
    result = hyprctl('eval', 'assert(agentoo_transparency_loaded, "Agentoo transparency integration is not loaded")')
    if result != 'ok':
        raise RuntimeError('Load the Agentoo Hyprland configuration first: ' + result)
    errors = hyprctl('configerrors')
    if errors:
        raise RuntimeError('Fix Hyprland configuration errors before changing transparency: ' + errors)


def kitty_defaults():
    # Kitty owns its include/geninclude/host/command-line parsing. This starts no
    # window and needs neither remote-control access nor a display connection.
    code = ('import json; from kitty.cli import default_config_paths; '
            'from kitty.config import load_config; '
            'o=load_config(*default_config_paths(())); '
            'print(json.dumps([o.background_opacity, o.dynamic_background_opacity, list(o.watcher)]))')
    try:
        result = subprocess.run(['kitty', '+runpy', code], text=True, capture_output=True, timeout=10)
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return None


def show(data, selected):
    defaults = {}
    if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
        for focus, option in zip(STATES, ('active', 'inactive')):
            try:
                value = json.loads(hyprctl('-j', 'getoption', f'decoration:{option}_opacity'))['float']
                defaults[focus] = (1 - float(value)) * 100
            except (RuntimeError, ValueError, KeyError, TypeError):
                pass
    kitty = kitty_defaults()
    print(f'{"WINDOW":<10} {"FOCUSED":<32} UNFOCUSED')
    for group in GROUPS if selected == 'all' else (selected,):
        cells = []
        for focus in STATES:
            value = effective(data, group, focus)
            source = 'override' if focus in data.get(group, {}) else 'inherited: all'
            if value is None:
                value = (1 - kitty[0]) * 100 if group == 'kitty' and kitty else defaults.get(focus)
                source = 'configured default'
            cells.append(f'{value:g}% ({source})' if value is not None else source)
        print(f'{group:<10} {cells[0]:<32} {cells[1]}')
    print('Kitty: background only. Other windows: whole window.')
    for location in conflicts():
        print(f'agentoo desktop: warning: transparency rule may conflict: {location}', file=sys.stderr)


def run(args, directory, atomic_write):
    path = directory / 'transparency.json'
    if not args.reset and args.focused is None and args.unfocused is None:
        show(read_state(path), args.window)
        return 0
    require_integration(recover=args.reset and args.window == 'all')
    if not args.reset:
        found = conflicts()
        if found:
            raise RuntimeError('Conflicting transparency rules; edit them before adjusting:\n' + '\n'.join(found))
    previous_umask = os.umask(0o077)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / 'transparency.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            original = path.read_bytes() if path.exists() else None
            previous = {} if args.reset and args.window == 'all' else read_state(path)
            updated = adjusted(previous, args.window, args.focused, args.unfocused, args.reset)
            if any(effective(updated, 'kitty', focus) is not None for focus in STATES):
                kitty = kitty_defaults()
                watcher = str(Path(__file__).with_name('kitty') / 'transparency.py')
                if not kitty or not kitty[1] or watcher not in kitty[2]:
                    raise RuntimeError('Kitty needs the Agentoo watcher and dynamic_background_opacity yes; '
                                       'install the shared Kitty configuration and restart older Kitty processes')
            if updated:
                atomic_write(path, json.dumps(updated, sort_keys=True, indent=2) + '\n')
            else:
                path.unlink(missing_ok=True)
            try:
                result = hyprctl('reload', 'config-only')
                if result != 'ok':
                    raise RuntimeError('Hyprland reload failed: ' + result)
                errors = hyprctl('configerrors')
                if errors:
                    raise RuntimeError('Hyprland configuration errors: ' + errors)
            except RuntimeError:
                if original is not None:
                    atomic_write(path, original)
                else:
                    path.unlink(missing_ok=True)
                try:
                    hyprctl('reload', 'config-only')
                except RuntimeError as error:
                    print(f'agentoo desktop: warning: rollback reload failed: {error}', file=sys.stderr)
                raise
    finally:
        os.umask(previous_umask)
    print('Transparency overrides reset.' if args.reset else 'Transparency updated.', file=sys.stderr)
    return 0


def rules():
    data = read_state(state_path())
    if data and conflicts():
        raise RuntimeError('Conflicting authored transparency rules; saved overrides were not applied')
    for group in GROUPS:
        for focus in STATES:
            value = effective(data, group, focus)
            if value is not None:
                print(group, focus, f'{value:g}', sep='\t')
    print('end')


if __name__ == '__main__':
    try:
        if sys.argv[1:] != ['rules']:
            raise RuntimeError('Private helper: expected rules')
        rules()
    except (OSError, RuntimeError) as error:
        print(f'agentoo desktop: {error}', file=sys.stderr)
        raise SystemExit(1)
