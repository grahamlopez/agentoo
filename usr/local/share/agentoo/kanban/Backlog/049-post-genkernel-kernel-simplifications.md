# Simplify kernel workflow mechanisms that existed for genkernel

Created: 2026-11-03
Status: Backlog

## Context

Commit `bf83dea` removed `agentoo kernel build --genkernel`. Custom kernels now
embed either the minimal initramfs (`usr/local/share/agentoo/initramfs/`) or an
explicit `--initramfs FILE`. Several mechanisms that remain were justified by
genkernel and may no longer be needed. Each needs a real kernel build, and
the boot-affecting ones need a boot test on a host, before changing.

## Candidates

1. **Source Makefile EXTRAVERSION edit.** `configure()` in
   `usr/local/bin/agentoo-kernel` uses sudo to back up and rewrite
   `EXTRAVERSION` in the kernel source Makefile, which removes Gentoo's `-gentoo`
   suffix. The recorded reason was that genkernel reads the Makefile directly, so
   a make command-line override was not enough. Kernel make accepts
   `EXTRAVERSION=...` on the command line, so passing it from `make()` may give
   the same release without sudo or source-tree changes. Check:
   `make -s kernelrelease`, `modules_install` paths, the `build`/`source`
   symlinks under `/lib/modules/<release>`, and whether external module builds
   against the custom release still see the right version. If this works, the
   Makefile backup, the `source_makefile_sha256` change detection (or its
   justification), and the related `kernel.md` "Configure" step 2 can go.

2. **Encrypted-root command-line arguments.** `kernel_host.specialize_cmdline`
   still writes `crypt_root=UUID=...` into `CONFIG_CMDLINE` by default, and keeps
   `crypt_root` vs `rd.luks.*` styles from the baseline. `crypt_root` is a
   genkernel argument and `rd.luks.*` is dracut's. The minimal `init` does not
   read the command line: it unlocks the recorded PARTUUID/mapper and mounts
   `@` directly. Decide what the custom kernel's `CONFIG_CMDLINE` actually needs
   (console/logging policy, `ro`, perhaps nothing storage-related), then simplify
   specialization, its validation of local `/etc/kernel/cmdline` styles, the
   matching tests, and the `kernel.md` "Host specialization" text. Keep the local
   identity checks that stop a build from targeting the wrong disk. The
   distribution kernel's `/etc/kernel/cmdline` (dracut) is separate and stays.

3. **Shared baseline `CONFIG_INITRAMFS_SOURCE` dependents.**
   `usr/local/share/agentoo/docs/kernel-shared-v04-config` was captured from a
   genkernel build. Re-save it from a minimal-initramfs build so its initramfs
   settings (owner IDs, compression) and any genkernel-motivated options
   match what the current builder needs.

4. **Mic-mute workaround.** `etc/udev/rules.d/90-thinktop-micmute.rules`
   corrects a scan-code mapping from genkernel's bundled hwdb. Card 020 tracks
   retiring it; with genkernel gone, check whether Thinktop booted with the
   minimal initramfs (which has no udev/hwdb) still needs the rule.

5. **Workspace placeholder handling.** The `empty-initramfs` placeholder and the
   two-pass build keep Kconfig's dependent initramfs settings while the real
   archive is created after the first compile. The minimal builder does not
   need the compiled kernel, so the archive could perhaps be built before the
   single compile. Check whether that removes the placeholder, the second
   `olddefconfig`/compile, and the related `kernel.md` caveats. Custom
   `--initramfs` archives already exist before the build.

## Completion

Each adopted simplification lands separately with updated tests and
`kernel.md`. Changes 1, 2 and 5 need a real config/build/install, and 2
needs a boot on at least one encrypted host (Thinktop or Flattop) using
`agentoo kernel install` and manual firmware registration. Record rejected
candidates and why on this card before closing it.
