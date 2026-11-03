# Gentoo configuration layout

This repository is designed to be checked out with `/` as its Git work tree on
every managed host. Files at their normal system paths are therefore both live
configuration and ordinary tracked files; there is no separate deployment or
synchronization step. The installed repository uses Git's non-cone sparse checkout
to omit the root `README.md` and `AGENTS.md`; ordinary development clones include
both files.

Universal policy belongs in native common fragments. Host-specific policy
belongs in a native fragment named for the host and is selected through
`/etc/agentoo/target-host`. Do not copy a complete common file into a host
variant, and do not make a common file silently depend on the machine where it
was edited.

Prefer native fragment, include, matching, and drop-in mechanisms. If a future
configuration format cannot express a common layer plus a selected host layer,
document that limitation and choose an explicit configuration ownership model.
User dotfiles must be real tracked files or local overrides, never deployed
copies or symlinks. See `/usr/local/share/agentoo/docs/README.md` for the configuration philosophy.

## Host selection

The installer selects the host configuration explicitly with `--target-host`;
it does not infer it from the hostname or installation machine. Supported
selectors are `generic`, `qemu`, `thinktop`, `startop`, and `flattop`.

It writes `/etc/agentoo/target-host`, containing the Portage-compatible assignment
`GENTOO_TARGET_HOST="qemu"`, for example. This file is intentionally untracked
local state because its value differs between installations. Portage's
`/etc/portage/make.conf` sources `/etc/portage/make.conf.d/00-common`, this
selector, then `/etc/portage/make.conf.d/90-${GENTOO_TARGET_HOST}`. It derives
`CFLAGS`, `CXXFLAGS`, `FCFLAGS` and `FFLAGS` from the selected `COMMON_FLAGS`
afterward. All host fragments remain visible on every host.

Use one double-quoted assignment, with no spaces around `=`. Host names start
with an ASCII letter or digit and contain only letters, digits, `_`, and `-`.
Python and Lua consumers read this assignment as data; malformed selectors
are errors. A missing selector leaves desktop defaults in effect. Kernel
configuration requires the selector or an explicit `--host`; firmware commands
require the selector.

Hyprland also reads that assignment as data and automatically loads the tracked
`/etc/xdg/hypr/hosts/name.lua` fragment when present; no separate Hyprland host
selector is required.

Host-specific packages belong in an optional native Portage set,
`/etc/portage/sets/host-<name>`. The installer emerges the selected host's set
during kernel-foundation, which records it in the world file; `host-thinktop`
supplies SOF firmware for its audio DSP. Sets describe the target hardware,
independent of the installation host.

Custom kernel builds separately select native Kconfig fragments under
`/etc/agentoo/kernel/hosts/<name>.config` through the same target-host selector
(or `agentoo kernel config --host NAME`). These fragments own embedded firmware
and host Kconfig exceptions. Local `/etc/kernel/cmdline` and discovered storage
identity supply boot identifiers; UUIDs are not tracked host policy. See the
[kernel guide](../../usr/local/share/agentoo/docs/kernel.md#host-specialization).

## Related guides

- [Installation, first boot, and user setup](../../usr/local/share/agentoo/docs/installation.md)
- [Git updates for the system repository](../../usr/local/share/agentoo/docs/git.md)
- [Shell and editor environment](../../usr/local/share/agentoo/docs/shell-editors.md)
- [Minimal Hyprland base and Kitty host defaults](../../usr/local/share/agentoo/docs/gui-base.md)
- [Firmware ownership and maintenance](../../usr/local/share/agentoo/docs/firmware.md)
- [Checkpoints and subvolume boundaries](../../usr/local/share/agentoo/docs/checkpoints.md)
- [Target host checklist](../../usr/local/share/agentoo/docs/host-onboarding.md)
- [Flattop hardware baseline](../../usr/local/share/agentoo/docs/hosts/flattop.md)
