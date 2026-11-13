# Simplify custom kernels using Gentoo's source-built kernel package

Created: 2026-11-13
Status: Backlog — explore after Bequiet onboarding with the existing implementation

## Goal and boundaries

Evaluate replacing most of `agentoo kernel`'s custom build/install lifecycle with
`sys-kernel/gentoo-kernel`, native configuration fragments and Portage's existing
kernel installation facilities. Preserve the capabilities we need while reducing
Agentoo-owned code, state and maintenance procedures.

Finish [Bequiet onboarding](../Open/026-bequiet-custom-kernel.md) using the current
implementation first. This proposal is not a dependency of that card and does not
authorize migration, implementation or replacement of working boot artifacts.

Retain the shared driver/capability union, selected host specialization, local
overrides, minimal embedded initramfs and direct EFI boot. Prefer native mechanisms;
do not add another kernel selector, configuration loader or maintenance framework.

## Initial evidence

Reviewed the installed Gentoo repository on 2026-11-13, including
`gentoo-kernel-6.18.62.ebuild`, `kernel-build.eclass`, `kernel-install.eclass`,
`linux-info.eclass`, `linux-mod-r1.eclass` and `dist-kernel-utils.eclass`.

- `gentoo-kernel` uses `kernel-build`, which already builds with separate source
  and output directories. Out-of-tree compilation itself is supported upstream.
- `kernel-build_src_install` publishes a prepared tree under
  `/usr/src/linux-${KV_FULL}` containing `.config`, generated headers/scripts,
  the kernel image, `System.map` and `Module.symvers` when modules are enabled.
  It installs the native per-release build/source/config/image links. This is the
  integration our current private retained output does not provide by default.
- `kernel-build_merge_configs` applies distribution defaults, module policy,
  optional savedconfig, signing-key settings and finally sorted
  `/etc/kernel/config.d/*.config` fragments. The existing full shared config and
  host Kconfig choices should be expressible through these native inputs.
  Generated versioned savedconfigs take native precedence over an unversioned
  savedconfig; decide whether managed fragments alone are sufficient rather than
  defining the same policy through both mechanisms.
- `config.d` does not select an Agentoo host automatically. Reuse the existing
  Portage profile selection and one explicit activation of its host fragment;
  keep machine-local archive paths and storage identity outside tracked policy.
- `CONFIG_INITRAMFS_SOURCE` can name our archive. The current minimal generator
  and encrypted-root policy can remain, but archive creation, a durable readable
  location and generation before Portage compilation need validation.
- Portage can compile in RAM through its native temporary-directory setting and
  install durable package-owned results. Native kernel installation provides EFI
  copy/signing hooks; manual `efibootmgr` registration remains a separate action.
- The existing implementation successfully boots Bequiet with USB unlock and
  NVIDIA. Its labelled output is not automatically discovered by `linux-info`
  when only the clean source tree is selected: the helper searches using the
  source release before the custom local version is known. Explicit
  `KERNEL_DIR`/`KBUILD_OUTPUT` works for the NVIDIA installation transaction.
- Most installed userspace kernel checks can fall back to `/proc/config.gz`;
  external-module builds need configured output. Dracut supports the per-release
  build link. The current linux-firmware hook nevertheless looks for its initial
  image under `KV_DIR`, so a separate output setting alone does not fix that hook.

These are source review and native-helper observations, not an accepted
`gentoo-kernel` build, installation or boot of our configuration. Automatic NVIDIA
maintenance for both custom and binary fallback kernels is not yet established.

## Evaluation and acceptance

- [ ] Trial native configuration merging without replacing the working kernel.
  Compare the complete resolved config against our shared baseline, host choices
  and boot requirements. Account for package defaults for signing/compression.
- [ ] Choose one authoritative configuration layering: shared defaults → selected
  host → local overrides. Avoid copied policy and unnecessary savedconfig layers.
- [ ] Build a separate candidate with our minimal embedded initramfs. Verify
  readable build inputs under native Portage isolation and correct EFI installation
  without generating an unwanted external initramfs or changing firmware entries.
- [ ] Verify RAM compilation, installed prepared-tree discovery and ordinary
  module/firmware maintenance through native Gentoo facilities. Test NVIDIA and
  userspace version agreement for both the custom kernel and binary fallback.
- [ ] Preserve explicit EFI registration and the required signing behavior;
  coordinate with [image signing](../Open/050-kernel-image-signing.md).
- [ ] Define the remaining Agentoo responsibilities: host preparation, local
  initramfs inputs, useful validation, native package invocation and EFI guidance.
  Keep a wrapper only where it adds a concrete operation or clarity.
- [ ] If the trial succeeds, replace the lifecycle directly and delete superseded
  workspace metadata, build/copy/install machinery, tests and documentation.
  No compatibility commands or parallel maintenance paths are required.
- [ ] Accept physical boot, required hardware and normal updates before retiring
  the existing workflow. Consolidate overlapping work in
  [kernel simplifications](../Open/049-post-genkernel-kernel-simplifications.md).

Prefer the simplest coherent result, even if it changes the current interface.
If preserving our requirements needs substantial glue, reconsider the approach
before building that glue. Close with the decision and validation in the finishing
commit and completed index; delete this card per board policy.
