# Use native shell and editor extensions instead of replacing vendor entry files

Created: 2026-10-31
Status: Backlog
Priority: Medium

The review compared tracked files against installed Portage package records and
found dual ownership of `/etc/vim/vimrc` (vim-core), `/etc/vim/sysinit.vim`
(neovim), and `/etc/zsh/zprofile` (zsh). Agentoo maintains replacements and asks
operators to reconcile incoming configuration-protected package files.

Gentoo already supplies `/etc/vim/vimrc.local` and `/etc/vim/nvimrc.local`
extension points. Its Zsh profile supports `/etc/profile.d/`; Zsh also supplies
system startup files with distinct lifecycle ordering. Inspect those native
mechanisms before retaining a full vendor-file replacement.

Move Agentoo policy into suitable native extensions, preserving intended settings
and user precedence. Check which vendor defaults would become active rather than
assuming the move is behavior-neutral. Document an explicit exception if a full
replacement is necessary. No copied user dotfiles or compatibility path is needed.

Complete when each remaining tracked entry file has a justified ownership model,
and native startup checks demonstrate the intended defaults and local overrides.
Update [configuration guidance](../../../../../../etc/agentoo/README.md).
Coordinate shell changes with [card 038](038-desktop-shell-startup-order.md),
and editor precedence with [card 042](042-neovim-local-override-precedence.md).
