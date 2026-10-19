-- Run with: lua usr/local/share/agentoo/tests/test_hypr_lid.lua [lid.lua path]
local source = arg[1] or "etc/xdg/hypr/lid.lua"
local function session(state, monitors)
    local env = { binds = {}, events = {}, timers = {}, changes = {}, reloads = 0, listeners = 0 }
    env.state = state
    env.monitors = monitors
    local api = {}
    function api.bind(key, callback, options)
        assert(options.locked)
        env.binds[key] = callback
    end
    function api.on(event, callback)
        local previous = env.events[event]
        env.events[event] = function()
            if previous then previous() end
            callback()
        end
    end
    function api.get_monitors() return env.monitors end
    function api.monitor(spec)
        assert(spec.disabled == true)
        env.changes[#env.changes + 1] = spec.output
        for index = #env.monitors, 1, -1 do
            if env.monitors[index].name == spec.output then
                table.remove(env.monitors, index)
            end
        end
        env.events["monitor.removed"]()
    end
    function api.exec_cmd(command)
        if command == "python3 /usr/local/share/agentoo/hypr/lid-resume.py" then
            env.listeners = env.listeners + 1
            return
        end
        assert(command == "hyprctl reload")
        env.reloads = env.reloads + 1
    end
    function api.timer(callback, options)
        assert((options.timeout == 250 or options.timeout == 1500) and options.type == "oneshot")
        local timer = { enabled = true, callback = callback }
        function timer:set_enabled(value) self.enabled = value end
        env.timers[#env.timers + 1] = timer
        return timer
    end
    local context = setmetatable({ hl = api, io = {
        popen = function()
            return { read = function() return env.state end, close = function() end }
        end,
    } }, { __index = _G })
    local chunk = assert(loadfile(source, "t", context))
    if setfenv then setfenv(chunk, context) end -- System Lua may be 5.1.
    chunk()
    function env.flush()
        -- Model the next event-loop tick, including timers queued by callbacks.
        local timers = env.timers
        env.timers = {}
        for _, timer in ipairs(timers) do
            if timer.enabled then timer.enabled = false; timer.callback() end
        end
    end
    function env.close()
        env.state = "state: closed"
        env.binds["switch:on:Lid Switch"](); env.flush()
    end
    function env.open()
        env.state = "state: open"
        env.binds["switch:off:Lid Switch"](); env.flush()
    end
    env.resume = context.agentoo_lid_resume
    return env
end
local function outputs(...)
    local result = {}
    for _, name in ipairs({ ... }) do result[#result + 1] = { name = name } end
    return result
end

-- Undocked close leaves the only output alone; suspend remains logind's job.
local undocked = session("state: open", outputs("eDP-1"))
undocked.close()
assert(#undocked.changes == 0 and undocked.reloads == 0)

-- Docked close disables only internal panels, not any external output.
local docked = session("state: open", outputs("eDP-1", "DP-4", "HDMI-A-1"))
docked.close()
assert(#docked.changes == 1 and docked.changes[1] == "eDP-1")
docked.flush() -- Our own monitor.removed event must not cause a reload loop.
assert(docked.reloads == 0 and #docked.changes == 1)
docked.open()
assert(docked.reloads == 1) -- Restore authored rules, not guessed defaults.
docked.open()
assert(docked.reloads == 1)

-- Boot/reload with an already-closed lid applies the policy.
for _, event in ipairs({ "hyprland.start", "config.reloaded" }) do
    local closed = session("state: closed", outputs("eDP-1", "DP-4"))
    closed.events[event]()
    closed.flush()
    assert(closed.changes[1] == "eDP-1")
end

-- Docking while closed and unplugging the last external display both reconcile.
local hotplug = session("state: closed", outputs("LVDS-1"))
hotplug.events["hyprland.start"](); hotplug.flush()
assert(#hotplug.changes == 0)
hotplug.monitors = outputs("LVDS-1", "DP-4")
hotplug.events["monitor.added"](); hotplug.flush()
assert(hotplug.changes[1] == "LVDS-1")
hotplug.monitors = outputs()
hotplug.events["monitor.removed"](); hotplug.flush()
assert(hotplug.reloads == 1)

-- Coalesce rapid close/open events; unknown lid state leaves displays alone.
local rapid = session("", outputs("DSI-1", "DP-4"))
rapid.events["config.reloaded"]()
rapid.binds["switch:on:Lid Switch"]()
rapid.binds["switch:off:Lid Switch"]()
rapid.flush()
assert(#rapid.changes == 0 and rapid.reloads == 0)

-- Parser-only verification has no monitor/event loop; do not create a timer.
local verify = session("state: closed", outputs())
verify.events["config.reloaded"]()
assert(#verify.timers == 0)
assert(verify.listeners == 0)

-- A lid transition missed during sleep is corrected from physical state.
local missed = session("state: open", outputs("eDP-1", "DP-4"))
missed.state = "state: closed"
missed.resume(); missed.flush()
assert(missed.changes[1] == "eDP-1")
missed.state = "state: open"
missed.resume(); missed.flush()
assert(missed.reloads == 1)

-- A dock can appear after the immediate resume pass without a switch event.
local resume = session("state: closed", outputs("eDP-1"))
resume.resume(); resume.flush()
assert(#resume.changes == 0)
resume.monitors = outputs("eDP-1", "DP-4")
resume.flush() -- Delayed resume pass queued the normal debounce.
assert(resume.changes[1] == "eDP-1")

-- An unreadable ACPI state must not override a valid close-switch event.
local unknown = session("", outputs("eDP-1", "DP-4"))
unknown.binds["switch:on:Lid Switch"](); unknown.flush()
assert(unknown.changes[1] == "eDP-1")
print("Hyprland lid policy tests passed")
