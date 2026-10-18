# Gentoo configuration layout

This repository is designed to be checked out with `/` as its Git work tree on
every managed host. Files at their normal system paths are therefore both live
configuration and ordinary tracked files; there is no separate deployment or
synchronization step.

Universal policy belongs in native common fragments. Host-specific policy
belongs in a native fragment named for the host and is selected through
`/etc/agentoo/target-host`. Do not copy a complete common file into a host
variant, and do not make a common file silently depend on the machine where it
was edited.

Prefer native fragment, include, matching, and drop-in mechanisms. If a future
configuration format cannot express a common layer plus a selected host layer,
document that limitation and choose an explicit configuration ownership model.
User dotfiles must be real tracked files or local overrides, never deployed
copies or symlinks. See `/usr/local/share/agentoo/docs/README.md` for the configuration philosophy.

The supported initial host names are `generic`, `qemu`, `thinktop`, and `startop`.
Startop matches Thinktop's shared-memory build directory and twelve-job build
limit, while retaining universal CPU flags until its hardware is identified.
The installer prints
its EFI registration command with the full device path required by its firmware.
`target-host` is intentionally local state rather than a tracked file because
its value differs between installations. It contains the Portage-compatible
assignment `GENTOO_TARGET_HOST="name"` so `make.conf` can source it directly.
Hyprland also reads that assignment as data and automatically loads the tracked
`/etc/xdg/hypr/hosts/name.lua` fragment when present; no separate Hyprland host
selector is required.

Kernel firmware requirements use shell assignment fragments under
`/etc/agentoo/kernel-firmware.d/`: the installer reads `00-common` first,
then `90-${GENTOO_TARGET_HOST}` when present. `SOF_FIRMWARE` must be `yes` or
`no`; the common default is `no`, and `thinktop` enables it for its audio DSP.
These files describe the target hardware, independent of the installation host.

## First-boot verification and checkpoint

`/root/001-firstboot-verify-and-checkpoint.sh` is the combined interactive entry point
after boot. It is tracked in agentoo; the installer sets its permissions to
`0700`. Run it as root on the booted target, with package operations and
configuration automation idle. Use `--verify-only` for diagnostics without
cleanup, checkpoint preflight, or a checkpoint prompt. Diagnostics report time and journal history using packaged logging defaults; checkpoint preflight additionally requires synchronized time.

After required verification succeeds, a short plan asks whether to remove
cached distfiles and binary packages and capture the fresh-install checkpoint. Declining leaves
installation files unchanged. Each attempt has a unique timestamp; existing
checkpoints are never overwritten. The helper is specialized for the installer's
root/home layout and ordinary `/var/cache/{distfiles,binpkgs,binhost}` caches, not a general
scheduled application-backup tool.

Snapshots and the manifest live in `gentoo-checkpoints/<name>` at the Btrfs top
level. The gzip-compressed EFI archive (`efi-files.tar.gz`), boot-entry recovery instructions, and
checksums live in `/boot/checkpoints/<name>`. Both locations must contain
`COMPLETE` markers before restoration. Failed attempts are retained for review;
retry creates a new attempt. Capture is live and sequential across subvolumes.
Restoration must occur through a controlled reboot/recovery procedure, not by
replacing the active root. Checkpoints share the disk with the original data.

## User setup

After verifying/checkpointing, run `/root/002-agentoo-setup-user.sh` interactively.
It installs Zsh, sudo, OpenSSH, Git, and the packaged `video` group, creates or validates `graham` with UID/GID 1000, a private
primary group and supplementary `wheel,portage,video`, and prompts for an account
password when none is usable and an optional SSH public key. Reruns preserve a
usable password and resume the optional Git identity choice after interruption. Conflicting identities stop setup; existing
home contents and supplementary groups are preserved. A fresh login is required
for supplementary group changes to take effect. No skeleton dotfiles are copied.
After installing packages, setup reapplies Agentoo's file permission policy so
shared Git configuration remains readable when configuring Graham's identity.
Setup separately offers a Git identity for Agentoo commits as root, stored in
`/var/lib/agentoo/repository.git/config`. Both prompts default to
`graham (@<hostname>)` and `m477@duck.com`; existing identity fields are preserved.
Each choice has its own completion marker, so rerunning setup on a machine that
already completed Graham's identity setup still offers the Agentoo identity step.

