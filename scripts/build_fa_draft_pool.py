#!/usr/bin/env python3
"""Rebuild the FA / DRAFT 60 pool section of index.html.

Pipeline (kept as separate stages so each is independently testable):

1. candidate generation -- union of every projected cut (parsed from the
   16 team-card <footer class="cuts"> blocks already committed in
   index.html) and every non-kept player in the live Yahoo 300-player
   fetch (local_data/yahoo/players_normalized.json), plus a small curated
   overlay of 2026 rookies/prospects that Yahoo's fetch does not carry.
2. metadata enrichment -- attach cap dollars, O-Rank, position, NBA team
   from the most authoritative source available per player. For a
   curated rookie/prospect Yahoo does not rank at all, a real dynasty
   rookie rank is converted to an O-Rank-scale proxy (calibrated against
   the curated names that DO have both a dynasty rank and a real Yahoo
   O-Rank -- see _fit_dynasty_or_scale) so it can compete on the same
   tiebreak axis as everyone else, rather than being dumped below every
   Yahoo-ranked player regardless of how good the rookie actually is.
3. sorting -- CAP dollars descending is the only primary key. Within a
   CAP tier, the tiebreak is a 50/50 blend (Candidate.blend_score) of
   live Yahoo O-Rank and a crowdsourced dynasty consensus rank (see
   data/dynasty/, built by scripts/build_dynasty_consensus.py from
   multiple independent dynasty-ranking sources). This guarantees CAP
   is strictly non-increasing top to bottom and that no dynasty/manual
   signal can ever promote a $0 player above a $1+ player -- but within
   a tier, a legitimately well-regarded rookie or dynasty asset CAN
   outrank a mediocre win-now-only veteran.
4. truncation -- top 60 by the sort above, with a small guaranteed-name
   list (curated rookies + Paul Reed) force-included if they would
   otherwise fall outside the cut, then the final 60 is re-sorted so CAP
   ordering is never broken by the guarantee step.

CAP is the only strict/primary sort key -- see the FA/DRAFT correction
pack issue: an earlier dynasty-weighted blend had pushed out established,
relevant free agents (e.g. Paul Reed) by letting dynasty rank override
CAP tiers entirely. That failure mode is structurally impossible here:
the 50/50 Yahoo/dynasty blend below only ever breaks ties WITHIN a CAP
tier (see Candidate.sort_key) -- a $0 dynasty darling still can never
beat a $1+ player, no matter how the blend weights are tuned.
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
import unicodedata
from dataclasses import dataclass

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
INDEX_HTML = os.path.join(REPO_ROOT, "index.html")
YAHOO_NORMALIZED = os.path.join(REPO_ROOT, "local_data", "yahoo", "players_normalized.json")
DYNASTY_RANKINGS = os.path.join(REPO_ROOT, "data", "dynasty", "consensus.json")

POOL_SIZE = 60
ROWS_PER_BLOCK = 20

# Curated overlay: 2026 draftees/prospects that must be reachable in the
# pool even when Yahoo's public 300-player fetch does not carry them.
# Position/NBA team verified against the actual 2026 NBA draft results
# (not a mock/projection -- the draft already happened this cycle).
# `dynastyRank` is each player's real post-draft dynasty rookie rank
# (NBC Sports Dynasty Rookie Rankings, 2026 NBA Draft class -- Boozer,
# Peterson hold the top spots). It is used to calibrate an O-Rank-scale
# proxy for the handful of these players Yahoo does not rank at all (see
# DYNASTY_OR_PROXY below) -- real dynasty standing decides how a
# Yahoo-missing rookie compares to the field, rather than mechanically
# sorting every such rookie behind every Yahoo-ranked player regardless
# of how good the rookie actually is.
CURATED_ROOKIE_OVERLAY = {
    "Cameron Boozer": dict(pos="PF", nba="MEM", dynastyRank=1),  # already in Yahoo fetch
    "Caleb Wilson": dict(pos="PF", nba="CHI", dynastyRank=3),  # already in Yahoo fetch
    "AJ Dybantsa": dict(pos="SF", nba="WAS", dynastyRank=4),  # already in Yahoo fetch
    "Darryn Peterson": dict(pos="SG", nba="UTA", dynastyRank=2),  # already in Yahoo fetch
    "Darius Acuff Jr.": dict(pos="PG", nba="SAC", dynastyRank=7),  # already in Yahoo fetch
    "Keaton Wagler": dict(pos="SG", nba="LAC", dynastyRank=8),  # already in Yahoo fetch
    "Mikel Brown Jr.": dict(pos="PG", nba="BKN", dynastyRank=6),  # already in Yahoo fetch
    "Kingston Flemings": dict(pos="PG", nba="ATL", dynastyRank=5),
    "Yaxel Lendeborg": dict(pos="PF", nba="GSW", dynastyRank=11),  # already in Yahoo fetch
    "Morez Johnson Jr.": dict(pos="PF", nba="DAL", dynastyRank=9),  # already in Yahoo fetch
    "Allen Graves": dict(pos="PF", nba="TOR", dynastyRank=17),
    "Meleek Thomas": dict(pos="SG", nba="CLE", dynastyRank=36),
    "Ebuka Okorie": dict(pos="PG", nba="DET", dynastyRank=16),
    "Brayden Burries": dict(pos="SG", nba="MIL", dynastyRank=10),  # already in Yahoo fetch
    "Aday Mara": dict(pos="C", nba="OKC", dynastyRank=14),
    "Hannes Steinbach": dict(pos="PF", nba="CHA", dynastyRank=13),  # already in Yahoo fetch (OR240)
    # Reviewed per the correction pack, included only if they clear the
    # CAP-first pool naturally (no forced-inclusion guarantee below).
    "Cameron Carr": dict(pos="SG", nba="LAL", dynastyRank=None),
    "Labaron Philon Jr.": dict(pos="PG", nba="PHI", dynastyRank=None),
}

# Calibrate a dynasty-rank -> O-Rank-scale proxy from the curated names
# that have BOTH a real dynasty rank and a real Yahoo O-Rank (a simple
# through-the-origin least-squares fit: OR ~= k * dynastyRank). Applied
# only to curated names Yahoo does not rank at all, so a legitimately
# well-regarded rookie can land ahead of a mediocre Yahoo-ranked veteran
# within a CAP tier, instead of every OR-missing rookie being dumped
# below every OR-having player regardless of real relative value.
def _fit_dynasty_or_scale(yahoo_by_norm):
    num = den = 0.0
    for name, meta in CURATED_ROOKIE_OVERLAY.items():
        rank = meta["dynastyRank"]
        yp = yahoo_by_norm.get(normalize_name(name))
        if rank is None or yp is None:
            continue
        o_rank = int(yp["oRank"])
        num += rank * o_rank
        den += rank * rank
    return num / den if den else 30.0  # fallback slope if fetch is ever empty


def _dynasty_or_proxy(dynasty_rank, scale):
    return round(dynasty_rank * scale)

# Names force-included in the final 60 regardless of where they'd
# naturally sort (see Candidate.guaranteed). Paul Reed is the one name
# guaranteed unconditionally; every curated rookie/prospect is guaranteed
# ONLY when Yahoo has no data for them at all (build_candidates sets
# guaranteed=True on exactly those candidates). A curated name Yahoo DOES
# rank -- even weakly -- competes on real merit like everyone else and is
# not forced in: forcing every named rookie regardless of real value was
# the earlier bug that piled rookies up at the bottom of the pool,
# displacing genuinely better non-rookie candidates.
ALWAYS_GUARANTEED_NAMES = {"Paul Reed"}

# Cut players present on a team's cut list but absent from both the
# Yahoo 300 fetch and the curated overlay. Forced into the universe with
# conservative real-world metadata so "all projected cuts" is literal.
CONSERVATIVE_CUT_DEFAULTS = {
    "Jamir Watkins": dict(pos="SG/SF", nba="WAS"),
    "Chaney Johnson": dict(pos="PF", nba="BKN"),
    "Matisse Thybulle": dict(pos="SG/SF", nba="LAL"),
}

MISSING_OR = 9999

# A cut chip is `<span class="cut-chip">NAME[<strong>CAP</strong>]</span>`,
# optionally with ONE nested health-badge span appended to NAME (e.g. a
# cut player who's INJ/REC) -- a bare non-greedy `(.*?)</span>` stops at
# that inner span's own close instead of the chip's, silently truncating
# the captured name and losing the cap/position lookup for every cut
# player who also carries a health badge. This explicitly consumes a
# complete nested health-badge span as part of the chip instead.
CUT_CHIP_RE = re.compile(
    r'<span class="cut-chip">('
    r'(?:[^<]|<strong>[^<]*</strong>|<span class="health-badge[^>]*>[^<]*</span>)*'
    r')</span>'
)


def normalize_name(name: str) -> str:
    name = html_lib.unescape(name)
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = name.replace("'", "").replace(".", "")
    name = re.sub(r"\s+(jr|sr|ii|iii|iv)$", "", name.strip().lower())
    name = re.sub(r"[^a-z0-9]+", " ", name).strip()
    return name


ALWAYS_GUARANTEED_NAMES_NORM = {normalize_name(n) for n in ALWAYS_GUARANTEED_NAMES}

# Known nickname/full-name mismatches between hashtagbasketball.com's
# crowdsourced dynasty list and Yahoo/this board's naming --
# normalize_name's unicode-stripping fixes diacritics (e.g. Jokic/Jokić)
# but not a genuinely different first name. Verified by hand: every
# hashtag name with no normalize_name match against Yahoo's 300-player
# fetch was cross-checked by last name (2026-10-01); these 4 are real
# aliases for the same person, the ~25 other last-name collisions found
# are different real players, not aliases. Maps hashtag's normalized
# name -> this project's normalized name.
DYNASTY_NAME_ALIASES = {
    normalize_name("Alexandre Sarr"): normalize_name("Alex Sarr"),
    normalize_name("Nicolas Claxton"): normalize_name("Nic Claxton"),
    normalize_name("Ron Holland II"): normalize_name("Ronald Holland II"),
    normalize_name("Carlton Carrington"): normalize_name("Bub Carrington"),
}

# Percentile-normalization denominators for the blended tiebreak (see
# Candidate.blend_score) -- the live Yahoo fetch and the crowdsourced
# dynasty list are different sizes (~300 vs ~400 real players), so a
# raw rank average would quietly give the longer list's tail more
# leverage. These are fallback defaults for synthetic-data unit tests
# that construct a Candidate directly; build_candidates passes the
# actual loaded list sizes explicitly per candidate instead of relying
# on module state (avoids any cross-test mutable-global leakage).
YAHOO_RANK_MAX = 300
DYNASTY_RANK_MAX = 400


@dataclass
class Candidate:
    name: str
    pos: str
    nba: str
    cap: float
    o_rank: int = MISSING_OR
    dynasty_rank: int | None = None
    yahoo_rank_max: int = YAHOO_RANK_MAX
    dynasty_rank_max: int = DYNASTY_RANK_MAX
    rookie: bool = False
    src: str = "fa"  # "cut" | "fa" | "r"
    src_team: str = ""
    guaranteed: bool = False

    def blend_score(self) -> float:
        """50/50 blend of live Yahoo O-Rank and crowdsourced dynasty rank,
        each expressed as a percentile (0=best) within its own list so
        neither source's list length biases the other. This is a
        tiebreak ONLY -- see sort_key: CAP dollars descending is still
        the sole primary key, so this can never promote a $0 player
        above a $1+ one.

        Missing a signal is a worst-case percentile (1.0) on THAT axis,
        not a free pass averaged away -- Yahoo's 300-player fetch is
        itself a curated "most fantasy-relevant" cut (see
        docs/YAHOO_DATA_SOURCE.md), so not appearing in it is as
        informative as not appearing on a curated dynasty board (see
        ABSENCE_PENALTY_PERCENTILE in build_dynasty_consensus.py). A
        player with real Yahoo value but genuinely no dynasty buzz, or
        vice versa, should land in the middle of a cap tier, not float
        to the top on half a signal -- e.g. a curated rookie overlay
        name with no live Yahoo data at all (Cameron Carr, Labaron
        Philon Jr.) no longer skips the Yahoo axis entirely."""
        has_o = self.o_rank != MISSING_OR
        has_d = self.dynasty_rank is not None
        o_component = self.o_rank / self.yahoo_rank_max if has_o else 1.0
        d_component = self.dynasty_rank / self.dynasty_rank_max if has_d else 1.0
        return 0.5 * o_component + 0.5 * d_component

    def sort_key(self):
        return (-self.cap, self.blend_score(), self.name)


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
            for chip in re.findall(CUT_CHIP_RE, cuts_block.group(1)):
                cap_m = re.search(r"<strong>(\d+)</strong>", chip)
                cap_val = float(cap_m.group(1)) if cap_m else 0.0
                name_only = re.sub(r"<strong>.*?</strong>", "", chip)
                name_only = re.sub(r"<span.*?</span>", "", name_only).strip()
                cuts.append({"name": html_lib.unescape(name_only), "cap": cap_val, "team": short_name})

    return kept, cuts


def load_yahoo_players(path=YAHOO_NORMALIZED):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    by_norm = {}
    for p in data:
        by_norm[normalize_name(p["name"])] = p
    return by_norm


def load_dynasty_rankings(path=DYNASTY_RANKINGS):
    """Return (dynasty_by_norm, rank_max). dynasty_by_norm maps a
    normalized name to {"rank": consensus rank, "pos": str|None,
    "team": str|None} (see scripts/build_dynasty_consensus.py); rank_max
    is the total player count, used to express a rank as a percentile in
    Candidate.blend_score. pos/team are a fallback ONLY -- never
    authoritative over live Yahoo data (see docs/YAHOO_DATA_SOURCE.md) --
    for the rare candidate neither Yahoo nor the curated overlay covers."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    by_norm = {}
    for p in data["players"]:
        key = normalize_name(p["name"])
        by_norm[DYNASTY_NAME_ALIASES.get(key, key)] = {
            "rank": p["consensusRank"], "pos": p.get("pos"), "team": p.get("team"),
        }
    return by_norm, data["playerCount"]


