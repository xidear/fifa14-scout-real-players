# -*- coding: utf-8 -*-
"""Generate a season-by-season scout guide from the all-real pool assignments."""
import os, csv, datetime, json
from collections import defaultdict

OUT = r"D:\FIFA14\work\scout_real_fifa14\out"
ASSIGN = os.path.join(OUT, "assignment.csv")
BOARDS = ["England", "France", "Germany", "Netherlands", "Italy", "Spain",
          "Europe Other", "Americas", "Africa", "Asia-Pacific"]
SEASONS = list(range(2013, 2027))


def load():
    rows = []
    for r in csv.DictReader(open(ASSIGN, encoding="utf-8-sig")):
        try:
            dob = datetime.date.fromisoformat(r["dob"])
        except Exception:
            continue
        rows.append({
            "pid": int(r["pid"]), "board": r["board"], "name": r["display"],
            "dob": dob, "pos": r["positions_2026"] or "",
            "pot": int(r["max_overall"]) if r["max_overall"] else 0,
            "cur": int(r["first_overall"]) if r["first_overall"] else 0,
            "nat": r["nat"],
        })
    return rows


def scoutable(rows, season):
    # age >= 16 on 1 July of the season
    cutoff = datetime.date(season - 16, 7, 1)
    return [r for r in rows if r["dob"] <= cutoff]


def main():
    rows = load()
    print("players", len(rows))
    guide_csv = os.path.join(OUT, "scout_guide.csv")
    md = []
    md.append("# FIFA14 全真实球探池 — 分板块/分赛季搜索指南\n")
    md.append("目标：每个赛季都能找到 16 岁以上、真实存在的球员；不再空手而归。\n")
    md.append("说明：\n")
    md.append("- 板块固定为 10 个：英格兰、法国、德国、荷兰、意大利、西班牙、欧洲其他、美洲、非洲、亚太。\n")
    md.append("- 球员 16 岁后才可被球探发现；表里的“可搜人数”是该赛季 7 月 1 日已满 16 岁的人数。\n")
    md.append("- 球探每周 13% 概率出结果；建议 9 级球探 + **深入搜索（20 周）**：至少出 1 人的概率约 94%。\n")
    md.append("- 排序默认按潜力（FIFA15–FC26 最高 Overall），潜力相同再看当前能力。\n")

    all_rows = []
    for season in SEASONS:
        pool = scoutable(rows, season)
        by_board = defaultdict(list)
        for r in pool:
            by_board[r["board"]].append(r)
        md.append(f"\n## {season} 赛季\n")
        md.append("| 板块 | 可搜人数 | 最高潜力 | 推荐 |\n|---|---:|---:|---|\n")
        for b in BOARDS:
            arr = sorted(by_board[b], key=lambda x: (-x["pot"], -x["cur"]))
            top = arr[0] if arr else None
            md.append(f"| {b} | {len(arr)} | {top['pot'] if top else 0} | {top['name'] if top else '-'} |\n")
        # top 8 new arrivals this season (became 16 since previous July 1)
        prev_cut = datetime.date(season - 17, 7, 1)
        arrivals = [r for r in pool if r["dob"] > prev_cut]
        arrivals = sorted(arrivals, key=lambda x: (-x["pot"], -x["cur"]))[:12]
        md.append(f"\n**{season} 新满 16 岁的高潜力球员（跨板块前 12）**\n")
        md.append("| 球员 | 板块 | 位置 | 生日 | 潜力 | 当前 | pid |\n|---|---|---|---|---:|---:|---:|\n")
        for r in arrivals:
            md.append(f"| {r['name']} | {r['board']} | {r['pos']} | {r['dob']} | {r['pot']} | {r['cur']} | {r['pid']} |\n")
        # top 6 per board, all scoutable
        md.append(f"\n**{season} 各板块可搜 Top 6（按潜力）**\n")
        for b in BOARDS:
            arr = sorted(by_board[b], key=lambda x: (-x["pot"], -x["cur"]))[:6]
            md.append(f"- **{b}**：" + "；".join(
                f"{r['name']}({r['pos'] or '?'}, 潜{r['pot']}, {r['dob'].year})" for r in arr) + "\n")
        # csv rows
        for b in BOARDS:
            arr = sorted(by_board[b], key=lambda x: (-x["pot"], -x["cur"]))
            for rank, r in enumerate(arr, 1):
                all_rows.append({"season": season, "board": b, "rank": rank,
                                 "scoutable_count": len(arr), "name": r["name"],
                                 "pid": r["pid"], "pos": r["pos"], "dob": r["dob"],
                                 "age": season - r["dob"].year, "potential": r["pot"],
                                 "current_first": r["cur"], "nat": r["nat"]})

    with open(guide_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        w.writeheader()
        w.writerows(all_rows)
    with open(os.path.join(OUT, "scout_guide.md"), "w", encoding="utf-8") as f:
        f.write("".join(md))
    print("wrote", guide_csv, "rows", len(all_rows))
    print("wrote", os.path.join(OUT, "scout_guide.md"))


if __name__ == "__main__":
    main()