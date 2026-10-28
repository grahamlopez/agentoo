# Firmware maintenance

Thinktop and Flattop have reviewed native savedconfig lists at
`/etc/agentoo/firmware/thinktop.list` and `/etc/agentoo/firmware/flattop.list`.
Their host Portage fragments enable savedconfig; apply the matching list locally
before rebuilding. Other targets retain broad coverage.
SOF audio firmware, CPU microcode and wireless regulatory data belong to separate
packages and are not trimmed by this list. Installed files, initramfs copies and
firmware embedded in a custom kernel are separate maintenance concerns.

## Apply or revise the selection

After deploying the host policy and reviewed list, use:

```sh
agentoo kernel firmware
agentoo kernel firmware apply --dry-run
agentoo kernel firmware apply
```

The bare command is read-only and never requests sudo. It shows the selected
target host/kernel profile, host firmware list, effective and installed USE flags,
existing native savedconfigs in precedence order, differences from the durable
input and installed package paths, installed payload bytes, and the running
kernel's embedded names and microcode. Embedded names are configuration evidence,
not proof of every runtime load or firmware version. The printed journal command
helps investigate actual firmware loads; initramfs copies remain separate.

`apply` handles local onboarding and later list revisions. It requires a deployed
reviewed list and effective `savedconfig -deduplicate -compress-xz -compress-zstd`
policy for linux-firmware. It pins the currently installed package version and
requires its source ebuild; it does not choose an upgrade or enable host policy
implicitly. Run with other package/configuration operations idle.

After displaying the plan and confirming, it mounts `/boot` through its existing
mount configuration if initramfs policy requires it and runs a Portage pretend
before changing savedconfigs. It then creates a unique backup under
`/var/backups/agentoo/kernel-firmware/`, saves the previous durable input and the
reviewed host list, and moves overriding native inputs into the backup. It handles
the installed version/revision and native target/build triplet precedence, leaving
unrelated package-version snapshots and lower-priority inputs alone. It installs
the host list at `/etc/portage/savedconfig/sys-kernel/linux-firmware` with mode 0644,
then runs a source-only, oneshot rebuild with `--ignore-default-opts`,
`--usepkg=n` and `--getbinpkg=n`. This bypasses `EMERGE_DEFAULT_OPTS`, including
binary-only defaults, without passing negative `*pkgonly` options that some
Portage resolver paths interpret by their presence. Host USE policy still applies.

On success it compares the generated versioned snapshot and installed package
paths against the host list and reports installed payload bytes. Distribution
initramfs regeneration follows the effective `dist-kernel`/`initramfs` policy.
It does not rebuild the custom kernel, alter its embedded firmware, register EFI
entries or reboot. Repeat cold-boot and functional/suspend checks on both kernels.

`--dry-run` performs no changes, sudo requests or confirmation. `--yes` accepts
the displayed apply plan, but does not bypass sudo authentication; the existing
kernel command readiness prompt is used when credentials are needed. Help works
without Portage or sudo. Exit status is 0 for a successful report/apply/plan,
1 for an operational failure/cancellation and 2 for invalid arguments. A reported
status mismatch is information, not itself a command failure.

Failed/interrupted apply can leave updated savedconfigs or a partially merged
package. The backup path is printed; no automatic rollback hides that state.
Inspect `agentoo kernel firmware` and the Portage failure, then correct and retry
or use the broad-coverage recovery below. Configuration backups do not contain a
copy of the full firmware tree. Installer integration is separate: a new install
still needs an explicit apply after deployment. No hook runs on Git updates.

### Manual equivalent

After deploying the configuration, install the reviewed host list into Portage's
native savedconfig location. This example selects Flattop; use `thinktop.list`
on Thinktop. Host selection does not copy the list automatically.

