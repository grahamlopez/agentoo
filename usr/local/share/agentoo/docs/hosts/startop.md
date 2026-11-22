# Startop hardware baseline

## Hardware identity

- **System:** Star Labs StarFighter (rev `1.0`, coreboot `26.08`).
- **CPU & memory:** Intel Core Ultra 9 285H (Arrow Lake, 16 logical CPUs),
  62 GiB RAM.
- **Graphics:** Intel Arc Pro 140T (`8086:7d51`, `i915` / Meteor Lake firmware).
- **Wireless:** Intel Wi-Fi 6E AX210 (`8086:2725`, `iwlwifi`) and Intel USB
  Bluetooth (`8087:0032`).
- **Audio:** Intel Arrow Lake cAVS (`8086:7728`) with HDA/ALC233 codec
  (`snd_hda_intel`).
- **Storage & I/O:** Two 1 TB NVMe SSDs—system Samsung 970 EVO (`144d:a808` at
  `02:00.0`) and unused secondary MAXIO MAP1602 (`1e4b:1602` at `59:00.0`,
  model string `Samsung SSD 990PRO 1TB`), Intel Thunderbolt 4 (`8086:7ec2`),
  Realtek USB 2.0 card reader (`0bda:0129`).
- **Display:** 3840×2400 panel (`eDP-1`).

## Scoped exceptions

- **Portage profile (`agentoo:hosts/startop`, inherits `hardware/intel-laptop`):**
  Selects `-march=arrowlake`, Rust `-C target-cpu=arrowlake`,
  `VIDEO_CARDS="-* intel"`, `/dev/shm` build storage, `MAKEOPTS="-j12"`, and
  `linux-firmware` `savedconfig`. Detected CPU feature flags stay local in
  `/etc/portage/package.use/00cpu-flags`.
- **Custom kernel (`/etc/agentoo/kernel/hosts/startop.config`):** Retains
  shared `CONFIG_MODULES=n`; embeds Meteor Lake graphics, AX210 Wi-Fi/PNVM,
  Intel Bluetooth (+ DDC companion for cold init), regulatory data, and Intel
  Arrow Lake microcode.
- **Installed firmware (`/etc/agentoo/firmware/startop.list`):** Trimmed
  `linux-firmware` selection covering Meteor Lake graphics, AX210, Intel
  Bluetooth, and RTL8156 dock Ethernet.
- **Dracut early KMS (`/etc/dracut.conf.d/startop.conf`):** Queries
  `host_selection.py` to force early `i915` loading in the binary fallback
  initramfs (prevents the autologin GPU race below).
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
  [card 054](../../kanban/Backlog/054-startop-power-after-resume.md). Native
  `gentoo-kernel` migration is tracked in
  [card 053](../../kanban/Open/053-gentoo-kernel-fleet-migration.md);
  shared kernel follow-ups live in
  [card 027](../../kanban/Backlog/027-shared-kernel-v0.3-followups.md).
