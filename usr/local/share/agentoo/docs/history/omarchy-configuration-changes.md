# Omarchy configuration changes and repairs

Audited: **2026-10-19**. System: Graham's ThinkPad running Omarchy, including the Dell U5226KW monitor workflow.

This document is for historical reference only. It records the changes discussed in the configuration audit of a past Omarchy system, their original motivation, the decisions made, and the resulting file changes. Evidence comes from task history across directories, the September suspend incident report, current user files, and installed Omarchy templates. It does not claim to inventory every unrelated file on the machine. As these changes were done specificially for an installed Omarchy system, they may not be directly relevant for agentoo.

Diff conventions:

- **Exact comparison**: current file compared with a preserved backup or installed template. Template comparisons describe today's net deviation, not necessarily the historical patch.
- **Reconstructed/semantic**: isolated changes recovered from the discussion; these may omit context or normalize formatting. They are documentary, not blindly applyable patches.
- **New-file diff**: the full current contents of a custom file shown against `/dev/null`. Later amendments are included.
- Firmware and generated binary changes have no text-file patch. Their sections say so explicitly.

Several settings in the earlier chat summaries were defaults and have been corrected here. Where the original complaint or authorship is unconfirmed, that limitation is explicit.

## 1. Keep the closed laptop awake during monitor input/PbP switching

Initial complaint: Switching the Dell U5226KW between PbP modes or video inputs suspended the closed ThinkPad. Waking it required opening the lid, and closing it while locked could trigger sleep again.

Discussion and decision: The external display briefly disappeared during switching. Linux then stopped treating the laptop as docked and applied its closed-lid suspend policy. We discussed ignoring the lid on external power, ignoring it universally, and a custom docking inhibitor. You selected the external-power rule.

Result: Installed and reloaded on September 17; you reported that the first few tests passed. The file is still installed. Battery lid-close suspend remains available. A simultaneous loss of USB-C power can still expose the battery policy.

Source: “Fix monitor switching sleep,” task `01a0afff-e453-7e83-a62f-9ba6f7661fa4`.

```diff
--- /dev/null	2026-10-19 09:02:21.526993081 -0400
+++ /etc/systemd/logind.conf.d/30-ignore-lid-on-external-power.conf	2026-09-17 11:35:23.661867349 -0400
@@ -0,0 +1,4 @@
+[Login]
+# Keep a closed, externally powered laptop awake when a dock or monitor
+# temporarily removes its display during an input or PbP mode switch.
+HandleLidSwitchExternalPower=ignore
```

## 2. Prevent NVIDIA driver teardown from blocking suspend

Initial complaint: Lid-close suspend sometimes failed, and some wake attempts required a forced reset.

Discussion and decision: The September 2 diagnosis found supergfxd blocked inside NVIDIA driver removal. Integrated mode blacklisted NVIDIA, but the initramfs configuration forced the modules to load early. We removed the forced load, kept Integrated mode, and rebuilt the UKI with limine-mkinitcpio.

Result: The controlled test suspended and resumed in 21 seconds without the NVIDIA freeze timeout. The rebuilt image lacked NVIDIA modules. The separate earlier resume failure did not have one proven cause.

Diff: Exact comparison against the preserved pre-repair file. The generated `/boot/EFI/Linux/omarchy_linux.efi` also changed; it is a binary and has no useful Markdown text diff.

Source: “Fix laptop suspend failures,” task `01a06237-68db-7072-af72-67c3598e81ab`; see `suspend-resume-incident-report.md`.

```diff
--- /etc/mkinitcpio.conf.d/nvidia.conf.pre-integrated-20260902	2026-08-28 13:43:16.517587589 -0400
+++ /etc/mkinitcpio.conf.d/nvidia.conf	2026-09-02 09:12:47.516723450 -0400
@@ -1 +1,6 @@
-MODULES+=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)
+# NVIDIA early KMS is intentionally disabled while supergfxd is configured
+# for Integrated mode.  Early-loading these modules overrides supergfxd's
+# blacklist and makes supergfxd tear down the live driver during boot, which
+# can hang in NVIDIA's PCI removal path and prevent suspend.
+#
+# The Intel iGPU still receives early KMS through mkinitcpio's kms hook.
```

## 3. Update Lenovo system firmware

Initial complaint: The suspend/resume investigation identified old BIOS 1.05 as an additional resume risk.

Discussion and decision: Installed fwupd and applied the Lenovo System Firmware update. BIOS changed from N4EET19W / 1.05 to N4EET24W / 1.10. The bundle also updated embedded-controller, management-engine, retimer and CPU microcode firmware.

