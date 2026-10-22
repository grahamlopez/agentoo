# Restore shared clipboard across Neovim, tmux, and Hyprland

Created: 2026-10-21
Status: Open
Opened: 2026-10-22

Restore the legacy configuration's clipboard workflow so text copied in Neovim,
tmux copy mode, and Hyprland applications can be pasted across all three.

- Review `~/local/legacy-configs/dots` and `dots-gui` for the working Neovim,
  tmux, terminal, and Wayland clipboard integration. Legacy Neovim uses
  `unnamed`/`unnamedplus`; Hyprland starts a `wl-paste` watcher for `cliphist`.
- Reconcile Agentoo's existing Neovim clipboard settings with tmux copy/paste,
  terminal support, and `wl-copy`/`wl-paste`; restore relevant legacy bindings
  and clipboard history/picker behavior where needed.
- Verify bidirectional copy/paste between Neovim inside tmux and graphical
  applications, including multiline text, after a fresh Hyprland login.
  Document required packages and bindings.

## Current assessment (2026-10-22)

Neovim already enables `unnamed`/`unnamedplus`, and wl-clipboard is installed.
The running tmux server uses `set-clipboard external` and exposes OSC 52 (`Ms`)
to its Kitty client. User testing confirmed the existing sharing behavior below.
Clipboard history remains in scope: cliphist, a session watcher, and a picker
are currently absent. Prefer the existing legacy Kitty/fzf approach where useful.

## Baseline results reported by user (2026-10-22)

All requested basic sharing paths passed. Kitty mouse selection inside Neovim
initially failed, but the user subsequently confirmed Shift+drag and
Ctrl+Shift+C work; no mouse configuration change is needed. Neovim reports
`mouse=nvi` and `mousemodel=popup_setpos`.

- [x] Graphical app -> Kitty paste.
- [x] Kitty mouse selection/copy -> graphical app outside Neovim.
- [x] Neovim inside tmux linewise yank -> graphical app.
- [x] Neovim visual selection + yank -> graphical app.
- [x] Graphical app -> Neovim `p`.
- [x] Neovim yank -> `p` in Neovim in a different tmux context.
- [x] tmux copy -> graphical app.
- [x] tmux copy -> tmux paste (`Ctrl+A`, `]`).
- [x] Neovim <-> graphical app outside tmux.
- [x] Neovim yank, then exit -> graphical app.
- [x] tmux copy -> Neovim `p`.
- [x] Neovim yank -> Kitty paste (`Ctrl+Shift+V`).
- [x] Kitty mouse copy (`Ctrl+Shift+C`) -> Neovim `p`.

- [x] Kitty Shift+drag inside Neovim, then Ctrl+Shift+C -> graphical app.

## Accepted buffer behavior and scope decision (2026-10-22)

Neovim yank -> tmux paste (`Ctrl+A`, `]`) does not transfer the yank: Neovim
updates the desktop clipboard, while this binding reads tmux's independent
buffer. The user explicitly chose to preserve this behavior and use either:

- Neovim yank, then Kitty paste (`Ctrl+Shift+V`).
- tmux copy mode over text displayed in Neovim, then tmux paste (`Ctrl+A`, `]`).

Do not add buffer synchronization or change the tmux paste binding. Review of
the saved legacy configs found the same Neovim clipboard settings and no tmux
clipboard bridge or custom paste binding. The legacy history picker also only
updated the desktop clipboard.

Clipboard history remains required. There is no need to replace working
Neovim clipboard integration or tmux copy behavior.

## Clipboard history acceptance (after implementation)

Packaging decision: enable GURU, mask `*/*::guru`, and unmask/accept testing
keywords only for `app-misc/cliphist::guru`. These configuration files are
prepared in the checkout. Live deployment and sync remain pending because
noninteractive sudo requires a password; no package has been installed.

- [ ] Multiple graphical, Neovim, and tmux copies appear in the history picker.
- [ ] Selecting an older entry restores it to the desktop clipboard with
      multiline text, indentation, and Unicode intact.
- [ ] Cancelling the picker leaves the current clipboard unchanged.
- [ ] A fresh login starts capture automatically; Hyprland reloads do not
      accumulate duplicate watchers.
- [ ] Document history retention and how to clear stored entries.
