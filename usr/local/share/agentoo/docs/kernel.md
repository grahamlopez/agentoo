# Rebuilding a custom kernel

`agentoo kernel` carries an existing complete config to new Gentoo sources,
builds a local x86_64 EFI kernel with an embedded initramfs, and installs it under
a versioned filename. Each subcommand also works through `agentoo-kernel`.
Run as your normal user; the command uses sudo for source Makefile changes,
system module installation, ESP writes and firmware registration. Initramfs builders run
as the build user and create user-owned workspace files.

```sh
agentoo kernel config --label agentoo-v0.4 \
  --config /usr/local/share/agentoo/docs/kernel-shared-v04-config
agentoo kernel build --label agentoo-v0.4 -j16
agentoo kernel install --label agentoo-v0.4
```

## Host specialization

Configure on the destination host. `/etc/agentoo/target-host` selects the tracked
native Kconfig fragment `/etc/agentoo/kernel/hosts/<name>.config`; `--host NAME`
overrides the selection, not the destination hardware or storage. Missing or
malformed profiles fail before workspace/source changes. Thinktop and flattop
are supplied initially; other hosts need reviewed profiles first.

The starting config supplies the shared driver/capability union. Host fragments
set explicit embedded firmware names, their absolute directory, CPU microcode
support and any justified Kconfig exceptions. They do not contain command lines,
initramfs paths or release labels. Complete saved configs remain useful baseline
snapshots, but their old boot identifiers and embedded firmware are replaced.
Adding a host must not prune the shared driver union. A future bequiet profile
can enable modules for NVIDIA; external-module building is still separate work.

`/etc/kernel/cmdline` is local installation data, never a tracked host UUID list.
Config reads it and inspects the mounted root through findmnt, lsblk and sysfs.
The supported layout is Btrfs subvolume `@`, directly on one LUKS2 mapping backed
by a GPT partition. Filesystem/LUKS/partition UUIDs and the actual mapping name
are recorded together. The local command line must contain matching `root=UUID=...`,
`rootfstype=btrfs`, `rootflags=subvol=@`, and either matching `crypt_root=UUID=...`
or the installer's `rd.luks.uuid=luks-...` plus `rd.luks.name=...=...`. If both
styles appear, both must match. Stale, duplicate or conflicting identifiers fail
with an explanation; correct the local file and retry. There is no automatic
rewrite of this file, fstab or storage. Block-device and dm sysfs access are
required; a restricted container is not a substitute for running on the host.

The starting config's command line supplies boot policy: console, logging,
`ro`, `root_trim=yes` and other non-storage arguments are retained in order.
Only root filesystem, encrypted-root and mapping/subvolume arguments are
specialized using the validated local identity. The baseline's encrypted-root
argument style is retained: `crypt_root` stays `crypt_root`, and dracut arguments
are updated only if the baseline explicitly includes them. The local distribution
kernel's `rd.luks.*` arguments are not imported into the custom kernel.
Missing root/layout arguments are supplied; when no encrypted-root style is
specified, config adds `crypt_root`. An empty baseline gets those storage arguments
and `ro`, without importing local boot policy. Old baseline UUIDs are replaced.
Unsupported initramfs policy fails explicitly rather
than being silently carried into an incompatible build.

The minimal initramfs uses the recorded PARTUUID and mapping name, US/Caps-to-Control
keymap, passphrase unlock, discards, `@` and `/sbin/init`. It accepts either boot
identifier style because its storage selection comes from those recorded inputs.
Alternative roots/layouts, token/key-file unlock, hibernation, nonstandard init,
or conflicting discard policy require separately scoped initramfs support.
Genkernel requires the matching `crypt_root=UUID=...` argument in the generated
command line. Use a baseline with that argument when choosing genkernel.
Previously configured workspaces retain their recorded command lines; reconfigure
from the desired baseline in a fresh workspace to adopt this behavior. Custom archives
remain explicit operator inputs and their internal storage policy is not inspected.

Config saves the original baseline, host fragment snapshot and provenance hashes,
resolved boot/storage identity and required host settings in the workspace.
Build uses this recorded policy even if the selector/profile/local command line
later changes. It checks host settings after each Kconfig resolution and refuses
silent changes. To adopt new host policy or boot identity, configure a fresh
workspace. Workspaces predating specialization must also be configured afresh.

Installed firmware remains independent: follow the native savedconfig procedure
in [firmware maintenance](firmware.md). Thinktop's existing selection is unchanged;
flattop retains broad installed coverage pending a reviewed savedconfig list.
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
2. Removes the source Makefile's Gentoo EXTRAVERSION suffix, backing up the
   original Makefile beside it when a change is needed. Genkernel reads that
   field directly, so changing only make's command-line value is insufficient.
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

