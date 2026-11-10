# Theming and light/dark appearance

Agentoo treats appearance as three independent choices:

1. **Mode:** light or dark. Agentoo publishes the preference; applications follow it.
2. **Color theme:** the colors used within each mode. (Coordinated theme
   selection across applications is future work)
3. **Wallpaper:** a selected image, which can optionally seed theme colors

## System light/dark preference

```sh
agentoo theme          # Show light, dark, or no-preference
agentoo theme light
agentoo theme dark
```

Run as your desktop user, without sudo. The preference persists across login.
Choose "follow system", "system", or "auto" once in applications that offer it.
Terminal applications may follow their terminal instead. Applications pinned to
light or dark retain their own choice. The command changes only the preference;
application theme selection, palette updates, and restarts remain user-controlled.

## Color theme integration

Theme selection should preserve the selected mode; changing modes should
preserve the selected theme. Where an application supports paired palettes,
supply both variants and use its native switching. Other integrations may need
palette updates, native reloads, or an explicit restart/resume step.

### Target themes

These are well-established themes that have light/dark variants and wide
application support, so should be good candidates for built-in agentoo support.

- Catpuccin (Mocha/Latte)
- Nord
- Solarized
- Tokyo Night
- Grubbox
- Kanagawa

### Generated themes

Omarchy has a nice facility where an application (FIXME: name?) can be opened
to edit and generate a theme based on pre-filled values from a supplied
wallpaper image.

## Target applications

Each entry describes **Light/dark** automation and **Color themes** within those
modes. **Pending** means assessment or Agentoo integration remains to be done,
not that the application lacks native support.

### Hyprland

