# Checkpoints and offline recovery

Use `agentoo checkpoint --help` (or `sh /boot/agentoo/checkpoint.sh --help`) for
all operations, component flags (`--system`/`--home`/`--efi`), cache-cleanup
defaults, `--dry-run`, and `--no-input` automation options. This runbook covers
storage layout, subvolume boundaries, and recovery without the installed root.

## Storage layout and subvolume boundaries

- **Fixed layout:** `@` for root and `@home` for home on a single Btrfs
  filesystem, with ordinary directories inside them. Nested subvolumes are
  refused because root snapshots exclude their contents.
- **Preventing nested subvolumes:** `/srv`, `/var/lib/machines`, and
  `/var/lib/portables` use ordinary directories via `/etc/tmpfiles.d/`
  overrides, and `/etc/agentoo/masked-units.conf` masks unused image/container
  units. Review checkpoint coverage before enabling container/image subvolumes.
- **Locations:** Btrfs snapshots and manifests live at top-level
  `gentoo-checkpoints/<name>`; gzip-compressed EFI archives and checksums live
  at `/boot/checkpoints/<name>`. Both locations require `COMPLETE` markers
  before restoration.
- **Size reporting (`list`):** Reports `TOTAL`, `EXCLUSIVE`, and `SHARED` file
  extents via `btrfs filesystem du --summarize` (excluding EFI, compression,
  metadata, and RAID). Shared rows are not additive across checkpoints;
  `EXCLUSIVE` indicates unique data rather than exact space reclaimed.
- **Removal retries:** Deletion across Btrfs and EFI is not atomic. `remove`
  writes a durable `REMOVING` marker first (making `inspect`/`restore` refuse
  it); if interrupted, rerun the same `remove` command.
- **Dry-run mounts:** Inspection temporarily mounts Btrfs top level read-only
  with `rescue=nologreplay` (kernel 5.9+) so offline filesystems are never
  replayed. Keep writers idle during capture or removal; package-cache cleanup
  refuses custom `DISTDIR`/`PKGDIR` paths, symlinks, or nested mounts.

## Recovery without the installed root

The implementation lives at `/boot/agentoo/checkpoint.sh` on the EFI partition
(pure POSIX `sh`, no Python or Bash dependency) outside `EFI/` so restoring
boot files never overwrites the running tool. Recovery media runs it directly
without mounting or executing anything from the installed root.

**Required recovery environment tools:** POSIX `sh`, GNU coreutils (`readlink`,
`stat`, `sha256sum`, `mktemp`), POSIX `awk`/`find`, `btrfs-progs` (kernel 5.9+
for `rescue=nologreplay`), `util-linux` (`findmnt`, `flock`), `procps`
(`pgrep`), `tar`, `gzip`, and `cryptsetup`.

Unlock the target and mount its EFI partition (replace partition placeholders;
leave target Btrfs subvolumes unmounted, and do not run from a chroot/container
that hides mounts):

```sh
cryptsetup open /dev/<encrypted-partition> cryptroot
mkdir -p /mnt/esp
mount /dev/<efi-partition> /mnt/esp
sh /mnt/esp/agentoo/checkpoint.sh list --device /dev/mapper/cryptroot
sh /mnt/esp/agentoo/checkpoint.sh inspect <name> --device /dev/mapper/cryptroot
sh /mnt/esp/agentoo/checkpoint.sh restore <name> --device /dev/mapper/cryptroot
```

The script infers `--efi-mount` from its own location and mounts Btrfs top
level itself. Default restoration replaces `@` (system) and overlays saved EFI
files while preserving `@home`. To restore only home:

```sh
sh /mnt/esp/agentoo/checkpoint.sh restore <name> --device /dev/mapper/cryptroot --home
```

### Restoration semantics and failure retry

- **No implicit backup or rollback:** `restore` stages writable snapshot copies,
  then deletes and replaces selected subvolumes. Create a named checkpoint
  beforehand if the system is still bootable.
- **If restore fails mid-way:** Stay in recovery, fix the reported cause (e.g.,
  space or hardware error), and **rerun the exact same restore command** with
  the same `--device` and component flags. Retries start fresh from the named
  checkpoint and handle missing current subvolumes or leftover staging copies.
  Never boot a partially restored system.
- **EFI and firmware:** Later EFI files remain untouched by the overlay.
  Firmware NVRAM entries are unchanged; use the saved firmware listing in the
  checkpoint as a reference for manual `efibootmgr` repair, then reboot and
  verify.

## Boundaries

- Creation is online-only and sequential across subvolumes (no application or
  cross-component atomicity; offline capture is deferred in
  [card 004](../kanban/Backlog/004-offline-checkpoint-creation.md)).
- On-disk checkpoints do not protect against disk failure.
- Scheduling and retention are manual; deletion uses explicit `remove`.
