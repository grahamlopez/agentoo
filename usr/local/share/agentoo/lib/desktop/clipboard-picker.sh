#!/bin/bash
# cliphist's fzf recipe, with cancellation leaving the clipboard untouched.
set -euo pipefail

if selection=$(cliphist list | fzf --no-sort --prompt='Clipboard> ' \
    --header='Enter: copy | Shift+Delete: delete entry | Esc: close' \
    --bind "shift-delete:execute-silent(printf '%s\\n' {1} | cliphist delete)+reload(cliphist list)"); then
    printf '%s\n' "$selection" | cliphist decode | wl-copy
fi
