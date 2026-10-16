# Develop the shared kernel configuration workflow

Created: 2026-10-14
Status: Open

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
