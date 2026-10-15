# Establish the single binary kernel baseline

Created: 2026-10-14
Status: Open

## Objective and agreed starting point

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
the [shared configuration workflow](015-shared-kernel-configuration-workflow.md).
Do not require a complete automation framework before establishing boot.

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

- [ ] Select and record the source version and establish inspection prerequisites.
- [ ] Save the default starting config and identify required built-in additions.
- [ ] Convert default module selections with `make mod2yesconfig`, disable module
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

## Completion and follow-up

Record boot results and feature acceptance separately. Complete this card when
the single-binary artifact and agreed functional coverage are demonstrated, with
untested cases and any unresolved requirements clearly accounted for. Begin
deliberate code removal under [kernel reduction](../Backlog/016-kernel-reduction-and-evidence.md)
only after the relevant functional baseline is accepted.
