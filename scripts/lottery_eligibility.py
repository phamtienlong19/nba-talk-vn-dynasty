#!/usr/bin/env python3
"""Who is eligible for the top of a draft: the commissioner's top-2 and number-one rules (config/draft_lottery_rules.json).

    python3 scripts/lottery_eligibility.py            # eligibility for the next three drafts
    python3 scripts/lottery_eligibility.py 2028       # one draft

Pure derivation from the recorded history: it reports which teams CANNOT pick 1st, or 1st/2nd, in a draft and why. It does
not model the lottery, and it cannot know picks that have not happened yet: a later draft's answer is "as of the recorded
history" and must be recomputed after each draft. Standard library only.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = os.path.join(ROOT, "config", "draft_lottery_rules.json")


def load(path: str = RULES) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def eligibility(cfg: dict, draft: int) -> dict:
    """-> {franchiseId: {"canPick1": bool, "canPickTop2": bool, "reasons": [...]}} for teams with a restriction.
    Teams absent from the result have none (as of the recorded history)."""
    r = cfg["rules"]
    top2, span = r["noTop2TwiceInARow"], r["oneNumberOnePerWindow"]
    out: dict = {}

    def mark(fid, key, why):
        e = out.setdefault(fid, {"canPick1": True, "canPickTop2": True, "reasons": []})
        e[key] = False
        e["reasons"].append(why)
        if key == "canPickTop2":
            e["canPick1"] = False  # not eligible for the top two means not eligible for 1st either

    for h in cfg["history"]:
        d = h["draft"]
        if d >= draft:
            continue
        for slot, fid in ((1, h.get("slot1")), (2, h.get("slot2"))):
            if not fid:
                continue
            if d == draft - 1 and slot in top2["slots"]:
                mark(fid, "canPickTop2", f"picked {'1st' if slot == 1 else '2nd'} in {d}: no top-2 pick in {draft}")
            if slot == span["slot"] and draft - d < span["windowDrafts"]:
                mark(fid, "canPick1", f"picked 1st in {d}: only one number-one pick in any {span['windowDrafts']}-year span "
                                      f"(not eligible for 1st through {d + span['windowDrafts'] - 1})")
    return out


def main(argv=None) -> int:
    args = (argv if argv is not None else sys.argv[1:])
    cfg = load()
    last = max(h["draft"] for h in cfg["history"])
    drafts = [int(args[0])] if args else [last + 1, last + 2, last + 3]
    names = {}
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import league_state as ls
        names = ls.load_inputs()["shorts"]
    except Exception:  # noqa: BLE001
        pass
    print(f"history recorded through {last}; later drafts are 'as of now' and change after each draft")
    for d in drafts:
        e = eligibility(cfg, d)
        print(f"\n{d} draft")
        if not e:
            print("  no restrictions")
        for fid, v in sorted(e.items()):
            label = "cannot pick 1st or 2nd" if not v["canPickTop2"] else "can pick 2nd, cannot pick 1st"
            print(f"  {names.get(fid, fid):9} {label} -- " + "; ".join(v["reasons"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
