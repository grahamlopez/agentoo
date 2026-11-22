# agentoo

An opinionated Gentoo distribution with agentic development and system
administration at its center. This repository brings its configuration and
installer under one roof, with a local overlay for custom ebuilds.

## Guides and docs

System

- [Host profiles and configuration policy](../../../../../etc/agentoo/README.md)
- [Installation, first boot, and user setup](installation.md)
- [Target host configuration checklist](host-onboarding.md)
  with [Thinktop](hosts/thinktop.md), [Flattop](hosts/flattop.md),
  [Startop](hosts/startop.md), and [Bequiet](hosts/bequiet.md) hardware baselines
- [System checkpoints and recovery](checkpoints.md)
- [Shell and editor environment](shell-editors.md)
- [Local Portage overlay](../portage/README.md)

Kernel

- [Firmware maintenance and diagnostics](firmware.md)
- [Native source and binary kernel workflows](kernel.md)
- [Initial Secure Boot signing and enrollment](secure-boot.md)
- [Agentoo initramfs packaging, development and smoke checks](initramfs.md)

User facing tools and configuration

Use `agentoo --help` (and `agentoo help COMMAND`) for CLI tool usage, options,
and examples; see [lib/cli.py](../lib/cli.py) for CLI conventions.

- [GUI installation and session setup](gui-base.md)
- [Audio setup and diagnostics](audio.md)
- [Displays, HiDPI, and laptop lid behavior](displays.md)
- [Secrets trust model and provisioning](../secrets/README.md)
- [Theming and light/dark appearance](theming.md)
- [Font diagnostics and selection](fonts.md)

## Philosophy and principles

### Configuration and state

The repository mirrors the target filesystem. Managed systems use a bare Git
repository at `/var/lib/agentoo/repository.git` with `/` as the work tree:
editing a tracked file changes the live configuration and appears in Git.

Prefer **system defaults → selected host fragments → local user overrides**,
using native Portage profile inheritance and application-native includes,
drop-ins, and matching rules. Actual precedence is application-specific and must
be checked when adding configuration.

- **System ownership:** Agentoo owns the system (`/etc`, `/usr/local`,
  `/boot/agentoo`). Put shared behavior on the system side wherever the
  application supports it.
- **Ebuilds vs. Git:** Ebuilds own packaged software and dependencies; avoid
  giving Git and Portage competing ownership of a file. USE flags select
  features rather than host identities.
- **Single branch, small host fragments:** All hosts share one branch and common
  defaults; keep host fragments minimal.
- **`$HOME` is untracked and disposable:** Agentoo never tracks `$HOME`
  configuration and never deploys user dotfiles as copies or symlinks. When an
  application requires a file in `$HOME/.config`, keep it a minimal untracked
  local override or include—never duplicate system defaults into `$HOME`.
- **Interactive state (4th layer):** Settings adjusted live during a session
  (such as appearance, wallpaper, or display/audio toggles) live in
  untracked `$XDG_STATE_HOME/agentoo/` or native user stores (e.g., GSettings).
  - *Live-only gate:* If a setting is not tweaked interactively in-session, put
    it in a static config file—do not build a CLI state manager for it.
  - *Never rewrite authored config:* Interactive tools write only to state,
    never mutating tracked `/etc` files or user `$HOME/.config` files.
  - *Clean reset:* Clearing state returns directly to authored defaults; native
    integrations read state directly without generating config copies.
- **Secrets and runtime state:** Secrets and generated runtime state stay
  outside Git.