The managed sudo policy requires Graham’s password. SSH keys remain local in
`/home/graham/.ssh/authorized_keys`, labeled `agentoo:graham:ssh-login` plus any
original source comment. Skipping a key does not enable password SSH login.
A Graham-specific SSH drop-in disables password and keyboard-interactive login.
The helper validates this policy and reloads SSH if already running; it does not start it. Verify a new
Graham login and `sudo -k; sudo -i` before closing the root console.

## Git updates

`agentoo git` accepts Git subcommands, aliases, and options directly, using
`/var/lib/agentoo/repository.git` with `/` as the work tree. For example,
`agentoo git br` and `agentoo git --no-pager log -5` work like their Git
equivalents. `setup-hooks` and `enable-write` are Agentoo helper commands.

Commands run as root; invoking the wrapper as an ordinary user requests sudo
authorization automatically. Git identity, configuration, and SSH access then
come from root's context.
If identity setup was skipped, configure it with
`agentoo git config --local user.name "Your Name"` and
`agentoo git config --local user.email "you@example.com"` before committing.

The shared Git configuration trusts `/var/db/repos/gentoo`, matching the entry
Portage adds for its Git repository backend.

Git aliases in `/etc/gitconfig` are shared by root and ordinary users. They work
with both `git` and `agentoo git`; no root-local copy is needed. To verify the
effective aliases and their source, run
`git config --show-origin --get-regexp '^alias\.'`. Account-local and repository
settings can override the shared defaults.

The installer configures `pull.rebase=true` locally in the live Git database, so
`agentoo git pull` rebases local commits by default. For an existing installation:
`agentoo git config --local pull.rebase true`. This setting persists in
`/var/lib/agentoo/repository.git/config`; it is separate from development-clone
settings. Commit or reconcile live edits before pulling; updates immediately
change system files, and Git hooks restore managed permissions.

## Shell and editor environment

The console uses `/etc/vconsole.conf` to select the tracked US keymap at
`/usr/share/keymaps/i386/qwerty/us-caps.map.gz`, where Caps Lock acts as Control.
This takes effect when systemd sets up the console on boot.

Shared defaults:

- Shell: `/etc/zsh/{zprofile,zshrc}`
- Git: `/etc/gitconfig`
- Vim: `/etc/vim/vimrc`
- Neovim: `/etc/xdg/nvim/`
- Tmux: `/etc/tmux.conf`
- SSH client: `/etc/ssh/ssh_config.d/50-agentoo.conf`

The installer's first-boot foundation installs Zsh and selects it as root's login
shell. Root uses these same shared shell defaults, with a red hostname in the
prompt instead of green. Account-local shell files can override the defaults.

Install tools with `emerge --ask --noreplace @terminal-env`. Package config
protection may produce `._cfg*` files; review these before replacing managed defaults.

For Zsh's packaged `zprofile`, the shared version retains Gentoo's environment
setup, profile scripts, and Nano editor fallback, then prefers Neovim or Vim
when installed. When the pending package file contains only that base setup,
keep the managed version (`z` in `dispatch-conf`, zap the new file). Review any
future package changes before discarding them.

Normal user configs remain local overrides, with no copied or symlinked dotfiles.

- Personal Git identity belongs in user-owned `~/.gitconfig-local`, already
  included by the shared configuration.
- Outgoing SSH keys and local host includes stay in the user’s home.
- Shared SSH defaults preserve an existing or forwarded agent.

## Minimal GUI

The optional [minimal Hyprland base](../../usr/local/share/agentoo/docs/gui-base.md)
uses `@gui-base`, shared Lua defaults under `/etc/xdg/hypr/`, and explicit TTY
launch. Read its installation and physical validation procedure before applying
it on a target.

