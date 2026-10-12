# EFI-resident helper or playbook for manual filesystem access

Created: 2026-10-11
Status: Backlog

## Context and decision

While deferring offline checkpoint creation, the user requested a separate helper
script or playbook on EFI for mounting target subvolumes from recovery media.
An unbootable system may still contain useful files, configuration, and logs.
Manual access enables extracting these without adding offline capture to the
checkpoint command.

The resource must be reachable by mounting EFI alone; instructions stored only
inside the unavailable system root do not solve recovery bootstrap. A script,
if chosen, should use POSIX sh and recovery-environment tools. Decide whether a
short playbook is sufficient before adding automation.

## Proposed scope

- Identify the target disk and unlock its encrypted Btrfs filesystem.
- Explain top-level access and separate mounts of the known system/home subvolumes.
- Default to read-only access; consider ro,rescue=nologreplay to avoid recovery
  writes, checking support in the selected recovery environment.
- Show mounts, filesystem identities, and destinations clearly. Require explicit
  consent for any writable access or other mutation.
- Demonstrate copying selected files to a separate destination without modifying
  checkpoints, replacing subvolumes, or initiating restoration.
- Explain unmounting and closing the encrypted mapping; refuse forced/lazy cleanup
  as a default.
- List required tools and distinguish inspection/data extraction from filesystem
  repair. Avoid assuming installation-host device names remain valid.

## Completion criteria

Install the resource on EFI through the normal project workflow, then verify that
it is usable from recovery media with the installed system unmounted. Test read-only
mounting, extraction, and cleanup using disposable encrypted/Btrfs targets.
Document the resource's location and a minimal mount-and-run/read procedure.

Related: 004-offline-checkpoint-creation.md.
