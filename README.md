# ios-rosy — iOS 16 on the Xiaomi Redmi 5 (rosy, MSM8953)

An experimental port of Apple's XNU kernel plus the **unmodified iOS 16.7.16
iPhone X userland** to the **Xiaomi Redmi 5 (codename `rosy`, Qualcomm MSM8953 /
Snapdragon 450, 3 GB RAM, 32 GB eMMC)**.

It is a derivative of the [ios-rebivincek / ios-vince](https://github.com/rebopawl-official/ios-rebivincek)
port (Redmi 5 Plus, same SoC family), which itself builds on
[ios-topaz](https://github.com/MakrSas/ios-topaz) → [ios-sweet](https://github.com/dipa-studio/ios-sweet)
→ [HackiOS](https://github.com/oosexgang/hackios-xnu-kernel).

> **Status, 2026-11-21:** the iOS UI reaches the **lock screen** on the phone.
> Console handover (patches 1001-1003), window-server surfaces
> (`vinceplace=1 vincecache=1`), the unmodified iOS 16.7.16 userland, the
> data-migration skip and the accountsd ownership fix (patch 1006) all work.
> Recipe that gets there: kernel `xnu-kernel-rosy8` (= patches 1001-1006),
> image `rosy-boot31.img`, boot-args with **`cpus=8`** - on one core launchd
> starves and every extension dies on `extension check-in timeout`.
> Still open: **no touch driver** (rosy has a FocalTech FT8006M, while the tree
> only drives vince's Synaptics TD4310), so the screen cannot be swiped or
> unlocked. This is a bring-up project, not a ROM.
>
> Current working status: [`rosy/notes/live/HANDOFF.md`](rosy/notes/live/HANDOFF.md)
> (the old `rosy/notes/STATUS.txt` is stale). Off-laptop backup of the whole
> working tree, including the milestone boot image as a release asset:
> https://github.com/mr4lok/rosy-port

## Why rosy is close

| device | codename | SoC | state |
| --- | --- | --- | --- |
| Redmi 5 Plus | vince | MSM8953 / SDM625 | boots to SpringBoard, GPU via Mesa |
| Mi A2 Lite / Redmi 6 Pro | daisy / sakura | MSM8953 / SDM625 | shim + eMMC bring-up |
| **Redmi 5** | **rosy** | **MSM8953 / SDM450** | **this port** |

Shared MSM8953 facts: GICv2 at `0x0b000000`, 19.2 MHz timebase, virtual timer
INTID 20, eMMC SDHCI at `0x07824900`, Adreno 506, Cortex-A53 (ARMv8.0, no 16 KiB
granule → XNU is built with 4 KiB pages).

## rosy board facts (measured)

| item | value | source |
| --- | --- | --- |
| panel | FocalTech FT8613 (EBBG), 5.7" 1440x720 DSI video | stock DTB |
| framebuffer | `0x90001000` (LK splash, 20.9 MB) | stock DTB |
| touch | FocalTech `fts` @ `0x38` on i2c-3 (BLSP1 QUP3), reset GPIO64, irq GPIO65 | stock DTB |
| RAM window | `0x45000000`–`0x84a00000` | LK console + DTB carve-outs |
| PMIC | PMI8940 | DTB |

Full details in [`rosy/notes/HW.md`](rosy/notes/HW.md).

## Layout

```
xnu/patches/        XNU patch series; 0960 adds -DVINCE/-DROSY, 0968/0976 carry
                    the ROSY panel geometry (1440x720)
rosy/shim/          arm64 boot shim (loader), panel 1440x720, RAM_LO/HI 0x10000000/0x84a00000
rosy/tools/         the rosy port tooling:
                      rosy_facts.py     board facts (single source of truth)
                      mkadt_rosy.py     Apple Device Tree generator
                      rosy_pack.py      kernel + ADT -> Android boot image
                      mkiosroot-rosy.sh builds the iOS 16.7.16 HFS+ root from the IPSW
                      flash-and-boot.sh wipe userdata + flash + boot
                      dump-phone.sh     collect live device facts
                      rosy-root-tweaks.py  userland tweak set applied to the iOS root image
                      rosy-fix-dirs.py  image-side repair helpers (--owner / --accounts)
rosy/notes/         HW.md, RUNBOOK.md, STATUS.txt, DEVICE.txt, and
                    live/HANDOFF.md + live/*.txt (device dumps, flash log)
vince/, tools/, userland/   the upstream ios-vince port this derives from
```

## How it boots

```
Xiaomi LK (unlocked)
  -> fastboot boot rosy-boot.img          (RAM only; nothing is written)
     -> shim: console, finds the payload in the ramdisk, copies XNU
        -> XNU Mach-O + Apple Device Tree (iPhone X / D22AP identity) + boot-args
           -> eMMC driver -> HFS+ root in userdata
              -> launchd -> backboardd -> SpringBoard
```

## Build

1. **Kernel** — GitHub Actions `xnu` workflow on `macos-15` (Xcode 16's `iig`
   matches the xnu-8796 IORPC ABI). Env: `TOPAZ_4K=1`, `VINCE=1`, `ROSY=1`.
   The artifact is `kernel.development.sweet`.
2. **Loader** — `cd rosy/shim && bash build.sh out` (needs clang/ld.lld).
3. **iOS root** — download the iPhone X iOS 16.7.16 (20H392) IPSW, extract the
   `OS` / `Cryptex1,SystemOS` / `Cryptex1,AppOS` DMGs, then
   `rosy/tools/mkiosroot-rosy.sh OS.dmg SystemOS.dmg AppOS.dmg ios16-root.img 20G`.
   Then `img2simg ios16-root.img ios16-root.simg`.
4. **Pack + boot** — `rosy/tools/rosy_pack.py` then
   `rosy/tools/flash-and-boot.sh`.

## Not in git

Apple's IPSW, the disk images, the stock ROM, the built kernel, the boot image,
the iOS root image, the loader binary and the stock DTB are all excluded
(`.gitignore`): they are large, and the iOS/Apple and vendor blobs are not
redistributable. Build them yourself with the steps above.

## Safety

- The only destructive step is `fastboot flash userdata`, which erases all
  Android data. The bootloader, `boot`, `system`, `vendor`, `modem` and `persist`
  partitions are untouched, so Android is recoverable by reflashing the stock
  fastboot ROM (or via EDL/9008).
- A failed `fastboot boot` can drop the phone into Qualcomm EDL mode
  (`05c6:900e`); hold Power ~15 s to recover. Nothing is written.
- No Wi-Fi, Bluetooth, cellular, audio, camera, sensors, Secure Enclave, Apple
  ID, iCloud or App Store. AMFI/sandbox are relaxed. Not a daily driver.

## Credits

Built on Apple's open-source XNU/libpthread/HFS, [BearSSL](https://bearssl.org),
[blacktop/darwin-xnu-build](https://github.com/blacktop/darwin-xnu-build),
[apfs-fuse](https://github.com/sgan81/apfs-fuse), Qualcomm/Xiaomi's published
kernel sources, and the ios-vince / ios-topaz / ios-sweet / HackiOS ports.
XNU patches are under the Apple Public Source License like XNU itself. Not
affiliated with Apple, Xiaomi or Qualcomm.
