#!/bin/sh
# CHECKPOINT CLI CONTRACT — standalone POSIX sh; no Python, Bash, or shared
# runtime helpers. Normal-command development policy: /usr/local/share/agentoo/lib/cli.py.
# Validate/help before privileges/effects. Stdout results; stderr plans/progress.
# --no-input must never prompt; restore authorization names the exact checkpoint.
# Rescue dependencies are checked below; sh alone does not supply filesystem tools.
# Fixed Agentoo layout: @ -> / and @home -> /home, with no nested subvolumes.
# EFI/ contains boot files; this tool lives outside EFI/ and survives restoration.
# Restore discards selected current state. No implicit backups or transaction journal.
set -eu
umask 077
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
usage() {
    case "${ACTION:-}" in
        create) printf '%s\n' 'Usage: agentoo checkpoint create LABEL [options]';;
        list) printf '%s\n' 'Usage: agentoo checkpoint list [options]';;
        inspect) printf '%s\n' 'Usage: agentoo checkpoint inspect NAME [options]';;
        remove) printf '%s\n' 'Usage: agentoo checkpoint remove NAME [options]';;
        restore) printf '%s\n' 'Usage: agentoo checkpoint restore NAME --device DEVICE [options]';;
        *) printf '%s\n' 'Usage: agentoo checkpoint {create|list|inspect|restore|remove} [options]';;
    esac
    cat <<'HELP'

Create LABEL: online capture; appends UTC timestamp and PID to label.
List: report Btrfs extent sizes (EFI excluded; shared sizes not additive).
Inspect NAME: verify recorded snapshots and EFI archive without target changes.
Remove NAME: permanently delete all saved components; current system unchanged.
Restore NAME: recovery media only; DISCARD selected current state, no backup.

  --device DEVICE       Target Btrfs device (required for restore; not create)
  --efi-mount PATH      EFI mountpoint (default inferred from script location)
  --system --home --efi Select exactly these components (create/restore)
  --no-system --no-home --no-efi  Subtract from defaults
  --clean-package-caches / --no-clean-package-caches  Create only; default CLEAN
                        when capturing system; otherwise keep caches
                        Explicit cleanup deletes distfiles, binpkgs, binhost
  --dry-run             Create/restore/remove: validate and plan; temporary read-only
                        inspection mount/files only, no target modifications
  --yes                 Create: authorize capture without confirmation prompt
  --confirm NAME        Restore/remove: authorize exact checkpoint without prompt
  --no-input            Never prompt; sudo -n; explicit authorization required
  -h, --help            Show help without privileges or effects

Create defaults: system + home + EFI, clear package caches with system capture.
Restore defaults: system + EFI, preserve home; EFI overlay preserves additions.
Options may precede/follow the name; -- ends options. No abbreviations.
Examples: agentoo checkpoint create before-update --dry-run
          agentoo checkpoint restore NAME --device /dev/mapper/cryptroot --confirm NAME
HELP
}
parse_args() {
ACTION=${1:-}
# Help must win even over incomplete values, but never interpret data after --.
for ARG do
    [ "$ARG" != -- ] || break
    case "$ARG" in --help|-h) usage; exit 0;; esac
done
case "$ACTION" in '') usage; exit 0;; create|list|inspect|restore|remove) shift;; *) die "unknown command: $ACTION";; esac
NAME=; S=; H=; E=; CLEAN=; DEVICE=; ESP_ARG=
DRY_RUN=0; NO_INPUT=0; YES=0; CONFIRM=; OPTIONS=1
POSITIVE=0
set_flag() {
    case "$1" in
        system) [ -z "$S" ] || [ "$S" = "$2" ] || die 'conflicting system flags'; S=$2;;
        home) [ -z "$H" ] || [ "$H" = "$2" ] || die 'conflicting home flags'; H=$2;;
        efi) [ -z "$E" ] || [ "$E" = "$2" ] || die 'conflicting EFI flags'; E=$2;;
    esac
    [ "$2" = 0 ] || POSITIVE=1
}
while [ $# -gt 0 ]; do
    if [ "$OPTIONS" = 0 ]; then
        [ -z "$NAME" ] || die 'too many checkpoint names'
        NAME=$1; shift; continue
    fi
    case "$1" in
        --) OPTIONS=0;;
        --system|--home|--efi|--no-system|--no-home|--no-efi)
            case "$ACTION" in create|restore) :;; *) die 'component flags apply only to create/restore';; esac
            FLAG=${1#--}; VALUE=1
            case "$FLAG" in no-*) FLAG=${FLAG#no-}; VALUE=0;; esac
            set_flag "$FLAG" "$VALUE";;
        --clean-package-caches|--no-clean-package-caches)
            [ "$ACTION" = create ] || die 'package cache cleanup applies only to create'
            VALUE=1; case "$1" in --no-*) VALUE=0;; esac
            [ -z "$CLEAN" ] || [ "$CLEAN" = "$VALUE" ] || die 'conflicting cleanup flags'; CLEAN=$VALUE;;
        --device|--efi-mount|--confirm|--device=*|--efi-mount=*|--confirm=*)
            OPTION=${1%%=*}
            case "$1" in *=*) VALUE=${1#*=};; *) [ $# -ge 2 ] || die "missing value for $1"; shift; VALUE=$1;; esac
            case "$VALUE" in ''|-*) die "invalid value for $OPTION";; esac
            case "$OPTION" in --device) DEVICE=$VALUE;; --efi-mount) ESP_ARG=$VALUE;; --confirm) CONFIRM=$VALUE;; esac;;
        --dry-run) DRY_RUN=1;; --no-input) NO_INPUT=1;; --yes) YES=1;;
        -*) die "unknown option: $1";;
        *) [ -z "$NAME" ] || die 'too many checkpoint names'; NAME=$1;;
    esac
    shift
