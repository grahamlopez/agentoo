# Git updates for the system repository

`agentoo git` accepts Git subcommands, aliases, and options directly, using
`/var/lib/agentoo/repository.git` with `/` as the work tree. For example,
`agentoo git br` and `agentoo git --no-pager log -5` work like their Git
equivalents. `enable-write` is an Agentoo helper command.

Read-only Git commands (`log`, `show`, `branch`, `diff`, `status`, and read-only
aliases) run as the invoking user with `GIT_OPTIONAL_LOCKS=0` against the
world-readable system repository (`core.sharedRepository=0644`, configured in
`/etc/agentoo/gitconfig` via `/etc/gitconfig`). Full-tree `status` or `diff`
without `sudo` still reports `Permission denied` on root-only tracked paths such
as `/root/`; use `sudo agentoo git status` for a complete work-tree check.

Mutating Git commands (`pull`, `fetch`, `push`, `commit`, `checkout`, etc.)
fail fast without `sudo` and require `sudo agentoo git ...`. Only `enable-write`
requests sudo authorization automatically. Root invocations use root's Git
configuration and SSH access.
If identity setup was skipped, configure it with
`sudo agentoo git config --local user.name "Your Name"` and
`sudo agentoo git config --local user.email "you@example.com"` before committing.

The shared Git configuration trusts `/var/db/repos/gentoo`, matching the entry
Portage adds for its Git repository backend.

Git aliases in `/etc/gitconfig` are shared by root and ordinary users. They work
with both `git` and `agentoo git`; no root-local copy is needed. To verify the
effective aliases and their source, run
`git config --show-origin --get-regexp '^alias\.'`. Account-local and repository
settings can override the shared defaults.

The installer configures `pull.rebase=true` locally in the live Git database, so
`agentoo git pull` rebases local commits by default. This setting persists in
`/var/lib/agentoo/repository.git/config`; it is separate from development-clone
settings. Commit or reconcile live edits before pulling; updates immediately
change system files, and Git hooks restore managed permissions.
