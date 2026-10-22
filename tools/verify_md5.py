#!/usr/bin/env python3
"""Verify the checksums of the two scout databases shipped in this repo."""
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = {
    os.path.join(ROOT, "scout", "main_fifa.db"): "3a8a4b70420f36e305009f2d02def18c",
    os.path.join(ROOT, "scout", "newdb_fifa.db"): "20492d18892da29e99bce4e8be9b2797",
}


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


bad = 0
for path, want in FILES.items():
    if not os.path.isfile(path):
        print("MISSING", path)
        bad += 1
        continue
    got = md5(path)
    ok = got == want
    print("%s  %s  %s  %d bytes" % (got, "OK " if ok else "BAD", os.path.basename(path),
                                    os.path.getsize(path)))
    bad += 0 if ok else 1
sys.exit(1 if bad else 0)