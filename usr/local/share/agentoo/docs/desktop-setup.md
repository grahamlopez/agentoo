# Terminal and desktop setup

Runbook for installing and verifying Agentoo's terminal (`@terminal-env`) and
Wayland desktop (`@gui-base`, `@gui-desktop`) environments. Use
`agentoo desktop --help`, `agentoo theme --help`, `agentoo display --help`, and
`agentoo screenshot --help` for CLI controls; shared Hyprland keybindings live
directly in `/etc/xdg/hypr/agentoo.lua`.

## Terminal and editor environment

Install with `sudo emerge --ask --noreplace @terminal-env`.

- **Native extension points:** Portage owns `/etc/zsh/zprofile`,
  `/etc/vim/vimrc`, and `/etc/vim/sysinit.vim` (excluded from Git; review
  updates in `dispatch-conf`). Agentoo tracks `/etc/zsh/{zshrc,zlogin}`,
  `/etc/vim/{vimrc,nvimrc}.local`, `/etc/xdg/nvim/agentoo.lua`,
  `/etc/tmux.conf`, `/etc/gitconfig`, and `/etc/ssh/ssh_config.d/50-agentoo.conf`.
- **Console keymap:** `/etc/vconsole.conf` selects `us-caps.map.gz` (Caps Lock
  as Control).
- **Local user overrides:** Put personal Git identity in `~/.gitconfig-local`;
  personal Vim/Neovim configs (`~/.vimrc`, `~/.config/nvim/init.lua`,
  `after/ftplugin/`) load after system defaults. In Neovim, personal highlight
  overrides survive ordinary changes; clear `agentoo_appearance` or register a
  later `ColorScheme` callback to override theme updates.
- **Updating `app-nvim/softlock`:** Because it is a live `9999` ebuild, normal
  `@world` updates do not fetch new commits—update explicitly with
  `sudo emerge --ask --oneshot app-nvim/softlock`.

## Wayland desktop installation

`@gui-base` provides Hyprland (`hyproverlay`), Hyprlock, Hypridle, Kitty,
Adwaita cursors/icons, PipeWire, WirePlumber, and `alsa-utils`—with no greeter,
UWSM, or XWayland. `@gui-desktop` adds `dconf`, `xdg-desktop-portal-gtk`,
`ddcutil`, `swaybg`, `grim`/`slurp`, `cliphist::guru`, `wl-clipboard`, `fzf`,
`keyd`, fonts, and `firefox-bin`. GURU is masked except for `cliphist` and
`obsidian`.

```sh
sudo emaint sync -r hyproverlay -r guru
sudo emerge --pretend --verbose --autounmask=n @gui-base   # or @gui-desktop
sudo emerge --ask --verbose @gui-base                      # or @gui-desktop
```

Check `gcc --version` first (Hyprland/Hyprlock ebuilds require an active recent
GCC or Clang; installing a compiler does not select it). After installing,
verify a normal local TTY login (`loginctl session-status`, `systemctl --user
status`, `busctl --user list`) and validate the shared config:

```sh
Hyprland --verify-config --config /etc/xdg/hypr/hyprland.lua
start-hyprland
```

Hyprland discovers `/etc/xdg/hypr/hyprland.lua` without any file in `$HOME`,
loading `agentoo.lua` → `/etc/xdg/hypr/hosts/<host>.lua` (via native Portage
profile) → optional `~/.config/hypr/agentoo-local.lua` → `lid.lua` → remembered
interactive state (`$XDG_STATE_HOME/agentoo/appearance.json`). Kitty similarly
loads `/etc/xdg/kitty/kitty.conf` and optional `/etc/xdg/kitty/hosts/<host>.conf`
via native `geninclude`.

## Autologin, screen locking, and console recovery

- **`tty1` autologin:** `/root/002-agentoo-setup-user.sh` writes the local
  `/etc/systemd/system/getty@tty1.service.d/autologin.conf` drop-in. `/etc/zsh/zlogin`
  runs `start-hyprland` once on `tty1` (without `exec`, leaving a shell on exit
  instead of a retry loop). To skip autostart temporarily, run
  `touch ~/.disable-hyprland-autostart`.
