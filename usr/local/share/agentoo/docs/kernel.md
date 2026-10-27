# Rebuilding a custom kernel

`agentoo kernel` carries an existing complete config to new Gentoo sources,
builds a local x86_64 EFI kernel with an embedded initramfs, and installs it under
a versioned filename. Each subcommand also works through `agentoo-kernel`.
Run as your normal user; the command uses sudo for source Makefile changes,
system module installation, ESP writes and firmware registration. Genkernel runs
as the build user and creates user-owned workspace files.

```sh
agentoo kernel config --label agentoo-v0.4
agentoo kernel build --label agentoo-v0.4 -j16
agentoo kernel install --label agentoo-v0.4
```

## Configure

The default starting config is `/proc/config.gz`; use `--config FILE` for a
plain or gzipped config. Sources default to `/usr/src/linux`; `--sources DIR`
selects another tree. The command resolves the source symlink once and records
its concrete path for subsequent steps.

The default workspace is `/dev/shm/<version>-<label>`. It must be absent or
empty. `--build-dir DIR` chooses another location. Build storage must permit
execution and writes; a read-only or `noexec` `/dev/shm` requires another location.
Kernel outputs and genkernel working directories live beneath that workspace.
The workspace normally disappears at reboot; no persistent build archive or
last-workspace pointer is created.

After showing the plan and confirming, config:

1. Saves the starting config inside the workspace.
2. Removes the source Makefile's Gentoo EXTRAVERSION suffix, backing up the
   original Makefile beside it when a change is needed. Genkernel reads that
   field directly, so changing only make's command-line value is insufficient.
3. Sets `CONFIG_LOCALVERSION="-<label>"`, disables automatic SCM release suffixes,
   and enables EFI-stub, initramfs and `/proc/config.gz` support. It preserves
   `CONFIG_CMDLINE` and existing module choices.
4. Lists new Kconfig options and runs interactive `oldconfig`.
   `--accept-defaults` chooses `olddefconfig` instead.
5. Checks the resulting release and prints configuration differences, including
   removed symbols and changes from dependency resolution.
6. Offers an optional config export, then prints the workspace path on stdout.

Only the starting config is imported from an older build. Old initramfs images,
firmware staging and caches are not copied. If embedded firmware paths in the
config are stale, update them to current system inputs before building.

## Build

Build and install require `--label`. By default they search `/dev/shm` for a
workspace ending in that exact label, validate its metadata and show the selected
directory for confirmation. Missing or ambiguous viable matches fail with an
explanation. `--build-dir DIR` selects a specific workspace and still requires a
matching label. The source Makefile must match the one recorded by config; this
check does not fingerprint every source file or patch.

```sh
agentoo kernel build --label agentoo-v0.4 --build-dir /path/to/workspace
```

The default compiler flags are `KCFLAGS="-march=native -O2 -pipe"`. Set `KCFLAGS`
in the environment to override them at config or build time. Builds target the
machine running the command; a shared driver config does not make these binaries
portable to other CPUs. Jobs default to the CPUs available to the process.

Build clears the old embedded-initramfs setting, resolves the config and compiles
the initial kernel. It then runs `modules_install INSTALL_MOD_STRIP=1` both on
the system and into the workspace. This stage runs even with `CONFIG_MODULES=n`:
the kernel installs built-in-module metadata in that case. Thus **build writes
to `/lib/modules/<release>`**, before EFI image installation. Do not reuse a
running module-enabled kernel's release for a different candidate.

Genkernel creates a fresh uncompressed LUKS-capable initramfs on every invocation,
using the workspace cache, temporary, module and output directories. It does not
mount `/boot`, update a bootloader, install firmware or save a config in
`/etc/kernels`. Module-free configs use `--no-ramdisk-modules`; module-enabled
configs use the workspace's staged modules. Host `/etc/genkernel.conf` settings
otherwise apply. External NVIDIA module rebuilding is not implemented.

For an explicitly supplied custom archive:

```sh
agentoo kernel build --label agentoo-v0.4 --initramfs /path/to/custom.cpio
```

`--initramfs` automatically disables genkernel and copies that archive into the
workspace. `--no-genkernel` requires an archive; explicit `--genkernel` conflicts
with `--initramfs`. The old config's initramfs path is never selected implicitly.

Finally, build embeds the archive, resolves the config and compiles again. It
checks release consistency and records the completed config/image hashes in the
workspace. It prints the final `bzImage` path on stdout. Interrupted builds retain
their workspace for inspection/retry; install rejects incomplete or changed
config/image pairs. The final config remains available for manual copying; there
is no second export prompt.

## Install

The default image destination is
`/boot/EFI/Gentoo/kernel-<version>-<label>.efi`; `--dest DIR` changes the directory.
After confirmation, the command mounts `/boot` through its existing mount
configuration if necessary, then checks that the destination is on a mounted
FAT GPT EFI System Partition.

If an image already exists at the destination, installation shows its backup
path and asks explicitly before backing up and replacing it. Backups have unique
timestamped names beside the image. The new image is copied to a temporary name
on the ESP and renamed into place after copying.

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
