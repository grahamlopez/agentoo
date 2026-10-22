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
For monitors without a model-specific mapping, relative volume first checks
for a conventional 0..100 response and refuses nonstandard encodings instead
of calculating an inappropriate write. The Dell mapping below decodes its
speaker-off flag before adjusting volume.
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
Generic controls preserve ddcutil's output and exit status; this output is not
a stable Agentoo JSON schema. Named Dell controls and Dell volume provide
readable results and report failed writes/readback as operational errors.
Argument errors exit 2; missing dependencies or selection errors exit 1. No automatic sudo, scan of unknown features, or writes on startup.

### Named Dell U5226KW controls

These commands require a connected monitor with EDID manufacturer/product
`DEL/439e`; vendor mappings are not sent to other monitor models.

```sh
agentoo display external layout               # Read the mapped layout name
agentoo display external layout off
agentoo display external layout 50-50
agentoo display external layout 25-75
agentoo display external layout 75-25
agentoo display external layout 33-67
agentoo display external layout 67-33
agentoo display external layout pip-small
agentoo display external layout pip-large
agentoo display external pip-position next
agentoo display external sub-input            # Read the secondary input
agentoo display external sub-input hdmi1
agentoo display external sub-input thunderbolt
agentoo display external audio-source window1
agentoo display external audio-source window2
agentoo display external speakers off
agentoo display external speakers on
agentoo display external volume               # e.g. 50/100 (speakers off)
agentoo display external volume up
agentoo display external usb                  # Read the active USB target
agentoo display external usb hdmi1
agentoo display external usb thunderbolt
agentoo display external usb next
```

`layout` and `sub-input` send one unverified write, then retry only readback as
the connection settles. They never repeat the write automatically. Successful
readback prints the mapped name and raw value; failure reports that the command
was sent but the resulting state could not be confirmed. `sub-input` requires
a mapped active PiP/PbP layout and changes only the secondary input. It can
show the same source as the main input; it is not a swap operation. The mapped
secondary inputs are currently limited to HDMI1 and Thunderbolt.

`pip-position next` requires small or large PiP. It advances clockwise through
top left, top right, bottom right, bottom left. The current position is not
readable through the mapped registers, so there is no absolute-position setter.
Its success means the action was sent, with physical movement confirmed during
mapping. Inset size and video inputs are retained.

`audio-source` reads/selects Window 1 or Window 2 via VCP 63. In the mapped
PbP layouts these are the left and right windows, respectively. `speakers`
reads/changes the monitor OSD's Speaker On/Off through VCP 8D; `mute on` is
its inverse (`speakers off`). These are monitor controls, independent of
PipeWire routing.

On the U5226KW, `volume` strips bit `0x80` from readback to get the 0..100
level; that bit reports Speaker Off. Absolute and relative volume changes
preserve the prior speaker state. Firmware turns speakers on during an ordinary
volume write, and flagged volume writes are ignored, so the CLI restores Off
immediately after the level write in the same ddcutil invocation. A brief
unmuted interval cannot be excluded. On write failure it attempts to restore
Off again and reports failure; successful readback must match both level and
speaker flag. Unchanged/clamped levels send no write.

Audio Switch Auto/Manual is not yet a named control. OSD changes affected F5,
but sending the observed Auto value directly did not change it, so F5 cannot
be treated as a simple scalar setting.

`usb` reads the active target. `usb thunderbolt` / `usb hdmi1` select a target
using its existing OSD USB assignment; they do not rewrite assignments.
Switching currently requires a mapped active two-window layout containing
Thunderbolt and HDMI1. A target already selected is a no-op. Otherwise the CLI
sends one cycle action and waits for the target status to match; it never
repeats the action on readback failure. `usb next` cycles that same mapped pair.
Other input pairs, duplicate video inputs, unmapped target status, and unmapped
layouts are rejected before switching. Peripherals may take several seconds
to re-enumerate after target status changes.

For checkout testing, prefix commands with `./usr/local/bin/agentoo` from the
repository root. The checkout implementation and its helper modules are used
without deploying them.

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

### Dell U5226KW findings, 2026-10-22

On thinktop, the Dell is connected through `card0-DP-4`, currently `i2c-13`.
The normal `6.18.54-agentoo-v0.2` kernel has modules disabled and
`CONFIG_I2C_CHARDEV=y`. ddcutil 2.2.6 with `user-permissions` works as the
active desktop user after reloading/triggering udev; a reboot or group change
was not needed. `external list` also prints an invalid-laptop-display entry
for the separate internal panel; that is expected.

These mappings were established by pairing command readback with the user's
physical/OSD observations. A register response alone does not establish what
appears on the panel.

| Named layout | OSD layout | VCP E9 value |
| --- | --- | --- |
| `off` | PiP/PbP Off | `0x00` |
| `50-50` | 50%–50% PbP | `0x24` |
| `25-75` | 25%–75% PbP | `0x29` |
| `75-25` | 75%–25% PbP | `0x2A` |
| `33-67` | 33%–67% PbP | `0x2D` |
| `67-33` | 67%–33% PbP | `0x2E` |
| `pip-small` | Small PiP inset | `0x21` |
| `pip-large` | Large PiP inset | `0x22` |

All listed values have successful command writes and matching readback.
The user confirmed their visible layouts. Canonical `0x2D` was subsequently
verified through the named setter after first observing it as the normalized
result of writing `0x01`. Do not treat `0x01` as a fixed PiP mode: its action
semantics are still uncertain.

