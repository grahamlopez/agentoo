# Refactor permissions policy to support recursive definitions

Created: 2026-10-14
Status: Backlog

## Requested changes

Refactor `etc/agentoo/permissions.conf` and `usr/local/bin/agentoo-permissions`
to use recursive directory definitions wherever practical. Adding, removing, or
moving tracked files within a covered directory should not require one policy
edit per file. Retain explicit rules for paths needing different permissions.

## Context

Adding the Codex and Claude Code ebuilds omitted four file entries from the
current flat policy. The post-merge hook reported missing policy coverage and
refused to fix any permissions, including unrelated mode mismatches. Most files
in the overlay and documentation trees share ownership and modes, making
per-file entries repetitive and easy to miss. Moving a Kanban card also requires
updating its policy path even though its permissions do not change.

## Implementation scope

- Define recursive rules with separate defaults for regular files and directories,
  plus explicit exceptions. Specify deterministic precedence for nested rules and
  exact paths; reject ambiguous or invalid definitions before changing anything.
- Apply recursive coverage to suitable uniform trees, including the Portage
  overlay and Kanban board. Audit other directories before converting them.
  Preserve restricted scripts, sudoers, credentials, and executable modes through
  explicit exceptions or appropriately scoped rules.
- Default recursive file selection to Git-tracked files. Define which parent
  directories are managed without recursively changing untracked files, generated
  state, credentials, or unrelated directory contents.
- Preserve symlink rejection, path containment, file-type checks, and validation
  before fixes. Recursive rules must not follow symlinks or change paths outside
  the configured target root. Preserve the opened-file checks during mutation.
- Make tracked-file coverage resolve through inherited rules. Keep useful errors
  for uncovered paths and invalid exceptions; clarify missing-directory behavior.
- Update the policy, permission documentation, and any installer or hook behavior
  affected by the new format. Preserve `--check`, `--fix`, and `--root` workflows.

## Completion criteria

- Adding a tracked file, deleting one, or moving it within a recursive tree needs
  no policy edit, and the checker correctly resolves ownership and mode.
- Nested and exact-path exceptions override defaults predictably; regular files
  and directories receive their respective modes. Restricted and executable
  paths retain their intended permissions.
- Uncovered tracked files are still reported. Untracked local state remains
  untouched, including when located inside a recursive tree.
- Invalid rules, symlinks, unexpected file types, and unsafe paths fail before
  any fixes. Checks against a mounted target behave consistently with `/`.
- Exercise these cases in a temporary Git work tree, including Kanban card moves,
  newly added ebuilds, and post-merge repair of unrelated mode mismatches.

This card records deferred work; it does not authorize implementing the refactor.
