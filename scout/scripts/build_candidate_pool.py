# -*- coding: utf-8 -*-
"""Build the all-real scout pool: 16,282 real players, 8 boards."""
import os, sys, csv, json, datetime, re
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from country_map import (load_country_table, rating_name_to_code, board_from_rating_name,
                         norm, ALIASES)
from match_players import name_score, nat_key, load_db, parse_dob

DATA = r"D:\FIFA14\work\scout_real_fifa14\data"
KAG = os.path.join(DATA, "kaggle")
OUT = r"D:\FIFA14\work\scout_real_fifa14\data"
DB_SIDS = set(json.load(open(os.path.join(DATA, "db_sofifa_ids_high.json"))))

# Comprehensive "already in the game" name index: every DB player name plus
# both OBB name pools. This catches name variants the Sofifa-ID map misses.
_IDX = json.load(open(os.path.join(DATA, "existing_name_index.json"), encoding="utf-8"))
DB_FULL, DB_PAIR = set(_IDX["db_full"]), set(_IDX["db_pair"])
OBB_FULL, OBB_PAIR = set(_IDX["obb_full"]), set(_IDX["obb_pair"])

# Stars the user explicitly wants in the pool; a common-name collision in the
# OBB commentary pool must not remove them.
PROTECTED = {
    "kylian mbappe", "erling haaland", "rodri", "jude bellingham",
    "lamine yamal", "vinicius junior", "bukayo saka", "phil foden",
    "pedri", "gianluigi donnarumma", "nicolo barella", "federico chiesa",
}

# Ballon d'Or ranked players (2014-2025). Famous players are never removed by
# the broad OBB name-pool filter; they are only removed on an exact DB record
# or a user-confirmed original-career appearance.
BALLON = set()
BALLON_PAIR = set()
_ballon_dir = os.path.join(DATA, "ballon")
for _fn in ("ballon_names.txt", "ballon_names_2022_2025.txt"):
    _p = os.path.join(_ballon_dir, _fn)
    if not os.path.exists(_p):
        continue
    for _line in open(_p, encoding="utf-8"):
        _n = norm(_line.strip())
        if not _n:
            continue
        BALLON.add(_n)
        _t = _n.split()
        if len(_t) >= 2:
            BALLON_PAIR.add(_t[0] + "|" + _t[-1])


def is_famous(c):
    """Famous = high rating or Ballon d'Or ranked. These get exact checks only."""
    try:
        if int(c.get("max_overall") or 0) >= 85:
            return True
    except ValueError:
        pass
    for s in (c.get("name"), c.get("short")):
        n = norm(s or "")
        if not n:
            continue
        if n in BALLON:
            return True
        t = n.split()
        if len(t) >= 2 and (t[0] + "|" + t[-1]) in BALLON_PAIR:
            return True
    return False


def is_ballon(c):
    for s in (c.get("name"), c.get("short")):
        n = norm(s or "")
        if not n:
            continue
        if n in BALLON:
            return True
        t = n.split()
        if len(t) >= 2 and (t[0] + "|" + t[-1]) in BALLON_PAIR:
            return True
    return False


def is_protected(c):
    for s in (c.get("short"), c.get("name")):
        n = norm(s or "")
        if n in PROTECTED:
            return True
    return False


# The user confirmed by playing the original game that these players are
# already present at career start (Lenglet at Nancy, Lucas Hernandez at
# Atletico, Bernardo Silva at Benfica). They must not be added a second time.
USER_CONFIRMED_EXISTING = {
    "clement nicolas laurent lenglet",
    "clement lenglet",
    "lucas francois bernard hernandez pi",
    "lucas hernandez",
    "bernardo mota veiga de carvalho e silva",
    "bernardo mota carvalho e silva",
    "bernardo silva",
}


