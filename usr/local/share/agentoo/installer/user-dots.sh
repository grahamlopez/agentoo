#!/usr/bin/env bash
#
# One-way terminal user environment installer for non-agentoo Linux hosts.
#
# Run directly without cloning the agentoo repository:
#   curl -fsSL https://raw.githubusercontent.com/grahamlopez/agentoo/main/usr/local/share/agentoo/installer/user-dots.sh | bash
#
# Inspect planned changes first:
#   curl -fsSL https://raw.githubusercontent.com/grahamlopez/agentoo/main/usr/local/share/agentoo/installer/user-dots.sh | bash -s -- --dry-run
#
# Installs managed config files into $XDG_DATA_HOME/agentoo/user-dots (default:
# ~/.local/share/agentoo/user-dots), softlock.nvim into Neovim's user packpath,
# and minimal native include stubs in $HOME for zsh, tmux, vim, nvim, and git.
# Existing unmanaged $HOME files are backed up automatically with a warning.

if [[ -z ${BASH_VERSION:-} ]]; then
  printf 'error: this installer requires Bash.\n' >&2
  exit 1
fi

set -Eeuo pipefail
IFS=$'\n\t'

readonly PROGRAM='user-dots.sh'
readonly MARKER='agentoo-user-dots: managed loader'
readonly AGENTOO_RAW_BASE='https://raw.githubusercontent.com/grahamlopez/agentoo'
readonly SOFTLOCK_ARCHIVE_BASE='https://github.com/grahamlopez/softlock.nvim/archive'

# Tracked agentoo paths mapped to relative destinations under $BUNDLE_DIR.
readonly MANIFEST=(
  'etc/zsh/zshrc:zsh/zshrc'
  'etc/tmux.conf:tmux.conf'
  'etc/vim/vimrc.local:vim/vimrc.local'
  'etc/xdg/nvim/agentoo.lua:nvim/agentoo.lua'
  'etc/xdg/nvim/queries/markdown/highlights.scm:nvim/queries/markdown/highlights.scm'
  'usr/local/share/nvim/site/after/ftplugin/markdown.lua:nvim/site/after/ftplugin/markdown.lua'
  'etc/agentoo/gitconfig-user:git/gitconfig-user'
  'etc/agentoo/gitignore-user:git/gitignore-user'
  'usr/local/share/agentoo/lib/git_wrap_commit_msg.py:git/git_wrap_commit_msg.py'
)

DRY_RUN=0
AGENTOO_REF='main'
SOFTLOCK_REF='main'
SOURCE_DIR=''
SOFTLOCK_DIR_SRC=''

STAGE_DIRS=()
BACKUPS=()

usage() {
  cat <<EOF
Usage: $PROGRAM [options]

Deploy agentoo's terminal user configuration (zsh, tmux, vim, nvim + softlock.nvim,
git) into \$HOME on a non-agentoo Linux host without cloning the agentoo repository.

Options:
  --dry-run              Show planned downloads, backups, and writes without making changes.
  --ref REF              Agentoo Git ref (branch, tag, or commit) to fetch (default: main).
  --softlock-ref REF     softlock.nvim Git ref to fetch (default: main).
  --source-dir DIR       Copy agentoo files from a local checkout instead of downloading.
  --softlock-dir DIR     Copy softlock.nvim from a local checkout instead of downloading.
  -h, --help             Show this help message and exit.
EOF
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  local dir
  for dir in "${STAGE_DIRS[@]}"; do
    if [[ -n $dir && -d $dir ]]; then
      rm -rf -- "$dir"
    fi
  done
}
trap cleanup EXIT

