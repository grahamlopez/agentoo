# Startop power increase after resume

Investigation begun 2026-11-03 on Startop, a Star Labs StarFighter with an
Intel Core Ultra 9 285H, i915 graphics, AX210 Wi-Fi, two NVMe drives, coreboot
26.08 (BIOS date 2026-08-13), and kernel `6.18.60-gentoo-dist-bin`.

Fresh-boot idle draw is approximately 4.8–5.2 W. After suspend/resume it rises
to approximately 6.2 W and CPU package idle stops progressing beyond C2.
This reproduces with S3, Linux s2idle, and firmware-enabled Modern Standby.
A 1.024 microsecond SOUTHPORT_A latency request appears after resume.
Temporarily removing the unused second SSD at `0000:59:00.0` clears the valid
request and restores package C6/C8 accumulation, isolating the failure to that
SSD or its root-port path through `0000:00:1c.0`. The responsible component
and exact mechanism remain unresolved.

## Read before interpreting the logs

**Do not restart the investigation from the GSC error or the USB resume error.**
The early logs suggested plausible causes, but controlled experiments below
disproved a graphics-only explanation and showed that enabling ME and Modern
Standby does not fix the remaining power increase. Repeating these routes
requires a new reason, such as a kernel or firmware change.

| Hypothesis prompted by early evidence | Experiment and result | Conclusion for further investigation |
| --- | --- | --- |
| GSC proxy initialization failure causes the entire increase | With ME and firmware Modern Standby enabled, the MEI proxy binds and GSC reports `RUNNING` before and after resume. Draw still rises from 5.20 to 6.20 W. | Disproved as a necessary cause of the remaining increase. Do not treat the earlier `LOAD FAIL` as the explanation for all results. |
| GT1 staying awake explains the entire increase | S3 leaves GT1 at 0% RC6 residency, but both forms of s2idle preserve approximately 100% GT1 RC6 residency while draw still rises and package C6/C8 stop. | GT1 failure is an additional S3 symptom, not a sufficient explanation of the shared regression. Its separate power cost was not isolated. |
| Missing or disabled GPU sleep support | RC6 is enabled; GT0 sleeps approximately 98% in both states, and GT1 sleeps approximately 100% in the s2idle tests. DMC firmware loads successfully. | Do not infer that GPU sleep is globally disabled from PowerTOP's GPU display. |
| S3 alone is responsible | Fresh boots were tested separately with S3 and s2idle. Both lose deeper package idle after resume. | Switching only `/sys/power/mem_sleep` to s2idle does not fix the increase. |
| ME disabled is the sole cause | Enabling ME while leaving firmware Modern Standby disabled gives 5.09 W before and 6.28 W after S3; GSC still fails in that test. | Enabling ME alone did not fix either the measured power regression or GSC initialization in that configuration. |
| The Linux s2idle test was invalid because firmware Modern Standby was disabled | Enable both ME and firmware Modern Standby. Journal confirms low-power S0 idle is the default and suspend uses s2idle. GSC works and both GPU tiles sleep, but draw increases and package idle remains blocked. | Firmware-supported Modern Standby was tested and did not fix the remaining regression. |
| USB controller remains awake after its resume error | `00:0d.0` logs `xHC error in resume, USBSTS 0x401, Reinit`, but is runtime-suspended afterward. Captured PCI runtime states match before and after. | The error alone does not demonstrate a sustained blocker; an undisclosed hardware-state problem is not excluded. |
| General PowerTOP tunables are missing | `powertop --auto-tune` changed PCI runtime PM, disabled the NMI watchdog, and changed writeback timeout. Quiet reports measured 6.16 W before and 6.22 W after. | No demonstrated benefit. Do not propose persisting auto-tune as an established fix. |
| Wi-Fi radio activity supplies the blocking request | Temporarily soft-block Wi-Fi after firmware Modern Standby resume. Draw falls from 6.20 to 5.73 W, but the request remains and package idle does not recover. | Radio-off saving is real in this sample but does not fix the blocker. Wi-Fi PCIe hardware is not excluded: the device remained runtime-active. |
| PCIe ASPM is globally disabled | PCI captures show L1 and L1.2 enabled on Wi-Fi and both SSD links; relevant settings remain unchanged across resume. | Do not recommend blanket ASPM enabling or `pcie_aspm=force` from these captures. Enabled settings do not prove actual link residency. |
| Resume loses the secondary SSD's configured NVMe power policy | Native NVMe captures show identical APST tables and Power Management feature value 4 before and after resume on the secondary SSD. Draw rises 5.31 to 6.62 W and the package-idle failure reproduces. | No missing APST configuration to restore was demonstrated. Matching readback does not prove correct internal hardware behavior or LTR updates. |
| A disabled PSR setting or missing DMC firmware prevents display power saving | Panel reports `PSR = no, Panel Replay = no`; `enable_psr` and `enable_dc` are both automatic (`-1`). DMC 2.23 loads. | No evidence for forcing PSR. Zero DMC transition counters alone did not identify the shared resume blocker. |

