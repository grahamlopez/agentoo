# Simplify desktop appearance state dependencies

Created: 2026-10-30
Status: Completed
Completed: 2026-10-31

Scope confirmed: all current adjustments remain required, as does saving and
restoring lightweight themes. JSON itself is not required; theme storage is a
separate design discussion. The earlier native-Lua attempt is preserved on
`desktop-lua` (available as `origin/desktop-lua` in this checkout); changing file
format alone did not provide the desired simplification.

`lib/desktop/state.py` imports feature validators while blur, transparency,
and effects import state readers back through deferred imports. The Kitty
watcher executes the transparency module through `runpy` and temporarily
changes its Python search path again on each timed read.

Give genuinely shared read-only path, state-reading, and inheritance operations
an acyclic home. Keep feature behavior with its owner and retain one validated
appearance file. Prefer ordinary imports where Kitty's environment permits;
do not introduce a general state framework or remove the watcher merely
because it spans processes.

During this work, remove redundant state-path forwarding and writer plumbing
where useful. Batch effect sections through the existing multi-section
validator rather than rebuilding all effect parsers once per section; preserve
reuse of CLI validation instead of adding a parallel schema.

Complete when the dependency direction is clear and reads remain free of
effects. Run desktop state/effects, transparency, and Lua tests, including
native Kitty reads, search-path restoration, focus inheritance, partial
imports, malformed state, reset, and write/reload rollback.

## Implementation

Shared path lookup, JSON reads, window inheritance, and parser options now live
in `lib/desktop/common.py`, which imports no feature modules. Feature modules
import these directly; `state.py` imports the features and owns the transaction.
Removed forwarding path helpers, deferred imports used to break the cycle, and
the redundant section wrapper. The CLI passes the appearance path directly;
the transaction uses the existing atomic writer without injected forwarding.
Effect sections are validated together using the existing CLI parsers.
The single-use import and merge helpers are inline in `update()`, keeping the
read, validate, merge, and apply procedure together.

The Kitty watcher now uses ordinary imports during one temporary search-path
adjustment at load time. Timed reads need neither `runpy` nor further path
changes, and do not load the state writer or unrelated feature modules.

Existing JSON, partial theme imports, category inheritance, conflict policy,
locking, private writes, and exact-byte rollback remain in place. Theme-storage
redesign and [conflict ownership](../Backlog/033-desktop-conflict-ownership.md)
remain separate work.

## Validation

All 78 focused Python tests passed: desktop state, effects, transparency, blur,
shared policy, desktop commands, CLI, and completion. No optional-tool skips
were reported; native Kitty and Hyprland parser checks ran. The Kitty test also
checks repeated reads after a file update, restored search paths, and absence
of the writer and unrelated features from its imports.

Both Hyprland transparency and blur Lua regression scripts passed.
`git diff --check` passed. No live desktop settings were changed; the full
repository suite was not rerun.

After the final inlining cleanup, all 13 desktop-state tests passed again,
including partial imports and exact-byte rollback; `git diff --check` passed.
