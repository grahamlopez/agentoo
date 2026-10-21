-- Hyprland 0.56.2 can retain a swaybg layer's old global position when an
-- auto-positioned output moves after another output is disabled. Observed:
-- closing thinktop's lid moved DP-4 from x=1920 to x=0, but its 3840-wide
-- wallpaper layer stayed at x=1920, leaving the left half of the monitor bare.
-- Windows were positioned correctly. Recreating the managed swaybg client
-- repaired the layer. Refresh only after actual output geometry changes,
-- regardless of whether they came from the lid handler, hotplug or user rules.
--
-- Evidence captured on 2026-10-20, Hyprland 0.56.2, commit
-- efb50993780079460b0cbed1363e2166a2de1d9f, with swaybg and a Dell U5226KW:
--   hyprctl monitors -j: DP-4 x=0, y=0, width=3840, height=2160, scale=1.
--   hyprctl layers -j: DP-4/background namespace="wallpaper", x=1920, y=0,
--     w=3840, h=2160. The disabled eDP-1 panel was 3840 pixels at scale=2,
--     explaining the stale 1920-logical-pixel offset. Fullscreen Kitty fit.
--   After `agentoo desktop wallpaper restore`, the wallpaper layer was x=0,
--     y=0, w=3840, h=2160 and covered the external output correctly.
-- The symptom was reported during both custom and distribution kernel tests.
-- No exact upstream issue was found. This is evidence of a compositor layer
-- placement defect, not proof of a particular faulty code path. In v0.56.2,
-- CMonitor::moveTo changes monitor position and moves floating windows but
-- does not update layer surfaces in that function. Source for comparison:
-- https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/output/Monitor.cpp#L1572-L1590
-- MonitorLayoutController::arrange calls the position controller, updates XDG
-- outputs, then emits layoutChanged; that event is what we debounce below:
-- https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/state/MonitorLayoutController.cpp
--
-- To check whether a future Hyprland release still needs this workaround:
-- 1. Record `hyprctl version`. In agentoo.lua, temporarily comment out the
--    require for this file. Do this in the actual config/include being loaded,
--    then run `hyprctl reload` so this handler is no longer registered.
-- 2. With the lid open, connect the external monitor. Run
--    `agentoo desktop wallpaper restore` ONCE to establish a correctly placed
--    client before testing. Confirm both outputs are active and DP-4 starts
--    to the right of eDP-1; an output already fixed at x=0 won't test this bug.
-- 3. Capture `hyprctl monitors -j` and `hyprctl layers -j`, close the lid, and
--    capture both again. Do not restore/restart swaybg between these captures:
--    doing so masks the defect. Check that the surviving monitor moved and
--    that its wallpaper layer moved by the same amount and covers it fully.
-- 4. Repeat lid open/close, unplug/replug, and any supported scale/layout
--    changes. A nonzero origin is valid: compare each layer with its own
--    monitor's position, not with an assumed desktop origin of zero.
-- 5. If the stale layer returns, re-enable the require and reload, then run
--    `agentoo desktop wallpaper restore` to repair the existing layer. Reload
--    alone intentionally preserves the client when geometry hasn't changed.
--    If repeated tests pass without this handler, remove its include, this
--    file and its geometry regression test; retain equivalent startup-only
--    wallpaper restoration. Record the tested version and physical results.
-- An upgrade, source change or passing parser/unit tests alone does not prove
-- the compositor now places existing wallpaper surfaces correctly.
local function geometry()
    local outputs = {}
    for _, monitor in ipairs(hl.get_monitors()) do
        outputs[#outputs + 1] = table.concat({ monitor.name, monitor.x, monitor.y,
            monitor.width, monitor.height, monitor.scale, monitor.transform }, ":")
    end
    table.sort(outputs) -- Enumeration order alone is not a layout change.
    return table.concat(outputs, "\n"), #outputs
end

local previous = geometry() -- Reloads preserve the existing wallpaper client.
local pending

hl.on("hyprland.start", function()
    previous = geometry()
    -- Restore is a quiet no-op if no wallpaper is selected. It replaces only
    -- this session's recorded client, preserving independently started clients.
    hl.exec_cmd("agentoo desktop wallpaper restore")
end)

hl.on("monitor.layout_changed", function()
    -- Parser-only --verify-config has no event loop in 0.56.2; avoid timers
    -- without outputs. A later layout event handles the first active output.
    if #hl.get_monitors() == 0 then return end
    if pending then pending:set_enabled(false) end
    -- Lid reconciliation can itself change the layout. Coalesce its events
    -- and let monitor placement settle before creating replacement surfaces.
    pending = hl.timer(function()
        pending = nil
        local current, count = geometry()
        if count == 0 or current == previous then return end
        previous = current
        hl.exec_cmd("agentoo desktop wallpaper restore")
    end, { timeout = 250, type = "oneshot" })
end)
