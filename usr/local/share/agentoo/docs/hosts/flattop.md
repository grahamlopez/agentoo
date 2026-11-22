# Flattop hardware baseline

## Hardware identity

- **System:** Framework Laptop 13 (13th Gen Intel Core, board `FRANMCCP06`
  rev `A6`, Insyde BIOS `03.16`).
- **CPU:** Intel Core i7-1360P (12 cores / 16 logical CPUs).
- **Graphics:** Intel Raptor Lake-P UHD Graphics (`8086:a720`, `i915`).
- **Wireless:** Intel Raptor Lake PCH CNVi Wi-Fi (`8086:51f1`, AX211,
  `iwlwifi`) and Intel USB Bluetooth (`8087:0033`).
- **Audio:** Intel Raptor Lake-P/U/H cAVS (`8086:51ca`) with IDT 92HD95 HDA
  codec (`snd_hda_intel`).
- **Storage & I/O:** WD PC SN810 / Black SN850 1 TB NVMe SSD (`15b7:5011`),
  Intel Thunderbolt 4 (`8086:a73e`/`8086:a76d`).
- **Built-in peripherals & display:** 2256×1504 (3:2) panel (`eDP-1`), Realtek
  UVC camera (`0bda:5634`), Goodix fingerprint reader (`27c6:609c`),
  `[s2idle] deep` sleep.

## Scoped exceptions

- **Portage profile (`agentoo:hosts/flattop`, inherits `hardware/intel-laptop`):**
  Selects `-march=raptorlake`, Rust `-C target-cpu=raptorlake`,
  `VIDEO_CARDS="-* intel"`, `/dev/shm` build storage, `MAKEOPTS="-j12"`,
  `linux-firmware` `savedconfig`, and `~amd64` keyword acceptance for
  `app-laptop/framework_tool`.
- **Custom kernel (`/etc/agentoo/kernel/hosts/flattop.config`):** Retains
  shared `CONFIG_MODULES=n`; embeds ADLP/TGL graphics, AX211 Wi-Fi/PNVM,
  Intel Bluetooth, regulatory data, and Intel Raptor Lake microcode.
  Disables absent AMD KVM/CCP, IT87 GPIO, IBM ACPI PCI hotplug, and
  `CONFIG_CHARGER_CROS_USBPD` while retaining `CROS_EC`.
- **Installed firmware (`/etc/agentoo/firmware/flattop.list`):** Trimmed
  `linux-firmware` selection covering ADLP/TGL graphics, AX211, Intel Bluetooth,
  and RTL8156 dock Ethernet.
- **Desktop (`/etc/xdg/hypr/hosts/flattop.lua`):** Sets internal `eDP-1` to
  `preferred` at scale `1`. Kitty uses shared defaults.

## Hardware quirks and negative findings

- **Audio:** Uses legacy HDA/IDT (`snd_hda_intel`); no SOF firmware is needed.
  The AVS alternative requests `intel/avs/adl/dsp_basefw.bin`, which is absent
  even from broad `linux-firmware`.
- **Charging & EC (`CHARGER_CROS_USBPD` / `cros_charge-control`):** Framework
  uses ACPI battery/mains reporting; `CHARGER_CROS_USBPD` fails with `-71` and
  is intentionally disabled. `cros_charge-control` intentionally declines load
  when Framework's custom charge-limit command (`0x3E03`) is present—do not
  force-load it or it resets the configured 90% ceiling to 0–100%.
- **Secure Boot enrollment:** On Insyde BIOS 03.16, delete PK under
  *Administer Secure Boot → PK Options* to enter Setup Mode, then enroll with
  `sbctl enroll-keys --microsoft --firmware-builtin --custom --ignore-immutable`
  (see [secure-boot.md](../secure-boot.md#flattop-firmware-menu)).
- **Benign ACPI logs:** Missing `RP28.PXSX.WIST` / `CNVW.IFUN` / `CNVW._DSM`
  errors also occur on the binary fallback kernel; do not chase them as custom
  kernel regressions.

## Peripheral and workflow notes

- Retains RTL8156 Ethernet firmware for the shared Dell U5226KW monitor/KVM.
- Open Framework EC/peripheral checks live in
  [card 025](../../kanban/Backlog/025-flattop-kernel-v0.3-followups.md);
  native `gentoo-kernel` migration is tracked in
  [card 053](../../kanban/Open/053-gentoo-kernel-fleet-migration.md).
