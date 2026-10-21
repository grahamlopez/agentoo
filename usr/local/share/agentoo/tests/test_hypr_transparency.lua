-- Run: lua5.4 usr/local/share/agentoo/tests/test_hypr_transparency.lua
local source = "etc/xdg/hypr/transparency.lua"
local rules = {}
local context = setmetatable({
    require = function(path)
        assert(path == "/etc/xdg/hypr/window-classes.lua")
        return dofile("etc/xdg/hypr/window-classes.lua")
    end,
    hl = { window_rule = function(rule) rules[#rules + 1] = rule end },
    agentoo_desktop_preferences = {transparency={all={focused=5},kitty={focused=5},browser={focused=0}}},
    io = {popen = function() error("Native preferences must not spawn helpers") end},
}, { __index = _G })
local chunk = assert(loadfile(source, "t", context))
if setfenv then setfenv(chunk, context) end
chunk()
assert(context.agentoo_transparency_loaded)
assert(#rules == 3)
assert(rules[1].match.class:match("^negative:"))
assert(rules[1].opacity == "0.95000000 override")
assert(rules[2].opacity == "1.00000000 override") -- Kitty text never fades.
assert(rules[3].opacity == "1.00000000 override") -- Explicit zero is retained.
for _, rule in ipairs(rules) do
    assert(rule.match.focus == true)
    assert(rule.match.fullscreen == nil and rule.match.float == nil)
end
print("Hyprland transparency contracts passed")
