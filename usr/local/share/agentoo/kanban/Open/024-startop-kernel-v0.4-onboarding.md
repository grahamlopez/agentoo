# Onboard Startop custom kernel v0.4 and trim installed firmware

Created: 2026-10-25
Updated: 2026-11-05
Status: Open

## Operation and evidence policy

Work through the phases in order, recording dates, commands, artifact paths,
results and unresolved issues below. This card is the operation checklist;
[the kernel guide](../../docs/kernel.md) and
[firmware guide](../../docs/firmware.md) define command behavior.
Checklist preparation does not execute the operations. Keep installation-specific
UUIDs and raw captures local; record durable hardware/policy conclusions in
[Startop's host notes](../../docs/hosts/startop.md).

Use the shared `kernel-shared-v04-config` as the starting config, preserving the
shared driver/capability union. Establish custom-kernel acceptance with broad
installed firmware before trimming. An unchecked item is pending, not evidence
of failure. Mark unused workload/peripheral checks explicitly with their scope.

## 1. Record the current host and recovery path

- [x] Record the running distribution release, installed source/firmware/microcode
  package versions, CPU identity, compiler version, effective firmware USE flags
  and `agentoo kernel firmware` report. Initial read-only inspection found
  `6.18.60-gentoo-dist-bin`, Core Ultra 9 285H, family 6/model 197/stepping 2,
  and microcode revision `0x122` after an early update from `0x121`.
- [x] Record the working distribution EFI image, matching module tree, EFI entry
  and BootOrder; confirm how to select that recovery entry from firmware. Keep
  working recovery media and a current checkpoint. Check Secure Boot state and,
  if enabled, settle image signing/trust before trying the custom candidate.
- [ ] On the unrestricted destination host, verify selector `startop`, mounted
  Btrfs subvolume `@` directly on one LUKS2/GPT mapping, its actual mapper name
  (`cryptroot` at inspection), local `/etc/kernel/cmdline`, fstab and ESP mount.
  Configuration must cross-check the actual storage identity successfully;
  restricted-environment inspection did not establish that validation passes.
- [x] Record operator distribution-kernel acceptance and peripheral scope (see
  session results).
- [ ] Complete PCI/USB and firmware inventory for that scope, including
  disconnected peripherals; preserve it for custom-kernel comparison.
- [ ] Record the current secondary-SSD configuration and suspend mode. Use the
  [power investigation](../../docs/hosts/startop-power.md) when comparing idle
  draw/package states; the existing SSD/root-port resume problem predates this
  custom kernel and must not be treated as a new regression without comparison.

## 2. Prepare tracked host policy

- [ ] Review runtime firmware loads, matching driver metadata/source and owning
  packages for the chosen kernel version. Exercise Bluetooth and peripherals,
  including after resume; distinguish failed optional requests from required
  payloads and successful fallbacks.
- [x] Add `etc/agentoo/kernel/hosts/startop.config` with explicit
  `CONFIG_FW_LOADER=y`, `CONFIG_MICROCODE=y`, `CONFIG_EXTRA_FIRMWARE` and
  `CONFIG_EXTRA_FIRMWARE_DIR="/lib/firmware"`. Include only justified Kconfig
  exceptions; do not put command lines, UUIDs, release labels or workspace paths
  in the fragment. No new host registry or loader is needed.
- [x] Review this candidate embedded selection against that evidence. All paths
  below were present during the initial inspection; presence alone does not
  establish runtime need or complete coverage.

  | Concern | Candidate package-relative paths | Evidence/review |
  | --- | --- | --- |
  | Graphics | `i915/mtl_dmc.bin`, `i915/mtl_guc_70.bin`, `i915/mtl_huc_gsc.bin`, `i915/mtl_gsc_1.bin` | Current boot/resume loads |
  | AX210 Wi-Fi | `iwlwifi-ty-a0-gf-a0-89.ucode`, `iwlwifi-ty-a0-gf-a0.pnvm` | Current loads; verify target-source API compatibility |
  | Bluetooth | `intel/ibt-0041-0041.sfi`, `intel/ibt-0041-0041.ddc` | SFI load observed; review companion DDC requirement |
  | Regulatory data | `regulatory.db`, `regulatory.db.p7s` | Current loads |
  | CPU microcode | `intel-ucode/06-c5-02` | Current CPU signature; verify early update after candidate boot |

- [x] Keep current HDA/ALC233 audio support. No SOF/Cirrus payload requirement
  has been established on Startop; do not inherit Thinktop's embedded selection.
  Review any additional peripheral firmware separately.
- [ ] Audit required devices against shared v0.4 and the chosen sources. Preserve
  the driver union and `CONFIG_MODULES=n` for the default minimal initramfs;
  add shared capabilities only where evidence requires them. Confirm built-in
  storage, encryption, keyboard and graphics support. Dracut's early-i915
  fragment applies to the distribution initramfs, not this minimal initramfs.
- [x] Update the host notes and host-onboarding coverage table when the profile
  is prepared. A data-only fragment does not need duplicate generic loader tests;
  add focused tests for any new behavior introduced during this work.

## 3. Extend custom-kernel EFI registration for Startop

- [ ] Review the installer's and distribution-kernel guidance's existing
  `--full-dev-path` policy and the custom command's registration code. Choose one
  authoritative definition of the registration policy, reusing it across
  activations where practical; avoid parallel hard-coded workaround rules.
- [x] Extend `agentoo kernel install` so Startop registration includes
  `--full-dev-path` in both the printed manual command and `--efi-add-entry`.
  Establish which recorded host identity controls registration; use the
  configured workspace identity rather than a subsequently changed selector.
- [x] Review entry matching with real full-device-path output: recognize the
  correct GPT partition and loader path, reuse a matching entry without creating
  duplicates, and reject matches on another partition or loader. Preserve the
  documented BootOrder behavior and leave BootNext alone.
- [x] Add focused regression coverage for Startop manual/automatic creation,
  full-path entry reuse, wrong partition/path and unaffected other hosts. Update
  kernel documentation to describe the resulting behavior and run the relevant
  repository checks. Record validation before installing/registering a candidate.

## 4. Prepare source and initramfs build inputs

- [ ] Select/install the intended kernel sources (the `@kernel-dev` set includes
  `gentoo-sources` and hardware inspection tools). Initially `/usr/src/linux`
  pointed to `linux-6.18.60-gentoo-dist-bin`; explicitly select the desired tree
  with `--sources` or the native source selector. Record the concrete path and
  version, and ensure it is suitable for an out-of-tree build.
- [ ] Fetch the pinned BusyBox source through Portage with DISTDIR
  `/var/cache/distfiles`; the archive was missing at inspection:
  `sudo emerge --fetchonly --nodeps '=sys-apps/busybox-1.36.1-r4'`.
- [ ] Verify compiler/static libc, make, Python, cpio, loadkeys, strip, cryptsetup
  and linked libraries plus the US/Caps-to-Control keymap. Run the minimal
  builder's documented `--check` with local PARTUUID/mapper inputs before the
  expensive build. This checks inputs, not actual static compilation or boot.
- [ ] Choose writable, executable build storage with sufficient free space and
  explicit job count (start with `-j12`). The restricted environment saw
  `/dev/shm` read-only; verify the real host mount or use `--build-dir` on disk.
  Record the workspace path; `/dev/shm` contents disappear at reboot. Kernel
  CLI jobs do not inherit Portage's MAKEOPTS.

## 5. Configure, build and install a candidate

Paths in the command examples are deployed paths. Supply the chosen `--sources`
and `--build-dir` where needed, and retain the same build directory throughout.

- [ ] Configure with `agentoo kernel config --label agentoo-v0.4 --config
  /usr/local/share/agentoo/docs/kernel-shared-v04-config`. Review new Kconfig
  choices and the printed diff, including dependency changes, resolved host
  settings, firmware presence, local storage identity and generated command line.
  Confirm old baseline UUIDs and Thinktop firmware have been replaced; preserve
  baseline non-storage boot policy intentionally.
- [ ] Build with `agentoo kernel build --label agentoo-v0.4 -j12`. Record compiler
  flags (default KCFLAGS uses `-march=native`), final release, completed config,
  image and fresh embedded-initramfs paths. Check initramfs ownership/embedding,
  staged built-in-module metadata and consistent release naming.
- [ ] Run the documented disposable initramfs storage smoke test against the
  generated archive/work directory. Record unlock, discards, read-only Btrfs
  mount and real-root udev handoff results. This does not establish physical
  keyboard or actual PID 1 boot acceptance.
- [ ] Save the final config and build evidence to a deliberate persistent local
  location before reboot, especially when using `/dev/shm`.
- [ ] Install with `agentoo kernel install --label agentoo-v0.4`. Review the ESP,
  destination, module tree and any replacement backups. Retain the distribution
  recovery image/modules. If signing is required, complete it before registration.
- [ ] Register using the reviewed Startop full-device-path command, or the
  extended `--efi-add-entry` workflow. Inspect the resulting entry, loader path
  and BootOrder. Select a deliberate first test boot; record the actual EFI entry
  used and retain access to the recovery entry.

## 6. Accept the custom kernel with broad installed firmware

- [ ] Cold boot: verify expected `uname -r`, image/config identity, internal and
  USB keyboard unlock, incorrect then correct passphrase, root `@`, mapper name,
  discard policy, systemd startup and normal `/home` mounting.
- [ ] Inspect boot logs and early microcode revision against the recorded
  distribution baseline. Confirm expected i915 DMC/GuC/HuC/GSC loads, Wi-Fi/PNVM,
  Bluetooth and regulatory data; investigate missing firmware and new errors.
- [ ] Desktop: repeated/cold-boot autostart, acceleration, internal/external
  displays, dock hotplug, brightness, backlight, hotkeys, lid and input devices.
- [ ] Camera `1bcf:2ced`: UVC binding, video nodes, real capture and privacy.
- [ ] Audio: speakers, internal mic, headset/jack, HDMI/DP and USB audio as used;
  compare actual operation rather than relying on HDA driver binding.
- [ ] Wi-Fi/Bluetooth: connections, traffic, reconnect, tethering and used devices;
  dock Ethernet link speed/traffic/hotplug if attached.
- [ ] Suspend/resume: repeat the used mode and rerun graphics, camera, audio,
  networking, input and dock checks. Compare idle draw/package states using the
  same SSD configuration and observation conditions as the distribution baseline.
- [ ] Check used sensors, SCU/platform/PMC USB, PMC/PMT and peripheral power/wake
  paths against the distribution kernel. Record binding differences; do not infer
  absent hardware from a missing custom driver. Decide separately whether raw
  SPI-NOR/MTD access is required; ordinary firmware loading does not require MTD.
- [ ] Run applicable [shared workload checks](../Backlog/027-shared-kernel-v0.3-followups.md#common-validation-where-used)
  for containers, networking, file services, storage and virtualization. Record
  unused items and any separately deferred acceptance.
- [ ] Record acceptance or specific blockers. Proceed to trimming after the
  custom candidate and distribution recovery path have established baselines.

## 7. Prepare and apply installed-firmware savedconfig trimming

- [ ] Inventory firmware requirements for both accepted kernel versions and all
  intended peripherals, including cold boot/resume and hardware that is currently
  disconnected. Combine runtime loads, target driver metadata/source and package
  ownership; the embedded list is not the installed selection.
- [ ] Review linux-firmware WHENCE, supported API alternatives, aliases and symlink
  targets. Retain distribution-kernel fallbacks and needed dock/peripheral files.
  Keep CPU microcode, regulatory data and any SOF payloads with their separate
  owning packages. Record exact linux-firmware and kernel versions reviewed.
- [ ] Add reviewed package-relative paths with hardware rationale to
  `etc/agentoo/firmware/startop.list`. Set
  `AGENTOO_LINUX_FIRMWARE_USE="savedconfig -deduplicate -compress-xz -compress-zstd"`
  in `etc/portage/make.conf.d/90-startop`. Reuse existing package.env wiring;
  do not add conflicting package.use policy or copy the list automatically on
  host selection. Update firmware/host documentation and coverage table.
- [ ] Record current installed payload counts/bytes and calculate the proposed
  retained selection. Check that a source ebuild for the installed package
  version is available and that no other package/configuration operation is active.
- [ ] Deploy reviewed policy and list; run `agentoo kernel firmware` then
  `agentoo kernel firmware apply --dry-run`. Review effective USE flags, native
  savedconfig version/triplet precedence, pinned source rebuild, backup plan and
  distribution-initramfs regeneration policy.
- [ ] Run `agentoo kernel firmware apply`. Record its backup directory and emerge
  result, generated versioned savedconfig, installed path comparison and actual
  payload bytes. Check the distribution initramfs was regenerated successfully.
  Interrupted apply needs inspection; it has no automatic rollback.
- [ ] Rebuild custom artifacts only if their embedded firmware inputs changed or
  an explicit custom initramfs contains affected firmware. Installed-file trimming
  alone does not require rebuilding the existing embedded selection.

## 8. Validate trimming and close onboarding

- [ ] Cold boot the distribution recovery kernel and custom candidate separately;
  repeat phase 6 hardware/firmware and suspend checks on both. Warm boots or a
  passing custom kernel can hide missing installed files through device caches,
  embedded payloads or initramfs copies.
- [ ] Record missing requests and successful fallback behavior, and revise the
  selection/reapply as needed. For broad-coverage recovery, follow the firmware
  guide: restore persistent `AGENTOO_LINUX_FIRMWARE_USE="-savedconfig"` and rebuild
  from source, or use its documented one-time override. Verify distribution
  initramfs regeneration; configuration backups do not contain the firmware tree.
- [ ] Record final config/release, embedded list, installed-list version, measured
  savings, microcode, EFI registration and acceptance scope in maintained host
  documentation. Carry remaining issues forward explicitly; update coverage
  tables only for support actually prepared and validated.
- [ ] Close this card using the board's normal completion procedure when the
  agreed acceptance scope is complete. Keep the working recovery boot path.

## Session results

- 2026-11-05: Prepared this checklist from repository policy and read-only host
  inspection. No kernel profile, EFI behavior, installed firmware policy, build,
  installation or firmware trimming has been changed by checklist preparation.
  Earlier inventory checkpoints remain historical evidence; current host results
  and the linked power investigation govern comparison.

- 2026-11-05, phase 1 read-only inventory: running
  `6.18.60-gentoo-dist-bin`; installed `gentoo-sources-6.18.60`,
  `linux-firmware-20261019`, `intel-microcode-20260925_p20260925`; GCC 16.2.1.
  Firmware report confirms broad coverage with savedconfig disabled, configured
  `-savedconfig -deduplicate -compress-xz -compress-zstd dist-kernel initramfs`,
  4,676 regular payloads, 2,603 symlinks and 2,087,238,841 payload bytes. A local
  versioned 7,279-path savedconfig exists but is inactive. Microcode is `0x122`.
  Gentoo source tree `/usr/src/linux-6.18.60-gentoo` is now present in addition
  to the distribution tree; source selection/build suitability remain to verify.
- Recovery inventory: BootCurrent is `0007` (`agentoo 6.18.60-gentoo-dist-bin`),
  first in BootOrder, with a full PCI/NVMe/GPT device path. Its distribution EFI
  image, external initramfs and matching module directory are present. Older
  Gentoo entries point at a different partition and are not established recovery
  choices. SecureBoot is disabled (EFI value 0); SetupMode is 0. Root is Btrfs
  `@` through `cryptroot`, `/boot` is FAT on nvme0n1p1, and selected suspend mode
  is s2idle. Storage identity validation, checkpoint/media readiness, boot-menu
  access and physical hardware acceptance remain pending. No boot variables,
  packages, kernel policy or firmware selection changed during this inventory.

- 2026-11-05, operator baseline: recovery materials/checkpoint and recovery
  selection readiness confirmed. Hardware is reported working on the distribution
  kernel except the known resume-power issue. Required peripherals match the
  other onboarded hosts: Dell external monitor, Bluetooth mice/headsets, Lily58
  over Bluetooth/USB, built-in and Logitech webcams, Blue USB microphone and
  shared peripheral coverage. This is operator acceptance, not a new instrumented
  test run. Defer investigation of resume power until all other onboarding works;
  retain ordinary suspend/resume functional acceptance in scope.
- Host policy prepared: added `etc/agentoo/kernel/hosts/startop.config`; existing
  profile parser accepts it and all 11 embedded inputs exist. The selected
  6.18.60 source's AX210 API maximum is 89, matching the observed payload;
  btintel derives companion DDC names from the same device identity and loads
  them on initialization. Core built-in NVMe/Btrfs/dm-crypt, keyboard, i915,
  HDA/ALC269-family, USB/Bluetooth HID, UVC, USB audio and RTL8152 driver choices
  are present in shared v0.4. No shared-baseline edits were needed for these
  checks. Full hardware/source audit, Kconfig resolution and boot acceptance
  remain pending. Dock firmware requirements remain part of the peripheral
  review before trimming; installed coverage is unchanged.

- EFI extension implemented: custom installation builds one registration command
  for manual output and automatic creation, adding `--full-dev-path` for the
  workspace's recorded Startop host. Existing partition/loader matching already
  accepts full device paths and needed no production changes. Regression tests
  exercise both loader renderings, creation/reuse, wrong partition and loader,
  selector independence, other-host behavior, BootOrder and absence of BootNext
  writes. All 36 kernel tests pass; no live image/module or EFI writes occurred.
  The standalone installer must remain runnable without a repository checkout;
  consolidating its policy with the installed distribution hook and Python CLI
  remains unresolved rather than introducing a new cross-language policy loader.

- Full repository checks: 358 Python tests ran; one unrelated SSH transport test
  failed because the sandbox prohibits binding its temporary ssh-agent Unix
  socket (`Operation not permitted`). The 36 focused kernel tests pass.
  The runner stops before Lua checks when Python discovery fails. Whitespace
  validation passes. Live firmware registration remains untested and unchanged.
