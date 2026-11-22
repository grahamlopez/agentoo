# Target host configuration checklist

Repository paths below are relative to the checkout and become absolute system
paths on deployed hosts. Replace `<host>` with the target selector. This covers
configuration support only; installation and hardware acceptance are separate.

## Required for an installer target

- [ ] **`usr/local/share/agentoo/installer/gentoo-install.sh`** — add the name to
  `valid_target_host()` and update every supported-name list in help and errors
  (including internal dispatch validation). Hostname alone does not select policy.
- [ ] **`usr/local/share/agentoo/portage/profiles/hosts/<host>/`** — add a native
  profile with `eapi` and `parent`, and only justified `make.defaults`,
  `package.use` and unstarred `packages` additions. Inherit `../../common` or an
  appropriate shared hardware parent. The common profile inherits Gentoo's
  desktop/systemd baseline; `etc/portage/make.conf` derives language flags from
  profile `COMMON_FLAGS`. Register the host in `profiles/profiles.desc` so native
  `eselect profile set agentoo:hosts/<host>` works. No selector file or loader
  mapping is needed.
- [ ] **`usr/local/share/agentoo/tests/test_installer.py`** — extend the accepted
  target list in `test_supported_targets_validate` and add coverage for any new
  installer behavior. The shared native profile adapter needs no new name registry.
- [ ] **`usr/local/share/agentoo/docs/hosts/<host>.md`** and
  **`usr/local/share/agentoo/docs/README.md`** — record hardware identity,
  scoped exceptions, and quirks using the uniform four-section baseline format
  in [docs/README.md](README.md#documentation), and link the new host baseline
  from the guide index.

## Required for custom kernel support

- [ ] **`etc/agentoo/kernel/hosts/<host>.config`** — add the host Kconfig fragment:
  explicit `CONFIG_EXTRA_FIRMWARE`, `CONFIG_EXTRA_FIRMWARE_DIR`, microcode support
  and justified host exceptions. Derive firmware names from this hardware, not
  another host's profile. The selected Portage profile supplies the default host;
  no CLI host list needs updating.
- [ ] **`etc/kernel/config.d/10-agentoo.config`** — review the
  shared baseline for missing required drivers/capabilities. Edit only if the
  shared union needs additions; preserve other hosts' requirements. Keep local
  UUIDs, firmware selection and temporary build paths out of shared-policy changes.
- [ ] **`usr/local/share/agentoo/tests/test_kernel.py`** — add focused coverage
  if onboarding introduces new profile handling, module or boot-input behavior.
  A new data-only host fragment does not require duplicating generic loader tests.

See [kernel specialization](kernel.md#host-specialization). Bequiet's NVIDIA
support requires a module-enabled host configuration and separately scoped
external-module integration; a host fragment alone does not provide that workflow.

## Optional host policy files

- [ ] **`etc/dracut.conf.d/<host>.conf`** — add distribution-initramfs policy
  only for demonstrated requirements. Dracut sources every `.conf` file as
  shell configuration; query the shared `host_selection.py` adapter before
  applying host settings, as `startop.conf` does for early i915 loading.
  Rebuild affected distribution initramfs images after changing policy.
- [ ] **Host profile `packages`** — add hardware requirements such as SOF
  firmware here. Portage includes them automatically in `@profile` and `@world`,
  independently of GUI installation. Reuse hardware parents for shared requirements.
  CPU microcode selection remains installer `--microcode`/CPU detection.
- [ ] **`etc/agentoo/firmware/<host>.list`** and **host profile `package.use`** —
  for reviewed installed-firmware trimming, add explicit package-relative paths
  and enable `sys-kernel/linux-firmware savedconfig -deduplicate -compress-xz -compress-zstd`
  in the profile. Otherwise inherit broad coverage. Do not duplicate managed
  policy in `/etc/portage/package.use`. See [firmware](firmware.md).
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
  only where needed. Existing shared sets are reusable; host hardware requirements
  belong in profile `packages`, not extra sets. These paths have no host-name
  selection mechanism.
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
  exception for its filename in that ignore file.

## Machine local files outside tracked host policy

These are installation-specific inputs or generated state, not files to copy
from another host into Git.

- [ ] **`/etc/portage/make.profile`** — installer-selected native symlink to
  `agentoo:hosts/<host>`; selects Portage, kernel, firmware and desktop policy
  independently of the hostname. Inspect with `eselect --brief --colour=no profile show`.
- [ ] **`/etc/kernel/cmdline`**, **`/etc/kernel/gentoo-dist-esp.uuid`** and
  **`/etc/fstab`** — local
  storage/boot identity. The installer verifies the target layout; tracked host
  profiles contain no disk UUIDs.
- [ ] **`/etc/portage/env/kernel-local`** and
  **`/etc/kernel/config.d/20-host.config`** — installation-time custom initramfs
  inputs and native host activation. Review after storage/profile changes;
  the resolved build validates host settings and required built-in boot drivers.
- [ ] **`/etc/portage/savedconfig/sys-kernel/linux-firmware`** and matching
  version/triplet snapshots — native local firmware inputs/output, managed by
  `agentoo kernel firmware apply` when trimming is selected. Adding a tracked
  host list does not install this input automatically.
- [ ] **`/etc/agentoo/secrets/<host>.conf`** and
  **`/etc/wpa_supplicant/wpa_supplicant-<interface>.conf`** — local secret mapping
  and credentials. Secrets profiles are explicitly chosen by file path, not
  selected from the Portage profile. See [secrets](../secrets/README.md).

## Existing host baselines

See the per-host hardware baselines for current host coverage and scoped
exceptions: [Thinktop](hosts/thinktop.md), [Flattop](hosts/flattop.md),
[Startop](hosts/startop.md), and [Bequiet](hosts/bequiet.md).
