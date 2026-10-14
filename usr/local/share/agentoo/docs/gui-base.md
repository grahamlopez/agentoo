# Minimal Hyprland base

The initial base selects Hyprland 0.56.2, Kitty, PipeWire, and WirePlumber.
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
agentoo-git status --short
agentoo-checkpoint create before-gui-base --no-clean-distfiles
agentoo-checkpoint list
agentoo-checkpoint inspect <exact-checkpoint-name>
```

Confirm the checkpoint completed and retain its exact name. See
[checkpoint and recovery procedures](checkpoints.md). Reconcile live edits,
then pull the reviewed commit with `agentoo-git pull`.

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
systemctl --user enable --now pipewire.socket pipewire-pulse.socket wireplumber.service
systemctl --user status pipewire.socket pipewire-pulse.socket wireplumber.service
wpctl status
```

These are real, local systemd enablement links managed by systemd, not copied
user dotfiles. To choose the same default for every user, root may instead use
`systemctl --global enable pipewire.socket pipewire-pulse.socket wireplumber.service`;
activate and verify the units from each normal user login. No lingering is needed.

If inspection finds an existing PulseAudio daemon or pipewire-media-session,
review and disable that user's competing units before starting the new stack.
Do not run PipeWire or WirePlumber as system services. Gentoo's `sound-server`
USE installs its WirePlumber audio enabler and supplies pipewire-pulse, the
PulseAudio protocol server; `pulseaudio` USE supplies libpulse integration.
ALSA clients use PipeWire through `pipewire-alsa`. Do not install a second audio
server or add an autostart launcher alongside systemd.

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

Caps Lock acts as Control, matching the shared console keymap. The background
is plain dark gray. No brightness utility or display-specific workaround is
selected in this base.

## Physical acceptance on thinktop

Record hardware, kernel, graphics driver, audio firmware, package/overlay
versions, commands, and outcomes in the open card. Complete all of the following:

1. Normal TTY login, parser check, launch, Kitty, window/workspace operations,
   volume keys, and no unexpected configuration errors.
2. Audible playback through `pw-play /path/to/sample.wav`, microphone capture
   with `pw-record /tmp/mic-test.wav` (stop with Ctrl+C), then replay that recording.
   Check the intended sink/source in `wpctl status`; also test an available ALSA
   client and PulseAudio client to establish both compatibility paths.
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
Ten exact overlay keyword exceptions sufficed; no shared Gentoo library needed
testing acceptance. Re-run the plan on thinktop after sync: installed packages,
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
