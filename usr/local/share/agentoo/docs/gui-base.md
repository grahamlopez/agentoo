# Minimal Hyprland base

The base selects Hyprland from hyproverlay, Kitty, PipeWire, and WirePlumber.
Hyprland and its listed overlay dependencies accept testing release updates
without exact version pins. Unkeyworded live ebuilds and package masks remain
excluded by the normal Portage policy. Preview updates after syncing; new
dependencies may require additional package-specific keyword decisions.
Launch it explicitly from a normal user's TTY login with `start-hyprland`.
There is no automatic session startup, greeter, UWSM, XWayland, launcher, panel,
notification daemon, portal, wallpaper daemon in the base, or screen locker. Suspend and
lid-close suspend belong to systemd/logind. Hyprland routes displays for docked
lid use as described below. Resume returns to an unlocked session.
Networking remains dhcpcd and wpa_supplicant.

## Before pulling on thinktop

Inspect the current installed packages, local Portage settings, Hyprland/user
configuration, and enabled user services. Preserve the working state before
the pull, since agentoo's live work tree is `/` and a pull changes configuration.
With package/configuration writers idle, as root:

```sh
agentoo git status --short
agentoo checkpoint create before-gui-base --no-clean-package-caches
agentoo checkpoint list
agentoo checkpoint inspect <exact-checkpoint-name>
```

Confirm the checkpoint completed and retain its exact name. See
[checkpoint and recovery procedures](checkpoints.md). Reconcile live edits,
then pull the reviewed commit with `agentoo git pull`.

## Inspect and install

The tracked `repos.conf/hyproverlay.conf` supplies the overlay definition; no
`eselect repository enable` step is needed. As root on thinktop:

```sh
emaint sync -r hyproverlay
portageq get_repo_path / hyproverlay
emerge --pretend --verbose --autounmask=n @gui-base
```

Read the full plan before installing. Expect the four selected packages and
their dependencies, Hyprland's `systemd dbus-session` features, Kitty's `wayland`,
and PipeWire's `sound-server pipewire-alsa pulseaudio systemd`. Both audio
packages use user services, with `system-service` disabled. Hyprland's `guiutils`,
`hyprpm`, `uwsm`, and `X` are disabled. Kitty's `X` is disabled. Profile defaults
can still select X support in shared libraries; this base does not blanket-disable
features used by other applications. X-only applications require a later,
explicitly reviewed XWayland choice.

The Hyprland ebuild requires an **active** GCC >=15 or Clang >=19. Check
`gcc --version` (or the selected Clang); merely installing a newer compiler
does not select it. Stop on missing versions, masks, REQUIRED_USE failures,
unexpected keyword requests, or blockers. Testing keyword acceptance does not
override an explicit package mask. Review changes before editing policy; do not
automatically accept Portage's proposed keyword or USE changes.

After the plan is satisfactory:

```sh
emerge --ask --verbose @gui-base
```

### Thinktop video acceleration

On thinktop, install `@gui-base-thinktop` instead of `@gui-base`. This set
includes the shared base plus Intel's VA-API media driver and `vainfo`:

```sh
emerge --ask --verbose @gui-base-thinktop
```

If `@gui-base` is already recorded in world_sets, installing the thinktop set
also records its host additions; the shared base remains included either way.
Keep `VIDEO_CARDS="intel"`. Intel video decoding uses the separate media
driver, rather than Mesa's `vaapi` feature. Identify the Intel render node via
`/sys/class/drm/renderD*/device/vendor` (`0x8086`), then verify it with
`vainfo --display drm --device /dev/dri/renderD129` (adjust the node if needed).
Check Firefox's `about:support` and video playback after installation.

### Thinktop NVIDIA power experiment

The unused NVIDIA GPU currently reaches D3cold with Nouveau. To test doing
without that driver, boot a separate, temporary EFI entry with the existing
kernel/initramfs and command line plus `module_blacklist=nouveau`. Keep the
working entry unchanged for rollback. Thinktop uses direct EFI registration:
editing `/etc/kernel/cmdline` alone does not change an existing entry.
The kernel blacklist prevents module loading even if Nouveau is in the initramfs.

