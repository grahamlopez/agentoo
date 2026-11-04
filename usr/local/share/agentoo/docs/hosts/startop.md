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

First-boot verification and checkpointing are reported complete. Desktop and
physical hardware acceptance remain pending: displays and acceleration,
brightness and input controls, camera capture/privacy, speakers/headphones and
microphone, Wi-Fi/Bluetooth, dock hotplug, suspend/resume and lid/power behavior.
Establish results on the distribution kernel before comparing a custom kernel.
See the [Startop follow-ups](../../kanban/Backlog/024-startop-kernel-v0.3-followups.md).

The first desktop autostart on Hyprland 0.57.0 failed because no DRM GPU was
available yet. The boot journal records Hyprland's abort at 9.08 seconds and
i915 DRM registration at 9.16 seconds; a manual launch succeeded afterward.
The native dracut fragment `/etc/dracut.conf.d/startop.conf` checks the existing
host selector and forces early i915 loading only for Startop, so graphics
initialization precedes tty1 autologin. Rebuild the
distribution initramfs after applying this configuration, then verify a cold
boot and record the result. Custom-kernel boot acceptance remains separate.

EFI registration uses the installer's existing `--full-dev-path` workaround.
Keep local storage identifiers and boot arguments outside tracked host policy.
