#!/usr/bin/env python3
"""Rebuild the FA / DRAFT 60 pool section of index.html.

Pipeline (kept as separate stages so each is independently testable):

1. candidate generation -- union of every projected cut (parsed from the
   16 team-card <footer class="cuts"> blocks already committed in
   index.html) and every non-kept player in the live Yahoo 300-player
   fetch (local_data/yahoo/players_normalized.json), plus a small curated
   overlay of 2026 rookies/prospects that Yahoo's fetch does not carry.
2. metadata enrichment -- attach cap dollars, Yahoo O-Rank, position,
   NBA team from the most authoritative source available per player.
3. sorting -- CAP dollars descending is the only primary key. Yahoo
   O-Rank (ascending) is the tiebreak within a CAP tier where available;
   a small manual-relevance value (real 2026 draft pick number, lower is
   better) is the tiebreak for players missing an O-Rank. This guarantees
   CAP is strictly non-increasing top to bottom and that no dynasty/manual
   signal can ever promote a $0 player above a $1+ player.
4. truncation -- top 60 by the sort above, with a small guaranteed-name
   list (curated rookies + Paul Reed) force-included if they would
   otherwise fall outside the cut, then the final 60 is re-sorted so CAP
   ordering is never broken by the guarantee step.

This intentionally does NOT use dynasty consensus rankings as a sorting
input -- see the FA/DRAFT correction pack issue: dynasty/prospect bias
had pushed out established, relevant free agents (e.g. Paul Reed). This
board is cap-ordered with selective dynasty-aware candidate completion,
not a dynasty board.
"""
from __future__ import annotations

import html as html_lib
import json
import os
import re
import unicodedata
from dataclasses import dataclass

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
INDEX_HTML = os.path.join(REPO_ROOT, "index.html")
YAHOO_NORMALIZED = os.path.join(REPO_ROOT, "local_data", "yahoo", "players_normalized.json")

POOL_SIZE = 60
ROWS_PER_BLOCK = 20

# Curated overlay: 2026 draftees/prospects that must be reachable in the
# pool even when Yahoo's public 300-player fetch does not carry them.
# Position/NBA team verified against the actual 2026 NBA draft results
# (not a mock/projection -- the draft already happened this cycle).
# `pick` is the real draft slot, used only as a last-resort manual
# tiebreak among otherwise-unranked players; it is never allowed to
# outrank a player with a real Yahoo O-Rank or nonzero CAP.
CURATED_ROOKIE_OVERLAY = {
    "Cameron Boozer": dict(pos="PF", nba="MEM", pick=None),  # already in Yahoo fetch
    "Caleb Wilson": dict(pos="PF", nba="CHI", pick=None),  # already in Yahoo fetch
    "AJ Dybantsa": dict(pos="SF", nba="WAS", pick=None),  # already in Yahoo fetch
    "Darryn Peterson": dict(pos="SG", nba="UTA", pick=None),  # already in Yahoo fetch
    "Darius Acuff Jr.": dict(pos="PG", nba="SAC", pick=None),  # already in Yahoo fetch
    "Keaton Wagler": dict(pos="SG", nba="LAC", pick=5),  # already in Yahoo fetch
    "Mikel Brown Jr.": dict(pos="PG", nba="BKN", pick=None),  # already in Yahoo fetch
    "Kingston Flemings": dict(pos="PG", nba="ATL", pick=8),
    "Yaxel Lendeborg": dict(pos="PF", nba="GSW", pick=None),  # already in Yahoo fetch
    "Morez Johnson Jr.": dict(pos="PF", nba="DAL", pick=None),  # already in Yahoo fetch
    "Allen Graves": dict(pos="PF", nba="TOR", pick=19),
    "Meleek Thomas": dict(pos="SG", nba="CLE", pick=34),
    "Ebuka Okorie": dict(pos="PG", nba="DET", pick=17),
    "Brayden Burries": dict(pos="SG", nba="MIL", pick=None),  # already in Yahoo fetch
    "Aday Mara": dict(pos="C", nba="OKC", pick=12),
    "Hannes Steinbach": dict(pos="PF", nba="CHA", pick=14),  # already in Yahoo fetch (OR240)
    # Reviewed per the correction pack, included only if they clear the
    # CAP-first pool naturally (no forced-inclusion guarantee below).
    "Cameron Carr": dict(pos="SG", nba="LAL", pick=24),
    "Labaron Philon Jr.": dict(pos="PG", nba="PHI", pick=22),
}

