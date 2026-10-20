# agentoo

An opinionated Gentoo distribution. See the
[project structure and configuration philosophy](usr/local/share/agentoo/docs/README.md)
and [development board](usr/local/share/agentoo/kanban/README.md).

Use `agentoo --help` for the unified CLI: Git, checkpoints, managed permissions,
secrets, display backlight, screenshots, desktop wallpaper, power status, and [font diagnostics and selection](usr/local/share/agentoo/docs/fonts.md).

Each command also has an independently runnable executable: `agentoo power`
and `agentoo-power` use the same implementation and arguments. Normal commands
use Python's standard library; the dispatcher only routes to fixed executable
paths. `agentoo help fonts doctor` shows nested help, and `agentoo --version`
reports the repository revision when readable.

The concise command policy lives in
[`usr/local/share/agentoo/cli.py`](usr/local/share/agentoo/cli.py).
Command scripts own their parsing, help, privileges, and output. Shared helpers
stay small; no plugin discovery or command framework is required.
Checkpoint is the recovery exception: invoke `agentoo-checkpoint` directly or
`sh /boot/agentoo/checkpoint.sh` without Python. Its filesystem utilities must
still be available; see its help and recovery documentation.

Zsh Tab completion covers commands, subcommands, options, and argument values.
Managed shells load it automatically in new sessions after deployment. To enable
it in an existing shell (or try it from a checkout), run:

```zsh
fpath=(/path/to/agentoo/usr/local/share/agentoo/zsh $fpath)
autoload -Uz compinit
compinit
compdef _agentoo agentoo
```

For a deployed system, use `/usr/local/share/agentoo/zsh` instead. The checkout
command enables completion for whichever `agentoo` is on your `PATH`.
Zsh asks `agentoo __complete` for suggestions. Python command options come from
the same argument parsers used to run those commands. Checkpoint keeps its
authoritative sh parser and a small completion description checked for parity;
completion never validates and forwards an operation to a second parser.
Font suites, installed families, backlight
controllers, and secret profile categories are read dynamically.
Completion lists use separate Commands, Options, and Values sections, with one
entry per row and aligned descriptions. Options display argument placeholders
like `--font FONT`; completion inserts only the option itself. Entries follow
the argument definitions' order, and long descriptions are shortened to fit.
The current command's usage appears above the sections, generated from its help
parser and joined into one logical line (which the terminal may wrap).
`agentoo git` delegates to zsh's Git completion using the system repository.
Checkpoint names must be entered explicitly; completion does not mount storage or
request privileges. When changing subcommands or options, update the relevant
argument parser; the zsh file needs no corresponding command or option edits. Run
`python3 -m unittest discover -s usr/local/share/agentoo/tests -p test_completion.py`.

The internal completion protocol accepts a one-based current argument index,
followed by the arguments after `agentoo`, including an empty current argument:
`agentoo __complete 3 fonts doctor --fo`. Output is tab-separated data containing
command, option, or value records (value, description, optional display label),
or requests for shell file, directory, user,
or Git completion. The shell never evaluates that output as code.

For missing glyphs, codepoints, Braille, Greek, Nerd icons, emoji, or font
rendering issues, start with `agentoo fonts doctor --text 'problem text' --json`.
See the [agent font diagnostic workflow](usr/local/share/agentoo/docs/fonts.md#agent-diagnostic-workflow)
for interpreting coverage, matching, and rendering evidence.

Operations request sudo only when needed; help and desktop utilities run as the
current user. Arbitrary Git commands also run as the current user: use explicit
`sudo agentoo git ...` for protected system repository writes. Git may require
root even for reads that traverse protected files or access its database.
Secrets confirm selected file replacements before Proton login. Use
`agentoo secrets install --profile FILE --user USER CATEGORY --dry-run` to inspect
the plan without fetching secrets or replacing files. Installation requires
interactive Proton authentication in an invocation-owned temporary session.
`--no-input` supports planning and rejects installation before privilege requests
or authentication. See the [secrets workflow](usr/local/share/agentoo/secrets/README.md).

`agentoo power` prints a brief status such as `97% | 4.8 W | ~18h 26m`.
Charging/full batteries show their status in place of discharge runtime.
Multiple batteries get a labeled line each.

`agentoo power show-all` reports each battery's charge, charging/discharging wattage,
estimated discharge runtime, and health, plus CPU governor, energy preference,
and platform profile where available. Battery wattage is not wall power;
unavailable kernel measurements are labeled explicitly.

`agentoo power --json` reports batteries, power sources, CPU policies, and platform
profile. Rates are watts, runtime is hours, capacity/health are percentages, and
unavailable measurements are `null`. Missing hardware is a successful partial
report. `agentoo permissions check --json` reports mismatches and path errors;
exit 0 means compliant, 1 means mismatches/errors, and 2 means invalid arguments.
Operational messages go to stderr. Use each command's help for its exact contract.

Checkpoint capture **clears distfile and binary-package caches by default when
capturing system**. Use `--no-clean-package-caches` to preserve them. Captures
without system preserve caches. Create/restore support `--dry-run`;
unattended capture requires `--yes --no-input`, and unattended restoration
requires `--confirm NAME --no-input`. List/inspect retain human output. Inspection
mounts suppress Btrfs log replay and require kernel 5.9 or newer. See
[checkpoint planning and recovery](usr/local/share/agentoo/docs/checkpoints.md)
for temporary inspection effects and the exact recovery boundaries.

The existing `agentoo-backlight` and `agentoo-screenshot` names remain supported.
Screenshot files go to `~/Downloads/Screenshots`.