See [host selection and configuration layout](../../../../../etc/agentoo/README.md#host-selection)
for native profile selection and how shared and host-specific configuration is
loaded.

### Scoped hardware exceptions

- **Keep defaults ideal:** Optimize shared defaults for the clean baseline; do
  not weaken common policy or add speculative generalizations for one machine.
- **Scope narrowly:** Bind each real-fleet workaround to the narrowest native
  selector—a host profile (`agentoo:hosts/<name>`) or an explicit hardware
  identifier (EDID, DMI, PCI/USB ID).
- **Preserve or compensate for the invariant:** When an exception relaxes a
  baseline guarantee, pair it with an explicit compensating control (e.g.,
  Bequiet enables `CONFIG_MODULES=y` for NVIDIA, paired with mandatory
  `MODULE_SIG_FORCE=y`).
- **Keep it visible and removable:** Record *why* the exception exists and what
  hardware requires it in a brief comment at the config site and in
  `docs/hosts/<host>.md`, so it can be retired cleanly when hardware or upstream
  behavior changes.

### Agentic design

- **Intrinsic boundaries over prose rules:** Encode safety, authority, and
  confirmation limits into tool behavior rather than relying on humans or agents
  to obey doc warnings (e.g., `gen-efi-cmd` prints instead of mutating NVRAM;
  `secrets install` refuses non-interactive input; `checkpoint restore` requires
  an exact confirmation token; the installer requires an explicit
  `--target-host`).
- **One structured plain-text output path:** Keep CLI output concise,
  predictable plain text that serves both humans and agents through a single
  code path. Add `--json` only for a real non-LLM programmatic consumer or data
  that loses fidelity in plain text—never just "for agents."
- **Concise negative findings:** When a non-obvious workaround, flag, or
  hardware behavior was tried and rejected or retired, leave a brief *why-not*
  note at the config/code site (or in `docs/hosts/<host>.md` for hardware facts)
  so future agents do not re-attempt the same dead end. Keep it to a sentence or
  two, never a changelog.

### Documentation

Minimize Markdown by putting knowledge where it operates. Every kind of
information has **one** authoritative home—never mirror it across two:

| Knowledge type | Single authoritative home |
| --- | --- |
| Tool mechanics (flags, bounds, units, exit codes, examples) | CLI `--help` (never mirrored in `docs/`) |
| Config/code invariants, register maps, and *why-not* notes | Comments beside the live code or config |
| Overlay package USE flags, user setup, and bump checklists | Native Portage (`metadata.xml`, `files/README.gentoo`, ebuild header comments) |
| Cross-tool mental models and multi-step human runbooks | Minimal `docs/` guides |
| Per-host hardware facts and exception indexes | Uniform `docs/hosts/<host>.md` baselines |
| Deferred work, investigations, future designs, active checklists, fleet migrations | `kanban/` cards |

**Litmus test for `docs/*.md`:** Strip out tool mechanics (→ `--help`) and
single-file config or packaging facts (→ comments / Portage). Keep a `docs/`
file only when a genuine cross-tool mental model or multi-step human workflow
remains—and point to `--help` or live files instead of paraphrasing flag tables,
keybinding tables, or config grammars (**No-Mirror rule**).

- **Current system only:** Durable docs (`docs/`, `README.md`, comments)
  describe the *current system*, never work-in-progress history. Never record
  test runs, dated verification logs, acceptance checklists ("pending/passed"),
  session checkpoints, or "not tested on hardware" disclaimers in durable
  docs—those belong in active Kanban cards or Git commit messages.
- **Git is the history folder:** Do not maintain `docs/history/` or archived
  legacy snapshots in the live `/` work tree. Delete retired docs cleanly with
  a descriptive commit message; Git history is the archive.
- **Uniform host baselines (`docs/hosts/<host>.md`):** Every onboarded physical
  host has one concise baseline using the same four sections:
  1. *Hardware identity* — model, CPU, GPU, Wi-Fi/BT, audio, storage.
  2. *Scoped exceptions* — host-specific profile, kernel, firmware, dracut, udev,
     desktop, and EFI exceptions with brief *why*.
  3. *Hardware quirks and negative findings* — concise *why-not* facts so agents
     do not repeat rejected fixes or misread benign logs.
  4. *Peripheral and workflow notes* — active display/dock/recovery notes and
     links to open `kanban/` investigations.

### Compatibility and fleet transitions

Agentoo is pre-alpha: code and configuration carry no backward-compatibility
shims, aliases, or upgrade paths. Clean reinstalls remain the ground-truth
baseline. When an in-place cutover across existing hosts is practical instead of
reinstalling, record the manual steps and a fleet host checklist in a temporary
`kanban/Open/` card—never in code or durable `docs/`—and delete the card once
every host has migrated (Git history retains it).

## Security and convenience boundaries

Baseline threat-model assumptions:

- **At rest and boot (hardened):** Defend against offline disk access and
  boot/kernel tampering (LUKS2 full-disk encryption, custom Secure Boot keys,
  module-less kernels or enforced module signatures).
- **Unlocked physical console (single-operator trust):** Once LUKS is unlocked
  at boot, physical access assumes the single local operator. Screen locking is
  casual walk-away protection, and the following single-user conveniences are
  intentional policy rather than oversights:
  - `tty1` autologin into Hyprland (which leaves the tty1 recovery shell
    unlocked if the compositor exits; see [screen locking](gui-base.md#screen-locking))
  - `ACCEPT_LICENSE="*"` in the common Portage profile
  - A root-owned `0600` GitHub token file for `agentoo git push`
- **Remote access, privileges, and supply chain (hardened):** Defend against
  network intrusion and untrusted artifacts (key-only SSH login, passworded
  `sudo`, strict tracked file permissions, ephemeral `/run`-backed secrets,
  checksum-pinned overlay sources, and GURU package allowlisting).

## Checks and verification

Live functionality on real hardware is the only real bar for project health.
The repository includes a lightweight test suite as an optional developer aid
for agentic iteration—not a philosophical requirement or substitute for real
hardware:

```sh
python3 usr/local/share/agentoo/tests/run_tests.py
```

This runs the Python and Lua checks using disposable files and mocks; skipped
checks indicate optional native tools are unavailable.
