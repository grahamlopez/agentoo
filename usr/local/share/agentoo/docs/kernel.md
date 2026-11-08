# Rebuilding a custom kernel

`agentoo kernel` carries an existing complete config to new Gentoo sources,
builds a local x86_64 EFI kernel with an embedded initramfs, and installs it under
a versioned filename. Each subcommand also works through `agentoo-kernel`.
Run as your normal user; the command uses sudo for system module installation,
ESP writes and firmware registration. Initramfs builders run as the build user
and create user-owned workspace files.

```sh
agentoo kernel config --label agentoo-v0.4 \
  --config /usr/local/share/agentoo/docs/kernel-shared-v04-config
agentoo kernel build --label agentoo-v0.4 -j16
agentoo kernel install --label agentoo-v0.4
```

## Host specialization

Configure on the destination host. The default target comes from the selected
Agentoo Portage profile and chooses the tracked native Kconfig fragment
`/etc/agentoo/kernel/hosts/<name>.config`. `--target-host NAME` overrides the
selection, not the destination hardware or storage. Missing or malformed profiles
fail before workspace/source changes. Thinktop, flattop and startop profiles are
supplied; Startop has build/boot and peripheral acceptance. Other hosts
need reviewed profiles first.

The starting config supplies the shared driver/capability union. Host fragments
set explicit embedded firmware names, their absolute directory, CPU microcode
support and any justified Kconfig exceptions. They do not contain command lines,
initramfs paths or release labels. Complete saved configs remain useful baseline
snapshots, but their command line and embedded firmware are replaced.
The shared snapshot was checked against the running minimal-initramfs v0.4
config and resolved with native Kconfig. Its archive path and firmware list are
empty; the workspace and selected host fragment provide those inputs.
Adding a host must not prune the shared driver union. A future bequiet profile
can enable modules for NVIDIA; external-module building is still separate work.

Config inspects the mounted root through findmnt, lsblk and sysfs. The supported
layout is Btrfs subvolume `@`, directly on one LUKS2 mapping backed by a GPT
partition. Filesystem/LUKS/partition UUIDs and the actual mapping name are recorded
together. These checks target the installed root directly; the distribution
kernel's local `/etc/kernel/cmdline` is independent and is neither read nor changed.
Block-device and dm sysfs access are required.

The embedded command line defaults to `ro console=tty0 loglevel=5`. Config does
not import command-line arguments from the starting config. Use `config --cmdline TEXT`
to select console/logging policy, or supply the storage arguments required by an
explicit custom archive. Custom archives and their command lines are operator
inputs; their internal storage policy is not inspected or rewritten.

Config enables the built-in command line and disables `CONFIG_CMDLINE_OVERRIDE`.
On x86, firmware/bootloader arguments follow the built-in defaults; precedence
for repeated arguments depends on the parameter.

The minimal initramfs uses the recorded PARTUUID and mapping name,
US/Caps-to-Control keymap, passphrase unlock, Btrfs `@` and `/sbin/init`.
It opens the encrypted mapping with `cryptsetup --allow-discards`; this policy
lives in the initramfs, without a kernel command-line switch. Periodic TRIM is
separate host configuration (`fstrim.timer`); this command does not enable it.
Alternative roots/layouts, token/key-file unlock and hibernation require a
separately supplied initramfs.

Config saves the original baseline, host fragment snapshot and provenance hashes,
resolved boot/storage identity and required host settings in the workspace.
Build uses this recorded policy even if the selected profile later changes.
It checks host settings after each Kconfig resolution and refuses silent changes. To adopt new host policy or boot identity, configure a fresh
workspace.

