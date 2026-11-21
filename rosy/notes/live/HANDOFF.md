# rosy-port handoff (2026-11-20, night)

## Phone
- Xiaomi Redmi 5 (rosy), MSM8953, 3 GB / 32 GB, bootloader unlocked, serial 68497977d250.
- `userdata` (mmcblk0p49) holds the iOS 16.7.16 HFS+ root (flashed 2026-11-19 08:11, FLASH_EXIT=0).
  Android data on it is gone. boot/system/vendor/modem/persist/recovery untouched -> reflash the
  stock fastboot ROM (`upstream/rosy_V11.0.2.0.ODAMIXM.tgz`) to get Android back.
- Every test since has been `fastboot boot` (RAM only). Nothing else was ever written.
- Phone is USB-attached, currently in TWRP recovery.

## What works (verified from kernel logs)
- Kernel + iOS userland boot. launchd runs the real iOS 16.7.16 daemons, SpringBoard stays up.
- GPU pool fix: boot-args `vinceplace=1 vincecache=1` + ADT canvas 1125x2436 put the window
  server's surfaces in the kernel's 192 MiB pool at 0x73c00000 (SweetSurface.cpp vince path).
  Result: `SWEET SURF: backboardd create ... -> 0x0`, **zero** `vm_page_find_contiguous` failures.
- `sweetfb_noconsole=1` mutes the kernel text console.
- Known-good image so far: `upstream/rosy-boot18.img`
  (dram 0x45000000 + 0x3b000000, canvas 1125x2436, fbcon 720x1440,
   cmdline: ... wdt=-1 vinceplace=1 vincecache=1 sweetfb_direct=0 sweetfb_noconsole=1 ...)

## The blocker, and the fix in flight
The panel never leaves the boot logo + progress bar. Root cause:
- patch 0046 called `PE_initialize_console(&video, kPEDisableScreen)` on the first GUI swap.
  That is what pauses the *graphics* console and hands the panel to iOS.
- It panicked: `kPEDisableScreen` -> `switch_to_serial_console()` writes `cons_ops_index`,
  which is `SECURITY_READ_ONLY_LATE`.
- patch 0067 replaced it with `sweet_console_muted = 1`, which only stops console **text**.
  The graphics console (logo + progress meter) keeps the panel forever.
- The meter's increments shrink 10000 -> 64 per tick with position = counter>>13, so the last
  pixels take tens of minutes; the window server's swap counters freeze at the same display
  time (~FB t 3300-3530) in every boot. That is the "stuck bar".

Fix: `xnu/patches/1001-rosy-console-handover.patch` (commit 6120eb5) makes `cons_ops_index`
writable and calls the handover again. Kernel build = GH run 44560920098 on mr4lok/ios-rosy.

## Progress 2026-11-20 night
- boot19 (`ignition_level=3`) failed the preboot stage ("failed to lookup preboot: 25", no
  preboot device). Level 1 is correct. Still stuck on logo + bar.
- Patch 1001 committed (6120eb5) and the kernel built clean: GH run 44560920098 (success).
  Artifact `xnu-kernel` id 14550667601.
- sudo whitelist restored by the user, so mounting/extracting the iOS root is possible again.

## boot20 (the handover test) - BOOTED 2026-11-19 ~22:27
- kernel: `upstream/xnu-kernel-rosy4/kernel.development.sweet` (sha256 b5174cba1e35...)
  from GH run 44560920098's artifact `xnu-kernel`; verified in the `xnu-buildtree` artifact
  that the built tree has `cons_ops_index` without SECURITY_READ_ONLY_LATE (serial_console.c:138)
  and the handover call (SweetFramebuffer.cpp:1928-1933).
- image: `upstream/rosy-boot20.img` sha256 f4d4ccfe2217bd6b4bcf0eb0cf2ab449dc8bd3896977f834762f52e6e9500205
  dram 0x45000000+0x3b000000, canvas 1125x2436, fbcon 720x1440,
  cmdline = boot18's (ignition_level=1, vinceplace=1, vincecache=1, sweetfb_direct=0,
  sweetfb_noconsole=1).
