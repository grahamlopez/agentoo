-- One validated saved snapshot per config load, shared by the three consumers.
-- Native require() caches this result and starts fresh on the next config load.
local stream = assert(io.popen("python3 /usr/local/share/agentoo/lib/desktop/state.py settings", "r"))
local contents = stream:read("*a")
-- Hyprland can reap popen's child before pclose. Its completion record proves
-- validation finished, even when pclose reports a spurious ECHILD.
stream:close()
assert(contents:sub(-4) == "end\n", "Cannot load Agentoo appearance state; see session stderr")

local sections = { transparency = {}, blur = {}, effects = {} }
for line in contents:gmatch("([^\n]+)\n") do
    if line ~= "end" then
        local section, record = line:match("^(%a+)\t(.+)$")
        assert(sections[section] and record, "Invalid Agentoo appearance data")
        table.insert(sections[section], record)
    end
end
for section, records in pairs(sections) do
    sections[section] = #records > 0 and (table.concat(records, "\n") .. "\n") or ""
end
return sections