Installed firmware remains independent: follow the native savedconfig procedure
in [firmware maintenance](firmware.md). Thinktop, Flattop and Startop have reviewed native
savedconfig lists; applying or revising them and rebuilding linux-firmware are
separate from kernel configuration. The Thinktop list also includes the recorded
RTL8156 dock Ethernet correction, which needs application on that host.
Use `agentoo kernel firmware` for read-only status, including savedconfig precedence,
installed selection and the running embedded names. After deploying a reviewed
host list and its Portage USE policy, `agentoo kernel firmware apply` backs up
overriding inputs, installs the native list and rebuilds the installed package
version from source. `apply --dry-run` displays the plan without sudo or changes.
Do not use the embedded list as the installed list: recovery kernels and
peripherals may need more files. CPU microcode, SOF and regulatory data also have
separate package ownership. Updating embedded payloads requires rebuilding the
kernel. Verify early microcode revision and actual hardware behavior after boot.

## Configure

The default starting config is `/proc/config.gz`; use `--config FILE` for a
plain or gzipped config. Sources default to `/usr/src/linux`; `--sources DIR`
selects another tree. The command resolves the source symlink once and records
its concrete path for subsequent steps.

The default workspace is `/dev/shm/<version>-<label>`. It must be absent or
empty. `--build-dir DIR` chooses another location. Build storage must permit
execution and writes; a read-only or `noexec` `/dev/shm` requires another location.
Kernel outputs and initramfs working directories live beneath that workspace.
The workspace normally disappears at reboot; no persistent build archive or
last-workspace pointer is created.

After showing the plan and confirming, config:

1. Saves the starting config inside the workspace.
2. Records the upstream EXTRAVERSION without Gentoo's suffix and passes it to
   every kernel make invocation. The source Makefile remains untouched.
3. Sets `CONFIG_LOCALVERSION="-<label>"`, disables automatic SCM release suffixes,
   and enables EFI-stub, initramfs and `/proc/config.gz` support. It replaces
   embedded firmware and command-line settings with the selected host inputs,
   replaces the old initramfs path with a workspace-owned empty directory and otherwise preserves existing module choices
   unless the host fragment explicitly overrides them.
4. Lists new Kconfig options and runs interactive `oldconfig`.
   `--accept-defaults` chooses `olddefconfig` instead.
5. Checks the resulting release, required host settings and firmware-file presence,
   then prints configuration differences, including removed symbols and changes
   from dependency resolution.
6. Offers an optional config export, then prints the workspace path on stdout.

Only the starting config is imported from an older build. Old initramfs images,
firmware staging and caches are not copied. Missing selected firmware fails
configuration; review the host fragment and installed packages before retrying.

### Command-line merge boot experiment

Use a separate label so the working EFI image remains available:

```sh
agentoo kernel config --label cmdline-test
agentoo kernel build --label cmdline-test
agentoo kernel install --label cmdline-test
```

The default baseline is the running kernel config. Before building, check the
workspace's `kernel/<release>/.config` for `CONFIG_CMDLINE_BOOL=y`, the intended
`CONFIG_CMDLINE`, and disabled `CONFIG_CMDLINE_OVERRIDE`. Install prints the
firmware registration command. In that command, replace `--create` with
`--create-only` to preserve the normal BootOrder, and append:

```sh
--unicode 'agentoo.cmdline_test=external loglevel=4'
```

Run that complete command to create the test entry with its arguments. Identify
its Boot number with `sudo efibootmgr -v -u`, then select it for one boot
(replace `XXXX` with its four-digit hexadecimal Boot number):

```sh
sudo efibootmgr --bootnext XXXX
```

The marker is supplied only through firmware, not added to `/etc/kernel/cmdline`
or the built-in string. After booting, check:

```sh
uname -r
cat /proc/cmdline
cat /proc/sys/kernel/printk
```

Expect the test label in the release and the built-in arguments followed by
`agentoo.cmdline_test=external loglevel=4`. The first printk value should be `4`
unless userspace has subsequently changed it. This tests delivery and a kernel
parameter; the minimal initramfs uses embedded storage settings and does not
parse command-line root/unlock/mount overrides. Reboot into the working image
if the candidate fails.

## Build

