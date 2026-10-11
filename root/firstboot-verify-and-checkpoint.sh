#!/bin/bash
# First-boot verification and optional fresh-install checkpoint.
# Run on the booted target: /root/firstboot-verify-and-checkpoint.sh
# Use --verify-only for diagnostics without checkpoint preflight or creation.
# The helper runs the existing first-boot checks, validates boot and filesystem
# identities, and offers a compact checkpoint plan only after verification passes.
# Accepting removes downloaded distfiles, captures read-only snapshots of root,
# home and their nested subvolumes, and saves a verified `efi-files.tar.gz` archive
# with boot-entry recovery instructions under `/boot/checkpoints/<name>`.
# Btrfs snapshots and their manifest live under `gentoo-checkpoints/<name>` at the
# filesystem top level. Both locations must have `COMPLETE` markers before use.
# The original checkpoint is never overwritten; failed attempts remain incomplete
# for inspection, and retry creates a new timestamped attempt.
#
# Behavior:
# - Required verification, including synchronized time, must pass before consent.
# - Active package/configuration operations block capture; pause other writers too.
# - Declining preserves downloads and removes the temporary inspection mount.
# - Acceptance removes distfiles, captures root/home and nested subvolumes
#   read-only, and verifies the gzip-compressed EFI archive by extraction.
# - Live snapshots are sequential, not atomic across subvolumes. EFI changes
#   since preflight cause failure rather than a completed inconsistent checkpoint.
# - Both storage locations need COMPLETE markers. Failed attempts remain
#   incomplete; retry creates a new name and never overwrites a prior baseline.
# - Restoration uses writable copies while target subvolumes are unmounted,
#   followed by a reboot. This helper does not perform restoration or scheduling.
set -Eeuo pipefail
verify_only=0
if (( $# > 1 )); then echo 'Expected at most one option: --verify-only or --help.' >&2; exit 2; fi
case ${1:-} in
  --verify-only) verify_only=1 ;;
  --help|-h)
    printf 'Usage: %s [--verify-only]\n' "$0"
    printf 'Default: diagnose, check checkpoint readiness, and offer a checkpoint.\n'
    printf '%s\n' '--verify-only: diagnostics only; no cleanup, snapshots, or checkpoint prompt.'
    exit 0 ;;
  '') ;;
  *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
esac

run_diagnostics() {
local failures=0 device interface
check() {
    printf '\n==> %s\n' "$1"
    shift
    "$@" || { printf 'CHECK FAILED (continuing)\n'; failures=$((failures + 1)); }
}
check 'Root filesystem' findmnt --mountpoint /
check 'Home filesystem' findmnt --mountpoint /home
check 'EFI filesystem' findmnt --mountpoint /boot
check 'Failed services' systemctl --failed --no-pager
check 'System health' systemctl is-system-running
check 'Network interfaces' ip -brief address
check 'Routes' ip route
check 'DHCP service' systemctl is-active dhcpcd.service
for device in /sys/class/net/*; do
    [[ -d $device/phy80211 ]] || continue
    interface=${device##*/}
    check "Wi-Fi authentication on $interface" systemctl is-active "wpa_supplicant@$interface.service"
    check "Wi-Fi service diagnostics on $interface" systemctl status --no-pager "wpa_supplicant@$interface.service"
done
check 'DNS resolution' timeout 15 getent hosts gentoo.org
if command -v curl >/dev/null; then
    check 'HTTPS connectivity' curl --head --fail --max-time 20 https://www.gentoo.org/
else
    check 'IP connectivity (ICMP may be filtered)' ping -c 3 -W 3 1.1.1.1
fi
check 'Time service' systemctl is-active systemd-timesyncd.service
check 'Time configuration' timedatectl status
check 'Time synchronization' timedatectl timesync-status
check 'Journal boot history' journalctl --list-boots --no-pager
check 'Persistent journal directory' test -d /var/log/journal
check 'Scrub timer enabled' systemctl is-enabled gentoo-btrfs-scrub.timer
check 'Scrub timer active' systemctl is-active gentoo-btrfs-scrub.timer
check 'Scrub schedule' systemctl list-timers gentoo-btrfs-scrub.timer --no-pager
printf '\n%s checks failed. Review the output above.\n' "$failures"
printf 'Optional integrity check: systemctl start gentoo-btrfs-scrub.service; btrfs scrub status /\n'
printf 'After a later reboot, verify that journalctl --list-boots includes the previous boot.\n'
(( failures == 0 ))
}

