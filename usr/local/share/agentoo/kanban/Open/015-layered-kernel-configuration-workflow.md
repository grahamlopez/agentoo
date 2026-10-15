# Develop the layered kernel configuration workflow

Created: 2026-10-14
Status: Open

## Objective and configuration model

Keep most kernel configuration shared across Agentoo hosts, with small selected
host fragments enabling their hardware. Develop the workflow against the real
[single-binary baseline](014-single-binary-kernel-baseline.md), initially using
manual operations to establish what the tooling needs to do.

The durable configuration lives in Git. A generated, complete `.config` remains
the editable workspace for ordinary `make menuconfig` and kernel builds. Apply
the shared base, then the explicitly selected host fragment, then let Kconfig
resolve dependencies. Host fragments may override ordinary shared defaults.
Validate firm requirements separately, including no modules and no nouveau.

Do not commit to a directory layout or command interface before exercising the
operations. Add reusable capability layers only if real host differences make
them useful. Local boot identity, credentials and generated artifacts must not
become shared configuration.

## Generation and build state

- Generate into a separate build directory using an explicitly identified source
  tree and target host. Record the source/patch identity and repository revision.
- Retain the exact input fragments and the last generated, resolved config so
  later local edits can be distinguished from repository changes.
- Show requested settings that dependency resolution changed or dropped. Check
  required behavior mappings and firm configuration requirements before building.

## Capture menuconfig changes

- Compare the edited config with the saved generated config. Present coherent,
  reviewable chunks, including dependent changes and enough context to judge them.
- The user chooses the shared base or a host fragment for each chunk during
  capture review. There is no separate promotion or approval process.
- Do not automatically put all local changes into the current host fragment.
  Common functionality such as USB audio may belong in shared configuration.
- Do not claim to infer which menu choices the user intended from the final
  config alone; distinguish observed differences from inferred intent.
- Prepare reviewable repository edits and regenerate from those candidate edits.
  Compare with the tested config. Report any remaining differences rather than
  claiming that an incomplete capture reproduces the working solution.
- Support selective capture and clear accounting for any edits left uncaptured.

## Review and relocate existing configuration

Support reviewing existing settings and moving coherent groups between shared
and host configuration. Preview how each affected host's resolved configuration
changes. Shared-to-host moves can remove support elsewhere; host-to-shared moves
can add it elsewhere. Show intentional behavior changes as well as configuration
that should remain equivalent. Preserve the requirement and rationale links.

Relocation is a normal review operation, not a separate promotion process. It
should be possible to correct placement later without reconstructing the original
debugging session.

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
- Persist meaningful decisions in the shared or host configuration. Let Kconfig
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
- [ ] Demonstrate relocation between host and shared configuration with affected
  host differences visible for review.
- [ ] Demonstrate repository updates both with a clean generated config and with
  uncaptured local edits.
- [ ] Exercise configuration migration to another source version and record new,
  obsolete and dependency-changed settings.
- [ ] Document the demonstrated workflow and automate the repetitive operations
  without concealing decisions or replacing ordinary kernel tools.

Related: [kernel reduction and evidence](../Backlog/016-kernel-reduction-and-evidence.md).
