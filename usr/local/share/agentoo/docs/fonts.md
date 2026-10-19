# Fonts

`agentoo fonts` reports font configuration. It never installs or activates fonts
implicitly. Use `agentoo help fonts` for commands and command-specific `--help`
for options. `agentoo fonts test` defaults to the full `all` collection and
prints in the current terminal. Detection recognizes Kitty and Linux console;
inside tmux it checks attached client terminal types rather than inherited Kitty
variables. Ambiguous or other terminals (including SSH) still receive visual
tests without needing a target. Firefox previews always require
`--target firefox`. Configuration commands require an identifiable supported
target or an explicit `--target`. Python 3 and fontconfig tools are required. Kitty previews need
Kitty; console operations need kbd's `setfont`; HTML opening needs Firefox.

```sh
agentoo fonts status --target kitty
agentoo fonts status --target console
agentoo fonts status --target firefox
agentoo fonts test all --target console
agentoo fonts test greek --target kitty
agentoo fonts test all --target firefox
agentoo fonts test kaomoji --target firefox --no-open --output /tmp/kaomoji.html
agentoo fonts coverage 'Liberation Mono' --suite greek
agentoo fonts explain 'ᾧ' --font 'Liberation Mono'
agentoo fonts list --available
agentoo fonts list --nerd
agentoo fonts install ubuntu-sans-mono
agentoo fonts preview 'UbuntuSansMono Nerd Font' --target kitty --size 12 --style Medium
agentoo fonts set 'UbuntuSansMono Nerd Font' --target kitty --size 12 --style Medium
agentoo fonts size 11 --target kitty
agentoo fonts choose --target kitty
agentoo fonts install terminus
agentoo fonts preview ter-v24n --target console
```

The shared visual collection includes Greek and polytonic Greek in precomposed
and decomposed forms, combining accents/breathings/iota subscripts, Braille,
thin/heavy/double box drawing, Unicode symbols, Nerd Font icons, emoji sequences,
and kaomoji. Samples use labeled groups designed for an 80-column terminal,
including side-by-side precomposed/combining Greek and thin/heavy/double borders.
Nerd Font groups repeat identical icons in three fixed contexts: spaced (room
to expand), adjacent (no separating cells), and bounded (`|icon|`, single-cell
fit). Kitty can enlarge symbols into following spaces, so compare the same
context across fonts; a size difference between contexts is expected.
Detailed codepoint tables are hidden by default; add `--codepoints` to terminal
tests (`--columns` controls table columns, capped at six to fit 80 columns).
Firefox keeps codepoints in expandable details. `width` supplies terminal
dimensions and rulers. Printed samples
are not automated success checks. `coverage` checks the distinct sample
codepoints against one fontconfig-selected face; it cannot validate shaping,
ligatures, fallback appearance, emoji sequences, or real application rendering.
The matched face is always shown so fontconfig substitution is visible.

## Installation

The small catalog uses the latest official Nerd Fonts GitHub release. User
installation is under `$XDG_DATA_HOME/fonts/agentoo` (default
`~/.local/share/fonts/agentoo`); `--system` uses `/usr/local/share/fonts/agentoo`
and requests sudo as needed. `--variant standard|mono|propo` defaults to
standard. Symbols-only archives are installed together. Upstream SHA-256 asset
digests or release checksum files are verified when provided; otherwise the
command explicitly reports that no upstream checksum was available. Licenses
are retained, and a manifest records the downloaded version and hash.
Reinstallation replaces the same managed catalog entry/variant. Installation
never changes application configuration. Removal prompts and only removes a
manifest-bearing Agentoo directory. Check active selections before removing.
`noto-cjk`, `noto-emoji`, and `unifont` are also available as Gentoo system
packages for broader fallback coverage. Package installation requests privileges
and uses Portage confirmation regardless of the user-font default.
Terminus installation uses `emerge --ask media-fonts/terminus-font`; manage
package removal with Portage. Nerd Font TTF/OTF files are not console PSF fonts.