- **Light/dark:** Agentoo does not currently change compositor colors with the mode.
- **Color themes:** Border and shadow colors can be set through
  [desktop appearance commands](desktop.md#desktop-appearance). Coordinated
  mode-specific palettes are pending.

### Kitty

- **Light/dark:** Automatic, live, after assigning a palette to each mode with
  `kitten themes` and restarting Kitty once. See [Kitty setup](#kitty-setup).
- **Color themes:** Native, manually selected light/dark/no-preference palettes.
  Previous choices were Catppuccin Latte for light and Mocha for dark/no
  preference. Integration with agentoo-wide theme selection is pending.

### Tmux

- **Light/dark:** Existing styling works in both modes; appearance changes also
  reach applications inside panes in the tested setup.
- **Color themes:** Existing default/ANSI styling follows terminal colors.
  Coordinated status-line and border theme selection is pending.

### Terminal tools

- **Light/dark:** Existing Zsh prompt, completion, and directory colors work in
  both modes. The other tools below remain to be assessed individually.
- **Color themes:** Terminal defaults and ANSI colors follow Kitty's palette;
  explicit RGB colors and application themes may need separate configuration.
  Coordinated theme selection is pending.

This is the target inventory for shell styling and command output. `LS_COLORS`
controls file colors in programs that use it; it is not a global output theme.
Kitty, tmux, Neovim, and the coding agents retain their own application entries.

| Tool | Color settings to cover |
| --- | --- |
| Zsh | Prompt and completion styling; file completion uses `LS_COLORS`. |
| `ls` | `LS_COLORS`, initialized by `dircolors` and customized in shared Zsh defaults. |
| Git | Native `color.*` settings in shared Git defaults. |
| `grep` | Match styling, including `GREP_COLORS`. |
| `rg` | Native `--colors` rules for matches, paths, and line numbers. |
| `fd` | File colors and integration with `LS_COLORS`. |
| Portage | Package, version, status, and diagnostic colors. |
| Gentoo helpers | `esearch`, `genlop`, and gentoolkit commands; assess each tool's output. |
| btop | Application theme, background, and terminal-palette behavior. |
| `fzf` | Native base schemes and custom `--color` settings. |
| `less` / `man` | Passed-through colors and terminal text attributes; shared defaults avoid forced colors. |
| `tree` | File listing colors and consistency with `ls` / `fd`. |
| `diff` | Added, removed, and changed text colors. |
| Agentoo commands | Status and diagnostic output, including `agentoo repos` and `agentoo term-colors`. |

Assess each tool for default/ANSI versus indexed/RGB colors, configuration
overrides, and whether a running process needs a refresh after a theme change.
btop and `fzf` have their own palette settings, so grouping them here does not
imply that changing the terminal palette is sufficient.

### Neovim

- **Light/dark:** Automatic; confirmed directly in Kitty and inside tmux.
- **Color themes:** Assessment and coordinated theme selection are pending.

### Firefox

- **Light/dark:** Follows the system preference live. Dark reader works fine.
- **Color themes:** Assessment and coordinated theme selection are pending.

### Prisma Browser

- **Light/dark:** Follows the system preference live. Dark reader works fine.
- **Color themes:** Assessment and coordinated theme selection are pending.

### ChatGPT desktop

- **Light/dark:** Automatic; confirmed working with mode switching.
- **Color themes:** Assessment and coordinated theme selection are pending.

### PCManFM-Qt and other Qt applications

- **Light/dark:** PCManFM-Qt switches live with Agentoo's portal integration and Qt
  palette-refresh patch. Other Qt applications remain to be verified.
- **Color themes:** Native Qt palette follows the portal preference. Custom color theme
  selection and interaction with application overrides remain to be assessed.

### Codex CLI

- **Light/dark:** Restart required in tested version 0.166.0. After switching mode,
  restart and use `codex resume --last` to return to the conversation.
- **Color themes:** Manual syntax-highlighting selection through `/theme`.
  Solarized (light) was readable in both modes after restart. Automatic variant
  selection and terminal appearance refresh remain unresolved; Ctrl+L and
  reselecting the syntax theme did not fix the running session's appearance.

### Pi coding agent

- **Light/dark:** Automatic; confirmed working with mode switching.
- **Color themes:** Assessment and coordinated theme selection are pending.

### Claude Code

- **Light/dark:** Automatic; confirmed working with mode switching.
- **Color themes:** Assessment and coordinated theme selection are pending.

## Setup and troubleshooting

### System preference and portal

Install the dependencies with `emerge --ask --noreplace @gui-desktop`.
The set includes dconf and the GTK portal backend, which pulls in
`sys-apps/xdg-desktop-portal` and `gnome-base/gsettings-desktop-schemas`.
The native `/etc/xdg/xdg-desktop-portal/hyprland-portals.conf` selects GTK
for the Settings interface. It exposes the preference as
`org.freedesktop.appearance color-scheme` and sends native change notifications.
Personal portal configuration takes precedence; portal files are selected as
whole files, not merged, so an existing personal file must also select the GTK
Settings backend. See the upstream [portal configuration reference](https://flatpak.github.io/xdg-desktop-portal/docs/portals.conf.html)
and [GTK Settings implementation](https://github.com/flatpak/xdg-desktop-portal-gtk/blob/main/src/settings.c).

After first installing the portal or changing its configuration, log out of
Hyprland and log back in. D-Bus activates the portal services on demand; no
Agentoo watcher or service enablement is needed. Ordinary mode changes need
neither a logout nor a compositor reload.


The authoritative setting is `org.gnome.desktop.interface color-scheme`, stored
through native GSettings/dconf. There is no second mode setting in Agentoo's
appearance state or login restore command. Repeating a setter is harmless.
The native value `default` is reported as `no-preference`, not guessed to be
light or dark. Queries report the preference, not application state.
Successful queries print one value to stdout; setters report to stderr.
Exit codes are 0 for success, 1 for settings failures, and 2 for invalid arguments.

### Kitty setup

Run `kitten themes`, choose a theme, and on the final screen save it as the light
scheme. Repeat for dark and no-preference, then restart Kitty. The native files
are `light-theme.auto.conf`, `dark-theme.auto.conf`, and
`no-preference-theme.auto.conf` in your Kitty configuration directory.
Ordinary default colors alone do not enable automatic switching. The automatic
files override other color settings, including command-line color overrides.
See [Kitty's automatic switching documentation](https://sw.kovidgoyal.net/kitty/kittens/themes/#change-color-themes-automatically-when-the-os-switches-between-light-and-dark).

### Qt portal integration and palette refresh

The shared Hyprland configuration selects Qt's native `xdgdesktopportal`
platform theme through `QT_QPA_PLATFORMTHEME`. It reads the existing Settings
portal preference and listens for changes; no separate palette manager is
needed. The installed Qt must supply `libqxdgdesktopportal.so` in its
`platformthemes` plugin directory.

Agentoo supplies a native Portage user patch for all Qt versions under
`/etc/portage/patches/dev-qt/qtbase/`. Without it, Qt 6.11.3 receives mode
changes but retains its cached startup palette. Deploying configuration alone
does not apply source patches. Rebuild the installed version after deployment:

```sh
sudo emerge --ask --oneshot =dev-qt/qtbase-6.11.3
```

Then close PCManFM-Qt completely and restart it. The patched portal plugin was
built separately and verified with an isolated Settings portal: a Qt Widgets
probe on Wayland switched its palette dark → light → dark → light while
running, including with `QProxyStyle`, which PCManFM-Qt uses. The unpatched
plugin received the same signals but kept its dark palette. PCManFM-Qt 2.4.1
was reported to pick up the initial mode but not live changes before this fix.
After a Portage rebuild on 2026-11-09, the user confirmed PCManFM-Qt starts
dark and switches live to light and back to dark with the plugin selected.
Portage applies the patch on subsequent Qt builds, including version updates,
and stops with an error if it cannot apply it. Successful application does not
prove compatibility: retest live switching when updating Qt and remove the
patch once upstream handles palette invalidation.

After deploying this default, log out and back in so terminals and applications
inherit it. For an immediate check, close PCManFM-Qt completely and launch:

```sh
QT_QPA_PLATFORMTHEME=xdgdesktopportal pcmanfm-qt
```

Then run `agentoo theme light` and `agentoo theme dark` from another terminal.
An already-running PCManFM-Qt process retains its original environment.
Existing terminals also retain their inherited environment after a Hyprland
reload. To launch Qt applications normally from such a terminal, first run
`export QT_QPA_PLATFORMTHEME=xdgdesktopportal`; a fresh login supplies the
shared default without this manual step.
Personal `QT_QPA_PLATFORMTHEME`, `QT_STYLE_OVERRIDE`, or application palette
settings can override this integration.
See [Qt's portal theme implementation](https://github.com/qt/qtbase/blob/6.11/src/plugins/platformthemes/xdgdesktopportal/qxdgdesktopportaltheme.cpp).


### Verify propagation

To inspect the public preference from the running desktop session:

```sh
gdbus call --session --dest org.freedesktop.portal.Desktop \
  --object-path /org/freedesktop/portal/desktop \
  --method org.freedesktop.portal.Settings.Read \
  org.freedesktop.appearance color-scheme
```

The returned unsigned value is 0 for no preference, 1 for dark, and 2 for light.
Switch both directions with applications already open, directly in Kitty and
inside tmux, then check newly launched applications and persistence after login.
The checkout tests exercise command errors, help/completion, and isolated native
GSettings persistence; they do not establish live portal or application behavior.


