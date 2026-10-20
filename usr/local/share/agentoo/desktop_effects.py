"""Personal desktop effects for Hyprland 0.56.2; no operations on import.

One parser supplies help, completion and saved-value validation. The private
settings entry point emits tab-separated data for effects.lua, never user code.
"""
import argparse
import json
import math
import os
import re
import sys

sys.dont_write_bytecode = True
from cli import ArgumentParser
from desktop_common import hyprctl

COMMANDS = ('corners', 'gaps', 'borders', 'animations', 'shadows', 'dimming')
WINDOW_STYLES = ('slide', 'popin', 'gnome', 'gnomed')
WORKSPACE_STYLES = ('slide', 'slidevert', 'fade', 'slidefade', 'slidefadevert')
PARENTS = {'windowsIn': 'windows', 'windowsOut': 'windows', 'windows': 'global',
           'workspacesIn': 'workspaces', 'workspacesOut': 'workspaces', 'workspaces': 'global',
           'specialWorkspaceIn': 'specialWorkspace', 'specialWorkspaceOut': 'specialWorkspace',
           'specialWorkspace': 'workspaces'}
WINDOW_NODES = ('windowsIn', 'windowsOut')
WORKSPACE_NODES = ('workspacesIn', 'workspacesOut', 'specialWorkspaceIn', 'specialWorkspaceOut')


def number(low, high, integer=False):
    def parse(value):
        try:
            result = int(value) if integer else float(value)
        except (ValueError, TypeError):
            raise argparse.ArgumentTypeError(f'expected {"an integer" if integer else "a number"} from {low} to {high}') from None
        if not low <= result <= high or not math.isfinite(result):
            raise argparse.ArgumentTypeError(f'expected a value from {low} to {high}')
        return result
    return parse


def color(value):
    if not re.fullmatch(r'#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?', value):
        raise argparse.ArgumentTypeError('expected #RRGGBB or #RRGGBBAA (quote colors in the shell)')
    return value.lower()


def gradient(value):
    colors = value.split(',')
    if not 1 <= len(colors) <= 10:
        raise argparse.ArgumentTypeError('expected 1–10 comma-separated colors')
    return ','.join(color(part.strip()) for part in colors)


def opaque_color(value):
    value = color(value)
    if len(value) != 7:
        raise argparse.ArgumentTypeError('expected #RRGGBB; use --opacity for shadow opacity')
    return value


