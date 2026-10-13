# Install and boot the Gentoo VM

These commands use `/home/graham/VMs/agentic-gentoo`, `/dev/nbd0`,
`/mnt/gentoo`, and the encrypted mapping `cryptroot`.
Run them in a normal host terminal. Enter passwords there when prompted.

## 1. Create a new VM and install

**Run this section only for a new installation.** For an existing VM, go to
section 3. The setup refuses to reuse an existing VM directory.
The installer erases its selected disk; do not rerun the full installer to boot.

Install the host tools:

```bash
sudo pacman -S --needed qemu-base edk2-ovmf virt-firmware jq python psmisc btrfs-progs cryptsetup curl dosfstools git gnupg
```

Create the disk and a reusable boot command. Paste this entire block:

```bash
(
  set -e
  mkdir -p /home/graham/VMs
  mkdir /home/graham/VMs/agentic-gentoo
  cd /home/graham/VMs/agentic-gentoo
  qemu-img create -f qcow2 target.qcow2 100G
  cat > boot.sh <<'BOOT'
#!/usr/bin/env bash
set -e
cd -- "$(dirname -- "$(readlink -f -- "$0")")"
test -s target.qcow2
test -s OVMF_VARS.4m.fd
exec qemu-system-x86_64 \
  -enable-kvm -machine q35 -cpu host -m 4096 -smp 4 \
  -nic user,model=virtio-net-pci,hostfwd=tcp:127.0.0.1:2222-:22 \
  -display none -serial mon:stdio \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd \
  -drive if=pflash,format=raw,file=OVMF_VARS.4m.fd \
  -drive if=virtio,format=qcow2,file=target.qcow2
BOOT
)
```

Attach the new disk. First check that `/dev/nbd0` is unused: it must have zero
capacity and no connection PID. If it is occupied, stop and identify its owner
using section 4.

```bash
sudo modprobe nbd nbds_max=8 max_part=16
lsblk /dev/nbd0
cat /sys/block/nbd0/pid
```

For an unused device, `lsblk` shows `0B` and `cat` reports no such file.
Then attach and install:

```bash
sudo qemu-nbd --format=qcow2 --connect=/dev/nbd0 /home/graham/VMs/agentic-gentoo/target.qcow2
sudo udevadm settle
lsblk /dev/nbd0
```

Confirm `/dev/nbd0` now shows **100G** before continuing. If attachment failed
or it still shows `0B`, stop; do not run the installer.

```bash
cd /home/graham/Projects/agentoo
./usr/local/share/agentoo/installer/gentoo-install.sh \
  --disk /dev/nbd0 --target-host qemu --install-binpkgs \
  --qemu-vars /home/graham/VMs/agentic-gentoo/OVMF_VARS.4m.fd
```

The installer creates the persistent firmware file and its Gentoo boot entry.
Wait for **“Handoff complete”** before proceeding. An error means the install
has stopped; preserve the disk and resume the failed phase rather than starting
the full installation again.

## 2. Boot after installation completes

Leave any chroot first (`exit`), then run this on the host:

```bash
cd /home/graham
sudo umount --recursive /mnt/gentoo &&
sudo cryptsetup close cryptroot &&
sudo qemu-nbd --disconnect /dev/nbd0
```

If any command fails, stop and use section 4. Do not disconnect a disk while
its filesystems or encrypted mapping are still in use.

Verify detachment:

```bash
lsblk /dev/nbd0
qemu-img info /home/graham/VMs/agentic-gentoo/target.qcow2
```

The device must show `0B`, and image inspection must succeed without a lock
error. If detachment is still finishing, repeat these two checks.
Then boot:

```bash
bash /home/graham/VMs/agentic-gentoo/boot.sh
```

Enter the disk-encryption passphrase, then log in as `root` with the guest
password set during installation. In the guest, run:

```bash
/root/001-firstboot-verify-and-checkpoint.sh
/root/002-agentoo-setup-user.sh
```

## 3. Boot an existing VM after a host reboot

Run only:

```bash
bash /home/graham/VMs/agentic-gentoo/boot.sh
```

No NBD attachment, host mount, disk creation, or installer run is needed.
Keep `target.qcow2`, `OVMF_VARS.4m.fd`, and `boot.sh` together.
For a VM created before this playbook, create `boot.sh` using just the
`cat > boot.sh` block in section 1, from its VM directory.

Unlock the disk and log in. Shut down from inside the guest with `poweroff`.
Ctrl-a c switches between the serial console and QEMU monitor.

## 4. Troubleshooting

### Input/output error during disk setup

If `/dev/nbd0` shows `0B` and `/sys/block/nbd0/pid` is absent, it is not
attached. The device name still exists after disconnection. With no mounts or
`cryptroot` mapping using it, attach the existing image again:

