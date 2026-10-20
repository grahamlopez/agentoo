# agentoo

An opinionated Gentoo distribution. See the
[project structure and configuration philosophy](usr/local/share/agentoo/docs/README.md)
and [development board](usr/local/share/agentoo/kanban/README.md).

Use `agentoo --help` for the unified CLI: Git, checkpoints, managed permissions,
secrets, display backlight, screenshots, power status, and [font diagnostics and selection](usr/local/share/agentoo/docs/fonts.md).

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
Zsh asks `agentoo __complete` for suggestions. Font and power options come from
the same Python argument parsers used to run those commands. Shared parsers in
`usr/local/share/agentoo/commands/cli.py` validate the shell commands' arguments
and provide their completions. Font suites, installed families, backlight
controllers, and secret profile categories are read dynamically.
Completion lists use separate Commands, Options, and Values sections, with one
entry per row and aligned descriptions. Options display argument placeholders
like `--font FONT`; completion inserts only the option itself. Entries follow
the argument definitions' order, and long descriptions are shortened to fit.
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
Secrets confirm selected file replacements before Proton login.

`agentoo power` prints a brief status such as `97% -- 4.8 W -- ~18h 26m`.
Charging/full batteries show their status in place of discharge runtime.
Multiple batteries get a labeled line each.

`agentoo power show-all` reports each battery's charge, charging/discharging wattage,
estimated discharge runtime, and health, plus CPU governor, energy preference,
and platform profile where available. Battery wattage is not wall power;
unavailable kernel measurements are labeled explicitly.

The old `agentoo-backlight` and `agentoo-screenshot` names remain compatibility
wrappers. Screenshot files go to `~/Downloads/Screenshots`.
