# Agentoo initramfs

`sys-kernel/agentoo-initramfs` packages Agentoo's early-boot implementation and
archive generator. It builds a private static BusyBox and installs it with the
generator, `/init` source, udev-handoff helper and storage smoke test under
`/usr/libexec/agentoo-initramfs`. Portage owns these installed files; the
implementation sources live in the overlay's
`sys-kernel/agentoo-initramfs/files/` directory.

The package supports built-in boot drivers, one LUKS2 partition, Btrfs
subvolume `@` and `/sbin/init` on the real root. Internal and kernel-supported
USB keyboards/receivers work through a compiled console keymap. Bluetooth,
initramfs udev/firmware loading, early module loading, resume, token unlock and boot animations
are not implemented. Kernel module support is allowed when the required boot
drivers remain built in; NVIDIA can load after the real-root handoff.

## Package and boot-image lifecycle

Install the custom-kernel prerequisites:

```sh
sudo emerge --ask @kernel-dev
```

The set includes `sys-kernel/agentoo-initramfs`; the package can also be emerged
individually. Portage fetches/verifies BusyBox sources and compiles the private
binary using its selected compiler and flags. The build requires static glibc
libraries. It does not install the normal `sys-apps/busybox` package or put
BusyBox applet links into the running system.

The installed generator assembles a host-specific archive from that BusyBox,
installed cryptsetup and its linked libraries, boot scripts and explicit storage
and keymap inputs. Assembly needs no compiler, source archive, network or root
privileges. Emerging the package does not generate an archive, rebuild a kernel,
write the ESP or change firmware entries.

For an existing configured kernel workspace:

```sh
agentoo kernel build --label LABEL
agentoo kernel install --label LABEL
```

See [kernel configuration and installation](kernel.md) to prepare a new workspace
and review installation behavior. Kernel build preflights the generator, creates
a fresh archive and embeds it before its single kernel make pass. Reuse the
workspace for incremental builds. Even an initramfs-only change needs a kernel
build/install for boot testing because the archive is embedded; unchanged kernel
objects can be reused.

## Host inputs

