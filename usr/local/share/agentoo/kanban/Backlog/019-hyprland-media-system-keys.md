# Make Hyprland media and system function keys work

Created: 2026-10-16
Status: Backlog

## Objective and current state

Make the physical keyboard's media and system function keys work reliably in
Hyprland, beginning with thinktop. Inventory all available keys and their Fn/Fn-lock
variants so coverage includes more than the initial volume and brightness keys.

The [minimal Hyprland base](../Completed/012-minimal-hyprland-base.md) provides
shared Lua configuration in `/etc/xdg/hypr/agentoo.lua`. It already binds speaker
volume up/down, speaker mute and microphone mute through `wpctl`; verify these
on hardware and fix any gaps. Existing bindings alone are not acceptance evidence.

## Scope and implementation

- Inventory emitted key events and firmware-handled functions on thinktop,
  including Fn-lock behavior. Distinguish missing input events from missing
  Hyprland bindings, and record any hardware or firmware limitations.
- Cover speaker volume up/down and mute, microphone mute, display brightness
  up/down, screen capture/Print Screen, and media playback controls
  (play/pause, stop, previous and next) where present.
- Review remaining system keys, including keyboard backlight, touchpad toggle,
  wireless/airplane mode, display switching, lock and sleep where present.
  Define the expected action for each available key; document unsupported keys
  and prerequisites instead of silently ignoring them. Coordinate sleep and
  other system actions with existing logind handling to avoid duplicate actions.
- Choose and package the small set of utilities required by the implemented
  actions. Keep shared bindings in the existing configuration, host-specific
  behavior behind explicit host selection, and personal overrides working.
- Define screen-capture shortcuts for full screen, active window and selected
  region, with documented file/clipboard destinations and cancellation behavior.
- Set sensible volume and brightness steps and bounds. Repeat continuous
  adjustments while held; ensure toggle/capture actions execute only once per
  press. Audio controls should follow the current default output/input devices.
- Provide useful state feedback where supported, including microphone mute and
  hardware indicators. Document any required desktop companions explicitly.

## Completion criteria

- [ ] Record a key/action inventory for thinktop, including Fn/Fn-lock variants,
  working firmware-managed functions and any unsupported functions with reasons.
- [ ] Verify volume, speaker mute, microphone mute, brightness, screen capture
  and available playback/system keys in a normal user's Hyprland session.
  Confirm actual playback/capture and display changes, not just command success.
- [ ] Verify held-key repetition, toggle behavior, adjustment bounds, screenshot
  contents/destinations/cancellation, and audio controls after default-device changes.
- [ ] Repeat relevant checks after suspend/resume and Hyprland exit/relaunch;
  exercise external audio/display devices where available and record coverage limits.
- [ ] Document bindings, dependencies, configuration overrides and troubleshooting;
  record physical validation results and any remaining limitations on this card.

This card tracks deferred work only; it does not apply configuration or authorize
implementation automatically.
