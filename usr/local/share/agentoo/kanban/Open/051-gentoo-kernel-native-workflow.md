# Native kernel workflow: Thinktop deployment and acceptance

Created: 2026-11-13
Updated: 2026-11-17
Status: Open — Thinktop custom kernel accepted; fallback/update checks and cleanup remain

## Scope and implementation

The custom gentoo-kernel build uses `sys-kernel/gentoo-kernel`, with a custom minimal
embedded initramfs and `CONFIG_MODULES=n`. Dracut belongs only to the independent
binary fallback kernel. Bequiet/NVIDIA/module-enabled acceptance is deferred; current
source validation rejects module-enabled configs. The operator has retained a
rollback branch; this repository carries no compatibility commands or parallel
build/configuration lifecycle.

The [kernel guide](../../docs/kernel.md) describes the implementation and the
manual one-off Thinktop setup before deployment:

- Shared kernel policy lives in `/etc/kernel/config.d/10-agentoo.config`.
  Native sorted fragments provide selected host specialization and local overrides.
- Target installation records local initramfs/storage inputs and activates a
  supported no-module host fragment using its already validated target data.
  `agentoo kernel prepare` and its exclusive helpers/tests/completion are removed.
  The generator owns the default keymap; kernel-local can override it explicitly.
- Shared native tmpfiles rules create the custom installkernel configuration link
  and sbctl hook mask. The installer applies them before kernel transactions;
  existing hosts apply them once after deploying the configuration.
- A source-package native Portage phase hook generates a fresh build-owned archive
  using the installed initramfs package and sets its computed source path with
  `scripts/config`. Final Kconfig validation checks built-in boot capabilities,
  host policy/selection, archive and embedded firmware presence and no modules.
- Native source signing uses sbctl's original key/certificate paths. Native
  package environment/plugin selection excludes dracut, standalone microcode and
  sbctl boot-layout hooks from the custom path. The shared ESP guard protects both
  source and binary installations. Firmware packages use `-initramfs`; the
  operator explicitly refreshes the binary fallback archive and recompiles the
  custom kernel. Shared dracut policy retains early microcode.
- The source package's native post-install hook selects its installed prepared
  tree with `eselect kernel`. Binary fallback updates preserve that selection.
- EFI guidance is implemented once in `gen-efi-cmd`; the install hook calls it.
  Generated commands use `--create-only`, preserving BootOrder and BootNext.
- Agentoo-owned workspace metadata, RAM copying/retention, build/install/module
  lifecycle and their commands/tests are deleted. Native PORTAGE_TMPDIR and
  package-owned prepared trees replace them. No selector or emerge wrapper added.
- Obsolete signing/genkernel simplification cards are superseded here; outstanding
  physical keyboard/signing/update checks remain acceptance work below. Old kernel
  baseline runbooks and duplicate baseline snapshots are removed.

The active shared localversion is `-agentoo-v0.5` (for example,
`6.18.62-agentoo-v0.5`). Binary fallback kernel labels remain unchanged.
Recorded trial releases below retain their actual tested names.

## Evidence already accepted

Thinktop selected profile, NVMe/LUKS2/Btrfs `@` root and ESP were inventoried.
The existing full read-only device-node identity validator passed outside the
agent sandbox. UUIDs remain local inputs, not tracked policy.

Native Gentoo 6.18.62 configuration merging reproduced shared + Thinktop + local
policy. The full semantic diff against composed policy contained compiler display
metadata and an additional disabled Gentoo symbol only. Against the running
kernel, GIGABYTE_WMI was enabled because it is explicitly part of the shared
union; release/archive-path differences were intentional.

Disposable native installkernel/configuration/plugin trials verified custom
installation without dracut or external archives, and fallback dracut selection
using a recording test double. Native package.env selection distinguished source
and binary atoms. Merely setting the plugin output variable
KERNEL_INSTALL_INITRD_GENERATOR did not override install.conf. Native
KERNEL_INSTALL_CONF_ROOT does not relocate plugin discovery; source plugin
selection therefore uses KERNEL_INSTALL_PLUGINS directly.

