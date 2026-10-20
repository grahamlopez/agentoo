-- Hyprland discovers this system fallback without a user entry file.
-- require() tracks included files for reload in the selected release.
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

-- Reuse the installer-managed host selection; no second selector is needed.
-- Parse its documented assignment as data, never execute shell contents.
local selector = "/etc/agentoo/target-host"
local file, message, code = io.open(selector, "r")
if file then
    local contents = file:read("*a")
    file:close()
    local host = contents:match('^%s*GENTOO_TARGET_HOST%s*=%s*"([%w_-]+)"%s*$')
    assert(host, selector .. ': expected GENTOO_TARGET_HOST="name"')
    include_optional("/etc/xdg/hypr/hosts/" .. host .. ".lua")
elseif code ~= 2 then
    error(message)
end

-- Personal settings follow shared and host settings; this is a real local file.
local config_home = os.getenv("XDG_CONFIG_HOME")
if not config_home or config_home:sub(1, 1) ~= "/" then
    local home = assert(os.getenv("HOME"), "HOME is needed for personal overrides")
    config_home = home .. "/.config"
end
include_optional(config_home .. "/hypr/agentoo-local.lua")

-- Keep closed panels disabled before reload applies monitor rules, including
-- host/personal rules. Do not briefly enable them during appearance changes.
require("/etc/xdg/hypr/lid.lua")

-- Apply remembered appearance overrides after authored defaults. Reloading with
-- no saved overrides exposes those defaults again, including personal rules.
require("/etc/xdg/hypr/transparency.lua")
require("/etc/xdg/hypr/blur.lua")
require("/etc/xdg/hypr/effects.lua")
