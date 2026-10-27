# Complete shared kernel v0.3 validation and deferred investigations

Created: 2026-10-25
Status: Backlog

## Scope and accepted state

Track remaining common work for the shared driver/capability union across
thinktop, startop, flattop and bequiet. Host boot arguments, firmware/microcode
and initramfs inputs remain exceptions. Shared `MODULES=n` and Nouveau exclusion
remain; bequiet has the operator-managed module exception described in its card.
No bonding/teaming/VRFs or hibernation is required. Ordinary suspend and swap,
GPU compute, Intel/AMD KVM and PCI/GPU passthrough remain requirements.

The final static audit passed at 3,068 enabled symbols, 1,584 fewer than the
original running baseline. Thinktop subsequently booted v0.3, and the operator
confirmed cameras, microphones and speakers working after suspend/resume.
This is host-scoped evidence, not complete fleet/workload acceptance.

Host cards: [thinktop](023-thinktop-kernel-v0.3-followups.md),
[startop](024-startop-kernel-v0.3-followups.md),
[flattop](025-flattop-kernel-v0.3-followups.md),
[bequiet](026-bequiet-kernel-v0.3-followups.md). Record per-host results there.

## Common validation, where used

- [ ] Networking: WireGuard/Tailscale split routes and IPv4/IPv6/DNS;
  Docker/Podman rootful/rootless connectivity and published ports; QEMU
  user/tap/bridge/NAT networking; laptop iPhone Wi-Fi tethering. Record actual
  backends/rules without changing them merely to test kernel coverage.
- [ ] File services: NFSv3/v4 client/server and SMB2.1+ client/Samba server on
  all hosts, with intended authentication, permissions, ACLs and xattrs.
  SMB3.1.1 POSIX is retained; old SMB1/2.0 client support is not required.
- [ ] Storage: used NVMe/SATA/USB/SD, LUKS mappings and Btrfs, generic SG/BSG
  management, removable FAT/exFAT/NTFS/ISO and actual Unicode/legacy filenames.
  Restore an omitted codepage if genuinely needed rather than forcing a wrong
  encoding. Verify ordinary swap/zram; no suspend-to-disk acceptance is needed.
- [ ] Resizable DM/LVM RAID with LUKS: settle layer order, RAID/reshape goals
  and exact LVM/cryptsetup/initramfs activation tools; test supported operations
  on disposable storage before real layouts/resizes. Preserve thin/cache/
  writecache and dm-mirror migration support. Btrfs encryption means Btrfs over
  LUKS here, not usable native Btrfs encryption. No data operations are approved
  merely by recording this card.
- [ ] Virtualization: actual Intel/AMD QEMU/KVM acceleration, device permissions,
  networking and used shared files/host–guest sockets. Validate passthrough
  separately on intended hosts, including groups/reset/ownership. Distribution
  kernels run inside guests; the shared kernel targets physical hosts.
- [ ] Platform: expected RTC/time initialization and used wake alarms;
  watchdog identity/state through sysfs and configured userspace selection;
  power profiles, Intel PMC/PMT/RAPL/uncore where applicable, low-power behavior,
  GPIO/pinctrl wake paths and used hotkeys/brightness/backlight/rfkill controls.
  Do not open watchdog devices just to inspect them.
- [ ] Peripherals: recorded keyboards/mice, keyd/uinput, TrackPoint/touchpad
  features, Logitech HID++/receiver/Bluetooth extra buttons/battery/reconnect,
  Lily58, Keychron and YubiKey functions as used. Test dock/display hotplug/DDC,
  camera privacy, headset detection, HDMI/DP/USB audio and used MIDI/serial
  devices/card readers. Match stable identities rather than class indices.
- [ ] Security/diagnostics: active LSMs, IMA/EVM initialization/policies/keyrings,
  verity and normal containers; used perf/BPF/probes/events/function tracing and
  normal observability. Specialist diagnostics can be restored or exercised with
  a suitable distribution kernel if later needed.

## Deferred evidence and optional reductions

- [ ] Compare all hosts against broad distribution kernels for full sensor,
  I2C/SPI/MDIO, GPIO, regulator, LED and clock coverage. Existing archives omit
  some classes; custom-kernel absence is not proof of absent hardware. Match
  exact devices/parent chains; do not blindly probe I2C or write controls.
- [ ] Before reconsidering SELinux/AppArmor removal, inspect each host's actual
  IMA subject/object label rules and low-address protection expectations.
  Removing both affects IMA_LSM_RULES and LSM_MMAP_MIN_ADDR. Preserve support
  until the compatibility question is resolved.
- [ ] Decide whether flattop Trace Hub/STM is wanted; its matching ACPI node
  is firmware-disabled/unbound. Keep the path pending that decision.
- [ ] Revisit held EEPROM/mux/clock/timing/PHY/UART drivers and ZL3073X support
  only with adequate hardware evidence. The checkpoint49 list records the
  exact candidates. Do not treat further symbol reduction as a release gate.
- [ ] If pursuing additional size reductions, investigate an independent HMM
  selector before removing Xe, and required SoundWire machine-driver selection
  before cutting its 31 forced codec helpers. Neither source patch nor alternate
  selector is currently approved; retain support meanwhile.

## Existing work and build maintenance

Continue the [shared configuration workflow](../Open/015-shared-kernel-configuration-workflow.md)
for durable inputs, menuconfig capture, host embedding, source/version migration
and reproducibility. It already owns that implementation; this card does not
revive the retired general kernel-reduction project. Link
[initramfs keyboard policy](020-initramfs-keyboard-policy.md) and
[firmware maintenance](../Completed/018-host-firmware-savedconfig.md) when relevant.

For each remaining host build use its own boot/firmware/microcode inputs and
fresh initramfs, portable compiler flags (do not replay old `-march=native`
notes), and verify synchronized release metadata before image naming or external
module builds. Review newly enabled defaults/dependencies during version bumps.
Thinktop has completed its fresh-initramfs build/boot and release verification;
the exact compiler flags used for that build were not independently established.

## Evidence and completion

Local review workspace:
`~/local/agentoo-build/kernel/6.18.57-agentoo-v0.3/`.
Use `checkpoints/50-final-config-audit/REPORT.txt`, checkpoint49 `held.json`,
and selected `pending_runtime_checks` entries in
`inventory/shared-requirements-review.json`. Some older statuses predate the
successful thinktop boot; its host card and first-boot evidence supersede them.

Close when host results and used workload checks are recorded and each remaining
optional investigation is resolved or explicitly carried forward with its tradeoff.
Preserve known-working recovery kernels. Tracking work does not authorize
automatic builds, installations, hardware control changes or device assignments.