# Curated names that MUST appear in the final 60 if they are not kept on
# a roster (forced-inclusion guarantee). Cameron Carr / Labaron Philon
# are deliberately excluded from this set per the correction pack --
# they're reviewed, not guaranteed.
GUARANTEED_NAMES = {n for n in CURATED_ROOKIE_OVERLAY if n not in ("Cameron Carr", "Labaron Philon Jr.")}
GUARANTEED_NAMES.add("Paul Reed")

# Cut players present on a team's cut list but absent from both the
# Yahoo 300 fetch and the curated overlay. Forced into the universe with
# conservative real-world metadata so "all projected cuts" is literal.
CONSERVATIVE_CUT_DEFAULTS = {
    "Jamir Watkins": dict(pos="SG/SF", nba="WAS"),
    "Chaney Johnson": dict(pos="PF", nba="BKN"),
    "Matisse Thybulle": dict(pos="SG/SF", nba="LAL"),
}

MISSING_OR = 9999
MISSING_PICK = 999


def normalize_name(name: str) -> str:
    name = html_lib.unescape(name)
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = name.replace("'", "").replace(".", "")
    name = re.sub(r"\s+(jr|sr|ii|iii|iv)$", "", name.strip().lower())
    name = re.sub(r"[^a-z0-9]+", " ", name).strip()
    return name


GUARANTEED_NAMES_NORM = {normalize_name(n) for n in GUARANTEED_NAMES}


@dataclass
class Candidate:
    name: str
    pos: str
    nba: str
    cap: float
    o_rank: int = MISSING_OR
    pick: int = MISSING_PICK
    rookie: bool = False
    src: str = "fa"  # "cut" | "fa" | "r"
    src_team: str = ""

    def sort_key(self):
        return (-self.cap, self.o_rank, self.pick, self.name)


def parse_team_cards(index_html: str):
    """Return (kept_names:set[norm], cuts:list[dict], team_short_by_block)."""
    kept = set()
    cuts = []
    for card in re.findall(r'<section class="team-card".*?</section>', index_html, re.S):
        short = re.search(r'<span class="identity-tag">([^<]*)</span>', card)
        short_name = html_lib.unescape(short.group(1)) if short else "?"

        for row in re.findall(r'<div class="player-row.*?</div></div>', card, re.S):
            name_m = re.search(r'<div class="pname">(.*?)</div>', row, re.S)
            if not name_m:
                continue
            raw_name = re.sub(r"<span.*?</span>", "", name_m.group(1)).strip()
            kept.add(normalize_name(raw_name))

        cuts_block = re.search(r'<div class="cuts-list">(.*?)</div></footer>', card, re.S)
        if cuts_block:
            for chip in re.findall(r'<span class="cut-chip">(.*?)</span>', cuts_block.group(1), re.S):
                cap_m = re.search(r"<strong>(\d+)</strong>", chip)
                cap_val = float(cap_m.group(1)) if cap_m else 0.0
                name_only = re.sub(r"<strong>.*?</strong>", "", chip).strip()
                cuts.append({"name": html_lib.unescape(name_only), "cap": cap_val, "team": short_name})

    return kept, cuts


def load_yahoo_players():
    with open(YAHOO_NORMALIZED, encoding="utf-8") as f:
        data = json.load(f)
    by_norm = {}
    for p in data:
        by_norm[normalize_name(p["name"])] = p
    return by_norm