Build replaces the embedded-initramfs input with a workspace-owned empty directory,
resolves the config and compiles
the initial kernel and any selected in-tree modules. It then runs
`modules_install INSTALL_MOD_STRIP=1` only into the workspace, under
`genkernel/<release>/modules/lib/modules/<release>/`. Old staged modules are
removed on rebuild so disabled drivers do not linger. This stage runs even with
`CONFIG_MODULES=n`, which stages built-in-module metadata. **Build does not write
to the system's `/lib/modules` or request sudo.** Genkernel uses this staged tree
when assembling a module-enabled initramfs.

Keeping a nonempty source path preserves Kconfig's dependent initramfs owner IDs,
compression choice and built-in ACPI override setting during configuration and
the initial build. The placeholder directory must remain empty. The final pass
replaces it with the newly generated or explicitly supplied archive; an old
archive is never reused implicitly.
Reconfigure from the original baseline in a fresh workspace if an earlier run
cleared `INITRAMFS_SOURCE` to an empty string: that run may already have dropped
the dependent settings, and the new placeholder cannot recover their old values.

By default (`--no-genkernel`), build runs the minimal initramfs builder in
`<workspace>/initramfs/<release>/`. It extracts the cached
`/var/cache/distfiles/busybox-1.36.1.tar.bz2`, builds a minimal static BusyBox,
and bundles installed cryptsetup and its libraries. The complete subtree is
regenerated on each build/retry; no network download is performed. The archive is
`<workspace>/initramfs/<release>/initramfs.cpio`.

Before compiling or changing build metadata, build invokes the minimal builder's
`--check` mode to check source availability, the keymap, required tools and
cryptsetup's linked libraries. This checks inputs, not static-link toolchain or
boot acceptance. Cache the pinned source once using the matching Gentoo ebuild:

```sh
sudo emerge --fetchonly --nodeps '=sys-apps/busybox-1.36.1-r4'
```

Portage must use `/var/cache/distfiles` as its DISTDIR for this default path.
This fetches/verifies sources without installing BusyBox. If a previous build
stopped at the missing-source check, rerun `agentoo kernel build --label LABEL`
in the same workspace; compiled kernel objects remain available for incremental
make. There is no need to rerun config or discard that workspace for this error.

This default uses the host identity recorded by config, with Btrfs `@`
and the US/Caps-to-Control console map. It requires
`CONFIG_MODULES=n` and built-in boot drivers. See the
[minimal initramfs instructions](../initramfs/README.md) for dependencies and
smoke tests. The builder receives explicit `--partuuid`, `--mapper` and `--keymap`
arguments; it has no implicit thinktop partition UUID.

Use `--genkernel` explicitly for the previous generator. Genkernel creates a
fresh uncompressed LUKS-capable initramfs using the workspace cache, temporary,
module and output directories. It does not mount `/boot`, update a bootloader,
install firmware or save a config in `/etc/kernels`. Module-free configs use
`--no-ramdisk-modules`; module-enabled configs use the workspace's staged modules.
Host `/etc/genkernel.conf` settings otherwise apply. External NVIDIA module
rebuilding is not implemented.

For an explicitly supplied custom archive:

```sh
agentoo kernel build --label agentoo-v0.4 --initramfs /path/to/custom.cpio
```

`--initramfs` bypasses both generators and copies that archive into the
workspace. Explicit `--genkernel` conflicts with `--initramfs`. The old config's initramfs path is never selected implicitly.

Finally, build embeds the archive, resolves the config and compiles again. It
checks release consistency and records the completed config/image hashes and a
manifest of staged module files and symlinks in the workspace. Before recording
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

If an image already exists at the destination, installation shows its backup
path and asks explicitly before backing up and replacing it. Backups have unique
timestamped names beside the image. Once all confirmations and ESP checks pass,
install copies the validated staged module tree into `/lib/modules/<release>`
as root and runs `depmod -a <release>` with umask `022` so generated indexes
remain readable even with a restrictive caller umask. This includes built-in metadata with
`CONFIG_MODULES=n`. It does not rerun make or require the original sources.
Existing files not present in the staged tree, including separately installed
external modules, are retained; external-module rebuilding remains manual.
Do not reuse a running module-enabled kernel's release for a different candidate.

Only after module installation and depmod succeed does install back up and
replace the EFI image. The new image is copied to a temporary name on the ESP
and renamed into place after copying. A module-copy or depmod failure leaves the
EFI image unchanged, but may leave partially updated system module files; fix
the error and retry installation.

By default installation prints an `efibootmgr` registration command for manual
use. To register and put the candidate first immediately:

```sh
agentoo kernel install --label agentoo-v0.4 --efi-add-entry
```

Registration reuses an entry matching the partition identity and loader path, or
creates one with `--create`, which also adds it to BootOrder. It then puts that
entry first and preserves the other entries' relative order. It leaves BootNext alone and prints
the resulting `efibootmgr -u` report. If a firmware operation fails, the installed
image remains; inspect the reported failure and `efibootmgr -u` before retrying.
There is no automatic reboot, signing or key enrollment.

Creation uses a child-process umask of `022` so a restrictive inherited umask
does not remove the read permissions requested by efibootmgr. An existing
root-only variable is not automatically chmodded by registration.

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
