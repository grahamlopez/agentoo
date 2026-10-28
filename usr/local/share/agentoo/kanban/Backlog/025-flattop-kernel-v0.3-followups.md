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

- [x] Explain the unbound charge-control device and inspect the existing charge
  limit using Framework's tool. The distribution boot explicitly reports
  `Framework charge control detected, preventing load`; this is intentional
  driver behavior. Operator queries confirm a 90% maximum and power readings
  consistent with charging paused at that limit; see evidence below.
- [x] Retain the current `CHARGER_CROS_CONTROL` exclusion. No kernel change is
  justified by these warnings or the observed charging behavior. The driver
  normally declines attachment when Framework's custom command is detected;
  forcing a successful probe initializes automatic charging with 0–100%
  thresholds. Revisit only if Linux threshold/charge-behavior controls are
  specifically needed, preserving or deliberately restoring intended limits.
- [ ] Track the separate CNVW ACPI missing-symbol bug. It occurs on both
  kernels; practical impact and a firmware fix remain unestablished.
- [ ] Consider BIOS 3.17 during routine firmware maintenance. It includes EC
  and security updates, but its release notes do not claim a fix for the
  USB-PD probe or CNVW errors. No update was performed in this investigation.
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
  After deployment, `agentoo kernel firmware apply` now performs the native
  savedconfig/backups/source-rebuild steps; the bare command reports status.
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

### Framework EC and charging review — 2026-10-27

Read-only inspection of the current custom-kernel boot and preceding
distribution boot confirms the same USB-PD probe and CNVW errors. The EC
registers successfully and acquires AML mutex `ECMT`. Installed BIOS is 03.16
(2026-03-06); EC sysfs reports `hx30_v0.0.1-94be25a`, firmware copy RO.

The USB-PD sequence (`No USB PD charging ports found`, `Unexpected number of
charge port count`, probe error -71) matches the longstanding Framework
interface issue tracked in [Framework issue #2](https://github.com/FrameworkComputer/SoftwareFirmwareIssueTracker/issues/2).
The installed kernel source returns `-EPROTO` when reported port counts fail
its consistency check. An [upstream patch discussion](https://lkml.iu.edu/2404.0/07644.html)
describes the unwanted messages on Framework systems. Treat this as a known
interface warning with no demonstrated functional impact here, not proof of
failed physical USB-C ports or failed battery protection. Actual charging,
USB-C or suspend symptoms would require separate investigation.

The preceding distribution boot's charge-control refusal is explained by the
[upstream driver](https://code.googlesource.com/linux/torvalds/linux/+/8abc1c8badc11c859bb4ba43211611347e59c55c/drivers/power/supply/cros_charge-control.c):
it detects Framework command `0x3E03` and returns `-ENODEV` by default. Normal
firmware charging remains available. Forced attachment can change charging
policy and is not needed merely to remove this message.

The operator supplied these queries from `framework_tool`:

```text
sudo framework_tool --charge-limit
Minimum 0%, Maximum 90%
Battery Cutoff: Unknown

sudo framework_tool --power
AC connected; battery connected
Charger Voltage: 16776mV
Charger Current: 0mA (0.00C)
Chg Input Current: 4748mA
Battery SoC: 89%; Charge level: 90%
Battery LFCC: 3058 mAh
Battery Capacity: 2754 mAh (46.198 Wh)
```

Independent sysfs inspection reports AC online, capacity 90%, status
`Not charging` and battery current 0. Together these are consistent with the
90% ceiling working at the time of inspection; persistence across reboots and
long-term behavior were not tested. The input-current field is distinct from
battery charging current. `Battery Cutoff: Unknown` alone does not establish
a fault. No evidence from this review indicates abnormal battery/power-system
stress; it is not a comprehensive battery-health assessment. Charge-limit
query syntax is documented in [Framework's examples](https://github.com/FrameworkComputer/framework-system/blob/main/EXAMPLES.md).

The separate ACPI failure references missing `^^RP28.PXSX.WIST` and aborts
`CNVW.IFUN` and `_DSM`. An [identical-signature report](https://community.frame.work/t/dmesg-acpi-bios-error-bug-could-not-resolve-symbol-rp28-pxsx-wist/72072)
exists for Laptop 12; it does not establish impact or a fix for this Laptop 13.
[Official Laptop 13 13th Gen BIOS 3.17 notes](https://resources.frame.work/downloads/laptop-13/13th-gen-intel-core/3.17/)
list a 2026-06-22 stable release with updated EC firmware and security fixes,
but no stated USB-PD probe or CNVW fix. No firmware, charging controls or kernel
settings were changed during this review. Detailed interface/workload checks
above remain open.

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