Native signing trials with `secureboot modules-sign` retained CONFIG_MODULES=n.
EFI-only key/certificate settings were sufficient; module-key settings were not
needed. Verification succeeded with the expected disposable certificate and
failed with an unrelated one. No production keys were used.

Automatic generation exposed ldd importing Portage preload libraries. The revised
`agentoo-initramfs-1-r1` generator uses pax-utils lddtree static ELF dependency
inspection instead. Removing LD_PRELOAD was ineffective because sandbox reinjected
it. The revised package built/staged successfully; generated archives exclude
libsandbox, and archived cryptsetup runs in a rootless chroot.

The operator ran the privileged disposable storage smoke test on Thinktop:
archived cryptsetup unlocked LUKS2 without udev, created its mapping, and BusyBox
mounted Btrfs `@` read-only with discards. The test reproduced SYSTEMD_READY=0
without the handoff rule, then validated the rule and successful Btrfs probing,
UUID link request and systemd readiness. Both PASS messages were supplied.

Real menuconfig editing/saving, direct .config editing with olddefconfig, delta
promotion into fragments, removal/remerge and earlier-policy promotion passed
without unrelated symbol changes. Full detached incremental compile/install
acceptance remains separate.

### Complete automatic native build

An uninterrupted unmodified Gentoo unpack/prepare/configure/compile/install run
passed outside the agent sandbox with normal rootless sandbox features, the
native automatic hook, staged revised generator and disposable EFI identity.
Archive generation happened before configuration. No merge/postinst/ESP write
or firmware mutation occurred.

| Check | Result |
| --- | --- |
| Trial release | `6.18.62-gentoo-dist-agentoo-trial` |
| Signed image | 62,257,712 bytes |
| Image SHA256 | `3cfaa84b12583711aaf0e684ec0506c7d54e5c0b5848506316cc0ca1225f0067` |
| Generated archive | 13,857,008 bytes, found verbatim in extracted staged signed image |
| Archive SHA256 | `766e35c8b160c882181083eb0e5f79aac2c9187d75d127e38ab07e9afad929bc` |
| Archive contents | Files/symlinks/modes match operator smoke-tested archive; 40 entries with correct root ownership, console node and machine inputs |
| Firmware | All 18 selected payloads found verbatim, including Intel microcode |
| Configuration | Only generated archive path differs from accepted placeholder trial; no-module and boot/host checks pass |
| Signature and links | Disposable signature verifies; native per-release links resolve within staged image |
| Package-image audit | No loadable modules, external boot archives, sandbox library or copy of private signing key |

Rootless build-info records sandbox/usersandbox/network/ipc/pid features and
unprivileged mode. Privileged emerge/userpriv and production-key access still
need live acceptance. Upstream signature checking was disabled in trials;
Manifest verification remained enabled. Native build uses about 9.2 GiB plus
link temporaries and staged image. A prior trial exceeded quota with old output
trees retained; obsolete outputs were removed and the final run passed without
recovery. Reserve peak quota/RAM headroom.

Native install QA flags retained certs/system_certificates.o. Inspection found
no section with both W and X, but no GNU-stack note; this is a retained build
object rather than EFI image or external module. No workaround was introduced.

Local disposable evidence remains under `/tmp/agentoo-kernel-051`, including
`automatic-build.log`, `automatic-candidate-audit.json`, native hook/input
fixtures, archive/loader checks and experiment results. The staged image is
under `automatic-tmp/portage/sys-kernel/gentoo-kernel-6.18.62/image`. It uses a test
identity and is not an image to deploy with trusted Secure Boot.

## Current implementation verification

- Earlier repository suite: all 349 Python tests and all six Lua suites passed
  outside the agent sandbox, including then-current setup, wrong-target ESP,
  create-only EFI quoting/boot-input and shared install-guidance forwarding tests.
