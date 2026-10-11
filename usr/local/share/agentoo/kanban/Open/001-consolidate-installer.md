# Consolidate the installer into agentoo

Created: 2026-10-10
Status: Open

## Intent and historical context

The installer has produced bootable Gentoo installations both in QEMU and on a
physical disk on the development host. The user wants agentoo to become
the main base of operations and eventually house this entire project, including
the installer. They explicitly deferred the migration: this card records future
work and does not request moving code now.

Current source repository: `/home/graham/Projects/gentoo-notes`.
Future primary repository: `/home/graham/Projects/agentoo`.
The inspected configs checkout was on branch `agentic-gentoo`; verify current
branch and local changes before implementation.

## Existing entry points

- `gentoo-notes/installer/gentoo-install.sh`: executable installer and canonical
  design record, with phase documentation adjacent to implementation.
- `gentoo-notes/installer/QEMU-NBD-INSTALL.md`: production QEMU/NBD playbook.
- `gentoo-notes/.agents/skills/qemu-nbd/SKILL.md`: target identification,
  privilege escalation, attachment, and teardown instructions; includes a
  namespace-recovery reference.
- `agentoo/etc/agentoo/README.md`: configuration layout conventions.
- `agentoo/usr/local/bin/agentoo-git`: helper for a bare Git repository
  at `/var/lib/agentoo/repository.git` with `/` as its work tree.

The installer currently covers disk setup, stage3 bootstrap, Portage foundation,
system update, kernel foundation, first-boot foundation, and handoff. Preserve
the working production path and target safety checks during migration.

## Recommendations for future implementation

1. Inventory installer dependencies, documentation, skills, references, and
   hard-coded repository paths before deciding the destination layout.
2. Account for agentoo being checked out directly onto `/` on managed
   systems. Choose deliberate locations for executable tools versus passive
   development resources; avoid accidental runtime behavior.
3. Move the installer with its canonical documentation and necessary supporting
   resources. Update commands, relative links, skill references, and source paths.
4. Check how an installer hosted in the same repository it checks out will obtain
   and select the configuration revision. Preserve explicit source/branch inputs.
5. Avoid leaving two independently maintained installer implementations. Define
   any compatibility pointer or wrapper deliberately.
6. Scope the rest of project consolidation with the user; do not assume every
   historical note or host artifact should become live configuration.

## Completion criteria

- The authoritative installer and associated runbook live in agentoo in
  a documented layout appropriate to its root-work-tree model.
- References and invocation paths work from the new location.
- Syntax and dry-run behavior are checked, with an appropriate production-path
  QEMU validation recorded. Do not rebuild or erase the existing baseline merely
  to validate file relocation.
- The old repository clearly points to the new authority, and the card records
  final paths, revisions, validation, and any remaining migration work.

Related: `002-minimal-systemd-initial-policy.md`. That change is separately
deferred; migration should not silently implement it.

## Migration update — 2026-10-10

The installer and runbook were copied to
`/usr/local/share/agentoo/installer/` in agentoo, including the agentoo path and
command updates. Their invocation examples now use that location. Uncommitted
changes in gentoo-notes were reverted; its committed copies are historical.
The project README documents agentoo as the maintained authority.

Validation: shell syntax, help output, documentation paths, and whitespace.
No disk operations or VM rebuild were performed. The qemu-nbd skill and its
namespace-recovery reference now live under `docs/skills/qemu-nbd/`, with a
verified link to the maintained runbook. Agents use it explicitly; discovery
integration is deferred. The card remains Open for production-path validation
when next testing an install and review of any remaining supporting references.
