-- Run with: lua usr/local/share/agentoo/tests/test_hypr_wallpaper.lua
local source = arg[1] or "etc/xdg/hypr/wallpaper.lua"
local function output(name, x, scale)
    return { name = name, x = x, y = 0, width = 3840, height = 2160,
        scale = scale or 1, transform = 0 }
end
local function session(monitors)
    local env = { monitors = monitors, events = {}, timers = {}, restores = 0 }
    local api = {}
    function api.get_monitors() return env.monitors end
    function api.on(event, callback) env.events[event] = callback end
    function api.exec_cmd(command)
        assert(command == "python3 /usr/local/share/agentoo/desktop_wallpaper.py")
        env.restores = env.restores + 1
    end
    function api.timer(callback, options)
        assert(options.timeout == 250 and options.type == "oneshot")
        local timer = { enabled = true, callback = callback }
        function timer:set_enabled(enabled) self.enabled = enabled end
        env.timers[#env.timers + 1] = timer
        return timer
    end
    local context = setmetatable({ hl = api }, { __index = _G })
    local chunk = assert(loadfile(source, "t", context))
    if setfenv then setfenv(chunk, context) end
    chunk()
    function env.layout() env.events["monitor.layout_changed"]() end
    function env.flush()
        local timers = env.timers
        env.timers = {}
        for _, timer in ipairs(timers) do
            if timer.enabled then timer.callback() end
        end
    end
    return env
end

-- A closed lid removes the 1920-logical-pixel panel and moves DP-4 to x=0.
-- Recreate wallpaper once, after coalescing intermediate layout events.
local docked = session({ output("eDP-1", 0, 2), output("DP-4", 1920) })
assert(docked.restores == 0 and #docked.timers == 0)
docked.events["hyprland.start"]()
assert(docked.restores == 1)
docked.monitors = { output("DP-4", 1920) }
docked.layout()
docked.monitors[1].x = 0
docked.layout()
assert(docked.restores == 1)
docked.flush()
assert(docked.restores == 2)

-- Unchanged layout notifications and config reloads leave the client alone.
docked.layout(); docked.flush()
assert(docked.restores == 2)
local reloaded = session(docked.monitors)
reloaded.layout(); reloaded.flush()
assert(reloaded.restores == 0)

-- Reopening the lid, reordered enumeration and scale-only changes.
docked.monitors = { output("eDP-1", 0, 2), output("DP-4", 1920) }
docked.layout(); docked.flush()
assert(docked.restores == 3)
docked.monitors = { docked.monitors[2], docked.monitors[1] }
docked.layout(); docked.flush()
assert(docked.restores == 3)
docked.monitors[1].scale = 2
docked.layout(); docked.flush()
assert(docked.restores == 4)

-- Startup events must not cause duplicate restoration from a queued timer.
local startup = session({})
startup.monitors = { output("eDP-1", 0, 2) }
startup.layout()
startup.events["hyprland.start"]()
startup.flush()
assert(startup.restores == 1)

-- Parser-only verification must not create timers; losing all outputs while a
-- timer is pending must not launch a wallpaper client with no active output.
local verify = session({})
verify.layout()
assert(#verify.timers == 0 and verify.restores == 0)
docked.monitors[1].x = 100
docked.layout()
docked.monitors = {}
docked.flush()
assert(docked.restores == 4)
print("Hyprland wallpaper geometry tests passed")
