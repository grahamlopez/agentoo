# Firmware maintenance

Thinktop retains selected `linux-firmware` files using
`/etc/agentoo/firmware/thinktop.list`. Other targets retain broad coverage.
SOF audio firmware, CPU microcode and wireless regulatory data belong to separate
packages and are not trimmed by this list. Installed files, initramfs copies and
firmware embedded in a custom kernel are separate maintenance concerns.

## Apply or revise the selection

After deploying the configuration, install the reviewed host list into Portage's
native savedconfig location:

```sh
sudo install -D -m 0644 /etc/agentoo/firmware/thinktop.list /etc/portage/savedconfig/sys-kernel/linux-firmware
sudo find /etc/portage/savedconfig -name 'linux-firmware*' -print
```

Gentoo searches matching version-and-revision (`PF`), version (`P`), then
unversioned (`PN`) names. At each level, target-triplet and build-triplet
locations precede the plain category location. **Move matching higher-priority
files aside** before applying a revised list. Initially, the existing
`sys-kernel/linux-firmware-20260622` is one such file. For example:

```sh
sudo mkdir -p /root/firmware-savedconfig-backup
sudo mv /etc/portage/savedconfig/sys-kernel/linux-firmware-20260622 /root/firmware-savedconfig-backup/
```

Only move files that exist and match the version being built; check triplet
subdirectories too. Mount the normal boot filesystems, then rebuild from source:

```sh
sudo emerge --pretend --verbose --oneshot --usepkg=n =sys-kernel/linux-firmware-20260622
sudo emerge --oneshot --usepkg=n =sys-kernel/linux-firmware-20260622
```

Use the appropriate version on later rebuilds. Check the build log's
`Building using saved configfile` path is the intended unversioned file, and
check successful distribution initramfs regeneration through `dist-kernel`.
Inspect the newly generated versioned savedconfig for the actual installed list.
There is no custom validation or binary-package guard; use source builds when
applying or updating the selection, and review missing/renamed firmware manually.

A new package version normally uses the unversioned input because an older
version's snapshot does not match. A rebuild of the same version prefers its
generated snapshot: move it aside again when revising the durable list. Neither
kernel needs rebuilding solely to trim installed files. Regenerate custom
initramfs copies if needed; rebuild the custom kernel when its embedded inputs
change.

## Routine maintenance

| Change | Operator action |
|---|---|
| Distribution kernel update | Update normally. Check firmware errors and hardware operation after booting it. If its drivers require new names, revise the host list and rebuild linux-firmware. |
| Custom kernel update | Follow the working kernel/initramfs build procedure. Review firmware requirements when changing drivers or kernel versions; the installed selection does not update the embedded list. |
| linux-firmware update | Review added/removed firmware names and relevant API versions. Update the explicit list as needed, reinstall it, check snapshot precedence, and build from source. New files are not selected automatically. |
| Host-list edit | Reinstall the list, move aside matching higher-priority snapshots, and rebuild linux-firmware even if its version is unchanged. Regenerate custom artifacts if embedded inputs change. |
| New hardware or driver | Review firmware requirements first; restore broad coverage while investigating if necessary. |

After a selection change, test a cold boot of both custom and distribution
recovery kernels, suspend/resume, graphics, Wi-Fi, Bluetooth, audio and relevant
NPU/peripheral workflows. Existing embedded firmware, initramfs copies and device
caches can conceal missing installed files. A passing build does not establish
hardware coverage.

## Find requirements and diagnose errors

Identify hardware IDs and bound drivers, including attached peripherals:

```sh
lspci -nnk
lsusb
sudo journalctl -k -b --no-pager | rg -i 'firmware|iwlwifi|bluetooth|sof|i915|xe|ivpu|nouveau'
```

Repeat the log check after exercising the affected device and after resume.
Use `-b -1` instead of `-b` to inspect the previous boot when comparing kernels.
Look for failed/direct firmware loads, missing files, timeouts and the subsequent
success or failure of device initialization. A failed request followed by a
successful fallback is not by itself evidence of broken functionality.

For a driver, inspect its advertised firmware names (replace the placeholders):

```sh
modinfo -k KERNEL_RELEASE -F firmware DRIVER
zcat /proc/config.gz | rg '^CONFIG_EXTRA_FIRMWARE='
```

`KERNEL_RELEASE` is the release under `/lib/modules`, including the distribution
fallback. Module metadata may be unavailable for custom built-in drivers; check
the matching kernel source for `MODULE_FIRMWARE` and firmware request/fallback
names. The second command shows what the running kernel embeds.

Combine driver metadata/source, hardware IDs and successful loads; neither logs
nor `modinfo` alone provide an exact complete selection. Compare both kernel
versions, retain matching API alternatives and PNVM/configuration files, and
identify the owning package before editing the host list. In linux-firmware's
source, `WHENCE` records names and symlink dependencies. Record explicit paths with a short
hardware rationale, retaining required aliases and shared targets. Gentoo's
installer handles its supported symlink dependencies; inspect the resulting
savedconfig rather than assuming every requested file was retained.

## Restore broad coverage

For a one-time recovery rebuild, use the applicable package version:

```sh
sudo env USE="-savedconfig" emerge --oneshot --usepkg=n =sys-kernel/linux-firmware-20260622
```

For persistent broad coverage, set `AGENTOO_LINUX_FIRMWARE_USE="-savedconfig"`
in `/etc/portage/make.conf.d/90-thinktop` and rebuild. Check distribution
initramfs regeneration and recreate affected custom artifacts. Keep a known
working boot path or installation media: the fallback kernel shares the same
root firmware directory.

See [configuration details](../../../../../etc/agentoo/README.md#installed-firmware-selection)
and [card 018](../kanban/Open/018-host-firmware-savedconfig.md) for implementation,
validation evidence and remaining live acceptance work.
