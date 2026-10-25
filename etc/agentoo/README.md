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

The supported initial host names are `generic`, `qemu`, `thinktop`, `startop`, and `flattop`.
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

## Flattop hardware baseline

Flattop is a Framework Laptop (13th Gen Intel Core), board FRANMCCP06 A6,
with an Intel Core i7-1360P (12 cores, 16 logical CPUs), Intel Raptor Lake-P
integrated graphics, AX211 Wi-Fi, Intel USB Bluetooth, and WD NVMe storage.
This baseline comes from `kernel-inventory-flattop-20261024T135738Z.tar.gz`,
collected on 2026-10-24 while running `6.12.21-gentoo-lopez64`.

The host Portage fragment selects Intel graphics, GCC `-march=raptorlake`,
Rust `-C target-cpu=raptorlake`, and Thinktop's operator-selected build policy:
`PORTAGE_TMPDIR="/dev/shm"` and `MAKEOPTS="-j12"`. The inventory does not report
RAM capacity. Installer transactions also default to RAM-backed builds;
`--no-ram-builds` selects disk-backed storage for an installer invocation.

The captured boot used i915, iwlwifi, btusb, nvme, and snd_hda_intel, with an
IDT 92HD95 audio codec. Keep broad linux-firmware coverage and the common
`SOF_FIRMWARE=no` policy; a DSP-detected log line alone does not establish that
SOF was used. Recheck audio and firmware requirements with the installed
distribution kernel before considering a reduced firmware list.

UEFI is evidenced by mounted efivarfs and EFI devices. System Secure Boot status
was not collected (the Bluetooth controller's secure-boot message is unrelated).
No host-specific EFI registration workaround is established. The previous
kernel config is evidence, not an Agentoo kernel configuration to install.

Before installation, confirm Secure Boot status, RAM capacity, the disk to erase,
and normal peripherals. Validate display, Wi-Fi, Bluetooth, speakers/headphones,
microphone, touchpad, and suspend/resume on the new kernel. The inventory reports
s2idle and deep sleep availability but does not exercise either. Display scaling,
fingerprint setup, and other desktop preferences remain unconfigured.

## Installed firmware selection

Thinktop enables native `linux-firmware[savedconfig]` through
`AGENTOO_LINUX_FIRMWARE_USE` in `make.conf.d/90-thinktop`. The common fragment
sets `-savedconfig`; `package.env/kernel` applies the variable only to this
package. Do not add a conflicting package.use setting: it takes precedence over
package.env. Other hosts retain broad coverage.

`/etc/agentoo/firmware/thinktop.list` is the reviewed, explicit firmware list.
The operator installs it as the machine-local
`/etc/portage/savedconfig/sys-kernel/linux-firmware`. Gentoo consumes that file
and writes a versioned snapshot after each build. Matching versioned and
triplet-specific files take precedence; move them aside when applying a revised
list. There are no Agentoo build hooks, automatic list expansion, or custom
firmware validation. For another host, review its own list before enabling
savedconfig and installing its selected input.

See the [firmware operator guide](../../usr/local/share/agentoo/docs/firmware.md)
for application, maintenance, diagnostics and recovery. This affects installed
linux-firmware only; embedded kernel firmware, SOF, CPU microcode and regulatory
data remain separate. Implementation and acceptance evidence are recorded
in [card 018](../../usr/local/share/agentoo/kanban/Completed/018-host-firmware-savedconfig.md).

## First-boot verification and checkpoint

`/root/001-firstboot-verify-and-checkpoint.sh` is the combined interactive entry point
after boot. It is tracked in agentoo; the installer sets its permissions to
`0700`. Run it as root on the booted target, with package operations and
configuration automation idle. Use `--verify-only` for diagnostics without
cleanup, checkpoint preflight, or a checkpoint prompt. Wi-Fi reporting checks
configured names against present radios and reports supplicant authentication
state, with inspection and manual interface-rename guidance when needed.
Informational hardware reports cover PCI drivers, sound cards, Bluetooth,
backlights, sleep modes, and recent firmware messages; manual functional tests
remain necessary and these reports do not gate checkpoint creation. Diagnostics
report time and journal history using packaged logging defaults; checkpoint
preflight additionally requires synchronized time.

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
for supplementary group changes to take effect. After account setup succeeds,
002 creates the local native tty1 autologin drop-in and reloads systemd without
restarting tty1. Fresh installations use normal password login until then;
autologin starts on tty1's next start or reboot. The drop-in is excluded from
Git; reruns preserve matching policy and stop on conflicting custom content.
No skeleton dotfiles are copied.
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
`geninclude` runs `/usr/local/share/agentoo/lib/kitty/host_config.py` when configuration
is loaded, including on startup and reload. The helper reads
`/etc/agentoo/target-host` as data and outputs the selected
`/etc/xdg/kitty/hosts/<name>.conf` fragment. Missing selectors or host fragments
leave Kitty's defaults in effect; malformed selectors and other read errors are
reported. The helper must be executable, as recorded in the permissions policy.

Thinktop sets `font_size 10.0`. Other hosts retain Kitty's default size.
User configuration, such as `~/.config/kitty/kitty.conf`, takes precedence;
remove a local `font_size` override to inherit the managed host setting.
No home configuration file, launch wrapper, or generated host include is needed.

The shared configuration also enables dynamic background opacity and loads the
Agentoo transparency watcher. `agentoo desktop transparency` stores personal
focused/unfocused choices in XDG state; Kitty text stays opaque. Processes
started before this integration was installed need a one-time restart. See
[window transparency](../../usr/local/share/agentoo/docs/desktop.md#window-transparency)
for inheritance, reset, conflict handling, and validation.

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

Physical installation runs on the destination hardware. The live environment may
use OpenRC: offline service masks, presets, and enablement use the target
stage3's `systemctl --root=/` through chroot. Hostname setup uses the target's
`systemd-firstboot`; machine identity uses `systemd-machine-id-setup` in the
chroot, preserving an existing valid target ID.
Systemd is required on the installed target, not on the live host. The fixed encrypted
Btrfs layout is `@` for root and `@home` for home; QEMU/NBD is a separately
supported host-backed installation path. Installer package transactions use
host-visible `/dev/shm` by default. Before target package operations, the installer
clears `noexec` on the target's inherited shm mount using a bind remount with
`exec,nosuid,nodev`; the live host's mount policy is preserved.
`--no-ram-builds` selects `/var/tmp` for an invocation,
including its child chroot phases. The installer and 002 report RAM/tmpfs capacity
without changing build policy or enforcing a capacity threshold. QEMU's booted guest uses normal disk-backed
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
