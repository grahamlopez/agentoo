<!--
This is a production-install runbook for installing Gentoo into a QEMU qcow2
target through NBD.  It must invoke usr/local/share/agentoo/installer/gentoo-install.sh exactly as a
real installation from the current Linux host would invoke it.  Do not add
alternate modes, trust inputs, mocks, or special installer settings here:
running these instructions is the production path.
-->

# QEMU NBD Gentoo install

## Optional binary packages during installation

Add `--install-binpkgs` to installer invocations to prefer signed binary
packages from Gentoo's official binhost. USE flags are respected throughout;
packages without matching binaries compile normally. When running individual
phases, repeat the option on system-update, kernel-foundation, and
first-boot-foundation. The option is not remembered between invocations.

The configuration repository leaves the binhost configured for later explicit
`emerge --getbinpkg` use, but does not enable binary packages in `FEATURES` or
`EMERGE_DEFAULT_OPTS`. Ordinary post-install package operations build from source.
The existing prebuilt distribution kernel is used in either installation mode.

## Default host-backed RAM builds

Installer package builds use host-visible `/dev/shm` by default, including
chroot updates and resumed phases. Use `--no-ram-builds` to select `/var/tmp` for an
invocation when memory is insufficient; it reaches child phases too. This does
not persist in QEMU's make.conf; the booted guest uses normal disk-backed
storage. Host memory and the mounted tmpfs limit constrain builds. Physical
hosts may keep their explicit machine-specific build-storage policy.

## Host tools

```bash
sudo pacman -S --needed qemu-base virt-firmware jq python psmisc btrfs-progs cryptsetup curl dosfstools git gnupg
```

## Set up this install shell

Paste this once into the terminal that will run the install commands:

```bash
INSTALL_DIR=/home/graham/VMs/agentic-gentoo
IMAGE=$INSTALL_DIR/target.qcow2
NBD_DEVICE=/dev/nbd0
CONFIG_SOURCE=/home/graham/Projects/agentoo
CONFIG_BRANCH=main

detach_target() {
  local nbd_pid_file=/sys/block/${NBD_DEVICE##*/}/pid
  local nbd_pid
  local attempt

  if mountpoint -q /mnt/gentoo/run; then sudo umount --recursive /mnt/gentoo/run; fi
  if mountpoint -q /mnt/gentoo/dev; then sudo umount --recursive /mnt/gentoo/dev; fi
  if mountpoint -q /mnt/gentoo/sys; then sudo umount --recursive /mnt/gentoo/sys; fi
  if mountpoint -q /mnt/gentoo/proc; then sudo umount --recursive /mnt/gentoo/proc; fi
  if mountpoint -q /mnt/gentoo/boot; then sudo umount /mnt/gentoo/boot; fi
  if mountpoint -q /mnt/gentoo/home; then sudo umount /mnt/gentoo/home; fi
  if mountpoint -q /mnt/gentoo; then sudo umount /mnt/gentoo; fi
  if sudo cryptsetup status cryptroot >/dev/null 2>&1; then sudo cryptsetup close cryptroot; fi
  if [[ -r $nbd_pid_file ]]; then
    nbd_pid=$(<"$nbd_pid_file")
    if [[ -n $nbd_pid && $nbd_pid != 0 ]]; then
      sudo qemu-nbd --disconnect "$NBD_DEVICE"
      for attempt in {1..50}; do
        [[ ! -r $nbd_pid_file ]] && break
        nbd_pid=$(<"$nbd_pid_file")
        [[ -z $nbd_pid || $nbd_pid == 0 ]] && break
        sleep 0.1
      done
      [[ ! -r $nbd_pid_file || -z $nbd_pid || $nbd_pid == 0 ]] || {
        printf 'NBD device did not finish disconnecting: %s\n' "$NBD_DEVICE" >&2
        return 1
      }
      for attempt in {1..50}; do
        qemu-img info "$IMAGE" >/dev/null 2>&1 && break
        sleep 0.1
      done
      qemu-img info "$IMAGE" >/dev/null 2>&1 || {
        printf 'Image write lock was not released: %s\n' "$IMAGE" >&2
        return 1
      }
    fi
  fi
}

attach_target() {
  local size_file=/sys/block/${NBD_DEVICE##*/}/size
  local attempt

  sudo qemu-nbd --format=qcow2 --connect="$NBD_DEVICE" "$IMAGE"
  for attempt in {1..50}; do
    [[ $(<"$size_file") != 0 ]] && break
    sleep 0.1
  done
  [[ $(<"$size_file") != 0 ]] || {
    printf 'NBD device did not report a capacity: %s\n' "$NBD_DEVICE" >&2
    return 1
  }
  sudo udevadm settle
  lsblk --paths --output NAME,SIZE,TYPE,FSTYPE,LABEL,MOUNTPOINTS "$NBD_DEVICE"
}
```

