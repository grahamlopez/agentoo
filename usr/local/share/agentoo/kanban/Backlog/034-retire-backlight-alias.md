# Retire the backlight compatibility entry point

Created: 2026-10-30
Status: Backlog

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
