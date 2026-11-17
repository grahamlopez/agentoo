# Convert Thinktop's no-module kernel to Gentoo's native package workflow

Created: 2026-11-13
Updated: 2026-11-16
Status: Open — evaluation and conversion design; native candidate not yet accepted

## Decision and scope

Evaluate replacing Thinktop's `gentoo-sources` / `agentoo kernel` build/install
lifecycle with `sys-kernel/gentoo-kernel` and native Portage facilities. Optimize
for explicit, authoritative, deduplicated and minimal configuration, and deletion
of Agentoo-owned lifecycle code.

The initial target is **Thinktop with CONFIG_MODULES=n**. Preserve the shared
built-in driver/capability union and Thinktop specialization. Bequiet, NVIDIA,
external modules and module-signing acceptance are deferred; they must not grow
this trial's implementation or block its acceptance. Preserve their working
workflow until a separate conversion is evaluated.

A custom minimal initramfs embedded in the EFI-stub kernel is a **hard
requirement**. Preserve its early-boot behavior. Packaging and generation are
flexible: start with the existing `sys-kernel/agentoo-initramfs` package and
generator, but simplify that arrangement if it reduces integration complexity.
An external initramfs or dracut-generated replacement does not satisfy this card.

Dracut belongs exclusively to the independently maintained packaged binary
fallback. The custom candidate must neither invoke dracut nor depend on its
output. Scope installkernel configuration through native mechanisms so each
kernel gets the intended behavior during ordinary maintenance: no external
initramfs generation for the custom kernel, dracut for the binary fallback.
Changing the current global configuration is in scope; preserve fallback
generation and boot behavior rather than its current configuration layout.
Keep direct EFI boot, image signing and explicit manual firmware registration; no bootloader or UKI
conversion is proposed.

Work currently covers evaluation and conversion design. Candidate installation,
firmware changes and retirement of working artifacts require a concrete reviewed
plan. Read-only inspection and disposable trials must not replace working boot
artifacts or change firmware entries.

## Source evidence and unresolved integration

Initial source review: installed Gentoo repository on 2026-11-13, including
`gentoo-kernel-6.18.62.ebuild`, `kernel-build.eclass`, `kernel-install.eclass`,
`linux-info.eclass`, `linux-mod-r1.eclass` and `dist-kernel-utils.eclass`.
Follow-up repository and installed-helper inspection: 2026-11-16.

- `kernel-build` provides separate source/output compilation and installs a
  prepared tree under `/usr/src/linux-${KV_FULL}`, with resolved config, kernel
  image and native per-release links. This can replace private retained outputs.
- Native merging applies distribution inputs, module policy, optional
  savedconfig, signing-key settings and sorted `/etc/kernel/config.d/*.config`.
  These final fragments can carry shared policy, one activated host fragment and
  local overrides. Host selection is not automatic; reuse the existing Portage
  profile selection rather than introduce a selector or config loader.
- Gentoo begins with a broad distribution config. Explicit negative choices in
  our baseline matter; a small additive fragment does not preserve a minimal
  kernel. Inspect the complete resolved result and new-option behavior.
- Versioned savedconfigs override unversioned savedconfigs. Prefer managed
  fragments alone and disable unnecessary savedconfig inputs; do not define the
  same policy in both. Archive resolved configs as evidence, not active policy.
- The initramfs ebuild builds private static BusyBox and installs the generator
  and scripts. It does **not** generate the host archive. Today `agentoo kernel`
  invokes that installed generator with explicit PARTUUID, mapper and keymap.
  Reuse this implementation initially; the ebuild/package boundary and generation
  integration may change if a simpler approach preserves the embedded archive.
- `CONFIG_INITRAMFS_SOURCE` can point to our archive. A durable readable location,
  generation before compilation and access under Portage isolation remain to be
  proved. Kernel installation hooks run too late to prepare an embedded archive.
- `/etc/kernel/install.conf` currently selects `initrd_generator=dracut` globally.
  `kernel-install_install_all` invokes installkernel even with `USE=-initramfs`;
  that flag alone does not prove dracut is disabled for the custom kernel. Revise
  the native installkernel configuration and its scope so custom installation
  selects no external initramfs generator while the binary fallback selects
  dracut. Check native package-scoped configuration/invocation mechanisms before
  adding hooks; do not introduce a dracut-based custom path.
