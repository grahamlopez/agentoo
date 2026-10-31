# Exclude local host and boot identity from Git

Created: 2026-10-31
Status: Backlog
Priority: Medium

The [shared ignore policy](../../../../../../etc/agentoo/gitignore) omits these
documented machine-local inputs:

- `/etc/agentoo/target-host`
- `/etc/kernel/cmdline`
- `/etc/kernel/gentoo-dist-esp.uuid`

Disposable `git check-ignore --no-index` checks using that policy confirmed all
three remain eligible for staging, while the existing local secret-profile and
Wi-Fi exclusions work. Hiding untracked files in status does not prevent staging.
Committing these inputs can distribute a host selection or storage identity to
other machines.

Add explicit exclusions in the authoritative shared policy. Review the related
[local-state inventory](../../docs/host-onboarding.md) for the same bounded gap;
do not replace this with a broad filesystem allowlist or another policy loader.
The retired `hyprland-host.lua` exclusion is also relevant to cleanup in
[card 044](044-retire-inactive-configuration-and-fallbacks.md).

Complete when disposable Git checks cover the local identity exclusions while
tracked host fragments remain addable. No live selector or boot identity needs
to be modified for validation.
