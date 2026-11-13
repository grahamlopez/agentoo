# Onboard Bequiet custom kernels

Status: Open — unsigned first-boot implementation; host acceptance pending

## Goal and scope

This card defines and tracks Bequiet custom-kernel onboarding. First get a
booting kernel with NVIDIA graphics/compute and required hardware working while
Secure Boot is disabled. Signing/enrollment, firmware trimming and driver-update
maintenance across installed kernels follow that acceptance; do not implement
those mechanisms in the first-boot patch.

Use the selected native Portage profile, shared kernel capability union and
existing config/build/install commands. Keep software/module processing under
Portage ownership, storage identity local and one authoritative workspace.
General command usage lives in [kernel.md](../../docs/kernel.md).

## Host inputs

- Profile: `agentoo:hosts/bequiet`; Ryzen 9 3950X, X570 AORUS MASTER/F39,
  approximately 128 GiB RAM.
- Working fallback: `6.18.62-gentoo-dist-bin`; NVIDIA open driver `595.104.02`;
  RTX PRO 2000 Blackwell and RTX 6000 Ada.
- Btrfs `@` on LUKS2 `cryptroot`, NVMe storage and a separate FAT ESP. Actual
  discovery passes outside the sandbox; keep UUIDs out of tracked policy.
- USB Lily58 unlock works on the distribution kernel; the operator switches to
  Bluetooth at the desktop. Early Bluetooth is not required.
- `@kernel-dev` is installed. Pin the concrete Gentoo source path per workspace.
- Firmware and module choices live in the
  [Bequiet fragment](../../../../../../etc/agentoo/kernel/hosts/bequiet.config).
  Installed firmware stays broad until boot acceptance.

## First-boot implementation

- [x] Add the reviewed fragment with modules/unloading, AMD microcode and host
  firmware. Keep the shared driver union and Nouveau exclusion. Shared
  `GIGABYTE_WMI=y` covers the current temperature driver.
- [x] Keep configuration and completed builds in
  `${XDG_STATE_HOME:-$HOME/.local/state}/agentoo/kernel/<release>`. Default builds
  compile in `/dev/shm/<release>` and copy completed results back. Failed RAM
  workspaces remain available for inspection, without automatic retry or copying
  partial compile results back. Explicit `--build-dir` builds directly in place.
- [x] Use native prepare and module staging at the retained location, preserving
  completed image/config hashes and recording stable module build links. Retain
  installed source trees for NVIDIA compilation.
- [x] Allow modules while requiring built-in boot capabilities. Check recorded
  NVMe/AHCI transport, device-mapper/AES-XTS/Btrfs, API filesystems, GPT/ELF,
  USB/xHCI/HID and a framebuffer console before and after Kconfig resolution.
- [x] Preserve native source EXTRAVERSION, including `-gentoo`, so Kbuild and
  Portage agree on the custom release; never edit the source Makefile.
- [x] During install, rebuild the exact installed NVIDIA package with explicit
  `KERNEL_DIR`/`KBUILD_OUTPUT`. Native `FEATURES=-userpriv` lets this transaction
  read the private user workspace without changing home permissions. Check all
  four required modules' versions, vermagic and installed paths.
- [x] Activate the image only after NVIDIA succeeds. On NVIDIA failure, restore
  the previous module tree when replacing a release and retain failed files.
  Preserve the distribution fallback and existing image/EFI behavior.
- [x] Select unsigned module policy. First-candidate installation uses existing
  `install --unsigned`; no certificate snapshots or signing-policy machinery.
- [x] Reduced implementation: all 394 Python tests pass (the sandbox-blocked SSH
  socket test passes separately with socket access), as do all six Lua checks.
  Native Kconfig preserves shared built-ins and boot requirements; certificate
  objects compile without generating a private key. Diff whitespace checks pass.

## Validation and host acceptance

- [x] Development checks: native Kconfig resolution, full RAM kernel build and
  retained-object reuse, actual NVIDIA source compilation, and agreement between
  real Gentoo linux-info and Kbuild release detection. Development images used
  synthetic storage and were deleted; they were not host boot candidates.
- [x] Host storage smoke test: archived cryptsetup unlocks disposable LUKS2
  without udev, creates its mapping with discards and BusyBox mounts Btrfs `@`
  read-only. The handoff rule restores UUID-link/systemd readiness after the
  missing-rule failure is reproduced. This does not establish physical boot.
- [ ] Apply changes to the live host and configure/build a fresh bring-up label
  from the shared baseline with explicit Gentoo sources and actual root identity.
- [ ] Install unsigned with the real native NVIDIA package transaction; inspect
  image/modules and register a separate firmware entry. Keep the fallback usable.
- [ ] Cold boot: visible console, USB Lily58 input, incorrect/correct passphrase,
  encrypted Btrfs root, systemd startup, expected release and early microcode.
- [ ] Check both GPUs with `nvidia-smi`, displays/Hyprland and required compute.
- [ ] Check used NVMe/SATA data access, Ethernet/Wi-Fi/Bluetooth, USB/dock/input,
  audio, camera/microphone and sensors. Test intended suspend/resume and keyboard
  transition. Confirm retained module build links still resolve after reboot.
- [ ] Verify AMD KVM/IOMMU initialization; broader passthrough/workload testing
  stays in the [shared card](../Backlog/027-shared-kernel-v0.3-followups.md).

## After first-boot acceptance

- [ ] Design and implement native NVIDIA module signing and kernel trust, then
  provision/back up keys and accept both Linux boot paths and Windows with
  Secure Boot enabled. Reuse native mechanisms before adding workspace state.
- [ ] Establish subsequent driver-update maintenance for the custom and fallback
  kernels. Do not add a cross-kernel update command before settling this scope.
- [ ] Review/add the Bequiet linux-firmware savedconfig and native USE policy;
  apply through existing firmware commands and revalidate both boot paths. Cover
  peripherals/cold initialization/resume. Retain linux-firmware-owned AMD microcode;
  regulatory data and NVIDIA GSP firmware have separate package ownership.

Close after the agreed host checks and later phases are complete or explicitly
split into separate cards. Record completion in the finishing commit and board
index, then delete this card per board policy.
