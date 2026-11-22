# Native kernel workflow

Portage owns kernel config merging, compilation, signing, prepared trees, and
installation (`sys-kernel/gentoo-kernel` for custom builds;
`sys-kernel/gentoo-kernel-bin` for the binary fallback). Agentoo supplies the
shared built-in driver union, selected host fragment, minimal embedded
initramfs, boot-critical validation, and manual EFI guidance (`agentoo kernel
--help`).

Custom `gentoo-kernel` builds require `CONFIG_MODULES=n` except on Bequiet,
which requires signed modules with signature enforcement (`MODULE_SIG_FORCE=y`).
Early-boot drivers stay built in on every host. Deferred maintenance and config
reduction live in [card 052](../kanban/Backlog/052-native-kernel-maintenance-followups.md).

## Host specialization

Authoritative layers applied in native filename order:

| Path | Purpose |
| --- | --- |
| `/etc/kernel/config.d/10-agentoo.config` | Tracked shared baseline, including explicit disabled options |
| `/etc/agentoo/kernel/hosts/<host>.config` | Tracked host specialization (preserves shared driver union) |
| `/etc/kernel/config.d/20-host.config` | Local symlink activating the selected host fragment |
| `/etc/kernel/config.d/80-local-boot.config` | Optional untracked command-line/release settings |
| `/etc/kernel/config.d/90-local.config` | Optional untracked overrides and experiments |
| `/etc/portage/env/kernel-local` | Local initramfs `PARTUUID`, mapper name, root transport, optional keymap |

The installer sets `/etc/portage/env/kernel-local`, `20-host.config`, and
`/etc/kernel/gentoo-dist-esp.uuid` from the validated LUKS2/Btrfs `@` layout
(review them manually after changing storage, profile, or ESP; keep UUIDs out
of Git). Shared `/etc/tmpfiles.d/agentoo-kernel.conf` links the custom
installkernel config and masks sbctl's incompatible BLS/UKI hook. No kernel
savedconfig layer is used; `post_src_prepare` generates a fresh initramfs
archive in `WORKDIR` and sets `CONFIG_INITRAMFS_SOURCE` via `scripts/config`.

## Setup and build

Establish and back up your sbctl keys first ([Secure Boot guide](secure-boot.md);
private keys stay under `/var/lib/sbctl/keys/db`, outside Git). Apply tmpfiles
and install the initramfs generator **before** building `@kernel-dev`:

```sh
sudo systemd-tmpfiles --create agentoo-kernel.conf
sudo emerge --ask --oneshot --usepkg=n sys-kernel/agentoo-initramfs
```

For existing hosts still migrating from `gentoo-sources`, establish local
inputs using [card 053](../kanban/Open/053-gentoo-kernel-fleet-migration.md).
Then preview and build:

```sh
sudo emerge --ask --pretend --verbose --usepkg=n @kernel-dev
sudo emerge --ask --usepkg=n @kernel-dev
```

What Portage handles natively:
- Generates the fresh embedded initramfs archive (`1-r1`+ uses static ELF
  inspection; see [initramfs guide](initramfs.md)), resolves Kconfig, and
  validates required built-in boot drivers and host policy.
- Signs the EFI image via `USE="secureboot modules-sign"` using sbctl's db
  key/cert (missing keys fail rather than generating replacements).
- Installs the signed image to `/boot/EFI/Gentoo/kernel-<release>.efi` (shared
  localversion `-agentoo-v0.5`) after checking `/boot` against
  `/etc/kernel/gentoo-dist-esp.uuid`, with no external initramfs or dracut run.
- Generates package-owned kmod built-in driver indexes via `depmod` in
  `post_src_install` and selects the installed prepared tree with
  `eselect kernel set linux-<release>` (binary refreshes keep a valid custom
  selection).
- To compile in RAM, use Portage's native `PORTAGE_TMPDIR` (~9.2 GiB+ headroom).

## Generate an EFI registration command

```sh
agentoo kernel gen-efi-cmd --image /boot/EFI/Gentoo/kernel-RELEASE.efi
```

Review and execute the printed `sudo efibootmgr --create-only ...` command
separately (leaves `BootOrder`/`BootNext` unchanged; Startop automatically adds
`--full-dev-path`). Select the candidate from the firmware boot menu for first
boot. Verify the image signature against the enrolled db cert:

```sh
sudo sbverify --cert /var/lib/sbctl/keys/db/db.pem \
  /boot/EFI/Gentoo/kernel-RELEASE.efi
```

