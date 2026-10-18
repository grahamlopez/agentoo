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

### Reboot persistence verified (2026-10-16)

After deployment of the corrected `RUN{builtin}` rule, a targeted change event
and read-only ioctl check returned 248 (`KEY_MICMUTE`). The user then rebooted
and ran only `read-mic-map.py`, without a manual correction or trigger; it again
returned 248. This verifies boot persistence of the real-root workaround on
thinktop. The earlier 190/F20 reboot result concerned the superseded IMPORT
version. Actual microphone mute toggling through Hyprland and its indicator
remain to be confirmed; keymap persistence alone is not action validation.

### Microphone action and LED/default-source finding

The user confirmed F4 toggles the PipeWire default-source mute state, but
reported that its LED is on after boot, goes off after a press, and does not
subsequently track toggles. Inspection found `platform::micmute` brightness 0
with the correct `audio-micmute` trigger selected; `SND_CTL_LED=y` and the ALSA
mic LED mode is `follow-mute`.

Crucially, PipeWire's default source was the virtual ALSA Loopback source
(`alsa_input.platform-snd_aloop.0.analog-stereo`), not the physical microphone.
Thus the earlier mute-state toggle alone did not validate physical microphone
muting. Selected the detected built-in SOF `HiFi__Mic__source` as the default
using `wpctl set-default` (session object ID 63; IDs are not persistent).
Physical microphone mute and LED tracking require a fresh user test, as does
default-source persistence after reboot. Initial LED-on behavior remains
unexplained; no custom LED writes or synchronization service were introduced.

The user subsequently confirmed that F4 mutes/unmutes the correct physical
microphone and the F4 LED follows the mute setting. This validates the current
default-source selection and existing kernel LED trigger without an LED-specific
workaround. Default-source persistence after reboot remains to be checked;
the microphone keymap's reboot persistence was already verified above.

### First-client audio initialization explained

Across further reboots, the user observed the F4 LED turning on during SOF
initialization before disk unlock and staying on until the first `wpctl status`.
That first command showed no sources/sinks; a second command showed them.
Service inspection confirmed PipeWire sockets enabled at user login but
`pipewire.service` disabled; WirePlumber was enabled under PipeWire's service.
Boot journal times showed sockets listening at 23.66 seconds and PipeWire plus
WirePlumber starting at 81.45 seconds. This supports first-client socket
activation and asynchronous device enumeration, rather than a missing key event.
The LED transition coincides with audio initialization; the exact pre-login
hardware mute state has not been measured.

Enabled `pipewire.service` for graham's user login and updated the GUI runbook
to enable the service explicitly (its unit also enables its socket). Subsequent
login startup, first-status enumeration and LED behavior remain to be verified.
This change starts audio at user login, not before disk unlock, and adds no LED
override or initramfs modification.

### Speaker mute LED diagnosis and runtime validation

The user confirmed F1 toggled PipeWire output mute but its LED never lit.
The selected output was the built-in SOF Speaker sink, not Loopback or an
external output. `platform::mute` already selected `audio-mute`, and ALSA's
speaker LED mode was `follow-mute`, but every card's speaker LED control list
was empty.

The installed UCM configuration for `cs42l43-spk+cs35l56` contains SetLED
attachments in FixedBootSequence for `cs42l43 Speaker Digital Switch` and
the amplifier speaker switches. Read-only ALSA enumeration confirmed these
controls on thinktop: IDs 39, 76 and 79 for the digital switch, AMP1 and AMP2
respectively (IDs are observations, not stable configuration inputs).

The user ran session-local `hotkey-investigation/attach-speaker-led.py`, which
discovers the SOF card and attaches those three controls by name through
`/sys/class/sound/ctl-led/speaker/cardN/attach`. The user confirmed that F1's
LED then follows speaker mute. This is a runtime association test, not an
installed persistent fix; it changes neither volume/mute nor the LED trigger.

The normal UCM attachments are privileged sysfs writes; WirePlumber runs as
the desktop user. Initial inspection found no installed alsactl executable,
ALSA system services, or `/var/lib/alsa` directory. Missing privileged ALSA/UCM
initialization is a lead, not yet a proven root cause. Investigate the intended
Gentoo ALSA initialization path before adding a custom LED service or rule.
Persistence and post-resume LED behavior remain unverified.

The follow-up package inspection confirmed `media-sound/alsa-utils` is absent.
Upstream alsactl performs UCM FixedBootSequence initialization, and its packaged
udev restore rules invoke it for sound-card events. Gentoo's ebuild installs
the udev rules and systemd units. Added alsa-utils to `@gui-base` as the normal
ALSA initialization/tooling dependency, rather than introducing a custom LED
service. Dependency resolution selected alsa-utils 1.2.16 and libsamplerate
0.2.2 without keyword changes; the sandboxed pretend command subsequently failed
while updating Portage news metadata, so this was not a fully successful emerge
check. Installation and fresh-boot validation of automatic LED attachments remain
pending; do not count the manual runtime attachment as proof of the package fix.

