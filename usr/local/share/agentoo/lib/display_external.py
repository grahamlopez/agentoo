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
DDC_TIMEOUT = 5
DELL_PIP_CYCLE = 0x02
DELL_USB_SWITCH = 0xFF00
DELL_MAIN_INPUTS = {'thunderbolt': 0x19, 'hdmi1': 0x11, 'hdmi2': 0x12, 'dp1': 0x0F, 'dp2': 0x13}
DELL_KVM_INPUTS = {'thunderbolt', 'hdmi1'}
DELL_SECONDARY_INPUTS = {'thunderbolt': 0x6739, 'hdmi1': 0x6731, 'hdmi2': 0x6732,
                         'dp1': 0x672F, 'dp2': 0x6733}
DELL_AUDIO_SOURCES = {'window1': 0xF1, 'window2': 0xF2}
DELL_USB_TARGETS = {'thunderbolt': 1, 'hdmi1': 4}
# VCP 8D names the mute state: 1=mute on, 2=mute off. The Dell OSD
# names the inverse state, Speaker: on=2, off=1.
MUTE_VALUES = {'on': 1, 'off': 2}
DELL_SPEAKER_VALUES = {'on': MUTE_VALUES['off'], 'off': MUTE_VALUES['on']}


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

def input_value(value):
    name = value.lower()
    return name if name in DELL_MAIN_INPUTS else vcp_value(value)


def secondary_value(value):
    if value in DELL_MAIN_INPUTS:
        if value not in DELL_SECONDARY_INPUTS:
            raise RuntimeError(f'Secondary input {value} has no verified mapping; no write sent')
        return DELL_SECONDARY_INPUTS[value]
    return int(value)


def main_value(value):
    return DELL_MAIN_INPUTS[value] if value in DELL_MAIN_INPUTS else int(value)


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
        child = sub.add_parser(name, help=description, aliases={'usb': ['kvm'], 'input': ['left'], 'sub-input': ['right']}.get(name, []))
        child.set_defaults(external_action=name)
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
            child.add_argument('value', nargs='?', choices=(*DELL_LAYOUTS, '100'), help='Omit to read; 100 is an alias for off')
            child.add_argument('--input', '--left', dest='layout_input',
                               type=argument_type(lambda v: 'active_kvm' if v.lower() == 'active_kvm' else input_value(v)),
                               help='Main/left source; active_kvm is available with off/100')
            child.add_argument('--sub-input', '--right', dest='layout_secondary', type=argument_type(input_value),
                               help='Secondary/right source (PiP: inset); requires an active layout')
            child.epilog = 'Dell U5226KW only. Sends each write once, then checks settled readback before continuing.'
        elif name == 'pip-position':
            child.add_argument('value', choices=('next',), help='Cycle top left → top right → bottom right → bottom left')
            child.epilog = 'Requires small or large PiP. Current position is not readable; an absolute position cannot be selected.'
        elif name == 'sub-input':
            child.add_argument('value', nargs='?', type=argument_type(input_value), help='Name or numeric VCP value; omit to read the secondary input')
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
            child.add_argument('value', nargs='?', type=argument_type(input_value), metavar='VALUE',
                               help='Dell input name or numeric VCP value; omit to read')
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
    encoding, current, maximum = _read_feature(command, '62')
    # SNC/CNC parsing is shared, but only continuous volume is safe for +/-.
    if encoding != 'C' or not 0 <= current <= maximum <= 100:
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
    _, current, limit = _read_feature(command, code)
    if maximum and limit is None:
        raise RuntimeError(f'VCP {code} response does not expose maximum/status bytes')
    return limit if maximum else current


def _read_feature(command, code):
    """Read once; return (encoding, current, maximum/status or None for SNC)."""
    try:
        result = subprocess.run([*command, 'getvcp', code, '--terse'],
                                capture_output=True, text=True, check=False, timeout=DDC_TIMEOUT)
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
                return 'C', int(fields[3]), int(fields[4])
            if fields[2] == 'SNC' and len(fields) == 4:
                return 'SNC', int(fields[3].removeprefix('x'), 16), None
            if fields[2] == 'CNC' and len(fields) == 7:
                values = [int(field.removeprefix('x'), 16) for field in fields[3:]]
                return 'CNC', (values[2] << 8) | values[3], (values[0] << 8) | values[1]
        except ValueError:
            break
    raise RuntimeError(f'Unexpected response for VCP {code}: {result.stdout.strip()}')

