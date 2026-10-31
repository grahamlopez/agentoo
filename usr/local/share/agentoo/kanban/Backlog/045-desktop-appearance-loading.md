# Investigate consolidating desktop appearance loading and transport

Created: 2026-10-31
Status: Backlog
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