SPECIFIC_POSITIONS = {"PG", "SG", "SF", "PF", "C"}


def pos_from_eligible(eligible):
    specific = [p for p in eligible if p in SPECIFIC_POSITIONS]
    return "/".join(specific) if specific else "F"


def build_candidates(index_html: str, yahoo_by_norm: dict, dynasty_by_norm: dict | None = None,
                      dynasty_rank_max: int | None = None):
    kept, cuts = parse_team_cards(index_html)
    dynasty_or_scale = _fit_dynasty_or_scale(yahoo_by_norm)

    def dynasty_proxy_or(dynasty_rank):
        return _dynasty_or_proxy(dynasty_rank, dynasty_or_scale) if dynasty_rank else MISSING_OR

    # Real list sizes feed the blend-score percentile normalization (see
    # Candidate.blend_score) instead of the module-level fallback
    # constants, so the tiebreak stays honest if either list's size
    # changes later. dynasty_by_norm/dynasty_rank_max are optional so
    # existing callers/tests that only care about the Yahoo/CAP pipeline
    # don't need to supply a dynasty dataset.
    yahoo_rank_max = len(yahoo_by_norm) if yahoo_by_norm else YAHOO_RANK_MAX
    dynasty_by_norm = dynasty_by_norm or {}
    dynasty_rank_max = dynasty_rank_max or DYNASTY_RANK_MAX

    candidates: dict[str, Candidate] = {}

    def add(cand: Candidate):
        key = normalize_name(cand.name)
        dynasty_entry = dynasty_by_norm.get(key)
        cand.dynasty_rank = dynasty_entry["rank"] if dynasty_entry else None
        cand.yahoo_rank_max = yahoo_rank_max
        cand.dynasty_rank_max = dynasty_rank_max
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
                rookie=yp["name"] in CURATED_ROOKIE_OVERLAY, src="cut", src_team=cut["team"],
            ))
            continue
        overlay = CURATED_ROOKIE_OVERLAY.get(cut["name"])
        if overlay is not None:
            # Yahoo has no data for this cut player at all -- guaranteed,
            # same as the backfill path below, EXCEPT the reviewed-not-
            # guaranteed names (dynastyRank=None marks those).
            add(Candidate(
                name=cut["name"], pos=overlay["pos"], nba=overlay["nba"], cap=cut["cap"],
                o_rank=dynasty_proxy_or(overlay["dynastyRank"]), rookie=True,
                guaranteed=overlay["dynastyRank"] is not None,
                src="cut", src_team=cut["team"],
            ))
            continue
        fallback = CONSERVATIVE_CUT_DEFAULTS.get(cut["name"])
        if fallback is not None:
            add(Candidate(
                name=cut["name"], pos=fallback["pos"], nba=fallback["nba"], cap=cut["cap"],
                src="cut", src_team=cut["team"],
            ))
            continue
        # Unknown cut with no Yahoo/curated/conservative-default source at
        # all: fall back to the dynasty consensus's own pos/team (a cross-
        # source cross-check, never authoritative over Yahoo) if it
        # covers this player; otherwise force-include literally with only
        # what the cut chip itself told us.
        dynasty_entry = dynasty_by_norm.get(normalize_name(cut["name"]))
        pos = (dynasty_entry.get("pos") or "") if dynasty_entry else ""
        nba = (dynasty_entry.get("team") or "") if dynasty_entry else ""
        add(Candidate(name=cut["name"], pos=pos, nba=nba, cap=cut["cap"], src="cut", src_team=cut["team"]))

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

    # 3. curated overlay backfill for names Yahoo/cuts never produced --
    # Yahoo has no data for these at all, so they're guaranteed, EXCEPT
    # the reviewed-not-guaranteed names (dynastyRank=None marks those).
    for name, meta in CURATED_ROOKIE_OVERLAY.items():
        key = normalize_name(name)
        if key in kept or key in candidates:
            continue
        add(Candidate(
            name=name, pos=meta["pos"], nba=meta["nba"], cap=0.0,
            o_rank=dynasty_proxy_or(meta["dynastyRank"]), rookie=True,
            guaranteed=meta["dynastyRank"] is not None, src="r",
        ))

    # Names guaranteed unconditionally, regardless of which path supplied
    # their data (e.g. Paul Reed usually arrives via the live Yahoo fetch).
    for name in ALWAYS_GUARANTEED_NAMES:
        cand = candidates.get(normalize_name(name))
        if cand is not None:
            cand.guaranteed = True

    return candidates


