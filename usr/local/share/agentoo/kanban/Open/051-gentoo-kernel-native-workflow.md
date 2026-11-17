# Native kernel workflow: Thinktop deployment and acceptance

Created: 2026-11-13
Status: Open — native implementation ready for deployment; physical acceptance pending

## Scope and implementation

The supported source kernel is `sys-kernel/gentoo-kernel`, with a custom minimal
embedded initramfs and `CONFIG_MODULES=n`. Dracut belongs only to the independent
binary fallback. Bequiet/NVIDIA/module-enabled acceptance is deferred; current
source validation rejects module-enabled configs. The operator has retained a
rollback branch; this repository carries no compatibility commands or parallel
build/configuration lifecycle.

The [kernel guide](../../docs/kernel.md) is the authoritative user workflow:

- Shared kernel policy lives in `/etc/kernel/config.d/10-agentoo.config`.
  Native sorted fragments provide selected host specialization and local overrides.
- `agentoo kernel prepare` verifies the mounted Btrfs/LUKS2 root and FAT GPT ESP,
  displays/replaces local native inputs, activates the selected host fragment and
  shared custom installkernel configuration, and masks the incompatible sbctl
  BLS/UKI hook. It does not build, mount, copy images or change firmware.
- A source-package native Portage phase hook generates a fresh build-owned archive
  using the installed initramfs package and sets its computed source path with
  `scripts/config`. Final Kconfig validation checks built-in boot capabilities,
  host policy/selection, archive and embedded firmware presence and no modules.
- Native source signing uses sbctl's original key/certificate paths. Native
  package environment/plugin selection excludes dracut, standalone microcode and
  sbctl boot-layout hooks from the custom path. The shared ESP guard protects both
  source and binary installations. The fallback retains its dracut path.
- EFI guidance is implemented once in `gen-efi-cmd`; the install hook calls it.
  Generated commands use `--create-only`, preserving BootOrder and BootNext.
- Agentoo-owned workspace metadata, RAM copying/retention, build/install/module
  lifecycle and their commands/tests are deleted. Native PORTAGE_TMPDIR and
  package-owned prepared trees replace them. No selector or emerge wrapper added.
- Obsolete signing/genkernel simplification cards are superseded here; outstanding
  physical keyboard/signing/update checks remain acceptance work below. Old kernel
  baseline runbooks and duplicate baseline snapshots are removed.

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

- Final repository suite: all 349 Python tests and all six Lua suites passed
  outside the agent sandbox, including native-preparation, wrong-target ESP,
  create-only EFI quoting/boot-input and shared install-guidance forwarding tests.
- Native unpack/prepare/configure against a disposable copy of the actual new
  repo config passed, including automatic generation and final validation. Only
  the intended release suffix and generated archive path differ from the accepted
  trial config. Removing stale compiler-probe metadata from the shared input
  caused no other resolved changes.
- Native package.env selection was checked for both atoms: source receives the
  custom config/plugin selection, binary fallback receives neither override.
- Fixture-only generator/checker/test-key paths replace installed paths during
  staging. Its eselect query requires consistent host ROOT/SYSROOT because repo
  paths are symlinked into the alternate tree; no production selector workaround
  or custom loader was added. Live system ROOT/SYSROOT remain native defaults.
- Shell syntax, changed-document links/code fences, removed-interface/reference
  searches and diff whitespace checks pass. Validation logs remain under
  `/tmp/agentoo-kernel-repo-check` and `/tmp/kernel-repo-accepted-suite.log`.

## Deployment and acceptance

- [ ] Deploy the current repo configuration; install agentoo-initramfs revision
  1-r1 before native kernel compilation. Run `agentoo kernel prepare` on Thinktop,
  reviewing actual root/ESP/local input changes.
- [ ] Review native emerge plan for @kernel-dev, source USE/signing inputs and
  coexistence with the installed binary fallback. Perform privileged build/install
  with the existing enrolled identity and verify the installed signature/config.
- [ ] Confirm custom installation invokes no dracut or standalone microcode
  generation, creates no external boot archive, checks the intended ESP and
  prints correct create-only guidance without changing firmware entries.
- [ ] Create a separate candidate entry; cold boot under Secure Boot. Verify
  passphrase retry/unlock, internal/USB input, Btrfs `@`, discards, microcode,
  normal startup, graphics/audio/network, peripherals and suspend/resume. Check
  Thinktop MICMUTE under the [keyboard-policy acceptance](020-initramfs-keyboard-policy.md).
- [ ] Independently verify the binary fallback's dracut generation and physical
  recovery remain accepted. Keep working installed entries until acceptance.
- [ ] Exercise a same-version rebuild and subsequent kernel version update;
  review new Kconfig choices, release paths and native prepared-tree discovery.
  Rebuild after installed initramfs/library/firmware input changes.
- [ ] Inspect binary-package signing-key handling before using/distributing locally
  produced binary packages. Package-image checks alone do not audit that format.
- [ ] Accept detached incremental configuration/build testing if desired; no
  persistent Agentoo workspace framework is required.
- [ ] Keep Bequiet/NVIDIA conversion and fleet physical acceptance explicitly
  deferred, without maintaining old lifecycle code or bring-up certificate policy.

Record live validation and decision in the finishing commit/completed index;
delete the card when Thinktop acceptance is complete. Do not mark unrelated
hosts or physical boot accepted from static or disposable tests.
