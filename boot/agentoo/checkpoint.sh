#!/bin/sh
# Fixed Agentoo layout: @ -> / and @home -> /home, with no nested subvolumes.
# EFI/ contains boot files; this tool lives outside EFI/ and survives restoration.
# Restore discards selected current state. No implicit backups or transaction journal.
set -eu
umask 077
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
usage() {
    cat <<'EOF'
Usage: agentoo-checkpoint create LABEL [component flags] [--[no-]clean-distfiles]
       agentoo-checkpoint list [--device DEVICE]
       agentoo-checkpoint inspect NAME [--device DEVICE] [--efi-mount PATH]
       agentoo-checkpoint restore NAME --device DEVICE [--efi-mount PATH] [component flags]

Positive --system --home --efi flags select exactly those components.
Negative-only --no-system --no-home --no-efi flags subtract from defaults.
Create: system + home + EFI; clean distfiles and binary packages with system capture.
--[no-]clean-distfiles controls both package caches.
Restore: system + EFI; preserve home. Selected current state is discarded.
Creation is online-only. Restore requires recovery media and unmounted targets.
EOF
}
ACTION=${1:-}
case "$ACTION" in --help|-h|'') usage; exit 0;; create|list|inspect|restore) shift;; *) die "unknown command: $ACTION";; esac
NAME=
if [ $# -gt 0 ]; then case "$1" in --help|-h) usage; exit 0;; esac; fi
if [ "$ACTION" != list ]; then
    [ $# -gt 0 ] || die 'missing checkpoint label/name'
    NAME=$1; shift
    [ "${#NAME}" -le 127 ] || die 'checkpoint name is too long'
    case "$NAME" in ''|.*|*[!A-Za-z0-9_.-]*) die 'invalid checkpoint label/name';; esac
fi
S=; H=; E=; CLEAN=; DEVICE=
ESP=$(dirname "$(dirname "$(readlink -f "$0")")")
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
    case "$1" in
        --help|-h) usage; exit 0;;
        --system|--home|--efi|--no-system|--no-home|--no-efi)
            case "$ACTION" in create|restore) :;; *) die 'component flags apply only to create/restore';; esac
            FLAG=${1#--}; VALUE=1
            case "$FLAG" in no-*) FLAG=${FLAG#no-}; VALUE=0;; esac
            set_flag "$FLAG" "$VALUE";;
        --clean-distfiles|--no-clean-distfiles)
            [ "$ACTION" = create ] || die 'package cache cleanup applies only to create'
            VALUE=1; [ "$1" != --no-clean-distfiles ] || VALUE=0
            [ -z "$CLEAN" ] || [ "$CLEAN" = "$VALUE" ] || die 'conflicting cleanup flags'
            CLEAN=$VALUE;;
        --device|--efi-mount)
            [ $# -ge 2 ] || die "missing value for $1"
            case "$2" in ''|-*) die "invalid value for $1";; esac
            if [ "$1" = --device ]; then DEVICE=$2; else ESP=$(readlink -f "$2"); fi
            shift;;
        *) die "unknown option: $1";;
    esac
    shift
done
DEFAULT=1; [ "$POSITIVE" = 0 ] || DEFAULT=0
S=${S:-$DEFAULT}; E=${E:-$DEFAULT}
HOME_DEFAULT=$DEFAULT; [ "$ACTION" != restore ] || HOME_DEFAULT=0
H=${H:-$HOME_DEFAULT}
[ "$ACTION" = list ] || [ "$ACTION" = inspect ] || [ "$S$H$E" != 000 ] || die 'empty component selection'
[ "$ACTION" != create ] || [ -z "$DEVICE" ] || die 'offline creation is deferred'
CLEAN=${CLEAN:-$S}
[ "$ACTION" != create ] || [ "$CLEAN" != 1 ] || [ "$S" = 1 ] || die 'cleaning requires system capture'
[ "$(id -u)" = 0 ] || die 'run as root'
for TOOL in btrfs findmnt mount umount flock mktemp sha256sum tar gzip awk sort cmp readlink stat pgrep; do
    command -v "$TOOL" >/dev/null || die "missing tool: $TOOL"
