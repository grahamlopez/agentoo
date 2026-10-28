"""Inspect and apply reviewed host lists using Gentoo's native savedconfig.

No Portage hooks, automatic discovery, or persistent parallel configuration state.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

import kernel_host

LISTS = Path('/etc/agentoo/firmware')
SAVED = Path('/etc/portage/savedconfig')
VDB = Path('/var/db/pkg')
FIRMWARE = Path('/lib/firmware')
BOOT = Path('/boot')
BACKUPS = Path('/var/backups/agentoo/kernel-firmware')
KERNEL_CONFIG = Path('/proc/config.gz')
MICROCODE = Path('/sys/devices/system/cpu/cpu0/microcode/version')


def entries(text, *, reviewed=False):
    result = []
    for line in text.splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        if reviewed:
            path = Path(line)
            if (line != line.strip() or path.is_absolute() or '..' in path.parts or
                    any(char in line for char in '*?[]\x00') or not path.parts):
                raise ValueError(f'host firmware list requires explicit relative paths: {line!r}')
            if line in result:
                raise ValueError(f'duplicate host firmware path: {line}')
        result.append(line)
    if reviewed and not result:
        raise ValueError('host firmware list is empty')
    return result


def list_info(path):
    result = dict(path=path, exists=False, entries=None, error=None)
    try:
        path.lstat()
    except FileNotFoundError:
        return result
    except OSError as error:
        # Do not mistake inaccessible higher-priority inputs for absent ones.
        result.update(exists=True, error=str(error))
        return result
    result['exists'] = True
    try:
        result['text'] = path.read_text()
        result['entries'] = entries(result['text'])
    except (OSError, UnicodeError) as error:
        result['error'] = str(error)
    return result


def portage_state():
    # Keep Gentoo imports out of parser/help/completion startup.
    try:
        import portage
    except ImportError as error:
        raise RuntimeError('Gentoo Portage Python support is required for firmware status/apply') from error
    vardb = portage.db[portage.root]['vartree'].dbapi
    installed = vardb.match('sys-kernel/linux-firmware')
    if len(installed) > 1:
        raise RuntimeError('multiple linux-firmware versions installed; resolve the package state first')
    if not installed:
        return None
    cpv = installed[0]
    settings = portage.config()
    db = portage.db[portage.root]['porttree'].dbapi
    settings.setcpv(cpv, mydb=vardb)
    if settings['EROOT'] != '/' or settings['PORTAGE_CONFIGROOT'] != '/':
        raise RuntimeError('firmware management currently supports only the local / Portage root')
    pf = cpv.split('/', 1)[1]
    return dict(cpv=cpv, pf=pf, p=re.sub(r'-r\d+$', '', pf),
                chost=settings.get('CHOST', ''), ctarget=settings.get('CTARGET', ''),
                use=set(settings['PORTAGE_USE'].split()),
                installed_use=set((VDB / cpv / 'USE').read_text().split()),
                available=bool(db.match('=' + cpv)))


def candidates(package):
    if package is None:
        return []
    result = []
    # Match restore_config in savedconfig.eclass, including empty CTARGET:
    # it tries the plain path first in that case, then CHOST if plain is absent.
    for name in (package['pf'], package['p'], 'linux-firmware'):
        for triplet in (package['ctarget'], package['chost'], ''):
            if triplet and (Path(triplet).name != triplet or triplet in ('.', '..')):
                raise ValueError(f'unsupported Portage triplet directory: {triplet!r}')
            path = SAVED / triplet / 'sys-kernel' / name
            if path not in result:
                result.append(path)
    return result


def inventory(package):
    result = dict(entries=set(), regular=0, symlinks=0, bytes=0, missing=[])
    if package is None:
        return result
    contents = VDB / package['cpv'] / 'CONTENTS'
    for line in contents.read_text().splitlines():
        if line.startswith('obj '):
            path = line[4:].rsplit(' ', 2)[0]
            kind = 'regular'
        elif line.startswith('sym '):
            path = line[4:].split(' -> ', 1)[0]
            kind = 'symlinks'
        else:
            continue
        prefix = next((prefix for prefix in ('/lib/firmware/', '/usr/lib/firmware/') if path.startswith(prefix)), None)
        if prefix is None:
            continue
        name = path[len(prefix):]
        result['entries'].add(name)
        result[kind] += 1
        try:
            if kind == 'regular':
                result['bytes'] += (FIRMWARE / name).stat().st_size
            elif not (FIRMWARE / name).exists():
                result['missing'].append(name)
        except OSError:
            result['missing'].append(name)
    return result


def running_kernel():
    result = dict(release=os.uname().release, firmware=None, directory=None, error=None, microcode=None)
    try:
        raw = KERNEL_CONFIG.read_bytes()
        text = (gzip.decompress(raw) if raw.startswith(b'\x1f\x8b') else raw).decode()
        config = dict(re.findall(r'^(CONFIG_\w+)=(.*)$', text, re.M))
        result['firmware'] = json.loads(config.get('CONFIG_EXTRA_FIRMWARE', '""')).split()
        result['directory'] = json.loads(config.get('CONFIG_EXTRA_FIRMWARE_DIR', '"/lib/firmware"'))
    except (OSError, ValueError, EOFError) as error:
        result['error'] = str(error)
    try:
        result['microcode'] = MICROCODE.read_text().strip()
    except OSError:
        pass
    return result


def inspect():
    host = kernel_host.selected_host()
    package = portage_state()
    desired = list_info(LISTS / f'{host}.list')
    inputs = [list_info(path) for path in candidates(package)]
    effective = next((item for item in inputs if item['exists']), None)
    profile = kernel_host.HOSTS / f'{host}.config'
    expected, profile_error = None, None
    if profile.is_file():
        try:
            _, _, _, values = kernel_host.read_profile(host)
            expected = json.loads(values['CONFIG_EXTRA_FIRMWARE']).split()
        except (OSError, ValueError, RuntimeError) as error:
            profile_error = str(error)
    return dict(host=host, package=package, desired=desired, inputs=inputs, effective=effective,
                durable=list_info(SAVED / 'sys-kernel/linux-firmware'), inventory=inventory(package),
                kernel=running_kernel(), profile=profile, profile_error=profile_error, expected_embedded=expected)


def compare(label, desired, actual, emit):
    if desired is None or actual is None:
        emit(f'{label}: unavailable')
        return
    missing, extra = sorted(set(desired) - set(actual)), sorted(set(actual) - set(desired))
    emit(f'{label}: ' + ('matches' if not missing and not extra else f'{len(missing)} missing, {len(extra)} extra'))
    for heading, names in (('missing', missing), ('extra', extra)):
        if names:
            emit(f'  {heading}: ' + ', '.join(names[:8]) + (f' ... ({len(names)} total)' if len(names) > 8 else ''))


def show_status(state):
    package, desired, kernel = state['package'], state['desired'], state['kernel']
    print(f'Target host: {state["host"]}')
    print(f'Kernel profile: {state["profile"]}' + ('' if state['profile'].is_file() else ' (not present)'))
    if state['profile_error']:
        print('  Profile error: ' + state['profile_error'])
    print(f'Host firmware list: {desired["path"]}')
    if desired['entries'] is not None:
        print(f'  {len(desired["entries"])} paths; SHA256 {hashlib.sha256(desired["text"].encode()).hexdigest()}')
        for name in desired['entries']:
            print('  ' + name)
    else:
        print('  ' + (desired['error'] or 'not present; no reviewed selection'))
    if package is None:
        print('linux-firmware: not installed')
    else:
        print(f'Package: {package["cpv"]}; source ebuild ' + ('available' if package['available'] else 'unavailable'))
        print('Configured USE: ' + ' '.join(flag if flag in package['use'] else '-' + flag
              for flag in ('savedconfig', 'deduplicate', 'compress-xz', 'compress-zstd', 'dist-kernel', 'initramfs')))
        print('Installed package savedconfig: ' + ('enabled' if 'savedconfig' in package['installed_use'] else 'disabled'))
    print(f'Portage durable input: {state["durable"]["path"]}' + ('' if state['durable']['exists'] else ' (absent)'))
    effective = state['effective']
    print('Native savedconfig precedence (existing inputs):')
    for item in state['inputs']:
        if item['exists']:
            detail = f'{len(item["entries"])} paths' if item['entries'] is not None else item['error']
            label = ' [first match]' if item is effective else ''
            if item is effective and item['error']:
                label = ' [first candidate; unreadable here]'
            print(f'  {item["path"]}: {detail}' + label)
    if effective is None:
        print('  no matching input')
    if not package or 'savedconfig' not in package['use']:
        print('  Savedconfig is disabled; these inputs will not be used by a rebuild.')
    compare('Host list vs durable input', desired['entries'], state['durable']['entries'], print)
    compare('Host list vs first native match', desired['entries'], effective['entries'] if effective else None, print)
    inv = state['inventory']
    print(f'Installed linux-firmware: {inv["regular"]} regular files, {inv["symlinks"]} symlinks, {inv["bytes"]:,} payload bytes')
    compare('Host list vs installed package paths', desired['entries'], inv['entries'] if package else None, print)
    if inv['missing']:
        print('Package-owned paths absent/broken on disk: ' + ', '.join(inv['missing']))
    print(f'Running kernel: {kernel["release"]}; microcode: {kernel["microcode"] or "unavailable"}')
    print('Built-in firmware (CONFIG_EXTRA_FIRMWARE):')
    if kernel['firmware'] is None:
        print('  unavailable: ' + kernel['error'])
    else:
        for name in kernel['firmware']:
            owner = 'linux-firmware' if name in inv['entries'] else 'not owned by installed linux-firmware'
            print(f'  {name} [{owner}]')
        print('  Build-time directory: ' + kernel['directory'])
        compare('Host kernel profile vs running embedded selection', state['expected_embedded'], kernel['firmware'], print)
    print(f'/boot mounted: {"yes" if BOOT.is_mount() else "no"}')
    print('Embedded names do not establish every runtime load or initramfs copy. Apply does not rebuild the custom kernel.')
    print('Runtime load diagnostics: journalctl -k -b --no-pager --grep="firmware|microcode"')


def plan(state):
    desired, package = state['desired'], state['package']
    if desired['entries'] is None:
        raise RuntimeError(f'{desired["path"]}: {desired["error"] or "no reviewed host list; deploy it first"}')
    selected = entries(desired['text'], reviewed=True)
    if package is None:
        raise RuntimeError('install linux-firmware before applying a host selection')
    if not package['available']:
        raise RuntimeError(f'no source ebuild for installed {package["cpv"]}; update the package/repository explicitly first')
    if 'savedconfig' not in package['use']:
        raise RuntimeError('the selected host must enable linux-firmware[savedconfig]; deploy its Portage policy first')
    if package['use'].intersection(('deduplicate', 'compress-xz', 'compress-zstd')):
        raise RuntimeError('host firmware apply requires -deduplicate -compress-xz -compress-zstd')
    durable = state['durable']['path']
    priority = [item['path'] for item in state['inputs']]
    overrides = [item for item in state['inputs'][:priority.index(durable)] if item['exists']]
    for item in [desired, state['durable'], *overrides]:
        path = item['path']
        if item['exists'] and (path.is_symlink() or not path.is_file() or item['error']):
            raise RuntimeError(f'{path}: apply supports readable regular files, not symlinks/directories')
    return selected, overrides


def apply(args, state, *, run, confirm, notice):
    selected, overrides = plan(state)
    package, desired = state['package'], state['desired']
    durable = state['durable']['path']
    # Omit *pkgonly entirely: some Portage resolver paths test option presence,
    # even when its parsed value is False. Ignore defaults instead of negating
    # a potentially inherited binary-only option.
    command = ['emerge', '--ignore-default-opts', '--verbose', '--oneshot', '--ask=n',
               '--usepkg=n', '--getbinpkg=n', '=' + package['cpv']]
    mount_boot = 'initramfs' in package['use'] and not BOOT.is_mount()
    notice(f'Target host: {state["host"]}\nHost list: {desired["path"]} ({len(selected)} paths)\nNative input: {durable}')
    notice('Back up and retire overriding inputs:\n' + ('\n'.join('  ' + str(item['path']) for item in overrides) or '  none'))
    notice(f'Backups: unique directory under {BACKUPS}; existing durable input is also backed up.')
    if mount_boot:
        notice('Mount /boot through its existing mount configuration before rebuilding.')
    notice('Source rebuild: ' + ' '.join(command))
    notice('Distribution initramfs regeneration follows the effective dist-kernel/initramfs USE policy. Custom kernel/EFI registration remain separate.')
    if args.dry_run:
        return
    missing = [name for name in ('emerge', 'install', 'mktemp', 'mv', *(['mount'] if mount_boot else [])) if shutil.which(name) is None]
    if missing:
        raise RuntimeError('required tools not found: ' + ', '.join(missing))
    confirm('Apply firmware selection and rebuild', args.yes)
    if desired['path'].read_text() != desired['text']:
        raise RuntimeError('host list changed while reviewing the plan; rerun apply')
    backup = None
    try:
        if mount_boot:
            run(['mount', BOOT], root=True)
        run([command[0], '--pretend', *command[1:]], root=True)
        run(['install', '-d', '-m', '0700', BACKUPS], root=True)
        backup = Path(run(['mktemp', '-d', BACKUPS / f'{state["host"]}-{package["pf"]}.XXXXXXXX'], root=True, capture=True))
        notice('Backup directory: ' + str(backup))
        with tempfile.NamedTemporaryFile(mode='w') as snapshot:
            snapshot.write(desired['text'])
            snapshot.flush()
            run(['install', '-m', '0600', snapshot.name, backup / 'host.list'], root=True)
            if state['durable']['exists']:
                run(['install', '-D', '-m', '0600', durable, backup / 'savedconfig' / durable.relative_to(SAVED)], root=True)
            for item in overrides:
                destination = backup / 'retired' / item['path'].relative_to(SAVED)
                run(['install', '-d', '-m', '0700', destination.parent], root=True)
                run(['mv', '--', item['path'], destination], root=True)
            run(['install', '-D', '-m', '0644', snapshot.name, durable], root=True)
        run(command, root=True)
        generated = list_info(SAVED / 'sys-kernel' / package['pf'])
        actual = inventory(package)
        if generated['entries'] is None or set(generated['entries']) != set(selected) or actual['entries'] != set(selected) or actual['missing']:
            compare('Host list vs generated snapshot', selected, generated['entries'], notice)
            compare('Host list vs installed package paths', selected, actual['entries'], notice)
            if actual['missing']:
                notice('Package-owned paths absent/broken on disk: ' + ', '.join(actual['missing']))
            raise RuntimeError('rebuild returned successfully but installed selection needs review; run agentoo kernel firmware')
        notice(f'Applied {len(selected)} paths; installed payloads: {actual["bytes"]:,} bytes. Backup: {backup}')
        notice('Cold-boot the custom and distribution recovery kernels and repeat hardware/suspend checks. Embedded firmware and device caches can conceal missing installed files.')
    except (OSError, ValueError, RuntimeError, KeyboardInterrupt, EOFError):
        if backup is not None:
            notice(f'Apply interrupted/failed; configuration may already be updated. Backups: {backup}. No automatic rollback was performed.')
        raise


def command(args, *, run, confirm, notice):
    state = inspect()
    if args.firmware_operation == 'apply':
        apply(args, state, run=run, confirm=confirm, notice=notice)
    else:
        show_status(state)