def write_switch(command, code, value):
    # Reconfiguration can remove DDC during immediate verification. Never
    # resend an action automatically; doing so could cycle it a second time.
    try:
        result = subprocess.run([*command, 'setvcp', code, str(value),
                                 '--permit-unknown-feature', '--noverify'], check=False, timeout=DDC_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f'Timed out writing VCP {code}; the panel may have applied it. '
                           'No write was retried; inspect the visible state and readback before retrying') from None
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
        target = getattr(args, 'layout_input', None)
        original_kvm = read_kvm_target(command) if args.value is not None else None
        if target == 'active_kvm':
            target = original_kvm
        secondary = getattr(args, 'layout_secondary', None)
        secondary_raw = secondary_value(secondary) if secondary is not None else None
        if args.value is not None:
            expected = DELL_LAYOUTS['off' if args.value == '100' else args.value]
            write_switch(command, 'E9', expected)
            wait_for_feature(command, 'E9', expected)
            if target is not None:
                try:
                    write_switch(command, '60', main_value(target))
                    wait_for_feature(command, '60', main_value(target))
                except RuntimeError as error:
                    raise RuntimeError(f'Layout {args.value if args.value != "100" else "off"} confirmed, but input {target} was not confirmed: {error}') from None
            if secondary_raw is not None:
                try:
                    write_switch(command, 'E8', secondary_raw)
                    wait_for_feature(command, 'E8', secondary_raw)
                except RuntimeError as error:
                    raise RuntimeError(f'Layout {args.value} and requested main input confirmed, but secondary input {secondary} was not confirmed: {error}') from None
            try:
                select_dell_usb(command, original_kvm)
            except RuntimeError as error:
                raise RuntimeError(f'Layout and requested video inputs confirmed, but KVM target {original_kvm} could not be preserved: {error}') from None
        else:
            expected = read_feature(command, 'E9')
        name = next((name for name, value in DELL_LAYOUTS.items() if value == expected), 'unknown')
        print(f'{name} (0x{expected:02X})')
        if target is not None:
            print(f'input {target} (0x{main_value(target):02X})')
        if secondary_raw is not None:
            print(f'sub-input {secondary} (0x{secondary_raw:04X})')
        if original_kvm is not None:
            print(f'kvm {original_kvm} (preserved)')
    elif action == 'pip-position':
        if read_feature(command, 'E9') not in (DELL_LAYOUTS['pip-small'], DELL_LAYOUTS['pip-large']):
            raise RuntimeError('Position cycling requires pip-small or pip-large')
        write_switch(command, 'E9', DELL_PIP_CYCLE)
        print('PiP position-cycle command sent; position is not readable through the mapped registers.', file=sys.stderr)
    elif action == 'usb':
        return run_dell_usb(args, command)
    elif action == 'sub-input':
        if args.value is not None:
            expected = secondary_value(args.value)
            layout = read_feature(command, 'E9')
            if layout == 0 or layout not in DELL_LAYOUTS.values():
                raise RuntimeError('Secondary input selection requires a mapped active PiP/PbP layout')
            write_switch(command, 'E8', expected)
            wait_for_feature(command, 'E8', expected)
        else:
            expected = read_feature(command, 'E8')
        name = next((name for name, value in DELL_SECONDARY_INPUTS.items() if value == expected), 'unknown')
        print(f'{name} (0x{expected:04X})')
    else:
        code, values = (('63', DELL_AUDIO_SOURCES) if action == 'audio-source'
                        else ('8D', DELL_SPEAKER_VALUES))
        if args.value is not None:
            expected = values[args.value]
            write_switch(command, code, expected)
            wait_for_feature(command, code, expected)
        else:
            expected = read_feature(command, code)
        name = next((name for name, value in values.items() if value == expected), 'unknown')
        print(f'{name} (0x{expected:02X})')
    return 0


def read_kvm_target(command):
    active = read_feature(command, 'E7', maximum=True) >> 8
    name = next((name for name, value in DELL_USB_TARGETS.items() if value == active), None)
    if name is None:
        raise RuntimeError(f'Unmapped active USB target 0x{active:02X}; no layout or input write sent')
    return name