The user subsequently installed alsa-utils 1.2.16, rebooted without the manual
attachment script, and confirmed F1 LED tracking works. Post-boot inspection
found speaker LED controls 79 and 76 attached automatically. `alsa-restore.service`
completed; `alsa-state.service` correctly skipped because its opt-in configuration
file was absent. First-run logs reported no saved asound.state and generic
initialization for Loopback/VirMIDI; the physical card's UCM directory was created
at `/var/lib/alsa/card2.conf.d`. This validates the normal packaged initialization
path for thinktop's F1 LED. No custom persistent speaker LED rule/service is
required. Suspend/resume and other-host acceptance remain separate checks.

### Shared brightness bindings prepared (2026-10-18)

Agreed to shared standard-key bindings, host-specific exceptions and a separate
`@laptop` utility set. Added `sys-power/acpilight` to that new set, rather than
adding an overlay for brightnessctl or requiring laptop utilities on desktops.
Gentoo's stable acpilight 1.2-r5 installs the xbacklight command and video-group
udev permissions. It requires no X server. User membership in video and package
installation remain deployment steps, not changes made during repository work.

Shared Lua binds XF86MonBrightnessUp/Down to `agentoo-backlight up/down` with
repetition. The helper selects only display backlights, does nothing when none
exist, and requires explicit controller selection if more than one exists.
It invokes acpilight in perceived-brightness steps of 5, with minimum raw level
1, and permits host bindings to name a controller. Thinktop currently exposes
one panel device, intel_backlight; no controller name is hard-coded in shared
configuration. The runbook describes installation, permissions and validation.

Shell/Lua syntax and diff whitespace checks passed. Isolated helper checks with
mock controllers verified no-panel behavior, one-panel command arguments,
ambiguous-device refusal, explicit selection and invalid-name rejection.
No physical brightness adjustment or installed Hyprland parser validation has
been performed yet. Deploy/install, reload Hyprland, and test normal-user access,
visible steps, held-key repeat, bounds and suspend/resume before acceptance.

The user subsequently confirmed the brightness keys work on thinktop after
resolving acpilight installation and video-group access. This establishes
reported physical key-to-brightness operation. Held-key repetition, minimum and
maximum usability, reboot persistence and suspend/resume have not been explicitly
confirmed. User setup now installs acct-group/video and includes video membership
on initial account creation and append-only reruns; fresh login remains required.

### Screenshot bindings prepared (2026-10-18)

The user selected file-only screenshots in `~/Downloads/Screenshots`, grim for
capture, slurp for region selection, and a standalone `agentoo-screenshot`
helper rather than extending the administrative `agentoo` command. wl-copy and
wl-paste are installed, but no clipboard manager/history is configured and the
helper does not use the clipboard. Added stable Gentoo grim/slurp to @gui-base.

The helper supports full (all outputs) and region modes, creates the destination
on demand, reserves unique timestamped PNG filenames with owner-only permissions,
and removes unsuccessful captures. Cancelling selection cannot fall through to
full-screen capture. Selection is live, with no freeze-preview dependency.
Shared bindings cover Print, Shift+Print and XF86SelectiveScreenshot. A new
thinktop host fragment binds keyd's F16 alias; the existing local host selector
must explicitly include it after deployment. No selector was created on the
live system during repository preparation.

Shell/Lua syntax, whitespace and isolated helper checks passed, including full
and region invocations, filename uniqueness, spaces in HOME, file permissions,
cancellation and capture-failure cleanup. Installed Hyprland parser checks,
package installation and physical screenshot/content/shortcut testing remain
pending. Active-window capture remains a separate unimplemented scope item.

The user clarified that @gui-base must remain the bare graphics foundation.
Created @gui-desktop extending @gui-base and moved grim/slurp into it. This
supersedes their initial placement in @gui-base. Screenshot dependency messages
and installation instructions now name @gui-desktop; @laptop remains independent.

### Automatic host selection correction (2026-10-18)

The user reported F9 capturing successfully but F10 doing nothing. Live binding
inspection showed no F16 binding: thinktop.lua was deployed but the previously
documented second, local Hyprland selector did not exist. The user clarified that
configuration changes must be tracked and take effect automatically on deployment.
Replaced the separate selector mechanism with parsing the existing installer-owned
`/etc/agentoo/target-host` assignment and including the matching tracked host
fragment when present. Thinktop already selects `GENTOO_TARGET_HOST="thinktop"`.
No new local file or manual include is required. Personal overrides still load
last; generic hosts without fragments keep shared defaults. The obsolete
hyprland-host.lua selector is no longer read. Shell text is never executed and
host names cannot traverse paths. Lua syntax and mocked selection checks passed
for thinktop, generic/missing fragments, absent selector and invalid path input.
Deploy/reload and physical F10 acceptance remain pending.
