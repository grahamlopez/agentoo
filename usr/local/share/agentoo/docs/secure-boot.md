# Initial Secure Boot signing and enrollment

Prepare a signed custom Agentoo kernel, retain the packaged Gentoo fallback and
Windows on another drive, then enable Secure Boot. Each keeps its own firmware
boot entry. This procedure uses sbctl's default file keys and direct EFI boot;
it does not change kernel command-line or lockdown policy.

Run Linux commands on the destination host as your normal user. Follow blocks
in order in the same shell; stop on any failed command. Firmware menu names
vary. Start with both Linux boot paths working and Secure Boot disabled.

## 1. Prepare Windows if present

Apply current Windows and applicable firmware updates first. Save the BitLocker
recovery key somewhere accessible without this PC. If BitLocker/device encryption
is enabled, run in administrator PowerShell before changing Secure Boot keys:

```powershell
Suspend-BitLocker -MountPoint "C:" -RebootCount 0
```

Expected: protection is suspended until explicitly resumed; the drive remains
encrypted. Keep Windows Boot Manager on its existing drive/ESP.

## 2. Install tools and preserve current trust

```sh
sudo emerge --ask app-crypt/sbctl app-crypt/sbsigntools
sudo sbctl status
sudo efibootmgr -v
sudo sbctl --disable-landlock export-enrolled-keys --dir /var/lib/sbctl/enrolled-before-esl --format esl
sudo sbctl --disable-landlock export-enrolled-keys --dir /var/lib/sbctl/enrolled-before-der --format der
```

Expected before key creation: `Installed: sbctl is not installed` is normal;
it refers to sbctl's local setup, not the installed executable. Setup Mode
should be disabled while the existing PK remains enrolled, and Secure Boot
disabled. Leave firmware settings unchanged at this stage. The two export
directories must not already exist. Save the boot-entry report and firmware
settings. DER exports supply certificates for reenrollment; ESL exports preserve
the original PK, KEK and db lists. If DER export warns about unsupported entries,
resolve their preservation before replacing trust. Do not clear the revocation
database (`dbx`).

The export commands disable sbctl's Landlock sandbox for those invocations only:
sbctl 0.16 otherwise tries to sandbox the output directory before creating it.
Do not pre-create the directories; export also rejects existing destinations.
Successful ESL export creates `PK.esl`, `KEK.esl` and `db.esl`; DER export creates
`PK`, `KEK` and `DB` subdirectories containing certificates.

Create keys once; reuse existing sbctl keys if already configured:

```sh
sudo sbctl create-keys
sudo sbctl status
sudo openssl x509 -in /var/lib/sbctl/keys/db/db.pem -noout -subject -fingerprint -sha256
```

Expected: key creation succeeds, status reports sbctl installed with an Owner
GUID, and the certificate fingerprint prints. Creating keys does not enroll
them: Setup Mode and Secure Boot remain unchanged. Back up
`/var/lib/sbctl` to secure offline storage before continuing; it contains private
keys. Use your mounted backup destination below, replacing the example path:

```sh
backup_dir=/path/to/mounted/secure-backup
sudo test -d "$backup_dir"
sudo bash -eu -c 'umask 077; set -C; tar -C /var/lib -cz sbctl > "$1"' \
  bash "$backup_dir/sbctl-before-enrollment.tar.gz"
sudo tar -tzf "$backup_dir/sbctl-before-enrollment.tar.gz"
```

Expected: the archive lists the keys and exported trust. Choose a fresh archive
filename for another backup; do not overwrite your only previous backup.

## 3. Sign a separate copy of the current custom kernel

Boot your working custom kernel first. Confirm `uname -r` is its release, not
`*-gentoo-dist-bin`. These commands preserve the original image:

```sh
custom_release=$(uname -r)
custom_source="/boot/EFI/Gentoo/kernel-$custom_release.efi"
custom_signed="/boot/EFI/Gentoo/kernel-$custom_release-signed.efi"
(
set -eu
mountpoint -q /boot || sudo mount /boot
test -s "$custom_source"
test ! -e "$custom_signed"
sudo sbsign --key /var/lib/sbctl/keys/db/db.key \
  --cert /var/lib/sbctl/keys/db/db.pem \
  --output "$custom_signed" "$custom_source"
sudo chmod 0644 "$custom_signed"
sudo sbverify --cert /var/lib/sbctl/keys/db/db.pem "$custom_signed"
agentoo kernel gen-efi-cmd --image "$custom_signed" --label 'Agentoo signed'
)
```

