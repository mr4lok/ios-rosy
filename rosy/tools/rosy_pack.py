#!/usr/bin/env python3
"""Pack the rosy XNU kernel + ADT into an Android boot image for `fastboot boot`.

Derivative of ios-rebivincek/vince/tools/vince_pack.py (MIT).

  python3 tools/rosy_pack.py KERNEL OUT.img --loader loader.Image --dtb stock.dtb \
      [--cmdline "..."] [--ramdisk ROOT.img]

The loader (arm64 shim) and the phone's own stock DTB are device inputs and are
not in git. KERNEL is the Mach-O from the `xnu-kernel` CI artifact
(kernel.development.sweet). Nothing is flashed by this script.
"""
import argparse, gzip, hashlib, os, struct, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import adt                                              # noqa: E402
import rosy_facts as F                                  # noqa: E402
import mkadt_rosy                                       # noqa: E402
import mkpayload                                        # noqa: E402

PAGE = 2048
# UNVERIFIED: vince LK load addresses. Measure on rosy with tools/dump-phone.sh.
KERNEL_ADDR = 0x80008000
RAMDISK_ADDR = 0x81000000
SECOND_ADDR = 0x80f00000
TAGS_ADDR = 0x80000100
LK_RAMDISK_PA = 0x13600000
OS_VERSION = 0x2000019B
CMDLINE = (b"androidboot.hardware=qcom msm_rtb.filter=0x237 ehci-hcd.park=3 "
           b"lpm_levels.sleep_disabled=1 androidboot.bootdevice=7824900.sdhci "
           b"loop.max_part=7 androidboot.init_fatal_reboot_target=recovery "
           b"printk.devkmsg=on console=ttyMSM0,115200,n8 androidboot.console=ttyMSM0 "
           b"earlycon=msm_serial_dm,0x78af000 ")
DEFAULT_CMDLINE = ('debug=0xc serial=3 cpus=1 keepsyms=1 rd=emmcroot0 emmcrw=1 rootrw=1 '
                   'unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin '
                   'launchd_unsecure_cache=1 wdt=-1')


def pad(b):
    return b + b"\0" * (-len(b) % PAGE)


def make_boot_img(loader_image, dtb, ramdisk):
    kz = gzip.compress(loader_image, 9, mtime=0) + dtb
    h = b"ANDROID!"
    h += struct.pack("<10I", len(kz), KERNEL_ADDR, len(ramdisk), RAMDISK_ADDR, 0,
                     SECOND_ADDR, TAGS_ADDR, PAGE, 0, OS_VERSION)
    h += b"rosy-xnu".ljust(16, b"\0")
    h += CMDLINE.ljust(512, b"\0")
    sha = hashlib.sha1()
    for blob in (kz, ramdisk, b""):
        sha.update(blob)
        sha.update(struct.pack("<I", len(blob)))
    h += sha.digest().ljust(32, b"\0")
    h += b"\0" * 1024
    assert len(h) == 1632, len(h)
    return pad(h) + pad(kz) + pad(ramdisk)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('kernel')
    ap.add_argument('out')
    ap.add_argument('--cmdline', default=DEFAULT_CMDLINE)
    ap.add_argument('--ramdisk', help='root image for md0 (boot with rd=md0), optional')
    ap.add_argument('--loader', required=True, help='arm64 shim Image (build/shim/loader.Image)')
    ap.add_argument('--dtb', required=True, help='stock DTB appended to the loader')
    a = ap.parse_args()

    loader = open(a.loader, 'rb').read()
    assert loader[56:60] == b'ARM\x64', 'loader is not an arm64 Image'
    dtb = open(a.dtb, 'rb').read()
    assert dtb[:4] == b'\xd0\x0d\xfe\xed', 'dtb is not a flattened device tree'

    with tempfile.TemporaryDirectory() as td:
        adt_path = os.path.join(td, 'rosy.adt')
        open(adt_path, 'wb').write(adt.serialize(mkadt_rosy.build()))
        payload, info = mkpayload.build(a.kernel, adt_path, a.cmdline, a.ramdisk)

    phys_base, mem_size = mkadt_rosy.PHYS_BASE, mkadt_rosy.MEM_SIZE
    limit = phys_base - LK_RAMDISK_PA
    if len(payload) > limit:
        sys.exit(f'payload is {len(payload):#x} bytes, but only {limit:#x} fit between the '
                 f'ramdisk address {LK_RAMDISK_PA:#x} and the kernel RAM at {phys_base:#x}')
    open(a.out, 'wb').write(make_boot_img(loader, dtb, payload))
    print(f"payload   {len(payload):#x} bytes at ramdisk {LK_RAMDISK_PA:#x}..{LK_RAMDISK_PA + len(payload):#x}")
    print(f"kernel RAM {phys_base:#x}..{phys_base + mem_size:#x}  virt_base {info['virt_base']}  entry {info['entry']}")
    print(f"cmdline   {a.cmdline}")
    print(f"wrote     {a.out} ({os.path.getsize(a.out)} bytes), sha256 "
          f"{hashlib.sha256(open(a.out, 'rb').read()).hexdigest()}")
    print("unverified facts: " + (", ".join(F.UNVERIFIED) or "none"))
    print("next:     fastboot boot " + a.out)


if __name__ == '__main__':
    main()
