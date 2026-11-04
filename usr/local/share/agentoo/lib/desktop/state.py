"""One appearance file and transaction for desktop commands; wallpaper is separate."""
import fcntl
import json
import os
from pathlib import Path
import sys

if __name__ == '__main__':
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desktop import blur, effects, transparency
from desktop.common import (atomic_write, effective, read, read_json,
                            window_rule_conflicts, WINDOW_GROUPS)

SECTIONS = ('transparency', 'blur', *effects.COMMANDS)


def validate_sections(data, *, partial=False):
    unknown = set(data) - set(SECTIONS)
    if unknown:
        raise RuntimeError('Unknown appearance sections: ' + ', '.join(sorted(unknown)))
    effect_sections = {name: values for name, values in data.items() if name in effects.COMMANDS}
    result = effects.validate_sections(effect_sections, partial=partial) if effect_sections else {}
    for name, values in data.items():
        if name == 'blur':
            result[name] = blur.validate_data(values)
        elif name == 'transparency':
            result[name] = transparency.validate_data(values)
    return result


def update(args, path, parser=None):
    directory = path.parent
    command = getattr(args, 'command', None)
    file = getattr(args, 'appearance_file', None)
    patch = None
    if file is not None:
        patch = read_json(Path(file))
        if command:
            if command not in patch:
                raise RuntimeError(f'Appearance file {file} has no {command} section')
            patch = {command: patch[command]}
        patch = validate_sections(patch, partial=True)
        changed = set(patch)
    else:
        changed = set(SECTIONS) if command is None else {command}
    if not changed:
        raise RuntimeError('Appearance file contains no settings to apply')
    clearing = args.action == 'clear'
    values = effects.validate(args, parser) if not clearing and file is None and command in effects.COMMANDS else None
    if 'transparency' in changed:
        transparency.require_integration(recover=clearing and args.window == 'all')
    if 'blur' in changed:
        blur.require_integration(recover=clearing and args.window == 'all')
    if changed & set(effects.COMMANDS):
        if not os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
            raise RuntimeError('A running Hyprland session is required to change desktop effects')
        if not clearing and effects.hyprctl('repl', 'return agentoo_effects_report and "ready" or "missing"') != 'ready':
            raise RuntimeError('Load the shared Agentoo effects.lua integration before changing effects')
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
                # Partial sections and window groups retain omitted fields.
                for name, values in patch.items():
                    previous = data.get(name, {})
                    if name == 'animations':
                        data[name] = effects.animation_update(previous, values)
                        continue
                    data[name] = {**previous, **values}
                    if name in ('transparency', 'blur'):
                        for group, fields in values.items():
                            data[name][group] = {**previous.get(group, {}), **fields}
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
            for feature in ('transparency', 'blur'):
                if feature in changed and any(data.get(feature, {}).get(group) for group in WINDOW_GROUPS):
                    found = window_rule_conflicts(feature)
                    if found:
                        raise RuntimeError(f'Conflicting {feature} window rules; edit and reload authored configuration before adjusting:\n' + '\n'.join(found))
            if 'transparency' in changed:
                selected = data.get('transparency', {})
                if any(effective(selected, 'kitty', focus) is not None for focus in transparency.STATES):
                    kitty = transparency.kitty_defaults()
                    watcher = '/usr/local/share/agentoo/lib/kitty/transparency.py'
                    if not kitty or not kitty[1] or watcher not in kitty[2]:
                        raise RuntimeError('Kitty configuration needs dynamic_background_opacity yes and watcher ' + watcher)
            # Validate duration against the receiving desktop without saving curves.
            if 'animations' in changed and 'duration' in data.get('animations', {}):
                if any(branch['bezier'].startswith('spring:') for branch in effects.live_animations().values()):
                    raise RuntimeError('Spring curves control their own timing; configure a bezier curve before using --duration')
            atomic_write(path, json.dumps(data, indent=2, sort_keys=True) + '\n')
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
                    atomic_write(path, original)
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


if __name__ == '__main__':
    try:
        if sys.argv[1:] != ['settings']:
            raise RuntimeError('Private helper: expected settings')
        # One validated snapshot for all three Hyprland appearance integrations.
        data = validate_sections(read())
        lines = []
        for group in WINDOW_GROUPS:
            for focus in transparency.STATES:
                value = effective(data.get('transparency', {}), group, focus)
                if value is not None:
                    lines.append(f'transparency\t{group}\t{focus}\t{value:g}')
        saved_blur = data.get('blur', {})
        for group in WINDOW_GROUPS:
            for focus, value in saved_blur.get(group, {}).items():
                lines.append(f'blur\t{group}\t{focus}\t' + ('on' if value else 'off'))
        for name, value in saved_blur.get('strength', {}).items():
            lines.append(f'blur\tstrength\t{name}\t{value}')
        lines.append('blur\trevision\t' + blur.revision(saved_blur))
        for group in effects.COMMANDS:
            for key, value in data.get(group, {}).items():
                lines.append(f'effects\t{group}\t{key}\t{value}')
        print('\n'.join([*lines, 'end']))
    except (OSError, RuntimeError) as error:
        print(f'agentoo desktop: {error}', file=sys.stderr)
        raise SystemExit(1)
