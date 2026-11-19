#!/bin/bash
# Flash the iOS root and boot it. Run with the phone in fastboot.
# The flash is destructive: it erases userdata (all Android data).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT_IMG="$HERE/upstream/ios16-root.simg"
BOOT_IMG="$HERE/upstream/rosy-boot.img"
export PATH="$HOME/.local/opt/platform-tools:$PATH"

echo "== devices =="; fastboot devices
echo
read -r -p "This ERASES userdata (all Android data). Type 'wipe' to continue: " a
[ "$a" = wipe ] || { echo aborted; exit 1; }

echo "== flashing $ROOT_IMG =="
# rosy's LK max-download-size is 0x1fe00000 (~484 MiB); 512M chunks get
# rejected with "data too large", so use 256M.
fastboot -S 256M flash userdata "$ROOT_IMG"
echo "== booting =="
fastboot boot "$BOOT_IMG"
