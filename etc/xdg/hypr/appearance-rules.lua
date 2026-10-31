-- Observe executed declarations, including requires outside ~/.config/hypr.
-- Native handles own enable/disable state and named-rule merging. Keep only
-- conflict ownership and source locations here, not a second rule definition.
local native_window_rule = hl.window_rule
local authored = {}
hl.window_rule = function(spec)
    local rule = native_window_rule(spec)
    if rule then
        local transparency = spec.opacity ~= nil or spec.opaque ~= nil or spec.force_rgbx ~= nil
        local blur = spec.no_blur ~= nil or spec.opaque ~= nil or spec.force_rgbx ~= nil
        if transparency or blur then
            local caller = debug.getinfo(2, "Sl")
            -- Tail calls can erase the caller frame; retain conflict detection
            -- without making a valid native declaration fail on missing metadata.
            local source = caller and (caller.source:sub(1, 1) == "@" and caller.source:sub(2) or caller.short_src)
                or "unknown Lua callsite"
            authored[#authored + 1] = {
                rule = rule, transparency = transparency, blur = blur,
                location = caller and source .. ":" .. caller.currentline or source,
            }
        end
    end
    return rule
end

local function conflicts(feature)
    local found = {}
    for _, entry in ipairs(authored) do
        if entry[feature] and entry.rule:is_enabled() then
            found[#found + 1] = entry.location
        end
    end
    return table.concat(found, "\n")
end
agentoo_window_rule_conflicts = conflicts

return {
    -- Managed appearance rules use the native setter so they do not report
    -- themselves as competing authored policy. Other declarations stay observed.
    window_rule = native_window_rule,
    check = function(feature)
        local found = conflicts(feature)
        assert(found == "", "Conflicting " .. feature .. " window rules; edit them before adjusting:\n" .. found)
    end,
}