(( EUID == 0 )) || { echo 'Run this script as root on the booted Gentoo target.'; exit 1; }
[[ -d /run/systemd/system && -r /etc/gentoo-release ]] || { echo 'Run on the booted target, not in a chroot.'; exit 1; }
if ! run_diagnostics; then exit 1; fi
(( verify_only == 0 )) || exit 0
exec 9>/run/firstboot-verify-and-checkpoint.lock
flock -n 9 || { echo 'Another first-boot checkpoint is running.'; exit 1; }
python3 - <<'PY'
import datetime, hashlib, json, os, pathlib, re, shutil, subprocess, tempfile

def run(*args):
    return subprocess.check_output(args, text=True).strip()
def require(condition, message):
    if not condition: raise RuntimeError(message)
def field(path, name):
    return run('findmnt', '-n', '-r', '-o', name, '--mountpoint', path)
def idle():
    # Conservative refusal; users must also pause their own configuration tools.
    result = subprocess.run(['pgrep', '-f', r'(^|/)(emerge|ebuild|emaint|dispatch-conf|etc-update|kernel-install|gentoo-install\.sh)( |$)'], capture_output=True)
    require(result.returncode == 1, 'Package/configuration operations are running, or process inspection failed. Finish them and retry.')
def digest(path):
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def hashes(base):
    result = {}
    for path in base.rglob('*'):
        require(not path.is_symlink(), 'Unexpected symlink in EFI files.')
        if path.is_file(): result[str(path.relative_to(base))] = digest(path)
    return result

