-- Native preferences loaded after host and handwritten defaults.
local saved = assert(agentoo_desktop_preferences).transparency or {}
local families = require("/etc/xdg/hypr/window-classes.lua")
local classes = { all = "negative:" .. families.kitty, kitty = families.kitty, browser = families.browser }
for _, group in ipairs({"all", "kitty", "browser"}) do
  for _, state in ipairs({"focused", "unfocused"}) do
    local value = (saved[group] or {})[state]
    if value == nil then value = (saved.all or {})[state] end
    if value ~= nil then
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
  end
end
agentoo_transparency_loaded = true
