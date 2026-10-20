-- Shared defaults for Hyprland 0.56.2. No host-specific workarounds.
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })
require("/etc/xdg/hypr/lid.lua")

-- Restore personal wallpaper once per session, never on config reload.
hl.on("hyprland.start", function()
    hl.exec_cmd("agentoo desktop wallpaper restore")
end)

hl.config({
    input = { kb_layout = "us", kb_options = "ctrl:nocaps" },
    general = { layout = "dwindle", gaps_in = 4, gaps_out = 8, border_size = 2 },
    dwindle = { preserve_split = true },
    decoration = { rounding = 0, blur = { enabled = false }, shadow = { enabled = false } },
    animations = { enabled = false },
    misc = {
        disable_hyprland_logo = true,
        disable_splash_rendering = true,
        background_color = "rgb(111111)",
    },
})

hl.bind("SUPER + Return", hl.dsp.exec_cmd("kitty"))
-- A persistent terminal overlay; Kitty sizes the content in columns and rows.
hl.workspace_rule({
    workspace = "special:terminal",
    on_created_empty = "kitty --class agentoo-dropdown -o remember_window_size=no -o initial_window_width=160c -o initial_window_height=45c",
})
hl.window_rule({
    match = { class = "agentoo-dropdown" },
    float = true,
    workspace = "special:terminal",
    move = "(monitor_w-window_w)/2 monitor_h*0.15",
})
hl.bind("SUPER + grave", hl.dsp.workspace.toggle_special("terminal"))
hl.bind("SUPER + SHIFT + Return", hl.dsp.exec_cmd("firefox-bin"))
hl.bind("SUPER + Q", hl.dsp.window.close())
hl.bind("SUPER + SHIFT + E", hl.dsp.exit())
hl.bind("SUPER + F", hl.dsp.window.fullscreen({ action = "toggle" }))
hl.bind("SUPER + V", hl.dsp.window.float({ action = "toggle" }))

hl.bind("ALT + TAB", function()
    hl.dispatch(hl.dsp.window.cycle_next())
    hl.dispatch(hl.dsp.window.bring_to_top())
end)
hl.bind("ALT + SHIFT + TAB", function()
    hl.dispatch(hl.dsp.window.cycle_next({ next = false }))
    hl.dispatch(hl.dsp.window.bring_to_top())
end)

for _, direction in ipairs({ "left", "right", "up", "down" }) do
    hl.bind("SUPER + " .. direction, hl.dsp.focus({ direction = direction }))
    hl.bind("SUPER + SHIFT + " .. direction, hl.dsp.window.move({ direction = direction }))
end
for workspace = 1, 10 do
    local key = workspace % 10
    hl.bind("SUPER + " .. key, hl.dsp.focus({ workspace = workspace }))
    hl.bind("SUPER + SHIFT + " .. key, hl.dsp.window.move({ workspace = workspace }))
end
hl.bind("SUPER + mouse:272", hl.dsp.window.drag(), { mouse = true })
hl.bind("SUPER + mouse:273", hl.dsp.window.resize(), { mouse = true })

hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+"), { repeating = true })
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"), { repeating = true })
hl.bind("XF86AudioMute", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"))
hl.bind("XF86AudioMicMute", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"))

-- Standard key meanings; laptops install @laptop for acpilight.
hl.bind("XF86MonBrightnessUp", hl.dsp.exec_cmd("agentoo backlight up"), { repeating = true })
hl.bind("XF86MonBrightnessDown", hl.dsp.exec_cmd("agentoo backlight down"), { repeating = true })

hl.bind("Print", hl.dsp.exec_cmd("agentoo screenshot full"))
hl.bind("SHIFT + Print", hl.dsp.exec_cmd("agentoo screenshot region"))
hl.bind("XF86SelectiveScreenshot", hl.dsp.exec_cmd("agentoo screenshot region"))
