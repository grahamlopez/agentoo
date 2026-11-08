# Verify microphone mapping before retiring the initramfs workaround

Created: 2026-10-16
Status: Open — workaround retained; cold-boot acceptance pending

The old genkernel hardware database mapped ThinkPad microphone scan 0x1a to
F20. The model-scoped real-root rule corrects it to MICMUTE. Retain
`etc/udev/rules.d/90-thinktop-micmute.rules` until hardware verification proves
it redundant. Its removal during cleanup was reversed on 2026-11-08.

The minimal initramfs has no udev/hwdb. Temporarily disable the workaround for
a controlled cold boot of Thinktop with this initramfs and no manual correction.
Verify microphone keycode 248 and that keyd/Hyprland receive MICMUTE. Restore the
rule if this fails; remove it permanently only after successful verification.
The development sandbox cannot perform physical keyboard or reboot validation.
Record results before closing this card and
[card 049](049-post-genkernel-kernel-simplifications.md).
