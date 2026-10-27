# Develop the kernel configuration and rebuild workflow

Created: 2026-10-14
Status: Open — implemented; operator build/boot validation pending
Updated: 2026-10-26

## Current goal

Help the operator rebuild an already-configured custom kernel when Portage
provides newer sources. Prepare a fresh workspace, show the resolved inputs,
run familiar kernel tools, and install the resulting self-contained EFI image.
The build directory is the handoff between commands; a small metadata file there
may record the choices needed by subsequent steps.

The command, help/completion and focused verification are implemented.
Full local build, module installation, genkernel and firmware behavior still need
operator validation; the automated checks use disposable tools and files.
The [manual build notes](../../docs/kernel-baseline-build.md) supply the starting
procedure; the decisions below supersede conflicting older proposals.

Builds run locally for the machine that will use the kernel. Cross-compilation
and producing CPU-portable binaries for other machines are outside this scope.
Use `KCFLAGS="-march=native -O2 -pipe"` by default and display the effective flags.
The shared driver/capability configuration can still support multiple hosts;
each host builds with its own boot inputs, firmware/microcode and CPU target.

## Proposed interface

```text
agentoo kernel config
    --label LABEL               required
    --config FILE               default: running kernel /proc/config.gz
    --sources DIR               default: /usr/src/linux
    --build-dir DIR             default: /dev/shm/<derived-kernel-release>
    --[no-]accept-defaults       default: disabled
    --yes

agentoo kernel build
    --label LABEL               required
    --build-dir DIR             default: discover workspace under /dev/shm
    -j, --jobs N                default: available CPU count
    --[no-]genkernel             default: enabled
    --initramfs FILE             implies --no-genkernel
    --yes

agentoo kernel install
    --label LABEL               required
    --build-dir DIR             default: discover workspace under /dev/shm
    --dest DIR                  default: /boot/EFI/Gentoo
    --[no-]efi-add-entry         default: disabled
    --yes
```

`--[no-]` denotes paired positive/negative options. Use one canonical `config`
spelling and named `--label`/`--sources` options, replacing the earlier competing
`configure <build_label>` interface.

`--yes` skips proceed confirmations, not Kconfig questions. `--accept-defaults`
selects `olddefconfig` instead of interactive `oldconfig`. Neither option
suppresses sudo authentication. There is no separate `--no-input` option in this
proposal: fully unattended execution is not a current requirement. Without a
terminal, fail clearly if confirmation or configuration interaction is needed.
Skip the optional config-export question when confirmations are bypassed.

Before privileged operations, check cached sudo authorization noninteractively.
If renewal is needed, wait without a timeout for Enter on the controlling terminal
before starting sudo's password prompt. `--yes` does not skip this readiness wait.
Run the privileged command with `sudo -n` after authorization so it cannot start
an unexpected timed password prompt if the authorization has been revoked.

Build/install load the selected workspace's recorded paths and release rather
than recalculating them from the current `/usr/src/linux` symlink. Both require
`--label`; by default search under `/dev/shm` for that exact build label, validate
the matching workspace's viability for the requested stage, and show the resolved
selection for confirmation. Do not keep a last-workspace pointer or silently
choose the newest match. Report missing, invalid or ambiguous matches with useful
details; an explicit `--build-dir` selects the handoff directory and must agree
with `--label`. `--yes` bypasses confirmation, not discovery or validation.

`--initramfs FILE` selects a supplied custom archive and implies
`--no-genkernel`. Reject an explicit conflicting `--genkernel`; reject
`--no-genkernel` without an archive. Generated initramfs images are fresh for
each build invocation, including retries; never silently reuse a prior image.

## Workspace and lifetime

- `config` requires an absent or empty build directory and reports a useful
  error otherwise. It does not overwrite or merge an existing workspace.
- Under that root, use `kernel/<release>` for kernel output and
  `genkernel/<release>/{cache,tmp,output,modules}` for genkernel working data.
  Store a small metadata file at the root. Exact metadata names/format remain
  implementation details, not a general build-management framework.
- Record the resolved source path, label, release, original config and effective
  settings needed for handoff. Preserve the original config for differences.
- Import only the starting config from previous builds, during `config`. Do not
  copy old firmware/microcode staging, initramfs images, caches or other artifacts.
  Use current system inputs to generate a fresh initramfs, or the custom archive
  explicitly supplied by the operator. Diagnose stale paths inherited in the
  starting config rather than automatically recovering files from old workspaces.
- The workspace is normally temporary. Do not require durable build records,
  archived artifacts or automatic config exports. Offer an optional config copy;
  the successfully booted kernel's `/proc/config.gz` is the usual next baseline.
  Ensure support for that configuration interface remains enabled.
- Build retries and incremental builds reuse a prepared workspace. Print config
  differences only during `config`; fail on missing or contradictory preparation
  with the specific paths/settings that caused the failure. Show available
  temporary storage.

## Config: prepare and review the candidate

Example:

```sh
agentoo kernel config --label agentoo-v0.4 --config ../path/to/.config --sources /usr/src/linux
```

