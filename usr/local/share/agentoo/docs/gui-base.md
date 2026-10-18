# Minimal Hyprland base

The base selects Hyprland from hyproverlay, Kitty, PipeWire, and WirePlumber.
Hyprland and its listed overlay dependencies accept testing release updates
without exact version pins. Unkeyworded live ebuilds and package masks remain
excluded by the normal Portage policy. Preview updates after syncing; new
dependencies may require additional package-specific keyword decisions.
Launch it explicitly from a normal user's TTY login with `start-hyprland`.
There is no automatic startup, greeter, UWSM, XWayland, launcher, panel,
notification daemon, portal, wallpaper daemon, or screen locker. Suspend and
lid handling belong to systemd/logind. Resume returns to an unlocked session.
Networking remains dhcpcd and wpa_supplicant.

## Before pulling on thinktop

Inspect the current installed packages, local Portage settings, Hyprland/user
configuration, and enabled user services. Preserve the working state before
the pull, since agentoo's live work tree is `/` and a pull changes configuration.
With package/configuration writers idle, as root:

```sh
agentoo git status --short
agentoo checkpoint create before-gui-base --no-clean-distfiles
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

## Configuration and launch

Hyprland 0.56.2 with hyprutils 0.14.2 discovers
`/etc/xdg/hypr/hyprland.lua` as its system fallback. No file in the user's home
is required. The shared entry loads, in order:

1. `/etc/xdg/hypr/agentoo.lua`: tracked universal defaults and bindings.
2. `/etc/agentoo/hyprland-host.lua`: optional, untracked explicit host selector.
3. `$XDG_CONFIG_HOME/hypr/agentoo-local.lua`, or
   `~/.config/hypr/agentoo-local.lua`: optional real personal override.

No host fragment is selected initially: monitors use preferred modes and auto
placement/scaling. When hardware testing establishes a need, add a small tracked
Lua fragment under `/etc/xdg/hypr/hosts/` and select it explicitly with a real
local `/etc/agentoo/hyprland-host.lua` containing, for example,
`require("/etc/xdg/hypr/hosts/thinktop.lua")`. Create the referenced fragment first.
This selector is independent of the shell-format Portage `target-host` file.
Personal scalar settings applied last override earlier values; bindings and
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
| Super+Q | Close active window |
| Super+Shift+E | Exit Hyprland |
| Super+F / Super+V | Toggle fullscreen / floating |
| Super+arrows / Super+Shift+arrows | Focus / move window |
| Super+1…0 / Super+Shift+1…0 | Workspace 1…10 / move window there |
| Super+left/right mouse drag | Move / resize |
| Audio volume, mute, mic-mute keys | WirePlumber controls |
| Display brightness up/down keys | acpilight, 5 points on its perceived scale; repeats while held |

Caps Lock acts as Control, matching the shared console keymap. The background
is plain dark gray.

### Laptop brightness

Laptop utilities live in the independent `@laptop` set, initially containing
`sys-power/acpilight`; keep future sensor/power utilities here when selected.
Do not require this set on desktops. As root, install `emerge --ask @laptop`
and add each intended desktop user to `video` with `usermod -aG video USER`.
Log out completely and log back in for group membership to take effect.
The package supplies backlight udev permissions; reboot after first installation
or reload rules and trigger the backlight add event before testing.

Despite its command name `xbacklight`, acpilight uses sysfs and needs neither X
nor sudo in the key bindings. Shared bindings use standard brightness key symbols,
not laptop F-key positions. `agentoo-backlight` selects a single display backlight
under `/sys/class/backlight`, quietly does nothing if none exists, and refuses an
ambiguous selection when multiple devices exist. A host override can replace the
bindings with `agentoo-backlight up CONTROLLER` and `down CONTROLLER`.
Keyboard LEDs are never selected as a display fallback.

Adjustments use acpilight's perceived scale in steps of 5, bounded by the utility
to 0–100 on that scale (minimum raw level 1, not panel-off). Inspect controllers
with `xbacklight -list`; run `agentoo-backlight down` and `up` as the normal user
before testing the physical keys. Confirm visible changes, held-key repetition,
usable minimum and maximum levels, and recovery after suspend/resume. A low
resolution or unsuitable panel curve may need a host-specific adjustment.

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
   drop-in only for a demonstrated host requirement; no competing lid handler.
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
