# Startop hardware baseline

The fresh Agentoo installation inspected on 2026-11-03 has an Intel Core Ultra
9 285H (Arrow Lake), 16 logical CPUs and 62 GiB usable RAM. Its Intel graphics
device is PCI `8086:7d51`, bound to i915 on the distribution kernel
`6.18.60-gentoo-dist-bin`. Wi-Fi is an Intel AX210 (`8086:2725`), bound to
iwlwifi. The Arrow Lake audio controller (`8086:7728`) uses snd_hda_intel;
driver binding alone does not establish working audio.

The host Portage profile selects GCC `-march=arrowlake`, Rust
`-C target-cpu=arrowlake` and `VIDEO_CARDS="intel"`. The active GCC 16.2.1 and
Rust 1.98.1 both identify the native CPU as Arrow Lake. Builds use `/dev/shm`
(32 GiB at inspection) and `MAKEOPTS="-j12"`. Package-specific memory needs may
require lower concurrency or disk-backed build storage.

The installer writes detected CPU feature flags to the local native
`/etc/portage/package.use/00cpu-flags`. Its values match cpuid2cpuflags on this
installation; keep that local definition rather than duplicating it in the
tracked host profile. Installed linux-firmware now uses the reviewed Startop savedconfig selection
described below.

First-boot verification and checkpointing are reported complete. On 2026-11-05
the operator confirmed recovery readiness and working distribution-kernel
hardware except the known resume-power issue. Required peripherals match the
other onboarded hosts: Dell external monitor, Bluetooth mice and headsets,
Lily58 Bluetooth/USB keyboard, built-in and Logitech webcams, Blue USB microphone
and shared peripherals. On 2026-11-05 the operator also confirmed those checks passing before and
after suspend on both kernels after firmware trimming. See the acceptance
record below.

The first desktop autostart on Hyprland 0.57.0 failed because no DRM GPU was
available yet. The boot journal records Hyprland's abort at 9.08 seconds and
i915 DRM registration at 9.16 seconds; a manual launch succeeded afterward.
The native dracut fragment `/etc/dracut.conf.d/startop.conf` checks the existing
native Agentoo Portage profile and forces early i915 loading only for Startop, so graphics
initialization precedes tty1 autologin. After applying this configuration and
rebuilding the distribution initramfs, the user confirmed successful desktop
autostart on reboot on 2026-11-03. The running session's `hyprctl deprecated-config`
and `hyprctl configerrors` checks report no deprecations or configuration errors.
Subsequent custom-kernel and post-trimming boot/device acceptance is recorded
below.

EFI registration uses the installer's existing `--full-dev-path` workaround.
Keep local storage identifiers and boot arguments outside tracked host policy.

## Power after suspend

Controlled tests reproduce approximately 1–1.4 W more idle draw after resume
and loss of CPU package states deeper than C2. S3 additionally leaves the media
GPU tile awake, but the power increase persists with both GPU tiles sleeping
and GSC firmware working under firmware-enabled Modern Standby. Read the
[power investigation and rejected hypotheses](startop-power.md) before
diagnosing the boot or resume errors again. That record includes raw captures,
the shared SOUTHPORT_A latency-request change, and unresolved next steps.
Temporarily removing the unused secondary SSD at `0000:59:00.0` restored
package C6/C8 accumulation and cleared the valid latency request, isolating
the failure to that SSD or its root-port path through `0000:00:1c.0`.

## Custom kernel onboarding

The Startop kernel fragment was used for shared v0.4 with the observed MTL
DMC/GuC/HuC/GSC, AX210 API 89/PNVM, Intel Bluetooth SFI plus companion DDC,
regulatory data and `intel-ucode/06-c5-02`. All 11 inputs were present at review.
Current audio uses HDA/ALC233; no SOF/Cirrus payload requirement is established.
The shared driver union is unchanged. On 2026-11-05 the operator configured, built, installed and booted
`6.18.60-agentoo-v0.4`, including the Startop full-device-path EFI registration
extension. The corrected storage/udev handoff smoke test passed, no systemd
units failed, and the operator reported the requested peripheral and functional
suspend/resume checks passing. Early microcode updated from 0x121 to 0x122.
After trimming and distribution-initramfs regeneration, the operator completed
the requested power-cycle, peripheral and suspend/resume checks on the
distribution kernel and then the custom kernel, reporting all checks passing.
Both kernels reported zero failed systemd units.

## Installed firmware acceptance

Broad installed firmware was retained through initial custom-kernel acceptance.
The native Startop list was then applied to `linux-firmware-20261019` on
2026-11-05. The durable input, generated versioned snapshot and installed paths
all match: 36 paths (22 regular payloads, 14 symlinks), totaling 23,466,209
regular-file bytes versus 2,087,238,841 for the broad package, a measured 98.9%
reduction. Selected payload checksums matched the installed VDB before trimming,
and all selected symlink targets were retained. Installed-package payload bytes
are not kernel-image, initramfs or allocated-disk measurements.

The list retains MTL graphics and the packaged DMC fallback, AX210 API
alternatives/PNVM and aliases, Intel Bluetooth SFI/DDC and shared RTL8156 dock
coverage. No PCI NPU was enumerated. Regulatory data, microcode and any SOF
firmware retain separate package ownership. Raw WHENCE and recovery modinfo
were unavailable in the sandbox during review; both actual boot paths and the
requested peripheral/suspend behavior were subsequently accepted by the operator.

Two native packaging details required manual follow-up during application:

- Portage placed the generated versioned snapshot in a protected `._cfg` file.
  Its 36 entries were verified against the host list before accepting the update.
- linux-firmware's initramfs hook followed `/usr/src/linux` to the custom source
  tree, which has no in-tree image/config, and skipped regeneration. Running
  `emerge --config '=sys-kernel/gentoo-kernel-bin-6.18.60'` regenerated/reinstalled
  the distribution artifacts before recovery-kernel acceptance. The custom image
  needed no rebuild. Existing EFI entries remained usable.

The application backup is under
`/var/backups/agentoo/kernel-firmware/startop-linux-firmware-20261019.5qn77rxc`.
The final host-list SHA256 is
`0b8ee10d30531de8a6de4b8691f6cb4d1a3fca1fe1c258257d62faa662aade25`.
Keep the accepted distribution recovery image and the custom image available.

The requested onboarding/device acceptance is complete. Resume-power diagnosis
remains deferred in the linked investigation. Broader shared workload, platform
and sensor audits, and a decision about raw SPI-NOR/MTD access, remain with the
[shared follow-ups](../../kanban/Backlog/027-shared-kernel-v0.3-followups.md);
this acceptance does not claim those specialist audits were performed.
