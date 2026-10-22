# Trim installed firmware through host selected savedconfig

Created: 2026-10-15
Status: Completed
Opened: 2026-10-22
Closed: 2026-10-22

## Closure and disposition

Closed at the operator's request after the native savedconfig rebuild and
operator-confirmed installed-size, initramfs, boot and functional checks. The
reviewed distribution-kernel boot has no unresolved firmware-loading failure.

A real linux-firmware version update and broad-coverage restoration exercise are
explicitly deferred, not claimed as tested. Follow the operator guide during the
next applicable maintenance; closure accepts these recorded limits.

## Objective and scope

Use Gentoo's native `linux-firmware[savedconfig]` to trim installed firmware on
Thinktop, keeping other hosts on broad coverage. Keep the custom and distribution
recovery kernels' requirements, supported peripherals, aliases and API fallback
versions. This does not change kernel driver configuration or automatically
change firmware embedded in a kernel/initramfs. SOF, CPU microcode and wireless
regulatory data belong to separate packages and are not trimmed here.

The [baseline card](../Completed/014-single-binary-kernel-baseline.md) is
historical evidence; its earlier manifest is not the current selection.
[Kernel reduction](../Completed/016-kernel-reduction-and-evidence.md) was retired
and is separate work.

## Implementation — 2026-10-22

At the operator's request, use native savedconfig and manual maintenance instead
of the initially prepared hooks, WHENCE parser, automatic checks and binary
rejection. Those custom implementations and their tests have been removed.

- Common/selected-host `make.conf.d` fragments set
  `AGENTOO_LINUX_FIRMWARE_USE`; `package.env/kernel` applies it only to
  linux-firmware. Thinktop enables savedconfig; generic/QEMU/Startop disable it.
  The previous package.use override is removed because it would override
  package.env. Files remain uncompressed for custom-kernel embedding.
- `etc/agentoo/firmware/thinktop.list` contains 43 explicit firmware paths,
  grouped by hardware with rationale. It has no globs or automatic expansion.
- The operator installs the selected list into the machine-local native path
  `/etc/portage/savedconfig/sys-kernel/linux-firmware`. Other hosts must review
  their own input before opting into savedconfig; the installer does not choose
  or copy a list automatically.
- Gentoo prefers a matching PF (version/revision), then P (version), then PN
  (unversioned) savedconfig. At each level it checks target-triplet/build-triplet
  locations before the plain category location. Move matching higher-priority
  inputs aside when applying a new list, including the existing broad
  `sys-kernel/linux-firmware-20260622` input. Confirm the chosen path in the log.
- A successful build writes a versioned snapshot of installed files. An older
  version's snapshot does not shadow a different new version, but a snapshot
  of the same version shadows subsequent unversioned edits. There is no custom
  guard: reviewing precedence, missing/renamed paths and new dependencies is
  operator maintenance. Use source builds when applying/revising/updating the
  selection; USE flags do not identify its contents or revision.

See the [operator guide](../../docs/firmware.md) for application, the maintenance
table, diagnostics and broad-coverage recovery. The shorter configuration summary
is in [etc/agentoo/README.md](../../../../../../etc/agentoo/README.md#installed-firmware-selection).

## Evidence and limits

- Initial inventory ran kernel `6.18.54-agentoo-v0.2`; distribution kernels `.54` and `.57`
  are installed. At that point linux-firmware was `20260622`, with savedconfig off.
- The operator's `../agentoo-build/kernel/6.18.54-agentoo-v0.2/.config` has the
  same 17 embedded firmware paths as `/proc/config.gz`. Its
  `.config.before-v0.3-cull` backup exactly matches the full running config;
  the current `.config` has other later edits. All 12 embedded linux-firmware
  paths are retained; the other five belong to SOF/wireless-regdb.
- Current hardware/logs confirm Intel graphics, Wi-Fi, Bluetooth and SoundWire
  audio. Local 6.18.57 driver source corroborates graphics, NPU 37xx and NVIDIA
  GB206 firmware names. NPU and NVIDIA recovery-driver payloads remain selected
  even though those devices are not currently bound in the custom kernel.
- The explicit list retains matching packaged Wi-Fi API versions, PNVM,
  graphics, Bluetooth, codec/amplifier tuning and shared payload/link targets.
  On updates, additions such as newer Wi-Fi APIs need manual review and edits.
- The original staged integration used upstream 20260622 WHENCE/installer with
  Gentoo's r9 savedconfig patch and installed payloads. All 27 regular payloads
  match the installed package's VDB checksums. The final explicit native list
  is rechecked through the same installer, without Agentoo build hooks.
- Expected image: **43 paths (27 regular files, 16 symlinks), 92,648,212 payload
  bytes**, versus **1,929,485,517 bytes** in current package-owned regular files.
  Projected saving: **1,836,837,305 bytes (95.2%)**. This is staged output, not
  measured post-merge filesystem allocation or kernel/initramfs savings.
- Disposable exact path/link/hash evidence remains at
  `/tmp/agentoo-018-stage/evidence.json`. Portage's configuration API confirms
  only Thinktop enables savedconfig, with unrelated packages unaffected; an
  environment `USE=-savedconfig` override supports broad-coverage recovery.
- The initial staging checks preceded live deployment. The operator subsequently
  confirmed the installed-size check and remaining boot/initramfs/hardware checks.
  See the live log review below. Prior tests of the removed custom implementation
  are not acceptance of native maintenance.

## Completion criteria

- [x] Prepare Thinktop-only native savedconfig policy and reviewed explicit list.
- [x] Install the selected input, resolve higher-priority savedconfigs and rebuild;
  43 retained paths verified, with the installed-size check confirmed by the operator.
  Numeric size figures above remain staged measurements.
- [x] Check regenerated distribution initramfs images and separately maintained
  custom artifacts so old copies do not conceal missing installed firmware.
- [x] Verify cold boot, suspend/resume, graphics, Wi-Fi, Bluetooth, audio, NPU and
  supported peripherals on custom and distribution recovery kernels as applicable.
- [ ] Deferred: exercise a real package-version update and broad-coverage
  restoration. These were not tested before closure; list application and
  snapshot review were exercised during the initial rebuild.
- [x] Document maintenance and recovery in a short operator guide.

## Live boot log review — 2026-10-22

The operator confirmed the installed-size check, then confirmed the remaining
boot/initramfs/hardware checks. The generated versioned savedconfig was compared
with the reviewed host list: exactly 43 paths, no missing or extra entries.

Read-only journal review finds the current boot runs `6.18.57-gentoo-dist-bin`
(boot ID `f8fd554f40eb4b5f8ae75437aa491162`, started 11:33:57 EDT). Intel graphics
DMC/GuC/HuC/GSC, Bluetooth SFI/DDC, NPU 37xx, NVIDIA GB206 GSP and SOF/Cirrus
codec/amplifier firmware all show successful initialization/loading. No unresolved
firmware-load failure appears in the available current-boot journal.

Wi-Fi requests absent `iwlwifi-bz-b0-fm-c0-c99.ucode` (error -2), then successfully
loads `iwlwifi-bz-b0-fm-c0-101.ucode`, version `101.6ef20b19.0`. The identical
request failure and successful fallback appear in the preceding custom-kernel
boot, so this is not a new trimming regression.

Other boot messages include BIOS `_OSI(Linux)`, Nouveau display-output warnings,
a missing `tpm2_id` helper, PMC telemetry and SPI JEDEC errors; these are not
missing linux-firmware payload reports. Log success alone does not establish
full workload acceptance. A real package update and broad-restoration exercise
remain unrecorded and are explicitly deferred by the closure above.
