# Rebuilding a custom kernel

`agentoo kernel` carries an existing complete config to new Gentoo sources,
builds a local x86_64 EFI kernel with an embedded initramfs, and installs it under
a versioned filename. Each subcommand also works through `agentoo-kernel`.
Run as your normal user; the command uses sudo for system module installation,
image signing, ESP writes and firmware registration. Initramfs builders run as
the build user and create user-owned workspace files.

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
fail before workspace/source changes. Thinktop, flattop, startop and bequiet
fragments are supplied; Startop has build/boot and peripheral acceptance.
Bequiet's unsigned module-enabled build/install implementation awaits host
acceptance in the [active card](../kanban/Open/026-bequiet-custom-kernel.md).
Other hosts need reviewed fragments first.

The starting config supplies the shared driver/capability union. Host fragments
set explicit embedded firmware names, their absolute directory, CPU microcode
support and any justified Kconfig exceptions. They do not contain command lines,
initramfs paths or release labels. Complete saved configs remain useful baseline
snapshots, but their command line and embedded firmware are replaced.
The shared snapshot was checked against the running minimal-initramfs v0.4
config and resolved with native Kconfig. Its archive path and firmware list are
empty; the workspace and selected host fragment provide those inputs.
Adding a host must not prune the shared driver union. Bequiet's fragment enables
modules and signature verification for NVIDIA while preserving built-in drivers.
NVIDIA bring-up is unsigned. Module signing and subsequent driver-update
maintenance are deferred until after the first boot/hardware acceptance.

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

Default workspaces live under
`${XDG_STATE_HOME:-$HOME/.local/state}/agentoo/kernel/<version>-<label>` and survive
reboot. Config requires an absent or empty workspace. Default builds copy the
workspace to `/dev/shm/<release>`, compile there, retain the results on disk and
remove the RAM copy. Native `make prepare` repairs the retained output Makefile;
module staging then records the persistent build link and final manifest. The
installed source tree must also remain available for NVIDIA rebuilds.

`--build-dir DIR` selects a workspace explicitly and builds directly there. Pass
it to each operation for a workspace outside the default root. This also provides
a direct build path when `/dev/shm` is read-only, `noexec` or too small. Both
workspace and compilation storage must permit execution and writes. A pre-existing
RAM work directory stops a default build before changes; inspect leftovers from
copy failures before retrying. There is no last-workspace pointer or archive service.

After showing the plan and confirming, config:

1. Saves the starting config inside the workspace.
2. Preserves the source's native version, including Gentoo's suffix. The source
   Makefile remains untouched; no EXTRAVERSION override is passed to make.
   Gentoo sources therefore produce releases such as `6.18.62-gentoo-<label>`,
   which native Portage module-version detection also recognizes.
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

Build, install and modules require `--label`. By default they search the persistent
workspace root for a directory ending in that exact label, validate its metadata
and show the selected directory for confirmation. Missing or ambiguous viable
matches fail. `--build-dir DIR` selects a specific workspace and still requires a
matching label. Build checks the recorded source Makefile; it does not fingerprint
every source file or patch. Install validates completed artifacts and needs the
retained source tree when NVIDIA rebuilding is selected.

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
profile or rediscover storage. The default requires built-in boot capabilities; `CONFIG_MODULES=y` is allowed.
The recorded root transport must be NVMe or AHCI SATA, with its driver built in.
The command also checks built-in device-mapper/AES-XTS/Btrfs, API filesystems,
ELF execution, GPT support, USB/xHCI/HID input and a framebuffer console.
These checks run before generation and again after Kconfig resolution. See the [initramfs guide](initramfs.md) for the package
boundary, standalone development and smoke testing.

Initramfs-only changes still require kernel build/install because the archive is
embedded. Reuse the configured workspace for incremental make; unchanged kernel
objects can be reused, while the archive and affected kernel image are rebuilt.
Emerging the package alone does not update an existing boot image.

