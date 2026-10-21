# Displays

## External displays and HiDPI

The shared configuration already uses the same automatic monitor policy as
[Omarchy's current Lua configuration](https://github.com/omacom/omarchy/blob/quattro/config/hypr/monitors.lua):

```lua
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })
```

The empty output matches displays without a specific rule. Hyprland enables
connected displays using their preferred resolution and refresh rate, places
new displays to the right, and chooses scaling from each display's pixel
density. Connecting an external display extends the desktop without a separate
monitor daemon. High resolution and scaling are independent: a laptop can use
2x while an external display uses 1x. See the
[Hyprland monitor reference](https://wiki.hypr.land/Configuring/Basics/Monitors/).

Inspect the running session before adding overrides:

```sh
hyprctl monitors all
hyprctl configerrors
```

Compare the active resolution, refresh rate, scale, and available modes. If a
terminal survives a compositor restart, its `HYPRLAND_INSTANCE_SIGNATURE` may
refer to the previous session. Use `hyprctl instances` and then
`hyprctl -i INSTANCE monitors all` to query the current one.

If the desired resolution is absent from the available modes, first investigate
the monitor's picture-by-picture/screen partition settings, input mode, cable,
dock, and graphics link. Changing `preferred` to `highres` cannot select a mode
the connection does not expose. For example, the Dell U5226KW was observed
offering at most 4608x2560 at 120 Hz, despite its
[specified full-panel resolution of 6144x2560](https://www.dell.com/en-us/shop/dell-ultrasharp-52-thunderbolt-hub-monitor-u5226kw/apd/210-bthw/).
After PiP was disabled on that monitor, Hyprland automatically selected
6144x2560 at 59.99 Hz with 1x scaling; 6144x2560 at 120 Hz also appeared in the
available modes. The automatic `preferred` policy selects the preferred timing,
which need not be the highest refresh rate.
These readings verify compositor state, not visible output on the panel. An
empty workspace shows the base's nearly black background; open a window on the
external workspace to distinguish that from a blank output. If it remains
blank, inspect `hyprctl rollinglog` and kernel display errors before declaring
the mode working.

For a display needing a fixed scale or arrangement, add a specific `hl.monitor`
rule to the host fragment or personal override described below. Prefer a
`desc:...` output match from `hyprctl monitors all` when connector names change
between docks. Keep the shared automatic fallback for unfamiliar displays.
Use a scale that divides both resolution dimensions into whole logical pixels;
positions are measured in those logical pixels.

[Omarchy also provides](https://github.com/omacom/omarchy/blob/quattro/manual/33-monitors.md)
scale shortcuts, mirroring, lid-based internal-display switching, and brightness
control for supported external monitors. These are separate enhancements;
Agentoo provides the automatic monitor rule, lid-based display switching, and
laptop backlight controls. Its GUI package policy disables XWayland, so Omarchy's global
`GDK_SCALE=2` and XWayland zero-scaling policy are not needed for this base.
Keep per-display compositor scaling as the default for mixed-density displays.

### Laptop lid behavior

`/etc/xdg/hypr/lid.lua` binds `switch:on:Lid Switch` and
`switch:off:Lid Switch` and reconciles monitor hotplug, session startup, and
configuration reloads. Each reconciliation re-reads physical ACPI lid state;
if it is unavailable, the latest switch event remains authoritative.
During configuration loading, after host and personal settings, the handler
reinstalls closed-lid disable rules before Hyprland applies monitor changes.
It also discovers internal connector names through DRM sysfs because disabled
panels are absent from the active monitor list. Appearance-setting reloads
therefore keep a docked, closed panel off instead of briefly enabling it.
Closing the lid with an active external output disables
the internal eDP/LVDS/DSI outputs; Hyprland moves their workspaces to remaining
outputs. Opening the lid reloads the configured rules to restore internal
outputs, including host and personal display settings. Hyprland decides where
workspaces return; this does not promise to restore each window's old location.
Connecting an external output while closed also disables internal outputs.
Removing the last external output restores the configured rules if the lid
handler had disabled the panel, avoiding a persistent disabled-panel rule.

There is no separate resume listener or background display process. Lid opening
and monitor hotplug trigger reconciliation through native Hyprland events.
Resume with the lid still closed and no monitor event has no explicit handler;
add one only if an ordinary suspend/resume test demonstrates a need.

Plugging in a dock can only resume a sleeping laptop if the hardware/firmware
supports waking on that connection. Hyprland cannot trigger that while suspended.
USB/Thunderbolt wake was enabled on thinktop, but the tested dock connection did
not wake it; opening the lid did. Cable-insertion wake is deferred. No wake or
firmware settings are changed by this handler.

The handler never requests suspend or takes a logind inhibitor. The logind
drop-in `/etc/systemd/logind.conf.d/30-ignore-lid-on-external-power.conf` sets
`HandleLidSwitchExternalPower=ignore`. A closed laptop stays awake on external
power even if the Dell temporarily disconnects while switching input or PiP/PbP
mode. This also keeps it awake on an ordinary charger without an external
display. On battery, undocked lid-close suspend remains enabled; docked behavior
retains logind's default ignore policy. Manual suspend remains available.
This follows the previously tested fix in
[the historical Omarchy notes](history/omarchy-configuration-changes.md#1-keep-the-closed-laptop-awake-during-monitor-inputpbp-switching).
If monitor reconfiguration also removes external power, the battery lid policy
can still suspend the laptop; this rule adds no timed disconnect grace period.
USB-C power readings can settle after logind's last display/USB hotplug event.
On thinktop this left a closed laptop awake after unplugging one Thunderbolt
port under both the custom kernel and the matching Gentoo distribution kernel.
The same ACPI `BRNS`/`_Q27` errors also occurred on a port that suspended
successfully, so they do not by themselves explain the missed suspend.

`80-agentoo-lid-recheck.rules` queues `agentoo-lid-recheck.timer` when a power
supply reports offline. Each event restarts a two-second timer; its oneshot
service sends logind a D-Bus Ping, waking its event loop so it re-evaluates
closed-lid policy against the settled power readings. It neither requests
suspend nor changes inhibitors or lid settings. The timer adds a retry, not
a minimum grace period: logind can still suspend earlier. No polling daemon
or timer enablement is needed. A temporary delayed-Ping experiment successfully
suspended the previously failing port on the distribution kernel; the permanent
udev/timer path and the custom kernel still require physical acceptance.
After installing the rule and both units, run `sudo systemctl daemon-reload`
and `sudo udevadm control --reload-rules`. Future power-supply events activate
the timer; do not enable it at boot.

Apply a changed drop-in with `sudo systemctl reload systemd-logind`; a service
restart is unnecessary. Systems with custom logind policy or a differently named
lid switch need their settings reviewed
with `systemd-analyze cat-config systemd/logind.conf`, `systemd-inhibit --list`,
and `hyprctl devices`.

Physical acceptance: close/open the lid with the Dell connected, check that
workspaces remain reachable and the panel returns, then test undocked lid-close
suspend on battery and staying awake on a charger. Test Dell input/PiP/PbP
switching with the lid closed and external power connected. Also test
dock/undock while closed and a config reload while closed.
Parser and simulated tests cannot verify physical suspend
or the monitor's visible output.

Run the simulated lid/hotplug regression checks from the repository root with
`lua usr/local/share/agentoo/tests/test_hypr_lid.lua`.

