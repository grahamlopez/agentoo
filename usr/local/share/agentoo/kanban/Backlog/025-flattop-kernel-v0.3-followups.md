# Resolve Framework controls and complete flattop kernel validation

Created: 2026-10-25
Status: Backlog

## Context

The shared configuration preserves flattop's positively identified Framework
EC functions. Flattop booted `6.18.57-agentoo-v0.4` on 2026-10-27, and the
operator confirmed everything works before and after suspend. Host boot inputs,
embedded firmware/microcode and the fresh minimal initramfs have initial boot
and functional acceptance. Retain the shared driver union and distribution
recovery kernel. Specialized tests and Framework investigations below remain
separate from that overall acceptance. See [shared follow-ups](027-shared-kernel-v0.3-followups.md).

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

- [x] Prepare tracked host specialization: `kernel/hosts/flattop.config` replaces
  inherited thinktop embedded firmware/microcode; `agentoo kernel config` checks
  local boot UUIDs and records the PARTUUID/mapping for the fresh initramfs.
  The embedded list uses successful distribution-kernel firmware loads on
  2026-10-27 (6.18.57-gentoo-dist-bin): i915 ADLP DMC/GuC and TGL HuC, AX211
  so-a0-gf-a0 API 89/PNVM, Intel Bluetooth 0040-0041 and regulatory data.
  CPU family 6/model 186/stepping 2 selects `intel-ucode/06-ba-02`.
  Current microcode is 0x6134, updated early from 0x6133. All selected payloads
  exist locally. This is preparation evidence, not custom-kernel boot acceptance.
- [x] Review a flattop native linux-firmware savedconfig list after broad-kernel
  evidence and custom-kernel functional acceptance. The explicit list has 34
  paths (22 regular files, 12 symlinks), 21,371,877 regular-file bytes, versus
  1,929,485,517 bytes in the broad package (projected 98.9% reduction).
  Selected installed files match the VDB checksums; aliases/targets and embedded
  linux-firmware coverage are retained. Portage's configuration API confirms
  Flattop/Thinktop enable savedconfig only for linux-firmware; generic/QEMU stay broad.
  The native installer and live trimming have not yet been exercised for Flattop.
- [ ] Install the Flattop list, move aside matching higher-priority native
  savedconfigs, rebuild linux-firmware from source and review the generated
  snapshot/distribution initramfs. Then cold-boot both kernels and repeat
  functional/suspend checks. The known RTL8156 monitor/KVM payload is retained;
  other external firmware-dependent peripherals are outside current scope.
- [x] Build/boot v0.4 with host inputs and record config, firmware loading and
  boot diagnostics; see acceptance below. Retain the distribution recovery kernel.
- [x] Operator functional acceptance before and after suspend (2026-10-27):
  "everything works before and after suspend." The preceding review identified
  camera, speakers/microphones/headphones and Bluetooth as functional checks.
  Individual specialist routes, privacy controls and external peripherals were
  not enumerated; the detailed checks below track those remaining coverage questions.
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

### Flattop v0.4 acceptance — 2026-10-27

Boot `9f10b8b307a845499051d3f6887c62fa` runs `6.18.57-agentoo-v0.4`.
The running config's ten embedded firmware entries match the tracked flattop
profile; `MODULES=n`, initramfs compression NONE and owner UID/GID 0 are retained.
Boot arguments contain the local root/LUKS UUIDs and `crypt_root`, with baseline
console/logging/discard policy and no imported dracut arguments.

Early microcode updated 0x6133 to 0x6134. i915 DMC/GuC/HuC, AX211 API 89/PNVM
and Bluetooth SFI/DDC initialized successfully. Wi-Fi acquired a DHCP lease.
The UVC camera binds and exposes capture devices, and the IDT 92HD95 codec is
detected. Root and home mounted and graphical startup completed. No unresolved
firmware-loading failure or kernel crash trace appeared in the initial review;
kernel taint was 0. The operator subsequently confirmed functional operation
before and after suspend; post-resume logs were not independently reviewed here.

The USB-PD charger probe error -71 and ACPI CNVW errors also occur on the preceding
distribution-kernel boot. EC LPC, hwmon, LEDs, keyboard backlight and sysfs bind;
charge-control and USB-PD charger remain unbound. Existing missing tpm2_id,
RTKit and BlueZ userspace warnings also occur on the distribution kernel.
These observations do not resolve optional charging controls or specialist
workloads. Installed firmware remains broad; savedconfig trimming is still open.

Framework EC/charging rationale: workspace checkpoint11 and its recorded runtime
follow-ups. Camera identification: checkpoint21. Trace Hub and other held
reductions: checkpoint49. The shared card gives the workspace location.
