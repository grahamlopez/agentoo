# Make Hyprland media and system function keys work

Created: 2026-10-16
Status: Open
Opened: 2026-10-16

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

## Investigation evidence (2026-10-16)

### Target and intended key functions

Physical tests were performed by the user on thinktop. DMI identifies Lenovo
ThinkPad T1g Gen 8, product `21TDCTO1WW`; the kernel reports BIOS N4EET24W
(1.10) and EC N4EHT21W. Compared kernels were
`6.18.54-agentoo-v0.2` and `6.18.54-gentoo-dist-bin`.

The user's printed key icons match Lenovo's model-specific documentation:

| Key | Intended special function | Physical Linux event under distribution kernel | v0.2 event after runtime mic correction, through keyd |
| --- | --- | --- | --- |
| F1 | Speaker mute | `KEY_MUTE` (113) | `KEY_MUTE` (113) |
| F2 | Volume down | `KEY_VOLUMEDOWN` (114) | `KEY_VOLUMEDOWN` (114) |
| F3 | Volume up | `KEY_VOLUMEUP` (115) | `KEY_VOLUMEUP` (115) |
| F4 | Microphone mute | `KEY_MICMUTE` (248) | `KEY_MICMUTE` (248) |
| F5 | Brightness down | `KEY_BRIGHTNESSDOWN` (224) | `KEY_BRIGHTNESSDOWN` (224) |
| F6 | Brightness up | `KEY_BRIGHTNESSUP` (225) | `KEY_BRIGHTNESSUP` (225) |
| F7 | Select/configure displays | `KEY_SWITCHVIDEOMODE` (227) | `KEY_SWITCHVIDEOMODE` (227) |
| F8 | Change power/performance mode | No keyboard event captured | No keyboard event captured |
| F9 | Print Screen | `KEY_SYSRQ` (99) | `KEY_SYSRQ` (99) |
| F10 | Open Snipping Tool | `KEY_SELECTIVE_SCREENSHOT` (634) | `KEY_F16` (186) |
| F11 | Open Microsoft Phone Link | `KEY_LINK_PHONE` (447) | `KEY_F23` (193) |
| F12 | User-customizable action in Lenovo Vantage | `KEY_BOOKMARKS` (156) | `KEY_BOOKMARKS` (156) |

These are intended OEM functions, including Windows-specific applications;
choose suitable Hyprland actions separately. F11 is phone integration, not
screen mirroring. F12 is programmable, not a fixed OEM action. Lenovo documents
F8 as switching power efficiency, balanced and performance modes. No keyboard
event does not establish that F8 is broken: ACPI notifications and actual
platform-profile changes have not yet been correlated with individual presses.

Sources:

