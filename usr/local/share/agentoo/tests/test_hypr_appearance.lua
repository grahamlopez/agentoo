-- Run: lua usr/local/share/agentoo/tests/test_hypr_appearance.lua
local function load(contents)
    local calls = 0
    local context = setmetatable({
        io = { popen = function(command, mode)
            assert(command:match("lib/desktop/state.py settings$") and mode == "r")
            calls = calls + 1
            return {
                read = function() return contents end,
                close = function() return nil, "No child processes", 10 end,
            }
        end },
    }, { __index = _G })
    local chunk = assert(loadfile("etc/xdg/hypr/appearance.lua", "t", context))
    if setfenv then setfenv(chunk, context) end
    local result = chunk()
    assert(calls == 1)
    return result
end
local saved = load("transparency\tall\tfocused\t5\nblur\trevision\t123\neffects\tcorners\tradius\t8\nend\n")
assert(saved.transparency == "all\tfocused\t5\n")
assert(saved.blur == "revision\t123\n")
assert(saved.effects == "corners\tradius\t8\n")
assert(load("end\n").transparency == "")
for _, contents in ipairs({"", "effects\tcorners\tradius\t8\n", "unknown\tx\nend\n"}) do
    assert(not pcall(load, contents), "incomplete or malformed helper output must fail")
end
print("Shared appearance transport contracts passed")
