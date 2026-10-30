# Make installer source readable as an operating procedure

Created: 2026-10-30
Status: Backlog

The installer intentionally teaches humans how to reproduce its operations
manually. Preserve that goal while eliminating parallel recipes that can drift
from execution. In `installer/gentoo-install.sh`, `system_update_chroot` uses
`install_emerge`, but the verbose recipe in `install_system_update` shows plain
`emerge`, omitting the wrapper's selected build-storage policy.

Keep inputs, assumptions, native operations, review points, and verification
visible in the implementation. Explain consequential choices beside the code.
Do not simply delete the teaching material or create a recipe-generation
framework. First establish examples on simpler commands; use that experience
to choose how installer source and verbose output should complement each other.

Also define the phase catalog once: `SELECTED_PHASES` and `PHASE_ORDER` currently
repeat the same default list. Initialize the selection from the ordered catalog.

Complete when a human can follow the chosen phase manually from its source,
without a separately maintained executable recipe. Preserve runtime behavior
and approval context; review verbose/dry-run output and run installer tests,
including default and explicit phase selection.
