# Investigate consolidating desktop appearance loading and transport

Created: 2026-10-31
Status: Completed
Priority: Medium

The implementation review found repeated appearance-loading machinery. On each
Hyprland configuration load, [transparency.lua](../../../../../../etc/xdg/hypr/transparency.lua),
[blur.lua](../../../../../../etc/xdg/hypr/blur.lua), and
[effects.lua](../../../../../../etc/xdg/hypr/effects.lua) independently invoke
Python, read the same appearance JSON, and consume separate tab-separated
records with completion markers. Each bridge adds code to the operation a human
must trace from a CLI adjustment to native configuration calls.

Trace the current load and investigate sharing one validated appearance read per
configuration load. Compare the complete implementation with the existing path;
moving the same complexity into a generic loader is not an improvement. Preserve
JSON, all confirmed adjustments, partial imports, authored defaults, reset,
conflict checks, and failure recovery. The previous `desktop-lua` branch did not
demonstrate a simpler replacement; consult that evidence before repeating it.
Keep the native animation-model question in
[card 046](046-native-animation-model.md).

Complete when the options and native constraints are recorded and a bounded
prototype demonstrates fewer concepts and less repeated machinery, or explains
why retaining the current path is preferable. If adopting a change, remove the
superseded bridges and verify actual startup/reload translation, malformed-state
failures, and saved-change/reset behavior with disposable native checks.

## Implementation and validation

Completed 2026-10-31. One private `state.py settings` entry now reads and validates
all saved appearance sections together. It prefixes the existing concrete record
formats for transparency, blur and effects, and emits one completion marker only
after complete validation. A small `appearance.lua` module runs that helper once
and supplies the three consumers through native require() caching. The previous
three private entry points and repeated process/completion handling were removed.
Native configuration translation, conflict ownership, blur revision reports and
JSON preference semantics remain in their existing owners.

The previous desktop-lua experiment (9a916c1) introduced a new preference schema,
Lua declarative parser/serializer, and a command-side Python/Lua bridge. This
change keeps JSON and the existing validators/record formats instead. No generated
configuration, dependency, persistent cache or general loader was added.

Installed Hyprland 0.56.2's `src/config/lua/ConfigManager.cpp` clears non-standard
package.loaded entries, resets native configuration and recreates the Lua state
before evaluating a new configuration. The shared snapshot therefore lasts one
actual load; subsequent loads read the file again. A native parser test changes
the saved file between consumers, proves a single helper invocation and consistent
settings/revision within that load, then verifies fresh values on the next load
and authored defaults after clearing the file.

Focused verification passed 69 Python tests across desktop state, effects, blur,
transparency, conflict ownership, shared policy and command contracts, plus three
Lua transport/translation scripts. Coverage includes malformed JSON/values and
unknown sections producing no partial transport output; completion marker failure
and spurious ECHILD; all existing styles; authored animation preservation;
partial imports; atomic rollback; and clearing malformed sections or all state.
`git diff --check` passed. Native checks used only disposable configuration files
with `Hyprland --verify-config`; no live session was reloaded.
