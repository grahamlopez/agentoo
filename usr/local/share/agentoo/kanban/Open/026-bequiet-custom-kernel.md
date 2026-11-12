# Onboard Bequiet custom kernels and NVIDIA module maintenance

Status: Open

## Goal and authority

Make `agentoo kernel config/build/install` usable on Bequiet, including subsequent
kernel rebuilds and NVIDIA driver updates. This card defines and tracks the work;
update decisions and checkboxes as implementation and host acceptance proceed.
Remove superseded instructions rather than retain historical findings. General
command usage belongs in [kernel.md](../../docs/kernel.md).

Reuse the selected Portage profile, shared kernel capability union, native Kconfig
fragments and Gentoo package/module mechanisms. Keep software under Portage
ownership and machine-local storage identity outside tracked policy. Do not add
another host selector or a separate NVIDIA installer.

## Starting point

- Profile: `agentoo:hosts/bequiet`.
- X570 AORUS MASTER, BIOS F39; Ryzen 9 3950X; approximately 128 GiB RAM.
- Distribution fallback: `6.18.62-gentoo-dist-bin`; NVIDIA open driver
  `595.104.02`; RTX PRO 2000 Blackwell and RTX 6000 Ada.
- Root: Btrfs `@` on `cryptroot`; separate FAT ESP. Validate complete LUKS2/GPT
  identity with the existing discovery code on the unrestricted host.
- Secure Boot currently disabled; the finished workflow must work with it enabled
  to satisfy the operator's external requirements. Sign EFI images and NVIDIA
  modules and establish kernel trust for their signing certificate. Additional
  hardening beyond that requirement is not a goal.
- USB unlock works on the current installation: the operator plugs in the
  Lily58 for boot, then uses Bluetooth at the desktop. Confirm this procedure
  on the custom kernel; early Bluetooth is not required.
- `gentoo-sources`, `agentoo-initramfs` and `sbctl` are not installed.

## Configuration and workflow changes

- [ ] Add `etc/agentoo/kernel/hosts/bequiet.config`: reviewed embedded firmware,
  AMD microcode, `CONFIG_MODULES=y` and `CONFIG_MODULE_UNLOAD=y`. Preserve the
  shared driver union, HMM/device-private/MMU-notifier support and Nouveau
  exclusion. Resolve with native Kconfig and review all deltas, including module
  signing, symbol exports and the NVIDIA ebuild's requirements.
- [ ] Compare hardware coverage with the distribution kernel. Review currently
  loaded `gigabyte_wmi`, which the shared baseline disables. Put justified common
  capabilities in the shared union and host exceptions in the fragment.
- [ ] Settle build storage before changing defaults. Preserve RAM builds if a
  simple, tested persistence step can retain usable external-module build inputs
  under `${XDG_STATE_HOME:-$HOME/.local/state}/agentoo/kernel/<release>`.
  A raw copy is not sufficient evidence: check absolute initramfs/config and
  metadata paths, generated build files, staged module build links, source-tree
  availability and manifest validation after relocation. Test an NVIDIA rebuild
  after reboot without the original RAM tree. Keep one authoritative retained
  build, with no last-workspace pointer or bespoke archive service. If reliable
  relocation needs disproportionate machinery, prefer persistent workspaces
  directly and retain `--build-dir` for explicit RAM builds. Update config,
  discovery, install, help, docs and tests consistently with the chosen approach.
- [ ] Allow module-enabled kernels with the existing minimal initramfs when all
  required boot capabilities are built in. Replace the blanket `MODULES=n`
  restriction with concrete checks for storage, crypto, filesystem, device-node,
  console and USB input requirements. Keep early boot independent of module
  loading; load NVIDIA after switching to the real root. Test both missing
  prerequisites and the accepted Bequiet configuration.
  Keep `MODULES=n` in the shared baseline; enable modules only in the Bequiet
  fragment. The CLI's separate runtime rejection still needs changing; do not
  implement a host-name bypass for the actual boot prerequisites.
- [ ] Establish external-module maintenance using the installed Gentoo NVIDIA
  ebuild and native source/output targeting (`KERNEL_DIR`, `KBUILD_OUTPUT`).
  Verify the final release, vermagic, symbol compatibility and matching
  driver/userspace version. Reuse native signing and depmod mechanisms.
