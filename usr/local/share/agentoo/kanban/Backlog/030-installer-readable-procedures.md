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

## Handoff at the command/installer boundary, 2026-10-31

The user agreed to begin this bounded installer pilot after context compaction.
No installer changes have started. Read AGENTS.md and check the current work
tree before proceeding; it was clean at implementation commit `58b13a8`.

The initial command review pass is complete. A subsequent critical review found
further non-installer issues, preserved in backlog cards
[036](036-kernel-installed-module-consistency.md) through
[044](044-retire-inactive-configuration-and-fallbacks.md). Those findings supersede
the earlier assessment that no further command work was apparent.

Commits simplified fonts, secrets, permissions,
kernel procedures, and desktop dependencies; fixed Git's SSH push transition;
corrected command guidance; and completed cards 031–035. All previously confirmed
command features remain required. Screenshot implementation remains deliberately
unchanged. Custom kernels retain minimal/genkernel/supplied initramfs support;
distribution kernels use upstream Gentoo mechanisms.

The latest change replaces desktop conflict scans with observation of executed
native Lua rule declarations. Card 033 records the design and limitations.
The full runner passed 318 Python tests and five Lua scripts without skips;
after final scoped-reset and tail-call coverage, all 18 focused state/conflict
tests passed. No live desktop reload, hardware write, or target operation ran.

Next, inspect `usr/local/share/agentoo/installer/gentoo-install.sh`, especially
`system_update_chroot`, `install_emerge`, `install_system_update`, phase selection,
and verbose/dry-run behavior. Use the real execution path as the manual reference;
preserve teaching content and explain RAM/disk build policy at its point of use.
Avoid a recipe-generation framework or a broad installer rewrite. Deduplicate
the phase catalog where appropriate. Preserve confirmations, privilege boundaries,
and storage safeguards. Validate with disposable installer tests, including
default/explicit phases and RAM/disk choices. Review this first phase before
extending the approach to others.
