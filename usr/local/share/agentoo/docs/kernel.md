# Native kernel workflow

Portage owns kernel configuration merging, compilation, signing, prepared trees
and installation. Agentoo supplies the shared built-in driver union, selected
host fragment, minimal embedded initramfs, boot-critical validation and manual
EFI guidance. The custom gentoo-kernel build uses `sys-kernel/gentoo-kernel`; the
binary fallback kernel uses `sys-kernel/gentoo-kernel-bin`.

The custom gentoo-kernel build currently requires `CONFIG_MODULES=n`. Thinktop's
disposable native builds and storage smoke test have passed; deployment, physical boot and
normal-update acceptance remain open in [card 051](../kanban/Open/051-gentoo-kernel-native-workflow.md).
Bequiet/NVIDIA and other module-enabled host acceptance are deferred. There is
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
| `/etc/portage/env/kernel-local` | Local initramfs PARTUUID, mapping name, keymap and root transport |

The selected Agentoo Portage profile is the sole host selection. `prepare`
validates Btrfs `@` directly on one LUKS2 GPT partition, NVMe/AHCI transport and the
mounted FAT GPT ESP, then displays and confirms the native local input changes.
It creates the host activation and custom installkernel configuration symlinks,
records the ESP UUID, and masks sbctl's BLS/UKI install hook. EFI signing instead
belongs to the source eclass; the fallback retains its packaged signature.
Local config.d overrides are not overwritten. Re-run preparation after changing
the selected host or storage identity; review replacements before accepting.

No kernel savedconfig layer is used. Resolved installed configs are evidence,
not another policy source. The source package's native phase hook generates a
fresh archive inside WORKDIR after fragment merging and sets its computed
`CONFIG_INITRAMFS_SOURCE` using `scripts/config`. That filename is a build input,
not a persistent local override. Archive paths in an installed config need not
survive Portage cleanup.

## Prepare and build

Deploy this repository's configuration first. Keep the working boot images and
entries available while accepting the candidate. Establish and back up your
existing sbctl identity using the [Secure Boot guide](secure-boot.md); private
keys stay under `/var/lib/sbctl/keys/db` and outside Git.

Install the revised generator **before** building the kernel, then prepare on the
destination host and select the native development set:

```sh
sudo emerge --ask --oneshot --usepkg=n sys-kernel/agentoo-initramfs
agentoo kernel prepare
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
flag constraint; `CONFIG_MODULES=n` remains mandatory and no module signing key
is configured. Native signing reads sbctl's original key/certificate paths.
Missing keys fail setup rather than generating a replacement identity.

Installation copies the signed source image to
`/boot/EFI/Gentoo/kernel-<release>.efi` after checking the mounted ESP against
`/etc/kernel/gentoo-dist-esp.uuid`. The shared localversion is `-agentoo-v0.5`;
version 6.18.62 produces release `6.18.62-agentoo-v0.5`. Binary fallback kernel labels are unchanged.
It generates no external initramfs and invokes neither dracut nor standalone
microcode generation. The selected firmware/microcode is embedded in the kernel.
Native results live under `/usr/src/linux-<release>` and `/lib/modules/<release>`;
there are no Agentoo build workspaces, manifests, image backups or module staging.
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
Thinktop also needs its MICMUTE acceptance check. Preserve binary recovery.

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
not part of binary recovery or this source-workflow acceptance.
