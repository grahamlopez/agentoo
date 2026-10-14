# Build a minimal Hyprland base on a physical target

Created: 2026-10-14
Status: Open (planning complete; implementation deferred to a physical target)

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
source already provides systemd/D-Bus environment handling and graphical session
target integration. Verify the selected packaged release and its build options
before adding session glue. Reconsider UWSM only for a concrete unmet need.

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

This discussion took place in a QEMU VM. Repository review, syntax checks,
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

## Work completed in the planning session

- Added historical-note and upcoming-removal comments to all three legacy sets:
  early_install, hyprland_env, and optionals. Their package entries are unchanged.
- Recorded agreed decisions and the implementation plan here. No GUI packages,
  repository configuration, keyword policy, services, or startup settings have
  been changed in this session.