def sort_and_truncate(candidates: dict):
    ordered = sorted(candidates.values(), key=lambda c: c.sort_key())
    top = ordered[:POOL_SIZE]
    top_keys = {normalize_name(c.name) for c in top}

    missing_guaranteed = [
        c for c in candidates.values()
        if c.guaranteed and normalize_name(c.name) not in top_keys
    ]

    if missing_guaranteed:
        # Bump the lowest-priority non-guaranteed rows out, in reverse
        # sort order, to make room -- then the whole 60 gets re-sorted so
        # CAP ordering is unaffected by *where* the guarantee inserted.
        removable = [c for c in reversed(top) if not c.guaranteed]
        top_set = list(top)
        for extra in missing_guaranteed:
            if removable:
                drop = removable.pop(0)
                top_set.remove(drop)
            top_set.append(extra)
        top = sorted(top_set, key=lambda c: c.sort_key())[:POOL_SIZE]

    return top


DEFENDING_CHAMPION_SHORT_NAME = "Đạt"
CROWN = "👑 "


def crown_prefix(short_name: str) -> str:
    return CROWN if short_name == DEFENDING_CHAMPION_SHORT_NAME else ""


def src_badge_html(c: "Candidate") -> str:
    # Provenance (src) and rookie status are independent facts -- a
    # rookie found via the live Yahoo fetch is still a rookie, and the
    # SRC badge's job is to say "R" for any rookie, not "FA" just because
    # of which source happened to supply their metadata. A cut still
    # wins over "R" since knowing WHICH team cut them is more specific
    # and no curated rookie is currently also a cut in this league.
    if c.src == "cut":
        return f'<span class="src src-cut">{crown_prefix(c.src_team)}{html_lib.escape(c.src_team)}</span>'
    if c.rookie:
        return '<span class="src src-r">R</span>'
    return '<span class="src src-fa">FA</span>'


