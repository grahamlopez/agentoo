# Build a self contained Agentoo kernel

Build one shared driver and capability configuration for all Agentoo hosts.

- host-specific boot parameters, firmware and CPU microcode are embedded into
  each host's self-contained EFI binary
- all selected kernel code is built in
- modules and nouveau are disabled
- the working distribution kernel is retained as recovery

Progress, verification results and open investigations belong in the
[baseline card](../kanban/Open/014-single-binary-kernel-baseline.md).

The [configuration workflow card](../kanban/Open/015-shared-kernel-configuration-workflow.md)
tracks automation developed from the demonstrated manual procedure.

## Install sources and core inspection tools

The repository's `@kernel-dev` set contains sources plus PCI, USB, platform and
sensor inspection tools:

```sh
sudo emerge -avn @kernel-dev
```

Inspect sensors already exposed
by the running kernel before considering additional hardware probing.

Set the explicit path to the installed source version being built, then check
the tree without switching `/usr/src/linux`. For example:

```sh
kernel_src=/usr/src/linux-6.18.54-gentoo
ls -ld /usr/src/linux "$kernel_src"
ls "$kernel_src/init/main.c"
make -s -C "$kernel_src" kernelversion
```

The complete source tree must contain `init/main.c`; `kernelversion` should
match the selected source version, including its Gentoo suffix. The `/usr/src/linux`
link may still select the binary distribution kernel's development tree. Use
the explicit full-source path when preparing the separate build directory.

## Inspect hardware and running system

Use these utilities to help identify driver requirements. They describe the
current attachments and running kernel, not every peripheral or capability the
shared kernel must support.

List PCI device IDs and current drivers, USB devices and their driver topology,
and sensors already exposed by the running kernel:

```sh
lspci -nnk
lsusb
lsusb -t
sensors
lsmod
```

Use loaded modules as an additive coverage checklist alongside device bindings
and requirements. Map missing support to Kconfig settings without pruning the
shared baseline with `localyesconfig`. Loaded modules do not cover every required
feature, and built-in drivers are not listed by `lsmod`.

Then read the current boot arguments, active root mount and storage layout:

```sh
cat /proc/cmdline
findmnt -no SOURCE,FSTYPE,OPTIONS /
lsblk -o NAME,TYPE,FSTYPE,UUID,MOUNTPOINTS
```

Use these to identify the target's root filesystem, encryption mapping and
subvolume requirements. Keep actual boot identifiers in local host inputs.
The embedded command line will replace the external `initrd=` reference;
module-only parameters also need review when converting to built-in drivers.

Read the active encrypted-root mapping's cipher, key size and sector size. For
a mapping named `cryptroot`:

```sh
sudo cryptsetup status cryptroot
```

Use these parameters to identify the built-in device-mapper and crypto support
needed for root access.

Next, read the current boot's firmware and microcode messages and identify the
CPU signature without loading or changing microcode:

```sh
sudo journalctl -k -b --no-pager -o cat | rg -i 'firmware|microcode'
sudo iucode_tool -S
```

Firmware requests can include unsuccessful optional or fallback names. Confirm
which files actually exist and are needed before creating the embedding list.
The log alone does not cover every supported peripheral or resume path.

## Prepare the default configuration

For incremental builds across reboots, use a persistent build directory outside
the repository and source tree for convenience. Set the source version and
target label explicitly; the target label identifies embedded inputs, not a
separate driver configuration. For example:

```sh
kernel_src=/usr/src/linux-6.18.54-gentoo
kernel_build="$HOME/local/agentoo-build/kernel/6.18.54-gentoo-thinktop"
mkdir -p "$HOME/local/agentoo-build/kernel"
mkdir "$kernel_build" &&
  make -C "$kernel_src" O="$kernel_build" defconfig &&
  cp "$kernel_build/.config" "$kernel_build/defconfig.original"
```

Run this as the ordinary build user, without sudo. Retain `defconfig.original`
unchanged for comparison. Use the same explicit source and `O=` directory for
subsequent configuration and build commands.

## Convert module selections to built ins

Convert existing module selections where possible, save the intermediate config,
and review the changes against the untouched default:

```sh
make -C "$kernel_src" O="$kernel_build" mod2yesconfig &&
  cp "$kernel_build/.config" "$kernel_build/defconfig.builtin" &&
  "$kernel_src/scripts/diffconfig" \
    "$kernel_build/defconfig.original" "$kernel_build/defconfig.builtin"
```

