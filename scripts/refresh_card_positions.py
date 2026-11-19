#!/usr/bin/env python3
"""Keep the position and NBA team shown on each team card's player rows in step with the Yahoo player registry.

The registry (data/yahoo/player_registry.json) is refreshed daily, but the team cards in index.html are static markup that only the manual
promote-yahoo-refresh.sh used to touch, so a player's new eligibility (e.g. PG/SG -> PG/SG/SF) showed in the data and the Trade Lab but not on the card.
This changes ONLY the position and NBA team text of rows that already exist. It never touches cap dollars, never adds, removes, moves or re-sorts a
player (cap and roster membership stay human decisions; see CLAUDE.md).

    python3 scripts/refresh_card_positions.py [--registry PATH] [--index-html PATH] [--check]
"""
import argparse
import html as html_lib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_fa_draft_pool import normalize_name, pos_from_eligible  # noqa: E402

ROW = re.compile(r'(<div class="player-row[^"]*"><div class="pos">)([^<]*)(</div><div class="pname">)(.*?)(</div><div class="nba">)([^<]*)(</div>)', re.S)


def refresh(index_html, registry_players):
    by_name = {}
    for p in registry_players:
        by_name.setdefault(normalize_name(p["name"]), p)
    changed = []

    def repl(m):
        pre, pos, mid, name_html, mid2, nba, tail = m.groups()
        name = html_lib.unescape(re.sub(r"<span.*?</span>", "", name_html)).strip()
        p = by_name.get(normalize_name(name))
        if p is None or not p.get("eligiblePositions"):
            return m.group(0)
        new_pos, new_nba = pos_from_eligible(p["eligiblePositions"]), p.get("nbaTeam") or nba
        if (new_pos, new_nba) == (pos, nba):
            return m.group(0)
        changed.append((name, pos, new_pos, nba, new_nba))
        return pre + html_lib.escape(new_pos) + mid + name_html + mid2 + html_lib.escape(new_nba) + tail

    return ROW.sub(repl, index_html), changed


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--registry", default=os.path.join(HERE, "..", "data", "yahoo", "player_registry.json"))
    ap.add_argument("--index-html", default=os.path.join(HERE, "..", "index.html"))
    ap.add_argument("--check", action="store_true", help="report only; exit 1 if a card is out of date")
    a = ap.parse_args()
    with open(a.registry, encoding="utf-8") as f:
        players = json.load(f)["players"]
    with open(a.index_html, encoding="utf-8") as f:
        page = f.read()
    new, changed = refresh(page, players)
    for n, p0, p1, t0, t1 in changed:
        print(f"{n}: {p0} {t0} -> {p1} {t1}")
    print(f"{len(changed)} card row(s) {'out of date' if a.check else 'updated'}")
    if a.check:
        sys.exit(1 if changed else 0)
    if changed:
        with open(a.index_html, "w", encoding="utf-8") as f:
            f.write(new)


if __name__ == "__main__":
    main()
