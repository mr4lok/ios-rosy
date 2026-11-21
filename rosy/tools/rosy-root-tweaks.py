#!/usr/bin/env python3
"""rosy adaptation of upstream tools/sweet-root-tweaks.py.

Runs as an unprivileged user against an HFS+ image mounted rw with
uid=1000,gid=1000 (so ace can write). New files are staged in STAGE and installed
afterwards with `sudo rsync --chown`, because chown needs root.

  python3 rosy-root-tweaks.py MOUNTED_ROOT STAGE_DIR
"""
import glob, os, plistlib, shutil, sys

BUILD, VERSION = '20H392', '16.7.16'
MOBILE = 501
PREFS = 'private/var/mobile/Library/Preferences'


def load(path):
    with open(path, 'rb') as f:
        return plistlib.load(f)


def dump(path, data, fmt=plistlib.FMT_BINARY):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        plistlib.dump(data, f, fmt=fmt)


def stage_pref(stage, name, values):
    """Accumulate keys into STAGE/NAME.plist (installed later as 501:501 0600)."""
    path = os.path.join(stage, name + '.plist')
    data = load(path) if os.path.exists(path) else {}
    data.update(values)
    dump(path, data)
    print('stage pref', name, sorted(values))


def launchd(root):
    path = os.path.join(root, 'System/Library/xpc/launchd.plist')
    st = os.stat(path)
    plist = load(path)
    jobs = plist['LaunchDaemons']
    renamed = 0
    for job in jobs.values():
        if '_PanicOnCrash' in job:
            job['_PanicOnCrasX'] = job.pop('_PanicOnCrash')
            renamed += 1
    removed = [k for k, j in jobs.items() if j.get('Label') == 'com.apple.CommCenter']
    for k in removed:
        del jobs[k]
    with open(path, 'wb') as f:
        plistlib.dump(plist, f, fmt=plistlib.FMT_BINARY)
    os.chmod(path, st.st_mode & 0o7777)
    print(f'launchd.plist: {renamed} _PanicOnCrash renamed, {len(removed)} CommCenter jobs removed')


def containers(root):
    base = os.path.join(root, 'private/var/containers')
    for sub in ('Bundle', 'Data/System', 'Shared/SystemGroup', 'Temp'):
        d = os.path.join(base, sub)
        if not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
            print('mkdir', d)


def activation(root, stage):
    found = None
    for meta in glob.glob(os.path.join(root, 'private/var/containers/Data/System/*',
                                       '.com.apple.mobile_container_manager.metadata.plist')):
        try:
            if load(meta).get('MCMMetadataIdentifier') == 'com.apple.mobileactivationd':
                found = os.path.dirname(meta)
                break
        except Exception:
            pass
    if found is None:
        print('warning: no mobileactivationd container; skipped data ark')
        return
    d = os.path.join(found, 'Library/internal')
    os.makedirs(d, exist_ok=True)
    dump(os.path.join(d, 'data_ark.plist'), {
        '-ActivationState': 'Activated', '-BrickState': False,
        '-BuildVersion': BUILD, '-ProductVersion': VERSION,
        '-DataMigrationCompleted': True, '-PreSydroDataMigrationCompleted': True,
    })
    print('data ark', d)


def audio(root):
    src = os.path.join(root, 'Library/Audio/Plug-Ins/HAL/VirtualAudio.plugin')
    dst_dir = os.path.join(root, 'Library/Audio/Plug-Ins/HAL.disabled')
    if os.path.exists(src):
        os.makedirs(dst_dir, exist_ok=True)
        shutil.move(src, dst_dir)
        print('VirtualAudio.plugin disabled')
    for conf in glob.glob(os.path.join(root, 'System/Library/Frameworks/MediaToolbox.framework/*/SubServerConfiguration.plist')):
        st = os.stat(conf)
        data = load(conf)
        data['StartRecorderServer'] = False
        with open(conf, 'wb') as f:
            plistlib.dump(data, f, fmt=plistlib.FMT_XML)
        os.chmod(conf, st.st_mode & 0o7777)
        print('StartRecorderServer off', os.path.relpath(conf, root))


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    root, stage = sys.argv[1], sys.argv[2]
    os.makedirs(stage, exist_ok=True)
    launchd(root)
    containers(root)
    activation(root, stage)
    audio(root)
    # the migration skip is the one that matters for the boot UI
    stage_pref(stage, 'com.apple.migration', {
        'LastSystemVersion': BUILD,
        'DMUserDataDisposition': {'SyntheticDidUpgrade': False, 'buildVersion': BUILD}})
    # NOTES.md also names this domain; write both, harmless
    stage_pref(stage, 'com.apple.DataMigration', {
        'LastSystemVersion': BUILD,
        'DMUserDataDisposition': {'SyntheticDidUpgrade': False, 'buildVersion': BUILD}})
    stage_pref(stage, 'com.apple.springboard', {
        'BKNoWatchdogs': True,
        'FBLaunchWatchdogExceptions': {'com.apple.purplebuddy': 100.0},
        'MCForceShowCloudConfigurationUI': False})
    stage_pref(stage, 'com.apple.purplebuddy', {
        'SetupDone': True, 'SetupFinishedAllSteps': True, 'SetupVersion': 11,
        'daemonizeNeedsToRun': False})
    stage_pref(stage, 'com.apple.purplebuddy.notbackedup', {
        k: False for k in ('ShouldRunDiagnosticsMiniBuddy', 'ShouldRunHSA2MiniBuddy',
                           'ShouldRunKeychainSyncMiniBuddy', 'ShouldRunMesaMiniBuddy',
                           'ShouldRunPaymentMiniBuddy', 'ShouldRunStandardMiniBuddy',
                           'SilentICDPUpgrade')})
    stage_pref(stage, 'com.apple.managedconfiguration.notbackedup', {
        'LockdownActivationIndicatesCloudConfigurationAvailable': False})
    print('staged in', stage)


if __name__ == '__main__':
    main()
