-- Run: lua usr/local/share/agentoo/tests/test_hypr_transparency.lua
local source = "etc/xdg/hypr/transparency.lua"
local rules = {}
local context = setmetatable({
    require = function(path)
        assert(path == "/etc/xdg/hypr/window-classes.lua")
        return dofile("etc/xdg/hypr/window-classes.lua")
    end,
    hl = { window_rule = function(rule) rules[#rules + 1] = rule end },
    io = { popen = function(command, mode)
        assert(command:match("lib/desktop/transparency.py rules$") and mode == "r")
        return {
            read = function() return "all\tfocused\t5\nkitty\tfocused\t5\nbrowser\tfocused\t0\nother\tfocused\t20\nend\n" end,
            close = function() return true end,
        }
    end },
}, { __index = _G })
local chunk = assert(loadfile(source, "t", context))
if setfenv then setfenv(chunk, context) end
chunk()
assert(context.agentoo_transparency_loaded)
assert(#rules == 4)
assert(rules[1].match.class:match("^negative:"))
assert(rules[1].opacity == "0.95000000 override")
assert(rules[2].opacity == "1.00000000 override") -- Kitty text never fades.
assert(rules[3].opacity == "1.00000000 override") -- Explicit zero is retained.
for _, rule in ipairs(rules) do
    assert(rule.match.focus == true)
    assert(rule.match.fullscreen == nil and rule.match.float == nil)
end
print("Hyprland transparency contracts passed")

assert(rules[4].match.class == dofile("etc/xdg/hypr/window-classes.lua").other)
assert(rules[4].opacity == "0.80000000 override")
