# Retire inactive configuration experiments and unnecessary fallbacks

Created: 2026-10-31
Status: Backlog
Priority: Lower

The critical review found inherited material that makes the supported path
harder to identify:

- [Neovim configuration](../../../../../../etc/xdg/nvim/agentoo.lua) retains
  commented Windows/WSL, LSP, and viewer implementations marked proposed removal.
- [Vim](../../../../../../etc/vim/vimrc) and
  [tmux](../../../../../../etc/tmux.conf) retain disabled experiments and obsolete
  explanatory references to those settings as active.
- [Zsh](../../../../../../etc/zsh/zshrc) searches five cross-distribution Git-prompt
  locations, including a [536-line vendored copy](../../shell/git-prompt.sh).
  The installed Gentoo Git package already supplies `/usr/share/git/git-prompt.sh`.
- [The ignore policy](../../../../../../etc/agentoo/gitignore) still describes the
  retired `hyprland-host.lua` selector as current policy.

Remove superseded implementations and unnecessary lookup paths. Move useful
future ideas into backlog/history rather than leaving dormant implementations in
active configuration. Verify the supported Gentoo package supplies the selected
prompt path before removing the vendored copy. Keep comments that explain active
policy, concrete failure risks, and evidence-backed workarounds.

Complete when active configuration presents the supported behavior directly,
without changing retained features. Run relevant native shell/editor/tmux syntax
or startup checks and confirm the Git prompt still works with packaged support.
Coordinate ignore-policy edits with
[card 039](039-ignore-local-host-and-boot-identity.md).
