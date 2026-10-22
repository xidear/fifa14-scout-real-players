# -*- coding: utf-8 -*-
"""Write the all-real 16,282 scout pool into the original main + New DB."""
import os, sys, csv, json, datetime, struct, hashlib, re
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fifa14_db import FifaDB, MAIN, NEWDB, write_bits, read_bits
from country_map import load_country_table, board_from_db_name, norm

BASE = r"D:\FIFA14\work\scout_real_fifa14\base"
DATA = r"D:\FIFA14\work\scout_real_fifa14\data"
OUT = r"D:\FIFA14\work\scout_real_fifa14\out"
EPOCH = datetime.date(1582, 10, 14)
FAKE_LO, FAKE_HI = 400000, 416281
SLOTS = {"Europe Other": 4640, "Americas": 4168, "England": 1623,
         "Asia-Pacific": 1121, "Africa": 961, "France": 944,
         "Germany": 687, "Netherlands": 395, "Spain": 999, "Italy": 744}
POS_MAP = {"LWB": "LB", "RWB": "RB", "CF": "ST"}

# Player-record preferred-position codes (bit179/189 main, 211/221 new).
# Derived from the DB's own player data and confirmed cases
# (Oberlechner/Dinescu = 16 = LWB).
POS_CODE = {
    "GK": 0, "SW": 1, "CM": 14, "CAM": 3, "RM": 30, "LM": 7,
    "RB": 6, "LB": 15, "CB": 10, "CDM": 22, "CF": 23, "ST": 28,
    "RW": 29, "LW": 8, "LWB": 16, "RWB": 6,
}


def plist(s):
    out = []
    for x in (s or "").replace("/", ",").split(","):
        x = x.strip().upper()
        if not x:
            continue
        x = {"FW": "ST", "LWF": "LW", "RWF": "RW", "SS": "CF"}.get(x, x)
        if x not in out:
            out.append(x)
    return out


def target_positions(c):
    """Real 2026 primary + one real secondary position (no donor inheritance)."""
    prim_list = plist(c.get("positions_2026")) or plist(c.get("positions")) or ["CM"]
    primary = prim_list[0]
    # Only FC26 alternate positions are real 2026 data; older-version
    # positions must not invent roles the player no longer has.
    alt = [x for x in plist(c.get("positions_2026_alt")) if x != primary]
    secondary = primary
    is_rodri = norm(c.get("name") or "") == "rodrigo hernandez cascante"
    if primary == "GK":
        secondary = "GK"
    elif primary == "CDM":
        # user rule: Rodri also plays CB; otherwise use the real FC26 alt
        # (Kimmich RB, Rice CM, Caicedo CM...), never a blanket CB.
        if is_rodri or "CB" in alt:
            secondary = "CB"
        elif alt:
            secondary = alt[0]
    elif primary in ("LW", "RW", "LM", "RM"):
        # wide players first look for a real forward role, then the real alt
        secondary = next((x for x in alt if x in ("ST", "CF")), alt[0] if alt else primary)
    else:
        secondary = alt[0] if alt else primary
    if secondary not in POS_CODE:
        secondary = primary if primary in POS_CODE else "CM"
    if primary not in POS_CODE:
        primary = "CM"
    return primary, secondary


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def days(d):
    return (d - EPOCH).days


def display_name(c):
    long = (c.get("name") or "").strip()
    short = (c.get("short") or "").strip()
    if not long:
        return short
    # non-Latin short/long handling: prefer a Latin form if available
    def has_cjk(s):
        return any("\u4e00" <= ch <= "\u9fff" for ch in s)
    if has_cjk(long) and short and not has_cjk(short):
        long = short
    if short and "." not in short:
        toks = short.split()
        if 1 <= len(toks) <= 3 and not any(len(t) <= 1 for t in toks):
            return short
    if short and "." in short:
        stoks = short.replace(".", " ").split()
        if len(stoks) >= 2:
            first = long.split()[0]
            sur = " ".join(stoks[1:])
            if sur.lower() in ("jr", "jr.", "junior"):
                sur = "Júnior"
            return first + " " + sur
    toks = long.split()
    if len(toks) <= 2:
        return long
    if toks[-1].lower() in ("jr", "jr.", "junior", "júnior", "filho", "neto", "sobrinho"):
        return toks[0] + " " + toks[-1]
    if toks[-2].lower() in ("van", "von", "de", "der", "den", "di", "da", "dos", "del", "la", "le", "du", "bin", "al", "el"):
        return toks[0] + " " + toks[-2] + " " + toks[-1]
    return toks[0] + " " + toks[-1]


