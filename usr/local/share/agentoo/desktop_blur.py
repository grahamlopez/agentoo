"""Blur preferences and read-only diagnostics for Hyprland 0.56.2.

The private `rules` entry point emits validated data, never executable Lua.
Saved choices are distinct from the compositor's authored defaults.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time

sys.dont_write_bytecode = True
from desktop_common import authored_hypr_paths, hyprctl

GROUPS = ('all', 'kitty', 'browser')
STATES = ('focused', 'unfocused')
LIMITS = {'size': 40, 'passes': 10}


def size(value):
    return integer(value, 'size')


def passes(value):
    return integer(value, 'passes')


def integer(value, name):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f'{name} must be an integer from 1 to {LIMITS[name]}') from None
    if not 1 <= number <= LIMITS[name]:
        raise argparse.ArgumentTypeError(f'{name} must be an integer from 1 to {LIMITS[name]}')
    return number


def add_parser(commands):
    parser = commands.add_parser('blur', help='Show or adjust window background blur',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Show or adjust window background blur.\n\n'
                    'All options are optional. Without options, show current settings.\n\n'
                    'Blur is off by default. To enable it, set --focused on and/or\n'
                    '--unfocused on. Changing --size or --passes alone does not enable blur.\n\n'
                    'Examples:\n'
                    '  agentoo desktop blur\n'
                    '  agentoo desktop blur --focused on --unfocused on\n'
                    '  agentoo desktop blur --focused on --unfocused on --size 3 --passes 1\n\n'
                    'Changes apply immediately and persist across desktop sessions.\n'
                    'Blur does not change transparency.',
        epilog='Focused and unfocused settings can be changed independently.\n'
               'Omitted settings remain unchanged. Blur is off unless enabled.\n\n'
               'Setting all clears category overrides for the supplied focus states.\n'
               'Kitty/browser overrides take precedence over shared values.\n'
               'Category reset restores inheritance; full reset removes all overrides,\n'
               'including strength, and restores configured defaults.\n\n'
               'Size/passes are global: use --window all. Changing strength does not\n'
               'enable blur. Omitted strength values retain configured defaults.\n\n'
               'Suggested economical starting point: size 3, passes 1.\n'
               'Blur off provides the greatest power saving.\n'
               'Panels, menus, notifications, and workspace-wide blur are not configured.\n'
               'Applications must have transparent content and permit compositor blur.\n\n'
               '--reset and --diagnose cannot accompany adjustment options.\n'
               '--diagnose makes no changes and does not measure GPU power.\n'
               'Troubleshooting: /usr/local/share/agentoo/docs/gui-base.md#window-blur\n\n'
               'More examples:\n'
               '  agentoo desktop blur --focused on --unfocused off\n'
               '  agentoo desktop blur --window browser --focused off --unfocused off\n'
               '  agentoo desktop blur --diagnose\n'
               '  agentoo desktop blur --reset\n\n'
               'Exit 0: success; 1: operational failure; 2: invalid arguments.')
    parser.add_argument('--window', choices=GROUPS, default='all', help='Windows to show or adjust (default: all)')
    parser.add_argument('--focused', choices=('on', 'off'), help='Enable or disable blur for focused windows')
    parser.add_argument('--unfocused', choices=('on', 'off'), help='Enable or disable blur for unfocused windows')
    parser.add_argument('--size', type=size, metavar='PIXELS', help='Shared blur size, from 1 to 40; does not enable blur')
    parser.add_argument('--passes', type=passes, metavar='COUNT', help='Shared blur passes, from 1 to 10; does not enable blur')
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--reset', action='store_true', help='Remove selected overrides')
    actions.add_argument('--diagnose', action='store_true', help='Show version, renderer/GPU, settings, compatibility, and conflicts')
    from desktop_state import file_option
    file_option(parser, child=True)
    return parser


def validate(args, parser):
    adjustments = any(getattr(args, name) is not None for name in (*STATES, 'size', 'passes'))
    from desktop_state import check_file_args
    check_file_args(args, parser, adjustments)
    if (args.reset or args.diagnose) and adjustments:
        parser.error('--reset and --diagnose cannot be combined with adjustment options')
    if args.window != 'all' and (args.size is not None or args.passes is not None):
        parser.error('--size and --passes apply globally; use --window all')


def state_path():
    from desktop_state import state_path as shared_path
    return shared_path()


def read_state(path):
    from desktop_state import section
    return validate_data(section('blur', path))


def validate_data(data):
    if not isinstance(data, dict) or set(data) - {*GROUPS, 'strength'}:
        raise RuntimeError(f'Invalid blur groups in blur section')
    for group, values in data.items():
        allowed = LIMITS if group == 'strength' else STATES
        if not isinstance(values, dict) or set(values) - set(allowed):
            raise RuntimeError(f'Invalid blur settings for {group} in blur section')
        for key, value in values.items():
            if group == 'strength':
                valid = type(value) is int and 1 <= value <= LIMITS[key]
            else:
                valid = type(value) is bool
            if not valid:
                raise RuntimeError(f'Invalid blur value for {group}.{key} in blur section')
    return data


def revision(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def adjusted(data, args):
    if args.reset and args.window == 'all':
        return {}
    data = {key: dict(values) for key, values in data.items()}
    if args.reset:
        data.pop(args.window, None)
    else:
        for focus in STATES:
            value = getattr(args, focus)
            if value is None:
                continue
            data.setdefault(args.window, {})[focus] = value == 'on'
            if args.window == 'all':
                for group in ('kitty', 'browser'):
                    data.get(group, {}).pop(focus, None)
        for name in LIMITS:
            value = getattr(args, name)
            if value is not None:
                data.setdefault('strength', {})[name] = value
    return {key: values for key, values in data.items() if values}


def conflicts():
    # Scalar blur configuration is an authored default. Window-rule effects can
    # compete with the managed rules; report rather than rewrite those files.
    found = []
    for path in authored_hypr_paths():
        for number, line in enumerate(path.read_text().splitlines(), 1):
            line = re.split(r'--|#', line, maxsplit=1)[0]
            if re.search(r'\b(no_blur|noblur|force_rgbx|opaque)\s*[= ,]', line):
                found.append(f'{path}:{number}')
    return found


def check_conflicts(data):
    """Only saved window rules can compete with authored window effects.

    Used before saving and when loading configuration. Strength-only state and
    a full reset do not install window rules, so neither is blocked by them.
    """
    if any(data.get(group) for group in GROUPS):
        found = conflicts()
        if found:
            raise RuntimeError('Conflicting blur rules; edit them before adjusting:\n' + '\n'.join(found))


def live_report(*, timeout=10):
    result = hyprctl('repl', 'return agentoo_blur_report and agentoo_blur_report() or "unavailable"', timeout=timeout)
    report = {}
    for line in result.splitlines():
        fields = line.split('\t')
        if len(fields) == 2:
            report[fields[0]] = fields[1]
    if report.get('format') != 'agentoo-blur-v2':
        raise RuntimeError('Agentoo blur integration is unavailable or outdated; reload the shared Hyprland configuration')
    required = ('revision', 'baseline', 'baseline_size', 'baseline_passes',
                'option.enabled', 'option.size', 'option.passes')
    missing = [key for key in required if key not in report or report[key] == 'unavailable']
    if missing:
        raise RuntimeError('Incomplete compositor snapshot: ' + ', '.join(missing))
    return report


def show(data, selected, report=None):
    print('Saved blur preferences (using configured defaults where unset):')
    print(f'{"WINDOW":<10} {"FOCUSED":<32} UNFOCUSED')
    for group in GROUPS if selected == 'all' else (selected,):
        cells = []
        for focus in STATES:
            value = data.get(group, {}).get(focus, data.get('all', {}).get(focus))
            source = 'override' if focus in data.get(group, {}) else 'inherited: all'
            if value is None:
                source = 'configured default'
                if report:
                    value = report['baseline'] == 'on'
            label = ('on' if value else 'off') if value is not None else 'unknown'
            cells.append(f'{label} ({source})')
        print(f'{group:<10} {cells[0]:<32} {cells[1]}')
    for name in LIMITS:
        value = data.get('strength', {}).get(name)
        source = 'override' if value is not None else 'configured default'
        if value is None and report:
            value = report['baseline_' + name]
        print(f'{name.capitalize()}: {value if value is not None else "unknown"} ({source})')
    if report:
        matches = report['revision'] == revision(data)
        print(f'Saved revision loaded in this session: {"yes" if matches else "no"}')
        print(f'Current blur engine: {report["option.enabled"]}')
        if not matches:
            print('agentoo desktop: warning: saved blur settings differ from this session; reload its configuration', file=sys.stderr)
    else:
        print('Configured defaults unavailable; Agentoo shared default is off for both focus states.')


def open_window_classes():
    clients = json.loads(hyprctl('-j', 'clients'))
    return ', '.join(sorted({client['class'] for client in clients if client.get('mapped', False)}))


def show_section(label, value):
    print(f'\n{label}:\n' + ('unavailable' if value is None else value or 'none'))


def diagnose(path, selected):
    """Read each source independently, then present the collected evidence."""
    errors = []

    def read(label, operation, *args):
        try:
            return operation(*args)
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
            errors.append(f'{label}: {error}')
            return None

    data = read('Saved preferences', read_state, path)
    report = read('Session snapshot', live_report)
    system = read('Compositor system report', hyprctl, 'systeminfo')
    config_errors = read('Configuration errors', hyprctl, 'configerrors')
    classes = read('Open window classes', open_window_classes)
    rule_conflicts = read('Potential conflicting rules', conflicts)

    print('Blur diagnostics (read-only; no GPU load or power measurement)')
    if data is None:
        print('Saved blur preferences: unavailable')
    else:
        show(data, selected, report)
    options = None if report is None else '\n'.join(
        f'  {key.removeprefix("option.")}: {value}'
        for key, value in sorted(report.items()) if key.startswith('option.'))
    show_section('Effective compositor options', options)
    show_section('Compositor system report (includes version and GPU inventory)', system)
    show_section('Configuration errors', config_errors)
    show_section('Open window classes', classes)
    show_section('Potential conflicting rules', None if rule_conflicts is None else '\n'.join(rule_conflicts))
    print('\nClient blur regions and actual rendering are not verified by this API.')
    print('Troubleshooting: /usr/local/share/agentoo/docs/gui-base.md#window-blur')
    for error in errors:
        print(f'agentoo desktop: {error}', file=sys.stderr)
    return 1 if errors or config_errors else 0


def require_integration(recover=False):
    if not os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
        raise RuntimeError('A running Hyprland session is required to change blur')
    if recover:
        hyprctl('version')
        return
    live_report()
    errors = hyprctl('configerrors')
    if errors:
        raise RuntimeError('Fix Hyprland configuration errors before changing blur: ' + errors)


def reload_saved(data):
    # One budget covers the reload request and every verification request.
    deadline = time.monotonic() + 2

    def remaining():
        timeout = deadline - time.monotonic()
        if timeout <= 0:
            raise RuntimeError('Timed out waiting for Hyprland to load blur settings')
        return timeout

    result = hyprctl('reload', 'config-only', timeout=remaining())
    if result != 'ok':
        raise RuntimeError('Hyprland reload failed: ' + result)
    while True:
        errors = hyprctl('configerrors', timeout=remaining())
        problem = 'Hyprland did not load the new blur settings'
        try:
            report = live_report(timeout=remaining())
        except RuntimeError as error:
            report = {}
            problem = str(error)
        if report.get('revision') == revision(data):
            if errors:
                raise RuntimeError('Hyprland configuration errors: ' + errors)
            return report
        # Reload can be queued. In particular, full reset must wait for stale
        # errors from a damaged saved file to clear, rather than restoring it.
        if time.monotonic() >= deadline:
            raise RuntimeError('Hyprland configuration errors: ' + errors if errors else problem)
        time.sleep(min(0.05, remaining()))


def save(args, directory, atomic_write):
    from desktop_state import update
    args.command = 'blur'
    return update(args, directory, atomic_write)


def run(args, directory, atomic_write):
    path = directory / 'appearance.json'
    if args.diagnose:
        return diagnose(path, args.window)
    if args.reset or getattr(args, 'appearance_file', None) is not None or any(getattr(args, name) is not None for name in (*STATES, *LIMITS)):
        return save(args, directory, atomic_write)

    data = read_state(path)
    try:
        report = live_report()
    except RuntimeError:
        report = None
    show(data, args.window, report)
    for location in conflicts():
        print(f'agentoo desktop: warning: blur rule may conflict: {location}', file=sys.stderr)
    return 0


def rules():
    data = read_state(state_path())
    check_conflicts(data)
    for group in GROUPS:
        for focus, value in data.get(group, {}).items():
            print(group, focus, 'on' if value else 'off', sep='\t')
    for name, value in data.get('strength', {}).items():
        print('strength', name, value, sep='\t')
    print('revision', revision(data), sep='\t')
    print('end')


if __name__ == '__main__':
    try:
        if sys.argv[1:] != ['rules']:
            raise RuntimeError('Private helper: expected rules')
        rules()
    except (OSError, RuntimeError) as error:
        print(f'agentoo desktop: {error}', file=sys.stderr)
        raise SystemExit(1)
