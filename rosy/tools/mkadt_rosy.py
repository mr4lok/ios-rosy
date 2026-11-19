#!/usr/bin/env python3
"""Apple Device Tree (ADT) for the Xiaomi Redmi 5 (rosy, MSM8953).

Derivative of ios-rebivincek/vince/tools/mkadt_vince.py (MIT), itself derived from
ios-sweet/tools/mkadt.py. Board values come from tools/rosy_facts.py; anything
marked UNVERIFIED there is a vince placeholder and must be replaced with live
measurements (tools/dump-phone.sh -> notes/rosy-live.json).

  mkadt_rosy.py OUT.adt [--dump]
"""
import os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import adt                                              # noqa: E402
import rosy_facts as F                                  # noqa: E402
from mkadt import node, u32, u64, cstr, d22ap_product, BOOT_MANIFEST_HASH  # noqa: E402

PHYS_BASE = F.get('PHYS_BASE')
MEM_SIZE = F.get('MEM_SIZE')
SOC_BASE = F.get('SOC_BASE')
GICD, GICD_SIZE = F.get('GICD'), F.get('GICD_SIZE')
GICC, GICC_SIZE = F.get('GICC'), F.get('GICC_SIZE')
TIMEBASE = F.get('TIMEBASE')
VTIMER_INTID = F.get('VTIMER_INTID')
FB = F.get('FB')
FB_SIZE = F.fb_size()
FB_W, FB_H, FB_STRIDE = F.get('FB_W'), F.get('FB_H'), F.get('FB_STRIDE')
FB_CANVAS_W, FB_CANVAS_H = F.get('FB_CANVAS_W'), F.get('FB_CANVAS_H')
ECID = F.get('ECID')
CPU_CLOCK = F.get('CPU_CLOCK')