def add_parsers(commands):
    parsers = {}
    descriptions = {
        'corners': 'Show or adjust window corners', 'gaps': 'Show or adjust tiled-window spacing',
        'borders': 'Show or adjust window borders', 'animations': 'Show or adjust window and workspace animations',
        'shadows': 'Show or adjust window shadows', 'dimming': 'Show or adjust focus and modal-parent dimming',
    }
    for name, description in descriptions.items():
        p = commands.add_parser(name, help=description, description=description + '.\n\n'
            'Without adjustment options, show settings and their sources. Changes apply\n'
            'immediately and persist. Omitted settings stay unchanged. --reset removes\n'
            'this command\'s overrides and restores configured defaults. Settings are global;\n'
            'window/workspace rules can still override them.',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog='Exit 0: success; 1: operational failure; 2: invalid arguments.')
        p.add_argument('--reset', action='store_true', help='Remove saved overrides; cannot combine with adjustments')
        from desktop_state import file_option
        file_option(p, child=True)
        parsers[name] = p
    p = parsers['corners']
    p.add_argument('--radius', type=number(0, 20, True), metavar='PIXELS', help='Corner radius, 0–20; 0 makes square corners')
    p.add_argument('--power', type=number(2, 10), metavar='NUMBER', help='Rounding power, 2–10; 2 is circular, 4 is a squircle')
    p = parsers['gaps']
    p.add_argument('--inner', type=number(0, 1000, True), metavar='PIXELS', help='Gap on each tiled-window side, 0–1000; adjacent sides add')
    p.add_argument('--outer', type=number(0, 1000, True), metavar='PIXELS', help='Additional gap at screen edges, 0–1000')
    p = parsers['borders']
    p.add_argument('--width', type=number(0, 20, True), metavar='PIXELS', help='Border width, 0–20; 0 hides borders')
    p.add_argument('--focused', type=gradient, metavar='COLORS', help='1–10 comma-separated focused colors, quoted #RRGGBB or #RRGGBBAA')
    p.add_argument('--unfocused', type=gradient, metavar='COLORS', help='1–10 comma-separated unfocused colors, quoted #RRGGBB or #RRGGBBAA')
    p.add_argument('--focused-angle', type=number(0, 360), metavar='DEGREES', help='Focused gradient angle, 0–360; preserves colors')
    p.add_argument('--unfocused-angle', type=number(0, 360), metavar='DEGREES', help='Unfocused gradient angle, 0–360; preserves colors')
    p.epilog = ('Colors and angles change independently; omitted values remain unchanged.\n'
                'One color is solid. Each color may include its own alpha value.\n\n'
                'Example:\n'
                "  agentoo desktop borders --focused '#89b4fa,#cba6f7,#f38ba8' --focused-angle 45\n\n"
                'Exit 0: success; 1: operational failure; 2: invalid arguments.')
    p = parsers['animations']
    p.add_argument('--enabled', choices=('on', 'off'), help='Master animation switch; other adjustments do not enable it')
    p.add_argument('--duration', type=number(1, 10000, True), metavar='MILLISECONDS', help='Duration for window open/close and workspace transitions, 1–10000 ms')
    p.add_argument('--windows', choices=WINDOW_STYLES, help='slide: from an edge; popin: grow; gnome/gnomed: grow with vertical movement (aliases)')
    p.add_argument('--workspaces', choices=WORKSPACE_STYLES, help='slide: horizontal; slidevert: vertical; fade: crossfade; slidefade/slidefadevert: combine movement and fade')
    p.add_argument('--window-direction', choices=('auto', 'top', 'bottom', 'left', 'right'), help='Slide direction; requires --windows slide')
    p.add_argument('--window-size', type=number(0, 100, True), metavar='PERCENT', help='Starting size, 0–100; requires --windows popin')
    p.add_argument('--workspace-distance', type=number(0, 100, True), metavar='PERCENT', help='Travel distance, 0–100; requires a sliding --workspaces style')
    p.epilog = ('Styles and durations preserve existing branch enable states and easing.\n'
                'Windows means open/close; workspaces includes special workspaces. Layers,\n'
                'window movement, fades and border rotation are not adjusted. Spring curves\n'
                'control their own timing: --duration requires a timed (bezier) curve.\n\n'
                'Examples:\n'
                '  agentoo desktop animations --enabled on\n'
                '  agentoo desktop animations --windows slide --window-direction left\n'
                '  agentoo desktop animations --windows popin --window-size 80 --duration 250\n'
                '  agentoo desktop animations --workspaces slidefadevert --workspace-distance 30\n\n'
                'Exit 0: success; 1: operational failure; 2: invalid arguments.')
    p = parsers['shadows']
    p.add_argument('--enabled', choices=('on', 'off'), help='Enable shadows; appearance adjustments do not enable them')
    p.add_argument('--size', type=number(0, 100, True), metavar='PIXELS', help='Shadow range, 0–100')
    p.add_argument('--opacity', type=number(0, 100), metavar='PERCENT', help='Shadow opacity, 0–100; 0 is invisible')
    p.add_argument('--color', type=opaque_color, metavar='COLOR', help='Shadow color, quoted #RRGGBB; preserves opacity')
    p.add_argument('--offset-x', type=number(-250, 250, True), metavar='PIXELS', help='Horizontal offset, -250–250')
    p.add_argument('--offset-y', type=number(-250, 250, True), metavar='PIXELS', help='Vertical offset, -250–250')
    p = parsers['dimming']
    p.add_argument('--enabled', choices=('on', 'off'), help='Dim unfocused windows')
    p.add_argument('--strength', type=number(0, 100), metavar='PERCENT', help='Inactive-window darkening, 0–100; does not set modal dimming strength')
    p.add_argument('--modal', choices=('on', 'off'), help='Dim modal parents by 50%% of remaining brightness, independently of --enabled')
    return parsers


def validate(args, parser):
    values = {k: v for k, v in vars(args).items() if k not in ('command', 'reset', 'appearance_file') and v is not None}
    from desktop_state import check_file_args
    check_file_args(args, parser, bool(values))
    if args.reset and values:
        parser.error('--reset cannot be combined with adjustments')
    if args.command == 'animations':
        if args.window_direction is not None and args.windows != 'slide':
            parser.error('--window-direction requires --windows slide')
        if args.window_size is not None and args.windows != 'popin':
            parser.error('--window-size requires --windows popin')
        if args.workspace_distance is not None and (args.workspaces is None or not args.workspaces.startswith('slide')):
            parser.error('--workspace-distance requires a sliding --workspaces style')
    return values


def state_path():
    from desktop_state import state_path as shared_path
    return shared_path()


def read_state(path, reset_group=None, selected=None):
    from desktop_state import read
    data = {k: v for k, v in read(path).items() if k in COMMANDS and k != reset_group and (selected is None or k == selected)}
    return validate_sections(data)