## First setup: create and attach a fresh target

```bash
mkdir -p "$INSTALL_DIR"
qemu-img create -f qcow2 "$IMAGE" 100G
sudo modprobe nbd nbds_max=8 max_part=16
attach_target
```

## Run the installer against the attached target

For a fresh installation, `--qemu-vars` names the new persistent firmware file
you want the installer to create; you do not need to obtain that file first.
The commands below place it at `$INSTALL_DIR/OVMF_VARS.4m.fd`. The installer
creates it from `/usr/share/edk2/x64/OVMF_VARS.4m.fd`, installed by the host's
OVMF/EDK2 firmware package. Create `$INSTALL_DIR` first, as in the setup above.
If your distribution stores the template elsewhere, pass `--qemu-vars-template`
with that path and use its matching OVMF CODE file when launching the VM.
Keep the generated VARS file: it holds the boot entry and must be reused by QEMU.

```bash
cd /home/graham/Projects/agentoo
./usr/local/share/agentoo/installer/gentoo-install.sh --disk "$NBD_DEVICE" \
  --config-source "$CONFIG_SOURCE" --config-branch "$CONFIG_BRANCH" \
  --target-host qemu --qemu-vars "$INSTALL_DIR/OVMF_VARS.4m.fd" --dry-run --verbose
./usr/local/share/agentoo/installer/gentoo-install.sh --disk "$NBD_DEVICE" \
  --config-source "$CONFIG_SOURCE" --config-branch "$CONFIG_BRANCH" \
  --target-host qemu --qemu-vars "$INSTALL_DIR/OVMF_VARS.4m.fd" --verbose

```

The default run finishes with `handoff`: it unmounts the target and closes LUKS.
After successful completion, proceed to detachment and boot testing below.
The phase-resume instructions below apply when installation stopped before
handoff and the target is still mounted.

The default installer now also runs `system-update`. CPU detection occurs on
the installation host; the VM boot command below uses `-cpu host` to expose
those same features. Configuration updates are reviewed interactively with
`dispatch-conf`, including when `--yes` is used. Compilation settings come from
the existing configuration repository.

If the update fails, the target remains mounted. Resume only that phase:

```bash
./usr/local/share/agentoo/installer/gentoo-install.sh --disk "$NBD_DEVICE" \
  --target-host qemu --phase system-update --verbose
sudo chroot /mnt/gentoo agentoo-git diff
sudo chroot /mnt/gentoo agentoo-permissions --check
sudo chroot /mnt/gentoo cat /etc/portage/package.use/00cpu-flags
```

## Prepare the distribution kernel

The default installer also runs `kernel-foundation`. To resume only that phase
on the existing mounted target:

```bash
./usr/local/share/agentoo/installer/gentoo-install.sh --disk "$NBD_DEVICE" \
  --target-host qemu --phase kernel-foundation \
  --qemu-vars "$INSTALL_DIR/OVMF_VARS.4m.fd" --dry-run --verbose
./usr/local/share/agentoo/installer/gentoo-install.sh --disk "$NBD_DEVICE" \
  --target-host qemu --phase kernel-foundation \
  --qemu-vars "$INSTALL_DIR/OVMF_VARS.4m.fd" --verbose
sudo chroot /mnt/gentoo cat /etc/kernel/cmdline
sudo ls -lh /mnt/gentoo/boot/EFI/Gentoo/
virt-fw-vars --input "$INSTALL_DIR/OVMF_VARS.4m.fd" --print
```

Use the installer's `--verbose` output for phase details. Save the printed kernel
version and command line for the later VM boot test.

Stop the VM before running this phase. It creates or updates the specified
OVMF store offline; use that same file in the QEMU command below. The default
template matches the CODE file shown below; for another OVMF build, supply
`--qemu-vars-template` with its matching VARS template. Detach NBD before
starting QEMU. Run first-boot configuration below before boot testing.

## Configure first boot

The default installer includes `first-boot-foundation`. For a previously
prepared target, resume it separately:

```bash
./usr/local/share/agentoo/installer/gentoo-install.sh --disk "$NBD_DEVICE" \
  --target-host qemu --hostname gentoo-vm --phase first-boot-foundation --dry-run --verbose
./usr/local/share/agentoo/installer/gentoo-install.sh --disk "$NBD_DEVICE" \
  --target-host qemu --hostname gentoo-vm --phase first-boot-foundation --verbose
```

