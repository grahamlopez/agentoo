# Fonts

Agentoo provides installed-font diagnostics, Kitty previews and selection, and a
read-only Firefox comparison. Portage owns installation and removal. Python 3 and
fontconfig are required; Kitty operations require `kitty` and `kitten`. Firefox
opening detects `firefox` or Gentoo's `firefox-bin`.

For agent troubleshooting, start with [the diagnostic workflow](#agent-diagnostic-workflow).
Use `agentoo fonts doctor --text 'problem text' --json` for machine-readable
codepoints and environment evidence. `agentoo fonts doctor --text 'problem text'`
provides a human-readable report. Neither needs a graphical window.

```sh
agentoo fonts                        # current Kitty settings and installed families
agentoo fonts status                 # same as no command
agentoo fonts status --filter ubuntu
agentoo fonts status --nerd
agentoo fonts test                   # samples in the current terminal, including tmux/SSH
agentoo fonts test greek
agentoo fonts test confusables
agentoo fonts test nerd
agentoo fonts test --interactive     # current configuration, separate Kitty window
agentoo fonts test --font 'Liberation Mono' --size 11
agentoo fonts set                    # native chooser, then adjustment preview
agentoo fonts set --font 'Liberation Mono' --size 11 --style Regular
```

## Command overview

- `agentoo fonts` or `agentoo fonts status`: current default Kitty settings and
  installed families grouped by style. `--filter TEXT` and `--nerd` filter only
  the installed-font section.
- `agentoo fonts test [SUITE]`: print samples with the invoking terminal's actual
  rendering; this can differ from saved configuration. `--font FAMILY`, `--size`,
  `--style`, or `--interactive` opens a dedicated interactive Kitty preview.
- `agentoo fonts set`: native chooser followed by adjustment preview. An explicit
  `--font FAMILY` applies immediately; `--restore TEXT` restores an exact fragment.
- `agentoo fonts doctor`: environment, codepoint, coverage, and matching diagnostics.
  `--text TEXT` inspects characters; `--font PATTERN` adds analysis of one matched
  face. `--font` and `--render` are mutually exclusive: use `test --font` to
  visually inspect a candidate; rendering diagnostics trace the current config.

Use `agentoo fonts COMMAND --help` for every option and default. The former
`list`, `preview`, `coverage`, `explain`, and `kitty-config` commands have been
removed. Translate an older printed `kitty-config --value TEXT` revert command
into `set --restore TEXT`, retaining its exact quoted text.

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

`set` without `--font` launches the native `kitten choose-fonts` against a
**temporary copy** of the user's font fragment. The chooser reads the current
fragment and supplies its native family, face, feature, and variable-axis UI.
The result continues into the same adjustment preview used by `test --interactive`.
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
Scroll to inspect long collections or pass a suite, such as `test greek --interactive`,
to focus on one. Interactive `set` accepts `--suite greek` too.

Run `test --font` twice and tile the resulting OS windows for side-by-side font or
size comparisons. Tmux panes share their terminal's font and cannot provide
independent font selections.

A save updates only `~/.config/kitty/agentoo-fonts.conf` (respecting
`XDG_CONFIG_HOME`) and adds its include to user `kitty.conf` if missing. Existing
unrelated settings and `symbol_map` entries are preserved. Explicit `set --font FONT`
checks that the installed family/style can be selected by Kitty instead of
silently accepting a substituted family. If the fragment changed during the
preview, saving stops rather than overwriting that newer change.

Saving sends Kitty's native reload signal to **all Kitty processes owned by the
current user**. It does not change other users' configurations. Instances using
custom config files or launch-time overrides can retain their own settings; the
command reports this limitation. Reloading also applies other pending edits in
each instance's configuration. No global remote-control permission is needed;
only the isolated preview enables remote control on its private temporary socket.

Every save prints an exact fragment revert command using `set --restore`;
keep it if needed. Reverting reloads all of the user's Kitty instances too.
There is no persistent backup history. Configure fallback overrides using native
Kitty `symbol_map` syntax in the fragment or another user include. Automatic
fallback remains the default; Agentoo does not create global fontconfig policy.

## Agent diagnostic workflow

Use `agentoo fonts doctor --text 'problem text' --json` for codepoints, Unicode
normalization, coverage, package ownership, fontconfig policy, and resolved Kitty
settings. Use `agentoo fonts doctor --text 'problem text'` for a human-readable report.
Font installation belongs to Portage; browser preview is
read-only, and saving a Kitty selection reloads all of the user's Kitty instances.

Run diagnostics as the affected desktop user, with the same fontconfig and XDG
environment as the application. Running through sudo can inspect a different
user's fonts and configuration. Commands work from tmux/SSH, but a remote host's
fontconfig inventory says nothing about the fonts of the local terminal displaying
that SSH session.

Start with a noninteractive report; include the user's exact problem text when
available. Preserve combining marks, variation selectors, and joiners rather than
retyping a visually similar character.

```sh
agentoo fonts doctor --json
agentoo fonts doctor --text 'ಠ ⠋ ᾧ 😀' --json
```

Choose the smallest additional diagnostic that answers the remaining question:

| Question | Command | Interpretation |
| --- | --- | --- |
| What are these characters/codepoints? | `agentoo fonts doctor --text 'ᾧ ᾇ'` | Unicode names, codepoints, categories, combining classes, covering families, and fontconfig candidates. |
| What could render this text with my preferred font? | `agentoo fonts doctor --text 'ಠ ⠋' --font 'Liberation Mono'` | Queries candidates with that pattern and reports single matched-face coverage; does not change fonts or establish rendering. |
| How does this exact string normalize? | `agentoo fonts doctor --text 'ᾧ ᾇ' --json` | Includes original input and full NFC/NFD strings, retaining sequence context. |
| Are tested Braille/Greek/icons missing from all visible fonts? | `agentoo fonts doctor --suite braille --json` | Reports coverage across all visible faces; choose `greek`, `nerd`, or another suite as needed. |
| Does one face cover the samples? | `agentoo fonts doctor --font 'Liberation Mono' --suite greek` | Always inspect the matched face and file: fontconfig may substitute another family. |
| Which fonts are installed and who owns them? | `agentoo fonts doctor --json` | See `faces` for file ownership and `packages` for versions, repository, and enabled USE flags. |
| What font names/styles can I select? | `agentoo fonts status` | Use installed family names, not Portage package names, with `test --interactive` and `set`. |
| What rendering policy is configured? | `agentoo fonts doctor --json` | `matches` contains fontconfig rendering properties; `kitty.settings` contains Kitty features, geometry, symbol maps, and composition. |
| Which fallback does a fresh Kitty actually use? | `agentoo fonts doctor --render --text 'ಠ ⠋ ᾧ 😀' --suite smoke` | Opens a diagnostic window and captures runtime fallback tracing; requires a GUI and someone to close it. |

Use `doctor --text TEXT --json` for programmatic JSON parsing; stdout is one
JSON document. Character records are distinct codepoints sorted numerically,
excluding spaces and newlines; they do not describe glyph clusters in input order.
Use the report's original text and normalization strings to inspect sequences.
There is no separate codepoint command or `--codepoints` switch.

A minimal Python consumer, without additional dependencies:

```python
import json
import subprocess

report = json.loads(subprocess.check_output(
    ["agentoo", "fonts", "doctor", "--text", "ಠ ⠋ ᾧ 😀", "--json"], text=True))
for char in report["text"]["characters"]:
    print(char["codepoint"], char["name"], char["covering_families"])
```

The useful JSON fields are:

| Field | Evidence |
| --- | --- |
| `environment`, `tools` | Terminal/tmux/SSH context, fontconfig/XDG overrides, and diagnostic executable paths. |
| `rules.enabled`, `rules.loaded`, `rules.warnings` | Selected rules, `fc-conflist` output, and conservative conflict hints. Loaded-rule output retains fontconfig's enabled/disabled markers. |
| `matches` | Verbose fontconfig matches for monospace, sans-serif, serif, and emoji, including antialiasing/hinting properties. |
| `faces` | Family, style, file, Portage owner, and inclusive integer character ranges from fontconfig. Ownership can be `(not Portage-owned)`. |
| `packages`, `font_directories` | Installed media-font packages, enabled USE flags, repository, and directories containing visible fonts. |
| `font_analysis` | Present with `--font`: requested pattern, actual matched family/file, inclusive character ranges, and per-suite coverage of that single face. Fontconfig can substitute a different family. |
| `coverage[SUITE]` | `total`, `covered`, and `missing` codepoint labels across all visible faces. Includes characters used in sample labels; not a Unicode conformance score. |
| `kitty.paths`, `kitty.settings`, `kitty.faces`, `kitty.geometry`, `kitty.fragment` | Resolved default configuration, selected faces/files, and user fragment. `kitty.errors` reports parsing problems; `kitty.error` reports a helper failure. |
| `text.input`, `text.NFC`, `text.NFD`, `text.characters` | Present with `--text`; per-character entries include `codepoint`, `name`, `category`, `combining`, `covering_families`, and `fontconfig_match`. With `--font`, `in_matched_face` distinguishes coverage in that single matched face from availability elsewhere. |
| `render_trace` | Present with `--render`; path to the captured Kitty fallback log. |

Optional command failures can appear as an `{"error": "..."}` object instead of
command output. Missing required fontconfig tools or a fatal error produce a
nonzero exit status and stderr. Check the exit status before parsing stdout;
do not interpret an unavailable diagnostic as missing glyph coverage.

Distinguish these three evidence levels when reporting a finding:

1. **Installed coverage:** a visible face advertises a codepoint. This does not
   establish which font an application chooses, shaping, or appearance.
2. **Resolved configuration/matching:** fontconfig candidates and Kitty's default
   parsed settings. Existing instances may use launch overrides, custom config
   paths, stale font lists, or unsaved runtime adjustments.
3. **Observed rendering:** a fresh Kitty fallback trace and the user's visual
   inspection. Kitty itself draws some terminal symbols. Trace output describes
   fallbacks for the rendered samples, not every glyph in every running instance.

If coverage exists but characters remain missing, check application restart and
actual rendering before recommending more packages. If the appearance is wrong,
inspect the selected face, cell geometry, feature/ligature settings, symbol maps,
and effective renderer-specific settings. Greek combining sequences and joined
emoji require visual checks even when individual codepoints are all covered.
The Firefox private-use limitation is described [below](#firefox-preview).

### Rendering traces and side effects

```sh
agentoo fonts doctor --render --suite nerd --output /tmp/nerd-render.log
agentoo fonts doctor --render --text 'ಠ ⠋' --json
```

`--render` explicitly opens a fresh diagnostic Kitty window. It cannot save font
settings. Close it with `q`; the command waits until the window closes, then
finishes the report. With `--json`, stdout remains a JSON document, and the trace
path appears in `render_trace`. An omitted `--output` creates a unique temporary
`.log` file. An explicit path is overwritten. Do not start an interactive render
when operating without a reachable GUI or someone available to close the window.

Ordinary `doctor` and `status` do not open a GUI or change
font settings. Doctor asks Kitty to resolve configuration with Kitty's own Python
API; this can execute existing `geninclude` scripts, just as a normal launch does.
It reports helper failures without hiding the remaining inventory. Doctor does
not install fonts, refresh caches, or alter rules. To generate a comparison without starting an
application, create [browser HTML](#firefox-preview) using `--no-open`.

`test --interactive` is interactive and can persist settings when the user presses `s`.
`set --font FONT` persists immediately; `set` without `--font` opens the chooser and
adjustment preview. Both saved selections and `set --restore` reverts reload all
the current user's Kitty instances. Keep the printed revert command. Installation
and removal are separate Portage operations; preserve this distinction when
suggesting or applying a change.

## Firefox preview

```sh
agentoo fonts test --target firefox
agentoo fonts test nerd --font 'Symbols Nerd Font Mono' --target firefox
agentoo fonts test all --target firefox --no-open --output /tmp/fonts.html
```

The local HTML page compares a generic font with an adjustable candidate stack,
size, and fallback order. Tests start with an installed Symbols Nerd Font after
the generic font on the candidate side when available. Firefox requires an
explicit compatible font for private-use Nerd icons; success on the candidate
side does not enable icons elsewhere in the browser. Use Inspector → Fonts to
identify actual rendered fonts. Browser previews do not reproduce Kitty's
rendering. They never edit Firefox preferences or prompt to accept a selection.

Terminal smoke samples include the style demonstration when attached to a TTY.
Use `doctor --text TEXT --json` for codepoint details; separate plain-output
and codepoint-table switches are not needed.

Console configuration, Firefox preference editing, and the custom font downloader
have been removed. Existing console/browser settings and old user-installed font
files are left untouched; inspect old installations before removing them manually.

## Development checks

```sh
python3 -m unittest discover -s usr/local/share/agentoo/tests -p 'test_fonts*.py' -v
python3 usr/local/bin/agentoo-fonts doctor --json
python3 usr/local/bin/agentoo-fonts test --target firefox --no-open --output /tmp/fonts.html
```
