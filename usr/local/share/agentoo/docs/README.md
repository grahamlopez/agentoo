# agentoo

An opinionated Gentoo distribution with development and system administration
at its center. This repository brings its configuration and installer under one roof, with a local overlay for custom ebuilds.

## Font troubleshooting for agents

Use `agentoo fonts doctor --text 'problem text' --json` for codepoints, Unicode
normalization, coverage, package ownership, fontconfig policy, and resolved Kitty
settings. Use `agentoo fonts doctor --text 'problem text'` for a human-readable report.
Read the [font diagnostic workflow](fonts.md#agent-diagnostic-workflow) for
command selection, JSON fields, and the limits of installed coverage versus
actual rendering. Font installation belongs to Portage; browser preview is
read-only, and saving a Kitty selection reloads all of the user's Kitty instances.

## Structure

The repository mirrors the target filesystem. Managed systems use a bare Git
repository at `/var/lib/agentoo/repository.git` with `/` as the work tree:
editing a tracked file changes the live configuration and appears in Git.

```text
/
├── etc/                              # Shared configuration, host fragments, and policy
├── boot/agentoo/checkpoint.sh         # Standalone recovery-capable shell tool
├── root/                             # First-boot verification and user setup
└── usr/local/
    ├── bin/                          # User-facing agentoo commands
    └── share/agentoo/
        ├── lib/                      # Python implementation and internal entry points
        │   ├── cli.py                # Parser policy and shared CLI helpers
        │   ├── completion.py         # Read-only completion service
        │   ├── git_transaction.py    # Internal Git deployment helper
        │   ├── display_backlight.py
        │   ├── desktop/              # Desktop state, effects, and wallpaper
        │   ├── fonts/                # Font configuration inspection helper
        │   └── kitty/                # Kitty host selection and watcher
        ├── fonts/                    # Font sample data
        ├── wallpapers/               # Wallpaper assets and attribution
        ├── docs/                     # Current guides and reference
        │   ├── history/              # Historical investigations and package lists
        │   └── skills/qemu-nbd/       # QEMU/NBD procedures and recovery reference
        ├── tests/                    # Python and Lua tests; run_tests.py runs both
        ├── git-hooks/                # Live-system permission automation
        ├── installer/                # Installer and installation runbook
        ├── kanban/                   # Backlog, Open, and Completed work
        ├── portage/                  # Working local Gentoo overlay
        ├── secrets/                  # Secret profile format and workflow
        └── shell/                    # Git prompt and Zsh completion integration
```

Application-native support files also live under `usr/local/share/nvim/` and
`usr/share/keymaps/`. The bare database at `/var/lib/agentoo/repository.git`,
local host selectors, user overrides, and runtime state are not repository payload.
User configuration ownership and the choice of shared or separate home Git work
trees remain TBD.

The authoritative installer and runbook live in `installer/` beside these docs.
The copies in `gentoo-notes` remain historical and are no longer maintained.
Development material accompanies deployed configuration deliberately.

Project skills live under `docs/skills/`. Ask agents explicitly to read
[the QEMU/NBD skill](skills/qemu-nbd/SKILL.md) before target operations.
Automatic discovery and agent-specific integration are future work; no skill
copies or symlinks are installed into user discovery directories.

The [Portage overlay](../portage/README.md) is enabled by the tracked
`/etc/portage/repos.conf/agentoo.conf` and updated through the project Git workflow.
Ebuilds own packaged software and dependencies; USE flags select features rather
than host identities. Avoid giving Git and ebuilds competing ownership of a file.

## Guides and verification

- [GUI installation and session setup](gui-base.md)
- [Audio setup and diagnostics](audio.md)
- [Cloud storage installation and setup](cloud-storage.md)
- [Displays, HiDPI, and laptop lid behavior](displays.md)
- [Firmware maintenance and diagnostics](firmware.md)
- [Desktop preferences](desktop.md)
- [Font diagnostics and selection](fonts.md)
- [Repository status and terminal color tests](terminal-tools.md)

Run the repository checks from a checkout:

```sh
python3 usr/local/share/agentoo/tests/run_tests.py
```

This runs the unified Python discovery suite followed by every Lua regression
script. Lua checks are explicitly reported as skipped when `lua` is unavailable.
Python tests that require optional native tools report their own skips. Tests use
disposable files and mocks; they do not establish live hardware correctness.

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

See the [custom kernel build notes](kernel-baseline-build.md) for the current
work-in-progress distribution-config approach. These are not yet a validated
runbook. [Card 14](../kanban/Completed/014-single-binary-kernel-baseline.md)
records the operator-confirmed successful custom-kernel boot, the superseded
defconfig-first experiment, and the remaining unverified acceptance checks.