- **`tty2` recovery console:** `/etc/systemd/system/getty.target.d/50-recovery-console.conf`
  provides a normal password login on `Ctrl+Alt+F2`. Activate after deployment
  with `sudo systemctl daemon-reload && sudo systemctl start getty@tty2.service`
  and verify login before rebooting. For boot recovery, append
  `systemd.unit=rescue.target` to the kernel command line.
- **Screen locking:** `Super+L` runs `loginctl lock-session`; Hypridle (started
  once per Hyprland session—do not also enable a user unit) launches Hyprlock,
  turns displays off via `agentoo display off`, and holds a `logind` sleep
  delay inhibitor (`inhibit_sleep = 3`). Note: screen locking does not secure
  the `tty1` recovery shell if Hyprland exits or crashes (see the threat model
  in [docs/README.md](README.md#security-and-convenience-boundaries)).

## Audio (PipeWire and WirePlumber)

Enable PipeWire as the desktop user (never as system services):

```sh
systemctl --user enable --now pipewire.service pipewire-pulse.socket wireplumber.service
wpctl status
pactl info   # expect: PulseAudio (on PipeWire ...)
```

Enable `pipewire.service` directly (not sockets alone) so audio devices
initialize at login instead of on first client connect. `alsa-utils` handles
privileged UCM boot setup (including hardware mute LEDs). Verify left/right
routing and mic capture after first setup and after suspend/resume:

```sh
paplay --channel-map=front-left --no-remix /usr/share/sounds/freedesktop/stereo/audio-channel-front-left.oga
paplay --channel-map=front-right --no-remix /usr/share/sounds/freedesktop/stereo/audio-channel-front-right.oga
parec --device=@DEFAULT_SOURCE@ --file-format=wav /tmp/mic-test.wav   # Ctrl+C, then paplay /tmp/mic-test.wav
```

Benign `mod.rt` / RTKit `ServiceUnknown` warnings do not indicate broken audio;
only investigate `sys-auth/rtkit` if playback actually drops out under load.

## Light/dark mode, portal, and Qt

`@gui-desktop` installs `dconf` and `xdg-desktop-portal-gtk` (configured by
`/etc/xdg/xdg-desktop-portal/hyprland-portals.conf` for the Settings portal).
Use `agentoo theme light|dark` to switch modes (stored in GSettings/dconf).
Log out and back in once after first installing the portal or deploying
`QT_QPA_PLATFORMTHEME=xdgdesktopportal`.

- **Kitty one-time setup:** Run `kitten themes` and save palettes for `light`,
  `dark`, and `no-preference` (`*-theme.auto.conf`), then restart Kitty once.
- **Qt live palette refresh:** Agentoo ships a Portage user patch under
  `/etc/portage/patches/dev-qt/qtbase/` so Qt 6 apps (e.g., PCManFM-Qt) refresh
  their cached palette live on mode changes. Rebuild from source after
  deployment (`sudo emerge --ask --oneshot --usepkg=n dev-qt/qtbase`) and
  restart Qt apps. Remove the patch once upstream fixes palette invalidation.
- **Verify portal value:**
  `gdbus call --session --dest org.freedesktop.portal.Desktop --object-path /org/freedesktop/portal/desktop --method org.freedesktop.portal.Settings.Read org.freedesktop.appearance color-scheme`
  (`0` = no preference, `1` = dark, `2` = light).
- Coordinated multi-app color theming plans live in
  [card 055](../kanban/Backlog/055-coordinated-color-theming.md).

## Desktop utilities

- **Clipboard history:** Hyprland starts `wl-paste --type text --watch cliphist store`
  once per session. Press `Ctrl+0` for the floating `fzf` picker (`Enter`
  restores, `Shift+Delete` deletes entry, `Escape` cancels); run `cliphist wipe`
  to clear history. Diagnostics: `journalctl -t agentoo-clipboard`.
- **Laptop brightness:** Intel laptop profiles install `sys-power/acpilight`
  via `@profile`; users need the `video` group (`002-agentoo-setup-user.sh`
  adds it, or `sudo usermod -aG video USER` + re-login).
- **Intel VA-API check:** Identify the Intel render node via
  `/sys/class/drm/renderD*/device/vendor` (`0x8086`) and run
  `vainfo --display drm --device /dev/dri/renderD129`.
- **Cloud storage:** For pCloud, see `agentoo cloud-storage pcloud --help` and
  [pcloud-drive-bin README.gentoo](../portage/net-misc/pcloud-drive-bin/files/README.gentoo).
