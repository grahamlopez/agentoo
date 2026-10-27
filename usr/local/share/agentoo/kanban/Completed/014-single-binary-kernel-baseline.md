# Establish the single binary kernel baseline

Created: 2026-10-14
Status: Closed — successful custom-kernel boot; original approach superseded
Closed: 2026-10-16

## Closure and disposition

Closed at the operator's request. On 2026-10-16 the operator confirmed that
the system is currently running a successfully booted custom kernel. This
supersedes the earlier preparation-only status recorded below. The original
defconfig-first approach and runbook did not provide the successful procedure.

Successful boot is confirmed by the operator; the exact running release, artifact
hash, module state, embedded-input verification, early microcode loading and
full functional acceptance have not been recorded here. Do not infer these
additional checks from boot success alone.

The unsuccessful `docs/kernel-build.md` runbook has been removed. The replacement
[distribution-config build notes](../../docs/kernel-baseline-build.md) record a
different starting point: rebuild from the distribution kernel configuration,
use genkernel for the initramfs, and approach removal of modules separately.
Those notes capture the replacement approach and remain work in progress;
operator-confirmed boot success does not establish that every documented step
or all original single-binary requirements have been validated. This closes the defconfig-first
experiment rather than prescribing it for subsequent work.

Retain the inventory, configuration checkpoints and firmware findings below as
historical evidence only. Recheck them against the source, configuration and
initramfs used by any new build; do not treat pending steps as current operating
instructions. Keep the distribution boot path available. Card
[15](../Completed/015-shared-kernel-configuration-workflow.md) remains separate workflow
work. [Card 16](../Completed/016-kernel-reduction-and-evidence.md) was retired on
2026-10-16 because the operator will perform reduction manually. Successful boot
and closure alone do not establish full functional acceptance.

## Historical objective and agreed starting point

Establish a working single-binary boot before deliberately reducing kernel code.
Start with `make defconfig` in a selected, pinned `gentoo-sources` tree, then
run `make mod2yesconfig` to convert its module selections to built-ins where
possible. Disable module support (`CONFIG_MODULES=n`) and nouveau
(`CONFIG_DRM_NOUVEAU=n`), add the required host and boot features, and resolve
dependencies again. Review the resulting config for dropped or changed features,
including options that require module support. Verify no `=m` selections remain.

This preserves the default selections as built-ins rather than enabling
everything with `allyesconfig` or pruning by loaded modules with `localyesconfig`.
The source tree's default configuration is not a guarantee of host coverage;
enable additional hardware and functionality as needed.

Maintain one shared kernel configuration supporting all Agentoo hosts, with the
union of their required hardware drivers and capabilities. This decision, agreed
on 2026-10-15, replaces the earlier plan for host-specific driver fragments.
Each host receives its own self-contained binary with host-specific embedded
boot parameters, firmware and CPU microcode. These build inputs do not introduce
host-specific driver selections.

The custom kernel must have no loadable modules. Selected kernel code, required
firmware and CPU microcode, command line, and initramfs must be built into the
EFI-capable kernel binary. Use the legacy `gentoo-notes/README.md` sections on
custom kernel, command line, firmware and custom initrd as the reference for
the previously achieved boot. Inspect its artifacts where useful without
treating another host's configuration as Thinktop's configuration.

Build the bootable baseline manually first, retaining the configuration, inputs
and commands. Use that actual build and subsequent feature debugging to develop
the [shared configuration workflow](../Completed/015-shared-kernel-configuration-workflow.md).
Do not require a complete automation framework before establishing boot.

