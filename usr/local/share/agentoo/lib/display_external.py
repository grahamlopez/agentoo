"""Control external monitors through ddcutil, independently of laptop backlights."""
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

DRM = Path('/sys/class/drm')
DELL_LAYOUTS = {
    'off': 0x00,
    '50-50': 0x24,
    '25-75': 0x29,
    '75-25': 0x2A,
    '33-67': 0x2D,
    '67-33': 0x2E,
    'pip-small': 0x21,
    'pip-large': 0x22,
}
DELL_SECONDARY_INPUTS = {'thunderbolt': 0x6739, 'hdmi1': 0x6731}
DELL_AUDIO_SOURCES = {'window1': 0xF1, 'window2': 0xF2}
DELL_USB_TARGETS = {'thunderbolt': 1, 'hdmi1': 4}


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
        ('layout', 'Read or select a mapped Dell U5226KW PiP/PbP layout'),
        ('pip-position', 'Advance the Dell U5226KW PiP inset clockwise'),
        ('sub-input', 'Read or select the Dell U5226KW secondary video input'),
        ('audio-source', 'Read or select the Dell U5226KW audio window'),
        ('speakers', 'Read or enable/disable Dell U5226KW speakers'),
        ('usb', 'Read or switch the Dell U5226KW shared USB target'),
    ):
        child = sub.add_parser(name, help=description)
        selector = child.add_mutually_exclusive_group()
        selector.add_argument('--output', metavar='CONNECTOR',
                             help='DRM connector name, for example card0-DP-4').completion = 'external_outputs'
        selector.add_argument('--bus', type=argument_type(bus_number), metavar='NUMBER',
                             help='Explicit I2C bus number; rediscover after reconnecting')
        if name == 'usb':
            child.add_argument('value', nargs='?', choices=('next', *DELL_USB_TARGETS), help='Omit to read the active USB target')
            child.epilog = ('Uses existing OSD USB assignments. Switching requires a mapped active two-window '
                            'layout with Thunderbolt and HDMI1. Shared USB devices move to the selected host; '
                            'the switch action is sent at most once.')
        elif name == 'audio-source':
            child.add_argument('value', nargs='?', choices=tuple(DELL_AUDIO_SOURCES), help='Omit to read the selected audio window')
        elif name == 'speakers':
            child.add_argument('value', nargs='?', choices=('on', 'off'), help='Omit to read; corresponds to Speaker in the Dell OSD')
        elif name == 'layout':
            child.add_argument('value', nargs='?', choices=tuple(DELL_LAYOUTS), help='Omit to read the layout')
            child.epilog = 'Dell U5226KW only. Writes once without immediate verification, then checks settled readback.'
        elif name == 'pip-position':
            child.add_argument('value', choices=('next',), help='Cycle top left → top right → bottom right → bottom left')
            child.epilog = 'Requires small or large PiP. Current position is not readable; an absolute position cannot be selected.'
        elif name == 'sub-input':
            child.add_argument('value', nargs='?', choices=tuple(DELL_SECONDARY_INPUTS), help='Omit to read; changes only the secondary input')
            child.epilog = 'Dell U5226KW only, in a mapped active PiP/PbP layout. Main input is unchanged; this is not a swap.'
        elif name in ('brightness', 'volume'):

            child.add_argument('value', nargs='?', type=argument_type(level), metavar='LEVEL',
                               help='0..100 in monitor units, or up/down by 5; omit to read')
            if name == 'volume':
                child.epilog = ('Dell U5226KW volume is decoded to 0..100 and preserves Speaker On/Off. '
                                'Its firmware briefly enables speakers on level writes; Off is restored immediately afterward.')
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


def dell_u5226kw_connected(bus):
    for output in connected_outputs():
        if (output / 'ddc').resolve().name != f'i2c-{bus}':
            continue
        try:
            edid = (output / 'edid').read_bytes()
        except OSError:
            continue
        # EDID manufacturer DEL, product 0x439e. Do not apply vendor mappings
        # to another monitor just because the connector/bus number matches.
        if len(edid) >= 128 and edid[8:12] == bytes.fromhex('10ac9e43'):
            return True
    return False

