# agentoo

An opinionated Gentoo distribution with development and system administration
at its center. This repository brings its configuration and installer under one roof, with custom ebuilds planned.

## Structure

The repository mirrors the target filesystem. Managed systems use a bare Git
repository at `/var/lib/agentoo/repository.git` with `/` as the work tree:
editing a tracked file changes the live configuration and appears in Git.

```text
/
├── etc/
│   ├── agentoo/                      # Host identity, policy, and permissions manifest
│   ├── portage/                      # Portage configuration and package sets
│   ├── zsh/, vim/, xdg/nvim/          # Shared shell and editor defaults
│   ├── gitconfig, tmux.conf           # Shared Git and tmux defaults
│   ├── ssh/                          # Client defaults and account access policy
│   └── …                             # Application system defaults (as added)
├── home/<user>/.config/               # Real user configs / local overrides (TBD)
├── root/
│   ├── 001-firstboot-verify-and-checkpoint.sh # Verify and optionally checkpoint
│   └── 002-agentoo-setup-user.sh       # Create Graham’s account and access
├── usr/local/
│   ├── bin/
│   │   ├── agentoo-git                # Manage the live configuration work tree
│   │   └── agentoo-permissions        # Check or restore managed file permissions
│   └── share/agentoo/
│       ├── docs/                     # Project documentation
│       │   └── skills/qemu-nbd/       # QEMU/NBD procedures and recovery reference
│       ├── kanban/
│       │   ├── Backlog/              # Deferred work
│       │   ├── Open/                 # Active work
│       │   └── Completed/            # Finished work
│       ├── git-hooks/                # Live-system permission automation
│       ├── installer/
│       │   ├── gentoo-install.sh     # Installer
│       │   └── QEMU-NBD-INSTALL.md    # Installation runbook
│       └── portage/                  # Custom ebuild repository (planned)
│           ├── metadata/             # Repository metadata (planned)
│           ├── profiles/             # Distribution package policy (planned)
│           ├── eclass/               # Shared build logic, if needed (planned)
│           └── <category>/<package>/ # Custom ebuilds (planned)
└── var/lib/agentoo/repository.git/    # Bare Git database (local state)
```

This is the intended layout, not an inventory: planned paths need not exist.
User configuration ownership and the choice of shared or separate home Git work
trees remain TBD. Local host identity, overrides, and Git databases are not
repository payload; a path appearing here does not mean its contents are tracked.

The authoritative installer and runbook live in `installer/` beside these docs.
The copies in `gentoo-notes` remain historical and are no longer maintained.
Development material may accompany deployed configuration at this stage.

Project skills live under `docs/skills/`. Ask agents explicitly to read
[the QEMU/NBD skill](skills/qemu-nbd/SKILL.md) before target operations.
Automatic discovery and agent-specific integration are future work; no skill
copies or symlinks are installed into user discovery directories.

The future Portage repository can live inside this Git repository: `repos.conf`
will point to its directory, and the project Git workflow will update it.
Ebuilds own packaged software and dependencies; profiles express distribution
package policy while inheriting Gentoo. USE flags select features, rather than
host identities. Avoid giving Git and ebuilds competing ownership of a file.

## Configuration philosophy

Prefer **system defaults → selected host includes → local user overrides**, using
application-native includes, drop-ins, and matching rules. Actual precedence is
application-specific and must be checked when adding configuration.

- Put shared behavior on the system side wherever the application supports it.
- Keep host fragments small; all hosts share one branch and the common defaults.
- Keep personal preferences and machine-local state local unless explicitly tracked.
- Never deploy user dotfiles as copies or symlinks. A user file is either a real
  live file tracked through a Git work tree, or an untracked local override.

When an application requires a file in `$HOME/.config`, prefer a small real entry
file that includes system defaults and optional local overrides. If it cannot
include system defaults, decide explicitly whether its real user configuration
is tracked or local; do not duplicate defaults through a deployment step.
Whether tracked user files share this repository or use a separate home work
tree remains open. Secrets and generated runtime state stay outside Git.

## Host selection

The installer selects the host configuration explicitly with `--target-host`;
it does not infer it from the hostname or installation machine. It writes the
untracked local file `/etc/agentoo/target-host`, containing `GENTOO_TARGET_HOST="qemu"`,
for example. Portage's `make.conf` sources the common fragment, this selector, then
`90-${GENTOO_TARGET_HOST}`. Supported selectors currently include `generic`, `qemu`,
`thinktop`, and `startop`. All their fragments remain visible on every host.

See [configuration details](../../../../../etc/agentoo/README.md) and the
[development board](../kanban/README.md), and
[installation runbook](../installer/QEMU-NBD-INSTALL.md).

See [managed file permissions](permissions.md) for checks and Git automation.
