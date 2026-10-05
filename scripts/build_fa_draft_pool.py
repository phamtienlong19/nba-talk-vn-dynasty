#!/usr/bin/env python3
"""Rebuild the FA / DRAFT 60 pool section of index.html.

Pipeline (kept as separate stages so each is independently testable):

1. candidate generation -- the complete universe is built BEFORE ranking:
   (A) every projected cut (parsed from the 16 team-card <footer
   class="cuts"> blocks in index.html); (B) every non-kept player in the
   live Yahoo 300-player fetch (local_data/yahoo/players_normalized.json);
   (C) every non-kept player the project's dynasty consensus
   (data/dynasty/consensus.json) ranks inside DYNASTY_CANDIDATE_CUTOFF --
   rookies, sophomores, 3rd/4th-year players and anyone else the consensus
   rates, whether or not Yahoo's top 300 carries them; (D) the small
   curated overlay of approved 2026 prospects.
2. metadata enrichment -- cap dollars, O-Rank, position, NBA team come from
   the most authoritative source per player (Yahoo first; the consensus
   board's pos/team only for players Yahoo lacks, with team abbreviations
   translated to Yahoo's convention).
3. sorting -- CAP dollars descending is the only primary key; a $0 player
   can never outrank a $1+ player. Within a CAP tier,
   Candidate.relevance_score blends two normalized percentile scores:
   60% current-market (Yahoo O-Rank / 300) and 40% dynasty consensus
   (consensus rank / consensus size). A player Yahoo does not rank gets a
   fixed MISSING_YAHOO_SCORE (0.80, i.e. as if Yahoo had him ~OR 240) on
   the Yahoo axis -- a documented uncertainty/current-contribution
   penalty -- so a dynasty-only player does not automatically outrank a
   credible Yahoo OR 120-160 rotation player but an elite young asset can
   still reach the 60. A player absent from the consensus board scores
   1.0 (worst) on the dynasty axis. No age bonus: youth only matters
   through the consensus rank itself.
4. truncation -- rows 1-39 are the plain ranking above. Rows 40-60
   hold the owner-approved depth names (TAIL_PINNED_NAMES + Paul Reed) and
   then the best rookies / sophomores / 3rd-year players (draft class from
   data/dynasty/draft_classes.json + the 2026 rookie source) by the same
   hybrid score -- so replacement-level veterans give way to young players
   without any age bonus or per-class quota. The final 60 is re-sorted so CAP
   ordering is never broken.

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
# `dynastyRank` is the real post-draft dynasty rookie rank (NBC Sports,
# 2026 class), kept as reference data only -- ranking uses the project
# consensus board (data/dynasty/consensus.json), not this field.
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

# Names force-included in the final 60 regardless of where they'd
# naturally sort (see Candidate.guaranteed). Paul Reed is the only one.
# Prospects and young players are NOT forced in: they are in the candidate
# universe and make the 60 only when the CAP-then-hybrid ranking earns it
# (no category quotas).
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

# Percentile-normalization denominators for the relevance tiebreak (see
# Candidate.relevance_score) -- the live Yahoo fetch and the crowdsourced
# dynasty list are different sizes (~300 vs ~400 real players), so a
# raw rank average would quietly give the longer list's tail more
# leverage. These are fallback defaults for synthetic-data unit tests
# that construct a Candidate directly; build_candidates passes the
# actual loaded list sizes explicitly per candidate instead of relying
# on module state (avoids any cross-test mutable-global leakage).
YAHOO_RANK_MAX = 300
DYNASTY_RANK_MAX = 400

# Within-CAP-tier hybrid (see Candidate.relevance_score). Yahoo (current
# market) stays the larger component.
YAHOO_WEIGHT = 0.60
DYNASTY_WEIGHT = 0.40
# Yahoo-axis score for a player Yahoo does not rank (0 = best, 1 = worst).
# 0.80 ~ "Yahoo would have him around OR 240": a conservative
# uncertainty/current-contribution penalty. Even with a top-10 dynasty rank
# the blended score is ~0.52, i.e. behind a credible Yahoo OR 120-150 player
# with a middling dynasty rank, but ahead of deep Yahoo-only players.
MISSING_YAHOO_SCORE = 0.80
# A non-kept player enters the candidate universe from the dynasty consensus
# if ranked at or inside this consensus rank (the board has ~540 players).
DYNASTY_CANDIDATE_CUTOFF = 250

# FA/DRAFT 60 layout: the first CORE_SIZE rows (pages 1-2) are the plain CAP-
# then-hybrid ranking. The remaining rows (page 3) are filled with owner-
# approved names (TAIL_PINNED_NAMES -- depth veterans plus young players the
# owner explicitly wants kept) and then the best rookies /
# sophomores / 3rd-year players by the same hybrid score. "Young" comes from
# data/dynasty/draft_classes.json (2025, 2024 classes) and the 2026 rookie
# source -- never an age bonus inside the score itself.
CORE_SIZE = 39
YOUNG_FIRST_CLASS_YEAR = 2024  # 2026 rookie, 2025 sophomore, 2024 3rd-year
TAIL_PINNED_NAMES = {
    "Grayson Allen", "Julian Champagnie", "Scotty Pippen Jr.", "Jake LaRavia",
    "Jared McCain", "Bilal Coulibaly",
    "Tre Jones",  # owner: preferred over De'Andre Hunter (plain rank 40) for the last depth slot
    "Allen Graves", "Aday Mara",  # owner: high-interest 2026 rookies whose deep Yahoo OR undersells them
}
DRAFT_CLASSES = os.path.join(REPO_ROOT, "data", "dynasty", "draft_classes.json")

# Dynasty-source team abbreviations -> Yahoo's convention.
DYNASTY_TEAM_TO_YAHOO = {"GS": "GSW", "NO": "NOP", "NOR": "NOP", "NY": "NYK", "PHO": "PHX", "SA": "SAS"}


def yahoo_team(abbr: str | None) -> str:
    abbr = abbr or ""
    return DYNASTY_TEAM_TO_YAHOO.get(abbr, abbr)


@dataclass
class Candidate:
    name: str
    pos: str
    nba: str
    cap: float
    o_rank: int = MISSING_OR  # real current Yahoo O-Rank only
    dynasty_rank: int | None = None
    yahoo_rank_max: int = YAHOO_RANK_MAX
    dynasty_rank_max: int = DYNASTY_RANK_MAX
    rookie: bool = False
    src: str = "fa"  # "cut" | "fa" | "r"
    src_team: str = ""
    guaranteed: bool = False
    young: bool = False  # rookie, sophomore or 3rd-year (see TAIL_PINNED_NAMES / draft_classes.json)
    pinned: bool = False  # owner-approved tail name

    def yahoo_score(self) -> float:
        """Current-market score (0 best, 1 worst): O-Rank as a percentile of
        the Yahoo list; MISSING_YAHOO_SCORE when Yahoo does not rank him."""
        if self.o_rank == MISSING_OR:
            return MISSING_YAHOO_SCORE
        return min(1.0, self.o_rank / self.yahoo_rank_max)

    def dynasty_score(self) -> float:
        """Dynasty score (0 best, 1 worst): consensus rank as a percentile of
        the consensus board; 1.0 when the consensus does not rank him."""
        if self.dynasty_rank is None:
            return 1.0
        return min(1.0, self.dynasty_rank / self.dynasty_rank_max)

    def relevance_score(self) -> float:
        """Within-CAP-tier relevance, lower is better:
        YAHOO_WEIGHT * yahoo_score + DYNASTY_WEIGHT * dynasty_score, each a
        normalized percentile (never raw ranks from lists of different
        length). Only ever consulted inside one CAP tier (see sort_key)."""
        return YAHOO_WEIGHT * self.yahoo_score() + DYNASTY_WEIGHT * self.dynasty_score()

    def sort_key(self):
        return (-self.cap, self.relevance_score(), self.name)


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
    Candidate.relevance_score. pos/team are a fallback ONLY -- never
    authoritative over live Yahoo data (see docs/YAHOO_DATA_SOURCE.md) --
    for the rare candidate neither Yahoo nor the curated overlay covers."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    by_norm = {}
    for p in data["players"]:
        key = normalize_name(p["name"])
        by_norm[DYNASTY_NAME_ALIASES.get(key, key)] = {
            "rank": p["consensusRank"], "pos": p.get("pos"), "team": p.get("team"), "name": p["name"],
        }
    return by_norm, data["playerCount"]


ROOKIE_SOURCE = os.path.join(REPO_ROOT, "data", "dynasty", "sources", "nbcsports_rookies.json")


def load_rookie_names(path=ROOKIE_SOURCE) -> set:
    """Normalized names of the 2026 draft class (the project's rookie-only
    dynasty source), used for the R badge -- not for ranking."""
    try:
        with open(path, encoding="utf-8") as f:
            return {normalize_name(p["name"]) for p in json.load(f)["players"]}
    except OSError:
        return set()


def load_draft_years(path=DRAFT_CLASSES) -> dict:
    """normalized name -> first-NBA-season draft year, for the 2025/2024 classes."""
    try:
        with open(path, encoding="utf-8") as f:
            classes = json.load(f)["classes"]
    except OSError:
        return {}
    return {normalize_name(n): int(year) for year, names in classes.items() for n in names}


SPECIFIC_POSITIONS = {"PG", "SG", "SF", "PF", "C"}


def pos_from_eligible(eligible):
    specific = [p for p in eligible if p in SPECIFIC_POSITIONS]
    return "/".join(specific) if specific else "F"


def build_candidates(index_html: str, yahoo_by_norm: dict, dynasty_by_norm: dict | None = None,
                      dynasty_rank_max: int | None = None, rookie_names: set | None = None,
                      draft_years: dict | None = None):
    kept, cuts = parse_team_cards(index_html)
    rookie_names = rookie_names or set()
    draft_years = draft_years or {}

    def is_rookie(name):
        return name in CURATED_ROOKIE_OVERLAY or normalize_name(name) in rookie_names

    # Real list sizes feed the relevance-score percentile normalization (see
    # Candidate.relevance_score) instead of the module-level fallback
    # constants, so the tiebreak stays honest if either list's size
    # changes later. dynasty_by_norm/dynasty_rank_max are optional so
    # existing callers/tests that only care about the Yahoo/CAP pipeline
    # don't need to supply a dynasty dataset.
    yahoo_rank_max = (
        max(len(yahoo_by_norm), max(int(p["oRank"]) for p in yahoo_by_norm.values()))
        if yahoo_by_norm else YAHOO_RANK_MAX
    )
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
                rookie=is_rookie(yp["name"]), src="cut", src_team=cut["team"],
            ))
            continue
        overlay = CURATED_ROOKIE_OVERLAY.get(cut["name"])
        if overlay is not None:
            # Yahoo has no data for this cut player at all.
            add(Candidate(
                name=cut["name"], pos=overlay["pos"], nba=overlay["nba"], cap=cut["cap"],
                rookie=True, src="cut", src_team=cut["team"],
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
        nba = yahoo_team(dynasty_entry.get("team")) if dynasty_entry else ""
        add(Candidate(name=cut["name"], pos=pos, nba=nba, cap=cut["cap"], src="cut", src_team=cut["team"]))

    # 2. all non-kept Yahoo-ranked players
    for key, yp in yahoo_by_norm.items():
        if key in kept:
            continue
        if key in candidates:
            continue
        add(Candidate(
            name=yp["name"], pos=pos_from_eligible(yp["eligiblePositions"]),
            nba=yp["nbaTeam"], cap=float(yp["capDollars"]), o_rank=int(yp["oRank"]),
            rookie=is_rookie(yp["name"]), src="fa",
        ))

    # 3. the project's dynasty consensus board: every non-kept player ranked
    # inside the candidate cutoff enters the universe even if Yahoo's top 300
    # doesn't carry him (young players with a poor/absent Yahoo OR). Display
    # name/pos/team come from the consensus board (Yahoo has no data for
    # these players by construction -- Yahoo-ranked ones were added above).
    for key, entry in sorted(dynasty_by_norm.items(), key=lambda kv: kv[1]["rank"]):
        if entry["rank"] > DYNASTY_CANDIDATE_CUTOFF:
            break
        if key in kept or key in candidates:
            continue
        display = entry.get("name") or key.title()
        add(Candidate(
            name=display, pos=entry.get("pos") or "", nba=yahoo_team(entry.get("team")),
            cap=0.0, rookie=is_rookie(display), src="r" if is_rookie(display) else "fa",
        ))

    # 4. curated overlay backfill for approved prospects none of the sources
    # above produced -- they enter the universe and compete like everyone
    # else (no forced slot -- see ALWAYS_GUARANTEED_NAMES).
    for name, meta in CURATED_ROOKIE_OVERLAY.items():
        key = normalize_name(name)
        if key in kept or key in candidates:
            continue
        add(Candidate(
            name=name, pos=meta["pos"], nba=meta["nba"], cap=0.0,
            rookie=True, src="r",
        ))

    pinned_norm = {normalize_name(n) for n in TAIL_PINNED_NAMES}
    for key, cand in candidates.items():
        cand.young = cand.rookie or draft_years.get(key, 0) >= YOUNG_FIRST_CLASS_YEAR
        cand.pinned = key in pinned_norm

    # Names guaranteed unconditionally, regardless of which path supplied
    # their data (e.g. Paul Reed usually arrives via the live Yahoo fetch).
    for name in ALWAYS_GUARANTEED_NAMES:
        cand = candidates.get(normalize_name(name))
        if cand is not None:
            cand.guaranteed = True

    return candidates


def sort_and_truncate(candidates: dict):
    """Pages 1-2 (CORE_SIZE rows): plain CAP-then-hybrid order. Page 3: the
    guaranteed / owner-pinned names still available, then the best young
    (rookie / sophomore / 3rd-year) candidates by the same hybrid score; if
    there aren't enough young candidates the rest fills in plain order. The
    final 60 is re-sorted so CAP order is never broken (tail rows are always
    behind every core row on the sort key, so the core is unchanged)."""
    ordered = sorted(candidates.values(), key=lambda c: c.sort_key())
    core = ordered[:CORE_SIZE]
    rest = ordered[CORE_SIZE:]
    tail_slots = POOL_SIZE - len(core)

    must = [c for c in rest if c.guaranteed or c.pinned]
    # A guaranteed name that is also past the pinned budget still gets in.
    tail = must[:tail_slots]
    chosen = {id(c) for c in tail}
    for c in rest:
        if len(tail) >= tail_slots:
            break
        if c.young and id(c) not in chosen:
            tail.append(c)
            chosen.add(id(c))
    for c in rest:  # not enough young candidates: plain order fills the page
        if len(tail) >= tail_slots:
            break
        if id(c) not in chosen:
            tail.append(c)
            chosen.add(id(c))

    return sorted(core + tail, key=lambda c: c.sort_key())[:POOL_SIZE]


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
    candidates = build_candidates(index_html, yahoo_by_norm, dynasty_by_norm, dynasty_rank_max,
                                  rookie_names=load_rookie_names(), draft_years=load_draft_years())
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
