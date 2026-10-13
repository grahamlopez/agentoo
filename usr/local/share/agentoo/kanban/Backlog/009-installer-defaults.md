# Prefer binary packages and require an explicit installation target

Created: 2026-10-13
Status: Backlog

## Requested changes

- Enable installation binary packages by default. Prefer signed official binaries
  that respect the target's USE flags; compile packages without matching binaries.
- State that default clearly in `--help`, and provide an explicit source-build
  opt-out. Keep ordinary post-install package operations source-based.
- Require `--target-host NAME` instead of silently choosing `generic`. Keep
  `generic`, `qemu`, `thinktop`, and `startop` as explicit supported choices.
  An inherited environment value must not substitute for the required option.

## Implementation scope

Update installer defaults, argument validation, help, and child-phase option
propagation together. Require the target for both normal and dry-run installation
invocations; keep `--help` usable without installation arguments. Ensure resumed
phases retain the selected package policy and validate the explicit target against
the installed target record.

Update the standalone curl example, QEMU runbook, and installer policy notes to
show the required target and default binary-package behavior. Remove wording that
describes installation binaries as opt-in. Preserve signature verification,
USE-aware source fallback, and the absence of persistent binary-build defaults.

## Completion criteria

Verify default binary preference and explicit source-only selection reach package
transactions and child phases. Missing or invalid `--target-host` must fail before
target mutation; explicit supported targets and argument-free help must work.
Help and documented examples must agree with the implemented defaults.

Related: [007 installer and post-boot simplification](../Open/007-installer-postboot-simplification.md).