### Kitty host defaults

Kitty loads `/etc/xdg/kitty/kitty.conf` before user configuration. Its native
`geninclude` runs `/usr/local/share/agentoo/kitty/host-config.py` when configuration
is loaded, including on startup and reload. The helper reads
`/etc/agentoo/target-host` as data and outputs the selected
`/etc/xdg/kitty/hosts/<name>.conf` fragment. Missing selectors or host fragments
leave Kitty's defaults in effect; malformed selectors and other read errors are
reported. The helper must be executable, as recorded in the permissions policy.

Thinktop sets `font_size 10.0`. Other hosts retain Kitty's default size.
User configuration, such as `~/.config/kitty/kitty.conf`, takes precedence;
remove a local `font_size` override to inherit the managed host setting.
No home configuration file, launch wrapper, or generated host include is needed.

## Optional systemd features and snapshot boundaries

- /srv, /var/lib/machines, and /var/lib/portables use ordinary directories.
- Same-named files in /etc/tmpfiles.d override vendor subvolume-creation rules;
  unrelated rules are retained. Review vendor changes when updating systemd.
- /etc/agentoo/masked-units.conf lists unused image/container units masked by the
  installer immediately after checkout. Existing hosts require explicit application.
- Unmasking does not remove the directory overrides or importd's ordinary-image
  defaults. Explicit image clones/ephemeral containers can still create subvolumes;
  review checkpoint coverage before enabling those operations.
- Nested subvolumes are excluded from root snapshots. Do not reintroduce them
  without changing and testing the checkpoint/recovery design.

## Installer policy and updates

Physical installation runs on the destination hardware. The fixed encrypted
Btrfs layout is `@` for root and `@home` for home; QEMU/NBD is a separately
supported host-backed installation path. Installer package transactions use
host-visible `/dev/shm` by default; `--no-ram-builds` selects `/var/tmp` for an invocation,
including its child chroot phases. QEMU's booted guest uses normal disk-backed
build storage.

Handoff verifies the installation and prints cleanup/boot guidance. It leaves
target mounts and LUKS open; teardown is manual. QEMU images must be unmounted,
closed, and detached from NBD before starting the guest. Automatic teardown was
removed after repeated namespace-holder failures made its complexity excessive.

Kernel policy is tracked in `/etc/portage/package.use/kernel`,
`/etc/kernel/install.conf`, and `/etc/dracut.conf.d/agentoo-dist.conf`.
The stable binary distribution kernel remains the fallback; the future custom
image workflow is separate and undefined. `/etc/kernel/cmdline` contains local
boot arguments. `/etc/kernel/gentoo-dist.version` is one-time installer handoff
data, not a permanently maintained running-kernel requirement.

Physical firmware registration remains manual. QEMU installation retains offline
registration in its explicitly selected VM variable store. See the installation
runbook for copy/paste registration after kernel updates. A small kernel-install
hook prints the populated command on the booted target; it never runs firmware
commands or changes BootOrder. Automatic registration during updates is deferred.

Networking uses the packaged dhcpcd service and `/etc/dhcpcd.conf`, with direct
ownership of `/etc/resolv.conf`. Systemd's resolvconf shim is disabled in package
USE policy. Physical setup copies a host per-interface or common wpa_supplicant
configuration unchanged if present, otherwise prompts or defers. Referenced
external credentials/certificates need separate provisioning. NetworkManager
profile conversion is not supported. Only configured
supplicant instances are required by post-boot verification. Secrets stay in
root-only per-interface files outside Git.
When prompting, blank SSID defers setup; open networks have an explicit yes/no
choice. For protected networks, wpa_passphrase reads the password directly from
the terminal with echo disabled, without putting it in command arguments.

Journald inherits packaged storage and retention defaults. The tracked monthly
scrub timer and ordinary-directory systemd storage policy remain intentional
Agentoo additions.
