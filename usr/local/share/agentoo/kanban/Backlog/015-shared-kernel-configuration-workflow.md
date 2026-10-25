# Develop the shared kernel configuration workflow

Created: 2026-10-14
Status: Backlog

## Objective and configuration model

Maintain one shared kernel configuration supporting all Agentoo hosts, including
the union of their required hardware drivers and capabilities. Do not introduce
host-specific driver fragments or a shared/host relocation workflow. This
decision, agreed on 2026-10-15, replaces the earlier layered proposal.
Develop the workflow against the real
[single-binary baseline](../Completed/014-single-binary-kernel-baseline.md), initially using
manual operations to establish what the tooling needs to do.

The durable configuration lives in Git. A generated, complete `.config` remains
the editable workspace for ordinary `make menuconfig` and kernel builds. Generate
from the shared configuration and let Kconfig resolve dependencies. Validate firm
requirements separately, including no modules and no nouveau.

The shared configuration defines driver and capability selections. Host-specific
boot parameters, firmware and microcode are separate embedded build inputs,
producing a self-contained binary per host. The final `.config` may therefore
differ in embedding fields such as `CONFIG_CMDLINE`, `CONFIG_EXTRA_FIRMWARE`
and build paths without becoming a host-specific driver configuration.

Do not commit to a directory layout or command interface before exercising the
operations. Keep credentials and generated artifacts out of Git. Record host
embedding inputs separately from shared configuration; settle their storage
format while exercising the build procedure.

## Proposed first increment: rebuild an existing configured kernel

Recorded: 2026-10-25. Deferred proposal, not an approved implementation contract.
The operator wants to start with carrying an already-configured custom kernel
forward when Portage supplies a newer source version. Keep the broader workflow
below as later work; it is not a prerequisite for this increment. Recording this
outline does not authorize implementation, builds, installation or firmware changes.

The operator's original sketch uses `configure`, `build` and `install`, a build
label, `/usr/src/linux` as the default source, an optional genkernel/custom
initramfs choice, and `/boot/EFI/Gentoo` as the default installation destination.
It requests config backups and differences, release naming without `-gentoo`,
and optional EFI registration that puts the candidate first while preserving
other entries and their relative order. The manual starting procedure is in
[distribution-config build notes](../../docs/kernel-baseline-build.md).

The interface and steps below are suggestions from the subsequent review, not
settled choices. In particular, explicit config/build selection, migration
interaction, source-preserving release overrides and module rejection need to
be confirmed through the actual procedure.

### Provisional interface

```text
agentoo kernel configure <build_label>
    --config FILE
    --source-location DIR       default: /usr/src/linux
    --build-dir DIR             default: ~/local/agentoo-build/kernel/<version>-<label>
    --accept-defaults
    --no-input

agentoo kernel build
    --build-dir DIR
    -j, --jobs N                default: available CPU count
    --[no-]genkernel             default: enabled
    --initramfs FILE             requires --no-genkernel
    --no-input

agentoo kernel install
    --build-dir DIR
    --dest DIR                  default: /boot/EFI/Gentoo
    --[no-]efi-add-entry         default: disabled
    --no-input
```

`--[no-]` denotes paired positive/negative options. The proposal requires
`--config` for configure and `--build-dir` for build/install rather than selecting
an implicit latest build. Record the resolved source path, label, configuration
inputs, effective build flags and completed artifact identity in the workspace;
the metadata format is undecided.

### Configure: carry the existing configuration forward

1. Validate label, input config, source and destination before effects. Resolve
   the source symlink to its concrete versioned tree.
2. Create a separate build directory, preserve the input config and back up an
   existing destination `.config` before replacement. Start from the supplied
   complete config rather than generating `defconfig` first.
3. Initially require `CONFIG_MODULES=n` with no `=m` selections; reject rather
   than silently convert a module-enabled input. This is a proposed limitation,
   not a universal host requirement: [bequiet](026-bequiet-kernel-v0.3-followups.md)
   has an operator-managed module exception for NVIDIA.
4. Preserve embedded command line, firmware choices and other existing settings.
   Display `/proc/cmdline` alongside the embedded command line for reference;
   do not automatically replace target boot inputs with the running host's inputs.
