# Desktop preferences

## Static wallpapers

`@gui-desktop` includes swaybg with `gdk-pixbuf` image loading for JPEG, WebP,
PNG, and other installed loader formats. Install or update the set with
`sudo emerge --ask @gui-desktop`. Wallpaper commands run as the normal user:

```sh
agentoo desktop wallpaper set ~/Pictures/mountains.jpg
agentoo desktop wallpaper
agentoo desktop wallpaper clear
agentoo help desktop wallpaper
```

`set FILE` displays one image across all monitors using fill scaling and remembers
its absolute path, without copying the image. With no subcommand, `wallpaper`
prints the remembered path, or nothing when none is selected. The system-owned
collection lives at `/usr/local/share/agentoo/wallpapers/`, grouped into ordinary
subdirectories as useful. No images or default selection are bundled yet.
Personal images can live anywhere readable.

The selection is a text file at `$XDG_STATE_HOME/agentoo/wallpaper`, defaulting to
`~/.local/state/agentoo/wallpaper`; relative XDG paths are ignored. This is local
user state outside Git. The helper atomically replaces the file and serializes
changes with a lock beside it. It does not generate user configuration files.

The shared `/etc/xdg/hypr/agentoo.lua` includes `wallpaper.lua`, which runs
`python3 /usr/local/share/agentoo/lib/desktop/wallpaper.py` internally on session startup and after actual monitor
geometry changes. Hyprland 0.56.2 was observed moving an auto-positioned external
output from x=1920 to x=0 on lid close while leaving its wallpaper layer at
x=1920. Recreating the managed swaybg client corrected the misplaced layer.
The handler debounces `monitor.layout_changed` for 250 ms and compares sorted
output names, positions, sizes, scales and transforms before restoring. Ordinary
config reloads, workspace changes and output enumeration order changes do not
restart the client. The geometry repair also covers lid opening and hotplug.
With no saved image, initialization quietly succeeds, including when swaybg is not
installed. A missing remembered image produces a warning and exit 1, retaining
the path for a later retry. New sessions retain the solid background in this case.
`clear` removes the selection and stops Agentoo's wallpaper processes, exposing
the compositor's background; it also works outside Wayland.

Setting/restoring an image requires a running Wayland session and an absolute
`XDG_RUNTIME_DIR`. Process records and swaybg diagnostic logs live under
`$XDG_RUNTIME_DIR/agentoo/`, separately for each Wayland display. Only recorded
processes with matching Linux start times are stopped, using PID descriptors to
avoid PID reuse races. Independently started swaybg instances are untouched.
The client exits when its compositor connection closes; no user service is added.

A replacement starts before the previous managed client stops. The helper checks
for immediate process or image-loader errors for half a second before remembering
the choice. swaybg provides no readiness acknowledgement: a delayed load or
rendering error can still occur afterward. Inspect the runtime log if an image
does not appear. Failed initial checks retain the previous selection and client.

Help and queries do not start clients or create state. Results go to stdout;
change summaries, warnings and errors go to stderr. Exit codes are 0 for success,
1 for operational failure, and 2 for invalid arguments. `agentoo-desktop` is also
independently runnable. Tab completion derives commands and file arguments from
the same parser as help.

After deployment and installation, test set, replacement, query, clear, logout,
and startup restoration in a real Hyprland session. Confirm ordinary config
reloads do not create another swaybg process, images appear on connected and
newly attached monitors, and clients exit on session shutdown. Repository tests
use a fake client and do not establish physical rendering correctness.

## Window transparency

```sh
agentoo desktop transparency
agentoo desktop transparency set --focused 5 --unfocused 10
agentoo desktop transparency set --window kitty --unfocused 20
agentoo desktop transparency set --window browser --focused 0 --unfocused 0
agentoo desktop transparency clear --window browser
agentoo desktop transparency clear
```

Percentages measure transparency: 0 is opaque, 90 is the maximum, and fractional
percentages are accepted. Focused and unfocused values change independently.
Without an action, the command prints settings without
creating state or changing windows. `--window` defaults to `all`; a query of
`all` shows all three groups with override, inherited, or configured-default
sources. Queries without a reachable compositor show saved values and label
unavailable defaults as `configured default` rather than guessing them.