## Measurements and method

The user initially watched `watch -n 2 agentoo power` for about 60 seconds:
fresh-boot readings alternated between 4.3 and 5.3 W in both console and
Hyprland; after resume readings varied between 5.9 and 6.9 W. These are
observed ranges, not averaged captures.

Subsequent captures use the archived `startop-power-snapshot.py`: ten battery
current-times-voltage samples spaced two seconds apart, GPU RC6 counter deltas,
RAPL energy deltas, CPU package counter snapshots, and PCI runtime states.
The detailed version adds debugfs and `lspci -vv` after the measurement to avoid
waking devices during idle sampling. Each before/after pair listed below has
the same boot ID; S3 and s2idle comparisons used separate fresh boots.
The controlled display setting was 3840×2400 at 60 Hz; backlight was reported
at 10% in the initial PowerTOP captures. Brightness, refresh rate, peripherals,
and applications were to be kept consistent within each pair.

| Capture pair or test | Before W | After W | GT1 RC6 before → after | Package state after resume |
| --- | ---: | ---: | --- | --- |
| Initial S3 pair, `power-before.json` / `power-after.json` | 4.764 | 6.204 | 99.97% → 0% | C2 accumulates; C3 through C10 zero |
| Initial s2idle capture, `power-after-s2idle.json` | No same-boot baseline | 6.234 | After: 99.97% | C6/C8 counters no longer advance |
| Detailed S3 pair | 4.925 | 6.279 | 99.99% → 0% | C2 accumulates; C3 through C10 zero |
| Detailed s2idle pair, firmware Modern Standby not enabled | 4.980 | 6.230 | 99.96% → approximately 100% | C6/C8 counters no longer advance |
| ME enabled, firmware Modern Standby disabled, S3 | 5.089 | 6.284 | 99.97% → 0% | C2 accumulates; C3 through C10 zero |
| ME and firmware Modern Standby enabled, s2idle | 5.197 | 6.197 | 99.95% → 99.96% | C6/C8/C10 counters no longer advance |
| Wi-Fi soft-blocked after the preceding resume | 6.197 | 5.734 | After: 100% | C6/C8/C10 counters still do not advance |
| Secondary SSD temporarily removed after resume | Earlier same-boot resumed baseline: 6.197 | 5.068 | After: approximately 100% | C6/C8 accumulation returns |
| Secondary SSD detected again after PCI rescan | Detached: 5.068 | 8.332 | After: 99.96% | C6/C8 do not advance; ASPM now disabled on this path |
| Fresh boot and resume with native NVMe diagnostics | 5.315 | 6.616 | 99.97% → 99.94% | C6/C8/C10 do not advance after resume; APST tables unchanged |

RC6 deltas near 100% can slightly exceed 100% because of counter/read timing
(one capture reports 100.02%). Package counters can reset across S3; compare
their increments within each capture, not absolute values across suspend.
For firmware Modern Standby, C10 had accumulated between captures, but did
not advance during the post-resume idle measurement. This does not establish
continuous inability to enter C10 at every point during the boot.

PowerTOP reported approximately 1.6–1.7% CPU usage. Its GPU section displayed
a malformed GPU identifier and 0% RC6 despite direct kernel counter evidence
of sleep. Its package labels also do not establish actual hardware package
residency. Use the captured counters to assess the GPU tiles and CPU package.

The early ad hoc display tests were inconclusive: the first `hyprctl keyword`
command was rejected by this Lua-based Hyprland, and later 60 Hz / display-off
samples during active investigation were noisy. Do not use those samples to
claim that refresh rate or backlight consumes no power. The quiet reboot and
resume comparisons establish the regression more clearly.

## Shared latency change

Every detailed before/after pair, including working GSC with firmware Modern
Standby enabled, shows this change:

```text
PMC0:SOUTHPORT_A
Before resume: LTR RAW 0x0
After resume:  LTR RAW 0x84208420
               Non-Snoop 1024 ns, Snoop 1024 ns, LTR_IGNORE 0

PMC0:AGGREGATED_SYSTEM
Before resume: LTR RAW 0x2010080
After resume:  LTR RAW 0x40201
```

