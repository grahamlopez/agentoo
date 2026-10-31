# Investigate reducing the duplicated native animation model

Created: 2026-10-31
Status: Backlog
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