Setting `all` clears Kitty/browser overrides for each supplied focus state.
An omitted focus state retains its shared value and category overrides.
Clearing Kitty or browser removes that category's overrides, restoring shared
inheritance. Clearing all removes every override and restores authored defaults,
including personal configuration. `clear` cannot accompany either percentage.
Shared defaults currently set no opacity, so absent host or personal settings
the underlying defaults are fully opaque.

Transparency occupies the `transparency` section of the shared
`$XDG_STATE_HOME/agentoo/appearance.json` (normally
`~/.local/state/agentoo/appearance.json`); relative XDG paths are ignored.
This is personal, untracked state. Updates use a private directory, atomic
replacement, and the shared `appearance.lock`.
Hyprland reads the JSON through a validating Python helper at startup and every
configuration reload; there is no separate restore command or generated config
to keep in sync. Updates require the shared integration in a running Hyprland
session, reload configuration without reconfiguring monitors, and restore the
previous saved record if reload fails. Operational messages go to stderr,
queries/help to stdout, and exit status is 0/1/2 for success/failure/invalid input.
Help and completion use the command's shared parser and require no session.

Hyprland uses absolute, focus-specific opacity rules for normal, floating,
dialog, fullscreen, and dropdown windows. Layer surfaces such as panels and
notifications and compositor/application popup menus are not targeted. Kitty
uses native **background-only** transparency, preserving text opacity. A shared
Kitty watcher tracks focus and notices saved changes within approximately 250ms,
without external remote-control permissions, sockets, or an extra daemon.
Reset re-reads Kitty's configuration, including its original command-line
overrides, before restoring background opacity. Kitty backgrounds supplied by an
application or background images follow Kitty's own transparency limitations.

Kitty must start with `dynamic_background_opacity yes` and the shared watcher.
The shared configuration provides both; personal settings can override them.
Kitty processes started before installation need a one-time restart: a reload
cannot retrofit dynamic opacity reliably. No running application is restarted
by this command. Kitty's standard `kitty` class and `agentoo-dropdown` are
recognized by the compositor. Browser classes include Firefox, Chromium,
Chrome, Brave, Edge, Vivaldi, Opera, LibreWolf, Floorp, and Zen. Custom application
classes require extending the shared class expressions in `window-classes.lua`.

Authored window opacity/opaque/force_rgbx rules in the personal Hyprland config
tree and selected host file cause adjustments to fail with file/line locations;
they are never rewritten. Queries warn about them. This scan is conservative:
unused files in the personal tree may be reported, while dynamically constructed
Lua or includes outside those locations require manual inspection. Decoration
opacity settings and Kitty `background_opacity` are underlying defaults, not
conflicts. A full reset remains available even with conflicting rules or a
damaged state file. Separate sessions share the saved choice; a different
already-running Hyprland session picks it up on its next configuration reload.

Verification: run `python3 -m unittest discover -s usr/local/share/agentoo/tests
-p test_transparency.py`, `lua usr/local/share/agentoo/tests/test_hypr_transparency.lua`,
and the CLI/wallpaper tests. Before deployment is considered visually validated,
check focus changes, existing/new Kitty windows, browser dialogs, fullscreen,
the dropdown, personal defaults after reset, and logout/login in a real session.
Parser and mocked API tests do not establish actual rendering correctness.

