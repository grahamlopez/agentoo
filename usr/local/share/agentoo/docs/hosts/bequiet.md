# Bequiet hardware baseline

The local saved inventory `bequiet-inventory-20261024.tar.gz` was collected on
2026-10-24 as `kernel-inventory-bequiet-20261024T140803Z.tar.gz`, running
`7.2.6-gentoo-dist`. It reports a Gigabyte X570 AORUS MASTER (BIOS F39),
AMD Ryzen 9 3950X (Zen 2, 16 cores / 32 logical CPUs), and two NVIDIA GPUs:

- RTX PRO 2000 Blackwell, PCI `10de:2d30`.
- RTX 6000 Ada Generation, PCI `10de:26b1`.

Both GPUs were bound to `nvidia`; boot evidence references NVIDIA 580.178.04
GSP firmware. The package inventory does not record the installed NVIDIA package
version. The collection reports no issues, but its virtualization command exited
nonzero. It does not establish workload or new-install acceptance, RAM capacity,
or Secure Boot status.

## Installation policy

Use `--target-host bequiet` on the destination hardware. The native Portage
profile inherits Agentoo's common AMD64 desktop/systemd baseline, selects
`-march=znver2` for GCC and `-C target-cpu=znver2` for Rust, and replaces the
upstream graphics defaults with `VIDEO_CARDS="nvidia"`. Build storage and job
counts retain native defaults; installer transactions use the shared RAM-build
policy unless `--no-ram-builds` is selected.

The profile includes `>=x11-drivers/nvidia-drivers-580` in `@profile`, independent
of GUI installation, with modules, tools and Wayland support. Blackwell requires
NVIDIA's open kernel modules. The profile enables `kernel-open` for driver
versions below 595; Gentoo's >=595 ebuilds provide only open modules and remove
that USE flag. No testing keyword or driver version pin is added.
See [Gentoo's kernel-open description](https://packages.gentoo.org/useflags/kernel-open).

The initial world update excludes NVIDIA until local boot inputs and kernel
tools are prepared. The kernel phase includes `@profile` alongside
`sys-kernel/gentoo-kernel-bin`, so Portage selects the binary kernel provider
before building NVIDIA modules. Shared `dist-kernel` USE policy
and Gentoo's native external-module integration rebuild NVIDIA modules for the
binary fallback kernel. The kernel phase regenerates the initramfs after modules are ready and checks
their release compatibility. No unconditional external-module rebuild follows
the package transaction.
Gentoo's NVIDIA package owns the Nouveau blacklist, DRM modesetting defaults,
and its Dracut configuration; Agentoo does not duplicate those settings.

Use the reviewed [linux-firmware savedconfig](../firmware.md#bequiet-selection)
through the existing firmware apply workflow. Both kernels and normal peripherals,
including suspend/resume, are accepted after trimming. AMD microcode comes from that package;
`--microcode auto` detects AMD when installation runs on Bequiet, or select
`--microcode amd` explicitly. A reviewed custom-kernel fragment is supplied;
see the [kernel workflow](../kernel.md) and acceptance below.

## Devices and installation acceptance

The inventory records Intel AX200 Wi-Fi (`iwlwifi`) and Intel USB Bluetooth,
Intel I211 Gigabit Ethernet (`igb`), Realtek RTL8125 2.5GbE (`r8169`), and attached
Realtek USB Ethernet. Audio includes Realtek ALC1220 through `snd_hda_intel`
and both NVIDIA HDMI/DP controllers. Storage includes three NVMe devices,
two AMD `1022:7901` AHCI controllers and two Seagate 3 TB SATA disks.

Before installation, identify the intended whole disk by persistent identity
and confirm which existing data must be preserved. The installer erases the
selected disk and creates its fixed encrypted Btrfs root/home layout. Do not
infer the installation target from the inventory's `nvme` or `sd` numbering.
Provision network credentials locally and confirm Secure Boot/module-signing
requirements before booting. No host-specific EFI registration workaround is
established; use the installer's printed manual registration command.

After boot, run the standard first-boot verifier and confirm NVIDIA driver
loading (`nvidia-smi`, both GPUs), console and display output, and the intended
Hyprland session when installed. Test required GPU compute workloads separately;
the profile does not install a CUDA toolkit or application stack. Validate used
Ethernet ports, Wi-Fi/Bluetooth, NVMe/SATA data access, audio, USB/input devices,
and intended suspend/resume behavior. Display layout retains shared defaults.
Normal-use hardware and suspend/resume acceptance are complete for this host.

## Kernel and Secure Boot

Bequiet is the only host permitted to enable loadable modules in the native
`gentoo-kernel` workflow, paired with mandatory module signing and signature
enforcement (`MODULE_SIG_FORCE=y`) using its enrolled sbctl db key and
certificate. Early-boot drivers remain built in; NVIDIA open modules load after
real-root handoff.

- **Custom kernel (`gentoo-kernel`):** Secure Boot enabled, enforced module
  signatures, NVIDIA open modules on both GPUs, and Hyprland desktop.
- **Binary fallback (`gentoo-kernel-bin`):** Console/network recovery under
  Secure Boot (`systemd.unit=multi-user.target systemd.mask=getty@tty1.service`;
  NVIDIA/desktop are outside the recovery requirement). See the
  [kernel guide](../kernel.md#binary-fallback).
- **Windows:** Direct firmware boot on its separate drive with Secure Boot enabled.

After same-version custom kernel rebuilds, rebuild `x11-drivers/nvidia-drivers`
explicitly before booting. Pending rebuild/update maintenance checks are tracked
in [card 052](../../kanban/Backlog/052-native-kernel-maintenance-followups.md).
See [Bequiet modules and NVIDIA](../kernel.md#bequiet-modules-and-nvidia) and
the [Secure Boot guide](../secure-boot.md).
