#!/usr/bin/env python3
"""The season's head-to-head pairings (who plays whom in each of the regular-season weeks; the playoffs are seeded later), stored as plain pairs of Yahoo team ids.

Finished weeks come from the stored results (`data/2026-27/matchups`); the current and future weeks are learned from the same matchup
pages (`yahoo_matchups`, a week with no stats prints `-/-`). Schedule metadata only: no stats, no ownership, nothing the Trade Lab,
draft or ledger reads. `python3 scripts/update_yahoo_matchups.py --schedule [--apply]` fills it.

    pairs(week_doc)            -> sorted [[teamId, teamId], ...] of one parsed or stored week
    build(by_week, cfg, at)    -> the document written to data/2026-27/schedule.json
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = "yahoo-schedule/1"
SCHEDULE_PATH = os.path.join(ROOT, "data", "2026-27", "schedule.json")


def regular_weeks(cfg) -> int:
    """Weeks with fixed pairings. The playoff weeks (config playoffs.weeks) are seeded from the standings, so Yahoo lists no opponent yet."""
    return min(cfg["playoffs"]["weeks"]) - 1


def pairs(doc) -> list:
    """The pairings of a stored week (`matchups[].teams[]`) or a list of parsed pages (`[].teams[]`), as sorted id pairs."""
    games = doc["matchups"] if isinstance(doc, dict) else doc
    return sorted(sorted(int(t["teamId"]) for t in g["teams"]) for g in games)


def check(by_week: dict, cfg: dict) -> list:
    """Problems that make a schedule untrustworthy: a week missing, a team twice or absent in a week, a team playing itself."""
    bad, want = [], sorted(cfg["teamIds"])
    for w in range(1, regular_weeks(cfg) + 1):
        if w not in by_week:
            bad.append("week %d has no pairings" % w)
            continue
        ids = sorted(i for p in by_week[w] for i in p)
        if ids != want or any(a == b for a, b in by_week[w]):
            bad.append("week %d does not pair every team exactly once" % w)
    return bad


def build(by_week: dict, cfg: dict, captured_at: str, source: str = "Yahoo public matchup pages") -> dict:
    return {"schema": SCHEMA, "season": cfg.get("season"), "leagueId": str(cfg["leagueId"]), "capturedAt": captured_at, "source": source,
            "weeks": {str(w): by_week[w] for w in sorted(by_week)}}


def load(path=SCHEDULE_PATH) -> dict:
    """{week: [[a, b], ...]} from the stored file, or {} when there is none yet."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return {int(w): p for w, p in json.load(f)["weeks"].items()}


def commit(doc: dict, path=SCHEDULE_PATH) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)
    return path
