

# Starting from distribution kernel


## set up user-owned kernel build environment

edit out EXTRAVERSION from /usr/src/linux*/Makefile

build_label="agentoo-baseline"
kernel_src=/usr/src/linux-6.18.54-gentoo
kernel_build="${HOME}/local/agentoo-build/kernel/6.18.54-${build_label}"
genkernel_build="${HOME}/local/agentoo-build/genkernel/6.18.54-${build_label}"
export KCFLAGS="-march=native -O2 -pipe"

mkdir -p "${kernel_build}"
mkdir -p "${genkernel_build}"/{cache,tmp,output,modules}


## prepare dist kernel config for source rebuild

make -C "${kernel_src}" O="${kernel_build}" defconfig 
cp "${kernel_build}/.config" "${kernel_build}/defconfig.original"
cp /usr/src/linux-6.18.54-gentoo-dist-bin/.config .
make olddefconfig


## set up kernel config for embedded cmdline and initramfs

cmdline='root=UUID=a0d8c112-b1fd-4a55-8515-d5eb8f13b76d'
cmdline+=' rootfstype=btrfs rootflags=subvol=@'
cmdline+=' crypt_root=UUID=aace61a6-83ee-4825-b1e2-71d6fd3995ea'
cmdline+=' ro root_trim=yes console=tty0 earlyprintk=efi,keep'
cmdline+=' loglevel=7 ignore_loglevel'
source/scripts/config --file .config \
    --enable CMDLINE_BOOL \
    --enable CMDLINE_OVERRIDE \
    --set-str CMDLINE "${cmdline}" \
    --set-str CONFIG_LOCALVERSION "-${build_label}" \
    --set-str CONFIG_DEFAULT_HOSTNAME "" \
    --enable BLK_DEV_INITRD \
    --set-str INITRAMFS_SOURCE "" \
    --set-val INITRAMFS_ROOT_UID 0 \
    --set-val INITRAMFS_ROOT_GID 0 \
    --disable INITRAMFS_COMPRESSION_GZIP \
    --disable INITRAMFS_COMPRESSION_BZIP2 \
    --disable INITRAMFS_COMPRESSION_LZMA \
    --disable INITRAMFS_COMPRESSION_XZ \
    --disable INITRAMFS_COMPRESSION_LZO \
    --disable INITRAMFS_COMPRESSION_LZ4 \
    --disable INITRAMFS_COMPRESSION_ZSTD \
    --enable INITRAMFS_COMPRESSION_NONE \
    --set-str MODULE_SIG_KEY 'certs/signing_key.pem' \
    --enable INITRAMFS_PRESERVE_MTIME


## build initial kernel and install modules to system and user build environment

make olddefconfig
make -j16
sudo make modules_install INSTALL_MOD_STRIP=1
make -C "${kernel_build}" INSTALL_MOD_PATH="${genkernel_build}/modules" INSTALL_MOD_STRIP=1 modules_install


## build initramfs

(with modules)

genkernel \
    --kerneldir=/usr/src/linux-6.18.54-gentoo \
    --kernel-outputdir="${kernel_build}" \
    --cachedir="${genkernel_build}/cache" \
    --tmpdir="${genkernel_build}/tmp" \
    --logfile="${genkernel_build}/genkernel.log" \
    --install \
    --bootdir="${genkernel_build}/output" \
    --kernel-modules-prefix="${genkernel_build}/modules" \
    --no-mountboot \
    --no-bootloader \
    --no-firmware-install \
    --no-compress-initramfs \
    --initramfs-filename="initramfs-6.18.54-${build_label}.cpio" \
    --luks \
    initramfs


## rebuild kernel to embed initramfs

source/scripts/config --file .config \
    --set-str INITRAMFS_SOURCE "${genkernel_build}/output/initramfs-6.18.54-${build_label}.cpio" \

make olddefconfig
make -j16


## install kernel image and configure firmware boot entry

sudo mount /boot
sudo cp arch/x86/boot/bzImage "/boot/EFI/Gentoo/kernel-6.18.54-${build_label}.efi"

kernel_esp=$(findmnt -rn -o SOURCE --mountpoint /boot)
kernel_esp_disk="/dev/$(lsblk -dnro PKNAME "${kernel_esp}")"
kernel_esp_part=$(lsblk -dnro PARTN "${kernel_esp}")
lsblk -o PATH,TYPE,FSTYPE,PARTUUID,MOUNTPOINTS "${kernel_esp_disk}"

sudo efibootmgr --create --disk "${kernel_esp_disk}" --part "${kernel_esp_part}" --label "${build_label}-6.18.54" --loader "\\EFI\\Gentoo\\kernel-6.18.54-${build_label}.efi"


