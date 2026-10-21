-- Remembered blur preferences follow authored configuration. No daemon, timer,
-- driver tweaks, or opacity changes: native focus rules select window blur.
agentoo_blur_report = nil
local function on(value) return value == true or value == 1 end
local baseline = on(hl.get_config("decoration.blur.enabled"))
local baseline_size = hl.get_config("decoration.blur.size")
local baseline_passes = hl.get_config("decoration.blur.passes")

local saved = assert(agentoo_desktop_preferences).blur or {}
local groups = { all = saved.all or {}, kitty = saved.kitty or {}, browser = saved.browser or {} }
local strength = {}
for name, value in pairs(saved.strength or {}) do strength["decoration.blur." .. name] = value end
local revision = agentoo_preferences.revision(saved)
local managed = next(groups.all) or next(groups.kitty) or next(groups.browser)

local families = require("/etc/xdg/hypr/window-classes.lua")
local classes = { all = ".*", kitty = families.kitty, browser = families.browser }
local function resolve(group, focus)
    if groups[group][focus] ~= nil then return groups[group][focus] end
    if groups.all[focus] ~= nil then return groups.all[focus] end
    return baseline
end
if managed then
    local engine = false
    -- Install all, then category rules: the last match takes precedence.
    -- Resolve omitted states against the original engine setting, rather than
    -- accidentally enabling them when another state turns the engine on.
    for _, group in ipairs({ "all", "kitty", "browser" }) do
        for _, focus in ipairs({ "focused", "unfocused" }) do
            local enabled = resolve(group, focus)
            engine = engine or enabled
            hl.window_rule({
                name = "agentoo-blur-" .. group .. "-" .. focus,
                match = { class = classes[group], focus = focus == "focused" },
                no_blur = not enabled,
            })
        end
    end
    strength["decoration.blur.enabled"] = engine
end
-- Strength alone never turns the engine on, nor changes another blur option.
if next(strength) then hl.config(strength) end

local function label(value) return value and "on" or "off" end
local loaded = {
    "format\tagentoo-blur-v2",
    "revision\t" .. revision,
    "baseline\t" .. label(baseline),
    "baseline_size\t" .. tostring(baseline_size),
    "baseline_passes\t" .. tostring(baseline_passes),
}
local options = {
    "enabled", "size", "passes", "new_optimizations", "ignore_opacity", "xray",
    "noise", "brightness", "contrast", "vibrancy", "popups", "input_methods", "special",
}
-- Loaded metadata describes the last config load; options are read at query
-- time, so diagnostics also see later runtime edits. One IPC returns both.
agentoo_blur_report = function()
    local report = table.concat(loaded, "\n")
    local function append(name, path)
        local success, value = pcall(hl.get_config, path)
        if not success or value == nil then value = "unavailable"
        elseif type(value) == "boolean" then value = label(value) end
        report = report .. "\noption." .. name .. "\t" .. tostring(value)
    end
    for _, name in ipairs(options) do append(name, "decoration.blur." .. name) end
    append("render.use_shader_blur_blend", "render.use_shader_blur_blend")
    return report
end
