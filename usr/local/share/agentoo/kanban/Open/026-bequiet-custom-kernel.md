# Onboard Bequiet custom kernels

Status: Open — unsigned boot accepted; finish onboarding with the existing implementation

## Goal and scope

This card defines and tracks Bequiet custom-kernel onboarding. First get a
booting kernel with NVIDIA graphics/compute and required hardware working while
Secure Boot is disabled. The unsigned candidate now boots; apply reviewed firmware
trimming next. Signing/enrollment and driver-update maintenance across installed
kernels remain separate work.

Complete this card using the existing implementation. The proposed thin wrapper
around Gentoo's source-built kernel package is deferred to
[card 051](../Backlog/051-gentoo-kernel-native-workflow.md); it is not a requirement
for closing Bequiet onboarding.

Use the selected native Portage profile, shared kernel capability union and
existing config/build/install commands. Keep software/module processing under
Portage ownership, storage identity local and one authoritative workspace.
Use bounded native kernel-context settings for remaining maintenance operations;
document current limitations rather than redesigning the kernel backend here.
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
  Installed linux-firmware selection lives in the
  [Bequiet list](../../../../../../etc/agentoo/firmware/bequiet.list).

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
- [x] Apply changes to the live host and configure/build `bequiet-bringup`
  from the shared baseline with explicit Gentoo sources and actual root identity.
  Completed image/config and staged module manifest checks pass. Built-in boot
  requirements pass; the retained module build link resolves after RAM cleanup.
- [x] Install unsigned with the real native NVIDIA package transaction. Installed
  image matches the completed build; all four required NVIDIA modules have the
  expected version/release and paths, with a valid retained build link. The
  distribution fallback image, initramfs and matching NVIDIA modules remain.
- [x] Register and boot the separate candidate entry. Firmware reports
  BootCurrent=0007, candidate first in BootOrder; distribution fallback 000A
  remains available. No BootNext is currently set.
- [ ] Diagnose and resolve SIGQUIT during fresh sudo authentication.
  Password entry terminated the installer with SIGQUIT; standalone `sudo -v`
  bypassed it. The helper predates the Bequiet changes. Isolate the regression
  before changing the workflow. Authentication-only trials of the unchanged
  helper both alone and after native NVIDIA lookup pass; the lookup leaves
  terminal settings unchanged. Full preflight reproduces a kernel-generated
  SIGQUIT before any privileged installation operation, but also passes unchanged.
  Confirmation-only authentication passes. Preflight leaves the quit character
  (`0x1c`), canonical/signal settings and foreground group unchanged. Investigate
  intermittent terminal input/authentication interaction: failures occur during
  manual typing on a Bluetooth Lily58; compare another keyboard in the same
  terminal. Do not record passwords. Require fresh-authentication acceptance for
  the fix.
- [x] Boot `6.18.62-gentoo-bequiet-bringup`: operator confirms visible console
  and working USB Lily58 unlock. Encrypted Btrfs `@` is mounted read/write;
  systemd reports no failed units. Microcode revision is `0x08701035`.
- [ ] Check incorrect-passphrase retry and cold power-on if this was a warm reboot.
- [x] Both GPUs appear in `nvidia-smi` with driver `595.104.02`; Hyprland is
  running on the RTX PRO 2000. Retained module build links resolve after reboot.
- [ ] Check intended display arrangements and required GPU compute workloads.
- [ ] Check used NVMe/SATA data access, Ethernet/Wi-Fi/Bluetooth, USB/dock/input,
  audio, camera/microphone and sensors. Test intended suspend/resume and keyboard
  transition.
- [x] AMD KVM and IOMMU initialize; `/dev/kvm` exists. Broader passthrough/workload
  testing stays in the [shared card](../Backlog/027-shared-kernel-v0.3-followups.md).

## Existing workflow maintenance

The native-consumer audit and proposed package-based replacement are recorded in
[card 051](../Backlog/051-gentoo-kernel-native-workflow.md). Finish this onboarding
with the current commands and explicit native targeting where needed.

