# Native kernel workflow

Portage owns kernel configuration merging, compilation, signing, prepared trees
and installation. Agentoo supplies the shared built-in driver union, selected
host fragment, minimal embedded initramfs, boot-critical validation and manual
EFI guidance. The custom gentoo-kernel build uses `sys-kernel/gentoo-kernel`; the
binary fallback kernel uses `sys-kernel/gentoo-kernel-bin`.

Custom gentoo-kernel builds require `CONFIG_MODULES=n` except on Bequiet, which
requires signed modules with signature enforcement. All hosts retain built-in
early-boot drivers. Thinktop's
`6.18.62-agentoo-v0.5` custom kernel was accepted by the operator on 2026-11-17
following a successful Secure Boot startup and hardware checks. Its same-version
rebuild passed, including package-owned built-in driver indexes. The binary
fallback `6.18.62-gentoo-dist-bin` also booted under Secure Boot into encrypted
Btrfs root with network recovery; `/usr/src/linux` retained the custom selection.
Future update validation, configuration reduction and optional development work
are tracked in [card 052](../kanban/Backlog/052-native-kernel-maintenance-followups.md).
Older Thinktop boot/power/service findings remain in
[card 023](../kanban/Backlog/023-thinktop-kernel-v0.3-followups.md).
Bequiet's native Secure Boot/NVIDIA, hardware and refreshed binary recovery
acceptance passed on 2026-11-17; remaining rebuild acceptance is recorded in its
[host guide](hosts/bequiet.md#native-conversion-status). Other hosts cannot enable
modules. See [Bequiet conversion](#bequiet-conversion). There is
one supported build interface: native Portage commands.

## Host specialization

Configuration is authoritative at these locations, applied in native filename order:

| Path | Purpose |
| --- | --- |
| `/etc/kernel/config.d/10-agentoo.config` | Tracked shared baseline, including explicit disabled options |
| `/etc/agentoo/kernel/hosts/<host>.config` | Tracked host specialization; preserve the shared driver union |
| `/etc/kernel/config.d/20-host.config` | Local symlink activating the selected host fragment |
| `/etc/kernel/config.d/80-local-boot.config` | Optional untracked command-line/release settings |
| `/etc/kernel/config.d/90-local.config` | Optional untracked overrides and experiments |
| `/etc/portage/env/kernel-local` | Local initramfs PARTUUID, mapping name and root transport; optional keymap override |

The selected Agentoo Portage profile is the sole host selection. Target
installation activates the matching reviewed host fragment and records local
inputs from its validated LUKS2/Btrfs `@` layout and NVMe/AHCI storage. Generic,
QEMU and module-enabled targets other than Bequiet retain the binary fallback workflow.
The installer records the mounted ESP UUID for both kernel installation paths.

These inputs are installation-time setup. After changing storage, the selected
profile or ESP, review `/etc/portage/env/kernel-local`, the host activation link
and `/etc/kernel/gentoo-dist-esp.uuid` directly. Keep UUIDs outside Git. Local
config.d overrides are preserved. The generator owns the default console keymap;
set `AGENTOO_INITRAMFS_KEYMAP` in kernel-local only to override it.

Shared `/etc/tmpfiles.d/agentoo-kernel.conf` creates the custom installkernel
configuration link and masks sbctl's incompatible BLS/UKI install hook. The
custom link reuses shared efistub policy; its drop-in disables external archive
generation. EFI signing belongs to the source eclass; the binary fallback
retains its packaged signature. Apply these rules immediately after deploying
configuration, before either kernel is installed; they also apply at boot.

No kernel savedconfig layer is used. Resolved installed configs are evidence,
not another policy source. The source package's native phase hook generates a
fresh archive inside WORKDIR after fragment merging and sets its computed
`CONFIG_INITRAMFS_SOURCE` using `scripts/config`. That filename is a build input,
not a persistent local override. Archive paths in an installed config need not
survive Portage cleanup.

## Setup and build

Deploy this repository's configuration first. Keep the working boot images and
entries available while accepting the candidate. Establish and back up your
existing sbctl identity using the [Secure Boot guide](secure-boot.md); private
keys stay under `/var/lib/sbctl/keys/db` and outside Git.

Apply shared installation policy, install the revised generator **before**
building the kernel, then select the native development set:

```sh
sudo systemd-tmpfiles --create agentoo-kernel.conf
sudo emerge --ask --oneshot --usepkg=n sys-kernel/agentoo-initramfs
```

For the one-off Thinktop conversion, first inspect `eselect --brief --colour=no
profile show`, `findmnt --target /`, `findmnt --mountpoint /boot` and
`lsblk -o NAME,TYPE,FSTYPE,PARTUUID,TRAN`.
Require the intended Thinktop profile, Btrfs `@` directly on LUKS2/NVMe and the
mounted target FAT GPT ESP. Record the encrypted partition's **PARTUUID**, not
its LUKS UUID, with `sudoedit /etc/portage/env/kernel-local`:

```sh
AGENTOO_INITRAMFS_PARTUUID=ENCRYPTED_PARTITION_PARTUUID
AGENTOO_INITRAMFS_MAPPER=cryptroot
AGENTOO_INITRAMFS_TRANSPORT=nvme
```

Activate the host fragment and record the mounted ESP's filesystem UUID:

```sh
sudo ln -sfnT /etc/agentoo/kernel/hosts/thinktop.config /etc/kernel/config.d/20-host.config
findmnt -n -o UUID --mountpoint /boot
sudoedit /etc/kernel/gentoo-dist-esp.uuid
```

The ESP file contains only that UUID. Review existing values before replacing
any local setup. The installer establishes these inputs on new supported targets;
there is no recurring preparation or migration command. Once the local inputs
are established, review and build the native development set:

```sh
sudo emerge --ask --pretend --verbose --usepkg=n @kernel-dev
sudo emerge --ask --usepkg=n @kernel-dev
```

Generator revision `1-r1` or newer uses static ELF dependency inspection and
excludes Portage preload libraries from the archive. The installed generator,
BusyBox and cryptsetup/libraries supply the archive; no sources are downloaded
by archive generation itself. See [initramfs development](initramfs.md).

Portage merges Gentoo package defaults and config.d, generates the custom
archive, resolves Kconfig, validates the final boot/host settings, compiles and
stages the native prepared tree. `secureboot modules-sign` satisfies Gentoo's
flag constraint. No-module hosts configure no module signing key. Bequiet's native
profile supplies the existing sbctl db key/certificate for kernel and NVIDIA module
signing; Gentoo supplies the module-signing Kconfig settings. Final validation
requires modules, signing, signing of all in-tree modules and signature enforcement
on Bequiet. Native EFI signing reads sbctl's original key/certificate paths.
Missing keys fail setup rather than generating a replacement identity.

Installation copies the signed source image to
`/boot/EFI/Gentoo/kernel-<release>.efi` after checking the mounted ESP against
`/etc/kernel/gentoo-dist-esp.uuid`. The shared localversion is `-agentoo-v0.5`;
version 6.18.62 produces release `6.18.62-agentoo-v0.5`. Binary fallback kernel labels are unchanged.
It generates no external initramfs and invokes neither dracut nor standalone
microcode generation. The selected firmware/microcode is embedded in the kernel.
Native results live under `/usr/src/linux-<release>` and `/lib/modules/<release>`.
The source package's `post_src_install` hook generates kmod indexes with
native depmod, including built-in driver indexes for CONFIG_MODULES=n. These
files are package-owned; built-in drivers remain recognizable to userspace tools.
After a custom package installation, its native Portage hook runs `eselect kernel
set linux-<release>` so `/usr/src/linux` selects that installed prepared tree.
Binary fallback installation uses its own release paths and preserves a valid
custom selection; do not flip the default for binary refreshes. Inspect it with
`eselect kernel show`. Until a custom build is installed, the binary tree may
be selected. Native eselect rejects an existing real `/usr/src/linux` directory;
review it manually rather than replacing it with a link.
There are no Agentoo build workspaces, manifests, image backups or module staging.
Portage's replacement/removal behavior applies. Keep a separately tested boot
entry; do not treat same-release replacement as an automatic rollback mechanism.

To compile in RAM, use Portage's native `PORTAGE_TMPDIR` setting with sufficient
space, execution permissions and quota headroom. Trials used about 9.2 GiB for
the build directory, plus link temporaries and the package image. Installed
package results remain on persistent storage. Do not retain a second RAM-copy
or workspace lifecycle.

## Generate an EFI registration command

For the installed source image:

```sh
agentoo kernel gen-efi-cmd \
  --image /boot/EFI/Gentoo/kernel-RELEASE.efi
```

The helper validates the image's mounted FAT GPT ESP and prints one shell-quoted
`sudo efibootmgr --create-only ...` command. Review and execute it separately.
It leaves BootOrder and BootNext unchanged. Select the candidate from the firmware
boot menu for first acceptance. Startop guidance adds its required full-device-path
option using the selected host profile. No command in this workflow reboots,
enrolls keys or changes firmware entries automatically.

The installkernel guidance hook calls the same helper. For binary fallback kernel
images ending `-gentoo-dist-bin.efi` (and standard external-initramfs distribution
images ending `-gentoo-dist.efi`), it includes `/etc/kernel/cmdline` and the matching
external `initrd=` path. The custom gentoo-kernel build uses its embedded boot
policy.
`--args 'loglevel=7'` adds optional firmware arguments; `--label TEXT` changes the
display label. Firmware arguments supplement the built-in command line; repeated
parameters have parameter-specific precedence. The minimal initramfs uses its
embedded storage identity, independently of those arguments.

Verify the actual source image against the intended enrolled certificate:

```sh
sudo sbverify --cert /var/lib/sbctl/keys/db/db.pem \
  /boot/EFI/Gentoo/kernel-RELEASE.efi
```

A matching signature does not establish firmware trust or physical boot success.
Check selected release, passphrase retries, internal/USB keyboards, Btrfs `@`,
discards, microcode, systemd startup, networking, displays/audio and suspend/resume.
Include Thinktop’s microphone mute button in input checks. Preserve binary recovery.

On 2026-11-17, the operator confirmed that Thinktop’s microphone mute button
worked after a full shutdown and power-on into `6.18.62-agentoo-v0.5` with
`90-thinktop-micmute.rules` disabled. Inspection confirmed that the rename
preceded boot, no active udev rule supplied the correction, and the live
ThinkPad input device had no `KEYBOARD_KEY_1a` property. The legacy genkernel
workaround was retired on this evidence (card 020). Raw keycode 248 was not
separately captured.

## Updates and rebuilds

Install/update the source package through Portage:

```sh
sudo emerge --ask --usepkg=n sys-kernel/gentoo-kernel
```

After configuration, generator, BusyBox, cryptsetup/libraries or embedded firmware
changes, regenerate and recompile the selected version:

```sh
sudo emerge --ask --oneshot --usepkg=n '=sys-kernel/gentoo-kernel-VERSION'
```

Update the generator and other archive inputs first. A normal source build's
prepare phase creates a new archive from the inputs installed at that time; a
later userspace upgrade does not update an already embedded archive. Recompilation
is required. `emerge --config` only reinstalls an existing custom gentoo-kernel
build; it cannot refresh its embedded archive or firmware. Review EFI guidance after every
new release and independently boot-test maintenance results.

### Firmware and microcode updates

`linux-firmware` and `intel-microcode` use `-initramfs`: updating their installed
payloads does not regenerate or reinstall either boot artifact. Shared dracut
policy explicitly enables early microcode for the binary fallback, overriding
the firmware packages' disabled generator defaults. No custom filtering hook
or all-kernels maintenance dispatcher is used.

After installing firmware/microcode updates, explicitly refresh both kernels:

```sh
sudo emerge --config '=sys-kernel/gentoo-kernel-bin-VERSION'
sudo emerge --ask --oneshot --usepkg=n '=sys-kernel/gentoo-kernel-VERSION'
```

Replace each VERSION with that package's intended installed version; they need
not match. Refresh each binary fallback version you intend to retain. The first
command regenerates its external archive; the second recompiles embedded inputs.
The same requirement applies after `agentoo kernel firmware apply`. Check both
results and cold-boot the affected kernels. `kernel-install add-all` and
`installkernel --all` do not select our custom package environment and are not
the refresh workflow for this mixed setup.

## Configuration experiments

For a reproducible experiment, edit `/etc/kernel/config.d/90-local.config`, then
force a source rebuild with the command above. Inspect the resolved config under
`/usr/src/linux-<release>/.config`. Remove the experimental entries to return to
shared/host policy on the next fresh merge. Promote accepted changes into the
appropriate tracked fragment and remove redundant local settings. Do not prune
other hosts' built-in driver requirements to specialize one host.

For menu-based exploration, use matching **full sources** from native unpack/
prepare, with a separate output directory seeded from a current resolved config:

```sh
mkdir -p "$experiment"
cp "$resolved_config" "$experiment/.config"
cp "$experiment/.config" "$experiment/before.config"
make -C "$sources" O="$experiment" menuconfig
# Alternatively edit .config directly, then resolve dependencies:
make -C "$sources" O="$experiment" olddefconfig
diff -u "$experiment/before.config" "$experiment/.config"
```

Use `ebuild /var/db/repos/gentoo/sys-kernel/gentoo-kernel/gentoo-kernel-VERSION.ebuild
unpack prepare configure` with dedicated native PORTAGE_TMPDIR for development;
the usual installed host inputs and signing setup still apply. Its WORKDIR
contains the full source directory and resolved `build/.config`. The installed
prepared tree is not assumed to be a full development tree.

Move intentional deltas into fragments and rebuild with Portage. Editing the
installed `.config` does not configure the next emerge. Removing a fragment does
not reset an already edited `.config`: remerge policy. Generated compiler metadata
and initramfs filenames are not settings to promote. If preparing a detached
compile, generate/select its own archive first; cleanup invalidates references to
another build's WORKDIR. The fast detached incremental compile/install loop still
needs acceptance; no separate persistent development framework is provided.

## Binary fallback

The binary package remains independently managed through the shared installkernel
configuration and dracut:

```sh
sudo emerge --ask sys-kernel/gentoo-kernel-bin
sudo emerge --config '=sys-kernel/gentoo-kernel-bin-VERSION'
```

The second command regenerates its external initramfs and reinstalls that version.
Its local root arguments remain in `/etc/kernel/cmdline`. Custom source package
environment/plugin selection does not apply to the binary package. Verify the
fallback's packaged signing certificate and firmware acceptance separately.

Bequiet's accepted fallback remains console/network recovery. When registering
that host's fallback, add `--args 'systemd.unit=multi-user.target
systemd.mask=getty@tty1.service'`; tty2 retains password login. NVIDIA support is
outside the binary recovery requirement; it is required for Bequiet's custom
kernel acceptance.

## Bequiet conversion

The native Bequiet conversion passed Secure Boot/NVIDIA, hardware and refreshed
binary recovery acceptance; see the
[host evidence](hosts/bequiet.md#native-conversion-status) for pending maintenance
checks. Keep the accepted
`6.18.62-gentoo-bequiet-secure` image/entry and binary console/network recovery.
Reuse the existing enrolled sbctl identity; this conversion does not require new
keys or reenrollment.

Follow the migration steps below on Bequiet, using its own root partition,
mapping and transport. Confirm the selected profile is Bequiet and activate
`/etc/agentoo/kernel/hosts/bequiet.config`. Review existing local overrides so
they do not replace the new release or native signing policy. The embedded
initramfs does not load modules; NVIDIA loads after real-root handoff, with its
package-owned GSP firmware and graphics configuration.

After building the source kernel in step 4, inspect its resolved configuration:

```sh
release=6.18.62-agentoo-v0.5
rg '^CONFIG_(MODULES|MODULE_UNLOAD|MODULE_SIG|MODULE_SIG_ALL|MODULE_SIG_FORCE|MODULE_SIG_HASH|MODULE_SIG_KEY)=' \
  "/usr/src/linux-$release/.config"
openssl x509 -inform DER -in "/usr/src/linux-$release/certs/signing_key.x509" \
  -noout -fingerprint -sha256
sudo openssl x509 -in /var/lib/sbctl/keys/db/db.pem -noout -fingerprint -sha256
```

Require `MODULES`, `MODULE_UNLOAD`, `MODULE_SIG`, `MODULE_SIG_ALL` and
`MODULE_SIG_FORCE` to be `y`, and matching certificate fingerprints.
`MODULE_SIG_KEY` may reference a temporary native build input; external modules
use the original sbctl paths from Bequiet's profile.

Confirm `eselect kernel show` selects the installed custom candidate, then build
NVIDIA using that native selection:

```sh
eselect kernel show
sudo emerge -av --usepkg=n x11-drivers/nvidia-drivers
for module in nvidia nvidia_modeset nvidia_drm nvidia_uvm; do
  modinfo -k "$release" -F filename "$module"
  modinfo -k "$release" -F vermagic "$module"
  modinfo -k "$release" -F signer "$module"
done
modprobe --set-version "$release" --show-depends nvidia_drm
```

Check the build log names the candidate release, module paths/version magic match
it and dependency indexes resolve the modules. Signer metadata requires kmod's
OpenSSL support; without it, empty signer fields and an unknown hash are
inconclusive. Bequiet's first conversion independently verified the module PKCS#7
signatures against the embedded certificate. These are preboot checks; module loading with signature
enforcement establishes kernel trust. Continue step 4's EFI verification and
manual registration, then boot the candidate under Secure Boot. Check
`sbctl status`, `uname -r`, `/sys/module/module/parameters/sig_enforce`, both GPUs
with `nvidia-smi`, Hyprland, USB unlock, normal peripherals and suspend/resume.
Test GPU compute workloads separately if required. Independently test recovery.

After custom kernel rebuilds, rebuild NVIDIA with the same emerge command above
before booting. A same-version rebuild or conversion does not change
`virtual/dist-kernel`'s subslot and does not automatically trigger its dependent
rebuilds. Native `dist-kernel` dependency handling supports version updates; its
behavior with both kernel providers still needs Bequiet acceptance. Repeat boot
checks after a same-version rebuild and a subsequent version update, inspecting
the resulting modules before boot. Record evidence in the Bequiet host guide. No custom
module dispatcher or workspace lifecycle is used.

## gentoo-sources to gentoo-kernel migration

These are one-time steps to migrate an already-installed system to the new
gentoo-kernel based custom kernel workflow. This configuration is established
by the installer on new systems.

Use the same sequence on each target host itself. Step 2 requires that host’s
storage values; don’t reuse Thinktop’s.

### 1. Deploy configuration and shared policy

sudo agentoo git pull
sudo systemd-tmpfiles --create agentoo-kernel.conf

target_host=$(python3 -B /usr/local/share/agentoo/lib/host_selection.py)
printf 'Selected host: %s\n' "$target_host"

Confirm this prints flattop, startop or bequiet, as appropriate. For Bequiet,
also follow [Bequiet conversion](#bequiet-conversion) before registering or booting
the candidate.

### 2. Establish local kernel inputs

Inspect the root mapping, encrypted partition and ESP:

findmnt -n -o SOURCE,FSTYPE,FSROOT --target /
lsblk -o NAME,TYPE,FSTYPE,PARTUUID,TRAN
findmnt -n -o SOURCE,FSTYPE,UUID --mountpoint /boot

Edit the native environment file:

sudoedit /etc/portage/env/kernel-local

Enter these settings, substituting the values from that host’s inventory:

AGENTOO_INITRAMFS_PARTUUID=ENCRYPTED_PARTITION_PARTUUID
AGENTOO_INITRAMFS_MAPPER=ROOT_MAPPING_NAME
AGENTOO_INITRAMFS_TRANSPORT=nvme

Use the partition’s PARTUUID, and the mapping name without /dev/mapper/.
Flattop previously used crypt_root; confirm its current value. Use sata instead
of nvme if the root disk’s transport is SATA.

Then activate the host fragment and record the mounted ESP’s filesystem UUID:

sudo chmod 0644 /etc/portage/env/kernel-local

sudo ln -sfnT \
  "/etc/agentoo/kernel/hosts/$target_host.config" \
  /etc/kernel/config.d/20-host.config

findmnt -n -o UUID --mountpoint /boot
sudoedit /etc/kernel/gentoo-dist-esp.uuid
sudo chmod 0644 /etc/kernel/gentoo-dist-esp.uuid

The ESP file should contain only the UUID printed immediately above.

Review any existing local kernel overrides before building:

ls -l /etc/kernel/config.d
rg -n 'CONFIG_(LOCALVERSION|INITRAMFS_SOURCE|CMDLINE)' /etc/kernel/config.d

Remove obsolete local overrides deliberately; the intended shared localversion
is -agentoo-v0.5.

### 3. Install prerequisites and apply firmware policy

Keep the currently installed firmware versions while applying the USE changes:

firmware_atom=$(portageq best_version / sys-kernel/linux-firmware)
microcode_atom=$(portageq best_version / sys-firmware/intel-microcode)

sudo emerge --ask --oneshot --newuse --usepkg=n "=$firmware_atom"
if [ -n "$microcode_atom" ]; then
  sudo emerge --ask --oneshot --newuse --usepkg=n "=$microcode_atom"
fi

sudo emerge --ask --oneshot --usepkg=n sys-kernel/agentoo-initramfs
sudo emerge --ask --noreplace sys-fs/dosfstools
sudo systemctl daemon-reload

Bequiet gets AMD microcode from linux-firmware and does not need intel-microcode.
Preserve the existing firmware savedconfig selection. Flattop firmware trimming
can remain separate.

### 4. Refresh the fallback, build and validate

Refresh whichever binary fallback version is installed on that host:

fallback_atom=$(portageq best_version / sys-kernel/gentoo-kernel-bin)
sudo emerge --config "=$fallback_atom"

Build the same source version evaluated on Thinktop:

sudo emerge --ask --oneshot --usepkg=n \
  '=sys-kernel/gentoo-kernel-6.18.62'

Check the result:

eselect kernel show
modinfo -k 6.18.62-agentoo-v0.5 i2c-dev

sudo sbverify --cert /var/lib/sbctl/keys/db/db.pem \
  /boot/EFI/Gentoo/kernel-6.18.62-agentoo-v0.5.efi

agentoo kernel gen-efi-cmd \
  --image /boot/EFI/Gentoo/kernel-6.18.62-agentoo-v0.5.efi

Review and execute the printed EFI command. On Startop, confirm it includes --full-dev-path.

Boot the custom kernel through the firmware menu, test the host’s hardware and
suspend/resume, then independently boot-test the refreshed binary fallback.
Stop at any failed command and send its output.
