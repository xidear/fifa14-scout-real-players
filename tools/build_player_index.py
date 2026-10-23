#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuild the app name index (assets/fifa.db) from the game's player DB.

The index stores pid -> display name plus the team/jersey tables.  Old versions
of this index concatenated all three DB name fields, which produced duplicated
surnames such as "Lucas Piazon Piazon".  The DB actually stores:

    field0 = first name (may be empty)
    field1 = surname, or a full name when field0 is empty
    field2 = short/nickname (may be empty)

Display name = field0 + " " + field1 (field2 is ignored).

    python tools/build_player_index.py --db scout/main_fifa.db --asset jersey-app/src/assets/fifa.db
"""
import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fifa14_db as F


def u32(d, o):
    return struct.unpack_from("<I", d, o)[0], o + 4


def u16(d, o):
    return struct.unpack_from("<H", d, o)[0], o + 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(HERE, "..", "scout", "main_fifa.db"))
    ap.add_argument("--asset", default=os.path.join(HERE, "..", "jersey-app", "src", "assets", "fifa.db"))
    args = ap.parse_args()

    d = open(args.asset, "rb").read()
    o = 0
    magic, o = u32(d, o)
    if magic != 0x4A523034:
        sys.exit("bad index magic in " + args.asset)
    n, o = u32(d, o)
    players = []
    for _ in range(n):
        pid, o = u32(d, o)
        ln, o = u16(d, o)
        players.append([pid, d[o:o + ln].decode("utf-8")])
        o += ln
    tn, o = u32(d, o)
    teams = []
    for _ in range(tn):
        tid, o = u32(d, o)
        cnt, o = u32(d, o)
        ln, o = u16(d, o)
        tname = d[o:o + ln].decode("utf-8")
        o += ln
        pairs = []
        for _ in range(cnt):
            pid, o = u32(d, o)
            jersey, o = u32(d, o)
            pairs.append((pid, jersey))
        teams.append((tid, tname, pairs))
    cn, o = u32(d, o)
    conflicts = []
    for _ in range(cn):
        a, o = u32(d, o)
        b, o = u32(d, o)
        conflicts.append((a, b))

    db = F.FifaDB.load(args.db, F.MAIN)

    def display_name(pid):
        names = db.names(pid) or []
        a = (names[0] or "").strip() if len(names) > 0 else ""
        b = (names[1] or "").strip() if len(names) > 1 else ""
        c = (names[2] or "").strip() if len(names) > 2 else ""
        if a and b:
            return a + " " + b
        return b or a or c or None

    changed = 0
    for p in players:
        nm = display_name(p[0])
        if nm and nm != p[1]:
            p[1] = nm
            changed += 1

    out = bytearray(struct.pack("<II", 0x4A523034, len(players)))
    for pid, name in players:
        b = name.encode("utf-8")
        out += struct.pack("<IH", pid, len(b)) + b
    out += struct.pack("<I", len(teams))
    for tid, tname, pairs in teams:
        b = tname.encode("utf-8")
        out += struct.pack("<IIH", tid, len(pairs), len(b)) + b
        for pid, jersey in pairs:
            out += struct.pack("<II", pid, jersey)
    out += struct.pack("<I", len(conflicts))
    for a, b in conflicts:
        out += struct.pack("<II", a, b)
    open(args.asset, "wb").write(out)
    print("players", len(players), "teams", len(teams), "changed", changed,
          "size", len(out))


if __name__ == "__main__":
    main()