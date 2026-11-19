#!/usr/bin/env python3
"""Turn notes/live/* into notes/rosy-live.json for tools/rosy_facts.py.

Proposes values from the collected dumps and prints them. Use --write to save;
review the proposal first (the RAM/splash choices are heuristics).

  python3 tools/parse-live.py [--write]
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
LIVE = os.path.join(ROOT, 'notes', 'live')
OUT = os.path.join(ROOT, 'notes', 'rosy-live.json')


def read(name):
    p = os.path.join(LIVE, name)
    if not os.path.exists(p):
        return ''
    with open(p, 'rb') as f:
        return f.read().decode('utf-8', 'replace')


def meminfo():
    txt = read('meminfo.txt')
    m = re.search(r'MemTotal:\s+(\d+)\s+kB', txt)
    return int(m.group(1)) if m else None


def ram_ranges():
    """All 'System RAM' ranges from /proc/iomem, as (base, top, size)."""
    out = []
    for line in read('iomem.txt').splitlines():
        m = re.match(r'\s*([0-9a-f]+)-([0-9a-f]+)\s*:\s*(.*)', line)
        if not m:
            continue
        base, top, name = int(m.group(1), 16), int(m.group(2), 16), m.group(3).strip()
        if name.lower() == 'system ram':
            out.append((base, top, top - base + 1))
    return out


def splash():
    """Look for the contiguous splash region in /proc/iomem."""
    for line in read('iomem.txt').splitlines():
        m = re.match(r'\s*([0-9a-f]+)-([0-9a-f]+)\s*:\s*(.*)', line)
        if not m:
            continue
        name = m.group(3).strip().lower()
        if 'splash' in name or 'continuous' in name:
            return int(m.group(1), 16), int(m.group(2), 16), name
    return None


def fb_size():
    try:
        w, h = read('fb0-size.txt').replace(',', ' ').split()[:2]
        bpp = int(read('fb0-bpp.txt').strip() or '32')
        return int(w), int(h), bpp
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()

    total_kb = meminfo()
    ranges = ram_ranges()
    sp = splash()
    fbs = fb_size()

    print(f'MemTotal:            {total_kb} kB' if total_kb else 'MemTotal:            (missing meminfo.txt)')
    print('System RAM ranges from /proc/iomem:')
    for base, top, size in ranges:
        print(f'  {base:#010x}-{top:#010x}  {size / 2**20:8.1f} MiB')
    if sp:
        print(f'splash region:       {sp[0]:#010x}-{sp[1]:#010x}  ({sp[2]})')
    else:
        print('splash region:       not found in iomem')
    if fbs:
        print(f'fb0:                 {fbs[0]}x{fbs[1]} @ {fbs[2]} bpp')

    proposal = {}
    # Heuristic: use the largest RAM range below 4 GiB as kernel RAM.
    if ranges:
        base, top, size = max(ranges, key=lambda r: r[2])
        if base < 0x100000000:
            proposal['PHYS_BASE'] = base
            proposal['MEM_SIZE'] = size
    if sp:
        proposal['FB'] = sp[0]
    if fbs and fbs[2] == 24:
        proposal['FB_W'], proposal['FB_H'] = fbs[0], fbs[1]
        proposal['FB_STRIDE'] = fbs[0] * 3

    print('\nproposed rosy-live.json:')
    print(json.dumps(proposal, indent=2))
    if a.write:
        with open(OUT, 'w') as f:
            json.dump(proposal, f, indent=2)
            f.write('\n')
        print(f'wrote {OUT}')
    else:
        print('(dry run; pass --write to save)')


if __name__ == '__main__':
    main()