Review changes beyond `m` to `y`, including dependency-driven additions or
removals. Module support itself is disabled in the following stage; this
conversion alone does not establish the no-modules requirement.

Disable module support and nouveau in the working config, resolve dependencies,
save the result and compare it with the built-in conversion:

```sh
"$kernel_src/scripts/config" --file "$kernel_build/.config" \
  --disable MODULES --disable DRM_NOUVEAU &&
  make -C "$kernel_src" O="$kernel_build" olddefconfig &&
  cp "$kernel_build/.config" "$kernel_build/defconfig.nomodules" &&
  "$kernel_src/scripts/diffconfig" \
    "$kernel_build/defconfig.builtin" "$kernel_build/defconfig.nomodules"
```

Review removed module-management settings separately from functionality that
requires module support. Confirm no module selections remain:

```sh
rg '^CONFIG_.*=m$' "$kernel_build/.config"
```

No matches are expected; ripgrep returns status 1 when no matches are found.
Check nouveau's resolved state as well:

```sh
"$kernel_src/scripts/config" --file "$kernel_build/.config" --state DRM_NOUVEAU
```

It must be disabled; a symbol omitted by Kconfig because its dependencies are
disabled is also unavailable in that configuration.

## Check required additions

Save references from the working kernel in the local build directory:

```sh
uname -r > "$kernel_build/kernel.running"
zcat /proc/config.gz > "$kernel_build/config.running"
lsmod > "$kernel_build/modules.running"
```

Compare its enabled features and loaded drivers with the new configuration as
coverage evidence. Do not replace the new configuration with this reference or
prune it to only currently loaded modules.

Inspect boot-critical EFI, device setup, storage, encryption and keyring settings:

```sh
rg '^(CONFIG_|# CONFIG_)(EFI|BLK_DEV_INITRD|DEVTMPFS|BTRFS|BLK_DEV_DM|DM_CRYPT|BLK_DEV_NVME|NVME|CRYPTO_(AES|XTS)|KEYS)' \
  "$kernel_build/.config"
```

Identify missing settings and their dependencies before enabling them. Extend
the audit to the observed drivers and required capabilities, including features
not exercised by the running system.

## Enable encrypted root storage

For NVMe-backed LUKS root using Btrfs and AES-XTS, enable the storage and
encryption drivers, including x86 AES-NI acceleration:

```sh
"$kernel_src/scripts/config" --file "$kernel_build/.config" \
  --enable BLK_DEV_NVME \
  --enable BTRFS_FS \
  --enable DM_CRYPT \
  --enable CRYPTO_XTS \
  --enable CRYPTO_AES_NI_INTEL &&
  make -C "$kernel_src" O="$kernel_build" olddefconfig &&
  cp "$kernel_build/.config" "$kernel_build/config.root-storage" &&
  "$kernel_src/scripts/diffconfig" \
    "$kernel_build/defconfig.nomodules" "$kernel_build/config.root-storage"
```

Confirm the requested options resolve to `y` and review dependency additions.
Retain the existing EFI, initramfs, devtmpfs, device-mapper, AES and keyring
support. These kernel drivers provide storage and decryption support; LUKS
unlocking still requires cryptsetup and its dependencies in the initramfs.

Check newly available child options rather than treating their defaults as
feature parity. Compare hardware-monitoring and Btrfs ACL support with the
working kernel:

```sh
rg '^(CONFIG_|# CONFIG_)(HWMON|NVME_HWMON|BTRFS_FS_POSIX_ACL)(=| is not set)' \
  "$kernel_build/config.running" "$kernel_build/.config"
```

Preserve required sensor interfaces and filesystem features before accepting
the storage configuration. With HWMON already enabled, retain NVMe sensor and
Btrfs POSIX ACL support as follows:

```sh
"$kernel_src/scripts/config" --file "$kernel_build/.config" \
  --enable NVME_HWMON --enable BTRFS_FS_POSIX_ACL &&
  make -C "$kernel_src" O="$kernel_build" olddefconfig &&
  cp "$kernel_build/.config" "$kernel_build/config.storage-features" &&
  "$kernel_src/scripts/diffconfig" \
    "$kernel_build/config.root-storage" "$kernel_build/config.storage-features"
```

## Check display and input support

Compare console, graphics and input settings with the working kernel, including
the I2C/platform dependencies of built-in input devices:

