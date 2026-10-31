# Preserve existing directories when installing secret files

Created: 2026-10-31
Status: Completed
Priority: High

In [agentoo-secrets](../../../../bin/agentoo-secrets), `install_file()` always
changes the destination parent's owner and mode. A root destination changes an
existing private directory from `0700` to `0755`; a user destination can take
ownership of an existing parent. These effects exceed replacing the selected
file and are absent from its printed replacement plan.

The review compared disposable directories: native `install -D -m 0600`
preserved the existing parent's `0700`, while Agentoo changed it to `0755`.
Ownership calls were mocked for the Agentoo reproduction; no real secrets or
system directories were involved. The current
[guide](../../secrets/README.md) documents assigned parent modes and asks for
dedicated parents, so update that contract along with the implementation.

Preserve existing parent ownership and permissions. Create missing directories
with intentional modes, and keep any necessary directory-policy changes explicit.
Use native behavior where sufficient; do not introduce a general deployment
engine. Retain private file modes, atomic replacement, authentication isolation,
and the field/template/github methods.

Completed on 2026-10-31. `install_file()` now creates only missing parent
directories, from the existing ancestor outward. Each new directory gets the
selected file owner/group and mode `0700` for user destinations or `0755` for
root destinations. Existing directories receive no ownership or mode changes.
This also avoids leaving new intermediate directories root-owned and private
when creating a nested user destination. The private temporary file and atomic
replacement procedure are unchanged; the guide describes the revised contract.

Validation: all 14 secrets tests pass, including disposable coverage for root
and user destinations, existing `0700`/`0750` parents, nested missing parents
under a restrictive umask, mode `0600` file replacement, and replacement failure
preserving the original file and parent while cleaning the temporary file.
Ownership calls were mocked; no real secrets or system directories were used.
`git diff --check` passed. No new mechanism or compatibility path was introduced.