Result: The subsequent controlled suspend/resume test passed. Firmware was a risk reduction; the evidence did not isolate it as the sole cause.

File changes: Firmware is device state, not a configuration text file. No file diff exists. The following is a state summary, not an executable patch.

```diff
- Lenovo BIOS: N4EET19W, version 1.05
+ Lenovo BIOS: N4EET24W, version 1.10
```

Source: September 2 suspend incident report.

## 4. Repair Limine's stale UKI checksum

Initial complaint: After the boot-image rebuild, Limine warned that the BLAKE2b hash of `boot():/EFI/Linux/omarchy_linux.efi` did not match.

Discussion and decision: The bootloader configuration had been written before the final EFI image. We refreshed its checksum without rebuilding the image again, preserving `/boot/limine.conf.pre-hash-refresh-20260902`.

Result: The recorded checksum was checked against the EFI image and matched at repair time. Later kernel updates can legitimately replace this value.

Diff: Historical semantic reconstruction. Hashes are abbreviated from the incident report; the original full protected boot files were not available to this audit. This is not an applyable patch.

```diff
--- /boot/limine.conf (before repair)
+++ /boot/limine.conf (after repair)
@@ UKI integrity checksum @@
- BLAKE2b for boot():/EFI/Linux/omarchy_linux.efi: bcea...bd7b
+ BLAKE2b for boot():/EFI/Linux/omarchy_linux.efi: 936a...a2c8
```

Source: September 2 suspend incident report.

## 5. Update the fingerprint reader firmware

Initial complaint: Fingerprint unlock commonly failed after suspend/resume.

Discussion and decision: Logs showed the Synaptics 06cb:00f9 reader disconnecting during sleep and fprintd retaining a failed or stale state after wake. Official libfprint/fprintd packages were already current at the time. You preferred an upstream package/firmware repair over a daemon restart hook, so we applied the matching vendor-signed firmware update.

Result: Firmware installation and enrollment checks succeeded, but the intermittent resume failure recurred. A custom lock plugin and restart service were discussed but were not installed. This issue was improved, not proven completely resolved.

File changes: Device firmware only; no PAM or custom service configuration was installed. This is a state summary.

```diff
- Synaptics reader firmware: 10.01.3273255
+ Synaptics reader firmware: 10.01.3478575
```

Source: “Fix fingerprint unlock after resume,” task `01a06834-c9a6-7003-8b91-46ab56cdaced`.

## 6. Customize Bash directory listings

Initial request/context: The shell discussion examined why ls invokes eza. A personal override is present, but the exact act of adding it is not established by the reviewed session.

Discussion and decision: Keep Omarchy's bootstrap and default Bash configuration, and place personal overrides after the default source line. The custom alias adds reverse ordering (`-r`) to the detailed eza listing.

Result: Current non-default configuration, with authorship/date unconfirmed. The Bash bootstrap itself is stock.

Diff: Current file against the installed Omarchy template.

```diff
--- /usr/share/omarchy/default/bashrc	2026-09-15 17:04:16.000000000 -0400
+++ /home/graham/.bashrc	2026-08-28 14:33:58.366538275 -0400
@@ -12,3 +12,4 @@
 #
 # Make an alias for invoking commands you use constantly
 # alias p='python'
+alias ls='eza -lhr --group-directories-first --icons=auto'
```

## 7. Use Right Alt as the Compose key

Initial preference: Use Right Alt for composing special characters. The original complaint text was not recovered; this is a verified personal deviation.

Discussion summary: The user input override replaces Omarchy's Caps-Lock Compose options with compose:ralt.

Result: The override is still present. Other commented keyboard/touchpad examples are inactive.

Diff: Current user file against the shipped user template.

```diff
--- /usr/share/omarchy/config/hypr/input.lua	2026-09-15 17:04:16.000000000 -0400
+++ /home/graham/.config/hypr/input.lua	2026-08-28 13:54:13.984889920 -0400
@@ -3,11 +3,12 @@
 
 -- Keyboard layout and options.
 -- See https://wiki.hypr.land/Configuring/Basics/Variables/#input
--- hl.config({
---   input = {
+hl.config({
+  input = {
 --     -- Use multiple keyboard layouts and switch between them with Left Alt + Right Alt.
 --     kb_layout = "us,dk,eu",
 --     kb_options = "compose:caps,shift:both_capslock_cancel,grp:alts_toggle",
+     kb_options = "compose:ralt",
 --
 --     -- Use a specific keyboard variant if needed (e.g. intl for international keyboards).
 --     kb_variant = "intl",
@@ -41,8 +42,8 @@
 --       -- Left-click-and-drag with three fingers.
 --       drag_3fg = 1,
 --     },
---   },
--- })
+  },
+})
 
 -- App-specific touchpad scroll speeds.
 -- o.window("(Alacritty|kitty|foot)", { scroll_touchpad = 1.5 })
```

