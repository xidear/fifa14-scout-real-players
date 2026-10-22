#!/usr/bin/env python3
"""Push the real-player scout databases to a rooted Android device.

Usage:
    python tools/push_db.py --adb "C:\\Android\\platform-tools\\adb.exe"
    python tools/push_db.py --pkg com.ea.game.fifa14_row --adb adb

The script stops the game, pushes the two .db files to /data/local/tmp,
backs up the files already on the device, copies them into the game's
data/cmn directory and fixes owner/group/mode so the game can read them.
"""
import argparse
import hashlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(ROOT, "scout", "main_fifa.db")
NEW = os.path.join(ROOT, "scout", "newdb_fifa.db")

EXPECTED = {
    MAIN: "3a8a4b70420f36e305009f2d02def18c",
    NEW: "20492d18892da29e99bce4e8be9b2797",
}


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(args, check=True):
    print("+", " ".join(args))
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.stdout.decode("utf-8", "replace").strip()
    if out:
        print(out)
    if check and p.returncode != 0:
        sys.exit("command failed (exit %d)" % p.returncode)
    return p.returncode, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adb", default="adb", help="path to adb executable")
    ap.add_argument("--pkg", default="com.ea.game.fifa14_row", help="game package name")
    ap.add_argument("--keep-running", action="store_true",
                    help="do not force-stop the game before copying")
    args = ap.parse_args()

    for f in (MAIN, NEW):
        if not os.path.isfile(f):
            sys.exit("missing file: " + f)
        got = md5(f)
        want = EXPECTED[f]
        print("%s  %s  %s" % (got, "OK " if got == want else "BAD", os.path.basename(f)))
        if got != want:
            sys.exit("checksum mismatch for " + f + " (expected %s)" % want)

    run([args.adb, "start-server"])
    _, devs = run([args.adb, "devices"])
    if "\tdevice" not in devs:
        sys.exit("no adb device in 'device' state")

    if not args.keep_running:
        run([args.adb, "shell", "am", "force-stop", args.pkg], check=False)

    run([args.adb, "push", MAIN, "/data/local/tmp/fifa_main.db"])
    run([args.adb, "push", NEW, "/data/local/tmp/fifa_new.db"])

    script = """set -e
PKG='%s'
BASE="/sdcard/Android/data/$PKG/data"
DIR="$BASE/cmn"
if [ ! -d "$DIR" ]; then
  echo "ERROR: $DIR not found. Launch the game once, then rerun."
  exit 3
fi
TS=$(date +%%Y%%m%%d_%%H%%M%%S)
mkdir -p "$DIR/New DB"
if [ -f "$DIR/fifa.db" ]; then cp -p "$DIR/fifa.db" "$DIR/fifa.db.bak_$TS"; fi
if [ -f "$DIR/New DB/fifa.db" ]; then cp -p "$DIR/New DB/fifa.db" "$DIR/New DB/fifa.db.bak_$TS"; fi
cp /data/local/tmp/fifa_main.db "$DIR/fifa.db"
cp /data/local/tmp/fifa_new.db "$DIR/New DB/fifa.db"
OWN=$(stat -c '%%u:%%g' "$BASE")
chown "$OWN" "$DIR/fifa.db" "$DIR/New DB/fifa.db"
chmod 664 "$DIR/fifa.db" "$DIR/New DB/fifa.db"
echo "--- installed:"
md5sum "$DIR/fifa.db" "$DIR/New DB/fifa.db"
ls -l "$DIR/fifa.db" "$DIR/New DB/fifa.db"
""" % args.pkg

    dev_script = "/data/local/tmp/rea_push_db.sh"
    tmp = os.path.join(ROOT, ".push_db.tmp.sh")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(script)
    try:
        run([args.adb, "push", tmp, dev_script])
        run([args.adb, "shell", "su", "-c", "sh " + dev_script])
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass

    print("\nDone. Start the game and create a NEW career (old saves are incompatible).")


if __name__ == "__main__":
    main()