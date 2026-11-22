# Agentoo initramfs

`sys-kernel/agentoo-initramfs` (`@kernel-dev`) builds a private static BusyBox
and installs the archive generator, `/init`, udev-handoff helper, and storage
smoke test under `/usr/libexec/agentoo-initramfs` (sources in
`usr/local/share/agentoo/portage/sys-kernel/agentoo-initramfs/files/`).

**Supported scope:** Built-in boot drivers, single LUKS2 partition, Btrfs
subvolume `@`, `/sbin/init`, and internal/USB keyboards via compiled console
keymap (`us-caps.map.gz`). Bluetooth, initramfs udev/firmware loading, early
module loading, resume, token unlock, and boot animations are not implemented.

## Lifecycle

Install/update the generator *before* building the custom kernel (see
[kernel guide](kernel.md#setup-and-build)):

```sh
sudo emerge --ask --oneshot --usepkg=n sys-kernel/agentoo-initramfs
sudo emerge --ask --oneshot --usepkg=n '=sys-kernel/gentoo-kernel-VERSION'
```

During `gentoo-kernel`'s `post_src_prepare`, Portage invokes
`/usr/libexec/agentoo-initramfs/build` with `/etc/portage/env/kernel-local`
(`AGENTOO_INITRAMFS_PARTUUID`, `AGENTOO_INITRAMFS_MAPPER`,
`AGENTOO_INITRAMFS_TRANSPORT`, optional `AGENTOO_INITRAMFS_KEYMAP`), assembling
a fresh archive inside `WORKDIR` using static ELF inspection (`lddtree`,
excluding Portage preload libraries). Because the archive embeds stripped copies
of installed `cryptsetup` libraries, rebuild `gentoo-kernel` after generator or
`cryptsetup`/library updates (`emerge --config` cannot refresh embedding).

## Standalone generation

Run as an ordinary user into a fresh, non-existent `--work` directory (pass
`--check` to validate inputs without creating output):

```sh
/usr/libexec/agentoo-initramfs/build \
  --work /dev/shm/agentoo-initramfs \
  --partuuid ENCRYPTED_PARTITION_UUID --mapper cryptroot
```

Defaults: `--mapper root` (installer uses `cryptroot`),
`--keymap /usr/share/keymaps/i386/qwerty/us-caps.map.gz`, optional
`--busybox FILE` for development staging.

## Development and staging

Edit sources under
`usr/local/share/agentoo/portage/sys-kernel/agentoo-initramfs/files/` (BusyBox
config lives in `busybox.config`; script-only edits need no BusyBox rebuild).
Stage without merging to test checkout scripts against the staged BusyBox:

```sh
initramfs_ebuild="$PWD/usr/local/share/agentoo/portage/sys-kernel/agentoo-initramfs/agentoo-initramfs-1-r1.ebuild"
initramfs_dev=/var/tmp/agentoo-initramfs-dev
sudo install -d -m 0755 "$initramfs_dev"
sudo env PORTAGE_TMPDIR="$initramfs_dev" \
  ebuild "$initramfs_ebuild" clean unpack configure compile install
initramfs_image="$initramfs_dev/portage/sys-kernel/agentoo-initramfs-1/image/usr/libexec/agentoo-initramfs"

initramfs_sources="$PWD/usr/local/share/agentoo/portage/sys-kernel/agentoo-initramfs/files"
python3 "$initramfs_sources/build" \
  --busybox "$initramfs_image/busybox" \
  --work /dev/shm/agentoo-initramfs-dev \
  --partuuid ENCRYPTED_PARTITION_UUID --mapper cryptroot
cpio -it < /dev/shm/agentoo-initramfs-dev/initramfs.cpio
```

Bump the ebuild revision when shipping script or BusyBox config changes, and
reinstall with `--usepkg=n` before boot testing.

## Disposable storage smoke test

Run on a host before building a boot candidate (uses a disposable 512 MiB
sparse loop file and random test key—never touches the real encrypted disk;
requires root, loop, dm, Btrfs, `cryptsetup`, `udevadm`, `blkid`, ~1 GiB RAM
for Argon2id):

```sh
sudo /usr/libexec/agentoo-initramfs/smoke /dev/shm/agentoo-initramfs
# Or for a checkout-generated archive:
sudo bash "$initramfs_sources/smoke" /dev/shm/agentoo-initramfs-dev
```

Exercises archived `cryptsetup` (LUKS2 unlock without udev), mapping-node
creation, Btrfs `@` read-only mount via archived BusyBox, and real-root udev
coldplug rules via `udevadm test` after the handoff helper.

## Early-boot handoff

The archive embeds root-owned `/dev/console` (5:1, mode `0600`) without root
build privileges. `/init` mounts API filesystems, loads the keymap, waits ~10 s
for the recorded `PARTUUID`, unlocks LUKS2 with discards (3 attempts, udev
disabled), mounts Btrfs `@` read-only, writes a temporary
`/run/udev/rules.d/09-agentoo-initramfs-root.rules` scoped to the active
mapping's device and LUKS UUID so real-root udev coldplug recognizes the
daemon-free mapping (disappears at reboot), moves mounts, and `switch_root`s
into `/sbin/init`. Pre-handoff failures drop to a rescue shell.
