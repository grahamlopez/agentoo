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

-- Local host selector: require only the host fragment explicitly chosen here.
include_optional("/etc/agentoo/hyprland-host.lua")

-- Personal settings follow shared and host settings; this is a real local file.
local config_home = os.getenv("XDG_CONFIG_HOME")
if not config_home or config_home:sub(1, 1) ~= "/" then
    local home = assert(os.getenv("HOME"), "HOME is needed for personal overrides")
    config_home = home .. "/.config"
end
include_optional(config_home .. "/hypr/agentoo-local.lua")