- It is running now. To read the result: power-cycle to fastboot (Power ~15 s, then
  Power + Vol Down), then `fastboot boot upstream/twrp.img`, then
  `bash upstream/ios-rebivincek/tools/sweet-log-pull.sh /tmp/sweetlog11.txt`.
- Verdict line to grep: `kPEDisableScreen` (PE_initialize_console kprintf's it). Its presence
  proves the handover ran. Then check whether the logo/bar are gone from the panel.

## boot20 result (log pulled 22:58)
- Pool works, SpringBoard runs, no panic, GUI still drawing (82k swaps at FB t=1490).
- **`kPEDisableScreen` is absent from the log** -> the handover never executed, and the bar
  still climbs to ~99%. So 1001 was in the wrong place.
- Why: 1001 put the call in the copy path of `AppleCLCD::present()`, which sits *after* the
  `vinceZeroPresent()` / `directPresent()` early returns; those set `fConsolePaused` themselves,
  so the first frame takes an early return and the handover block is never reached.
  (`SWEET FB: swap` lines are present, so the copy path does run - just not its first block.)

## boot21 (fix for the above)
- `xnu/patches/1002-rosy-console-handover-early.patch` (commit 317a34b) moves the handover to the
  top of `present()` so it runs on the first frame either way.
- Kernel build: GH run 44578299292. Then repack as `upstream/rosy-boot21.img` (same settings as
  boot20) and boot it.
- Verdict: `kPEDisableScreen` present in the log = the handover ran. Then look at the panel.

## boot21 - BOOTED 2026-11-19 ~23:30 (the one to check in the morning)
- kernel `upstream/xnu-kernel-rosy5/kernel.development.sweet` sha256 5c36ee94c281a43c...
  (from GH run 44578299292, which carries patches 1001 + 1002).
- image `upstream/rosy-boot21.img` sha256 749584b8dabb690751ac734d34a300de70cab11817696d44adbabc4787068956
  settings identical to boot20 (dram 0x45000000+0x3b000000, canvas 1125x2436, fbcon 720x1440,
  ignition_level=1, vinceplace=1, vincecache=1, sweetfb_direct=0, sweetfb_noconsole=1).
- It is running now. Morning steps: put it in fastboot (Power ~15 s, then Power + Vol Down),
  then `fastboot boot upstream/twrp.img`, then
  `bash upstream/ios-rebivincek/tools/sweet-log-pull.sh /tmp/sweetlog12.txt`.
- Verdict: grep `kPEDisableScreen`. Present -> the handover finally ran; then look at the panel
  (bar/logo gone = win; bar frozen at a low percent = kernel bar stopped, logo is userland).

## boot21 result (log pulled 10:34)
- Still stuck: bar filled to ~99% and stopped. `kPEDisableScreen` is still absent - but that is
  *not* a valid signal: `PE_initialize_console` prints it with kprintf *after*
  switch_to_serial_console(), so it goes to the serial console and never reaches the sweet log.
- boot21 ran ~9.3 h, GUI drew ~219k swaps, no panic.

## boot22 (unambiguous instrumented build)
- `xnu/patches/1003-rosy-console-handover-log.patch` adds two IOLog lines:
  "SWEET FB: first present, fConsolePaused=%d" (top of present()) and
  "SWEET FB: first GUI frame -> console handover" (inside the handover block).
- GH run 44678808965. Kernel -> `upstream/xnu-kernel-rosy6/`, image -> `upstream/rosy-boot22.img`.
- Reading the log:
    both lines present                     -> the block ran; the bar/logo must be userland
    only "first present" with paused=1     -> something set fConsolePaused earlier; find it
    only "first present" with paused=0     -> the handover ran; look at the panel
    neither line                           -> present() is not reached the way we think

## boot22 result (log pulled 11:20) - THE KERNEL SIDE IS DONE
- Both instrumented lines are in the log, at the first GUI frame (backboardd's first swap):
      SWEET FB: first GUI frame -> console handover
      SWEET FB: first present, fConsolePaused=1
  So patch 1002's placement is right and the kernel console handover works.
- `kPEDisableScreen` is still absent, correctly: that kprintf runs after
  switch_to_serial_console() and goes to serial, never to the sweet log.

## What the screen actually is (from the iOS root, mounted read-only)
- `upstream/ios16-root.img` mounts with `sudo mount -t hfsplus -o loop,ro,force`.
- backboardd (`/usr/libexec/backboardd`) is the boot UI:
    BKDisplayRenderOverlayAppleLogo          -> the Apple logo overlay
    PUIProgressWindow (ProgressUI.framework)  -> progress window
    "Successfully applied kernel progress indicator" / kern.progressoptions
- The BAR is the KERNEL's progress meter: backboardd drives it through `kern.progressmeter`
  (sysctl -> vc_set_progressmeter), and `kern.progressoptions` sets style/position.
  `kPEDisableScreen` only pauses `vc_progress_enable` (the boot progress crawl); it does NOT
  clear `vc_progressmeter_enable`, which is what gates `internal_set_progressmeter`'s drawing.
  That is why the bar kept climbing to 99% after the handover.
- Dismissal on real iOS is userland's job: `IOPlatformExpert::setConsoleInfo(op)` ->
  `PE_initialize_console(..., kPEReleaseScreen)` (video_console.c:3028) is what calls
  `vc_enable_progressmeter(FALSE)`. Nobody is doing it here.

## Where boot got to (boot22 log)
- launchd reached "[Event: boot] Early boot complete. Continuing system boot."
- SpringBoard is running ("SpringBoard boosted (#1)"), GUI drew ~16.6k swaps.
- Lots of extension check-in timeouts; "Too many corpses being created".

## Userland findings (iOS root mounted ro at ~/.hermes/cache/scratch/iosroot)
- The BAR is the kernel's own progress meter. backboardd drives it via `kern.progressmeter`
  (sysctl -> vc_set_progressmeter) and sets style/position via `kern.progressoptions`
  ("Successfully applied kernel progress indicator" in backboardd). kPEDisableScreen ->
  gc_pause(TRUE) clears vc_progress_enable and gc_enabled but NOT vc_progressmeter_enable,
  which is the only gate on internal_set_progressmeter's drawing. Hence the bar survives.
- The Apple logo is USERLAND: backboardd's BKDisplayRenderOverlayAppleLogo. The kernel ships
  pexpert/pexpert/AppleBoot.h (gAppleBootPict, 128x128) but nothing references it in this tree.
- Dismissal is userland: backboardd's BKBootUIPresenter (strings at ~813600 in /tmp/bb.strings)
  waits for `systemShellDidFinishLaunching:` / `firstBootDetectorDidFinishFirstBoot:` and owns
  `hideAppleLogoOnLaunch`, `isShowingBootUI`, `showingBootUI`. The meter is released by
  IOPlatformExpert::setConsoleInfo -> PE_initialize_console(kPEReleaseScreen)
  (video_console.c:3028, the only caller of vc_enable_progressmeter(FALSE)).
- frontboardd does not exist on iOS 16 (FrontBoard is inside SpringBoard) - not a lead.
- userland health: 10x "extension check-in timeout" (syncdefaultsd, SiriTTSSynthesiz,
  MacinTalkAUSP, KonaSynthesizer, com.apple.migrat), "Too many corpses being created", and
  launchd "Could not opt into 50 MB Jetsam high watermark: 22: Invalid argument".
- backboardd's and SpringBoard's os_log never reach the sweet log (only launchd's does), so
  their state is invisible from here.

## REAL FIX (found 2026-11-20) - the image was missing the userland bring-up tweaks
Upstream NOTES.md (this repo) documents the exact symptom and cure:
  - boot 0055n: "SpringBoard waits in -[BKSSystemShellService _checkIn] ... backboardd holds
    the system shell check-in until the data migration ends, so the migration is the gate."
  - boot 0053s: "The iOS data-migration boot screen (Apple logo + progress bar)".
  - image v12 = migration skipped -> HOME SCREEN milestone.
The rosy image was built by tools/mkiosroot-rosy.sh, which never runs
tools/sweet-root-tweaks.py. Confirmed: /private/var/mobile/Library/Preferences held only
.GlobalPreferences.plist, and the boot22 log shows com.apple.datamigrator active.

### Done
- Copy: upstream/ios16-root-tweaked.img (sha 5d70007168e68761..., identical to the original).
- Mounted rw (uid=1000) and applied the upstream tweak set via
  ~/.hermes/cache/scratch/rosy-root-tweaks.py (runs unprivileged; new files staged then
  installed with `sudo rsync --chown`):
    launchd.plist  7x _PanicOnCrash -> _PanicOnCrasX, 2 CommCenter jobs removed
    containers     /private/var/containers/{Bundle:33, Data/System, Shared/SystemGroup, Temp}
    audio          VirtualAudio.plugin -> HAL.disabled; MediaToolbox StartRecorderServer=off
    prefs (501:501 0600): com.apple.migration + com.apple.DataMigration
                   (LastSystemVersion 20H392 + DMUserDataDisposition buildVersion 20H392),
                   com.apple.springboard (BKNoWatchdogs...), com.apple.purplebuddy (Setup
                   skipped), com.apple.purplebuddy.notbackedup, managedconfiguration
  fsck.hfsplus reports the volume OK; plists read back correct.
- ADT already has /chosen unique-chip-id + chip-id (tools/mkadt_rosy.py:50-51).

### Flashed 2026-11-20 ~12:15 - FLASH_EXIT=0, 877 s, 60/60 chunks
`fastboot -S 256M flash userdata ios16-root-tweaked.simg` succeeded; then
`fastboot boot rosy-boot22.img` (RAM only) and the phone left fastboot. It is running now.
When the user is back: power-cycle to fastboot -> `fastboot boot upstream/twrp.img` ->
`bash upstream/ios-rebivincek/tools/sweet-log-pull.sh /tmp/sweetlog14.txt`.
Verdict: `exec com.apple.datamigrator` ABSENT = the migration skip worked.

### Original plan (kept for reference)
1. `fastboot -S 256M flash userdata upstream/ios16-root-tweaked.simg`   (~15 min, wipes userdata)
2. `fastboot boot upstream/rosy-boot22.img`  (RAM only)
3. Expected: the migration never runs, backboardd releases the system-shell check-in, the
   boot UI is dismissed -> home screen (Setup is skipped in the tweaks).
4. Read the log the same way (TWRP + tools/sweet-log-pull.sh) and check that
   com.apple.datamigrator is NOT exec'd.
2. Repack: `tools/rosy_pack.py <kernel> upstream/rosy-boot20.img --loader upstream/rosy-loader.Image
   --dtb upstream/rosy-stock.dtb --cmdline "debug=0xc serial=3 cpus=1 keepsyms=1 rd=emmcroot0
   emmcrw=1 rootrw=1 unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin
   launchd_unsecure_cache=1 wdt=-1 vinceplace=1 vincecache=1 sweetfb_direct=0
   sweetfb_noconsole=1 vincetouch=0 vincekeys=0"`
3. `fastboot boot upstream/rosy-boot20.img`, then pull the log via TWRP and check for
   `kPEDisableScreen` and whether the bar/logo are gone.
4. If the logo persists, it is userland (backboardd) and the boot-progress handoff is next.

## Dead ends / things that were wrong
- boot2/3: fbcon 1440x720 -> the split Apple logo.
- boot4-12: canvas 1125x2436 then 1080x2400 -> console only, no GUI (surfaces failed).
- boot13: canvas 720x1440 -> same.
- boot14: dram base 0x10000000 -> never verified; the old "the lower window killed the kernel"
  claim came from a stale log ring, not a real boot.
- boot16: `gpu=1` -> that is the topaz (sm7150) pool, wrong chip. Discarded.
- boot17: vinceplace fix works, but the console covered the GUI.
- boot19: `ignition_level=3` -> preboot stage fails ("failed to lookup preboot: 25", no preboot
  device). Level 1 is correct; keep it.
- `notes/live/STATUS.txt` is stale (says "Nothing written to it yet", lists the old 1440x720 fbcon).

## Environment notes
- sudo is NOT passwordless: `/etc/sudoers.d/porting` no longer exists, so mount/hfsplus/apfs-fuse/
  rsync/apt-get/dpkg/losetup all prompt. Only the Linux Mint driver tools are NOPASSWD.
- Local toolchain: ~/.local/opt (platform-tools, gh, 7zz, LLVM 18.1.8, libsparse).
- gh is authenticated as mr4lok; admin on mr4lok/ios-rosy (our repo), no push rights on the
  upstream rebopawl-official/ios-rebivincek.
- `gh workflow run` (workflow_dispatch) needs admin and works on mr4lok/ios-rosy; pushes to the
  `rosy` branch now trigger the `xnu` workflow (added in the CI commit).

## How to drive it without hands on the phone
`fastboot boot` works while the phone sits in fastboot. `adb reboot bootloader` does NOT work
in this TWRP build (user-stated 2026-11-20) - a physical press is needed to get back to
fastboot. From TWRP, adb needs a physical touch on the phone screen and ~15 s before commands
work. A boot that drops the phone to EDL (05c6:900e) needs Power held ~15 s.

## boot26 - the accountsd exception, exactly (sweetscan=accountsd)
Cmdline = boot18's + `sweetscan=accountsd`. sha256 49081e109800609468551ae0803584744e84bd231fd1b3e80eb3ba0a5f029bac.
First accountsd abort at t~83 s, so a ~4 min run is enough.

    ACDServerCreateDirectory('file:///var/mobile/Library/Accounts/') failed:
      Error Domain=NSCocoaErrorDomain Code=513 "You don't have permission to save the file
      "Accounts" in the folder "Library"." NSFilePath=/var/mobile/Library/Accounts
      Code=512 "The file couldn't be saved." reason=Failed to create file; code = 2
    -> NSInternalInconsistencyException "Unexpected number of persistent stores (0), expected 1"
    -> abort. 106 aborts in the 4 min run (424 in the 11 h boot25 run).

Chain: accountsd crash-loop -> profiled parked in `-[ACAccountStore accounts]` -> SpringBoard and
lsd parked on `MCProfileConnection checkIn` -> no home screen.
Ruled out: disk space (5.3 GB free), SQLite/IO errors, cfprefsd (3/4 workqueue threads idle),
sandbox denials for accountsd (none logged), usermanagerd (UMD_INIT ran, uid 501 mobile created).

Image facts: /private/var/mobile and /private/var/mobile/Library are mode 0711 uid 501 gid 501,
no ACLs; `Accounts` does not exist. `Preferences` is 0755, `Caches` 0700.
/private/var is a separate data-protection mount: "MKB_INIT: mount is with NO CPROTECT ...
on (/private/var/)", "does not support Data Protection".
Patch 0057 (no config_ext_resolver) IS in the tree. accountsd/lsd/profiled/SpringBoard all run
UserName=mobile.

## Next step (proposed)
Pre-create /var/mobile/Library/Accounts (world-writable, 501:501) in the image and re-flash.
If accountsd gets past it -> permission/ACL problem. If not -> data-protection mount semantics.

## NIGHT RESEARCH 2026-11-21 (full write-up: notes/live/RESEARCH-2026-11-21.md)
Recursive checks done, and the ones that matter:

- accountsd aborts ONLY on the tweaked image (logs 14-18: 52-560 aborts; logs 8/9/11/12/13:
  0 aborts, including an 11 h boot).  BUT the pre-tweak boots were stalled in the data
  migration for ~1 h, so accountsd may simply never have reached its CoreData init there.
  The tweak *unmasked* the bug more likely than it caused it.
- image-vs-image metadata diff of /private/var: only `./` mtime, `mobile/Library/` mtime and
  `mobile/Library/Preferences/` mode 755 -> 775 differ.  /var/mobile and /var/mobile/Library
  are 0711 uid 501 gid 501 in BOTH images, no ACLs.  launchd.plist diff is exactly the intended
  2 CommCenter jobs removed + 7 `_PanicOnCrash` renames.
- Permission path traced to the exact line: `vnode_authorize_posix()` (bsd/vfs/vfs_subr.c)
  grants write on mode 0711 only via `vauth_file_owner()`, which is
  `va_uid == kauth_cred_getuid(cred)`.  So EACCES <=> the caller's uid is not the directory's
  ca_uid.  HFS fills va_uid from `cap->ca_uid` (sweet_hfs/core/hfs_attrlist.c:1485).
- `/private/var/db/dslocal` does NOT exist in the image (no local user records), yet
  `UMD_INIT: Allocated kernel persona with ID: 1000, Type: 5, UID: 501` - so uid 501 exists as
  a kernel persona, but launchd's `UserName=mobile` resolution path is unverified.
- Both images are HFSX ('HX') v5, blockSize 4096, sane header counts.

Artifacts prepared (all committed on branch `rosy`):
- `xnu/patches/1004-rosy-mkdir-trace.patch`  - logs caller uid/gid + parent mode/uid/gid + errno
  for every denied mkdir.  CI run 44817645429.
- `xnu/patches/1005-rosy-hfs-perm-permissive.patch` - makes HFS report the caller as the owner
  (MNT_UNKNOWNPERMISSIONS behaviour, unconditional).  Same run.
- `tools/rosy-fix-dirs.py` - image-side candidates: pre-create Accounts, run accountsd as root,
  or chmod 0777 /var/mobile{,/Library}.
- `notes/live/RESEARCH-2026-11-21.md` - the full hypothesis table with evidence.

Morning plan: boot the run-44817645429 kernel (1004+1005) with `sweetscan=accountsd`.
If accountsd stops aborting -> 1005 was the fix (uid mismatch).  If it still aborts, the
`ROSY MKDIR DENY` line names the caller uid and the parent's real mode/uid.

## boot27 - prepared 2026-11-21 (morning, after the power cut)
- Kernel `upstream/xnu-kernel-rosy7/kernel.development.sweet` (17,801,840 B, sha256
  3a3b4c61f5726d726bdc1653e6de9f2773d435f5d6eca24f9b7a2dff07f734ea) from GH run 44817645429.
  Verified: arm64 Mach-O, contains `ROSY MKDIR DENY` (patch 1004) and the 1003 handover markers;
  CI log shows 1001-1005 all "Applying patch" and the build succeeded.
- Image `upstream/rosy-boot27.img` (17,463,296 B, sha256
  9628bb17c2b2b8f432f4e499b37f5d1035c6d3fff713958a49cac9b6b7ac2372).
  Cmdline is byte-identical to boot26's (checked): boot18's + `sweetscan=accountsd`.
  Only the kernel differs from boot26 -> clean A/B for patch 1005.
- Not booted yet: the power cut left the phone off/disconnected (no 18d1 device on USB).
- Device steps needed: plug USB, Power ~15 s to ensure off, then Power + Vol Down -> fastboot.
- Then: `fastboot boot upstream/rosy-boot27.img`, wait ~4-5 min (first accountsd abort was t~83 s),
  power-cycle to fastboot -> `fastboot boot upstream/twrp.img` ->
  `bash upstream/ios-rebivincek/tools/sweet-log-pull.sh /tmp/sweetlog19.txt`.
- Verdict: `ROSY MKDIR DENY` lines present -> 1005 did not cover that path (read the caller uid /
  parent mode+uid it prints). Absent + no accountsd abort -> 1005 was the fix; then check whether
  SpringBoard/lsd got past `MCProfileConnection checkIn` and the home screen appeared.

## boot27 result (2026-11-21 ~07:35-07:42) - patch 1005 did NOT work, but the trace named the cause
- Screen: kernel text -> Apple logo -> **black**. No EDL drop, clean 5 min run.
- Log `/tmp/sweetlog19.txt`: `CRASH accountsd` x200, `ACDServerCreateDirectory` x201,
  `ROSY MKDIR DENY` x626. Every deny is the same parent:
      parent mode 0x41c9 (040711) uid 1000 gid 1000 mntflags 0x1480d000
  (`0x1480d000` = the `/private/var` mount, per `MKB_INIT: mount is with NO CPROTECT:0x1480d000`).
  So the caller is uid 501 and the *directory owner is 1000* - exactly the EACCES case.

### ROOT CAUSE (ground truth, not a hypothesis)
- `ios16-root-tweaked.img`: `/private/var/mobile/Library` is mode 0711 **uid 1000 gid 1000**.
- `ios16-root.img` (original): same path is 0711 **uid 501 gid 501**.
- The tweak mounted the volume rw with `uid=1000,gid=1000` (so ace could write root-owned files);
  Linux hfsplus wrote those values back into the catalog for every directory whose children were
  touched.  Whole-volume metadata diff (rsync -i dry-run as root between the two mounts):
      /etc, /tmp, /var                       symlinks, owner+group -> 1000
      /Library/Audio/Plug-Ins, .../HAL       owner+group -> 1000
      /System/.../MediaToolbox.framework     owner+group -> 1000
      /private/var                            owner+group -> 1000 (was 0:0)
      /private/var/mobile/Library             owner+group -> 1000 (was 501:501)   <-- the blocker
      /private/var/mobile/Library/Preferences mode 755 -> 775 (intended)
  plus the intended additions (containers/, Library/Audio/Plug-Ins/HAL.disabled/, 6 Preference plists).
  Only `/private/var/mobile/Library` actually blocks anything, but all of it should be repaired.
- Why patch 1005 changed nothing: it edited `vattr_data_for_common_attrs()`, which only serves
  getattrlist.  `VNOP_GETATTR` is `hfs_vnop_getattr()` and it fills `va_uid` from `cp->c_uid`
  (hfs_vnops.c:816 and :1091), and that is what `vnode_authorize_callback_int()` reads for the
  POSIX check (vfs_subr.c:9895-9915).  Verified in the `xnu-buildtree` artifact of run 44817645429.
  MNT_IGNORE_OWNERSHIP itself does not short-circuit the POSIX check (it only affects new-file
  ownership and chown), so mounting with that flag would not have helped either.

## boot28 - patch 1006 (commit 306f5b6, CI run 44856495186, success)
- `xnu/patches/1006-rosy-hfs-getattr-owner.patch`: apply the MNT_IGNORE_OWNERSHIP-style policy in
  the two `hfs_vnop_getattr()` paths (AUTH fast path + general path) and in `packcommonattr()`
  (getattrlist bulk), so a non-root caller is reported as the owner; logs `SWEET HFS PERM` once.
- Kernel `upstream/xnu-kernel-rosy8/kernel.development.sweet` 17,785,496 B
  sha256 6c7ab82d9cd620d04977e69c98d2d1ecc7b690f66fa58a126fd113d19e7802a1
  (contains `SWEET HFS PERM`, `ROSY MKDIR DENY`, handover markers; arm64 Mach-O).
- Image `upstream/rosy-boot28.img` 17,463,296 B
  sha256 2f2418a3f6dfaa358989bd010991c4ea3f6bc8cbc10d83c3e1e0e17066509239
  cmdline identical to boot26/boot27 (boot18's + `sweetscan=accountsd`).
- Not booted yet: the phone was left in TWRP (adb root works) and cannot reach fastboot without a
  physical press.  Do NOT reboot it blindly - `adb reboot bootloader` does not work in this TWRP
  build and a plain reboot would boot Android, which may try to format the HFS+ userdata.
- Steps when the user is back:
    1. Power ~15 s -> off, then Power + Vol Down -> fastboot.
    2. `fastboot boot upstream/rosy-boot28.img`; wait ~4-5 min.
    3. Power ~15 s -> off, Power + Vol Down -> fastboot, `fastboot boot upstream/twrp.img`,
       `bash upstream/ios-rebivincek/tools/sweet-log-pull.sh /tmp/sweetlog20.txt`.
- Verdict: `SWEET HFS PERM` present + `ROSY MKDIR DENY`/`CRASH accountsd` gone ->
  the owner mismatch was the blocker; then check the panel and whether SpringBoard/lsd got past
  `MCProfileConnection checkIn`.  If denies remain, the new line names the parent again.
- Proper image repair (needs the user; `chown` is not in the agent's sudo whitelist):
    `sudo chown 0:0  <mnt>/private/var`
    `sudo chown 501:501 <mnt>/private/var/mobile/Library`
  `tools/rosy-fix-dirs.py --owner MOUNTED_ROOT` prints/runs these; the whole-volume diff above
  lists the remaining cosmetic ones.  Rebuild the simg + reflash afterwards (~15 min).

## boot28-31 (2026-11-21 afternoon) - the blocker is FIXED; iOS reaches the LOCK SCREEN
- boot28 (patch 1006, cpus=1): `SWEET HFS PERM` present, `ROSY MKDIR DENY` 0, `CRASH accountsd` 0,
  `ACDServerCreateDirectory` 0. The ownership fix works. No panic.
- boot29 (same kernel + `sweetsample=cfprefsd,SpringBoard,backboardd,lsd,syncdefaultsd`):
  SpringBoard's main thread spent ~2/3 of samples in
  `_CFPREFERENCES_IS_WAITING_FOR_USER_CFPREFSD` -> `-[CFPrefsSearchListSource
  synchronouslySendSystemMessage:...]` -> `_xpc_connection_send_message_with_reply_sync`
  (waiting on cfprefsd); cfprefsd's own event thread was in `-[CFPrefsDaemon
  handleMultiMessage:replyHandler:]` forwarding an XPC message; 107 "Too many corpses",
  dozens of `extension check-in timeout` kills; `lsd` jetsammed once (16 MB limit) and never
  restarted. GUI froze at 9 swaps; panel slept (`VINCE WLED: backlight off`).
- boot30 (**cpus=8**, only change): `SWEET CPU: cpu=0..7 came alive; SGI1 OK`, no panic,
  `extension check-in timeout` **0** (was dozens), `Too many corpses` 3 (was 107). The
  one-core starvation was real and was masking everything. ADT already declares cpu0..cpu7
  (mkadt_rosy.py); `cpus=1` was purely a boot-arg.
- **boot31 (cpus=8 + vincekeys=1) = MILESTONE: the iOS UI reached the LOCK SCREEN**
  (kernel rosy8, image `upstream/rosy-boot31.img`, sha256 fbe5318f1381d0986d9d0dac93dc2c92cd55558e45f57a4841bda2457f5f348d).
  The earlier "texts > logo > black" was the panel idling to sleep with no input, not a stall.
  Upstream reference for this stage: `NOTES.md` lines 15-18 (home screen on 0069s, image v14,
  cpus=6, sweetfb_hz=30; v14 = our tweak set; input working was needed to *see* it).
- Open items, in order:
  1. Touch: rosy has a FocalTech FT8006M, but `bsd/dev/vince_input.c` drives a Synaptics
     TD4310 and `bsd/dev/sweet_touch.c` a Goodix/FocalTech for topaz. A rosy touch driver is
     still TODO (needed to swipe / unlock / use the home screen).
  2. Keys: `vincekeys=1` boots fine but the log has not been checked yet for
     `VINCE INPUT: key N down/up` - confirm whether power/volume reach iOS.
  3. Image repair: `chown 0:0 <mnt>/private/var` + `chown 501:501
     <mnt>/private/var/mobile/Library` (needs the user's sudo), then rebuild simg + reflash.
  4. `sweetfb_hz=30` (upstream used it; ours is unset) and iPhone X identity for Setup.
- Do NOT boot without `vinceplace=1 vincecache=1`; and note the panel sleeps with no input,
  so a black screen is not evidence of a stall.
