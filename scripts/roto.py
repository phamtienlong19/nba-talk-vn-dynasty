#!/usr/bin/env python3
"""Roto points, ranks and all-play from one week's category totals of every team (display only; the league is head-to-head).

Roto: in each of the nine categories the 16 teams are ranked and the worst gets 1 point, the best 16 (fewer turnovers is better); teams that
are level share the average of the places they cover (two at the bottom: 1.5 each). A team's roto score is the sum over the categories; the
rank is a competition rank (two teams on 67.5 are both 11th). All-play: every team against every other, category by category, as if it had
played them all that week. Percentages compare as exact fractions, so equal percentages tie.

Input: {teamId: stats} with stats shaped like the live feed's: fg [made, att], ft [made, att], tpm, pts, reb, ast, st, blk, to.
`scripts/live_roto.js` is the page's port of this file; tests/test_roto.py holds both to the same fixture.
"""
from __future__ import annotations

import os
import sys
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yahoo_matchups as ym  # noqa: E402

CATS = ym.CATEGORIES                                              # (key, label, fewer_is_better)


def value(stats, key):
    """The category value as an exact number; None when there is nothing to compare yet (no attempts, no data)."""
    if key in ("fgPct", "ftPct"):
        m, a = (stats.get("fg") if key == "fgPct" else stats.get("ft")) or (None, None)
        return Fraction(m, a) if a else None
    v = stats.get(key)
    return None if v is None else Fraction(v)


def _places(values, lower):
    """{index: points} for a list of comparable values: 1 for the worst ... n for the best, ties averaged."""
    order = sorted(range(len(values)), key=lambda i: values[i], reverse=lower)       # worst first (the largest turnover count is worst)
    out, i = {}, 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in order[i:j + 1]:
            out[k] = (i + 1 + j + 1) / 2
        i = j + 1
    return out


def roto(stats_by_team: dict) -> dict:
    """-> {teamId: {"points": {cat: pts}, "total": n, "rank": r}}; every team gets points in a category only when all teams have a value."""
    ids = sorted(stats_by_team)
    res = {t: {"points": {}, "total": 0.0} for t in ids}
    for key, _label, lower in CATS:
        vals = [value(stats_by_team[t], key) for t in ids]
        if any(v is None for v in vals):
            for t in ids:
                res[t]["points"][key] = None
            continue
        for k, pts in _places(vals, lower).items():
            res[ids[k]]["points"][key] = pts
            res[ids[k]]["total"] += pts
    for t in ids:
        res[t]["rank"] = 1 + sum(1 for u in ids if res[u]["total"] > res[t]["total"])
    return res


def head_to_head(a: dict, b: dict) -> dict:
    """a against b: category wins, losses, ties, the margin (wins minus losses) and the nine winners (1 a, -1 b, 0 level)."""
    w = l = t = 0
    detail = {}
    for key, _label, lower in CATS:
        x, y = value(a, key), value(b, key)
        if x is None or y is None:
            detail[key] = None
            continue
        if x == y:
            t += 1
            detail[key] = 0
        elif (x < y) == lower:
            w += 1
            detail[key] = 1
        else:
            l += 1
            detail[key] = -1
    return {"w": w, "l": l, "t": t, "margin": w - l, "detail": detail}


def all_play(stats_by_team: dict) -> dict:
    """-> {"cells": {rowTeam: {colTeam: h2h}}, "record": {teamId: [W, L, T]}} where a cell is won with more category wins."""
    ids = sorted(stats_by_team)
    cells = {a: {b: head_to_head(stats_by_team[a], stats_by_team[b]) for b in ids if b != a} for a in ids}
    record = {}
    for a in ids:
        wlt = [0, 0, 0]
        for c in cells[a].values():
            wlt[0 if c["margin"] > 0 else 1 if c["margin"] < 0 else 2] += 1
        record[a] = wlt
    return {"cells": cells, "record": record}