```bash
sudo qemu-nbd --format=qcow2 --connect=/dev/nbd0 /home/graham/VMs/agentic-gentoo/target.qcow2
sudo udevadm settle
lsblk /dev/nbd0
```

Confirm `100G`, then retry the installer only if this is still your intended
fresh installation. Do not create the image again. If a connected device
reports I/O errors, inspect `sudo journalctl -k -n 100` before retrying writes.

### Image write lock

Identify the process using the image:

```bash
sudo fuser -v /home/graham/VMs/agentic-gentoo/target.qcow2
pgrep -af qemu
```

If another VM is running, use that VM or shut it down from inside the guest.
If `qemu-nbd` owns the image, confirm its command names this image and
`/dev/nbd0`, then follow section 2's cleanup. Do not bypass disk locking.

### Busy mount or encrypted mapping

Leave all chroots and move host terminals outside `/mnt/gentoo`. Wait for
installer and package builds to finish. Inspect the target and its users:

```bash
findmnt -R /mnt/gentoo
sudo cryptsetup status cryptroot
sudo fuser -vm /mnt/gentoo
```

Confirm `cryptroot` belongs to `/dev/nbd0p2` before closing it.
If ordinary unmounting succeeds but the mapping remains busy, another mount
namespace may hold copies of the mounts. Run this read-only scan to show
only namespaces containing `/mnt/gentoo` or its descendants:

```bash
sudo bash <<'SCAN'
while read -r pid; do
  mounts=$(nsenter -t "$pid" -m -- findmnt -rn -o SOURCE,TARGET |
    awk '$2 == "/mnt/gentoo" || index($2, "/mnt/gentoo/") == 1')
  if [[ -n $mounts ]]; then
    printf '\nPID %s\n%s\n' "$pid" "$mounts"
  fi
done < <(lsns -t mnt -n -o PID)
SCAN
```

After the installer and package builds have finished, leave all chroots and
run this block on the host. It finds current namespace PIDs automatically,
checks that each root mount belongs to `cryptroot`, and stops on an unexpected
source or failed unmount. It does not stop services.

```bash
cd /home/graham
sudo bash <<'CLEANUP'
set -e
backing=$(cryptsetup status cryptroot | awk '$1 == "device:" {print $2}')
[[ $backing == /dev/nbd0p2 ]] || {
  echo "Stop: cryptroot is not backed by /dev/nbd0p2: $backing" >&2
  exit 1
}
while read -r pid; do
  source=$(nsenter -t "$pid" -m -- findmnt -rn \
    --mountpoint /mnt/gentoo -o SOURCE) || continue
  case "$source" in
    /dev/mapper/cryptroot|/dev/mapper/cryptroot\[*)
      echo "Unmounting Gentoo mounts in PID $pid"
      nsenter -t "$pid" -m -- umount --recursive /mnt/gentoo
      ;;
    *)
      echo "Stop: unexpected source in PID $pid: $source" >&2
      exit 1
      ;;
  esac
done < <(lsns -t mnt -n -o PID)
CLEANUP
```

Only after this block finishes without an unmount failure, close and detach:

```bash
sudo cryptsetup close cryptroot &&
sudo qemu-nbd --disconnect /dev/nbd0
```

Verify `/dev/nbd0` shows `0B` and `qemu-img info` succeeds as in section 2,
then boot:

```bash
bash /home/graham/VMs/agentic-gentoo/boot.sh
```

A namespace without `findmnt` may print “No such file or directory”; the loop
continues, but successful mapping closure is still required before detachment.
If closure remains busy, rerun the read-only scan and investigate remaining
holders. If only descendant mounts remain, inspect and unmount those exact
paths. Do not use forced/lazy unmounts or kill services as a shortcut.
See [namespace recovery](../docs/skills/qemu-nbd/references/namespace-recovery.md)
for deeper inspection when these checks do not resolve the holder.

### Missing EFI kernel, followed by PXE

Confirm you are booting the intended disk and its matching persistent firmware
file. Inspect the disk:

```bash
qemu-img info /home/graham/VMs/agentic-gentoo/target.qcow2
```

A newly created 100 GiB image occupying only about 200 KiB is a warning that
the installed disk may have been replaced. Creating a qcow2 image again at
an existing path overwrites it; firmware boot entries survive separately.
Restore a known backup or investigate the disk before reinstalling.

If the installed disk is intact, stop QEMU and inspect its EFI partition and
kernel files. A missing file or stale entry needs kernel/firmware repair; PXE
is the fallback after local boot fails.

### SSH connection refused

Unlock and boot the guest first. The boot command forwards host port 2222 to
guest port 22. In the guest, check `systemctl status sshd`; from the host use
`ssh -p 2222 graham@127.0.0.1` after creating and authorizing that account.