```sh
for option in VT VT_CONSOLE FRAMEBUFFER_CONSOLE DRM_FBDEV_EMULATION \
  DRM_I915 DRM_XE INPUT_EVDEV INPUT_UINPUT SERIO_I8042 KEYBOARD_ATKBD \
  USB_XHCI_HCD USB_XHCI_PCI HID_GENERIC USB_HID HID_MULTITOUCH \
  I2C_HID_ACPI I2C_DESIGNWARE_PLATFORM MFD_INTEL_LPSS_PCI PINCTRL_METEORLAKE
do
  printf '%-28s running=%-5s new=%s\n' "$option" \
    "$("$kernel_src/scripts/config" --file "$kernel_build/config.running" --state "$option")" \
    "$("$kernel_src/scripts/config" --file "$kernel_build/.config" --state "$option")"
done
```

Use differences to identify additions, then check their source dependencies and
resolve the config. The console and required keyboard paths must work before
the encrypted-root prompt. Enabled graphics drivers also need their embedded
firmware; configuration alone does not establish display functionality.

An `undef` result means the symbol is absent from the config; inspect Kconfig
to distinguish an incorrect name from an option hidden by disabled parents.
Enable the missing console and input paths with their required parent options:

```sh
"$kernel_src/scripts/config" --file "$kernel_build/.config" \
  --enable DRM_FBDEV_EMULATION --enable DRM_CLIENT_DEFAULT_FBDEV \
  --enable FRAMEBUFFER_CONSOLE --enable DRM_XE \
  --enable INPUT_MISC --enable INPUT_UINPUT --enable HID_MULTITOUCH \
  --enable I2C_HID --enable I2C_HID_ACPI \
  --enable I2C_DESIGNWARE_CORE --enable I2C_DESIGNWARE_PLATFORM \
  --enable MFD_INTEL_LPSS_PCI \
  --enable PINCTRL --enable PINCTRL_METEORLAKE &&
  make -C "$kernel_src" O="$kernel_build" olddefconfig &&
  cp "$kernel_build/.config" "$kernel_build/config.display-input" &&
  "$kernel_src/scripts/diffconfig" \
    "$kernel_build/config.storage-features" "$kernel_build/config.display-input"
```

Review resolved settings and dependency additions. Preserve i915 support when
adding xe; verify the intended GPU driver binding during boot testing. Kconfig
parent options include PINCTRL for the Intel pin controller and
I2C_DESIGNWARE_CORE for its platform driver. MFD_INTEL_LPSS_PCI selects the
LPSS core and common clock support required by the I2C platform path.

## Check wireless and Bluetooth support

Compare the wireless stack, Intel Wi-Fi operation modes, Bluetooth transport
and HID/protocol support with the working kernel:

```sh
for option in WIRELESS WLAN WLAN_VENDOR_INTEL CFG80211 MAC80211 \
  IWLWIFI IWLMLD IWLMVM RFKILL BT BT_BREDR BT_LE BT_HCIBTUSB \
  BT_HCIBTUSB_AUTOSUSPEND BT_HCIBTUSB_BCM BT_HCIBTUSB_MTK \
  BT_HCIBTUSB_RTL BT_HIDP BT_RFCOMM BT_BNEP UHID
do
  printf '%-28s running=%-5s new=%s\n' "$option" \
    "$("$kernel_src/scripts/config" --file "$kernel_build/config.running" --state "$option")" \
    "$("$kernel_src/scripts/config" --file "$kernel_build/.config" --state "$option")"
done
```

Check device-specific operation-mode dependencies as well as the controller
driver. Bluetooth HID/audio capability also depends on userspace and firmware;
enabled kernel options alone do not establish functional coverage. Network
tuning remains separate from enabling required kernel functionality.

With the wireless stack and RFKILL already enabled, add Intel Wi-Fi operation
modes and Bluetooth support matching the required capabilities:

```sh
"$kernel_src/scripts/config" --file "$kernel_build/.config" \
  --enable IWLWIFI --enable IWLMLD --enable IWLMVM \
  --enable BT --enable BT_BREDR --enable BT_LE \
  --enable BT_HCIBTUSB --enable BT_HCIBTUSB_AUTOSUSPEND \
  --enable BT_HCIBTUSB_BCM --enable BT_HCIBTUSB_MTK --enable BT_HCIBTUSB_RTL \
  --enable BT_HIDP --enable BT_RFCOMM --enable BT_BNEP --enable UHID &&
  make -C "$kernel_src" O="$kernel_build" olddefconfig &&
  cp "$kernel_build/.config" "$kernel_build/config.wireless-bluetooth" &&
  "$kernel_src/scripts/diffconfig" \
    "$kernel_build/config.display-input" "$kernel_build/config.wireless-bluetooth"
```

