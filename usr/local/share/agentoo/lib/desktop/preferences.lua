-- Shared preference data operations. Hyprland loads this module in-process;
-- command-side operations run it with lua5.4. No Python is needed on reload.
local M = {}
local header = "-- Managed by agentoo desktop.\n-- Hand-editing is discouraged: changes may be overwritten or disrupt generation.\n-- Keep handwritten settings in agentoo-local.lua. Copy this file to save a preset.\n"
local function keys(t)
    local result = {}
    for k in pairs(t) do
        assert(type(k) == "string", "Preference keys must be strings")
        result[#result + 1] = k
    end
    table.sort(result)
    return result
end
local function number(low, high, integer)
    return function(v)
        return type(v) == "number" and v == v and v >= low and v <= high and (not integer or v % 1 == 0)
    end
end
local function choices(values)
    local allowed = {}
    for word in values:gmatch("%S+") do allowed[word] = true end
    return function(v) return type(v) == "string" and allowed[v] == true end
end
local switch = choices("on off")
local boolean = function(v) return type(v) == "boolean" end
local function color(v)
    return type(v) == "string" and (v:match("^#%x%x%x%x%x%x$") or v:match("^#%x%x%x%x%x%x%x%x$"))
end
local function gradient(v)
    if type(v) ~= "string" or v == "" or v:sub(-1) == "," then return false end
    local count = 0
    for part in (v .. ","):gmatch("(.-),") do
        if not color(part:match("^%s*(.-)%s*$")) then return false end
        count = count + 1
    end
    return count <= 10
end
local schema = {
    corners = { radius = number(0,20,true), power = number(2,10) },
    gaps = { inner = number(0,1000,true), outer = number(0,1000,true) },
    borders = { width = number(0,20,true), focused = gradient, unfocused = gradient,
        focused_angle = number(0,360), unfocused_angle = number(0,360) },
    animations = { enabled = switch, duration = number(1,10000,true), windows = choices("slide popin gnome gnomed"),
        workspaces = choices("slide slidevert fade slidefade slidefadevert"),
        window_direction = choices("auto top bottom left right"), window_size = number(0,100,true), workspace_distance = number(0,100,true) },
    shadows = { enabled = switch, size = number(0,100,true), opacity = number(0,100),
        color = function(v) return color(v) and #v == 7 end,
        offset_x = number(-250,250,true), offset_y = number(-250,250,true) },
    dimming = { enabled = switch, strength = number(0,100), modal = switch },
    transparency = {}, blur = {},
}
for _, group in ipairs({"all", "kitty", "browser"}) do
    schema.transparency[group] = { focused = number(0,90), unfocused = number(0,90) }
    schema.blur[group] = { focused = boolean, unfocused = boolean }
end
schema.blur.strength = { size = number(1,40,true), passes = number(1,10,true) }
local function check(data, fields, path)
    assert(type(data) == "table" and getmetatable(data) == nil, "Invalid preference table: " .. path)
    for _, key in ipairs(keys(data)) do
        local rule = fields[key]
        assert(rule, "Unknown appearance setting: " .. path .. key)
        if type(rule) == "table" then check(data[key], rule, path .. key .. ".")
        else assert(rule(data[key]), "Invalid appearance setting: " .. path .. key) end
    end
end
function M.validate(data, partial)
    check(data, schema, "")
    for _, focus in ipairs({"focused", "unfocused"}) do
        if data.borders and data.borders[focus] then
            data.borders[focus] = data.borders[focus]:gsub("%s+", ""):lower()
        end
    end
    if data.shadows and data.shadows.color then data.shadows.color = data.shadows.color:lower() end
    local a = data.animations or {}
    if a.window_direction and (not partial or a.windows) then assert(a.windows == "slide", "window_direction requires windows: slide") end
    if a.window_size and (not partial or a.windows) then assert(a.windows == "popin", "window_size requires windows: popin") end
    if a.workspace_distance and (not partial or a.workspaces) then
        assert(a.workspaces and a.workspaces:match("^slide"), "workspace_distance requires a sliding workspaces style")
    end
    return data
end
function M.path()
    local home = os.getenv("XDG_CONFIG_HOME")
    if not home or home:sub(1,1) ~= "/" then home = assert(os.getenv("HOME"), "HOME is required") .. "/.config" end
    return home .. "/hypr/agentoo-desktop.lua"
end
-- Reject executable constructs, leaving Lua itself to parse the table literal.
-- Quoted strings and comments are skipped so their contents are always data.
local function declarative(source)
    local i, tokens = 1, {}
    while i <= #source do
        local rest = source:sub(i)
        local comment = rest:match("^%-%-[^\n]*")
        local quote = source:sub(i,i)
        if comment then i = i + #comment
        elseif quote == '"' or quote == "'" then
            i = i + 1
            while i <= #source do
                local ch = source:sub(i,i)
                i = i + 1
                if ch == "\\" then i = i + 1 elseif ch == quote then break end
            end
            tokens[#tokens+1] = " string "
        else
            assert(not rest:match("^%[=*%["), "Use quoted strings in preference tables")
            tokens[#tokens+1] = quote
            i = i + 1
        end
    end
    local text = table.concat(tokens)
    assert(text:match("^%s*return%s*{"), "Preferences must return a declarative table")
    for word in text:gmatch("[%a_][%w_]*") do
        assert(not ({["function"]=true,["local"]=true,["while"]=true,["for"]=true,["repeat"]=true,
            ["if"]=true,["do"]=true,["goto"]=true,["end"]=true})[word], "Executable Lua is not supported in preferences")
    end
    assert(not text:find("[():]"), "Function calls and expressions are not supported in preferences")
end
function M.load(path, selected, partial, optional, omitted)
    local file, message, code = io.open(path, "r")
    if not file then
        if optional and code == 2 then return {} end
        error("Cannot read appearance file " .. path .. ": " .. tostring(message))
    end
    local source = file:read("*a")
    file:close()
    declarative(source)
    local chunk = assert(load(source, "@" .. path, "t", {}))
    local data = chunk()
    assert(type(data) == "table", "Appearance file must return a table")
    if omitted and omitted ~= "" then data[omitted] = nil end
    if selected and selected ~= "" then data = data[selected] and { [selected] = data[selected] } or {} end
    return M.validate(data, partial)
end
local function literal(value, depth)
    if type(value) == "string" then return string.format("%q", value) end
    if type(value) ~= "table" then return tostring(value) end
    local lines = {"{"}
    for _, key in ipairs(keys(value)) do
        lines[#lines+1] = string.rep("  ", depth+1) .. "[" .. string.format("%q",key) .. "] = " .. literal(value[key],depth+1) .. ","
    end
    lines[#lines+1] = string.rep("  ",depth) .. "}"
    return table.concat(lines,"\n")
end
function M.serialize(data) return header .. "return " .. literal(data,0) .. "\n" end
function M.merge(previous, patch)
    for section, values in pairs(patch) do
        local old = previous[section] or {}
        if section == "animations" then
            if values.windows and values.windows ~= "slide" then old.window_direction = nil end
            if values.windows and values.windows ~= "popin" then old.window_size = nil end
            if values.workspaces and not values.workspaces:match("^slide") then old.workspace_distance = nil end
        end
        for key, value in pairs(values) do
            if section == "blur" or section == "transparency" then
                old[key] = old[key] or {}
                for field, v in pairs(value) do old[key][field] = v end
            else old[key] = value end
        end
        previous[section] = old
    end
    return previous
end
function M.revision(data)
    -- Stable fingerprint shared by the CLI and the native compositor report.
    local hash = -3750763034362895579
    local source = M.serialize(data)
    for i = 1, #source do hash = (hash ~ source:byte(i)) * 1099511628211 end
    return string.format("%016x",hash)
end
-- Command-side queries return a Python literal of validated schema values.
-- Saved files and all merging/serialization remain Lua. No JSON is involved.
local function python(value)
    if type(value) == "table" then
        local entries = {}
        for _, key in ipairs(keys(value)) do entries[#entries+1] = string.format("%q",key) .. ":" .. python(value[key]) end
        return "{" .. table.concat(entries,",") .. "}"
    elseif type(value) == "string" then return string.format("%q",value)
    elseif type(value) == "boolean" then return value and "True" or "False"
    else return tostring(value) end
end
local function receive()
    return assert(load(io.read("*a"), "@command", "t", {}))()
end
local function emit(data) print(python(data)) end
function M.command(args)
    local op = args[1]
    if op == "read" then emit(M.load(args[2],args[3],args[4] == "partial",false,args[5]),"")
    elseif op == "encode" then io.write(M.serialize(receive()))
    elseif op == "validate" then emit(M.validate(receive(),args[2] == "partial"),"")
    elseif op == "merge" then
        local data = receive()
        emit(M.validate(M.merge(data.previous,data.patch)),"")
    elseif op == "revision" then print(M.revision(receive()))
    else error("Unknown preference operation") end
end
-- require() supplies a module name; direct invocation supplies command args.
if arg and arg[0] and (arg[0] == "preferences.lua" or arg[0]:match("/preferences%.lua$")) then
    local ok, message = pcall(M.command,arg)
    if not ok then io.stderr:write(tostring(message),"\n"); os.exit(1) end
end
return M
