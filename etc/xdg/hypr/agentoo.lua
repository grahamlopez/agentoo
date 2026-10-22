-- Shared defaults for Hyprland 0.56.2. No host-specific workarounds.
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })

-- Restore on startup and after monitor geometry changes; ordinary reloads
-- retain the existing client. See wallpaper.lua for the layer-position repair.
-- That file contains captured 0.56.2 evidence, upstream source references and
-- the procedure for disabling/retesting/removing the workaround after upgrades.
-- Do not simply remove this include permanently: it also owns startup restore.
require("/etc/xdg/hypr/wallpaper.lua")

hl.config({
    input = {
        kb_layout = "us",
        kb_options = "ctrl:nocaps",
        special_fallthrough = true,
    },
    general = { layout = "dwindle", gaps_in = 4, gaps_out = 8, border_size = 2 },
    dwindle = { preserve_split = true },
    decoration = { rounding = 0, blur = { enabled = false }, shadow = { enabled = false } },
    animations = { enabled = false },
    misc = {
        -- Wake DPMS-blanked displays from the keyboard, avoiding mouse wakeups.
        mouse_move_enables_dpms = false,
        key_press_enables_dpms = true,
        disable_hyprland_logo = true,
        disable_splash_rendering = true,
        background_color = "rgb(111111)",
    },
})

hl.bind("SUPER + Return", hl.dsp.exec_cmd("kitty"))

-- Capture text once per session; configuration reloads do not start watchers.
hl.on("hyprland.start", function()
    hl.exec_cmd("wl-paste --type text --watch cliphist store")
end)
hl.bind("CTRL + 0", function()
    for _, window in ipairs(hl.get_windows()) do
        if window.mapped and window.class == "agentoo-clipboard" then
            -- send_shortcut marks this entire callback for key-release replay
            -- in 0.56.2, which can reopen the picker after it has closed.
            for _, state in ipairs({ "down", "up" }) do
                hl.dispatch(hl.dsp.send_key_state({ mods = "", key = "Escape", state = state, window = window }))
            end
            return
        end
    end
    hl.exec_cmd("kitty --class agentoo-clipboard -o remember_window_size=no -o initial_window_width=100c -o initial_window_height=25c bash /usr/local/share/agentoo/lib/desktop/clipboard-picker.sh")
end)
hl.window_rule({
    match = { class = "agentoo-clipboard" },
    float = true,
    move = "(monitor_w-window_w)/2 (monitor_h-window_h)/2",
})

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
hl.bind("CTRL + 9", hl.dsp.workspace.toggle_special("terminal"))
-- Keep applications launched from the dropdown on the regular workspace below.
hl.on("window.open", function(window)
    local workspace = window.workspace
    if window.class == "agentoo-dropdown" or not workspace or workspace.name ~= "special:terminal" then
        return
    end
    local monitor = window.monitor
    local target = monitor and monitor.active_workspace
    if target then
        hl.dispatch(hl.dsp.window.move({ window = window, workspace = target, follow = false }))
    end
end)
hl.bind("SUPER + SHIFT + Return", hl.dsp.exec_cmd("firefox-bin"))
hl.bind("SUPER + Q", hl.dsp.window.close())
hl.bind("SUPER + SHIFT + E", hl.dsp.exit())
hl.bind("SUPER + F", hl.dsp.window.fullscreen({ action = "toggle" }))
hl.bind("SUPER + V", hl.dsp.window.float({ action = "toggle" }))

require("/etc/xdg/hypr/alt-tab.lua")

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
hl.bind("XF86MonBrightnessUp", hl.dsp.exec_cmd("agentoo display backlight up"), { repeating = true })
hl.bind("XF86MonBrightnessDown", hl.dsp.exec_cmd("agentoo display backlight down"), { repeating = true })

hl.bind("Print", hl.dsp.exec_cmd("agentoo screenshot full"))
hl.bind("SHIFT + Print", hl.dsp.exec_cmd("agentoo screenshot region"))
hl.bind("XF86SelectiveScreenshot", hl.dsp.exec_cmd("agentoo screenshot region"))