The request persists with Wi-Fi soft-blocked. PCI runtime states and ASPM
settings remain unchanged across the controlled captures. Individual endpoint
LTR capabilities are not a mapping from this PMC row to a specific device.
The secondary-SSD removal experiment below associates this blocking request
with the path through `0000:00:1c.0` to `0000:59:00.0`. This is experimental
isolation, not a complete architectural mapping of the PMC row. It does not
distinguish a request generated by the SSD from root-port or firmware state.

The kernel reports `Invalid LTR scale factor` when reading some rows, and
initialization reports `couldn't get DMU telem endpoint -19`. The detailed
`lpm_status` and `lpm_requirements` reads return null. These limit interpretation
of PMC telemetry; neither warning independently proves the cause. The repeated
SOUTHPORT_A transition and its removal track loss and recovery of deeper
package idle. Removing the SSD changes more than the latency request alone,
so that observation does not independently prove the latency field is the
sole mechanism.
No LTR-ignore override or PCI register modification has been tested.

## Secondary SSD isolation

After firmware-enabled Modern Standby resume, the unused secondary NVMe
controller at `0000:59:00.0` was temporarily removed from the PCI tree. Its
parent is `0000:00:1c.0`; its NVMe model string is `Samsung SSD 990PRO 1TB`
and PCI identity is MAXIO `1e4b:1602`. The system disk is the separate 970 EVO
at `0000:02:00.0`, holding `/`, `/home`, and `/boot` through its partitions
and encrypted root mapping. Before removal, the secondary drive had no
mounts, swap, block-device holders, or users reported by root-level `fuser`.

The test wrote `1` to that secondary controller's PCI `remove` file, waited
15 seconds, ran the 20-second collector, and used an exit trap to write `1`
to `/sys/bus/pci/rescan`. `secondary-ssd-detached.json` confirms the controller
was absent throughout the capture. Sysfs inspection afterward confirms it
was detected again at `0000:59:00.0`.

During removal, battery draw averaged 5.068 W. Package C6 increased by
306,319 counter units and C8 by 15,469,330; both GPU tiles were approximately
100% in RC6. SOUTHPORT_A changed from `0x84208420` with a valid 1024 ns
requirement to `0x08420842`, decoded as no valid snoop/non-snoop latency
requirement. `LTR_IGNORE` remained zero. This was not a latency-ignore test.

This is the first intervention that restored deeper package idle after
resume. A wattage decrease alone could have been the removed drive's own
consumption; the restored C6/C8 accumulation and changed request additionally
implicate that PCIe path in the package-idle regression. The historical
6.197 W resumed baseline is from the same boot, not an immediately adjacent
control sample. The removed drive's power cost and the package-idle saving
have not been separated.

The follow-up `secondary-ssd-restored.json` shows detection was restored,
but the original link power configuration was not. Draw averaged 8.332 W,
GT1 slept 99.96%, and package C6/C8 did not advance. SOUTHPORT_A reported
`0x88428842`, a valid 67,584 ns request, rather than the original 1024 ns
request. More importantly, `lspci` shows ASPM disabled and all four L1
substate enables cleared at both the SSD and its `00:1c.0` root port. Those
features were enabled in the original post-resume capture. Endpoint LTR
capability values also changed from 15,728,640 ns to zero.

Thus PCI rescan restored device detection but did not restore equivalent
power policy. The 8.332 W result is a new configuration and must not be
interpreted as simple recurrence of the original approximately 6.2 W fault.
Reboot before further comparisons to restore the boot-time link setup.
Do not use remove/rescan as an established workaround or promise that it
fully restores power settings. The positive removal result still implicates
this device path; a negative secondary-drive test would have left the system
drive unresolved. No system-drive detachment is needed to follow this lead.

## Native NVMe power settings

After installing nvme-cli and rebooting to restore the original link setup,
`nvme-before.json` and `nvme-after.json` capture the same boot, with ME and
firmware Modern Standby left enabled. Battery draw is 5.315 W before and
6.616 W after resume. Both GPU tiles continue sleeping, package C6/C8/C10
stop advancing during the resumed idle capture, and SOUTHPORT_A changes
from no request to `0x84208420` (1024 ns). ASPM and L1 substate settings
remain enabled; the earlier post-rescan ASPM disablement is not present.

All native Identify Controller and Get Feature commands succeeded:

| Controller | Identity | Power Management feature before → after | APST readback |
| --- | --- | --- | --- |
| `02:00.0`, system SSD | 970 EVO, firmware `2B2QEXE7` | 0 → 4 | Identical; enabled, entries 0–3 transition to state 4 after 100 ms |
| `59:00.0`, secondary SSD | Model string 990PRO, MAXIO `1e4b:1602`, firmware `SN13124` | 4 → 4 | Identical; enabled, entries 0–2 transition to state 3 after 100 ms, entry 3 to state 4 after 2000 ms |