SPECIFIC_POSITIONS = {"PG", "SG", "SF", "PF", "C"}


def pos_from_eligible(eligible):
    specific = [p for p in eligible if p in SPECIFIC_POSITIONS]
    return "/".join(specific) if specific else "F"


def build_candidates(index_html: str, yahoo_by_norm: dict):
    kept, cuts = parse_team_cards(index_html)

    candidates: dict[str, Candidate] = {}

    def add(cand: Candidate):
        key = normalize_name(cand.name)
        existing = candidates.get(key)
        if existing is None or (existing.src != "cut" and cand.src == "cut"):
            candidates[key] = cand

    # 1. all projected cuts
    for cut in cuts:
        key = normalize_name(cut["name"])
        yp = yahoo_by_norm.get(key)
        if yp is not None:
            add(Candidate(
                name=yp["name"], pos=pos_from_eligible(yp["eligiblePositions"]),
                nba=yp["nbaTeam"], cap=float(yp["capDollars"]), o_rank=int(yp["oRank"]),
                src="cut", src_team=cut["team"],
            ))
            continue
        overlay = CURATED_ROOKIE_OVERLAY.get(cut["name"])
        if overlay is not None:
            add(Candidate(
                name=cut["name"], pos=overlay["pos"], nba=overlay["nba"], cap=cut["cap"],
                pick=overlay["pick"] or MISSING_PICK, rookie=True, src="cut", src_team=cut["team"],
            ))
            continue
        fallback = CONSERVATIVE_CUT_DEFAULTS.get(cut["name"])
        if fallback is not None:
            add(Candidate(
                name=cut["name"], pos=fallback["pos"], nba=fallback["nba"], cap=cut["cap"],
                src="cut", src_team=cut["team"],
            ))
            continue
        # Unknown cut with no source at all: still force-include literally,
        # with only what the cut chip itself told us.
        add(Candidate(name=cut["name"], pos="", nba="", cap=cut["cap"], src="cut", src_team=cut["team"]))

    # 2. all non-kept Yahoo-ranked players
    for key, yp in yahoo_by_norm.items():
        if key in kept:
            continue
        if key in candidates:
            continue
        rookie = yp["name"] in CURATED_ROOKIE_OVERLAY
        add(Candidate(
            name=yp["name"], pos=pos_from_eligible(yp["eligiblePositions"]),
            nba=yp["nbaTeam"], cap=float(yp["capDollars"]), o_rank=int(yp["oRank"]),
            rookie=rookie, src="fa",
        ))

    # 3. curated overlay backfill for names Yahoo/cuts never produced
    for name, meta in CURATED_ROOKIE_OVERLAY.items():
        key = normalize_name(name)
        if key in kept or key in candidates:
            continue
        add(Candidate(
            name=name, pos=meta["pos"], nba=meta["nba"], cap=0.0,
            pick=meta["pick"] or MISSING_PICK, rookie=True, src="r",
        ))

    return candidates


def sort_and_truncate(candidates: dict):
    ordered = sorted(candidates.values(), key=lambda c: c.sort_key())
    top = ordered[:POOL_SIZE]
    top_keys = {normalize_name(c.name) for c in top}

    missing_guaranteed = [
        c for key in GUARANTEED_NAMES_NORM
        if (c := candidates.get(key)) is not None
        and key not in top_keys
    ]

    if missing_guaranteed:
        # Bump the lowest-priority non-guaranteed rows out, in reverse
        # sort order, to make room -- then the whole 60 gets re-sorted so
        # CAP ordering is unaffected by *where* the guarantee inserted.
        removable = [c for c in reversed(top) if normalize_name(c.name) not in GUARANTEED_NAMES_NORM]
        top_set = list(top)
        for extra in missing_guaranteed:
            if removable:
                drop = removable.pop(0)
                top_set.remove(drop)
            top_set.append(extra)
        top = sorted(top_set, key=lambda c: c.sort_key())[:POOL_SIZE]

    return top


