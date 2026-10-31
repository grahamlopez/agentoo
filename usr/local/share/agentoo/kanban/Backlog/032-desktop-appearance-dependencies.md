# Simplify desktop appearance state dependencies

Created: 2026-10-30
Status: Backlog

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

## Handoff for the next context, 2026-10-31

Resume with this card after reviewing the working tree. The current HEAD is
`a295512` (external-monitor cleanup). The uncommitted batch contains power and
terminal-color cleanup, their tests, a pCloud comment clarification, this card,
and card 035's move to Completed. Do not discard or repeat that work.

Power's brief formatter and the color chart are now inline. Power reuses one
current measurement and has explicit energy/charge health calculations. The
review found no additional issues in that diff. All 30 relevant tests passed
(8 power, 5 color, 16 CLI, 1 completion). Output comparisons against HEAD passed
for power's brief/detailed/JSON reports on fixed measurements and for colors at
widths 9, 20, 40, and 80. The full repository suite was not rerun for this batch.

The command review and operator scope decisions are complete:

- Preserve Git/repos and pCloud scope, including manually launched pCloud.
  Card [035](../Completed/035-pcloud-process-scope.md) records that decision.
- Preserve font diagnostics, Firefox previews, native Kitty selection, the
  custom adjustment preview, and rendering traces; preserve all three secret
  methods (field, template, GitHub credentials).
- External control supports only the Dell U5226KW; retain laptop backlights
  across target hosts. Leave screenshot code in its current form.
- Preserve minimal initramfs and genkernel for custom builds. Distribution
  kernels use native upstream mechanisms without an Agentoo management layer.

The next bounded implementation is this dependency cleanup, keeping the
existing JSON format and theme/import behavior. Inspect actual consumers before
choosing where shared read-only operations belong; do not add a framework.
Preserve native Kitty reads and its Python search-path invariant. Validate
affected Python and Lua tests, noting any optional native-tool skips.
Theme-storage redesign and card [033](033-desktop-conflict-ownership.md)'s
conflict-policy changes are separate tasks. Installer work in
[030](030-installer-readable-procedures.md) follows the command-focused work.