Build and install require `--label`. By default they search `/dev/shm` for a
workspace ending in that exact label, validate its metadata and show the selected
directory for confirmation. Missing or ambiguous viable matches fail with an
explanation. `--build-dir DIR` selects a specific workspace and still requires a
matching label. Build requires the source Makefile to match the one recorded by config; this
check does not fingerprint every source file or patch. Install validates the
completed artifacts and does not require the source tree.

```sh
agentoo kernel build --label agentoo-v0.4 --build-dir /path/to/workspace
```

The default compiler flags are `KCFLAGS="-march=native -O2 -pipe"`. Set `KCFLAGS`
in the environment to override them at config or build time. Builds target the
machine running the command; a shared driver config does not make these binaries
portable to other CPUs. Jobs default to the CPUs available to the process.

Build creates or copies the archive first, sets `CONFIG_INITRAMFS_SOURCE`,
resolves the config and compiles the kernel and selected in-tree modules once.
It then runs `modules_install INSTALL_MOD_STRIP=1` only into the workspace,
under `modules/<release>/lib/modules/<release>/`. Old staged modules are removed
on rebuild so disabled drivers do not linger. This stage runs even with
`CONFIG_MODULES=n`, which stages built-in-module metadata. **Build does not write
to the system's `/lib/modules` or request sudo.**

Only config uses an empty directory as its temporary `INITRAMFS_SOURCE`, keeping
Kconfig's dependent owner IDs, compression and built-in ACPI override settings
available before an archive exists. Build replaces it with the archive before
its single configuration resolution and compile.

Install `@kernel-dev` before building; it includes `sys-kernel/agentoo-initramfs`.
By default, build invokes `/usr/libexec/agentoo-initramfs/build` to assemble
`<workspace>/initramfs/<release>/initramfs.cpio` from the package's private static
BusyBox and installed cryptsetup/libraries. It regenerates this disposable
subtree on each build/retry. Generation does not compile BusyBox or download
sources.

Before changing build metadata or compiling, build invokes the generator's
`--check` mode to validate its binary, required applets, keymap, required tools
and cryptsetup's linked libraries. This checks inputs, not boot acceptance.
After fixing a missing prerequisite, retry build in the same workspace; there
is no need to rerun config or discard existing kernel objects.

The generator receives explicit `--partuuid`, `--mapper` and `--keymap` arguments
from the identity recorded by config. It does not query the current Portage
profile or rediscover storage. The default requires `CONFIG_MODULES=n` and
built-in boot drivers. See the [initramfs guide](initramfs.md) for the package
boundary, standalone development and smoke testing.

Initramfs-only changes still require kernel build/install because the archive is
embedded. Reuse the configured workspace for incremental make; unchanged kernel
objects can be reused, while the archive and affected kernel image are rebuilt.
Emerging the package alone does not update an existing boot image.

Module-enabled configs require an explicitly supplied archive. External NVIDIA
module rebuilding is not implemented.

```sh
agentoo kernel build --label agentoo-v0.4 --initramfs /path/to/custom.cpio
```

`--initramfs` bypasses the minimal builder and copies that archive into
`<workspace>/initramfs/<release>/initramfs.cpio`. The old config's initramfs
path is never selected implicitly.

After compilation and module staging, build checks release consistency and
records the completed config/image hashes and a manifest of staged module files and symlinks in the workspace. Before recording
the manifest, staged directories are normalized to `0755` and files to `0644`;
symlinks are preserved. It prints the final `bzImage` path on stdout. Interrupted builds retain
their workspace for inspection/retry; install rejects incomplete or changed
config/image pairs or changed staged modules. Workspaces built before module
manifests were introduced must be rebuilt before installation. The final config remains available for manual copying; there
is no second export prompt.

## Install

The default image destination is
`/boot/EFI/Gentoo/kernel-<version>-<label>.efi`; `--dest DIR` changes the directory.
After confirmation, the command mounts `/boot` through its existing mount
configuration if necessary, then checks that the destination is on a mounted
FAT GPT EFI System Partition.

