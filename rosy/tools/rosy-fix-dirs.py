#!/usr/bin/env python3
"""rosy: prepare the iOS root image with candidate fixes for the accountsd abort.

accountsd dies on ACDServerCreateDirectory('file:///var/mobile/Library/Accounts/')
-> NSFileWriteNoPermissionError, and its crash loop blocks
profiled -> MCProfileConnection -> SpringBoard/lsd (no home screen).

This script applies ONE of the image-side candidates (default: all of them, they
are independent and idempotent).  Run it against a *copy* of the image, then
fsck + img2simg + flash as usual.

    python3 tools/rosy-fix-dirs.py MOUNTED_ROOT [--owner] [--accounts]
                                        [--root-accountsd] [--mode]

ROOT CAUSE (2026-11-21): /private/var/mobile/Library is mode 0711 owned by
uid 1000 in the tweaked image (the original IPSW-derived image has 501:501).
The tweak mounted the volume rw with `uid=1000,gid=1000` so ace could write
root-owned files, and Linux hfsplus wrote those values back into the catalog
for every directory whose children were touched: /private/var, /private/var/
mobile/Library, /Library/Audio/Plug-Ins{,/HAL}, /System/Library/Frameworks/
MediaToolbox.framework and the /etc, /tmp, /var symlinks.  vnode_authorize_
posix() grants write on a 0711 directory to its owner only, so uid-501 daemons
(accountsd and friends) get EACCES creating their subdirectories.

  --owner           print (and, if sudo allows, run) the ownership repair for
                    the directories above; this is the real fix for the blocker
  --accounts        pre-create /private/var/mobile/Library/Accounts (501:501 0755)
  --root-accountsd  set UserName=root for com.apple.accountsd in launchd.plist
                    (vfs_context_issuser() short-circuits the POSIX check)
  --mode            also make /private/var/mobile and .../Library 0777
                    (strongest image-side hammer; keeps owner 501:501)

Nothing here is a substitute for the kernel-side fix (xnu/patches/1006, which
makes hfs_vnop_getattr report the caller as the owner); these are the image-side
candidates so they can be tested without another round of editing.
"""
import argparse, os, plistlib, shutil, subprocess, sys, tempfile

MOBILE = 501
PREFS = 'private/var/mobile/Library/Preferences'
LAUNCHD = 'System/Library/xpc/launchd.plist'

# directories whose catalog owner the tweak clobbered (see module docstring):
# relpath, uid, gid
OWNER_REPAIR = (
    ('private/var', 0, 0),
    ('private/var/mobile/Library', MOBILE, MOBILE),
)


def owner(root):
    """Restore the catalog ownership the rw mount with uid=1000 wrote back."""
    for rel, uid, gid in OWNER_REPAIR:
        p = os.path.join(root, rel)
        if not os.path.isdir(p):
            print('missing', p)
            continue
        r = subprocess.run(['sudo', '-n', 'chown', '%d:%d' % (uid, gid), p],
                           capture_output=True, text=True)
        if r.returncode == 0:
            print('chown %d:%d %s' % (uid, gid, p))
        else:
            print('needs root - run: sudo chown %d:%d %s' % (uid, gid, p))


def accounts(root):
    """Pre-create .../Library/Accounts owned by mobile.

    A plain os.makedirs here would leave the new directory owned by the
    invoking user (1000), and mode 0755 would then keep accountsd (uid 501)
    out of it -- the exact bug this script is working around.  So stage an
    empty directory and let `sudo rsync --chown` install it as 501:501.
    """
    d = os.path.join(root, 'private/var/mobile/Library/Accounts')
    parent = os.path.dirname(d)
    if os.path.isdir(d):
        print('exists', d)
        return
    stage = tempfile.mkdtemp(prefix='rosy-accounts-')
    try:
        os.mkdir(os.path.join(stage, 'Accounts'))
        os.chmod(os.path.join(stage, 'Accounts'), 0o755)
        r = subprocess.run(
            ['sudo', '-n', 'rsync', '-a', '--chown=%d:%d' % (MOBILE, MOBILE),
             os.path.join(stage, 'Accounts'), parent + '/'],
            capture_output=True, text=True)
        if r.returncode == 0:
            print('created %s (501:501 0755)' % d)
            return
        print('rsync failed (%s); falling back to a local mkdir' % r.stderr.strip())
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    print('created %s owned by uid %d -- run --owner afterwards' % (d, os.getuid()))


def root_accountsd(root):
    p = os.path.join(root, LAUNCHD)
    st = os.stat(p)
    pl = plistlib.load(open(p, 'rb'))
    jobs = pl['LaunchDaemons']
    hit = 0
    for k, j in jobs.items():
        if j.get('Label') == 'com.apple.accountsd':
            j['UserName'] = 'root'
            hit += 1
    plistlib.dump(pl, open(p, 'wb'), fmt=plistlib.FMT_BINARY)
    os.chmod(p, st.st_mode & 0o7777)
    print(f'accountsd UserName=root on {hit} job(s)')


def mode_hammer(root):
    for rel in ('private/var/mobile', 'private/var/mobile/Library'):
        p = os.path.join(root, rel)
        if os.path.isdir(p):
            os.chmod(p, 0o777)
            print('chmod 0777', p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root')
    ap.add_argument('--owner', action='store_true')
    ap.add_argument('--accounts', action='store_true')
    ap.add_argument('--root-accountsd', action='store_true')
    ap.add_argument('--mode', action='store_true')
    a = ap.parse_args()
    if not (a.owner or a.accounts or a.root_accountsd or a.mode):
        a.owner = a.accounts = a.root_accountsd = a.mode = True   # default: all
    if a.owner:
        owner(a.root)
    if a.accounts:
        accounts(a.root)
    if a.root_accountsd:
        root_accountsd(a.root)
    if a.mode:
        mode_hammer(a.root)


if __name__ == '__main__':
    main()
