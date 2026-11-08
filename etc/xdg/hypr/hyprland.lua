-- Remember authored animation calls while loading defaults and personal files.
-- The native setter requires complete definitions; appearance.json stores only
-- public preferences, so omitted animation fields are filled here on each load.
local native_animation = hl.animation
agentoo_animation_defaults = {}
hl.animation = function(settings)
    local copy = {}
    for key, value in pairs(settings) do copy[key] = value end
    agentoo_animation_defaults[settings.leaf] = copy
    return native_animation(settings)
end

-- Hyprland discovers this system fallback without a user entry file.
-- require() tracks included files for reload in the selected release.
require("/etc/xdg/hypr/appearance-rules.lua")
require("/etc/xdg/hypr/agentoo.lua")

local function include_optional(path)
    local file, message, code = io.open(path, "r")
    if file then
        file:close()
        require(path)
    elseif code ~= 2 then -- ENOENT: an absent override is expected.
        error(message)
    end
end

-- Use the same native profile selection as Portage and Agentoo's other tools.
local target = assert(io.popen("python3 /usr/local/share/agentoo/lib/host_selection.py", "r"))
local host = target:read("*a"):match("^%s*([%w][%w_-]*)%s*$")
-- Hyprland reaps children itself; pclose may report ECHILD after a successful query.
target:close()
assert(host, "could not determine the selected Agentoo host profile")
include_optional("/etc/xdg/hypr/hosts/" .. host .. ".lua")

-- Personal settings follow shared and host settings; this is a real local file.
local config_home = os.getenv("XDG_CONFIG_HOME")
if not config_home or config_home:sub(1, 1) ~= "/" then
    local home = assert(os.getenv("HOME"), "HOME is needed for personal overrides")
    config_home = home .. "/.config"
end
include_optional(config_home .. "/hypr/agentoo-local.lua")

hl.animation = native_animation

-- Keep closed panels disabled before reload applies monitor rules, including
-- host/personal rules. Do not briefly enable them during appearance changes.
require("/etc/xdg/hypr/lid.lua")

-- Apply remembered appearance overrides after authored defaults. Reloading with
-- no saved overrides exposes those defaults again, including personal rules.
require("/etc/xdg/hypr/transparency.lua")
require("/etc/xdg/hypr/blur.lua")
require("/etc/xdg/hypr/effects.lua")
