"""Resolve explicit host policy and the local encrypted-root identity.

No configuration is sourced as shell code and no storage is changed.
"""
import json
from pathlib import Path
import re
import shlex
import uuid

SELECTOR = Path('/etc/agentoo/target-host')
HOSTS = Path('/etc/agentoo/kernel/hosts')
CMDLINE = Path('/etc/kernel/cmdline')
KEYMAP = '/usr/share/keymaps/i386/qwerty/us-caps.map.gz'
SYS_BLOCK = Path('/sys/class/block')


def read_profile(host=None):
    if host is None:
        match = re.fullmatch(r'\s*GENTOO_TARGET_HOST="([a-zA-Z0-9_-]+)"\s*', SELECTOR.read_text())
        if not match:
            raise ValueError(f'{SELECTOR}: expected GENTOO_TARGET_HOST="name"')
        host = match[1]
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]*', host):
        raise ValueError('invalid host name')
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
                             'PATH,KNAME,TYPE,FSTYPE,UUID,PARTUUID', source], capture=True))['blockdevices']
    if len(devices) != 1:
        raise RuntimeError('cannot inspect the mounted root device; run on the destination host with block-device access')
    root = devices[0]
    parents = root.get('children', [])
    if root['type'] != 'crypt' or root['fstype'] != 'btrfs' or len(parents) != 1:
        raise RuntimeError('expected Btrfs directly on a single encrypted mapping; LVM/RAID layouts need separate initramfs support')
    partition = parents[0]
    if partition['type'] != 'part' or partition['fstype'] != 'crypto_LUKS':
        raise RuntimeError('expected the encrypted root backing device to be a LUKS partition')
    sysfs = SYS_BLOCK / Path(root['kname']).name / 'dm'
    if not (sysfs / 'uuid').read_text().startswith('CRYPT-LUKS2-'):
        raise RuntimeError('the minimal initramfs requires LUKS2')
    mapper = (sysfs / 'name').read_text().strip()
    if not re.fullmatch(r'[a-zA-Z0-9_+-]+', mapper):
        raise RuntimeError('unsupported root mapping name')
    identity = dict(root_uuid=identifier(root['uuid']), luks_uuid=identifier(partition['uuid']),
                    partuuid=identifier(partition['partuuid']), mapper=mapper, subvolume='@', keymap=KEYMAP)
    commandline = CMDLINE.read_text().strip()
    if not commandline or '\n' in commandline or '"' in commandline or '\\' in commandline:
        raise RuntimeError(f'{CMDLINE}: expected one plain kernel command line')
    tokens = shlex.split(commandline)
    if any(token.startswith('rd.luks.') and not token.startswith(('rd.luks.uuid=', 'rd.luks.name=')) for token in tokens):
        raise RuntimeError(f'{CMDLINE}: only passphrase-based rd.luks.uuid/name inputs are supported')
    if any(token.startswith('root_trim=') and token != 'root_trim=yes' for token in tokens):
        raise RuntimeError(f'{CMDLINE}: the minimal initramfs policy enables discards; root_trim must be yes')
    def one(key):
        matches = [token.split('=', 1)[1] for token in tokens if token.startswith(key + '=')]
        if len(matches) != 1:
            raise RuntimeError(f'{CMDLINE}: expected exactly one {key}= argument')
        return matches[0]
    def same_uuid(value, expected, prefix='UUID='):
        if not value.startswith(prefix) or identifier(value[len(prefix):]) != expected:
            raise RuntimeError(f'{CMDLINE}: boot identifiers disagree with the mounted root; correct the local command line')
    same_uuid(one('root'), identity['root_uuid'])
    if one('rootfstype') != 'btrfs' or one('rootflags') != 'subvol=@':
        raise RuntimeError(f'{CMDLINE}: expected rootfstype=btrfs rootflags=subvol=@')
    crypt = [token for token in tokens if token.startswith('crypt_root=')]
    dracut = [token for token in tokens if token.startswith(('rd.luks.uuid=', 'rd.luks.name='))]
    if crypt:
        same_uuid(one('crypt_root'), identity['luks_uuid'])
    if dracut:
        same_uuid(one('rd.luks.uuid'), identity['luks_uuid'], 'luks-')
        if one('rd.luks.name') != identity['luks_uuid'] + '=' + mapper:
            raise RuntimeError(f'{CMDLINE}: rd.luks.name disagrees with the mounted mapping')
    if not crypt and not dracut:
        raise RuntimeError(f'{CMDLINE}: expected crypt_root or rd.luks root identification')
    unsupported = [token for token in tokens if token.startswith(('initrd=', 'resume=', 'rd.luks.key=', 'cryptkey='))]
    unsupported += [token for token in tokens if token.startswith('init=') and token != 'init=/sbin/init']
    if unsupported:
        raise RuntimeError(f'{CMDLINE}: unsupported boot inputs: {unsupported}; review initramfs policy first')
    # Preserve the established minimal-builder discard policy explicitly.
    identity['allow_discards'] = True
    identity['cmdline'] = commandline
    return identity


def expectations(values, identity):
    return {**values, 'CONFIG_CMDLINE_BOOL': 'y', 'CONFIG_CMDLINE_OVERRIDE': 'y',
            'CONFIG_CMDLINE': json.dumps(identity['cmdline'])}


def check_expected(actual, expected):
    differences = [f'{key}: wanted {value}, got {actual.get(key, "<absent>")}'
                   for key, value in expected.items() if actual.get(key, 'n') != value]
    if differences:
        raise RuntimeError('host settings changed or did not survive Kconfig resolution:\n  ' + '\n  '.join(differences))