## 8. Add a direct Neovim launcher shortcut

Initial preference: Launch Neovim directly from the desktop in Foot. The original request text was not recovered.

Discussion summary: Add a personal Super+N binding while retaining Omarchy's default bindings.

Diff: Reconstructed isolated hunk from the current configuration; the separate layout shortcut is documented below.

```diff
--- /home/graham/.config/hypr/bindings.lua
+++ /home/graham/.config/hypr/bindings.lua
@@
+o.bind("SUPER + N", "NEOVIM", "foot nvim")
```

## 9. Customize general window appearance and scratchpad animation

Initial complaints/preferences: More visible window transparency and a dropdown-style scratchpad entrance. The exact original request for rounding/dimming was not recovered.

Discussion summary: Keep appearance changes in the user looknfeel.lua override. Enable rounded corners and inactive-window dimming, set focused/unfocused opacity to 0.95/0.90, and make the scratchpad enter from above.

Result: All settings remain present. Browser opacity required an additional change, documented in the next section.

Diff: Reconstructed isolated additions/enabled options, omitting unchanged template comments.

```diff
--- /home/graham/.config/hypr/looknfeel.lua
+++ /home/graham/.config/hypr/looknfeel.lua
@@
+o.window({ tag = "default-opacity" }, { opacity = "0.95 0.90" })
+hl.animation({
+  leaf = "specialWorkspaceIn",
+  enabled = true,
+  speed = 3,
+  bezier = "easeOutQuint",
+  style = "slidevert -50%",
+})
+hl.config({
+  decoration = {
+    rounding = 8,
+    dim_inactive = true,
+    dim_strength = 0.15,
+  },
+})
```

## 10. Make Firefox and Chromium follow the general opacity preference

Initial complaint: Firefox/Chromium appeared more opaque than terminals, ChatGPT and Prisma Access Browser.

Discussion and decision: Omarchy removes its default-opacity tag from recognized browser windows and gives them separate opacity rules. Therefore the general tag override could not affect them. After discussing a class regex, you requested compact overrides matching Omarchy's existing browser tags. An earlier XWayland suggestion was not the selected repair.

Result: Added October 3 and still present. The historical task could not run live compositor validation.

Diff: Historical additions, verified against the current file.

```diff
--- /home/graham/.config/hypr/looknfeel.lua
+++ /home/graham/.config/hypr/looknfeel.lua
@@
 o.window({ tag = "default-opacity" }, { opacity = "0.95 0.90" })
+-- Keep Firefox- and Chromium-family browsers aligned with the general window opacity.
+o.window({ tag = "chromium-based-browser" }, { opacity = "0.95 0.90" })
+o.window({ tag = "firefox-based-browser" }, { opacity = "0.95 0.90" })
```

Source: “Fix Firefox window opacity,” task `01a10278-ec88-71f3-9214-ec5e637d6406`.

## 11. Configure separate laptop/external scaling and Dell 120 Hz

Initial requests: Keep the ultrawide at 100% scaling and the laptop at 1.6x; improve the ultrawide experience. Later pointer-lag troubleshooting found the Dell preferred EDID mode was 60 Hz despite support for 120 Hz.

Discussion and decision: Use normal per-monitor rules for scaling, and explicitly request the Dell's native 120 Hz mode. These are independent of the layout listener. The former blanket 1.6x setting was superseded.

Result: Generic outputs use scale 1, eDP-1 uses 1.6, and DP-4 requests 6144x2560@120. The explicit connector rule depends on the Dell remaining DP-4.

Diff: Current net deviation against the installed Omarchy template, combining the related monitor-rule changes.

Sources: “Optimize Hyprland for ultrawide,” task `01a0abd3-06fd-71a0-85b4-1ec53e76c56d`; “Troubleshoot pointer lag,” task `01a0d8b3-f32d-7712-8d1c-42ab20dac42d`.