- [Lenovo T1g Gen 8 / P1 Gen 8 keyboard shortcuts](https://download.lenovo.com/manual/thinkpad_p1_gen8_t1g_gen8/user_guide/en/Use_the_keyboard_shortcuts.html)
- [Lenovo Intelligent Cooling and F8 modes](https://download.lenovo.com/manual/thinkpad_p1_gen8_t1g_gen8/user_guide/en/Intelligent_Cooling.html)
- [Linux ThinkPad ACPI driver documentation](https://docs.kernel.org/admin-guide/laptops/thinkpad-acpi.html)

### Capture sequence and interpretation

1. Initial `libinput debug-events --show-keycodes` and `keyd monitor` captures
   on v0.2 showed only speaker mute/volume, Print Screen, a wake-up event and
   ordinary F1–F12. Both saw events from keyd's virtual keyboard. The configuration
   `/etc/keyd/default.conf` matches `*`; service logs confirm that keyd intercepts
   the AT keyboard, ThinkPad Extra Buttons and Video Bus (also the audio jack).
2. With keyd stopped, a v0.2 libinput capture again showed only the AT-keyboard
   events. After rebooting into the distribution kernel, the equivalent capture
   also showed the Extra Buttons and Video Bus events listed above, except F8.
   Device event numbers changed across boots; discover by device name each time.
3. A reusable Python collector then read raw evdev events, bypassing libinput,
   with keyd temporarily stopped. The distribution baseline confirmed microphone
   scan code `0x1a` (26) as `KEY_MICMUTE` and brightness down as
   `KEY_BRIGHTNESSDOWN`. After rebooting back into v0.2, the same collector saw
   microphone scan `0x1a` as `KEY_F20` (190), and brightness down correctly as
   `KEY_BRIGHTNESSDOWN`.
4. A second script changed only the running ThinkPad input keymap, using
   `EVIOCSKEYCODE` to map scan `0x1a` from 190 to 248 and verifying the result
   with `EVIOCGKEYCODE`. It captured the full physical function row with keyd
   stopped, restarted keyd, and captured its virtual keyboard in a second pass.
   Every special key except F8 appeared in both passes. The physical events
   matched the distribution kernel; keyd translated F10 to F16 and F11 to F23.
   Ordinary Fn+F1–F12 produced F1–F12 in both passes. A `KEY_WAKEUP` event also
   occurred immediately before F1 in the second pass; its cause is unconfirmed.

The earlier conclusion that v0.2 lacked working hotkey drivers was premature.
Raw input confirms working event delivery on v0.2 after the reboot, including
brightness without a brightness-related correction. The initial libinput-only
absence remains unexplained; do not claim that the microphone correction fixed
all missing events. Fn variants were exercised, but Fn-lock toggling, every
firmware-managed function and post-resume behavior remain unverified.

### Simultaneous raw/libinput comparison

On the same v0.2 boot, after the runtime microphone correction, the user ran
`compare-libinput.py`. It stopped keyd and opened raw evdev and libinput readers
simultaneously on the same three physical devices, without an exclusive grab or
additional keymap change. The full special row and Fn+F1–F12 were pressed once.
Both readers reported identical key press/release sequences: all special keys
except F8, ordinary F1–F12, and the additional wake-up event before F1.
Thus libinput is not currently filtering the missing keys; the earlier omissions
are not reproduced. This does not isolate the effect of reboot, prior device
state or the mic correction on the original failure. Do not claim that reboot
alone fixed it or that the mic correction fixes other keys.

Evidence: session-local directory
`/home/graham/local/agentoo/hotkey-investigation/compare-6.18.54-agentoo-v0.2-20261016-214701/`,
containing `raw.txt` and `libinput.txt`. The comparison script restores previously
active keyd and returns capture ownership to the invoking sudo user. A future
reboot test before any manual correction is still needed for persistence.

### Confirmed initramfs keymap discrepancy

The v0.2 configuration is retained in
[kernel-thinktop-v02-config](../../docs/kernel-thinktop-v02-config).
`CONFIG_INITRAMFS_SOURCE` identifies the embedded archive at
`/home/graham/local/agentoo-build/genkernel/6.18.54-agentoo-v0.2/output/initramfs-6.18.54-agentoo-v0.2.cpio`.
Its `etc/udev/hwdb.bin` was extracted and queried using the actual ThinkPad
device name and DMI modalias. Compared with the live hardware database:

- Embedded database explicitly supplies `KEYBOARD_KEY_1a=f20`; the live database
  has no override for that scan code. The inspected kernel source defaults the
  microphone key to `KEY_MICMUTE`. The embedded mapping explains the observed
  v0.2 F20 event.
- Embedded database also supplies `KEYBOARD_KEY_07=f21`, where the live database
  uses `touchpad_toggle`, and lacks several newer mappings present in the live
  database. These differences have not all been physically exercised.
- Embedded and live `60-evdev.rules` differ. Genkernel's `append_eudev()` unpacks
  its own eudev and hwids packages, builds `hwdb.bin` with that eudev's
  `udevadm`, then removes the source hwdb files from the image. Build logs
  identify the cached package as `eudev-3.2.14-x86_64.tar.xz`; rebuilding an
  unchanged image is not evidence that its keyboard policy has been corrected.

Built-in input drivers are present during initramfs boot, allowing its keymap
policy to affect them before the real root filesystem is mounted. The runtime
mic correction is verified but will be lost on reboot. No persistent input rule,
initramfs change, kernel rebuild or new Hyprland binding has been applied in
this investigation.

### Kernel and ACPI comparison

Both configurations enable ThinkPad ACPI, ACPI video, embedded-controller
support, evdev, sparse keymaps, ACPI WMI and platform profiles. ThinkPad video
and hotkey polling suboptions also match. v0.2 has `CONFIG_MODULES=n` and these
drivers built in; the distribution kernel loads ThinkPad ACPI and ACPI video
as modules. This timing difference was an investigation lead, not proof of a
driver initialization bug. No driver-option change is currently justified.

Both raw baselines reported:

- Hotkey reporting enabled; mask and recommended mask `0xff8c7ffb`, all-mask
  `0xfffffffb`, source mask `0x00000000`, polling frequency 10.
- `hotkey_bios_enabled=0` on the working distribution kernel as well as v0.2;
  this value does not diagnose the failure. Reading the legacy enable/BIOS-mask
  attributes itself generated deprecation warnings.
- ThinkPad driver delegates brightness handling to standard ACPI video. Its
  message about disabling ThinkPad brightness events is not evidence of missing
  brightness functionality.
- ACPI GPE `6E`, total GPE and SCI counters advanced during both 25-second
  captures: distribution 1701 → 1767; v0.2 1739 → 1808. These aggregate counts
  are not per-key attribution. No new kernel messages appeared during either
  capture interval.
- Compared driver parameters matched. Platform profile snapshots differed
  (`performance` on distribution, `balanced` on v0.2), but no before/after F8
  profile test was performed, so do not attribute this difference to F8.

The boot log also contained `Unknown key identifier 'zoom'` from udev on v0.2;
its relevance remains unconfirmed. Root-readable tracepoint availability was
collected where accessible, but no kernel trace was recorded.

### Evidence artifacts and remaining work

Session-local raw artifacts are in `/home/graham/local/agentoo/hotkey-investigation/`:

- `6.18.54-gentoo-dist-bin-20261016-213014/`: working raw baseline.
- `6.18.54-agentoo-v0.2-20261016-213248/`: raw baseline showing microphone F20.
- `row-6.18.54-agentoo-v0.2-20261016-213651/`: verified runtime correction,
  full physical row and keyd output, plus service logs.
- `capture.py`: baseline collector; `check-row.py`: temporary mic correction
  and two-pass full-row collector. Both restore previously active keyd on exit.

Earlier libinput/keyd captures were saved under `/tmp/agentoo-*.log`; those
paths are temporary and may not survive reboot. The durable conclusions are
recorded here; local raw artifacts are not assumed to be committed or installed
project payload. Initial capture ownership required a one-time correction;
the scripts now return generated artifacts to the invoking sudo user's ownership.

Next steps:

- Make microphone keymap policy persistent and consistent across initramfs and
  the real root; verify the generated image's actual policy before rebuilding
  the embedded kernel image. Choose the narrowest maintainable fix.
- Verify events reach Hyprland, then implement the missing actions. Account for
  keyd's confirmed F16/F23 translations instead of binding only physical codes.
  Current shared bindings cover speaker volume/mute and mic mute only.
- Investigate F8 via ACPI notifications and measured platform-profile changes.
- Explain the earlier libinput omissions if reproducible; do not infer a kernel
  regression from those captures alone.
- Validate actual actions, mute indicators, screenshots, bounds/repetition,
  device changes, reboot persistence and suspend/resume. Captured events alone
  do not establish that any user-facing action succeeded.

### Persistent real-root workaround prepared (2026-10-16)

Added `/etc/udev/rules.d/90-thinktop-micmute.rules` to the repository. It matches
input event devices named ThinkPad Extra Buttons only when DMI vendor is LENOVO
and product is `21TDCTO1WW`. On add/change it overrides scan `0x1a` to `micmute`
and invokes udev's keyboard builtin after the standard rules. Other models and
other input devices are unaffected; another identical model would also match.

`udevadm verify` passed. `udevadm test --extra-rules-dir=...` against the current
ThinkPad device matched this rule and reported `KEYBOARD_KEY_1a=micmute`.
The file is not yet installed in the live `/etc/udev/rules.d`; root installation,
rule reload and a cold-boot test without the manual correction remain pending.
Removal after corrected initramfs validation is tracked by
[card 020](../Backlog/020-initramfs-keyboard-policy.md). Embedded audio firmware
is unchanged.

This card is tracking documentation; tooling must not apply it automatically.

### First reboot test and rule correction

After the user installed the real-root rule and rebooted into v0.2, udev's
device database contained `KEYBOARD_KEY_1a=micmute`, but a read-only
`EVIOCGKEYCODE` check still returned 190 (F20). Property presence and rule-match
validation did not establish that the actual keymap was changed.

Verbose `udevadm test` showed that `IMPORT{builtin}="keyboard"` is evaluated
before the `ENV{KEYBOARD_KEY_1a}` assignment within the same rule. Changed the
rule to `RUN{builtin}+="keyboard"`, deferring application until assignments are
complete. Deployment and an actual ioctl readback, followed by reboot validation,
are required before considering persistence fixed. `read-mic-map.py` discovers
the ThinkPad input device and reads the map without changing it.
