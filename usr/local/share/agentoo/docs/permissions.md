# Managed file permissions

`agentoo-permissions` checks without changing anything. Run
`agentoo-permissions --fix` as root to restore ownership and modes declared in
`/etc/agentoo/permissions.conf`. Use `--root /mnt/gentoo` for a mounted target.
The tool requires Python 3, already required by Gentoo/Portage.

The manifest uses filesystem-relative paths, numeric UID/GID, and octal modes.
A trailing `/` declares a directory, whose ownership and mode are also checked.
Add an entry whenever adding a tracked file. Files must exist and be regular;
symlinks and missing policy entries for tracked files cause failure before fixes.
Only listed paths are changed; there is no recursive ownership repair. Local
identity, credentials, generated files, and unlisted directory permissions remain the
installer's responsibility. In particular, the checkpoint helper stays `0700`.

The installer applies the manifest after checkout, then configures the live
repository's `core.hooksPath` to `/usr/local/share/agentoo/git-hooks`:

- After checkout, merge, or rewrite/rebase: fix when running as root; otherwise check.
- Before commit: check and block the commit if permissions or policy coverage fail.

For an existing installation using the new agentoo paths, run
`agentoo-git setup-hooks` as root. It fixes permissions and enables these hooks;
it refuses to replace a different configured hooks directory. This is not a
migration command for legacy gentoo-config installations.

Hooks guard both the `/` work tree and the installed Git database path. They
are not enabled in development clones. Post-operation failures report problems
but do not roll back Git changes. Manual edits, chmod, and Git operations such
as reset/restore are not all covered: run the checker after manual recovery.
No background service or automatic privilege prompt is installed. To disable
these hooks, use `agentoo-git git config --unset core.hooksPath`.