Other early-boot driver/unlock requirements need an explicitly supplied archive.
NVIDIA loads after real-root handoff; it does not require initramfs module loading.

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
the RAM directory for inspection; partial compile results are not copied back.
Remove or relocate that directory before retrying a default build. Completed
builds are copied back before RAM cleanup; a failed copy leaves the RAM directory
available and the persistent workspace incomplete; install rejects incomplete or changed
config/image pairs or changed staged modules. Workspaces built before module
manifests were introduced must be rebuilt before installation. The final config remains available for manual copying; there
is no second export prompt.

## Install

The default image destination is
`/boot/EFI/Gentoo/kernel-<version>-<label>.efi`; `--dest DIR` changes the directory.
Installation signs by default using `sbsign` and sbctl's standard file key and
certificate at `/var/lib/sbctl/keys/db/db.{key,pem}`. Follow
[initial signing and enrollment](secure-boot.md) to create and back up the keys.
Missing signing tools or unreadable inputs stop installation; `--yes` does not
bypass signing. Firmware Secure Boot state does not change this default.
After confirmation and a privileged check that signing inputs are readable,
the command mounts `/boot` through its existing mount configuration if necessary,
then checks that the destination is on a mounted FAT GPT EFI System Partition.

To explicitly install the original image without signing or verification:

```sh
agentoo kernel install --label agentoo-v0.4 --unsigned
```

Unsigned installation needs no signing tools or keys. Such images normally
cannot boot with Secure Boot enabled. Config and build remain independent of
signing; alternate key layouts and hardware tokens are not supported here.

An installation is identified by kernel version plus label. Reusing both
replaces that installation, including a changed build; a different version or
label installs alongside it. If the image or module tree already exists, install
shows its backup path and asks explicitly before replacement. Image and module
backups use the same timestamp beside their respective live paths.

Install copies the validated staged module tree into a temporary root under
`/lib/modules`, then runs native `depmod --basedir <temporary-root> -a <release>`
with umask `022`. This produces readable indexes before changing the installed
tree, including built-in metadata with `CONFIG_MODULES=n`. In-tree module
activation does not rerun make; NVIDIA rebuilding requires the recorded sources
and output. The image is also copied to a temporary name
on the ESP before activation. Unless `--unsigned` was supplied, that copy is
signed, verified against the expected certificate using `sbverify --cert`, and
set to mode `0644`. The workspace image and recorded build hashes stay unchanged.
Signing or verification failure leaves the live image and module tree untouched
and performs no firmware registration; remaining staging files are retained.

The complete module tree replaces `/lib/modules/<release>`; files absent from
the staged build are removed from the live tree. For a module-enabled kernel with
the packaged NVIDIA driver selected, installation then rebuilds that exact installed
package from source against the recorded kernel source/output tree. Native Portage
policy supplies module processing and depmod. The command checks module versions,
release compatibility and installed paths before activating the image. If NVIDIA
rebuilding or these checks fail, the previous module
tree is restored, failed files are retained for inspection and the image/boot
entries remain unchanged. Other external-module packages remain operator work.
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
There is no automatic reboot or key enrollment.

Creation uses a child-process umask of `022` so a restrictive inherited umask
does not remove the read permissions requested by efibootmgr. An existing
root-only variable is not automatically chmodded by registration.

## Generate an EFI registration command

For an installed image, print a registration command independently of its build
workspace:

```sh
agentoo kernel gen-efi-cmd \
  --image /boot/EFI/Gentoo/kernel-RELEASE.efi
```

`--args TEXT` optionally supplies extra firmware-passed kernel arguments. `--label TEXT`
sets the boot-entry display name; its default is the image filename without the
extension. For example:

```sh
agentoo kernel gen-efi-cmd \
  --image /boot/EFI/Gentoo/kernel-RELEASE.efi \
  --label 'Agentoo debug' --args 'loglevel=7 ignore_loglevel'
```

The image must exist on a mounted FAT GPT EFI System Partition. The command
inspects that mount and partition to determine the disk, partition number and
firmware-relative loader path. The currently selected Agentoo Portage profile
supplies host registration policy, including Startop's `--full-dev-path`.
It needs no build workspace, kernel sources, root authorization or `efibootmgr`
installation to print the command, and does not mount the ESP or write firmware.

