# On-demand checkpoints and recovery

As root on the booted target:

    agentoo-checkpoint create terminal-env
    agentoo-checkpoint list
    agentoo-checkpoint inspect <exact-checkpoint-name>

Keep package/configuration tools and other writers idle during capture. Labels
receive a UTC timestamp and process ID; existing checkpoints are never overwritten.
Create and restore print a compact plan and require confirmation.

| Default | Create | Restore |
|---|---|---|
| System | Capture | Replace current system |
| Home | Capture | Preserve current home |
| EFI | Capture boot files | Overlay saved boot files |
| Distfiles | Clean with system capture | Not applicable |

- Positive flags select exactly the specified components: `--system`, `--home`, `--efi`.
- Negative-only flags subtract from defaults: `--no-system`, `--no-home`, `--no-efi`.
- Home-only capture: `agentoo-checkpoint create personal-work --home`.
- `--[no-]clean-distfiles` applies only to create. Explicit cleaning requires system capture.
- Conflicting flags and empty selections are rejected.

The supported layout is `@` for root and `@home` for home on one Btrfs filesystem,
with ordinary directories inside them. Nested subvolumes are refused because a
root snapshot does not include their contents. Agentoo's documented systemd
directory policy prevents the optional storage services from introducing these.

Snapshots live at Btrfs top level `gentoo-checkpoints/<name>`. EFI archives live
at `/boot/checkpoints/<name>`. Completion markers, filesystem identities,
snapshot identities and EFI archive checksums are verified before restoration.

## Recovery without the installed root

The implementation lives at `/boot/agentoo/checkpoint.sh` on the EFI partition.
The installed command is a launcher. Recovery media can run the implementation
directly without mounting or executing anything from the installed root.

Use a normal recovery environment with:

- POSIX sh and GNU core utilities
- Btrfs tools
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

After a failed restore, remain in recovery and retry the same command. Each
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
