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

The init script explicitly disables device-mapper udev handling for cryptsetup
only. It enables discards, tries the passphrase three times, mounts `@` read-only,
moves the API mounts and executes BusyBox switch_root. It waits up to roughly
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
It never opens or modifies the real encrypted partition. This test exercises
storage activation and mounting, not the PID 1 handoff or physical keyboard.

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
