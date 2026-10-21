"""Blur preferences and read-only diagnostics for Hyprland 0.56.2.

Saved choices are distinct from the compositor's authored defaults.
"""
import argparse
import json
import os
import re
import sys
import time

sys.dont_write_bytecode = True
from desktop.common import authored_hypr_paths, hyprctl

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
    feature = commands.add_parser('blur', help='Show or change window background blur',
        description='Without an action, show current blur settings. Blur is off by default.',
        epilog='Blur does not change transparency. Applications must have transparent content and permit compositor blur. '
               'Troubleshooting: /usr/local/share/agentoo/docs/desktop.md#window-blur')
    from desktop.state import file_option, window_option
    window_option(feature)
    feature.add_argument('--diagnose', action='store_true',
                         help='Show version, renderer/GPU, settings, compatibility and conflicts; makes no changes')
    actions = feature.add_subparsers(dest='action')
    parser = actions.add_parser('set', help='Apply and remember blur settings',
        description='Apply and remember blur settings. Omitted settings stay unchanged.',
        epilog='Changing strength alone does not enable blur. Size/passes require --window all. '
               'Setting all clears category overrides for supplied focus states; category overrides take precedence. '
               'An economical starting point is size 3, passes 1. Blur off saves the most power. '
               'Supply at least one adjustment or --file; --file cannot accompany adjustments '
               'or a kitty/browser window category.')
    window_option(parser, child=True)
    parser.add_argument('--focused', choices=('on', 'off'), help='Enable or disable blur for focused windows')
    parser.add_argument('--unfocused', choices=('on', 'off'), help='Enable or disable blur for unfocused windows')
    parser.add_argument('--size', type=size, metavar='PIXELS', help='Shared blur size, 1–40; does not enable blur')
    parser.add_argument('--passes', type=passes, metavar='COUNT', help='Shared blur passes, 1–10; does not enable blur')
    file_option(parser)
    clear = actions.add_parser('clear', help='Remove saved blur overrides',
        description='Remove saved blur overrides and apply configured defaults. '
                    'Clearing kitty/browser restores inheritance; all clears every override, including strength.')
    window_option(clear, child=True)
    return feature


def validate(args, parser):
    if args.diagnose and args.action is not None:
        parser.error('--diagnose cannot be combined with an action')
    if args.action == 'set' and args.window != 'all' and (args.size is not None or args.passes is not None):
        parser.error('--size and --passes apply globally; use --window all')


def state_path():
    from desktop.state import state_path as shared_path
    return shared_path()


def read_state(path):
    from desktop.state import section
    return section('blur', path)


def revision(data):
    from desktop.state import native
    return native('revision', data=data).strip()


def adjusted(data, args):
    data = {key: dict(values) for key, values in data.items()}
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
    print('Troubleshooting: /usr/local/share/agentoo/docs/desktop.md#window-blur')
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
    expected_revision = revision(data)
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
        if report.get('revision') == expected_revision:
            if errors:
                raise RuntimeError('Hyprland configuration errors: ' + errors)
            return report
        # Reload can be queued. In particular, full reset must wait for stale
        # errors from a damaged saved file to clear, rather than restoring it.
        if time.monotonic() >= deadline:
            raise RuntimeError('Hyprland configuration errors: ' + errors if errors else problem)
        time.sleep(min(0.05, remaining()))


def query(path, window):
    data = read_state(path)
    try:
        report = live_report()
    except RuntimeError:
        report = None
    show(data, window, report)
    for location in conflicts():
        print(f'agentoo desktop: warning: blur rule may conflict: {location}', file=sys.stderr)
    return 0
