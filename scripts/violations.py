#!/usr/bin/env python3
"""Commissioner-recorded violations (`data/2026-27/violations.json`): read, validated, and handed to the page. Display only: nothing here
counts points, applies the Tank Violator ladder, or touches rosters, salaries, the Trade Lab, the draft or the ledger.

    load(path)          -> the list of records, each checked against the franchise ids
    page_view(records)  -> what the page needs (a record never carries more than its public wording)
"""
from __future__ import annotations

import datetime
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "2026-27", "violations.json")
KINDS = {"TANK_VIOLATION": "Tank violation"}
STATUSES = ("RECORDED", "WITHDRAWN")


class ViolationError(ValueError):
    pass


def load(franchise_ids, path=PATH) -> list:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    seen = set()
    for v in doc["violations"]:
        where = v.get("id", "?")
        if v["id"] in seen:
            raise ViolationError("%s: repeated id" % where)
        seen.add(v["id"])
        if v["franchiseId"] not in franchise_ids:
            raise ViolationError("%s: unknown franchise %s" % (where, v["franchiseId"]))
        if v["kind"] not in KINDS:
            raise ViolationError("%s: unknown kind %s" % (where, v["kind"]))
        if v["status"] not in STATUSES:
            raise ViolationError("%s: unknown status %s" % (where, v["status"]))
        if not isinstance(v["week"], int) or not 1 <= v["week"] <= 20:
            raise ViolationError("%s: week must be 1-20" % where)
        if v.get("points") is not None and not (isinstance(v["points"], int) and v["points"] >= 0):
            raise ViolationError("%s: points must be null or a whole number" % where)
        for e in v.get("evidence") or []:
            try:
                datetime.date.fromisoformat(e["date"])
            except (KeyError, ValueError):
                raise ViolationError("%s: evidence needs an ISO date" % where)
        if re.search(r"\$", json.dumps(v, ensure_ascii=False)):
            raise ViolationError("%s: no dollar signs in league text" % where)
    return doc["violations"]


def page_view(records) -> list:
    """Withdrawn records are kept in the file for history and not shown."""
    return [{"id": v["id"], "team": v["franchiseId"], "kind": v["kind"], "label": KINDS[v["kind"]], "week": v["week"], "summary": v["summary"],
             "detail": v["detail"], "evidence": [{k: e.get(k) for k in ("date", "player", "slot", "status")} for e in v.get("evidence") or []],
             "points": v.get("points"), "pointsNote": v.get("pointsNote"), "priorWarnings": v.get("priorWarnings")}
            for v in records if v["status"] == "RECORDED"]