The now-removed `docs/kernel-build.md` was the user-facing procedure for this experiment.
The operator runs host commands. Keep steps and expected checks in the runbook;
record results, verification status and host findings in this card. The
initial source version is 6.18.54, explicitly accepted after reviewing Gentoo's
stable selection. Core prerequisites are recorded in `@kernel-dev`; the operator
confirmed successful installation, including `gentoo-sources-6.18.54`, on
2026-10-15. The operator verified `init/main.c` in
`/usr/src/linux-6.18.54-gentoo` and `make kernelversion` reporting
`6.18.54-gentoo`; `/usr/src/linux` still selects the distribution kernel's
development tree. The operator generated `x86_64_defconfig` successfully in
`~/local/agentoo-build/kernel/6.18.54-gentoo-thinktop` and saved the untouched
`.config` as `defconfig.original`. `make mod2yesconfig` completed and its result
was saved as `defconfig.builtin`: all 12 reported changes were `m` to `y`,
covering EFIVAR_FS, netfilter components and X86_PKG_TEMP_THERMAL. No other
changes were reported. The operator then disabled MODULES and DRM_NOUVEAU and
ran `olddefconfig`, saving `defconfig.nomodules`. The diff reports MODULES
changing to n and removal of module-related settings, an architecture helper
and previously disabled tests; no enabled device driver is shown being removed.
The operator confirmed no matches for `^CONFIG_.*=m$` and that the nouveau-state
check passed. Required additions and build remain pending. Audit loaded modules
as additive coverage evidence rather than applying `localyesconfig` pruning.
Defer perf until a specific measurement requires it.

## Initial Thinktop inventory

The operator supplied PCI/USB driver and sensor output on 2026-10-15 using
the runbook commands. Current bindings are evidence for additions to the shared
configuration, not a complete capability list or a validated custom build.

| Area | Observed hardware and bindings |
| --- | --- |
| Graphics | Intel `8086:7d51` uses i915; xe is an alternative listed module. NVIDIA `10de:2d19` has no bound driver; nouveau remains excluded. |
| Storage | Two Samsung NVMe controllers `144d:a810` use nvme; Realtek SD reader `10ec:5261` uses rtsx_pci. |
| Wireless | Intel CNVi `8086:7740` uses iwlwifi; USB `8087:0037` uses btusb. |
| Audio | Intel cAVS `8086:7728` uses sof-audio-pci-intel-mtl, with snd_sof_pci_intel_mtl listed; snd_hda_intel is an alternative. Codec/topology/firmware dependencies still need inventory. |
| Camera | Chicony `04f2:b83f` has uvcvideo interfaces and a usbhid interface; an application-specific interface is unbound. |
| USB and docks | xhci_hcd/xhci_pci, PCIe ports and Thunderbolt bindings, including a Barlow Ridge Thunderbolt 5 bridge/controller topology. |
| Platform | igen6_edac, processor_thermal_device_pci, intel_vsec, intel_vpu, intel_pmc_ssram_telemetry, intel_lpss_pci, mei_me, i2c_i801 and spi_intel_pci are listed for bound devices. |
| Sensors | coretemp, spd5118 over I801 SMBus, both NVMe drives, ThinkPad, ACPI thermal/fan/battery, UCSI power and iwlwifi temperature readings are exposed. |

Synaptics USB device `06cb:00f9` and PCI device `8086:774c` have no reported
driver binding. Do not infer that an unbound device is unnecessary. Sensor
presence records interface coverage, not validation of every reported value.
The `Kernel modules` list includes alternatives; do not blindly enable every
listed driver or prune to this host's currently loaded modules.

The operator confirmed the working storage layout: `nvme1n1p2` is the LUKS
container opened as `cryptroot`; Btrfs subvolume `@` is root, with `/home` also
on that mapped filesystem. `nvme1n1p1` is the EFI filesystem at `/boot`. The
other disk has a separate encrypted partition and is not the running root.
Keep exact UUIDs in local embedding inputs. The current Dracut boot arguments
include explicit root and LUKS UUIDs, mapper name, `rootfstype=btrfs`,
`rootflags=subvol=@`, `ro`, a nouveau module blacklist and an external initrd
path. Review initramfs-specific syntax, remove the external initrd reference,
and omit the blacklist when nouveau is disabled at build time.

`cryptsetup status cryptroot` confirms LUKS2, cipher `aes-xts-plain64`,
a 512-bit combined XTS key, key location `keyring`, and 512-byte sectors.
Record the corresponding built-in device-mapper, crypto and keyring requirements;
key derivation/unlock behavior also depends on the initramfs userspace.

The supplied loaded-module list extends the PCI/USB inventory with:

- SOF/SoundWire and Cirrus CS42L43/CS35L56 codec, MFD, pinctrl, SPI, DSP and
  regmap dependencies, plus HDA/HDMI audio. Map the full chain rather than only
  the PCI audio controller.
- `kvm`/`kvm_intel`, `tun`, VLAN `8021q` and supporting protocols, `uinput`,
  FUSE and binfmt_misc. Loading alone is not the complete VM/VPN requirement.
