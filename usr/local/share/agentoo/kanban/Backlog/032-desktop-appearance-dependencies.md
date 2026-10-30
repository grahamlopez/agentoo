# Simplify desktop appearance state dependencies

Created: 2026-10-30
Status: Backlog

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