def build(seed=None):
    seed = seed if seed is not None else os.urandom(64)
    phandle = iter(range(1, 1000))
    ph = lambda: ('AAPL,phandle', u32(next(phandle)))

    chosen = node('chosen', [
        ph(),
        ('dram-base', u64(PHYS_BASE)),
        ('dram-size', u64(MEM_SIZE)),
        ('random-seed', seed),
        ('debug-enabled', u32(1)),
        ('firmware-version', cstr('rosy-loader')),
        ('system-firmware-version', cstr('rosy-loader')),
        ('boot-manifest-hash', BOOT_MANIFEST_HASH),
        ('crypto-hash-method', cstr('sha2-384')),
        ('display-scale', u32(3)),
        ('unique-chip-id', struct.pack('<Q', ECID)),
        ('chip-id', u32(0x8015)),                       # Apple A11 (iPhone X)
        ('certificate-production-status', u32(0)),
        ('effective-production-status-ap', u32(0)),
        ('certificate-security-mode', u32(1)),
        ('effective-security-mode-sep', u32(1)),
    ], [node('memory-map', [ph()]),
        node('asmb', [ph(), ('lp-sip0', u64(0x6f)), ('lp-sip1', u32(1))])])

    # Eight Cortex-A53: cluster 0 = MPIDR 0x0-0x3, cluster 1 = 0x100-0x103.
    cpu_nodes = []
    for core in range(8):
        mpidr = (0x100 if core >= 4 else 0) | (core & 3)
        cpu_nodes.append(node(f'cpu{core}', [
            ph(),
            ('device_type', cstr('cpu')),
            ('compatible', cstr('qcom,kryo260') + cstr('qcom,kryo470') + cstr('ARM,v8')),
            ('reg', u32(mpidr)),
            ('cpu-id', u32(core)),
            ('cluster-id', u32(0)),
            ('cluster-type', u32(0)),                  # CLUSTER_TYPE_SMP
            ('die-cluster-id', u32(0)),
            ('cluster-core-id', u32(core)),
            ('l2-cache-id', u32(core >> 2)),
            ('l2-cache-size', u32(0x80000)),
            ('l3-cache-id', u32(0)),
            ('state', cstr('running' if core == 0 else 'stopped')),
            ('timebase-frequency', u32(TIMEBASE)),
            ('clock-frequency', u32(CPU_CLOCK)),
            ('bus-frequency', u32(100000000)),
            ('memory-frequency', u32(933000000)),
            ('peripheral-frequency', u32(TIMEBASE)),
            ('fixed-frequency', u32(TIMEBASE)),
        ]))
    cpus = node('cpus', [ph(), ('#address-cells', u32(1)), ('#size-cells', u32(0))], cpu_nodes)

    gic = node('gic', [
        ph(),
        ('compatible', cstr('arm,gic-v2') + cstr('qcom,msm-qgic2')),
        ('interrupt-controller', b''),
        ('virtual-timer-intid', u32(VTIMER_INTID)),
        ('reg', u64(GICD - SOC_BASE, GICD_SIZE, GICC - SOC_BASE, GICC_SIZE)),
    ])
    arm_io = node('arm-io', [
        ph(),
        ('device_type', cstr('sweet-io')),
        ('compatible', cstr('sweet-io') + cstr('arm-io')),
        ('#address-cells', u32(2)),
        ('#size-cells', u32(2)),
        ('ranges', u64(0, SOC_BASE, 0x100000000 - SOC_BASE)),
    ], [gic,
        # No hardware: watchdogd checks IODeviceTree:/arm-io/wdt for no-pmu.
        node('wdt', [ph(), ('no-pmu', u32(1))]),
        # Main display. IOMobileFramebuffer.framework counts /arm-io children
        # whose device_type is "display-subsystem" and reads the canvas size
        # from the node; the kernel's AppleCLCD matches "sweet,display".
        # Without this SpringBoard has no CADisplay and crash-loops.
        node('disp0', [
            ph(),
            ('device_type', cstr('display-subsystem')),
            ('compatible', cstr('sweet,display')),
            ('canvas-width', u32(FB_CANVAS_W)),
            ('canvas-height', u32(FB_CANVAS_H)),
        ]),
        # launchd only starts wifid when the tree has a "wlan" node.
        node('wlan', [
            ph(),
            ('device_type', cstr('wlan')),
            ('compatible', cstr('topaz,wcn3988')),
        ])])

    fbcon = node('sweet-fbcon', [
        ph(),
        ('reg', u64(FB, FB_SIZE)),
        ('width', u32(FB_W)),
        ('height', u32(FB_H)),
        ('stride', u32(FB_STRIDE)),
    ])

    defaults = node('defaults', [ph(), ('no-effaceable-storage', u32(1))])
    buttons = node('buttons', [
        ph(),
        ('button-names', cstr('volup') + cstr('voldown') + cstr('hold')),
        ('home-button-type', u32(2)),
        ('opposed-power-vol-buttons', u32(1)),
    ])

    product_props = d22ap_product()
    if product_props:
        product_props = [(k, cstr('sRGB') if k == 'artwork-display-gamut' else v)
                         for k, v in product_props]
    product = [node('product', [ph()] + product_props)] if product_props else []

    return node('device-tree', [
        ph(),
        ('compatible', cstr('D22AP') + cstr('iPhone10,3') + cstr('xiaomi,rosy') +
         cstr('xiaomi,sweet') + cstr('qcom,msm8953') + cstr('AppleARM')),
        ('model', cstr('iPhone10,3')),
        ('target-type', cstr('D22')),
        ('target-sub-type', cstr('D22AP')),
        ('manufacturer', cstr('Apple Inc.')),
        ('#address-cells', u32(2)),
        ('#size-cells', u32(2)),
    ], [chosen, defaults, cpus, arm_io, fbcon, buttons] + product)


if __name__ == '__main__':
    out = sys.argv[1]
    blob = adt.serialize(build())
    open(out, 'wb').write(blob)
    if '--dump' in sys.argv:
        adt.dump(adt.parse(blob)[0])
    print(f'{out}: {len(blob)} bytes; unverified: {", ".join(F.UNVERIFIED) or "none"}',
          file=sys.stderr)