An installation is identified by kernel version plus label. Reusing both
replaces that installation, including a changed build; a different version or
label installs alongside it. If the image or module tree already exists, install
shows its backup path and asks explicitly before replacement. Image and module
backups use the same timestamp beside their respective live paths.

Install copies the validated staged module tree into a temporary root under
`/lib/modules`, then runs native `depmod --basedir <temporary-root> -a <release>`
with umask `022`. This produces readable indexes before changing the installed
tree, including built-in metadata with `CONFIG_MODULES=n`. It does not rerun make
or require the original sources. The image is also copied to a temporary name
on the ESP before activation.

The complete module tree replaces `/lib/modules/<release>`; files absent from
the build, including separately installed external modules, are removed from
the live tree. Rebuild required external modules manually for the new build.
Replacing the running release is allowed, including a module-enabled build.
Until reboot, later module loads use the replacement tree with the old running
kernel; changed modules may be incompatible. The operator chooses when to replace
and reboot. No separate boot or override flag is required.

After staging succeeds, install backs up the old image, renames the old module
tree to its backup, moves the new complete tree into place, and finally renames
the staged image into place. The command prints the native operations and staging
paths. On failure or cancellation it stops and retains backups and any remaining
staging files for inspection. Recovery is manual; no automatic rollback rewrites
the installed paths. Successful installation removes its temporary staging root.

These renames span two filesystems; an interrupted installation can leave an
incomplete pair. Inspect both live paths, then finish installation or restore
**both** original image/module backups before booting that release. Retain the
original backups when retrying: a later attempt can back up an already partial
installation. Backups and failed staging directories remain until removed manually.

By default installation prints an `efibootmgr` registration command for manual
use. To register and put the candidate first immediately:

```sh
agentoo kernel install --label agentoo-v0.4 --efi-add-entry
```

Startop registration adds `--full-dev-path` to both the printed manual command
and automatic creation, using the host recorded in the workspace. The standalone
installer and distribution-kernel guidance use the same workaround independently.

Registration reuses an entry matching the partition identity and loader path, or
creates one with `--create`, which also adds it to BootOrder. It then puts that
entry first and preserves the other entries' relative order. It leaves BootNext alone and prints
the resulting `efibootmgr -u` report. If a firmware operation fails, the installed
image remains; inspect the reported failure and `efibootmgr -u` before retrying.
There is no automatic reboot, signing or key enrollment.

Creation uses a child-process umask of `022` so a restrictive inherited umask
does not remove the read permissions requested by efibootmgr. An existing
root-only variable is not automatically chmodded by registration.

## Secure Boot

The kernel command does not sign images or enroll firmware keys. Signing and
firmware trust remain separate operator steps; a successful installation does
not establish that Secure Boot will accept the image.

[Historical baseline and Secure Boot experiments](history/kernel-baseline-build.md#signing-images-for-secure-boot)
preserve earlier notes on separate signed custom images, a distribution-kernel
UKI, key backups/enrollment, and testing both boot paths. Those machine-specific
notes are unvalidated historical evidence, not a maintained signing procedure.

## Interaction and results

Each stage displays its selected inputs before confirmation. `--yes` accepts its
displayed plans, including backup/replacement; it does not answer Kconfig or sudo
prompts. It also skips the optional config-export question. For config without a
terminal, supply both `--yes` and `--accept-defaults`. There is no `--no-input`
option and no promise of unattended sudo authentication.

Before each privileged operation, the command checks cached sudo authorization
without prompting. If a password is needed, it waits on the controlling terminal
for you to press Enter before starting sudo's timed password prompt. This wait
has no timeout and `--yes` does not skip it. The operation then uses `sudo -n`,
so revoked authorization fails rather than starting another unexpected prompt.

Results and requested help go to stdout; plans, prompts, build output and progress
go to stderr. Exit status is 0 for success, 1 for operational failure or
cancellation, and 2 for invalid CLI arguments. A successful build/install does not
establish successful boot or hardware acceptance. Retain a working recovery
kernel while testing the candidate.