parse_args() {
  while (( $# > 0 )); do
    case "$1" in
      --dry-run)
        DRY_RUN=1
        shift
        ;;
      --ref)
        (( $# >= 2 )) || die '--ref requires a value'
        AGENTOO_REF=$2
        shift 2
        ;;
      --softlock-ref)
        (( $# >= 2 )) || die '--softlock-ref requires a value'
        SOFTLOCK_REF=$2
        shift 2
        ;;
      --source-dir)
        (( $# >= 2 )) || die '--source-dir requires a value'
        SOURCE_DIR=$2
        shift 2
        ;;
      --softlock-dir)
        (( $# >= 2 )) || die '--softlock-dir requires a value'
        SOFTLOCK_DIR_SRC=$2
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "unknown option: $1 (see --help)"
        ;;
    esac
  done
}

# Match usr/local/share/agentoo/lib/xdg.py: accept only absolute XDG paths.
xdg_dir() {
  local value=$1 fallback=$2
  if [[ $value == /* ]]; then
    printf '%s\n' "${value%/}"
  else
    printf '%s/%s\n' "${HOME%/}" "$fallback"
  fi
}

sh_quote() {
  local s=$1
  printf "'%s'" "${s//\'/\'\\\'\'}"
}

vim_sq_escape() {
  local s=$1
  printf '%s' "${s//\'/\'\'}"
}

dq_escape() {
  local s=$1
  s=${s//\\/\\\\}
  s=${s//\"/\\\"}
  printf '%s' "$s"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

fetch_url() {
  local url=$1 dest=$2
  curl -fsSL --retry 2 --connect-timeout 15 -o "$dest" -- "$url" \
    || die "failed to download $url"
}

backup_path_for() {
  local target=$1 stamp=$2 candidate n=1
  candidate="${target}.pre-agentoo.${stamp}"
  while [[ -e $candidate || -L $candidate ]]; do
    candidate="${target}.pre-agentoo.${stamp}.${n}"
    n=$((n + 1))
  done
  printf '%s\n' "$candidate"
}

loud_backup_warning() {
  local original=$1 backup=$2
  cat >&2 <<EOF

========================================================================
WARNING: Backed up existing unmanaged file before installing managed stub:
  original: $original
  backup:   $backup
Review the backup and move any host-local overrides you want to keep
below the managed loader in $original.
========================================================================

EOF
}

stage_bundle() {
  local stage_root=$1 entry src dst target
  for entry in "${MANIFEST[@]}"; do
    src=${entry%%:*}
    dst=${entry#*:}
    target="$stage_root/$dst"
    mkdir -p -- "$(dirname -- "$target")"
    if [[ -n $SOURCE_DIR ]]; then
      [[ -r "$SOURCE_DIR/$src" ]] || die "missing source file: $SOURCE_DIR/$src"
      cp -- "$SOURCE_DIR/$src" "$target"
    else
      fetch_url "$AGENTOO_RAW_BASE/$AGENTOO_REF/$src" "$target"
    fi
    chmod 0644 -- "$target"
  done
  chmod 0755 -- "$stage_root/git/git_wrap_commit_msg.py"
}

stage_softlock() {
  local stage_root=$1 src_tree=$2 archive_tmp extracted top item
  if [[ -n $src_tree ]]; then
    [[ -d "$src_tree/plugin" ]] || die "invalid softlock directory (missing plugin/): $src_tree"
    top=$src_tree
  else
    archive_tmp=$(mktemp -d)
    STAGE_DIRS+=("$archive_tmp")
    fetch_url "$SOFTLOCK_ARCHIVE_BASE/$SOFTLOCK_REF.tar.gz" "$archive_tmp/softlock.tar.gz"
    extracted="$archive_tmp/extract"
    mkdir -p -- "$extracted"
    tar -xzf "$archive_tmp/softlock.tar.gz" -C "$extracted"
    top=$(find "$extracted" -mindepth 1 -maxdepth 1 -type d | head -n 1)
    [[ -n $top && -d "$top/plugin" ]] || die 'downloaded softlock.nvim archive is missing plugin/'
  fi

  mkdir -p -- "$stage_root"
  cp -R -- "$top/plugin" "$stage_root/plugin"
  if [[ -d "$top/doc" ]]; then
    cp -R -- "$top/doc" "$stage_root/doc"
  fi
  for item in README.md LICENSE; do
    if [[ -f "$top/$item" ]]; then
      cp -- "$top/$item" "$stage_root/$item"
    fi
  done
}

swap_dir() {
  local staged=$1 dest=$2 prev=''
  mkdir -p -- "$(dirname -- "$dest")"
  if [[ -e $dest || -L $dest ]]; then
    prev="${dest}.prev.$$"
    rm -rf -- "$prev"
    mv -- "$dest" "$prev"
  fi
  if mv -- "$staged" "$dest"; then
    if [[ -n $prev ]]; then
      rm -rf -- "$prev"
    fi
  else
    if [[ -n $prev ]]; then
      mv -- "$prev" "$dest"
    fi
    die "failed to install directory: $dest"
  fi
}

install_stub() {
  local target=$1 content=$2 stamp=$3 backup
  if [[ -f $target ]] && grep -Fq -- "$MARKER" "$target"; then
    printf 'keep    %s (already managed; local overrides preserved)\n' "$target"
    return 0
  fi

  if [[ -e $target || -L $target ]]; then
    backup=$(backup_path_for "$target" "$stamp")
    if (( DRY_RUN )); then
      printf 'backup  %s -> %s\n' "$target" "$backup"
      printf 'write   %s\n' "$target"
      return 0
    fi
    mv -- "$target" "$backup"
    BACKUPS+=("$target -> $backup")
    loud_backup_warning "$target" "$backup"
  elif (( DRY_RUN )); then
    printf 'create  %s\n' "$target"
    return 0
  fi

  mkdir -p -- "$(dirname -- "$target")"
  printf '%s\n' "$content" > "$target"
  printf 'write   %s\n' "$target"
}

render_zshrc_stub() {
  local bundle=$1
  cat <<EOF
# $MARKER
# Add host-local overrides below this line.
source $(sh_quote "$bundle/zsh/zshrc")
EOF
}

render_tmux_stub() {
  local bundle=$1
  cat <<EOF
# $MARKER
# Add host-local overrides below this line.
source-file "$(dq_escape "$bundle/tmux.conf")"
EOF
}

render_vimrc_stub() {
  local bundle=$1
  cat <<EOF
" $MARKER
" Add host-local overrides below this line.
execute 'source ' . fnameescape('$(vim_sq_escape "$bundle/vim/vimrc.local")')
EOF
}

render_nvim_stub() {
  local bundle=$1
  cat <<EOF
-- $MARKER
-- Add host-local overrides below this line.
local _agentoo_dots = "$(dq_escape "$bundle")"
local _user_cfg = vim.fn.stdpath("config")
local _user_after = _user_cfg .. "/after"
vim.opt.rtp:prepend(_agentoo_dots .. "/nvim")
vim.opt.rtp:remove(_user_cfg)
vim.opt.rtp:prepend(_user_cfg)
vim.opt.rtp:append(_agentoo_dots .. "/nvim/site/after")
vim.opt.rtp:remove(_user_after)
vim.opt.rtp:append(_user_after)
dofile(_agentoo_dots .. "/nvim/agentoo.lua")
EOF
}

render_gitconfig_stub() {
  local bundle=$1
  cat <<EOF
# $MARKER
# Add host-local overrides below or in ~/.gitconfig-local.
[include]
    path = "$(dq_escape "$bundle/git/gitconfig-user")"
[core]
    excludesFile = "$(dq_escape "$bundle/git/gitignore-user")"
[hook "wrap-commit-msg"]
    event = commit-msg
    command = "$(dq_escape "$(sh_quote "$bundle/git/git_wrap_commit_msg.py")")"
[include]
    path = ~/.gitconfig-local
EOF
}

print_host_notes() {
  local tool missing=()
  for tool in zsh tmux nvim vim git rg fzf fd gpg python3; do
    command -v "$tool" >/dev/null 2>&1 || missing+=("$tool")
  done
  if (( ${#missing[@]} > 0 )); then
    printf 'note: optional host tools not installed: %s\n' "${missing[*]}"
  fi
  if [[ ${SHELL:-} != */zsh ]] && command -v zsh >/dev/null 2>&1; then
    printf 'note: current login shell is %s; switch with: chsh -s "%s"\n' \
      "${SHELL:-unset}" "$(command -v zsh)"
  fi
  if [[ ! -e "$HOME/.gitconfig-local" ]]; then
    printf 'note: put personal Git identity (user.name, user.email) in ~/.gitconfig-local\n'
  fi
}

main() {
  parse_args "$@"
  [[ -n ${HOME:-} && -d $HOME ]] || die 'HOME must be set to an existing directory'

  if [[ -z $SOURCE_DIR || -z $SOFTLOCK_DIR_SRC ]]; then
    require_cmd curl
  fi
  if [[ -z $SOFTLOCK_DIR_SRC ]]; then
    require_cmd tar
  fi

  local data_home config_home bundle_dir softlock_dir stamp
  data_home=$(xdg_dir "${XDG_DATA_HOME:-}" '.local/share')
  config_home=$(xdg_dir "${XDG_CONFIG_HOME:-}" '.config')
  bundle_dir="$data_home/agentoo/user-dots"
  softlock_dir="$data_home/nvim/site/pack/agentoo/start/softlock"
  stamp=$(date +%Y%m%d-%H%M%S)

  if (( DRY_RUN )); then
    printf 'dry-run: no files will be modified\n'
    if [[ -n $SOURCE_DIR ]]; then
      printf 'source  %s -> %s (%d files)\n' "$SOURCE_DIR" "$bundle_dir" "${#MANIFEST[@]}"
    else
      printf 'fetch   %s/%s -> %s (%d files)\n' "$AGENTOO_RAW_BASE" "$AGENTOO_REF" "$bundle_dir" "${#MANIFEST[@]}"
    fi
    if [[ -n $SOFTLOCK_DIR_SRC ]]; then
      printf 'source  %s -> %s\n' "$SOFTLOCK_DIR_SRC" "$softlock_dir"
    else
      printf 'fetch   %s/%s.tar.gz -> %s\n' "$SOFTLOCK_ARCHIVE_BASE" "$SOFTLOCK_REF" "$softlock_dir"
    fi
  else
    mkdir -p -- "$data_home/agentoo" "$data_home/nvim/site/pack/agentoo/start"
    local staged_bundle staged_softlock
    staged_bundle=$(mktemp -d "$data_home/agentoo/.user-dots-stage.XXXXXX")
    STAGE_DIRS+=("$staged_bundle")
    staged_softlock=$(mktemp -d "$data_home/nvim/site/pack/agentoo/start/.softlock-stage.XXXXXX")
    STAGE_DIRS+=("$staged_softlock")

    # Stage everything before touching any live destination so partial failures leave $HOME intact.
    stage_bundle "$staged_bundle"
    stage_softlock "$staged_softlock" "$SOFTLOCK_DIR_SRC"

    swap_dir "$staged_bundle" "$bundle_dir"
    swap_dir "$staged_softlock" "$softlock_dir"
    printf 'install %s\n' "$bundle_dir"
    printf 'install %s\n' "$softlock_dir"

    if [[ -d "$softlock_dir/doc" ]] && command -v nvim >/dev/null 2>&1; then
      if ! nvim --headless -u NONE -i NONE -n -c "execute 'helptags ' . fnameescape('$(vim_sq_escape "$softlock_dir/doc")')" -c 'quit' >/dev/null 2>&1; then
        printf 'warning: failed to generate Neovim helptags for softlock.nvim\n' >&2
      fi
    fi
  fi

  install_stub "$HOME/.zshrc" "$(render_zshrc_stub "$bundle_dir")" "$stamp"
  install_stub "$HOME/.tmux.conf" "$(render_tmux_stub "$bundle_dir")" "$stamp"
  install_stub "$HOME/.vimrc" "$(render_vimrc_stub "$bundle_dir")" "$stamp"
  install_stub "$config_home/nvim/init.lua" "$(render_nvim_stub "$bundle_dir")" "$stamp"
  install_stub "$HOME/.gitconfig" "$(render_gitconfig_stub "$bundle_dir")" "$stamp"

  if (( ! DRY_RUN )); then
    print_host_notes
    if (( ${#BACKUPS[@]} > 0 )); then
      printf '\nBACKUP SUMMARY (review and merge any local settings you want to keep):\n' >&2
      local entry
      for entry in "${BACKUPS[@]}"; do
        printf '  %s\n' "$entry" >&2
      done
    fi
  fi
}

main "$@"