def select_dell_usb(command, value):
    # E7 current bytes hold the USB/video assignment table. Its MH status byte
    # identifies the active input; observed 1=Thunderbolt and 4=HDMI1.
    status = read_feature(command, 'E7', maximum=True)
    active = status >> 8
    if value is not None:
        if active not in DELL_USB_TARGETS.values():
            raise RuntimeError(f'Unmapped active USB target 0x{active:02X}; no switch sent')
        # This toggle is deliberately restricted to the two mapped hosts.
        target = (next(value for value in DELL_USB_TARGETS.values() if value != active)
                  if value == 'next' else DELL_USB_TARGETS[value])
        if target != active:
            layout = read_feature(command, 'E9')
            main = read_feature(command, '60')
            secondary_raw = read_feature(command, 'E8')
            secondary = next((DELL_MAIN_INPUTS[name] for name, raw in DELL_SECONDARY_INPUTS.items()
                              if raw == secondary_raw), None)
            if layout == 0 or layout not in DELL_LAYOUTS.values() or {main, secondary} != {DELL_MAIN_INPUTS[name] for name in DELL_KVM_INPUTS}:
                raise RuntimeError('USB switching requires a mapped active two-window layout with '
                                   'Thunderbolt and HDMI1; no switch sent')
            write_switch(command, 'E7', DELL_USB_SWITCH)
            wait_for_feature(command, 'E7', (target << 8) | (status & 0xFF), maximum=True)
            active = target
    name = next((name for name, value in DELL_USB_TARGETS.items() if value == active), 'unknown')
    return name, active


def run_dell_usb(args, command):
    name, active = select_dell_usb(command, args.value)
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
                change += ['8D', str(DELL_SPEAKER_VALUES['off'])]
            change += ['--noverify']
            try:
                result = subprocess.run(change, check=False, timeout=DDC_TIMEOUT)
                failure = 'Volume write failed' if result.returncode else None
            except subprocess.TimeoutExpired:
                failure = 'Volume write timed out; the panel may have applied it'
            if failure:
                if speaker_off:
                    # Restore only Speaker Off, never retry the uncertain level write.
                    try:
                        restore = subprocess.run([*command, 'setvcp', '8D',
                                                  str(DELL_SPEAKER_VALUES['off']), '--noverify'],
                                                 check=False, timeout=DDC_TIMEOUT)
                        restored = restore.returncode == 0
                    except subprocess.TimeoutExpired:
                        restored = False
                    if not restored:
                        raise RuntimeError(f'{failure}; Speaker Off could not be restored; speaker state is uncertain; inspect the panel')
                raise RuntimeError(f'{failure}; no volume write was retried; read the level and speaker state before retrying')
            wait_for_feature(command, '62', target | (0x80 if speaker_off else 0))
    print(f'{target}/100 (speakers {"off" if speaker_off else "on"})')
    return 0

def run(args, parser):
    if args.external_action == 'layout':
        left = getattr(args, 'layout_input', None)
        right = getattr(args, 'layout_secondary', None)
        if (left is not None or right is not None) and args.value is None:
            parser.error('input options require a layout value')
        if right is not None and args.value in ('off', '100'):
            parser.error('--right/--sub-input requires an active PiP/PbP layout')
        if left == 'active_kvm' and args.value not in ('off', '100'):
            parser.error('active_kvm requires layout off or layout 100')
        if right is not None:
            secondary_value(right)  # Validate before changing layout.
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
        if action == 'input' and args.value in DELL_MAIN_INPUTS:
            require_dell_u5226kw(bus)
            args.value = str(main_value(args.value))
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
                    value = str(MUTE_VALUES[value])
                command += ['setvcp', code]
                # Raw set is an explicit request, including unknown vendor codes.
                command += (['+' if value == 'up' else '-', '5'] if value in ('up', 'down') else [value])
                if action == 'set':
                    command += ['--permit-unknown-feature']
                if getattr(args, 'no_verify', False):
                    command += ['--noverify']
                else:
                    command += ['--verify']
    # User-requested raw passthrough intentionally has no timeout: preserve
    # ddcutil's output and exit status. Internal policy reads/writes are bounded.
    return subprocess.run(command, check=False).returncode
