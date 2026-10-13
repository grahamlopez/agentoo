# Investigate automatic distribution kernel EFI registration

Created: 2026-10-12
Status: Backlog

## Decision and scope

Physical firmware registration remains manual. The installer retains automatic
offline registration in an explicitly selected QEMU variable store, to keep
development guest creation convenient. This investigation concerns broader native
registration during distribution-kernel updates; it does not remove the existing
QEMU installer convenience or implement a custom-kernel path.

- Compare Gentoo's packaged registration tools with the documented manual path.
- Identify the firmware entries, BootOrder, and BootNext values they change.
- Verify offline installation cannot write the installation host's firmware.
- Cover Startop's full-device-path requirement and any proposed guest-update path.
- Test installation, updates, reboot, failure, and removal while preserving a
  known-working distribution fallback and independent custom-image artifacts.
- Recommend whether automation is worthwhile and how users explicitly enable it.

## Completion criteria

Record the options, sources, update/failure behavior, and proposed enablement.
Validate on disposable physical/VM targets as appropriate before enabling it.
Creating this card does not authorize automatic physical firmware modifications.

Related: [007 installer and post-boot simplification](../Completed/007-installer-postboot-simplification.md).
