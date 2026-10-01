#!/usr/bin/env python3
"""Mechanically refresh each KEPT player's Yahoo-governed display fields
(position, NBA team, cap dollars) in index.html's keeper board.

This is a display-only refresh against a Yahoo normalized-players
snapshot: it NEVER adds, removes, or reorders a player row. Which
players are kept is a human/discretionary decision (see CLAUDE.md's
human-decision boundary) and this script does not touch it -- it only
updates the three Yahoo-authoritative fields (see
docs/YAHOO_DATA_SOURCE.md) on a row that is already there, and only for
a kept player the snapshot actually covers. A kept player missing from
the live fetch keeps its last known display values unchanged, same
policy as the historical manual refresh (see
ai_exchange/CURRENT_STATE.json canonicalState.lastYahooRefresh).

Reuses build_fa_draft_pool.normalize_name/pos_from_eligible rather than
re-deriving name-matching or position-collapsing logic.

Standard library only.

Usage:
    python3 scripts/refresh_keeper_board_display.py \
        --index-html index.html \
        --yahoo-players local_data/yahoo/players_normalized.json \
        --output index.html \
        [--stats-out artifacts/yahoo-refresh/keeper_board_stats.json]
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from build_fa_draft_pool import normalize_name, pos_from_eligible  # noqa: E402

PLAYER_ROW_RE = re.compile(
    r'(<div class="player-row[^"]*"><div class="pos">)([^<]*)'
    r'(</div><div class="pname">)(.*?)(</div><div class="nba">)([^<]*)'
    r'(</div><div class="cap">)([^<]*)(</div></div>)',
    re.S,
)


def _cap_display(value) -> str:
    value = float(value)
    return str(int(value)) if value.is_integer() else str(value)


def refresh_keeper_board(index_html: str, yahoo_by_norm: dict) -> tuple[str, int]:
    """Return (new_html, rows_updated). A row counts as updated only when
    at least one of pos/nba/cap actually differs from the live snapshot."""
    updated = 0

    def repl(match: re.Match) -> str:
        nonlocal updated
        pre_pos, pos, pre_name, name_html, pre_nba, nba, pre_cap, cap, tail = match.groups()
        raw_name = re.sub(r"<span.*?</span>", "", name_html).strip()
        key = normalize_name(html_lib.unescape(raw_name))
        yp = yahoo_by_norm.get(key)
        if yp is None:
            return match.group(0)

        new_pos = pos_from_eligible(yp["eligiblePositions"])
        new_nba = yp["nbaTeam"]
        new_cap = _cap_display(yp["capDollars"])

        if new_pos == pos and new_nba == nba and new_cap == cap:
            return match.group(0)

        updated += 1
        return (
            f"{pre_pos}{html_lib.escape(new_pos)}{pre_name}{name_html}"
            f"{pre_nba}{html_lib.escape(new_nba)}{pre_cap}{new_cap}{tail}"
        )

    new_html = PLAYER_ROW_RE.sub(repl, index_html)
    return new_html, updated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-html", required=True)
    parser.add_argument("--yahoo-players", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stats-out", default=None)
    args = parser.parse_args()

    with open(args.index_html, encoding="utf-8") as f:
        index_html = f.read()

    with open(args.yahoo_players, encoding="utf-8") as f:
        yahoo_players = json.load(f)
    yahoo_by_norm = {normalize_name(p["name"]): p for p in yahoo_players}

    new_html, updated = refresh_keeper_board(index_html, yahoo_by_norm)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(new_html)

    if args.stats_out:
        os.makedirs(os.path.dirname(args.stats_out) or ".", exist_ok=True)
        with open(args.stats_out, "w", encoding="utf-8") as f:
            json.dump({"keptPlayerRowsUpdated": updated}, f, indent=2)

    print(f"Keeper board display refresh: {updated} player row(s) updated")


if __name__ == "__main__":
    main()
