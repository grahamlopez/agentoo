#!/bin/bash
# Diagnose first boot, verify boot identities, then offer the standard checkpoint.
# --verify-only runs diagnostics without capture preflight or cleanup.
# Capture policy is owned by agentoo checkpoint; restore is its recovery subcommand.
set -Eeuo pipefail
verify_only=0
die() { printf 'Verification failed: %s\n' "$*" >&2; exit 1; }
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

# Report configured radios independently of the interfaces discovered this boot,
# so an old name cannot disappear silently from verification. No automatic rename.
report_wifi_configuration() {
  local config_dir=${1:-/etc/wpa_supplicant} net_dir=${2:-/sys/class/net}
  local config interface state
  for config in "$config_dir"/wpa_supplicant-*.conf; do
    [[ -s $config && -f $config && ! -L $config ]] || continue
    interface=${config##*/wpa_supplicant-}
    interface=${interface%.conf}
    if [[ ! -d $net_dir/$interface/phy80211 ]]; then
      printf '\nWARNING: Wi-Fi configuration names an absent wireless interface: %s\n' "$interface"
      printf 'Inspect current names: ip -brief link; ls /sys/class/net/*/phy80211\n'
      printf 'If this is the same adapter under a new name, inspect the configuration, then as root:\n'
      printf '  systemctl disable --now %q\n' "wpa_supplicant@$interface.service"
      printf '  mv -i -- %q /etc/wpa_supplicant/wpa_supplicant-NEW_INTERFACE.conf\n' "$config"
      printf '  systemctl enable --now wpa_supplicant@NEW_INTERFACE.service\n'
      printf 'Replace NEW_INTERFACE with the verified wireless interface; do not overwrite another configuration.\n'
      continue
    fi
    if command -v wpa_cli >/dev/null; then
      state=$(wpa_cli -i "$interface" status 2>/dev/null | awk -F= '$1 == "wpa_state" {print $2}') || state=
      printf '\nWi-Fi authentication on %s: %s\n' "$interface" "${state:-status unavailable}"
      [[ $state != COMPLETED ]] || continue
    else
      printf '\nWi-Fi authentication on %s: wpa_cli unavailable.\n' "$interface"
    fi
    printf 'Inspect authentication and service logs as root:\n'
    printf '  wpa_cli -i %q status\n' "$interface"
    printf '  systemctl status --no-pager %q\n' "wpa_supplicant@$interface.service"
    printf '  journalctl -b -u %q --no-pager -n 50\n' "wpa_supplicant@$interface.service"
    printf 'If intentionally configured but disabled, enable it with:\n'
    printf '  systemctl enable --now %q\n' "wpa_supplicant@$interface.service"
    printf 'Review credentials locally; do not paste passwords or full supplicant configuration into reports.\n'
  done
}

run_diagnostics() {
local failures=0 device interface
check() {
    printf '\n==> %s\n' "$1"
    shift
    "$@" || { printf 'CHECK FAILED (continuing)\n'; failures=$((failures + 1)); }
}
show() {
    printf '\n==> %s\n' "$1"
    shift
    "$@" || printf 'Information unavailable (not a required check).\n'
}
check 'Root filesystem' findmnt --mountpoint /
check 'Home filesystem' findmnt --mountpoint /home
check 'EFI filesystem' findmnt --mountpoint /boot
show 'Failed services' systemctl --failed --no-pager
check 'System health' systemctl is-system-running
show 'Network interfaces' ip -brief address
show 'Routes' ip route
check 'DHCP service' systemctl is-active dhcpcd.service
for device in /sys/class/net/*; do
    [[ -d $device/phy80211 ]] || continue
    interface=${device##*/}
    if ! systemctl is-enabled --quiet "wpa_supplicant@$interface.service"; then
        printf '\nWi-Fi on %s is not configured for startup; skipping authentication check.\n' "$interface"
        continue
    fi
    check "Wi-Fi service on $interface" systemctl is-active "wpa_supplicant@$interface.service"
    show "Wi-Fi service diagnostics on $interface" systemctl status --no-pager "wpa_supplicant@$interface.service"
done
report_wifi_configuration
check 'DNS resolution' timeout 15 getent hosts gentoo.org
if command -v curl >/dev/null; then
    check 'HTTPS connectivity' curl --head --fail --max-time 20 https://www.gentoo.org/
else
    check 'IP connectivity (ICMP may be filtered)' ping -c 3 -W 3 1.1.1.1
fi
check 'Time service' systemctl is-active systemd-timesyncd.service
show 'Time configuration' timedatectl status
show 'Time synchronization' timedatectl timesync-status
show 'Journal boot history (packaged logging defaults)' journalctl --list-boots --no-pager
check 'Scrub timer enabled' systemctl is-enabled gentoo-btrfs-scrub.timer
check 'Scrub timer active' systemctl is-active gentoo-btrfs-scrub.timer
show 'Scrub schedule' systemctl list-timers gentoo-btrfs-scrub.timer --no-pager
printf '\n==> Hardware inventory (informational; does not gate checkpoints)\n'
show 'PCI devices and bound drivers' lspci -nnk
show 'ALSA sound cards' cat /proc/asound/cards
show 'Bluetooth controllers' ls /sys/class/bluetooth
show 'Display backlight controllers' ls /sys/class/backlight
show 'Available sleep modes' cat /sys/power/mem_sleep
show 'Recent kernel firmware and microcode messages' journalctl -k -b --no-pager -n 40 --grep 'firmware|microcode|sof[-_]'
printf '\nManual hardware checks: displays/scaling, brightness keys, speakers/headphones, microphone, Bluetooth pairing, and suspend/resume.\n'
printf 'For laptop dock tests: close the lid on external power, change monitor input, then unplug the dock/power and verify suspend; reopen and verify the panel.\n'
printf 'Device detection does not prove these functions work; retain any warnings for follow-up.\n'
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
# Verify boot ingredients independently of the one-time installation release.
field() { findmnt -rn --uniq -o "$2" --mountpoint "$1"; }
findmnt --verify --tab-file /etc/fstab
root_uuid=$(field / UUID)
[[ -n $root_uuid && $(field / FSTYPE) == btrfs && $(field / FSROOT) == /@ ]] || die 'Root must be Btrfs subvolume @.'
[[ $(field /home FSTYPE) == btrfs && $(field /home FSROOT) == /@home && $(field /home UUID) == "$root_uuid" ]] || die 'Home must be @home on the root filesystem.'
[[ $(field /boot FSTYPE) == vfat && $(field /boot UUID) == "$(cat /etc/kernel/gentoo-dist-esp.uuid)" ]] || die 'EFI filesystem differs from the target record.'
[[ ,$(field /boot OPTIONS), == *,rw,* ]] || die 'EFI filesystem is read-only.'
for path in / /home; do
    expected=@
    [[ $path != /home ]] || expected=@home
    options=$(findmnt --fstab -rn -o OPTIONS --target "$path")
    [[ ,$options, == *,subvol=$expected,* || ,$options, == *,subvol=/$expected,* ]] || die "fstab subvolume differs: $path"
done
for line in "$(cat /etc/kernel/cmdline)" "$(cat /proc/cmdline)"; do
    # Kernel command lines are space-separated, unlike arbitrary shell input.
    [[ " $line " == *" root=UUID=$root_uuid "* && " $line " == *' rootflags=subvol=@ '* ]] || die 'Boot parameters differ from the mounted root.'
done
[[ -d /lib/modules/$(uname -r) ]] || die 'Running kernel modules are missing.'
atom=$(portageq best_version / sys-kernel/gentoo-kernel-bin)
[[ -n $atom ]] || die 'Distribution fallback is not installed.'
mapfile -t releases < <(awk '$1 == "obj" && $2 ~ /\/include\/config\/kernel.release$/ {print $2}' "/var/db/pkg/$atom/CONTENTS")
(( ${#releases[@]} == 1 )) || die 'Cannot identify the installed distribution fallback.'
version=$(cat "${releases[0]}")
[[ $version =~ ^[A-Za-z0-9._+-]+-gentoo-dist(-bin)?$ && -d /lib/modules/$version ]] || die 'Distribution fallback modules are missing.'
for artifact in "/boot/EFI/Gentoo/kernel-$version.efi" "/boot/EFI/Gentoo/initramfs-$version.img"; do
    [[ -s $artifact ]] || die "Missing fallback boot file: $artifact"
done
[[ $(timedatectl show -p NTPSynchronized --value) == yes ]] || die 'Time is not synchronized yet; wait and retry.'
[[ -z $(systemctl --failed --no-legend --plain --no-pager) ]] || die 'Failed systemd units remain.'
exec /usr/local/bin/agentoo checkpoint create fresh-install
