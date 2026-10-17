# Correct initramfs keyboard policy and retire the mic-mute workaround

Created: 2026-10-16
Status: Backlog

## Context

The [Hyprland function-key investigation](../Open/019-hyprland-media-system-keys.md)
found that thinktop's v0.2 embedded genkernel initramfs hardware database maps
ThinkPad microphone scan code `0x1a` to `F20`. The kernel driver defaults to
`MICMUTE`; the live system's database does not override that scan code.
Genkernel uses its own eudev/hwids packages, so rebuilding an unchanged image
retains the unwanted mapping.

The real-root workaround is
[`/etc/udev/rules.d/90-thinktop-micmute.rules`](../../../../../../etc/udev/rules.d/90-thinktop-micmute.rules).
It matches only the ThinkPad Extra Buttons input device on Lenovo product
`21TDCTO1WW`, then sets scan `0x1a` to `micmute` after the standard keyboard
rules. This is model-scoped rather than serial-number-scoped. Repository rule
validation and reboot persistence are recorded on card 019; the runtime correction
was already verified separately.

## Revisit during custom initramfs work

- Ensure the future initramfs preserves the intended microphone mapping and
  review whether it needs keyboard remapping at all. Keep this separate from
  embedded audio firmware/topology, which solves early firmware availability.
- Inspect the generated image's actual keyboard policy and verify a cold boot
  without the real-root workaround or manual keymap correction.
- Confirm microphone mute reaches keyd/Hyprland as `MICMUTE`, then remove the
  redundant real-root rule and document the final policy.

This is a follow-up to the unfinished kernel/initramfs build workflow, not a
requirement to rebuild the current kernel just for this mapping.