Identify Controller output is identical within each pair. The secondary
controller advertises states 3 and 4 as non-operational, with respective
entry/exit latencies of 5000/10000 and 8000/45000 microseconds. Kernel
`nvme_core.default_ps_max_latency_us` is 100000 in both captures. Advertised
power maxima are capabilities, not measured device consumption. The system
SSD's Power Management readback change does not establish it as the culprit;
the positive secondary-device isolation remains the stronger evidence.

These reads reject a lost or changed secondary-controller APST table as the
demonstrated explanation. They cannot tell whether the controller actually
enters the advertised states or emits the correct runtime LTR messages.
Do not write a different power policy merely because package sleep is blocked:
there is no observed secondary-controller configuration difference to restore.

The next useful comparison is another kernel with firmware, disks, and power
settings held constant, using the same before/after collector. Only
`6.18.60-gentoo-dist-bin` was installed at this check. Kernel selection and
installation remain pending. A successful comparison would narrow software
version dependence; failure on another kernel would not alone prove a
firmware or hardware defect. The existing reproducer and captures are also
sufficient to prepare a report for Star Labs or Linux NVMe/PCI maintainers;
no report has been sent.

## Graphics and firmware details

With ME disabled, boot logs show GSC firmware loading followed approximately
20 seconds later by:

```text
GT1: GSC proxy component didn't bind within the expected timeout
GT1: GSC proxy handler failed to init
```

The post-S3 debug report shows GSC `LOAD FAIL`, GT1 in RC0 with forcewake
request `0x10000`, and RC6 enabled. Before S3, GT1 is in RC6 with forcewake
`0x0`. The same GSC failure status is present before suspend, when idle power
is low. The driver status is therefore not itself proof that GT1 was awake
before suspend.