Implementation references: [Hyprland 0.56.2 opacity parser](https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/desktop/rule/windowRule/WindowRule.cpp),
[window rules](https://wiki.hypr.land/configuring/core/rules/window-rules/),
and Kitty's installed 0.48.2 watcher and background-opacity documentation
(`/usr/share/doc/kitty-0.48.2/html/launch.html` and `conf.html`).

## Window blur

```sh
agentoo desktop blur
agentoo desktop blur set --focused on --unfocused on --size 3 --passes 1
agentoo desktop blur set --focused on --unfocused off
agentoo desktop blur set --window browser --focused off --unfocused off
agentoo desktop blur --diagnose
agentoo desktop blur clear
```

Running blur without an action shows settings. `set` requires an adjustment or `--file`.
Blur is off in the shared Agentoo configuration. Enable it with `--focused on`
and/or `--unfocused on`. Changing size or passes alone saves strength without
enabling blur; the command reports when blur remains off. Enabling focused blur does not
enable unfocused blur, and vice versa. On/off preferences support the same
`all`, `kitty`, and `browser` groups as transparency. Setting `all` clears
category overrides only for supplied focus states. Clearing a category restores
shared inheritance; clearing all removes every blur override, including strength,
and re-exposes the authored host/personal/system defaults. Thus an explicit
personal `blur.enabled = true` remains a default and can take effect after clearing overrides.
Blur never modifies opacity or the saved transparency preferences.

Size and passes are global rather than per-window: they require `--window all`.
Accepted integers are 1–40 for size (matching the renderer's effective size
range) and 1–10 for passes. Neither strength option turns blur on. Omitted
strength settings retain the existing configured values; there is no implicit
preset. Size 3 / passes 1 is an optional modest starting point, not a power
measurement or a guarantee against artifacts. Try reducing size before adding
passes if blur looks poor. Turning both focus states off for all groups disables
the blur engine. Focus rules are native compositor rules: no blur polling process,
timer, per-frame script, or automatic battery/AC switching is added.

The integration preserves optimization, shader, algorithm, color modulation,
GPU selection, and driver settings. Upstream optimizations remain at their
configured values (normally enabled). It does not add blur to panels,
notifications, menus, input methods, or the background of an entire special
workspace. Independently authored settings for those surfaces are untouched;
the global engine switch still gates their rendering. Ordinary, floating,
fullscreen, dialog, and dropdown windows follow the focus/category rules.
Custom class families are defined once in `window-classes.lua` for both blur and
transparency.

Choices occupy the `blur` section of `$XDG_STATE_HOME/agentoo/appearance.json`,
defaulting to `~/.local/state/agentoo/appearance.json`, with the shared
`appearance.lock` serializing updates.
Relative XDG paths are ignored. Writes are atomic; the command reloads Hyprland
with `config-only` and verifies that the compositor has loaded the saved revision.
The reload request and verification calls share a two-second timeout budget.
The revision confirms which preferences were loaded; it does not prove a fresh
reload completed for an unchanged revision, or verify application rendering.
Failure or interruption restores the original state bytes and attempts a rollback
reload with the normal ten-second transport timeout. Rollback is best effort;
restoring the file does not guarantee that the live compositor recovered.
No generated configuration or separate restore command is needed:
`blur.lua` reads validated data on startup and config reload. Concurrent sessions
share choices; another existing session adopts them on its next reload. A full
reset can recover a malformed blur section or a conflicting-rule config error;
malformed JSON itself requires repairing the shared file.

Authored `no_blur`, `noblur`, `opaque`, and `force_rgbx` rules in the selected
host file or personal Hyprland config tree are conservatively reported with
file/line locations. The same conflict policy is used before saving and during
configuration loading: conflicts block changes whose resulting state contains
managed window rules. Strength-only state and a reset that removes the last
managed window rule remain usable. Defaults such as `blur.size` and
`blur.enabled` are retained rather than treated as conflicts. The scan cannot
evaluate arbitrary Lua or includes outside those locations; unused personal
files may also be flagged. No authored file is rewritten.

Queries show saved preferences, inheritance, and defaults captured before the
managed settings were applied. They separately report whether the saved revision
was loaded in this session and the engine's current on/off value. A runtime edit
can change the current engine without changing the loaded revision.
If no reachable integrated session is available,
saved values are still shown, but configured defaults are labeled unknown.
Help, completion, and queries create no state. Operational summaries and warnings
go to stderr; help/results go to stdout. Exit statuses are 0 for success, 1 for
operational failure, and 2 for invalid input. `clear` and `--diagnose` are
mutually exclusive and cannot accompany adjustments.

`--diagnose` is read-only. It reports the running compositor version/system/GPU
inventory, backend/OpenGL version when reported by Hyprland, effective blur
options, open application classes, and conflicting rules. One runtime snapshot
returns the captured defaults/revision and query-time options; with system info,
configuration errors, and the class inventory, a normal diagnostic uses four
compositor requests. It continues collecting independent evidence when a source
fails, including when the saved state is corrupt. Snapshot completeness is
checked at its read boundary: missing core options make that source unavailable.
Other sources are still collected, and each failed source reports its error to
stderr. Any source failure produces exit 1. Unsupported optional options are
shown as unavailable without invalidating the core snapshot.
GPU inventory is not
proof of which GPU renders a particular surface. No GPU benchmark, wattage
estimate, kernel change, session restart, or automatic workaround is performed.
Troubleshooting advice lives here. Diagnostics report observed settings without
embedding thresholds or GPU-cost heuristics in the command.

Blur requires transparent content. Hyprland 0.56.2 also respects clients using
`ext-background-effect`: an empty client blur region prevents blur even if the
engine is on. A window-rule on/off setting cannot override that protocol
decision. The public diagnostic API does not expose those regions, so diagnostics
explain this limitation rather than claiming that appearance is verified. Kitty
needs no external remote-control access for compositor blur. Application-specific
blur requests may require reloading that application's own configuration.

Checks:

```sh
python3 -m unittest discover -s usr/local/share/agentoo/tests -p test_blur.py
lua usr/local/share/agentoo/tests/test_hypr_blur.lua
```

The tests include native Hyprland parser checks for independent focus states,
strength-only changes, engine shutdown, and preservation of authored defaults.
They also check persistence, corrupt-state recovery, failed-reload rollback,
diagnostic read-only behavior, and help/completion. After deployment, visually
check existing/new Kitty and browser windows, focus transitions, fullscreen,
dropdowns, reset to personal defaults, and startup restoration. Compare actual
power at idle and during scrolling/resizing with blur off/on, including after
display sleep; parser checks do not establish rendering or power correctness.

References: [Hyprland 0.56.2 blur eligibility](https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/render/Renderer.cpp),
[upstream configuration guidance](https://github.com/hyprwm/hyprland-wiki/blob/main/content/configuring/core/config-options.md#blur),
[display-sleep/GPU report for 0.53](https://github.com/hyprwm/Hyprland/discussions/12760),
and [application blur requests after 0.56](https://github.com/hyprwm/Hyprland/discussions/15606).
User reports guide diagnostics; they are not treated as diagnoses or verified
workarounds for this machine. Newer upstream blur variants are not exposed by
this interface, which targets the installed 0.56.2 API.


## Desktop appearance

Six global commands complement `blur` and `transparency`. Run a command without
adjustments to inspect settings; use `--help` for choices, units, and limits.
Help and tab completion work without a desktop session. These are preferences
for the current user, not edits to the tracked or personal Lua configuration.

```sh
agentoo desktop corners set --radius 10 --power 4
agentoo desktop gaps set --inner 4 --outer 8
agentoo desktop borders set --width 2 --focused '#89b4fa' --unfocused '#45475a'
agentoo desktop borders set --focused '#89b4fa,#cba6f7,#f38ba8' --focused-angle 45
agentoo desktop animations set --enabled on
agentoo desktop animations set --windows popin --window-size 80 --duration 250
agentoo desktop animations set --workspaces slidefadevert --workspace-distance 30
agentoo desktop shadows set --enabled on --size 12 --opacity 35
agentoo desktop shadows set --color '#000000' --offset-y 3
agentoo desktop dimming set --enabled on --strength 15 --modal on
agentoo desktop corners
agentoo desktop corners clear
```

Omitted settings keep their saved values or configured defaults. Zero and `off`
are explicit choices. Each `clear` removes only that command's preferences,
revealing authored defaults, including personal configuration. `clear` accepts no adjustment flags. Queries distinguish saved overrides from current
compositor values and configured defaults. Without a reachable integration,
effective values are unavailable rather than guessed. Queries create no state.

| Command | Controls and units |
|---|---|
| `corners` | `--radius` 0–20 layout pixels; zero is square. `--power` 2–10; 2 is circular, 4 is a squircle. |
| `gaps` | `--inner` and `--outer`, each 0–1000 layout pixels. Inner spacing applies on each window side; adjacent sides add. Outer spacing adds at screen edges. Applies to tiled windows. |
| `borders` | `--width` 0–20 layout pixels; zero hides borders. `--focused` and `--unfocused` accept 1–10 comma-separated, quoted `#RRGGBB` or `#RRGGBBAA` colors. `--focused-angle` and `--unfocused-angle` take 0–360 degrees. |
| `animations` | Master `--enabled on\|off`; `--duration` 1–10000 milliseconds; window and workspace styles and their parameters below. |
| `shadows` | `--enabled on\|off`; `--size` 0–100 layout pixels; `--opacity` 0–100 percent; quoted `--color '#RRGGBB'`; `--offset-x` and `--offset-y`, each -250–250 layout pixels. |
| `dimming` | `--enabled on\|off` for inactive windows; independent `--modal on\|off` for modal parents; `--strength` 0–100 percent inactive-window darkening. |

Border colors and angles change independently for each focus state. A single
color gives a solid border; two to ten colors give a gradient. Each color can
include alpha. A color-only change retains the saved or authored angle; an
angle-only change retains all colors. Omitting both retains the authored gradient
unchanged. `borders clear` removes all saved border colors, angles, and width.

Appearance adjustments do not enable animations or shadows. Dimming strength
enables neither dimming mode. Modal dimming independently adds 50% of remaining
brightness: an otherwise undimmed parent becomes 50% dimmed; a parent already
15% dimmed becomes 57.5% dimmed. Hyprland 0.56.2 does not expose an independent
modal strength. See the [pinned window dimming implementation](https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/desktop/view/Window.cpp). Shadow color and opacity can be changed separately;
unspecified RGB/alpha, gradient angle, and the other offset coordinate are
preserved. An authored inactive-shadow color remains an override. The shadow
query shows the gradient and its first color's opacity. Opacity is quantized to
8-bit alpha, so the current percentage can differ slightly from the saved value.
Window/workspace rules and application decorations can override global settings;
these commands do not inspect or rewrite such rules. Global corner, border,
shadow, and dimming settings do not style panels, menus, or notifications.

### Animation styles and timing

For the pinned Hyprland **0.56.2**, all native styles for the exposed targets are
available in help and completion:

| Option | Styles |
|---|---|
| `--windows` | `slide`: from an edge; `popin`: grow into place; `gnome` / `gnomed`: the same grow-and-move effect. |
| `--workspaces` | `slide`: horizontal; `slidevert`: vertical; `fade`: crossfade; `slidefade` / `slidefadevert`: horizontal / vertical movement plus fading. |

Optional parameters must accompany a compatible style selection:

- `--windows slide --window-direction auto\|top\|bottom\|left\|right`
- `--windows popin --window-size PERCENT` (integer 0–100)
- `--workspaces STYLE --workspace-distance PERCENT` (integer 0–100; sliding styles only)

Compatible saved style parameters are retained when omitted. Switching to an
incompatible style removes obsolete parameters; when no parameter is saved, the
native default applies. Duration alone retains the existing styles and parameters. Window style adjustments target
opening/closing, not dragging or resizing. Workspace adjustments also cover special
workspaces. Layer animations, independent fade branches, and gradient rotation
are not managed. The master enable switch still controls all Hyprland animations.

Only public animation choices are saved: `enabled`, `windows`, `window_size`,
`window_direction`, `workspaces`, `workspace_distance`, and `duration`. There are
no saved compositor branches or machine-specific curve references. During every
configuration load, the entry file records authored `hl.animation` calls, restores
the native setter, and fills omitted details from those definitions. Thus the
same portable preferences retain the receiving desktop's timings, custom easing,
and individual branch enable states. The fallback is Hyprland 0.56.2's native
global default (800 ms, `default` bezier, enabled). Authored changes to omitted
settings take effect on the next reload without resetting preferences.

Spring curves set their own timing: style changes preserve them, but `--duration`
rejects affected spring branches instead of replacing their easing. Enabling the
master switch preserves individually disabled branches; queries show their states.

The style list and parameter handling were checked against
[Hyprland 0.56.2's validator](https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/animation/AnimationManager.cpp)
and [Lua setter](https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/config/lua/bindings/LuaBindingsConfigRules.cpp).

### Persistence and verification

All eight appearance commands share `$XDG_STATE_HOME/agentoo/appearance.json`,
defaulting to `~/.local/state/agentoo/appearance.json`. The `appearance.lock`
serializes changes and writes
are atomic. Changes require the running shared integration. Reload uses
`hyprctl reload config-only`, retaining monitor configuration. A reported reload
failure restores the previous saved state and attempts to reload it. No daemon,
new configuration scanner, or generated configuration file is involved. Hyprland reads
validated data through `lib/desktop/effects.py settings` at startup and reload.

Malformed values are reported clearly. `clear` can recover a malformed command
section without discarding other effects; malformed JSON itself requires repairing
the file. Operational summaries/errors go to stderr, queries/help to stdout.
Exit codes: 0 success, 1 operational failure, 2 invalid arguments.

Verification:

```sh
python3 -m unittest discover -s usr/local/share/agentoo/tests -p test_effects.py
```

Tests cover parser/completion behavior, independent updates, scoped reset,
failed-reload recovery, portable animation inheritance, and isolated
`Hyprland --verify-config` checks for settings, colors, every exposed style, and
reset-to-authored defaults. They do not change a live desktop or verify rendered
appearance; those checks remain part of installed-session validation.


### Importing a desktop appearance

The saved state and import files use the same JSON structure. Wallpaper is
excluded: it retains its separate selection and lifecycle.

```json
{
  "borders": {
    "width": 2,
    "focused": "#79618f,#41434f,#527b69",
    "focused_angle": 45
  },
  "corners": {"radius": 10, "power": 4},
  "gaps": {"inner": 4, "outer": 8},
  "animations": {
    "enabled": "on",
    "windows": "popin",
    "window_size": 80,
    "workspaces": "slidefade",
    "duration": 250
  },
  "shadows": {"enabled": "on", "size": 12, "opacity": 35},
  "dimming": {"enabled": "on", "strength": 15},
  "transparency": {"all": {"focused": 5, "unfocused": 10}},
  "blur": {"all": {"focused": true, "unfocused": true}, "strength": {"size": 3, "passes": 1}}
}
```

```sh
agentoo desktop set --file appearance.json
agentoo desktop borders set --file appearance.json
agentoo desktop blur set --file appearance.json
```

The top-level command validates every supplied section before saving and reloads
once. A subcommand selects and validates only its own section, ignoring other
sections; a missing selected section is an error. Unknown sections at the top
level and unknown fields in selected sections are errors. Invalid JSON or values
never partially apply. Imports require a running shared desktop integration.

Every section is optional, and each section is a partial update: omitted fields,
window groups, and focus states remain unchanged. Importing a shared `all` value
retains category overrides that the file does not explicitly supply (unlike an
explicit CLI `--window all` adjustment, which clears corresponding overrides).
Compatible saved animation parameters persist; changing styles discards parameters
that cannot apply to the new style. JSON keys follow option names with underscores
instead of hyphens. Blur's focus values are JSON booleans; other on/off choices
use the strings `"on"` and `"off"`, matching their CLI values. Empty sections make
no changes; an empty top-level file is rejected.

`set --file` cannot accompany adjustment flags or a selected
Kitty/browser window category. Files apply and persist: their supplied values are
copied into normal state, with no ongoing dependency on the source file. The
import file is left untouched (unless it is itself the normal saved state file).
`clear` removes saved overrides and applies configured defaults rather than
writing fixed default values. Top-level `agentoo desktop clear` clears every
appearance section and forgets and stops the managed wallpaper. A feature
`clear` affects only that feature; transparency/blur also support `--window`.
An empty saved object is retained after removing all preferences.

The interface uses `set` and `clear` consistently. Adjustment flags and `--file`
belong to `set`; bare feature commands are read-only queries. The previous
direct adjustment syntax, `--reset`, and public wallpaper `restore` command
are deliberately removed. Wallpaper startup and layout repair use the internal
helper; appearance initialization continues reading saved state as before.

Only `appearance.json` is read for appearance preferences. Older per-command
state files and compositor snapshots are not supported or imported. Wallpaper
retains its separate selection file. Queries do not create or change state.

Additional verification:

```sh
python3 -m unittest discover -s usr/local/share/agentoo/tests -p test_desktop_state.py
```

These checks cover all-section and selected-section imports, validation before
writes, partial merges, one reload per import, rollback of the entire saved
appearance, and using one portable animation file with different
authored animation settings in native Hyprland config verification.