SRC_HTML = {
    "cut": lambda c: f'<span class="src src-cut">{crown_prefix(c.src_team)}{html_lib.escape(c.src_team)}</span>',
    "fa": lambda c: '<span class="src src-fa">FA</span>',
    "r": lambda c: '<span class="src src-r">R</span>',
}

DEFENDING_CHAMPION_SHORT_NAME = "Đạt"
CROWN = "👑 "


def crown_prefix(short_name: str) -> str:
    return CROWN if short_name == DEFENDING_CHAMPION_SHORT_NAME else ""


def render_pool_html(ranked: list) -> str:
    blocks = []
    for start in range(0, len(ranked), ROWS_PER_BLOCK):
        chunk = ranked[start:start + ROWS_PER_BLOCK]
        rows = []
        for i, c in enumerate(chunk, start=start + 1):
            row_class = "pool-row rookie-row" if c.rookie else "pool-row"
            src_html = SRC_HTML[c.src](c)
            cap_display = str(int(c.cap)) if float(c.cap).is_integer() else str(c.cap)
            rows.append(
                f'<div class="{row_class}">'
                f'<div class="pool-rank">{i}</div>'
                f'<div class="pool-pos">{html_lib.escape(c.pos)}</div>'
                f'<div class="pool-player">{html_lib.escape(c.name)}</div>'
                f'<div class="pool-nba">{html_lib.escape(c.nba)}</div>'
                f'<div class="pool-cap">{cap_display}</div>'
                f'<div class="pool-src">{src_html}</div>'
                f'</div>'
            )
        head = '<div class="pool-head"><span>#</span><span>POS</span><span>PLAYER</span><span>NBA</span><span>CAP</span><span>SRC</span></div>'
        blocks.append(f'<section class="pool-block">{head}{"".join(rows)}</section>')
    return f'<div class="pool-grid">{"".join(blocks)}</div>'


POOL_GRID_END_ANCHOR = '<section class="page" id="cap">'


def _find_pool_grid_span(index_html: str) -> tuple[int, int]:
    """Return (start, end) of the full <div class="pool-grid">...</div></section>
    block. Anchored on the unique next-page marker rather than a bare
    "</div></section>" regex, since that substring also closes every
    individual pool-block and would otherwise match only the first one."""
    start = index_html.index('<div class="pool-grid">')
    end = index_html.index(POOL_GRID_END_ANCHOR, start)
    return start, end


def splice_pool_into_index(index_html: str, pool_html: str) -> str:
    start, end = _find_pool_grid_span(index_html)
    replacement = pool_html + "</section>"
    return index_html[:start] + replacement + index_html[end:]


def build(index_html: str) -> tuple[str, list]:
    yahoo_by_norm = load_yahoo_players()
    candidates = build_candidates(index_html, yahoo_by_norm)
    ranked = sort_and_truncate(candidates)
    pool_html = render_pool_html(ranked)
    new_html = splice_pool_into_index(index_html, pool_html)
    return new_html, ranked


def main():
    with open(INDEX_HTML, encoding="utf-8") as f:
        index_html = f.read()

    start, end = _find_pool_grid_span(index_html)
    before_names = {
        html_lib.unescape(n) for n in
        re.findall(r'<div class="pool-player">(.*?)</div>', index_html[start:end])
    }

    new_html, ranked = build(index_html)

    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(new_html)

    after_names = {c.name for c in ranked}
    entered = sorted(after_names - before_names)
    exited = sorted(before_names - after_names)

    print(f"FA/DRAFT 60 rebuilt: {len(ranked)} players")
    print(f"\nENTERED ({len(entered)}):")
    for n in entered:
        print(f"  + {n}")
    print(f"\nEXITED ({len(exited)}):")
    for n in exited:
        print(f"  - {n}")


if __name__ == "__main__":
    main()
