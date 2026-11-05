# Startop hardware baseline

The fresh Agentoo installation inspected on 2026-11-03 has an Intel Core Ultra
9 285H (Arrow Lake), 16 logical CPUs and 62 GiB usable RAM. Its Intel graphics
device is PCI `8086:7d51`, bound to i915 on the distribution kernel
`6.18.60-gentoo-dist-bin`. Wi-Fi is an Intel AX210 (`8086:2725`), bound to
iwlwifi. The Arrow Lake audio controller (`8086:7728`) uses snd_hda_intel;
driver binding alone does not establish working audio.

The host Portage fragment selects GCC `-march=arrowlake`, Rust
`-C target-cpu=arrowlake` and `VIDEO_CARDS="intel"`. The active GCC 16.2.1 and
Rust 1.98.1 both identify the native CPU as Arrow Lake. Builds use `/dev/shm`
(32 GiB at inspection) and `MAKEOPTS="-j12"`. Package-specific memory needs may
require lower concurrency or disk-backed build storage.

The installer writes detected CPU feature flags to the local native
`/etc/portage/package.use/00cpu-flags`. Its values match cpuid2cpuflags on this
installation; keep that local definition rather than duplicating it in the
tracked host fragment. Installed linux-firmware retains broad default coverage.

First-boot verification and checkpointing are reported complete. On 2026-11-05
the operator confirmed recovery readiness and working distribution-kernel
hardware except the known resume-power issue. Required peripherals match the
other onboarded hosts: Dell external monitor, Bluetooth mice and headsets,
Lily58 Bluetooth/USB keyboard, built-in and Logitech webcams, Blue USB microphone
and shared peripherals. This is operator acceptance; repeat functional checks
on the custom kernel and on both boot paths after installed-firmware trimming.
See the [Startop kernel and firmware operation checklist](../../kanban/Open/024-startop-kernel-v0.4-onboarding.md).

The first desktop autostart on Hyprland 0.57.0 failed because no DRM GPU was
available yet. The boot journal records Hyprland's abort at 9.08 seconds and
i915 DRM registration at 9.16 seconds; a manual launch succeeded afterward.
The native dracut fragment `/etc/dracut.conf.d/startop.conf` checks the existing
host selector and forces early i915 loading only for Startop, so graphics
initialization precedes tty1 autologin. After applying this configuration and
rebuilding the distribution initramfs, the user confirmed successful desktop
autostart on reboot on 2026-11-03. The running session's `hyprctl deprecated-config`
and `hyprctl configerrors` checks report no deprecations or configuration errors.
Repeated and cold-boot acceptance and custom-kernel boot acceptance remain
separate checks.

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

The Startop kernel fragment is prepared for shared v0.4 with the observed MTL
DMC/GuC/HuC/GSC, AX210 API 89/PNVM, Intel Bluetooth SFI plus companion DDC,
regulatory data and `intel-ucode/06-c5-02`. All 11 inputs were present at review.
Current audio uses HDA/ALC233; no SOF/Cirrus payload requirement is established.
The shared driver union is unchanged. Kconfig resolution, custom build/boot and
hardware acceptance remain pending, as does the custom EFI registration extension.

Keep broad installed firmware until the custom candidate is accepted. The
operation checklist tracks subsequent savedconfig review for both kernels and
peripherals. Resume-power investigation is deferred until other onboarding is
working; functional suspend/resume tests remain required.
