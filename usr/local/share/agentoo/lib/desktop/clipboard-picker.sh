#!/bin/bash
# cliphist's fzf recipe, with cancellation leaving the clipboard untouched.
set -euo pipefail

if selection=$(cliphist list | fzf --no-sort --prompt='Clipboard> ' \
    --header='Enter: copy | Shift+Delete: delete entry | Esc: close' \
    --bind "shift-delete:execute-silent(printf '%s\\n' {1} | cliphist delete)+reload(cliphist list)"); then
    # wl-copy forks to serve the selection. Keep its inherited stderr off the
    # terminal so Kitty can close, while retaining diagnostics in the journal.
    printf '%s\n' "$selection" | cliphist decode | systemd-cat -t agentoo-clipboard wl-copy
fi