Review driver, protocol and crypto dependencies after resolution, and verify
the requested options remain enabled. Preserve required Bluetooth transports
and firmware for supported peripherals when later reducing the shared kernel.

## Check audio and webcam support

Compare the audio stack, Intel SOF/SoundWire machine driver and Cirrus codec
paths with the working kernel, along with USB audio and camera support:

```sh
for option in SOUND SND SND_HDA_INTEL SND_HDA_CODEC_HDMI SND_SOC \
  SND_SOC_SOF_TOPLEVEL SND_SOC_SOF_PCI SND_SOC_SOF_METEORLAKE \
  SND_SOC_SOF_INTEL_SOUNDWIRE SND_SOC_INTEL_SOUNDWIRE_SOF_MACH \
  SOUNDWIRE SOUNDWIRE_INTEL MFD_CS42L43_SDW PINCTRL_CS42L43 SPI_CS42L43 \
  SND_SOC_CS42L43_SDW SND_SOC_CS35L56_SDW SND_USB_AUDIO \
  MEDIA_SUPPORT MEDIA_CAMERA_SUPPORT MEDIA_USB_SUPPORT VIDEO_DEV USB_VIDEO_CLASS
do
  printf '%-42s running=%-5s new=%s\n' "$option" \
    "$("$kernel_src/scripts/config" --file "$kernel_build/config.running" --state "$option")" \
    "$("$kernel_src/scripts/config" --file "$kernel_build/.config" --state "$option")"
done
```

Check parent options and dependencies in the selected source before enabling
missing drivers. Audio requires the machine/codec paths and embedded DSP,
topology and amplifier firmware, not only the PCI controller driver. Keep USB
audio and UVC support for required external devices even when not attached.

Enable the SOF/SoundWire and codec chain, HDMI and USB audio, and UVC camera
support. Include the SPI parent and Intel machine-driver naming option required
by the SoundWire machine driver. Let Kconfig select internal helpers and inspect
the resolved result. Enabling the SOF PCI parent also exposes platform defaults;
review those when reducing code after functional acceptance.

```sh
"$kernel_src/scripts/config" --file "$kernel_build/.config" \
  --enable SPI --enable SND_HDA_CODEC_HDMI --enable SND_HDA_CODEC_HDMI_INTEL \
  --enable SND_HDA_CODEC_HDMI_GENERIC --enable SND_SOC --enable SND_SOC_SOF_TOPLEVEL \
  --enable SND_SOC_SOF_INTEL_TOPLEVEL --enable SND_SOC_SOF_PCI --enable SND_SOC_SOF_METEORLAKE \
  --enable SND_SOC_SOF_HDA_LINK --enable SND_SOC_SOF_HDA_AUDIO_CODEC \
  --enable SND_SOC_SOF_INTEL_SOUNDWIRE --enable SND_SOC_INTEL_USER_FRIENDLY_LONG_NAMES \
  --enable SND_SOC_INTEL_SOUNDWIRE_SOF_MACH --enable SOUNDWIRE --enable SOUNDWIRE_INTEL \
  --enable MFD_CS42L43_SDW --enable PINCTRL_CS42L43 --enable SPI_CS42L43 \
  --enable SND_SOC_CS42L43_SDW --enable SND_SOC_CS35L56_SDW --enable SND_USB_AUDIO \
  --enable MEDIA_SUPPORT --enable MEDIA_SUPPORT_FILTER --enable MEDIA_CAMERA_SUPPORT \
  --enable MEDIA_USB_SUPPORT --enable VIDEO_DEV --enable USB_VIDEO_CLASS &&
  make -C "$kernel_src" O="$kernel_build" olddefconfig &&
  cp "$kernel_build/.config" "$kernel_build/config.audio-webcam" &&
  "$kernel_src/scripts/diffconfig" \
    "$kernel_build/config.wireless-bluetooth" "$kernel_build/config.audio-webcam"
```

## Enable platform and sensor support

Preserve power, thermal and sensor interfaces, platform controls, USB-C and
Thunderbolt. RAS is required by EDAC; PMT telemetry and VSEC are dependencies
of the Intel PMC path. These settings support the observed hardware; extend
them as other hosts add requirements.