def split_name(display):
    toks = display.split()
    if len(toks) <= 1:
        return "", display
    return toks[0], " ".join(toks[1:])


def append_str(db, s):
    if not s:
        return 0
    b = s.encode("utf-8")
    off = len(db.d)
    db.d += struct.pack("<H", len(b)) + b
    return off


def choose_donor(cand, donors_by_pos, donors_by_broad, donors_all, rot):
    def plist(s):
        return [x.strip().upper() for x in (s or "").split(",") if x.strip()]
    poslist = plist(cand.get("positions_2026")) or plist(cand.get("positions")) or ["CM"]
    pos = POS_MAP.get(poslist[0], poslist[0])
    alt = plist(cand.get("positions_2026_alt")) + [x for x in plist(cand.get("positions")) if x]
    secondary = []
    for x in alt:
        y = POS_MAP.get(x, x)
        if y != pos and y not in secondary:
            secondary.append(y)
    # user's versatility rules, always added (not only when alt is empty):
    # wingers/wide mids can play ST/CF; CDM can play CB; CB can play CDM/FB;
    # CAM/CM can play CM/CDM; ST can play CF.
    add = []
    if pos in ("LW", "RW", "LM", "RM"):
        add = ["ST", "CF"]
    elif pos == "CDM":
        add = ["CB"]
    elif pos == "CB":
        add = ["CDM", "RB", "LB"]
    elif pos == "CAM":
        add = ["CM"]
    elif pos == "CM":
        add = ["CDM", "CAM"]
    elif pos == "ST":
        add = ["CF"]
    secondary = [x for x in add if x != pos] + [x for x in secondary if x not in add]
    target = cand.get("first_overall")
    try:
        target = int(target) if target not in (None, "") else 55
    except ValueError:
        target = 55
    pool = donors_by_pos.get(pos) or donors_by_broad.get(
        "GK" if pos == "GK" else ("DEF" if pos in ("RB", "LB", "CB") else
                                  ("MID" if pos in ("CDM", "CM", "CAM", "LM", "RM") else "FWD"))) or donors_all
    if not pool:
        return None
    # prefer donors who already list a matching secondary position (versatility)
    if secondary:
        weights = {}
        for x in add:
            if x != pos:
                weights[x] = 10
        for x in secondary:
            weights.setdefault(x, 1)
        scored = []
        best = 0
        for d in pool:
            dps = set(plist(d.get("positions")))
            cnt = sum(w for s, w in weights.items() if s in dps)
            if cnt > best:
                best = cnt
            scored.append((cnt, d))
        if best > 0:
            pool = [d for cnt, d in scored if cnt == best]
    # closest first_ovr, rotate among ties
    pool = sorted(pool, key=lambda d: abs((d["first_ovr"] or 60) - target))
    k = min(5, len(pool))
    return pool[rot % k]


