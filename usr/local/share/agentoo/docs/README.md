# agentoo

An opinionated Gentoo distribution with agentic development and system
administration at its center. This repository brings its configuration and
installer under one roof, with a local overlay for custom ebuilds.

## Guides and docs

System

- [Host selectors and configuration policy](../../../../../etc/agentoo/README.md)
- [Installation, first boot, and user setup](installation.md)
- [Target host configuration checklist](host-onboarding.md)
  and [Flattop hardware baseline](hosts/flattop.md)
- [System checkpoints and recovery](checkpoints.md)
- [Git updates for the system repository](git.md)
- [Managed file permissions and Git automation](permissions.md)
- [Shell and editor environment](shell-editors.md)
- [Local Portage overlay](../portage/README.md)

Kernel

- [Firmware maintenance and diagnostics](firmware.md)
- [Custom kernel rebuild commands](kernel.md)
- [Minimal initramfs building and smoke checks](../initramfs/README.md)

User facing tools and configuration

- [Agentoo CLI usage, completion, and conventions](agentoo-cli.md)
- [GUI installation and session setup](gui-base.md)
- [Audio setup and diagnostics](audio.md)
- [Cloud storage installation and setup](cloud-storage.md)
- [Displays, HiDPI, and laptop lid behavior](displays.md)
- [Secret profiles and installation](../secrets/README.md)
- [Desktop preferences](desktop.md)
- [Font diagnostics and selection](fonts.md)
- [Repository status and terminal color tests](terminal-tools.md)

Misc

- [Installation runbook for QEMU VMs](../installer/QEMU-NBD-INSTALL.md)
- [Agent skills for QEMU/NBD target operations and recovery](skills/qemu-nbd/SKILL.md)

## Configuration philosophy

The repository mirrors the target filesystem. Managed systems use a bare Git
repository at `/var/lib/agentoo/repository.git` with `/` as the work tree:
editing a tracked file changes the live configuration and appears in Git.

Prefer **system defaults → selected host includes → local user overrides**,
using application-native includes, drop-ins, and matching rules. Actual
precedence is application-specific and must be checked when adding
configuration.

- Put shared behavior on the system side wherever the application supports it.
- Ebuilds own packaged software and dependencies; avoid giving Git and Portage
  competing ownership of a file. USE flags select features rather than host
  identities.
- Keep host fragments small; all hosts share one branch and the common
  defaults.
- Keep personal preferences and machine-local state local unless explicitly
  tracked.
- Never deploy user dotfiles as copies or symlinks. A user file is either a
  real live file tracked through a Git work tree, or an untracked local
  override.

When an application requires a file in `$HOME/.config`, prefer a small real
entry file that includes system defaults and optional local overrides. If it
cannot include system defaults, decide explicitly whether its real user
configuration is tracked or local; do not duplicate defaults through a
deployment step. Whether tracked user files share this repository or use a
separate home work tree remains open. Secrets and generated runtime state stay
outside Git.

See [host selection and configuration policy](../../../../../etc/agentoo/README.md#host-selection)
for installer selection, the local selector file, and how shared and host-specific
configuration is loaded.

## Checks and verification

Run the repository checks from a checkout:

```sh
python3 usr/local/share/agentoo/tests/run_tests.py
```

This runs the repository's Python and Lua regression tests. Lua checks are
reported as skipped when `lua` is unavailable; Python tests that need optional
native tools report their own skips. Tests use disposable files and mocks; they
do not establish live hardware correctness.