The selected native Agentoo Portage profile supplies the default host for
`agentoo kernel config`. That command records the host Kconfig policy and
storage identity discovered from the mounted root. Its `--target-host` override
selects kernel policy for that operation; it does not change Portage's profile
or compilation settings. See [host selection](../../../../../etc/agentoo/README.md#host-selection).

Kernel build passes the recorded PARTUUID, mapper and keymap to the generator.
Generation does not query the selected profile or detect the host again. Both
standalone and integrated generation use the same implementation. No package
USE flag selects a host, and tracked package sources contain no host disk UUIDs.

## Standalone generation

Run as an ordinary user, using the destination root partition's GPT PARTUUID
and its installed mapping name:

```sh
/usr/libexec/agentoo-initramfs/build \
  --work /dev/shm/agentoo-initramfs \
  --partuuid ENCRYPTED_PARTITION_UUID --mapper cryptroot
```

`--partuuid` is required. `--mapper` defaults to `root`; the installer normally
uses `cryptroot`. `--keymap` defaults to
`/usr/share/keymaps/i386/qwerty/us-caps.map.gz`. `--busybox FILE` selects a compiled
static binary instead of the package's adjacent `busybox` executable, primarily
for development. It does not accept a source tree.

The work directory must not exist. The generator writes `root/` and
`initramfs.cpio` beneath it. Choose a fresh disposable directory for each run.
Pass `--check` with the same arguments to validate the binary, required applets,
keymap, required tools and cryptsetup's linked libraries without creating the
workspace. Preflight does not establish boot acceptance.

The package declares runtime dependencies for Python, cpio, loadkeys, strip,
cryptsetup and ldd. The shared US/Caps-to-Control keymap is supplied by Agentoo's
configuration repository. The archive contains stripped copies of installed
cryptsetup libraries; rebuild the archive and embedded kernel after relevant
cryptsetup/library security updates. Updating installed libraries alone does not
update existing archives.

## Development and testing

Edit the sources under
`usr/local/share/agentoo/portage/sys-kernel/agentoo-initramfs/files/` in the
checkout. BusyBox configuration has one definition, `busybox.config`. The ebuild
pins its upstream source version and compiles it. Script edits need no BusyBox
recompilation.

To stage the package without merging it, run from the repository root on a
Gentoo development host:

```sh
initramfs_ebuild="$PWD/usr/local/share/agentoo/portage/sys-kernel/agentoo-initramfs/agentoo-initramfs-1.ebuild"
initramfs_dev=/var/tmp/agentoo-initramfs-dev
sudo install -d -m 0755 "$initramfs_dev"
sudo env PORTAGE_TMPDIR="$initramfs_dev" \
  ebuild "$initramfs_ebuild" clean unpack configure compile install
initramfs_image="$initramfs_dev/portage/sys-kernel/agentoo-initramfs-1/image/usr/libexec/agentoo-initramfs"
```

Use a dedicated temporary build location: `clean` removes this package's previous
Portage build tree there. Use the current ebuild filename and package version
when those change. The staging phases compile and install into Portage's image
directory; they do not merge files into the running system.

Run the checkout generator against the staged binary:

```sh
initramfs_sources="$PWD/usr/local/share/agentoo/portage/sys-kernel/agentoo-initramfs/files"
python3 "$initramfs_sources/build" \
  --busybox "$initramfs_image/busybox" \
  --work /dev/shm/agentoo-initramfs-dev \
  --partuuid ENCRYPTED_PARTITION_UUID --mapper cryptroot
cpio -it < /dev/shm/agentoo-initramfs-dev/initramfs.cpio
```

Repeat with a fresh output directory after editing scripts. The checkout
`init` and `udev-handoff` are copied by the checkout generator, so script edits
are exercised directly. Rebuild the staged package when BusyBox configuration
or its source version changes.

Run repository regression checks from the checkout:

```sh
python3 usr/local/share/agentoo/tests/run_tests.py
```

Then run the disposable storage test described below. It checks the generated
archive independently of a kernel build. To embed that exact archive for a boot
test, use the kernel build's `--initramfs /absolute/path/initramfs.cpio` option,
then install through the normal kernel workflow.

Before validating the packaged default path, reinstall the package from source
so changed local files are used even if a binary package is available:

```sh
sudo emerge --ask --oneshot --usepkg=n sys-kernel/agentoo-initramfs
agentoo kernel build --label LABEL
agentoo kernel install --label LABEL
```

Increment the ebuild revision when shipped scripts or BusyBox configuration
change, so normal Portage updates select the new implementation. Update the
Manifest when changing the BusyBox source archive. Keep installed files under
Portage ownership; edit package sources rather than installed copies.

## Disposable storage smoke test

Run on the host before building a boot candidate:

```sh
sudo /usr/libexec/agentoo-initramfs/smoke /dev/shm/agentoo-initramfs
```

For a checkout-generated archive, use the checkout's test implementation:

```sh
sudo bash "$initramfs_sources/smoke" /dev/shm/agentoo-initramfs-dev
```

This requires root, mount namespaces, loop devices, device-mapper, Btrfs kernel
support, btrfs-progs, host cryptsetup, udevadm and blkid. These additional test
requirements are not needed for normal archive generation. It uses a disposable
512 MiB sparse file and random test key; Argon2id requests 1 GiB RAM.

The test runs archived cryptsetup with private `/dev` and `/run`, unlocks LUKS2
without udev, checks mapping-node creation, creates Btrfs `@` and mounts it
read-only with archived BusyBox. It also evaluates real-root udev rules with
real filesystem probing, checking UUID-link requests and systemd readiness after
the archived handoff helper. `udevadm test` does not emit events, execute RUN
commands or start services. Cleanup removes test mounts, mapping and loop
attachment. The test does not open or modify the real encrypted partition.

Full PID 1 handoff, physical keyboard behavior and graphics require boot testing.
Retain a working EFI image. Check internal/USB keyboards, incorrect then correct
passphrase, Btrfs `@`, active discards, normal systemd startup and firmware.
On Thinktop, inspect MICMUTE behavior before retiring its real-root workaround.
Record boot results against the tested host and image; packaging success and
storage smoke tests alone do not establish boot acceptance.

## Early-boot behavior

The archive includes a root-owned `/dev/console` character device (5:1, mode
0600), generated without root so the kernel can attach initial standard I/O.
`/init` mounts devtmpfs, proc, sysfs and tmpfs, loads the keymap and waits roughly
ten seconds for the recorded partition. It disables device-mapper udev handling
for cryptsetup, enables discards and permits three passphrase attempts. It
mounts Btrfs `@` read-only, prepares the real-root udev handoff, moves API mounts
and executes BusyBox `switch_root`. Failures before handoff enter a rescue shell.
The real root must contain `/dev`, `/proc`, `/sys` and `/run` directories.

The handoff writes `/run/udev/rules.d/09-agentoo-initramfs-root.rules`, scoped to
the active mapping's exact device and LUKS mapping UUID and non-suspended state.
This lets real-root udev coldplug recognize a mapping created without an
initramfs udev database. The rule disappears at reboot and adds no initramfs
daemon or hardware database.

See [the original bring-up investigations](history/initramfs-bringup.md) for
dated validation and the root-device handoff failure that motivated this rule.