def require_dell_u5226kw(bus):
    if dell_u5226kw_connected(bus):
        return
    raise RuntimeError('This named control requires a connected Dell U5226KW (EDID DEL/439e); '
                       'use capabilities and explicit VCP access for other monitors')

def read_feature(command, code, *, maximum=False):
    try:
        result = subprocess.run([*command, 'getvcp', code, '--terse'],
                                capture_output=True, text=True, check=False, timeout=5)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f'Timed out reading VCP {code}') from None
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f'Cannot read VCP {code}')
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) < 4 or fields[:2] != ['VCP', code]:
            continue
        try:
            if fields[2] == 'C' and len(fields) == 5:
                return int(fields[4 if maximum else 3])
            if fields[2] == 'SNC' and len(fields) == 4:
                if maximum:
                    raise RuntimeError(f'VCP {code} response does not expose maximum/status bytes')
                return int(fields[3].removeprefix('x'), 16)
            if fields[2] == 'CNC' and len(fields) == 7:
                index = 3 if maximum else 5
                return (int(fields[index].removeprefix('x'), 16) << 8) | int(fields[index + 1].removeprefix('x'), 16)
        except ValueError:
            break
    raise RuntimeError(f'Unexpected response for VCP {code}: {result.stdout.strip()}')

def write_switch(command, code, value):
    # Reconfiguration can remove DDC during immediate verification. Never
    # resend an action automatically; doing so could cycle it a second time.
    result = subprocess.run([*command, 'setvcp', code, str(value),
                             '--permit-unknown-feature', '--noverify'], check=False)
    if result.returncode:
        raise RuntimeError(f'VCP {code} write returned {result.returncode}; the panel may have applied it. '
                           'Inspect the visible state and readback before retrying')

def wait_for_feature(command, code, expected, *, maximum=False):
    detail = 'no response'
    for _ in range(8):
        time.sleep(0.4)
        try:
            actual = read_feature(command, code, maximum=maximum)
            if actual == expected:
                return
            detail = f'read 0x{actual:04X}, expected 0x{expected:04X}'
        except RuntimeError as error:
            detail = str(error)
    raise RuntimeError(f'Write sent but settled VCP {code} readback was not confirmed: {detail}. '
                       'No write was retried; inspect the panel before retrying')

def run_dell(args, command, bus):
    require_dell_u5226kw(bus)
    action = args.external_action
    if action == 'layout':
        if args.value is not None:
            expected = DELL_LAYOUTS[args.value]
            write_switch(command, 'E9', expected)
            wait_for_feature(command, 'E9', expected)
        else:
            expected = read_feature(command, 'E9')
        name = next((name for name, value in DELL_LAYOUTS.items() if value == expected), 'unknown')
        print(f'{name} (0x{expected:02X})')
    elif action == 'pip-position':
        if read_feature(command, 'E9') not in (0x21, 0x22):
            raise RuntimeError('Position cycling requires pip-small or pip-large')
        write_switch(command, 'E9', 0x02)
        print('PiP position-cycle command sent; position is not readable through the mapped registers.', file=sys.stderr)
    elif action == 'usb':
        return run_dell_usb(args, command)
    elif action == 'sub-input':
        if args.value is not None:
            layout = read_feature(command, 'E9')
            if layout == 0 or layout not in DELL_LAYOUTS.values():
                raise RuntimeError('Secondary input selection requires a mapped active PiP/PbP layout')
            expected = DELL_SECONDARY_INPUTS[args.value]
            write_switch(command, 'E8', expected)
            wait_for_feature(command, 'E8', expected)
        else:
            expected = read_feature(command, 'E8')
        name = next((name for name, value in DELL_SECONDARY_INPUTS.items() if value == expected), 'unknown')
        print(f'{name} (0x{expected:04X})')
    else:
        code, values = (('63', DELL_AUDIO_SOURCES) if action == 'audio-source'
                        else ('8D', {'on': 2, 'off': 1}))
        if args.value is not None:
            expected = values[args.value]
            write_switch(command, code, expected)
            wait_for_feature(command, code, expected)
        else:
            expected = read_feature(command, code)
        name = next((name for name, value in values.items() if value == expected), 'unknown')
        print(f'{name} (0x{expected:02X})')
    return 0


