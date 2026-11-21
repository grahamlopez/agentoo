# Startop hardware baseline

## Hardware identity

Star Labs StarFighter (coreboot 26.08), Intel Core Ultra 9 285H (Arrow Lake,
16 logical CPUs), 62 GiB RAM, Intel Arrow Lake integrated graphics
(`8086:7d51`, `i915` / Meteor Lake firmware), Intel AX210 Wi-Fi (`8086:2725`),
Intel USB Bluetooth, HDA/ALC233 audio (`8086:7728`, `snd_hda_intel`), internal
3840×2400 panel, and two NVMe drives (system Samsung 970 EVO at `02:00.0`;
unused secondary MAXIO `1e4b:1602` at `59:00.0`).

## Scoped exceptions

- **Portage profile (`agentoo:hosts/startop`, inherits `hardware/intel-laptop`):**
  Selects `-march=arrowlake`, Rust `-C target-cpu=arrowlake`,
  `VIDEO_CARDS="-* intel"`, `/dev/shm` build storage, `MAKEOPTS="-j12"`, and
  `linux-firmware` `savedconfig`. Detected CPU feature flags stay local in
  `/etc/portage/package.use/00cpu-flags`.
- **Custom kernel (`/etc/agentoo/kernel/hosts/startop.config`):** Retains
  shared `CONFIG_MODULES=n`; embeds Meteor Lake graphics, AX210 API 89/PNVM,
  Bluetooth `ibt-0041-0041` (+ DDC companion for cold init), regulatory data,
  and `intel-ucode/06-c5-02`.
- **Installed firmware (`/etc/agentoo/firmware/startop.list`):** Trimmed
  `linux-firmware` selection covering Meteor Lake graphics, AX210, Intel
  Bluetooth, and RTL8156 dock Ethernet.
- **Dracut early KMS (`/etc/dracut.conf.d/startop.conf`):** Queries
  `host_selection.py` and forces early `i915` loading in the binary fallback
  initramfs so DRM initializes before `tty1` autologin launches Hyprland.
- **EFI registration:** `gentoo-install.sh`, `agentoo kernel gen-efi-cmd`, and
  `99-agentoo-boot-guidance.install` add `--full-dev-path`, required by
  Startop's coreboot/UEFI firmware.
- **Desktop (`/etc/xdg/hypr/hosts/startop.lua`):** Sets internal `eDP-1` to
  `3840x2400@60` at scale `1.5`. Kitty uses shared defaults.

## Hardware quirks and negative findings

- **Audio & NPU:** Uses HDA/ALC233 (`snd_hda_intel`); no SOF/Cirrus payload
  or PCI NPU is required.
- **Autologin GPU race:** Without early `i915` in the binary fallback initramfs,
  fast `tty1` autologin aborts Hyprland with `No gpus in scanGPUs` ~80 ms before
  DRM registers.
- **Post-resume idle power regression:** Idle draw rises ~1–1.4 W after suspend
  and package C-states stop past C2. Controlled tests ruled out GSC/ME, S3 vs.
  s2idle/Modern Standby, PowerTOP auto-tune, Wi-Fi radio, ASPM, and NVMe APST
  loss, isolating the fault to the unused secondary NVMe path (`00:1c.0` →
  `59:00.0`). Do not use PCI remove/rescan as a workaround: rescan leaves ASPM
  and L1 substates disabled.

## Peripheral and workflow notes

- Uses the shared Dell U5226KW monitor/KVM, Bluetooth mice/headsets, Lily58
  keyboard, webcams, and Blue USB microphone.
- Full post-resume power evidence and rejected hypotheses live in
  [startop-power.md](startop-power.md). Native `gentoo-kernel` migration is
  tracked in [card 053](../../kanban/Open/053-gentoo-kernel-fleet-migration.md);
  shared kernel follow-ups live in
  [card 027](../../kanban/Backlog/027-shared-kernel-v0.3-followups.md).
