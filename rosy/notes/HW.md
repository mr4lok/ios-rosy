# rosy hardware facts

Device: Xiaomi Redmi 5, codename **rosy**, model MDE1/MDI1/MDG1.
SoC: Qualcomm **MSM8953 / Snapdragon 450** (SDM450), 8x Cortex-A53 @ 1.8 GHz, Adreno 506.
RAM: 2 / 3 / 4 GB (this unit: 3 GB). Storage: 16 / 32 GB eMMC (this unit: 32 GB).
Panel: 5.7" IPS, **1440x720** (720x1440), 18:9.

## Verified shared MSM8953 values (from vince + daisy ports)

| item | value | source |
| --- | --- | --- |
| GIC | GICv2 (QGIC2), dist `0x0b000000`, cpu if `0x0b002000` | vince/daisy |
| timer | 19.2 MHz, virtual timer INTID 20 | vince/daisy |
| eMMC | SDHCI `0x07824900` (core `0x07824000`), eMMC 5.1 | vince/daisy |
| GPU | Adreno 506 (A5xx) | vince |
| CPU | 8x Cortex-A53 r0p4, ARMv8.0, **no 16 KiB granule** → 4 KiB pages | vince |
| PSCI | 1.0 over `smc`; cluster 0 MPIDR 0-3, cluster 1 0x100-0x103 | vince |

## rosy board values (measured from the live DTB, 2026-11-18)

| item | value | status |
| --- | --- | --- |
| panel DDIC | FocalTech **FT8613** (EBBG, 5.7" 720p) — `qcom,dsi-pref-prim-pan` | **verified** (DTB) |
| panel mode | 1440x720 DSI video, 60 Hz | **verified** (DTB) |
| framebuffer | `0x90001000`, size `0x13ff000` (`reserved-memory/splash_region`) | **verified** (DTB) |
| touch | `focaltech,fts` @ **0x38** on i2c-3 (BLSP1 QUP3 `0x78b7000`), reset GPIO64, irq GPIO65 | **verified** (DTB + live i2c) |
| touch coords | 1440x720 (`focaltech,display-coords = <0 0 0x2d0 0x5a0>`) | **verified** (DTB) |
| msm-id / board-id | `<0x152 0x0>` / `<0x1000b 0x1>` | **verified** (DTB) |
| RAM | MemTotal 2897148 kB (~2.76 GiB usable); carveouts start at `0x84a00000` | **verified** (meminfo + DTB) |
| RAM window | `0x10000000`-`0x84a00000` (loader RAM_LO/RAM_HI, same as vince) | **verified** (vince loader + rosy DTB) |
| CPU clock | 1.8 GHz | **verified** (SDM450) |
| fingerprint | Goodix GF3208 | **verified** (defconfig) |
| loader / DTB | `rosy-stock.dtb` extracted from the stock ROM `boot.img` | **done** |

## Sources

- lk2nd rosy DTS: `dts/sdm450-xiaomi-rosy.dts` (panel compatibles).
- LineageOS `android_kernel_xiaomi_rosy` `arch/arm/boot/dts/qcom/`:
  `msm8953_rosy.dtsi`, `sdm450_rosy.dtsi`, `msm8953-qrd-sku3_rosy.dtsi`,
  `dsi-panel-ft8613-ebbg-5p7-720p-video.dtsi`.
- vince port: `rebopawl-official/ios-rebivincek` (README, NOTES.md, vince/tools).
- daisy shim: `TODOCRACK/Daisy_XNU16` (eMMC/GIC/framebuffer addresses).
- ios-sweet / ios-topaz: the base XNU patch series and ADT/payload tools.

## Open questions for the phone dump

1. What does `/proc/iomem` call the LK splash buffer, and at what address?
2. Which RAM range does the kernel actually get (3 GB layout)?
3. Which I2C bus / address is the touch controller, and what is its name?
4. Does `fastboot boot` work on rosy's LK, or must we use the `recovery` slot?
5. Partition layout: `userdata` size and GPT index.
