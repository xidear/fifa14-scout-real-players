# -*- coding: utf-8 -*-
"""Patch the original FIFA14 career config inside the OBB to boost CPU
signing of young/free players. Values are replaced in place (same byte
length) so the OBB layout does not shift.
"""
import re, hashlib, shutil, os, sys

import argparse

SECTION_START = 924406512  # [CAREER] block inside the 1,386,236,976-byte original OBB
SECTION_LEN = 40000

# key -> new value (same printed length as the original, padded with spaces)
# Only CPU-activity boosts are kept. "Seller willingness" params stay at vanilla values:
#   IDEAL_NUM_PLAYERS 23, MAX_PLAYERS 30, STAR_INTEREST_THRESHOLD 70,
#   TRANSFER_PLAYER_DIF_BUY_MULT 0.75
# Raising them made every CPU club want a bigger squad, so they demanded huge premiums
# when the user bid for a non-listed player (e.g. 24M for a 17M player = 50%).
VALUES = {
    "PROB_BUYING_PLAYER": "95",
    "SIGNING_CHANCE": "95",
    "SMALL_TEAM_SIGNING_CHANCE": "99",
    "PROB_CPU_OFFER": "95",
    "RATING_DIFF_FOR_CPU_SCOUT": "40",
    "PROB_SELLING_RANDOM_PLAYER": "60",
    "PROB_OF_OFFER_WITHDRAWL": "10",
    "CPU_BUY_PRICE_RANGE": "99",
    "CPU_RANDOM_BUY_PRICE_RANGE": "99",
    "CPU_GOOD_PLAYER_BUY_PRICE_RANGE": "300",
    "CPU_BAD_PLAYER_BUY_PRICE_RANGE": "99",
    "WAGE_OFFER_DIVIDER": "05",
}
# exact same-length line fragments (single-digit values that must grow)
EXACT = {
    b"MAX_PER_TEAM_BUYS = 3": b"MAX_PER_TEAM_BUYS =12",
    b"MAX_PER_TEAM_SALES = 3": b"MAX_PER_TEAM_SALES =12",
    b"PROB_CPU_APPROACH = 6": b"PROB_CPU_APPROACH =90",
    b"CHANCE_OF_BOSMAN = 3": b"CHANCE_OF_BOSMAN =90",
}


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description="Boost CPU transfer activity in the original OBB")
    ap.add_argument("src", help="original main.*.obb")
    ap.add_argument("dst", help="output OBB path (a copy is written)")
    args = ap.parse_args()
    SRC, DST = args.src, args.dst
    if not os.path.exists(SRC):
        sys.exit("missing " + SRC)
    shutil.copyfile(SRC, DST)
    with open(DST, "r+b") as f:
        f.seek(SECTION_START)
        data = bytearray(f.read(SECTION_LEN))
        if b"[CAREER]" not in data[:200]:
            sys.exit("career section not found at expected offset")
        changed = []
        for old, new in EXACT.items():
            c = data.count(old)
            if c != 1:
                print("WARN exact count", old, c)
                continue
            data = data.replace(old, new)
            changed.append((old.decode(), "", new.decode(), SECTION_START + data.find(new)))
        for key, val in VALUES.items():
            pat = re.compile(rb"(?m)^(\s*" + key.encode() + rb"\s*=\s*)([0-9.]+)")
            ms = list(pat.finditer(data))
            if not ms:
                print("WARN no match", key)
                continue
            for m in ms:
                old = m.group(2)
                new = val.encode()
                if len(new) > len(old):
                    print("WARN too long", key, old, new)
                    continue
                repl = new + b" " * (len(old) - len(new))
                data[m.start(2):m.end(2)] = repl
                changed.append((key, old.decode(), repl.decode().strip(), SECTION_START + m.start(2)))
        f.seek(SECTION_START)
        f.write(data)
    print("changed", len(changed))
    for c in changed:
        print(" ", c)
    print("src", md5(SRC), os.path.getsize(SRC))
    print("dst", md5(DST), os.path.getsize(DST))


if __name__ == "__main__":
    main()