1. Read the supplied complete config, or decompress `/proc/config.gz`. Fail
   clearly if the running config is unavailable; do not silently use a different
   baseline. Validate source, label and empty destination before effects.
2. Resolve the source symlink and derive the upstream version and labeled release.
   Print the old-config origin, concrete source path, workspace and release:

   ```text
   old config:       running /proc/config.gz
   kernel sources:   /usr/src/linux-<version>-gentoo
   build directory:  /dev/shm/<version>-agentoo-v0.4
   kernel version:   <version>-agentoo-v0.4

   proceed [Y/n]?
   ```

3. Create the workspace, preserve the baseline and copy it to the kernel output
   `.config`. Start from that config without an initial `defconfig` generation.
4. Remove the Gentoo EXTRAVERSION suffix and set
   `CONFIG_LOCALVERSION="-<label>"` and disable automatic SCM release suffixes.
   Keep the source Makefile edit, showing the change and backing up the original.
   A make command-line override was verified locally, but genkernel directly parses
   the source Makefile's EXTRAVERSION, so that override alone is insufficient.
   Verify the complete release with `make kernelrelease`.
5. Show newly encountered options and run `oldconfig`, or `olddefconfig` when
   defaults were explicitly accepted. Report removed symbols and settings changed
   by dependency resolution as well as additions; do not equate migration with
   preserving every old behavior.
6. Preserve `CONFIG_CMDLINE` unchanged. Update only `CONFIG_LOCALVERSION` for the
   new label; there is no release-bearing boot argument to rewrite.
7. Print changes from the original config and the final resolved release. Keep
   module choices from the supplied config; do not automatically convert them or
   reject module-enabled inputs.
8. Offer `save copy of config? [y/N]`; if requested, ask for a destination and
   suggest `<release>_config`. Offer this question after `config` only; the
   workspace config remains available for manual copying after a build. Save the
   workspace metadata needed by build/install.

## Build: compile, install modules and embed the initramfs

1. Load the workspace metadata and check that source, config and release agree.
   Show specific findings for unexpected state. Resolve errors before compiling.
   Print effective `KCFLAGS`,
   config/source/workspace paths and release, then ask `proceed [Y/n]?`.
2. Clear `CONFIG_INITRAMFS_SOURCE` for the initial build, resolve the config and
   run `make -jN` with the recorded source and separate output directory.
3. Run the normal module-install stage for every build, even with module support
   disabled. This is an intentional visible stage, maintaining one procedure for
   laptops and future bequiet builds:

   ```sh
   sudo make modules_install INSTALL_MOD_STRIP=1
   make INSTALL_MOD_PATH="${genkernel_build}/modules" INSTALL_MOD_STRIP=1 modules_install
   ```

   Both commands must use the same source/output/release as the build. System
   module installation is an explicit effect of `build` and appears in its plan.
   The installed 6.18.57 source explicitly installs built-in-module metadata
   even with `CONFIG_MODULES=n`. Run the normal target and propagate failures;
   do not replace it with a simulated success.
4. In genkernel mode, generate a fresh uncompressed initramfs using workspace
   cache/tmp/output paths and `<release>` filenames. Run genkernel as the build
   user so its outputs remain readable by the subsequent unprivileged make.
   Retain LUKS support,
   `--no-mountboot`, `--no-bootloader` and `--no-firmware-install`. For module-free
   configs use `--no-ramdisk-modules`; for module-enabled configs use the staged
   modules prefix. Replace historical hardcoded versions with recorded paths.
5. In custom mode, `--initramfs FILE` disables genkernel automatically. Use a
   workspace copy of that explicitly supplied archive instead of invoking
   genkernel. Keep the same compilation and module-install stages. Never infer
   a custom archive from the old config's `CONFIG_INITRAMFS_SOURCE` path.
6. Set `CONFIG_INITRAMFS_SOURCE` to the selected archive, run `olddefconfig` and
   build the final kernel with `make -jN`. Surface unexpected config/release changes.
7. Verify final release consistency, EFI-stub and embedded-initramfs settings,
   and availability of the running-config interface. Record completion in the
   workspace so install can distinguish a completed image from a partial build.
   Print the image path. No durable export is required.

## Install: copy the image and optionally register it

1. Load the workspace, validate the completed image and release, and print the
   image path, destination and EFI-registration choice. Ask `proceed [Y/n]?`.
2. Mount `/boot` through its existing mount configuration if needed. Verify the
   destination is on the intended ESP before copying. Derive disk, partition and
   firmware loader path from that ESP using `findmnt`/`lsblk`.
3. Copy the kernel to `<dest>/kernel-<release>.efi`. Preserve the known-working
   fallback. If replacement is needed, show the existing image and backup path
   and explicitly confirm overwrite plus backup with the operator before either
   action. `--yes` accepts this displayed plan. Preserve the existing image in a
   timestamped backup before replacing it; do not overwrite an earlier backup.
   Copy the new image to an ESP-local temporary file, then rename it into place.
