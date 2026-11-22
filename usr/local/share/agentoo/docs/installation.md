# Installation, first boot, and user setup

The installer is `usr/local/share/agentoo/installer/gentoo-install.sh`; its
source and `--verbose` output describe each phase.

## Installer policy

The explicit `--target-host NAME` selects `agentoo:hosts/NAME` with native
`eselect profile set` during Portage foundation, after both repositories are
available and before the initial world update. `/etc/portage/make.profile` is the
only persistent host selector. Stage3's base system already supplies
`app-admin/eselect` and its profile module; the installer checks native profile
reporting before selecting the destination profile. Later phases reject a target
that differs from the selected profile. See [host selection](../../../../../etc/agentoo/README.md#host-selection).

Bequiet installation configures the binary fallback kernel and packaged NVIDIA
open modules; its custom native `gentoo-kernel` workflow is documented in the
[kernel guide](kernel.md#bequiet-modules-and-nvidia) and its
[hardware baseline](hosts/bequiet.md).

The initial world update excludes NVIDIA drivers to defer their kernel dependency
until boot inputs exist. The kernel phase includes `@profile` alongside the
binary fallback kernel. Native `dist-kernel` dependencies handle external
module builds; the installer then regenerates the initramfs.

Hardware packages come from the selected profile's `@profile` membership; GUI
and terminal sets remain optional environment choices. Installer transactions
prefer signed official binaries and let Portage check USE/dependency compatibility
and fall back to source builds. Agentoo profiles inherit the supported upstream
baseline; no exact upstream profile symlink is required by the binhost check.

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

At install time, the installer activates the host kernel fragment symlink,
records local initramfs inputs, and applies shared tmpfiles rules for the
custom installkernel link and sbctl hook mask; the custom package selects its
prepared tree via native `eselect` once installed. `/etc/kernel/cmdline` holds
local boot arguments, and `/etc/kernel/gentoo-dist.version` is one-time
installer handoff data rather than a permanently maintained running-kernel
requirement. For ongoing custom kernel builds, binary fallback maintenance, and
post-firmware refreshes, see the [kernel guide](kernel.md) and
[firmware guide](firmware.md).

Physical firmware registration remains manual; QEMU installation retains
offline registration in its explicitly selected VM variable store. A
`kernel-install` hook prints the populated `agentoo kernel gen-efi-cmd` command
on the booted target without running firmware commands or changing `BootOrder`.
Automatic registration during updates is deferred.

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

Checkpoints share the disk with the original data and must be restored offline
through a controlled recovery procedure—never by replacing the active root. See
[checkpoints and offline recovery](checkpoints.md) for storage layout,
`COMPLETE` markers, and restoration steps.

## User setup

After verifying/checkpointing, run `/root/002-agentoo-setup-user.sh` interactively.
It installs Zsh, sudo, OpenSSH, Git, and the packaged `video` group, creates or validates `graham` with UID/GID 1000, a private
primary group and supplementary `wheel,portage,video`, and prompts for an account
password when none is usable and an optional SSH public key. Reruns preserve a
usable password and resume the optional Git identity choice after interruption. Conflicting identities stop setup; existing
home contents and supplementary groups are preserved. A fresh login is required
for supplementary group changes to take effect. After account setup succeeds, `002` writes the local git-ignored `tty1`
autologin drop-in and reloads systemd without restarting `tty1` (autologin
starts on `tty1`'s next start or reboot; reruns preserve matching policy and
stop on conflicting content—see
[autologin and console recovery](desktop-setup.md#autologin-screen-locking-and-console-recovery)).
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