```diff
--- /usr/share/omarchy/config/hypr/monitors.lua	2026-09-15 17:04:16.000000000 -0400
+++ /home/graham/.config/hypr/monitors.lua	2026-09-25 09:18:09.300267727 -0400
@@ -1,14 +1,20 @@
 -- See https://wiki.hypr.land/Configuring/Basics/Monitors/
 -- List current monitors and supported resolutions with: hyprctl monitors all
 
-local omarchy_gdk_scale = 2
-local omarchy_monitor_scale = "auto"
+local omarchy_gdk_scale = 1
+local omarchy_monitor_scale = 1
 
 hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))
 hl.monitor({ output = "", mode = "preferred", position = "auto", scale = omarchy_monitor_scale })
 
+-- The generic rule keeps external displays at native scale. Make the
+-- high-DPI laptop panel use Omarchy's 1.6x scale preset.
+hl.monitor({ output = "eDP-1", mode = "preferred", position = "auto", scale = 1.6 })
+
 -- Configure a specific monitor.
--- hl.monitor({ output = "DP-2", mode = "2560x1440@144", position = "0x0", scale = 1 })
+-- The Dell's EDID marks 60 Hz as "preferred" even though the panel supports
+-- 120 Hz, so select the high-refresh native mode explicitly.
+hl.monitor({ output = "DP-4", mode = "6144x2560@120", position = "0x0", scale = 1 })
 
 -- Portrait/rotated secondary monitor (transform: 1 = 90°, 3 = 270°).
 -- hl.monitor({ output = "DP-2", mode = "preferred", position = "auto", scale = 1, transform = 1 })
```

## 12. Automatically select the centered ultrawide layout

Initial request: Use a wider centered Master column only when the 6144x2560 ultrawide is the sole display; retain the usual layout on the laptop and in other monitor arrangements.

Discussion and decision: Static monitor rules could handle scaling but not the required global layout selection. We added a personal session listener. Follow-up fixes handled disabled panels, Lua control syntax, saved per-workspace layouts, startup/hotplug settling, and restoring saved layouts after leaving native ultrawide mode. The initial 54% Master width was revised; the current script uses mfact=0.50 and slave_count_for_center_master=2.

Result: Installed with a Hyprland autostart entry. The complete current script is shown as a new-file diff. It includes the later manual-mode support described in the next section, avoiding an invented intermediate script. Auto selects Master only for a solo 6144x2560 output; saved workspace rules are restored in Dwindle mode.

Source: “Optimize Hyprland for ultrawide,” task `01a0abd3-06fd-71a0-85b4-1ec53e76c56d`.

```diff
--- /usr/share/omarchy/config/hypr/autostart.lua	2026-09-15 17:04:16.000000000 -0400
+++ /home/graham/.config/hypr/autostart.lua	2026-09-16 16:33:06.720811305 -0400
@@ -1,2 +1,3 @@
 -- Extra autostart processes.
 -- o.launch_on_start("my-service")
+o.launch_on_start("/home/graham/.local/bin/omarchy-hyprland-ultrawide-layout-watch")
```

