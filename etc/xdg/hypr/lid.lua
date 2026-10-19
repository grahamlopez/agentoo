-- Display routing only: logind still owns undocked lid-close suspend.
-- Runtime disable rules are discarded by reload, restoring authored settings.
local function read_lid()
    local stream = io.popen("cat /proc/acpi/button/lid/*/state 2>/dev/null", "r")
    if not stream then return nil end
    local state = stream:read("*a")
    stream:close()
    if state:match("state:%s+closed") then return true end
    if state:match("state:%s+open") then return false end
    return nil -- Preserve the switch event if ACPI state is unavailable.
end

local closed = read_lid()
local disabled_by_lid = false
local pending

local function internal(name)
    return name:match("^eDP%-") or name:match("^LVDS%-") or name:match("^DSI%-")
end

local function reconcile()
    local actual = read_lid()
    if actual ~= nil then closed = actual end
    local panels = {}
    local external = false
    for _, monitor in ipairs(hl.get_monitors()) do
        if internal(monitor.name) then
            panels[#panels + 1] = monitor.name
        else
            external = true
        end
    end

    if closed and external then
        for _, name in ipairs(panels) do
            disabled_by_lid = true
            hl.monitor({ output = name, disabled = true })
        end
    elseif disabled_by_lid then
        disabled_by_lid = false
        -- Restore the fallback plus host/personal rules, rather than guessing
        -- the panel's mode, position, scaling, or color settings.
        hl.exec_cmd("hyprctl reload")
    end
end

local function schedule()
    if pending then pending:set_enabled(false) end
    -- Let hotplug/configuration processing finish before changing outputs.
    pending = hl.timer(reconcile, { timeout = 250, type = "oneshot" })
end

hl.bind("switch:on:Lid Switch", function()
    closed = true
    schedule()
end, { locked = true })
hl.bind("switch:off:Lid Switch", function()
    closed = false
    schedule()
end, { locked = true })

hl.on("hyprland.start", schedule)
hl.on("config.reloaded", function()
    -- --verify-config has no event loop: creating a timer there crashes 0.56.2.
    -- Session startup handles the initial configuration with no outputs yet.
    if #hl.get_monitors() > 0 then
        schedule()
    end
end)
hl.on("monitor.added", schedule)
hl.on("monitor.removed", schedule)