Enter your host administrator password if sudo asks for it. When the installer
asks you to create the Gentoo root login password, enter your chosen new guest
password twice. This phase also installs Zsh and makes it root's login shell,
using Agentoo's shared configuration with a red hostname in root's prompt.
If you resumed first-boot configuration separately, run handoff
before detachment:

```bash
./usr/local/share/agentoo/installer/gentoo-install.sh --disk "$NBD_DEVICE" \
  --target-host qemu --qemu-vars "$INSTALL_DIR/OVMF_VARS.4m.fd" --phase handoff
```

## Detach and preserve the target for later work

```bash
detach_target
```

## Start over with a fresh target, if needed

```bash
detach_target
# A fresh disk gets a new ESP GUID. Archive its old firmware store as well.
if [[ -e "$INSTALL_DIR/OVMF_VARS.4m.fd" ]]; then
  mv "$INSTALL_DIR/OVMF_VARS.4m.fd" "$INSTALL_DIR/OVMF_VARS.4m.fd.previous-$(date +%Y%m%d-%H%M%S)"
fi
rm -f "$IMAGE"
qemu-img create -f qcow2 "$IMAGE" 100G
attach_target
```

## Boot after first-boot configuration

```bash
# Use the persistent store prepared by kernel-foundation; do not reinitialize it.
if [[ -f "$INSTALL_DIR/OVMF_VARS.4m.fd" ]]; then
  qemu-system-x86_64 \
    -enable-kvm \
    -machine q35 \
    -cpu host \
    -m 4096 \
    -smp 4 \
    -nic user,model=virtio-net-pci,hostfwd=tcp:127.0.0.1:2222-:22 \
    -display none -serial mon:stdio \
    -drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd \
    -drive if=pflash,format=raw,file="$INSTALL_DIR/OVMF_VARS.4m.fd" \
    -drive if=virtio,format=qcow2,file="$IMAGE"
else
  printf 'Run kernel-foundation to prepare the VM firmware store first.\n'
fi
```

Enter the disk-encryption passphrase at the unlock prompt, then log in as
`root` using the guest root password set during first-boot configuration.
Use Ctrl-a c to switch between the serial console and QEMU monitor.

### SSH from the host

The boot command forwards host `127.0.0.1:2222` to guest TCP port 22. The
forward is accessible only from the host. Relaunch QEMU with the updated command
if the VM was started without it; a guest reboot alone does not add the forward.

After unlocking the disk, use the guest serial console to install and enable
the SSH server, if needed:

```bash
emerge --ask net-misc/openssh
systemctl enable --now sshd
```

From a host terminal, connect using a guest account authorized for SSH:

```bash
ssh -p 2222 guest-user@127.0.0.1
```

Replace `guest-user` with your guest username. For `root`, configure an authorized
SSH key in the guest's `/root/.ssh/authorized_keys`; the guest root password set
by the installer does not by itself guarantee SSH login is permitted. Keep the
serial console available for disk unlocking and SSH setup.

## Verify and checkpoint the running guest

After logging in as root, run:

```bash
/root/001-firstboot-verify-and-checkpoint.sh
```

For diagnostics without creating or offering another checkpoint, run:

```bash
/root/001-firstboot-verify-and-checkpoint.sh --verify-only
```

Keep package operations and configuration automation idle throughout capture.
Snapshots are taken live and sequentially, not atomically across subvolumes.
No shutdown or installer-host involvement is needed for checkpoint creation.
QEMU firmware-file backup is optional and outside this guest helper. A restore
requires a controlled reboot/recovery procedure; do not replace the running root.
For on-demand capture and offline recovery, see
/usr/local/share/agentoo/docs/checkpoints.md. There is no scheduled checkpointing.

After verification/checkpointing, run `/root/002-agentoo-setup-user.sh` to create
Graham’s account with password-required sudo and an optional SSH login key.

Run these commands in the guest root console:

```bash
findmnt --target /
findmnt --target /home
findmnt --target /boot
systemctl --failed --no-pager
ip address
getent hosts gentoo.org
curl --head --fail --max-time 20 https://www.gentoo.org/
systemctl is-active dhcpcd systemd-timesyncd
timedatectl status
timedatectl timesync-status
systemctl list-timers gentoo-btrfs-scrub.timer --no-pager
systemctl start gentoo-btrfs-scrub.service
btrfs scrub status /
journalctl --list-boots --no-pager
```

For a reboot check, note the printed machine ID and write a journal message:

