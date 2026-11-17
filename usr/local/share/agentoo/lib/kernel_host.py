"""Validate explicit host policy and built-in boot capabilities.

No configuration is sourced as shell code and no storage is changed.
"""
import json
from pathlib import Path
import re
import sys

from host_selection import HOST_NAME, read_host

HOSTS = Path('/etc/agentoo/kernel/hosts')
HOST_LINK = Path('/etc/kernel/config.d/20-host.config')
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


def read_profile(host=None, *, root=Path('/')):
    host = selected_host(host)
    path = Path(root) / HOSTS.relative_to('/') / f'{host}.config'
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


def check_minimal_config(values, identity):
    storage = {'nvme': ('BLK_DEV_NVME',), 'sata': ('SCSI', 'BLK_DEV_SD', 'ATA', 'SATA_AHCI')}
    transport = identity.get('transport')
    if transport not in storage:
        raise RuntimeError(f'minimal initramfs does not support root transport {transport!r}')
    missing = [f'CONFIG_{name}=y' for name in (*MINIMAL_BUILTINS, *storage[transport])
               if values.get('CONFIG_' + name) != 'y']
    if not any(values.get('CONFIG_' + name) == 'y' for name in ('FB_EFI', 'FB_VESA', 'DRM_SIMPLEDRM')):
        missing.append('one built-in EFI/VESA/simpledrm framebuffer')
    if missing:
        raise RuntimeError('minimal initramfs requires built-in boot support:\n  ' + '\n  '.join(missing) +
                           '\nEnable these capabilities; early module loading is not supported.')


def check_expected(actual, expected):
    differences = [f'{key}: wanted {value}, got {actual.get(key, "<absent>")}'
                   for key, value in expected.items() if actual.get(key, 'n') != value]
    if differences:
        raise RuntimeError('host settings changed or did not survive Kconfig resolution:\n  ' + '\n  '.join(differences))


def validate_config(path, transport, root=Path('/')):
    values = {}
    for line in Path(path).read_text().splitlines():
        match = re.fullmatch(r'(CONFIG_\w+)=(.*)', line)
        disabled = re.fullmatch(r'# (CONFIG_\w+) is not set', line)
        if match:
            values[match[1]] = match[2]
        elif disabled:
            values[disabled[1]] = 'n'
    if values.get('CONFIG_MODULES') != 'n':
        raise RuntimeError('native custom-kernel acceptance currently requires CONFIG_MODULES=n; module hosts are deferred')
    _, profile, _, expected = read_profile(root=root)
    active = Path(root) / HOST_LINK.relative_to('/')
    if not active.is_symlink() or active.resolve() != profile.resolve():
        raise RuntimeError('active /etc/kernel/config.d/20-host.config must link to the selected host fragment')
    check_expected(values, expected)
    check_minimal_config(values, {'transport': transport})
    check_expected(values, {'CONFIG_EFI_STUB': 'y', 'CONFIG_BLK_DEV_INITRD': 'y',
                           'CONFIG_IKCONFIG': 'y', 'CONFIG_IKCONFIG_PROC': 'y',
                           'CONFIG_CMDLINE_BOOL': 'y', 'CONFIG_CMDLINE_OVERRIDE': 'n',
                           'CONFIG_INITRAMFS_ROOT_UID': '0', 'CONFIG_INITRAMFS_ROOT_GID': '0'})
    archive = Path(json.loads(values['CONFIG_INITRAMFS_SOURCE']))
    if not archive.is_file():
        raise RuntimeError(f'embedded initramfs is missing: {archive}')
    firmware = Path(json.loads(values['CONFIG_EXTRA_FIRMWARE_DIR']))
    missing = [name for name in json.loads(values['CONFIG_EXTRA_FIRMWARE']).split()
               if not (firmware / name).is_file()]
    if missing:
        raise RuntimeError('missing embedded firmware: ' + ', '.join(missing))
    return values


if __name__ == '__main__':
    try:
        validate_config(sys.argv[1], sys.argv[2], sys.argv[3])
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f'agentoo kernel: {error}', file=sys.stderr)
        sys.exit(1)