[i915 GSC code](https://raw.githubusercontent.com/torvalds/linux/v6.18/drivers/gpu/drm/i915/gt/uc/intel_gsc_uc.c)
marks firmware failed when initial proxy setup fails and skips starting
firmware already marked in error. That suggested a resume failure chain,
but this mechanism was not traced in the running kernel. The successful GSC
experiment demonstrates that it cannot explain the whole power regression.

Enabling ME alone left GSC failed and no MEI bus visible in that test.
Enabling firmware Modern Standby as well produced a visible MEI proxy binding
to i915, GSC `RUNNING` before and after suspend, both GPU tiles sleeping,
and a boot log stating `Low-power S0 idle used by default for system suspend`.
The tests establish these configurations' outcomes, not why ME exposure
differed between them.

The firmware menu initially showed only a lid-switch policy with `Normal`,
`Sleep only`, and `Disabled`; it was set to `Normal`. These choices do not
select S3 or S0ix. Enabling ME exposed a separate `Modern Standby (S0ix)`
toggle, initially disabled. It was then enabled for the final firmware test.
[Star Labs documents the separate settings and the ME requirement](https://ch.starlabs.systems/pages/coreboot-options).
Selecting Linux `s2idle` while that firmware option is disabled is a different
experiment from firmware-enabled Modern Standby; both have now been tested.

Last observed configuration: ME enabled, firmware Modern Standby enabled,
Linux `[s2idle] deep`, panel at 60 Hz, and Wi-Fi restored by the soft-block
test's exit trap. No permanent power workaround was installed.

## Historical baseline

The legacy `gentoo-notes/README.md`, under “starfighter quirks and todos”,
records 4.2 W on a minimal console with very low backlight, 5–5.5 W in
Hyprland, approximately 0.5 W more with a USB mouse, and an unresolved
1.5 W increase after suspend/resume. Thus the remembered 4 W figure was
not a documented matching desktop baseline, and the resume problem predates
the current Agentoo install.

Legacy `gentoo-configs/usr/local/sbin/set-power-profile.sh` used battery EPP
`balance_power`, `max_perf_pct=40`, `no_turbo=1`, NVMe runtime PM `auto`, and
`iw ... set power_save on`. Current initial settings were `balance_performance`,
100%, turbo enabled, and no explicit Wi-Fi power-save policy established.
The legacy phase11 kernel enabled power-efficient workqueues; the current
runtime parameter was `N`. These differences have not been individually
tested and must not be represented as measured fixes. PowerTOP auto-tune
does not reproduce that legacy CPU profile.

The legacy kernel plan documents Gentoo 6.18.8, i915, and both the 970 EVO and
the drive identifying itself as a 990 PRO already installed. The current
second drive's PCI controller identifies as MAXIO MAP1602 despite its NVMe
model string; neither identity observation establishes its role in the issue.

## Preserved evidence and next investigation

[The evidence archive](startop-power-evidence.tar.gz) preserves the original
captures and the collector used for them, with their boot IDs and raw output:

- `power-before.json`, `power-after.json`, `power-after-s2idle.json`
- `detailed-before-s3.json`, `detailed-after-s3.json`
- `detailed-before-s2idle.json`, `detailed-after-s2idle.json`
- `me-enabled-before.json`, `me-enabled-after-s3.json`
- `me-modern-standby-before.json`, `me-modern-standby-after.json`
- `wifi-blocked.json`, `secondary-ssd-detached.json`,
  `secondary-ssd-restored.json`, `gpu-after-resume.txt`, `startop-power-snapshot.py`
- `nvme-before.json`, `nvme-after.json`, `startop-power-snapshot-with-nvme.py`

The original PowerTOP HTML and early text reports were in `/tmp` and were
lost across reboot. Their observations above are retained from the session;
the archive does not contain those original reports. The legacy repositories
were read under `~/local/legacy/{gentoo-notes,gentoo-configs}` and are not
included in the archive. Root-level working copies of captures were left intact.

Continue with the experimentally isolated secondary SSD and its root port.
The clean reboot and native NVMe readback comparison are now complete; no
secondary-controller power configuration change was found across resume.
Distinguish firmware state restoration from endpoint driver behavior through
a kernel comparison and source investigation. The secondary SSD was detached
once and detected again; link power policy differed afterward. The system SSD
has not been detached. No latency requirement override has been performed.

The working root-level collector was extended to use `nvme-cli`
when installed, reading Identify Controller, current Power Management
(feature `0x02`), and current Autonomous Power State Transition (`0x0c`)
for both controllers after idle sampling. Controller PCI paths and firmware
versions are included so device numbering changes do not confuse comparisons.
The archive preserves the earlier collector and the extended version as
`startop-power-snapshot-with-nvme.py`, used for the native NVMe pair. No NVMe
feature values have been written as part of this investigation.

If a future kernel or firmware change motivates retesting, use a fresh boot
for each sleep mode, save before/after captures, and compare package counter
increments as well as watts. Preserve the working-GSC s2idle case as a control
so a recurring S3 graphics failure is not mistaken for the shared cause.

## Handoff for the next kernel comparison

Work stopped after the native NVMe comparison, pending machinery to configure
and install custom Startop kernels. There is no demonstrated permanent fix.
The next experiment is a kernel comparison, not another round of GPU,
ME, sleep-mode, PowerTOP, or Wi-Fi-radio tuning.

1. Read the rejected-hypothesis table and secondary-SSD isolation results
   first. The latter proves a useful device path but does not prove the SSD
   itself defective or prove that one specific latency field is the sole cause.
2. Keep the existing distribution kernel bootable. For the first comparison,
   retain its configuration as closely as practical rather than simultaneously
   trimming drivers and changing the kernel version. Preserve the exact tested
   config and version; a custom kernel with different settings tests both
   version and configuration and must be interpreted accordingly.
3. Keep ME and firmware Modern Standby enabled, use s2idle, and retain the
   60 Hz display setting and comparable brightness/peripherals. Confirm GSC is
   running and both GPU tiles sleep; this avoids the additional S3 failure.
4. Use the archive's `startop-power-snapshot-with-nvme.py` with Python 3,
   root access, nvme-cli, and pciutils. Extract it to a persistent working
   location before rebooting. The root-level loose script and JSON files are
   convenient working copies, not required for recovering the investigation.
5. After a fresh boot, let activity settle and save a before capture. Suspend
   once, resume, wait a minute, and save an after capture. Capture labels must
   include the tested kernel; keep both files and its config together.
6. A useful improvement preserves package C6/C8 accumulation after resume
   and removes the battery-draw increase. Compare SOUTHPORT_A and GPU counters
   too; watts alone are noisy. APST and ASPM being enabled are not sufficient
   acceptance criteria.
7. If a second kernel reproduces the failure, investigate secondary-controller
   and root-port resume/LTR handling or prepare a minimal report for Star Labs
   and the relevant kernel maintainers. If it fixes the failure, narrow the
   version/config difference. Do not repeat detach/rescan as a workaround:
   it restored detection but disabled ASPM in the captured test.

The archive preserves the evidence needed for this handoff. The original
PowerTOP reports were lost as noted above; do not claim to have those files
or reconstruct their raw data from the summarized readings.