def _name_keys(c):
    keys = []
    full_first = norm(c.get("name") or "").split()
    full_first = full_first[0] if full_first else ""
    for s in (c.get("name"), c.get("short")):
        n = norm(s or "")
        if not n:
            continue
        keys.append(("full", n))
        t = n.split()
        if len(t) >= 2:
            for x in t[1:]:
                keys.append(("pair", t[0] + "|" + x))
            if len(t[0]) == 1 and full_first:
                keys.append(("pair", full_first + "|" + t[-1]))
    return keys


# Famous players that the loose Kim/Jae surname-pair test wrongly matches to an
# unrelated DB namesake; verified manually as genuinely absent from the 14 DB.
FORCE_KEEP = {"kim min jae"}


def is_name_existing(c):
    """Layered duplicate check.

    1. Exact record in the two original 14 DBs -> existing.
    2. Explicit user-confirmed original-career player -> existing.
    3. Famous (Ballon d'Or / OVR>=85) -> keep unless 1/2 matched.
    4. Non-famous -> broad OBB name-pool match also counts as existing.
    """
    if is_protected(c):
        return False
    if norm(c.get("name") or "") in FORCE_KEEP:
        return False
    if norm(c.get("name") or "") in USER_CONFIRMED_EXISTING:
        return True
    keys = _name_keys(c)
    for kind, k in keys:
        if kind == "full" and k in DB_FULL:
            return True
        if kind == "pair" and k in DB_PAIR:
            return True
    # famous players are only removed on exact DB/user-confirmed evidence
    if is_famous(c):
        return False
    for kind, k in keys:
        if kind == "full" and k in OBB_FULL:
            return True
        if kind == "pair" and k in OBB_PAIR:
            return True
    return False

BOARD_SLOTS = {
    "Europe Other": 4640, "Americas": 4168, "England": 1623,
    "Asia-Pacific": 1121, "Africa": 961, "France": 944,
    "Germany": 687, "Netherlands": 395, "Spain": 999, "Italy": 744,
}
BOARD_PROXY_CODE = {"England": 13, "France": 17, "Germany": 20,
                    "Netherlands": 33, "Europe Other": 3, "Spain": 44,
                    "Italy": 26, "Americas": 53, "Africa": 132,
                    "Asia-Pacific": 154}


