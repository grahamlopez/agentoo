# Self-contained recovery without a separately booted host

Created: 2026-10-12
Status: Backlog

## Context and decision

Agentoo checkpoint restoration currently requires a separate recovery environment
with the target system unmounted. The recovery command lives on EFI, but its
interpreter and utilities still come from that environment. Provide a recovery
environment that boots on the installed machine without another host or external
boot media, including when the installed root cannot boot.

The design is intentionally undecided. Investigate the options, present the
tradeoffs, and agree on an approach before implementing installer or disk-layout
changes. This card authorizes tracking the work, not implementing it now.

## Investigation

- Examine how Omarchy implements recovery and rollback, using its current source
  and documentation. Determine which parts remain usable when the installed root
  is unavailable, and whether they apply to Agentoo's encrypted Btrfs layout.
- Explore a separate minimal bootable recovery partition: required size,
  filesystem, boot entry, installed utilities, and maintenance strategy.
- Compare an EFI-resident recovery kernel/initramfs or independent recovery image
  with the partition approach. Check available EFI space and independence from
  the installed root, its libraries, and its package manager.
- Decide whether recovery must work offline, how it obtains updates, and how a
  working recovery image survives an interrupted update or checkpoint restore.
- Define the supported failure cases and boundaries: broken root configuration,
  kernel or initramfs failure, missing boot entries, damaged EFI, and disk failure.
  Same-disk recovery cannot protect against loss of that disk.

## Proposed implementation scope

- Add the selected environment to fresh installations and expose a clear firmware
  or boot-menu entry. Document how to select it when normal boot fails.
- Include the tools needed to identify disks, unlock LUKS, inspect Btrfs, and run
  the EFI checkpoint command without executing files from the installed root.
- Preserve the existing restore safeguards: refuse an active target root or
  mounted selected subvolumes, show target identities and selected components,
  and require explicit confirmation before replacing current state.
- Support read-only inspection and file extraction as well as checkpoint restore.
  Coordinate with the manual filesystem access card rather than duplicating it.
- Keep the recovery environment available across restoration and define its
  relationship to EFI capture, boot-file overlay, and firmware entries.
- Document how recovery itself is maintained and retain an external-media fallback
  for failures outside the chosen environment's capabilities.

## Completion criteria

Record the investigated options, sources, and chosen design. On disposable
encrypted Btrfs/EFI targets, deliberately break normal boot and demonstrate
booting recovery without external media or another host, unlocking the target,
inspecting files, restoring a checkpoint, and successfully rebooting Agentoo.
Verify cancellation, wrong-target refusal, mounted-target refusal, and recovery
availability after restoration. Document disk-space requirements, maintenance,
entry instructions, and supported failure cases.

Related: 004-offline-checkpoint-creation.md; 005-efi-manual-filesystem-access.md;
`/usr/local/share/agentoo/docs/checkpoints.md`.