- [ ] Document and verify the existing NVIDIA maintenance procedure for the
  custom and fallback kernels using native source/output settings. Keep driver
  and userspace versions aligned; no new cross-kernel updater is required.
- [x] Confirm the explicit context for this firmware application: run firmware
  apply as root with native `KERNEL_DIR=/usr/src/linux-6.18.62-gentoo-dist-bin`
  and empty `KBUILD_OUTPUT`. Native Portage preserves these settings and the
  firmware hook finds the prepared image/map and reaches its `--all` installation
  call in a non-mutating check. The global eselect target stays on Gentoo sources;
  actual fallback regeneration remains part of application acceptance below.

## Firmware trimming

- [x] Review the normal-use inventory with the operator. Select seven explicit
  paths for AMD family-17h microcode, AX200 API 77 (payload/root alias), Intel
  Bluetooth SFI/DDC and RTL8125A/RTL8156B Ethernet. Both kernels load these network
  names. NVIDIA GSP and regulatory data stay separately package-owned.
- [x] Add the host list and native `savedconfig -deduplicate -compress-xz
  -compress-zstd` policy. Projected regular payload: 2,200,953 bytes instead of
  2,087,238,841 bytes (99.9% reduction); applied measurements match this selection.
  Selected installed-package checksums and the Wi-Fi alias match. Four native
  profile tests and sixteen firmware workflow tests pass; checkout-policy dry-run
  identifies the versioned snapshot to retire. No workflow code was added.
- [x] Apply repository policy and rebuild `sys-kernel/linux-firmware-20261019`
  using the explicit native context. Installed payload is six regular files and
  one symlink, exactly 2,200,953 bytes; installed paths and durable input match
  the host list. The old versioned snapshot is backed up by the existing workflow.
- [x] Verify fallback image/initramfs regeneration. The new initramfs contains
  AMD microcode; the custom image still matches its recorded completed-build hash.
- [x] Accept the protected versioned snapshot at
  `/etc/portage/savedconfig/sys-kernel/linux-firmware-20261019`. Firmware status
  confirms that the active versioned snapshot, durable input and installed paths
  all match the seven-entry host list. Installed payload is 2,200,953 bytes.
- [x] Reboot the custom kernel after trimming. Expected release, read/write
  encrypted root, both NVIDIA GPUs and no failed systemd units are confirmed.
  AX200 API 77 and Bluetooth firmware initialize; the Lily58 appears over USB
  and Bluetooth. Onboard RTL8125A links at 2.5 Gb/s. No missing-firmware errors
  are observed; embedded firmware still limits what this proves about disk inputs.
- [x] Boot the distribution fallback after trimming (BootCurrent=000A).
  Expected release, read/write encrypted root, both GPUs and no failed units
  are confirmed. AX200 API 77 and Intel Bluetooth firmware load, both USB and
  Bluetooth Lily58 devices appear, and RTL8125A links at 2.5 Gb/s. Microcode is
  `0x08701035`; no missing-firmware errors are observed. This kernel embeds no
  extra firmware, providing evidence for the trimmed installed selection.
  The native selector still points to Gentoo sources; the custom entry remains
  first in BootOrder and BootNext is clear.
- [ ] Confirm a full power-off/start of the custom kernel if its post-trim boot
  was only a restart. Exercise Wi-Fi connectivity, Bluetooth keyboard, USB
  Ethernet, audio/camera/microphone and intended suspend/resume on both kernels.

## Deferred signing and driver maintenance

- [ ] Design and implement native NVIDIA module signing and kernel trust, then
  provision/back up keys and accept both Linux boot paths and Windows with
  Secure Boot enabled. Reuse native mechanisms before adding workspace state.
- [ ] Establish subsequent driver-update maintenance for the custom and fallback
  kernels. Do not add a cross-kernel update command before settling this scope.

Close after the agreed host checks and later phases are complete or explicitly
split into separate cards. Record completion in the finishing commit and board
index, then delete this card per board policy.
