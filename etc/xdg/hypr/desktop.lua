-- Apply the one user-owned appearance table after all configured defaults.
-- Lua reads and validates it in-process; config loads never launch Python.
agentoo_preferences = require("/usr/local/share/agentoo/lib/desktop/preferences.lua")
agentoo_desktop_preferences = agentoo_preferences.load(agentoo_preferences.path(), nil, false, true)
local conflict = agentoo_authored_rule_conflicts or {}
local transparency = agentoo_desktop_preferences.transparency or {}
local blur = agentoo_desktop_preferences.blur or {}
if next(transparency) then
    assert(not (conflict.opacity or conflict.opaque or conflict.force_rgbx), "Conflicting authored transparency rules")
end
if next(blur.all or {}) or next(blur.kitty or {}) or next(blur.browser or {}) then
    assert(not (conflict.no_blur or conflict.noblur or conflict.opaque or conflict.force_rgbx), "Conflicting authored blur rules")
end
require("/etc/xdg/hypr/transparency.lua")
require("/etc/xdg/hypr/blur.lua")
require("/etc/xdg/hypr/effects.lua")
