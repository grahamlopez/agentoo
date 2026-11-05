# Theming and light/dark appearance

## System light/dark preference

```sh
agentoo theme          # Show light, dark, or no-preference
agentoo theme light
agentoo theme dark
```

Run these as your desktop user, without sudo. The setters persist only
`org.gnome.desktop.interface color-scheme` through native GSettings/dconf.
There is no second mode setting in Agentoo's appearance state, no login restore
command, and no theme or palette selection. Repeating a setter is harmless.
The initial native value `default` is reported as `no-preference`, not guessed
to be light or dark. Queries report the system preference, not application state.
Successful queries print one value to stdout; setters report to stderr.
Exit codes are 0 for success, 1 for settings failures, and 2 for invalid arguments.

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

## Application setup

Choose "follow system", "system", or "auto" once in each application's
appearance settings. Terminal applications may follow their terminal instead;
configure the terminal's native light/dark switching too. Applications pinned
to dark or light keep their own preference. These commands do not edit
application settings, supply palettes, change wallpaper or compositor colors,
or restart applications. Whether an application updates live depends on its
own support and configuration.

### Kitty

Kitty requires a one-time choice of colors for each appearance; its ordinary
default colors alone do not enable automatic switching. Run `kitten themes`,
choose a theme, and on the final screen save it as the light scheme. Repeat
for the dark and no-preference schemes, then restart Kitty. This creates the
native `light-theme.auto.conf`, `dark-theme.auto.conf`, and
`no-preference-theme.auto.conf` files in your Kitty configuration directory.
Subsequent `agentoo theme light` / `dark` changes should switch Kitty live.
Those automatic files take precedence over other color settings, including
command-line color overrides. See [Kitty's automatic switching documentation](https://sw.kovidgoyal.net/kitty/kittens/themes/#change-color-themes-automatically-when-the-os-switches-between-light-and-dark).

## Verification

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

## Observed application behavior

User-reported desktop checks on 2026-11-05:

| Application | Mode switching |
| --- | --- |
| Firefox | Follows the system preference live. |
| Prisma Browser | Follows the system preference live. |
| Kitty | Switches live after configuring its native automatic theme files; the legacy choices were Catppuccin Latte for light and Mocha for dark/no preference. |
| Neovim | Confirmed working with mode switching, directly in Kitty and inside tmux. |
| Tmux | Confirmed working with mode switching, including terminal applications inside panes. |
| Zsh | Prompt, completion, and directory colors confirmed working in both modes. |
| Pi coding agent | Confirmed working with mode switching. |
| Claude Code | Confirmed working with mode switching. |
| ChatGPT desktop | Confirmed working with mode switching. |
| Codex CLI (installed version 0.166.0) | Requires restart after switching modes, then `codex resume --last` to return to the conversation. Solarized (light) syntax highlighting was readable in both modes after restart. Ctrl+L and reselecting the syntax theme did not resolve the running session's appearance. |

These observations do not establish behavior for other versions or every
terminal/tmux arrangement. Retest Codex live switching after relevant updates.

## Future theme selection

Future custom theme selection may need application-specific palette updates,
native reloads, or an explicit restart/resume step where live updates fail.
Changing Codex's syntax theme alone did not refresh its terminal appearance in
the check above, so custom theme support must verify that separately. Keep
theme selection and mode preference independent; `agentoo theme light|dark`
currently only publishes the native preference and does not restart applications.

