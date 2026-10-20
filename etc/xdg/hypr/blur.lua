-- Remembered blur preferences follow authored configuration. No daemon, timer,
-- driver tweaks, or opacity changes: native focus rules select window blur.
agentoo_blur_report = nil
local function on(value) return value == true or value == 1 end
local baseline = on(hl.get_config("decoration.blur.enabled"))
local baseline_size = hl.get_config("decoration.blur.size")
local baseline_passes = hl.get_config("decoration.blur.passes")

local stream = assert(io.popen("python3 /usr/local/share/agentoo/desktop_blur.py rules", "r"))
local contents = stream:read("*a")
-- Hyprland can reap popen's child before pclose. Check the completion record,
-- not pclose's potentially spurious ECHILD result (also used by transparency).
stream:close()
assert(contents:sub(-4) == "end\n", "Cannot load Agentoo blur state; see session stderr")

local groups = { all = {}, kitty = {}, browser = {} }
local strength = {}
local revision
local managed = false
for line in contents:gmatch("([^\n]+)\n") do
    if line ~= "end" then
        local group, key, value = line:match("^(%a+)\t(%a+)\t([^\t]+)$")
        if group == "strength" then
            -- Python owns semantic validation and limits. Lua only checks the
            -- transport before passing validated values to the compositor.
            local number = tonumber(value)
            assert((key == "size" or key == "passes") and number)
            strength["decoration.blur." .. key] = number
        elseif groups[group] then
            assert((key == "focused" or key == "unfocused") and (value == "on" or value == "off"))
            groups[group][key] = value == "on"
            managed = true
        else
            revision = line:match("^revision\t([a-f0-9]+)$")
            assert(revision and #revision == 64, "Invalid Agentoo blur data")
        end
    end
end
assert(revision, "Missing Agentoo blur revision")

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
