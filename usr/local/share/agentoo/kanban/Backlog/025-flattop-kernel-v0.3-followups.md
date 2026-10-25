# Resolve Framework controls and validate flattop kernel v0.3

Created: 2026-10-25
Status: Backlog

## Context

The shared configuration preserves flattop's positively identified Framework
EC functions. No v0.3 build/boot or functional acceptance is recorded here.
Prepare flattop-specific boot inputs, firmware/microcode and fresh initramfs;
retain the shared driver union. See [shared follow-ups](027-shared-kernel-v0.3-followups.md).

## Framework charging and EC investigation

- [ ] Investigate existing charging tools/interfaces, desired charge limits,
  EC firmware/API compatibility and why the collected `cros_charge_control`
  platform device was unbound despite its driver being loaded.
- [ ] Decide whether to enable `CHARGER_CROS_CONTROL`, deliberately left off.
  Target source normally declines attachment when a Framework-specific command
  is detected; successful probe initializes automatic charging with 0–100%
  thresholds. Inspect first and preserve or deliberately restore intended
  limits during any eventual test. Normal firmware charging/ACPI reporting
  remain available; Linux threshold/charge-behavior controls from this driver
  are an unresolved capability, not a proven-safe permanent removal.
- [ ] Verify EC LPC binding, expected fan/temperature channels, LEDs, keyboard
  backlight, EC character-device/sysfs interfaces and USB-PD information/logging.
  Do not change EC controls merely to inspect their presence.

## Candidate build and validation

- [ ] Build/boot v0.3 with host inputs and record config, firmware loading and
  boot diagnostics, retaining a working recovery boot.
- [ ] Test built-in Realtek UVC camera `0bda:5634`: binding, actual capture,
  privacy controls and resume. Its earlier USB video interfaces were unbound;
  the old ov13858 module/ACPI declarations did not establish its capture path.
- [ ] Test IDT/Sigmatel audio, speakers/microphones/headsets, used HDMI/DP/USB
  audio and all relevant routes after suspend/resume. AVS alternatives remain.
- [ ] Validate radio/consumer keys, keyboard backlight, brightness, touchpad,
  external displays/docks, Wi-Fi/Bluetooth, storage and peripheral wake paths.
- [ ] Compare full distribution-kernel sensor/GPIO/regulator/LED/clock coverage
  and exercise the applicable workloads from the shared card.
- [ ] Resolve optional Trace Hub/STM use before revisiting its retained driver
  chain: ACPI `INTC1001` matches target support but was status0/unbound. General
  perf/BPF/ftrace are independently preserved.
- [ ] Decide whether raw Linux SPI-NOR/MTD flash access is needed. It is absent
  from the shared baseline, independently of ordinary firmware loading.

## Evidence

Framework EC/charging rationale: workspace checkpoint11 and its recorded runtime
follow-ups. Camera identification: checkpoint21. Trace Hub and other held
reductions: checkpoint49. The shared card gives the workspace location.
