# rosy-port runbook (morning of 2026-11-19)

Everything below is staged. The only remaining steps need the phone and the
user's OK for the one destructive command.

## Artifacts (all in ~/ports/rosy-port/upstream/)

| file | what | size |
| --- | --- | --- |
| `xnu-kernel-rosy/kernel.development.sweet` | XNU kernel (xnu-8796, VINCE+ROSY, 4K pages) | 17.8 MB |
| `rosy-loader.Image` | arm64 boot shim, panel 1440x720 | 61 KB |
| `rosy-stock.dtb` | rosy device tree from the stock ROM | 258 KB |
| `rosy-boot.img` | Android boot image = loader + kernel + ADT + payload | 17.5 MB |
| `ios16-root.img` | iOS 16.7.16 iPhone X root, HFS+ 20 G | 20 G |
| `ios16-root.simg` | sparse image for fastboot | ~15 G |

Boot args used: `debug=0xc serial=3 cpus=1 keepsyms=1 rd=emmcroot0 emmcrw=1
rootrw=1 unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin
launchd_unsecure_cache=1 wdt=-1 sweetfb_native=1 vincetouch=0 vincekeys=0`

## Steps

1. Phone in fastboot (Power + Vol Down), USB attached.
2. `fastboot devices` -> 68497977d250.
3. DESTRUCTIVE, wipes all Android data on userdata:
   `fastboot -S 512M flash userdata ios16-root.simg`   (~10 min)
4. `fastboot boot rosy-boot.img`  (RAM only; nothing written)
5. Watch the screen. First boot is minutes on the Apple logo, then the lock screen.
   Touch/keys are disabled in this first image (vincetouch=0 vincekeys=0);
   the next build turns them on.
6. To read the kernel log: reboot to a recovery (OrangeFox/TWRP) and run
   `tools/sweet-log-pull.sh` (the kernel keeps a persistent log on the eMMC).

## If the phone drops to EDL (05c6:900e)

Hold Power ~15 s to force it off, then power on. Nothing was written by
`fastboot boot`.

## Known limits of this first image

- No Wi-Fi, Bluetooth, cellular, audio, camera, sensors, Apple ID, iCloud,
  App Store, activation. AMFI/sandbox relaxed.
- Touch and buttons disabled (vincetouch=0, vincekeys=0); CPU renderer only
  (the GPU path needs the Mesa/freedreno userland build).
- cpus=1 (one core); the other seven are enabled in a later build.