```bash
cat /etc/machine-id
logger -t install-check "Journal persistence check before reboot"
reboot
```

Unlock the disk and log in as root again, then run:

```bash
cat /etc/machine-id
journalctl --list-boots --no-pager
journalctl -b -1 -t install-check --no-pager
```

Confirm that the machine ID matches the previous output, both boots are listed,
and the previous boot's tagged message is readable.

## Distribution kernel updates and manual physical registration

The distribution fallback uses stable `gentoo-kernel-bin`, the tracked kernel
policy, and Gentoo's packaged generation/copy tools. After updating it, register
the new version manually on physical hardware and retain a tested previous
entry. Custom source images must use separate names/paths and must not modify
this fallback pipeline. Automatic offline QEMU registration remains part of
initial guest creation; native registration during later kernel updates is deferred.

On the booted target, identify the release and ESP:

```bash
ATOM=$(portageq best_version / sys-kernel/gentoo-kernel-bin)
awk '$1 == "obj" && $2 ~ /\/include\/config\/kernel.release$/ {print $2}' "/var/db/pkg/$ATOM/CONTENTS"
findmnt --mountpoint /boot -o SOURCE,UUID,FSTYPE
lsblk -o NAME,PKNAME,PARTN,UUID
cat /etc/kernel/cmdline
```

Read the `kernel.release` associated with the installed distribution fallback.
Replace the values below with that release and the ESP's actual parent disk and
partition number. `/etc/kernel/gentoo-dist.version` is installation history and
must not supply the version for later updates.

```bash
VERSION=REPLACE_WITH_DISTRIBUTION_RELEASE
DISK=/dev/REPLACE_WITH_ESP_PARENT_DISK
PART=1
sudo efibootmgr --verbose
sudo efibootmgr --create-only --disk "$DISK" --part "$PART" \
  --label "Gentoo distribution $VERSION" \
  --loader "\\EFI\\Gentoo\\kernel-$VERSION.efi" \
  --unicode "$(cat /etc/kernel/cmdline) initrd=\\EFI\\Gentoo\\initramfs-$VERSION.img"
```

For Startop, add `--full-dev-path` to the creation command. Inspect the resulting
entry and select a one-time boot with `sudo efibootmgr --bootnext XXXX` if desired.
Creation is explicit and does not change persistent BootOrder. The small
`99-agentoo-boot-guidance.install` hook also prints a populated command on the
booted target when matching EFI files exist. It never executes the command;
these instructions remain the fallback. Kernel-install can run more than once
during a package transaction, so guidance may be repeated.

## Applying this cleanup to an existing installation

Fresh installation checks out the tracked policy before package configuration.
For an existing target, review `agentoo-git diff`, then reconcile older local
installer policy before updating packages. Do not delete unknown/user-owned files.

- Move local boot arguments from `/etc/kernel/gentoo-dist.cmdline` to
  `/etc/kernel/cmdline` after checking their mounted-root identity; maintain one
  record, not two competing copies.
- Remove old installer-marked `zz-kernel-foundation` USE/keyword files and the
  installer-marked Dracut/ESP guard files once their tracked replacements are
  installed. Unmarked files require manual reconciliation. Do not keep both guards.
- Reconcile the old dhcpcd ExecStart drop-in and alternate configuration with the
  packaged service and normal `/etc/dhcpcd.conf`. Keep per-interface supplicant
  startup and the no-duplicate-hook setting. The package plan must remove
  systemd's resolvconf compatibility symlink; check for any other provider before
  deleting the fake-path workaround.
- Remove only the installer-marked `90-first-boot.conf` journald drop-in. Preserve
  existing journal directories and logs. Report previous-boot history after reboot.
- Review protected configuration updates with `dispatch-conf`, check permissions,
  then test networking, the fallback boot files, and reboot before checkpointing.

Recoverable installer failures preserve the target for inspection and retry.
If first-boot packages leave protected configuration updates, review them with
`chroot "$MOUNT_ROOT" dispatch-conf`, preserve the intended shared configuration,
then resume `first-boot-foundation`. Use an ordinary interactive terminal.
Disk-setup failures still clean up the resources created by that attempt. If a
mapping remains busy after ordinary handoff unmounts, use the explicit
[namespace recovery procedure](../docs/skills/qemu-nbd/references/namespace-recovery.md);
normal handoff no longer enters other processes' mount namespaces automatically.
Keep the installation mount root outside `/tmp`: service-private `/tmp` overlays
can hide propagated target mounts from the ordinary recovery procedure. The
disposable image itself may still live in `/tmp`.
