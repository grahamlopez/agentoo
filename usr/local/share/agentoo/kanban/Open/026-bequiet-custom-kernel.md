# Onboard Bequiet custom kernels

Status: Open — custom kernel, Windows, console recovery and trimmed firmware accepted; maintenance outstanding

## Goal and scope

This card defines and tracks Bequiet custom-kernel onboarding. First get a
booting kernel with NVIDIA graphics/compute and required hardware working while
Secure Boot is disabled. The unsigned candidate and trimmed firmware are accepted
on both boot paths; the signed custom candidate boots with Secure Boot and
module enforcement active. Windows and console/network fallback acceptance under
Secure Boot are confirmed. Finish driver-update maintenance and the remaining
authentication/backup items with the existing implementation.

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
- [x] Operator confirms the remaining boot and hardware acceptance checks.
- [x] Both GPUs appear in `nvidia-smi` with driver `595.104.02`; Hyprland is
  running on the RTX PRO 2000. Retained module build links resolve after reboot.
- [x] Operator confirms intended display arrangements and required workloads.
- [x] Operator confirms used NVMe/SATA data access, Ethernet/Wi-Fi/Bluetooth, USB/dock/input,
  audio, camera/microphone and sensors. Test intended suspend/resume and keyboard
  transition.
- [x] AMD KVM and IOMMU initialize; `/dev/kvm` exists. Broader passthrough/workload
  testing stays in the [shared card](../Backlog/027-shared-kernel-v0.3-followups.md).

## Existing workflow maintenance

The native-consumer audit and proposed package-based replacement are recorded in
[card 051](../Backlog/051-gentoo-kernel-native-workflow.md). Finish this onboarding
with the current commands and explicit native targeting where needed.

- [ ] Document and verify NVIDIA maintenance for the custom kernel using native
  source/output settings. Keep driver and userspace versions aligned. The packaged
  fallback is console/network recovery and does not require NVIDIA; no cross-kernel
  updater is required.
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
- [x] Operator confirms all remaining post-trim cold-start, Wi-Fi connectivity,
  Bluetooth keyboard, USB Ethernet, audio/camera/microphone and intended
  suspend/resume acceptance on both kernels.

## Secure Boot onboarding and driver maintenance

- Secure Boot prerequisite: both configs enable `IMA_ARCH_POLICY` and
  `MODULE_SIG`. Native `security/integrity/ima/ima_efi.c:arch_get_ima_policy`
  enables module-signature enforcement when EFI Secure Boot is active, even
  without `MODULE_SIG_FORCE`. The custom candidate's module trust is accepted
  below; the fallback NVIDIA modules remain unsigned. EFI image signing/enrollment
  alone is insufficient for that fallback's NVIDIA support.
- Host state: sbctl's PK/KEK/db are enrolled, Setup Mode is disabled and Secure
  Boot is enabled. Boot0008 is current and first in BootOrder; the bring-up and
  packaged fallback entries remain available.
- [x] Create Bequiet's sbctl identity, Owner GUID
  `b4bd2c67-353c-47a8-abbc-349782544a03`. Public db certificate SHA256:
  `77:C1:03:91:89:72:F0:14:16:FA:DF:C3:47:88:B6:70:5D:D1:72:72:68:5E:09:E0:5C:21:30:29:5C:FA:90:3B`.
- [x] Operator confirms backup of `/var/lib/sbctl` to secure offline storage and
  archive verification before proceeding with trust configuration or enrollment.
- [x] Prepare native signing policy: kernel trusts `/etc/kernel/certs/db.pem`;
  NVIDIA enables `modules-sign` and uses that public certificate plus sbctl's
  private db key. No installer runtime code or certificate snapshots are added.
- [x] Publish `/etc/kernel/certs/db.pem` with mode `0644`; its SHA256 fingerprint
  matches the backed-up sbctl identity above. The selected source remains
  `/usr/src/linux-6.18.62-gentoo`.
- [x] Apply repository policy live and configure `bequiet-secure`. Its recorded
  host fragment matches live policy, resolved config trusts the public certificate,
  and effective NVIDIA settings enable `modules-sign` with the intended key/cert.