def main():
    os.makedirs(OUT, exist_ok=True)
    by_code, by_name = load_country_table()
    main_db = FifaDB.load(os.path.join(BASE, "main_fifa.db"), MAIN)
    new_db = FifaDB.load(os.path.join(BASE, "newdb_fifa.db"), NEWDB)
    print("main", main_db.summary(), "new", new_db.summary(), flush=True)

    # slots by board/country
    def nat_of(db, pid):
        o = db.record_offset(pid)
        v = 0
        for k in range(8):
            b = 518 + k if db.layout.name == "main" else 550 + k
            v = (v << 1) | ((db.d[o + (b >> 3)] >> (7 - (b & 7))) & 1)
        return v

    slots = defaultdict(list)
    for pid in range(FAKE_LO, FAKE_HI + 1):
        code = nat_of(main_db, pid)
        info = by_code.get(code)
        name = info["name"] if info else ""
        cont = info["cont"] if info else 0
        bd = board_from_db_name(name, cont) if name else "Unknown"
        slots[bd].append((pid, code))
    print("slots", {k: len(v) for k, v in slots.items()}, flush=True)

    cands = list(csv.DictReader(open(os.path.join(DATA, "candidate_pool.csv"), encoding="utf-8-sig")))
    print("candidates", len(cands), flush=True)
    # disambiguate namesakes: if several distinct players share a display name,
    # keep the common name for the highest-rated one and use the full name for the rest.
    groups = defaultdict(list)
    for c in cands:
        groups[display_name(c)].append(c)
    display_override = {}
    for disp, arr in groups.items():
        if len({(c["dob"], c["nat"]) for c in arr}) > 1:
            arr = sorted(arr, key=lambda c: (-(int(c["max_overall"] or 0)),
                                             -(int(c["tournament_count"] or 0)), c["dob"]))
            for c in arr[1:]:
                display_override[id(c)] = c["name"]

    def disp_name(c):
        return display_override.get(id(c), display_name(c))

    by_board = defaultdict(list)
    for c in cands:
        by_board[c["selected_board"]].append(c)

    donors = list(csv.DictReader(open(os.path.join(DATA, "donor_pool.csv"), encoding="utf-8-sig")))
    dpos, dbroad, dall = defaultdict(list), defaultdict(list), []
    for d in donors:
        d["pid"] = int(d["pid"])
        d["first_ovr"] = int(d["first_ovr"]) if d["first_ovr"] else None
        dpos[POS_MAP.get(d["first_pos"], d["first_pos"])].append(d)
        dbroad[d["broad"]].append(d)
        dall.append(d)
    print("donors", len(donors), flush=True)

    # assign per board, preferring same country code
    assignments = []
    rot = 0
    for board, slist in slots.items():
        clist = by_board.get(board, [])
        if len(clist) < len(slist):
            raise SystemExit(f"not enough candidates for {board}: {len(clist)} < {len(slist)}")
        by_code_c = defaultdict(list)
        for c in clist:
            by_code_c[str(c["db_code"])].append(c)
        remaining = list(clist)
        rem_ids = set(id(c) for c in remaining)
        used = set()
        for pid, code in slist:
            pick = None
            arr = by_code_c.get(str(code), [])
            while arr:
                c = arr.pop(0)
                if id(c) not in used:
                    pick = c
                    break
            if pick is None:
                while remaining:
                    c = remaining.pop(0)
                    if id(c) not in used:
                        pick = c
                        break
            if pick is None:
                raise SystemExit("ran out of candidates")
            used.add(id(pick))
            donor = choose_donor(pick, dpos, dbroad, dall, rot)
            rot += 1
            assignments.append({"pid": pid, "board": board, "slot_code": code,
                                "cand": pick, "donor": donor})

    print("assignments", len(assignments), flush=True)
    if len(assignments) != sum(SLOTS.values()):
        raise SystemExit("assignment count mismatch")

    # write records
    appended = {"main": 0, "new": 0}
    changed_records = 0
    for a in assignments:
        pid, c, d = a["pid"], a["cand"], a["donor"]
        disp = disp_name(c)
        first, last = split_name(disp)
        dday = days(datetime.date.fromisoformat(c["dob"]))
        pot = int(c["max_overall"]) if c["max_overall"] else 60
        pot = max(0, min(127, pot))
        code = int(c["db_code"]) if c["db_code"] not in (None, "") else a["slot_code"]
        pos1, pos2 = target_positions(c)
        a["pos1"], a["pos2"] = pos1, pos2
        p1, p2 = POS_CODE[pos1], POS_CODE[pos2]

        # main
        om = main_db.record_offset(pid)
        rm = bytearray(main_db.d[om:om + 72])
        pm = main_db.record_offset(d["pid"])
        dm = main_db.d[pm:pm + 72]
        before_len = len(main_db.d)
        if first:
            struct.pack_into("<I", rm, 4, append_str(main_db, first))
        else:
            struct.pack_into("<I", rm, 4, 0)
        struct.pack_into("<I", rm, 8, append_str(main_db, last))
        struct.pack_into("<I", rm, 12, 0)
        struct.pack_into("<I", rm, 16, dday)
        rm[20:72] = dm[20:72]
        # donor's pref bits came with the block; overwrite with the player's
        # real 2026 positions so positions never drift to the donor's roles.
        write_bits(rm, 179, 5, p1)
        write_bits(rm, 189, 5, p2)
        write_bits(rm, 518, 8, code & 0xFF, msb=True)
        write_bits(rm, 374, 7, pot)
        main_db.d[om:om + 72] = rm
        appended["main"] += len(main_db.d) - before_len
        changed_records += 1

        # new db
        on = new_db.record_offset(pid)
        rn = bytearray(new_db.d[on:on + 76])
        pn = new_db.record_offset(d["pid"])
        dn = new_db.d[pn:pn + 76]
        before_len = len(new_db.d)
        if first:
            struct.pack_into("<I", rn, 4, append_str(new_db, first))
        else:
            struct.pack_into("<I", rn, 4, 0)
        struct.pack_into("<I", rn, 8, append_str(new_db, last))
        struct.pack_into("<I", rn, 12, 0)
        struct.pack_into("<I", rn, 16, 0)
        struct.pack_into("<I", rn, 20, dday)
        rn[24:76] = dn[24:76]
        write_bits(rn, 211, 5, p1)
        write_bits(rn, 221, 5, p2)
        write_bits(rn, 550, 8, code & 0xFF, msb=True)
        write_bits(rn, 406, 7, pot)
        new_db.d[on:on + 76] = rn
        appended["new"] += len(new_db.d) - before_len

    print("records written", changed_records, "appended", appended, flush=True)

    # existing players: potential only
    existing = {}
    for r in csv.DictReader(open(os.path.join(DATA, "players_matched.csv"), encoding="utf-8-sig")):
        if r["db_status"] == "existing" and r["db_pid"] and r["max_overall"]:
            pid = int(r["db_pid"])
            pot = int(r["max_overall"])
            existing[pid] = max(existing.get(pid, 0), pot)
    n_ex = 0
    for pid, pot in existing.items():
        om = main_db.record_offset(pid)
        on = new_db.record_offset(pid)
        if om is None or on is None:
            continue
        rm = bytearray(main_db.d[om:om + 72])
        write_bits(rm, 374, 7, max(0, min(127, pot)))
        main_db.d[om:om + 72] = rm
        rn = bytearray(new_db.d[on:on + 76])
        write_bits(rn, 406, 7, max(0, min(127, pot)))
        new_db.d[on:on + 76] = rn
        n_ex += 1
    print("existing potential edits", n_ex, flush=True)

    # save
    mp = os.path.join(OUT, "main_fifa.db")
    np = os.path.join(OUT, "newdb_fifa.db")
    main_db.save(mp)
    new_db.save(np)
    print("saved", mp, len(main_db.d), md5(mp))
    print("saved", np, len(new_db.d), md5(np))

    # report
    rep = {
        "records": changed_records, "existing_potential": n_ex,
        "appended_bytes": appended,
        "main_size": len(main_db.d), "new_size": len(new_db.d),
        "main_md5": md5(mp), "new_md5": md5(np),
        "boards": {b: len(v) for b, v in slots.items()},
        "candidate_sources": dict(Counter(a["cand"]["source"] for a in assignments)),
        "chinese": sum(1 for a in assignments if a["cand"]["chinese"] == "True"),
        "tournament": sum(1 for a in assignments if a["cand"]["tournament"] == "True"),
        "rating_missing": sum(1 for a in assignments if a["cand"]["rating_missing"] == "True"),
    }
    with open(os.path.join(OUT, "report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT, "assignment.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pid", "board", "slot_code", "name", "display", "dob", "nat", "db_code",
                    "positions_2026", "positions_2026_alt", "pos1", "pos2",
                    "max_overall", "first_overall", "donor_pid", "donor_name"])
        for a in assignments:
            c, d = a["cand"], a["donor"]
            w.writerow([a["pid"], a["board"], a["slot_code"], c["name"], disp_name(c),
                        c["dob"], c["nat"], c["db_code"], c["positions_2026"],
                        c.get("positions_2026_alt", ""),
                        a.get("pos1", ""), a.get("pos2", ""),
                        c["max_overall"], c["first_overall"], d["pid"] if d else "",
                        d["name"] if d else ""])
    print(json.dumps(rep, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()