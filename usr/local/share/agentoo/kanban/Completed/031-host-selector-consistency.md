# Make Python host-selector parsing consistent

Created: 2026-10-30
Status: Completed
Completed: 2026-10-31

The same `/etc/agentoo/target-host` assignment is parsed separately by
`lib/kernel_host.py`, `lib/kitty/host_config.py`, and `lib/desktop/common.py`.
Kernel parsing rejects spaces around `=` that the other readers accept;
desktop conflict scanning silently ignores malformed selectors while Kitty
and kernel operations report them.

Establish the accepted assignment syntax, then reuse a small Python parser
rather than maintaining parallel definitions. Preserve each caller's explicit
policy for absent selectors and absent host profiles. Read the assignment as
data, never execute it. Keep the Lua consumer native; do not introduce a
cross-language loader framework.

Complete when consumers agree on syntax and malformed input, with focused
checks for canonical assignments, whitespace, and missing/invalid files.
Run the affected kernel, Kitty, and desktop tests. Treat accepted-syntax changes
as behavior changes rather than incidental cleanup.

## Implementation

`lib/host_selection.py` owns the Python parser and host-name syntax. Kernel,
Kitty, and desktop conflict inspection use it directly. The native Lua reader
uses the same accepted syntax without invoking Python.

The documented Portage-compatible assignment remains authoritative: a single
double-quoted value, no whitespace around `=`, and an ASCII letter/digit
followed by letters, digits, underscores, or hyphens. Surrounding whitespace
and blank lines are allowed. Spaces around `=` and names beginning with `_`
or `-` are now rejected consistently, rather than accepted by some readers
and rejected by others. No executable shell input is accepted.

Malformed selectors now fail desktop conflict inspection instead of silently
omitting the host fragment. Missing selectors or host fragments still leave
Kitty/Hyprland defaults intact. Kernel configuration can select an explicit
host without the selector; absent kernel profiles still fail.

## Validation

Focused kernel, firmware, desktop, and transparency checks passed, including
native Kitty state reads. Shared-selector tests exercise all Python consumers,
missing selectors/profiles, malformed contents, surrounding whitespace, and
the real Lua entry file with external modules intercepted. No desktop settings
or live host selectors were changed.

The complete repository runner passed all 314 Python tests and all five Lua
regression scripts, with no skips. It ran outside the sandbox because the
repository tests need a disposable local SSH-agent socket; no network fetch or
live target operation was needed. `git diff --check` passed.
