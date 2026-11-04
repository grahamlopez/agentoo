# Startop power increase after resume

Investigation begun 2026-11-03 on Startop, a Star Labs StarFighter with an
Intel Core Ultra 9 285H, i915 graphics, AX210 Wi-Fi, two NVMe drives, coreboot
26.08 (BIOS date 2026-08-13), and kernel `6.18.60-gentoo-dist-bin`.

Fresh-boot idle draw is approximately 4.8–5.2 W. After suspend/resume it rises
to approximately 6.2 W and CPU package idle stops progressing beyond C2.
This reproduces with S3, Linux s2idle, and firmware-enabled Modern Standby.
The strongest shared lead is a new 1.024 microsecond SOUTHPORT_A latency
request after resume. Its source and causal role remain unproven.

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
**SOUTHPORT_A has not been mapped to a particular root port or endpoint.**
Do not name Wi-Fi or either SSD as its source based only on this label.

The kernel reports `Invalid LTR scale factor` when reading some rows, and
initialization reports `couldn't get DMU telem endpoint -19`. The detailed
`lpm_status` and `lpm_requirements` reads return null. These limit interpretation
of PMC telemetry; neither warning independently proves the cause. The repeated
SOUTHPORT_A transition is a lead, not yet a demonstrated causal blocker.
No LTR-ignore override or PCI register modification has been tested.

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
- `wifi-blocked.json`, `gpu-after-resume.txt`, `startop-power-snapshot.py`

The original PowerTOP HTML and early text reports were in `/tmp` and were
lost across reboot. Their observations above are retained from the session;
the archive does not contain those original reports. The legacy repositories
were read under `~/local/legacy/{gentoo-notes,gentoo-configs}` and are not
included in the archive. Root-level working copies of captures were left intact.

Continue by mapping PMC0 SOUTHPORT_A to the relevant controller and checking
its latency-request restoration across resume. Distinguish firmware state
restoration from endpoint driver behavior. The Wi-Fi soft-block did not
unbind or runtime-suspend its PCI device, and NVMe internal power-state
configuration was not inspected. These remain open routes; overriding latency
requirements or detaching storage has not been justified or performed.

If a future kernel or firmware change motivates retesting, use a fresh boot
for each sleep mode, save before/after captures, and compare package counter
increments as well as watts. Preserve the working-GSC s2idle case as a control
so a recurring S3 graphics failure is not mistaken for the shared cause.
