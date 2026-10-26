#!/usr/bin/env python3
"""Push a patched main.*.obb to a rooted Android device.

Usage:
    python tools/push_obb.py --obb D:/FIFA14/modified_copy_20261025/main.136.com.ea.game.fifa14_row.obb --adb adb --serial 89e96829

Steps:
  1. verify the local file size/md5 against EXPECTED (or --force to skip);
  2. force-stop the game (the OBB cannot be replaced while it is mapped);
  3. adb push to /data/local/tmp, back up the current OBB on the device;
  4. su cp into the obb directory, restore the original owner/group/mode;
  5. md5 the file on the device and compare.

The game must be restarted by the user afterwards.
"""
import argparse
import hashlib
import os
import subprocess
import sys

PKG = "com.ea.game.fifa14_row"
OBB_NAME = "main.136.com.ea.game.fifa14_row.obb"
EXPECTED_MD5 = "ec2cd8b36448188c575f2a98a198fdda"
EXPECTED_SIZE = 1386236976


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--obb", required=True, help="local patched OBB")
    ap.add_argument("--adb", default="adb")
    ap.add_argument("--serial", default="", help="adb -s <serial> (needed with 2+ devices)")
    ap.add_argument("--no-backup", action="store_true", help="skip the on-device backup copy")
    ap.add_argument("--force", action="store_true", help="do not verify md5/size")
    args = ap.parse_args()

    path = args.obb
    if not os.path.isfile(path):
        sys.exit("missing " + path)
    size = os.path.getsize(path)
    if not args.force:
        if size != EXPECTED_SIZE:
            sys.exit("size %d != %d" % (size, EXPECTED_SIZE))
        got = md5(path)
        if got != EXPECTED_MD5:
            sys.exit("md5 %s != %s" % (got, EXPECTED_MD5))
        print("local ok: %s %d bytes" % (got, size))

    base = [args.adb] + (["-s", args.serial] if args.serial else [])
    sh = lambda cmd: subprocess.run(base + ["shell", cmd], stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT).stdout.decode("utf-8", "replace").strip()

    target = "/sdcard/Android/obb/%s/%s" % (PKG, OBB_NAME)
    if not sh("ls " + target).startswith(target):
        sys.exit("device OBB not found: " + target)

    # toybox on the Mi Pad 4 segfaults on `stat -c "%u %g %a"`; split the calls
    uid_gid = sh("stat -c '%u %g' " + target).split()
    mode = sh("stat -c '%a' " + target).split()
    uid_gid_mode = uid_gid + mode
    if len(uid_gid_mode) != 3:
        sys.exit("cannot stat device OBB: " + " ".join(uid_gid_mode))
    uid, gid, mode = uid_gid_mode
    print("device obb owner %s:%s mode %s" % (uid, gid, mode))

    print("+ force-stop", PKG)
    sh("am force-stop " + PKG)

    if not args.no_backup:
        bak = "/sdcard/FIFA14_obb_backup_%s.obb" % __import__("datetime").date.today().isoformat()
        if sh("ls " + bak).startswith(bak):
            print("backup already exists, keeping: " + bak)
        else:
            print("+ backup ->", bak)
            sh('su -c "cp %s %s"' % (target, bak))
            print("  backup size:", sh("stat -c %%s " + bak))

    tmp = "/data/local/tmp/new.obb"
    print("+ adb push ->", tmp)
    subprocess.run(base + ["push", path, tmp], check=True)

    print("+ install on device")
    out = sh('su -c "cp %s %s && chown %s:%s %s && chmod %s %s && md5sum %s"'
             % (tmp, target, uid, gid, target, mode, target, target))
    print(" ", out)
    sh("rm -f " + tmp)

    got = out.split()[0] if out else ""
    if got != EXPECTED_MD5:
        sys.exit("device md5 %s != %s" % (got, EXPECTED_MD5))
    print("OK - restart FIFA14 yourself (do not launch it from here)")


if __name__ == "__main__":
    main()