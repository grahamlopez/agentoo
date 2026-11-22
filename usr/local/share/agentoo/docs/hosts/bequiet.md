# Bequiet hardware baseline

## Hardware identity

- **System:** Desktop workstation, Gigabyte X570 AORUS MASTER (AMI BIOS `F39`).
- **CPU:** AMD Ryzen 9 3950X (Zen 2, 16 cores / 32 logical CPUs).
- **Graphics:** Dual NVIDIA GPUs—RTX PRO 2000 Blackwell (`10de:2d30`) and RTX
  6000 Ada (`10de:26b1`).
- **Networking & Bluetooth:** Intel Wi-Fi 6 AX200 (`8086:2723`, `iwlwifi`),
  Intel USB Bluetooth (`8087:0029`), Intel I211 1GbE (`8086:1539`, `igb`),
  Realtek RTL8125 2.5GbE (`10ec:8125`, `r8169`).
- **Audio:** AMD Starship/Matisse HD Audio (`1022:1487`, Realtek ALC1220 codec,
  `snd_hda_intel`) plus NVIDIA HDMI/DP audio (`10de:22eb`, `10de:22ba`).
- **Storage & sleep:** Three NVMe SSDs—WD_BLACK SN770 2 TB (`15b7:5017`),
  Samsung 980 1 TB (`144d:a809`), and Samsung 970 EVO 1 TB (`144d:a808`); two
  AMD FCH AHCI SATA controllers (`1022:7901`) with two 3 TB Seagate HDDs
  (`ST3000DM008`, `ST3000DM001`); `s2idle [deep]` sleep.

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
  real-root handoff. Embeds AMD family-17h microcode, AX200 Wi-Fi, Intel
  Bluetooth, RTL8125, and RTL8156 dock Ethernet firmware.
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
