#!/bin/bash
# Build the iOS 16.7.16 root for rosy, using only the host's passwordless-sudo
# whitelist: apfs-fuse, mount/umount, rsync, mkfs/fsck.hfsplus.
#
# Difference from upstream tools/mkiosroot.sh: the cryptex -> root "hard link"
# passes are done with `rsync --ignore-existing` (a copy, not a link). That
# duplicates the shared cache instead of linking it, which is functionally the
# same for dyld at ignition level 1 and costs a few GB of the 16 GB image.
#
#   mkiosroot-rosy.sh OS.dmg SYSTEMOS.dmg APPOS.dmg OUT.img [SIZE]
set -euo pipefail
[[ $# -ge 4 ]] || { echo "usage: $0 OS.dmg SYSTEMOS.dmg APPOS.dmg OUT.img [SIZE]"; exit 2; }
os=$(realpath "$1") sysos=$(realpath "$2") appos=$(realpath "$3") out=$4 size=${5:-16G}
[[ ! -e $out ]] || { echo "refusing to overwrite $out" >&2; exit 1; }

SUDO=/usr/bin/sudo
# The sudoers whitelist names /usr/bin/apfs-fuse (a symlink to the /usr/local
# build), so resolve it explicitly instead of relying on PATH order.
APFS=/usr/bin/apfs-fuse
[[ -x $APFS ]] || APFS=$(command -v apfs-fuse)

work=$(mktemp -d)
mounts=()
cleanup() {
	local m
	for m in "${mounts[@]:-}"; do
		[[ -n "$m" ]] && $SUDO /bin/umount "$m" 2>/dev/null || true
	done
	rm -rf "$work"
}
trap cleanup EXIT

apfs_mount() {
	ln -s "$1" "$work/$2.dmg"
	mkdir "$work/$2"
	$SUDO "$APFS" "$work/$2.dmg" "$work/$2"
	mounts+=("$work/$2")
}
apfs_mount "$os" os
apfs_mount "$sysos" sysos
apfs_mount "$appos" appos

truncate -s "$size" "$out"
/usr/sbin/mkfs.hfsplus -s -J -v iOSRoot "$out"
mkdir "$work/root"
$SUDO /bin/mount -t hfsplus -o loop,force "$out" "$work/root"
mounts+=("$work/root")

copy() { echo "copying $1"; $SUDO /usr/bin/rsync -aH --numeric-ids "$1/" "$2/"; }

copy "$work/os/root" "$work/root"
# --mkpath creates the missing destination parents (upstream used `sudo mkdir -p`).
echo "copying SystemOS cryptex"
$SUDO /usr/bin/rsync -aH --numeric-ids --mkpath \
	"$work/sysos/root/" "$work/root/private/preboot/Cryptexes/OS/"
echo "copying AppOS cryptex"
$SUDO /usr/bin/rsync -aH --numeric-ids --mkpath \
	"$work/appos/root/" "$work/root/private/preboot/Cryptexes/App/"

# Cryptex files with no counterpart in the OS root (libobjc-trampolines, ...),
# plus the dyld shared cache: copy the missing ones into the root.
echo "merging cryptexes into the root"
$SUDO /usr/bin/rsync -aH --numeric-ids --ignore-existing \
	"$work/root/private/preboot/Cryptexes/OS/" "$work/root/"
$SUDO /usr/bin/rsync -aH --numeric-ids --ignore-existing \
	"$work/root/private/preboot/Cryptexes/App/" "$work/root/"

# logd's log stores: owner _logd (272), plus the .migrated markers.
stage=$(mktemp -d)
mkdir -p "$stage/diagnostics/timesync" "$stage/uuidtext"
: > "$stage/diagnostics/.migrated"
: > "$stage/diagnostics/timesync/.migrated"
: > "$stage/uuidtext/.migrated"
$SUDO /usr/bin/rsync -a --chown=272:272 --chmod=D751,F644 --mkpath "$stage/diagnostics" "$work/root/private/var/db/"
$SUDO /usr/bin/rsync -a --chown=272:272 --chmod=D755,F644 "$stage/uuidtext" "$stage/diagnostics/timesync" "$work/root/private/var/db/"
rm -rf "$stage"

# System keybag for the built-in AppleKeyStore (no passcode).
stage=$(mktemp -d)
printf '%s\n' '<?xml version="1.0" encoding="UTF-8"?>' \
	'<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">' \
	'<plist version="1.0"><dict><key>KeyBagKeys</key><data>U1dFRVQ=</data></dict></plist>' > "$stage/systembag.kb"
$SUDO /usr/bin/rsync -a --chown=0:0 --chmod=0600 --mkpath "$stage/systembag.kb" "$work/root/private/var/keybags/systembag.kb"
rm -rf "$stage"

df -h "$work/root"
$SUDO /bin/umount "$work/root"
fsck.hfsplus -f -y "$out" | grep -v 'Illegal name' || true
fsck.hfsplus -f -n "$out"
echo "wrote $out"
