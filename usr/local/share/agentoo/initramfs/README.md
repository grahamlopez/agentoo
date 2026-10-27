# Minimal machine-specific initramfs

This initial implementation targets thinktop: built-in kernel drivers, one
LUKS2 partition, Btrfs subvolume `@`, and `/sbin/init` on the real root.
It supports the internal keyboard and kernel-supported USB keyboards/receivers.
The build compiles the installed US/Caps-to-Control console map to BusyBox format.
Bluetooth, udev, firmware, modules, resume and token integrations are omitted.

The default `agentoo kernel build` runs this builder automatically in
`<kernel-workspace>/initramfs/<release>/`. `--genkernel` selects the previous
generator; `--initramfs FILE` bypasses generation and embeds that file.

To build separately as your ordinary user:

```sh
usr/local/share/agentoo/initramfs/build \
  --work /dev/shm/agentoo-initramfs
```

The work directory must not exist. By default, the builder extracts
`/var/cache/distfiles/busybox-1.36.1.tar.bz2` inside the workspace. No download
is performed. `--busybox-source DIR` uses an already extracted source tree. The default PARTUUID and keymap are specific
to thinktop; `--partuuid` and `--keymap` override them. Build requires a C compiler,
static libc development files, make, Python 3, cpio, loadkeys, strip and installed
cryptsetup with its shared libraries. No packages or boot files are installed.
The archive contains stripped copies of installed libraries; rebuild after
cryptsetup/library security updates. BusyBox is statically linked.

The archive includes a root-owned `/dev/console` character device (5:1, mode
0600), so the kernel can attach initial standard input/output before `/init`
mounts devtmpfs. Its archive entry is generated without requiring root.

The init script explicitly disables device-mapper udev handling for cryptsetup
only. It enables discards, tries the passphrase three times, mounts `@` read-only,
writes a runtime udev rule for the active mapping, moves the API mounts and
executes BusyBox switch_root. The rule lives in `/run/udev/rules.d/` and matches
the exact kernel device and LUKS mapping UUID, with a non-suspended table. It
lets real-root udev process the initial coldplug event without an initramfs
udev database. It disappears at reboot and adds no daemon or hardware database. It waits up to roughly
ten seconds for the partition. Failures before handoff enter a rescue shell.
The real root must already contain /dev, /proc, /sys and /run directories.

## Disposable storage smoke test

Run on the host, before building a boot candidate:

```sh
sudo usr/local/share/agentoo/initramfs/smoke /dev/shm/agentoo-initramfs
```

Requires root, mount namespaces, loop devices, device-mapper, Btrfs kernel
support, btrfs-progs and host cryptsetup. Uses a temporary 512 MiB sparse file
and a random test key; Argon2id requests 1 GiB RAM, matching the real root.
It extracts the archive and runs its cryptsetup with private /dev and /run,
without a udev daemon. It verifies mapping-node creation, formats the disposable
mapping, creates `@`, and mounts that subvolume read-only using staged BusyBox.
The trap removes test mounts, mapping, loop attachment and temporary files.
It never opens or modifies the real encrypted partition. After storage tests,
it evaluates the installed real-root udev rules with private `/dev` and `/run`.
It first reproduces the rejected coldplug (`SYSTEMD_READY=0`), then invokes the
archived handoff helper and checks actual Btrfs probing, the requested UUID
symlink, and systemd readiness properties. This uses `udevadm test`: it does not
emit kernel events, run a daemon, create the requested symlinks, or start
systemd units. Full PID 1 handoff and physical keyboard acceptance still require
boot testing. The host test also requires `udevadm` and `blkid`.

## Boot candidate

After the smoke test passes, prepare a new kernel workspace using the existing
kernel workflow, then:

```sh
agentoo kernel build --label agentoo-v0.5 \
  --initramfs /dev/shm/agentoo-initramfs/initramfs.cpio
```

Install separately using the existing workflow, retaining a working EFI image.
Cold-boot checks: internal keyboard, USB cable/paired receiver, incorrect then
correct passphrase, root `@`, active discard flag, systemd startup, and firmware
behavior. Compare microcode against the observed baseline `0x122`. Inspect the
microphone-mute key before retiring the existing real-root workaround.

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