- [x] Build `bequiet-secure`. Retained image/config match completed-build hashes,
  native kernel release matches, and the compiled trusted-certificate list is an
  exact DER match to the public db certificate. Live NVIDIA signing policy remains
  enabled with the intended key/cert.
- [x] Install `bequiet-secure`: `sbverify` accepts the EFI image with the public
  db certificate; OpenSSL verifies all four installed NVIDIA module signatures
  against that certificate. Module version/release and retained build link match.
  Host kmod lacks OpenSSL support, so blank `modinfo` signer fields do not indicate
  unsigned modules. Secure Boot remains disabled.
- [x] Operator's root EFI listing confirms Boot0008 points to the signed
  `bequiet-secure` image on the intended ESP, with no extra arguments. Boot0007
  is current and the distribution fallback remains Boot000A.
- [x] Boot the separate signed candidate through BootNext with
  `module.sig_enforce=1` and Secure Boot disabled. BootCurrent is 0008, expected
  release/command line match, and `sig_enforce` is `Y`. The journal confirms the
  db certificate loaded; all four NVIDIA modules are loaded, both GPUs appear
  with driver `595.104.02`, Hyprland runs and systemd reports no failed units.
  BootNext is consumed; the unsigned bring-up entry remains first in BootOrder.
- Fallback requirement: the operator accepts a full console boot with networking.
  Keep the packaged kernel/initramfs and existing firmware selection. Do not add
  Shim/MOK, Nouveau support or local NVIDIA module trust for this recovery path.
- [x] Accept Boot000A console/network recovery with Secure Boot enabled and
  Setup Mode disabled. Its tested entry retains root/initramfs inputs and adds
  `systemd.unit=multi-user.target systemd.mask=getty@tty1.service`. Console login
  works, encrypted Btrfs `@` is read/write, Ethernet has an address, DNS resolves,
  HTTPS returns 200 and systemd reports no failed units. The packaged kernel
  enforces module signatures; no separate module blacklist is needed for this
  accepted recovery path. BootNext is consumed and signed Boot0008 remains the
  default for the next ordinary reboot.
- [x] Recheck enrollment inputs: SetupMode=1, SecureBoot=0 and no active
  PK/KEK/db/dbx; firmware default databases exist. Both Linux EFI signatures
  verify against their respective local/package certificates. Gentoo fallback
  certificate SHA256:
  `B9:09:37:4A:D0:AB:39:B2:7E:7D:73:B3:EA:B6:E9:98:09:C9:76:CA:6C:92:BD:35:A5:75:23:14:6E:28:CE:F7`.
- [x] Operator confirms Windows Secure Boot acceptance and the requested
  encryption/protection checks, including normal unlock after reboot and resuming
  BitLocker if it was suspended. Its recovery key is backed up if applicable.
- [x] Put the tested signed Boot0008 first in BootOrder, preserving the other
  entries and their relative order. Native EFI reports it as current/default.
- [ ] After staging Gentoo's certificate, refresh the offline `/var/lib/sbctl`
  backup under a new archive name and verify it, as required by the guide.
- [x] Stage Gentoo's certificate and run native enrollment with
  `--microsoft --firmware-builtin --custom`. The command reports success; the
  enrolled list includes the local PK/KEK/db identities, Gentoo, Microsoft and
  Gigabyte. PK/KEK/db variables exist and enrollment survives restart.
- [x] Restart and accept the custom kernel under firmware enforcement.
  `sbctl status` and EFI variables confirm SetupMode=0 and SecureBoot=1;
  `6.18.62-gentoo-bequiet-secure` boots with `sig_enforce=Y`. All four NVIDIA
  modules load, both GPUs work with driver `595.104.02`, Hyprland runs and there
  are no failed systemd units. The journal confirms Secure Boot and the expected
  db certificate. The console/network fallback is accepted separately above.

Close after the agreed host checks and later phases are complete or explicitly
split into separate cards. Record completion in the finishing commit and board
index, then delete this card per board policy.
