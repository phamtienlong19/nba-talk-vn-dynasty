#!/usr/bin/env python3
"""Mechanically recompute each team's cap total / floor-ceiling gap in
index.html from its own kept-player rows -- both where it's shown on each
team-card header (.cap-box/.cap-total/.gap-big) and on the dedicated CAP
page (.cap-card/.cap-num/.cap-gap). Both places are driven by the SAME
computed total per team, so they can never drift from each other.

This is pure arithmetic over numbers already on the board (the sum of a
team's own already-displayed kept-player .cap values) plus the current
floor/ceiling -- it makes no roster/keeper-selection decision and reads
no external data source itself. It does not touch which players are
kept (see refresh_keeper_board_display.py for that boundary).

Three regimes, matching the two text conventions already on the board
("<N> ROOM", "<N> TO FLOOR") plus the CSS class gap-zero that already
existed (background/color only) but had never been used because no
team had ever reached/exceeded the ceiling before:

    total < floor            -> gap-floor, "<floor-total> TO FLOOR"
    floor <= total <= ceiling -> gap-room / gap-near, "<room> ROOM"
                                 (gap-near when room <= NEAR_THRESHOLD --
                                 inferred from the board's own existing
                                 near/room split, not independently
                                 documented anywhere; see NEAR_THRESHOLD)
    total > ceiling           -> gap-zero, "<total-ceiling> OVER" (new
                                 wording -- no prior board state ever hit
                                 this regime, so there was no existing
                                 convention to preserve)

Standard library only.

Usage:
    python3 scripts/refresh_team_cap_summary.py \
        --index-html index.html \
        --floor 130 --ceiling 176 \
        --output index.html \
        [--stats-out artifacts/yahoo-refresh/cap_summary_stats.json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from build_fa_draft_pool import CROWN  # noqa: E402

# Inferred from the board's own pre-existing near/room split (see the
# module docstring): observed gap-near values were {1, 2, 4}, observed
# gap-room values were {6, 7, 8, ...} -- the true cutoff could be 4 or 5;
# this picks the more conservative (evidence-backed) of the two. Purely
# cosmetic/presentational -- never affects a total, a legality check, or
# a roster decision.
NEAR_THRESHOLD = 4

TEAM_CARD_RE = re.compile(r'<section class="team-card.*?</section>', re.S)
IDENTITY_TAG_RE = re.compile(r'<span class="identity-tag">([^<]*)</span>')
PLAYER_CAP_RE = re.compile(r'<div class="player-row[^"]*">.*?<div class="cap">([\d.]+)</div></div>', re.S)

CAP_BOX_RE = re.compile(
    r'(<div class="cap-box )([a-z-]+)(">\s*<div class="cap-total">)(\d+(?:\.\d+)?)'
    r'(<span>/)(\d+)(</span></div>\s*<div class="gap-big">)([^<]*)(</div>\s*</div>)',
    re.S,
)

CAP_CARD_RE = re.compile(
    r'(<div class="cap-card )([a-z-]+)("[^>]*>\s*<div class="cap-team">.*?<b>)([^<]*)'
    r'(</b>.*?<div class="cap-num">)(\d+(?:\.\d+)?)(<span>/)(\d+)'
    r'(</span></div><div class="cap-gap">)([^<]*)(</div></div>)',
    re.S,
)


def _fmt(value: float) -> str:
    value = float(value)
    return str(int(value)) if value.is_integer() else str(value)


def classify_cap(total: float, floor: int, ceiling: int) -> tuple[str, str]:
    if total < floor:
        return "gap-floor", f"{_fmt(floor - total)} TO FLOOR"
    room = ceiling - total
    if room < 0:
        return "gap-zero", f"{_fmt(-room)} OVER"
    if room <= NEAR_THRESHOLD:
        return "gap-near", f"{_fmt(room)} ROOM"
    return "gap-room", f"{_fmt(room)} ROOM"


def _team_totals(index_html: str) -> dict:
    totals = {}
    for card in TEAM_CARD_RE.findall(index_html):
        tag = IDENTITY_TAG_RE.search(card).group(1)
        totals[tag] = sum(float(c) for c in PLAYER_CAP_RE.findall(card))
    return totals


def refresh_team_cap_summary(index_html: str, floor: int, ceiling: int) -> tuple[str, dict]:
    """Return (new_html, {team_tag: {"total": .., "class": .., "text": ..}})."""
    totals = _team_totals(index_html)
    summary = {tag: dict(zip(("class", "text"), classify_cap(total, floor, ceiling)), total=total)
               for tag, total in totals.items()}

    def repl_card(m: re.Match) -> str:
        card = m.group(0)
        tag = IDENTITY_TAG_RE.search(card).group(1)
        info = summary[tag]

        def repl_box(bm: re.Match) -> str:
            pre1, _old_cls, pre2, _old_total, pre3, _old_ceil, pre4, _old_text, suf = bm.groups()
            return f"{pre1}{info['class']}{pre2}{_fmt(info['total'])}{pre3}{ceiling}{pre4}{info['text']}{suf}"

        return CAP_BOX_RE.sub(repl_box, card, count=1)

    new_html = TEAM_CARD_RE.sub(repl_card, index_html)

    def repl_cap_card(m: re.Match) -> str:
        pre1, _old_cls, pre2, tag_html, pre3, _old_total, pre4, _old_ceil, pre5, _old_text, suf = m.groups()
        plain_tag = tag_html[len(CROWN):] if tag_html.startswith(CROWN) else tag_html
        info = summary[plain_tag]
        return f"{pre1}{info['class']}{pre2}{tag_html}{pre3}{_fmt(info['total'])}{pre4}{ceiling}{pre5}{info['text']}{suf}"

    new_html = CAP_CARD_RE.sub(repl_cap_card, new_html)

    return new_html, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-html", required=True)
    parser.add_argument("--floor", type=int, required=True)
    parser.add_argument("--ceiling", type=int, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stats-out", default=None)
    args = parser.parse_args()

    with open(args.index_html, encoding="utf-8") as f:
        index_html = f.read()

    new_html, summary = refresh_team_cap_summary(index_html, args.floor, args.ceiling)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(new_html)

    if args.stats_out:
        os.makedirs(os.path.dirname(args.stats_out) or ".", exist_ok=True)
        with open(args.stats_out, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

    over = {tag: info for tag, info in summary.items() if info["class"] == "gap-zero" and "OVER" in info["text"]}
    print(f"Team cap summary refreshed for {len(summary)} teams against {args.floor}/{args.ceiling}")
    if over:
        print("OVER CEILING (needs commissioner review, not auto-fixed):")
        for tag, info in over.items():
            print(f"  {tag}: {_fmt(info['total'])}/{args.ceiling} ({info['text']})")


if __name__ == "__main__":
    main()
