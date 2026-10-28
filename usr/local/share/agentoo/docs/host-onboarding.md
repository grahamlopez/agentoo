# Target host configuration checklist

Repository paths below are relative to the checkout and become absolute system
paths on deployed hosts. Replace `<host>` with the target selector. This covers
configuration support only; installation and hardware acceptance are separate.

## Required for an installer target

- [ ] **`usr/local/share/agentoo/installer/gentoo-install.sh`** — add the name to
  `valid_target_host()` and update every supported-name list in help and errors
  (including internal dispatch validation). Hostname alone does not select policy.
- [ ] **`etc/portage/make.conf.d/90-<host>`** — add the selected Portage fragment.
  Set only justified differences: `COMMON_FLAGS` and language flags,
  `RUSTFLAGS`, `VIDEO_CARDS`, `PORTAGE_TMPDIR` and `MAKEOPTS`. An empty/comment-only
  fragment is valid when common defaults suffice. `etc/portage/make.conf`
  already sources this path dynamically; it needs no host-specific edit.
- [ ] **`usr/local/share/agentoo/tests/test_installer.py`** — extend the accepted
  target list in `test_supported_targets_validate` and add coverage for any new
  installer behavior. Existing generic host loaders need no new name registry.
- [ ] **`etc/agentoo/README.md`** and **`usr/local/share/agentoo/docs/README.md`** —
  update supported selectors. Record hardware assumptions and the selected
  host policy in `etc/agentoo/README.md`.

## Required for custom kernel support

- [ ] **`etc/agentoo/kernel/hosts/<host>.config`** — add the host Kconfig fragment:
  explicit `CONFIG_EXTRA_FIRMWARE`, `CONFIG_EXTRA_FIRMWARE_DIR`, microcode support
  and justified host exceptions. Derive firmware names from this hardware, not
  another host's profile. Kernel host selection is file-based; no CLI host list
  needs updating.
- [ ] **`usr/local/share/agentoo/docs/kernel-shared-v04-config`** — review the
  shared baseline for missing required drivers/capabilities. Edit only if the
  shared union needs additions; preserve other hosts' requirements. Keep local
  UUIDs, firmware selection and workspace paths out of shared-policy changes.
- [ ] **`usr/local/share/agentoo/tests/test_kernel.py`** — add focused coverage
  if onboarding introduces new profile handling, module or boot-input behavior.
  A new data-only host fragment does not require duplicating generic loader tests.

See [kernel specialization](kernel.md#host-specialization). Bequiet's NVIDIA
support requires a module-enabled host configuration and separately scoped
external-module integration; a host fragment alone does not provide that workflow.

## Optional host policy files

- [ ] **`etc/agentoo/kernel-firmware.d/90-<host>`** — add only if installer SOF
  policy differs from `00-common`; use `SOF_FIRMWARE=yes` or `no`. CPU microcode
  package selection comes from installer `--microcode`/CPU detection, not this
  fragment. This policy is separate from custom-kernel embedded firmware.
- [ ] **`etc/agentoo/firmware/<host>.list`** and
  **`etc/portage/make.conf.d/90-<host>`** — for reviewed installed-firmware trimming,
  add explicit package-relative paths and set
  `AGENTOO_LINUX_FIRMWARE_USE="savedconfig -deduplicate -compress-xz -compress-zstd"`.
  Otherwise inherit broad coverage. `etc/portage/package.env/kernel` and
  `etc/portage/env/linux-firmware.conf` already consume this variable; no per-host
  wiring is needed. Do not add conflicting package.use flags. See [firmware](firmware.md).
- [ ] **`etc/xdg/hypr/hosts/<host>.lua`** — add monitor/scaling or key-binding
  differences. `etc/xdg/hypr/hyprland.lua` selects it automatically; missing host
  files retain shared behavior.
- [ ] **`etc/xdg/kitty/hosts/<host>.conf`** — add host terminal defaults when
  needed. `etc/xdg/kitty/kitty.conf` and
  `usr/local/share/agentoo/lib/kitty/host_config.py` already select it; a missing
  fragment retains Kitty defaults.
- [ ] **`etc/udev/rules.d/`** — add narrowly hardware-matched rules only for
  demonstrated device requirements. Follow Thinktop's DMI/PCI identity scoping;
  merely naming a file after a host does not restrict where its rules run.
- [ ] **`etc/keyd/`**, **`etc/systemd/`** and **`etc/modules-load.d/`** — edit only
  for required input, service/power or module policy differences. These directories
  have no Agentoo target-host loader; use native device matching/drop-ins and
  document their scope rather than assuming filename-based host selection.
- [ ] **`etc/portage/sets/`**, **`etc/portage/package.use/`** and
  **`etc/portage/package.accept_keywords/`** — add missing package capabilities
  only where needed. Existing shared sets are reusable; host selection does not
  automatically install a set. These paths have no host-name selection mechanism.
- [ ] **`usr/local/share/agentoo/installer/gentoo-install.sh`**
  (`print_physical_kernel_boot_commands`) and
  **`etc/kernel/install.d/99-agentoo-boot-guidance.install`** — edit both if a new
  host needs a firmware registration workaround. Startop's `--full-dev-path`
  handling is the existing example. Extend the relevant installer fixtures.
- [ ] **`etc/agentoo/permissions.conf`** — add exceptions only for new paths or
  modes not covered by existing tree rules. Ordinary host fragments under `etc/`
  already inherit root ownership, file mode 0644 and directory mode 0755.
- [ ] **`etc/agentoo/gitignore`** — extend only when adding new local/generated
  state outside existing exclusions. Local secret profiles are already excluded;
  a deliberately tracked profile containing references only needs an explicit
  exception, as `qemu.conf` has.

## Machine local files outside tracked host policy

These are installation-specific inputs or generated state, not files to copy
from another host into Git.

- [ ] **`/etc/agentoo/target-host`** — installer-written
  `GENTOO_TARGET_HOST="<host>"`; selects Portage, kernel, firmware and desktop
  fragments independently of the hostname.
- [ ] **`/etc/kernel/cmdline`** and **`/etc/fstab`** — local
  storage/boot identity. Custom kernel configuration validates the actual layout
  against local boot arguments; tracked host profiles contain no disk UUIDs.
- [ ] **`/etc/portage/savedconfig/sys-kernel/linux-firmware`** and matching
  version/triplet snapshots — native local firmware inputs/output, managed by
  `agentoo kernel firmware apply` when trimming is selected. Adding a tracked
  host list does not install this input automatically.
- [ ] **`/etc/agentoo/secrets/<host>.conf`** and
  **`/etc/wpa_supplicant/wpa_supplicant-<interface>.conf`** — local secret mapping
  and credentials. Secrets profiles are explicitly chosen by file path, not
  selected from `target-host`. See [secrets](../secrets/README.md).

## Current host coverage

| Host | Installer and Portage | Custom kernel profile | Installed firmware list | Desktop fragments |
| --- | --- | --- | --- | --- |
| Thinktop | Present | Present | Present | Hyprland and Kitty |
| Flattop | Present | Present | Present | Hyprland; Kitty defaults |
| Startop | Present; CPU/graphics policy still provisional | Missing | Broad default | Shared defaults |
| Bequiet | Missing | Missing; NVIDIA modules needed | Broad default | Shared defaults |
