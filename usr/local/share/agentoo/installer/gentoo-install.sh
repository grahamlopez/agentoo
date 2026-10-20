#!/usr/bin/env bash
#
# Repeatable Gentoo installer — first milestone
#
# Download and run this single file; no local repository checkout is needed:
#   curl -fL https://raw.githubusercontent.com/grahamlopez/agentoo/main/usr/local/share/agentoo/installer/gentoo-install.sh -o gentoo-install.sh
#   bash ./gentoo-install.sh --disk /dev/REPLACE_WITH_TARGET_DISK --target-host generic [options]
# Keep the downloaded file available: child chroot phases copy this same script.
# Stage3 and the target configuration are fetched during installation.
#
# This file is both the executable installer and its canonical design record.
# Each phase begins with its own readable explanation immediately beside the
# code that implements it.  Run with `--verbose` to print the technical notes
# for each selected phase, or read the source directly.
#
# This installer currently owns seven phases:
#   disk-setup: validate the target, then create GPT → EFI → LUKS2 → Btrfs →
#   @ + @home.
#   stage3-bootstrap: obtain and verify the current official AMD64 desktop-
#   systemd stage3, extract it, and prepare a chroot environment.
#   portage-foundation: install the live configuration work tree, configure
#   Portage for Git synchronization, and establish locale and timezone.
#   system-update: establish CPU policy, update @world, and review configuration.
#   kernel-foundation: install the binary distribution kernel, firmware, and
#   broad initramfs, then validate EFI files and register QEMU firmware offline.
#   first-boot-foundation: configure mounts, identity, root login, minimal
#   networking, packaged journal defaults, time synchronization and Btrfs scrubbing.
#   handoff: verify the mounted target and print manual cleanup and boot guidance.
#
# It executes selected phases by default.  Use --dry-run to print plans without
# making changes.  Disk setup also requires confirmation of the exact target.
# kernel-foundation prepares the distribution fallback and QEMU EFI entry.
# Physical EFI registration and actual boot verification remain manual; custom kernels
# are built after installation.

if [[ -z ${BASH_VERSION:-} ]]; then
  printf 'error: this installer requires Bash.\n' >&2
  exit 1
fi

set -Eeuo pipefail
IFS=$'\n\t'