done
if [ "$ACTION" = list ]; then [ -z "$NAME" ] || die 'list accepts no checkpoint name'
else
    [ -n "$NAME" ] || die 'missing checkpoint label/name'
    [ "${#NAME}" -le 127 ] || die 'checkpoint name is too long'
    case "$NAME" in .*|*[!A-Za-z0-9_.-]*) die 'invalid checkpoint label/name';; esac
fi
[ "$ACTION" != create ] || [ "${#NAME}" -le 64 ] || die 'create label is too long'
case "$ACTION" in list|inspect)
    [ "$DRY_RUN$YES" = 00 ] && [ -z "$CONFIRM" ] || die 'authorization/dry-run applies only to create/restore/remove';; esac
[ "$YES" = 0 ] || [ "$ACTION" = create ] || die '--yes applies only to create'
[ -z "$CONFIRM" ] || { { [ "$ACTION" = restore ] || [ "$ACTION" = remove ]; } && [ "$CONFIRM" = "$NAME" ]; } || die '--confirm must match the exact restore/remove name'
[ "$ACTION" != restore ] || [ -n "$DEVICE" ] || die 'restore requires --device'
DEFAULT=1; [ "$POSITIVE" = 0 ] || DEFAULT=0
S=${S:-$DEFAULT}; E=${E:-$DEFAULT}
HOME_DEFAULT=$DEFAULT; [ "$ACTION" != restore ] || HOME_DEFAULT=0
H=${H:-$HOME_DEFAULT}
[ "$ACTION" = list ] || [ "$ACTION" = inspect ] || [ "$S$H$E" != 000 ] || die 'empty component selection'
[ "$ACTION" != create ] || [ -z "$DEVICE" ] || die 'offline creation is deferred'
if [ "$ACTION" = create ]; then CLEAN=${CLEAN:-$S}; else CLEAN=${CLEAN:-0}; fi
[ "$CLEAN" != 1 ] || [ "$S" = 1 ] || die 'cleaning requires system capture'
if [ "$DRY_RUN" = 0 ]; then
    case "$ACTION" in
        create) [ "$YES" = 1 ] || { [ "$NO_INPUT" = 0 ] && [ -t 0 ]; } || die 'capture requires --yes or interactive stdin';;
        restore|remove) [ -n "$CONFIRM" ] || { [ "$NO_INPUT" = 0 ] && [ -t 0 ]; } || die "$ACTION requires --confirm NAME or interactive stdin";;
    esac
fi
}
parse_args "$@"
if [ "$(id -u)" != 0 ]; then
    printf 'agentoo: checkpoint requires root; requesting sudo authorization.\n' >&2
    if [ "$NO_INPUT" = 1 ]; then exec sudo -n -- sh "$0" "$@"; fi
    exec sudo -- sh "$0" "$@"
fi
ESP=${ESP_ARG:-$(dirname "$(dirname "$(readlink -f "$0")")")}
for TOOL in btrfs findmnt mount umount flock mktemp sha256sum tar gzip awk sort cmp readlink stat pgrep mv cp sync mkdir rm rmdir find df du date cat dirname id; do
    command -v "$TOOL" >/dev/null || die "missing tool: $TOOL"
