"""Hardware facts for the Xiaomi Redmi 5 (rosy, Qualcomm MSM8953 / Snapdragon 450).

Sources:
  * MSM8953 shared values (GICv2, architected timer, SDHCI eMMC) measured on the
    Redmi 5 Plus (vince) and Mi A2 Lite (daisy) XNU ports.
  * rosy panel from the lk2nd device tree: FocalTech FT8613 / FT8006M, 5.7" 720p
    (1440x720) DSI video mode.
  * rosy SoC / CPU / RAM / storage from the LineageOS device tree.

Anything tagged UNVERIFIED is a placeholder carried over from the vince port.
Replace it with live measurements: run tools/dump-phone.sh (writes
notes/rosy-live.json), then drop the UNVERIFIED tags here.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OVERRIDE = os.path.normpath(os.path.join(HERE, '..', 'notes', 'rosy-live.json'))

# --- shared MSM8953 (verified on vince + daisy) ---
_SOC = dict(
    GICD=0x0b000000, GICD_SIZE=0x1000,      # QGIC2 distributor
    GICC=0x0b002000, GICC_SIZE=0x1000,      # QGIC2 CPU interface
    TIMEBASE=19200000,                      # 19.2 MHz XO
    VTIMER_INTID=20,                        # virtual timer PPI on this SoC
    SDHCI=0x07824900, SDHCI_SIZE=0x1000,    # eMMC 5.1 host controller
    SOC_BASE=0x01000000,                    # /arm-io child offset base
)

# --- rosy board ---
_BOARD = dict(
    ECID=0x524F535900000001,                # 'ROSY' + 1, synthetic
    # VERIFIED on the live DTB (reserved-memory/splash_region@0x90001000, 0x13ff000):
    FB=0x90001000,                          # LK splash buffer left scanned out
    # VERIFIED on the live DTB (mdss_dsi_ft8613_ebbg_5p7_720p_video is the primary
    # panel; touch focaltech,display-coords = <0 0 0x2d0 0x5a0> = 1440x720):
    FB_W=1440, FB_H=720, FB_STRIDE=1440 * 3,   # 24 bpp packed B,G,R
    PANEL='ft8613_ebbg 5.7in 720p',
    # VERIFIED on the live DTB (focaltech@38, focaltech,fts, BLSP1 QUP3 / i2c-3):
    TOUCH_IC='FocalTech FTS (FT8006M family)',
    TOUCH_ADDR=0x38, TOUCH_BUS='i2c-3 (BLSP1 QUP3 @0x78b7000)',
    TOUCH_RESET_GPIO=64, TOUCH_IRQ_GPIO=65,
    FINGERPRINT='Goodix GF3208',
    CPU_CLOCK=1800000000,                   # SDM450 max 1.8 GHz
    # rosy's LK loads its image/DTB/ramdisk at 0x40080000 / 0x43400000 /
    # 0x43600000 (seen on the loader console), so the kernel RAM must sit above
    # them and below the TZ/modem carve-outs at 0x84a00000 (DTB reserved-memory).
    PHYS_BASE=0x45000000,
    MEM_SIZE=0x3fa00000,                    # 0x45000000 - 0x84a00000 (~1.0 GiB)
)

_FACTS = {}
_FACTS.update(_SOC)
_FACTS.update(_BOARD)

# Live measurements win over everything above.
if os.path.exists(OVERRIDE):
    with open(OVERRIDE) as f:
        _FACTS.update(json.load(f))

# PHYS_BASE / MEM_SIZE are carried from the vince port (same MSM8953 low-RAM map).
UNVERIFIED = [k for k in ('PHYS_BASE', 'MEM_SIZE') if k in _FACTS]


def get(key, default=None):
    return _FACTS.get(key, default)


def fb_size():
    return _FACTS['FB_W'] * _FACTS['FB_H'] * 3


if __name__ == '__main__':
    for k in sorted(_FACTS):
        v = _FACTS[k]
        print(f'{k:14} {v:#x}' if isinstance(v, int) else f'{k:14} {v}')
    print('unverified:', ', '.join(UNVERIFIED) or 'none')