Expected: `Signature verification OK`, followed by an EFI registration command.
Run the printed command, replacing `--create` with `--create-only` to retain
BootOrder. Select the new entry from the firmware boot menu and test root unlock
and normal startup while Secure Boot is still disabled. Keep the original entry.
If the signed path already exists, inspect it rather than overwriting it blindly.

## 4. Verify the fallback and stage certificates

Test the existing fallback entry, including its external initramfs and command
line, before running the following blocks. No UKI conversion or local fallback
signing is needed.

Choose the installed fallback release explicitly; replace this example if needed:

```sh
dist_release=6.18.57-gentoo-dist-bin
dist_cert="/usr/src/linux-$dist_release/certs/signing_key.x509"
dist_image="/boot/EFI/Gentoo/kernel-$dist_release.efi"
(
set -eu
test -s "$dist_cert"
test -s "$dist_image"
test -s "/boot/EFI/Gentoo/initramfs-$dist_release.img"
openssl x509 -inform DER -in "$dist_cert" -noout -subject -fingerprint -sha256
dist_pem=$(mktemp)
trap 'rm -f -- "$dist_pem"' EXIT
openssl x509 -inform DER -in "$dist_cert" -out "$dist_pem"
sbverify --cert "$dist_pem" "$dist_image"
)
```

Expected: Gentoo's distribution signing identity and `Signature verification OK`.
Use the certificate from the trusted installed package, not an unrelated download.

Stage Gentoo's certificate and preserve the current db/KEK certificates, including
Windows certificates added by updates that firmware defaults may lack:

```sh
sudo install -d /var/lib/sbctl/keys/custom/db /var/lib/sbctl/keys/custom/KEK
sudo install -m 0644 "$dist_cert" \
  "/var/lib/sbctl/keys/custom/db/gentoo-$dist_release.der"
sudo bash -eu <<'SH'
for cert in /var/lib/sbctl/enrolled-before-der/DB/*.der; do
    install -m 0644 "$cert" /var/lib/sbctl/keys/custom/db/
done
for cert in /var/lib/sbctl/enrolled-before-der/KEK/*.der; do
    install -m 0644 "$cert" /var/lib/sbctl/keys/custom/KEK/
done
SH
```

Expected: both loops succeed. sbctl's custom certificate directories take DER
certificates. Back up `/var/lib/sbctl` again using a new archive name.

## 5. Enroll and enable Secure Boot

```sh
sudo systemctl reboot --firmware-setup
```

Perform these steps in the firmware interface; Linux commands cannot select
these menus for you:

| Firmware control | Before enrollment | Final state |
| --- | --- | --- |
| Secure Boot | Disabled during image preparation/testing. Some firmware requires the toggle enabled when removing PK to allow enrollment. | Enabled, with verification active. |
| Key management / Standard / Custom | Open key management; select Custom only if required to expose key editing. | Retain the enrolled keys; the required menu label varies by firmware. |
| Platform Key (PK) | Remove PK to enter Setup Mode, preserving KEK/db/dbx where supported. | Your PK enrolled by sbctl; Setup Mode disabled. |
| Restore factory/default keys | Do not select during this procedure. | Do not select: it would replace the added trust. |

**Setup Mode is the absence of an enrolled PK**, not necessarily a menu toggle.
Disabling Secure Boot alone does not enter it. A firmware setting named Custom
does not prove either Setup Mode or active verification; on some firmware it
only disables verification. Follow the machine's key-management controls rather
than assuming Custom must be enabled throughout. Do not switch back to Standard
if that action restores factory keys.

### Flattop firmware menu

Verified on Flattop, Framework Laptop 13 (13th Gen Intel Core), Insyde BIOS
03.16, on 2026-11-09:

1. Press **F2** during startup and open **Administer Secure Boot**.
2. Open **PK Options → Delete PK**, select the existing certificate, and
   confirm **Delete this signature**. Use Delete, not Enroll: Enroll opens a
   file chooser and is not needed for this step.
3. Leave KEK, DB and DBX intact. Do not use **Erase all Secure Boot Settings**
   or restore factory keys.
4. Press **F10** to save and exit, then boot the tested signed Agentoo entry.

