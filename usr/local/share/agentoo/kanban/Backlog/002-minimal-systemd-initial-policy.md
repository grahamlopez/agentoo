# Establish minimal systemd policy during installation

Created: 2026-10-10
Status: Backlog

## Intent and historical context

While planning Btrfs snapshots for the freshly installed QEMU target, we found
three unexpected nested subvolumes. The user values conceptual simplicity and
wants unused systemd features disabled from the initial installation/configuration,
rather than applying an after-the-fact cleanup to every install. They explicitly
deferred these configuration and installer changes. No implementation is
authorized by this card alone.

The original snapshot plan covered `@` (root), `@home`, EFI files, and QEMU
firmware variables. Discovery of nested subvolumes complicated that plan because
root snapshots do not recursively include their contents. The proposed simpler
system layout keeps root and home as the system subvolumes, with ordinary
directories for the unused feature locations. A separately managed download
cache remains an independent, undecided snapshot concern.

## Confirmed findings from read-only inspection

Target image: `/home/graham/VMs/agentic-gentoo/target.qcow2`, virtual size 32 GiB.
It was attached through `/dev/nbd0`, unlocked as
`/dev/mapper/gentoo-qemu-checkpoint`, and inspected with temporary read-only
mounts using `ro,rescue=nologreplay,subvolid=5`. These are historical attachment
details, not authority to operate on those names without verifying live identity.

The installer explicitly creates only root and home subvolumes. The target also
contained the following empty nested subvolumes and matching vendor tmpfiles rules:

| Subvolume | Target rule file under `/usr/lib/tmpfiles.d` | Rule |
|---|---|---|
| `@/srv` | `home.conf` | `q /srv 0755 - - -` |
| `@/var/lib/machines` | `systemd-nspawn.conf` | `Q /var/lib/machines 0700 - - -` |
| `@/var/lib/portables` | `portables.conf` | `Q /var/lib/portables 0700` |

The rules identify systemd-tmpfiles as their creation mechanism, but the exact
invocation was not traced. Their presence does not establish that associated
services are enabled or running; service state was not audited.

- `/srv` holds locally served data. It has no dedicated service to disable.
- `/var/lib/machines` stores systemd-managed container/machine images.
- `/var/lib/portables` stores systemd portable-service images.
- `q` and `Q` request subvolumes when supported; ordinary directory creation is
  the proposed local policy instead.

## Recommended implementation approach

1. Inspect the installed systemd version, unit files, D-Bus/socket activation,
   dependencies, and Gentoo packaging before selecting exact units. Consider
   `systemd-machined.service`, `systemd-portabled.service`, and image-import
   support where applicable, but do not treat this list as a verified mask set.
   Machine management may integrate with other virtualization tools; assess that
   before disabling it universally.
2. Store the policy in agentoo, using native common/host fragments and
   overrides consistent with `etc/agentoo/README.md`. Decide explicitly
   whether all target hosts should share it.
3. Use masks where the intent is to prevent activation. Merely disabling a unit
   does not prevent on-demand activation. Retain packaged software initially;
   changing systemd build features is outside the proposed first implementation.
4. Override vendor tmpfiles behavior under `/etc/tmpfiles.d` to create ordinary
   directories with the original permissions. Preserve unrelated rules,
   especially `/home` handling in `home.conf`. Do not edit package-owned files
   under `/usr/lib` or disable systemd-tmpfiles globally.
5. Trace installation timing: stage3 extraction and package post-install hooks
   may create directories/subvolumes before first-boot configuration. Inspect
   whether the stage3 already contains these paths/subvolumes and install policy
   early enough to prevent their creation during package operations. Applying
   rules only in first-boot-foundation may be too late. Account for the configs
   checkout currently occurring in portage-foundation.
6. For existing installs, devise a guarded one-time conversion of these empty
   subvolumes into ordinary directories. Refuse destructive conversion when
   contents are present; preserve ownership, permissions, and relevant attributes.
   An existing snapshot would still retain its historical layout.

## Trade-offs and intended scope

The goal is simpler configuration and rollback reasoning. Empty subvolumes use
negligible space, and inactive optional services offer little performance benefit
when disabled. Local overrides introduce maintenance responsibility as vendor
rules evolve. Ordinary directories will roll back with root and cannot be
snapshotted independently. Optional image-management features must be re-enabled
if needed later. Normal Portage-installed services and basic boot functionality
should remain unaffected.

## Completion criteria

- A fresh production-path QEMU install has the intended directory layout before
  first boot, and retains it after boot, reboot, and an appropriate package-update
  check.
- Selected unused services cannot activate; boot, networking, time sync, journal,
  Btrfs scrub, and package management still work.
- Existing-install conversion is guarded and verified separately if requested.
- Root/home checkpoint and restore handling reflects the simpler layout.
- Record exact policy files, unit choices, placement in installer phases,
  validation, and reversibility instructions on this card.

## References

- Current installer: `/home/graham/Projects/gentoo-notes/installer/gentoo-install.sh`.
- [systemd tmpfiles configuration](https://www.freedesktop.org/software/systemd/man/latest/tmpfiles.d.html)
- [Btrfs subvolumes and snapshot boundaries](https://btrfs.readthedocs.io/en/latest/Subvolumes.html)
- [Systemd image classes and storage directories](https://github.com/systemd/systemd/blob/main/man/importctl.xml)

Related: `001-consolidate-installer.md`. Update these historical source pointers
when migration occurs; the two changes can be planned independently.