A valid signature does not prove firmware trust or hardware boot success—verify
release, passphrase retries, internal/USB keyboards, Btrfs `@`, discards,
microcode, systemd startup, networking, displays/audio, and suspend/resume while
keeping a working binary recovery entry.

## Updates and rebuilds

```sh
# Normal version update:
sudo emerge --ask --usepkg=n sys-kernel/gentoo-kernel
# Force rebuild after config, initramfs generator, cryptsetup, or firmware edits:
sudo emerge --ask --oneshot --usepkg=n '=sys-kernel/gentoo-kernel-VERSION'
```

Update `sys-kernel/agentoo-initramfs` and userspace archive inputs *before*
rebuilding: embedded archives and firmware require full recompilation
(`emerge --config` only reinstalls an existing build).

### Firmware and microcode updates

`linux-firmware` and `intel-microcode` use `-initramfs`. After any firmware,
microcode, or `agentoo kernel firmware apply` change, explicitly refresh both
boot artifacts (see [firmware guide](firmware.md)):

```sh
sudo emerge --config '=sys-kernel/gentoo-kernel-bin-VERSION'
sudo emerge --ask --oneshot --usepkg=n '=sys-kernel/gentoo-kernel-VERSION'
```

Do not use `kernel-install add-all` or `installkernel --all`.

## Configuration experiments

Edit `/etc/kernel/config.d/90-local.config` and force a source rebuild, then
inspect `/usr/src/linux-<release>/.config`. Promote accepted deltas into
tracked fragments and remove redundant local overrides (never prune other hosts'
built-in driver requirements).

For interactive `menuconfig` exploration against full sources:

```sh
sudo env PORTAGE_TMPDIR=/var/tmp/kernel-exp \
  ebuild /var/db/repos/gentoo/sys-kernel/gentoo-kernel/gentoo-kernel-VERSION.ebuild \
  unpack prepare configure

mkdir -p "$experiment"
cp "$resolved_config" "$experiment/.config"
cp "$experiment/.config" "$experiment/before.config"
make -C "$sources" O="$experiment" menuconfig   # or edit + olddefconfig
diff -u "$experiment/before.config" "$experiment/.config"
```

Promote only intentional deltas into `/etc/kernel/config.d/` (never generated
compiler metadata or temporary initramfs paths) and rebuild through Portage.

## Binary fallback

Managed independently through shared installkernel and dracut (`/etc/kernel/cmdline`):

```sh
sudo emerge --ask sys-kernel/gentoo-kernel-bin
sudo emerge --config '=sys-kernel/gentoo-kernel-bin-VERSION'
```

On Bequiet, register the binary fallback as console/network recovery with
`--args 'systemd.unit=multi-user.target systemd.mask=getty@tty1.service'`
(NVIDIA and desktop graphics are outside the recovery requirement).

## Bequiet modules and NVIDIA

Bequiet is the only host permitted to enable loadable modules, paired with
mandatory signing and `MODULE_SIG_FORCE=y` using its enrolled sbctl db key/cert.
NVIDIA loads after real-root handoff with its package-owned GSP firmware.

After building `gentoo-kernel` on Bequiet, verify resolved signing config and
matching certificate fingerprints:

```sh
release=6.18.62-agentoo-v0.5
rg '^CONFIG_(MODULES|MODULE_UNLOAD|MODULE_SIG|MODULE_SIG_ALL|MODULE_SIG_FORCE|MODULE_SIG_HASH|MODULE_SIG_KEY)=' \
  "/usr/src/linux-$release/.config"
openssl x509 -inform DER -in "/usr/src/linux-$release/certs/signing_key.x509" \
  -noout -fingerprint -sha256
sudo openssl x509 -in /var/lib/sbctl/keys/db/db.pem -noout -fingerprint -sha256
```

Require `MODULES`, `MODULE_UNLOAD`, `MODULE_SIG`, `MODULE_SIG_ALL`, and
`MODULE_SIG_FORCE` to be `y`, then confirm `eselect kernel show` points to the
candidate and rebuild NVIDIA before booting:

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

Note: `kmod` built without OpenSSL prints empty signer fields even on validly
signed modules; verify live enforcement via
`/sys/module/module/parameters/sig_enforce` and `nvidia-smi` after booting
under Secure Boot. Always run the NVIDIA rebuild above after same-version
custom kernel rebuilds (same-version rebuilds do not change
`virtual/dist-kernel`'s subslot).
