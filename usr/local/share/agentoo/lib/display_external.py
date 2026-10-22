"""Control external monitors through ddcutil, independently of laptop backlights."""
from pathlib import Path
import re
import shutil
import subprocess

DRM = Path('/sys/class/drm')


def bus_number(value):
    try:
        number = int(value, 10)
    except ValueError:
        raise ValueError('expected a nonnegative decimal bus number') from None
    if number < 0:
        raise ValueError('expected a nonnegative decimal bus number')
    return number


def feature_code(value):
    if not re.fullmatch(r'(?:0[xX])?[0-9a-fA-F]{1,2}', value):
        raise ValueError('expected a hexadecimal VCP feature code (00..FF)')
    return f'{int(value, 16):02X}'


def vcp_value(value):
    try:
        number = int(value, 16 if value.lower().startswith('0x') else 10)
    except ValueError:
        raise ValueError('expected a decimal or 0x-prefixed value (0..65535)') from None
    if not 0 <= number <= 65535:
        raise ValueError('expected a value in 0..65535')
    return str(number)


def level(value):
    if value in ('up', 'down'):
        return value
    if not value.isdecimal() or not 0 <= int(value) <= 100:
        raise ValueError('expected 0..100, up, or down')
    return str(int(value))


def argument_type(function):
    # argparse expects ArgumentTypeError for custom diagnostics, not tracebacks.
    import argparse
    def parse(value):
        try:
            return function(value)
        except ValueError as error:
            raise argparse.ArgumentTypeError(str(error)) from None
    return parse


def configure_parser(parser):
    parser.description = __doc__
    parser.epilog = ('Requires ddcutil, i2c-dev and access to the display I2C device. '
                     'Automatically selects only when one connected external DDC connector exists. '
                     'Values and feature support depend on the monitor; inspect capabilities first.')
    sub = parser.add_subparsers(dest='external_action', required=True)
    sub.add_parser('list', help='Detect monitors and report DDC access using ddcutil')
    for name, description in (
        ('capabilities', 'Read the monitor-reported feature codes and values'),
        ('brightness', 'Read or change monitor brightness (VCP 10)'),
        ('volume', 'Read or change monitor speaker volume (VCP 62)'),
        ('mute', 'Read or change monitor audio mute (VCP 8D)'),
        ('input', 'Read or select a video input (VCP 60)'),
        ('get', 'Read a VCP feature, including vendor-specific features'),
        ('set', 'Write an explicitly specified VCP feature and value'),
    ):
        child = sub.add_parser(name, help=description)
        selector = child.add_mutually_exclusive_group()
        selector.add_argument('--output', metavar='CONNECTOR',
                             help='DRM connector name, for example card0-DP-4').completion = 'external_outputs'
        selector.add_argument('--bus', type=argument_type(bus_number), metavar='NUMBER',
                             help='Explicit I2C bus number; rediscover after reconnecting')
        if name in ('brightness', 'volume'):
            child.add_argument('value', nargs='?', type=argument_type(level), metavar='LEVEL',
                               help='0..100 in monitor units, or up/down by 5; omit to read')
        elif name == 'mute':
            child.add_argument('value', nargs='?', choices=('on', 'off'), help='Omit to read')
        elif name == 'input':
            child.add_argument('value', nargs='?', type=argument_type(vcp_value), metavar='VALUE',
                               help='Monitor input value, decimal or 0x hex; omit to read')
        elif name in ('get', 'set'):
            child.add_argument('code', type=argument_type(feature_code), help='Hexadecimal VCP code, e.g. 10 or E9')
            if name == 'set':
                child.add_argument('value', type=argument_type(vcp_value), help='Decimal or 0x hex value')
        if name in ('set', 'input'):
            child.add_argument('--no-verify', action='store_true',
                               help='Skip readback for writes that disconnect or cannot be read back')
    return parser


def connected_outputs():
    outputs = []
    for path in sorted(DRM.glob('card*-*')):
        if re.match(r'card\d+-(eDP|LVDS|DSI)-', path.name):
            continue
        try:
            if (path / 'status').read_text().strip() == 'connected' and (path / 'ddc').exists():
                outputs.append(path)
        except OSError:
            continue
    return outputs


def select_bus(args):
    if args.bus is not None:
        return args.bus
    outputs = connected_outputs()
    if args.output is not None:
        outputs = [p for p in outputs if p.name == args.output]
        if not outputs:
            raise RuntimeError(f'No connected external DDC output: {args.output}')
    if not outputs:
        raise RuntimeError('No connected external DDC output; check the cable or use --bus NUMBER')
    if len(outputs) != 1:
        raise RuntimeError('Multiple external outputs; select --output: ' + ', '.join(p.name for p in outputs))
    name = (outputs[0] / 'ddc').resolve().name
    if not re.fullmatch(r'i2c-\d+', name):
        raise RuntimeError(f'Cannot determine I2C bus for {outputs[0].name}; use --bus NUMBER')
    return int(name[4:])



def check_relative_volume(command):
    result = subprocess.run([*command, 'getvcp', '62', '--terse'],
                            capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'Cannot read monitor volume')
    match = re.search(r'^VCP 62 C (\d+) (\d+)$', result.stdout, re.MULTILINE)
    if not match or not 0 <= int(match[1]) <= int(match[2]) <= 100:
        raise RuntimeError('Monitor reports a nonstandard volume encoding; relative volume is unavailable. '
                           'Inspect external get 62 and use the OSD until its encoding is established.')


def run(args, parser):
    if not shutil.which('ddcutil'):
        raise RuntimeError('ddcutil is not installed; install app-misc/ddcutil (see docs/displays.md)')
    command = ['ddcutil']
    action = args.external_action
    if action == 'list':
        command += ['detect']
    else:
        command += ['--bus', str(select_bus(args))]
        if action == 'capabilities':
            command += ['capabilities']
        else:
            code = {'brightness': '10', 'volume': '62', 'mute': '8D', 'input': '60'}.get(action)
            if code is None:
                code = args.code
            value = getattr(args, 'value', None)
            if value is None:
                command += ['getvcp', code]
            else:
                if action == 'volume' and value in ('up', 'down'):
                    check_relative_volume(command)
                if action == 'mute':
                    value = '1' if value == 'on' else '2'
                command += ['setvcp', code]
                # Raw set is an explicit request, including unknown vendor codes.
                command += (['+' if value == 'up' else '-', '5'] if value in ('up', 'down') else [value])
                if action == 'set':
                    command += ['--permit-unknown-feature']
                if getattr(args, 'no_verify', False):
                    command += ['--noverify']
                else:
                    command += ['--verify']
    # Preserve ddcutil's output and exit status. No sudo or automatic writes on reads.
    return subprocess.run(command, check=False).returncode