- I2C HID/ACPI, hid_multitouch, hid_sensor_hub, UCSI/Type-C, Meteor Lake
  pinctrl, SD/MMC and Thunderbolt support beyond controller bindings.
- CPU thermal/power monitoring, RAPL, uncore frequency, ThinkPad and Lenovo
  WMI/firmware interfaces, SPD5118, Intel PMC/PMT and ACPI platform support.
- Both i915 and xe are loaded, though i915 is the observed bound display driver.
  `Used by 0` does not by itself establish whether a module is dispensable.

The loaded-module audit and mapping to source Kconfig dependencies remain pending.

The operator saved `kernel.running`, `config.running` and `modules.running`
locally in the build directory. The new config already enables BLK_DEV_INITRD,
EFI/EFI_STUB, EFI partition parsing, devtmpfs (including automatic mounting),
device-mapper, KEYS and generic AES. The operator enabled BLK_DEV_NVME,
BTRFS_FS, DM_CRYPT, CRYPTO_XTS and CRYPTO_AES_NI_INTEL and saved
`config.root-storage`; the diff and subsequent inspection confirm all five
resolved to y. Dependencies include NVME_CORE, additional crypto/checksum
support, RAID6/XOR helpers and ZSTD compression. Comparing with `config.running`
identified missing NVME_HWMON and BTRFS_FS_POSIX_ACL, with HWMON=y in both
configurations. The operator enabled both and saved `config.storage-features`;
the diff confirms exactly those two n-to-y changes. Display/input and remaining
capability coverage are still pending.

The display/input comparison confirms the core VT console, i915, evdev,
i8042/AT keyboard, xHCI and generic USB HID paths are enabled. Missing settings
include DRM fbdev/framebuffer console, xe, uinput, multitouch, ACPI I2C HID,
DesignWare platform I2C and Meteor Lake pinctrl. The checklist's
`INTEL_LPSS_PCI` was an incorrect symbol name; the source defines
`MFD_INTEL_LPSS_PCI`. Absent child symbols require parent/dependency checks,
not a presumption that the source lacks support. Source Kconfig inspection
identified the PINCTRL, I2C_DESIGNWARE_CORE, I2C_HID and INPUT_MISC parent
options and LPSS/common-clock dependencies. The operator applied the display/input
additions and saved `config.display-input`; the diff confirms the requested
paths resolved to y, including the fbdev default DRM client and framebuffer
console, xe, uinput, multitouch, I2C HID, DesignWare platform I2C, LPSS and
Meteor Lake pinctrl. Dependencies add common clocks, GPIO/pinconf support,
DRM helpers and framebuffer infrastructure. Many newly visible child options
remain n. Runtime display/input acceptance is pending.

The wireless/Bluetooth comparison confirms WIRELESS, WLAN, WLAN_VENDOR_INTEL,
CFG80211, MAC80211 and RFKILL already resolve to y. IWLWIFI, IWLMLD, IWLMVM,
Bluetooth and its required USB/protocol/HID paths, and UHID are missing.
The running config enables classic and LE Bluetooth, USB autosuspend and
Broadcom/MediaTek/Realtek USB support in addition to Intel. Corresponding
The operator applied the additions and saved `config.wireless-bluetooth`;
the diff confirms all requested options resolved to y, including IWLMLD/IWLMVM,
classic/LE Bluetooth, USB autosuspend/vendor protocols, HIDP, RFCOMM, BNEP
and UHID. Dependencies include ECDH/ECC/KPP and Bluetooth vendor helpers.
RFCOMM TTY and BNEP multicast/protocol filters remain n; compare these and
other newly exposed capabilities with requirements before final acceptance.
Wireless/Bluetooth runtime tests remain pending.

The operator supplied firmware logs and CPU identification on 2026-10-15:

- CPU signature `0x000c0652`, running microcode revision `0x00000122`. The log
  reports the current revision; it does not establish that a new patch was
  applied early. Verify the matching installed blob before embedding it.
- Wi-Fi's `iwlwifi-bz-b0-fm-c0-c99.ucode` request failed with error -2; the
  driver successfully loaded `iwlwifi-bz-b0-fm-c0-101.ucode`, version
  `101.6ef20b19.0`. `iwl-debug-yoyo.bin` was also requested; necessity and
  availability remain to be checked.
