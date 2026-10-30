# Base desktop conflict handling on active configuration

Created: 2026-10-30
Status: Backlog

`lib/desktop/common.py:authored_hypr_paths` scans every `.lua` and `.conf`
under the user's Hyprland directory. Blur and transparency use regex matches
from that scan to block some saves and loads. An unused configuration copy can
therefore be treated as competing policy even though Hyprland never loads it.

The requirement is to avoid competing window rules without rewriting authored
configuration. Establish explicit ownership and precedence, then narrow
blocking checks to evidence of active conflicts. Investigate available native
information before choosing a mechanism; do not build a Lua evaluator or assume
a native API completely answers the question. Account for includes from the
active personal entry file rather than merely checking that file alone.

Complete when unused files cannot block appearance changes, real competing
rules remain understandable, and full-reset recovery works. Verify inactive
copies, active includes/conflicts, and saved-state loading; run affected
Python/Lua tests and validate behavior in Hyprland.
