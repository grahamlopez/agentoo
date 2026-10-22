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
Agentoo provides the automatic monitor rule, lid-based display switching,
laptop backlight controls, and the external DDC controls described below. Its GUI package policy disables XWayland, so Omarchy's global
`GDK_SCALE=2` and XWayland zero-scaling policy are not needed for this base.
Keep per-display compositor scaling as the default for mixed-density displays.

## External monitor controls (DDC/CI)

`agentoo display external` runs `ddcutil` as the current user. It does not need
Hyprland or an X server. Laptop controls remain under `display backlight`.
Read operations do not send Set VCP commands. Help and completion do not probe
DDC or require privileges.

```sh
agentoo display external list
agentoo display external capabilities
agentoo display external brightness       # Read VCP 10
agentoo display external brightness 40
agentoo display external brightness up    # Add 5 monitor units
agentoo display external volume 30        # Monitor speaker level, VCP 62
agentoo display external mute on          # VCP 8D: 1=mute, 2=unmute
agentoo display external mute off
agentoo display external input            # Read VCP 60
agentoo display external get E9           # Read an explicit hexadecimal code
```

Brightness and volume accept 0..100 or `up`/`down` by five monitor units;
these are monitor values, not a perceived-brightness curve. Relative adjustment
uses ddcutil's read/modify/write with clamping to the monitor's reported range.
Relative volume first checks for a conventional 0..100 response and refuses
nonstandard encodings instead of calculating an inappropriate write.
Omit a value to read the setting. Unsupported features fail through ddcutil.
Monitor modes such as HDR or automatic brightness may restrict manual settings.

Without a selector, the command finds connected external DRM connectors with a
DDC link in sysfs. Internal eDP/LVDS/DSI panels are excluded. Exactly one connector
must match, otherwise selection fails before a DDC command runs. Each operation
except `list` accepts `--output card0-DP-4` or `--bus 16`, mutually exclusively.
Connector and bus numbers can change after reconnection; no display number or
bus is saved. `list` delegates to `ddcutil detect` for DDC diagnostics.

```sh
agentoo display external brightness --output card0-DP-4
agentoo display external capabilities --bus 16
agentoo display external input 0x19 --output card0-DP-4
```

Input values are monitor-specific: use the capabilities report. Explicit VCP
access accepts a hexadecimal feature code and a decimal or `0x`-prefixed 16-bit
value, for example `agentoo display external set CODE VALUE --bus NUMBER`.
Explicit `set` passes `--permit-unknown-feature` to ddcutil so vendor features
can be addressed. This is an expert interface; it does not establish what
those features mean.
Normal writes request ddcutil verification. `input` and `set` accept
`--no-verify` for operations that disconnect the control path or cannot be read
back. A successful unverified write only establishes that the command was sent.
The CLI preserves ddcutil's output and exit status; this output is not a stable
Agentoo JSON schema. Argument errors exit 2; missing dependencies or selection
errors exit 1. No automatic sudo, scan of unknown features, or writes on startup.

### Gentoo setup

`@gui-desktop` includes `app-misc/ddcutil`, with `user-permissions` enabled and X/USB
monitor backends disabled. The DisplayPort/HDMI DDC path also works over
Thunderbolt/USB-C video connections. `/etc/modules-load.d/agentoo-display.conf`
loads `i2c-dev` at boot when built as a module. Kernels with
`CONFIG_I2C_CHARDEV=y` provide the interface directly and need no module load.
For the current session after deploying package policy:

```sh
sudo emerge --noreplace --oneshot app-misc/ddcutil
# Only for kernels with CONFIG_I2C_CHARDEV=m:
sudo modprobe i2c-dev
agentoo display external list
```

If ddcutil was already installed, apply the changed USE policy with
`sudo emerge --oneshot --newuse app-misc/ddcutil` instead.
The running kernel needs `CONFIG_I2C_CHARDEV` (built in or as a module).
Recent ddcutil versions supply `60-ddcutil-i2c.rules`, granting active local
sessions access with `TAG+="uaccess"` for I2C devices under display controllers.
If installation happens after loading the module, reload udev rules and trigger
I2C device events:

```sh
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=i2c-dev
sudo udevadm settle
```

