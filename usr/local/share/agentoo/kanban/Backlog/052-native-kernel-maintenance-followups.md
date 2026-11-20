# Validate and simplify native kernel maintenance

Created: 2026-11-17
Status: Backlog

## Accepted foundation

Thinktop's custom gentoo-kernel build `6.18.62-agentoo-v0.5` and binary fallback
kernel `6.18.62-gentoo-dist-bin` boot under Secure Boot. The custom kernel passed
operator hardware acceptance and a same-version rebuild/reboot. Package-owned
kmod indexes correctly identify built-in drivers. Both firmware packages install
payloads without automatic initramfs maintenance; the operator explicitly
refreshes each boot artifact. Native Portage remains the build/install interface.

The conversion is completed card 051; its final evidence is retained in Git
history and the [completed index](../README.md#completed). This card carries
future maintenance and optional development work, not missing Thinktop first-boot
acceptance. See the [kernel guide](../../docs/kernel.md).

## Remaining work

- [ ] Validate a subsequent kernel version update with native Portage. Review
  Kconfig changes, resolved shared/host/local policy, prepared-tree discovery,
  EFI paths/signatures and selection of the custom tree. Refresh the binary
  fallback separately and preserve a tested recovery entry. No recurring Agentoo
  preparation command or per-operation selector flipping is needed.
- [ ] Reduce `/etc/kernel/config.d/10-agentoo.config` to deliberate policy.
  It still resembles a complete resolved snapshot and includes derived settings.
  Remove compiler/Kconfig-derived material and settings that do not express an
  intentional policy, while retaining explicit enabled/disabled choices that
  protect requirements across Gentoo default changes. Do not blindly delete
  every entry reported redundant during merging. Prove the resolved config is
  semantically unchanged for the accepted kernel, preserving the shared driver
  union and host firmware; review and document intentional differences separately.
- [ ] Audit native binary packages before using or distributing locally built
  custom kernel packages. Use disposable signing identities and inspect archive
  contents, environment/build metadata and logs for private keys or PINs. The
  staged/installed-image audit found no signing_key.pem, but does not establish
  the safety of the binary-package format. Source builds with --usepkg=n remain
  the accepted workflow until this audit is complete.
- [ ] If detached incremental compilation/installation is wanted, validate the
  native full-source/output-directory loop, including fresh embedded archive
  ownership, signing, install safety and rollback expectations. Fragment edits,
  menuconfig/direct .config exploration and delta promotion are already described
  and tested; full detached build/install acceptance is separate. Do not add an
  Agentoo workspace lifecycle or build wrapper.
- [ ] Remove the duplicate Agentoo i2c-dev module-load declaration after confirming
  ddcutil's packaged declaration supplies the binary fallback requirement. Keep
  built-in index generation; masking module loading is not the indexing fix.

Bequiet's native conversion passed Secure Boot/NVIDIA, hardware and refreshed
binary recovery acceptance on 2026-11-17; see
[hosts/bequiet.md](../../docs/hosts/bequiet.md#kernel-and-secure-boot). Validate a
same-version custom rebuild followed by NVIDIA rebuilding and reboot, then a
subsequent version update including native external-module dependency handling.
Other module-enabled conversions remain deferred; shared/fleet
requirements stay in [card 027](027-shared-kernel-v0.3-followups.md). Thinktop's
older boot/power/service findings and target dosfstools provisioning stay in
[card 023](023-thinktop-kernel-v0.3-followups.md). Card 020’s MICMUTE workaround
retirement was accepted after the controlled cold-boot test recorded in the
[kernel guide](../../docs/kernel.md).

## Completion

Record evidence for work actually performed. Optional experiments may be declined
explicitly; do not infer authorization for live builds, firmware changes or other
hosts from this backlog entry. Keep policy in native layers and remove superseded
interfaces rather than retaining compatibility paths.
