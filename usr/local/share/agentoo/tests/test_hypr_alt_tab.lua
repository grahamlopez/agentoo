-- Run with: lua usr/local/share/agentoo/tests/test_hypr_alt_tab.lua
local source = arg[1] or "etc/xdg/hypr/alt-tab.lua"
local regular, dropdown, other = {}, { name = "special:terminal" }, {}
local monitor = { active_workspace = regular, active_special_workspace = dropdown }
local windows, active, events, bindings = {}, nil, {}, {}
local function window(id, workspace)
    local w = { stable_id = id, workspace = workspace, monitor = monitor,
        mapped = true, hidden = false, accepts_input = true, focus_history_id = id - 1 }
    windows[#windows + 1] = w
    return w
end
local a, b, c = window(1, regular), window(2, regular), window(3, dropdown)
local excluded = window(4, other)
active = a
hl = {
    get_windows = function() return windows end,
    get_active_window = function() return active end,
    get_active_monitor = function() return monitor end,
    on = function(name, callback) events[name] = callback end,
    bind = function(name, callback) bindings[name] = callback end,
    dispatch = function(callback) callback() end,
    dsp = {
        focus = function(args) return function()
            active = args.window
            if events['window.active'] then events['window.active'](active) end
        end end,
        window = { bring_to_top = function() return function() end end },
    },
}
dofile(source)
local function focus(w) active = w; events['window.active'](w) end
local function tab(reverse) bindings[reverse and 'ALT + SHIFT + TAB' or 'ALT + TAB']() end
local function release() events['input.keyboard.key'](64, 0, 0) end
-- A, B, C focus history: A -> C -> B, newest first.
focus(b); focus(c); focus(a)
tab(); assert(active == c, 'first Tab selects previous window including dropdown')
release(); tab(); assert(active == a, 'a fresh gesture bounces to origin')
release()
-- Repeated Tab keeps the original order despite focus events.
tab(); assert(active == c)
tab(); assert(active == b, 'second Tab reaches third MRU window')
tab(true); assert(active == c, 'Shift+Tab reverses within frozen order')
release()
-- Both Alt keys must be released before committing.
events['input.keyboard.key'](64, 0, 1)
events['input.keyboard.key'](108, 0, 1)
tab(); assert(active == a)
events['input.keyboard.key'](64, 0, 0)
tab(); assert(active == b, 'right Alt keeps gesture alive')
events['input.keyboard.key'](108, 0, 0)
-- A hidden dropdown is excluded without being opened.
monitor.active_special_workspace = nil
focus(a); tab(); assert(active == b, 'hidden dropdown excluded')
release()
-- Closed windows in an existing snapshot are skipped.
monitor.active_special_workspace = dropdown
focus(b); focus(c); focus(a)
tab(); assert(active == c)
b.mapped = false; events['window.close'](b)
tab(); assert(active == a, 'closed candidate skipped')
release()
-- Empty candidate list is harmless.
a.mapped = false; c.mapped = false
tab(); release()
print('alt-tab: all tests passed')