4. With registration disabled, print the exact `efibootmgr` command to register
   the image. With `--efi-add-entry`, create or reuse the matching entry, put it
   first, preserve all other entries and their relative order, then print
   `efibootmgr -u`. Match entries by GPT partition identity and loader path.
   Create with `--create`, which also adds the entry to BootOrder, then set the
   preserved order; leave BootNext alone. Use a child-process umask of `022` for
   creation so efivarfs entries retain their requested read permissions. Report
   failures without deleting the installed image or existing entries.
5. Do not automatically reboot. Successful compilation/installation is separate
   from the operator's boot and functional validation.

## CLI conventions

Follow the [existing CLI policy](../../lib/cli.py): independently runnable
`agentoo-kernel`, thin dispatcher routing, one parser for execution/help/completion,
no implicit option abbreviations, safe help without effects or privileges, and
validation before effects/escalation. Results and requested help go to stdout;
plans, progress, prompts and operational summaries go to stderr. Add help,
completion and focused verification with implementation. Do not add options merely
to match other commands when this workflow has no use for them.

## Later work

- Secure Boot signing (`--secureboot-sign`): settle signing inputs and integration
  separately before adding the option.
- Shared configuration generation and selective capture of menuconfig edits into
  Git, preserving the union of required host drivers/capabilities. Keep host boot
  identifiers, firmware/microcode and build paths separate from shared selections.
  Account for dependent changes and reproduce the selected edits before claiming
  capture is complete. This is not required for the current rebuild workflow.
- Repository updates must not silently rebuild or replace working configurations
  or boot images. Source adoption remains an explicit operator operation.
- External NVIDIA module rebuilding and acceptance remain future bequiet work;
  running the module-install stages does not itself implement that integration.

## Completion criteria for the first increment

- [ ] Demonstrate migration from a running or supplied config to newer sources,
  showing new, removed and dependency-changed settings and correct release naming.
- [ ] Demonstrate fresh-workspace enforcement, metadata handoff, build retries and
  label-based discovery under `/dev/shm`, including useful diagnostics for
  missing, inconsistent or ambiguous workspaces.
- [ ] Demonstrate local native compilation, the explicit module-install stages
  with module support disabled/enabled, and fresh genkernel/custom archive paths.
- [ ] Demonstrate confirmation bypass separately from accepting Kconfig defaults,
  and optional config export without mandatory durable records.
- [ ] Install a versioned EFI image while preserving recovery artifacts; verify
  overwrite/backup confirmation, printed registration commands and opt-in
  entry/order handling.
- [ ] Record operator boot results separately from static/build checks. Provide
  help/completion and focused verification following existing command conventions.

## Related work

[Shared v0.3 follow-ups](../Backlog/027-shared-kernel-v0.3-followups.md) and its linked host
cards own runtime validation and findings. Their earlier portable-compiler
recommendation is superseded for this local-build workflow by the native-build
choice above. [Bequiet](../Backlog/026-bequiet-kernel-v0.3-followups.md) records its module
exception; do not treat module support as an accidental omission.

[Initramfs keyboard policy](../Backlog/020-initramfs-keyboard-policy.md) remains separate;
regenerating the same policy does not fix it. [Distribution-kernel EFI
registration](../Backlog/008-automatic-efi-registration.md) excludes the custom-kernel path.
The [single-binary baseline](../Completed/014-single-binary-kernel-baseline.md)
and [retired reduction card](../Completed/016-kernel-reduction-and-evidence.md)
provide historical context rather than current operating instructions.

## Implementation and verification

Implementation is in `usr/local/bin/agentoo-kernel`, with its parser used by the
shared completion service. [Kernel command documentation](../../docs/kernel.md)
records invocation, interaction, effects and limits. No build framework or new
shared runtime layer was introduced.

- Focused tests use disposable sources and fake make/genkernel/sudo tools:
  config handoff and source backup, module-install stages, fresh initramfs on
  retry, custom archives with module-enabled configs, installation backup,
  ambiguous workspace/source checks and preserved EFI order.
- Sudo readiness follow-up (2026-10-27): all eight focused tests pass, including
  waiting for Enter before authentication and using cached authorization without
  prompting. No real sudo authentication was exercised by these tests.
- Existing CLI tests cover direct/grouped help, incomplete-value help, invalid
  options and completion parity; real Zsh completion includes the new command.
- Repository verification passed: 247 Python tests and all five Lua scripts.
- A real configuration-only smoke check used installed 6.18.57 sources with the
  stored Thinktop v0.2 config and a temporary output directory. `olddefconfig`
  succeeded, retained CMDLINE and produced `6.18.57-agentoo-cli-smoke`. Besides
  LOCALVERSION, Kconfig added the compiler's inline-memset option. No source
  Makefile change was needed because this source tree was already normalized.
- The source-Makefile fingerprint and completed config/image hashes catch common
  stale handoffs; they are not a complete source-tree provenance system.
- No full kernel build, real module/genkernel installation, ESP write, firmware
  change or reboot was performed during implementation verification. Leave this
  card open for normal operator validation; mocked paths do not prove bootability.
