# Trim installed firmware through host selected savedconfig

Created: 2026-10-15
Status: Backlog

## Objective and prerequisites

Use Gentoo's `linux-firmware[savedconfig]` mechanism to retain only firmware
needed by each selected Agentoo target host. Begin with Thinktop, then make
the selection repeatable for other hosts through the existing explicit
`/etc/agentoo/target-host` policy. This does not introduce host-specific kernel
driver configurations.

Follow the [single-binary kernel baseline](../Open/014-single-binary-kernel-baseline.md)
and its verified firmware manifest. Reuse that inventory as evidence rather
than blocking the initial kernel build on installed-firmware trimming. Firmware
embedded in a kernel and firmware retained by a package are separate selections.

## Current policy and scope

`/etc/portage/package.use/kernel` currently sets
`sys-kernel/linux-firmware -savedconfig`, preserving broad firmware coverage for
the distribution fallback. Design an explicit selected-host override for this
package and its savedconfig input without enabling trimming on other hosts.
Inspect the current ebuild/eclass behavior before choosing paths or override
mechanisms; ensure the savedconfig selection works for builds and updates.

This card concerns installed `sys-kernel/linux-firmware` files.
`sys-firmware/sof-firmware` and `sys-firmware/intel-microcode` are separate
packages and need separate policy if their installed contents are later trimmed.
Kernel firmware embedding remains part of the kernel build procedure.

## Investigation and implementation

- Establish the required firmware set from hardware, driver/source metadata,
  successful firmware loads and the baseline's embedding manifest. Account for
  supported peripherals and capabilities not active during collection.
- Include the distribution recovery kernel's needs and relevant fallback/API
  versions; it may request different firmware from the custom kernel. Do not
  equate an observed request list with the complete set of required files.
- Verify savedconfig handling of compressed files, symlinks, shared dependencies
  and firmware paths. Retain regulatory data and other package contents needed
  by the selected functionality.
- Keep host selections and rationale durable in the repository, with generated
  inventories and machine-local identifiers outside shared policy. Reuse common
  requirements where practical rather than maintaining unexplained duplicate
  lists.
- Establish how savedconfig inputs behave when package versions or firmware
  names change. Surface missing/renamed required files and new dependencies;
  do not silently accept a stale selection after an update.
- Document adding firmware for new hardware, regenerating affected custom
  artifacts and distribution initramfs images, and restoring broad firmware
  coverage if a selection causes a regression.

## Completion criteria

- [ ] Thinktop explicitly selects savedconfig without changing other hosts'
  firmware policy or the shared kernel driver configuration.
- [ ] A package rebuild demonstrably removes excluded package files and retains
  required firmware; record the installed size difference and exact selection.
- [ ] Verify cold boot, suspend/resume and relevant graphics, Wi-Fi, Bluetooth,
  audio, NPU and peripheral workflows with the custom kernel and distribution
  fallback as applicable. Account for initramfs copies and firmware caches so
  they do not conceal missing installed files.
- [ ] Exercise a firmware package update and savedconfig revision, including
  detection of stale paths and restoration of broad coverage.
- [ ] Document the user-facing maintenance and recovery procedure and record
  test evidence and any limits to coverage.

Related: [kernel reduction and evidence](016-kernel-reduction-and-evidence.md).
