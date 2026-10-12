#!/bin/bash
# Diagnose first boot, verify boot identities, then offer the standard checkpoint.
# --verify-only runs diagnostics without capture preflight or cleanup.
# Capture policy is owned by agentoo-checkpoint; restore is its recovery subcommand.
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
if (( failures == 0 )); then
    if (( verify_only )); then
        printf '\nDiagnostic commands passed; synchronized time is not required in verify-only mode.\n'
    else
        printf '\nDiagnostic commands passed; checking checkpoint prerequisites…\n'
    fi
else
    printf '\n%s checks failed. Review the output above.\n' "$failures"
fi
printf 'Optional integrity check: systemctl start gentoo-btrfs-scrub.service; btrfs scrub status /\n'
printf 'After a later reboot, verify that journalctl --list-boots includes the previous boot.\n'
(( failures == 0 ))
}

(( EUID == 0 )) || { echo 'Run this script as root on the booted Gentoo target.'; exit 1; }
[[ -d /run/systemd/system && -r /etc/gentoo-release ]] || { echo 'Run on the booted target, not in a chroot.'; exit 1; }
if ! run_diagnostics; then exit 1; fi
(( verify_only == 0 )) || exit 0
python3 - <<'PY'
import pathlib, re, shutil, subprocess, sys
def run(*args):
    return subprocess.check_output(args, text=True).strip()
def require(condition, message):
    if not condition: raise RuntimeError(message)
def field(path, name):
    return run("findmnt", "-rn", "--uniq", "-o", name, "--mountpoint", path)

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
    require(run('timedatectl', 'show', '-p', 'NTPSynchronized', '--value') == 'yes', 'Time is not synchronized yet.\nWait briefly, then rerun this script.')
    require(not run('systemctl', '--failed', '--no-legend', '--plain', '--no-pager'), 'Failed systemd units remain.')
except RuntimeError as error:
    print(f'Checkpoint not created: {error}', file=sys.stderr)
    sys.exit(1)

PY
exec /usr/local/bin/agentoo-checkpoint create fresh-install
