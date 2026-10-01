#!/usr/bin/env python3
"""Build a single crowdsourced dynasty consensus ranking from multiple
independent dynasty-ranking sources (data/dynasty/sources/*.json).

Each source covers a different number of players (a full board, or a
free-tier/article top-N). A player's score is the AVERAGE of their
percentile (rank / that source's player count, lower is better) across
only the sources that actually cover them -- not appearing in a
shorter/paywalled source is not treated as a negative signal, since
that absence usually just reflects the source's own cutoff, not an
opinion about the player.

Name matching reuses build_fa_draft_pool.normalize_name (handles
diacritics/punctuation) plus DYNASTY_NAME_ALIASES for the handful of
genuine nickname/full-name mismatches between sources that unicode
normalization alone can't fix (e.g. Alex Sarr / Alexandre Sarr).

Standard library only.

Usage:
    python3 scripts/build_dynasty_consensus.py \
        --sources data/dynasty/sources/hashtagbasketball.json \
                  data/dynasty/sources/dynatyze.json \
                  data/dynasty/sources/rotowire.json \
        --output data/dynasty/consensus.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from build_fa_draft_pool import DYNASTY_NAME_ALIASES, normalize_name  # noqa: E402


def _canonical_key(name: str) -> str:
    key = normalize_name(name)
    return DYNASTY_NAME_ALIASES.get(key, key)


def _name_preference(name: str) -> tuple[int, int]:
    non_ascii = sum(1 for ch in name if ord(ch) > 127)
    return (non_ascii, len(name))


def _pick_display_name(name_counts: dict) -> str:
    """Majority vote across sources first -- a single source's one-off
    typo (e.g. a spreadsheet row reading "Kon Knueppel II" when every
    other source agrees on "Kon Knueppel") must never win just for being
    a longer string. Only fall back to the diacritics/length heuristic
    to break a genuine tie between equally-common spellings."""
    max_count = max(name_counts.values())
    tied = [name for name, count in name_counts.items() if count == max_count]
    return max(tied, key=_name_preference)


def build_consensus(sources: list[dict]) -> list[dict]:
    """sources: list of {"source": str, "players": [{"rank": int, "name": str,
    "pos": str|None, "team": str|None}]} -- pos/team are optional per
    source (not every source's export carries them).
    Returns a list of {"name", "pos", "team", "consensusRank", "percentile",
    "sourcesCount", "sources": [source names]} sorted best-first. pos/team
    are a same-person cross-check / fallback for a player no live Yahoo
    data covers -- never authoritative over Yahoo (see
    docs/YAHOO_DATA_SOURCE.md)."""
    by_key: dict[str, dict] = {}

    for src in sources:
        src_name = src["source"]
        count = len(src["players"])
        for raw_p in src["players"]:
            # A raw source export can carry incidental whitespace (seen in
            # the ALL ACCESS spreadsheet, e.g. "Yang Hansen " with a
            # trailing space) -- strip it so it never wins display-name
            # selection as a spurious "different" spelling.
            p = {**raw_p, "name": raw_p["name"].strip()}
            key = _canonical_key(p["name"])
            entry = by_key.setdefault(
                key, {"name_counts": {}, "percentiles": [], "sources": [], "pos": None, "team": None},
            )
            entry["name_counts"][p["name"]] = entry["name_counts"].get(p["name"], 0) + 1
            entry["percentiles"].append(p["rank"] / count)
            entry["sources"].append(src_name)
            # pos/team: first source to supply one wins (not every source
            # carries them -- e.g. rotowire has no position column).
            if entry["pos"] is None and p.get("pos"):
                entry["pos"] = p["pos"]
            if entry["team"] is None and p.get("team"):
                entry["team"] = p["team"]

    rows = []
    for key, entry in by_key.items():
        percentile_avg = sum(entry["percentiles"]) / len(entry["percentiles"])
        rows.append({
            "key": key,
            "name": _pick_display_name(entry["name_counts"]),
            "pos": entry["pos"],
            "team": entry["team"],
            "percentile": percentile_avg,
            "sourcesCount": len(entry["sources"]),
            "sources": entry["sources"],
        })

    rows.sort(key=lambda r: (r["percentile"], r["name"]))
    for i, row in enumerate(rows, start=1):
        row["consensusRank"] = i
        del row["key"]
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    loaded = []
    source_meta = []
    for path in args.sources:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        loaded.append(data)
        source_meta.append({
            "source": data["source"], "playerCount": data["playerCount"], "fetchedAt": data.get("fetchedAt"),
        })

    consensus = build_consensus(loaded)

    out = {
        "generatedFrom": source_meta,
        "playerCount": len(consensus),
        "players": consensus,
    }
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote {args.output}: {len(consensus)} players from {len(loaded)} sources")


if __name__ == "__main__":
    main()