```diff
--- /dev/null	2026-10-19 09:02:21.526993081 -0400
+++ /home/graham/.local/bin/omarchy-hyprland-ultrawide-layout-watch	2026-09-25 12:41:02.774647513 -0400
@@ -0,0 +1,132 @@
+#!/usr/bin/env bash
+
+# Switch layouts according to the active display set.
+# The 6144x2560 display uses a centered Master layout; every other setup
+# retains Omarchy's default Dwindle layout.
+
+set -u
+
+socket="${XDG_RUNTIME_DIR}/hypr/${HYPRLAND_INSTANCE_SIGNATURE}/.socket2.sock"
+workspace_layouts_dir="${XDG_STATE_HOME:-${HOME}/.local/state}/omarchy/workspace-layouts"
+layout_mode_state="${XDG_STATE_HOME:-${HOME}/.local/state}/omarchy/hyprland-layout-mode"
+last_layout=""
+
+layout_mode() {
+  local mode="auto"
+
+  [[ -f "${layout_mode_state}" ]] && mode=$(<"${layout_mode_state}")
+  case "${mode}" in
+    auto|master|dwindle) printf '%s\n' "${mode}" ;;
+    *) printf '%s\n' auto ;;
+  esac
+}
+
+use_ultrawide_layout() {
+  local monitors
+
+  monitors="$(hyprctl monitors -j 2>/dev/null)" || return 0
+  jq -e '
+    [.[] | select(.disabled != true)] as $active
+    | $active | length == 1
+    and $active[0].width == 6144
+    and $active[0].height == 2560
+  ' >/dev/null <<<"${monitors}"
+}
+
+apply_ultrawide_workspace_overrides() {
+  local layout_file workspace
+
+  # Omarchy remembers per-workspace layout choices here. Override only those
+  # saved rules while the ultrawide is solo; the default global layout covers
+  # workspaces with no saved rule.
+  for layout_file in "${workspace_layouts_dir}"/*.lua; do
+    [[ -e "${layout_file}" ]] || continue
+    workspace="${layout_file##*/}"
+    workspace="${workspace%.lua}"
+    [[ "${workspace}" =~ ^-?[0-9]+$ ]] || continue
+
+    hyprctl eval "hl.workspace_rule({ workspace = '${workspace}', layout = 'master' })" >/dev/null
+  done
+}
+
+restore_saved_workspace_layouts() {
+  local layout_file workspace layout
+
+  for layout_file in "${workspace_layouts_dir}"/*.lua; do
+    [[ -e "${layout_file}" ]] || continue
+    workspace="${layout_file##*/}"
+    workspace="${workspace%.lua}"
+    [[ "${workspace}" =~ ^-?[0-9]+$ ]] || continue
+
+    layout=$(sed -nE 's/.*layout[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/p' "${layout_file}" | head -1)
+    [[ "${layout}" =~ ^(dwindle|scrolling|master|monocle|lua:[A-Za-z0-9._-]+)$ ]] || continue
+
+    hyprctl eval "hl.workspace_rule({ workspace = '${workspace}', layout = '${layout}' })" >/dev/null
+  done
+}
+
+apply_layout() {
+  local desired_layout mode
+
+  mode=$(layout_mode)
+  case "${mode}" in
+    master) desired_layout="master" ;;
+    dwindle) desired_layout="dwindle" ;;
+    *)
+      if use_ultrawide_layout; then
+        desired_layout="master"
+      else
+        desired_layout="dwindle"
+      fi
+      ;;
+  esac
+
+  [[ "${desired_layout}" == "${last_layout}" ]] && return 0
+
+  if [[ "${desired_layout}" == "master" ]]; then
+    hyprctl eval "hl.config({ general = { layout = 'master' }, master = { orientation = 'center', mfact = 0.50, new_status = 'slave', slave_count_for_center_master = 2 } })" >/dev/null
+    apply_ultrawide_workspace_overrides
+  else
+    hyprctl eval "hl.config({ general = { layout = 'dwindle' } })" >/dev/null
+    # Dynamic workspace rules persist across reloads, so reapply the user's
+    # saved layouts explicitly when leaving the ultrawide-only mode.
+    restore_saved_workspace_layouts
+  fi
+
+  last_layout="${desired_layout}"
+}
+
+apply_layout_after_monitor_settles() {
+  (
+    # Monitor modes and clamshell state can settle after the first hotplug
+    # event, especially just after login or resume.
+    for delay in 1 3 7; do
+      sleep "${delay}"
+      last_layout=""
+      apply_layout
+    done
+  ) &
+}
+
+poll_layout_mode() {
+  while true; do
+    sleep 1
+    apply_layout
+  done
+}
+
+apply_layout
+apply_layout_after_monitor_settles
+poll_layout_mode &
+
+while read -r event; do
+  case "${event}" in
+    monitoradded\>\>*|monitoraddedv2\>\>*|monitorremoved\>\>*|monitorremovedv2\>\>*|configreloaded\>\>*)
+      # A reload resets runtime keywords, so deliberately reconsider even if
+      # the display arrangement itself did not change.
+      last_layout=""
+      apply_layout
+      apply_layout_after_monitor_settles
+      ;;
+  esac
+done < <(socat -U - "UNIX-CONNECT:${socket}")
```

## 13. Add manual layout selection and a bar widget

Initial request/context: Extend the automatic ultrawide layout behavior with explicit Auto/Master/Dwindle control.

Discussion and decision: Store a persistent user selection, provide a command and Super+Alt+L shortcut, and expose a bar widget. Left click cycles modes; right click returns to Auto. The listener polls the saved selection.

Result: The command, widget, and shortcut remain installed. At the October 19 audit, the saved selection was master, which overrides automatic monitor-based selection. The listener modifications are included in its complete diff in the previous section.

Diff: Complete new files plus isolated reconstructed config/state hunks.

```diff
--- /home/graham/.config/hypr/bindings.lua
+++ /home/graham/.config/hypr/bindings.lua
@@
+o.bind("SUPER + ALT + L", "Cycle layout mode", "omarchy-hyprland-layout-mode cycle")
--- /home/graham/.config/omarchy/shell.json
+++ /home/graham/.config/omarchy/shell.json
@@ bar.layout.center @@
+{ "id": "graham.layout-mode" },
--- /dev/null
+++ /home/graham/.local/state/omarchy/hyprland-layout-mode
@@
+master
```

The state hunk records the audit-time selection, not a claim that manual Master was the original default.

Source: ultrawide task, including its September 25 follow-up.