- Existing ESP checks and EFI guidance match distribution release suffixes; the
  guidance also requires an external initramfs. Review candidate release naming
  and these consumers so ESP protection remains effective and custom registration
  does not acquire fallback `initrd=` arguments.
- Native `USE=secureboot` requires `modules-sign` in kernel-build. Image signing
  and module support are separate requirements: determine the simplest native
  signing path for `CONFIG_MODULES=n` without adding module policy or exposing
  private keys in installed trees/binary packages. Reuse the sbctl identity.
- Native Portage temporary-directory configuration can provide RAM compilation.
  Durable package results are required; private RAM-copy/retention machinery is
  not. Prepared-tree discovery and firmware maintenance need a no-module trial.

This is source evidence, not an accepted native build, installation or boot.
[Current kernel procedure](../../docs/kernel.md),
[initramfs package and lifecycle](../../docs/initramfs.md), and
[Thinktop fragment](../../../../../../etc/agentoo/kernel/hosts/thinktop.config)
remain the reference inputs.

## Intended configuration scheme

Use native sorted `/etc/kernel/config.d/*.config` inputs. Proposed filenames:

| Path | Ownership and purpose |
| --- | --- |
| `/etc/kernel/config.d/10-agentoo.config` | Tracked authoritative shared baseline, including explicit disabled options |
| `/etc/agentoo/kernel/hosts/thinktop.config` | Tracked authoritative Thinktop specialization |
| `/etc/kernel/config.d/20-host.config` | Local activation of the selected host fragment, preferably a symlink |
| `/etc/kernel/config.d/80-local-boot.config` | Untracked local boot inputs, including the durable archive path |
| `/etc/kernel/config.d/90-local.config` | Untracked user overrides and temporary experimental settings |

Validate this layout during the trial. Activate exactly one host through existing
host preparation/profile selection; do not copy host policy or add a loader.
Move the shared baseline out of the documentation snapshot into its active
configuration location. Update deferred-host callers if needed to share that
same authority rather than retaining a second maintained baseline. Full resolved
configs are build evidence, not additional active policy. No savedconfig layer
is intended. Preserve native Kconfig resolution and inspect dependency effects.

Keep storage identity local and pass it explicitly to archive generation. Do not
invent a Kconfig symbol or duplicate UUIDs merely to fit the fragment scheme.
Confirm that the binary package ignores these source-kernel fragments and that
its fallback configuration remains independent.

## Intended user workflow

These commands describe the target interface, not an accepted runbook. `VERSION`
and `RELEASE` are placeholders; validate exact versions, filenames and mechanisms
before publishing executable host instructions.

### Distribution binary fallback

Install/update through Portage:

```sh
sudo emerge --ask sys-kernel/gentoo-kernel-bin
```

Native installation generates the external initramfs with dracut and installs the
EFI image. Regenerate that initramfs and reinstall an existing package version:

```sh
sudo emerge --config '=sys-kernel/gentoo-kernel-bin-VERSION'
```

### Custom Thinktop kernel

Configure through the shared/host/local fragments, then install/update:

```sh
sudo emerge --ask sys-kernel/gentoo-kernel
```

The intended operation prepares the custom archive before compilation, merges
configuration, builds with `CONFIG_MODULES=n`, embeds the archive, signs the EFI
image and installs durable package results. It invokes no dracut and produces no
external initramfs. Integrating archive preparation with ordinary maintenance is
still unresolved; define an exact explicit preparation command if native
integration cannot provide it simply. Do not advertise emerge alone as sufficient
until archive freshness and ordering are proved.

After changing configuration or embedded archive contents, force a source rebuild
of the selected version:

```sh
sudo emerge --ask --oneshot --usepkg=n '=sys-kernel/gentoo-kernel-VERSION'
```

`emerge --config` cannot refresh an embedded archive; recompilation is required.
Document regeneration/rebuild after generator, BusyBox, cryptsetup/library and
embedded firmware changes. Ordinary package updates must use the intended scoped
configuration without manual environment workarounds.

### EFI registration and boot acceptance

Retain useful registration guidance for both installed images:

```sh
agentoo kernel gen-efi-cmd --image /boot/EFI/Gentoo/kernel-RELEASE.efi
```

