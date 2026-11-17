# Thinktop kernel follow-ups

Created: 2026-10-25
Updated: 2026-11-17
Status: Backlog

## Accepted runtime evidence

Thinktop booted `6.18.57-agentoo-v0.3`. Read-only checks found an untainted
kernel with 3,068 enabled symbols and no module-valued symbols. The running
configuration matched the build directory; its only change from the final
audited configuration was the fresh v0.3 initramfs path.

The operator confirmed working internal and external cameras, microphones and
speakers, including after suspend/resume. These tests have passed on thinktop;
they do not establish acceptance on the other hosts or every audio route.

## Remaining work

- [ ] Supply `rtl_nic/rtl8156b-2.fw` for the RTL8156 dock Ethernet adapter.
  It is absent on disk and failed to load under both v0.2 and v0.3. Review
  installed savedconfig selection and early/built-in firmware availability;
  then verify link speed, connectivity, reconnect and resume. Driver binding
  alone does not establish wired operation. See firmware maintenance (completed card 018).
  The tracked Thinktop savedconfig list was corrected on 2026-10-27 while
  preparing Flattop's list; application/rebuild on Thinktop and wired validation
  remain outstanding. The same payload is retained for Flattop's possible use
  of the shared monitor/KVM.
- [ ] Follow up the BERT diagnostic: this boot reports one firmware-provided
  error record from a previous boot, but skips printing its contents. Record
  recurrence and obtain the full record if it repeats or instability appears.
  No cause or hardware failure has been established from the available log.
- [ ] Test remaining used audio routes: headphones/headset detection and
  HDMI/DP audio. Dummy regulator and HDMI converter warnings also appeared
  under v0.2; do not treat them as demonstrated v0.3 regressions.
- [ ] Verify used external displays, brightness/DDC controls, dock hotplug,
  Bluetooth mouse reconnect/resume and recorded keyboard/input functions.
- [ ] Verify ThinkPad ACPI, think-lmi and Lenovo Other Mode interfaces, used
  hotkeys/platform profiles and the host-specific platform/monitoring checks
  in the [shared card](027-shared-kernel-v0.3-followups.md).
- [ ] Record results for the shared networking, storage, virtualization,
  security and diagnostics checks as those workloads are exercised.

## Boot-log follow-ups from v0.5 acceptance

Reviewed the 2026-11-17 11:24 boot of `6.18.62-agentoo-v0.5` after its same-version
rebuild, the preceding v0.5 boot, and the retained v0.4.1 boot beginning
2026-11-16 19:59 (boot ID `12696bfdfd4c4192a766ad21fb9c5691`). The findings below
also occur with v0.4.1; they are not established regressions from the native
gentoo-kernel conversion. No panic, kernel Oops, Btrfs error or storage I/O
failure was found in the reviewed logs. The operator accepted the custom v0.5
kernel; see the [accepted native workflow](../../docs/kernel.md). Completed card
051 is retained in Git history through the [completed index](../README.md#completed).

- [x] **Check and repair the ESP filesystem.** `/dev/nvme1n1p1`, mounted
  at `/boot`, repeatedly reports `Volume was not properly unmounted` and asks
  for fsck. This warning also occurs with v0.4.1, and the preceding shutdown
  logs a successful `/boot` unmount. On 2026-11-17 the operator installed
  dosfstools and reloaded systemd; the generated mount unit now requires native
  systemd-fsck for this ESP, matching fstab check-pass 2. An unmounted read-only
  check found only the dirty flag and the corresponding boot-sector/backup
  difference at byte 65 (01/00), with no reported file-chain/allocation errors.
  The operator ran fsck.fat -a while unmounted; a subsequent fsck.fat -n was
  clean, with neither warning and unchanged file/cluster counts. `/boot` was
  remounted. The subsequent 2026-11-17 11:34 binary fallback boot ran native
  systemd-fsck successfully with a clean result; no FAT warning recurred.
- [ ] Include dosfstools in target-installation prerequisites for native ESP
  checking. The repaired host now has the package and the expected generated
  mount dependency; ensure new installations receive it as well.
- [ ] **Investigate SPD5118 resume errors.** Both the v0.4.1 boot and the
  preceding v0.5 boot report `spd5118 17-0050: Failed to write b = 0: -6`,
  `spd5118_resume returns -6`, and failed asynchronous device resume. The device
  identifies as a DDR5 temperature sensor; overall s2idle resume completes.
  Check sensor availability before/after suspend and recurrence, then determine
  whether a driver/firmware correction is needed. This is not evidence of a
  memory-integrity failure. The latest reviewed boot had no such resume event.
- [ ] **Investigate Intel PMC telemetry availability.** Both kernel versions
  report `pmc_core: couldn't get DMU telem endpoint -19`. Review platform support
  and power/s2idle measurements alongside the monitoring checks above. The
  message alone does not establish broken suspend or excessive power use.
- [ ] **Resolve the missing TPM udev helper.**
  `/usr/lib/udev/rules.d/60-tpm2-id.rules` invokes `tpm2_id identify`, but
  `/usr/lib/udev/tpm2_id` is absent. Review the owning package and native USE/rule
  policy for the intended TPM features; remove the rule/helper inconsistency
  through its appropriate configuration owner. Do not infer TPM hardware failure
  from the failed helper execution.
- [ ] **Investigate D-Bus supplementary-group handling.** Boot logs include
  `dbus-daemon: Failed to drop supplementary groups: Operation not permitted`
  on both versions. Check the emitting service's credentials, capabilities and
  sandbox policy, and establish the impact before changing privilege settings.

Other reviewed output provides context, rather than additional demonstrated
kernel failures:

- AMD KVM/CCP, IT87 and ChromeOS driver probes encounter absent hardware in the
  shared built-in driver union. Preserve other hosts' driver requirements when
  considering logging/configuration cleanup.
- Wi-Fi requests `iwlwifi-bz-b0-fm-c0-c99.ucode`, then successfully loads
  `iwlwifi-bz-b0-fm-c0-101.ucode`. The failed first request is followed by a
  working fallback, not an established wireless initialization failure.
- PNP/resource overlap, i8042 Keylock, HID feature-report and audio dummy-regulator/
  deferred-binding warnings also predate the conversion. Audio firmware loads;
  use actual hardware symptoms and comparison evidence to prioritize further work.
- PipeWire/WirePlumber and portal RTKit warnings reflect an unavailable optional
  service. Inspect scheduling if audio drops out under load; do not add a service
  solely to suppress logs. See [audio guidance](../../docs/audio.md).
- The missing `i2c_dev` error is resolved by package-owned built-in indexes and
  passed the rebuilt v0.5 reboot check; do not track it as an open boot failure.

Kernel source timestamps place many probe warnings before `/init` starts at
about 5.39 seconds; encrypted-root Btrfs mounting occurs around 35.39 seconds.
The ESP warning occurs later, around 37.21 seconds. Journal collection timestamps
batch early messages after unlock, so use `_SOURCE_MONOTONIC_TIMESTAMP` when
distinguishing pre-unlock messages from later service output.

## Evidence and related work

Local first-boot evidence is in
`~/local/agentoo-build/kernel/6.18.57-agentoo-v0.3/inventory/thinktop-v0.3-first-boot-20261025/`,
especially `REVIEW.txt` and `first-boot-findings.json`. The review includes the
operator's later camera/audio/suspend acceptance.

[Initramfs keyboard policy](../Open/020-initramfs-keyboard-policy.md) remains separate
work; a fresh initramfs alone does not establish that its keyboard policy was
corrected. Common validation and held reductions belong to the
[shared follow-ups](027-shared-kernel-v0.3-followups.md).
