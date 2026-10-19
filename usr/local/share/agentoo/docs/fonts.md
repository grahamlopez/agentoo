# Fonts

Agentoo provides installed-font diagnostics, Kitty previews and selection, and a
read-only Firefox comparison. Portage owns installation and removal. Python 3 and
fontconfig are required; Kitty operations require `kitty` and `kitten`. Firefox
opening detects `firefox` or Gentoo's `firefox-bin`.

```sh
agentoo fonts                         # resolved default Kitty settings
agentoo fonts list                   # installed families and styles
agentoo fonts list ubuntu
agentoo fonts list --nerd
agentoo fonts test                   # samples in the current terminal, including tmux/SSH
agentoo fonts test greek
agentoo fonts test confusables
agentoo fonts test nerd --codepoints --columns 4
agentoo fonts preview                # current configuration, separate Kitty window
agentoo fonts preview 'Liberation Mono' --size 11
agentoo fonts set                    # native chooser, then adjustment preview
agentoo fonts set 'Liberation Mono' --size 11 --style Regular
```

## Installation

The Agentoo overlay provides five versioned Nerd Font packages:

- `media-fonts/ubuntu-sans-mono-nerd`
- `media-fonts/ubuntu-mono-nerd`
- `media-fonts/jetbrains-mono-nerd`
- `media-fonts/fira-code-nerd`
- `media-fonts/liberation-mono-nerd` (upstream family: Literation Mono)

Each offers `normal`, `mono`, and `proportional` USE flags; `mono` is enabled by
default and at least one is required. These select icon sizing, not the width of
the Latin programming font. Upstream archives bundle the variants, so flags trim
installed files rather than download size. Only the named family is installed:
Liberation's Sans/Serif and JetBrains' separate NL family are excluded.

```sh
emerge --ask media-fonts/jetbrains-mono-nerd::agentoo
# In /etc/portage/package.use/fonts, for example:
# media-fonts/jetbrains-mono-nerd normal mono -proportional
```

These packages carry `~amd64` and `~arm64` keywords, accepted by Agentoo in
`/etc/portage/package.accept_keywords/common`. On other systems, accept the
appropriate testing keyword before installation. All download hashes are pinned in
Portage manifests. Original licenses are retained. Use normal Portage operations
to upgrade, change variants, or remove fonts. Installation never selects a font.

Gentoo's `media-fonts/symbols-nerd-font` supplies standalone Nerd symbols and is
already a Kitty dependency. Unifont and Noto Emoji provide broad Unicode and
color emoji coverage. A patched primary font is optional in Kitty. Restart
applications after installing fonts if their discovery state is stale.

## Kitty preview and selection

`set` without a family launches the native `kitten choose-fonts` against a
**temporary copy** of the user's font fragment. The chooser reads the current
fragment and supplies its native family, face, feature, and variable-axis UI.
The result continues into the same adjustment preview used by `preview`.
Chooser completion alone never saves the real configuration.

The dedicated preview window loads normal system/user Kitty configuration plus
the temporary fragment. Existing symbol maps and fallback policy therefore
remain in effect. It runs outside tmux, including when invoked from tmux.
Preview represents the default launch configuration, not existing instances'
command-line overrides or unsaved runtime adjustments.

Controls:

- `+` / `-`: point size in half-point steps, bounded to 4–96.
- `h` / `l`: decrease/increase cell width.
- `j` / `k`: decrease/increase cell height.
- `r`: reset size and spacing to the preview's starting values.
- `s`: save the selection and close.
- `q`, Escape, Ctrl+C, or closing the window: discard temporary changes.

Spacing retains the original unit (percent, pixels, or points). Changes alter
the cell geometry, not the glyph's aspect ratio; tight cells can clip glyphs.
Only adjusted spacing properties are rewritten. Samples show confusables,
ligatures, density rulers, Greek including combining forms, symbols, Braille,
borders, Nerd icons in three spacing contexts, emoji sequences, and kaomoji.
Scroll to inspect long collections or use `--suite` to focus on one.

