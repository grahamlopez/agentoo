# Preserve existing directories when installing secret files

Created: 2026-10-31
Status: Backlog
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

Complete when installing a file leaves an existing parent's ownership/mode
unchanged, including on failure. Add disposable coverage for existing private
parents, missing directories, root/user destinations, and file replacement.
