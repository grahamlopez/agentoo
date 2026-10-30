# Decide whether pCloud should manage only service-owned processes

Created: 2026-10-30
Status: Backlog

Investigation, not an established obsolete-code removal. In
`usr/local/bin/agentoo-cloud-storage`, `stop_unmanaged` maintains a separate
process-identification, signalling, and wait path originally supporting
migration from manually launched pCloud. Systemd already handles managed stop.
However, `docs/cloud-storage.md` documents that the application menu still
launches the native client directly, and promises unmanaged stop behavior.

Decide whether supporting both launch paths remains useful. A service-only stop
could instead direct users to the application's Quit action for unmanaged
instances, while retaining duplicate-instance detection before start. This
would reduce functionality, not just implementation detail; do not remove it
solely because it is labelled migration code.

Complete with an explicit scope decision. If narrowing behavior, update help,
guides, and tests together; verify managed start/stop, unmanaged-instance
detection, and the chosen manual quit guidance. If retaining both paths,
record the continuing requirement without creating a replacement framework.
