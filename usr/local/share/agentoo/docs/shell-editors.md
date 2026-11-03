# Shell and editor environment

The console uses `/etc/vconsole.conf` to select the tracked US keymap at
`/usr/share/keymaps/i386/qwerty/us-caps.map.gz`, where Caps Lock acts as Control.
This takes effect when systemd sets up the console on boot.

Shared defaults:

- Shell: `/etc/zsh/{zshrc,zlogin}`, after Gentoo's packaged `zprofile`
- Git: `/etc/gitconfig`
- Vim: `/etc/vim/vimrc.local`, loaded by Gentoo's packaged `vimrc`
- Neovim: `/etc/vim/nvimrc.local` loads `/etc/xdg/nvim/agentoo.lua` from
  Gentoo's packaged `sysinit.vim`
- Tmux: `/etc/tmux.conf`
- SSH client: `/etc/ssh/ssh_config.d/50-agentoo.conf`

The installer's first-boot foundation installs Zsh and selects it as root's login
shell. Root uses these same shared shell defaults, with a red hostname in the
prompt instead of green. Account-local shell files can override the defaults.

Install tools with `emerge --ask --noreplace @terminal-env`. Portage owns
`/etc/zsh/zprofile`, `/etc/vim/vimrc`, and `/etc/vim/sysinit.vim`; Agentoo uses
their native extension points. The shared Git ignore policy excludes those
vendor entries to prevent adding them again. Accept package updates to these
entry files after review in `dispatch-conf`.

No vendor configuration is copied into the repository.

Gentoo's Zsh profile loads the distribution environment and `/etc/profile.d/`.
Agentoo's interactive `zshrc` prefers Neovim, then Vim; personal startup files
can override that choice. Desktop launch waits until all personal startup files,
including `.zlogin`, have run; see [console recovery and startup](gui-base.md#automatic-login-and-console-recovery).

Vim retains its upstream defaults before Agentoo preferences. Both editors also
receive Gentoo's native shell syntax, cursor restoration, ebuild indentation,
and crontab writing policy. Neovim's packaged configuration strips trailing
whitespace when writing ebuilds and eclasses. Personal `.vimrc` and Neovim
`init.lua`/`init.vim` load afterward; filetype-specific overrides can use native
`after/ftplugin/` files.

Neovim applies shared appearance defaults during initialization and on
`ColorScheme`, in the native `agentoo_appearance` autocommand group. Personal
highlight settings survive ordinary option and window changes; register a later
personal `ColorScheme` callback to retain them across theme changes, or clear
that group to disable shared theme updates. Window-local keyword matches use
`agentoo_todo_matches`. `:TransparentToggle` changes backgrounds while preserving
foregrounds and other styles.

Normal user configs remain local overrides, with no copied or symlinked dotfiles.

- Personal Git identity belongs in user-owned `~/.gitconfig-local`, already
  included by the shared configuration.
- Outgoing SSH keys and local host includes stay in the user’s home.
- Shared SSH defaults preserve an existing or forwarded agent.
