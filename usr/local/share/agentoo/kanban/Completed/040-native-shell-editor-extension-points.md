# Use native shell and editor extensions instead of replacing vendor entry files

Created: 2026-10-31
Status: Completed
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

Completed on 2026-10-31 with [card 038](038-desktop-shell-startup-order.md).
Portage now owns all three vendor entry files without tracked replacements.
The authoritative shared Git ignore policy excludes their exact paths, keeping
restored package entries from being staged again while extensions remain addable.
Vim preferences live in its native `vimrc.local`; Neovim's native `nvimrc.local`
loads the existing shared Lua file. Project-owned `zshrc` retains interactive
preferences and editor selection; project-owned `zlogin` schedules desktop
startup after personal `.zlogin`. Neither Zsh file belongs to the installed
package, as verified from its VDB contents.

Gentoo's Vim entry suppresses `defaults.vim`, so the local preference file
explicitly clears that skip flag before retaining Agentoo's existing upstream
baseline. Disposable option comparisons showed a simple rename would otherwise
lose key timeouts, mouse support, truncated-line display, and numeric/language
mapping defaults. Native Gentoo cursor, syntax, ebuild and crontab policies now
apply; duplicate project crontab and Neovim ebuild policies were removed, leaving
only the soft-tab delta. Neovim's newly active native ebuild whitespace stripping
is documented. Personal editor files still load afterward; filetype overrides
can use native `after/ftplugin/` files.

[Configuration guidance](../../../../../../etc/agentoo/README.md) now explains
ownership and deployment: pulling these tracked removals deletes the live vendor
files on existing installations. Remerge their packages and accept the native
replacements through `dispatch-conf`, including protected updates to missing
files, before opening another shell or editor. No vendor files are copied into
the repository and no automatic migration mechanism was added.

Validation: all eight disposable checks in `test_shell_editors.py`
passed without skips. Vim and Neovim execute Gentoo's actual package defaults,
then the real project extension and personal overrides; checks cover retained
Vim upstream defaults, project preferences, personal precedence, and native
ebuild/crontab behavior. Zsh checks cover the paired startup ordering change.
`zsh -n` and `git diff --check` passed. No live package configuration was changed.
Disposable Git checks also confirm the three vendor exclusions and that native
project extensions remain eligible for staging.
The separate appearance precedence issue remains in
[card 042](042-neovim-local-override-precedence.md).
