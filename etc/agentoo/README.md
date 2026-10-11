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

`/root/firstboot-verify-and-checkpoint.sh` is the combined interactive entry point
after boot. The installer supplies its diagnostic companion,
`/root/gentoo-firstboot-checks.sh` and sets the
combined helper's permissions to `0700`. Run it as root on the booted target,
with package operations and configuration automation idle.

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
