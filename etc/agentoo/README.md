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
cleanup, checkpoint preflight, or a checkpoint prompt. Diagnostics report time
state; checkpoint preflight additionally requires synchronized time.

After required verification succeeds, a short plan asks whether to remove
downloaded distfiles and capture the fresh-install checkpoint. Declining leaves
installation files unchanged. Each attempt has a unique timestamp; existing
checkpoints are never overwritten. The helper is specialized for the installer's
root/home layout and ordinary `/var/cache/distfiles` cache, not a general
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
It installs Zsh, sudo, and OpenSSH, creates or validates `graham` with UID/GID 1000, a private
primary group and supplementary `wheel,portage`, and prompts for an account
password and optional SSH public key. Conflicting identities stop setup; existing
home contents and supplementary groups are preserved. No skeleton dotfiles are copied.

The managed sudo policy requires Graham’s password. SSH keys remain local in
`/home/graham/.ssh/authorized_keys`, labeled `agentoo:graham:ssh-login` plus any
original source comment. Skipping a key does not enable password SSH login.
A Graham-specific SSH drop-in disables password and keyboard-interactive login.
The helper validates this policy and reloads SSH if already running; it does not start it. Verify a new
Graham login and `sudo -k; sudo -i` before closing the root console.

## Git updates

The installer configures `pull.rebase=true` locally in the live Git database, so
`agentoo-git pull` rebases local commits by default. For an existing installation:
`agentoo-git git config --local pull.rebase true`. This setting persists in
`/var/lib/agentoo/repository.git/config`; it is separate from development-clone
settings. Commit or reconcile live edits before pulling; updates immediately
change system files, and Git hooks restore managed permissions.

## Shell and editor environment

Shared defaults live in `/etc/zsh/{zprofile,zshrc}`, `/etc/gitconfig`,
`/etc/vim/vimrc`, `/etc/tmux.conf`, `/etc/xdg/nvim/`, and the SSH client drop-in
`/etc/ssh/ssh_config.d/50-agentoo.conf`. Install tools with
`emerge --ask --noreplace @comfy_env`. Package config protection may produce
`._cfg*` files; review these before replacing the Git-managed defaults.

Normal user configs remain local overrides, with no copied or symlinked dotfiles.
Set Graham’s author identity once with `git config --global user.name` and
`git config --global user.email`; outgoing SSH keys and local host includes stay
in his home. Shared SSH defaults preserve an existing/forwarded agent.

Deferred legacy sections are commented with `proposed removal` for review.
The Markdown query archive stays outside runtime query paths. GUI startup,
agent tooling, language managers, and automatic root tmux sessions are deferred.
Neovim requires version 0.11 or newer. Vim is a small fallback configuration;
Neovim retains Space as leader while Vim retains its default backslash leader.
User history, caches, undo, and spell additions stay in writable user storage.