E9=`0x02` cycles the inset clockwise, physically confirmed through the full
sequence top left → top right → bottom right → bottom left → top left.
Size and inputs remain unchanged, and E9 still reads the size (`0x21`/`0x22`).
Moving the inset through the OSD changed none of the advertised vendor-register
values sampled, so an absolute position/readback mapping is not established.
A [script for another Dell model](https://gist.github.com/lainosantos/06d233f6c586305cde67489c2e4a764d)
provided the initial position-action hypothesis; it was then tested locally.

| Input arrangement | VCP 60 | VCP E8 |
| --- | --- | --- |
| HDMI1 left/main, Thunderbolt right/secondary | `0x11` | `0x6739` |
| Thunderbolt left/main, HDMI1 right/secondary | `0x19` | `0x6731` |

Both arrangements have command writes and readback. Setting VCP 60 does not
automatically exchange the secondary input. Changing only one input can display
the same source twice. A test with overlapping user/agent commands demonstrated
that explicitly; coordinate live experiments with one writer. E8's high bits
are not generally decoded, so named secondary selection is limited to these
observed values on this model.

Capabilities advertise main input values `19 0F 13 11 12`. An independent
[U5226KW implementation](https://github.com/coralnode/delldispctl) labels these
Thunderbolt, DP1, DP2, HDMI1, HDMI2, respectively. Only Thunderbolt and HDMI1
were physically tested here; USB upstream targets must not be inferred from
these video-input values.

| Audio/brightness control | Established behavior |
| --- | --- |
| Brightness, 10 | Relative down changed 50→45; absolute 50 restored it. Both exited 0 with matching readback. |
| Volume, 62 | Low seven bits are 0..100 level; bit `0x80` means Speaker Off. Readback max `0xFF64` is not a usable scaling maximum. |
| Speaker, 8D | `1`=Off/muted, `2`=On/unmuted. Both writes and readback tested. |
| Audio source, 63 | `0xF1`=Window 1, `0xF2`=Window 2, confirmed in the OSD. Named Window 2 restoration succeeded. |
| Audio Switch | OSD Auto/Manual affects F5, but direct F5=`0` did not select Auto. No scripted setter established. |

Mute testing changed volume readback from 178 (50+128) to 50 and back.
An ordinary volume write of 45 enabled speakers; restoring Off changed
readback to 173. The OSD confirmed Volume 45 and Speaker Off. Writing flagged
volume 172 (`44 | 0x80`) was ignored. The named relative-volume command
subsequently restored level 50 with Speaker Off and confirmed readback 178.
Volume writes therefore send the new level and, when necessary, immediately
restore Speaker Off in the same ddcutil invocation; a brief unmuted interval
cannot be excluded. The original audio state was restored to volume 50,
Window 2, Speaker Off, Audio Switch Manual.

For Audio Switch, sampled F5 values were packed `0x1D28` before the first OSD
change, `0` after Auto, then a stable `1` after Manual. Sending F5=`0` returned
exit 0 but readback stayed `1`, and the user confirmed Manual was unchanged.
This is insufficient to treat F5 as a scalar setting.

Layout/input changes can alter EDID and interrupt DDC. The user observed
ENXIO errors under immediate verification even when the panel applied the
change. `--no-verify` writes returned exit 0, and separate settled reads matched.
The named controls therefore write once and retry only readback. An error does
not establish that a write had no effect; inspect before resending.

USB tests used the user's confirmed OSD assignment **HDMI 1 → USB-C 3**,
with Thunderbolt initially owning the shared devices. E7 current=`0x1640`
holds assignment data; it is not the active target. Its MH status byte was
`1` on Thunderbolt and `4` after a successful E7=`0xFF00` cycle action.
The Logitech receiver, C922 webcam, Blue microphone, and Realtek Ethernet
adapter all disappeared from this host. A second cycle restored MH=`1`, and
all four devices reappeared after USB enumeration completed. Both writes
returned exit 0; video inputs/layout were not changed by the test. A subsequent named `usb hdmi1` command returned `hdmi1 (status 0x04)`
and left the target selected; the user physically confirmed that the shared
USB mouse controlled the HDMI1 computer. This verifies the destination, not
just disappearance from Thunderbolt. The named `usb thunderbolt` restoration then succeeded and returned
`thunderbolt (status 0x01)`.

The named USB targets map those observed status values, not physical port
numbers: status `4` denotes the HDMI1 selection in this setup, whose USB
assignment is USB-C 3. It must not be labelled USB-C 4. A
[report for another Dell](https://github.com/ekamil/dell-ddc-documentation)
provided the E7 cycle action and assignment-packing hypothesis; assignment
`0x1640` decodes HDMI1 to USB3 consistently with the local OSD observation.
No assignment setter or arbitrary upstream-port selector is provided.
A switch can move keyboard, mouse, microphone, camera, or Ethernet to the
other host; the test used Wi-Fi to keep the agent connection independent.

ALSA identified the Dell as a DisplayPort audio sink with stereo LPCM at
32/44.1/48 kHz. PipeWire exposes HDMI/DisplayPort outputs, but the inspected
session's default was the laptop speakers. Monitor controls do not route
applications' audio. Inspect `wpctl status`, `pactl list sinks`, and
`pactl list cards`; `pactl set-default-sink SINK_NAME` changes the default, and
existing streams may need `pactl move-sink-input STREAM_ID SINK_NAME`.
Valid ELD/readback does not verify audible playback.

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

