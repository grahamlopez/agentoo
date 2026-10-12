# Establish minimal systemd policy during installation

Created: 2026-10-10
Status: Completed (policy implementation)

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

## Reopened for checkpoint simplification (2026-10-11)

The user now authorizes documented ordinary-directory overrides and optional-feature
masks. The checkpoint design assumes only top-level root/home boundaries. Existing
At policy review, the VM subvolumes were empty and had not been removed. Preserve the named baseline.

Systemd 261.2 inspection confirms the three vendor tmpfiles rules. Machined and
portabled are inactive/static; machined also has a socket and both have D-Bus aliases.
Importd is absent. Masks cover future importd/nspawn activation, preserving shared
machine.slice/machines.target infrastructure.

Same-named tmpfiles overrides retain unrelated vendor rules and replace only the
three target entries with d. Importd defaults suppress imported Btrfs subvolumes
and quotas. These do not prohibit manual Btrfs commands, explicit image clones,
or ephemeral-container snapshots; enabling those needs a checkpoint-layout review.

Installer masks are applied just after checkout in portage-foundation, before
target package operations. Stage3 extraction cannot recreate subvolume objects.
A fresh install/reboot test is still required before closing this card. Current-VM
conversion was scheduled separately; rollout results are recorded below.

Current installer: /usr/local/share/agentoo/installer/gentoo-install.sh.

Validation: on a disposable Btrfs root in the VM, the actual installer function
created every requested mask. Native systemd-tmpfiles with the local overrides
created ordinary /srv (0755), /var/lib/machines (0700), and /var/lib/portables (0700).
After removing all test masks and those directories, rerunning tmpfiles recreated
ordinary directories again. That fixture test did not change the installed guest.
Its existing directories were root-owned, empty, and matched those modes.

Reviewed conversion plan: apply the policy/masks on the VM, verify emptiness again,
delete only those three current subvolumes, recreate ordinary directories through
tmpfiles, and verify directory types, health, and later reboot. Do not touch the
historical baseline snapshots. Full fresh-install validation is still outstanding.

## Implementation completion

The reviewed policy implementation is complete and was validated on disposable
Btrfs fixtures using the actual installer mask function and native systemd-tmpfiles.
Full fresh-install validation remains outstanding. The installed-VM rollout below
validates conversion and reboot/restore behavior, without claiming a fresh install.
The older named checkpoint retains its historical nested-subvolume layout.

## Installed-VM rollout and checkpoint validation — 2026-10-11

- Updated the guest to the committed systemd policy through a local Git bundle;
  no authenticated remote operation was performed.
- Rechecked that all three subvolumes were empty and root-owned. Applied masks,
  stopped the optional storage managers, deleted only those current subvolumes,
  and recreated ordinary directories using the native tmpfiles overrides.
- Verified /srv remains 0755 and machines/portables remain 0700, all root-owned.
  No nested subvolumes remained below root or home. Normal reboot retained this.
- Created the complete system/home/EFI checkpoint
  `vm-restore-test-20261012T002851Z-13713` with the new EFI-hosted shell command.
  Distfiles cleanup used the default policy. The historical fresh-install and
  development home-only checkpoints were retained.
- Changed system, home and EFI canaries, added a system file and a later EFI file,
  then booted a temporary recovery initramfs with target root/home unmounted.
  Recovery SSH used the public authorization key and a host key generated in RAM;
  no installed password hashes or private host keys were included in that image.
- Default restore reverted system and saved EFI files, removed the later system
  file, preserved changed home, and preserved the later EFI file.
- Explicit system/home/EFI restore reverted home too. Repeated system/EFI restore
  succeeded. Both checkpoint snapshots remained read-only with matching UUIDs;
  archive checksums and manifests verified. No temporary restore copies remained.
- Normal boot mounted the replacement subvolumes by name. First-boot diagnostics
  reported zero failures; boot-identity preflight succeeded and its capture prompt
  was declined. Time synchronized, networking/HTTPS worked, persistent journal
  history was present, the scrub timer was active, and all 63 managed permissions
  matched. Optional storage units remained masked; no nested subvolumes returned.
- Btrfs scrub completed over 4.92 GiB with no errors; no failed services remained.
- Removed the temporary recovery firmware entry/image and live canary files.
  Normal firmware boot order was unchanged. The complete named checkpoint remains
  available for later recovery, including its saved test canaries.

## Final closeout review and failure tests — 2026-10-11

Disposable Btrfs/FAT images in the VM verified the remaining failure boundaries:

- Checksum entries must name exactly the three required files; a renamed archive
  entry was rejected even when that alternate file had a matching checksum.
- Wrong EFI UUID, read-only EFI, incomplete markers, and a mismatched completion
  marker refused restoration before changing the selected current data. Listing
  now reports a mismatched marker as incomplete.
- Real low-space conditions on Btrfs and EFI refused capture before deleting
  distfiles. Low EFI space also refused restoration before replacing subvolumes.
- An injected partial EFI copy failed after writing a broken test file. Retrying
  the same command restored saved files and preserved later EFI additions.
- The documented mount-and-run path worked with the stock implementation reached
  from the mounted EFI partition, with target root/home unmounted. No Python or
  target-root executables were needed for recovery.

The suite also rechecked component selection, conflicting options, declined plans,
archive corruption, nested/mounted target refusal, abandoned staging cleanup,
interruption after deleting current root, and repeated successful restoration.
All passed. Permission-policy coverage includes all 63 planned tracked files.
Recovery prerequisites now explicitly include procps/pgrep. The fresh-install
runbook uses the agreed 100 GiB image. A full fresh install remains the user's next
validation step; this closeout does not claim that it has run.

## Fresh-install and default-restore validation — 2026-10-11

The user completed a new installation, handoff, firstboot, and Graham's account
setup, then created `user-created-20261012T025431Z-55395` and disposable root/home
markers. The fresh target uses separate top-level `@` and `@home` subvolumes.

- The real EFI-hosted command restored system and EFI from that checkpoint while
  the selected targets were unmounted in a temporary recovery initramfs.
- The root marker disappeared; the home marker's SHA-256 stayed unchanged. EFI
  files matched the saved archive, machine identity stayed unchanged, and the
  named system/home snapshots remained read-only. No nested subvolumes appeared.
- Boot continued normally from the restored root. Firstboot diagnostics passed,
  time synchronized, previous journal history remained, and all 63 managed file
  permissions matched. Btrfs scrub completed over 4.24 GiB with no errors.
- Temporary recovery image, firmware entry, root SSH test key, temporary SSH
  enablement, and remaining live marker were removed. Normal boot order stayed
  unchanged; both complete named checkpoints remain available.
- The pending Git-identity fix wrote both values as Graham from root's private
  working directory using a disposable configuration file on the fresh guest.

Recovery preparation exposed two test-helper defects (relative sshd execution
and initramfs account initialization); both were corrected before restoration.
These helpers are not part of the shipped checkpoint utility.
