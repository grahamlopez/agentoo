# Minimal Hyprland base

The base selects Hyprland from hyproverlay, Kitty, PipeWire, and WirePlumber.
Hyprland and its listed overlay dependencies accept testing release updates
without exact version pins. Unkeyworded live ebuilds and package masks remain
excluded by the normal Portage policy. Preview updates after syncing; new
dependencies may require additional package-specific keyword decisions.
The system automatically logs graham in on tty1 and starts `start-hyprland`.
Other users and TTYs can launch it explicitly with `start-hyprland`.
There is no greeter, UWSM, XWayland, launcher, panel,
notification daemon, portal, wallpaper daemon in the base, or screen locker. Suspend and
lid-close suspend belong to systemd/logind. Hyprland routes displays for docked
lid use as described below. Resume returns to an unlocked session.
Networking remains dhcpcd and wpa_supplicant.

## Automatic login and console recovery

`/etc/systemd/system/getty@tty1.service.d/autologin.conf` adds graham autologin
to the packaged getty command. `/etc/zsh/zprofile` launches Hyprland only for
graham (UID 1000), in an interactive login shell on tty1, with no existing
Wayland or X display. It calls the launcher without `exec`: when it returns,
including after a startup failure, a shell remains available. There is no retry
loop. Logging out of that shell starts a fresh autologin and desktop attempt.
Personal Zsh startup files still run after the system login profile.

`/etc/systemd/system/getty.target.d/50-recovery-console.conf` requests a separate
normal password login on tty2. It needs no enablement symlink. After deploying,
run as root:

```sh
systemctl daemon-reload
systemctl start getty@tty2.service
```

Before rebooting, press Ctrl+Alt+F2 and verify a working login as graham with
sudo, and/or root with its password. A root login also bypasses graham's personal
shell configuration. Do not restart tty1's getty from its active session; the
autologin change takes effect on the next boot or getty restart.

If the desktop hangs or its configuration is unusable, switch to tty2. To skip
automatic Hyprland startup, run as graham:

```sh
touch ~/.disable-hyprland-autostart
```

Remove that file to restore startup. Manual `start-hyprland` remains available.
If autologin itself fails, tty2 still provides a normal login prompt. To remove
autologin permanently, remove the tty1 drop-in and run `systemctl daemon-reload`;
also disable the profile's automatic desktop launch if a manual tty1 login
should remain a console.

For boot recovery, append `systemd.unit=rescue.target` to the kernel command
line for one boot and authenticate as root. Verify root's password before
relying on this route. Console switching cannot recover a kernel or GPU hard
lock. Autologin grants physical users access to graham's session after boot;
this setup does not add a screen locker.

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

## Audio and displays

See [audio setup and diagnostics](audio.md) and [external displays, HiDPI, and laptop lid behavior](displays.md).

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
5. `/etc/xdg/hypr/blur.lua`: remembered Agentoo blur preferences; authored blur
   defaults remain in effect until a preference is explicitly set.
6. `/etc/xdg/hypr/effects.lua`: remembered corners, gaps, borders, animations,
   shadows, and dimming preferences, applied after authored defaults.

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

Run `agentoo display off` to turn off all display outputs through DPMS without
locking or suspending. It waits one second for key release, allowing monitors
to enter standby. Shared defaults enable keyboard wake and disable mouse wake
for both built-in panels and external monitors.

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
| Alt+Tab / Alt+Shift+Tab | Cycle recent windows forward / backward, including the visible dropdown |
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

`/etc/xdg/hypr/alt-tab.lua` tracks focus history for the active monitor's regular
workspace and includes the terminal overlay while it is visible. Press and
release Alt+Tab to bounce between the two most recent windows. Hold Alt and press
Tab again to advance through a frozen snapshot of that history; Shift+Tab moves
backward. Releasing the last Alt key commits the actual focused window. Closed,
hidden and moved windows are skipped; new windows join the next gesture.
Reloading seeds history from Hyprland's current focus order. This fragment uses
the standard evdev left/right Alt keycodes, matching Agentoo's US keyboard layout.
Run `lua usr/local/share/agentoo/tests/test_hypr_alt_tab.lua` from the checkout
for the mocked switching checks. On a live session, check two-window bouncing,
held-Alt multi-window cycling, reverse cycling, mouse focus, closing a candidate,
and cycling with the dropdown shown and hidden.

The terminal overlay uses a named special workspace and launches Kitty on demand.
It requests 160 columns by 45 rows, centered horizontally with its top edge
15% of the monitor height from the top. Hiding it keeps the shell and running
programs alive; closing the terminal lets the next toggle create a fresh one.
New application windows opened in the dropdown workspace are moved to the
regular workspace on that monitor, so hiding the dropdown leaves them visible.
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
not laptop F-key positions. `agentoo display backlight` selects a single display backlight
under `/sys/class/backlight`, quietly does nothing if none exists, and refuses an
ambiguous selection when multiple devices exist. A host override can replace the
bindings with `agentoo display backlight up CONTROLLER` and `down CONTROLLER`.
Keyboard LEDs are never selected as a display fallback.

Adjustments use acpilight's perceived scale in steps of 5, bounded by the utility
to 0–100 on that scale (minimum raw level 1, not panel-off). Inspect controllers
with `xbacklight -list`; run `agentoo display backlight down` and `up` as the normal user
before testing the physical keys. Confirm visible changes, held-key repetition,
usable minimum and maximum levels, and recovery after suspend/resume. A low
resolution or unsuitable panel curve may need a host-specific adjustment.

### Clipboard history

`@gui-desktop` supplies `app-misc/cliphist::guru`, wl-clipboard, and fzf;
Kitty comes from `@gui-base`. GURU is masked except for cliphist. Sync it with
`sudo emaint sync -r guru` before installing the set.

At Hyprland startup, `wl-paste --type text --watch cliphist store` captures
text copies. Reloading configuration does not start another watcher. After
deployment, log out and back in to start capture, or run that command once in
a terminal for the current session.

Press **Ctrl+0** to search history in a floating Kitty/fzf window. Enter restores
the selected entry to the desktop clipboard; Escape cancels without changing it.
Shift+Delete deletes the highlighted history entry and refreshes the list;
it leaves the active clipboard unchanged. Backspace and Delete edit the search
query normally. The window closes when the picker exits. Paste normally, for example with
Ctrl+Shift+V in Kitty or `p` in Neovim. tmux's Ctrl+A, ] still reads its own
buffer; history selection does not update it.

The picker follows [cliphist's upstream fzf recipe](https://github.com/sentriz/cliphist#picker-examples).
Decoding restores original whitespace and multiline content rather than the
one-line preview. Images are not captured by this text-only watcher.
Installed cliphist 0.7.0 defaults to 750 entries, stored in
`${XDG_CACHE_HOME:-~/.cache}/cliphist/db`, retained across logins until evicted
or cleared. Run `cliphist wipe` to clear history; the active desktop clipboard
is separate. Configure cliphist through its native user configuration if needed.

Verify copies from graphical applications, Neovim, and tmux appear in the picker;
restore an older multiline entry and check whitespace and Unicode. Check Escape
preserves the current clipboard, and confirm a fresh login starts capture and
configuration reloads leave only one watcher.

### Screenshots

`@gui-desktop` extends `@gui-base` with desktop conveniences, initially
screenshots, wallpapers, and text clipboard history. Install it with
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
hardware correctness. The [archived package lists](history/package-sets/README.md) remain historical
references pending review of their remaining requirements. They are not active
Portage sets; do not install or depclean packages automatically from them.

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

## Desktop preferences

See [wallpapers, transparency, blur, and desktop appearance](desktop.md).
