-- MRU switching across the regular workspace and its visible terminal overlay.
-- Hyprland 0.56.2: LuaWindow.focus_history_id is zero for the newest window;
-- input.keyboard.key reports evdev keycodes + 8 (64/108 are left/right Alt).
local rank, clock = {}, 0
local session
local alt_down = {}

local function remember(window)
    if window and window.stable_id then
        clock = clock + 1
        rank[window.stable_id] = clock
    end
end

-- Preserve the compositor's existing history when this fragment is reloaded.
for _, window in ipairs(hl.get_windows()) do
    rank[window.stable_id] = -(window.focus_history_id or 0)
end
remember(hl.get_active_window())

local function finish()
    session = nil
    remember(hl.get_active_window())
end

local function eligible(window, monitor)
    if not window.mapped or window.hidden or not window.accepts_input then return false end
    if window.monitor ~= monitor then return false end
    local workspace = window.workspace
    local special = monitor.active_special_workspace
    return workspace == monitor.active_workspace
        or (special ~= nil and special.name == "special:terminal" and workspace == special)
end

local function cycle(step)
    local monitor = hl.get_active_monitor()
    if not monitor then finish(); return end
    if session and (session.monitor ~= monitor
        or session.workspace ~= monitor.active_workspace
        or session.special ~= monitor.active_special_workspace) then
        finish()
    end

    local live = {}
    for _, window in ipairs(hl.get_windows()) do
        if eligible(window, monitor) then live[window.stable_id] = window end
    end
    if not session then
        remember(hl.get_active_window())
        local order = {}
        for id in pairs(live) do order[#order + 1] = id end
        table.sort(order, function(a, b)
            local ra, rb = rank[a] or -math.huge, rank[b] or -math.huge
            if ra == rb then return a < b end
            return ra > rb
        end)
        session = {
            monitor = monitor, workspace = monitor.active_workspace,
            special = monitor.active_special_workspace, order = order, index = 1,
        }
        local current = hl.get_active_window()
        for i, id in ipairs(order) do
            if current and id == current.stable_id then session.index = i end
        end
    end

    -- Retain the snapshot order; skip windows closed, hidden or moved since then.
    for _ = 1, #session.order do
        session.index = ((session.index - 1 + step) % #session.order) + 1
        local target = live[session.order[session.index]]
        if target then
            hl.dispatch(hl.dsp.focus({ window = target }))
            hl.dispatch(hl.dsp.window.bring_to_top({ window = target }))
            return
        end
    end
    finish()
end

hl.on("window.active", function(window)
    if not session then remember(window) end
end)
hl.on("window.close", function(window)
    if window and window.stable_id then rank[window.stable_id] = nil end
end)
hl.on("input.keyboard.key", function(keycode, _, state)
    if keycode ~= 64 and keycode ~= 108 then return end
    alt_down[keycode] = state ~= 0 or nil
    if state == 0 and not next(alt_down) then finish() end
end)

hl.bind("ALT + TAB", function() cycle(1) end)
hl.bind("ALT + SHIFT + TAB", function() cycle(-1) end)