```diff
--- /dev/null	2026-10-19 09:02:21.526993081 -0400
+++ /home/graham/.local/bin/omarchy-hyprland-layout-mode	2026-09-25 12:42:20.703990954 -0400
@@ -0,0 +1,46 @@
+#!/usr/bin/env bash
+
+# Select how the personal ultrawide layout listener chooses a layout.
+
+set -u
+
+state_dir="${XDG_STATE_HOME:-${HOME}/.local/state}/omarchy"
+state_file="${state_dir}/hyprland-layout-mode"
+
+current_mode() {
+  local mode="auto"
+  [[ -f "${state_file}" ]] && mode=$(<"${state_file}")
+  case "${mode}" in
+    auto|master|dwindle) printf '%s\n' "${mode}" ;;
+    *) printf '%s\n' auto ;;
+  esac
+}
+
+set_mode() {
+  local mode="$1"
+
+  mkdir -p "${state_dir}"
+  printf '%s\n' "${mode}" >"${state_file}"
+
+  case "${mode}" in
+    auto) omarchy-notification-send "Layout mode: Auto" ;;
+    master) omarchy-notification-send "Layout mode: Master (manual)" ;;
+    dwindle) omarchy-notification-send "Layout mode: Dwindle (manual)" ;;
+  esac
+}
+
+case "${1:-status}" in
+  status) current_mode ;;
+  auto|master|dwindle) set_mode "$1" ;;
+  cycle)
+    case "$(current_mode)" in
+      auto) set_mode master ;;
+      master) set_mode dwindle ;;
+      *) set_mode auto ;;
+    esac
+    ;;
+  *)
+    echo "Usage: omarchy-hyprland-layout-mode [status|auto|master|dwindle|cycle]" >&2
+    exit 1
+    ;;
+esac
```

```diff
--- /dev/null	2026-10-19 09:02:21.526993081 -0400
+++ /home/graham/.config/omarchy/plugins/graham.layout-mode/manifest.json	2026-09-25 12:40:39.144546973 -0400
@@ -0,0 +1,17 @@
+{
+  "schemaVersion": 1,
+  "id": "graham.layout-mode",
+  "name": "Layout mode",
+  "version": "1.0.0",
+  "author": "Graham",
+  "description": "Choose automatic, Master, or Dwindle window layout behavior.",
+  "kinds": ["bar-widget"],
+  "entryPoints": { "barWidget": "BarWidget.qml" },
+  "barWidget": {
+    "displayName": "Layout mode",
+    "description": "Click to cycle Auto, Master, and Dwindle layout modes.",
+    "category": "System",
+    "allowMultiple": false,
+    "defaultSection": "right"
+  }
+}
```

```diff
--- /dev/null	2026-10-19 09:02:21.526993081 -0400
+++ /home/graham/.config/omarchy/plugins/graham.layout-mode/BarWidget.qml	2026-09-26 10:37:19.006440834 -0400
@@ -0,0 +1,71 @@
+import QtQuick
+import Quickshell
+import Quickshell.Io
+import qs.Commons
+import qs.Ui
+
+BarWidget {
+  id: root
+  moduleName: "graham.layout-mode"
+
+  property string mode: "auto"
+  // A compact grid glyph keeps the bar tidy; the hover tooltip names the mode.
+  readonly property string label: "▦"
+  readonly property string tooltip: mode === "master"
+    ? "Layout: Master (manual)"
+    : (mode === "dwindle" ? "Layout: Dwindle (manual)" : "Layout: Auto")
+
+  function refresh() {
+    if (!statusProcess.running) statusProcess.running = true
+  }
+
+  function setMode(nextMode) {
+    if (actionProcess.running) return
+    actionProcess.command = ["/home/graham/.local/bin/omarchy-hyprland-layout-mode", nextMode]
+    actionProcess.running = true
+  }
+
+  implicitWidth: button.implicitWidth
+  implicitHeight: button.implicitHeight
+
+  Component.onCompleted: refresh()
+
+  Timer {
+    interval: 1000
+    running: true
+    repeat: true
+    onTriggered: root.refresh()
+  }
+
+  Process {
+    id: statusProcess
+    command: ["/home/graham/.local/bin/omarchy-hyprland-layout-mode", "status"]
+    stdout: StdioCollector {
+      waitForEnd: true
+      onStreamFinished: {
+        var nextMode = String(text || "").trim()
+        if (nextMode === "auto" || nextMode === "master" || nextMode === "dwindle") root.mode = nextMode
+      }
+    }
+  }
+
+  Process {
+    id: actionProcess
+    onExited: root.refresh()
+  }
+
+  WidgetButton {
+    id: button
+    anchors.fill: parent
+    bar: root.bar
+    text: root.label
+    tooltipText: root.tooltip + " — left click cycles; right click returns to Auto"
+    active: root.mode !== "auto"
+    horizontalMargin: 8
+
+    onPressed: function(button) {
+      if (button === Qt.RightButton) root.setMode("auto")
+      else if (button === Qt.LeftButton) root.setMode("cycle")
+    }
+  }
+}
```