def render_pool_html(ranked: list) -> str:
    blocks = []
    for start in range(0, len(ranked), ROWS_PER_BLOCK):
        chunk = ranked[start:start + ROWS_PER_BLOCK]
        rows = []
        for i, c in enumerate(chunk, start=start + 1):
            row_class = "pool-row rookie-row" if c.rookie else "pool-row"
            src_html = src_badge_html(c)
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


def build(index_html: str, yahoo_players_path: str = YAHOO_NORMALIZED,
          dynasty_rankings_path: str = DYNASTY_RANKINGS) -> tuple[str, list]:
    yahoo_by_norm = load_yahoo_players(yahoo_players_path)
    dynasty_by_norm, dynasty_rank_max = load_dynasty_rankings(dynasty_rankings_path)
    candidates = build_candidates(index_html, yahoo_by_norm, dynasty_by_norm, dynasty_rank_max)
    ranked = sort_and_truncate(candidates)
    pool_html = render_pool_html(ranked)
    new_html = splice_pool_into_index(index_html, pool_html)
    return new_html, ranked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yahoo-players", default=YAHOO_NORMALIZED,
        help="normalized Yahoo snapshot to rebuild against (default: the local gitignored refresh output)",
    )
    parser.add_argument(
        "--dynasty-rankings", default=DYNASTY_RANKINGS,
        help="crowdsourced dynasty consensus rankings to rebuild against (default: data/dynasty/consensus.json)",
    )
    args = parser.parse_args()

    with open(INDEX_HTML, encoding="utf-8") as f:
        index_html = f.read()

    start, end = _find_pool_grid_span(index_html)
    before_names = {
        html_lib.unescape(n) for n in
        re.findall(r'<div class="pool-player">(.*?)</div>', index_html[start:end])
    }

    new_html, ranked = build(index_html, args.yahoo_players, args.dynasty_rankings)

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
