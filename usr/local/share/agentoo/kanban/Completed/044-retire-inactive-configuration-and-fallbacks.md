# Retire inactive configuration experiments and unnecessary fallbacks

Created: 2026-10-31
Status: Completed
Priority: Lower

The critical review found inherited material that makes the supported path
harder to identify:

- [Neovim configuration](../../../../../../etc/xdg/nvim/agentoo.lua) retains
  commented Windows/WSL, LSP, and viewer implementations marked proposed removal.
- [Vim](../../../../../../etc/vim/vimrc.local) and
  [tmux](../../../../../../etc/tmux.conf) retain disabled experiments and obsolete
  explanatory references to those settings as active.
- [Zsh](../../../../../../etc/zsh/zshrc) searches five cross-distribution Git-prompt
  locations, including a 536-line vendored copy of `shell/git-prompt.sh`.
  The installed Gentoo Git package already supplies `/usr/share/git/git-prompt.sh`.
- [The ignore policy](../../../../../../etc/agentoo/gitignore) also described the
  retired `hyprland-host.lua` selector as current policy; card 039 removed it.

Remove superseded implementations and unnecessary lookup paths. Move useful
future ideas into backlog/history rather than leaving dormant implementations in
active configuration. Verify the supported Gentoo package supplies the selected
prompt path before removing the vendored copy. Keep comments that explain active
policy, concrete failure risks, and evidence-backed workarounds.

Complete when active configuration presents the supported behavior directly,
without changing retained features. Run relevant native shell/editor/tmux syntax
or startup checks and confirm the Git prompt still works with packaged support.
Coordinate ignore-policy edits with
[card 039](../Completed/039-ignore-local-host-and-boot-identity.md).


## Completion, 2026-10-31

Removed commented WSL/Windows, language-server/diagnostic and Glow
implementations, unused settings, and long future-idea lists from shared Neovim
configuration. Removed disabled Vim folding, completion, coloring, numbering,
Fortran, terminal-key and clipboard experiments. Removed tmux's disabled
agent-specific extended-key settings and obsolete option examples, and corrected
its stale claim of a second active `terminal-features` assignment.

Zsh now sources only Gentoo's `/usr/share/git/git-prompt.sh`, guarded for an
absent package. The installed Git package owns that path and its ebuild installs
it unconditionally; `@terminal-env` already includes Git. Removed the duplicate
vendored script and cross-distribution lookup paths. Current prompt policy and
home-directory suppression are unchanged. The ignore-policy cleanup was already
completed by card 039.

Active Vim, Neovim and tmux non-comment content was compared byte-for-byte with
the preceding revision and is unchanged, including card 042's appearance logic.
Preserved active ESC/terminfo workarounds, native package behavior, personal
precedence, clipboard/movement bindings, transparency and Tree-sitter logic.

Validation passed: three native Neovim tests and eight shell/editor tests, Zsh
syntax checking, and disposable full Zsh startup rendering a packaged Git prompt
while retaining home-directory suppression. An isolated native tmux server loaded
the cleaned configuration; global/server options and all key bindings exactly
matched its pre-cleanup baseline. Its private temporary socket was the only tmux
server accessed. No live editor, shell, desktop or tmux session was changed.

## Retained ideas and evidence

Unselected editor ideas remain available in the original configuration history:
native/Lua completion and diagnostics; undo/folding navigation and persistence;
Markdown tables, previews/images, writing modes, links/PKM and theming. The old
reference lists also record word-count display and folded Markdown `conceal_lines`
investigations. These are historical leads, not newly selected features or active
workarounds. Recheck current native behavior before implementing any of them.

Exact pre-cleanup revision: `10f6c18d62053d578fee3656e1d66c58f2fba083`.

```sh
git show 10f6c18d62053d578fee3656e1d66c58f2fba083:etc/xdg/nvim/agentoo.lua
git show 10f6c18d62053d578fee3656e1d66c58f2fba083:etc/vim/vimrc.local
git show 10f6c18d62053d578fee3656e1d66c58f2fba083:etc/tmux.conf
git show 10f6c18d62053d578fee3656e1d66c58f2fba083:etc/zsh/zshrc
git show 10f6c18d62053d578fee3656e1d66c58f2fba083:usr/local/share/agentoo/shell/git-prompt.sh
```
