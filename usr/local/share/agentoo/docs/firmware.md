# Firmware maintenance

Use `agentoo kernel firmware --help` (`apply --help`) for CLI options; reviewed
per-host payload lists live under `/etc/agentoo/firmware/<host>.list`.

Host firmware has three owners, each selected by the native Portage profile:

| Concern | Host file | Consumer |
| --- | --- | --- |
| Extra firmware packages (e.g., SOF) | profile `packages` | Portage `@profile` / `@world` |
| Installed `linux-firmware` trimming | `/etc/agentoo/firmware/<name>.list` + profile `package.use` | `agentoo kernel firmware apply`, then Portage |
| Custom-kernel embedded firmware | `CONFIG_EXTRA_FIRMWARE` in `/etc/agentoo/kernel/hosts/<name>.config` | Native source rebuild ([kernel guide](kernel.md#host-specialization)) |

CPU microcode follows installer `--microcode` (AMD microcode lives inside
`linux-firmware` and must stay in Bequiet's savedconfig; Intel microcode, SOF
audio, regulatory data, and NVIDIA GSP firmware belong to separate packages).
Intel laptop profiles and Bequiet enable `savedconfig` for `linux-firmware`;
other targets inherit `-savedconfig` (broad coverage).

## Apply or revise `linux-firmware` trimming

```sh
agentoo kernel firmware                 # read-only status (no sudo)
agentoo kernel firmware apply --dry-run
agentoo kernel firmware apply
```

`apply` pins the installed `linux-firmware` version, backs up overriding native
savedconfigs under `/var/backups/agentoo/kernel-firmware/`, installs
`/etc/agentoo/firmware/<host>.list` to
`/etc/portage/savedconfig/sys-kernel/linux-firmware`, and rebuilds from source
(`--ignore-default-opts --usepkg=n --getbinpkg=n`). No automatic rollback hides
a failed build; check `agentoo kernel firmware` and the backup path if
interrupted.

- **Protected `._cfg` snapshots:** Portage may protect a newly generated
  versioned snapshot as a `._cfg` file; review it against the host list and
  accept via `dispatch-conf` before treating it as active.
- **Manual savedconfig precedence:** Portage searches `PF` (version+rev) → `P`
  (version) → `PN` (unversioned), checking target/build triplet dirs before
  plain category dirs. When manually rebuilding the *same* version with a
  revised unversioned list, move matching higher-priority versioned snapshots
  aside first, then run `sudo emerge --oneshot --usepkg=n '=sys-kernel/linux-firmware-VERSION'`.

## Explicit post-update kernel refresh

`linux-firmware` and `intel-microcode` use `-initramfs`, so package updates and
`agentoo kernel firmware apply` do **not** refresh boot images automatically.
Explicitly refresh both kernels (use each package's installed `VERSION`) and
cold-boot test both:

```sh
sudo emerge --config '=sys-kernel/gentoo-kernel-bin-VERSION'
sudo emerge --ask --oneshot --usepkg=n '=sys-kernel/gentoo-kernel-VERSION'
```

Do not use `kernel-install add-all` or `installkernel --all`—they do not select
Agentoo's custom package environment. On Bequiet, also rebuild
`x11-drivers/nvidia-drivers` after same-version custom kernel rebuilds (see
[Bequiet modules and NVIDIA](kernel.md#bequiet-modules-and-nvidia)).

## Maintenance triggers

| Change | Operator action |
| --- | --- |
| Distribution kernel update | Check firmware errors after boot; add any newly required names to the host list and reapply. |
| Custom kernel update | Review `CONFIG_EXTRA_FIRMWARE` when changing drivers/versions; installed trimming does not update embedded lists. |
| `linux-firmware` update | Review added/removed names and API versions (new files are not auto-selected), update host list, reapply, and refresh both kernels. |
| Host-list edit | Deploy, run `agentoo kernel firmware apply`, and refresh both kernels. |
| New hardware or driver | Review requirements first; restore broad coverage while investigating if needed. |

## Diagnose missing firmware

```sh
lspci -nnk
lsusb
sudo journalctl -k -b --no-pager | rg -i 'firmware|iwlwifi|bluetooth|sof|i915|xe|ivpu|nouveau'
modinfo -k KERNEL_RELEASE -F firmware DRIVER   # module kernels; check source MODULE_FIRMWARE for built-ins
zcat /proc/config.gz | rg '^CONFIG_EXTRA_FIRMWARE='
```

Repeat the journal check after exercising devices and after suspend/resume. A
failed initial request followed by a working fallback (e.g., older `iwlwifi` API)
is not a failure. Cross-check driver metadata, `WHENCE` in `linux-firmware`
source (for symlink targets), and successful loads; retain required aliases and
API alternatives.

## Restore broad coverage

One-time recovery rebuild:

```sh
sudo env USE="-savedconfig" emerge --oneshot --usepkg=n '=sys-kernel/linux-firmware-VERSION'
```

For persistent broad coverage on one machine, add
`sys-kernel/linux-firmware -savedconfig` to `/etc/portage/package.use/local`
and rebuild. Explicitly refresh both boot artifacts afterward.