mountdir = None
checkpoint = None
try:
    for command in ('btrfs', 'tar', 'gzip', 'efibootmgr', 'findmnt', 'portageq', 'pgrep'):
        require(shutil.which(command), f'Missing tool: {command}')
    subprocess.run(['findmnt', '--verify', '--tab-file', '/etc/fstab'], check=True)
    root_uuid = field('/', 'UUID')
    home_uuid = field('/home', 'UUID')
    esp_uuid = field('/boot', 'UUID')
    require(field('/', 'FSTYPE') == field('/home', 'FSTYPE') == 'btrfs', 'Root and home must be Btrfs.')
    require(root_uuid == home_uuid and root_uuid, 'Root and home must share a filesystem.')
    require(field('/boot', 'FSTYPE') == 'vfat', 'The EFI partition must be mounted at /boot.')
    require('rw' in field('/boot', 'OPTIONS').split(','), 'EFI partition is read-only.')
    require(esp_uuid == pathlib.Path('/etc/kernel/gentoo-dist-esp.uuid').read_text().strip(), 'EFI partition identity differs from installer record.')
    cmdline = pathlib.Path('/etc/kernel/gentoo-dist.cmdline').read_text().strip()
    root_name = field('/', 'FSROOT').lstrip('/')
    home_name = field('/home', 'FSROOT').lstrip('/')
    require(all(re.fullmatch(r'[A-Za-z0-9_@.-]+', name) for name in (root_name, home_name)), 'Unsupported root/home layout.')
    require(root_name != home_name, 'Root and home must be separate subvolumes.')
    for path, expected in (('/', root_name), ('/home', home_name)):
        options = run('findmnt', '--fstab', '-n', '-r', '-o', 'OPTIONS', '--target', path).split(',')
        require(any(option in ('subvol=' + expected, 'subvol=/' + expected) for option in options), 'Mounted subvolume differs from fstab: ' + path)
    require(f'root=UUID={root_uuid}' in cmdline.split() and f'rootflags=subvol={root_name}' in cmdline.split(), 'Recorded boot parameters differ from mounted root.')
    running = pathlib.Path('/proc/cmdline').read_text().split()
    require(f'root=UUID={root_uuid}' in running and f'rootflags=subvol={root_name}' in running, 'Running kernel boot parameters differ from target.')
    version = pathlib.Path('/etc/kernel/gentoo-dist.version').read_text().splitlines()[-1]
    require(re.fullmatch(r'[A-Za-z0-9._+-]+', version), 'Invalid kernel version.')
    require(run('uname', '-r') == version, 'Running kernel differs from installed distribution kernel; reboot before checkpointing.')
    require(pathlib.Path('/lib/modules', version).is_dir(), 'Kernel modules are missing.')
    for name in (f'kernel-{version}.efi', f'initramfs-{version}.img'):
        require(pathlib.Path('/boot/EFI/Gentoo', name).stat().st_size > 0, f'Missing boot file: {name}')
    require(run('timedatectl', 'show', '-p', 'NTPSynchronized', '--value') == 'yes', 'Time is not synchronized yet; retry after synchronization.')
    require(not run('systemctl', '--failed', '--no-legend', '--plain', '--no-pager'), 'Failed systemd units remain.')
    dist = pathlib.Path(run('portageq', 'envvar', 'DISTDIR'))
    require(str(dist) == '/var/cache/distfiles' and dist.is_dir() and not dist.is_symlink(), 'Expected an ordinary /var/cache/distfiles directory; review custom cache layout manually.')
    mounts = run('findmnt', '-r', '-n', '-o', 'TARGET').splitlines()
    require(not any(p == str(dist) or p.startswith(str(dist) + '/') for p in mounts), 'Distfiles contains a mount; refusing cleanup.')
    idle()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    name = 'fresh-install-' + stamp
    mountdir = pathlib.Path(tempfile.mkdtemp(prefix='gentoo-checkpoint-', dir='/run'))
    subprocess.run(['mount', '-t', 'btrfs', '-o', 'subvolid=5', 'UUID=' + root_uuid, str(mountdir)], check=True)
    listing = run('btrfs', 'subvolume', 'list', str(mountdir))
    sources = [root_name, home_name]
    for line in listing.splitlines():
        path = line.split(' path ', 1)[1]
        if path.startswith(root_name + '/') or path.startswith(home_name + '/'):
            require(re.fullmatch(r'[A-Za-z0-9_@./+-]+', path), 'Unsupported nested subvolume path.')
            sources.append(path)
        elif path not in sources:
            require(path.startswith('gentoo-checkpoints/'), 'Unexpected sibling subvolume: ' + path)
    require(len(sources) == len(set(sources)), 'Duplicate subvolume paths.')
    require(not any(p == root_name + '/var/cache/distfiles' or p.startswith(root_name + '/var/cache/distfiles/') for p in sources), 'Distfiles contains a subvolume; review custom cache layout manually.')
    size = run('du', '-sh', str(dist)).split()[0]
    efi = pathlib.Path('/boot/EFI')
    before = hashes(efi)
    require(before, 'No EFI files found.')
    efi_bytes = sum(p.stat().st_size for p in efi.rglob('*') if p.is_file())
    require(shutil.disk_usage('/boot').free > efi_bytes + 32 * 1024**2, 'Insufficient EFI free space for backup plus reserve.')
    require(shutil.disk_usage('/').free > 1024**3, 'Less than 1 GiB free on Btrfs; free space before checkpointing.')
    # Capture the actual target firmware listing; never call this in a chroot.
    entries = run('efibootmgr', '--verbose')
    print(f'''\nFresh-install checkpoint plan\n  Verified system → {name}\n  ├─ Remove downloaded sources: {dist} ({size})\n  ├─ Preserve {len(sources)} read-only snapshots: {', '.join(sources)}\n  ├─ Save compressed EFI files + boot recovery record\n  └─ Verify all components before marking complete\n\n  Snapshots: Btrfs top level /gentoo-checkpoints/{name}\n  Boot backup: /boot/checkpoints/{name}\n  Keep package/configuration tools idle until completion.\n  Later restores require a reboot/recovery procedure.\n  Journal persistence across reboot is a separate later check.\n''')
    with open('/dev/tty', 'w') as tty:
        tty.write('Remove these downloads and create the checkpoint? [y/N] '); tty.flush()
    with open('/dev/tty', 'r') as tty:
        accepted = tty.readline().strip().lower() in ('y', 'yes')
    if not accepted:
        print('Verification passed. Checkpoint declined; no installation files changed.')
    else:
        idle()
        parent = mountdir / 'gentoo-checkpoints'
        require(not parent.is_symlink(), 'Checkpoint storage is a symlink.')
        parent.mkdir(mode=0o700, exist_ok=True)
        require(parent.is_dir(), 'Invalid checkpoint storage.')
        checkpoint = parent / name
        checkpoint.mkdir(mode=0o700)
        (checkpoint / 'INCOMPLETE').write_text('Do not restore: checkpoint creation has not finished.\n')
        boot_parent = pathlib.Path('/boot/checkpoints')
        require(not boot_parent.is_symlink(), 'Boot checkpoint storage is a symlink.')
        boot_parent.mkdir(exist_ok=True)
        boot = boot_parent / name
        boot.mkdir()
        (boot / 'INCOMPLETE').write_text('Do not restore until matching Btrfs checkpoint is COMPLETE.\n')
        for child in dist.iterdir():
            if child.is_dir() and not child.is_symlink(): shutil.rmtree(child)
            else: child.unlink()
        os.sync()
        records = []
        for index, source in enumerate(sources):
            dest = checkpoint / f'subvolume-{index:03d}'
            subprocess.run(['btrfs', 'subvolume', 'snapshot', '-r', str(mountdir / source), str(dest)], check=True)
            require(run('btrfs', 'property', 'get', '-ts', str(dest), 'ro') == 'ro=true', 'Snapshot is not read-only.')
            records.append({'source': source, 'snapshot': dest.name, 'details': run('btrfs', 'subvolume', 'show', str(dest))})
        archive = boot / 'efi-files.tar.gz'
        subprocess.run(['tar', '--gzip', '-cf', str(archive), '-C', '/boot', 'EFI'], check=True)
        with tempfile.TemporaryDirectory(prefix='gentoo-efi-verify-', dir='/var/tmp') as tmp:
            subprocess.run(['tar', '--gzip', '-xf', str(archive), '-C', tmp], check=True)
            require(hashes(pathlib.Path(tmp) / 'EFI') == before == hashes(efi), 'EFI contents changed or archive verification failed.')
        (boot / 'boot-entries.txt').write_text(entries + '\n')
        esp_source = field('/boot', 'SOURCE')
        parent_disk = run('lsblk', '-n', '-r', '-o', 'PKNAME', esp_source)
        partition = run('lsblk', '-n', '-r', '-o', 'PARTN', esp_source)
        import shlex
        recreate = ['efibootmgr', '--create', '--full-dev-path', '--disk', '/dev/' + parent_disk, '--part', partition,
                    '--label', 'Gentoo checkpoint', '--loader', f'\\EFI\\Gentoo\\kernel-{version}.efi',
                    '--unicode', cmdline + f' initrd=\\EFI\\Gentoo\\initramfs-{version}.img']
        instructions = f'''Checkpoint: {name}\nEFI UUID: {esp_uuid}\nRoot UUID: {root_uuid}\n\nRestore root/home and nested subvolumes together from the matching COMPLETE\nBtrfs checkpoint while they are unmounted, using writable snapshots and the\nmanifest's source paths. Do not replace a running root. Keep the baseline.\n\nMount the verified EFI partition and extract efi-files.tar.gz into its root.\nPreserve this archive. Verify checksums before extraction. This restores saved\nfiles but does not remove EFI files added later; review those separately.\n\nLeave firmware entries alone if they still point to the restored files.\nIf missing, run the following from a UEFI-booted target or rescue system.\nVerify disk identity first: device names can change. Preserve unrelated entries.\n{shlex.join(recreate)}\n\nCompare boot-entries.txt and adjust boot order with efibootmgr --bootorder\nusing the current entry numbers, which may differ from the saved numbers.\nThis text is not a complete firmware-variable backup.\n'''
        (boot / 'restore-instructions.txt').write_text(instructions)
        checksums = ''.join(f'{digest(p)}  {p.name}\n' for p in (archive, boot / 'boot-entries.txt', boot / 'restore-instructions.txt'))
        (boot / 'checksums.txt').write_text(checksums)
        manifest = {'name': name, 'root_uuid': root_uuid, 'esp_uuid': esp_uuid, 'kernel': version,
                    'snapshots': records, 'efi_hashes': before, 'boot_checksums': checksums,
                    'consistency': 'Live snapshots captured sequentially; no group-atomic or application-consistency guarantee.'}
        (checkpoint / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (boot / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        os.sync()
        (checkpoint / 'INCOMPLETE').unlink()
        (boot / 'INCOMPLETE').unlink()
        (boot / 'COMPLETE').write_text(name + '\n')
        (checkpoint / 'COMPLETE').write_text(name + '\n')
        os.sync()
        print(f'\nCheckpoint complete: {name}\nContinue configuring this system. Preserve both the Btrfs checkpoint and EFI backup.')
except Exception as error:
    print(f'\nCheckpoint not completed: {error}', flush=True)
    if checkpoint:
        print('Partial components are retained. Do not restore unless BOTH locations have COMPLETE markers.\nRetry this script to create a new checkpoint; nothing is overwritten.')
    raise SystemExit(1)
finally:
    if mountdir:
        result = subprocess.run(['umount', str(mountdir)])
        if result.returncode == 0: mountdir.rmdir()
        else: print(f'Temporary mount remains at {mountdir}; unmount it before recovery operations.')
PY