## Kitty and console

Kitty changes affect only the real user `agentoo-fonts.conf` fragment and its
include in the user `kitty.conf`. Existing system settings, symbol maps and
other includes are preserved. Reload Kitty's configuration or open a new window
after applying. Later settings or launch-time overrides can supersede the
fragment. The native chooser edits this same fragment.

Kitty preview opens a separate window with a temporary font override and the
sample collection. Press `a` to save, `r`/Escape/Ctrl+C to close without saving.
Console preview temporarily saves the active font/map, displays samples, then
waits indefinitely for those same keys. It restores the snapshot before saving
an accepted selection. Ordinary interruption restores too; forced process kill
or power loss cannot run cleanup. Console preview must run interactively; use
`--console /dev/ttyN` to identify a console explicitly from another terminal.
No tmux settings are changed. Console persistence changes only FONT in
`/etc/vconsole.conf`.

There is no persistent undo history or backup collection. Each applied change
prints a shell-quoted revert command. Keep that command if needed. When no
console FONT was configured previously, the printed command resets to the boot
default and clears FONT; it cannot recreate an unidentified manually loaded
font after the temporary snapshot has been deleted. Do not remove a font needed
by a revert command.

## Firefox

```sh
agentoo fonts preview 'Noto Sans' --target firefox
agentoo fonts fallback show --target firefox --role monospace --script x-western
agentoo fonts fallback add 'Symbols Nerd Font' --target firefox --role monospace --script x-western
agentoo fonts fallback add 'Noto Sans' --target firefox --role sans-serif --script x-unicode
agentoo fonts set 'Liberation Mono' --target firefox --role monospace
```

The local HTML page compares existing generic fonts with an adjustable candidate
stack and size. It includes a fallback mode, codepoints, and all the shared
samples. The page does not mutate preferences. After inspecting, close Firefox and return
to the terminal: `a` saves the command-line family/role/script; `r`/Escape/Ctrl+C
leaves preferences unchanged. HTML control adjustments are visual only and do
not change the selection saved by the CLI. Use `preview --fallback` to accept
as a fallback instead of changing the primary font. `--no-open` only generates
the page and never prompts or applies settings. Inspect actual rendered fonts
with Firefox Inspector's Fonts panel; CSS stacks and fontconfig candidates alone
cannot establish which font rendered each character. HTML previews are stored
in a single cache file unless `--output` supplies another path. No local server
or extension is needed.

Persistent Firefox settings require the selected profile to be closed.
`--profile NAME` selects explicitly; the installation-default profile is used
only when unambiguous. `set` changes `font.name.ROLE.SCRIPT`; `fallback` edits
`font.name-list.ROLE.SCRIPT` while leaving primary font preferences alone.
Default role/script are monospace/x-western. Changes take effect on next start.
Exact font-pref revert commands use the `preference` subcommand and update both
user.js and persisted prefs.js when clearing a preference. Existing unrelated
preferences are preserved.

Fallback changes are script/role specific, not a universal Unicode switch. An
explicit list replaces that preference's built-in list; it cannot guarantee that
a website, privacy setting, or already-present primary glyph will use the new
font. Keep Latin reference text visible and test actual problem pages. The tool
does not force website fonts, change browser chrome, disable privacy protection,
or install user-wide fontconfig rules. Nerd Font icons require compatible PUA
codepoints; Unicode support alone does not establish Nerd Font coverage.

References: [Nerd Fonts releases](https://github.com/ryanoasis/nerd-fonts/releases),
[Firefox font preferences](https://github.com/mozilla-firefox/firefox/blob/main/modules/libpref/init/all.js),
[Firefox Fonts inspector](https://firefox-source-docs.mozilla.org/devtools-user/page_inspector/how_to/edit_fonts/).

## Development checks

```sh
python3 -m unittest discover -s usr/local/share/agentoo/fonts/tests -v
python3 usr/local/share/agentoo/commands/fonts.py test all --target firefox --no-open --output /tmp/fonts.html
```