- [ ] Resolve module-tree ownership and ordering. Custom install replaces the
  entire release tree, so NVIDIA installed beforehand would be lost. Define one
  explicit sequence for initial install, same-release rebuilds and driver
  updates. Verify native Portage handling of both the custom kernel and the
  distribution fallback, including dist-kernel/initramfs hooks and driver
  upgrades. Choose the smallest coherent native integration after testing;
  a one-off emerge is not proof of maintenance. Module failure must leave an
  available recovery boot path and must not activate an incomplete candidate
  by default.
- [ ] Implement NVIDIA module signing through Gentoo's `modules-sign` and native
  signing inputs. Establish a persistent signing key and certificate trusted by
  the custom kernel; do not depend on a disposable build-generated key or assume
  firmware db enrollment alone establishes module trust. Prefer reusing the
  existing signing identity if technically suitable, without exposing its private
  key to the unprivileged kernel build. Include the public certificate through
  native Kconfig trust settings. Verify fallback kernel trust separately and
  ensure native strip/sign/compress ordering. Do not add forced module enforcement
  merely because Secure Boot is required. Retain explicit EFI `--unsigned` for
  development; acceptance requires signed images and modules with Secure Boot on.
- [ ] Update command usage, host coverage, onboarding guidance and focused
  regression tests with the final implementation. Replace deferred/manual
  Bequiet instructions; do not add compatibility paths.

## Firmware selection

Review these candidates against the target kernel and actual devices:

- AMD: `amd-ucode/microcode_amd_fam17h.bin`.
- AX200: `iwlwifi-cc-a0-77.ucode`; regulatory database and signature.
- Bluetooth: `intel/ibt-20-1-3.sfi` and its `.ddc` companion.
- Ethernet: `rtl_nic/rtl8125a-3.fw` and `rtl_nic/rtl8156b-2.fw`.

Keep installed linux-firmware coverage broad until the custom boot path works.
Keep NVIDIA's driver-versioned GSP firmware package-owned on the real root for
post-root module loading; do not embed its large payload without an early-boot
requirement.

- [ ] Review and add `etc/agentoo/firmware/bequiet.list` for installed firmware
  needed by both kernels and used peripherals, including cold initialization and
  suspend/resume. Do not simply copy the embedded-firmware list. AMD microcode,
  regulatory data and NVIDIA firmware have separate package ownership; include
  only linux-firmware-owned paths in its savedconfig.
- [ ] Enable native `savedconfig -deduplicate -compress-xz -compress-zstd` policy
  in Bequiet's Portage profile. Reuse `agentoo kernel firmware apply --dry-run`
  and `apply` for native savedconfig precedence, backup and source rebuild.
  Verify distribution initramfs regeneration targets its actual source/output
  tree rather than the custom workspace. No new firmware application mechanism.
- [ ] Apply trimming after initial boot acceptance, rebuild affected boot images
  and accept both kernels again, including used network/Bluetooth peripherals.

## Implementation and acceptance

- [ ] Install prerequisites through `@kernel-dev`; configure a fresh
  workspace on Bequiet using explicit Gentoo sources and the shared baseline.
  Build locally with native CPU flags.
- [ ] Run focused regressions, then repository checks. Exercise native Kconfig
  resolution and actual external-module compilation. Verify module build links
  after reboot; mocks alone do not establish compatibility.
- [ ] Install a separately labelled candidate, complete NVIDIA setup and inspect
  image/modules before boot selection. Preserve the working distribution image,
  initramfs and usable NVIDIA recovery path.
- [ ] Cold boot: visible console, USB Lily58 input, incorrect/correct passphrase,
  encrypted Btrfs root, systemd startup and early microcode.
- [ ] Verify both GPUs with `nvidia-smi`, displays/Hyprland and required GPU
  compute workloads; confirm module signatures, trusted signer and actual loading
  with Secure Boot enabled. Follow the existing enrollment guide, retain required
  Gentoo/Windows firmware trust, and verify both Linux boot paths and Windows.
- [ ] Validate used NVMe/SATA, Ethernet/Wi-Fi/Bluetooth, USB/dock devices,
  analog/HDMI/DP/USB audio, camera/microphone and expected sensor channels.
  Test intended suspend/resume and USB-to-Bluetooth keyboard transition.
- [ ] Verify AMD KVM acceleration and AMD-Vi/IOMMU initialization. Broader
  passthrough and shared workload qualification remain in the
  [shared card](../Backlog/027-shared-kernel-v0.3-followups.md).
- [ ] Exercise same-release reinstallation and NVIDIA update/rebuild maintenance
  for both boot paths. Confirm failure/retry behavior and boot the fallback.

Close when the maintained workflow and these checks pass. Record completion in
the finishing commit and board index, then delete this card per board policy.
