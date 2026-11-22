# Displays, DDC/CI, and laptop lid policy

Use `agentoo display --help` (`off`, `backlight`, `external`) for CLI controls;
Dell U5226KW VCP register mappings live in
[lib/display_external.py](../lib/display_external.py). This guide covers
cross-tool display scaling, DDC/CI setup, and laptop lid/power coordination.

## Monitor scaling and modes

Shared Hyprland defaults use per-display automatic policy:

```lua
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })
```

No monitor daemon or global `GDK_SCALE` is needed (`@gui-base` disables
XWayland). Inspect active outputs with `hyprctl monitors all` and
`hyprctl configerrors` before adding overrides to `/etc/xdg/hypr/hosts/<host>.lua`
or `~/.config/hypr/agentoo-local.lua`. Prefer `desc:...` output matches when
dock connector names change, and choose scales that divide both dimensions into
whole logical pixels.

If an expected resolution or refresh rate is absent from `hyprctl monitors all`,
check the monitor's PiP/PbP settings, cable, dock, and graphics link first
(e.g., the Dell U5226KW exposes 6144×2560@120 only when PiP/PbP is off;
`preferred` picks EDID preferred timing, not necessarily the highest refresh).

## DDC/CI setup (`app-misc/ddcutil`)

`@gui-desktop` installs `app-misc/ddcutil[user-permissions,-X,-usb-monitor]`.
The running kernel must provide `CONFIG_I2C_CHARDEV` (built in on custom
kernels; `i2c-dev` loaded via `/etc/modules-load.d/agentoo-display.conf` on
module kernels). After first installation, reload udev so `60-ddcutil-i2c.rules`
(`TAG+="uaccess"`) grants the active local session access to display I2C
devices without opening every `/dev/i2c-*` globally:

```sh
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=i2c-dev
sudo udevadm settle
```

Enable DDC/CI in the monitor OSD, and verify with `agentoo display external list`.

## Laptop lid, `logind`, and external power

- **Clear division of ownership:** `/etc/xdg/hypr/lid.lua` routes outputs
  *only*—disabling internal eDP/LVDS/DSI panels when the lid is closed with an
  external display, and re-applying closed-lid rules via DRM sysfs during
  appearance reloads so a docked panel never flashes on. `systemd-logind`
  remains the sole suspend-policy owner.
- **Staying awake across monitor switches:**
  `/etc/systemd/logind.conf.d/30-ignore-lid-on-external-power.conf` sets
  `HandleLidSwitchExternalPower=ignore` so a closed, externally powered laptop
  does not suspend when a monitor briefly drops video during input or PiP/PbP
  switching. Apply edits with `sudo systemctl reload systemd-logind`. Battery
  undocked lid-close suspend stays enabled.
- **Delayed USB-C power recheck:** USB-C power supplies can report offline
  *after* logind's last hotplug event, leaving an unplugged closed laptop
  awake. `/etc/udev/rules.d/80-agentoo-lid-recheck.rules` triggers
  `agentoo-lid-recheck.timer` (2 s; do not enable at boot) when a power supply
  goes offline, sending logind a D-Bus `Ping` so it re-evaluates closed-lid
  policy against the settled readings.