5. Set `CONFIG_LOCALVERSION="-<build_label>"`. Investigate passing `EXTRAVERSION=`
   consistently to make instead of editing Portage's source Makefile. Verify the
   complete resulting release through `make kernelrelease`, including any other
   local-version contributions.
6. List new symbols and use `oldconfig` for explicit choices. Proposed
   `--accept-defaults` selects `olddefconfig`; `--no-input` fails if choices
   remain without that explicit acceptance. Report removed/changed settings too.
7. Show differences against the supplied config and any previous destination
   config, recheck firm requirements, and save the resolved configuration.

### Build: produce the self-contained EFI kernel

1. Validate recorded source/config identity, tools and embedding inputs. Detect
   missing or changed sources before reuse. Define the identity checks during
   implementation rather than assuming a versioned path alone is sufficient.
2. Record effective flags, including explicitly supplied `KCFLAGS`; do not replay
   historical `-march=native` automatically. Use portable flags for shared targets.
3. In genkernel mode, clear the old embedded initramfs path for the preliminary
   build, build that kernel, then generate a fresh uncompressed initramfs in the
   workspace. Retain the prior config and inputs for failure recovery.
4. Follow the module-free manual genkernel policy: LUKS support, no ramdisk
   modules, no firmware installation, no boot mounting and no bootloader changes.
5. In custom mode, require `--no-genkernel --initramfs FILE` and copy the supplied
   archive into the workspace. Validate its suitability for the target; selecting
   a file does not establish successful root unlock or boot.
6. Set `CONFIG_INITRAMFS_SOURCE` to the workspace archive, resolve the config,
   review unexpected changes and build the final kernel. No `modules_install`
   step is needed for this initial module-free scope.
7. Verify release metadata, EFI-stub support, embedded-initramfs configuration
   and module-free state. Record final config/image hashes and return the image
   path. Static checks do not establish successful boot or functional acceptance.

### Install: copy the artifact and optionally register it

1. Validate the completed build and recorded image identity before escalation.
2. Inspect the destination mount and EFI System Partition. The proposal permits
   mounting `/boot` through its existing mount configuration when necessary;
   confirm mount handling and destination validation during implementation.
3. Install `kernel-<release>.efi`, preserving any existing different image and
   keeping the known-working distribution/custom fallback available.
4. Derive disk, partition and firmware loader path from the actual ESP.
5. With registration disabled, print the exact `efibootmgr` registration command.
6. With `--efi-add-entry`, create or reuse the matching entry, put it first while
   preserving every other entry's relative order, and print `efibootmgr -u`.
   Define duplicate matching and partial-failure reporting before implementation.

### Deferred work and open decisions

- Shared-config generation and menuconfig capture remain in this card's broader
  scope. Dist-config conversion and kernel reduction are outside this increment.
- The original sketch's `--[no-]allow-modules` conflicts with its requirement to
  remove all module-valued symbols regardless of that option. Resolve that
  meaning before adding module support; do not imply bequiet is supported by the
  proposed module-free implementation.
- Defer the sketched `--dual-boot-sign`. Signing with a trusted private key and
  retaining Microsoft trust for dual boot are separate operations. Settle explicit
  signing inputs/tool integration before offering a signing interface.
- Confirm config replacement/backup behavior, migration review, workspace layout,
  genkernel privilege requirements, artifact replacement and ESP handling through
  manual use. Do not introduce automatic source adoption or rebooting.
- Follow the established [CLI policy](../../lib/cli.py): standalone
  `agentoo-kernel`, one parser for execution/help/completion, safe help, no implicit
  option abbreviations, validation before effects/escalation, results on stdout,
  operational output on stderr and noninteractive authorization for `--no-input`.
  Add help/completion and focused verification with any eventual implementation.

### Related work

- [Shared v0.3 follow-ups](027-shared-kernel-v0.3-followups.md) and its linked host
  cards own runtime validation and host findings; this card owns workflow tooling.
- [Initramfs keyboard policy](020-initramfs-keyboard-policy.md) remains separate:
  regenerating the existing genkernel image does not itself fix keyboard policy.
