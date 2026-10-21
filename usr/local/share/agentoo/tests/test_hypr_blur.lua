-- Run: lua5.4 usr/local/share/agentoo/tests/test_hypr_blur.lua
local function run(data, baseline)
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
        agentoo_preferences = dofile("usr/local/share/agentoo/lib/desktop/preferences.lua"),
        agentoo_desktop_preferences = {blur=data},
        io = {popen = function() error("Native preference loading must not spawn helpers") end},
    }, { __index = _G })
    local chunk = assert(loadfile("etc/xdg/hypr/blur.lua", "t", context))
    if setfenv then setfenv(chunk, context) end
    chunk()
    return config, rules, context.agentoo_blur_report(), context.agentoo_blur_report
end

local config, rules, report, snapshot = run({kitty={focused=true}}, false)
assert(config["decoration.blur.enabled"] == true)
assert(#rules == 6)
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

config, rules = run({all={focused=false,unfocused=false}}, true)
assert(config["decoration.blur.enabled"] == false)
for _, rule in ipairs(rules) do assert(rule.no_blur == true) end

config, rules = run({strength={size=3,passes=1}}, false)
assert(#rules == 0 and config["decoration.blur.enabled"] == false)
assert(config["decoration.blur.size"] == 3 and config["decoration.blur.passes"] == 1)

config, rules = run({}, true) -- Full reset leaves authored defaults in control.
assert(#rules == 0 and config["decoration.blur.enabled"] == true)
print("Hyprland blur contracts passed")
