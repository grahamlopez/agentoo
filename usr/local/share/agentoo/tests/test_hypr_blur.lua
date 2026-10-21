-- Run: lua usr/local/share/agentoo/tests/test_hypr_blur.lua
local function run(records, baseline)
    local config = {
        ["decoration.blur.enabled"] = baseline,
        ["decoration.blur.size"] = 8,
        ["decoration.blur.passes"] = 1,
    }
    local rules = {}
    local context = setmetatable({
        require = function(path)
            assert(path == "/etc/xdg/hypr/window-classes.lua")
            return dofile("etc/xdg/hypr/window-classes.lua")
        end,
        hl = {
            get_config = function(key) return config[key] end,
            config = function(values)
                for key, value in pairs(values) do
                    assert(key:match("^decoration%.blur%.")) -- Transparency is independent.
                    config[key] = value
                end
            end,
            window_rule = function(rule) rules[#rules + 1] = rule end,
        },
        io = { popen = function()
            return {
                read = function() return records .. "revision\t" .. string.rep("a", 64) .. "\nend\n" end,
                close = function() return nil, "No child processes", 10 end,
            }
        end },
    }, { __index = _G })
    local chunk = assert(loadfile("etc/xdg/hypr/blur.lua", "t", context))
    if setfenv then setfenv(chunk, context) end
    chunk()
    return config, rules, context.agentoo_blur_report(), context.agentoo_blur_report
end

local config, rules, report, snapshot = run("kitty\tfocused\ton\n", false)
assert(config["decoration.blur.enabled"] == true)
assert(#rules == 8)
assert(rules[1].match.class == ".*" and rules[1].no_blur == true)
assert(rules[3].match.focus == true and rules[3].no_blur == false)
assert(rules[4].match.focus == false and rules[4].no_blur == true)
for _, rule in ipairs(rules) do
    assert(rule.match.float == nil and rule.match.fullscreen == nil)
end
assert(report:find("option.enabled\ton") and report:find("baseline\toff"))
config["decoration.blur.enabled"] = false
assert(snapshot():find("option.enabled\toff")) -- Query-time options, not a cached engine value.
assert(snapshot():find("baseline\toff"))

config, rules = run("all\tfocused\toff\nall\tunfocused\toff\n", true)
assert(config["decoration.blur.enabled"] == false)
for _, rule in ipairs(rules) do assert(rule.no_blur == true) end

config, rules = run("strength\tsize\t3\nstrength\tpasses\t1\n", false)
assert(#rules == 0 and config["decoration.blur.enabled"] == false)
assert(config["decoration.blur.size"] == 3 and config["decoration.blur.passes"] == 1)

config, rules = run("", true) -- Full reset leaves authored defaults in control.
assert(#rules == 0 and config["decoration.blur.enabled"] == true)
print("Hyprland blur contracts passed")

config, rules = run("other\tfocused\ton\n", false)
assert(config["decoration.blur.enabled"] == true)
assert(rules[3].no_blur and rules[5].no_blur)
assert(rules[7].no_blur == false and rules[8].no_blur == true)
assert(rules[7].match.class == dofile("etc/xdg/hypr/window-classes.lua").other)
config, rules = run("all\tfocused\ton\nall\tunfocused\toff\nkitty\tfocused\toff\nbrowser\tfocused\toff\nother\tfocused\toff\n", true)
assert(config["decoration.blur.enabled"] == false)