## 14. Expose Stay Awake continuously in the bar

Initial complaint: Missing external-monitor blanking/locking was traced to Omarchy's persistent Stay Awake toggle. Its icon was difficult to find when inactive.

Discussion and decision: We verified the persistent flag and ruled out automatic monitor-based activation. You toggled it off. To make the state obvious, we split the indicator group and gave Stay Awake its own always-visible instance rather than cloning the Monitor widget.

Result: Applied September 24 and still configured. This UI change is separate from the logind docked-suspend repair; Stay Awake suppresses idle locking/screensaver behavior.

Diff: Historical structural change, normalized as compact JSON objects. The custom layout widget was added separately.

```diff
--- /home/graham/.config/omarchy/shell.json
+++ /home/graham/.config/omarchy/shell.json
@@ bar.layout.center @@
-{ "id": "omarchy.indicators" },
+{ "id": "omarchy.indicators", "items": ["Dictation", "ScreenRecording", "Reminder", "NightLight", "Dnd"] },
+{ "id": "omarchy.indicators", "items": ["StayAwake"], "alwaysShow": true },
```

Source: “Fix monitor switching sleep,” September 24 follow-up.

## 15. Preserve custom bar tray and battery display state

Initial preference: Keep desired tray icons visible and display the battery percentage. Exact provenance for each current UI preference is incomplete.

Discussion summary: The current tray pins chrome_status_icon_1 and has no explicitly hidden entries. Battery showPercentage is enabled. The earlier request to eliminate the tray expansion limit does not establish that a max-visible patch was actually applied.

Result: These are verified saved user preferences; do not infer an unlimited-tray implementation from them. Bluetooth is already in the shipped bar layout and is excluded as a custom addition.

Diff: Semantic reconstruction of the relevant saved settings; formatting normalized.

```diff
--- /home/graham/.config/omarchy/shell.json (without saved preferences)
+++ /home/graham/.config/omarchy/shell.json
@@ bar.layout.right @@
-{ "id": "omarchy.tray" },
+{ "id": "omarchy.tray", "pinned": ["chrome_status_icon_1"], "hidden": [] },
@@
-{ "id": "omarchy.power" }
+{ "id": "omarchy.power", "showPercentage": true }
```

## 16. Use smaller terminal fonts

Initial preference: Smaller terminal text. Exact original request text was not recovered.

Discussion summary: The current defaults comparison establishes font size 8 in Alacritty, Kitty and Ghostty. Alacritty also leaves explicit face-style selection unspecified. Kitty retains much older copied template content; most of it matches the current system defaults in /etc/xdg/kitty/kitty.conf and is not an additional personal customization.

Result: Foot now matches its size-9 template, so it is excluded from the current changes. Font/style choices below are current net differences, not a proven sequence of edits.

Diffs: Exact installed-template comparisons for Alacritty/Ghostty; isolated Kitty font hunk.

```diff
--- /etc/xdg/kitty/kitty.conf (inherited default)
+++ /home/graham/.config/kitty/kitty.conf (user override)
@@
-font_size        9.0
+font_size 8.0
```

```diff
--- /usr/share/omarchy/config/alacritty/alacritty.toml	2026-09-15 17:04:16.000000000 -0400
+++ /home/graham/.config/alacritty/alacritty.toml	2026-10-01 18:56:22.195268993 -0400
@@ -7,10 +7,10 @@
 osc52 = "CopyPaste"
 
 [font]
-normal = { family = "JetBrainsMono Nerd Font", style = "Regular" }
-bold = { family = "JetBrainsMono Nerd Font", style = "Bold" }
-italic = { family = "JetBrainsMono Nerd Font", style = "Italic" }
-size = 9
+normal = { family = "JetBrainsMono Nerd Font" }
+bold = { family = "JetBrainsMono Nerd Font" }
+italic = { family = "JetBrainsMono Nerd Font" }
+size = 8
 
 [window]
 padding.x = 14
```

