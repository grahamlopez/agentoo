# Migrate remaining hosts from gentoo-sources to native gentoo-kernel

Created: 2026-11-20
Status: Open

## Fleet checklist

- [x] `thinktop` (converted; see completed card 051)
- [x] `bequiet` (converted; see [hosts/bequiet.md](../../docs/hosts/bequiet.md))
- [ ] `flattop`
- [ ] `startop`

Delete this card once every existing host has migrated; new installations
establish these local inputs automatically in `gentoo-install.sh`.

## Migration steps

Run the sequence below on each remaining target host itself. Step 2 requires
that host's own storage values; do not reuse another host's identifiers.

### 1. Deploy configuration and shared policy

```sh
sudo agentoo git pull
sudo systemd-tmpfiles --create agentoo-kernel.conf

target_host=$(python3 -B /usr/local/share/agentoo/lib/host_selection.py)
printf 'Selected host: %s\n' "$target_host"
```

Confirm this prints `flattop` or `startop`, as appropriate.

### 2. Establish local kernel inputs

Inspect the root mapping, encrypted partition, and ESP:

```sh
findmnt -n -o SOURCE,FSTYPE,FSROOT --target /
lsblk -o NAME,TYPE,FSTYPE,PARTUUID,TRAN
findmnt -n -o SOURCE,FSTYPE,UUID --mountpoint /boot
```

Edit the native environment file:

```sh
sudoedit /etc/portage/env/kernel-local
```

Enter these settings, substituting the values from that host's inventory:

```sh
AGENTOO_INITRAMFS_PARTUUID=ENCRYPTED_PARTITION_PARTUUID
AGENTOO_INITRAMFS_MAPPER=ROOT_MAPPING_NAME
AGENTOO_INITRAMFS_TRANSPORT=nvme
```

Use the partition's PARTUUID, and the mapping name without `/dev/mapper/`.
Flattop previously used `crypt_root`; confirm its current value. Use `sata`
instead of `nvme` if the root disk's transport is SATA.

Then activate the host fragment and record the mounted ESP's filesystem UUID:

```sh
sudo chmod 0644 /etc/portage/env/kernel-local

sudo ln -sfnT \
  "/etc/agentoo/kernel/hosts/$target_host.config" \
  /etc/kernel/config.d/20-host.config

findmnt -n -o UUID --mountpoint /boot
sudoedit /etc/kernel/gentoo-dist-esp.uuid
sudo chmod 0644 /etc/kernel/gentoo-dist-esp.uuid
```

The ESP file should contain only the UUID printed immediately above.

Review any existing local kernel overrides before building:

```sh
ls -l /etc/kernel/config.d
rg -n 'CONFIG_(LOCALVERSION|INITRAMFS_SOURCE|CMDLINE)' /etc/kernel/config.d
```

Remove obsolete local overrides deliberately; the intended shared localversion
is `-agentoo-v0.5`.

### 3. Install prerequisites and apply firmware policy

Keep the currently installed firmware versions while applying the USE changes:

```sh
firmware_atom=$(portageq best_version / sys-kernel/linux-firmware)
microcode_atom=$(portageq best_version / sys-firmware/intel-microcode)

sudo emerge --ask --oneshot --newuse --usepkg=n "=$firmware_atom"
if [ -n "$microcode_atom" ]; then
  sudo emerge --ask --oneshot --newuse --usepkg=n "=$microcode_atom"
fi

sudo emerge --ask --oneshot --usepkg=n sys-kernel/agentoo-initramfs
sudo emerge --ask --noreplace sys-fs/dosfstools
sudo systemctl daemon-reload
```

Preserve the existing firmware savedconfig selection. Flattop firmware trimming
can remain separate.

### 4. Refresh the fallback, build, and validate

Refresh whichever binary fallback version is installed on that host:

```sh
fallback_atom=$(portageq best_version / sys-kernel/gentoo-kernel-bin)
sudo emerge --config "=$fallback_atom"
```

Build the source kernel:

```sh
sudo emerge --ask --oneshot --usepkg=n \
  '=sys-kernel/gentoo-kernel-6.18.62'
```

Check the result:

```sh
eselect kernel show
modinfo -k 6.18.62-agentoo-v0.5 i2c-dev

sudo sbverify --cert /var/lib/sbctl/keys/db/db.pem \
  /boot/EFI/Gentoo/kernel-6.18.62-agentoo-v0.5.efi

agentoo kernel gen-efi-cmd \
  --image /boot/EFI/Gentoo/kernel-6.18.62-agentoo-v0.5.efi
```

Review and execute the printed EFI command. On Startop, confirm it includes
`--full-dev-path`.

Boot the custom kernel through the firmware menu, test the host's hardware and
suspend/resume, then independently boot-test the refreshed binary fallback.
Stop at any failed command and investigate before switching defaults.