Review and execute the printed command separately. The binary fallback receives
its local command line and external `initrd=` argument; the custom kernel uses
its embedded boot policy and no external initramfs argument. Validate filename
recognition, signing and Thinktop-specific requirements before using this path.
Keep registration explicit and retain working entries for candidate boot tests.

### Fragment-based experimentation

Edit `/etc/kernel/config.d/90-local.config` with explicit Kconfig settings and
rebuild the selected source package using the command above. Inspect the final
resolved config to verify dependencies did not change the intended settings.
Remove experimental entries to return to shared/host policy. Promote accepted
changes into the shared baseline or host fragment and remove redundant local
entries. Check that experiments preserve required built-in boot capabilities.

### Menu-based and direct .config experimentation

Use a disposable full source/output tree seeded from the resolved package config.
The installed prepared tree is not assumed to be a full development source tree.
With matching sources and a configured experiment output directory:

```sh
make -C "$sources" O="$experiment" menuconfig
# Alternatively edit "$experiment/.config", then resolve dependencies:
make -C "$sources" O="$experiment" olddefconfig
```

Snapshot the initial resolved config, compare the experiment's result and promote
intentional settings into the appropriate fragment before a packaged build.
Editing `/usr/src/linux-RELEASE/.config` does not configure the next emerge.
Avoid editing Portage's temporary configs as the everyday interface: native
configuration creates separate preparation and compilation trees.

Validate and document the exact source acquisition, seeding, commands and diff
procedure. Evaluate a direct incremental compile/test loop with native make and
Portage phase tools where useful, including release isolation and safe candidate
installation. Do not claim a replacement for the existing fast menuconfig/build
loop until tested, or add a new persistent workspace framework merely to retain
it. Record any development convenience lost in the conversion decision.

## Intended implementation ownership

| Responsibility | Intended owner |
| --- | --- |
| Config merging, Kconfig resolution and kernel compilation | Gentoo kernel package/eclasses |
| RAM build location | Native Portage temporary-directory configuration |
| Installed image/config/prepared tree and package upgrades/removal | Portage |
| EFI signing and copying | Native kernel/installkernel facilities, subject to trial |
| Shared/host kernel policy and local-input preparation | Agentoo configuration and necessary validation |
| Custom initramfs implementation and generation | Agentoo; packaging/integration may be simplified |
| Manual EFI registration guidance | Existing Agentoo helper where useful |

Retire Thinktop's dependency on custom workspace discovery, JSON metadata,
source hashes, RAM copying/retention, module manifests/staging and bespoke image
installation as native facilities replace them. Do not introduce an emerge
forwarding wrapper. Change `@kernel-dev` and host package selection to use the
source-built kernel where appropriate, preserving prerequisites and deferred-host
needs. Shared implementation required by Bequiet remains until its own conversion;
record those remaining consumers rather than globally deleting working support.

## Operational evaluation

Complete each gate with exact inputs, commands, results and unresolved differences
in the evidence section below. Stop at an unresolved boot-critical difference.

### 1. Inventory and conversion plan

- [ ] Confirm Thinktop's selected profile, running release/config, source version,
  root transport/storage identity, embedded firmware and boot requirements.
  Record working custom/fallback image paths and entries without changing them.
- [ ] Define one active layering: shared baseline → selected Thinktop fragment →
  machine-local boot inputs and user overrides, with explicit native ordering.
  Choose fragment activation through existing host preparation. Keep UUIDs and
  archive paths local. Remove competing savedconfig/policy inputs from the plan.
- [ ] Specify candidate release, package slot, installed tree and EFI filename.
  Check coexistence with working kernels, update/removal behavior and same-version
  rebuild behavior. Do not promise current custom backup semantics from Portage.
- [ ] Define scoped native installkernel configuration for both kernel packages
  and the EFI-signing route. Test both hook selections with disposable inputs
  before any live package installation: custom runs no external generator;
  binary fallback retains dracut. Record versions and verify ordinary Portage
  installation/reinstallation uses the intended configuration without ad hoc
  operator environment overrides.

### 2. Resolve configuration without installation

- [ ] Use isolated Portage staging through configuration phases; no merge, ESP
  writes or firmware registration. Record USE flags and the exact fragment order.
- [ ] Compare the full resolved config against the shared baseline plus Thinktop
  policy. Explain intended deltas, distribution signing/compression defaults and
  new Kconfig options; verify `CONFIG_MODULES=n` survives final resolution.