readonly PROGRAM=${0##*/}
readonly DEFAULT_EFI_SIZE='1G'
readonly STAGE3_BASE_URL='https://distfiles.gentoo.org/releases/amd64/autobuilds/current-stage3-amd64-desktop-systemd'
readonly STAGE3_LATEST_MANIFEST='latest-stage3-amd64-desktop-systemd.txt'
readonly GENTOO_RELEASE_KEYS_URL='https://dev.gentoo.org/~sam/dist/sec-keys/openpgp-keys-gentoo-release/gentoo-release.asc.20260125.gz'
readonly GENTOO_AUTOMATED_RELEASE_FINGERPRINT='13EBBDBEDE7A12775DFDB1BABB572E0E2D182910'
readonly GENTOO_REPOSITORY_URL='https://github.com/gentoo-mirror/gentoo.git'
readonly GENTOO_REPOSITORY_SIGNING_FINGERPRINT='EF9538C9E8E64311A52CDEDFA13D0EF1914E7A72'
readonly DEFAULT_CONFIG_SOURCE='https://github.com/grahamlopez/agentoo.git'
readonly DEFAULT_CONFIG_BRANCH='main'
readonly DEFAULT_TIMEZONE='America/New_York'
readonly DEFAULT_LOCALE='en_US.UTF-8'

TARGET_DISK=${TARGET_DISK:-}
LUKS_NAME=${LUKS_NAME:-cryptroot}
BTRFS_LABEL=${BTRFS_LABEL:-GENTOO}
readonly ROOT_SUBVOL=@
readonly HOME_SUBVOL=@home
EFI_SIZE=${EFI_SIZE:-$DEFAULT_EFI_SIZE}
MOUNT_ROOT=${MOUNT_ROOT:-/mnt/gentoo}
CONFIG_SOURCE=${CONFIG_SOURCE:-$DEFAULT_CONFIG_SOURCE}
CONFIG_BRANCH=${CONFIG_BRANCH:-$DEFAULT_CONFIG_BRANCH}
TARGET_HOST='' # Only an explicit command-line option selects the target.
TARGET_TIMEZONE=${TARGET_TIMEZONE:-$DEFAULT_TIMEZONE}
TARGET_LOCALE=${TARGET_LOCALE:-$DEFAULT_LOCALE}
MODE=apply
ASSUME_YES=0
INSTALL_BINPKGS=1
RAM_BUILDS=1
PACKAGE_OPTIONS=(--usepkg=n --getbinpkg=n)
BINARY_INSTALL_OPTIONS=()
SELECTED_PHASES=(disk-setup stage3-bootstrap portage-foundation system-update kernel-foundation first-boot-foundation handoff)
VERBOSE=0
INTERNAL_PORTAGE_CHROOT=0
INTERNAL_UPDATE_CHROOT=0
INTERNAL_KERNEL_CHROOT=0
TARGET_MICROCODE=${TARGET_MICROCODE:-auto}
TARGET_SOF_FIRMWARE=
QEMU_VARS=${QEMU_VARS:-}
QEMU_VARS_TEMPLATE=${QEMU_VARS_TEMPLATE:-/usr/share/edk2/x64/OVMF_VARS.4m.fd}
TARGET_HOSTNAME=${TARGET_HOSTNAME:-}
INTERNAL_FIRSTBOOT_OFFLINE=0
TARGET_CPU_FLAGS=${TARGET_CPU_FLAGS:-}

EFI_PARTITION=
CRYPT_PARTITION=
MOUNTED_ROOT=0
MOUNTED_HOME=0
MOUNTED_EFI=0
LUKS_OPENED=0

PHASE_ORDER=(disk-setup stage3-bootstrap portage-foundation system-update kernel-foundation first-boot-foundation handoff)

usage() {
  cat <<EOF
Usage: $PROGRAM --disk DEVICE --target-host NAME [options]

Install the selected Gentoo phases.  The current milestone prepares an
encrypted Btrfs disk, bootstraps the verified stage3, and establishes the
target's Portage configuration, then updates the base system and prepares
the distribution kernel for direct EFI boot, then configures first boot.

Required:
  --disk DEVICE              Whole block device to erase, for example /dev/nvme0n1
  --target-host NAME         Configuration target: generic, qemu, thinktop, or startop.

Options:
  --dry-run                  Print plans and perform no changes.
  --yes                      Automatically continue through ordinary phase and
                              destructive-action confirmations.  This never
                              supplies, skips, or infers secret input.
  --install-binpkgs          Prefer signed official binaries during installation (default),
                              respecting USE flags; compile unmatched packages.
                              Source builds remain the post-install default.
  --no-install-binpkgs       Build installation packages from source.
  --no-ram-builds            Build in /var/tmp instead of the default /dev/shm.
                              This never changes post-install build storage.
  --verbose                  Print technical notes and detailed phase output.
                              It does not affect execution or confirmations.
  --phase NAME               Run a named phase (currently: disk-setup,
                              stage3-bootstrap, portage-foundation, system-update,
                              kernel-foundation, first-boot-foundation, handoff). May be
                              repeated; phases run in installer order.
  --config-source SOURCE     Public Git URL or local repository path
                              (default: $CONFIG_SOURCE).
  --config-branch BRANCH     Configuration branch to install
                              (default: $CONFIG_BRANCH).
  --hostname NAME            Target hostname; defaults to named target-host, prompts
                              for generic/qemu (or preserves existing hostname).
  --cpu-flags FLAGS          Explicit CPU_FLAGS_X86 flags for another target;
                              otherwise detect the running CPU.
  --microcode KIND           auto, intel, amd, or none (default: $TARGET_MICROCODE).
                              auto detects the installation host CPU vendor.
  --qemu-vars FILE           Persistent raw OVMF variable store for target qemu;
                              required for its kernel-foundation phase.
  --qemu-vars-template FILE  Matching OVMF template used only for a new store
                              (default: $QEMU_VARS_TEMPLATE).
  --timezone ZONE            Target timezone (default: $TARGET_TIMEZONE).
  --locale LOCALE            Target UTF-8 locale (default: $TARGET_LOCALE).
  --luks-name NAME           Mapper name after opening LUKS (default: $LUKS_NAME).
  --btrfs-label LABEL        Btrfs volume label (default: $BTRFS_LABEL).
  --efi-size SIZE            EFI partition size, e.g. 1G (default: $EFI_SIZE).
  --mount-root PATH          Where prepared filesystems remain mounted
                              (default: $MOUNT_ROOT).
  -h, --help                 Show this help.

Environment overrides mirror these options: TARGET_DISK, LUKS_NAME,
BTRFS_LABEL, EFI_SIZE, MOUNT_ROOT, CONFIG_SOURCE,
CONFIG_BRANCH, TARGET_TIMEZONE, TARGET_LOCALE, TARGET_CPU_FLAGS,
TARGET_MICROCODE, TARGET_HOSTNAME, QEMU_VARS, and QEMU_VARS_TEMPLATE.
--target-host must be supplied explicitly; TARGET_HOST is not inherited.
SOF audio firmware is selected by the target's agentoo fragments.

Safety model:
  * Selected phases run by default; --dry-run is the non-destructive mode.
  * Mutating phases show their plan and ask before continuing.  --yes is the
    global opt-in to automatic continuation.
  * Disk setup refuses partitions, disks with mounted descendants, and disks
    that back the running root, boot, or EFI filesystems.
  * The LUKS passphrase is prompted only during real disk setup; it is never
    accepted in an argument, printed, or written to a file by this script.
EOF
}

log() {
  printf '\n==> %s\n' "$*"
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

run_privileged() {
  local answer
  if (( EUID == 0 )); then
    "$@"
    return $?
  fi
  require_command sudo
  if ! sudo -n -v 2>/dev/null; then
    # Wait without a timeout before starting sudo's timed password prompt.
    # Use the controlling terminal so pipelines, heredocs, and captured command
    # output retain their original input and output streams. --yes never skips
    # this readiness check for authentication.
    [[ -r /dev/tty && -w /dev/tty ]] \
      || { printf 'error: a terminal is required to renew sudo authorization.\n' >&2; return 1; }
    printf '\nHost administrator authorization is needed. Press Enter when ready to enter your sudo password: ' >/dev/tty
    IFS= read -r answer </dev/tty \
      || { printf 'error: could not read readiness for sudo authorization.\n' >&2; return 1; }
    sudo -p "Host administrator password for %p (authorizes this installer; does not set a Gentoo password): " -v </dev/tty >/dev/tty 2>&1 || return $?
  fi
  # Do not start a timed prompt if authorization was revoked after checking.
  sudo -n -- "$@"
}

resolve_target_partitions() {
  TARGET_DISK=$(readlink -f -- "$TARGET_DISK")
  case ${TARGET_DISK##*/} in
    *[0-9]) EFI_PARTITION=${TARGET_DISK}p1; CRYPT_PARTITION=${TARGET_DISK}p2 ;;
    *) EFI_PARTITION=${TARGET_DISK}1; CRYPT_PARTITION=${TARGET_DISK}2 ;;
  esac
}

require_chroot_mounts() {
  local source
  for source in proc sys dev run; do
    mountpoint -q "$MOUNT_ROOT/$source" || die "required chroot mount is missing: $source"
  done
}

# Run one target phase with a clean environment and invocation-owned helper.
run_chroot_phase() {
  local phase=$1 helper
  shift
  helper=/run/$PROGRAM.$phase.$$
  run_privileged install -m 700 "$0" "$MOUNT_ROOT$helper"
  run_privileged /bin/bash -c '
    set -euo pipefail
    target_root=$1 helper=$2
    shift 2
    cleanup_helper() {
      local status=$?
      trap - EXIT
      rm -f -- "$target_root$helper" || printf "Warning: temporary phase helper remains.\n" >&2
      exit "$status"
    }
    trap cleanup_helper EXIT
    chroot "$target_root" /usr/bin/env -i \
      HOME=/root PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
      TERM="${TERM:-dumb}" /bin/bash "$helper" "$@"
  ' "$PROGRAM-$phase" "$MOUNT_ROOT" "$helper" "$@"
}

install_emerge() {
  local build_dir=/dev/shm
  (( RAM_BUILDS )) || build_dir=/var/tmp
  PORTAGE_TMPDIR=$build_dir emerge "$@"
}

target_emerge() {
  local root=$1 build_dir=/dev/shm
  shift
  (( RAM_BUILDS )) || build_dir=/var/tmp
  chroot "$root" /usr/bin/env PORTAGE_TMPDIR=$build_dir /usr/bin/emerge "$@"
}

# Atomic local-data writes permit matching content, owned files, or stage3 comments.
write_target_file() (
  local path=$1 temporary content old
  content=$(cat)
  if [[ -e $path || -L $path ]]; then
    [[ -f $path && ! -L $path ]] || die "unsafe target file: $path"
    old=$(cat "$path")
    if [[ $old != "$content" ]] &&
       ! grep -Fxq '# Managed by gentoo-install first-boot-foundation.' "$path" &&
       grep -Evq '^[[:space:]]*(#.*)?$' "$path"; then
      die "existing target file requires manual review: $path"
    fi
  fi
  temporary=$(mktemp "${path}.XXXXXX")
  trap 'rm -f -- "$temporary"' EXIT
  printf '%s\n' "$content" >"$temporary"
  chmod 644 "$temporary"
  mv -f -- "$temporary" "$path"
)

# Command-line selection and configuration

is_selected() {
  local wanted=$1 phase
  for phase in "${SELECTED_PHASES[@]}"; do
    [[ $phase == "$wanted" ]] && return 0
  done
  return 1
}

valid_phase() {
  local wanted=$1 phase
  for phase in "${PHASE_ORDER[@]}"; do
    [[ $phase == "$wanted" ]] && return 0
  done
  return 1
}

set_phase_selection() {
  local phase=$1
  valid_phase "$phase" || die "unknown phase: $phase"
  if [[ ${PHASES_EXPLICIT:-0} == 0 ]]; then
    SELECTED_PHASES=()
    PHASES_EXPLICIT=1
  fi
  SELECTED_PHASES+=("$phase")
}

parse_args() {
  while (($#)); do
    case $1 in
      --disk|--phase|--luks-name|--btrfs-label|--efi-size|--mount-root|--config-source|--config-branch|--target-host|--timezone|--locale|--cpu-flags|--microcode|--qemu-vars|--qemu-vars-template|--hostname)
        (($# >= 2)) && [[ $2 != --* ]] \
          || die "$1 requires a value; use $PROGRAM --help for examples"
        ;;
    esac
    case $1 in
      --disk)
        (($# >= 2)) || die '--disk requires a device path'
        TARGET_DISK=$2
        shift
        ;;
      --disk=*) TARGET_DISK=${1#*=} ;;
      --dry-run) MODE=dry-run ;;
      --yes) ASSUME_YES=1 ;;
      --install-binpkgs) INSTALL_BINPKGS=1 ;;
      --no-install-binpkgs) INSTALL_BINPKGS=0 ;;
      --no-ram-builds) RAM_BUILDS=0 ;;
      --verbose) VERBOSE=1 ;;
      --phase)
        (($# >= 2)) || die '--phase requires a phase name'
        set_phase_selection "$2"
        shift
        ;;
      --phase=*) set_phase_selection "${1#*=}" ;;
      --luks-name)
        (($# >= 2)) || die '--luks-name requires a value'
        LUKS_NAME=$2
        shift
        ;;
      --luks-name=*) LUKS_NAME=${1#*=} ;;
      --btrfs-label)
        (($# >= 2)) || die '--btrfs-label requires a value'
        BTRFS_LABEL=$2
        shift
        ;;
      --btrfs-label=*) BTRFS_LABEL=${1#*=} ;;
      --efi-size)
        (($# >= 2)) || die '--efi-size requires a value'
        EFI_SIZE=$2
        shift
        ;;
      --efi-size=*) EFI_SIZE=${1#*=} ;;
      --mount-root)
        (($# >= 2)) || die '--mount-root requires a path'
        MOUNT_ROOT=$2
        shift
        ;;
      --mount-root=*) MOUNT_ROOT=${1#*=} ;;
      --config-source)
        (($# >= 2)) || die '--config-source requires a URL or path'
        CONFIG_SOURCE=$2
        shift
        ;;
      --config-source=*) CONFIG_SOURCE=${1#*=} ;;
      --config-branch)
        (($# >= 2)) || die '--config-branch requires a branch name'
        CONFIG_BRANCH=$2
        shift
        ;;
      --config-branch=*) CONFIG_BRANCH=${1#*=} ;;
      --target-host)
        (($# >= 2)) || die '--target-host requires a name'
        TARGET_HOST=$2
        shift
        ;;
      --target-host=*) TARGET_HOST=${1#*=} ;;
      --timezone)
        (($# >= 2)) || die '--timezone requires a zone name'
        TARGET_TIMEZONE=$2
        shift
        ;;
      --timezone=*) TARGET_TIMEZONE=${1#*=} ;;
      --locale)
        (($# >= 2)) || die '--locale requires a locale name'
        TARGET_LOCALE=$2
        shift
        ;;
      --locale=*) TARGET_LOCALE=${1#*=} ;;
      --cpu-flags)
        (($# >= 2)) || die '--cpu-flags requires a flag list'
        TARGET_CPU_FLAGS=$2
        shift
        ;;
      --cpu-flags=*) TARGET_CPU_FLAGS=${1#*=} ;;
      --microcode)
        (($# >= 2)) || die '--microcode requires auto, intel, amd, or none'
        TARGET_MICROCODE=$2
        shift
        ;;
      --microcode=*) TARGET_MICROCODE=${1#*=} ;;
      --qemu-vars)
        (($# >= 2)) || die '--qemu-vars requires a file path'
        QEMU_VARS=$2
        shift
        ;;
      --qemu-vars=*) QEMU_VARS=${1#*=} ;;
      --qemu-vars-template)
        QEMU_TEMPLATE_EXPLICIT=1
        (($# >= 2)) || die '--qemu-vars-template requires a file path'
        QEMU_VARS_TEMPLATE=$2
        shift
        ;;
      --qemu-vars-template=*) QEMU_TEMPLATE_EXPLICIT=1; QEMU_VARS_TEMPLATE=${1#*=} ;;
      --hostname)
        (($# >= 2)) || die '--hostname requires a value'
        TARGET_HOSTNAME=$2
        shift
        ;;
      --hostname=*) TARGET_HOSTNAME=${1#*=} ;;
      --internal-firstboot-offline) INTERNAL_FIRSTBOOT_OFFLINE=1 ;;
      --internal-kernel-chroot) INTERNAL_KERNEL_CHROOT=1 ;;
      --internal-update-chroot) INTERNAL_UPDATE_CHROOT=1 ;;
      --internal-portage-chroot) INTERNAL_PORTAGE_CHROOT=1 ;;
      -h|--help)
        usage
        exit 0
        ;;
      *) die "unknown option: $1" ;;
    esac
    shift
  done
}

# Runtime interaction

# Validate user inputs before any phase can modify the disk. Target-side state
# and execution prerequisites remain checked where the phases use them.
validate_arguments() {
  local -a errors=()
  local option value normalized
  [[ -n $TARGET_HOST ]] || errors+=("--target-host NAME is required; choose generic, qemu, thinktop, or startop.")
  [[ -z $TARGET_HOST ]] || valid_target_host "$TARGET_HOST" || errors+=("--target-host '$TARGET_HOST' is unknown; choose generic, qemu, thinktop, or startop. Use --hostname for a custom machine name.")
  case $TARGET_MICROCODE in
    auto|intel|amd|none) ;;
    *) errors+=("--microcode must be auto, intel, amd, or none.") ;;
  esac
  [[ $EFI_SIZE =~ ^[1-9][0-9]*[MmGg]$ ]] || errors+=("--efi-size must be a positive size such as 1G or 512M.")
  normalized=$(readlink -m -- "$MOUNT_ROOT")
  [[ $MOUNT_ROOT == /* && $normalized != / && $MOUNT_ROOT != *$'\n'* ]] \
    || errors+=("--mount-root must be an absolute directory other than /, such as /mnt/gentoo.")
  for option in LUKS_NAME BTRFS_LABEL; do
    value=${!option}
    [[ $value =~ ^[A-Za-z0-9._@+-]+$ && $value != . && $value != .. ]] \
      || errors+=("$option must be a nonempty name using letters, numbers, dots, underscores, @, +, or hyphens; '.' and '..' are not allowed.")
  done
  [[ $LUKS_NAME =~ ^[A-Za-z0-9_-]+$ ]] || errors+=("LUKS_NAME must use letters, numbers, underscores, or hyphens.")
  [[ -z $TARGET_HOSTNAME || ( ${#TARGET_HOSTNAME} -le 63 && $TARGET_HOSTNAME =~ ^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$ ) ]] \
    || errors+=("--hostname must be one DNS label of at most 63 characters, with letters, numbers, and internal hyphens.")
  [[ $TARGET_LOCALE =~ ^[A-Za-z][A-Za-z_]*\.(UTF-8|utf8)$ ]] \
    || errors+=("--locale must be a UTF-8 locale such as en_US.UTF-8.")
  [[ $TARGET_TIMEZONE =~ ^[A-Za-z0-9_+-]+(/[A-Za-z0-9_+-]+)*$ && -f /usr/share/zoneinfo/$TARGET_TIMEZONE ]] \
    || errors+=("--timezone must name an installed timezone, such as America/New_York; see /usr/share/zoneinfo.")
  [[ -z $TARGET_CPU_FLAGS || $TARGET_CPU_FLAGS =~ ^[a-z0-9_]+([[:blank:]][a-z0-9_]+)*$ ]] \
    || errors+=("--cpu-flags must be a space-separated list of lowercase CPU flag names.")
  [[ -n $CONFIG_SOURCE && $CONFIG_SOURCE != -* && $CONFIG_SOURCE != *$'\n'* && $CONFIG_SOURCE != *$'\r'* ]] \
    || errors+=("--config-source must be a nonempty Git URL or local repository path.")
  if command -v git >/dev/null 2>&1; then
    git check-ref-format --branch "$CONFIG_BRANCH" >/dev/null 2>&1 \
      || errors+=("--config-branch must be a valid Git branch name, such as main.")
  else
    errors+=("Install git so --config-branch can be validated before installation.")
  fi
  if [[ -z $TARGET_DISK ]]; then
    errors+=("--disk is required; use lsblk to identify the separate whole target disk.")
  elif [[ ! -b $TARGET_DISK ]]; then
    errors+=("--disk '$TARGET_DISK' is not an available block device; check lsblk.")
  elif [[ $(lsblk -dn -o TYPE "$TARGET_DISK") != disk ]]; then
    errors+=("--disk must identify a whole disk, not a partition or encrypted mapping; check lsblk.")
  fi
  if [[ $TARGET_HOST != qemu && ( -n $QEMU_VARS || ${QEMU_TEMPLATE_EXPLICIT:-0} == 1 ) ]]; then
    errors+=("--qemu-vars and --qemu-vars-template apply only to --target-host qemu; omit them for a physical target.")
  fi
  if [[ $TARGET_HOST == qemu ]]; then
    if is_selected kernel-foundation && [[ -z $QEMU_VARS ]]; then
      errors+=("--target-host qemu needs --qemu-vars FILE for kernel-foundation. Choose a new path in your VM directory, such as /path/to/VM/OVMF_VARS.4m.fd; the installer creates it from the OVMF template. See usr/local/share/agentoo/installer/QEMU-NBD-INSTALL.md.")
    fi
    if [[ -n $QEMU_VARS ]]; then
      [[ $QEMU_VARS != *$'\n'* && $QEMU_VARS != *$'\r'* && ! -L $QEMU_VARS && ( ! -e $QEMU_VARS || -f $QEMU_VARS ) ]] \
        || errors+=("--qemu-vars must be a regular file path, not a symlink or directory.")
      [[ -d $(dirname -- "$QEMU_VARS") ]] || errors+=("Create the parent directory for --qemu-vars before running the installer.")
      if is_selected kernel-foundation && [[ ! -e $QEMU_VARS ]]; then
        [[ -f $QEMU_VARS_TEMPLATE && -r $QEMU_VARS_TEMPLATE ]] \
          || errors+=("--qemu-vars-template is unavailable; install OVMF or supply a readable template matching your VM's OVMF CODE file.")
      fi
    fi
  fi
  if ((${#errors[@]})); then
    printf 'Please correct these arguments before continuing:\n' >&2
    printf '  * %s\n' "${errors[@]}" >&2
    exit 1
  fi
}

confirm_phase() {
  local phase=$1 answer

  (( ASSUME_YES )) && return 0
  [[ -r /dev/tty && -w /dev/tty ]] || die "a terminal is required to confirm $phase; use --yes only when appropriate"
  printf '\nContinue with %s? [y/N] ' "$phase" >/dev/tty
  IFS= read -r answer </dev/tty || die "could not read confirmation for $phase"
  case $answer in
    y|Y|yes|YES|Yes) return 0 ;;
    *)
      printf 'Stopped before %s.\n' "$phase"
      exit 0
      ;;
  esac
}

# Disk setup verification

verification_error() {
  printf 'error: disk setup verification failed: %s\n' "$*" >&2
  return 1
}

mount_has_option() {
  local mountpoint=$1 expected_option=$2 options option

  options=$(run_privileged findmnt --noheadings --output OPTIONS --target "$mountpoint") || return 1
  IFS=, read -r -a options <<<"$options"
  for option in "${options[@]}"; do
    [[ $option == "$expected_option" ]] && return 0
  done
  return 1
}

mount_uses_subvolume() {
  local mountpoint=$1 expected_subvolume=$2

  mount_has_option "$mountpoint" "subvol=$expected_subvolume" \
    || mount_has_option "$mountpoint" "subvol=/$expected_subvolume"
}

verify_disk_setup() {
  # This is a production gate: disk setup calls it before allowing later
  # installer phases to use the prepared filesystem.
  local efi_type crypt_type mapper_device luks_version filesystem_type label
  local mount_source mount_fstype target_disk_name subvolume partition_table_type

  # 1. Check the inspection tools first so a missing tool is reported as a
  # verification failure, rather than being mistaken for a malformed layout.
  for command in lsblk readlink awk cryptsetup blkid btrfs findmnt mountpoint; do
    command -v "$command" >/dev/null 2>&1 \
      || verification_error "required command is unavailable: $command" || return 1
  done

  # 2. Confirm that the chosen disk has the intended GPT and that both
  # partition paths resolve to direct children of that exact disk.
  # Probe the disk itself: lsblk can expose stale udev metadata immediately
  # after repartitioning, even after udevadm settle has returned.
  partition_table_type=$(run_privileged blkid --probe --output value --match-tag PTTYPE "$TARGET_DISK") \
    || verification_error "could not probe target partition table; check authorization and device access: $TARGET_DISK" || return 1
  [[ $partition_table_type == gpt ]] \
    || verification_error "target does not have a GPT partition table: $TARGET_DISK" || return 1
  target_disk_name=${TARGET_DISK##*/}
  [[ $(run_privileged lsblk --nodeps --raw --noheadings --output PKNAME "$EFI_PARTITION") == "$target_disk_name" ]] \
    || verification_error "EFI partition is not on the target disk: $EFI_PARTITION" || return 1
  [[ $(run_privileged lsblk --nodeps --raw --noheadings --output PKNAME "$CRYPT_PARTITION") == "$target_disk_name" ]] \
    || verification_error "LUKS partition is not on the target disk: $CRYPT_PARTITION" || return 1

  # 3. Confirm the EFI and encrypted partition types, plus the FAT filesystem
  # firmware needs on the unencrypted EFI System Partition.
  efi_type=$(run_privileged lsblk --nodeps --raw --noheadings --output PARTTYPE "$EFI_PARTITION" | awk '{ print tolower($1) }')
  crypt_type=$(run_privileged lsblk --nodeps --raw --noheadings --output PARTTYPE "$CRYPT_PARTITION" | awk '{ print tolower($1) }')
  [[ $efi_type == c12a7328-f81f-11d2-ba4b-00a0c93ec93b ]] \
    || verification_error "EFI partition has the wrong GPT type: $EFI_PARTITION" || return 1
  [[ $crypt_type == ca7d7ccb-63ed-4c53-861c-1742536059cc ]] \
    || verification_error "LUKS partition has the wrong GPT type: $CRYPT_PARTITION" || return 1
  [[ $(run_privileged blkid --output value --match-tag TYPE "$EFI_PARTITION") == vfat ]] \
    || verification_error "EFI partition is not FAT: $EFI_PARTITION" || return 1

  # 4. Confirm the partition is LUKS2 and the open mapper points back to it.
  run_privileged cryptsetup isLuks "$CRYPT_PARTITION" >/dev/null 2>&1 \
    || verification_error "partition is not a LUKS container: $CRYPT_PARTITION" || return 1
  luks_version=$(run_privileged cryptsetup luksDump "$CRYPT_PARTITION" 2>/dev/null | awk -F: '$1 ~ /^[[:space:]]*Version$/ { gsub(/[[:space:]]/, "", $2); print $2; exit }')
  [[ $luks_version == 2 ]] \
    || verification_error "LUKS container is not LUKS2: $CRYPT_PARTITION" || return 1
  [[ -b /dev/mapper/$LUKS_NAME ]] \
    || verification_error "LUKS mapper is missing: /dev/mapper/$LUKS_NAME" || return 1
  mapper_device=$(run_privileged cryptsetup status "$LUKS_NAME" 2>/dev/null | awk 'tolower($1) == "device:" { print $2; exit }')
  [[ -n $mapper_device && $(readlink -f -- "$mapper_device") == $(readlink -f -- "$CRYPT_PARTITION") ]] \
    || verification_error "LUKS mapper does not use the intended partition: /dev/mapper/$LUKS_NAME" || return 1

  # 5. Confirm the mapper contains the labeled Btrfs filesystem and the two
  # named subvolumes used by the following installation phases.
  filesystem_type=$(run_privileged blkid --output value --match-tag TYPE "/dev/mapper/$LUKS_NAME" || true)
  label=$(run_privileged blkid --output value --match-tag LABEL "/dev/mapper/$LUKS_NAME" || true)
  [[ $filesystem_type == btrfs ]] \
    || verification_error "mapper does not contain Btrfs: /dev/mapper/$LUKS_NAME" || return 1
  [[ $label == "$BTRFS_LABEL" ]] \
    || verification_error "Btrfs label is not $BTRFS_LABEL" || return 1
  for subvolume in "$ROOT_SUBVOL" "$HOME_SUBVOL"; do
    run_privileged btrfs subvolume list "$MOUNT_ROOT" | awk -v expected="$subvolume" '
      / path / { sub(/^.* path /, ""); if ($0 == expected) found = 1 }
      END { exit !found }
    ' || verification_error "Btrfs subvolume is missing: $subvolume" || return 1
  done

  # 6. Confirm all three mounts exist before checking their sources, types,
  # subvolumes, and mount options individually.
  for mountpoint in "$MOUNT_ROOT" "$MOUNT_ROOT/home" "$MOUNT_ROOT/boot"; do
    run_privileged mountpoint -q "$mountpoint" \
      || verification_error "expected mount is missing: $mountpoint" || return 1
  done
  for mountpoint in "$MOUNT_ROOT" "$MOUNT_ROOT/home"; do
    mount_source=$(run_privileged findmnt --noheadings --output SOURCE --target "$mountpoint")
    mount_fstype=$(run_privileged findmnt --noheadings --output FSTYPE --target "$mountpoint")
    # Btrfs reports a mounted subvolume as /device[/subvolume].  The suffix is
    # mount metadata, not part of the backing mapper path.
    mount_source=${mount_source%%\[*}
    [[ $(readlink -f -- "$mount_source") == $(readlink -f -- "/dev/mapper/$LUKS_NAME") && $mount_fstype == btrfs ]] \
      || verification_error "Btrfs mount has the wrong source or type: $mountpoint" || return 1
  done
  mount_uses_subvolume "$MOUNT_ROOT" "$ROOT_SUBVOL" \
    || verification_error "root mount does not use subvolume $ROOT_SUBVOL: $MOUNT_ROOT" || return 1
  mount_uses_subvolume "$MOUNT_ROOT/home" "$HOME_SUBVOL" \
    || verification_error "home mount does not use subvolume $HOME_SUBVOL: $MOUNT_ROOT/home" || return 1
  for mountpoint in "$MOUNT_ROOT" "$MOUNT_ROOT/home"; do
    mount_has_option "$mountpoint" noatime \
      || verification_error "Btrfs mount is missing noatime: $mountpoint" || return 1
    mount_has_option "$mountpoint" compress=zstd:1 \
      || verification_error "Btrfs mount is missing compress=zstd:1: $mountpoint" || return 1
  done
  # 7. Finally, ensure the firmware-visible mount still comes from the EFI
  # partition, rather than from the encrypted Btrfs filesystem.
  mount_source=$(run_privileged findmnt --noheadings --output SOURCE --target "$MOUNT_ROOT/boot")
  mount_fstype=$(run_privileged findmnt --noheadings --output FSTYPE --target "$MOUNT_ROOT/boot")
  [[ $(readlink -f -- "$mount_source") == $(readlink -f -- "$EFI_PARTITION") && $mount_fstype == vfat ]] \
    || verification_error "EFI mount has the wrong source or type: $MOUNT_ROOT/boot" || return 1
}

# Disk setup presentation, input, and recovery

print_plan() {
  cat <<EOF

Installation disk plan
  $TARGET_DISK
  ├─ $EFI_PARTITION: EFI System Partition, FAT32, $EFI_SIZE → $MOUNT_ROOT/boot
  └─ $CRYPT_PARTITION: LUKS2 → /dev/mapper/$LUKS_NAME
     └─ Btrfs ($BTRFS_LABEL)
        ├─ $ROOT_SUBVOL → $MOUNT_ROOT
        └─ $HOME_SUBVOL → $MOUNT_ROOT/home

This will irreversibly erase every existing partition and filesystem on
$TARGET_DISK.  Dry-run mode changes nothing.
EOF
}

confirm_target() {
  # Read /dev/tty rather than stdin so this still works when the installer
  # arrived through `curl ... | bash`; stdin is the script body in that case.
  [[ $ASSUME_YES == 1 ]] && return 0
  local answer
  printf '\nType the exact target disk to erase (%s): ' "$TARGET_DISK" >/dev/tty
  IFS= read -r answer </dev/tty || die 'could not read destructive-action confirmation from the terminal'
  [[ $answer == "$TARGET_DISK" ]] || die 'target confirmation did not match; no changes made'
}

prompt_luks_passphrase() {
  # Keep the passphrase out of argv, exports, shell history, and files.  It is
  # piped directly to cryptsetup below and then removed from shell state.
  local first second
  [[ -r /dev/tty && -w /dev/tty ]] || die 'cannot securely prompt for a LUKS passphrase without a terminal'
  printf 'New target disk LUKS passphrase: ' >/dev/tty
  IFS= read -r -s first </dev/tty || die 'could not read LUKS passphrase'
  printf '\nConfirm target LUKS passphrase: ' >/dev/tty
  IFS= read -r -s second </dev/tty || die 'could not read LUKS passphrase confirmation'
  printf '\n' >/dev/tty
  [[ -n $first ]] || die 'empty LUKS passphrases are not accepted'
  [[ $first == "$second" ]] || die 'LUKS passphrases did not match'
  LUKS_PASSPHRASE=$first
  unset first second
}

cleanup_after_failure() {
  # Reverse only mounts and the mapper created by this run.  A partition table
  # or LUKS header cannot be safely "undone" after disk setup is confirmed.
  local exit_code=${1:-$?}
  (( exit_code == 0 )) && return
  set +e
  if (( MOUNTED_EFI )); then run_privileged umount "$MOUNT_ROOT/boot"; fi
  if (( MOUNTED_HOME )); then run_privileged umount "$MOUNT_ROOT/home"; fi
  if (( MOUNTED_ROOT )); then run_privileged umount "$MOUNT_ROOT"; fi
  if (( LUKS_OPENED )); then run_privileged cryptsetup close "$LUKS_NAME"; fi
  unset LUKS_PASSPHRASE 2>/dev/null || true
  printf 'error: disk setup did not complete; any mounts created by this run were cleaned up.\n' >&2
  exit "$exit_code"
}

# Disk setup phase

disk_setup() {
  local command value mountpoint source backing_disk

  if (( VERBOSE )); then
    cat <<'EOF'
Disk setup: target protection, layout, and mount mechanics
==========================================================

The installer accepts one whole block device and derives its partitions.  For
example, /dev/nvme0n1 becomes /dev/nvme0n1p1 and /dev/nvme0n1p2.

Optional manual safety checks
-----------------------------

The target must have lsblk type `disk`; partitions, /dev/mapper entries, and
ordinary paths are rejected.  The script then protects disks backing /, /boot,
/efi, or /boot/efi, as well as mounted or active-swap descendants.

lsblk --paths --output NAME,SIZE,TYPE,FSTYPE,LABEL,MOUNTPOINTS /dev/nvme0n1
findmnt --target /
findmnt --target /boot
findmnt --target /efi
findmnt --target /boot/efi
swapon --show
test ! -e /dev/mapper/cryptroot

Erase and partition the disk
----------------------------

The target receives a GPT containing two partitions: a FAT32 EFI System
Partition (default 1 GiB, GPT type EF00) and a LUKS2 container using the
remainder (type 8309).  The ESP stays outside LUKS because UEFI firmware must
read the later boot image before Linux can decrypt the root filesystem.

wipefs --all --force /dev/nvme0n1
sfdisk --wipe always --wipe-partitions always /dev/nvme0n1 <<'SFDISK_LAYOUT'
label: gpt
size=1G, type=C12A7328-F81F-11D2-BA4B-00A0C93EC93B, name="EFI"
type=CA7D7CCB-63ED-4C53-861C-1742536059CC, name="cryptroot"
SFDISK_LAYOUT

partprobe /dev/nvme0n1
udevadm settle

Create the EFI, LUKS, and Btrfs layers
---------------------------------------

The LUKS partition opens as /dev/mapper/<luks-name>.  Btrfs is formatted there,
not on the raw partition, so the filesystem, subvolume metadata, and later
Gentoo files are encrypted.  `--data single` is appropriate for one device;
`--metadata dup` retains two metadata copies on that device and is standard
practice as recommended by upstream.

mkfs.fat -F 32 -n EFI /dev/nvme0n1p1
cryptsetup luksFormat --type luks2 /dev/nvme0n1p2
cryptsetup open /dev/nvme0n1p2 cryptroot
mkfs.btrfs --force --label GENTOO --data single --metadata dup /dev/mapper/cryptroot

Create the root and home subvolumes
-----------------------------------

The fresh Btrfs top level, normally subvolume ID 5, is mounted temporarily only
to create @ and @home.  The stage3 must later be unpacked after @ is remounted
as <mount-root>.  @home is mounted separately at <mount-root>/home so system
snapshots can exclude home by default.  Named `subvol=@` paths are simpler to
inspect in fstab and recovery commands than numeric IDs.

mkdir -p /mnt/gentoo
mount -o subvolid=5 /dev/mapper/cryptroot /mnt/gentoo
btrfs subvolume create /mnt/gentoo/@
btrfs subvolume create /mnt/gentoo/@home
umount /mnt/gentoo

Mount the layout for the next phase
-----------------------------------

`noatime,compress=zstd:1` is a conservative initial root/home mount policy
to start.  Do not add `ssd` or `space_cache=v2`: modern Btrfs handles those
automatically.  Do not globally enable autodefrag, nodatacow, nodatasum, or
compress-force without a workload-specific reason; they can harm snapshot or
integrity behavior.

The ESP mounts at <mount-root>/boot, where its EFI directory becomes /boot/EFI
inside the installed system.  Later UKIs will live there for direct firmware
booting.

mount -o subvol=@,noatime,compress=zstd:1 /dev/mapper/cryptroot /mnt/gentoo
mkdir -p /mnt/gentoo/home /mnt/gentoo/boot
mount -o subvol=@home,noatime,compress=zstd:1 /dev/mapper/cryptroot /mnt/gentoo/home
mount /dev/nvme0n1p1 /mnt/gentoo/boot
mkdir -p /mnt/gentoo/boot/EFI

Optional manual verification
----------------------------

The printed lsblk table and layout plan are the checks to read before applying
the plan.

cryptsetup isLuks /dev/nvme0n1p2
btrfs subvolume list /mnt/gentoo
findmnt -R /mnt/gentoo
EOF
  fi

  log 'Phase: disk-setup'

  # Commands used by every disk-setup branch.  The longer apply-only tool list
  # stays below its condition so dry-run remains usable in a minimal live ISO.
  for command in lsblk findmnt readlink awk sort; do
    require_command "$command"
  done

  [[ -n $TARGET_DISK ]] || die 'pass a target with --disk DEVICE'
  TARGET_DISK=$(readlink -f -- "$TARGET_DISK")
  [[ -b $TARGET_DISK ]] || die "target is not a block device: $TARGET_DISK"
  [[ $(lsblk -dn -o TYPE "$TARGET_DISK") == disk ]] || die "target must be a whole disk, not a partition or mapper: $TARGET_DISK"
  local target_bytes
  target_bytes=$(lsblk --bytes --nodeps --noheadings --output SIZE "$TARGET_DISK") \
    || die "could not read target capacity: $TARGET_DISK"
  [[ $target_bytes =~ ^[[:space:]]*[0-9]+[[:space:]]*$ && $target_bytes -gt 0 ]] \
    || die "target has zero capacity: $TARGET_DISK; attach its backing image before running the installer"
  if [[ ${TARGET_DISK##*/} =~ ^nbd[0-9]+$ ]]; then
    [[ -s /sys/block/${TARGET_DISK##*/}/pid ]] \
      || die "NBD target is disconnected: $TARGET_DISK; attach its backing image before running the installer"
  fi
  [[ $EFI_SIZE =~ ^[1-9][0-9]*[MmGg]$ ]] || die "EFI size must look like 1G or 512M: $EFI_SIZE"
  [[ $MOUNT_ROOT == /* && $MOUNT_ROOT != / ]] || die "mount root must be a non-root absolute path: $MOUNT_ROOT"
  for value in "$LUKS_NAME" "$BTRFS_LABEL"; do
    [[ $value =~ ^[A-Za-z0-9._@+-]+$ ]] || die "unsupported characters in layout name: $value"
  done

  # NVMe, eMMC, and loop device names already end in a digit, so their
  # partitions are /dev/nvme0n1p1 rather than /dev/nvme0n11.  SATA-style names
  # remain /dev/sda1.  Both names come from the one accepted target disk.
  resolve_target_partitions

  # findmnt can identify a plain partition, a /dev/mapper LUKS device, or an
  # LVM logical volume.  lsblk --inverse walks that source back to physical
  # disks, which catches a live root hidden below a device-mapper layer.
  local backing_disks mountpoints swap_sources
  for mountpoint in / /boot /efi /boot/efi; do
    if ! source=$(findmnt --noheadings --output SOURCE --target "$mountpoint" 2>/dev/null); then
      [[ $mountpoint != / ]] || die 'could not inspect the running root filesystem'
      continue
    fi
    # The Btrfs [/subvolume] suffix is mount metadata, not a device name.
    source=${source%%\[*}
    [[ -b $source ]] || continue
    backing_disks=$(lsblk --inverse --noheadings --paths --output PATH,TYPE "$source" \
      | awk '$2 == "disk" { print $1 }' | sort -u) \
      || die "could not inspect the disks backing $mountpoint: $source"
    while IFS= read -r backing_disk; do
      [[ $backing_disk != "$TARGET_DISK" ]] || die "refusing target that backs the running root, boot, or EFI filesystem: $TARGET_DISK"
    done <<< "$backing_disks"
  done

  # A parent disk usually has no mountpoint even when a child partition does.
  # Swap is not mounted at all, so it needs its own reverse-dependency check.
  mountpoints=$(lsblk --raw --noheadings --output MOUNTPOINTS "$TARGET_DISK") \
    || die "could not inspect target mounts: $TARGET_DISK"
  if [[ -n ${mountpoints//[[:space:]]/} ]]; then
    die "refusing target with mounted filesystems: $TARGET_DISK"
  fi
  if command -v swapon >/dev/null 2>&1; then
    swap_sources=$(swapon --show --noheadings --raw --output NAME) \
      || die 'could not inspect active swap'
    while IFS= read -r source; do
      [[ -n $source ]] || continue
      [[ $source != "$TARGET_DISK" ]] || die "refusing target that backs active swap: $TARGET_DISK"
      [[ -b $source ]] || continue
      backing_disks=$(lsblk --inverse --noheadings --paths --output PATH,TYPE "$source" \
        | awk '$2 == "disk" { print $1 }' | sort -u) \
        || die "could not inspect disks backing active swap: $source"
      while IFS= read -r backing_disk; do
        [[ $backing_disk != "$TARGET_DISK" ]] || die "refusing target that backs active swap: $TARGET_DISK"
      done <<< "$backing_disks"
    done <<< "$swap_sources"
  fi

  [[ ! -e /dev/mapper/$LUKS_NAME ]] || die "LUKS mapper already exists: /dev/mapper/$LUKS_NAME"
  if [[ $MODE == apply ]]; then
    for command in sfdisk wipefs partprobe udevadm mkfs.fat cryptsetup mkfs.btrfs btrfs mount umount mountpoint blkid; do
      require_command "$command"
    done
    (( EUID == 0 )) || require_command sudo
    ! mountpoint -q "$MOUNT_ROOT" || die "mount root is already mounted: $MOUNT_ROOT"
  fi

  log 'Disk inventory'
  lsblk --paths --output NAME,SIZE,TYPE,FSTYPE,LABEL,MOUNTPOINTS "$TARGET_DISK"

  print_plan
  if [[ $MODE == dry-run ]]; then
    printf '\nDry run: no changes made. Re-run without --dry-run only after reviewing this plan.\n'
    return 0
  fi

  confirm_phase 'disk setup'
  confirm_target
  if (( EUID != 0 )); then
    cat <<EOF

Disk setup will now use sudo to:
  * erase and repartition $TARGET_DISK;
  * create and open the LUKS2 container as /dev/mapper/$LUKS_NAME;
  * create the Btrfs filesystem and subvolumes; and
  * mount the prepared root, home, and EFI filesystems below $MOUNT_ROOT.
EOF
  fi
  prompt_luks_passphrase
  trap cleanup_after_failure ERR

  # Clear visible old signatures, then pass an explicit GPT layout to sfdisk.
  # sfdisk also wipes signatures that fall within the new partitions.  Ask the
  # kernel to reread the new table before formatting its partition devices.
  log "Erasing partition and filesystem signatures on $TARGET_DISK"
  run_privileged wipefs --all --force "$TARGET_DISK"
  run_privileged sfdisk --wipe always --wipe-partitions always "$TARGET_DISK" <<EOF
label: gpt
size=$EFI_SIZE, type=C12A7328-F81F-11D2-BA4B-00A0C93EC93B, name="EFI"
type=CA7D7CCB-63ED-4C53-861C-1742536059CC, name="cryptroot"
EOF
  run_privileged partprobe "$TARGET_DISK"
  run_privileged udevadm settle

  [[ -b $EFI_PARTITION && -b $CRYPT_PARTITION ]] || die 'partition devices did not appear after partitioning'
  # The ESP is FAT32 because firmware consumes it before Linux is running.
  # Its label is informational and does not participate in root mounting.
  run_privileged mkfs.fat -F 32 -n EFI "$EFI_PARTITION"

  log "Creating and opening LUKS2 container as $LUKS_NAME"
  printf '%s' "$LUKS_PASSPHRASE" | run_privileged cryptsetup luksFormat --type luks2 --batch-mode --key-file=- "$CRYPT_PARTITION"
  printf '%s' "$LUKS_PASSPHRASE" | run_privileged cryptsetup open --key-file=- "$CRYPT_PARTITION" "$LUKS_NAME"
  unset LUKS_PASSPHRASE
  LUKS_OPENED=1

  # Mount Btrfs top-level ID 5 only long enough to create the intended install
  # subvolumes.  Never extract the stage3 while this staging mount is active.
  run_privileged mkfs.btrfs --force --label "$BTRFS_LABEL" --data single --metadata dup "/dev/mapper/$LUKS_NAME"
  run_privileged mkdir -p "$MOUNT_ROOT"
  run_privileged mount -o subvolid=5 "/dev/mapper/$LUKS_NAME" "$MOUNT_ROOT"
  MOUNTED_ROOT=1
  run_privileged btrfs subvolume create "$MOUNT_ROOT/$ROOT_SUBVOL"
  run_privileged btrfs subvolume create "$MOUNT_ROOT/$HOME_SUBVOL"
  run_privileged umount "$MOUNT_ROOT"
  MOUNTED_ROOT=0

  # These are the fixed root/home options later expected in fstab.  Named subvolumes,
  # rather than numeric IDs, keep recovery commands and fstab auditable.
  run_privileged mount -o "subvol=$ROOT_SUBVOL,noatime,compress=zstd:1" "/dev/mapper/$LUKS_NAME" "$MOUNT_ROOT"
  MOUNTED_ROOT=1
  run_privileged mkdir -p "$MOUNT_ROOT/home" "$MOUNT_ROOT/boot"
  run_privileged mount -o "subvol=$HOME_SUBVOL,noatime,compress=zstd:1" "/dev/mapper/$LUKS_NAME" "$MOUNT_ROOT/home"
  MOUNTED_HOME=1
  # Match the boot-time FAT mask: permissions are mount-wide on EFI, including
  # the root-only recovery tool checked out there by config-foundation.
  run_privileged mount -o fmask=0133,dmask=0022 "$EFI_PARTITION" "$MOUNT_ROOT/boot"
  MOUNTED_EFI=1
  run_privileged mkdir -p "$MOUNT_ROOT/boot/EFI"

  if ! verify_disk_setup; then
    printf 'error: disk setup verification failed; stopping before later phases.\n' >&2
    cleanup_after_failure 1
  fi
  trap - ERR

  log 'Disk setup complete'
  run_privileged findmnt -R "$MOUNT_ROOT"
  cat <<EOF

The encrypted filesystem remains open at /dev/mapper/$LUKS_NAME and mounted at
$MOUNT_ROOT for the next installer phase.  The passphrase has been discarded
from this script's shell state.
EOF
}

# Stage3 bootstrap support

download_file() {
  local url=$1 destination=$2

  if command -v curl >/dev/null 2>&1; then
    run_privileged curl --fail --location --proto '=https' --tlsv1.2 --output "$destination" "$url"
  else
    run_privileged wget --https-only --secure-protocol=TLSv1_2 --output-document="$destination" "$url"
  fi
}

verify_pinned_release_signature() {
  local signed_file=$1 verified_file=$2 status_output

  # GnuPG reports the signing subkey and its primary key through VALIDSIG.
  # A good signature alone is insufficient because the downloaded key bundle
  # contains more than one public key; require Gentoo's pinned primary key.
  # --decrypt handles a clear-signed file: it verifies its signature and
  # writes only its authenticated plaintext to verified_file.  --verify alone
  # checks the signature but deliberately does not extract that plaintext.
  status_output=$(run_privileged gpg --batch --homedir "$STAGE_GPG_HOME" \
    --status-fd=1 --output "$verified_file" --decrypt "$signed_file")
  printf '%s\n' "$status_output" | awk -v expected="$GENTOO_AUTOMATED_RELEASE_FINGERPRINT" '
    $1 == "[GNUPG:]" && $2 == "VALIDSIG" && toupper($12) == expected { found = 1 }
    END { exit !found }
  ' || die "signature is not made by Gentoo's pinned automated-release key: ${signed_file##*/}"
}

cleanup_stage3_bootstrap_failure() {
  local exit_code=${1:-$?}

  (( exit_code == 0 )) && return
  trap - ERR EXIT
  set +e
  # These locations are made by mktemp in this invocation.  Leave the mounted
  # install layout intact; a failed download or verification must not undo it.
  [[ -n ${STAGE_WORKDIR:-} ]] && run_privileged rm -rf -- "$STAGE_WORKDIR"
  printf 'error: stage3 bootstrap failed; temporary downloads removed, target preserved for retry.\n' >&2
  exit "$exit_code"
}

confirm_expected_bootstrap_target_state() {
  local entry entries
  local -a unexpected=()

  # Inspect as root so restrictive target directory permissions do not hide entries.
  # Capture find output with its exit status; process substitutions hide failures
  # and could misreport an unreadable target as empty or missing.
  entries=$(run_privileged find "$MOUNT_ROOT" -mindepth 1 -maxdepth 1 -print) \
    || die "could not inspect bootstrap target: $MOUNT_ROOT"
  while IFS= read -r entry; do
    [[ -n $entry ]] || continue
    case ${entry##*/} in
      home|boot) ;;
      *) unexpected+=("$entry") ;;
    esac
  done <<< "$entries"
  entries=$(run_privileged find "$MOUNT_ROOT/home" -mindepth 1 -maxdepth 1 -print) \
    || die "could not inspect bootstrap home: $MOUNT_ROOT/home"
  while IFS= read -r entry; do [[ -z $entry ]] || unexpected+=("$entry"); done <<< "$entries"
  entries=$(run_privileged find "$MOUNT_ROOT/boot" -mindepth 1 -maxdepth 1 -print) \
    || die "could not inspect bootstrap EFI mount: $MOUNT_ROOT/boot"
  while IFS= read -r entry; do
    [[ -z $entry || ${entry##*/} == EFI ]] || unexpected+=("$entry")
  done <<< "$entries"
  if ! run_privileged test -d "$MOUNT_ROOT/boot/EFI"; then
    unexpected+=("missing directory: $MOUNT_ROOT/boot/EFI")
  else
    entries=$(run_privileged find "$MOUNT_ROOT/boot/EFI" -mindepth 1 -maxdepth 1 -print) \
      || die "could not inspect bootstrap EFI directory: $MOUNT_ROOT/boot/EFI"
    while IFS= read -r entry; do [[ -z $entry ]] || unexpected+=("$entry"); done <<< "$entries"
  fi

  ((${#unexpected[@]})) || return 0
  printf '\nUnexpected stage3-bootstrap target state:\n' >&2
  printf '  %s\n' "${unexpected[@]}" >&2
  printf 'The normal full installer rerun recreates an empty target before this phase.\n' >&2
  confirm_phase 'stage3 bootstrap with this unexpected target state'
}

stage3_bootstrap() {
  local command source stage3_filename stage3_size stage3_url
  local latest_manifest latest_verified archive sha256 sha256_verified release_keys
  local manifest_archive manifest_size manifest_extra

  if (( VERBOSE )); then
    cat <<EOF
Stage3 bootstrap: verified desktop-systemd base system
======================================================

The selected stage is Gentoo Release Engineering's AMD64 desktop-systemd
archive.  The signed latest-stage manifest names the current archive; its
example filename below is only a concrete follow-along value and will change
as Gentoo publishes new stage3 releases.

Discover, download, and verify the stage3
-----------------------------------------

The installer obtains Gentoo's release-key bundle, then accepts each signed
manifest only when its signer is Gentoo's pinned automated-release key. Verify
the latest-stage manifest first, then verify the detached checksum manifest
before extracting the archive. Do not accept an archive whose signed checksum
fails.

cd /mnt/gentoo
curl --fail --location --output gentoo-release.asc.20260125.gz https://dev.gentoo.org/~sam/dist/sec-keys/openpgp-keys-gentoo-release/gentoo-release.asc.20260125.gz
gzip --decompress --stdout gentoo-release.asc.20260125.gz | gpg --import
gpg --with-fingerprint --list-keys 13EBBDBEDE7A12775DFDB1BABB572E0E2D182910
wget https://distfiles.gentoo.org/releases/amd64/autobuilds/current-stage3-amd64-desktop-systemd/latest-stage3-amd64-desktop-systemd.txt
gpg --output latest-stage3-amd64-desktop-systemd.txt.verified --decrypt latest-stage3-amd64-desktop-systemd.txt

wget https://distfiles.gentoo.org/releases/amd64/autobuilds/current-stage3-amd64-desktop-systemd/stage3-amd64-desktop-systemd-20260913T163055Z.tar.xz
wget https://distfiles.gentoo.org/releases/amd64/autobuilds/current-stage3-amd64-desktop-systemd/stage3-amd64-desktop-systemd-20260913T163055Z.tar.xz.sha256
gpg --output stage3-amd64-desktop-systemd-20260913T163055Z.tar.xz.sha256.verified --decrypt stage3-amd64-desktop-systemd-20260913T163055Z.tar.xz.sha256
sha256sum --check stage3-amd64-desktop-systemd-20260913T163055Z.tar.xz.sha256.verified

Extract the stage and prepare the chroot
----------------------------------------

Extraction preserves extended attributes and the numeric owners assigned by
Release Engineering.  The resolver copy and slave bind mounts make the new
system usable for the next chroot-based configuration phase without allowing
mount events to propagate back into the live environment.

tar xpf stage3-amd64-desktop-systemd-20260913T163055Z.tar.xz --xattrs-include='*.*' --numeric-owner -C /mnt/gentoo
cp --dereference /etc/resolv.conf /mnt/gentoo/etc/resolv.conf
mount --types proc /proc /mnt/gentoo/proc
mount --rbind /sys /mnt/gentoo/sys
mount --make-rslave /mnt/gentoo/sys
mount --rbind /dev /mnt/gentoo/dev
mount --make-rslave /mnt/gentoo/dev
mount --bind /run /mnt/gentoo/run
mount --make-slave /mnt/gentoo/run

The bootstrap phase intentionally stops before entering the chroot or changing
Portage configuration; those belong to the next semantic phase.
EOF
  fi

  log 'Phase: stage3-bootstrap'

  for command in readlink lsblk; do
    require_command "$command"
  done
  [[ -n $TARGET_DISK ]] || die 'stage3-bootstrap requires --disk DEVICE to verify the prepared layout'
  TARGET_DISK=$(readlink -f -- "$TARGET_DISK")
  [[ -b $TARGET_DISK ]] || die "target is not a block device: $TARGET_DISK"
  [[ $MOUNT_ROOT == /* && $MOUNT_ROOT != / ]] || die "mount root must be a non-root absolute path: $MOUNT_ROOT"
  for command in "$LUKS_NAME" "$BTRFS_LABEL"; do
    [[ $command =~ ^[A-Za-z0-9._@+-]+$ ]] || die "unsupported characters in layout name: $command"
  done
  resolve_target_partitions

  cat <<EOF

Stage3 bootstrap plan
  * verify the mounted disk-setup layout below $MOUNT_ROOT;
  * validate Gentoo's signed latest-stage manifest;
  * download the current AMD64 desktop-systemd stage3 and validate its signed
    SHA-256 manifest;
  * extract the archive into $MOUNT_ROOT; and
  * prepare DNS and the chroot mounts (/proc, /sys, /dev, /run).
EOF
  if [[ $MODE == dry-run ]]; then
    printf '\nDry run: no network access or filesystem changes made.\n'
    return 0
  fi

  for command in awk find grep tar gzip gpg sha256sum stat mount mountpoint cp mktemp; do
    require_command "$command"
  done
  if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
    die 'stage3 bootstrap requires curl or wget to download Gentoo release files'
  fi
  (( EUID == 0 )) || require_command sudo
  for source in /etc/resolv.conf /proc /sys /dev /run; do
    [[ -e $source ]] || die "live environment prerequisite is unavailable: $source"
  done
  [[ ! -d $MOUNT_ROOT/var/lib/agentoo/repository.git ]] || die 'stage3 extraction is bootstrap-only; resume a later phase on a configured target'

  confirm_phase 'stage3 bootstrap'
  verify_disk_setup || die 'stage3-bootstrap requires a verified disk-setup layout'
  confirm_expected_bootstrap_target_state

  STAGE_WORKDIR=$(run_privileged mktemp -d "$MOUNT_ROOT/.stage3-bootstrap.XXXXXX")
  # The downloads are public release material.  Keep the workspace traversable
  # so the non-privileged parser can read GnuPG's verified output; the GnuPG
  # home itself remains root-only inside this directory.
  run_privileged chmod 755 "$STAGE_WORKDIR"
  # EXIT covers deliberate safety stops via die(); ERR covers failed commands
  # under errexit.  Both leave the validated disk layout itself untouched.
  trap 'cleanup_stage3_bootstrap_failure $?' ERR EXIT
  STAGE_GPG_HOME=$(run_privileged mktemp -d "$STAGE_WORKDIR/.gnupg.XXXXXX")

  latest_manifest=$STAGE_WORKDIR/$STAGE3_LATEST_MANIFEST
  latest_verified=$latest_manifest.verified
  release_keys=$STAGE_WORKDIR/gentoo-release.asc.20260125.gz
  download_file "$GENTOO_RELEASE_KEYS_URL" "$release_keys"
  run_privileged gzip --decompress --stdout "$release_keys" \
    | run_privileged gpg --batch --homedir "$STAGE_GPG_HOME" --import >/dev/null
  download_file "$STAGE3_BASE_URL/$STAGE3_LATEST_MANIFEST" "$latest_manifest"
  verify_pinned_release_signature "$latest_manifest" "$latest_verified"

  # Accept exactly one release entry from the authenticated manifest.  This
  # forbids URLs, path traversal, other architectures, and other init systems.
  stage3_filename=
  stage3_size=
  # Gentoo's generated manifest may omit a trailing newline, so preserve its
  # final record when read reports EOF after assigning that record.
  while IFS=$' \t' read -r manifest_archive manifest_size manifest_extra || [[ -n ${manifest_archive:-} ]]; do
    [[ -z ${manifest_extra:-} ]] || continue
    [[ $manifest_archive =~ ^stage3-amd64-desktop-systemd-[0-9]{8}T[0-9]{6}Z\.tar\.xz$ ]] || continue
    [[ $manifest_size =~ ^[1-9][0-9]*$ ]] || continue
    [[ -z $stage3_filename ]] || die 'signed latest-stage manifest contains multiple matching stage3 archives'
    stage3_filename=$manifest_archive
    stage3_size=$manifest_size
  done <"$latest_verified"
  [[ -n $stage3_filename ]] || die 'signed latest-stage manifest does not name an AMD64 desktop-systemd stage3 archive'

  stage3_url=$STAGE3_BASE_URL/$stage3_filename
  archive=$STAGE_WORKDIR/$stage3_filename
  sha256=$archive.sha256
  sha256_verified=$sha256.verified
  log "Downloading verified $stage3_filename"
  download_file "$stage3_url" "$archive"
  [[ $(stat --format=%s "$archive") == "$stage3_size" ]] \
    || die "downloaded stage3 size does not match the signed latest-stage manifest"
  download_file "$stage3_url.sha256" "$sha256"
  verify_pinned_release_signature "$sha256" "$sha256_verified"
  grep -Eq "^[[:xdigit:]]{64}[[:space:]]+\\*?$stage3_filename$" "$sha256_verified" \
    || die 'signed SHA-256 manifest does not contain the selected stage3 archive'
  (
    cd "$STAGE_WORKDIR"
    sha256sum --check --status "${sha256_verified##*/}"
  ) || die 'stage3 SHA-256 verification failed'

  log 'Extracting verified stage3 archive'
  run_privileged tar xpf "$archive" --xattrs-include='*.*' --numeric-owner -C "$MOUNT_ROOT"
  run_privileged cp --dereference /etc/resolv.conf "$MOUNT_ROOT/etc/resolv.conf"
  mountpoint -q "$MOUNT_ROOT/proc" || run_privileged mount --types proc /proc "$MOUNT_ROOT/proc"
  mountpoint -q "$MOUNT_ROOT/sys" || run_privileged mount --rbind /sys "$MOUNT_ROOT/sys"
  run_privileged mount --make-rslave "$MOUNT_ROOT/sys"
  mountpoint -q "$MOUNT_ROOT/dev" || run_privileged mount --rbind /dev "$MOUNT_ROOT/dev"
  run_privileged mount --make-rslave "$MOUNT_ROOT/dev"
  mountpoint -q "$MOUNT_ROOT/run" || run_privileged mount --bind /run "$MOUNT_ROOT/run"
  run_privileged mount --make-slave "$MOUNT_ROOT/run"

  [[ -x $MOUNT_ROOT/bin/bash && -r $MOUNT_ROOT/etc/resolv.conf ]] \
    || die 'extracted stage3 is missing its shell or resolver configuration'
  for source in "$MOUNT_ROOT/proc" "$MOUNT_ROOT/sys" "$MOUNT_ROOT/dev" "$MOUNT_ROOT/run"; do
    mountpoint -q "$source" || die "required chroot mount is missing: $source"
  done
  run_privileged rm -rf -- "$STAGE_WORKDIR"
  unset STAGE_WORKDIR STAGE_GPG_HOME
  trap - ERR EXIT

  log 'Stage3 bootstrap complete'
  cat <<EOF

The verified AMD64 desktop-systemd stage3 is installed at $MOUNT_ROOT.
DNS and /proc, /sys, /dev, and /run are mounted there for the next phase.
EOF
}

# Portage foundation support

valid_target_host() {
  case $1 in
    generic|qemu|thinktop|startop) return 0 ;;
    *) return 1 ;;
  esac
}

cleanup_portage_foundation_failure() {
  local exit_code=${1:-$?}
  (( exit_code == 0 )) && return
  trap - ERR EXIT
  set +e
  [[ -n ${PORTAGE_REPOSITORY_GPG_HOME:-} ]] \
    && run_privileged rm -rf -- "$PORTAGE_REPOSITORY_GPG_HOME"
  printf 'error: Portage foundation failed; temporary helpers removed, target preserved for retry.\n' >&2
  exit "$exit_code"
}

# Use the official binhost configuration supplied by the Gentoo stage3.
# Only installer commands enable binaries; use Gentoo's normal signing trust helper.
prepare_install_binpkgs() {
  local root=${1:-/} profile
  (( INSTALL_BINPKGS )) || return 0
  [[ -r ${root%/}/etc/portage/binrepos.conf/gentoo.conf ]] \
    || die 'binary installation requires the Gentoo stage3 binrepos.conf/gentoo.conf'
  chroot "$root" /usr/bin/python3 - /etc/portage/binrepos.conf/gentoo.conf <<'PY' \
    || die 'binary installation requires the signed official AMD64 23.0 stage3 binhost and its default cache path'
import configparser
import sys

config = configparser.ConfigParser(interpolation=None)
with open(sys.argv[1]) as source:
    config.read_file(source)
repo = config['gentoo']
if (repo['sync-uri'].rstrip('/') !=
        'https://distfiles.gentoo.org/releases/amd64/binpackages/23.0/x86-64'
        or not repo.getboolean('verify-signature', fallback=False)
        or repo['location'] != '/var/cache/binhost/gentoo'):
    sys.exit(1)
PY
  profile=$(readlink "${root%/}/etc/portage/make.profile")
  [[ $profile == */23.0/desktop/systemd ]] \
    || die 'official install binhost requires the AMD64 23.0 desktop/systemd profile'
  chroot "$root" /usr/bin/getuto
}

portage_foundation_chroot() {
  local profile locale_choice normalized_locale available_locale

  (( EUID == 0 )) || die 'the internal Portage phase must run as root'
  [[ -r /etc/gentoo-release ]] || die 'the internal Portage phase is not running in a Gentoo target'
  valid_target_host "$TARGET_HOST" || die "unsupported target host: $TARGET_HOST"
  [[ -r /etc/portage/make.conf.d/90-$TARGET_HOST ]] \
    || die "configuration repository does not provide target host: $TARGET_HOST"
  [[ -r /usr/share/zoneinfo/$TARGET_TIMEZONE ]] \
    || die "timezone is unavailable in the target: $TARGET_TIMEZONE"
  [[ $TARGET_LOCALE =~ ^[A-Za-z][A-Za-z_]*\.(UTF-8|utf8)$ ]] \
    || die "locale must be a UTF-8 locale such as en_US.UTF-8: $TARGET_LOCALE"

  for command in eselect locale-gen portageq; do
    require_command "$command"
  done

  # Verify that Portage can parse the common and selected native fragments
  # before repository or locale state is changed.
  portageq envvar COMMON_FLAGS >/dev/null \
    || die 'Portage could not evaluate the installed make.conf layers'

  [[ -d /var/db/repos/gentoo/.git ]] \
    || die 'the installation host did not provide the Gentoo Git work tree'
  portageq repos_config / | grep -Fq 'sync-type = git' \
    || die 'Portage does not report Git synchronization for the Gentoo repository'
  portageq repos_config / | grep -Fq 'sync-uri = https://github.com/gentoo-mirror/gentoo.git' \
    || die 'Portage does not report the expected Gentoo Git synchronization endpoint'

  profile=$(eselect profile show)
  [[ $profile == *desktop/systemd* ]] \
    || die "stage3 profile is not an AMD64 desktop/systemd profile: $profile"

  ln -snf "../usr/share/zoneinfo/$TARGET_TIMEZONE" /etc/localtime
  printf '%s\n' "$TARGET_TIMEZONE" >/etc/timezone
  printf '%s UTF-8\n' "$TARGET_LOCALE" >/etc/locale.gen
  locale-gen
  locale_choice=${TARGET_LOCALE/UTF-8/utf8}
  eselect locale set "$locale_choice"
  env-update

  normalized_locale=${TARGET_LOCALE,,}
  normalized_locale=${normalized_locale//-/}
  available_locale=0
  while IFS= read -r locale_choice; do
    locale_choice=${locale_choice,,}
    locale_choice=${locale_choice//-/}
    if [[ $locale_choice == "$normalized_locale" ]]; then
      available_locale=1
      break
    fi
  done < <(locale -a)
  (( available_locale )) || die "generated locale is unavailable: $TARGET_LOCALE"
  [[ $(readlink -f /etc/localtime) == "/usr/share/zoneinfo/$TARGET_TIMEZONE" ]] \
    || die "timezone link does not resolve to $TARGET_TIMEZONE"

  log 'Portage foundation complete'
  cat <<EOF

Configuration target: $TARGET_HOST
Gentoo profile:       ${profile##*$'\n'}
Timezone:             $TARGET_TIMEZONE
Locale:               $TARGET_LOCALE

The Gentoo ebuild repository now synchronizes through the official Git mirror.
Target-side Git installation and the initial @world update remain intentionally
deferred to the system-update phase.
EOF
}

# Git creates parent directories using its umask. File permission repair cannot
# make private parents readable, so shared system configuration needs 0755 dirs.
# Existing private directories (notably /root and the FAT-masked ESP) stay private.
checkout_configuration() {
  run_privileged /bin/bash -c 'umask 022; exec git "$@"' "$PROGRAM-checkout" \
    --git-dir="$1" --work-tree="$2" checkout --force "$CONFIG_BRANCH"
}

# Target-only masks precede package hooks that can create snapshot boundaries.
# Stage3 tar extraction creates directories, not Btrfs subvolume objects.
# Checkout supplies tmpfiles overrides; never defer this policy until first boot.
apply_optional_systemd_policy() {
  local policy=$MOUNT_ROOT/etc/agentoo/masked-units.conf unit
  [[ -f $policy && ! -L $policy ]] || die 'checkout lacks optional systemd policy'
  while IFS= read -r unit || [[ -n $unit ]]; do
    [[ -z $unit || $unit == \#* ]] && continue
    [[ $unit =~ ^[a-zA-Z0-9][a-zA-Z0-9@_.-]*\.(service|socket)$ ]] || die "invalid masked unit: $unit"
    run_privileged systemctl --root="$MOUNT_ROOT" mask "$unit"
  done < "$policy"
}

install_portage_foundation() {
  local command source config_git_dir config_revision signature_status planned_profile esp_uuid

  if (( VERBOSE )); then
    cat <<'EOF'
Portage foundation: live configuration and Git synchronization
================================================================

The configuration repository is a bare Git database whose work tree is the
installed system itself. Files below /etc and /usr/local are therefore both
operational configuration and tracked files; no deployment copy or symlink
farm separates edits from version control. Common Portage policy is loaded
before the explicitly selected host fragment.

Install the configuration work tree
-----------------------------------

mkdir -p /var/lib/agentoo
git clone --bare --single-branch --branch main https://github.com/grahamlopez/agentoo.git /var/lib/agentoo/repository.git
git --git-dir=/var/lib/agentoo/repository.git config core.bare false
git --git-dir=/var/lib/agentoo/repository.git config core.worktree /
git --git-dir=/var/lib/agentoo/repository.git config status.showUntrackedFiles no
git --git-dir=/var/lib/agentoo/repository.git config pull.rebase true
git --git-dir=/var/lib/agentoo/repository.git config remote.origin.fetch +refs/heads/main:refs/remotes/origin/main
git --git-dir=/var/lib/agentoo/repository.git config branch.main.remote origin
git --git-dir=/var/lib/agentoo/repository.git config branch.main.merge refs/heads/main
git --git-dir=/var/lib/agentoo/repository.git --work-tree=/ checkout --force main
printf '%s\n' 'GENTOO_TARGET_HOST="qemu"' >/etc/agentoo/target-host

mkdir -p /mnt/gentoo/var/db/repos
git clone --depth 1 https://github.com/gentoo-mirror/gentoo.git /mnt/gentoo/var/db/repos/gentoo
GNUPGHOME=/tmp/gentoo-repository-keys
mkdir -m 700 "$GNUPGHOME"
gpg --homedir "$GNUPGHOME" --import /mnt/gentoo/usr/share/openpgp-keys/gentoo-release.asc
GNUPGHOME="$GNUPGHOME" git -C /mnt/gentoo/var/db/repos/gentoo verify-commit HEAD
rm -rf "$GNUPGHOME"

Configure the target from inside the chroot
-------------------------------------------

chroot /mnt/gentoo /bin/bash
portageq repos_config /
eselect profile show
ln -snf ../usr/share/zoneinfo/America/New_York /etc/localtime
printf '%s\n' America/New_York >/etc/timezone
printf '%s UTF-8\n' en_US.UTF-8 >/etc/locale.gen
locale-gen
eselect locale set en_US.utf8
env-update

The Gentoo stage3 supplies the official AMD64 23.0 x86-64 binhost
in /etc/portage/binrepos.conf/gentoo.conf, with signature verification.
It is available for explicit emerge --getbinpkg use but is not enabled by
ordinary post-install operations. Installation prefers signed binaries by default;
--no-install-binpkgs selects source-only installer package operations.

This phase validates the effective Portage configuration and repository but
does not update @world. That update belongs after all common and host-specific
policy is established.
EOF
  fi

  log 'Phase: portage-foundation'

  valid_target_host "$TARGET_HOST" || die "unsupported target host: $TARGET_HOST"
  [[ -n $CONFIG_SOURCE && $CONFIG_SOURCE != *$'\n'* ]] || die 'configuration source must be a non-empty single line'
  [[ -n $CONFIG_BRANCH && $CONFIG_BRANCH != -* && $CONFIG_BRANCH != *$'\n'* ]] \
    || die 'configuration branch must be a non-empty branch name'
  [[ $TARGET_TIMEZONE =~ ^[A-Za-z0-9_+-]+(/[A-Za-z0-9_+-]+)*$ && $TARGET_TIMEZONE != *..* ]] \
    || die "unsupported timezone syntax: $TARGET_TIMEZONE"
  [[ $TARGET_LOCALE =~ ^[A-Za-z][A-Za-z_]*\.(UTF-8|utf8)$ ]] \
    || die "locale must be a UTF-8 locale such as en_US.UTF-8: $TARGET_LOCALE"
  [[ -n $TARGET_DISK ]] || die 'portage-foundation requires --disk DEVICE to verify the prepared layout'
  TARGET_DISK=$(readlink -f -- "$TARGET_DISK")
  [[ -b $TARGET_DISK ]] || die "target is not a block device: $TARGET_DISK"
  resolve_target_partitions

  if [[ $MODE == dry-run ]]; then
    planned_profile='existing AMD64 desktop/systemd profile (verified during execution)'
  else
    require_command chroot
    (( EUID == 0 )) || require_command sudo
    [[ -x $MOUNT_ROOT/bin/bash && -r $MOUNT_ROOT/etc/gentoo-release ]] \
      || die 'portage-foundation requires an extracted Gentoo stage3'
    # The stage3 profile symlink exists before its repository is populated.
    # Read its target without resolving the not-yet-installed profiles tree.
    planned_profile=$(run_privileged readlink "$MOUNT_ROOT/etc/portage/make.profile")
    planned_profile=${planned_profile##*/profiles/}
    [[ -n $planned_profile ]] || die 'stage3 profile link is missing'
  fi
  cat <<EOF

Portage foundation plan
Configuration target: $TARGET_HOST
Gentoo profile:       $planned_profile
Timezone:             $TARGET_TIMEZONE
Locale:               $TARGET_LOCALE

  * install configuration branch $CONFIG_BRANCH from $CONFIG_SOURCE;
  * apply managed file permissions and enable Git permission hooks;
  * select the common plus $TARGET_HOST Portage layers;
  * clone and authenticate the Gentoo Git repository;
  * verify the existing profile and configure timezone and locale; and
  * stop before the initial @world update.
EOF
  if [[ $MODE == dry-run ]]; then
    printf '\nDry run: no repository, chroot, or target configuration changes made.\n'
    return 0
  fi

  for command in chroot git gpg install mktemp mountpoint python3 readlink tee; do
    require_command "$command"
  done
  git check-ref-format --branch "$CONFIG_BRANCH" >/dev/null \
    || die "invalid configuration branch name: $CONFIG_BRANCH"
  (( EUID == 0 )) || require_command sudo
  verify_disk_setup || die 'portage-foundation requires a verified disk-setup layout'
  [[ -x $MOUNT_ROOT/bin/bash && -r $MOUNT_ROOT/etc/gentoo-release ]] \
    || die 'portage-foundation requires an extracted Gentoo stage3'
  for source in "$MOUNT_ROOT/proc" "$MOUNT_ROOT/sys" "$MOUNT_ROOT/dev" "$MOUNT_ROOT/run"; do
    mountpoint -q "$source" || die "required chroot mount is missing: $source"
  done

  confirm_phase 'Portage foundation'
  trap 'cleanup_portage_foundation_failure $?' ERR EXIT

  # A retry must keep the original policy selection, rather than silently
  # relabeling an existing checkout as a different source, branch, or host.
  local record expected
  for record in source branch target-host; do
    case $record in
      source) expected=$CONFIG_SOURCE ;;
      branch) expected=$CONFIG_BRANCH ;;
      target-host) expected="GENTOO_TARGET_HOST=\"$TARGET_HOST\"" ;;
    esac
    if run_privileged test -s "$MOUNT_ROOT/etc/agentoo/$record"; then
      [[ $(run_privileged cat "$MOUNT_ROOT/etc/agentoo/$record") == "$expected" ]] ||
        die "existing $record differs; resume with the original installation options"
    fi
  done
  run_privileged install -d -m 755 "$MOUNT_ROOT/var/lib/agentoo"
  if [[ ! -d $MOUNT_ROOT/var/lib/agentoo/repository.git ]]; then
    run_privileged git clone --bare --single-branch --branch "$CONFIG_BRANCH" \
      "$CONFIG_SOURCE" "$MOUNT_ROOT/var/lib/agentoo/repository.git"
  fi
  config_git_dir=$MOUNT_ROOT/var/lib/agentoo/repository.git
  run_privileged git --git-dir="$config_git_dir" config core.bare false
  run_privileged git --git-dir="$config_git_dir" config core.worktree /
  run_privileged git --git-dir="$config_git_dir" config status.showUntrackedFiles no
  run_privileged git --git-dir="$config_git_dir" config pull.rebase true
  run_privileged git --git-dir="$config_git_dir" config remote.origin.fetch "+refs/heads/$CONFIG_BRANCH:refs/remotes/origin/$CONFIG_BRANCH"
  run_privileged git --git-dir="$config_git_dir" config "branch.$CONFIG_BRANCH.remote" origin
  run_privileged git --git-dir="$config_git_dir" config "branch.$CONFIG_BRANCH.merge" "refs/heads/$CONFIG_BRANCH"
  # The configured revision marks a completed checkout; preserve live edits on retry.
  if ! run_privileged test -s "$MOUNT_ROOT/etc/agentoo/revision"; then
    checkout_configuration "$config_git_dir" "$MOUNT_ROOT"
  fi
  config_revision=$(run_privileged git --git-dir="$config_git_dir" rev-parse "$CONFIG_BRANCH^{commit}")
  [[ -f $MOUNT_ROOT/usr/local/bin/agentoo-permissions && ! -L $MOUNT_ROOT/usr/local/bin/agentoo-permissions ]] \
    || die 'configuration checkout lacks the Agentoo permissions implementation'
  run_privileged python3 "$MOUNT_ROOT/usr/local/bin/agentoo-permissions" fix --root "$MOUNT_ROOT"
  esp_uuid=$(run_privileged findmnt -rn -o UUID --mountpoint "$MOUNT_ROOT/boot")
  [[ -n $esp_uuid ]] || die 'mounted ESP UUID is missing'
  printf '%s\n' "$esp_uuid" | run_privileged tee "$MOUNT_ROOT/etc/kernel/gentoo-dist-esp.uuid" >/dev/null
  apply_optional_systemd_policy
  # Enable only after first checkout: hooks use the target's absolute live paths.
  run_privileged git --git-dir="$config_git_dir" config core.hooksPath /usr/local/share/agentoo/git-hooks

  run_privileged install -d -m 755 "$MOUNT_ROOT/etc/agentoo"
  printf 'GENTOO_TARGET_HOST="%s"\n' "$TARGET_HOST" \
    | run_privileged tee "$MOUNT_ROOT/etc/agentoo/target-host" >/dev/null
  printf '%s\n' "$CONFIG_SOURCE" | run_privileged tee "$MOUNT_ROOT/etc/agentoo/source" >/dev/null
  printf '%s\n' "$CONFIG_BRANCH" | run_privileged tee "$MOUNT_ROOT/etc/agentoo/branch" >/dev/null
  printf '%s\n' "$config_revision" | run_privileged tee "$MOUNT_ROOT/etc/agentoo/revision" >/dev/null

  [[ -r $MOUNT_ROOT/usr/share/openpgp-keys/gentoo-release.asc ]] \
    || die 'the stage3 does not provide the Gentoo release-key bundle'
  run_privileged install -d -m 755 "$MOUNT_ROOT/var/db/repos"
  if [[ ! -d $MOUNT_ROOT/var/db/repos/gentoo/.git ]]; then
    run_privileged git clone --depth 1 "$GENTOO_REPOSITORY_URL" "$MOUNT_ROOT/var/db/repos/gentoo"
  fi
  PORTAGE_REPOSITORY_GPG_HOME=$(run_privileged mktemp -d "$MOUNT_ROOT/.gentoo-repository-keys.XXXXXX")
  run_privileged gpg --batch --homedir "$PORTAGE_REPOSITORY_GPG_HOME" --import \
    "$MOUNT_ROOT/usr/share/openpgp-keys/gentoo-release.asc" >/dev/null
  signature_status=$(run_privileged env GNUPGHOME="$PORTAGE_REPOSITORY_GPG_HOME" \
    git -C "$MOUNT_ROOT/var/db/repos/gentoo" verify-commit --raw HEAD 2>&1) \
    || die 'the Gentoo repository tip does not have a valid signature'
  grep -Fq "$GENTOO_REPOSITORY_SIGNING_FINGERPRINT" <<<"$signature_status" \
    || die 'the Gentoo repository tip was not signed by the pinned repository key'
  run_privileged rm -rf -- "$PORTAGE_REPOSITORY_GPG_HOME"
  unset PORTAGE_REPOSITORY_GPG_HOME

  run_chroot_phase portage --internal-portage-chroot --target-host "$TARGET_HOST" \
    --timezone "$TARGET_TIMEZONE" --locale "$TARGET_LOCALE" "${BINARY_INSTALL_OPTIONS[@]}"
  trap - ERR EXIT

  log 'Portage foundation installed'
  cat <<EOF

Configuration source:   $CONFIG_SOURCE
Configuration branch:   $CONFIG_BRANCH
Configuration revision: $config_revision
Configuration target:   $TARGET_HOST

The bare configuration repository is stored at
/var/lib/agentoo/repository.git with / as its live work tree.
EOF
}


# System update: reconcile the stage3 with the configured target policy.
# Upstream references:
# https://wiki.gentoo.org/wiki/Handbook:AMD64/Installation/Base
# https://wiki.gentoo.org/wiki/CPU_FLAGS_*
# https://wiki.gentoo.org/wiki/Dispatch-conf
# https://wiki.gentoo.org/wiki/Upgrading_Gentoo

pending_config_updates() {
  local root=${1:-} protect path
  local -a paths context=()
  [[ -z $root ]] || context=(chroot "$root")
  protect=$("${context[@]}" portageq envvar CONFIG_PROTECT)
  IFS=' ' read -r -a paths <<<"$protect"
  for path in "${paths[@]}"; do
    [[ -d $root$path ]] || continue
    find "$root$path" -type f -name '._cfg????_*' -print
  done
}

system_update_chroot() {
  local flags pending archive_dir
  (( EUID == 0 )) || die 'the internal system update must run as root'
  [[ -r /etc/gentoo-release && -d /var/lib/agentoo/repository.git ]] \
    || die 'system-update requires the Gentoo target and configuration repository'
  [[ -r /etc/portage/make.conf.d/90-$TARGET_HOST ]] \
    || die 'the selected target configuration is missing'
  valid_target_host "$TARGET_HOST" || die 'unsupported system-update target'
  grep -Fxq "GENTOO_TARGET_HOST=\"$TARGET_HOST\"" /etc/agentoo/target-host \
    || die 'system-update target differs from the installed Portage foundation'
  require_command emerge
  require_command portageq
  require_command eselect
  require_command dispatch-conf
  require_command emaint
  if [[ -n $TARGET_CPU_FLAGS ]]; then
    [[ $TARGET_CPU_FLAGS =~ ^[a-z0-9_]+([[:blank:]][a-z0-9_]+)*$ ]] || die 'invalid CPU flag list'
  fi
  portageq envvar COMMON_FLAGS >/dev/null
  prepare_install_binpkgs
  # The choice applies only to installer commands; no persistent opt-in.
  install_emerge --oneshot --noreplace "${PACKAGE_OPTIONS[@]}" dev-vcs/git app-portage/cpuid2cpuflags
  emaint --auto sync
  # news list can return 1 after successfully listing items; read displays titles too.
  eselect news read
  install_emerge --oneshot --update "${PACKAGE_OPTIONS[@]}" sys-apps/portage

  flags=$TARGET_CPU_FLAGS
  if [[ -z $flags ]]; then
    flags=$(cpuid2cpuflags)
    [[ $flags == 'CPU_FLAGS_X86: '* ]] || die 'CPU detection did not return CPU_FLAGS_X86'
    flags=${flags#CPU_FLAGS_X86: }
  fi
  [[ $flags =~ ^[a-z0-9_]+([[:blank:]][a-z0-9_]+)*$ ]] || die 'invalid CPU flag list'
  install -d /etc/portage/package.use
  printf '*/* cpu_flags_x86: %s\n' "$flags" >/etc/portage/package.use/00cpu-flags
  printf 'Target CPU flags: %s\n' "$flags"
  install_emerge --pretend --verbose --update --deep --newuse "${PACKAGE_OPTIONS[@]}" @world
  confirm_phase 'initial world update (review relevant news above)'
  install_emerge --verbose --update --deep --newuse "${PACKAGE_OPTIONS[@]}" @world

  pending=$(pending_config_updates)
  if [[ -n $pending ]]; then
    printf '\nConfiguration updates awaiting review:\n%s\n' "$pending"
    [[ -r /dev/tty && -w /dev/tty ]] \
      || die 'configuration review requires a terminal; rerun system-update interactively'
    # Read the archive setting as data, never source the configuration as shell code.
    archive_dir=$(sed -n 's/^[[:space:]]*archive-dir[[:space:]]*=[[:space:]]*//p' /etc/dispatch-conf.conf | tail -n 1)
    archive_dir=${archive_dir:-/etc/config-archive}
    [[ $archive_dir == /* ]] || die 'dispatch-conf archive-dir must be absolute'
    install -d -m 700 "$archive_dir"
    dispatch-conf </dev/tty >/dev/tty 2>&1
    pending=$(pending_config_updates)
    [[ -z $pending ]] || die "configuration updates remain unresolved: $pending"
  fi
  install_emerge --verbose "${PACKAGE_OPTIONS[@]}" @preserved-rebuild
  pending=$(pending_config_updates)
  [[ -z $pending ]] || die "rebuilds left configuration updates requiring review: $pending"
  git --git-dir=/var/lib/agentoo/repository.git --work-tree=/ --no-pager diff --stat
  printf '\nReview configuration changes with: agentoo git diff\n'
  printf 'CPU policy is stored in /etc/portage/package.use/00cpu-flags.\n'
  printf 'No dependency cleanup is performed in this phase.\n'
}

install_system_update() {
  local source status=0
  log 'Phase: system-update'
  if (( VERBOSE )); then
    cat <<'EOF'
System update: reconcile the base system with target policy
==========================================================

Install tools and synchronize repositories
------------------------------------------

Install target-side Git and CPU detection tools using the selected package
policy, synchronize repositories, and read Gentoo news before approving the
initial world update. PACKAGE_OPTIONS enables binary downloads by default
(--no-install-binpkgs disables them) and requires matching USE flags and
unchanged dependencies. Packages without suitable binaries build from source.
Gentoo getuto prepares signing trust before binary-enabled package operations.

emerge --oneshot --noreplace "${PACKAGE_OPTIONS[@]}" dev-vcs/git app-portage/cpuid2cpuflags
emaint --auto sync
eselect news read
emerge --oneshot --update "${PACKAGE_OPTIONS[@]}" sys-apps/portage

Update Portage first so the world update uses the current package manager.

Establish target CPU policy
---------------------------

CPU flags default to the running machine. When preparing another machine,
provide --cpu-flags with that machine's supported flags. QEMU must expose the
same features (the runbook uses -cpu host). The detected or supplied flags are
written to /etc/portage/package.use/00cpu-flags before updating @world.
Compilation settings are inherited unchanged from the configuration files.

cpuid2cpuflags
printf '*/* cpu_flags_x86: %s\n' "$flags" >/etc/portage/package.use/00cpu-flags

Review and update the base system
---------------------------------

Show the proposed package changes and ask before proceeding with the update.

emerge --pretend --verbose --update --deep --newuse "${PACKAGE_OPTIONS[@]}" @world
emerge --verbose --update --deep --newuse "${PACKAGE_OPTIONS[@]}" @world

Review configuration and rebuild consumers
------------------------------------------

When protected configuration updates exist, prepare the archive directory
specified in /etc/dispatch-conf.conf and review updates with dispatch-conf.
Unresolved updates stop the phase. --yes does not answer merge choices.
Then rebuild preserved-library consumers and show tracked configuration changes.

install -d -m 700 "$archive_dir"
dispatch-conf
emerge --verbose "${PACKAGE_OPTIONS[@]}" @preserved-rebuild
git --git-dir=/var/lib/agentoo/repository.git --work-tree=/ --no-pager diff --stat
agentoo git diff

This phase stops before kernel installation and does not clean dependencies.
A failed update leaves the target mounted so this phase can be resumed.
EOF
  fi
  cat <<EOF

System update plan
Target root:          $MOUNT_ROOT
Configuration target: $TARGET_HOST
CPU flags:            ${TARGET_CPU_FLAGS:-detect from the running machine}

  * install Git and CPU detection tools, synchronize repositories, and read news;
  * save target CPU flags and review the proposed @world update;
  * ask before updating packages with the selected installer package policy;
  * review pending configuration updates interactively with dispatch-conf; and
  * rebuild preserved-library consumers and show configuration changes.
EOF
  if [[ $MODE == dry-run ]]; then
    printf '\nDry run: no packages, CPU policy, or configuration files changed.\n'
    return
  fi
  require_command chroot
  require_command mountpoint
  (( EUID == 0 )) || require_command sudo
  [[ -n $TARGET_DISK ]] || die 'system-update requires --disk DEVICE'
  TARGET_DISK=$(readlink -f -- "$TARGET_DISK")
  [[ -b $TARGET_DISK ]] || die "target is not a block device: $TARGET_DISK"
  resolve_target_partitions
  verify_disk_setup || die 'system-update requires a verified disk layout'
  [[ -r $MOUNT_ROOT/etc/gentoo-release ]] || die 'the Gentoo target is missing'
  require_chroot_mounts
  confirm_phase 'system update'
  # Preserve the mounted target on failure so builds and merges can be resumed.
  local -a update_options=("${BINARY_INSTALL_OPTIONS[@]}")
  (( ASSUME_YES == 0 )) || update_options+=(--yes)
  run_chroot_phase update --internal-update-chroot --target-host "$TARGET_HOST" \
    --cpu-flags "$TARGET_CPU_FLAGS" "${update_options[@]}" || status=$?
  (( status == 0 )) || die 'system-update did not complete; target remains mounted for review and retry'
  log 'System update complete: ready for kernel installation'
}

# Distribution kernel foundation: independent from the later custom EFI image.
# Upstream references:
# https://wiki.gentoo.org/wiki/Distribution_Kernel
# https://wiki.gentoo.org/wiki/Installkernel
# https://wiki.gentoo.org/wiki/Dracut
# https://wiki.gentoo.org/wiki/Handbook:AMD64/Installation/Kernel

# Resolve the vendor-level microcode choice without pruning firmware files.
# Auto microcode reads the running installation host, not the destination CPU;
# cross-vendor installations must provide an explicit --microcode selection.
resolve_kernel_firmware_policy() {
  case $TARGET_MICROCODE in
    auto)
      local vendor
      vendor=$(awk -F: '/vendor_id/ { gsub(/[[:space:]]/, "", $2); print $2; exit }' /proc/cpuinfo)
      case $vendor in
        GenuineIntel) TARGET_MICROCODE=intel ;;
        AuthenticAMD) TARGET_MICROCODE=amd ;;
        *) die 'CPU vendor is unknown; specify --microcode intel, amd, or none' ;;
      esac
      ;;
    intel|amd|none) ;;
    *) die 'microcode must be auto, intel, amd, or none' ;;
  esac
}

# Read firmware requirements from the installed configuration's common and host
# shell fragments. Validate the resolved SOF value rather than duplicating target
# hardware choices in command-line switches or installer defaults.
read_kernel_firmware_policy() {
  local root=$1 directory SOF_FIRMWARE=
  directory=${root%/}/etc/agentoo/kernel-firmware.d
  valid_target_host "$TARGET_HOST" || die "unsupported kernel target: $TARGET_HOST"
  [[ -f $directory/00-common && ! -L $directory/00-common ]] \
    || die "missing firmware policy: $directory/00-common; update the target agentoo checkout"
  source "$directory/00-common"
  if [[ -e $directory/90-$TARGET_HOST || -L $directory/90-$TARGET_HOST ]]; then
    [[ -f $directory/90-$TARGET_HOST && ! -L $directory/90-$TARGET_HOST ]] \
      || die "firmware policy is not a regular file: $directory/90-$TARGET_HOST"
    source "$directory/90-$TARGET_HOST"
  fi
  case $SOF_FIRMWARE in
    yes|no) TARGET_SOF_FIRMWARE=$SOF_FIRMWARE ;;
    *) die "SOF_FIRMWARE must be yes or no in $directory" ;;
  esac
}

# Record target boot parameters or ESP identity, allowing retries with the same value.
# An existing file must be regular, not a symlink, and contain matching text;
# a conflict stops the phase rather than silently changing the boot target.
kernel_target_data() {
  local path=$1 value=$2
  if [[ -e $path || -L $path ]]; then
    [[ -f $path && ! -L $path && $(cat "$path") == "$value" ]] \
      || die "existing target boot data requires manual review: $path"
  fi
  printf '%s\n' "$value" >"$path"
}

# Check host-side offline firmware prerequisites before installing packages.
# fuser returns 1 for both an unused file and some inspection failures. Keep its
# diagnostics: missing files or failed authorization must not mean "safe to edit".
require_idle_qemu_vars() {
  local output status=0
  output=$(run_privileged fuser "$1" 2>&1) || status=$?
  case $status in
    0) die 'QEMU variable store is in use; stop the VM before offline registration' ;;
    1) [[ -z $output ]] || die "could not inspect QEMU variable-store use: $output" ;;
    *) die "could not inspect QEMU variable-store use (status $status): $output" ;;
  esac
}

# Require an explicit VM store and a stopped VM; a new store needs a matching
# raw OVMF template, while existing stores retain their firmware state.
check_qemu_firmware() {
  [[ $TARGET_HOST == qemu ]] || {
    [[ -z $QEMU_VARS ]] || die '--qemu-vars is only valid for target qemu'
    return
  }
  [[ -n $QEMU_VARS ]] || die 'target qemu requires --qemu-vars FILE for offline EFI registration'
  [[ $QEMU_VARS != *$'\n'* ]] || die 'QEMU variable-store path must be a single line'
  [[ ! -L $QEMU_VARS ]] || die 'QEMU variable store must not be a symlink'
  QEMU_VARS=$(readlink -m -- "$QEMU_VARS")
  [[ -d ${QEMU_VARS%/*} ]] || die 'create the QEMU variable-store parent directory first'
  require_command virt-fw-vars
  require_command jq
  require_command fuser
  if [[ -e $QEMU_VARS ]]; then
    [[ -f $QEMU_VARS ]] || die 'QEMU variable store must be a regular raw OVMF file'
    require_idle_qemu_vars "$QEMU_VARS"
  else
    [[ -f $QEMU_VARS_TEMPLATE && -r $QEMU_VARS_TEMPLATE ]] \
      || die "matching OVMF template is unavailable: $QEMU_VARS_TEMPLATE"
  fi
  local source=$QEMU_VARS_TEMPLATE
  [[ ! -e $QEMU_VARS ]] || source=$QEMU_VARS
  run_privileged virt-fw-vars --input "$source" --print >/dev/null \
    || die 'cannot read the raw OVMF variable store'
}

# QEMU ONLY: edit the VM's offline OVMF file with the host virt-fw-vars CLI.
# Physical targets never call this function or write firmware here; their manual
# efibootmgr instructions are printed separately for the destination machine.
# The CLI accepts "EFI-path kernel-arguments" as one --append-boot-filepath value.
# Its file-only device path suits our single-disk VM, but does not bind to an ESP
# GUID. Keep using this store with that VM; do not share it between installations.
# A function subshell scopes temporary-file cleanup; operations remain in the
# main installer and use its existing privilege helper where needed.
register_qemu_distribution_kernel() (
  [[ $TARGET_HOST == qemu ]] || return 0
  check_qemu_firmware
  log 'Registering the distribution kernel in QEMU firmware offline'
  set -Eeuo pipefail
  trap "die 'offline QEMU registration failed; target remains mounted for review and retry'" ERR
  umask 077
  vars=$QEMU_VARS template=$QEMU_VARS_TEMPLATE root=$MOUNT_ROOT
  source=$template
  [[ ! -e $vars ]] || source=$vars
  work=$(mktemp -d)
  publish=
  trap 'rm -rf -- "$work"; if [[ -n $publish ]]; then run_privileged rm -f -- "$publish"; fi' EXIT
  version=$(run_privileged sed -n '2p' "$root/etc/kernel/gentoo-dist.version")
  [[ $(run_privileged head -n 1 "$root/etc/kernel/gentoo-dist.version") == '# Managed by gentoo-install kernel-foundation.'
     && $version =~ ^[A-Za-z0-9._+-]+-gentoo-dist(-bin)?$ ]]
  kernel="\\EFI\\Gentoo\\kernel-$version.efi"
  initrd="\\EFI\\Gentoo\\initramfs-$version.img"
  run_privileged test -s "$root/boot/EFI/Gentoo/kernel-$version.efi"
  run_privileged test -s "$root/boot/EFI/Gentoo/initramfs-$version.img"
  cmdline=$(run_privileged cat "$root/etc/kernel/cmdline")
  [[ -n $cmdline && $cmdline != *$'\n'* && $cmdline != *$'\r'* ]]
  run_privileged virt-fw-vars --input "$source" --output-json /dev/stdout >"$work/before.json"
  # Only the QEMU VM store is passed to the CLI, never the host's live EFI variables.
  run_privileged virt-fw-vars --input "$source" --output "$work/appended.fd" \
    --append-boot-filepath "$kernel $cmdline initrd=$initrd"
  run_privileged virt-fw-vars --input "$work/appended.fd" --output-json /dev/stdout >"$work/appended.json"
  # Identify the CLI-created entry and reuse an identical entry on ordinary retries.
  new=$(jq -er --slurpfile before "$work/before.json" '
    [$before[0].variables[].name] as $names |
    [.variables[] | select(.name | test("^Boot[0-9A-Fa-f]{4}$")) |
     select(.name as $n | $names | index($n) | not)] |
    if length == 1 then .[0].name else error("expected one new boot entry") end
  ' "$work/appended.json")
  entry=$(jq -er --arg name "$new" '.variables[] | select(.name == $name) | .data' "$work/appended.json")
  matching=$(jq -er --arg data "$entry" --arg new "$new" '
    [.variables[] | select(.name | test("^Boot[0-9A-Fa-f]{4}$")) |
     select(.name != $new and .data == $data) | .name] |
    if length > 1 then error("duplicate matching boot entries require review")
    else .[0] // $new end
  ' "$work/appended.json")
  # BootOrder is a sequence of little-endian 16-bit entry numbers. Move the selected
  # entry first while retaining all other entries; jq edits only this JSON variable.
  number="${matching:6:2}${matching:4:2}"
  appended_number="${new:6:2}${new:4:2}"
  jq --arg number "${number,,}" --arg appended "${appended_number,,}" '
    [.variables[] | select(.name == "BootOrder") |
     .data = ($number + ([.data | scan("....") | select(ascii_downcase != $number and ascii_downcase != $appended)] | join("")))] |
    {version: 2, variables: .}
  ' "$work/appended.json" >"$work/order.json"
  options=()
  [[ $matching == "$new" ]] || options+=(--delete "$new")
  run_privileged virt-fw-vars --input "$work/appended.fd" --output "$work/final.fd" \
    "${options[@]}" --set-json "$work/order.json"
  run_privileged virt-fw-vars --input "$work/final.fd" --output-json /dev/stdout >"$work/final.json"
  # Verify the selected entry/order and preservation of all previous other variables.
  jq -e --arg selected "$matching" --arg data "$entry" --arg number "${number,,}" \
    --slurpfile before "$work/before.json" '
    any(.variables[]; .name == $selected and .data == $data) and
    any(.variables[]; .name == "BootOrder" and (.data | startswith($number))) and
    (.variables as $after | all($before[0].variables[] | select(.name != "BootOrder");
      . as $old | any($after[]; . == $old)))
  ' "$work/final.json" >/dev/null
  if [[ -e $vars ]]; then
    if cmp -s "$work/before.json" "$work/final.json"; then
      printf 'QEMU firmware already contains %s: %s\n' "$matching" "$kernel"
      exit 0
    fi
    # Recheck immediately before publishing; the VM must stay stopped throughout.
    require_idle_qemu_vars "$vars"
    backup=$(run_privileged mktemp "${vars}.backup-XXXXXX")
    run_privileged cp --preserve=all -- "$vars" "$backup"
    printf 'Previous QEMU firmware store: %s\n' "$backup"
  fi
  # Publish on the destination filesystem so the final rename is atomic.
  publish=$(run_privileged mktemp "${vars}.new-XXXXXX")
  run_privileged cp -- "$work/final.fd" "$publish"
  if [[ -e $vars ]]; then
    run_privileged chown --reference="$vars" "$publish"
    run_privileged chmod --reference="$vars" "$publish"
  else
    run_privileged chown --reference="${vars%/*}" "$publish"
    run_privileged chmod 600 "$publish"
  fi
  run_privileged mv -f -- "$publish" "$vars"
  publish=
  printf 'Registered QEMU %s: %s\nVM firmware store: %s\n' "$matching" "$kernel" "$vars"
)

# Inspect the installed release and initramfs for matching EFI/kernel artifacts,
# encrypted-root tools, boot drivers, microcode, and any installed NVIDIA modules.
# These checks validate boot ingredients; successful boot still needs a VM or hardware.
verify_distribution_kernel() {
  local version=$1 image=/boot/EFI/Gentoo/kernel-$1.efi
  local initrd=/boot/EFI/Gentoo/initramfs-$1.img listing modules driver filename
  [[ -s $image && -s $initrd && -s /lib/modules/$version/modules.dep ]] \
    || die "kernel, initramfs, or module dependency index is missing for $version"
  [[ $(head -c 2 "$image") == MZ ]] || die 'distribution kernel is not an EFI executable'
  grep -Fxq 'CONFIG_EFI_STUB=y' "/lib/modules/$version/build/.config" \
    || die 'distribution kernel does not provide EFI stub support'
  cmp -s "$image" "/lib/modules/$version/vmlinuz" \
    || die 'EFI image differs from the installed distribution kernel'
  modules=$(lsinitrd -m "$initrd")
  for driver in crypt btrfs; do
    grep -Eq "^[[:space:]]*${driver}[[:space:]]*$" <<<"$modules" \
      || die "initramfs lacks the Dracut $driver module"
  done
  listing=$(lsinitrd "$initrd")
  grep -Eq '[ /](systemd-)?cryptsetup([[:space:]]|$)' <<<"$listing" \
    || die 'initramfs lacks a LUKS unlock executable'
  # Check the installed kernel's drivers, never the currently running host's.
  for driver in btrfs dm_crypt nvme ahci virtio_pci virtio_blk usbhid hid_generic xhci_pci atkbd; do
    filename=$(modinfo -k "$version" -F filename "$driver")
    if [[ $filename != '(builtin)' ]]; then
      filename=${filename##*/}
      grep -Fq "$filename" <<<"$listing" || die "initramfs lacks $driver ($filename)"
    fi
  done
  if [[ $TARGET_MICROCODE != none ]]; then
    local microcode_blob=AuthenticAMD.bin
    [[ $TARGET_MICROCODE != intel ]] || microcode_blob=GenuineIntel.bin
    grep -Fq "$microcode_blob" <<<"$listing" \
      || die 'initramfs lacks early CPU microcode'
  fi
  if portageq has_version / x11-drivers/nvidia-drivers; then
    for driver in nvidia nvidia_modeset nvidia_drm nvidia_uvm; do
      [[ $(modinfo -k "$version" -F vermagic "$driver") == "$version "* ]] \
        || die "NVIDIA module does not match $version: $driver"
    done
  fi
  printf '\nValidated distribution kernel: %s\nEFI kernel: %s\nInitramfs: %s\n' "$version" "$image" "$initrd"
}

# Print manual physical-firmware commands for the release just validated.
# Use the target disk and saved boot parameters; create-only preserves BootOrder,
# and an optional BootNext command selects one boot without changing defaults.
print_physical_kernel_boot_commands() {
  local version=$1 cmdline=$2 esp_uuid=$3
  local image="\\EFI\\Gentoo\\kernel-$version.efi"
  local initrd="\\EFI\\Gentoo\\initramfs-$version.img"
  local label="Gentoo distribution $version"
  cat <<INSTRUCTIONS

Manual EFI registration for this physical target
------------------------------------------------
Run these commands yourself from a UEFI-booted Linux environment on the
motherboard that will boot this disk. The installer only prints them.
Target disk: $TARGET_DISK
ESP: partition 1, filesystem UUID $esp_uuid
If you move the disk to another machine, confirm its device name there before
running the registration command.

# Inspect existing entries and boot order before making a manual change.
sudo efibootmgr --verbose

# Create this kernel's entry without adding it to the persistent BootOrder.
INSTRUCTIONS
  local device_path_option=
  [[ $TARGET_HOST != startop ]] || device_path_option=' --full-dev-path'
  printf 'sudo efibootmgr --create-only%s --disk %q --part 1 \\\n' "$device_path_option" "$TARGET_DISK"
  printf '  --label %q --loader %q \\\n' "$label" "$image"
  printf '  --unicode %q\n' "$cmdline initrd=$initrd"
  cat <<'INSTRUCTIONS'

# Find the newly created entry by its label and note its four-digit Boot number.
sudo efibootmgr --verbose

# Optional: replace XXXX below with that number, then select it for ONE boot.
# For example, Boot0007 means use 0007. BootOrder is unchanged.
sudo efibootmgr --bootnext XXXX

BootNext is cleared by firmware after use; it does not arrange a permanent
default. Keep existing entries and images while validating this installation.
INSTRUCTIONS
}

# Configure and install the binary fallback kernel inside the mounted Gentoo target.
# Establish update policy, install tools/firmware, rebuild modules and initramfs,
# then validate the selected release without writing firmware boot entries.
kernel_foundation_chroot() {
  local root_uuid luks_uuid efi_uuid cmdline atom version pending
  require_command emerge
  require_command portageq
  local -a tools=(sys-kernel/installkernel sys-kernel/dracut sys-fs/btrfs-progs sys-fs/cryptsetup sys-boot/efibootmgr)
  local -a packages=(sys-kernel/linux-firmware)
  (( EUID == 0 )) || die 'the internal kernel phase must run as root'
  [[ -r /etc/gentoo-release && -d /var/lib/agentoo/repository.git ]] \
    || die 'kernel-foundation requires the Gentoo target and configuration repository'
  valid_target_host "$TARGET_HOST" || die 'unsupported kernel target'
  grep -Fxq "GENTOO_TARGET_HOST=\"$TARGET_HOST\"" /etc/agentoo/target-host \
    || die 'kernel target differs from the installed Portage foundation'
  read_kernel_firmware_policy /
  [[ -s /etc/portage/package.use/00cpu-flags ]] || die 'run system-update before kernel-foundation'
  pending=$(pending_config_updates)
  [[ -z $pending ]] || die "resolve protected configuration updates first: $pending"
  mountpoint -q /boot && [[ $(findmnt -n -o FSTYPE --target /boot) == vfat ]] \
    || die 'the target EFI partition must be mounted at /boot'
  resolve_target_partitions
  root_uuid=$(blkid -s UUID -o value "/dev/mapper/$LUKS_NAME")
  luks_uuid=$(cryptsetup luksUUID "$CRYPT_PARTITION")
  [[ $root_uuid =~ ^[[:xdigit:]-]+$ && $luks_uuid =~ ^[[:xdigit:]-]+$ ]] || die 'invalid target UUIDs'
  efi_uuid=$(findmnt -n -o UUID --target /boot)
  [[ $efi_uuid =~ ^[[:xdigit:]-]+$ ]] || die 'could not identify the mounted ESP UUID'
  cmdline="root=UUID=$root_uuid rootfstype=btrfs rootflags=subvol=$ROOT_SUBVOL rd.luks.uuid=luks-$luks_uuid rd.luks.name=$luks_uuid=$LUKS_NAME ro"
  [[ $TARGET_HOST != qemu ]] || cmdline+=' console=tty0 console=ttyS0,115200n8'

  for policy in /etc/portage/package.use/kernel /etc/kernel/install.conf /etc/dracut.conf.d/agentoo-dist.conf /etc/kernel/install.d/04-agentoo-esp.install; do
    [[ -f $policy && ! -L $policy ]] || die "missing tracked kernel policy: $policy"
  done
  kernel_target_data /etc/kernel/cmdline "$cmdline"
  kernel_target_data /etc/kernel/gentoo-dist-esp.uuid "$efi_uuid"
  [[ $TARGET_MICROCODE != intel ]] || packages+=(sys-firmware/intel-microcode)
  [[ $TARGET_SOF_FIRMWARE != yes ]] || packages+=(sys-firmware/sof-firmware)
  # Keep the binary provider in every transaction to prevent an OR dependency
  # (firmware -> virtual/dist-kernel) from selecting the source provider.
  # Explicit packages, rather than @early_install (which also contains sources
  # and Genkernel). kernel-bin is an ebuild containing a prebuilt kernel; this
  # works in both source-only and binary-preferred installation modes.
  prepare_install_binpkgs
  install_emerge --pretend --verbose --update --newuse "${PACKAGE_OPTIONS[@]}" "${tools[@]}" "${packages[@]}" sys-kernel/gentoo-kernel-bin
  confirm_phase 'distribution kernel packages (review the plan above)'
  # Dracut modules require target-side tools before the kernel postinst runs.
  # This transaction has no firmware -> virtual/dist-kernel dependency.
  install_emerge --verbose --update --newuse "${PACKAGE_OPTIONS[@]}" "${tools[@]}"
  # Fail closed if local overrides re-enable firmware-writing plugins.
  local hook
  for hook in /usr/lib/kernel/install.d/*efistub* /etc/kernel/install.d/*efistub*; do
    [[ ! -e $hook ]] || die "unexpected firmware registration hook: $hook"
  done
  install_emerge --verbose --update --newuse "${PACKAGE_OPTIONS[@]}" "${packages[@]}" sys-kernel/gentoo-kernel-bin
  install_emerge --oneshot --verbose "${PACKAGE_OPTIONS[@]}" @module-rebuild
  atom=$(portageq best_version / sys-kernel/gentoo-kernel-bin)
  [[ -n $atom ]] || die 'binary distribution kernel was not installed'
  # pkg_config regenerates the initramfs after external modules are ready,
  # using the installed package's release rather than uname -r.
  install_emerge --config "=$atom"
  # Resolve the version from this package's recorded installed kernel tree.
  local -a release_files=()
  local contents_path
  while IFS= read -r contents_path; do
    [[ -r $contents_path ]] && release_files+=("$contents_path")
  done < <(awk '$1 == "obj" && $2 ~ /\/include\/config\/kernel.release$/ { print $2 }' "/var/db/pkg/$atom/CONTENTS")
  ((${#release_files[@]} == 1)) || die "could not identify the installed kernel release for $atom"
  version=$(<"${release_files[0]}")
  [[ $version =~ ^[A-Za-z0-9._+-]+-gentoo-dist(-bin)?$ ]] || die "unexpected distribution kernel release: $version"
  verify_distribution_kernel "$version"
  printf '# Managed by gentoo-install kernel-foundation.\n%s\n' "$version" >/etc/kernel/gentoo-dist.version
  pending=$(pending_config_updates)
  [[ -z $pending ]] || die "kernel packages left protected configuration updates: $pending"
  printf '\nKernel command line:\n%s\n' "$cmdline"
  printf 'EFI initrd argument: initrd=\\EFI\\Gentoo\\initramfs-%s.img\n' "$version"
  if [[ $TARGET_HOST == qemu ]]; then
    printf 'The host-side phase will now register this kernel in the offline VM firmware store.\n'
  else
    printf 'No firmware entry was registered. Register on the destination motherboard.\n'
    print_physical_kernel_boot_commands "$version" "$cmdline" "$efi_uuid"
  fi
  printf 'After kernel updates, register the new version; retain a tested previous entry.\n'
  printf 'Custom EFI images use their own build/copy workflow, without make install.\n'
  agentoo git --no-pager diff --stat
}

# Present the kernel phase plan and verify the mounted target before installation.
# Run this same standalone script inside the chroot with resolved target options,
# removing its temporary copy afterward and leaving mounts available on failure.
install_kernel_foundation() {
  local source status=0
  log 'Phase: kernel-foundation'
  resolve_kernel_firmware_policy
  if [[ $MODE == dry-run && ! -e $MOUNT_ROOT/etc/agentoo/kernel-firmware.d/00-common ]]; then
    TARGET_SOF_FIRMWARE='from target configuration (available after Portage foundation)'
  else
    read_kernel_firmware_policy "$MOUNT_ROOT"
  fi
  [[ $TARGET_HOST == qemu || -z $QEMU_VARS ]] || die '--qemu-vars is only valid for target qemu'
  if (( VERBOSE )); then
    cat <<'NOTES'
Distribution kernel: a reliable installation and recovery foundation
====================================================================

Install the prebuilt, unmodified Gentoo distribution kernel. This avoids
kernel compilation during installation and future world updates. A broad
Dracut initramfs supports encrypted Btrfs, physical storage, QEMU VirtIO,
and keyboard input. No host-only pruning or custom kernel configuration is
used. The binary kernel and its virtual dependency stay on stable AMD64
keywords to avoid pulling a testing source kernel during later world updates.
auto microcode follows the installation host; override it when preparing
another CPU vendor. SOF audio firmware follows the installed configuration:
/etc/agentoo/kernel-firmware.d/00-common and optional 90-TARGET fragments.
Microcode selection is vendor-level: Intel adds intel-microcode, AMD uses
linux-firmware. Firmware remains broad, with CPU matching performed at boot.
The none option skips vendor-specific selection and verification; it does not
remove microcode that the generic initramfs includes from installed firmware.

Establish package and image-generation policy
--------------------------------------------
Tracked /etc/portage/package.use/kernel supplies dist-kernel,
installkernel[systemd,dracut] and kernel-bin[initramfs,-generic-uki]. It disables
boot-manager and EFI registration flags. /etc/kernel/install.conf selects:

layout=efistub
initrd_generator=dracut
uki_generator=none
BOOT_ROOT=/boot

The layout copies an EFI kernel and separate initramfs onto the mounted ESP;
it does not require USE=efistub (which would add firmware-registration hooks).
An ESP guard stops distribution updates if the expected FAT partition is not
mounted at /boot. Final system configuration must arrange this mount in fstab.
The Dracut configuration keeps hostonly=no, early_microcode=yes, crypt/btrfs
modules, and storage/keyboard drivers. These settings persist across updates.
Static policy is tracked in Agentoo; review it through the normal Git workflow. Conflicting saved boot parameters
or ESP identity also stop the phase. These checks do not open a merge dialog
or roll back earlier changes in the phase.

Install prerequisites, then firmware and the kernel together
-----------------------------------------------------------------
Example commands inside the target chroot (Intel system with SOF audio):

emerge --pretend --verbose --update --newuse sys-kernel/installkernel sys-kernel/dracut sys-fs/btrfs-progs sys-kernel/linux-firmware sys-firmware/intel-microcode sys-firmware/sof-firmware sys-fs/cryptsetup sys-boot/efibootmgr sys-kernel/gentoo-kernel-bin
emerge --verbose --update --newuse sys-kernel/installkernel sys-kernel/dracut sys-fs/btrfs-progs sys-fs/cryptsetup sys-boot/efibootmgr
emerge --verbose --update --newuse sys-kernel/linux-firmware sys-firmware/intel-microcode sys-firmware/sof-firmware sys-kernel/gentoo-kernel-bin
emerge --oneshot @module-rebuild
emerge --config =sys-kernel/gentoo-kernel-bin-6.18.54

The first install command provides tools needed by Dracut inside the target.
Keep kernel-bin explicitly selected in the firmware transaction so its virtual
dependency cannot choose a source-built provider. The last command regenerates
the selected installed kernel's initramfs after external modules are built.
dist-kernel provides ongoing package integration,
including NVIDIA when installed; no GPU driver is selected automatically.

Read the target's firmware requirements
--------------------------------------
The common fragment sets SOF_FIRMWARE=no; 90-thinktop sets SOF_FIRMWARE=yes.
The selected host fragment overrides common policy, independent of the CPU or
audio hardware visible on the installation host. Missing common policy or an
invalid value stops the phase before package installation.

cat /etc/agentoo/kernel-firmware.d/00-common
cat /etc/agentoo/kernel-firmware.d/90-thinktop

Inspect actual target boot ingredients
-------------------------------------
Derive UUIDs from the target devices, never the host's running command line:

blkid -s UUID -o value /dev/mapper/cryptroot
cryptsetup luksUUID /dev/nbd0p2
cat /etc/kernel/cmdline
lsinitrd -m /boot/EFI/Gentoo/initramfs-6.18.54-gentoo-dist-bin.img
lsinitrd /boot/EFI/Gentoo/initramfs-6.18.54-gentoo-dist-bin.img
modinfo -k 6.18.54-gentoo-dist-bin btrfs
modinfo -k 6.18.54-gentoo-dist-bin nvidia

Only inspect NVIDIA if installed. The phase verifies the EFI executable,
matching kernel/modules, cryptsetup or systemd-cryptsetup, crypt/btrfs modules,
boot drivers and early microcode. It does not prove hardware behavior or
successful boot.

Maintenance and the boundary to first boot
-----------------------------------------
emerge --update --deep --newuse @world

Distribution package hooks install versioned kernel/initramfs files beneath
/boot/EFI/Gentoo. For later physical-system kernel updates, the user registers
each new version manually with efibootmgr from the running target. Retaining a
previous kernel and EFI entry known to boot is user maintenance advice, not an
installer-managed recovery policy. A fresh installation has no previous Gentoo
kernel to retain. QEMU registration preserves entries already in its variable
store, but cannot determine whether any entry has been successfully boot-tested.
Firmware variables belong to the running machine, even inside a chroot. Registration
from a UEFI live system on the destination physical machine is valid. For a VM,
use the offline registration below. Do not register VM entries from
the host-side NBD chroot, which exposes the physical host's firmware variables.
First-boot configuration follows in first-boot-foundation. Physical
registration and actual boot tests remain outside this kernel phase. This phase
does not write physical firmware or prune old EFI files.
For physical targets, the phase ends by printing copy-ready efibootmgr commands
for the validated disk, release, initramfs, and root/LUKS parameters. The commands
use --create-only to leave the persistent BootOrder untouched. After reviewing
the new Boot number, optionally use --bootnext NUMBER for a single boot test;
firmware clears BootNext after use. No physical firmware command is executed
by the installer, including when --yes is used.

Example manual commands on the destination motherboard (replace the UUIDs):
sudo efibootmgr --verbose
sudo efibootmgr --create-only --disk /dev/nvme0n1 --part 1 \
  --label 'Gentoo distribution 6.18.54-gentoo-dist-bin' \
  --loader '\EFI\Gentoo\kernel-6.18.54-gentoo-dist-bin.efi' \
  --unicode 'root=UUID=ROOT_UUID rootfstype=btrfs rootflags=subvol=@ rd.luks.uuid=luks-LUKS_UUID rd.luks.name=LUKS_UUID=cryptroot ro initrd=\EFI\Gentoo\initramfs-6.18.54-gentoo-dist-bin.img'
sudo efibootmgr --verbose
sudo efibootmgr --bootnext 0007 # Only if the new entry was Boot0007.

The future optimized kernel is independently built and copied to a distinct
EFI path and explicit versioned source tree: distribution updates may change
/usr/src/linux. Do not invoke make install for that path, which would run these
hooks.

Register QEMU firmware offline (target qemu only)
------------------------------------------------
Supply --qemu-vars with the VM's persistent raw OVMF variable-store file. For
a new store, --qemu-vars-template selects the template matching the VM's OVMF
CODE image. Existing stores are preserved, not reset from the template.
The VM must be stopped. The host needs virt-fw-vars and jq.

sudo pacman -S --needed virt-firmware jq
virt-fw-vars --input /path/to/VM/OVMF_VARS.4m.fd --print
./usr/local/share/agentoo/installer/gentoo-install.sh --disk /dev/nbd0 --target-host qemu \
  --phase kernel-foundation --qemu-vars /path/to/VM/OVMF_VARS.4m.fd --verbose

The QEMU-only registration uses virt-fw-vars --append-boot-filepath with the
EFI path, saved root/LUKS arguments, serial-console arguments and initrd path.
The CLI constructs the EFI entry; the installer reuses an identical entry on
retries, puts it first in BootOrder, preserves other variables, validates a
temporary store, and backs up a changed existing store before replacing it.
The file-only device path is intended for this single-disk VM, not physical
firmware or a shared variable store. Physical targets print efibootmgr commands
for manual execution on the destination machine instead.
Keep using this same variable-store file in QEMU on every subsequent boot.
Successful offline registration prepares the VM entry; it does not prove boot.
NOTES
  fi
  cat <<PLAN

Distribution kernel plan
Target root:          $MOUNT_ROOT
Configuration target: $TARGET_HOST
Kernel:               sys-kernel/gentoo-kernel-bin (stable AMD64 fallback)
CPU microcode:        $TARGET_MICROCODE
SOF audio firmware:   $TARGET_SOF_FIRMWARE
EFI files:            /boot/EFI/Gentoo/kernel-VERSION.efi and initramfs-VERSION.img
QEMU firmware store:  ${QEMU_VARS:-not specified; used only for target qemu}

  * establish distribution-only package and Dracut policy;
  * install broad firmware, microcode, and the binary distribution kernel;
  * rebuild external modules and regenerate the matching initramfs;
  * validate the direct EFI boot ingredients and print target boot parameters.
PLAN
  if [[ $TARGET_HOST == qemu ]]; then
    printf '  * register the selected kernel in the offline VM firmware store, retaining older entries.\n'
  fi
  if [[ $MODE == dry-run ]]; then
    printf '\nDry run: no packages, kernel policy, EFI files, or firmware stores changed.\n'
    return
  fi
  [[ -n $TARGET_DISK ]] || die 'kernel-foundation requires --disk DEVICE'
  TARGET_DISK=$(readlink -f -- "$TARGET_DISK")
  [[ -b $TARGET_DISK ]] || die "target is not a block device: $TARGET_DISK"
  resolve_target_partitions
  verify_disk_setup || die 'kernel-foundation requires a verified disk layout'
  require_chroot_mounts
  [[ -r $MOUNT_ROOT/etc/gentoo-release ]] || die 'the Gentoo target is missing'
  check_qemu_firmware
  confirm_phase 'distribution kernel foundation'
  local -a options=("${BINARY_INSTALL_OPTIONS[@]}")
  (( ASSUME_YES == 0 )) || options+=(--yes)
  run_chroot_phase kernel --internal-kernel-chroot --target-host "$TARGET_HOST" \
    --disk "$TARGET_DISK" --luks-name "$LUKS_NAME" \
    --microcode "$TARGET_MICROCODE" "${options[@]}" || status=$?
  (( status == 0 )) || die 'kernel-foundation did not complete; target remains mounted for review and retry'
  # Offline firmware editing is exclusively for the QEMU target.
  if [[ $TARGET_HOST == qemu ]]; then
    register_qemu_distribution_kernel
  fi
  log 'Distribution kernel foundation complete: boot ingredients validated; actual boot remains untested'
}

# First boot foundation: configure the mounted target without contacting its bus.
# References: Gentoo Handbook Installation/System and Installation/Tools;
# systemd-firstboot(1), systemctl(1), and dhcpcd's 20-resolv.conf hook.
# Runtime initialization is automatic at boot. This phase establishes persistent
# identity, mounts, credentials and explicit service policy before that boot.
configure_wifi() (
  local root=$1 device interface destination source candidate ssid open_network temporary=
  umask 077
  trap 'if [[ -n $temporary ]]; then rm -f -- "$temporary"; fi' EXIT
  for device in /sys/class/net/*; do
    [[ -d $device/phy80211 ]] || continue
    interface=${device##*/}
    destination=$root/etc/wpa_supplicant/wpa_supplicant-$interface.conf
    if [[ -e $destination || -L $destination ]]; then
      [[ -s $destination && -f $destination && ! -L $destination ]] || die "inspect existing Wi-Fi configuration: $destination"
      chmod 600 "$destination"
      printf 'Preserving Wi-Fi configuration for %s.\n' "$interface"
      continue
    fi
    install -d -m 755 "$root/etc/wpa_supplicant"
    source=
    for candidate in "/etc/wpa_supplicant/wpa_supplicant-$interface.conf" \
        /etc/wpa_supplicant/wpa_supplicant.conf /etc/wpa_supplicant.conf; do
      [[ -s $candidate && -f $candidate ]] || continue
      source=$candidate
      break
    done
    if [[ -n $source ]]; then
      install -m 600 "$source" "$destination"
      printf 'Copied native Wi-Fi configuration for %s.\n' "$interface"
      continue
    fi
    printf 'No native host wpa_supplicant configuration found for %s; NetworkManager/iwd profiles are not imported.\n' "$interface"
    printf 'Wi-Fi SSID for %s (blank to defer): ' "$interface" >/dev/tty
    IFS= read -r ssid </dev/tty
    [[ -n $ssid ]] || continue
    printf 'Open network (no password)? [y/N] ' >/dev/tty
    IFS= read -r open_network </dev/tty
    temporary=$(mktemp "$destination.XXXXXX")
    printf 'ctrl_interface=/run/wpa_supplicant\n' >"$temporary"
    if [[ $open_network == y || $open_network == Y || $open_network == yes ]]; then
      ssid=$(printf '%s' "$ssid" | od -An -v -tx1 | tr -d ' \n')
      printf 'network={\n ssid=%s\n key_mgmt=NONE\n}\n' "$ssid" >>"$temporary"
    else
      # New wpa_passphrase requires a terminal; older releases do not hide input.
      # Restore terminal settings even when generation fails or is interrupted.
      (
        local tty_settings
        tty_settings=$(stty -g </dev/tty)
        trap 'stty "$tty_settings" </dev/tty; printf "\n" >/dev/tty' EXIT
        stty -echo </dev/tty
        printf 'Wi-Fi password: ' >/dev/tty
        chroot "$root" /usr/bin/wpa_passphrase "$ssid" </dev/tty
      ) | sed '/^[[:space:]]*#psk=/d' >>"$temporary"
    fi
    mv -- "$temporary" "$destination"
    temporary=
    printf 'Configured Wi-Fi for %s.\n' "$interface"
  done
)

firstboot_offline() {
  (( EUID == 0 )) || die 'offline first-boot setup requires root'
  local root=$MOUNT_ROOT root_uuid esp_uuid hostname=$TARGET_HOSTNAME command unit
  [[ -r $root/etc/gentoo-release && -d $root/var/lib/agentoo/repository.git ]] \
    || die 'first-boot-foundation requires the configured Gentoo target'
  grep -Fxq "GENTOO_TARGET_HOST=\"$TARGET_HOST\"" "$root/etc/agentoo/target-host" \
    || die 'target-host differs from the installed configuration'
  for command in systemd-firstboot systemctl; do require_command "$command"; done
  [[ -x $root/usr/lib/systemd/systemd-timesyncd ]] || die 'target systemd lacks timesyncd'
  [[ -s $root/etc/kernel/cmdline ]] || die 'run kernel-foundation first'
  if [[ -z $hostname && $TARGET_HOST != generic && $TARGET_HOST != qemu ]]; then hostname=$TARGET_HOST; fi
  if [[ -z $hostname && -s $root/etc/hostname ]]; then hostname=$(cat "$root/etc/hostname"); fi
  if [[ -z $hostname ]]; then
    [[ -r /dev/tty ]] || die 'supply --hostname when no terminal is available'
    printf 'Target hostname: ' >/dev/tty
    IFS= read -r hostname </dev/tty || die 'could not read hostname'
  fi
  [[ ${#hostname} -le 63 && $hostname =~ ^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$ ]] \
    || die 'hostname must be one DNS label, at most 63 characters'
  [[ ! -s $root/etc/hostname || $(cat "$root/etc/hostname") == "$hostname" ]] \
    || die 'existing hostname conflicts with requested hostname'
  root_uuid=$(blkid -s UUID -o value "/dev/mapper/$LUKS_NAME")
  esp_uuid=$(blkid -s UUID -o value "$EFI_PARTITION")
  [[ $root_uuid =~ ^[[:xdigit:]-]+$ && $esp_uuid =~ ^[[:xdigit:]-]+$ ]] || die 'invalid filesystem UUIDs'
  [[ $(cat "$root/etc/kernel/gentoo-dist-esp.uuid") == "$esp_uuid" ]] || die 'kernel ESP identity differs'
  grep -Fq "rootflags=subvol=$ROOT_SUBVOL " "$root/etc/kernel/cmdline" || die 'kernel root subvolume differs'
  grep -Fq "root=UUID=$root_uuid " "$root/etc/kernel/cmdline" || die 'kernel root UUID differs'

  # Run package operations inside the target, but never start services there.
  [[ -f $root/root/001-firstboot-verify-and-checkpoint.sh && ! -L $root/root/001-firstboot-verify-and-checkpoint.sh ]] \
    || die 'configuration checkout lacks /root/001-firstboot-verify-and-checkpoint.sh; update agentoo before first-boot-foundation'
  run_privileged chmod 700 "$root/root/001-firstboot-verify-and-checkpoint.sh"
  [[ -f $root/root/002-agentoo-setup-user.sh && ! -L $root/root/002-agentoo-setup-user.sh ]] \
    || die 'configuration checkout lacks /root/002-agentoo-setup-user.sh; update agentoo before first-boot-foundation'
  run_privileged chmod 700 "$root/root/002-agentoo-setup-user.sh"
  local -a packages=(net-misc/dhcpcd app-shells/zsh)
  [[ $TARGET_HOST == qemu ]] || packages+=(net-wireless/wpa_supplicant)
  prepare_install_binpkgs "$root"
  target_emerge "$root" --pretend --verbose --update --newuse "${PACKAGE_OPTIONS[@]}" "${packages[@]}"
  confirm_phase 'first-boot networking packages (review the plan above)'
  target_emerge "$root" --verbose --update --newuse "${PACKAGE_OPTIONS[@]}" "${packages[@]}"
  local pending
  pending=$(pending_config_updates "$root")
  if [[ -n $pending ]]; then
    printf '\nConfiguration updates awaiting review (installation will continue):\n%s\n' "$pending"
    printf 'After boot, review these with sudo dispatch-conf; preserve intentional Agentoo settings.\n'
  fi

  # Root uses the same system Zsh defaults as ordinary users, without home copies.
  local root_shell
  root_shell=$(chroot "$root" /bin/sh -c 'readlink -f "$(command -v zsh)"') || die 'target Zsh is unavailable'
  [[ $root_shell == /* && -x $root$root_shell ]] || die 'target Zsh path is invalid'
  grep -Fxq "$root_shell" "$root/etc/shells" || die 'target Zsh is not listed in /etc/shells'
  chroot "$root" /usr/sbin/usermod --shell "$root_shell" root

  write_target_file "$root/etc/fstab" <<EOF
# Managed by gentoo-install first-boot-foundation.
UUID=$root_uuid / btrfs noatime,compress=zstd:1,subvol=@ 0 0
UUID=$root_uuid /home btrfs noatime,compress=zstd:1,subvol=@home 0 0
UUID=$esp_uuid /boot vfat fmask=0133,dmask=0022 0 2
EOF
  write_target_file "$root/etc/adjtime" <<'EOF'
0.0 0 0.0
0
UTC
EOF
  # Preserve the packaged service and configuration, adding only our hook policy.
  local dhcpcd_config=$root/etc/dhcpcd.conf
  [[ -f $dhcpcd_config && ! -L $dhcpcd_config ]] || die 'packaged dhcpcd.conf is missing'
  grep -Fxq 'nohook wpa_supplicant, hostname' "$dhcpcd_config" ||
    printf '\n# Per-interface supplicant services own authentication; hostname is local.\nnohook wpa_supplicant, hostname\n' >>"$dhcpcd_config"
  # A resolvconf provider would divert DNS updates to a service we do not use.
  ! chroot "$root" /usr/bin/env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin /bin/sh -c 'command -v resolvconf' >/dev/null ||
    die 'remove the resolvconf provider (systemd USE=-resolvconf) before configuring direct dhcpcd DNS'
  if [[ $TARGET_HOST != qemu ]]; then
    configure_wifi "$root"
  fi
  local exclude=$root/var/lib/agentoo/repository.git/info/exclude
  grep -Fxq '/etc/wpa_supplicant/wpa_supplicant-*.conf' "$exclude" ||
    printf '\n/etc/wpa_supplicant/wpa_supplicant-*.conf\n' >>"$exclude"
  # Fresh identity is random, not inherited from the shared host /run or D-Bus.
  # firstboot preserves already initialized values; never use --reset/--force.
  systemd-firstboot --root="$root" --hostname="$hostname" --setup-machine-id
  # Some stage3 shadow files already have a locked entry. passwd deliberately
  # initializes it; firstboot may regard an existing entry as already configured.
  if ! awk -F: '$1 == "root" { if ($2 == "" || $2 ~ /^[!*]/) exit 1; found=1 } END { if (!found) exit 1 }' "$root/etc/shadow"; then
    printf '\nSet the Gentoo root login password for %s.\n' "$hostname"
    printf 'The next "Enter new password" prompts create this target install.\n'
    printf 'This does not change the disk encryption passphrase or any host password.\n\n'
    chroot "$root" /usr/bin/passwd root
  else
    printf 'Gentoo root login password is already set; preserving it.\n'
  fi
  [[ $(cat "$root/etc/machine-id") =~ ^[[:xdigit:]]{32}$ ]] || die 'target machine ID is invalid'
  local version
  version=$(tail -n 1 "$root/etc/kernel/gentoo-dist.version")
  [[ $version =~ ^[A-Za-z0-9._+-]+-gentoo-dist(-bin)?$ ]] || die 'invalid recorded kernel version'
  [[ -s $root/boot/EFI/Gentoo/kernel-$version.efi && -s $root/boot/EFI/Gentoo/initramfs-$version.img && -d $root/lib/modules/$version ]] \
    || die 'distribution kernel, initramfs or modules are missing'
  # The bootstrap resolver is a regular copy, not a link to the host's resolver.
  [[ -f $root/etc/resolv.conf && ! -L $root/etc/resolv.conf ]] || die 'target resolv.conf must be a regular file for dhcpcd'
  systemctl --root="$root" preset-all --preset-mode=enable-only
  for unit in NetworkManager.service systemd-networkd.service systemd-networkd.socket systemd-networkd-wait-online.service systemd-resolved.service wpa_supplicant.service iwd.service syslog-ng.service rsyslog.service syslog.service sysklogd.service metalog.service chronyd.service ntpd.service; do
    if [[ -e $root/usr/lib/systemd/system/$unit || -e $root/etc/systemd/system/$unit ]]; then
      systemctl --root="$root" disable "$unit"
    fi
  done
  local config interface
  if [[ $TARGET_HOST != qemu ]]; then
    for config in "$root"/etc/wpa_supplicant/wpa_supplicant-*.conf; do
      [[ -s $config && ! -L $config ]] || continue
      interface=${config##*/wpa_supplicant-}
      interface=${interface%.conf}
      systemctl --root="$root" enable "wpa_supplicant@$interface.service"
      systemctl --root="$root" is-enabled "wpa_supplicant@$interface.service" >/dev/null \
        || die "Wi-Fi service not enabled: $interface"
    done
  fi
  systemctl --root="$root" enable dhcpcd.service systemd-timesyncd.service gentoo-btrfs-scrub.timer
  for unit in dhcpcd.service systemd-timesyncd.service gentoo-btrfs-scrub.timer; do
    systemctl --root="$root" is-enabled "$unit" >/dev/null || die "service not enabled: $unit"
  done
  chroot "$root" findmnt --verify --tab-file /etc/fstab
  awk -F: '$1 == "root" { if ($2 == "" || $2 ~ /^[!*]/) exit 1; found=1 } END { if (!found) exit 1 }' "$root/etc/shadow" \
    || die 'root has no usable password; set it in the target and retry'
  printf '\nFirst-boot foundation complete for %s. Runtime services have not been started.\n' "$hostname"
  printf 'After boot, run /root/001-firstboot-verify-and-checkpoint.sh to verify the system and optionally create its fresh-install checkpoint.\n'
  printf 'Then run /root/002-agentoo-setup-user.sh to configure Graham’s account and access.\n'
  printf 'Physical targets still require their EFI entry registered on the destination motherboard.\n'
}

install_firstboot_foundation() {
  log 'Phase: first-boot-foundation'
  cat <<PLAN
Target root: $MOUNT_ROOT
Hostname: ${TARGET_HOSTNAME:-$([[ $TARGET_HOST == generic || $TARGET_HOST == qemu ]] && printf 'prompt (or preserve existing)' || printf '%s' "$TARGET_HOST")}
Clock: UTC
Networking: dhcpcd; $([[ $TARGET_HOST == qemu ]] && printf 'virtual Ethernet only' || printf 'copy native wpa_supplicant config or prompt/defer')
Logging: packaged journald defaults
Time: enable existing systemd-timesyncd (no added time-service packages)
Storage: UUID mounts and monthly Btrfs scrub (no automatic balance/defrag)
PLAN
  if (( VERBOSE )); then
    cat <<'NOTES'
--hostname selects the target hostname. Without it, a named physical target
uses --target-host; generic/qemu preserves an existing hostname or prompts.
An existing root password is preserved; a missing or locked password prompts
for a new Gentoo root login password, including with --yes.

Configure identity and credentials with systemd-firstboot --root, then apply
Gentoo's enable-only presets before explicit offline service selection. UTC
is written to the target adjtime file; the host hardware clock is untouched.
No live systemctl, timedatectl, hostnamectl, or daemon-reload is used.

Wi-Fi credentials remain local root-only state, excluded from agentoo Git tracking.
Physical targets use the packaged wpa_supplicant@INTERFACE.service with
root-only per-interface configuration files and automatically detected
Wi-Fi interface names from the installation host. No custom Wi-Fi unit or udev startup rule is installed.
Copy the host's per-interface or common native configuration unchanged when
present; otherwise prompt for SSID/password or defer Wi-Fi. Referenced external
credentials/certificates require separate provisioning. Existing target
credentials are preserved on retries. Only configured packaged supplicant service instances are enabled.
QEMU uses virtual Ethernet and receives DHCP/DNS from its host-side backend.

dhcpcd owns routes and resolv.conf directly; competing network services are
disabled. Its built-in supplicant hook is disabled to avoid duplicate instances.
The scrub runs once monthly for the shared root/home filesystem. No extra
logging daemon, cron daemon, NTP package, or Btrfs maintenance package is needed.
Policy files reject unmarked conflicts, including active existing fstab or
installer policy configuration; reconcile these before retrying. The phase is resumable
but does not roll back earlier writes or package installation on failure.
NOTES
  fi
  [[ $MODE != dry-run ]] || { printf '\nDry run: no configuration, credentials, packages, or services changed.\n'; return; }
  [[ -n $TARGET_DISK ]] || die 'first-boot-foundation requires --disk'
  TARGET_DISK=$(readlink -f -- "$TARGET_DISK")
  resolve_target_partitions
  verify_disk_setup || die 'first-boot-foundation requires verified target mounts'
  local source
  require_chroot_mounts
  confirm_phase 'first-boot foundation'
  local -a options=("${BINARY_INSTALL_OPTIONS[@]}")
  (( ASSUME_YES == 0 )) || options+=(--yes)
  run_privileged /bin/bash "$0" --internal-firstboot-offline --disk "$TARGET_DISK" \
    --mount-root "$MOUNT_ROOT" --target-host "$TARGET_HOST" --hostname "$TARGET_HOSTNAME" \
    --luks-name "$LUKS_NAME" "${options[@]}"
}

# Identify the connected image for manual cleanup/boot guidance. Never guess a VM path.
qemu_handoff_image() {
  run_privileged /bin/bash -s -- "$TARGET_DISK" <<'IMAGE'
set -euo pipefail
device=${1##*/}
[[ $device =~ ^nbd[0-9]+$ ]] || exit 1
pid=$(cat "/sys/block/$device/pid")
[[ $pid =~ ^[0-9]+$ ]] || exit 1
mapfile -d '' -t args <"/proc/$pid/cmdline"
[[ ${args[0]##*/} == qemu-nbd ]] || exit 1
for arg in "${args[@]}"; do [[ $arg != --image-opts && $arg != --image-opts=* ]] || exit 1; done
image=${args[-1]}
[[ $image == /* ]] || image=$(readlink -f "/proc/$pid/cwd")/$image
image=$(readlink -e -- "$image")
[[ -f $image && $image != *$'\n'* ]] || exit 1
printf '%s\n' "$image"
IMAGE
}

print_qemu_handoff_commands() {
  local image=$1 code=${QEMU_VARS_TEMPLATE/OVMF_VARS/OVMF_CODE}
  local pid_file=/sys/block/${TARGET_DISK##*/}/pid
  printf '\nQEMU boot cheat sheet\n---------------------\n'
  printf 'The target remains mounted and LUKS is open. Clean up and detach before starting QEMU.\n'
  printf 'Leave any chroot and change to a directory outside the target before cleanup.\n'
  printf 'The boot entry was prepared during kernel setup; do not run host efibootmgr.\n'
  if [[ -z $image ]]; then
    image=/path/to/attached-target.qcow2
    printf 'Replace VM_IMAGE below with the qcow2 image attached to %s.\n' "$TARGET_DISK"
  fi
  if [[ -z $QEMU_VARS ]]; then
    printf 'Replace VM_VARS below with the firmware file prepared during kernel setup.\n'
  fi
  if [[ $code == "$QEMU_VARS_TEMPLATE" || ! -f $code ]]; then
    code=/path/to/matching/OVMF_CODE.fd
    printf 'Replace OVMF_CODE below with the CODE image matching your VARS template.\n'
  fi
  printf '\nVM_IMAGE=%q\nVM_VARS=%q\nOVMF_CODE=%q\n' "$image" "${QEMU_VARS:-/path/to/prepared/OVMF_VARS.fd}" "$code"
  printf 'if sudo umount --recursive %q && sudo cryptsetup close %q && sudo qemu-nbd --disconnect %q; then\n' \
    "$MOUNT_ROOT" "$LUKS_NAME" "$TARGET_DISK"
  printf '  for attempt in {1..50}; do\n'
  printf '    [[ ! -e %q ]] && qemu-img info "$VM_IMAGE" >/dev/null 2>&1 && break\n' "$pid_file"
  printf '    sleep 0.1\n  done\n'
  printf '  if [[ ! -e %q ]] && qemu-img info "$VM_IMAGE" >/dev/null 2>&1; then\n' "$pid_file"
  cat <<'COMMANDS'
    qemu-system-x86_64 \
      -enable-kvm -machine q35 -cpu host -m 4096 -smp 4 \
      -nic user,model=virtio-net-pci,hostfwd=tcp:127.0.0.1:2222-:22 \
      -display none -serial mon:stdio \
      -drive "if=pflash,format=raw,readonly=on,file=${OVMF_CODE//,/,,}" \
      -drive "if=pflash,format=raw,file=${VM_VARS//,/,,}" \
      -drive "if=virtio,format=qcow2,file=${VM_IMAGE//,/,,}"
  else
    printf 'NBD/image is still busy; inspect before starting QEMU.\n' >&2
  fi
fi
COMMANDS
  printf '\nIn the VM: unlock LUKS, log in as root, then run:\n/root/001-firstboot-verify-and-checkpoint.sh\n'
  printf 'After verification/checkpointing: /root/002-agentoo-setup-user.sh\n'
  printf 'Ctrl-a c switches between the serial console and QEMU monitor.\n'
  printf 'Reference: usr/local/share/agentoo/installer/QEMU-NBD-INSTALL.md\n'
}

# Handoff deliberately leaves teardown to the user. Automatic unmount/LUKS close
# repeatedly hit busy mappings, including mount copies in other namespaces during
# QEMU testing and a failed physical handoff. The error handling and host-specific
# edge cases outweighed the benefit.
# Before proposing automation again, justify that complexity against this small,
# explicit manual procedure; do not grow another namespace-recovery subsystem here.
# Failed disk-setup attempts still clean up the resources they created.
handoff() {
  log 'Phase: handoff'
  cat <<PLAN
Handoff plan
Target root: $MOUNT_ROOT
  * verify the target disk layout and first-boot configuration;
  * leave target mounts and /dev/mapper/$LUKS_NAME open; and
  * print manual cleanup and remaining boot steps.
PLAN
  if (( VERBOSE )); then
    printf '\nHandoff verifies and reports only. Cleanup and destination boot selection are manual.\n'
  fi
  [[ $MODE != dry-run ]] || { printf '\nDry run: no mounts or encrypted mappings changed.\n'; return; }
  [[ -n $TARGET_DISK ]] || die 'handoff requires --disk'
  TARGET_DISK=$(readlink -f -- "$TARGET_DISK")
  resolve_target_partitions
  verify_disk_setup || die 'handoff requires verified target mounts'
  run_privileged test -s "$MOUNT_ROOT/etc/fstab" || die 'first-boot fstab is missing'
  local version cmdline esp_uuid qemu_image=
  version=$(run_privileged tail -n 1 "$MOUNT_ROOT/etc/kernel/gentoo-dist.version")
  [[ $version =~ ^[A-Za-z0-9._+-]+-gentoo-dist(-bin)?$ ]] || die 'invalid recorded kernel version'
  cmdline=$(run_privileged cat "$MOUNT_ROOT/etc/kernel/cmdline")
  esp_uuid=$(run_privileged cat "$MOUNT_ROOT/etc/kernel/gentoo-dist-esp.uuid")
  if [[ $TARGET_HOST == qemu ]]; then
    qemu_image=$(qemu_handoff_image) || qemu_image=
  fi
  log 'Handoff complete: installation verified; target remains mounted and LUKS open'
  if [[ $TARGET_HOST == qemu ]]; then
    print_qemu_handoff_commands "$qemu_image"
  else
    print_physical_kernel_boot_commands "$version" "$cmdline" "$esp_uuid"
    printf '\nManual cleanup before booting (leave any chroot and change to a directory outside the target first):\n'
    printf 'sudo umount --recursive %q && sudo cryptsetup close %q\n' "$MOUNT_ROOT" "$LUKS_NAME"
  fi
  printf '\nIf cleanup reports a busy filesystem or mapping, stop and inspect holders; see the documented namespace-recovery procedure.\n'
  printf 'Unlock LUKS, log in with the target root password, and verify mounts, networking and failed services.\n'
}

main() {
  parse_args "$@"
  if (( INSTALL_BINPKGS )); then
    PACKAGE_OPTIONS=(--usepkg=y --getbinpkg=y --binpkg-respect-use=y --binpkg-changed-deps=y)
    BINARY_INSTALL_OPTIONS=(--install-binpkgs)
  else
    BINARY_INSTALL_OPTIONS=(--no-install-binpkgs)
  fi
  if (( INTERNAL_PORTAGE_CHROOT || INTERNAL_UPDATE_CHROOT || INTERNAL_KERNEL_CHROOT || INTERNAL_FIRSTBOOT_OFFLINE )); then
    valid_target_host "$TARGET_HOST" || die '--target-host must explicitly select generic, qemu, thinktop, or startop'
  else
    validate_arguments
  fi
  if (( RAM_BUILDS )); then
    require_command findmnt
    [[ $(findmnt -n -o FSTYPE --mountpoint /dev/shm) == tmpfs ]] || die 'installation RAM builds require /dev/shm as tmpfs; use --no-ram-builds to disable'
  else
    BINARY_INSTALL_OPTIONS+=(--no-ram-builds)
  fi
  if (( INTERNAL_FIRSTBOOT_OFFLINE )); then
    resolve_target_partitions
    firstboot_offline
    return
  fi
  if (( INTERNAL_KERNEL_CHROOT )); then
    kernel_foundation_chroot
    return
  fi
  if (( INTERNAL_UPDATE_CHROOT )); then
    system_update_chroot
    return
  fi
  if (( INTERNAL_PORTAGE_CHROOT )); then
    portage_foundation_chroot
    return
  fi
  if (( INSTALL_BINPKGS )); then
    log 'Package policy: prefer signed binaries with matching USE flags; otherwise build from source'
  else
    log 'Package policy: build from source'
  fi
  # Resolve host firmware prerequisites before any earlier destructive phase.
  if is_selected kernel-foundation && [[ $MODE != dry-run ]]; then
    if [[ $TARGET_HOST == qemu ]]; then
      printf '\nChecking QEMU firmware before any disk changes. Administrator authorization\nis needed to verify that the variable store is readable and not in use.\n'
    fi
    check_qemu_firmware
  fi
  if is_selected disk-setup; then
    disk_setup
  fi
  if is_selected stage3-bootstrap; then
    stage3_bootstrap
  fi
  if is_selected portage-foundation; then
    install_portage_foundation
  fi
  if is_selected system-update; then
    install_system_update
  fi
  if is_selected kernel-foundation; then
    install_kernel_foundation
  fi
  if is_selected first-boot-foundation; then
    install_firstboot_foundation
  fi
  if is_selected handoff; then
    handoff
  fi
}

main "$@"
