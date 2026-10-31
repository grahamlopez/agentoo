# Investigate reducing the duplicated native animation model

Created: 2026-10-31
Status: Completed
Priority: Medium

Agentoo maintains part of Hyprland's animation model in several places.
[Python](../../lib/desktop/effects.py) has a parent hierarchy for resolving live
animation settings. [Lua](../../../../../../etc/xdg/hypr/effects.lua) has another
hierarchy and copied native defaults. The
[configuration entry](../../../../../../etc/xdg/hypr/hyprland.lua) temporarily wraps
`hl.animation` to remember authored definitions for saved adjustments. These
representations require coordinated maintenance when the native model changes.

Inspect the installed compositor's API and implementation before proposing a
replacement; do not assume a native getter exists. Establish which information
is available during configuration loading and which must be retained to preserve
authored settings. Seek a direct native path or a smaller justified model without
introducing an animation framework or changing the saved preference format.
Coordinate shared loading with [card 045](045-desktop-appearance-loading.md).

Preserve the confirmed style and duration controls, inheritance, enable states,
easing, compatible saved parameters, spring timing restrictions, and reset to
authored defaults. Narrowing supported features requires a separate requirements
decision.

Complete when native constraints and alternatives are documented, with a bounded
prototype proving simpler behavior or a reason to retain the existing design.
Any adopted change must remove superseded representations and have focused
native checks for inherited/authored branches, adjustments, and reset.

## Investigation result: retain the current model

Completed 2026-10-31 against installed Hyprland 0.56.2, using its local source
archive and Lua stubs. There is no native Lua getter for animation definitions or
effective branch values. The existing small representations serve different
phases and cannot yet be replaced by a simpler native path:

- During configuration loading, Lua must retain authored definitions before
  saved style/duration preferences are applied. The `hl.animation` setter requires
  a complete enabled definition (speed and bezier or spring); it cannot patch
  just style or duration while preserving omitted settings. The capture wrapper
  and small parent/default table supply those settings without saving another
  authority in appearance.json.
- During a command query or duration validation, Python needs current effective
  settings, including runtime changes after configuration loading. Native
  `hyprctl -j animations` emits internal values for each node, an overridden flag,
  and no parent/effective-value fields. Resolving unoverridden nodes therefore
  requires the parent relationships in Python. Authored Lua captures would not
  describe later native runtime changes.

Native source evidence:

- `src/config/lua/bindings/LuaBindingsConfigRules.cpp`, `hlAnimation` (lines
  390–476): complete enabled definitions, disabled-node reset, curve validation
  and native tree mutation; `hlGetConfig` (1020–1045) reads scalar/structured
  configuration options from m_configValues, not the animation tree.
- The same file's `registerConfigRuleBindings` and installed
  `/usr/share/hypr/stubs/hl.meta.lua`: animation setter and general option getter,
  with no animation getter binding.
- `src/config/shared/animation/AnimationTree.cpp`, `reset`: native parent graph
  and global defaults (enabled, speed 8, default bezier, empty style).
- `src/debug/HyprCtl.cpp`, `animationsRequest` (927–985): JSON uses internal
  enabled/speed/bezier/style values and overridden, without resolved values or
  parent identity. Native C++ tree access exists, but is not a Lua configuration
  API; introducing a compositor plugin would add substantially more machinery.

Disposable `Hyprland --verify-config` checks confirmed unknown animation keys
return nil/error through hl.get_config, no get_animation/animations function is
present, and a style-only setter fails for missing required enabled/speed fields.
No live compositor IPC, plugin, reload or desktop changes were needed.

Moving the graph into a shared file would add cross-language data loading and
transport merely to relocate nine explicit relationships. Inferring parents from
name spelling would obscure the native hierarchy. Neither improves the complete
procedure. Retain the capture and small tables, and revisit this decision if
upstream exposes effective animation getters or partial setters during loading.
The separate shared-loading improvement in card 045 removes repeated processes
without entangling these animation phases. Existing native tests continue to
cover authored/inherited branches, disabled branches, style/duration preservation
and reset; all confirmed adjustments and spring timing restrictions remain.
