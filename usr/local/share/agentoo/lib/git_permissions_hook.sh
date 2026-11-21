#!/usr/bin/env bash
set -Eeuo pipefail
# Canonical paths: usr/local/share/agentoo/lib/paths.py (SYSTEM_GIT_DIR/SYSTEM_WORK_TREE).
# Invoked by Git config hooks for the installed system repository only.
[[ $(git rev-parse --show-toplevel) == / ]] || exit 0
[[ $(git rev-parse --absolute-git-dir) == /var/lib/agentoo/repository.git ]] || exit 0
mode=check
if [[ ${1:-} == fix && $EUID == 0 ]]; then mode=fix; fi
if ! /usr/local/bin/agentoo permissions "$mode"; then
  printf 'agentoo: permissions need attention; run agentoo permissions fix as root.\n' >&2
  exit 1
fi