For distribution images named `kernel-<release>-gentoo-dist.efi` or
`kernel-<release>-gentoo-dist-bin.efi`, the command automatically reads the local
`/etc/kernel/cmdline` and adds `initrd=` pointing to the matching
`initramfs-…-gentoo-dist.img` or `initramfs-…-gentoo-dist-bin.img` beside the
image on the ESP.
Both the command-line file and archive must exist and be nonempty. `--args`
adds options after these distribution boot arguments. For example:

```sh
agentoo kernel gen-efi-cmd \
  --image /boot/EFI/Gentoo/kernel-6.18.62-gentoo-dist-bin.efi
```

The generated entry captures these inputs at registration time. Editing
`/etc/kernel/cmdline` later does not update an existing firmware entry.

To manually correct a distribution entry created without boot arguments, append
the following to its `efibootmgr --create` command (substitute the installed
release in the initramfs filename):

```sh
--unicode -- "$(cat /etc/kernel/cmdline) initrd=\EFI\Gentoo\initramfs-6.18.62-gentoo-dist-bin.img"
```

This creates a new entry rather than editing the old entry's arguments. Use
`--create-only` instead of `--create` to leave BootOrder unchanged, then select
the corrected entry from the firmware boot menu to test it.

Stdout contains one shell-quoted `sudo efibootmgr --create ...` command; review
and run it separately. Running it creates a new entry and places it first in
BootOrder, retaining existing entries. It does not edit an existing entry's
arguments. For other image names, omitting `--args` or supplying an empty string
creates an entry with no firmware-supplied arguments. Nonempty arguments use Unicode encoding
and follow an option delimiter so they cannot become efibootmgr options.

For Agentoo-built kernels, firmware arguments supplement the embedded command
line. Repeated parameters have parameter-specific behavior; these arguments do
not remove embedded settings. Use `config --cmdline TEXT` and rebuild when the
embedded defaults themselves need changing. The minimal initramfs still uses
its embedded storage identity, independently of firmware arguments.

## Secure Boot

See [initial signing and enrollment](secure-boot.md) for commands to sign a
separate custom image and establish firmware trust for Agentoo, the Gentoo
fallback and Windows. Install signs by default; key creation and firmware
enrollment remain explicit operator steps. A successfully verified signature
does not establish that the firmware trusts that certificate or will accept the
image. Boot-test each required entry with Secure Boot enabled. The packaged
Gentoo fallback remains managed independently by Portage/installkernel/dracut.

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

## Bequiet boot bring-up before signing

Apply the repository changes on the host and keep Secure Boot disabled. Bequiet's
profile selects `-modules-sign` for this first milestone. Config/build do not need
signing keys or a certificate, and installation still builds NVIDIA against the
final kernel and verifies its package version, release and installed paths.

```sh
agentoo kernel config --label bequiet-bringup \
  --config /usr/local/share/agentoo/docs/kernel-shared-v04-config \
  --sources /usr/src/linux-6.18.62-gentoo
agentoo kernel build --label bequiet-bringup
agentoo kernel install --label bequiet-bringup --unsigned
```

Use the installed source version when it changes. `--unsigned` explicitly skips
EFI image signing; module signing follows native `modules-sign` independently.
The shared lockdown LSM selects module verification. The fragment leaves signature
enforcement and automatic signing disabled and generates no signing key. No
module signing keys or certificates are used for this milestone.
Retain the distribution fallback. Register a separate firmware entry and test USB
unlock, normal startup, both GPUs, displays/Hyprland and used peripherals before
starting signing/enrollment or firmware trimming.

Use `eselect kernel` to select the Gentoo source tree; `config` defaults to that
selection and records its concrete path for later builds. `--sources` is an
optional per-workspace override. Normal Portage integration with retained output
trees remains under review: the native module helpers require the matching output
context, and linux-firmware's regeneration hook assumes an image in its source
directory. Repeatedly changing the source selector is not the intended workflow.
This implementation rebuilds NVIDIA only for the candidate being installed;
ordinary driver updates, firmware-hook integration and module signing remain in
the [work card](../kanban/Open/026-bequiet-custom-kernel.md).
