# Build and validate bequiet kernel v0.3 with NVIDIA support

Created: 2026-10-25
Status: Backlog

## Context and module exception

Bequiet needs external NVIDIA modules. The shared configuration stays
`MODULES=n`; the operator manually enables modules in bequiet's derived config.
No candidate build/boot or NVIDIA runtime acceptance is recorded. The existing
module-enabled preview still contains thinktop boot inputs and is not a ready
bequiet configuration. See [shared follow-ups](027-shared-kernel-v0.3-followups.md).

## Build, NVIDIA and compute

- [ ] Prepare bequiet boot parameters, AMD firmware/microcode and fresh
  initramfs. Build a portable target from the same shared driver union.
- [ ] Enable `MODULES` manually in the derivative and review all normalization
  deltas. Prefer `MODULE_UNLOAD=y` for maintenance/reload; unloading is not
  asserted to be a prerequisite for basic driver loading or compute.
- [ ] Identify and build the actual NVIDIA driver against the final target
  release. Verify signing/lockdown requirements and kernel/module compatibility.
  The exploratory defaults signed modules without forced signature enforcement;
  the installed NVIDIA version was not collected.
- [ ] Validate NVIDIA graphics and required GPU compute workloads. Preserve
  HMM/device-private/MMU-notifier support and the current Xe selector chain;
  Nouveau stays off. Any independent HMM selection/Xe removal is separate work.

## AMD platform and peripherals

- [ ] Verify AMD KVM guest acceleration and AMD-Vi/IVRS/IOMMU initialization,
  groups and DMA-fault logs. Check NVMe/SATA/USB/network/NVIDIA DMA compatibility.
  Keep PSP/AMDTEE/SEV exclusions when normalizing the derivative.
- [ ] Review actual GPU/PCI passthrough grouping, interrupt remapping, reset,
  ownership and host setup before testing assignments; no suitability has yet
  been demonstrated by the static driver audit.
- [ ] Verify both AMD `1022:7901` AHCI controllers, ST3000DM008/ST3000DM001
  disks, existing data access and link/reset/power behavior. Use persistent disk
  identifiers. Any suspend/resume test must reflect the host's intended use.
- [ ] Test both Ethernet ports (IGB and R8169), Wi-Fi/Bluetooth and attached
  USB/dock networking as used, including actual link speeds/reconnect.
- [ ] Check IT87/it8792 and other expected temperature/fan/voltage channels
  against the distribution kernel; validate used RTC/watchdog/platform functions.
- [ ] Test ALC1220 analog audio (retained ALC882 family), NVIDIA HDMI/DP,
  S/PDIF and USB audio as used, plus displays and recorded input peripherals.
- [ ] Complete applicable networking, storage, security and diagnostics
  validation from the shared card.

## Evidence

Use the bequiet inventory dated 2026-10-24, AHCI/KVM/IOMMU checkpoints28/33–35,
GPU/HMM evidence in checkpoints20–23, and the module-override findings in final
audit checkpoint50. The shared card identifies the workspace and evidence index.