```diff
--- /usr/share/omarchy/config/ghostty/config	2026-09-15 17:04:16.000000000 -0400
+++ /home/graham/.config/ghostty/config	2026-10-01 18:51:28.749934042 -0400
@@ -4,7 +4,7 @@
 # Font
 font-family = "JetBrainsMono Nerd Font"
 font-style = Regular
-font-size = 9
+font-size = 8
 
 # Window
 window-theme = ghostty
```

## 17. Stop Enter from accepting Neovim completions

Initial complaint: Enter accepted completion suggestions when you intended to insert a newline.

Discussion and decision: We discussed removing Enter acceptance and the side effects of using Tab, including interaction with snippets and AI suggestions. The current personal Blink spec chooses super-tab while retaining Ctrl-Y as an accept key. The discussion task did not record the write itself; the file was later verified present.

Result: The file remains installed. Tab accepts completion, Enter falls back to its ordinary behavior, and command-line completion has a separate mapping.

Diff: Complete new user override.

Source: “Find minimal nvim Enter fix,” task `01a080ea-ea6d-7390-9b86-fec68fd12cdb`.

```diff
--- /dev/null	2026-10-19 09:02:21.526993081 -0400
+++ /home/graham/.config/nvim/lua/plugins/blink.lua	2026-09-08 08:20:06.779929825 -0400
@@ -0,0 +1,11 @@
+return {
+  {
+    "saghen/blink.cmp",
+    opts = {
+      keymap = {
+        preset = "super-tab",
+        ["<C-y>"] = { "select_and_accept" },
+      },
+    },
+  },
+}
```

## 18. Temporarily repair Codex limit reporting

Initial complaint: The agent panel showed token counts but reported Codex limits unavailable.

Discussion and decision: Token totals came from local session files, while allowance windows required an app-server query. The collector passed the removed untrusted approval mode. We patched the packaged collector to use on-request and retained a .bak copy.

Result: The task recorded working limit meters. The currently installed collector uses on-request, but that alone does not prove whether the installed package has incorporated the fix. Treat this as a confirmed historical local patch whose current divergence from a pristine package was not re-established.

Diff: Historical one-line semantic reconstruction; the /usr/share path and /usr/bin path referred to the same packaged target.

```diff
--- /usr/bin/omarchy-agent-usage-codex
+++ /usr/bin/omarchy-agent-usage-codex
@@ app-server command @@
-      [codex, "-s", "read-only", "-a", "untrusted", "app-server"],
+      [codex, "-s", "read-only", "-a", "on-request", "app-server"],
```

Source: “Investigate Codex limits status,” task `01a049cd-e3da-72f2-baad-ef7c06336bd3`.

## Scope corrections and investigations without an applied customization

- **Lock-before-suspend delay:** `/etc/systemd/logind.conf.d/20-inhibit-delay.conf` sets `InhibitDelayMaxSec=15`, but Omarchy migration `1784970000.sh` explicitly describes this as a shipped drop-in. The previous summary incorrectly classified it as a confirmed personal repair. There is no supported local-change diff to present.
- **Bluetooth widget:** the original August 30 task found Bluetooth already configured and restarted the shell. It did not add the widget. Bluetooth also exists in the current shipped bar layout.
- **tmux and Starship:** compared user files matched installed templates in the audit; their bindings, prompt and CSI-u support are not personal changes.
- **Terminal keyboard translation:** Shift+Enter and Alt+Shift+Enter CSI-u mappings are shipped defaults. Kitty moved these defaults to `/etc/xdg/kitty/kitty.conf`; retaining older user-file copies does not prove a new local feature.
- **Other Neovim files:** clipboard, transparency, theme hot reload, disabled animated scrolling and news settings were already present, but their provenance was not established. They are excluded from the verified change history rather than attributed to us.
- **Claude usage reporting:** traced to expired authentication. The recommendation was to sign in again; no panel-config repair was recorded.
- **Zsh migration:** discussed, not installed as part of this work.
- **Fingerprint workarounds:** no custom resume-restart service, lock-plugin clone or libfprint package was installed in the reviewed task.
- **Thunderbolt no-video issue (September 24):** diagnosed display-link flapping and recommended cable/port/power-cycle/monitor-firmware checks. No Omarchy configuration edit was made in that task.
- **Pointer lag (September 25):** the persistent display-mode change is in section 11. Performance-profile testing was reverted to balanced. Moving the wireless receiver to another monitor USB port improved the problem; that physical change has no file diff.
- **Power-button policy:** `/etc/systemd/logind.conf.d/10-ignore-power-button.conf` exists, but the audit did not establish it as a personal change; it is not silently counted as one.

No live suspend or monitor-switching test was performed during this documentation audit. The docked-suspend result relies on the recorded successful user tests and the continued presence of the installed rule.

