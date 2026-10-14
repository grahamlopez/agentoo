# Revisit vconsole fonts and tmux borders

Created: 2026-10-14
Status: Backlog

## Requested work

Revisit virtual console fonts as part of Agentoo's broader font policy. Choose
readable text, a comfortable size, and suitable Unicode coverage, then reconcile
tmux borders and pane labels with that choice. This work is deferred; tracking
this card does not authorize font installation or configuration changes.

## Findings

- Legacy `~/local/legacy-configs/dots/.tmux.conf` and Agentoo's `etc/tmux.conf`
  have identical appearance settings. Both select `pane-border-lines heavy` and
  `pane-border-format '#[align=right] #P ━━━'`. Their functional differences
  concern extended keyboard input, not borders.
- The affected tmux client reported `terminal=linux utf8=1`, and its effective
  pane border setting was `heavy`.
- Directly printing thin box-drawing characters worked; heavy characters did
  not. The active console Unicode map contained `0xc4 U+2500` (thin horizontal)
  and `0xb3 U+2502` (thin vertical), but no U+2501 (heavy horizontal) or U+2503
  (heavy vertical). Missing heavy-line mappings explain this failure; changing
  the locale or TERM does not supply the missing font glyphs.
- Setting `pane-border-lines single` improved the borders. The three marks
  beside pane numbers remained separate because they are literal heavy Unicode
  characters in `pane-border-format`, independent of the border style.
- Agentoo's `/etc/vconsole.conf` specifies a keymap but no font. The precise
  identity of the originally loaded font was not established.

## Font trials

- Installed `eurlatgr` maps all heavy border characters used by tmux, with
  several mapped to double-line glyphs. The user disliked its appearance.
- Installed `Lat2-Terminus16` was too small. Its map aliases U+2501 to the thin
  horizontal glyph and lacks U+2503, so it does not resolve heavy borders.
- Installing `media-fonts/terminus-font` and trying `ter-v24n`, `ter-v32n`, or
  bold variants was suggested. No trial results for those variants were
  confirmed; no font choice was accepted for persistence.

## Investigation and completion criteria

- Evaluate readable sizes and text appearance on the intended console displays
  alongside Unicode coverage. Inspect actual glyph shapes and mappings rather
  than assuming UTF-8 support guarantees coverage.
- Decide whether to retain heavy tmux borders or use thin borders with matching
  pane labels. A known thin-line workaround is:

  ```tmux
  set -g pane-border-lines single
  set -g pane-border-format '#[align=right] #P ───'
  ```

- Validate direct printing of thin and heavy lines, tmux corners and junctions,
  and the three marks beside pane numbers. Check console readability and any
  color effects of the selected font, plus tmux appearance in graphical terminals.
- Document the chosen font package, size, persistence in `/etc/vconsole.conf`,
  and restoration procedure. Verify persistence after reboot before completion.

## Diagnostic and restoration notes

From the affected console outside tmux, `sudo setfont -ou
/tmp/console-unicode-map` saves the current Unicode map without loading a font.
Inspect it with `rg -i '2500|2501|2502|2503' /tmp/console-unicode-map`.

Before a future font trial, save the active font and map with
`sudo setfont -O /tmp/console-font-backup.psf`; restore with
`sudo setfont /tmp/console-font-backup.psf`. That backup path was suggested during
this investigation; confirm it exists before relying on it. Keep a durable
backup if restoration is needed across reboots.
