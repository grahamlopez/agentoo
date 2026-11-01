# Keep installed kernel images and modules consistent

Created: 2026-10-31
Status: Completed
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
[card 027](../Backlog/027-shared-kernel-v0.3-followups.md); this card owns the installation defect.


## Completion, 2026-10-31

The install procedure now stages an exact module tree under `/lib/modules` and
runs native `depmod --basedir` there before touching the installed release. It
also stages the image on the ESP. Replacements retain the previous image and
module tree with matching timestamped backup names, activate complete artifacts
with native renames, and restore modules if activation fails before the image
rename. Rollback failures explicitly identify retained recovery paths; staging
cleanup errors do not mask that diagnosis.

Version plus label still identifies the installation. Reusing the pair replaces
it, while another version or label installs alongside. Exact replacement removes
obsolete and separately installed external modules; external-module rebuilding
remains manual and the guide states that policy. The running module-enabled
release is protected even without loaded modules or an existing module tree;
boot another release and retry. Running module-free replacement remains allowed.

Verification: all 38 disposable kernel tests passed, including obsolete-module
removal after a changed build, repeated replacement, version/label coexistence,
restrictive umask, staging failure, failures before every activation rename,
interruptions after every successful rename, first-install rollback, rollback
failure diagnostics, cleanup failure, running-kernel capability, storage checks,
and firmware registration. A separate native disposable check copied one module
and metadata into a temporary root, ran the installed `depmod --basedir`, renamed
the root, and used `modprobe --dirname ... --show-depends` to confirm the generated
indexes still resolve the copied module. No module was loaded and no live
module tree, ESP, firmware or kernel was changed.

Image and module renames span filesystems; power loss, SIGKILL and crashes are
not atomic. The guide explicitly requires inspecting/retrying the installation
or restoring both matching backups before booting an interrupted release.
Keep a working recovery kernel; live boot/hardware acceptance remains separate.

## Expert workflow revision, 2026-11-01

The user clarified that these utilities target expert operators and should
preserve their tested update workflow without extensive guardrails. This
supersedes the initial running-release prohibition and automatic rollback above.
Same-version/same-label replacement is allowed while that kernel is running,
including modular builds, with the existing confirmation and no override flag.
The guide explains the potential module incompatibility until reboot.

The installation remains a direct stage, back up, and replace procedure using
native commands. Exact module trees, prepared indexes, complete staged images,
backups, and target checks remain. Removed activation-state bookkeeping,
post-interrupt state inference, automatic module restoration/removal, and nested
rollback/cleanup error handling. A failed or cancelled operation stops, reports
the retained artifacts, and leaves recovery to the operator. Successful installs
clean their own staging root. Retrying preserves earlier backups and failed
staging directories; retain original backups because another attempt can capture
an already partial installation.

Disposable regression coverage now exercises replacement of a running modular
release, module/image activation failures, interruption, retained recovery
artifacts, retries, obsolete-module removal, and version/label coexistence.
All 51 kernel/firmware tests passed without skips. Comparison against the
pre-review implementation confirmed configuration, build, host specialization,
and initramfs code unchanged. No live build, installation, or firmware change ran.
