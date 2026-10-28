# Complete thinktop kernel v0.3 follow-ups

Created: 2026-10-25
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
  alone does not establish wired operation. See [firmware maintenance](../Completed/018-host-firmware-savedconfig.md).
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

## Evidence and related work

Local first-boot evidence is in
`~/local/agentoo-build/kernel/6.18.57-agentoo-v0.3/inventory/thinktop-v0.3-first-boot-20261025/`,
especially `REVIEW.txt` and `first-boot-findings.json`. The review includes the
operator's later camera/audio/suspend acceptance.

[Initramfs keyboard policy](020-initramfs-keyboard-policy.md) remains separate
work; a fresh initramfs alone does not establish that its keyboard policy was
corrected. Common validation and held reductions belong to the
[shared follow-ups](027-shared-kernel-v0.3-followups.md).