done
exec 9>/run/agentoo-checkpoint.lock
flock -n 9 || die 'another checkpoint operation is running'
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
    if [ -n "$STAGE" ] && [ -d "$STAGE" ]; then cleanup_stage "$STAGE" || printf 'Temporary copies remain: %s\n' "$STAGE" >&2; fi
    if [ -n "$TOP" ]; then
        if ! umount "$TOP"; then printf 'Temporary mount remains: %s\n' "$TOP" >&2; return; fi
    fi
    rm -rf "$TMP"
}
trap cleanup 0
trap 'exit 130' INT
trap 'exit 143' TERM
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
    [ "$(awk -F= -v key="$1" '$1==key {n++} END {print n+0}' "$CP/manifest")" = 1 ] || die "missing/duplicate metadata: $1"
    awk -F= -v key="$1" '$1==key {print substr($0,index($0,"=")+1)}' "$CP/manifest"
}
esp_check() {
    [ "$(field "$ESP" FSTYPE)" = vfat ] || die "EFI must be mounted at $ESP"
    case "$ACTION" in create|restore)
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
    printf 'Proceed? [y/N] ' >/dev/tty
    IFS= read -r ANSWER </dev/tty || ANSWER=
    case "$ANSWER" in y|Y|yes|YES) :;; *) printf 'Declined; target unchanged.\n'; exit 0;; esac
}
mount_top() {
    mkdir "$TMP/top"
    OPTIONS=subvolid=5; [ "$1" != ro ] || OPTIONS=$OPTIONS,ro
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
    cmp "$CP/manifest" "$BOOT/manifest" || die 'EFI/Btrfs manifests differ'
    awk 'NF!=2 || $2 !~ /^(efi-files\.tar\.gz|boot-entries\.txt|restore-instructions\.txt)$/ {bad=1}
         {seen[$2]++} END {if (NR!=3) bad=1; for (key in seen) if (seen[key]!=1) bad=1; exit bad}' "$BOOT/checksums" || die 'invalid EFI checksum file'
    (cd "$BOOT" && sha256sum -c checksums) || die 'EFI checksum mismatch'
    tar -tzf "$BOOT/efi-files.tar.gz" > "$TMP/archive-paths"
    awk \
        '$0 !~ /^EFI(\/|$)/ || $0 ~ /(^|\/)\.\.(\/|$)/ {bad=1} END {exit bad}' "$TMP/archive-paths" || die 'unsafe EFI archive paths'
    tar -tvzf "$BOOT/efi-files.tar.gz" > "$TMP/archive-types"
    awk \
        'substr($0,1,1)!="d" && substr($0,1,1)!="-" {bad=1} END {exit bad}' "$TMP/archive-types" || die 'unsafe EFI archive entries'
    mkdir "$TMP/extracted"
    tar -xzf "$BOOT/efi-files.tar.gz" -C "$TMP/extracted"
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
    idle; mount_top rw
    [ "$(df -Pk "$TOP" | awk 'NR==2 {print $4}')" -gt 1048576 ] || die 'free at least 1 GiB on Btrfs first'
    for KIND in system home; do if enabled "$KIND"; then flat "$TOP/$(rootname "$KIND")"; fi; done
    if [ "$CLEAN" = 1 ]; then
        for DIR in "$TOP/@" "$TOP/@/var" "$TOP/@/var/cache"; do
            [ -d "$DIR" ] && [ ! -L "$DIR" ] || die 'unsafe package cache path'
        done
        [ "$(portageq envvar DISTDIR)" = /var/cache/distfiles ] || die 'custom distfile layout requires --no-clean-distfiles'
        [ "$(portageq envvar PKGDIR)" = /var/cache/binpkgs ] || die 'custom binary package layout requires --no-clean-distfiles'
        for CACHE in /var/cache/distfiles /var/cache/binpkgs; do
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
    NAME=$NAME-$(date -u +%Y%m%dT%H%M%SZ)-$$
    plan; idle
    mkdir -p "$STORE"; CP=$STORE/$NAME; mkdir "$CP"
    printf 'Capture incomplete\n' > "$CP/INCOMPLETE"
    if [ "$CLEAN" = 1 ]; then
        for CACHE in /var/cache/distfiles /var/cache/binpkgs; do
            DIR=$TOP/@$CACHE
            [ ! -d "$DIR" ] || find "$DIR" -mindepth 1 -maxdepth 1 -exec rm -rf -- '{}' +
        done
    fi
    if [ "$E" = 1 ]; then
        [ ! -L "$ESP/checkpoints" ] || die 'EFI checkpoint storage is a symlink'
        mkdir -p "$ESP/checkpoints"; BOOT=$ESP/checkpoints/$NAME; mkdir "$BOOT"
        printf 'Capture incomplete\n' > "$BOOT/INCOMPLETE"
        tar -czf "$BOOT/efi-files.tar.gz" -C "$ESP" EFI
        mkdir "$TMP/efi-check"; tar -xzf "$BOOT/efi-files.tar.gz" -C "$TMP/efi-check"
        hash_efi "$TMP/efi-check" > "$TMP/efi-copy"; hash_efi "$ESP" > "$TMP/efi-after"
        cmp "$TMP/efi-before" "$TMP/efi-copy" && cmp "$TMP/efi-before" "$TMP/efi-after" || die 'EFI changed or archive verification failed'
        if command -v efibootmgr >/dev/null; then efibootmgr -v > "$BOOT/boot-entries.txt" 2>&1 || true
        else printf 'Firmware listing unavailable\n' > "$BOOT/boot-entries.txt"; fi
    fi
    sync
    for KIND in system home; do
        enabled "$KIND" || continue
        btrfs subvolume snapshot -r "$TOP/$(rootname "$KIND")" "$CP/$KIND"
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
    printf 'Checkpoint complete: %s\n' "$NAME"
else
    if [ -z "$DEVICE" ]; then
        [ "$ACTION" != restore ] || die 'restore requires --device'
        [ "$(field / FSTYPE)" = btrfs ] || die 'supply --device for the target'
        DEVICE=UUID=$(field / UUID)
    fi
    MODE=ro; [ "$ACTION" != restore ] || MODE=rw
    mount_top "$MODE"
    if [ "$ACTION" = list ]; then
        for CP in "$STORE"/*; do
            [ -d "$CP" ] || continue
            STATE=incomplete
            if [ -f "$CP/COMPLETE" ] && [ "$(cat "$CP/COMPLETE")" = "${CP##*/}" ] && [ ! -e "$CP/INCOMPLETE" ]; then STATE=complete; fi
            [ -f "$CP/manifest" ] || STATE="$STATE (legacy format)"
            printf '%s  %s\n' "${CP##*/}" "$STATE"
        done
        exit 0
    fi
    CP=$STORE/$NAME; verify_checkpoint
    if [ "$ACTION" = inspect ]; then
        cat "$CP/manifest"; [ "$(meta efi)" != 1 ] || verify_efi
        printf 'Recorded components verified; target unchanged.\n'; exit 0
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
    ESP_UUID=$(meta esp_uuid); plan; offline
    for OLD in "$STORE"/.restore-*; do [ ! -d "$OLD" ] || cleanup_stage "$OLD" || die 'unexpected temporary restore contents'; done
    STAGE=$(mktemp -d "$STORE/.restore-XXXXXX")
    for KIND in system home; do if enabled "$KIND"; then btrfs subvolume snapshot "$CP/$KIND" "$STAGE/$KIND"; fi; done
    sync
    for KIND in system home; do
        enabled "$KIND" || continue
        CURRENT=$TOP/$(rootname "$KIND")
        [ ! -e "$CURRENT" ] || btrfs subvolume delete "$CURRENT"
        mv "$STAGE/$KIND" "$CURRENT"
        sync
    done
    if [ "$E" = 1 ]; then cp -R "$TMP/extracted/EFI/." "$ESP/EFI/"; sync; fi
    cleanup_stage "$STAGE"; STAGE=
    printf 'Restore complete. Reboot and verify. Named checkpoint retained.\n'
fi
