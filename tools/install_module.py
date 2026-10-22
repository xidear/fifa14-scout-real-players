#!/usr/bin/env python3
"""Install the Magisk auto-show module (requires root + Magisk).

    python tools/install_module.py --adb adb
    python tools/install_module.py --adb adb --start-now
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "magisk-module")
DEST = "/data/adb/modules/fifa14_jersey_auto"


def run(cmd, check=True):
    print("+", " ".join(cmd))
    p = subprocess.run(cmd)
    if check and p.returncode != 0:
        sys.exit("failed: " + " ".join(cmd))
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adb", default="adb")
    ap.add_argument("--start-now", action="store_true",
                    help="start service.sh immediately instead of waiting for reboot")
    args = ap.parse_args()

    run([args.adb, "push", MOD, "/data/local/tmp/fifa14_jersey_auto"])
    script = ("mkdir -p {d} && cp /data/local/tmp/fifa14_jersey_auto/module.prop {d}/"
              " && cp /data/local/tmp/fifa14_jersey_auto/service.sh {d}/"
              " && chmod 644 {d}/module.prop && chmod 755 {d}/service.sh"
              " && rm -f /data/local/tmp/fifa14_jersey_auto.lock"
              " && ls -l {d}").format(d=DEST)
    run([args.adb, "shell", "su", "-c", script])

    if args.start_now:
        run([args.adb, "shell", "su", "-c",
             "nohup sh %s/service.sh >/dev/null 2>&1 &" % DEST])
        print("started now (takes effect on next FIFA14 launch)")
    else:
        print("installed; active after the next reboot")


if __name__ == "__main__":
    main()