# Make Python host-selector parsing consistent

Created: 2026-10-30
Status: Backlog

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
