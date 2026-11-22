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
See [desktop setup](../../docs/desktop-setup.md#lightdark-mode-portal-and-qt)
for portal, Kitty, and Qt setup.

## Color theme integration

Theme selection should preserve the selected mode; changing modes should
preserve the selected theme. Where an application supports paired palettes,
supply both variants and use its native switching. Other integrations may need
palette updates, native reloads, or an explicit restart/resume step.

### Target themes

These are well-established themes that have light/dark variants and wide
application support, so should be good candidates for built-in agentoo support.

- Catppuccin (Mocha/Latte)
- Nord
- Solarized
- Tokyo Night
- Gruvbox
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
  `agentoo desktop --help` (`borders`, `shadows`). Coordinated
  mode-specific palettes are pending.

### Kitty

- **Light/dark:** Automatic, live, after assigning a palette to each mode with
  `kitten themes` and restarting Kitty once. See
  [Kitty setup](../../docs/desktop-setup.md#lightdark-mode-portal-and-qt).
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