After the tracked rule is present on the live system, create the test entry
from a root Bash shell (`sudo bash`) to register the EFI entry. This leaves
BootOrder unchanged:

```bash
(
    set -eu
    gpu_test_version=$(uname -r)
    gpu_test_esp=$(findmnt -rn -o SOURCE --mountpoint /boot)
    gpu_test_disk="/dev/$(lsblk -dnro PKNAME "$gpu_test_esp")"
    gpu_test_part=$(lsblk -dnro PARTN "$gpu_test_esp")
    gpu_test_cmdline=$(cat /etc/kernel/cmdline)
    test -s "/boot/EFI/Gentoo/kernel-$gpu_test_version.efi"
    test -s "/boot/EFI/Gentoo/initramfs-$gpu_test_version.img"
    sudo efibootmgr --create-only --disk "$gpu_test_disk" --part "$gpu_test_part" \
        --label "Gentoo thinktop GPU-off test" \
        --loader "\\EFI\\Gentoo\\kernel-$gpu_test_version.efi" \
        --unicode "$gpu_test_cmdline module_blacklist=nouveau initrd=\\EFI\\Gentoo\\initramfs-$gpu_test_version.img"
)
```

Select that entry manually from the firmware boot menu for the test boot.
To remove the experiment, identify its number using `efibootmgr`, then run
`sudo efibootmgr --bootnum NNNN --delete-bootnum` for that test entry only.

The tracked udev rule permits runtime power management on the exact Lenovo
NVIDIA device and upstream bridge. It does not remove the device from PCI.
After deploying the rule, reboot into the test entry and inspect:

```sh
cat /proc/cmdline
lsmod | rg nouveau
readlink /sys/bus/pci/devices/0000:01:00.0/driver
cat /sys/bus/pci/devices/0000:01:00.0/power/control
cat /sys/bus/pci/devices/0000:01:00.0/power/runtime_status
cat /sys/bus/pci/devices/0000:01:00.0/power_state
cat /sys/bus/pci/devices/0000:00:01.0/power/runtime_status
```

Expect no Nouveau module or GPU driver binding, `auto`, `suspended`, `D3cold`,
and a suspended bridge. An unbound GPU's runtime status alone is insufficient:
verify the actual power state and compare idle battery discharge under the
same conditions. Repeat after suspend/resume and with external displays.
GPU-wired display outputs may become unavailable. If it remains powered or
display/resume behavior regresses, boot the unchanged entry. Do not remove
Nouveau from the kernel build until this experiment passes.