- Graphics requests: `i915/mtl_dmc.bin`, `i915/mtl_guc_70.bin`,
  `i915/mtl_huc_gsc.bin`, `i915/mtl_gsc_1.bin`.
- Bluetooth requests: `intel/ibt-0093-0291.sfi` and `.ddc`, with firmware
  download completion reported. Regulatory data requests: `regulatory.db`
  and `regulatory.db.p7s`.
- NPU request: `intel/vpu/vpu_37xx_v1.bin`.
- Audio requests: `intel/sof-ipc4/arl/sof-arl.ri`, `sof-arl-openmodules.ri`
  and `sof-arl-debug.ri` under the same directory; `cs42l43.bin`; and
  topologies under `intel/sof-ace-tplg/`: the aggregate
  `sof-arl-cs42l43-l2-cs35l56-l3-2ch.tplg` and function topologies
  `sof-sdca-jack-id0.tplg`, `sof-sdca-1amp-id2.tplg`,
  `sof-arl-dmic-2ch-id3.tplg`, `sof-hdmi-pcm5-id5.tplg`.
- Amplifier requests under `cirrus/`: `cs35l56-b0-dsp1-misc-17aa2349.wmfw`,
  plus `cs35l56-b0-dsp1-misc-17aa2349-amp1.wmfw`, `-amp2.wmfw`,
  `-amp1.bin` and `-amp2.bin`.

Firmware staging subsequently verified 22 raw firmware/microcode files totaling
9,419,069 bytes under the local build directory's `firmware/`. The selection and
provenance are retained in `firmware.list` and `firmware.manifest.json` (source,
resolved symlink target, size and SHA-256). `config.firmware` records resolved
`FW_LOADER=y`, `MICROCODE=y` and `EXTRA_FIRMWARE` embedding settings. No kernel
image has been compiled or booted.

The staged selection includes the successful Wi-Fi 101 firmware, matching PNVM,
i915 firmware, Bluetooth SFI/DDC, regulatory data, NPU firmware, SOF firmware and
topologies, CS42L43 firmware, generic CS35L56 firmware and per-amplifier calibration.
`iucode_tool` selected `intel-ucode/06-c5-02` for signature `0x000c0652`, revision
`0x122`, dated 2026-02-18; that raw microcode file is also staged.

Six requested names were absent: Wi-Fi c99 and `iwl-debug-yoyo.bin`, SOF
`sof-arl-openmodules.ri` and `sof-arl-debug.ri`, and the two per-amplifier `.wmfw`
files. These are recorded in `firmware.absent-requests`; the supplied logs show
successful loading using available main/fallback firmware. The selection remains
subject to runtime validation, including peripherals not exercised by this boot.
Early microcode loading and firmware completeness have not been demonstrated.

## Scope and preparation

- Begin boot testing on Thinktop, then extend support and validation across
  Agentoo hosts through the same shared configuration. Do not remove a driver
  merely because Thinktop does not use it. Choose compiler/CPU settings that
  support the intended hosts rather than specializing for the build machine.
- Add a package set for inspection tools and kernel sources. Decide whether
  optional QEMU/OVMF test tools warrant a separate set when implementing this.
- Inventory hardware, driver bindings, firmware dependencies, storage/boot
  identity, and existing userspace interfaces. Record unavailable probes.
- Preserve source and patch provenance, tool versions, original defconfig,
  final resolved config, firmware and initramfs contents, build commands, and
  artifact hashes. Keep keys and credentials outside Git and build records.
- Separate unavoidable changes for embedding and built-in operation, hardware
  additions, and nouveau exclusion from later reduction experiments.
- Confirm early microcode loading, not merely the presence of microcode bytes.

## Host specific embedded build inputs

Generate a separate EFI artifact for each explicitly selected target host using
the shared driver and capability configuration. Embed that host's boot parameters
(including root/encrypted-root identity), required firmware and matching CPU
microcode. Keep the initramfs procedure shared, supplying host data where needed.
An identical binary across hosts and automatic root selection are not goals.

Record the selected host and exact embedded inputs with each artifact. Validate
that they describe the target rather than the machine doing the build, including
for cross-host builds. Keep credentials outside Git and the image; machine-local
boot identifiers must not become universal defaults. Firmware manifests should
cover the host's supported peripherals and usage, not only currently attached
devices. Firmware, microcode and boot-parameter updates require regenerating
the affected host's self-contained artifact.