- Native unpack/prepare/configure against a disposable copy of the actual new
  repo config passed, including automatic generation and final validation. Only
  the intended release suffix and generated archive path differ from the accepted
  trial config. Removing stale compiler-probe metadata from the shared input
  caused no other resolved changes.
- Native package.env selection was checked for both atoms: source receives the
  custom config/plugin selection, binary fallback kernel receives neither override.
- Fixture-only generator/checker/test-key paths replace installed paths during
  staging. Its eselect query requires consistent host ROOT/SYSROOT because repo
  paths are symlinked into the alternate tree; no production selector workaround
  or custom loader was added. Live system ROOT/SYSROOT remain native defaults.
- Shell syntax, changed-document links/code fences, removed-interface/reference
  searches and diff whitespace checks pass. Validation logs remain under
  `/tmp/agentoo-kernel-repo-check` and `/tmp/kernel-repo-accepted-suite.log`.

### Final implementation checks (2026-11-17)

- All 348 Python tests and six Lua suites pass outside the agent sandbox. The
  removed preparation/storage-discovery tests are replaced by target-installer
  input/retry/wrong-target checks. A final installer-only run passes all 22 tests.
- Fresh native unpack/prepare/configure uses the current repository fragments,
  revised hooks, default packaged keymap and disposable signing identity. It
  passes outside the agent sandbox with normal Gentoo sandbox features. The
  resolved config differs from the accepted complete build only in localversion
  (`-agentoo-v0.5`) and generated archive path; CONFIG_MODULES remains disabled.
- Effective Portage settings retain binary `initramfs` and Intel `split-ucode`,
  disable both firmware packages' `initramfs`, and restrict custom config/plugin
  selection to the source atom. Actual firmware ebuild postinst bodies skip
  boot maintenance with these flags; no firmware/package merge was performed.
- Native tmpfiles creates/reapplies both shared links, including replacing a
  stale sbctl hook in a disposable root. No tracked symlinks or permission-rule
  exceptions are needed.
- Native eselect plus Gentoo's source-link update functions pass binary-first,
  custom-first, binary-update, custom-update and localversion-change checks.
  Binary updates preserve a valid custom selection.
- Native installkernel check/copy plugins pass install and reinstall for both
  paths in `/tmp`; only dracut execution is recorded by a test double. The custom
  path calls no dracut and creates no external archive; the binary path does both.
  Shared ESP guard and guidance are covered separately by repository tests.
- A real rootless dracut build also produces a disposable fallback archive. Its
  early CPIO contains both vendor microcode files and the selected Thinktop Intel
  payload verbatim. Native configuration ordering overrides both firmware
  packages' disabled early-microcode defaults. The rootless build logs ldconfig
  warnings; privileged installed fallback and physical boot remain unaccepted.
- Logs and fixtures: `/tmp/agentoo-kernel-final-suite-host.log`,
  `/tmp/agentoo-kernel-final-installer.log`, `/tmp/agentoo-kernel-final-policy/`,
  and `/tmp/agentoo-kernel-repo-check/configure-final-policy-host.log`.
  No live configuration, packages, keys, boot images or firmware entries changed.

## Implemented decisions

### Remove prepare; use installation-time setup and shared policy

- [x] Remove `agentoo kernel prepare` outright, its dispatch/completion surface,
  exclusive implementation/helpers and obsolete tests/docs. Preserve useful
  checks in the installer and normal build/install paths. No alias, migration
  command, recurring bootstrap operation or compatibility layer.
- [x] Extend the existing target installer to establish native local initramfs
  inputs (PARTUUID, mapper and transport; generator-default keymap), selected host-fragment
  activation and target ESP UUID. Reuse the installer's already validated host,
  root and ESP data; do not add a second discovery/selection mechanism or store
  another authoritative host identity.
- [x] Treat those persisted local values as installation-time setup, revisited
  only after relevant storage/profile/ESP changes. Document direct native edits
  for those changes rather than another management command. UUIDs remain untracked.