```sh
sudo install -D -m 0644 /etc/agentoo/firmware/flattop.list /etc/portage/savedconfig/sys-kernel/linux-firmware
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

In other words, moving a snapshot aside is needed when changing the selection
and rebuilding the same version. Only move files that exist and match the
version being built; check triplet subdirectories too. Mount the normal boot
filesystems, then rebuild from source:

```sh
sudo emerge --pretend --verbose --oneshot --usepkg=n '=sys-kernel/linux-firmware-20260622'
sudo emerge --oneshot --usepkg=n '=sys-kernel/linux-firmware-20260622'
```

Use the appropriate version on later rebuilds. Check the build log's
`Building using saved configfile` path is the intended unversioned file, and
check successful distribution initramfs regeneration through `dist-kernel`.
Inspect the newly generated versioned savedconfig for the actual installed list.
No custom Portage hook or binary-package guard is installed; use source builds
when applying or updating the selection, and review missing/renamed firmware manually.

A new package version normally uses the unversioned input because an older
version's snapshot does not match. A rebuild of the same version prefers its
generated snapshot: move it aside again when revising the durable list. Neither
kernel needs rebuilding solely to trim installed files. Regenerate custom
initramfs copies if needed; rebuild the custom kernel when its embedded inputs
change.

## Flattop selection and Thinktop dock correction

The Flattop list targets the accepted 6.18.57 distribution/custom kernels and
linux-firmware-20260622. It retains ADLP graphics DMC/GuC, TGL HuC and their
advertised i915 fallbacks; all packaged AX211 so-a0-gf-a0 API alternatives and
PNVM, including root aliases; Intel Bluetooth 8087:0033 SFI/DDC; and
`rtl_nic/rtl8156b-2.fw` for the RTL8156 dock Ethernet documented on Thinktop.
The last entry preserves potential use of the shared monitor/KVM; no other
external firmware-dependent peripherals are assumed for Flattop.

The reviewed list has 34 paths (22 regular payloads, 12 symlinks), totaling
21,371,877 regular-file bytes versus 1,929,485,517 for the current broad package:
a projected 98.9% reduction. These are installed-input measurements and a
projection, not post-merge allocation or kernel/initramfs savings. Selected
regular-file checksums match Portage's installed VDB; symlink targets are
explicitly retained. The native installer has not yet been exercised with this
list. Inspect its resulting versioned savedconfig and test both boot paths.

Both accepted kernels use legacy HDA/IDT audio; no SOF firmware is selected.
The retained AVS driver alternative requests `intel/avs/adl/dsp_basefw.bin`,
which is absent even from this broad package. An AVS/SOF experiment needs a
separate firmware review; trimming does not establish that alternative's support.
UVC camera, keyboard/touchpad and the recorded USB fingerprint device establish
no additional linux-firmware requirement. Microcode and regulatory data remain
installed through their own packages, and the custom embedded selection stays
separate from this installed-file list.

Thinktop card 023 records a missing `rtl8156b-2.fw` request under v0.2/v0.3.
The tracked Thinktop list now includes that payload too. Its earlier 43-path
acceptance predates this correction: reapply the updated list and rebuild on
Thinktop. Check wired link speed, traffic, reconnect and resume. If a built-in
driver requests it before root becomes available, separately review early or
built-in firmware availability; changing savedconfig alone does not embed it.

## Routine maintenance

| Change | Operator action |
|---|---|
| Distribution kernel update | Update normally. Check firmware errors and hardware operation after booting it. If its drivers require new names, revise the host list and rebuild linux-firmware. |
| Custom kernel update | Follow the working kernel/initramfs build procedure. Review firmware requirements when changing drivers or kernel versions; the installed selection does not update the embedded list. |
| linux-firmware update | Review added/removed firmware names and relevant API versions. Update the explicit list as needed, reinstall it, check snapshot precedence, and build from source. New files are not selected automatically. |
| Host-list edit | Deploy and run `agentoo kernel firmware apply`, even if the package version is unchanged. It reinstalls the list, retires matching overrides and rebuilds from source. Regenerate custom artifacts if embedded inputs change. |
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
sudo env USE="-savedconfig" emerge --oneshot --usepkg=n '=sys-kernel/linux-firmware-20260622'
```

For persistent broad coverage, set `AGENTOO_LINUX_FIRMWARE_USE="-savedconfig"`
in the affected host's `/etc/portage/make.conf.d/90-<host>` and rebuild. Check distribution
initramfs regeneration and recreate affected custom artifacts. Keep a known
working boot path or installation media: the fallback kernel shares the same
root firmware directory.

See [configuration details](../../../../../etc/agentoo/README.md#installed-firmware-selection)
and [card 018](../kanban/Completed/018-host-firmware-savedconfig.md) for implementation,
validation evidence and explicitly deferred maintenance checks.
