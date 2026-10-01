#!/usr/bin/env python3
"""Mechanically refresh each KEPT player's Yahoo-governed display fields
(position, NBA team, cap dollars) in index.html's keeper board, and each
CUT player's Yahoo-sourced name/cap in the same team-card's cuts-list.

This is a display-only refresh against a Yahoo normalized-players
snapshot: it NEVER adds, removes, or reorders a player row, and never
moves a player between kept/cut or between teams. Which players are
kept is a human/discretionary decision (see CLAUDE.md's human-decision
boundary) and this script does not touch it -- it only updates the
Yahoo-authoritative fields (see docs/YAHOO_DATA_SOURCE.md) on a row/chip
that is already there, and only for a player the snapshot actually
covers. A player missing from the live fetch keeps its last known
display values unchanged, same policy as the historical manual refresh
(see ai_exchange/CURRENT_STATE.json canonicalState.lastYahooRefresh).

Cut chips are also re-sorted CAP descending (Yahoo O-Rank ascending
tiebreak) after refreshing, and use Yahoo's current display name when
available -- e.g. a player Yahoo now lists as "X Jr." instead of "X"
is still the same person, not a new/duplicate entry (see
CUT_CHIP_RE in build_fa_draft_pool.py for the identity-matching rule
this relies on).

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
from build_fa_draft_pool import CUT_CHIP_RE, MISSING_OR, normalize_name, pos_from_eligible  # noqa: E402

PLAYER_ROW_RE = re.compile(
    r'(<div class="player-row[^"]*"><div class="pos">)([^<]*)'
    r'(</div><div class="pname">)(.*?)(</div><div class="nba">)([^<]*)'
    r'(</div><div class="cap">)([^<]*)(</div></div>)',
    re.S,
)

CUTS_LIST_RE = re.compile(r'(<div class="cuts-list">)(.*?)(</div></footer>)', re.S)
HEALTH_BADGE_RE = re.compile(r'<span class="health-badge[^>]*>[^<]*</span>')


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


def _parse_chip(chip_inner: str):
    """Split a cut-chip's captured inner content into (name, cap, health_badge_html)."""
    badge_m = HEALTH_BADGE_RE.search(chip_inner)
    badge_html = badge_m.group(0) if badge_m else ""
    without_badge = HEALTH_BADGE_RE.sub("", chip_inner)
    cap_m = re.search(r"<strong>(\d+)</strong>", without_badge)
    cap_val = float(cap_m.group(1)) if cap_m else 0.0
    name = re.sub(r"<strong>.*?</strong>", "", without_badge).strip()
    return html_lib.unescape(name), cap_val, badge_html


def _render_chip(name: str, cap: float, badge_html: str) -> str:
    cap_part = f" <strong>{_cap_display(cap)}</strong>" if cap else ""
    return f'<span class="cut-chip">{html_lib.escape(name)}{badge_html}{cap_part}</span>'


def refresh_cut_chips(index_html: str, yahoo_by_norm: dict) -> tuple[str, int]:
    """Return (new_html, chips_updated). Never adds, removes, or moves a
    cut between teams -- same roster-membership boundary as
    refresh_keeper_board. Only refreshes each existing cut's Yahoo-sourced
    name/cap (falling back to its last known values when Yahoo has no data
    for it, same as a kept row), then re-sorts each team's chips CAP
    descending (Yahoo O-Rank ascending tiebreak, original order last)."""
    updated = 0

    def repl_cuts_list(match: re.Match) -> str:
        nonlocal updated
        prefix, body, suffix = match.groups()
        chips = []
        for i, chip_inner in enumerate(CUT_CHIP_RE.findall(body)):
            name, cap, badge_html = _parse_chip(chip_inner)
            o_rank = MISSING_OR
            yp = yahoo_by_norm.get(normalize_name(name))
            if yp is not None:
                new_name = yp["name"]
                new_cap = float(yp["capDollars"])
                o_rank = int(yp["oRank"])
                if new_name != name or new_cap != cap:
                    updated += 1
                name, cap = new_name, new_cap
            chips.append((name, cap, badge_html, o_rank, i))

        chips.sort(key=lambda c: (-c[1], c[3], c[4]))
        new_body = "".join(_render_chip(name, cap, badge_html) for name, cap, badge_html, _, _ in chips)
        return f"{prefix}{new_body}{suffix}"

    new_html = CUTS_LIST_RE.sub(repl_cuts_list, index_html)
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

    new_html, kept_updated = refresh_keeper_board(index_html, yahoo_by_norm)
    new_html, cuts_updated = refresh_cut_chips(new_html, yahoo_by_norm)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(new_html)

    if args.stats_out:
        os.makedirs(os.path.dirname(args.stats_out) or ".", exist_ok=True)
        with open(args.stats_out, "w", encoding="utf-8") as f:
            json.dump({
                "keptPlayerRowsUpdated": kept_updated,
                "cutChipsUpdated": cuts_updated,
            }, f, indent=2)

    print(
        f"Keeper board display refresh: {kept_updated} kept player row(s), "
        f"{cuts_updated} cut chip(s) updated"
    )


if __name__ == "__main__":
    main()
