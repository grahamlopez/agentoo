# Gentoo configuration layout

This repository is checked out with `/` as its Git work tree on every managed
host; installed repositories use Git's non-cone sparse checkout to omit root
`README.md` and `AGENTS.md`, while development clones include both. See
[docs/README.md](../../usr/local/share/agentoo/docs/README.md) for layering
principles, state policy, and the full index of guides and host baselines.

## Host selection

The installer selects the host explicitly with `--target-host`; it does not
infer policy from the hostname or installation machine. Supported profiles are
registered in `usr/local/share/agentoo/portage/profiles/profiles.desc` (inspect
with `eselect profile list`).

The sole persistent selection is Portage's native `/etc/portage/make.profile`
symlink pointing to `agentoo:hosts/<name>`:

```sh
eselect profile list
eselect profile set agentoo:hosts/thinktop
eselect --brief --colour=no profile show
emerge --ask --update --deep --newuse @world
```

Selection changes configuration, not running services or installed packages;
apply affected kernel, initramfs, and desktop configuration separately. The
symlink is local state, excluded from the system Git work tree. There is no
second host selector, generated configuration deployment, or host-identity USE
flag.

Native inheritance supplies Gentoo's AMD64 23.0 desktop/systemd baseline,
Agentoo common defaults, shared hardware layers where appropriate, and host
differences. `make.defaults`, `package.use`, and `packages` hold their normal
Portage meanings. `/etc/portage/make.conf` derives C/C++/Fortran flags once from
profile `COMMON_FLAGS`; native `make.conf` and `package.use` remain local
overrides. Put shared managed defaults in profiles rather than shadowing them
with duplicate settings under `/etc/portage`.

Host hardware requirements are unstarred `packages` entries in the profiles,
which Portage includes automatically in `@profile` (already part of `@world`).
`@terminal-env`, `@gui-base`, and `@gui-desktop` remain explicit environment
choices.

Non-Portage consumers use `/usr/local/share/agentoo/lib/host_selection.py`,
which calls `eselect --brief --colour=no profile show`, trims whitespace, and
accepts `agentoo:hosts/<name>`. It can be imported by Python or invoked with
`python3` by Lua and shell consumers. It does not resolve symlinks, parse
profile inheritance, or maintain another host registry. Failed, unset, and
unrelated profile selections are errors; an absent optional application fragment
leaves shared defaults intact. Stage3 supplies `app-admin/eselect`, including
its profile module; the installer checks reporting before selecting the Agentoo
profile.

Hyprland and Kitty load optional native `/etc/xdg/{hypr,kitty}/hosts/<name>`
fragments through that shared adapter. Dracut's host-scoped config and
kernel-install EFI guidance also use it. Target installation activates
`/etc/agentoo/kernel/hosts/<name>.config` through a local native `config.d`
symlink and records local initramfs inputs in Portage's per-package environment;
see the [native kernel guide](../../usr/local/share/agentoo/docs/kernel.md) for
kernel build and recovery policy.
