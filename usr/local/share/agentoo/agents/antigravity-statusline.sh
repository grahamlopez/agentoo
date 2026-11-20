#!/usr/bin/env bash
set -euo pipefail

input=$(cat)

mapfile -t f < <(
  jq -r '
    def clean: if . == null then "" else tostring | gsub("[\r\n]+"; " ") end;
    (
      .quota["gemini-5h"]
      // ((.quota // {}) | to_entries | map(select(.key | test("5h"; "i"))) | first | .value)
    ) as $q5h |
    [
      (.cycle_mode | if type == "object" then (.name // .id // .mode // "default") elif type == "string" and length > 0 then . else "default" end),
      (.model.display_name // .model.id // "model"),
      (.effort // .model.effort // .thinking_level // .reasoning_effort // ""),
      (.workspace.current_dir // .cwd // ""),
      (.vcs.branch // .git_branch // ""),
      (if .vcs.dirty == true then "1" else "0" end),
      (.conversation_title // .session_name // .session.name // .conversation.title // .session_id // ""),
      (.context_window.remaining_percentage | if . == null then "" else (round | tostring) end),
      (
        (
          $q5h.remaining_fraction
          // (if .rate_limits.five_hour.used_percentage != null then (100 - .rate_limits.five_hour.used_percentage) / 100 else null end)
        ) | if . == null then "" else ((. * 100) | round | tostring) end
      ),
      ($q5h.reset_in_seconds | if . == null then "" else (floor | tostring) end)
    ] | .[] | clean
  ' <<<"$input"
)

mode=${f[0]:-default}
model=${f[1]:-model}
effort=${f[2]:-}
cwd=${f[3]:-}
branch=${f[4]:-}
dirty=${f[5]:-0}
session=${f[6]:-}
ctx_pct=${f[7]:-}
q5h_pct=${f[8]:-}
q5h_secs=${f[9]:-}

# Fall back to git if branch isn't in the JSON payload
if [[ -z "$branch" && -n "$cwd" && -d "$cwd" ]]; then
  branch=$(git -C "$cwd" rev-parse --abbrev-ref HEAD 2>/dev/null || true)
fi

# Shorten cwd (~ for HOME; keep trailing segments if deep)
dir="${cwd/#$HOME/\~}"
if [[ "$dir" == */*/*/* ]]; then
  dir="…/${dir#*/*/}"
fi

# Truncate long session names
if (( ${#session} > 40 )); then
  session="${session:0:39}…"
fi

# ANSI palette
R=$'\033[0m'
DIM=$'\033[2m'
BOLD=$'\033[1m'
CYAN=$'\033[36m'
MAGENTA=$'\033[35m'
BLUE=$'\033[34m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
RED=$'\033[31m'
SEP=" ${DIM}│${R} "

join_parts() {
  local out="" p
  for p in "$@"; do
    out+="${out:+$SEP}${p}"
  done
  printf '%s\n' "$out"
}

line1=()
line2=()

# Line 1: mode, model + effort, directory + git branch
case "${mode,,}" in
  auto)         mode_color="${BOLD}${YELLOW}" ;;
  accept-edits) mode_color="${BOLD}${GREEN}" ;;
  plan)         mode_color="${BOLD}${BLUE}" ;;
  *)            mode_color="${DIM}" ;;
esac
line1+=("${mode_color}[${mode}]${R}")

model_str="${BOLD}${CYAN}${model}${R}"
if [[ -n "$effort" && "${model,,}" != *"(${effort,,})"* ]]; then
  model_str+=" ${MAGENTA}(${effort})${R}"
fi
line1+=("$model_str")

loc=""
[[ -n "$dir" ]] && loc="${BLUE}${dir}${R}"
if [[ -n "$branch" ]]; then
  dirty_mark=""
  [[ "$dirty" == "1" ]] && dirty_mark="${YELLOW}*${R}"
  loc+="${loc:+ }${GREEN}${branch}${dirty_mark}${R}"
fi
[[ -n "$loc" ]] && line1+=("$loc")

# Line 2: session name, context remaining, 5h quota remaining + reset countdown
[[ -n "$session" ]] && line2+=("${DIM}${session}${R}")

if [[ -n "$ctx_pct" ]]; then
  c=$GREEN
  (( ctx_pct <= 15 )) && c=$RED || { (( ctx_pct <= 40 )) && c=$YELLOW; }
  line2+=("${DIM}ctx${R} ${c}${ctx_pct}%${R}")
else
  line2+=("${DIM}ctx --${R}")
fi

if [[ -n "$q5h_pct" ]]; then
  q=$GREEN
  (( q5h_pct <= 15 )) && q=$RED || { (( q5h_pct <= 40 )) && q=$YELLOW; }
  q5h_str="${DIM}5h${R} ${q}${q5h_pct}%${R}"
  if [[ -n "$q5h_secs" && "$q5h_secs" =~ ^[0-9]+$ ]] && (( q5h_secs > 0 )); then
    h=$(( q5h_secs / 3600 ))
    m=$(( (q5h_secs % 3600) / 60 ))
    if (( h > 0 )); then
      q5h_str+=" ${DIM}(${h}h ${m}m)${R}"
    elif (( m > 0 )); then
      q5h_str+=" ${DIM}(${m}m)${R}"
    else
      q5h_str+=" ${DIM}(<1m)${R}"
    fi
  fi
  line2+=("$q5h_str")
else
  line2+=("${DIM}5h --${R}")
fi

join_parts "${line1[@]}"
join_parts "${line2[@]}"
