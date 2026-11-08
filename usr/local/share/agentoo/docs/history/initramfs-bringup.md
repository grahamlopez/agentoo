# Initramfs bring-up investigations

These records describe the original BusyBox 1.36.1 initramfs investigation,
including the 2026-10-27 boot failure. Commands, recovery instructions and pending
acceptance statements below belong to that investigation; they are not current
setup instructions or a statement of present host acceptance. See the
[current initramfs guide](../initramfs.md) for packaging, development and testing.

## Initial investigation validation

The first archive was built successfully with BusyBox 1.36.1 and cryptsetup
2.8.8. Staged cryptsetup ran in a user-namespace chroot with bundled libraries;
staged shell syntax, arithmetic and wait primitives passed. The binary keymap
structure and Caps Lock -> Control entry were verified. Archive size is about
13 MiB uncompressed. The user subsequently ran the full disposable storage smoke test successfully
on the host: LUKS2 unlock without udev, mapping-node creation, discards and
read-only Btrfs `@` mounting passed. Boot acceptance remains pending.

## Direct mapper fstab experiment (unsuccessful)

Changing the source of both Btrfs fstab entries from the filesystem UUID to
`/dev/mapper/root` did not fix the handoff. The subsequent boot timed out waiting
for `/dev/mapper/root`, confirming that changing the path alone does not satisfy
systemd device readiness. Configuration generation had passed, but boot
acceptance failed. The runtime udev handoff rule below addresses that readiness
problem directly.

Restore the saved UUID-based fstab before testing the udev handoff approach.
The live fstab is installer-generated and is not tracked in this repository, so
switching branches or deploying Git changes does not restore it automatically.
No installer defaults or historical kernel configurations were changed.

## First boot investigation (2026-10-27)

The first boot unlocked and mounted root and started real-root systemd.
Its persistent journal (boot `03b3874a3b4e4736ab1cb9b8ff8d23df`) records a
successful root remount, then a timeout for the Btrfs UUID needed by `/home`.
The installed `10-dm.rules` rejects coldplug `add` events for mappings without a
prior activation property; the original daemon-free initramfs provided none.
The runtime handoff rule addresses this exact transition. A namespace-isolated
regression test reproduces rejection and checks acceptance plus mapping scoping;
filesystem probe properties are supplied by a test fixture because the sandbox
cannot open block devices. The extended host smoke test uses real probing on the
disposable mapping. Acceptance of that extended test and a corrected boot remain
pending.
