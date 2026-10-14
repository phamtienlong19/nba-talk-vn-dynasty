#!/usr/bin/env python3
"""Idempotently import confirmed draft selections into data/2026-27/draft_state.json.

    python3 scripts/import_draft_results.py            # reads data/2026-27/draft_results.json

Names are resolved against the Yahoo player master (stable playerKey); the selecting franchise is the CURRENT owner
of the pick in the OFFICIAL post-trade ledger (never the original slot holder). Re-running changes nothing. A record
that contradicts an existing selection, repeats a player, jumps the draft order, or targets a held pick is rejected.
Standard library only.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_fa_draft_pool as pool  # noqa: E402
import league_state as ls  # noqa: E402

RESULTS_PATH = os.path.join(ls.DATA_DIR, "draft_results.json")
STATE_PATH = os.path.join(ls.DATA_DIR, "draft_state.json")
NAME_ALIASES: dict = {}  # normalized result name -> normalized registry name (none needed so far)


class ImportError_(ValueError):
    pass


def resolve_name(registry: dict, name: str) -> dict:
    idx: dict = {}
    for p in registry.values():
        idx.setdefault(pool.normalize_name(p["name"]), []).append(p)
    key = pool.normalize_name(name)
    key = NAME_ALIASES.get(key, key)
    hits = idx.get(key, [])
    if len(hits) != 1:
        raise ImportError_(f"cannot uniquely resolve {name!r} in the player master ({len(hits)} matches)")
    return hits[0]


def build_events(inputs: dict, results: dict, existing: list) -> list:
    """Return the full, ordered event list = existing events + any new ones (idempotent)."""
    # ownership is read from the official ledger WITHOUT draft events, so the owner is the post-trade holder
    bare = dict(inputs)
    bare["draft"] = {**inputs["draft"], "events": []}
    state = ls.resolve(bare, (), "OFFICIAL")
    order = [p["pickId"] for p in sorted(inputs["picks"]["picks"], key=lambda p: (p["round"], p["slot"]))]
    by_pick = {e["pickId"]: e for e in existing}
    held = {h["pickId"] for h in ls.active_holds(inputs)}
    seen_players = {e["playerKey"]: e["pickId"] for e in existing}
    new = []
    for i, r in enumerate(results["results"]):
        pid = r["pickId"]
        if i >= len(order):
            raise ImportError_(f"more results than draft slots ({len(order)})")
        if pid != order[i]:
            raise ImportError_(f"results must follow the draft order: position {i + 1} is {order[i]}, got {pid}")
        player = resolve_name({**inputs["registry"], **inputs["extraPlayers"]}, r["player"])
        key = player["playerKey"]
        if pid in by_pick:
            if by_pick[pid]["playerKey"] != key:
                raise ImportError_(f"{pid} already records {by_pick[pid]['playerKey']}, not {r['player']} ({key})")
            continue
        if pid in held:
            raise ImportError_(f"{pid} is on commissioner hold; cannot record its selection")
        if key in seen_players:
            raise ImportError_(f"{r['player']} was already selected at {seen_players[key]}")
        seen_players[key] = pid
        owner = state["pickOwner"][pid]
        new.append({"eventId": f"DRAFT-{pid}", "type": "DRAFT_PICK", "pickId": pid, "franchiseId": owner,
                    "playerKey": key, "rookie": bool(r.get("rookie")), "source": "commissioner-confirmed draft results"})
    events = sorted(existing + new, key=lambda e: order.index(e["pickId"]))
    # the recorded selections must be one contiguous run from pick 1.01 (no skipped slot)
    done = [e["pickId"] for e in events]
    if done != order[:len(done)]:
        raise ImportError_(f"recorded selections are not a contiguous run from {order[0]}: {done}")
    return events


def main():
    inputs = ls.load_inputs()
    results = ls._load(RESULTS_PATH)
    state = ls._load(STATE_PATH)
    events = build_events(inputs, results, state.get("events", []))
    added = len(events) - len(state.get("events", []))
    state["events"] = events
    state["status"] = "IN_PROGRESS" if events else "PRE_DRAFT"
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"draft_state: {len(events)} selections ({added} new)")


if __name__ == "__main__":
    try:
        main()
    except ImportError_ as e:
        print(f"IMPORT REJECTED: {e}", file=sys.stderr)
        sys.exit(1)
