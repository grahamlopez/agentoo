# Retire the backlight compatibility entry point

Created: 2026-10-30
Status: Completed
Completed: 2026-10-31

`usr/local/bin/agentoo-backlight` explicitly identifies itself as a compatibility
entry point. The canonical operation is `agentoo display backlight`; the audit
found no live in-repository callers of the old name, but personal/external
scripts have not been checked. The CLI guide still promises support for it.

Check remaining callers, then remove the old executable and its support promise
if compatibility is no longer required. Keep the canonical command, device
selection behavior, help, and completion. `agentoo-screenshot` is a normal
standalone command and is not part of this retirement.

Complete when affected bindings/scripts use the canonical invocation and
display/backlight tests pass. Check removal from deployed systems as well as
the checkout; do not add another alias or fallback to preserve the retired name.

## Resolution

The operator established that Agentoo is pre-alpha and backward compatibility
is not a requirement; AGENTS.md now states that policy. Removed the tracked
`agentoo-backlight` executable, its otherwise-unused parser/entry functions,
the test fixture entry, and the guide's compatibility promise. Current bindings
already use `agentoo display backlight`. Historical cards retain the old name
as evidence of earlier implementation. No compatibility or migration path was
added, and screenshot code was left unchanged.

Validation: all 16 CLI tests and six desktop-command tests pass, including
canonical backlight adjustment, help, and completion checks. Screenshot file
contents were verified unchanged from the start of this task.
