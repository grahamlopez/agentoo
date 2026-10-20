# On-demand checkpoints and recovery

As root on the booted target:

    agentoo checkpoint create terminal-env
    agentoo checkpoint list
    agentoo checkpoint inspect <exact-checkpoint-name>

Keep package/configuration tools and other writers idle during capture. Labels
receive a UTC timestamp and process ID; existing checkpoints are never overwritten.
Create and restore print their plan to stderr and require authorization. Interactive
confirmation reads terminal stdin. In automation, use `create --yes --no-input`
or `restore NAME --confirm NAME --no-input`; the latter must name the exact saved
checkpoint. `--no-input` also uses `sudo -n` and never opens `/dev/tty`.

Options may precede or follow the name, including `--device=DEVICE` and
`--efi-mount=PATH`. `--` ends option parsing. Help is available at every operation
before any privilege request or inspection. Repeated value options use the last
value; conflicting component/cache flags are rejected.

| Default | Create | Restore |
|---|---|---|
| System | Capture | Replace current system |
| Home | Capture | Preserve current home |
| EFI | Capture boot files | Overlay saved boot files |
| Distfiles and binary packages | Clean with system capture; otherwise preserve | Not applicable |

- Positive flags select exactly the specified components: `--system`, `--home`, `--efi`.
- Negative-only flags subtract from defaults: `--no-system`, `--no-home`, `--no-efi`.
- Home-only capture: `agentoo checkpoint create personal-work --home`.
- `--clean-package-caches` explicitly enables distfile and binary package cleanup
  (the default when capturing system); `--no-clean-package-caches` preserves them.
  Captures without system preserve caches by default. These options apply
  only to create.
  Explicit cleaning requires system capture. This retains the original cleanup
  default for system capture.
- Conflicting flags and empty selections are rejected.

The supported layout is `@` for root and `@home` for home on one Btrfs filesystem,
with ordinary directories inside them. Nested subvolumes are refused because a
root snapshot does not include their contents. Agentoo's documented systemd
directory policy prevents the optional storage services from introducing these.

Cleanup empties `/var/cache/distfiles`, `/var/cache/binpkgs`, and
`/var/cache/binhost`, including the Gentoo stage3's default downloaded binary
cache at `/var/cache/binhost/gentoo`. Missing caches are
skipped. Cleanup with custom `DISTDIR` or `PKGDIR` paths is refused; use
`--no-clean-package-caches` to capture without cleanup in that case.
Symlinked cache paths and mounts inside any cache are refused before deletion.
Keep any additional binhost caches inside `/var/cache/binpkgs` or
`/var/cache/binhost` to include them.

Snapshots live at Btrfs top level `gentoo-checkpoints/<name>`. EFI archives live
at `/boot/checkpoints/<name>`. Completion markers, filesystem identities,
snapshot identities and EFI archive checksums are verified before restoration.

`list` includes human-readable Btrfs `TOTAL`, `EXCLUSIVE`, and `SHARED` sizes
for each checkpoint, using `btrfs filesystem du --summarize`. Total counts file
extents referenced by the checkpoint; exclusive counts extents not shared with
other files; shared counts shared extents referenced within the checkpoint,
deduplicating overlapping shared extents in that set. Shared blocks can also be
referenced by the live system or other checkpoints, so row sizes cannot be added
to determine total snapshot overhead. Exclusive is a useful indication of unique
file data, rather than an exact prediction of space reclaimed by deletion.

This scans files and can take time on large checkpoints. It requires no quotas
and includes legacy nested snapshots. `?` means measurement was unavailable.
These are file extent figures, not exact physical disk usage: compression,
filesystem metadata and RAID replication are not accounted for. EFI archives
on the separate EFI partition are excluded.

To measure a snapshot directly when its path is mounted:

    btrfs filesystem du --summarize /path/to/snapshot

If full Btrfs quotas are already enabled, `btrfs qgroup show /` provides per-
subvolume referenced and exclusive accounting without walking every file.

## Planning, output, and automation