The resulting `sudo sbctl status` reported **Setup Mode: Enabled** and
**Secure Boot: Disabled**, with vendor keys `microsoft builtin-db builtin-KEK`.
sbctl displays a cross beside Setup Mode Enabled; that is the expected state
for enrollment, not a failure. The two **Add UEFI CA 2023** and
**Add UEFI CA Option ROM 2023** options had also been enabled; those additions
alone did not enter Setup Mode. **Select a UEFI file as trusted for execution**
was not used. This confirms entry into Setup Mode; enrollment and enforced
Secure Boot acceptance are separate steps below.

### Enroll the prepared certificates

Save changes and boot the tested signed Agentoo entry. Then run:

```sh
sudo sbctl status
```

Expected: **Setup Mode enabled**. Before enrollment, ensure all required current
certificates were staged above. This command replaces PK/KEK/db with your keys
plus staged, Microsoft and firmware-default certificates:

```sh
sudo sbctl enroll-keys --microsoft --firmware-builtin --custom
sudo sbctl list-enrolled-keys
sudo sbctl status
```

If enrollment reports immutable KEK/db files (observed on Flattop after deleting
only PK), retry with sbctl's scoped immutable-attribute handling:

```sh
sudo sbctl enroll-keys --microsoft --firmware-builtin --custom --ignore-immutable
sudo sbctl list-enrolled-keys
sudo sbctl status
```

This allows sbctl to clear the Linux immutable attributes before writing its
enrollment variables. It does not bypass the option-ROM safety checks. Do not
clear immutable flags across all of efivarfs or delete the retained databases.

Expected: enrollment succeeds, Setup Mode becomes disabled, and the enrolled
list includes your db certificate, Gentoo's certificate and retained Windows
trust. Compare their SHA256 fingerprints with those recorded earlier. Stop on
an option-ROM safety error; do not use force/bypass flags. Some firmware begins
enforcing immediately after enrollment, so the tested signed entry must exist
before this step.

Return to firmware and enable Secure Boot if necessary, retaining custom keys.
Do not restore factory keys afterward: that would remove the added trust.
The acceptance criteria are Secure Boot enabled and Setup Mode disabled in
`sbctl status`, followed by successful boots of all required entries. Exact
firmware menu labels require the motherboard/laptop model and firmware version.

## 6. Verify all boot paths

Boot the signed custom entry and the existing Gentoo fallback entry separately.
On each boot:

```sh
sudo sbctl status
uname -r
findmnt /
```

Expected: **Secure Boot enabled**, **Setup Mode disabled**, the selected release,
and the normal root filesystem. A signature check alone does not prove firmware
acceptance. `sbctl verify` checks your own signing key; it is not the acceptance
test for the separately trusted Gentoo or Windows signatures.

Boot Windows from its firmware entry. In administrator PowerShell:

```powershell
Confirm-SecureBootUEFI
Resume-BitLocker -MountPoint "C:"
Get-BitLockerVolume -MountPoint "C:"
```

Expected: `True` and BitLocker protection on, if BitLocker was suspended. Reboot
Windows once more to confirm normal unlock. If a boot path is rejected, disable
Secure Boot in firmware while retaining keys, boot a working entry, and inspect
the image signature and enrolled trust before retrying. Do not clear the TPM.

## Later updates

`agentoo kernel install --label LABEL` signs automatically and fails if it
cannot sign/verify, using the standard sbctl file key and certificate prepared
above. The workspace's unsigned build image stays unchanged. `--unsigned`
explicitly bypasses signing; such images normally cannot boot with Secure Boot
enabled. See [kernel installation](kernel.md#install) for replacement and backup
behavior. Existing workspaces can be installed without rebuilding just to sign.

Portage/installkernel/dracut continue maintaining the fallback. Verify each new
fallback against its packaged certificate; if its fingerprint changes, enroll
the new certificate before relying on that entry. Windows retains Microsoft's
signatures and its separate drive/boot entry. Firmware resets or factory-key
restoration can require reenrolling Agentoo/Gentoo trust.

References: [sbctl commands](https://github.com/Foxboron/sbctl/blob/master/docs/sbctl.8.txt),
[custom certificate format](https://github.com/Foxboron/sbctl/blob/master/certs/certs.go),
[Gentoo kernel packaging](https://github.com/gentoo/gentoo/blob/master/sys-kernel/gentoo-kernel-bin/gentoo-kernel-bin-6.18.57.ebuild),
[BitLocker suspension](https://learn.microsoft.com/en-us/troubleshoot/windows-client/windows-security/suspend-bitlocker-protection-non-microsoft-updates),
[Windows certificate updates](https://learn.microsoft.com/en-us/troubleshoot/windows-client/windows-security/update-secure-boot-certificates).