```sh
"$kernel_src/scripts/config" --file "$kernel_build/.config" \
  --enable RAS --enable EDAC --enable EDAC_IGEN6 --enable THERMAL --enable HWMON \
  --enable SENSORS_CORETEMP --enable SENSORS_SPD5118 --enable INT340X_THERMAL \
  --enable POWERCAP --enable INTEL_RAPL --enable INTEL_POWERCLAMP \
  --enable INTEL_UNCORE_FREQ_CONTROL --enable INTEL_VSEC --enable INTEL_PMT_DISCOVERY \
  --enable INTEL_PMT_TELEMETRY --enable INTEL_PMC_CORE --enable ACPI_PROCESSOR_AGGREGATOR \
  --enable ACPI_TAD --enable ACPI_WMI --enable THINKPAD_ACPI --enable THINKPAD_LMI \
  --enable LENOVO_WMI_TUNING --enable MXM_WMI --enable WATCHDOG --enable MFD_INTEL_PMC_BXT \
  --enable ITCO_WDT --enable DMADEVICES --enable INTEL_IDMA64 --enable INTEL_MEI_GSC_PROXY \
  --enable DRM_ACCEL --enable DRM_ACCEL_IVPU --enable MTD --enable MTD_SPI_NOR \
  --enable SPI_INTEL_PCI --enable TYPEC --enable TYPEC_UCSI --enable UCSI_ACPI \
  --enable USB_ROLE_SWITCH --enable USB4 --enable HID_SENSOR_HUB --enable INPUT_JOYDEV \
  --enable INPUT_PCSPKR --enable SERIO_RAW &&
  make -C "$kernel_src" O="$kernel_build" olddefconfig &&
  cp "$kernel_build/.config" "$kernel_build/config.platform" &&
  "$kernel_src/scripts/diffconfig" \
    "$kernel_build/config.audio-webcam" "$kernel_build/config.platform"
```

## Enable removable media and compatibility features

Enable SD and USB storage, removable filesystems and userspace filesystem
interfaces. Retain the running kernel's Bluetooth protocol extensions, generic
HD-audio codec/LED support, DisplayPort CEC and accelerated hash implementations.
SIGMATEL/Conexant codec selection also selects the generic HDA LED helper.
Firmware requirements remain specific to each target's devices.

```sh
"$kernel_src/scripts/config" --file "$kernel_build/.config" \
  --enable MMC --enable MISC_RTSX_PCI --enable MMC_REALTEK_PCI --enable MMC_BLOCK \
  --enable USB_STORAGE --enable USB_UAS --enable SCSI --enable BLK_DEV_SD --enable VFAT_FS \
  --enable EXFAT_FS --enable NTFS3_FS --enable NTFS3_FS_POSIX_ACL --enable NLS_UTF8 \
  --enable FUSE_FS --enable CUSE --enable BINFMT_MISC --enable SND_HDA_GENERIC \
  --enable SND_HDA_CODEC_SIGMATEL --enable SND_HDA_CODEC_CONEXANT \
  --enable DRM_DISPLAY_DP_AUX_CEC --enable BT_RFCOMM_TTY --enable BT_BNEP_MC_FILTER \
  --enable BT_BNEP_PROTO_FILTER --enable BT_MSFTEXT --enable BT_AOSPEXT --enable IWLDVM \
  --enable CRYPTO_GHASH_CLMUL_NI_INTEL --enable CRYPTO_POLYVAL_CLMUL_NI &&
  make -C "$kernel_src" O="$kernel_build" olddefconfig &&
  cp "$kernel_build/.config" "$kernel_build/config.removable-filesystems" &&
  "$kernel_src/scripts/diffconfig" \
    "$kernel_build/config.platform" "$kernel_build/config.removable-filesystems"
```

## Select and embed firmware and microcode

Firmware is a host-specific build input. Keep the selection and staged files in
`$kernel_build`, separate from the shared driver configuration. This does not
trim installed firmware; that is tracked in the
[firmware savedconfig card](../kanban/Backlog/018-host-firmware-savedconfig.md).

Review firmware requests from the working kernel while exercising the target's
devices, including audio, Bluetooth, Wi-Fi, graphics and supported peripherals:

```sh
sudo journalctl -k -b --no-pager -o cat | rg -i 'firmware|microcode'
```