Check `ls -l /dev/i2c-*` and `getfacl /dev/i2c-N` if access fails. Do not grant
all users access to every I2C device. Older package versions may use group-based
rules; inspect the installed rule before choosing an access policy. Enable
DDC/CI in the monitor's OSD. Some docks or cables do not forward DDC reliably.
See [ddcutil permissions](https://www.ddcutil.com/i2c_permissions/),
[capabilities caveats](https://www.ddcutil.com/command_capabilities/), and
[write/verification behavior](https://www.ddcutil.com/command_setvcp/).

### Dell U5226KW investigation, 2026-10-22

Read-only inspection on thinktop identified `DELL U5226KW` on `card0-DP-4`,
linked to `i2c-16`. The laptop panel is on `card0-eDP-1`/`i2c-12`.
At initial inspection, ddcutil was absent, i2c-dev was not loaded, and there were
no `/dev/i2c-*` nodes. The CLI's simulated tests do not prove hardware support. No monitor setting was changed during this initial inspection.
After booting the normal `6.18.54-agentoo-v0.2` kernel, `/proc/config.gz`
confirmed modules disabled and `CONFIG_I2C_CHARDEV=y`. The Dell moved to
`i2c-13`; `/dev/i2c-13` initially existed with root-only access. Installing
ddcutil 2.2.6 with `user-permissions`, reloading udev rules, and triggering
`i2c-dev` events successfully granted access without a reboot or group change.
`external list` then detected the Dell; its separate invalid-laptop-display
entry is expected.

| Requested control | Interface and current evidence |
| --- | --- |
| Brightness | VCP 10 read successfully: current 50, maximum 100. Writes not yet tested. |
| Speaker volume/mute | VCP 8D reads mute on. VCP 62 reports current 178 (`0xB2`), maximum 65380 (`0xFF64`); encoding still to establish. Relative volume refuses this response. Writes not yet tested. |
| Video input | VCP 60 reads HDMI1 (`0x11`), even though the Linux connector is DP-4. Numeric writes not yet tested. |
| PiP/PbP configuration | Advertised E9 reads `0x24`; its meaning still needs an OSD comparison. |
| USB target switching | Advertised E7 reads `0x1640` (max `0x0105`); target mapping still needs an OSD comparison. |

An independent [U5226KW control implementation](https://github.com/coralnode/delldispctl)
reports tested video input values of Thunderbolt `0x19`, DP1 `0x0F`, DP2 `0x13`,
HDMI1 `0x11`, and HDMI2 `0x12`. These are upstream observations, not locally
verified values. USB upstream targets and PiP sub-inputs must not be inferred
from this video input list.

The capabilities report advertises input values `19 0F 13 11 12`, E7 values
`00 01 02 03 FE FF`, and E9 values
`00 01 02 21 22 24 29 2A 2D 2E 2F 31 32 33 34 35 36 41 42 51`.
Read-only vendor snapshots also returned E8=`0x6739`, EA=`0xF801`,
EF=`0xB001`, F0=`0`, and speaker-select 63=`0xF2`. These are raw values, not
established meanings. Several capabilities values use multi-byte encodings
that ddcutil flags as parse errors; individual reads still succeed.

For PiP and USB,
compare those reads before and after a single OSD change, recording the layout,
input assignments and USB target. Establish the exact code/value mapping before
adding friendly commands. A video or USB switch may remove this host's display,
keyboard, mouse, network, or DDC path. Plan a physical recovery path before
performing a switching test; an unverified send is not proof that it worked.

ALSA's `/proc/asound/card0/eld#2.20` reported the Dell as a DisplayPort audio
sink with two-channel LPCM at 32/44.1/48 kHz. PipeWire exposes HDMI/DisplayPort
outputs, and the session's default was the laptop speakers at inspection time.
DDC volume/mute changes monitor settings; it does not route applications' audio.
Inspect `wpctl status`, `pactl list sinks`, and `pactl list cards` to select the
available display output. `pactl set-default-sink SINK_NAME` changes the default;
existing streams may require `pactl move-sink-input STREAM_ID SINK_NAME`.
A visible sink or valid ELD alone does not prove audible playback.

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

