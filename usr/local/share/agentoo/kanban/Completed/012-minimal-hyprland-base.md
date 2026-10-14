# Build a minimal Hyprland base on a physical target

Created: 2026-10-14
Status: Completed
Completed: 2026-10-14

## Decisions and scope

Build the smallest simple, maintainable GUI base that provides Hyprland, Kitty,
audio, and suspend/resume. Hyprland is an explicit user preference. Use numbered
releases from hyproverlay, with stable Gentoo packages wherever possible and only
justified testing keyword exceptions. Keep the existing desktop-systemd base.

Launch explicitly with the packaged start-hyprland command from a normal user's
TTY login. Start with a plain background and minimal terminal, window-management,
and exit bindings. Defer launcher, notifications, locking, screen sharing, panel,
wallpaper daemon, graphical greeter, and automatic login/startup. Until locking
is added, resume returns to an unlocked session.

Use PipeWire and WirePlumber, including ALSA and PulseAudio protocol compatibility
through PipeWire. pipewire-pulse is PipeWire's compatibility server, not a second
PulseAudio audio system. Keep dhcpcd and wpa_supplicant; do not introduce
NetworkManager or competing systemd network services.

Use existing systemd/logind for suspend and laptop lid behavior. Prefer shared
system defaults, small explicitly selected host fragments, and local user
overrides, following the repository configuration philosophy. Do not deploy
copied or symlinked user dotfiles.

## Session management rationale

UWSM was considered for systemd user session lifecycle, environment propagation,
autostart, and shutdown cleanup. Leave it out of the initial base: those benefits
do not yet justify another layer for this small environment. Current Hyprland
source provides systemd/D-Bus environment handling. The selected 0.56.2 release
imports and clears that environment and supports systemd readiness notification;
plain TTY launch does not start a managed graphical session target by itself.
No initial service requires that target. Reconsider UWSM only for a concrete
unmet need, rather than adding session glue in anticipation.

The old gentoo-notes README records a pam_systemd failure with missing
XDG_RUNTIME_DIR, worked around by disabling systemd-userdbd. UWSM would not repair
the underlying login failure. Verify PAM, logind, the user service manager, and
D-Bus first; do not inherit the disablement without reproducing the fault.
The old shell profile also sleeps one second before startup; omit that delay
unless a reproducible race establishes a need.

Old Kitty warnings concerned missing portal settings, absent notifications, and
failure to create a systemd scope. The first two relate to deferred features;
the scope failure warrants user service manager diagnosis. Do not add optional
services merely to silence warnings.

## Historical material and packaging context

The locally cloned legacy-configs repositories are references, not desired state:
gentoo-notes/README.md, dots/.zprofile, and dots-gui/.config/hypr/ are particularly
relevant. Their location is session-local and they are not repository payload.
Reassess legacy graphics-driver, firmware, monitor, and audio workarounds against
the actual physical target before retaining any.

Gentoo announced removal of the Hyprland stack in February 2026, with removal
scheduled for March 11, citing rapid changes and testing/maintenance burden.
Upstream currently directs Gentoo users to the community hyproverlay repository.
Resolve current release availability and dependency requirements during
implementation; do not reuse the old dependency or keyword list.

References:

- [Gentoo removal announcement](https://www.mail-archive.com/gentoo-dev%40lists.gentoo.org/msg102415.html)
- [Hyprland installation](https://wiki.hypr.land/getting-started/installation/)
- [Hyprland systemd startup](https://wiki.hypr.land/Useful-Utilities/Systemd-start/)
- [Hyprland native integration source](https://github.com/hyprwm/Hyprland/blob/main/src/Compositor.cpp)
- [UWSM responsibilities](https://github.com/Vladimir-csp/uwsm)
- [PipeWire PulseAudio compatibility](https://docs.pipewire.org/page_man_pipewire-pulse_1.html)

## Implementation plan

1. Review every existing keyword exception across agentoo, including non-GUI
   entries. Remove obsolete exceptions; retain justified ones with comments.
   Put GUI policy in focused files. Scope Hyprland exceptions to their repository
   and accept testing shared libraries only when the selected release requires
   them. Distinguish testing keywords from explicit package masks.
2. Configure hyproverlay and create a fresh @gui-base explicitly selecting
   Hyprland, Kitty, PipeWire, and WirePlumber. Inspect dependencies and USE flags
   with Portage before installation. Avoid live builds and unnecessary companions.
3. Verify normal TTY login and the user session infrastructure; use the supplied
   startup command without UWSM or historical startup workarounds.
4. Add minimal shared Hyprland configuration using the chosen release's supported
   format and verified include/override behavior. Add host settings only as needed.
5. Configure PipeWire/WirePlumber user startup and application compatibility.
   Verify playback, microphone input, volume control, and target-specific firmware.
6. Verify manual suspend and laptop lid behavior through logind, including
   graphics, input, audio, and networking recovery. Check docked/external-display
   behavior when applicable; avoid competing lid handlers.
7. Document installation, explicit launch/exit, configuration ownership, keyword
   rationale, and validation results. Retire legacy sets when their replacements
   and remaining package requirements have been reviewed.

## Validation and execution boundary

The original planning discussion took place in a QEMU VM. Repository review, syntax checks,
dependency resolution, and limited guest integration tests can be performed
there. Guest graphics/audio tests cannot establish physical GPU, audio firmware,
lid, or suspend recovery correctness. Carry out the actual base implementation
and hardware validation on a physical target; select and identify that target
before operating on it. This card is passive planning documentation, not an
instruction for tooling to apply configuration automatically.

Before changing the physical target, inspect installed packages and configuration
and preserve a known-working checkpoint. Completion requires an inspected Portage
plan, successful installation, and normal-user login → launch → playback and
microphone → suspend/resume → exit → relaunch. Verify repeated resume, device
recovery, expected user services, and clean session shutdown. Record hardware,
versions, commands, outcomes, and any remaining limitations; do not count VM
checks as physical validation.

## Work completed in the original planning session

- Added historical-note and upcoming-removal comments to all three legacy sets:
  early_install, hyprland_env, and optionals. Their package entries are unchanged.
- Recorded agreed decisions and the implementation plan here. No GUI packages,
  repository configuration, keyword policy, services, or startup settings have
  been changed in this session.

## Repository preparation (2026-10-14)

The user selected repository-only work: they will commit and pull onto thinktop
to install and test. This session has not installed packages, enabled services,
modified the live system, or performed physical validation. Keep this card open.

- Added hyproverlay repository configuration and `@gui-base`, selecting numbered
  Hyprland 0.56.2, Kitty, PipeWire, and WirePlumber.
- Reviewed all keyword exceptions. Replaced broad GUI acceptance with ten exact
  version exceptions scoped to hyproverlay, including its glaze 7.x compatibility
  build. Stable Gentoo Wayland libraries need no exception. Removed legacy
  gentoo-sources/keyd/cliphist/hyprpaper/toolkit/GUI utility acceptance; retained
  and explained the four original testing Agentoo package exceptions, scoped to
  agentoo. Preserved independently added scoped keyd/group exceptions; these
  packages are outside `@gui-base`.
- Moved audio USE policy into `package.use/gui-base`; selected user systemd audio
  services, native Wayland Kitty, and native systemd Hyprland, with UWSM, plugins,
  GUI companions, and XWayland disabled.
- Added shared Lua configuration discovered through the system XDG fallback,
  with plain background, terminal/window/workspace/exit/volume bindings, optional
  explicit host selection, and a final real personal override. No user entry
  file, copied defaults, startup delay, or login workaround is required.
- Added the [installation and validation runbook](../../docs/gui-base.md),
  covering a checkpoint before the live pull, package-plan inspection, normal
  TTY login, user audio enablement, launch/exit, and physical acceptance.
- Preserved the three historical sets until their remaining package requirements
  receive a separate review. Removing keyword acceptance does not uninstall
  packages; inspect existing testing installations before a world update.

Validation: an isolated Portage configuration using the desktop/systemd profile
and Intel graphics resolved `emerge --pretend --verbose --autounmask=n @gui-base`
successfully against Gentoo `9ef593f1a819cdc0465b29afb11d03bac79ad5f8` and
hyproverlay `b2e7344722289a04ec5ccab6957a83597cd13048`. The plan selected 60
package merges (59 new, one new slot), with stable Kitty 0.48.2, PipeWire 1.6.8,
and WirePlumber 0.5.15. Selected release source confirms the used Lua APIs,
absolute `require()` tracking, XDG fallback discovery, watchdog argument
forwarding, and native session environment handling. Lua syntax checks passed;
Portage atoms/repository configuration parsed, permission policy covers all new
files, and `git diff --check` passed. At repository-preparation time, the installed
Hyprland parser and runtime/hardware checks remained for thinktop; subsequent
physical testing is recorded below.

Before completion, record thinktop's exact hardware/firmware and installed
versions, checkpoint name, inspected plan/build result, normal-user session and
audio compatibility tests, repeated suspend/lid/dock recovery, and clean
exit/relaunch results. Re-run dependency resolution after sync on that target.

## Thinktop validation reported by the user (2026-10-14)

- Synced hyproverlay, successfully emerged `@gui-base`, and entered Hyprland.
- Speaker playback works. Initial left/right announcement samples played through
  both speakers because the files are mono; the runbook now routes them explicitly.
  Separate channel routing has not yet been confirmed.
- Suspend/resume was very fast, and sound still works after resume. This confirms
  a reported suspend/resume cycle and playback recovery; the sleep state has not
  been checked against the journal.
- The missing-guiutils startup warning is expected with the chosen minimal
  package policy. RTKit `ServiceUnknown` warnings were observed from `wpctl`,
  which still returned the volume successfully. No audio dropouts were reported.

At this initial report, still unconfirmed: microphone capture/replay before and after resume, ALSA
compatibility, volume/mute controls, repeated suspend/resume, lid/dock behavior
where applicable, input/network recovery, user-session/configuration checks,
and clean exit/relaunch. Exact hardware/installed versions and checkpoint details
also remained to be recorded. The final acceptance report follows.

## Final physical acceptance (2026-10-14)

The user confirmed successful repeated suspend/resume cycles with working audio,
then explicitly confirmed microphone recording/replay, lid behavior, and clean
Hyprland exit/relaunch. The card is closed on this physical acceptance report.
Installation, launch, playback, microphone, repeated suspend/resume, lid handling,
and exit/relaunch are reported passed on thinktop. The agent did not execute
these interactive hardware tests.

Read-only host/package inspection records:

- Target selector: `thinktop`; Lenovo product `21TDCTO1WW`.
- Running kernel: `6.18.54-gentoo-dist-bin`.
- Installed Hyprland 0.56.2, Kitty 0.48.2, PipeWire 1.6.8, WirePlumber 0.5.15,
  and SOF firmware 2025.12.2.

Accepted limitations: no screen locking (resume is unlocked), GUI utilities,
portals, notifications, or other deferred desktop companions. The missing
GUI-utilities warning and optional RTKit warnings are documented in the session
and runbook; playback recovery works and no dropouts were reported. The runbook
was corrected to use installed PulseAudio-compatible tools and explicit routing
of the mono channel-announcement samples.

No raw hardware-test logs, checkpoint identifier, separate ALSA/channel-isolation
result, or dock/external-display result were supplied in this conversation;
do not treat this closure as independent verification of those details. Legacy
sets remain historical pending separate review of their remaining requirements.