def validate_sections(data, *, partial=False):
    try:
        root = ArgumentParser()
        parsers = add_parsers(root.add_subparsers())
        if not isinstance(data, dict) or set(data) - set(COMMANDS):
            raise ValueError('unknown effect')
        result = {}
        for group, values in data.items():
            if not isinstance(values, dict):
                raise ValueError('expected effect settings')
            actions = {a.dest: a for a in parsers[group]._actions if a.dest not in ('help', 'reset', 'appearance_file')}
            result[group] = {}
            for key, value in values.items():
                if key not in actions or type(value) not in (int, float, str):
                    raise ValueError(f'invalid {group}.{key}')
                action = actions[key]
                if action.choices and value not in action.choices:
                    raise ValueError(f'invalid {group}.{key}')
                result[group][key] = action.type(str(value)) if action.type else value
        animation = result.get('animations', {})
        if 'window_direction' in animation and (not partial or 'windows' in animation) and animation.get('windows') != 'slide':
            raise ValueError('window_direction requires windows: slide')
        if 'window_size' in animation and (not partial or 'windows' in animation) and animation.get('windows') != 'popin':
            raise ValueError('window_size requires windows: popin')
        if 'workspace_distance' in animation and (not partial or 'workspaces' in animation) and not animation.get('workspaces', '').startswith('slide'):
            raise ValueError('workspace_distance requires a sliding workspaces style')
        return result
    except (ValueError, TypeError, argparse.ArgumentTypeError) as error:
        raise RuntimeError(f'Invalid appearance settings: {error}') from error


def live_animations():
    nodes = {v['name']: v for v in json.loads(hyprctl('-j', 'animations'))[0]}
    result = {}
    for name in WINDOW_NODES + WORKSPACE_NODES:
        node = name
        while not nodes[node]['overridden'] and node in PARENTS:
            node = PARENTS[node]
        result[name] = {k: nodes[node][k] for k in ('enabled', 'speed', 'bezier', 'style')}
    return result


def animation_update(previous, values):
    updated = dict(previous)
    if 'windows' in values:
        if values['windows'] != 'slide':
            updated.pop('window_direction', None)
        if values['windows'] != 'popin':
            updated.pop('window_size', None)
    if 'workspaces' in values and not values['workspaces'].startswith('slide'):
        updated.pop('workspace_distance', None)
    updated.update(values)
    return updated


def show(data, group):
    values = data.get(group, {})
    report = {}
    if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
        try:
            text = hyprctl('repl', 'return agentoo_effects_report and agentoo_effects_report() or ""')
            report = dict(line.split('\t', 1) for line in text.splitlines() if '\t' in line)
        except RuntimeError as error:
            print(f'agentoo desktop: {error}', file=sys.stderr)
    root = ArgumentParser()
    parser = add_parsers(root.add_subparsers())[group]
    print(group.capitalize() + ':')
    for action in parser._actions:
        key = action.dest
        if key in ('help', 'reset', 'appearance_file'):
            continue
        saved = values.get(key)
        if isinstance(saved, (int, float)):
            unit = ' ms' if key == 'duration' else ' deg' if key.endswith('_angle') else '%' if key in ('opacity', 'strength', 'window_size', 'workspace_distance') else '' if key == 'power' else ' px'
            saved = f'{saved:g}{unit}'
        current = report.get(f'{group}.{key}')
        if saved is not None:
            print(f'  {key.replace("_", "-")}: {saved} (saved override)' + (f'; current: {current}' if current is not None else '; current: unavailable'))
        else:
            print(f'  {key.replace("_", "-")}: {current if current is not None else "unavailable"} (configured default)')
    if group == 'animations':
        try:
            live = live_animations() if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE') else {}
        except (RuntimeError, ValueError, KeyError, TypeError) as error:
            live = {}
            print(f'agentoo desktop: cannot query animation branches: {error}', file=sys.stderr)
        for name in WINDOW_NODES + WORKSPACE_NODES:
            branch = live.get(name)
            source = 'current branch'
            if branch:
                print(f'  {name}: {branch["style"] or "default"}, {branch["speed"] * 100:g} ms, '
                      f'{branch["bezier"]}, {"on" if branch["enabled"] else "off"} ({source}{"; current unavailable" if not live else ""})')
            else:
                print(f'  {name}: unavailable (configured default)')
        print('Use --help for styles, parameters and examples. The master switch controls all animations.')
    if group in ('animations', 'shadows'):
        print('Appearance adjustments do not change the master enable setting.')
    if group == 'dimming':
        print('Strength controls inactive windows. Modal dimming adds 50% of remaining brightness.')


def reload_settings():
    result = hyprctl('reload', 'config-only')
    if result != 'ok':
        raise RuntimeError('Hyprland reload failed: ' + result)
    errors = hyprctl('configerrors')
    if errors:
        raise RuntimeError('Hyprland configuration errors: ' + errors)


def run(args, directory, atomic_write, parser):
    values = validate(args, parser)
    if not args.reset and not values and getattr(args, 'appearance_file', None) is None:
        show(read_state(directory / 'appearance.json', selected=args.command), args.command)
        return 0
    from desktop_state import update
    return update(args, directory, atomic_write, parser)


def settings():
    data = read_state(state_path())
    lines = []
    for group, values in data.items():
        for key, value in values.items():
            lines.append(f'{group}\t{key}\t{value}')
    print('\n'.join([*lines, 'end']))


if __name__ == '__main__':
    try:
        if sys.argv[1:] != ['settings']:
            raise RuntimeError('Private helper: expected settings')
        settings()
    except (OSError, RuntimeError) as error:
        print(f'agentoo desktop: {error}', file=sys.stderr)
        raise SystemExit(1)
