# Managed file permissions

`agentoo permissions check` checks without changing anything. Run
`agentoo permissions fix` as root to restore ownership and modes declared in
`/etc/agentoo/permissions.conf`. Use `--root /mnt/gentoo` for a mounted target.
The tool requires Python 3 and the agentoo Git repository. Both are available
when the installer applies the policy after its configuration checkout.

## Policy rules

Paths are relative to the target root. Owners are numeric UID/GID so the policy
works before user accounts exist. Modes are four-digit octal values; special
permission bits are rejected. Comments occupy their own lines.

```conf
# kind path uid gid file-mode directory-mode
tree usr/local/share/agentoo/ 0 0 0644 0755
tree usr/local/share/agentoo/git-hooks/ 0 0 0755 0755

# kind path uid gid mode
file usr/local/share/agentoo/installer/gentoo-install.sh 0 0 0755
file etc/sudoers.d/90-agentoo-graham 0 0 0440
dir etc/agentoo/secrets/ 0 0 0755
```

- `tree` supplies defaults for tracked files beneath a directory, the tree root,
  and parent directories of those tracked files within that tree. Its file mode
  and directory mode are separate.
- `file` manages one regular file and overrides any enclosing tree's file mode.
- `dir` manages only that directory and overrides its inherited directory mode.
  A `dir` rule does not provide defaults for descendants.

Rule order has no effect. Exact rules win; otherwise the closest enclosing tree
wins. A tree and a directory exception may name the same directory. Duplicate
rules of the same type, or file rules conflicting with directory/tree rules at
the same path, are errors, even when their values match.

Recursive rules select files from Git's tracked-file list rather than walking
all filesystem contents. Adding, removing, or moving a tracked ebuild or Kanban
card within a covered tree therefore needs no policy edit. An untracked file
inside the same directory remains untouched. Directories containing only
untracked files remain untouched too, unless explicitly declared as a tree root
or `dir`. Exact `file` rules deliberately manage their named files even if they
are untracked; use these only for intentional exceptions.

Every tracked file must resolve to a rule. Tree roots and exact paths must
exist with the expected type; missing paths fail validation. Removed inherited
files and their otherwise unused parent directories drop out automatically once
removed from Git's index. Update or remove stale exact rules when deleting or
moving their paths. The Git index is authoritative, including staged additions,
moves, and removals; unstaged deletions of tracked files remain errors.

On managed systems the tool uses `/var/lib/agentoo/repository.git` with the
target root as its work tree. In a development checkout or temporary test
repository it uses the target root's `.git`. A missing repository is an error;
there is no fallback to recursively managing local files.

## Safety and hooks

All selected paths and policy coverage are validated before fixes begin.
Symlinks in any managed path component, unsafe paths, and unexpected file types
cause failure. Directory-descriptor traversal avoids following substituted
parent symlinks, and fixes recheck the opened object's type and identity.
Concurrent filesystem changes can still interrupt a repair; stop other writers
while repairing and rerun the checker if interrupted.

The installer applies the policy after checkout, then configures the live
repository's `core.hooksPath` to `/usr/local/share/agentoo/git-hooks`:

- After checkout, merge, or rewrite/rebase: fix when running as root; otherwise check.
- Before commit: check and block the commit if permissions or policy coverage fail.

For an existing installation, run `agentoo git setup-hooks` as root to fix
permissions and enable the hooks. It refuses to replace a different configured
hooks directory. Hooks guard both the `/` work tree and the installed Git
database path, and are not enabled in development clones. Post-operation
failures report problems but do not roll back Git changes. Run the checker after
manual recovery; reset/restore and manual edits are not all covered by hooks.
No background service or automatic privilege prompt is installed. To disable
these hooks, use `agentoo git config --unset core.hooksPath`.

Run the focused checks from a development checkout with:

```sh
python3 -m unittest discover -s usr/local/share/agentoo/tests
```