## remove modules from the kernel

everything stays the same. except:

Disable the MODULES symbol at the top level of the make menuconfig, and run `make mod2yesconfig`

genkernel \
    --kerneldir=/usr/src/linux-6.18.54-gentoo \
    --kernel-outputdir="${kernel_build}" \
    --cachedir="${genkernel_build}/cache" \
    --tmpdir="${genkernel_build}/tmp" \
    --logfile="${genkernel_build}/genkernel.log" \
    --install \
    --bootdir="${genkernel_build}/output" \
    --no-ramdisk-modules \
    --no-mountboot \
    --no-bootloader \
    --no-firmware-install \
    --no-compress-initramfs \
    --initramfs-filename="initramfs-6.18.54-${build_label}.cpio" \
    --luks \
    initramfs


# Signing images for Secure Boot


## 1. Install tools and generate keys:

```
# Enable these USE flags persistently:
# needed for bundling dist kernel with external initramfs
echo 'sys-apps/systemd boot kernel-install ukify' |
  sudo tee /etc/portage/package.use/secureboot

sudo emerge --ask --changed-use sys-apps/systemd app-crypt/sbctl
sudo sbctl create-keys
sudo sbctl status
```

Back up /var/lib/sbctl securely offline before proceeding; it contains private signing keys. Also preserve your current firmware keys/settings and, if Windows uses BitLocker, have its recovery key available.

## 2. Create separate signed images, preserving the existing boot files:

```
sudo mount -o remount,rw /boot

sudo cp /boot/EFI/Gentoo/kernel-6.18.57-agentoo-v0.3.efi \
  /boot/EFI/Gentoo/agentoo-v0.3-signed.efi

sudo sbctl sign --save /boot/EFI/Gentoo/agentoo-v0.3-signed.efi

sudo /usr/lib/systemd/ukify build \
  --linux=/boot/EFI/Gentoo/kernel-6.18.57-gentoo-dist-bin.efi \
  --initrd=/boot/EFI/Gentoo/initramfs-6.18.57-gentoo-dist-bin.img \
  --cmdline=@/etc/kernel/cmdline \
  --os-release=@/etc/os-release \
  --uname=6.18.57-gentoo-dist-bin \
  --output=/boot/EFI/Gentoo/gentoo-dist-signed.efi

sudo sbctl sign --save /boot/EFI/Gentoo/gentoo-dist-signed.efi

sudo sbverify --cert /var/lib/sbctl/keys/db/db.pem \
  /boot/EFI/Gentoo/agentoo-v0.3-signed.efi
sudo sbverify --cert /var/lib/sbctl/keys/db/db.pem \
  /boot/EFI/Gentoo/gentoo-dist-signed.efi
```

## 3. Register both images without changing BootOrder:

```
sudo efibootmgr --create-only --disk /dev/nvme1n1 --part 1 \
  --label 'agentoo v0.3 signed' \
  --loader '\EFI\Gentoo\agentoo-v0.3-signed.efi'

sudo efibootmgr --create-only --disk /dev/nvme1n1 --part 1 \
  --label 'Gentoo distribution signed UKI' \
  --loader '\EFI\Gentoo\gentoo-dist-signed.efi'

sudo efibootmgr
sync
sudo mount -o remount,ro /boot
```

Use the firmware boot menu to test each new entry while Secure Boot is still disabled, including unlocking the encrypted root filesystem.

## 4. Enter firmware setup, switch Secure Boot into Setup Mode using its custom-key controls, and leave Secure Boot disabled for the enrollment boot. Disabling Secure Boot alone does not enter Setup Mode.

Back in Linux:

```
sudo sbctl status                  # Confirm Setup Mode is enabled
sudo sbctl enroll-keys --microsoft --firmware-builtin
sudo sbctl status
```

Including Microsoft and firmware-provided certificates retains trust needed by Windows and firmware option ROMs. If enrollment reports a safety error, investigate it rather than bypassing it. sbctl documentation (https://github.com/Foxboron/sbctl/blob/master/docs/sbctl.8.txt)

## 5. Enable Secure Boot in firmware without restoring factory keys, then test both signed entries again:

```
sudo sbctl status                  # Expect Secure Boot enabled
uname -r                           # Confirm the selected kernel
cat /sys/kernel/security/lockdown  # Inspect kernel lockdown separately
```

Once both work, make the signed v0.3 entry the normal first boot choice.

For future updates: sign each new custom image; rebuild and sign the fallback UKI whenever its kernel, initramfs, or command line changes. Your current installkernel configuration does neither automatically. sbctl sign-all can re-sign registered files, but does not rebuild the fallback UKI.