Create `$kernel_build/firmware.list` with one required firmware request name per
line, relative to `/lib/firmware`, without compression suffixes. Preserve names
requested by drivers even when installed files are symlinks. Include topology,
calibration, regulatory and auxiliary files as applicable. A request can be an
unsuccessful fallback or optional debug file: review successful loading and the
driver's behavior rather than copying every logged name. Boot logs alone do not
cover disconnected peripherals or every supported use.

For Intel microcode, identify the target CPU and verify its matching installed
file; substitute the selected filename below. When building for another host,
use that host's CPU identity rather than the build machine's.

```sh
iucode_tool -S
iucode_tool -S -l /lib/firmware/intel-ucode/06-c5-02
```

Include the matching `intel-ucode/...` name in `firmware.list`. The x86-64 early
microcode loader supports `EXTRA_FIRMWARE`; see
`Documentation/arch/x86/microcode.rst` in the selected sources. AMD hosts need
the corresponding AMD microcode selection. Verify early loading after boot;
matching the current revision alone does not demonstrate an update occurred.

Stage raw bytes under their request names. `EXTRA_FIRMWARE` does not support
compressed files. This copies symlink targets, decompresses installed `.xz` or
`.zst` files, fails on missing selections, and records sources and SHA-256 hashes:

```sh
python3 - "$kernel_build" <<'PYTHON'
from pathlib import Path
import hashlib, json, lzma, subprocess, sys

build = Path(sys.argv[1])
manifest = []
for name in sorted(set((build / "firmware.list").read_text().splitlines())):
    if not name or name.startswith("/") or ".." in Path(name).parts or any(c.isspace() for c in name):
        raise SystemExit(f"Invalid firmware name: {name!r}")
    source = next((Path("/lib/firmware") / (name + suffix)
                   for suffix in ("", ".xz", ".zst")
                   if (Path("/lib/firmware") / (name + suffix)).is_file()), None)
    if source is None:
        raise SystemExit(f"Missing firmware: {name}")
    data = source.read_bytes()
    if source.suffix == ".xz":
        data = lzma.decompress(data)
    elif source.suffix == ".zst":
        data = subprocess.check_output(["zstd", "-dc", str(source)])
    target = build / "firmware" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    manifest.append(dict(name=name, source=str(source), resolved_source=str(source.resolve()),
                         bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
if not manifest:
    raise SystemExit("Empty firmware selection")
(build / "firmware.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
PYTHON
```

Review the manifest before configuring embedding. The JSON manifest is only a
provenance record. It records where each blob came from and its hash; nothing
currently consumes it.

Preserve the prior configuration and review the resolved difference:

```sh
cp "$kernel_build/.config" "$kernel_build/config.before-firmware" &&
  "$kernel_src/scripts/config" --file "$kernel_build/.config" \
    --enable FW_LOADER --enable MICROCODE \
    --set-str EXTRA_FIRMWARE "$(sort -u "$kernel_build/firmware.list" | paste -sd ' ' -)" \
    --set-str EXTRA_FIRMWARE_DIR "$kernel_build/firmware" &&
  make -C "$kernel_src" O="$kernel_build" olddefconfig &&
  cp "$kernel_build/.config" "$kernel_build/config.firmware" &&
  "$kernel_src/scripts/diffconfig" \
    "$kernel_build/config.before-firmware" "$kernel_build/config.firmware"
```

Confirm `FW_LOADER=y`, `MICROCODE=y`, the complete `EXTRA_FIRMWARE` list and the
staging directory in the resolved configuration. Retain the list, manifest and
staged bytes with the build inputs. Firmware and microcode updates require
restaging and rebuilding the binary. After boot, check device operation and
firmware logs; files still present on the root filesystem can conceal omissions
from the embedded selection.

## Prepare the embedded command line and initramfs

Use dracut for the first working baseline; replacing it with a custom initramfs
is a later change. Keep the target's boot identifiers in the local build directory.
For a build targeting the currently running host, copy its proven arguments and
remove the external initrd reference and nouveau blacklist:

```sh
python3 - "$kernel_build" <<'PYTHON'
from pathlib import Path
import sys
args = Path("/proc/cmdline").read_text().split()
args = [arg for arg in args if not arg.startswith(("initrd=", "module_blacklist="))]
(Path(sys.argv[1]) / "cmdline").write_text(" ".join(args) + "\n")
PYTHON
cat "$kernel_build/cmdline"
```

Review the root UUID, filesystem, subvolume and LUKS UUID/name against the target's
storage inventory. If the original blacklist contains other drivers, preserve
any required exclusions separately. Cross-host builds need the target's arguments.
Keep bootloader arguments available for debugging by leaving
`CMDLINE_OVERRIDE` disabled.

