#!/usr/bin/env python3
"""Install the jersey-number editor APK and grant the overlay permission.

    python tools/install_app.py --adb adb
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APK = os.path.join(ROOT, "jersey-app", "apk", "jersey-app.apk")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adb", default="adb")
    args = ap.parse_args()
    if not os.path.isfile(APK):
        sys.exit("missing " + APK)
    for cmd in ([args.adb, "install", "-r", APK],
                [args.adb, "shell", "appops", "set", "com.zcode.jersey",
                 "SYSTEM_ALERT_WINDOW", "allow"]):
        print("+", " ".join(cmd))
        p = subprocess.run(cmd)
        if p.returncode != 0:
            print("  (failed; continue manually)")
    print("""
Done.
1. Open 'FIFA14 改号' and let Magisk grant root.
2. Tap '开启改号面板', then switch to FIFA14 career mode.
3. The round '改' button appears at the left edge; tap it to open the list.
""")


if __name__ == "__main__":
    main()