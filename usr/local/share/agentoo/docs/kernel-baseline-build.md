
Here are the old instructions:


- if savedefconfig is available
  - cp defconfig to /usr/src/linux/.config
  - `make olddefconfig`
- populate CONFIG_CMDLINE="root=UUID=<uuid of /dev/mapper/root> crypt_root=UUID=<uuid of /dev/nvme0n1p2> ro root_trim=yes panic=10"
- enable CONFIG_CMDLINE_OVERRIDE
- make necessary things built-in and not modules (see .config progression)
  - so far I know DM_CRYPT can be either built-in or a module (in the initrd)
- build the kernel with `KCFLAGS="-march=native -O2 -pipe" make -j12`
- install modules with `make modules_install INSTALL_MOD_STRIP=1`
  - this noticeably affects boot speed
- generate an initrd with `genkernel --luks --no-compress-initramfs initramfs`
- copy the generated initrd to `/root/initrd-<whatever>.cpio.xz` (or whatever compression)
- uncompress the initrd image with `unxz`
- add the path to the initrd to CONFIG_INITRAMFS_SOURCE
- rebuild the kernel
- `cp arch/x86/boot/bzImage /boot/EFI/boot/boot64x.efi`
- `efibootmgr --create --disk /dev/nvme0n1 --part 1 --label "gentoo" --loader /EFI/boot/bootx64.efi`
  - or currently on startop: `efibootmgr --create --index 6 --full-dev-path --disk /dev/nvme1n1 --part 1 --label "gentoo" --loader /EFI/boot/boot64x.efi`

Note: recently I like to disable the initramfs compression in the kernel so that decompression isn't needed at boot. This also means that `unxz` is needed between `genkernel --luks initramfs` and building it into the kernel



Here's what I did to build locally as my user:

export KCFLAGS="-march=native -O2 -pipe"
kernel_build=/home/graham/local/agentoo-build/kernel/6.18.54-agentoo-mgl
gk_work=/home/graham/local/agentoo-build/genkernel
mkdir -p "$gk_work"/{cache,tmp,output,modules}

cp .config .config-with-initramfs
vim .config # remove initramfs source
make olddefconfig

make -j12
sudo make modules_install INSTALL_MOD_STRIP=1
make -C "$kernel_build" INSTALL_MOD_PATH="$gk_work/modules" INSTALL_MOD_STRIP=1 modules_install

genkernel \
    --kerneldir=/usr/src/linux-6.18.54-gentoo \
    --kernel-outputdir="$kernel_build" \
    --cachedir="$gk_work/cache" \
    --tmpdir="$gk_work/tmp" \
    --logfile="$gk_work/genkernel.log" \
    --install \
    --bootdir="$gk_work/output" \
    --kernel-modules-prefix="$gk_work/modules" \
    --no-mountboot \
    --no-bootloader \
    --no-firmware-install \
    --no-compress-initramfs \
    --initramfs-filename=initramfs-6.18.54-gentoo-agentoo-mgl.cpio \
    --luks \
    initramfs

vim .config # add initramfs file location
make olddefconfig
make -j12

cp arch/x86/boot/bzImage /boot/EFI/Gentoo/kernel-6.18.54-agentoo-mgl.efi

kernel_esp=$(findmnt -rn -o SOURCE --mountpoint /boot)
kernel_esp_disk="/dev/$(lsblk -dnro PKNAME "$kernel_esp")"
kernel_esp_part=$(lsblk -dnro PARTN "$kernel_esp")
lsblk -o PATH,TYPE,FSTYPE,PARTUUID,MOUNTPOINTS "$kernel_esp_disk"

efibootmgr --create --disk "$kernel_esp_disk" --part "$kernel_esp_part" --label "Agentoo-mgl-6.18.54" --loader "\\EFI\\Gentoo\\kernel-6.18.54-agentoo-mgl.efi"

