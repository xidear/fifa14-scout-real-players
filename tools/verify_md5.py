#!/usr/bin/env python3
"""Verify the checksums of the two scout databases shipped in this repo."""
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = {
    os.path.join(ROOT, "scout", "main_fifa.db"): "a74a7e8acfd93b71068a96d094d8c32f",
    os.path.join(ROOT, "scout", "newdb_fifa.db"): "ca6bf1280bd559c6613e581c53269903",
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