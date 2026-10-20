-- Loaded after host/personal settings. JSON remains the only saved authority.
-- The helper emits group/state/percentage records, never executable Lua.
local stream = assert(io.popen("python3 /usr/local/share/agentoo/desktop_transparency.py rules", "r"))
local contents = stream:read("*a")
-- Hyprland's SIGCHLD handler can reap popen's child before pclose, which then
-- reports ECHILD even for a successful helper. Require its completion record.
stream:close()
assert(contents:sub(-4) == "end\n", "Cannot load Agentoo transparency state; see session stderr")

local kitty = "(?i:kitty|agentoo-dropdown)"
local browser = "(?i:firefox(-bin|-esr|-developeredition|-nightly)?|org.mozilla.firefox|librewolf|floorp|zen(-browser)?|chromium(-browser)?|google-chrome(-stable|-beta|-unstable)?|chrome|brave(-browser)?|com.brave.Browser|microsoft-edge(-stable|-beta|-dev)?|vivaldi(-stable)?|opera)"
local classes = { all = "negative:" .. kitty, kitty = kitty, browser = browser }
for group, state, raw in contents:gmatch("(%a+)\t(%a+)\t([^\n]+)\n") do
    local value = tonumber(raw)
    assert(classes[group] and (state == "focused" or state == "unfocused") and value and value >= 0 and value <= 90)
    -- A focus-specific absolute rule also handles fullscreen windows, without
    -- changing the omitted focus state's authored rules or decoration default.
    -- Kitty itself controls background opacity; keep its text fully opaque.
    local opacity = group == "kitty" and 1 or (1 - value / 100)
    hl.window_rule({
        name = "agentoo-transparency-" .. group .. "-" .. state,
        match = { class = classes[group], focus = state == "focused" },
        opacity = string.format("%.8f override", opacity),
    })
end
agentoo_transparency_loaded = true