- [x] Place the custom installkernel configuration arrangement in shared
  configuration/deployment or target installation. The current link is
  `/etc/kernel/custom/install.conf -> ../install.conf`, not `/usr/src/linux`;
  it reuses common efistub settings while the custom drop-in selects no external
  generator. Prefer native sharing without copied policy or a custom loader.
- [x] Make disabling the incompatible sbctl hook explicit shared distribution
  policy, independent of local storage setup. Resolve its native mask/deployment
  and permissions handling; do not leave a global signing-policy change hidden
  in a user preparation command.
- [x] Keep ongoing work in its appropriate native path: fresh archive generation,
  configuration merging/boot validation, compilation/signing, and checking the
  mounted ESP before copy. Moving setup does not remove these safety checks.
- [x] Document Thinktop's existing-system conversion as a manual one-off. The
  rollback branch is available. No migration machinery is implemented or retained.
  Maintained kernel/initramfs/installation/CLI guides are updated together.
  Performing that live conversion remains deployment work below.

Signing clarification: `gentoo-kernel[secureboot]` signs the staged image through
`kernel-build.eclass` / `secureboot_sign_efi_file` before installkernel copies it
to the ESP. It uses sbctl's original db key/certificate, not sbctl's install hook.
The installed `91-sbctl.install` assumes a BLS `ENTRY_DIR_ABS/linux` or UKI
`EFI/Linux` location and does not handle our direct `EFI/Gentoo` layout. The
binary fallback kernel retains its packaged signature. No replacement signing
mechanism is needed merely because that hook is disabled.

### Establish the default /usr/src/linux selection

Decision: `/usr/src/linux` selects the installed prepared tree of the custom
gentoo-kernel build, e.g. `/usr/src/linux-6.18.62-agentoo-v0.5`, through native
`eselect kernel`. The binary fallback uses its explicit versioned paths.
All policy decisions needed for implementation are settled. Implementation and
disposable two-kernel maintenance validation are complete. Live acceptance
remains pending.

- [x] Document the accepted default selection in the maintained guides.
- [x] Establish selection through native `eselect kernel` in the custom package's
  post-install hook, once its prepared tree exists, for both new installations
  and Thinktop's conversion. No per-operation selector flipping or new selector.
- [x] Verify native updates to either package leave selection in the intended
  family and advance it appropriately. Review selection when localversion changes.
  Both packages retain their own explicit versioned trees/per-release links;
  their native installation routines should not depend on changing this default.
- [x] Review linux-info/KERNEL_DIR consumers and firmware maintenance. Firmware
  hooks no longer dispatch all-kernels installation; source configuration and
  explicit binary refresh use their own versioned inputs. Live package-update
  acceptance remains below.

### Make firmware maintenance explicit for both kernels

The installed linux-firmware ebuild, with initramfs/dist-kernel integration,
requests `dist-kernel_reinstall_initramfs ... --all`. Native installkernel
forwards that to `kernel-install add-all`, revisiting both installed kernels.
The invocation runs in the **linux-firmware package environment**, so our
**gentoo-kernel-only** config/plugin selection does not apply. Shared configuration
then selects dracut for the custom gentoo-kernel build as well. This can generate
an unwanted external archive or fail during firmware maintenance; it cannot
refresh firmware or the archive embedded in the already compiled custom image.

Decision: the operator explicitly refreshes both kernels after firmware updates.
Accepted because the extra operator work is small and avoids Agentoo policy hooks
or dispatchers. Intel microcode updates use the same automatic all-kernels path
and are included in this decision. Implementation and disposable validation are
complete; live acceptance remains pending.

- [x] Disable automatic initramfs maintenance for `sys-kernel/linux-firmware`
  and `sys-firmware/intel-microcode` using native `-initramfs` USE settings.
  Retain the firmware/microcode files needed by both kernel workflows. Do not
  add a custom all-kernels filtering plugin or patch the upstream ebuilds.
