# Keep installed kernel images and modules consistent

Created: 2026-10-31
Status: Backlog
Priority: High

The non-installer critical review reproduced a successful `agentoo kernel install`
retaining an obsolete `.ko` in an existing release directory, although that file
was absent from the validated staged module manifest. Installation copies the
staged tree over `/lib/modules/<release>` without removing obsolete entries.
It also changes installed modules before replacing the EFI image; an image
backup alone does not preserve the previous build's matching modules.

See [the install procedure](../../../../bin/agentoo-kernel) and
[disposable kernel fixtures](../../tests/test_kernel.py). The reproduction used
those fixtures with fake build/storage tools and a temporary destination; no
live modules, ESP, or firmware were changed.

User requirement clarified on 2026-10-31: reusing `--label` for an installed
kernel requests replacement; a new label keeps a separate installation.
Replacement is required, so do not require a new label merely because build
contents changed. The current artifact identity includes both kernel version
and label; retain that distinction when identifying the installation to replace.

Find the simplest coherent replacement procedure that keeps the image and its
module tree consistent, removes obsolete modules, and handles failures explicitly.
Consider replacement of a release used by the running kernel. Do not assume a
general deployment transaction framework is needed. Preserve target checks,
confirmations, safe retries, and the existing initramfs choices.

Complete when a successful installation cannot silently retain obsolete modules
or present a mixed build as the validated artifact. Add focused coverage for an
existing destination, removed drivers, repeat installation, and failures between
module and image operations. Coordinate with the existing shared-kernel follow-up
[card 027](027-shared-kernel-v0.3-followups.md); this card owns the installation defect.
