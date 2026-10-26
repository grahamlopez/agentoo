
agentoo secrets on my new flattop install gave not useful diagnostics and wouldn't work

sudo agentoo secrets install --profile agentoo --user graham all
Password:
agentoo secrets: Operation failed; check inputs, permissions, and dependencies. Partial installs may remain.

## Resolution

Profile-open failures now identify the file and OS error and explain that
`--profile` expects a local file, not a Proton vault name. Simple progress
messages identify retrieval, destination writes, and Git configuration before
each operation. The change keeps the implementation readable without adding
preflight checks or a diagnostic framework; raw provider errors remain suppressed.

Validation: all 10 existing secrets tests pass. A dry run with `--profile agentoo`
reproduces the missing-file failure and now reports the actionable profile error.
No live secrets were retrieved or installed during validation.