def load_fc24():
    players = {}
    p = os.path.join(KAG, "fc24", "male_players.csv")
    with open(p, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            pid = row["player_id"]
            q = players.get(pid)
            if q is None:
                q = {"id": pid, "url": row["player_url"], "long": row["long_name"],
                     "short": row["short_name"], "dob": parse_dob(row["dob"]),
                     "nat": row["nationality_name"], "versions": []}
                players[pid] = q
            try:
                ver = int(float(row["fifa_version"]))
                ovr = int(row["overall"])
            except ValueError:
                continue
            q["versions"].append((ver, ovr, int(row["potential"]),
                                  row["player_positions"], row["club_name"], row["league_name"]))
    for q in players.values():
        q["versions"].sort(key=lambda x: x[0])
    return players


def load_fc26():
    out = []
    p = os.path.join(KAG, "fc26", "ea_fc26_players.csv")
    with open(p, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            dob = parse_dob(row.get("birthdate", ""))
            if not dob:
                continue
            out.append({"id": row.get("id", ""), "first": row.get("firstName", ""),
                        "last": row.get("lastName", ""), "common": row.get("commonName", ""),
                        "dob": dob, "ovr": int(row["overallRating"]) if row.get("overallRating") else None,
                        "pos": row.get("position", ""), "alt": row.get("alternatePositions", ""),
                        "nat": row.get("nationality", ""), "team": row.get("team", "")})
    return out


def load_fc25():
    out = []
    p = os.path.join(KAG, "fc25", "male_players.csv")
    with open(p, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            try:
                ovr = int(float(row["OVR"]))
            except (ValueError, KeyError):
                continue
            out.append({"name": row.get("Name", ""), "key": norm(row.get("Name", "")),
                        "ovr": ovr, "pos": row.get("Position", ""),
                        "alt": row.get("Alternative positions", ""),
                        "nat": row.get("Nation", "")})
    return out


def load_tournament():
    p = os.path.join(DATA, "players_matched.csv")
    out = []
    with open(p, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["db_status"] != "new":
                continue
            out.append(r)
    return out


def main():
    by_code, by_name = load_country_table()
    db, countries, db_players = load_db()
    db_by_dob = defaultdict(list)
    db_by_full = defaultdict(list)
    db_by_surname = defaultdict(list)
    for p in db_players:
        p["full_name"] = p["full"]
        p["alt_names"] = [n for n in p["names"] if n]
        key = norm(p["full"])
        if key:
            db_by_full[key].append(p)
            db_by_surname[key.split()[-1]].append(p)
        if p["dob"]:
            db_by_dob[p["dob"]].append(p)
    print("db players", len(db_players), flush=True)

    def is_db_existing(cand):
        sid = str(cand.get("sofifa_id") or "")
        if sid and sid in DB_SIDS:
            return True
        cdob = datetime.date.fromisoformat(cand["dob"]) if cand["dob"] else None
        cands = []
        if cdob:
            cands += db_by_dob.get(cdob, [])
        cands += db_by_full.get(cand["name_key"], [])
        last = cand["name_key"].split()[-1] if cand["name_key"].split() else ""
        if last:
            cands += db_by_surname.get(last, [])
        seen = set()
        sn = nat_key(cand["nat"])
        for c in cands:
            if c["pid"] in seen:
                continue
            seen.add(c["pid"])
            ns = name_score(cand["name"], c["full_name"])
            if cand.get("short"):
                ns = max(ns, name_score(cand["short"], c["full_name"]))
            for alt in c["alt_names"]:
                ns = max(ns, name_score(cand["name"], alt))
                if cand.get("short"):
                    ns = max(ns, name_score(cand["short"], alt))
            if ns < 30:
                continue
            score = ns
            if c["dob"] and cdob:
                d = abs((c["dob"] - cdob).days)
                if d == 0:
                    score += 50
                elif d <= 366:
                    score += 25
                else:
                    continue
            cn = nat_key(c.get("nat", ""))
            if cn and sn and (cn == sn or cn in sn or sn in cn):
                score += 20
            elif ns < 50:
                continue
            if score >= 75:
                return True
        return False

    def make_candidate(name, key, short, dob, nat, positions, alt, max_ovr, first_ovr,
                       first_ver, latest_club, latest_league, source, sofifa_id="", fc26_id="",
                       tournament=False, tournament_count=0, rating_missing=False):
        # CJK long names normalise to an empty key; use the Latin short name
        # so the player is not silently merged/dropped by dedupe.
        if (not key) and short:
            key = norm(short)
            if key:
                name = short
        board = board_from_rating_name(nat)
        code = rating_name_to_code(nat, by_name)
        proxy = False
        if board == "Unknown":
            # fall back to DB country name -> board
            if code is not None and code in by_code:
                board = by_code[code]["board"]
        if code is None:
            code = BOARD_PROXY_CODE.get(board)
            proxy = True
        return {
            "source": source, "sofifa_id": sofifa_id, "fc26_id": fc26_id,
            "name": name, "name_key": key, "short": short,
            "dob": dob.isoformat() if dob else "", "dob_year": dob.year if dob else 0,
            "nat": nat, "board": board, "db_code": code, "country_proxy": proxy,
            "positions": positions, "positions_alt": alt,
            "max_overall": max_ovr, "first_overall": first_ovr, "first_ver": first_ver,
            "latest_club": latest_club, "latest_league": latest_league,
            "tournament": tournament, "tournament_count": tournament_count,
            "rating_missing": rating_missing,
            "young": bool(dob and dob.year >= 2000),
            "chinese": norm(nat) in ("china pr", "chinese taipei", "hong kong", "macau"),
        }

    # FC24 base candidates
    fc24 = load_fc24()
    print("fc24 unique", len(fc24), flush=True)
    cands = []
    fc24_by_dob = defaultdict(list)
    for q in fc24.values():
        if not q["dob"] or not q["long"] or not q["versions"]:
            continue
        latest = q["versions"][-1]
        first = q["versions"][0]
        max_ovr = max(v[1] for v in q["versions"])
        cand = make_candidate(q["long"], norm(q["long"]), q["short"], q["dob"], q["nat"],
                              latest[3], "", max_ovr, first[1], first[0],
                              latest[4], latest[5], "fc24", sofifa_id=q["id"])
        if cand["board"] == "Unknown":
            if q["id"] == "237086": print("DBG kim board unknown", flush=True)
            continue
        if is_db_existing(cand) or is_name_existing(cand):
            continue
        cand["_q"] = q
        cands.append(cand)
        fc24_by_dob[q["dob"]].append(cand)
    print("fc24 new candidates", len(cands), flush=True)

    # FC26: enrich or add
    fc26 = load_fc26()
    print("fc26", len(fc26), flush=True)
    fc26_by_dob = defaultdict(list)
    for c in cands:
        if c["source"] == "fc24":
            fc26_by_dob[parse_dob(c["dob"])].append(c)
    added26 = 0
    for q in fc26:
        key = norm(q["first"] + " " + q["last"])
        best = None
        bsc = -1
        for c in fc26_by_dob.get(q["dob"], []):
            ns = name_score(q["first"] + " " + q["last"], c["name"])
            if ns < 30:
                continue
            cn, sn = nat_key(q["nat"]), nat_key(c["nat"])
            sc = ns + (20 if cn and sn and (cn == sn or cn in sn or sn in cn) else 0)
            if sc > bsc:
                bsc = sc
                best = c
        if best and bsc >= 50:
            best["positions_2026"] = q["pos"]
            best["positions_2026_alt"] = q["alt"]
            if q["ovr"]:
                best["max_overall"] = max(best["max_overall"] or 0, q["ovr"])
                if not best["first_overall"]:
                    best["first_overall"] = q["ovr"]
        else:
            cand = make_candidate(q["first"] + " " + q["last"], key, q["common"], q["dob"],
                                  q["nat"], q["pos"], q["alt"], q["ovr"], q["ovr"], 26,
                                  q["team"], "", "fc26", fc26_id=q["id"])
            if cand["board"] == "Unknown":
                continue
            if is_db_existing(cand) or is_name_existing(cand):
                continue
            cand["positions_2026"] = q["pos"]
            cand["positions_2026_alt"] = q["alt"]
            cands.append(cand)
            added26 += 1
    print("fc26-only added", added26, flush=True)

    # FC25: only raise max overall / fill position
    fc25 = load_fc25()
    fc25_by_key = defaultdict(list)
    for q in fc25:
        fc25_by_key[q["key"]].append(q)
    up25 = 0
    for c in cands:
        for q in fc25_by_key.get(c["name_key"], []):
            cn, sn = nat_key(q["nat"]), nat_key(c["nat"])
            if cn and sn and (cn == sn or cn in sn or sn in cn):
                if q["ovr"] > (c["max_overall"] or 0):
                    c["max_overall"] = q["ovr"]
                    up25 += 1
                if not c.get("positions_2026"):
                    c["positions_2026"] = q["pos"]
                    c["positions_2026_alt"] = q["alt"]
                break
    print("fc25 max updates", up25, flush=True)

    # tournament flags + tournament-only candidates
    tour = load_tournament()
    print("tournament new", len(tour), flush=True)
    by_key = defaultdict(list)
    by_key_year = defaultdict(list)
    by_sofifa = {}
    for c in cands:
        by_key[(c["name_key"], c["dob"])].append(c)
        by_key_year[(c["name_key"], c["dob_year"])].append(c)
        if c["sofifa_id"]:
            by_sofifa[str(c["sofifa_id"])] = c
    tmatch = 0
    tadd = 0
    for r in tour:
        dob = parse_dob(r["dob"])
        key = r["name_key"]
        hit = None
        sid = str(r.get("sofifa_id", "") or "")
        if sid and sid in by_sofifa:
            hit = by_sofifa[sid]
        if hit is None:
            for c in by_key.get((key, r["dob"]), []):
                hit = c
                break
        if hit is None and dob:
            for y in (dob.year, dob.year - 1, dob.year + 1):
                for c in by_key_year.get((key, y), []):
                    hit = c
                    break
                if hit:
                    break
        if hit:
            hit["tournament"] = True
            hit["tournament_count"] += 1
            tmatch += 1
        else:
            maxo = int(r["max_overall"]) if r["max_overall"] else None
            firsto = int(r["first_ovr"]) if r["first_ovr"] else None
            cand = make_candidate(r["name"], key, "", dob, r["teams"].split(";")[0],
                                  r["fc26_pos"] or r["fc24_pos"] or r["pos"], r.get("fc26_alt", ""),
                                  maxo, firsto or maxo, r.get("first_ver") or "",
                                  "", "", "tournament", sofifa_id=r.get("sofifa_id", ""),
                                  tournament=True, tournament_count=1,
                                  rating_missing=not bool(maxo))
            if cand["board"] == "Unknown":
                continue
            if is_db_existing(cand) or is_name_existing(cand):
                continue
            cands.append(cand)
            tadd += 1
    print("tournament matched", tmatch, "added", tadd, flush=True)

    # filter sane ages / names / boards
    clean = []
    for c in cands:
        if not c["dob"] or not c["name"] or not c["board"] or c["board"] == "Unknown":
            continue
        y = c["dob_year"]
        if y < 1980 or y > 2010:
            continue
        if c["max_overall"] is None:
            c["max_overall"] = 55
        if c["first_overall"] is None:
            c["first_overall"] = min(55, c["max_overall"])
        clean.append(c)
    cands = clean
    print("clean candidates", len(cands), flush=True)

    # dedupe candidates: same DOB + nationality + similar name = one person
    def dedupe(cands):
        groups = defaultdict(list)
        for c in cands:
            groups[(c["dob"], nat_key(c["nat"]))].append(c)

        def same_person(a, b):
            if name_score(a["name"], b["name"]) >= 30:
                return True
            if not a.get("name_key") or not b.get("name_key"):
                return True
            ta = a["name_key"].split()
            tb = b["name_key"].split()
            if ta and tb and ta[-1] == tb[-1]:
                f1, f2 = ta[0], tb[0]
                if f1 == f2:
                    return True
                if len(f1) >= 3 and len(f2) >= 3 and (f1.startswith(f2) or f2.startswith(f1)):
                    return True
            return False

        out = []
        for grp in groups.values():
            clusters = []
            for c in grp:
                placed = False
                for cl in clusters:
                    for x in cl:
                        if same_person(c, x):
                            cl.append(c)
                            placed = True
                            break
                    if placed:
                        break
                if not placed:
                    clusters.append([c])
            for cl in clusters:
                def pref(x):
                    toks = len(x["name_key"].split()) if x["name_key"] else 99
                    return (0 if x["name_key"] else 1, toks, -(x["max_overall"] or 0))
                best = min(cl, key=pref)
                for x in cl:
                    if x is best:
                        continue
                    best["max_overall"] = max(best["max_overall"] or 0, x["max_overall"] or 0)
                    best["first_overall"] = min(best["first_overall"] or 99, x["first_overall"] or 99)
                    best["tournament"] = best["tournament"] or x["tournament"]
                    best["tournament_count"] += x["tournament_count"]
                    if not best.get("positions_2026") and x.get("positions_2026"):
                        best["positions_2026"] = x["positions_2026"]
                        best["positions_2026_alt"] = x.get("positions_2026_alt", "")
                    if not x["rating_missing"]:
                        best["rating_missing"] = False
                    best["chinese"] = best["chinese"] or x["chinese"]
                    best["young"] = best["young"] or x["young"]
                out.append(best)
        return out

    before = len(cands)
    cands = dedupe(cands)
    print("dedupe", before, "->", len(cands), flush=True)

    # selection per board / age band
    def band(c):
        y = c["dob_year"]
        if y <= 1999:
            return "A"
        if y <= 2004:
            return "B"
        return "C"

    for c in cands:
        c["band"] = band(c)
        c["forced"] = is_ballon(c)
        c["sort_key"] = (0 if c["tournament"] else 1,
                         0 if c["young"] else 1,
                         -(c["max_overall"] or 0),
                         -c["dob_year"])
    pools = defaultdict(lambda: defaultdict(list))
    for c in cands:
        pools[c["board"]][c["band"]].append(c)
    for b in pools:
        for k in pools[b]:
            pools[b][k].sort(key=lambda x: x["sort_key"])

    selected = []
    stats = {}
    for board, slots in BOARD_SLOTS.items():
        nA = int(round(slots * 0.45))
        nB = int(round(slots * 0.35))
        nC = slots - nA - nB
        take = {"A": nA, "B": nB, "C": nC}
        chosen = []
        used = set()
        # Asia-Pacific: reserve ~300 slots for Chinese players (no official licence)
        if board == "Asia-Pacific":
            for bnd, quota in (("A", 135), ("B", 105), ("C", 60)):
                cnt = 0
                for c in pools[board][bnd]:
                    if c["chinese"] and id(c) not in used:
                        used.add(id(c))
                        chosen.append(c)
                        cnt += 1
                        if cnt >= quota:
                            break
        for bnd in ("A", "B", "C"):
            for c in pools[board][bnd]:
                if len([x for x in chosen if x["band"] == bnd]) >= take[bnd]:
                    break
                if id(c) in used:
                    continue
                used.add(id(c))
                chosen.append(c)
        # fill shortages from the same board, any band
        if len(chosen) < slots:
            for bnd in ("A", "B", "C"):
                for c in pools[board][bnd]:
                    if len(chosen) >= slots:
                        break
                    if id(c) in used:
                        continue
                    used.add(id(c))
                    chosen.append(c)
                if len(chosen) >= slots:
                    break
        # guarantee Ballon d'Or-ranked players are present: replace the
        # lowest-rated non-forced pick in the same board (same band first).
        forced_missing = []
        for bnd in ("A", "B", "C"):
            for c in pools[board][bnd]:
                if c.get("forced") and id(c) not in used:
                    forced_missing.append(c)
        for c in forced_missing:
            victims = [x for x in chosen if not x.get("forced") and x["band"] == c["band"]]
            if not victims:
                victims = [x for x in chosen if not x.get("forced")]
            if not victims:
                break
            victim = min(victims, key=lambda x: (int(x["max_overall"] or 0), x["dob_year"]))
            chosen.remove(victim)
            used.discard(id(victim))
            used.add(id(c))
            chosen.append(c)
        for c in chosen:
            c["selected_board"] = board
        selected.extend(chosen)
        stats[board] = {"slots": slots, "picked": len(chosen),
                        "pool": {k: len(v) for k, v in pools[board].items()},
                        "bands": Counter(c["band"] for c in chosen)}
    print(json.dumps({k: {"slots": v["slots"], "picked": v["picked"], "pool": v["pool"],
                          "bands": dict(v["bands"])} for k, v in stats.items()},
                     ensure_ascii=False, indent=2), flush=True)
    print("total selected", len(selected), "target", sum(BOARD_SLOTS.values()), flush=True)

    fields = ["source", "sofifa_id", "fc26_id", "name", "name_key", "short", "dob", "dob_year",
              "nat", "board", "db_code", "country_proxy", "positions", "positions_alt",
              "positions_2026", "positions_2026_alt", "max_overall", "first_overall",
              "first_ver", "latest_club", "latest_league", "tournament", "tournament_count",
              "rating_missing", "young", "chinese", "band", "selected_board"]
    path = os.path.join(DATA, "candidate_pool.csv")
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(selected)
    print("wrote", path, len(selected))
    with open(os.path.join(DATA, "candidate_stats.json"), "w", encoding="utf-8") as f:
        json.dump({k: {"slots": v["slots"], "picked": v["picked"], "pool": v["pool"],
                       "bands": dict(v["bands"])} for k, v in stats.items()},
                  f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()