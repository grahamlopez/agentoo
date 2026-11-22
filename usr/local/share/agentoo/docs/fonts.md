# Fonts

Use `agentoo fonts --help` (`status`, `test`, `set`, `doctor`) for CLI usage,
interactive preview controls, and JSON output; see
[portage/README.md](../portage/README.md) for overlay Nerd Font packages
(`media-fonts/*-nerd`). This guide covers only the cross-tool font diagnostic
mental model.

## Three evidence levels

Always distinguish these levels when diagnosing missing or ugly glyphs:

1. **Installed coverage:** A visible face advertises the codepoint. This does
   not establish which font an application selects, shaping, or visual quality.
2. **Resolved configuration and matching:** `fontconfig` candidates and Kitty's
   default parsed config. Existing instances may use launch overrides, custom
   configs, or stale font lists.
3. **Observed rendering:** A fresh `agentoo fonts doctor --render` fallback
   trace plus visual inspection. Kitty draws some terminal/box symbols itself.

## Diagnostic workflow

Start with a non-interactive report using the user's exact problem string
(preserving combining marks, variation selectors, and joiners):

```sh
agentoo fonts doctor --text 'problem text' --json
```

- Run diagnostics as the **affected desktop user**—never through `sudo` (which
  sees a different fontconfig/XDG environment). Over SSH, the remote host's
  fontconfig inventory says nothing about the local terminal rendering the
  session.
- If a codepoint is covered by installed fonts but still renders as missing,
  check application restart and actual rendering (`--render`) before installing
  more packages.
- Greek combining sequences and joined emoji require visual inspection even
  when every individual codepoint is covered.

## Kitty vs. Firefox behavior

- **Kitty:** Automatic fallback (`media-fonts/symbols-nerd-font`, Unifont, Noto
  Emoji) is the default; override specific ranges with native `symbol_map` in
  `~/.config/kitty/agentoo-fonts.conf` rather than adding global fontconfig
  policy. Saving with `agentoo fonts set` reloads all Kitty processes owned by
  the current user and prints an exact `set --restore` revert command.
- **Firefox:** Private-use Nerd icons require an explicit compatible font in
  the CSS font stack. `agentoo fonts test --target firefox` generates a
  read-only HTML comparison; use DevTools *Inspector → Fonts* to verify which
  face actually rendered.
