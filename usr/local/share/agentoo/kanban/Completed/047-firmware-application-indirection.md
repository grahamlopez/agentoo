# Simplify single-use indirection in firmware application

Created: 2026-10-31
Status: Completed
Priority: Lower

The implementation review found the firmware path split across the
[kernel command](../../../../bin/agentoo-kernel) and
[firmware module](../../lib/kernel_firmware.py): the CLI calls `command()`, which
inspects state and chooses `apply()` or status; `apply()` calls the single-use
`plan()` preflight. Execution, confirmation, and notice functions are passed
through these layers. Following the complete operating procedure requires
unnecessary jumps before reaching its native operations.

Consider putting the small firmware dispatch directly in the CLI branch and
the application preflight beside the application procedure. Retain helpers that
actually serve multiple callers and shared privilege behavior where justified.
Do not replace the removed indirection with a generic command runner, dependency
injection mechanism, or broader module reorganization.

Preserve status/apply scope, native savedconfig precedence, validation before
writes, dry-run behavior, confirmation and sudo boundaries, backups, source
rebuild policy, and installed-result checks. The module/image installation
defect in [card 036](../Completed/036-kernel-installed-module-consistency.md) is separate work.

Complete when the firmware application reads as a more direct procedure with
superseded wrappers removed. Run the focused disposable firmware tests and
review planning, rejection, and failure messages; no live firmware rebuild or
storage operation is required for this refactor.


## Completion, 2026-10-31

Firmware status/apply dispatch now lives directly in the CLI branch, and apply's
validation and native override selection are inline with its operating procedure.
The single-use `command()` and `plan()` wrappers are removed. The existing
shared CLI execution, authorization, confirmation and notice functions remain;
there is no new runner, callback mechanism or module structure.

The native savedconfig precedence, dry-run boundary, validation before writes,
backups, source-only emerge options, confirmation/privilege boundaries and
installed-result checks are unchanged. Focused verification exercises status
and apply through the actual CLI with disposable firmware/package fixtures;
policy-precedence coverage now checks the real application instead of the
removed planning wrapper. All 54 kernel/firmware tests passed without skips
(38 kernel and 16 firmware tests), including rejection and failure cases. No
live firmware rebuild or system change ran.
