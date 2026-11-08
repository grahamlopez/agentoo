# Flattop hardware baseline

Flattop is a Framework Laptop (13th Gen Intel Core), board FRANMCCP06 A6,
with an Intel Core i7-1360P (12 cores, 16 logical CPUs), Intel Raptor Lake-P
integrated graphics, AX211 Wi-Fi, Intel USB Bluetooth, and WD NVMe storage.
This baseline comes from `kernel-inventory-flattop-20261024T135738Z.tar.gz`,
collected on 2026-10-24 while running `6.12.21-gentoo-lopez64`.

The host Portage profile selects Intel graphics, GCC `-march=raptorlake`,
Rust `-C target-cpu=raptorlake`, and Thinktop's operator-selected build policy:
`PORTAGE_TMPDIR="/dev/shm"` and `MAKEOPTS="-j12"`. The inventory does not report
RAM capacity. Installer transactions also default to RAM-backed builds;
`--no-ram-builds` selects disk-backed storage for an installer invocation.

The captured boot used i915, iwlwifi, btusb, nvme, and snd_hda_intel, with an
IDT 92HD95 audio codec. Flattop's profile does not select SOF firmware; a DSP-detected
log line alone does not establish that SOF was used. Subsequent distribution
and custom-kernel boot evidence supports the reviewed Flattop savedconfig list,
`/etc/agentoo/firmware/flattop.list` (see [firmware](../firmware.md)). Applying
the list and validating after trimming are separate steps.

UEFI is evidenced by mounted efivarfs and EFI devices. System Secure Boot status
was not collected (the Bluetooth controller's secure-boot message is unrelated).
No host-specific EFI registration workaround is established. The previous
kernel config is evidence, not an Agentoo kernel configuration to install.

Before installation, confirm Secure Boot status, RAM capacity, the disk to erase,
and normal peripherals. Validate display, Wi-Fi, Bluetooth, speakers/headphones,
microphone, touchpad, and suspend/resume on the new kernel. The inventory reports
s2idle and deep sleep availability but does not exercise either. Display scaling,
fingerprint setup, and other desktop preferences remain unconfigured.
