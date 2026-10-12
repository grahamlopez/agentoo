# Offline checkpoint creation

Created: 2026-10-11
Status: Backlog

## Context and decision

During checkpoint refinement, we considered capturing an unbootable target from
recovery media before restoring a named checkpoint. Such capture could preserve
uncheckpointed configuration, data, and diagnostic logs; it does not repair boot.

The user deferred this capability until a concrete need arises. The intended
current boundary is online creation and offline restoration. Restore intentionally
discards selected current state, retains named checkpoints, and creates no implicit
pre-restore backup. Users can explicitly checkpoint before restoring when the
system is bootable.

The current command is agentoo-checkpoint, with its implementation on EFI and
a system-side launcher. It uses POSIX sh for recovery compatibility.

## Proposed scope

- Explicit --device selects an unlocked offline Btrfs target.
- Reuse capture operations for Agentoo's known top-level system/home layout.
- Require the target EFI mount when EFI capture is selected.
- Refuse mounted target system/home subvolumes; avoid chroot or target executables.
- Print target identity, mode, selected components, and cleanup before confirmation.
- Preserve the agreed component-selection semantics and online behavior.
- Decide offline distfile cleanup explicitly. Exact pre-restore preservation
  should use --no-clean-distfiles; do not silently assume an unbootable target
  lacks valuable data.

## Completion criteria

Test offline capture on disposable Btrfs/EFI images, verify the resulting checkpoint
can restore its selected components, and document recovery-tool dependencies and
invocation. Keep this optional capability separate from the simpler restore path.

Related: 005-efi-manual-filesystem-access.md.
