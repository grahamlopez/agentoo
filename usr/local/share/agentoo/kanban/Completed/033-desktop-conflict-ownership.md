# Base desktop conflict handling on active configuration

Created: 2026-10-30
Status: Completed
Completed: 2026-10-31

`lib/desktop/common.py:authored_hypr_paths` scans every `.lua` and `.conf`
under the user's Hyprland directory. Blur and transparency use regex matches
from that scan to block some saves and loads. An unused configuration copy can
therefore be treated as competing policy even though Hyprland never loads it.

The requirement is to avoid competing window rules without rewriting authored
configuration. Establish explicit ownership and precedence, then narrow
blocking checks to evidence of active conflicts. Investigate available native
information before choosing a mechanism; do not build a Lua evaluator or assume
a native API completely answers the question. Account for includes from the
active personal entry file rather than merely checking that file alone.

Complete when unused files cannot block appearance changes, real competing
rules remain understandable, and full-reset recovery works. Verify inactive
copies, active includes/conflicts, and saved-state loading; run affected
Python/Lua tests and validate behavior in Hyprland.

## Native investigation and ownership

Inspected the installed Hyprland 0.56.2 API stubs, headers, CLI help, and cached
upstream source. There is no exposed complete window-rule listing to query.
The native [rule handle](https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/config/lua/objects/LuaWindowRule.cpp)
reports current enable/disable state, and the
[native declaration](https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/config/lua/bindings/LuaBindingsConfigRules.cpp)
merges repeated named rules. Use those facts rather than reconstructing Lua or
maintaining a parallel rule definition.

Saved appearance owns the window effects it installs. Enabled authored opacity,
opaque, or force_rgbx declarations compete with managed transparency; no_blur,
opaque, or force_rgbx declarations compete with managed blur, including explicit
false values. Scalar decoration defaults remain underlying configuration.
Checks establish property ownership, not whether arbitrary matchers overlap.

## Implementation

`appearance-rules.lua` observes executed `hl.window_rule` calls before shared,
host, and personal configuration loads. It keeps only native handles, relevant
ownership flags, and caller locations. This includes native requires outside
the personal tree, constructed declarations, and later runtime callbacks.
Native handles reflect disabled rules and named redeclarations. Managed rules
use the retained native setter directly, so they do not conflict with themselves.

The CLI queries the running session through one shared read-only helper.
Saved-rule loading checks the same registry directly in Lua, without spawning
an IPC query back into a compositor that is currently loading configuration.
Removed the recursive file scan, both regex scans, their forwarding helpers,
and desktop's now-unneeded host-selector reader.

Both features check the resulting saved window groups before writing. Full
reset, clearing the last managed window rule, and blur strength-only changes
remain available with competing authored rules. Editing authored files requires
a configuration reload before the CLI's active-session evidence changes. No
authored file is rewritten. The new integration needs a shared-config reload
after deployment; no old scanner or compatibility path remains.

Lua tail calls can erase caller metadata; they retain conflict detection with
an unknown callsite instead of breaking an otherwise valid native declaration.
The observation wrapper can also appear in native validation diagnostics for
malformed rule arguments. Conflict diagnostics retain authored callsites when
Lua supplies them. Rules created outside the Lua setter and arbitrary matcher
intersection are not inferred.

## Validation

The full runner passed all 318 Python tests and all five Lua regression scripts,
with no skips. Native Hyprland verification covers inactive backups/branches,
scalar defaults, actual host/personal includes outside the tree, constructed
rules, saved-state rejection, disabled handles, named merging, runtime rules,
and managed-rule exclusion. Existing tests cover malformed state, resets,
read-only Kitty behavior, and exact-byte rollback.

Final review added scoped-reset coverage and fixed the native tail-call case;
all 18 focused state/conflict tests passed afterward. `git diff --check` passed.
Tests used isolated native configuration parsing and disposable files; no live
session was reloaded and no appearance or hardware settings were changed.
