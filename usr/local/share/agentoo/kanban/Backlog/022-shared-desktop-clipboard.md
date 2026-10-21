# Restore shared clipboard across Neovim, tmux, and Hyprland

Created: 2026-10-21
Status: Backlog

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
