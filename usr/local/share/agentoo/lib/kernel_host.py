"""Resolve explicit host policy and the local encrypted-root identity.

No configuration is sourced as shell code and no storage is changed.
"""
import json
from pathlib import Path
import re
import uuid

from host_selection import HOST_NAME, read_host

HOSTS = Path('/etc/agentoo/kernel/hosts')
KEYMAP = '/usr/share/keymaps/i386/qwerty/us-caps.map.gz'
SYS_BLOCK = Path('/sys/class/block')
MINIMAL_BUILTINS = (
    'BINFMT_ELF', 'DEVTMPFS', 'PROC_FS', 'SYSFS', 'TMPFS', 'EFI_PARTITION',
    'BLK_DEV_DM', 'DM_CRYPT', 'CRYPTO_AES', 'CRYPTO_XTS', 'BTRFS_FS',
    'INPUT', 'VT', 'VT_CONSOLE', 'HID', 'HID_GENERIC', 'USB', 'USB_HID',
    'USB_XHCI_HCD', 'USB_XHCI_PCI', 'FRAMEBUFFER_CONSOLE',
)


def selected_host(host=None):
    if host is None:
        return read_host()
    if not re.fullmatch(HOST_NAME, host):
        raise ValueError('invalid host name')
    return host


def read_profile(host=None):
    host = selected_host(host)
    path = HOSTS / f'{host}.config'
    if not path.is_file():
        raise RuntimeError(f'{path}: no kernel profile for {host}; create a reviewed host profile first')
    text = path.read_text()
    values = {}
    for line in text.splitlines():
        disabled = re.fullmatch(r'# (CONFIG_\w+) is not set', line)
        if disabled:
            key, value = disabled[1], 'n'
        elif not line.strip() or line.startswith('#'):
            continue
        else:
            match = re.fullmatch(r'(CONFIG_\w+)=(y|m|n|[0-9]+|0x[0-9a-fA-F]+|"[^"\\\n]*")', line)
            if not match:
                raise ValueError(f'{path}: invalid Kconfig fragment line: {line}')
            key, value = match.groups()
        if key.startswith(('CONFIG_CMDLINE', 'CONFIG_INITRAMFS', 'CONFIG_LOCALVERSION')):
            raise ValueError(f'{path}: {key} belongs to generated build policy')
        if key in values:
            raise ValueError(f'{path}: duplicate {key}')
        values[key] = value
    for key in ('CONFIG_EXTRA_FIRMWARE', 'CONFIG_EXTRA_FIRMWARE_DIR'):
        if key not in values or not values[key].startswith('"'):
            raise ValueError(f'{path}: explicit {key} string required')
    if not Path(json.loads(values['CONFIG_EXTRA_FIRMWARE_DIR'])).is_absolute():
        raise ValueError(f'{path}: firmware directory must be absolute')
    names = json.loads(values['CONFIG_EXTRA_FIRMWARE']).split()
    if any(Path(name).is_absolute() or '..' in Path(name).parts for name in names):
        raise ValueError(f'{path}: firmware names must be relative paths without ..')
    return host, path, text, values


def identifier(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError) as error:
        raise RuntimeError(f'missing or invalid storage UUID: {value!r}') from error


def resolve_identity(run):
    mounts = json.loads(run(['findmnt', '--json', '--output', 'SOURCE,FSTYPE,FSROOT', '--target', '/'], capture=True))['filesystems']
    if len(mounts) != 1 or mounts[0]['fstype'] != 'btrfs' or mounts[0]['fsroot'] != '/@':
        raise RuntimeError('host specialization requires the installed Btrfs @ root on one LUKS2 partition')
    source = mounts[0]['source'].split('[', 1)[0]
    devices = json.loads(run(['lsblk', '--json', '--tree', '--inverse', '--paths', '--output',
                             'PATH,KNAME,TYPE,FSTYPE,UUID,PARTUUID,TRAN', source], capture=True))['blockdevices']
    if len(devices) != 1:
        raise RuntimeError('cannot inspect the mounted root device; run on the destination host with block-device access')
    root = devices[0]
    parents = root.get('children', [])
    if root['type'] != 'crypt' or root['fstype'] != 'btrfs' or len(parents) != 1:
        raise RuntimeError('expected Btrfs directly on a single encrypted mapping; LVM/RAID layouts need separate initramfs support')
    partition = parents[0]
    if partition['type'] != 'part' or partition['fstype'] != 'crypto_LUKS':
        raise RuntimeError('expected the encrypted root backing device to be a LUKS partition')
    disks = partition.get('children', [])
    transport = disks[0].get('tran') if len(disks) == 1 and disks[0]['type'] == 'disk' else None
    sysfs = SYS_BLOCK / Path(root['kname']).name / 'dm'
    if not (sysfs / 'uuid').read_text().startswith('CRYPT-LUKS2-'):
        raise RuntimeError('the minimal initramfs requires LUKS2')
    mapper = (sysfs / 'name').read_text().strip()
    if not re.fullmatch(r'[a-zA-Z0-9_+-]+', mapper):
        raise RuntimeError('unsupported root mapping name')
    identity = dict(root_uuid=identifier(root['uuid']), luks_uuid=identifier(partition['uuid']),
                    partuuid=identifier(partition['partuuid']), mapper=mapper, subvolume='@', keymap=KEYMAP,
                    transport=transport)
    return identity


def check_minimal_config(values, identity):
    storage = {'nvme': ('BLK_DEV_NVME',), 'sata': ('SCSI', 'BLK_DEV_SD', 'ATA', 'SATA_AHCI')}
    transport = identity.get('transport')
    if transport not in storage:
        raise RuntimeError(f'minimal initramfs does not support root transport {transport!r}; use --initramfs')
    missing = [f'CONFIG_{name}=y' for name in (*MINIMAL_BUILTINS, *storage[transport])
               if values.get('CONFIG_' + name) != 'y']
    if not any(values.get('CONFIG_' + name) == 'y' for name in ('FB_EFI', 'FB_VESA', 'DRM_SIMPLEDRM')):
        missing.append('one built-in EFI/VESA/simpledrm framebuffer')
    if missing:
        raise RuntimeError('minimal initramfs requires built-in boot support:\n  ' + '\n  '.join(missing) +
                           '\nEnable these capabilities or use --initramfs; early module loading is not supported.')


def expectations(values, identity):
    return {**values, 'CONFIG_CMDLINE_BOOL': 'y', 'CONFIG_CMDLINE_OVERRIDE': 'n',
            'CONFIG_CMDLINE': json.dumps(identity['cmdline'])}


def check_expected(actual, expected):
    differences = [f'{key}: wanted {value}, got {actual.get(key, "<absent>")}'
                   for key, value in expected.items() if actual.get(key, 'n') != value]
    if differences:
        raise RuntimeError('host settings changed or did not survive Kconfig resolution:\n  ' + '\n  '.join(differences))
