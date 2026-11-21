# Thinktop hardware baseline

## Hardware identity

Lenovo ThinkPad (subsystem `17aa:2349`), Intel Core Ultra 7 255H (Arrow Lake,
16 logical CPUs), 62 GiB RAM, Intel Arrow Lake integrated graphics (`i915` /
Meteor Lake firmware), unused NVIDIA RTX 5060 Mobile (`10de:2d19`, upstream
bridge `8086:7ecc`), Intel CNVi Wi-Fi (`iwlwifi-bz-b0-fm-c0`), Intel USB
Bluetooth (`8087:0037`), Meteor Lake NPU (`vpu_37xx`), Intel SOF + SoundWire
audio (`cs42l43` codec, dual `cs35l56` amplifiers), internal 3840×2400 panel,
and NVMe storage.

## Scoped exceptions

- **Portage profile (`agentoo:hosts/thinktop`, inherits `hardware/intel-laptop`):**
  Selects `-march=arrowlake`, Rust `-C target-cpu=arrowlake`,
  `VIDEO_CARDS="-* intel"`, `/dev/shm` build storage, `MAKEOPTS="-j12"`,
  `linux-firmware` `savedconfig`, and `sys-firmware/sof-firmware` in `@profile`
  for SoundWire/SOF audio.
- **Custom kernel (`/etc/agentoo/kernel/hosts/thinktop.config`):** Retains
  shared `CONFIG_MODULES=n`; embeds Meteor Lake graphics, CNVi Wi-Fi, Bluetooth
  `ibt-0093-0291`, SOF/Cirrus audio payloads, regulatory data, and
  `intel-ucode/06-c5-02`.
- **Installed firmware (`/etc/agentoo/firmware/thinktop.list`):** Trimmed
  `linux-firmware` selection covering graphics, CNVi Wi-Fi, Bluetooth, Meteor
  Lake NPU, SoundWire/Cirrus DSP payloads, and RTL8156 dock Ethernet.
- **Discrete GPU power (`/etc/udev/rules.d/80-thinktop-gpu-power.rules`):**
  Scoped to PCI `10de:2d19` and bridge `8086:7ecc` under Lenovo subsystem
  `17aa:2349` to set `power/control=auto` on the unused discrete RTX 5060 Mobile.
- **Desktop (`/etc/xdg/hypr/hosts/thinktop.lua`):** Sets internal `eDP-1` to
  `3840x2400@60` at scale `1.5`. Kitty uses shared defaults.

## Hardware quirks and negative findings

- **Secure Boot enrollment:** Firmware does not expose `dbDefault` variables
  (`sbctl enroll-keys --firmware-builtin` fails); enroll using
  `--microsoft --custom --ignore-immutable` after staging exported db/KEK certs
  (see [secure-boot.md](../secure-boot.md)).
- **Microphone mute button:** The legacy genkernel `90-thinktop-micmute.rules`
  workaround is retired; native `gentoo-kernel` handles the key without a udev
  override.
- **Unused NVIDIA GPU:** Kept unbound (Nouveau excluded from the shared kernel).
  PCI sysfs `remove` does not guarantee power-off—always verify actual
  `power_state` (`D3cold`) and idle battery draw before altering GPU PM policy.
- **Benign boot logs:** Initial `iwlwifi` lookup for `-c99.ucode` falls back
  cleanly to `-101.ucode`. AMD KVM/CCP, IT87, and ChromeOS probe failures come
  from absent hardware in the shared built-in driver union.

## Peripheral and workflow notes

- Connects to the shared Dell U5226KW monitor/KVM (Thunderbolt + RTL8156 dock
  Ethernet). `/etc/udev/rules.d/80-agentoo-lid-recheck.rules` handles delayed
  USB-C power-offline settling when unplugging a closed laptop.
- Open host follow-ups live in
  [card 023](../../kanban/Backlog/023-thinktop-kernel-v0.3-followups.md);
  native kernel maintenance lives in
  [card 052](../../kanban/Backlog/052-native-kernel-maintenance-followups.md).