Run `preview` twice and tile the resulting OS windows for side-by-side font or
size comparisons. Tmux panes share their terminal's font and cannot provide
independent font selections.

A save updates only `~/.config/kitty/agentoo-fonts.conf` (respecting
`XDG_CONFIG_HOME`) and adds its include to user `kitty.conf` if missing. Existing
unrelated settings and `symbol_map` entries are preserved. Explicit `set FONT`
checks that the installed family/style can be selected by Kitty instead of
silently accepting a substituted family. If the fragment changed during the
preview, saving stops rather than overwriting that newer change.

Saving sends Kitty's native reload signal to **all Kitty processes owned by the
current user**. It does not change other users' configurations. Instances using
custom config files or launch-time overrides can retain their own settings; the
command reports this limitation. Reloading also applies other pending edits in
each instance's configuration. No global remote-control permission is needed;
only the isolated preview enables remote control on its private temporary socket.

Every save prints an exact fragment revert command using `kitty-config --value`;
keep it if needed. Reverting reloads all of the user's Kitty instances too.
There is no persistent backup history. Configure fallback overrides using native
Kitty `symbol_map` syntax in the fragment or another user include. Automatic
fallback remains the default; Agentoo does not create global fontconfig policy.

## Agent diagnostics

```sh
agentoo fonts doctor
agentoo fonts doctor --suite greek --json
agentoo fonts doctor --text 'ಠ ⠋ ᾧ 😀'
agentoo fonts doctor --render --suite nerd --output /tmp/nerd-render.log
agentoo fonts coverage 'Liberation Mono' --suite greek
agentoo fonts explain 'ᾧ' --font 'Liberation Mono'
```

Doctor reports enabled and actually loaded fontconfig rules, potential conflicts,
custom fontconfig environment, visible faces/files and Portage owners, installed
font package versions/USE flags, effective generic matches including rendering
properties, and sample-codepoint coverage. It also asks Kitty to resolve its
normal configuration using Kitty's own parser: selected faces/files, include
paths, symbol maps, ligatures/features, cell geometry, composition, and drawing
settings. This helper uses Kitty's Python API; failures are reported without
hiding the remaining diagnostics. It can execute existing Kitty `geninclude`
scripts just as a normal launch does.

`--text` adds Unicode names, categories, combining classes, normalization forms,
covering families, and representative fontconfig matches for the exact problem.
`--json` exposes the same evidence in structured form. Coverage and fontconfig
matches do not prove actual rendering, shaping, correct private-use icons, or
emoji composition. Kitty itself draws some terminal symbols.

`--render` explicitly opens a fresh diagnostic Kitty window with fallback
tracing. It cannot save settings. Close it with `q`; the captured trace records
runtime fallback decisions for those samples, not every existing Kitty window.
An omitted `--output` creates a unique trace file in the temporary directory.
Doctor does not install fonts, refresh caches, or alter rendering rules.

## Firefox preview

```sh
agentoo fonts preview --target firefox
agentoo fonts preview 'Symbols Nerd Font Mono' --target firefox --suite nerd
agentoo fonts test all --target firefox --no-open --output /tmp/fonts.html
```

The local HTML page compares a generic font with an adjustable candidate stack,
size, and fallback order. Tests start with an installed Symbols Nerd Font after
the generic font on the candidate side when available. Firefox requires an
explicit compatible font for private-use Nerd icons; success on the candidate
side does not enable icons elsewhere in the browser. Use Inspector → Fonts to
identify actual rendered fonts. Browser previews do not reproduce Kitty's
rendering. They never edit Firefox preferences or prompt to accept a selection.

Console configuration, Firefox preference editing, and the custom font downloader
have been removed. Existing console/browser settings and old user-installed font
files are left untouched; inspect old installations before removing them manually.

## Development checks

```sh
python3 -m unittest discover -s usr/local/share/agentoo/fonts/tests -v
python3 usr/local/share/agentoo/commands/fonts.py doctor --json
python3 usr/local/share/agentoo/commands/fonts.py preview --target firefox --no-open --output /tmp/fonts.html
```
