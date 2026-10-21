-- Run with lua5.4. Native loading is shared by Hyprland and command operations.
local preferences = dofile('usr/local/share/agentoo/lib/desktop/preferences.lua')
local path = os.tmpname()
local function read(source, selected, partial, omitted)
    local file = assert(io.open(path, 'w'))
    file:write(source)
    file:close()
    return preferences.load(path, selected, partial, false, omitted)
end
local ok, message = pcall(function()
    local source = preferences.serialize({gaps={inner=4},blur={all={focused=false}}})
    local first = read(source)
    assert(first.gaps.inner == 4 and first.blur.all.focused == false)
    assert(source:find('Hand%-editing is discouraged'))
    assert(preferences.revision(first) == preferences.revision(read(source)))
    local merged = preferences.merge(first,{gaps={outer=8},blur={all={unfocused=true}}})
    assert(merged.gaps.inner == 4 and merged.gaps.outer == 8)
    assert(merged.blur.all.focused == false and merged.blur.all.unfocused == true)
    local a = preferences.merge({animations={windows='popin',window_size=80}}, {animations={windows='slide'}})
    assert(a.animations.windows == 'slide' and a.animations.window_size == nil)
    a = read('return {animations={window_size=80}}',nil,true)
    assert(a.animations.window_size == 80)
    for _, invalid in ipairs({
        'return {gaps={inner=true}}', 'return {gaps={inner=-1}}',
        'return {corners={radius=1.5}}', 'return {blur={all={focused="on"}}}',
        'return {wallpaper="file.png"}', 'return {animations={windows="slide",window_size=80}}',
        'return {shadows={opacity=0/0}}', 'return {gaps={inner=math.huge}}',
        'return {gaps={inner=(function() return 4 end)()}}',
        'os.execute("false"); return {}', 'return {gaps={inner=io.open("file")}}',
        'return {gaps={inner=function() end}}',
    }) do
        assert(not pcall(read,invalid), 'Accepted invalid preferences: '..invalid)
    end
    assert(read('return {borders={width=2},gaps={typo=1}}','borders').borders.width == 2)
    assert(read('return {gaps={typo=1},corners={radius=4}}',nil,false,'gaps').corners.radius == 4)
    assert(read('-- normal line comment\nreturn {borders={focused="#12345680"}}').borders.focused == '#12345680')
    assert(preferences.serialize({}) == preferences.serialize(read('return {}')))
end)
os.remove(path)
assert(ok,message)
print('Native Lua preference contracts passed')
