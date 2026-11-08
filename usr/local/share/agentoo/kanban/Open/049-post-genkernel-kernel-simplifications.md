# Remove obsolete genkernel workflow mechanisms

Created: 2026-11-03
Status: Open — implementation complete; host acceptance pending

## Implemented 2026-11-08

- Kernel make receives the recorded upstream EXTRAVERSION as a command-line
  assignment. Config no longer writes or backs up the source Makefile.
- Custom command lines default to `ro console=tty0 loglevel=5`; `config --cmdline TEXT` explicitly
  selects other policy, including arguments required by supplied archives.
  Removed crypt_root/root_trim generation and command-line style handling.
  Mounted Btrfs @ / LUKS2 identity and UUID checks remain; distribution dracut
  configuration is independent. Discards remain in init's --allow-discards.
- Build prepares the archive before one configuration resolution and compile,
  then stages modules. Old staging is still removed on rebuild.
- Shared baseline resolved with native Kconfig and checked against the running
  minimal-initramfs v0.4 config. Initramfs owner/compression settings agree.
  Removed old command-line policy, archive path and host firmware inputs.
- Removed the archived package-list dependency and stale installer commentary.
  Retained the Thinktop mic-mute workaround pending a controlled cold-boot test.
  Historical kernel-baseline-build.md is
  intentionally unchanged at the user's request.
- Updated regression tests, CLI help and kernel/initramfs documentation.

The subsequent `sys-kernel/agentoo-initramfs` packaging work moves the generator
and boot scripts into the overlay package. The kernel continues generating the
archive before its single make pass; see the [initramfs guide](../../docs/initramfs.md).
The host acceptance below remains outstanding for this kernel simplification work.

## Retained mechanisms

The configure-time empty directory keeps Kconfig's dependent initramfs settings
available before an archive exists. It is created once in a fresh workspace;
there is no build-time placeholder reset or second compile.

The source Makefile hash still detects a source-version change between config
and build. It protects the recorded release and is independent of source edits.

## Development validation

- Full Python discovery: 364 tests, with one sandbox-only failure creating a
  temporary SSH-agent Unix socket. That isolated test passed with socket access.
  The 33 kernel tests passed again after final test cleanup. All six Lua scripts
  passed. Diff whitespace checks passed.
- Native Gentoo 6.18.57 Kconfig resolution preserved initramfs owner IDs and
  uncompressed archive policy. A small real EFI/initramfs kernel compiled with
  the expected release, then staged modules under that release without changing
  the source Makefile. A separate disposable source with EXTRAVERSION=-gentoo
  also resolved the intended release with the command-line override and retained
  its Makefile contents. A small external module compiled both through source/O
  invocation and through the staged build link without release overrides;
  modinfo reported the expected vermagic. Native modules_install emitted a build
  link and no separate source link; the generated output Makefile locates sources.
- The visible host configuration reports fstrim.timer disabled using
  systemctl --root=/ is-enabled. System-bus access is denied, so active state
  could not be checked. No timer configuration was changed.

## Acceptance still required

Run config/build/install on Thinktop or Flattop, register a separate firmware
entry and cold boot it. Verify encrypted root, active discard flag, normal
systemd startup and peripherals. On Thinktop verify MICMUTE keycode 248 without
manual remapping; see [card 020](020-initramfs-keyboard-policy.md).
Check host fstrim.timer state separately; enabling periodic TRIM is not part of
the kernel workflow. The development sandbox has no /dev/mapper access and
cannot perform host install or cold-boot acceptance. Do not close this card until
those results are recorded.