- [x] Explicitly enable early microcode in the binary fallback's native dracut
  configuration: the firmware packages' `-initramfs` settings also change their
  supplied dracut defaults to disable it. Verify the configuration precedence
  and resulting archive; disabling automatic maintenance must not lose microcode.
- [x] Document the operator sequence after firmware/microcode updates: regenerate
  each retained binary fallback kernel's external archive with
  `sudo emerge --config '=sys-kernel/gentoo-kernel-bin-VERSION'`, then rebuild
  the custom gentoo-kernel build with
  `sudo emerge --ask --oneshot --usepkg=n '=sys-kernel/gentoo-kernel-VERSION'`.
  Replace VERSION with the intended installed package version. Update maintained
  callers/docs together; firmware installation alone does not refresh boot images.
- [x] Check effective package settings and exercise actual firmware and Intel
  microcode postinst bodies: no automatic boot-image installation, dracut
  invocation or standalone microcode generation.
  Verify real disposable fallback generation includes microcode, and custom
  configuration selects a fresh archive without creating an external one. Native
  install/reinstall trials and effective package environments verify source-only
  overrides do not leak onto the binary path. Full custom embedding is covered
  by the earlier accepted build; privileged refresh/rebuild remains below.
  Review other applicable
  `add-all`/`installkernel --all` callers; the generic all-kernels operation is not
  the supported refresh workflow for this mixed setup.
- [x] Keep recompilation of the custom gentoo-kernel build explicit after changes
  to embedded firmware/microcode, initramfs implementation or linked libraries.
  External initramfs regeneration is not a substitute for embedding fresh inputs.

The disposable checks supplement the earlier build/signing/archive and operator
storage-smoke evidence. Keep privileged build/userpriv, retained-object QA,
binary-package and physical acceptance limits below open.

## Deployment and acceptance

Thinktop boot evidence (2026-11-17): the operator rebooted and live inspection
confirms `6.18.62-agentoo-v0.5`, Secure Boot enabled in user mode, and the custom
prepared tree selected by `/usr/src/linux`. The host root is writable Btrfs `@`
on cryptroot with async discard. No failed system units are reported. Microcode
revision is `0x122`; graphics, wireless, Bluetooth and audio firmware initialization
appear in the boot log. The operator explicitly accepts this custom kernel based
on these checks and the requested keyboard/USB input, audio, Wi-Fi/Bluetooth,
display/dock, suspend/resume and MICMUTE checks. Thinktop's custom gentoo-kernel
build `6.18.62-agentoo-v0.5` is accepted. Binary fallback and future maintenance
acceptance remain separate; individual passphrase-retry results were not recorded.

Boot follow-up: modules-load requests `i2c-dev` from both tracked
`/etc/modules-load.d/agentoo-display.conf` and packaged
`/usr/lib/modules-load.d/ddcutil.conf`, logging a missing-module error despite
CONFIG_I2C_CHARDEV=y and CONFIG_MODULES=n. Investigation confirms this is missing
built-in module indexes: v0.4.1's retained boot explicitly reports i2c_dev built
in, while v0.5 lacks modules.builtin.bin and modules.builtin.alias.bin. Both
releases' text modules.builtin include i2c-dev. Native modules_install skips
depmod with CONFIG_MODULES=n; systemd's 50-depmod.install also skips a tree without
a kernel/ directory, so adding that plugin alone would not fix this case.