- [ ] Validate the proposed configuration paths, single-host activation and local
  ignore rules. Demonstrate fragment overrides, removal of an experimental override
  and promotion without duplicated policy. Confirm the binary fallback is unaffected.
- [ ] Exercise menuconfig and direct .config edits in a disposable matching source
  tree; record exact setup/diff commands and rebuild through native fragments.
  Assess the incremental development loop before retiring existing commands.
- [ ] Verify built-in root transport, LUKS/AES-XTS/Btrfs, input/console, EFI stub,
  embedded firmware/microcode, command line and initramfs requirements using the
  existing checks where applicable. Avoid a second definition of boot policy.

### 3. Build an isolated embedded candidate

- [ ] Start with the existing packaged generator; run its preflight and disposable
  storage smoke test. Generate the archive from explicit verified local storage
  inputs. Record its location and how an ordinary future build regenerates it
  first. Simplify packaging/generation if needed; embedding remains mandatory.
- [ ] Build through gentoo-kernel with that archive under native Portage isolation.
  Prove the archive is embedded and readable, `CONFIG_MODULES=n`, firmware inputs
  are present and release/image/config agree. Inspect staged artifacts for secrets.
- [ ] Verify RAM compilation through native temporary storage and durable staged
  results. Distinguish any lost incremental-build convenience from requirements;
  do not recreate workspace persistence merely to match the old interface.

### 4. Review and accept installation and maintenance

- [ ] Present the concrete install/EFI plan before changing live boot artifacts.
  Preserve the working custom kernel and binary fallback; leave BootOrder and
  BootNext unchanged. Verify the target ESP and image signature before boot testing.
- [ ] Confirm the custom installation invokes no dracut, creates/references no
  external initramfs and produces correct manual direct-EFI registration guidance.
  Independently verify the binary fallback retains dracut generation and recovery.
- [ ] Cold boot Thinktop: incorrect/correct passphrase, internal/USB input, encrypted
  Btrfs root, active discard policy, microcode, console, normal startup, peripherals
  and required suspend/resume behavior. Check MICMUTE against existing acceptance
  work. Verify signed boot with Secure Boot enabled where configured.
- [ ] Exercise a subsequent kernel update and same-version rebuild; verify native
  prepared-tree/config discovery and linux-firmware maintenance. Regenerate and
  rebuild after an initramfs implementation or cryptsetup/library change; record
  the maintenance procedure and any manual steps explicitly.

### 5. Convert and remove superseded work

- [ ] Decide whether the result is simpler. If substantial integration glue is
  needed, document why and reconsider packaging/generation integration first.
  Retain the custom embedded initramfs; if native packaging cannot support it
  simply, reconsider the gentoo-kernel conversion rather than that requirement.
- [ ] Keep Agentoo responsibilities limited to host/local-input preparation,
  initramfs generation, necessary validation and useful EFI guidance. Use a
  wrapper only for a concrete operation; do not wrap emerge just to rename it.
- [ ] Update Thinktop's package/configuration inputs, callers, checks and guides
  together. Delete superseded Thinktop lifecycle mechanisms where possible.
  Record shared code still required by deferred hosts; no compatibility aliases
  or new parallel maintenance framework. Global removal waits for those hosts.
- [ ] Reconcile relevant acceptance with
  [kernel simplifications](049-post-genkernel-kernel-simplifications.md) and
  [image signing](050-kernel-image-signing.md); do not close unrelated host work.

## Evidence and decision

- 2026-11-16: narrowed to Thinktop, no modules; custom embedded initramfs required,
  with flexible packaging/generation. Scope native installkernel configuration
  for custom and binary paths; dracut confined to binary fallback.
  Bequiet/NVIDIA/module signing deferred.
- Intended interface: native emerge commands, one shared/host/local fragment
  scheme, fragment-based experiments and disposable menuconfig/.config exploration;
  archive-preparation integration and development-loop details still need trials.
- Native config trial: pending.
- Initramfs preparation and scoped installkernel configuration: pending.
- Candidate build/signing/install: pending.
- Physical boot and ordinary maintenance: pending.
- Conversion decision and remaining host follow-up: pending.

Close with the decision and validation in the finishing commit and completed
index; delete this card per board policy. Completion applies to this Thinktop
conversion, not untested deferred hosts.
