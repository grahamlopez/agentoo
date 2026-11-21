# Flattop hardware baseline

## Hardware identity

Framework Laptop 13 (13th Gen Intel Core, board FRANMCCP06 A6), Intel Core
i7-1360P (12 cores / 16 logical CPUs), Intel Raptor Lake-P integrated graphics
(`i915`), Intel AX211 Wi-Fi (`iwlwifi`), Intel USB Bluetooth (`8087:0033`), IDT
92HD95 HDA audio (`snd_hda_intel`), Realtek UVC camera (`0bda:5634`), WD NVMe
storage, and internal 2880×1920 (3:2) panel.

## Scoped exceptions

- **Portage profile (`agentoo:hosts/flattop`, inherits `hardware/intel-laptop`):**
  Selects `-march=raptorlake`, Rust `-C target-cpu=raptorlake`,
  `VIDEO_CARDS="-* intel"`, `/dev/shm` build storage, `MAKEOPTS="-j12"`,
  `linux-firmware` `savedconfig`, and `~amd64` keyword acceptance for
  `app-laptop/framework_tool`.
- **Custom kernel (`/etc/agentoo/kernel/hosts/flattop.config`):** Retains
  shared `CONFIG_MODULES=n`; embeds ADLP/TGL graphics, AX211 Wi-Fi/PNVM,
  Bluetooth `ibt-0040-0041`, regulatory data, and `intel-ucode/06-ba-02`.
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

- Retains `rtl_nic/rtl8156b-2.fw` for the shared Dell U5226KW monitor/KVM.
- Open Framework EC/peripheral checks live in
  [card 025](../../kanban/Backlog/025-flattop-kernel-v0.3-followups.md);
  native `gentoo-kernel` migration is tracked in
  [card 053](../../kanban/Open/053-gentoo-kernel-fleet-migration.md).