A disposable copy of v0.5's text metadata reproduces failed modinfo lookup.
Running native depmod there generates the missing indexes; modinfo then reports
filename (builtin) and modprobe --show-depends reports builtin i2c_dev. Evidence
is in /tmp/agentoo-builtin-index-nw5c8npu/results.json. Depmod emits a nonfatal
missing-modules.order warning because the no-module install omits that file.
Providing an empty modules.order in the disposable no-module tree removes the
warning. Inspection of the removed workflow confirms it supplied this empty
order file and ran depmod explicitly; this behavior was missed in the conversion.
Implemented correction: the existing package-specific bashrc's post_src_install
hook touches modules.order and runs native depmod against ED for KV_FULL. This
supplies the empty order file for the no-module build and generates package-owned
indexes before merge. All nine kernel tests pass, including real kmod lookup
before/after the hook, repeated execution, and no loadable module files. A
disposable copy of the actual installed v0.5 metadata also passes the new hook
without warnings and reports i2c-dev as built in.
No service-condition workaround is needed. Removing Agentoo's duplicate ddcutil
module-load request is independent cleanup. The operator first repaired the live
indexes with depmod and normalized metadata permissions to 0644; modinfo then
recognized i2c-dev as built in. The operator subsequently deployed the hook,
rebuilt the same version and rebooted. Inspection of the 2026-11-17 11:24 boot
confirms 6.18.62-agentoo-v0.5 with Secure Boot enabled, the deployed hook matching
the checkout, and rebuilt order/index files with mode 0644. The boot journal
reports "Module 'i2c_dev' is built in" and successful completion of module loading;
the missing-module error is resolved. Ordinary-user modinfo also succeeds.
Other logged driver/service diagnostics have not yet been
attributed to this conversion; do not treat them as newly introduced without
comparison evidence.

Live configure follow-up: Thinktop's privileged emerge reached final validation
but failed because native `ESYSROOT` was empty for the live root. The hook passed
that empty string to Python, which resolved host paths relative to the source
directory. Fixed the hook to pass `${ESYSROOT:-/}`. A regression test covers empty,
explicit `/` and alternate roots; all eight kernel tests pass. The corrected hook
also validates the disposable configured build against the live host policy.
The earlier alternate-root fixture did not cover this live-root convention.
The operator deployed the fix, completed privileged emerge and rebooted into the
accepted custom kernel. The failed configure attempt is superseded by that
successful build/install and operator boot acceptance.

- [x] Deploy the completed configuration and apply
  `sudo systemd-tmpfiles --create agentoo-kernel.conf`. Establish Thinktop's
  untracked kernel-local inputs, host activation and ESP UUID manually as in
  the kernel guide. Install agentoo-initramfs revision 1-r1 before compilation.
- [x] Complete the privileged custom source build/install with the existing
  enrolled identity and installed configuration; the candidate boots under
  Secure Boot alongside the retained binary fallback.
- [ ] Confirm custom installation invokes no dracut or standalone microcode
  generation, creates no external boot archive, checks the intended ESP and
  prints correct create-only guidance without changing firmware entries.
- [x] Accept the separate Thinktop candidate under Secure Boot. Live boot checks
  and operator acceptance cover the custom kernel and requested hardware checks
  above, including MICMUTE. Individual passphrase-retry results are not recorded;
  this acceptance does not establish binary fallback or other-host acceptance.
- [ ] Independently verify the binary fallback kernel's privileged dracut
  generation, early microcode and physical recovery. After applying the firmware
  USE changes, verify real package updates perform no boot-image maintenance;
  explicitly refresh both kernels. Keep working entries until acceptance.
- [x] Exercise a same-version rebuild and reboot with the deployed indexing hook;
  confirm readable package-installed indexes and successful built-in recognition.
- [ ] Track subsequent kernel version update acceptance separately: review new
  Kconfig choices, release paths and native prepared-tree discovery. Rebuild
  after installed initramfs/library/firmware input changes.
- [ ] Inspect binary-package signing-key handling before using/distributing locally
  produced binary packages. Package-image checks alone do not audit that format.
- [ ] Accept detached incremental configuration/build testing if desired; no
  persistent Agentoo workspace framework is required.
- [ ] Keep Bequiet/NVIDIA conversion and fleet physical acceptance explicitly
  deferred, without maintaining old lifecycle code or bring-up certificate policy.

Record live validation and decision in the finishing commit/completed index;
delete the card when Thinktop acceptance is complete. Do not mark unrelated
hosts or physical boot accepted from static or disposable tests.
