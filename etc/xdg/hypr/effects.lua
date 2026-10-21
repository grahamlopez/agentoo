-- Saved global preferences follow authored defaults. Python validates values;
-- this file only translates data into native Hyprland configuration calls.
agentoo_effects_report = nil
local options = {
    corners = { radius = "decoration.rounding", power = "decoration.rounding_power" },
    gaps = { inner = "general.gaps_in", outer = "general.gaps_out" },
    borders = { width = "general.border_size", focused = "general.col.active_border", unfocused = "general.col.inactive_border" },
    animations = { enabled = "animations.enabled" },
    shadows = { enabled = "decoration.shadow.enabled", size = "decoration.shadow.range" },
    dimming = { enabled = "decoration.dim_inactive", strength = "decoration.dim_strength", modal = "decoration.dim_modal" },
}
local saved = assert(agentoo_desktop_preferences)
local function color(value)
    return (#value == 7 and "rgb(" or "rgba(") .. value:sub(2) .. ")"
end
local animation = saved.animations or {}
local parents = {
    windowsIn = "windows", windowsOut = "windows", windows = "global",
    workspacesIn = "workspaces", workspacesOut = "workspaces", workspaces = "global",
    specialWorkspaceIn = "specialWorkspace", specialWorkspaceOut = "specialWorkspace", specialWorkspace = "workspaces",
}
local function baseline(name)
    local authored = agentoo_animation_defaults or {}
    local settings = authored[name]
    if not settings then
        if parents[name] then return baseline(parents[name]) end
        -- Native Hyprland 0.56.2 global animation defaults.
        return { enabled = true, speed = 8, bezier = "default", style = "" }
    end
    if settings.enabled == false then return { enabled = false, speed = 1, bezier = "default", style = "" } end
    return settings
end
for _, name in ipairs({ "windowsIn", "windowsOut", "workspacesIn", "workspacesOut", "specialWorkspaceIn", "specialWorkspaceOut" }) do
    local windows = name:sub(1, 7) == "windows"
    local style = windows and animation.windows or (not windows and animation.workspaces or nil)
    if style or animation.duration then
        local current = baseline(name)
        local settings = {}
        for key, value in pairs(current) do settings[key] = value end
        settings.leaf = name
        if animation.duration then
            assert(not settings.spring, "Agentoo --duration requires a bezier animation curve")
            settings.speed = tonumber(animation.duration) / 100
        end
        if style then
            settings.style = style
            if windows and style == "slide" and animation.window_direction and animation.window_direction ~= "auto" then
                settings.style = style .. " " .. animation.window_direction
            elseif windows and style == "popin" and animation.window_size then
                settings.style = style .. " " .. tostring(animation.window_size) .. "%"
            elseif not windows and style:sub(1, 5) == "slide" and animation.workspace_distance then
                settings.style = style .. " " .. tostring(animation.workspace_distance) .. "%"
            end
        end
        hl.animation(settings)
    end
end
local config = {}
for group, fields in pairs(options) do
    for key, option in pairs(fields) do
        local value = (saved[group] or {})[key]
        if value and not (group == "borders" and key ~= "width") then
            if value == "on" or value == "off" then config[option] = value == "on"
            else config[option] = assert(tonumber(value)) end
            if group == "dimming" and key == "strength" then config[option] = config[option] / 100 end
        end
    end
end
-- A color-only edit retains the angle; an angle-only edit retains all colors.
local borders = saved.borders or {}
for _, focus in ipairs({ "focused", "unfocused" }) do
    local option = options.borders[focus]
    if borders[focus] or borders[focus .. "_angle"] then
        local gradient = hl.get_config(option)
        if borders[focus] then
            gradient.colors = {}
            for hex in borders[focus]:gmatch("[^,]+") do
                gradient.colors[#gradient.colors + 1] = color(hex)
            end
        end
        gradient.angle = tonumber(borders[focus .. "_angle"]) or gradient.angle
        config[option] = gradient
    end
end
local shadow = saved.shadows or {}
if shadow.color or shadow.opacity then
    -- Preserve authored alpha/RGB when only its counterpart is adjusted, even
    -- for an authored gradient. Inactive shadow rules remain native overrides.
    local gradient = hl.get_config("decoration.shadow.color")
    local colors = {}
    for _, hex in ipairs(gradient.colors) do
        local alpha = shadow.opacity and math.floor(tonumber(shadow.opacity) * 255 / 100 + 0.5) or tonumber(hex:sub(3, 4), 16)
        local rgb = shadow.color and shadow.color:sub(2) or hex:sub(5, 10)
        colors[#colors + 1] = "rgba(" .. rgb .. string.format("%02x", alpha) .. ")"
    end
    config["decoration.shadow.color"] = { colors = colors, angle = gradient.angle }
end
if shadow.offset_x or shadow.offset_y then
    local offset = hl.get_config("decoration.shadow.offset")
    config["decoration.shadow.offset"] = { tonumber(shadow.offset_x) or offset.x, tonumber(shadow.offset_y) or offset.y }
end
if next(config) then hl.config(config) end

local function display(value)
    if type(value) == "boolean" then return value and "on" or "off" end
    if type(value) ~= "table" then return tostring(value) end
    if value.colors then
        local colors = {}
        for _, hex in ipairs(value.colors) do colors[#colors + 1] = "#" .. hex:sub(5, 10) .. hex:sub(3, 4) end
        return table.concat(colors, " ") .. (#colors > 1 and (" " .. tostring(value.angle) .. "deg") or "")
    end
    if value.top then
        return string.format("%s %s %s %s px (top right bottom left)", value.top, value.right, value.bottom, value.left)
    end
    return tostring(value.x) .. ", " .. tostring(value.y)
end
agentoo_effects_report = function()
    local lines = {}
    for group, fields in pairs(options) do
        for key, option in pairs(fields) do
            local value = hl.get_config(option)
            if group == "dimming" and key == "strength" then value = tostring(value * 100) .. "%" end
            if key == "radius" or key == "width" or key == "size" then value = tostring(value) .. " px" end
            lines[#lines + 1] = group .. "." .. key .. "\t" .. display(value)
        end
    end
    for _, focus in ipairs({ "focused", "unfocused" }) do
        lines[#lines + 1] = "borders." .. focus .. "_angle\t" .. tostring(hl.get_config(options.borders[focus]).angle) .. " deg"
    end
    local gradient = hl.get_config("decoration.shadow.color")
    lines[#lines + 1] = "shadows.color\t" .. display(gradient)
    lines[#lines + 1] = "shadows.opacity\t" .. string.format("%.1f", tonumber(gradient.colors[1]:sub(3, 4), 16) * 100 / 255) .. "% (first color)"
    local offset = hl.get_config("decoration.shadow.offset")
    lines[#lines + 1] = "shadows.offset_x\t" .. tostring(offset.x) .. " px"
    lines[#lines + 1] = "shadows.offset_y\t" .. tostring(offset.y) .. " px"
    return table.concat(lines, "\n")
end