`create LABEL --dry-run` and `restore NAME --device DEVICE --dry-run` run the
preflight checks and print the operation plan without authorization or target
modification. They still require root, take the checkpoint lock, write temporary
files under `/run`, and temporarily mount Btrfs top level **read-only** with `rescue=nologreplay`
(kernel 5.9 or newer), preventing log replay when initially mounting an offline
filesystem. An unsupported mount fails rather than falling back to log replay.
Existing live filesystem mounts and their concurrent writers remain outside
this guarantee; the command never remounts a live filesystem read-only. EFI
verification can extract an archive into the temporary directory. They create no
snapshots, delete no caches/subvolumes, and write no EFI files. Dry-run success
is not a guarantee that subsequent writes will succeed or other writers stay idle.
The inspected EFI partition may be mounted read-only for dry-run.
The [Btrfs mount-option documentation](https://btrfs.readthedocs.io/en/latest/ch-mount-options.html)
explains why a read-only mount alone does not suppress tree-log replay.

Successful creation prints only the exact generated checkpoint name on stdout.
Plans, phase progress, verification chatter, and restore completion go to stderr.
Human list output and inspect manifests remain stdout results.

- Invalid arguments, missing privileges/tools, and operational failures exit 1.
  Declining interactive confirmation exits 0 without mutation. SIGINT/SIGTERM
  use 130/143; shell signal traps may wait for the current filesystem tool.

## Recovery without the installed root

The implementation lives at `/boot/agentoo/checkpoint.sh` on the EFI partition.
`agentoo-checkpoint` is a POSIX sh launcher. Both it and the script run without
Python or Bash; the grouped `agentoo checkpoint` dispatcher requires Python. Recovery media can run the implementation
directly without mounting or executing anything from the installed root.

Use a normal recovery environment with:

- POSIX sh and GNU core utilities, including readlink, stat, sha256sum, mktemp
- POSIX awk and find; portageq additionally for online cache cleanup
- Btrfs tools and a kernel supporting `rescue=nologreplay` (5.9+) for inspection
- util-linux tools, including findmnt and flock
- procps tools, including pgrep
- tar and gzip
- cryptsetup for unlocking an encrypted target

Unlock the target and mount its EFI partition:

    cryptsetup open /dev/<encrypted-partition> cryptroot
    mkdir -p /mnt/esp
    mount /dev/<efi-partition> /mnt/esp
    sh /mnt/esp/agentoo/checkpoint.sh list --device /dev/mapper/cryptroot
    sh /mnt/esp/agentoo/checkpoint.sh inspect <name> --device /dev/mapper/cryptroot
    sh /mnt/esp/agentoo/checkpoint.sh restore <name> --device /dev/mapper/cryptroot

Replace the partition placeholders with the target devices. The implementation
infers the EFI mount from its own location; `--efi-mount PATH` overrides it.
It mounts Btrfs top level itself. Leave selected target subvolumes unmounted.
Do not run recovery from a chroot or container that hides other target mounts.

Default restoration discards the current system and overlays saved EFI files,
while preserving home. To restore only home:

    sh /mnt/esp/agentoo/checkpoint.sh restore <name> --device /dev/mapper/cryptroot --home

Restore stages writable snapshot copies, then deletes and replaces selected
current subvolumes. It makes no implicit backup. If desired, explicitly create a
named pre-restore checkpoint while the system is still bootable.

Restore reports the failed phase and completed components on stderr. Replacement
can fail between deleting a current subvolume and moving its staged copy; EFI
copying can stop partway through an overlay. There is no rollback or journal.

After a failed restore, remain in recovery, correct the reported problem, and retry
the same command with the same device and component selection. Each
attempt starts from the named checkpoint; missing current subvolumes and leftover
temporary copies are handled. Do not boot a partially restored system. Hardware
failures, insufficient space and damaged checkpoints still require correcting
the reported problem before retrying.

EFI files added later remain present. Firmware entries are left unchanged; the
saved firmware listing is a reference for manual repair. The implementation lives
outside `EFI/` so restoring boot files does not replace the running tool.

Reboot and verify after success. Legacy fresh-install checkpoints remain stored,
but their nested layout requires their original recorded recovery procedure;
this command lists them and refuses automatic inspection/restoration.

## Boundaries

- Creation is online-only; offline capture is deferred.
- Live capture is sequential, without application or cross-component atomicity.
- On-disk checkpoints do not protect against disk failure.
- Checkpoint deletion, scheduling and retention are manual.
- First-boot verification invokes this same capture command after its health checks.

## Verification status

Parser, help, human reporting, authorization and dry-run boundaries have
isolated tests with mocked filesystem tools. No live mount, snapshot, cache
cleanup or restore is part of those checks. Disposable-storage end-to-end restore,
real rescue media with an alternate POSIX shell, and installed-system verification
remain required before relying on this revision for recovery.