def run_dell_usb(args, command):
    # E7 current bytes hold the USB/video assignment table. Its MH status byte
    # identifies the active input; observed 1=Thunderbolt and 4=HDMI1.
    status = read_feature(command, 'E7', maximum=True)
    active = status >> 8
    if args.value is not None:
        if active not in DELL_USB_TARGETS.values():
            raise RuntimeError(f'Unmapped active USB target 0x{active:02X}; no switch sent')
        target = (4 if active == 1 else 1) if args.value == 'next' else DELL_USB_TARGETS[args.value]
        if target != active:
            layout = read_feature(command, 'E9')
            main = read_feature(command, '60')
            secondary_raw = read_feature(command, 'E8')
            secondary = {0x6739: 0x19, 0x6731: 0x11}.get(secondary_raw)
            if layout == 0 or layout not in DELL_LAYOUTS.values() or {main, secondary} != {0x19, 0x11}:
                raise RuntimeError('USB switching requires a mapped active two-window layout with '
                                   'Thunderbolt and HDMI1; no switch sent')
            write_switch(command, 'E7', 0xFF00)
            wait_for_feature(command, 'E7', (target << 8) | (status & 0xFF), maximum=True)
            active = target
    name = next((name for name, value in DELL_USB_TARGETS.items() if value == active), 'unknown')
    print(f'{name} (status 0x{active:02X})')
    return 0


def run_dell_volume(args, command):
    raw = read_feature(command, '62')
    current = raw & 0x7F
    speaker_off = bool(raw & 0x80)
    if raw & ~0xFF or current > 100:
        raise RuntimeError(f'Unexpected Dell volume encoding: 0x{raw:04X}; no volume write sent')
    target = current
    if args.value is not None:
        if args.value in ('up', 'down'):
            target = max(0, min(100, current + (5 if args.value == 'up' else -5)))
        else:
            target = int(args.value)
        if target != current:
            # Dell ignores the mute flag on volume writes and ordinary levels
            # enable its speakers. Restore the previous Off state in the same
            # invocation. This cannot promise there is no brief unmuted interval.
            change = [*command, 'setvcp', '62', str(target)]
            if speaker_off:
                change += ['8D', '1']
            change += ['--noverify']
            result = subprocess.run(change, check=False)
            if result.returncode:
                if speaker_off:
                    restore = subprocess.run([*command, 'setvcp', '8D', '1', '--noverify'], check=False)
                    if restore.returncode:
                        raise RuntimeError('Volume write failed and Speaker Off could not be restored; inspect the panel')
                raise RuntimeError('Volume write failed; read the level and speaker state before retrying')
            wait_for_feature(command, '62', target | (0x80 if speaker_off else 0))
    print(f'{target}/100 (speakers {"off" if speaker_off else "on"})')
    return 0

def run(args, parser):
    if not shutil.which('ddcutil'):
        raise RuntimeError('ddcutil is not installed; install app-misc/ddcutil (see docs/displays.md)')
    command = ['ddcutil']
    action = args.external_action
    if action == 'list':
        command += ['detect']
    else:
        bus = select_bus(args)
        command += ['--bus', str(bus)]
        if action == 'volume' and dell_u5226kw_connected(bus):
            return run_dell_volume(args, command)
        if action in ('layout', 'pip-position', 'sub-input', 'audio-source', 'speakers', 'usb'):
            return run_dell(args, command, bus)
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
