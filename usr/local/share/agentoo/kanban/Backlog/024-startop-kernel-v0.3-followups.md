# Build and validate startop kernel v0.3

Created: 2026-10-25
Status: Backlog

## Context

The shared driver configuration includes startop's recorded requirements, but
no v0.3 build/boot or functional acceptance has been recorded for this host.
Use its own boot parameters, firmware/microcode and fresh initramfs rather than
copying thinktop's embedded inputs. Keep the shared driver union and portable
CPU target. See the [shared follow-ups](027-shared-kernel-v0.3-followups.md).

## Remaining work

- [ ] Prepare host inputs, build/boot v0.3 and record the actual configuration,
  release, firmware loading and boot diagnostics. Keep a working recovery boot.
- [ ] Verify the built-in Sunplus camera `1bcf:2ced`: UVC binding, video nodes,
  real image capture, privacy controls and operation after suspend/resume.
  The earlier kernel lacked camera support; USB identification resolved driver
  selection but did not establish working capture.
- [ ] Test speakers, internal microphone, headset/jack detection, HDMI/DP and
  attached USB audio as used, including after suspend/resume. The recorded
  ALC233 codec ID `10ec:0235` uses the retained ALC269 family.
- [ ] Check SCU platform/PMC USB, PMC/PMT, low-power behavior and the used
  power, hotkey, brightness, backlight and firmware-settings interfaces.
- [ ] Compare sensor channels and GPIO/regulator/LED/clock bindings with a
  broad distribution kernel; then verify candidate monitoring and peripheral
  power/wake paths. Do not infer hardware absence from the older custom kernel.
- [ ] Validate recorded input devices, Bluetooth, Wi-Fi, external displays,
  docks, storage and suspend/resume, plus the applicable shared workload checks.
- [ ] Decide whether Linux raw SPI-NOR/MTD access is wanted for firmware-flash
  tools. A reference kernel binds `spi-nor`, while shared `MTD=n` already
  inherited the original thinktop baseline. Restore narrowly only if required;
  ordinary file/built-in firmware loading is independent.

## Evidence

Use the startop inventory dated 2026-10-24 and exact target-source mappings in
the shared build workspace. Camera identification is recorded in checkpoint21;
SCU/platform and hardware-monitoring evidence is indexed by checkpoint36.
The shared card identifies the workspace and cross-host validation requirements.