Generate an ordinary initramfs archive, rather than a UKI. Use isolated dracut
configuration so distribution fallback settings do not add drivers or microcode.
Kernel drivers, firmware and early microcode are already built into this kernel.
Root is needed for dracut's library-cache generation on this system:

```sh
mkdir -p "$kernel_build/dracut-empty.conf.d" "$kernel_build/dracut-tmp"
: > "$kernel_build/dracut.conf"
sudo dracut --force \
  --conf "$kernel_build/dracut.conf" \
  --confdir "$kernel_build/dracut-empty.conf.d" \
  --tmpdir "$kernel_build/dracut-tmp" \
  --no-hostonly --no-hostonly-cmdline \
  --no-kernel --no-early-microcode --no-uefi --gzip \
  --add 'crypt btrfs systemd-cryptsetup' \
  "$kernel_build/initramfs.dracut.cpio.gz" 6.18.54-gentoo-agentoo &&
  sudo chown "$(id -u):$(id -g)" "$kernel_build/initramfs.dracut.cpio.gz"
```

Use the candidate's release string for the last argument. A missing module-tree
notice is expected before compilation with `--no-kernel`; other errors need
investigation. Inspect the generated archive before configuring embedding:

```sh
sudo lsinitrd -m "$kernel_build/initramfs.dracut.cpio.gz"
sudo lsinitrd "$kernel_build/initramfs.dracut.cpio.gz"
```

The module list names dracut generator components; `kernel-modules` there does
not mean the archive contains loadable kernel modules. Inspect the file listing.

Confirm an `/init` entry, a populated `etc/ld.so.cache`, systemd root-mount and password-prompt support,
`systemd-cryptsetup`, Btrfs tools and their libraries. Confirm no `.ko` files,
external firmware payloads, keys or unintended crypttab entries. LUKS unlocking
uses the embedded command line and an interactive passphrase prompt.

After the archive passes inspection, configure embedding:

```sh
cp "$kernel_build/.config" "$kernel_build/config.before-boot-inputs" &&
  "$kernel_src/scripts/config" --file "$kernel_build/.config" \
    --enable CMDLINE_BOOL --disable CMDLINE_OVERRIDE \
    --set-str CMDLINE "$(cat "$kernel_build/cmdline")" \
    --enable BLK_DEV_INITRD --enable RD_GZIP \
    --set-str INITRAMFS_SOURCE "$kernel_build/initramfs.dracut.cpio.gz" &&
  make -C "$kernel_src" O="$kernel_build" olddefconfig &&
  cp "$kernel_build/.config" "$kernel_build/config.boot-inputs" &&
  "$kernel_src/scripts/diffconfig" \
    "$kernel_build/config.before-boot-inputs" "$kernel_build/config.boot-inputs"
```

The kernel build reads this archive directly; it must remain readable by the
build user. Check the resolved command line and initramfs path before compilation.
Archive inspection does not establish successful root unlock or boot.

## Compile the kernel

Run as your ordinary user. Display output while saving the build log; `pipefail`
ensures a failed build is reported even when `tee` succeeds. The subshell keeps
this setting local to the command.

```sh
(
  set -o pipefail
  make -C "$kernel_src" O="$kernel_build" -j"$(nproc)" bzImage 2>&1 |
    tee "$kernel_build/log.build"
)
```

On success, the image is `$kernel_build/arch/x86/boot/bzImage`. Inspect the image
and verify its embedded inputs before installation. If compilation fails, review
`$kernel_build/log.build` before continuing.

## Inspect the completed image

Wait for compilation to finish successfully. Check the release, EFI format and
configuration recovered from the actual image:

```sh
kernel_image="$kernel_build/arch/x86/boot/bzImage"
kernel_release=$(cat "$kernel_build/include/config/kernel.release")
file "$kernel_image"
"$kernel_src/scripts/extract-ikconfig" "$kernel_image" > "$kernel_build/config.image" &&
  cmp "$kernel_build/.config" "$kernel_build/config.image"
sha256sum "$kernel_image" > "$kernel_build/bzImage.sha256"
```

Expect the intended candidate release and an x86-64 EFI-capable kernel image.
Review `config.image`: module support and nouveau must be disabled; EFI stub,
firmware, command line and initramfs settings must describe the selected target.
Retain the config, firmware selection, initramfs, command line and build log with
the image. A matching config establishes the build settings; boot testing still
needs to establish that the embedded inputs work without external replacements.