## Recovery and boot testing

Retain the working distribution kernel, initramfs, and EFI entry. Install custom
candidates under separate versioned names and test without replacing the
known-working boot path. Confirm access to the firmware's fallback selection
before the first hardware test. Coordinate reboots and inspect the resulting
system before accepting a candidate. No automated reboot or persistent boot
order change is authorized by this card.

Disposable QEMU/OVMF tests may help validate EFI and encrypted-root mechanics;
they cannot establish Thinktop hardware support. Use test disks rather than
live host disks for such tests.

## Milestone one Single binary boot

- [x] Select and record the source version and establish inspection prerequisites.
- [x] Save the default starting config.
- [ ] Identify required built-in additions.
- [x] Convert default module selections with `make mod2yesconfig`, disable module
  support and nouveau, and review dependency resolution for lost functionality.
- [ ] Build an EFI kernel with embedded command line, initramfs and firmware;
  verify target-specific boot parameters, firmware and microcode, no loadable
  modules and no nouveau build.
- [ ] Demonstrate boot without an external initrd or firmware-supplied boot
  arguments; verify root unlock, the correct root/subvolume, and userspace start.
- [ ] Verify early microcode, required firmware loading and fallback availability.
- [ ] Retain the exact working artifact and a reproducible account of its inputs.

## Milestone two Functional acceptance before reduction

The user requires performance and features to be preserved. Clarify detailed
requirements piecemeal through actual usage; record pending coverage explicitly.
Boot success alone does not authorize claiming feature parity or starting broad
reduction. Cover at least:

- Advanced QEMU use, with actual requirements for nesting, accelerated I/O,
  networking, passthrough, memory features and other workloads established as used.
- Multiple VPN types, including their routing, filtering and crypto requirements.
- Userspace performance controls, applicable governors, sensors and monitoring.
- USB webcam, microphone, mice, mass storage and flash drives.
- Bluetooth mice, keyboards, headphones and headsets.
- Host graphics/displays, audio, networking, storage, relevant docks, hotplug,
  power behavior and suspend/resume.

Identify unsupported driver constraints explicitly, including out-of-tree drivers
that cannot satisfy built-in operation. Do not silently drop a requirement or
re-enable nouveau to resolve one. Compare performance and boot behavior with the
working system and keep passphrase-entry time separate where practical.

## Original completion criteria (not met)

Record boot results and feature acceptance separately. Complete this card when
the single-binary artifact and agreed functional coverage are demonstrated, with
untested cases and any unresolved requirements clearly accounted for. Begin
deliberate code removal under [kernel reduction](../Completed/016-kernel-reduction-and-evidence.md)
only after the relevant functional baseline is accepted.

## Initramfs preparation

Use dracut for the first baseline, then replace it with a custom initramfs as a
separate tested change. The local `cmdline` file preserves the working root,
Btrfs subvolume and LUKS arguments without the external initrd or nouveau
blacklist. Boot arguments and initramfs settings have not yet been applied to
the kernel configuration.

An unprivileged dracut 112 run produced `initramfs.dracut.cpio.gz`, but logged
`ldconfig might need uid=0 (root) for chroot()`. This archive is not accepted.
Regenerate using the runbook's sudo command, inspect the contents, then apply
embedding settings. No kernel compilation, installation or reboot occurred.

The operator regenerated the archive with sudo. Inspection confirmed a
22,730,925-byte gzip/newc archive with `/init`, a populated `etc/ld.so.cache`,
systemd password-prompt/cryptsetup components and Btrfs tools. No `.ko` files,
firmware payloads or `etc/crypttab` were found in its listing. Dracut module names
such as `kernel-modules` identify generator components, not embedded `.ko` files.

Applied command-line and archive embedding settings, saved as
`config.boot-inputs` with `diff.boot-inputs`. `CMDLINE_BOOL`, `BLK_DEV_INITRD` and
`RD_GZIP` resolve to y; `CMDLINE_OVERRIDE` remains disabled for boot-time debugging.
Module support and nouveau remain disabled, with no `=m` selections. This is
static preparation only; compilation, root-unlock and boot tests remain pending.
