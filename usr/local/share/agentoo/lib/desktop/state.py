"""One appearance file and transaction for desktop commands; wallpaper is separate."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import sys

from desktop.common import atomic_write, xdg_directory

SECTIONS = ('transparency', 'blur', 'corners', 'gaps', 'borders', 'animations', 'shadows', 'dimming')


def state_path():
    return xdg_directory('XDG_STATE_HOME', '.local/state') / 'agentoo/appearance.json'


def read_json(path):
    try:
        data = json.loads(path.read_text())
    except (ValueError, OSError) as error:
        raise RuntimeError(f'Cannot read appearance file {path}: {error}') from error
    if not isinstance(data, dict):
        raise RuntimeError(f'Appearance file {path} must contain a JSON object')
    return data


def validate_sections(data, *, partial=False):
    from desktop import blur as blur
    from desktop import effects as effects
    from desktop import transparency as transparency
    unknown = set(data) - set(SECTIONS)
    if unknown:
        raise RuntimeError('Unknown appearance sections: ' + ', '.join(sorted(unknown)))
    result = {}
    for name, values in data.items():
        if name == 'blur':
            result[name] = blur.validate_data(values)
        elif name == 'transparency':
            result[name] = transparency.validate_data(values)
        else:
            result[name] = effects.validate_sections({name: values}, partial=partial)[name]
    return result


def read(path=None):
    path = state_path() if path is None else Path(path)
    return read_json(path) if path.exists() else {}


def section(name, path=None):
    return read(path).get(name, {})


def file_option(parser, *, required=False):
    parser.add_argument('--file', dest='appearance_file', metavar='FILE',
                        required=required,
                        help='Apply and remember supplied appearance settings from JSON; omitted settings stay unchanged').completion = 'files'


def window_option(parser, *, child=False):
    parser.add_argument('--window', choices=('all', 'kitty', 'browser', 'other'),
                        default=argparse.SUPPRESS if child else 'all',
                        help='Window category; other excludes kitty and browsers (default: all)')


def imported(path, command=None):
    data = read_json(Path(path))
    if command:
        if command not in data:
            raise RuntimeError(f'Appearance file {path} has no {command} section')
        data = {command: data[command]}
    return validate_sections(data, partial=True)


def merged(previous, patch):
    """Partial sections and window groups retain omitted fields."""
    from desktop.effects import animation_update
    result = dict(previous)
    for name, values in patch.items():
        if name == 'animations':
            result[name] = animation_update(previous.get(name, {}), values)
            continue
        result[name] = {**previous.get(name, {}), **values}
        if name in ('transparency', 'blur'):
            for group, fields in values.items():
                result[name][group] = {**previous.get(name, {}).get(group, {}), **fields}
    return result


def update(args, directory, write=atomic_write, parser=None):
    from desktop import blur as blur
    from desktop import effects as effects
    from desktop import transparency as transparency

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
    path = directory / 'appearance.json'
    previous_umask = os.umask(0o077)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / 'appearance.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            original = path.read_bytes() if path.exists() else None
            data = read(path)
            if clearing:
                if command is None:
                    data = {}
                elif command in ('blur', 'transparency') and args.window != 'all':
                    values = validate_sections({command: data.get(command, {})})[command]
                    data[command] = {group: fields for group, fields in values.items() if group != args.window}
                else:
                    data.pop(command, None)
            elif patch is not None:
                data = merged(data, patch)
            elif command == 'blur':
                data[command] = blur.adjusted(blur.validate_data(data.get(command, {})), args)
            elif command == 'transparency':
                data[command] = transparency.adjusted(transparency.validate_data(data.get(command, {})),
                                                      args.window, args.focused, args.unfocused)
            else:
                if command == 'animations':
                    data[command] = effects.animation_update(data.get(command, {}), values)
                else:
                    data[command] = {**data.get(command, {}), **values}
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
            write(path, json.dumps(data, indent=2, sort_keys=True) + '\n')
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
