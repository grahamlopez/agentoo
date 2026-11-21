# Bequiet hardware baseline

## Hardware identity

Desktop workstation, Gigabyte X570 AORUS MASTER (BIOS F39), AMD Ryzen 9 3950X
(Zen 2, 16 cores / 32 logical CPUs), dual NVIDIA GPUs (RTX PRO 2000 Blackwell
`10de:2d30` and RTX 6000 Ada `10de:26b1`), Intel AX200 Wi-Fi (`iwlwifi`), Intel
USB Bluetooth (`8087:0029`), Intel I211 1GbE (`igb`), Realtek RTL8125 2.5GbE
(`r8169`), Realtek ALC1220 HDA audio (`snd_hda_intel`) + NVIDIA HDMI/DP audio,
three NVMe drives, and two AMD `1022:7901` AHCI SATA controllers.

## Scoped exceptions

- **Portage profile (`agentoo:hosts/bequiet`, inherits `common`):** Selects
  `-march=znver2`, Rust `-C target-cpu=znver2`, `VIDEO_CARDS="-* nvidia"`,
  `>=x11-drivers/nvidia-drivers-580` in `@profile` (with open kernel modules
  required by Blackwell), `MODULES_SIGN_KEY`/`MODULES_SIGN_CERT` pointing to
  sbctl's db key, and `linux-firmware` `savedconfig`.
- **Custom kernel (`/etc/agentoo/kernel/hosts/bequiet.config`):** Sole host
  permitted to enable loadable modules (`CONFIG_MODULES=y`,
  `CONFIG_MODULE_UNLOAD=y`), paired with mandatory module signing and
  `MODULE_SIG_FORCE=y`. Early-boot drivers remain built in; NVIDIA loads after
  real-root handoff. Embeds AMD family-17h microcode, AX200 API 77, Bluetooth
  `ibt-20-1-3`, RTL8125A, and RTL8156B.
- **Installed firmware (`/etc/agentoo/firmware/bequiet.list`):** Trimmed
  `linux-firmware` selection (AMD microcode comes from `linux-firmware`, not
  `intel-microcode`; NVIDIA GSP firmware is owned by `nvidia-drivers`).
- **Desktop:** Uses shared Hyprland and Kitty defaults.

## Hardware quirks and negative findings

- **NVIDIA packaging ownership:** Gentoo's `x11-drivers/nvidia-drivers` owns
  the Nouveau blacklist, DRM modesetting defaults, and Dracut configuration—do
  not duplicate them in `/etc`.
- **Same-version kernel rebuilds:** Rebuilding the same `gentoo-kernel` version
  does not change `virtual/dist-kernel`'s subslot; explicitly rebuild
  `x11-drivers/nvidia-drivers` before rebooting (see
  [Bequiet modules and NVIDIA](../kernel.md#bequiet-modules-and-nvidia)).
- **Module signature inspection:** `kmod` built without OpenSSL prints empty
  `modinfo` signer fields even when PKCS#7 signatures are valid; verify kernel
  enforcement at boot via `/sys/module/module/parameters/sig_enforce`.
- **Benign firmware note:** Optional `iwl-debug-yoyo.bin` is absent from broad
  `linux-firmware` and unnecessary.

## Peripheral and workflow notes

- Dual-boots Linux and Windows on separate drives with Secure Boot enabled.
- Binary fallback (`gentoo-kernel-bin`) is scoped to console/network recovery
  (`systemd.unit=multi-user.target systemd.mask=getty@tty1.service`; NVIDIA and
  desktop graphics are outside the recovery requirement). See
  [kernel.md](../kernel.md#binary-fallback) and
  [secure-boot.md](../secure-boot.md).
- Pending same-version rebuild and version-update checks live in
  [card 052](../../kanban/Backlog/052-native-kernel-maintenance-followups.md).
