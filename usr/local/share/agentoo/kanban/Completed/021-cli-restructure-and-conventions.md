# Restructure the Agentoo CLI and establish durable command conventions

Created: 2026-10-19
Status: Completed — implemented, reviewed, and accepted through normal usage
Completed: 2026-10-21

## Decisions and review status

Use [clig.dev](https://clig.dev/) as guidance, subject to Agentoo's minimalism,
simplicity, maintainability, and rescue requirements. The restructuring is
committed on main. The user considers normal installed-system usage sufficient
to satisfy the remaining acceptance items and close this card.

The user approved the behavior changes with these qualifications:

1. **Root help approved.** Retain its current presentation.
2. **Clear distfile and binary-package caches by default when capturing system.**
   Captures without system preserve caches; `--no-clean-package-caches` opts out.
3. **No compatibility aliases.** Use only canonical cache options and permission
   `check`/`fix` subcommands; do not restore removed spellings.
4. **Remove borrowed Proton sessions and checkpoint JSON reporting.** Retain one
   owned interactive secrets session and human checkpoint reports. Keep validation,
   planning, cancellation, verification, and recovery safeguards. Review both
   removals independently for unintended behavior changes.

## Closure decision

On 2026-10-21, the user accepted the remaining operational acceptance items based
on normal usage. No separate operational-validation card is required for closure.
This is operator acceptance, separate from the automated verification below.
It is not an independently witnessed record of every originally listed failure,
interruption, disposable-storage, or alternate rescue-shell scenario. No such
specific executions are inferred from normal usage or mocked tests.

## Structure and maintenance rules

- `usr/local/bin/agentoo` is a thin Python dispatcher: explicit command catalog,
  root help/version, help/completion routing, and exec to fixed executable paths.
- Each normal command is an independently runnable Python `agentoo-NAME`
  executable containing its implementation. Direct/grouped invocations agree.
- Each normal command owns one parser for execution, help, and completion.
  No duplicate prevalidation or argument translation in the dispatcher.
- `usr/local/share/agentoo/lib/cli.py` contains the authoritative concise policy and
  small parser helper. Imports use the sibling installed share directory and
  work from a checkout. Completion lives in `lib/completion.py`; the
  Git deployment helper is `lib/git_transaction.py`.
- `boot/agentoo/checkpoint.sh` remains self-contained POSIX sh, without Python,
  Bash, or shared runtime helpers. `agentoo-checkpoint` is a small sh launcher.
  Rescue instructions name the script directly when the installed root is absent.
- Use the standard library; extract helpers only from actual repetition. No CLI
  framework, base-command classes, plugin discovery, capability metadata schema,
  mandatory option set, or launcher/module pair for every command.
- No project `AGENTS.md`. Put the policy in implementation comments/docstrings,
  a pointer in the dispatcher, and important exceptions beside their code.
- Add command surface together with help/completion and focused verification.
  Tests discover baseline help from the catalog but cannot prove every behavior.

## CLI policy

1. Use familiar long options and useful short forms; reject implicit option
   abbreviations. Support conventional equals forms and practical ordering.
2. Help succeeds before privileges/effects. Respect `--` as a data boundary and
   preserve arbitrary Git arguments rather than interpreting them as Agentoo flags.
3. Results and requested help go to stdout; plans, progress, warnings, and update
   summaries go to stderr. Document useful machine formats and exit semantics.
4. `--no-input` must never prompt, including through sudo/authentication. Fail
   clearly when input or authorization is unavailable; use `sudo -n` where needed.
5. Validate inputs before effects, and before escalation where readable. Protected
   inputs may require sudo, after which validation must run again.
6. Respect XDG paths, redirection, terminal capabilities, and color preferences
   where applicable. Do not add features merely to satisfy every guide suggestion.
7. There are no compatibility requirements for this restructuring. Keep the
   canonical interface small; document intentional behavior changes.

## Implemented behavior changes

| Area | Implemented behavior |
|---|---|
| Invocation | The original eight command families have standalone `agentoo-*` executables. Obsolete private implementations, compatibility loaders, and legacy dispatcher are removed. |
| Help and identification | Nested help and incomplete-value help work safely; concise root help is approved. Root version reports repository revision or unavailable. Typo suggestions never execute corrections. |
| Parsing and completion | One authoritative normal-command parser; independent sh parser plus small checked completion description for checkpoint. Equals forms/order work; implicit abbreviations and removed aliases fail. |
| Streams | Results/help stay stdout; operational notices move to stderr. Screenshot returns its saved path; checkpoint creation returns its exact generated name. |
| Power | Adds JSON measurements with documented units/null values; missing hardware is a successful partial report. Existing text output is preserved. |
| Permissions | Explicit `check`/`fix`; no hidden operation flags. Check JSON exits 0 compliant, 1 mismatches/errors, 2 syntax errors; JSON is rejected for fix. `--no-input` uses sudo -n. |
| Fonts | `--no-input` blocks interactive windows/choosers, while explicit selection/restore/samples and browser `--no-open` remain usable. Save identifies changed files and retains undo. Diagnostic phases use stderr; short queries have 15-second bounds, GUI lifetime is unbounded. |
| Desktop | Brightness behavior is preserved. Screenshot safe help and region `--no-input` rejection added; cancellation terminates/reaps the child and removes incomplete files. Desktop hotkeys remain usable. |
| Git | Arbitrary forwarding/guard selection preserved. Own setup operations have safe help/validation and noninteractive sudo; notices and lock waits use stderr. Genuine hooksPath query failures fail. |
| Secrets validation/install | Equals/interleaved categories work; unknown categories and invalid selected input fail before fetching/writing. Adds dry-run and explicit confirmation. Replacement is atomic per file; partial multi-file installs remain possible. |
| Secrets authentication | One invocation-owned private /run interactive session, followed by logout and local cleanup. No borrowed-session option or unattended installation. `--no-input` permits dry-run planning and fails installation before privilege/provider effects. `--yes` skips replacement confirmation, not authentication. |
| Secrets operational bounds | Provider diagnostics are sanitized and inherited Proton overrides removed. Calls have 60s provider, 10s logout, and 15s Git-config bounds; provider cancellation is bounded. Default owned-session cleanup remains. |
| Checkpoint caches | System capture clears distfiles/binpkgs/binhost by default; non-system capture preserves them. Only `--clean-package-caches` / `--no-clean-package-caches` are supported. |
| Checkpoint authorization/planning | Terminal-stdin confirmation; unattended create needs `--yes`, restore exact `--confirm NAME`. `--no-input` uses sudo -n. Dry-run validates/plans before mutation but still needs root, locks, temporary files, and inspection mounts/extraction. |
| Checkpoint inspection | Read-only mounts use `rescue=nologreplay` (kernel 5.9+), with no unsafe fallback or live remount. Concurrent writers remain outside the dry-run guarantee. Required utilities are checked before filesystem operations. |
| Checkpoint reporting | Human listing and verified manifest output; no JSON option/encoder/schema. Progress/failure phase/completed components use stderr. No rollback journal; sh may defer traps while filesystem tools run. |

Preserved: brightness increments/no-panel success, private unique screenshot files,
font preview isolation/undo, checkpoint identities/completeness/archive checks and
home-preserving restore default, Git deployment guarding, secret profile formats,
file ownership/modes, and repository-specific GitHub credential configuration.

Exact workflows and limits live in [checkpoint documentation](../../docs/checkpoints.md),
[secrets documentation](../../secrets/README.md), [permissions documentation](../../docs/permissions.md),
and [font documentation](../../docs/fonts.md). Keep procedures there rather than
copying them into this card.

## Implementation and review sequence

| Phase | Scope | State |
|---|---|---|
| 1 | Establish concise implementation policy and record baseline behavior. | Implemented |
| 2 | Establish dispatcher/standalone layout with power, then migrate fonts and permissions. | Implemented |
| 3 | Migrate backlight/screenshot, then Git, then secrets; review each unit. | Implemented and independently reviewed |
| 4 | Improve checkpoint separately, preserving rescue independence. | Implemented and independently reviewed; operator acceptance recorded below |
| 5 | Address safe help/parsing, interaction, streams, planning, useful JSON for power/permissions/fonts, progress, and recovery feedback. | Implemented and user-approved |
| 6 | Remove transitional code/aliases and update callers, completion, docs, and tests. | Implemented |
| 7 | Complete user review, deploy separately, and validate operational paths. | Completed through user acceptance of normal installed-system usage |

The original eight recommendations are covered by: safe help (R1), parser parity
(R2), optional interaction (R3), streams (R4), useful machine output (R5), help and
identification (R6), operational feedback/recovery (R7), and planning/side effects
(R8). Root help is approved; unattended secrets and checkpoint JSON
were deliberately excluded to keep critical operation paths small.

## Verification evidence

- Main verification on 2026-10-21: **158 Python tests and five Lua scripts pass**,
  including real interactive Zsh completion. The formerly separate 21-test font
  selection suite is now included in unified discovery.
- Checkpoint/launcher sh syntax, installer Bash syntax, and whitespace checks pass.
  `/bin/sh` here is Bash; this does not establish alternate rescue-shell behavior.
- Tests use fake provider/filesystem tools and disposable files. No real credentials,
  authenticated sessions, live configuration, mounts, snapshots, or restoration
  were exercised by implementation tests.
- Independent reviews caught and corrected transitional wrapper recursion,
  screenshot child-cancellation waits, protected-profile escalation, confirmation
  interruption, secret-bearing decode failures, missing rescue dependencies,
  read-only Btrfs log replay, and diagnostic stdout leaks.
- All four Git hooks already use canonical permission subcommands. Isolated
  root/nonroot checks verify pre-commit always checks, root post hooks fix,
  nonroot post hooks check, and permission failures propagate. The deployment
  guard and installer also use canonical forms.
- Separate implementation agents removed borrowed authentication and checkpoint
  JSON; an independent reviewer compared both runtime diffs against the staged
  baseline and found no unintended changes. All 21 focused tests pass, covering
  retained owned-session cleanup, human reporting, verification, and removed-option
  rejection. Root help is unchanged. The removals reduce runtime files by 114 lines.

## Acceptance and retained limits

- [x] User approved root help presentation and the revised behavior changes.
- [x] User accepts installed command and privilege behavior through normal usage.
- [x] User accepts GUI capture, previews, and cancellation through normal usage.
- [x] User accepts installed Git deployment and permission-hook behavior.
- [x] User accepts Proton authentication and session handling.
- [x] User accepts checkpoint and rescue readiness for this restructuring.

These checkmarks record the user's closure decision, not additional test runs by
the implementation agent. The original operational checklist included checkpoint
cache cleanup, mounted-live inspection, restoration, failure/interruption/retry on
disposable storage, and an alternate POSIX shell on minimal rescue media. No
per-scenario results were supplied with this acceptance; those remain useful
checks when relevant rather than blockers for this completed card.

The documented implementation limits remain: restoration has no rollback journal,
secret installation can partially complete, and planning cannot freeze other
writers. Closing the restructuring does not change those boundaries or establish
behavior on every host or rescue environment.