- [Distribution-kernel EFI registration](008-automatic-efi-registration.md)
  explicitly excludes this custom-kernel installation path. Share findings where
  useful without expanding that card's scope.

## Generation and build state

- Generate into a separate build directory using an explicitly identified source
  tree and an explicitly selected target host for embedded boot parameters,
  firmware and microcode. Record the source/patch identity, repository revision
  and host inputs. Do not specialize the driver selection or compiler CPU target
  for the build machine.
- Retain the exact configuration inputs and the last generated, resolved config so
  later local edits can be distinguished from repository changes.
- Show requested settings that dependency resolution changed or dropped. Check
  required behavior mappings and firm configuration requirements before building.

## Capture menuconfig changes

- Compare the edited config with the saved generated config. Present coherent,
  reviewable chunks, including dependent changes and enough context to judge them.
- The user chooses which chunks to persist in the shared configuration. There
  is no destination selection, relocation or separate promotion process.
- Account for generated embedding fields separately: do not capture a host's
  boot identity, firmware list or build paths into universal defaults. Surface
  edits to these fields for review and update the appropriate embedding inputs
  explicitly rather than silently discarding them.
- Review changes for effects on all supported hosts. A driver unused on the
  machine doing the capture may still be required by another host.
- Do not claim to infer which menu choices the user intended from the final
  config alone; distinguish observed differences from inferred intent.
- Prepare reviewable repository edits and regenerate from those candidate edits.
  Compare with the tested config. Report any remaining differences rather than
  claiming that an incomplete capture reproduces the working solution.
- Support selective capture and clear accounting for any edits left uncaptured.

## Repository updates

A pull updates durable inputs; it must not silently overwrite an edited working
config, rebuild a kernel or replace a boot artifact. Generate an updated candidate
in a fresh directory and show the difference from the previous working build.

Initially, stop when uncaptured local edits exist and require them to be captured
or explicitly discarded. Do not attempt automatic three-way reconciliation in
the first implementation. Preserve existing builds while reviewing candidates.

## Kernel source updates

Installing new sources through Portage and adopting a new custom kernel are
separate operations. Migrate configuration deliberately against an identified
source version; do not silently treat new defaults as reviewed decisions.

- Identify newly encountered options before assigning defaults. Use available
  kernel tools such as `listnewconfig`, `helpnewconfig`, `oldconfig` and
  `scripts/diffconfig` to support review.
- Investigate disappeared/renamed symbols and existing values changed by new
  dependencies. Do not mistake an ignored old setting for preserved behavior.
- Persist meaningful decisions in the shared configuration. Let Kconfig
  manage hidden dependency symbols where appropriate.
- Record the configuration's intended kernel version and test the migrated
  candidate before adoption. Decide how to represent overlapping supported
  versions if an actual rollout requires them.

## Requirements and accumulated knowledge

Persist required behavior, scope, implementation references and test evidence
alongside configuration. Record a requirement even before its symbol mapping is
known. Capture hardware findings, userspace failures, enabling settings, firmware
and userspace prerequisites as they are discovered. Keep configuration values
authoritative in the configuration inputs; explanations link to them.

Record failures and later regressions as well as successful tests. Preserve the
host, kernel version, artifact identity and exercised scenarios behind a claim.
Avoid treating absent devices or unused capabilities as proof of dispensability.

## Completion criteria

- [ ] Demonstrate generation, menuconfig editing, chunk review and capture using
  an actual baseline change, with equivalent regenerated output.
- [ ] Demonstrate that capturing a hardware addition preserves the driver and
  capability requirements of other supported hosts.
- [ ] Demonstrate host-specific embedding from the same shared driver config,
  with embedding fields accounted for separately during capture and regeneration.
- [ ] Demonstrate repository updates both with a clean generated config and with
  uncaptured local edits.
- [ ] Exercise configuration migration to another source version and record new,
  obsolete and dependency-changed settings.
- [ ] Document the demonstrated workflow and automate the repetitive operations
  without concealing decisions or replacing ordinary kernel tools.

Historical context (retired; operator-managed): [kernel reduction and evidence](../Completed/016-kernel-reduction-and-evidence.md).
