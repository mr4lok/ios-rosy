#!/usr/bin/env bash
# Collect the live hardware facts the rosy ADT needs. Nothing here flashes or
# writes to the phone. Run it with the phone connected over USB.
#
#   bash tools/dump-phone.sh
#
# Phase A (Android booted, USB debugging on) and phase B (fastboot mode) are
# independent; run whichever applies. Output lands in notes/live/.
set +e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
OUT="$ROOT/notes/live"
mkdir -p "$OUT"
ADB="$HOME/.local/opt/platform-tools/adb"
FASTBOOT="$HOME/.local/opt/platform-tools/fastboot"
command -v adb  >/dev/null || ADB=adb
command -v fastboot >/dev/null || FASTBOOT=fastboot

echo "== adb devices =="; "$ADB" devices -l | tee "$OUT/adb-devices.txt"

if "$ADB" get-state >/dev/null 2>&1; then
  echo "== collecting from Android =="
  "$ADB" shell getprop | grep -Ei 'ro\.(product|build|hardware|bootloader)|gui|panel|touch|fs_type' > "$OUT/getprop.txt"
  "$ADB" exec-out cat /proc/meminfo            > "$OUT/meminfo.txt"
  "$ADB" exec-out cat /proc/iomem              > "$OUT/iomem.txt"
  "$ADB" exec-out cat /proc/partitions         > "$OUT/partitions.txt"
  "$ADB" exec-out cat /proc/bus/input/devices  > "$OUT/input-devices.txt"
  "$ADB" exec-out ls -l /dev/block/by-name     > "$OUT/by-name.txt" 2>&1
  "$ADB" exec-out ls -R /sys/bus/i2c/devices   > "$OUT/i2c.txt" 2>&1
  "$ADB" exec-out cat /sys/class/graphics/fb0/name          > "$OUT/fb0-name.txt" 2>&1
  "$ADB" exec-out cat /sys/class/graphics/fb0/virtual_size  > "$OUT/fb0-size.txt" 2>&1
  "$ADB" exec-out cat /sys/class/graphics/fb0/bits_per_pixel > "$OUT/fb0-bpp.txt" 2>&1
  "$ADB" exec-out cat /sys/class/graphics/fb0/stride       > "$OUT/fb0-stride.txt" 2>&1
  # Flattened device tree (the authoritative source for the panel/touch nodes).
  "$ADB" exec-out cat /sys/firmware/fdt          > "$OUT/fdt.dtb" 2>"$OUT/fdt.err"
  "$ADB" exec-out ls /proc/device-tree           > "$OUT/device-tree-ls.txt" 2>&1
  echo "fdt bytes: $(wc -c < "$OUT/fdt.dtb")"
  "$ADB" shell 'ls -d /sys/devices/*/mdss* /sys/devices/*dsi* 2>/dev/null' > "$OUT/mdss.txt" 2>&1
else
  echo "== no adb device (boot the phone or enable USB debugging) =="
fi

echo "== fastboot devices =="; "$FASTBOOT" devices | tee "$OUT/fastboot-devices.txt"
if "$FASTBOOT" getvar product >/dev/null 2>&1; then
  echo "== collecting from fastboot =="
  "$FASTBOOT" getvar all 2>&1 | tee "$OUT/fastboot-getvar-all.txt"
  "$FASTBOOT" oem device-info 2>&1 | tee "$OUT/fastboot-device-info.txt"
  "$FASTBOOT" getvar unlocked 2>&1 | tee "$OUT/fastboot-unlocked.txt"
  "$FASTBOOT" getvar secure 2>&1 | tee "$OUT/fastboot-secure.txt"
else
  echo "== no fastboot device (power + volume down) =="
fi

echo
echo "saved to $OUT"
echo "next: python3 tools/parse-live.py"
