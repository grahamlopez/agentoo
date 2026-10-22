#!/bin/bash
# Read the desktop clipboard on demand, preserving tmux's existing buffers.
set -euo pipefail
socket=$1
pane=$2
tmux_cmd=(tmux -S "$socket")

# Ordinary tmux paste remains available in sessions without Wayland.
if [[ -z ${WAYLAND_DISPLAY:-} ]]; then
    exec "${tmux_cmd[@]}" paste-buffer -p -t "$pane"
fi

buffer="agentoo-clipboard-$$"
file=$(mktemp)
trap 'rm -f "$file"; "${tmux_cmd[@]}" delete-buffer -b "$buffer" 2>/dev/null || true' EXIT

# Stage the read before loading: a failed clipboard read must not paste stale
# data. --no-newline preserves trailing newlines exactly as provided.
if ! timeout 3 wl-paste --no-newline --type text > "$file"; then
    "${tmux_cmd[@]}" display-message -t "$pane" 'Clipboard unavailable; use prefix = for tmux buffers'
    exit 1
fi
"${tmux_cmd[@]}" load-buffer -b "$buffer" "$file"
"${tmux_cmd[@]}" paste-buffer -d -p -b "$buffer" -t "$pane"