PCI sysfs `remove` only removes the device from Linux's device list; it does
not guarantee power-off. See the [kernel PCI sysfs documentation](https://docs.kernel.org/PCI/sysfs-pci.html).

Review configuration-protected files with `dispatch-conf`. Keep agentoo defaults
when an incoming file only restores an upstream example; assess substantive
package changes. Thinktop's installer firmware policy already selects SOF
firmware, but verify it is installed and loaded on this target. A successful
dependency plan does not establish audio or graphics hardware support.

## Verify the normal user session

Log in as the desktop user on a real TTY, rather than through `su`, `sudo`, or
an SSH session. Before launching:

```sh
printf '%s\n' "$XDG_RUNTIME_DIR" "$DBUS_SESSION_BUS_ADDRESS"
loginctl session-status
systemctl --user status
busctl --user list
```

Verify `/run/user/$(id -u)` exists with the user's ownership, the login belongs
to the active local seat, and the user manager and session bus work. Diagnose
PAM/logind/user-service failures before adding launch wrappers. Do not inherit
the historical systemd-userdbd mask, sleep, or UWSM workaround.

Hyprland 0.56.2 imports its session environment into systemd and D-Bus and clears
it on clean exit. Its systemd build also sends readiness notification when
applicable. Plain TTY launch does **not** by itself start a managed
`hyprland.service` or `graphical-session.target`. This base has no services
requiring that graphical target; add session management only for an observed need.

## Audio startup and compatibility

Run these commands as the desktop user after verifying their user manager:

```sh
systemctl --user enable --now pipewire.service pipewire-pulse.socket wireplumber.service
systemctl --user status pipewire.socket pipewire-pulse.socket wireplumber.service
wpctl status
```

These are real, local systemd enablement links managed by systemd, not copied
user dotfiles. To choose the same default for every user, root may instead use
`systemctl --global enable pipewire.service pipewire-pulse.socket wireplumber.service`;
activate and verify the units from each normal user login. No lingering is needed.

Enable `pipewire.service` at user login; its unit also enables `pipewire.socket`.
Enabling only the sockets delays PipeWire and WirePlumber initialization until
the first client connects. On thinktop this produced an empty first
`wpctl status` and a mic LED transition when audio initialized. Starting the
service at login avoids that client-triggered startup, though device discovery
is still asynchronous. The LED before user login is kernel/firmware behavior.

If inspection finds an existing PulseAudio daemon or pipewire-media-session,
review and disable that user's competing units before starting the new stack.
Do not run PipeWire or WirePlumber as system services. Gentoo's `sound-server`
USE installs its WirePlumber audio enabler and supplies pipewire-pulse, the
PulseAudio protocol server; `pulseaudio` USE supplies libpulse integration.
ALSA clients use PipeWire through `pipewire-alsa`. Do not install a second audio
server or add an autostart launcher alongside systemd.

`@gui-base` also includes `media-sound/alsa-utils` for alsactl's privileged
ALSA/UCM initialization and mixer-state handling, plus diagnostic tools. This
is separate from the PipeWire audio server. UCM boot sequences can associate
hardware mute LEDs with ALSA controls through root-only sysfs attributes;
user-session WirePlumber alone cannot perform those writes. On thinktop,
manually applying the installed UCM's speaker LED associations restored F1 LED
tracking. After installing alsa-utils and rebooting, the user confirmed automatic
F1 LED tracking; the packaged startup path attached the amplifier controls without
the manual script. Verify this on other targets before adding custom LED
workarounds. Inspect `alsa-restore.service`, `alsa-state.service` and the packaged
udev rules rather than enabling both state-management schemes blindly.

### Check services and devices

Run all audio commands below as the normal desktop user inside Kitty, without
sudo. Check socket activation, running services, and device discovery:

```sh
systemctl --user status pipewire.socket pipewire-pulse.socket wireplumber.service
wpctl status
pactl info
systemctl --user status pipewire.service pipewire-pulse.service
pactl list short sinks
pactl list short sources
```

The sockets should be listening and WirePlumber running. After the clients have
connected, both PipeWire services should be running. `pactl info` should identify
the server as `PulseAudio (on PipeWire ...)`, confirming that these PulseAudio
clients use PipeWire. In `wpctl status`, check that the desired playback sink and
microphone source exist and have the default marker (`*`). A source named
`*.monitor` records speaker output rather than the physical microphone.

If the wrong device is selected, use the numeric **sink/source node IDs** shown
by `wpctl status`, rather than the card/device IDs. Replace these placeholders:

```sh
wpctl set-default <sink-node-id>
wpctl set-default <microphone-node-id>
```

Check mute and volume before playback or recording:

```sh
wpctl get-volume @DEFAULT_AUDIO_SINK@
wpctl get-volume @DEFAULT_AUDIO_SOURCE@
```

If muted, unmute the intended device. Start playback at a modest level and
adjust microphone gain as needed:

```sh
wpctl set-mute @DEFAULT_AUDIO_SINK@ 0
wpctl set-volume @DEFAULT_AUDIO_SINK@ 25%
wpctl set-mute @DEFAULT_AUDIO_SOURCE@ 0
```

### Test speakers, microphone, and controls

The installed freedesktop channel-announcement samples are **mono**, despite
living under `stereo/`. Plain playback normally sends them to both speakers.
Route each explicitly without upmixing for a browser-free channel test:

```sh
paplay --channel-map=front-left --no-remix /usr/share/sounds/freedesktop/stereo/audio-channel-front-left.oga
paplay --channel-map=front-right --no-remix /usr/share/sounds/freedesktop/stereo/audio-channel-front-right.oga
```

Confirm audible playback from the expected left/right speakers or headphones.
Speak into the microphone while this command records, then press Ctrl+C:

```sh
parec --device=@DEFAULT_SOURCE@ --file-format=wav /tmp/mic-test.wav
```

Replay the recording and confirm your speech is audible and clear:

```sh
paplay /tmp/mic-test.wav
```

Try the Hyprland volume-up/down, speaker-mute, and microphone-mute keys. Check
the resulting levels with `wpctl get-volume` and unmute before further tests.
These playback/recording commands exercise PulseAudio compatibility through
PipeWire. Native `pw-play`/`pw-record` require PipeWire's optional `extra` USE flag,
which this base does not enable.

For the separate ALSA compatibility check, use `aplay` if available:

```sh
aplay -L
aplay -D default /tmp/mic-test.wav
```

Confirm the default ALSA device uses the installed PipeWire ALSA configuration
and your recording plays. Avoid `-D hw:...`, which bypasses the compatibility
path. If `aplay` is absent on an installation predating the updated `@gui-base`,
install `media-sound/alsa-utils` as root with
`emerge --ask media-sound/alsa-utils`, then run the tests as the normal user.

### Check recovery and diagnose failures

After each manual or lid-triggered suspend/resume, repeat `wpctl status`, the
speaker test, and microphone record/replay. Verify that the intended devices
return and controls still work. Also verify startup after a fresh normal login.
Record the results in the open card; hearing a startup sound alone does not
establish microphone or resume correctness.

For connection failures, inspect the user services and session checks above.
For missing devices, inspect ALSA discovery and user-service logs:

```sh
cat /proc/asound/cards
journalctl --user -b -u pipewire.service -u pipewire-pulse.service -u wireplumber.service
```

If the kernel exposes no expected card, check audio driver/firmware errors as
root with `journalctl -k -b`, including SOF firmware on thinktop. If devices
exist but sound is absent, check default node selection, mute, volume, and the
selected profile/route before changing configuration. Preserve the relevant
output when reporting a failure.

Warnings from `mod.rt` reporting RTKit `ServiceUnknown` mean the optional
real-time scheduling service is unavailable. They do not indicate broken device
discovery or explain channel mixing. PipeWire can use process resource limits,
the realtime portal, or RTKit to obtain real-time scheduling; these warnings
alone do not establish the server threads' scheduling policy. If audio is stable,
record the limitation and continue testing. If playback/recording drops out under
load, inspect scheduling and consider Gentoo's optional `sys-auth/rtkit` package
after reviewing its dependency plan. Avoid adding services just to silence a
short-lived `wpctl` client's warnings. See the
[PipeWire realtime module documentation](https://docs.pipewire.org/page_module_rt.html).

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
[the historical Omarchy notes](omarchy-configuration-changes.md#1-keep-the-closed-laptop-awake-during-monitor-inputpbp-switching).
If monitor reconfiguration also removes external power, the battery lid policy
can still suspend the laptop; this rule adds no timed disconnect grace period.
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

## Configuration and launch

Hyprland 0.56.2 with hyprutils 0.14.2 discovers
`/etc/xdg/hypr/hyprland.lua` as its system fallback. No file in the user's home
is required. The shared entry loads, in order:

1. `/etc/xdg/hypr/agentoo.lua`: tracked universal defaults and bindings.
2. `/etc/xdg/hypr/hosts/NAME.lua`, when present, selected automatically by the
   existing installer-managed `/etc/agentoo/target-host`.
3. `$XDG_CONFIG_HOME/hypr/agentoo-local.lua`, or
   `~/.config/hypr/agentoo-local.lua`: optional real personal override.
4. `/etc/xdg/hypr/transparency.lua`: remembered Agentoo transparency overrides,
   when present. Resetting them exposes the preceding authored settings.

Monitors use preferred modes and auto placement/scaling by default. Host-specific
exceptions belong in tracked `/etc/xdg/hypr/hosts/NAME.lua` fragments. The shared
entry reads the documented `GENTOO_TARGET_HOST="name"` assignment from
`/etc/agentoo/target-host` as data and loads that host's fragment if present.
The installer already creates this one local host identity; no separate Hyprland
selector or manual include is needed. Missing selectors/fragments retain shared
defaults; malformed selectors produce a configuration error. The former
`/etc/agentoo/hyprland-host.lua` selector is no longer read and may be removed.
Personal scalar settings override earlier values; bindings and
monitor rules have their own semantics, so check duplicates when extending them.

An existing personal `hyprland.lua` takes precedence over the system Lua entry.
In this release Lua discovery is attempted before legacy `.conf` discovery,
so the system Lua entry can also supersede an old personal `hyprland.conf`.
Inspect old configuration before the first launch. A user choosing their own
real entry can include the shared entry with
`require("/etc/xdg/hypr/hyprland.lua")`; never copy or symlink the shared defaults.
`HYPRLAND_CONFIG` or `--config` can also select a different entry explicitly.

Check the installed parser as the normal user, then launch:

```sh
Hyprland --verify-config --config /etc/xdg/hypr/hyprland.lua
start-hyprland
```

For an explicit first test of the shared entry despite another selected config,
use `start-hyprland -- --config /etc/xdg/hypr/hyprland.lua`. `--` passes arguments
through the packaged watchdog launcher. Check `hyprctl configerrors` inside the
session. `require()` tracks included files for reload; run `hyprctl reload` after
creating a previously absent optional file.

| Binding | Action |
|---|---|
| Super+Enter | Kitty |
| Super+grave (backtick) | Show / hide the persistent terminal overlay |
| Super+Q | Close active window |
| Super+Shift+E | Exit Hyprland |
| Super+F / Super+V | Toggle fullscreen / floating |
| Super+arrows / Super+Shift+arrows | Focus / move window |
| Super+1…0 / Super+Shift+1…0 | Workspace 1…10 / move window there |
| Super+left/right mouse drag | Move / resize |
| Audio volume, mute, mic-mute keys | WirePlumber controls |
| Display brightness up/down keys | acpilight, 5 points on its perceived scale; repeats while held |
| Print Screen | PNG capture of all outputs |
| Shift+Print Screen / region-capture key | Select a rectangular region; Escape cancels |

Caps Lock acts as Control, matching the shared console keymap. The background
is plain dark gray.

The terminal overlay uses a named special workspace and launches Kitty on demand.
It requests 160 columns by 45 rows, centered horizontally with its top edge
15% of the monitor height from the top. Hiding it keeps the shell and running
programs alive; closing the terminal lets the next toggle create a fresh one.
The cell size follows the normal Kitty font settings; the requested geometry
requires enough monitor space at the selected font size and display scale.

### Laptop brightness

Laptop utilities live in the independent `@laptop` set, initially containing
`sys-power/acpilight`; keep future sensor/power utilities here when selected.
Do not require this set on desktops. As root, install `emerge --ask @laptop`
The user setup script `/root/002-agentoo-setup-user.sh` installs the packaged
`video` group and adds Graham on initial setup and reruns. For existing users
without rerunning setup, use `usermod -aG video USER` as root.
Log out completely and log back in for group membership to take effect.
The package supplies backlight udev permissions; reboot after first installation
or reload rules and trigger the backlight add event before testing.

Despite its command name `xbacklight`, acpilight uses sysfs and needs neither X
nor sudo in the key bindings. Shared bindings use standard brightness key symbols,
not laptop F-key positions. `agentoo backlight` selects a single display backlight
under `/sys/class/backlight`, quietly does nothing if none exists, and refuses an
ambiguous selection when multiple devices exist. A host override can replace the
bindings with `agentoo backlight up CONTROLLER` and `down CONTROLLER`.
Keyboard LEDs are never selected as a display fallback.

Adjustments use acpilight's perceived scale in steps of 5, bounded by the utility
to 0–100 on that scale (minimum raw level 1, not panel-off). Inspect controllers
with `xbacklight -list`; run `agentoo backlight down` and `up` as the normal user
before testing the physical keys. Confirm visible changes, held-key repetition,
usable minimum and maximum levels, and recovery after suspend/resume. A low
resolution or unsuitable panel curve may need a host-specific adjustment.

### Screenshots

`@gui-desktop` extends `@gui-base` with desktop conveniences, initially
`gui-apps/grim`, `gui-apps/slurp`, and `gui-apps/swaybg`. Install it with
`sudo emerge --ask @gui-desktop`; keep `@gui-base` as the minimal graphics/audio
foundation and `@laptop` as an independent hardware-utility set. Run
`agentoo screenshot full` to capture all outputs in one image, or
`agentoo screenshot region` to drag a rectangle. Files are saved under
`~/Downloads/Screenshots`, created on demand, with timestamped unique PNG names
and owner-only file permissions. The helper neither copies to the clipboard nor
starts a background service. Cancellation or capture failure leaves no image.
Region selection is live, not a frozen preview. Test these commands from a normal
user's Hyprland terminal after installing the updated set, then test the keys.

Thinktop's physical F9 emits Print Screen; its F10 becomes Linux KEY_F16 through
keyd, then XF86Launch7 in the default evdev XKB map. The tracked
`/etc/xdg/hypr/hosts/thinktop.lua` binds that XF86Launch7 region alias and is
loaded automatically when the existing target-host assignment names thinktop.
Reload Hyprland after deployment. Other hosts use Print Screen,
Shift+Print Screen or the standard region-capture symbol unless a demonstrated
input quirk requires a host alias. Do not bind ordinary F10 universally.

## Physical acceptance on thinktop

Record hardware, kernel, graphics driver, audio firmware, package/overlay
versions, commands, and outcomes in the open card. Complete all of the following:

1. Normal TTY login, parser check, launch, Kitty, window/workspace operations,
   volume keys, and no unexpected configuration errors.
2. Check the intended sink/source in `wpctl status` and confirm `pactl info`
   identifies PipeWire's PulseAudio compatibility server. Test audible playback
   with the explicitly routed left/right sample commands in the audio section.
   Capture speech with
   `parec --device=@DEFAULT_SOURCE@ --file-format=wav /tmp/mic-test.wav`
   (stop with Ctrl+C), then replay with `paplay /tmp/mic-test.wav`. These exercise
   PulseAudio compatibility through PipeWire; also test an available ALSA client.
   `pw-play`/`pw-record` require PipeWire's optional `extra` USE flag and are not
   included by this base.
3. `systemctl suspend`, resume, and repeat several times. Check graphics,
   keyboard/touchpad, microphone/playback, and dhcpcd/wpa_supplicant recovery.
4. Lid-close suspend and lid-open resume. Inspect `systemd-analyze cat-config
   systemd/logind.conf` and `systemd-inhibit --list`; verify packaged lid policy,
   including docked/external-display behavior when applicable. Add a logind
   drop-in only for a demonstrated host requirement. Hyprland's lid handler
   routes outputs only; logind remains the sole suspend-policy owner.
5. Close applications, exit, and relaunch. Compare `systemctl --user
   show-environment` inside and after the session for stale Wayland variables,
   inspect `pgrep -a -u "$(id -u)" -f 'Hyprland|start-hyprland|kitty'`, and review
   `journalctl --user -b`. Audio user services can persist for the TTY login;
   compositor/watchdog and closed graphical clients should not.

Do not mark the card complete until these physical checks succeed. Repository
syntax and pretend checks do not establish installability at build time or
hardware correctness. Legacy package sets remain historical references pending
a separate review of their remaining package requirements; do not install
`@hyprland_env` as part of this base or depclean its packages automatically.

## Packaging evidence and keyword review

Repository preparation on 2026-10-14 used Gentoo commit
`9ef593f1a819cdc0465b29afb11d03bac79ad5f8` and hyproverlay commit
`b2e7344722289a04ec5ccab6957a83597cd13048`. A pretend check with the desktop/systemd
profile, Intel video selection, and isolated configuration/cache selected
Hyprland 0.56.2, Kitty 0.48.2, PipeWire 1.6.8, and WirePlumber 0.5.15.
Ten exact overlay keyword exceptions sufficed for that initial check; no shared
Gentoo library needed testing acceptance. These exceptions now apply across
release versions of the same overlay packages. Re-run the plan on thinktop
after sync: installed packages,
local overrides, and repository updates can change it.

All previous keyword exceptions were reviewed. The four retained original common
exceptions are repository-scoped Agentoo secret/AI packages with testing keywords.
Independently added scoped keyd/group exceptions are preserved; neither package
is selected by `@gui-base`. Removed exceptions
cover gentoo-sources (stable versions exist; the maintained kernel policy uses
gentoo-kernel-bin), obsolete broad Hyprland/glaze acceptance, unselected hyprpaper,
GUI utilities/toolkit, unscoped legacy keyd acceptance, cliphist, and stable
Wayland libraries/scanner.
Removing acceptance does not uninstall packages. Inspect any existing testing
installations and subsequent world update plan separately.

Sources inspected for the selected release:

- [Hyproverlay packaging](https://codeberg.org/hyproverlay/hyproverlay/src/commit/b2e7344722289a04ec5ccab6957a83597cd13048/gui-wm/hyprland/hyprland-0.56.2.ebuild)
- [Hyprland 0.56.2 source and example](https://github.com/hyprwm/Hyprland/tree/v0.56.2)
- [Hyprutils 0.14.2 configuration discovery](https://github.com/hyprwm/hyprutils/blob/v0.14.2/src/path/Path.cpp)
- [Gentoo PipeWire ebuild and user-service guidance](https://github.com/gentoo/gentoo/blob/9ef593f1a819cdc0465b29afb11d03bac79ad5f8/media-video/pipewire/pipewire-1.6.8.ebuild)

## Static wallpapers

`@gui-desktop` includes swaybg with `gdk-pixbuf` image loading for JPEG, WebP,
PNG, and other installed loader formats. Install or update the set with
`sudo emerge --ask @gui-desktop`. Wallpaper commands run as the normal user:

```sh
agentoo desktop wallpaper set ~/Pictures/mountains.jpg
agentoo desktop wallpaper
agentoo desktop wallpaper clear
agentoo help desktop wallpaper
```

`set FILE` displays one image across all monitors using fill scaling and remembers
its absolute path, without copying the image. With no subcommand, `wallpaper`
prints the remembered path, or nothing when none is selected. The system-owned
collection lives at `/usr/local/share/agentoo/wallpapers/`, grouped into ordinary
subdirectories as useful. No images or default selection are bundled yet.
Personal images can live anywhere readable.

The selection is a text file at `$XDG_STATE_HOME/agentoo/wallpaper`, defaulting to
`~/.local/state/agentoo/wallpaper`; relative XDG paths are ignored. This is local
user state outside Git. The helper atomically replaces the file and serializes
changes with a lock beside it. It does not generate user configuration files.

The shared `/etc/xdg/hypr/agentoo.lua` registers `agentoo desktop wallpaper restore`
on `hyprland.start`, which runs once per session rather than on config reload.
With no saved image, restore quietly succeeds, including when swaybg is not
installed. A missing remembered image produces a warning and exit 1, retaining
the path for a later retry. New sessions retain the solid background in this case.
`clear` removes the selection and stops Agentoo's wallpaper processes, exposing
the compositor's background; it also works outside Wayland.

Setting/restoring an image requires a running Wayland session and an absolute
`XDG_RUNTIME_DIR`. Process records and swaybg diagnostic logs live under
`$XDG_RUNTIME_DIR/agentoo/`, separately for each Wayland display. Only recorded
processes with matching Linux start times are stopped, using PID descriptors to
avoid PID reuse races. Independently started swaybg instances are untouched.
The client exits when its compositor connection closes; no user service is added.

A replacement starts before the previous managed client stops. The helper checks
for immediate process or image-loader errors for half a second before remembering
the choice. swaybg provides no readiness acknowledgement: a delayed load or
rendering error can still occur afterward. Inspect the runtime log if an image
does not appear. Failed initial checks retain the previous selection and client.

Help and queries do not start clients or create state. Results go to stdout;
change summaries, warnings and errors go to stderr. Exit codes are 0 for success,
1 for operational failure, and 2 for invalid arguments. `agentoo-desktop` is also
independently runnable. Tab completion derives commands and file arguments from
the same parser as help.

After deployment and installation, test set, replacement, query, clear, logout,
and startup restoration in a real Hyprland session. Confirm ordinary config
reloads do not create another swaybg process, images appear on connected and
newly attached monitors, and clients exit on session shutdown. Repository tests
use a fake client and do not establish physical rendering correctness.

## Window transparency

```sh
agentoo desktop transparency
agentoo desktop transparency --focused 5 --unfocused 10
agentoo desktop transparency --window kitty --unfocused 20
agentoo desktop transparency --window browser --focused 0 --unfocused 0
agentoo desktop transparency --window browser --reset
agentoo desktop transparency --reset
```

Percentages measure transparency: 0 is opaque, 90 is the maximum, and fractional
percentages are accepted. Focused and unfocused values change independently.
Without adjustment options or `--reset`, the command prints settings without
creating state or changing windows. `--window` defaults to `all`; a query of
`all` shows all three groups with override, inherited, or configured-default
sources. Queries without a reachable compositor show saved values and label
unavailable defaults as `configured default` rather than guessing them.

Setting `all` clears Kitty/browser overrides for each supplied focus state.
An omitted focus state retains its shared value and category overrides.
Resetting Kitty or browser removes that category's overrides, restoring shared
inheritance. Resetting all removes every override and restores authored defaults,
including personal configuration. `--reset` cannot accompany either percentage.
Shared defaults currently set no opacity, so absent host or personal settings
the underlying defaults are fully opaque.

Transparency is saved at `$XDG_STATE_HOME/agentoo/transparency.json`, defaulting
to `~/.local/state/agentoo/transparency.json`; relative XDG paths are ignored.
This is personal, untracked state, like the wallpaper selection. Updates use a
private directory, atomic replacement, and an exclusive `transparency.lock`.
Hyprland reads the JSON through a validating Python helper at startup and every
configuration reload; there is no separate restore command or generated config
to keep in sync. Updates require the shared integration in a running Hyprland
session, reload configuration without reconfiguring monitors, and restore the
previous saved record if reload fails. Operational messages go to stderr,
queries/help to stdout, and exit status is 0/1/2 for success/failure/invalid input.
Help and completion use the command's shared parser and require no session.

Hyprland uses absolute, focus-specific opacity rules for normal, floating,
dialog, fullscreen, and dropdown windows. Layer surfaces such as panels and
notifications and compositor/application popup menus are not targeted. Kitty
uses native **background-only** transparency, preserving text opacity. A shared
Kitty watcher tracks focus and notices saved changes within approximately 250ms,
without external remote-control permissions, sockets, or an extra daemon.
Reset re-reads Kitty's configuration, including its original command-line
overrides, before restoring background opacity. Kitty backgrounds supplied by an
application or background images follow Kitty's own transparency limitations.

Kitty must start with `dynamic_background_opacity yes` and the shared watcher.
The shared configuration provides both; personal settings can override them.
Kitty processes started before installation need a one-time restart: a reload
cannot retrofit dynamic opacity reliably. No running application is restarted
by this command. Kitty's standard `kitty` class and `agentoo-dropdown` are
recognized by the compositor. Browser classes include Firefox, Chromium,
Chrome, Brave, Edge, Vivaldi, Opera, LibreWolf, Floorp, and Zen. Custom application
classes require extending the class expressions in `transparency.lua`.

Authored window opacity/opaque/force_rgbx rules in the personal Hyprland config
tree and selected host file cause adjustments to fail with file/line locations;
they are never rewritten. Queries warn about them. This scan is conservative:
unused files in the personal tree may be reported, while dynamically constructed
Lua or includes outside those locations require manual inspection. Decoration
opacity settings and Kitty `background_opacity` are underlying defaults, not
conflicts. A full reset remains available even with conflicting rules or a
damaged state file. Separate sessions share the saved choice; a different
already-running Hyprland session picks it up on its next configuration reload.

Verification: run `python3 -m unittest discover -s usr/local/share/agentoo/tests
-p test_transparency.py`, `lua usr/local/share/agentoo/tests/test_hypr_transparency.lua`,
and the CLI/wallpaper tests. Before deployment is considered visually validated,
check focus changes, existing/new Kitty windows, browser dialogs, fullscreen,
the dropdown, personal defaults after reset, and logout/login in a real session.
Parser and mocked API tests do not establish actual rendering correctness.

Implementation references: [Hyprland 0.56.2 opacity parser](https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/desktop/rule/windowRule/WindowRule.cpp),
[window rules](https://wiki.hypr.land/configuring/core/rules/window-rules/),
and Kitty's installed 0.48.2 watcher and background-opacity documentation
(`/usr/share/doc/kitty-0.48.2/html/launch.html` and `conf.html`).