done
if [ "$CLEAN" = 1 ]; then command -v portageq >/dev/null || die 'missing tool: portageq (package cache cleanup)'; fi
exec 9>/run/agentoo-checkpoint.lock
flock -n 9 || die 'another checkpoint operation is running'
PHASE=preflight; COMPLETED=; RESTORE_STARTED=0
TOP=; TMP=$(mktemp -d /run/agentoo-checkpoint.XXXXXX); STAGE=
cleanup_stage() {
    [ ! -L "$1" ] || return 1
    for KIND in system home; do
        [ ! -L "$1/$KIND" ] || return 1
        if [ -e "$1/$KIND" ]; then
            btrfs subvolume show "$1/$KIND" >/dev/null || return 1
            CHILDREN=$(btrfs subvolume list -o "$1/$KIND") || return 1
            [ -z "$CHILDREN" ] || return 1
            btrfs subvolume delete "$1/$KIND" >/dev/null || return 1
        fi
    done
    rmdir "$1"
}
cleanup() {
    STATUS=$?
    if [ "$STATUS" != 0 ]; then
        printf 'Checkpoint %s failed during %s. Completed components: %s.\n' "$ACTION" "$PHASE" "${COMPLETED:-none}" >&2
        if [ "$ACTION" = remove ]; then
            printf 'Retry remove %s with the same device and EFI mount to finish any remaining cleanup.\n' "$NAME" >&2
        fi
        if [ "$RESTORE_STARTED" = 1 ]; then
            printf 'Do not boot partial state. Remain in recovery, correct the failure, then retry restore %s with the same component selection and device. Named checkpoint retained.\n' "$NAME" >&2
        fi
    fi
    if [ -n "$STAGE" ] && [ -d "$STAGE" ]; then cleanup_stage "$STAGE" || printf 'Temporary copies remain: %s\n' "$STAGE" >&2; fi
    if [ -n "$TOP" ]; then
        if ! umount "$TOP"; then printf 'Temporary mount remains: %s\n' "$TOP" >&2; return; fi
    fi
    rm -rf "$TMP"
}
trap cleanup 0
trap 'printf "Interrupted during %s\n" "$PHASE" >&2; exit 130' INT
trap 'printf "Terminated during %s\n" "$PHASE" >&2; exit 143' TERM HUP
field() {
    [ "$(findmnt -rn --uniq -o TARGET --target "$1")" = "$(readlink -f "$1")" ] || die "not a mountpoint: $1"
    findmnt -rn --uniq -o "$2" --target "$1"
}
flat() {
    btrfs subvolume show "$1" >/dev/null
    CHILDREN=$(btrfs subvolume list -o "$1")
    [ -z "$CHILDREN" ] || die "nested subvolumes at $1; apply Agentoo directory policy first"
}
subuuid() {
    DETAILS=$(btrfs subvolume show "$1") || return 1
    printf '%s\n' "$DETAILS" | awk '$1=="UUID:" {print $2; exit}'
}
enabled() { case "$1" in system) [ "$S" = 1 ];; home) [ "$H" = 1 ];; efi) [ "$E" = 1 ];; esac; }
rootname() { case "$1" in system) printf '@';; home) printf '@home';; esac; }
meta() {
    META_FILE=$CP/manifest
    if [ "$ACTION" = remove ] && [ ! -e "$META_FILE" ]; then META_FILE=$CP/REMOVING; fi
    [ "$(awk -F= -v key="$1" '$1==key {n++} END {print n+0}' "$META_FILE")" = 1 ] || die "missing/duplicate metadata: $1"
    awk -F= -v key="$1" '$1==key {print substr($0,index($0,"=")+1)}' "$META_FILE"
}
esp_check() {
    [ "$(field "$ESP" FSTYPE)" = vfat ] || die "EFI must be mounted at $ESP"
    case "$ACTION:$DRY_RUN" in create:0|restore:0|remove:0)
        case ",$(field "$ESP" OPTIONS)," in *,rw,*) :;; *) die 'EFI filesystem is read-only';; esac;;
    esac
    [ -z "${ESP_UUID:-}" ] || [ "$(field "$ESP" UUID)" = "$ESP_UUID" ] || die 'EFI UUID mismatch'
}
idle() {
    if pgrep -f '(^|/)(emerge|ebuild|emaint|dispatch-conf|etc-update|kernel-install|gentoo-install\.sh)( |$)' >/dev/null; then
        die 'finish package/configuration operations first'
    else
        [ "$?" = 1 ] || die 'process inspection failed'
    fi
}
hash_efi() {
    (cd "$1" && find EFI -type f -exec sha256sum '{}' +) > "$TMP/hashes"
    LC_ALL=C sort "$TMP/hashes"
}
plan() {
    printf '\n┌─ %s %s\n' "$ACTION" "$NAME"
    if [ "$ACTION" = remove ]; then
        printf '│ DELETE checkpoint snapshots and EFI archive permanently.\n'
        printf '│ Btrfs UUID: %s; checkpoint: %s\n' "$FS_UUID" "$CP"
        printf '└─ Current system, home, boot files and firmware entries unchanged.\n'
    else
        for KIND in system home efi; do
            if enabled "$KIND"; then
                WORD=capture
                if [ "$ACTION" = restore ]; then
                    WORD='DISCARD current state; replace from checkpoint'
                    [ "$KIND" != efi ] || WORD='overlay saved files; preserve later additions'
                fi
            else
                WORD='not captured'; [ "$ACTION" != restore ] || WORD='preserve current'
            fi
            printf '│ %-7s %s\n' "$KIND" "$WORD"
        done
        printf '│ Btrfs UUID: %s\n' "$FS_UUID"
        if [ "$E" = 1 ]; then printf '│ EFI: %s (UUID %s); firmware entries unchanged\n' "$ESP" "$ESP_UUID"; fi
        if [ "$ACTION" = create ]; then
            WORD='keep distfiles and binary packages'; [ "$CLEAN" != 1 ] || WORD='DELETE distfiles and binary packages'
            printf '│ Cleanup: %s\n└─ Keep other writers idle; capture is sequential.\n' "$WORD"
        else
            printf '└─ No implicit backups. Named checkpoint retained; temporary copies discarded.\n'
        fi
    fi
    [ "$DRY_RUN" = 0 ] || { printf 'Dry run: temporary inspection mount/files only; targets unchanged.\n'; exit 0; }
    [ "$YES" != 1 ] && [ -z "$CONFIRM" ] || return 0
    printf 'Proceed? [y/N] '
    IFS= read -r ANSWER || ANSWER=
    case "$ANSWER" in y|Y|yes|YES) :;; *) printf 'Declined; target unchanged.\n'; exit 0;; esac
}
mount_top() {
    mkdir "$TMP/top"
    OPTIONS=subvolid=5; [ "$1" != ro ] || OPTIONS=$OPTIONS,ro,rescue=nologreplay
    printf 'Mounting Btrfs top level for %s inspection...\n' "$1" >&2
    mount -t btrfs -o "$OPTIONS" "$DEVICE" "$TMP/top"
    TOP=$TMP/top
    FS_UUID=$(field "$TOP" UUID)
    STORE=$TOP/gentoo-checkpoints
    [ ! -L "$STORE" ] || die 'checkpoint storage is a symlink'
}
offline() {
    [ "$(field / UUID)" != "$FS_UUID" ] || die 'boot separate recovery media before restore'
    findmnt -rn -o UUID,FSROOT,TARGET > "$TMP/mounts"
    for KIND in system home; do
        enabled "$KIND" || continue
        ROOT=/$(rootname "$KIND")
        awk -v uuid="$FS_UUID" -v root="$ROOT" -v own="$TOP" \
            '$1==uuid && $3!=own && ($2=="/" || $2==root || index($2,root"/")==1) {bad=1} END {exit bad}' \
            "$TMP/mounts" || die "unmount target $KIND before recovery"
    done
}
verify_checkpoint() {
    [ -d "$CP" ] && [ ! -L "$CP" ] || die 'checkpoint not found'
    [ -f "$CP/manifest" ] && [ ! -L "$CP/manifest" ] || die 'legacy/unsupported checkpoint: use its original recovery instructions'
    [ "$(meta format)" = 2 ] && [ "$(meta name)" = "$NAME" ] || die 'invalid checkpoint metadata'
    [ "$(meta root_uuid)" = "$FS_UUID" ] || die 'Btrfs UUID mismatch'
    [ ! -e "$CP/REMOVING" ] || die 'checkpoint removal in progress; retry remove'
    [ -f "$CP/COMPLETE" ] && [ "$(cat "$CP/COMPLETE")" = "$NAME" ] && [ ! -e "$CP/INCOMPLETE" ] || die 'incomplete checkpoint'
    for KIND in system home efi; do
        PRESENT=$(meta "$KIND")
        case "$PRESENT" in 0) continue;; 1) :;; *) die 'invalid component metadata';; esac
        [ "$KIND" != efi ] || continue
        [ ! -L "$CP/$KIND" ] || die 'snapshot is a symlink'
        [ "$(btrfs property get -ts "$CP/$KIND" ro)" = ro=true ] || die 'snapshot is not read-only'
        [ "$(subuuid "$CP/$KIND")" = "$(meta "${KIND}_uuid")" ] || die 'snapshot UUID mismatch'
        flat "$CP/$KIND"
    done
}
verify_efi() {
    ESP_UUID=$(meta esp_uuid); esp_check
    [ ! -L "$ESP/checkpoints" ] || die 'EFI checkpoint storage is a symlink'
    BOOT=$ESP/checkpoints/$NAME
    [ ! -L "$BOOT" ] || die 'EFI checkpoint is a symlink'
    [ -f "$BOOT/COMPLETE" ] && [ "$(cat "$BOOT/COMPLETE")" = "$NAME" ] && [ ! -e "$BOOT/INCOMPLETE" ] || die 'incomplete EFI checkpoint'
    [ ! -L "$BOOT/checksums" ] && [ ! -L "$BOOT/efi-files.tar.gz" ] || die 'unsafe EFI archive path'
    cmp "$CP/manifest" "$BOOT/manifest" >&2 || die 'EFI/Btrfs manifests differ'
    awk 'NF!=2 || $2 !~ /^(efi-files\.tar\.gz|boot-entries\.txt|restore-instructions\.txt)$/ {bad=1}
         {seen[$2]++} END {if (NR!=3) bad=1; for (key in seen) if (seen[key]!=1) bad=1; exit bad}' "$BOOT/checksums" || die 'invalid EFI checksum file'
    (cd "$BOOT" && sha256sum -c checksums >&2) || die 'EFI checksum mismatch'
    tar -tzf "$BOOT/efi-files.tar.gz" > "$TMP/archive-paths"
    awk \
        '$0 !~ /^EFI(\/|$)/ || $0 ~ /(^|\/)\.\.(\/|$)/ {bad=1} END {exit bad}' "$TMP/archive-paths" || die 'unsafe EFI archive paths'
    tar -tvzf "$BOOT/efi-files.tar.gz" > "$TMP/archive-types"
    awk \
        'substr($0,1,1)!="d" && substr($0,1,1)!="-" {bad=1} END {exit bad}' "$TMP/archive-types" || die 'unsafe EFI archive entries'
    mkdir "$TMP/extracted"
    tar -xzf "$BOOT/efi-files.tar.gz" -C "$TMP/extracted"
}
# Removal never recursively traverses checkpoint directories. Validate every
# entry before authorization, and preserve the manifest until all payload is gone.
removal_files() {
    for ENTRY in "$1"/* "$1"/.[!.]* "$1"/..?*; do
        [ -e "$ENTRY" ] || [ -L "$ENTRY" ] || continue
        case "${ENTRY##*/}" in
            system|home) [ "$1" = "$CP" ] || die 'unexpected EFI directory'; continue;;
            manifest|COMPLETE) :;;
            REMOVING) [ "$1" = "$CP" ] || die 'unexpected EFI removal marker';;
            checksums|efi-files.tar.gz|boot-entries.txt|restore-instructions.txt)
                [ "$1" != "$CP" ] || die 'unexpected Btrfs checkpoint file';;
            *) die "unexpected checkpoint entry: $ENTRY";;
        esac
        [ -f "$ENTRY" ] && [ ! -L "$ENTRY" ] || die "unsafe checkpoint entry: $ENTRY"
    done
}
remove_checkpoint() {
    PHASE='validate removal'
    [ -d "$CP" ] && [ ! -L "$CP" ] || die 'checkpoint not found'
    findmnt -rn -o TARGET > "$TMP/removal-mounts"
    awk -v dir="$CP" '$0==dir || index($0,dir"/")==1 {bad=1} END {exit bad}' "$TMP/removal-mounts" || die 'mounted checkpoint path'
    # An empty final directory may remain if interrupted just before rmdir.
    if [ -z "$(find "$CP" -mindepth 1 -maxdepth 1 -print)" ]; then
        plan >&2
        rmdir "$CP"; sync
        printf 'Removed checkpoint %s.\n' "$NAME" >&2
        exit 0
    fi
    for ENTRY in "$CP/manifest" "$CP/REMOVING"; do
        [ ! -L "$ENTRY" ] || die 'unsafe removal metadata'
    done
    [ -f "$CP/manifest" ] || [ -f "$CP/REMOVING" ] || die 'legacy/unsupported checkpoint removal; manual cleanup required'
    [ "$(meta format)" = 2 ] && [ "$(meta name)" = "$NAME" ] || die 'invalid checkpoint metadata'
    [ "$(meta root_uuid)" = "$FS_UUID" ] || die 'Btrfs UUID mismatch'
    RETRY=0
    if [ -e "$CP/REMOVING" ]; then
        [ -f "$CP/REMOVING" ] && [ ! -L "$CP/REMOVING" ] || die 'invalid removal marker'
        RETRY=1
    else
        [ -f "$CP/COMPLETE" ] && [ "$(cat "$CP/COMPLETE")" = "$NAME" ] && [ ! -e "$CP/INCOMPLETE" ] || die 'incomplete checkpoint; manual cleanup required'
    fi
    removal_files "$CP"
    for KIND in system home efi; do
        PRESENT=$(meta "$KIND")
        case "$PRESENT" in 0|1) :;; *) die 'invalid component metadata';; esac
        if [ "$KIND" = efi ]; then E=$PRESENT; continue; fi
        [ ! -L "$CP/$KIND" ] || die 'snapshot is a symlink'
        if [ -e "$CP/$KIND" ]; then
            [ "$PRESENT" = 1 ] || die 'unexpected snapshot'
            [ "$(btrfs property get -ts "$CP/$KIND" ro)" = ro=true ] || die 'snapshot is not read-only'
            [ "$(subuuid "$CP/$KIND")" = "$(meta "${KIND}_uuid")" ] || die 'snapshot UUID mismatch'
            flat "$CP/$KIND"
        else
            [ "$PRESENT" = 0 ] || [ "$RETRY" = 1 ] || die 'missing snapshot'
        fi
    done
    BOOT=
    if [ "$E" = 1 ]; then
        ESP_UUID=$(meta esp_uuid); esp_check
        [ ! -L "$ESP/checkpoints" ] || die 'EFI checkpoint storage is a symlink'
        BOOT=$ESP/checkpoints/$NAME
        [ ! -L "$BOOT" ] || die 'EFI checkpoint is a symlink'
        if [ -e "$BOOT" ]; then
            [ -d "$BOOT" ] || die 'EFI checkpoint is not a directory'
            removal_files "$BOOT"
            if [ "$RETRY" = 0 ]; then
                cmp "$CP/manifest" "$BOOT/manifest" >&2 || die 'EFI/Btrfs manifests differ'
            fi
        else
            [ "$RETRY" = 1 ] || die 'missing EFI checkpoint'
        fi
    fi
    for DIR in "$CP" ${BOOT:+"$BOOT"}; do
        awk -v dir="$DIR" '$0==dir || index($0,dir"/")==1 {bad=1} END {exit bad}' "$TMP/removal-mounts" || die "mounted checkpoint path: $DIR"
    done
    plan >&2
    PHASE='mark removal'
    if [ -f "$CP/manifest" ]; then cp "$CP/manifest" "$CP/REMOVING"; fi
    sync
    # Restore and inspect refuse REMOVING even while COMPLETE still exists.
    for KIND in system home; do
        PHASE="remove $KIND snapshot"
        if [ -e "$CP/$KIND" ]; then btrfs subvolume delete "$CP/$KIND" >&2; fi
    done
    PHASE='remove EFI archive'
    if [ -n "$BOOT" ] && [ -d "$BOOT" ]; then
        for ENTRY in "$BOOT"/*; do [ ! -e "$ENTRY" ] || rm -- "$ENTRY"; done
        rmdir "$BOOT"
    fi
    sync
    PHASE='remove metadata'
    # Keep retry metadata through payload deletion. A final directory containing
    # only these files can be safely retried after a failed metadata cleanup.
    rm -f -- "$CP/COMPLETE"
    rm -f -- "$CP/manifest"
    rm -- "$CP/REMOVING"
    rmdir "$CP"
    sync
    printf 'Removed checkpoint %s.\n' "$NAME" >&2
    exit 0
}
if [ "$ACTION" = create ]; then
    [ "${#NAME}" -le 64 ] || die 'create label is too long'
    [ "$(field / FSTYPE)" = btrfs ] && [ "$(field / FSROOT)" = /@ ] || die 'online Agentoo root must be @'
    [ "$(stat -Lc '%d:%i' /)" = "$(stat -Lc '%d:%i' /proc/1/root)" ] || die 'create must run on the booted system, not in a chroot'
    FS_UUID=$(field / UUID); DEVICE=UUID=$FS_UUID
    if [ "$H" = 1 ]; then
        [ "$(field /home UUID)" = "$FS_UUID" ] && [ "$(field /home FSROOT)" = /@home ] || die 'home must be mounted from @home on the root filesystem'
    fi
    ESP_UUID=none
    if [ "$E" = 1 ]; then ESP_UUID=$(field "$ESP" UUID); esp_check; fi
    if [ "$E" = 1 ]; then
        [ -r /etc/kernel/gentoo-dist-esp.uuid ] &&
        [ "$ESP_UUID" = "$(cat /etc/kernel/gentoo-dist-esp.uuid)" ] || die 'EFI differs from installer record'
    fi
    idle; MODE=rw; [ "$DRY_RUN" = 0 ] || MODE=ro; mount_top "$MODE"
    [ "$(df -Pk "$TOP" | awk 'NR==2 {print $4}')" -gt 1048576 ] || die 'free at least 1 GiB on Btrfs first'
    for KIND in system home; do if enabled "$KIND"; then flat "$TOP/$(rootname "$KIND")"; fi; done
    if [ "$CLEAN" = 1 ]; then
        for DIR in "$TOP/@" "$TOP/@/var" "$TOP/@/var/cache"; do
            [ -d "$DIR" ] && [ ! -L "$DIR" ] || die 'unsafe package cache path'
        done
        [ "$(portageq envvar DISTDIR)" = /var/cache/distfiles ] || die 'custom distfile layout requires --no-clean-package-caches'
        [ "$(portageq envvar PKGDIR)" = /var/cache/binpkgs ] || die 'custom binary package layout requires --no-clean-package-caches'
        for CACHE in /var/cache/distfiles /var/cache/binpkgs /var/cache/binhost; do
            DIR=$TOP/@$CACHE
            [ ! -L "$DIR" ] || die "unsafe package cache symlink: $CACHE"
            if [ -e "$DIR" ]; then
                [ -d "$DIR" ] || die "unsafe package cache directory: $CACHE"
            fi
            findmnt -rn -o TARGET | awk -v cache="$CACHE" '$0==cache || index($0,cache"/")==1 {bad=1} END {exit bad}' || die "package cache contains a mount: $CACHE"
        done
    fi
    if [ "$E" = 1 ]; then
        [ -d "$ESP/EFI" ] && [ ! -L "$ESP/EFI" ] || die 'missing ordinary EFI directory'
        [ ! -L "$ESP/checkpoints" ] || die 'EFI checkpoint storage is a symlink'
        [ "$(df -Pk "$ESP" | awk 'NR==2 {print $4}')" -gt "$(du -sk "$ESP/EFI" | awk '{print $1+32768}')" ] || die 'insufficient EFI backup space'
        find "$ESP/EFI" ! -type f ! -type d -print > "$TMP/efi-special"
        [ ! -s "$TMP/efi-special" ] || die 'EFI contains unsupported file types'
        hash_efi "$ESP" > "$TMP/efi-before"
        [ -s "$TMP/efi-before" ] || die 'no EFI files found'
    fi
    PHASE=plan
    NAME=$NAME-$(date -u +%Y%m%dT%H%M%SZ)-$$
    plan >&2; idle
    mkdir -p "$STORE"; CP=$STORE/$NAME; mkdir "$CP"
    printf 'Capture incomplete\n' > "$CP/INCOMPLETE"
    if [ "$CLEAN" = 1 ]; then
        PHASE="clean package caches"; printf 'Cleaning package caches...\n' >&2
        for CACHE in /var/cache/distfiles /var/cache/binpkgs /var/cache/binhost; do
            DIR=$TOP/@$CACHE
            [ ! -d "$DIR" ] || find "$DIR" -mindepth 1 -maxdepth 1 -exec rm -rf -- '{}' +
        done
    fi
    if [ "$E" = 1 ]; then
        [ ! -L "$ESP/checkpoints" ] || die 'EFI checkpoint storage is a symlink'
        mkdir -p "$ESP/checkpoints"; BOOT=$ESP/checkpoints/$NAME; mkdir "$BOOT"
        printf 'Capture incomplete\n' > "$BOOT/INCOMPLETE"
        PHASE="archive EFI"; printf 'Archiving and verifying EFI...\n' >&2
        tar -czf "$BOOT/efi-files.tar.gz" -C "$ESP" EFI
        mkdir "$TMP/efi-check"; tar -xzf "$BOOT/efi-files.tar.gz" -C "$TMP/efi-check"
        hash_efi "$TMP/efi-check" > "$TMP/efi-copy"; hash_efi "$ESP" > "$TMP/efi-after"
        cmp "$TMP/efi-before" "$TMP/efi-copy" >&2 && cmp "$TMP/efi-before" "$TMP/efi-after" >&2 || die 'EFI changed or archive verification failed'
        if command -v efibootmgr >/dev/null; then efibootmgr -v > "$BOOT/boot-entries.txt" 2>&1 || true
        else printf 'Firmware listing unavailable\n' > "$BOOT/boot-entries.txt"; fi
    fi
    PHASE=sync; printf 'Syncing filesystems...\n' >&2
    sync
    for KIND in system home; do
        enabled "$KIND" || continue
        PHASE="capture $KIND"; printf 'Capturing %s...\n' "$KIND" >&2
        btrfs subvolume snapshot -r "$TOP/$(rootname "$KIND")" "$CP/$KIND" >&2
        COMPLETED="$COMPLETED $KIND"
    done
    {
        printf 'format=2\nname=%s\nroot_uuid=%s\nesp_uuid=%s\nsystem=%s\nhome=%s\nefi=%s\n' "$NAME" "$FS_UUID" "$ESP_UUID" "$S" "$H" "$E"
        for KIND in system home; do if enabled "$KIND"; then printf '%s_uuid=%s\n' "$KIND" "$(subuuid "$CP/$KIND")"; fi; done
    } > "$CP/manifest"
    if [ "$E" = 1 ]; then
        printf 'Leave working firmware entries unchanged. Compare boot-entries.txt with efibootmgr -v; recreate missing entries manually. Root UUID: %s; EFI UUID: %s.\n' "$FS_UUID" "$ESP_UUID" > "$BOOT/restore-instructions.txt"
        cp "$CP/manifest" "$BOOT/manifest"
        (cd "$BOOT" && sha256sum efi-files.tar.gz boot-entries.txt restore-instructions.txt > checksums)
        sync; printf '%s\n' "$NAME" > "$BOOT/COMPLETE"; rm "$BOOT/INCOMPLETE"
    fi
    sync; printf '%s\n' "$NAME" > "$CP/COMPLETE"; rm "$CP/INCOMPLETE"; sync
    printf '%s\n' "$NAME"
else
    if [ -z "$DEVICE" ]; then
        [ "$ACTION" != restore ] || die 'restore requires --device'
        [ "$(field / FSTYPE)" = btrfs ] || die 'supply --device for the target'
        DEVICE=UUID=$(field / UUID)
    fi
    MODE=ro; case "$ACTION:$DRY_RUN" in restore:0|remove:0) MODE=rw;; esac
    mount_top "$MODE"
    CP=$STORE/$NAME
    if [ "$ACTION" = remove ]; then remove_checkpoint; fi
    if [ "$ACTION" = list ]; then
        PHASE="measure checkpoint extents"
        printf 'Scanning checkpoint file extents...\n' >&2
        printf '%-12s %-12s %-12s %-26s %s\n' TOTAL EXCLUSIVE SHARED STATE CHECKPOINT
        for CP in "$STORE"/*; do
            [ -d "$CP" ] && [ ! -L "$CP" ] || continue
            STATE=incomplete
            if [ -f "$CP/COMPLETE" ] && [ "$(cat "$CP/COMPLETE")" = "${CP##*/}" ] && [ ! -e "$CP/INCOMPLETE" ]; then STATE=complete; fi
            [ ! -e "$CP/REMOVING" ] || STATE=removing
            [ -f "$CP/manifest" ] || STATE="$STATE (legacy format)"
            # Scan each checkpoint as one set, including legacy nested snapshots.
            # FIEMAP sizes describe file extents, not compressed physical usage.
            SIZES='? ? ?'
            if LC_ALL=C btrfs filesystem du --summarize --human-readable "$CP" > "$TMP/usage"; then
                SIZES=$(awk 'NR==2 && NF>=4 {print $1, $2, $3; found=1}
                    END {if (!found) print "? ? ?"}' "$TMP/usage")
            else
                printf 'Warning: sizes unavailable for %s\n' "${CP##*/}" >&2
            fi
            printf '%s\n' "$SIZES" | awk -v state="$STATE" -v name="${CP##*/}" \
                '{printf "%-12s %-12s %-12s %-26s %s\n", $1, $2, $3, state, name}'
        done
        printf 'Btrfs file extents only; EFI excluded. Shared blocks overlap checkpoints; sizes are not additive.\n'
        exit 0
    fi
    PHASE="verify checkpoint"; printf 'Verifying checkpoint %s...\n' "$NAME" >&2
    CP=$STORE/$NAME; verify_checkpoint
    if [ "$ACTION" = inspect ]; then
        PHASE="verify recorded components"; printf 'Verifying recorded components...\n' >&2
        [ "$(meta efi)" != 1 ] || verify_efi
        cat "$CP/manifest"
        printf 'Recorded components verified; target unchanged.\n' >&2; exit 0
    fi
    for KIND in system home efi; do if enabled "$KIND"; then [ "$(meta "$KIND")" = 1 ] || die "checkpoint lacks $KIND"; fi; done
    offline
    if [ "$E" = 1 ]; then
        verify_efi
        [ -d "$ESP/EFI" ] && [ ! -L "$ESP/EFI" ] || die 'missing ordinary EFI directory'
        [ "$(df -Pk "$ESP" | awk 'NR==2 {print $4}')" -gt "$(du -sk "$TMP/extracted/EFI" | awk '{print $1+32768}')" ] || die 'insufficient EFI restoration space'
    fi
    for KIND in system home; do
        enabled "$KIND" || continue
        CURRENT=$TOP/$(rootname "$KIND")
        [ ! -L "$CURRENT" ] || die 'target is a symlink'
        [ ! -e "$CURRENT" ] || flat "$CURRENT"
    done
    PHASE=plan; ESP_UUID=$(meta esp_uuid); plan >&2; offline
    for OLD in "$STORE"/.restore-*; do [ ! -d "$OLD" ] || cleanup_stage "$OLD" || die 'unexpected temporary restore contents'; done
    PHASE="stage restore snapshots"; printf 'Staging restore snapshots...\n' >&2
    STAGE=$(mktemp -d "$STORE/.restore-XXXXXX")
    for KIND in system home; do if enabled "$KIND"; then btrfs subvolume snapshot "$CP/$KIND" "$STAGE/$KIND" >&2; fi; done
    PHASE=sync; printf 'Syncing filesystems...\n' >&2
    sync
    for KIND in system home; do
        enabled "$KIND" || continue
        PHASE="replace $KIND"; RESTORE_STARTED=1; printf 'Replacing %s...\n' "$KIND" >&2
        CURRENT=$TOP/$(rootname "$KIND")
        [ ! -e "$CURRENT" ] || btrfs subvolume delete "$CURRENT" >&2
        mv "$STAGE/$KIND" "$CURRENT"
        sync; COMPLETED="$COMPLETED $KIND"
    done
    if [ "$E" = 1 ]; then PHASE="overlay EFI"; RESTORE_STARTED=1; printf 'Overlaying EFI...\n' >&2; cp -R "$TMP/extracted/EFI/." "$ESP/EFI/"; sync; COMPLETED="$COMPLETED efi"; fi
    cleanup_stage "$STAGE"; STAGE=
    printf 'Restore complete. Reboot and verify. Named checkpoint retained.\n' >&2
fi
