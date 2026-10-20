# Restructure the Agentoo CLI and establish durable command conventions

Created: 2026-10-19
Status: Open

## Objective

Align the command surface with [Command Line Interface Guidelines](https://clig.dev/)
while preserving Agentoo's minimalism, simplicity, and maintainability. Use Python
for the dispatcher and normal commands, expose independently runnable
`agentoo-*` executables, and retain a self-contained POSIX `sh` checkpoint tool
for rescue environments without Python.

This card records the agreed plan. It does not implement or deploy changes.
Future implementers should read the complete card; later simplifications below
take precedence over earlier proposals for a generic CLI framework.

## 1. Design philosophy and boundaries

1. Build a small command suite, not a CLI framework. Prefer Python's standard
   library and `argparse`; no new framework dependency without a concrete need.
2. Each command owns its parser, validation, help, privileges, and operation.
   Parse once. The dispatcher must not validate arguments and then forward the
   original tokens to a different parser.
3. Each top-level command has a directly runnable `agentoo-NAME` executable.
   It may contain its implementation; do not require a thin launcher plus a
   separate module for every command.
4. Keep the dispatcher thin: command catalog, root help/version, help routing,
   completion routing, and `exec` to fixed installed executable paths. Use a
   simple explicit command-to-description mapping, not unrestricted PATH plugin
   discovery or an elaborate metadata registry.
5. Extract small shared helpers from real repetition. No command base classes,
   generic lifecycle, capability schema, dependency injection system, or metadata
   required solely to make behavior generically testable.
6. Add options where useful. Do not require every command to implement JSON,
   plain, quiet, debug, dry-run, or no-input when these have no meaningful role.
7. Preserve existing grouped invocations and the existing dashed backlight and
   screenshot commands. Avoid gratuitous renaming, aliases, and deprecation
   infrastructure. Prefer additive changes and explain necessary incompatibilities.
8. Keep arbitrary Git arguments intact. Apply Agentoo conventions to its own
   Git operations without intercepting the underlying Git interface incorrectly.
9. Checkpoint is the deliberate language and parsing exception. Its recovery
   implementation must run without Python, shared Python helpers, or Bash.
   POSIX `sh` does not imply that required filesystem utilities are universally
   available: document and check the actual rescue dependencies.
10. Do not add an `AGENTS.md`. The user explicitly deferred project-wide agent
    instructions. Do not substitute automatic agent work or deployment for review.

## 2. Intended structure

```text
usr/local/bin/
    agentoo                  Python dispatcher
    agentoo-power            Python command
    agentoo-fonts            Python command
    agentoo-permissions      Python command
    agentoo-backlight        Python command
    agentoo-screenshot       Python command
    agentoo-git              Python command
    agentoo-secrets          Python command
    agentoo-checkpoint       Minimal sh launcher for recovery implementation

usr/local/share/agentoo/
    cli.py                   Authoritative concise policy and small shared helpers
    ...                      Existing data and necessary internal helpers

boot/agentoo/
    checkpoint.sh            Self-contained POSIX sh implementation
```

Choose one simple, explicit mechanism for command scripts to import the shared
helper. Ensure it works from the installed layout and supports isolated checkout
verification. Do not add a packaging framework just to solve imports.

`agentoo power ...` and `agentoo-power ...` must have equivalent behavior,
including validation, privilege handling, and exit status. Help may identify the
invocation naturally. A Python dispatcher is unavailable without Python: rescue
instructions must name direct `agentoo-checkpoint` or `sh /boot/agentoo/checkpoint.sh`.

## 3. Durable alignment policy

Place the complete concise mandatory policy in the shared CLI module's opening
docstring/comment. Put a prominent pointer and dispatch-specific rules in the
dispatcher. Keep important exceptions beside their implementation, especially
checkpoint's rescue boundary. Do not duplicate the full policy in every script
or require a command-contract template. Separate documentation may explain
examples and rationale; keep mandatory rules authoritative in one place.

1. Use readable GNU-style long options, established short aliases, `--help`,
   `--version` where appropriate, and `--` to separate options from operands.
2. Keep intended results on stdout; plans, progress, warnings, and operational
   summaries belong on stderr. Help requested explicitly goes to stdout.
3. Provide documented machine output and exit semantics for reporting commands
   that need scripting. Treat those formats as stable interfaces.
4. Make interaction optional. On commands supporting it, `--no-input` prohibits
   prompts, including privilege and authentication prompts. Missing input or
   authorization must fail clearly rather than hang.
5. Validate public input before privilege escalation or side effects. Help must
   succeed without either, including at nested command levels.
6. Keep names and argument behavior consistent. Support conventional long-option
   value forms and practical order independence; explicitly document boundaries
   for forwarded commands. Disable implicit option abbreviations.
7. Respect XDG locations, redirection, terminal capabilities, and `NO_COLOR` where
   applicable. Do not add color or configuration machinery merely for compliance.
8. Prefer additive changes; document deliberate exceptions and provide a clear
   migration path for necessary incompatible changes.
9. Adding command surface requires updating its implementation, help/completion,
   relevant policy comments, and verification together. Tests do not replace
   implementation guidance or prove undeclared behavior absent.

## 4. Audit findings and required improvements

The initial audit inspected the dispatcher, all eight command families,
completion, and relevant tests. Harmless probes used a temporary launcher with
sudo blocked. All eight existing `test_cli.py` tests passed; passing those tests
did not establish the behavior below. Reconfirm findings against the current
revision before changing code.

### R1 — Highest: make help safe and consistent

Reproduced at audit time:

- `agentoo backlight up --help` interpreted `--help` as a controller and failed.
- `agentoo screenshot region --help` exited 2 with usage rather than successful help.
- `agentoo secrets install --profile FILE --user graham ssh --help` reached sudo.
- `agentoo git enable-write --help` reached sudo.
- `agentoo help fonts doctor` was rejected because help accepted one level only.

Make help work at every command depth and practical argument position before
any privileges or action. Specifically distinguish Agentoo-owned Git operations
from arguments forwarded to Git. Never inspect beyond an explicit argument
boundary as though forwarded data were Agentoo options.

### R2 — Highest: eliminate parser disagreement

Shared Python validation accepted these forms; shell execution rejected them:

```sh
agentoo checkpoint list --device=/dev/example
agentoo checkpoint create --efi-mount /boot demo
agentoo secrets install --profile=/tmp/example --user=graham ssh
```

Checkpoint required its name immediately after the action. Secrets stopped
option parsing at the first category. Shell parsers did not support the equals
forms. Argparse's implicit abbreviations introduced another potential mismatch.

Make one parser authoritative for each normal command and remove duplicate
prevalidation. Keep checkpoint's sh parser authoritative, with focused parity
checks for supported syntax, help, and its small completion description.

### R3 — High: provide optional interaction and automation

Checkpoint create/restore always confirmed through `/dev/tty`. Secrets always
read confirmation and invoked interactive Proton login. Sudo could prompt too.

Implement useful noninteractive paths and explicit confirmation for automation.
Consider `--confirm CHECKPOINT_NAME` for restoration rather than a generic yes
flag. Document a viable unattended authentication path before claiming secrets
is automatable. Do not solve authentication by putting secrets in argument values
or environment variables. Without interactive stdin, fail with the required
input/authorization instructions rather than silently opening `/dev/tty`.

### R4 — High: separate results from operational messaging

Checkpoint plans, tool chatter, verification messages, secret installation
notices, font save/undo/reload messages, and permission repair summaries were
mixed into stdout. Route operational messaging to stderr. Preserve permission
check findings on stdout as its intended result. Consider returning only the
created checkpoint name on stdout. Preserve screenshot's useful saved-path output.

### R5 — Medium: add useful stable machine output

`fonts doctor --json` already exists. Add JSON for power, permission checks,
checkpoint list, and checkpoint inspect. Use documented units, numeric values,
and distinct unavailable values; emit one valid document without chatter.
Define exit behavior for valid reports that detect problems or contain partial
information. Prioritize useful JSON over blanket plain-mode support.

### R6 — Medium: improve help and identification

Root help repeated command names and extensive syntax while backlight/screenshot
help was sparse. Checkpoint leaf help showed every operation. Root `--version`
failed, general documentation/support links were missing, examples were uneven,
and typo suggestions were absent.

Give bare `agentoo` concise grouped commands and a few examples; provide complete
leaf options, defaults, consequences, and examples. Add useful version/revision
identification and documentation links. Suggestions may advise but must not
silently execute corrected commands. Prioritize clarity over formatting machinery.

### R7 — Medium: improve progress, cancellation, and recovery

Checkpoint usage scans, hashing, archives, verification, and sync could run with
little phase feedback. Font external calls and secret logout cleanup lacked
timeouts; the Git deployment lock could wait silently. Existing cleanup handlers
are valuable, but restoration explicitly had no transaction journal.

Add stderr phase/wait feedback, suitable bounds on external-service calls and
cleanup, and immediate interruption feedback. Do not arbitrarily time out valid
long filesystem operations or user-controlled previews. Explain which restore
components completed and how to recover after interruption. Investigate and
document actual recovery behavior; do not assume rerunning is safe or introduce
a generic transaction engine merely to satisfy this card.

### R8 — Medium: expose plans and consequential side effects

Permissions check already previews much of repair. Secrets/checkpoint lacked
separate planning. System checkpoint creation deleted package caches by default;
`--clean-distfiles` also controlled binary-package caches. Font save could modify
both its fragment and `kitty.conf`, but its success output named only the fragment.

Provide meaningful planning for secrets/checkpoints, documenting any inspection
mounts or temporary state required. Reconsider default cache deletion and name
the option for all affected caches; record the compatibility decision explicitly.
Explain all configuration files changed by font selection and retain its undo
instruction. Keep consent proportional to actual consequences.

## 5. Phased implementation and review

1. **Establish policy and baseline.** Add concise implementation policy comments;
   record current invocations, forwarding boundaries, dependencies, and behavior.
   No AGENTS.md, mandatory metadata schema, or framework scaffolding.
2. **Restructure dispatch and parsing.** Establish the executable layout and small
   shared helper. Move existing Python commands first, then convert shell commands
   individually. Remove duplicate argument validation. Verify grouped/direct
   equivalence and preserve compatibility throughout.
3. **Fix help and syntax (R1, R2, R6).** Make help side-effect-free, support nested
   help and conventional argument forms, align completion, add identification,
   and improve the root/leaf documentation.
4. **Make operations predictable (R3, R4, R8).** Implement noninteractive behavior,
   confirmation and authentication paths, stream separation, meaningful planning,
   and clear side-effect/default policies.
5. **Add machine interfaces (R5).** Implement useful JSON reports and document
   format/exit contracts. Add other output modes only when justified.
6. **Improve operational feedback (R7).** Address progress, lock waits, timeouts,
   interruption, and recovery information using command-specific solutions.
7. **Finish verification and documentation.** Exercise both invocation forms,
   update user/recovery documentation and completion, and record installed-system
   checks separately from isolated checks before closing the card.

Suggested migration order: power, fonts, permissions, backlight/screenshot, Git,
then secrets. Checkpoint changes form a separate reviewable unit throughout.
These phases organize dependencies, not seven mandatory large commits: fix local
behavior gaps alongside migrations when that makes changes easier to review.

## 6. Preserve existing strengths

- Explicit dispatch with no unknown-command fallback.
- Dynamic read-only Zsh completion without executing its output as shell code.
- Python parsers shared by execution and completion.
- Screenshot private unique files, path output, and cancellation/failure cleanup.
- Font JSON evidence, isolated previews, atomic writes, concurrent-edit checks,
  and printed undo instructions.
- Checkpoint preflight validation, locking, completeness markers, and home
  preservation by default during restore.
- Secret-manager integration, isolated temporary sessions, and credential cleanup.
- Git deployment permission repair and compositor state restoration.

Do not add cosmetic color, rename `power show-all`, introduce extension discovery,
or rewrite as a single binary just to make the suite appear more uniform.

## 7. Acceptance and handoff

- [ ] Python normal-command structure and independently runnable executables work;
  checkpoint remains directly usable under sh without Python/Bash.
- [ ] R1–R8 each have implementation and validation notes, or an explicit reviewed
  scope decision explaining any remaining work.
- [ ] Help at every supported depth/position is successful and cannot escalate or
  perform an operation; tests include the reproduced failures above.
- [ ] Parsing, help, and completion agree; equals forms, ordering, `--`, unknown
  options, and conflicting/repeated flags have defined behavior where relevant.
- [ ] Direct and grouped calls preserve arguments and agree on effects/status.
- [ ] Relevant operations support noninteractive use or clearly report what is
  missing, without prompting; test privilege and authentication paths too.
- [ ] Results and operational messages are separated; reporting JSON is parseable
  and documented, including unavailable/partial/problem outcomes.
- [ ] Consequential defaults and dry-run/plan limits are documented and tested.
- [ ] Cancellation/failure checks cover cleanup and recovery claims without
  destructive experiments on the live system.
- [ ] Registry-discovered baseline help checks cover registered commands; focused
  tests cover actual behavior. No claim that generic tests discover all new surface.
- [ ] Existing completion, desktop, Git guard, permissions, and checkpoint guarantees
  remain intact; update permission policy and callers if relocation requires it.
- [ ] Docs name direct rescue invocations and actual required tools; installed and
  hardware validation still pending is identified explicitly.

For work across future agents/sessions, append a short dated handoff noting the
phase and commands completed, files changed, checks and results, unresolved
decisions, and the next concrete step. Update existing checkboxes rather than
duplicating the plan. Keep partial work Open; distinguish implementation, isolated
verification, deployment, and operator-confirmed behavior. Independent reviewers
should assess both observable contracts and whether the change introduced
unnecessary abstraction, dependencies, duplication, or ceremony.