## Copy the candidate to the EFI system partition

Inspect the mounted ESP and existing firmware entries. Confirm a working recovery
entry and its kernel/initramfs are still available, and that you can select it
from the firmware boot menu:

```sh
findmnt --mountpoint /boot
sudo ls -lh /boot/EFI/Gentoo
sudo efibootmgr -v | tee "$kernel_build/efibootmgr.before"
```

Use the mounted ESP, not a disk name remembered from an earlier boot. If Secure
Boot is enabled, the candidate must be signed with a key trusted by the firmware
before copying; this procedure does not enroll keys or alter Secure Boot policy.

Choose a new filename for every candidate. Copy only the self-contained image;
its initramfs, firmware and command line are embedded. The following block
restores a read-only ESP to read-only even if copying fails:

```sh
kernel_candidate="$kernel_release-agentoo-baseline"
kernel_efi="/boot/EFI/Gentoo/kernel-$kernel_candidate.efi"
(
  set -eu
  esp_options=$(findmnt -rn -o OPTIONS --mountpoint /boot)
  case ",$esp_options," in
    *,ro,*)
      sudo mount -o remount,rw /boot
      trap 'sudo mount -o remount,ro /boot' EXIT
      ;;
  esac
  sudo mkdir -p /boot/EFI/Gentoo
  sudo test ! -e "$kernel_efi"
  sudo install -m 0644 "$kernel_image" "$kernel_efi"
  sudo cmp "$kernel_image" "$kernel_efi"
  sync
)
```

Continue only if the block succeeds. Keep the distribution kernel, its external
initramfs and all existing recovery entries unchanged. Do not use `make install`
or overwrite the removable-media fallback path `EFI/BOOT/BOOTX64.EFI`.

## Register and test the firmware entry

Derive the disk and partition from the mounted ESP, inspect them, then register
the candidate without changing persistent BootOrder:

```sh
kernel_esp=$(findmnt -rn -o SOURCE --mountpoint /boot)
kernel_esp_disk="/dev/$(lsblk -dnro PKNAME "$kernel_esp")"
kernel_esp_part=$(lsblk -dnro PARTN "$kernel_esp")
lsblk -o PATH,TYPE,FSTYPE,PARTUUID,MOUNTPOINTS "$kernel_esp_disk"
```

Confirm these identify the ESP containing the copied image before continuing.

```sh
sudo efibootmgr --create-only \
  --disk "$kernel_esp_disk" --part "$kernel_esp_part" \
  --label "Agentoo $kernel_candidate" \
  --loader "\\EFI\\Gentoo\\kernel-$kernel_candidate.efi"
sudo efibootmgr -v
```

The new entry should point to the correct ESP and filename, with no additional
kernel arguments or `initrd=` reference. Confirm BootOrder matches the saved
listing. Identify the new four-digit hexadecimal Boot number; do not assume it
will have a particular value.

For the first test, select the entry manually from the firmware boot menu, or
set it for the next boot only (replace `NNNN` with that entry's number):

```sh
sudo efibootmgr --bootnext NNNN
sudo efibootmgr
```

Reboot when ready. BootNext is consumed for that attempt and leaves persistent
BootOrder unchanged. If the candidate fails, select the retained distribution
entry from the firmware menu. To cancel a pending test before rebooting:

```sh
sudo efibootmgr --delete-bootnext
```

After a successful boot, check the running release, embedded arguments, root
unlock/subvolume and kernel messages:

```sh
uname -r
cat /proc/cmdline
findmnt -no SOURCE,FSTYPE,OPTIONS /
sudo cryptsetup status cryptroot
sudo journalctl -k -b --no-pager -o cat | rg -i 'microcode|firmware|failed|error'
sudo efibootmgr
```

Confirm the candidate release, intended encrypted root and Btrfs subvolume, and
absence of an external `initrd=` argument. Verify early microcode and required
device firmware, then test graphics, input, networking, audio and the agreed
feature coverage. Record results in the baseline card. Keep the recovery entry
and persistent BootOrder until the candidate is accepted.

To remove a rejected candidate, boot the working kernel first, identify its
candidate entry with `efibootmgr -v`, then delete only that entry:

```sh
sudo efibootmgr --bootnum NNNN --delete-bootnum
```

The unused versioned EFI file may be removed separately after confirming its
path; restore the ESP's prior mount mode afterwards.
