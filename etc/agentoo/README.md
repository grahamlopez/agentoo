# Gentoo configuration layout

This repository is designed to be checked out with `/` as its Git work tree on
every managed host. Files at their normal system paths are therefore both live
configuration and ordinary tracked files; there is no separate deployment or
synchronization step. The installed repository uses Git's non-cone sparse checkout
to omit the root `README.md` and `AGENTS.md`; ordinary development clones include
both files.

Universal policy belongs in native common fragments. Host-specific policy
belongs in a native fragment named for the host and is selected by the native
Agentoo Portage profile. Do not copy a complete common file into a host variant,
and do not make a common file silently depend on the machine where it was edited.

Prefer native fragment, include, matching, and drop-in mechanisms. If a future
configuration format cannot express a common layer plus a selected host layer,
document that limitation and choose an explicit configuration ownership model.
User dotfiles must be real tracked files or local overrides, never deployed
copies or symlinks. See `/usr/local/share/agentoo/docs/README.md` for the configuration philosophy.

## Host selection

The installer selects the host explicitly with `--target-host`; it does not
infer policy from the hostname or installation machine. Supported targets are
`generic`, `qemu`, `thinktop`, `startop`, `flattop`, and `bequiet`.

The sole persistent selection is Portage's native `/etc/portage/make.profile`
symlink. Agentoo profiles live under
`/usr/local/share/agentoo/portage/profiles/hosts/<name>` and are listed in the
overlay's `profiles/profiles.desc`. Select and inspect a profile with:

```sh
eselect profile list
eselect profile set agentoo:hosts/thinktop
eselect --brief --colour=no profile show
emerge --ask --update --deep --newuse @world
```

Select the profile appropriate to the destination hardware and review the emerge
plan. Selection changes configuration, not running services or installed packages;
apply the affected kernel, initramfs and desktop configuration separately.
The symlink is local state, excluded from the system Git work tree. There is no
second host selector, generated configuration deployment, or host-identity USE flag.

Native inheritance supplies Gentoo's AMD64 23.0 desktop/systemd baseline,
Agentoo common defaults, the shared Intel laptop layer where appropriate, and
host differences. `make.defaults`, `package.use` and `packages` hold their normal
Portage meanings. `/etc/portage/make.conf` derives C/C++/Fortran flags once from
profile `COMMON_FLAGS`; native make.conf and package.use settings remain local
overrides. Override individual language flags there when needed. Put shared
managed defaults in profiles rather than shadowing them with duplicate settings
under `/etc/portage`.

Host hardware requirements are unstarred `packages` entries in the profiles.
Portage's native `profile-set` support includes them in `@profile`, already part
of `@world`, so no hardware set needs recording in `world_sets`. Intel laptop
profiles select the Intel media driver, VA-API diagnostics and acpilight whether
or not a GUI is installed. Thinktop also selects SOF firmware. Bequiet selects
the NVIDIA driver with Wayland support and open kernel modules for its Blackwell
and Ada GPUs. `@terminal-env`,
`@gui-base` and `@gui-desktop` remain explicit environment choices.

Non-Portage consumers use `/usr/local/share/agentoo/lib/host_selection.py`, which
calls `eselect --brief --colour=no profile show`, trims whitespace and accepts
`agentoo:hosts/<name>`. It can be imported by Python or invoked with `python3` by
Lua and shell consumers. It does not resolve symlinks, parse profile inheritance,
or maintain another host registry. Failed, unset and unrelated profile selections
are errors; an absent optional application fragment leaves shared defaults intact.
Stage3 supplies `app-admin/eselect`, including its profile module; the installer
checks reporting before selecting the Agentoo profile.

Hyprland and Kitty load their native `/etc/xdg/{hypr,kitty}/hosts/<name>`
fragments through that shared adapter. Dracut's early-i915 exception and the
kernel-install EFI guidance also use it. Custom kernel commands select native
Kconfig fragments under `/etc/agentoo/kernel/hosts/<name>.config` and reviewed
firmware lists through the same profile. `agentoo kernel config --target-host NAME`
is an explicit configuration-operation override; it does not change the selected
Portage profile or turn the build into a cross-build. Generic and QEMU have
Portage profiles but no reviewed custom-kernel fragments. Bequiet has a reviewed
fragment and unsigned NVIDIA build/install implementation; host acceptance
is tracked in the [active card](../../usr/local/share/agentoo/kanban/Open/026-bequiet-custom-kernel.md).

Local `/etc/kernel/cmdline` and discovered storage identity supply boot
identifiers; UUIDs are not tracked host policy. See the
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
- [Bequiet hardware baseline](../../usr/local/share/agentoo/docs/hosts/bequiet.md)
