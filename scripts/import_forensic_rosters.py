#!/usr/bin/env python3
"""Import the pre-keeper roster ownership baseline from the forensic
2026-08-20 state snapshot markdown file.

Standard library only.

Usage:
    python3 scripts/import_forensic_rosters.py \\
        "local_sources/nba_talk_vn_dynasty_forensic_state_2026-08-20(6).md"

Parses ONLY the canonical Section 2 `teams.md` code block from that file --
the pre-keeper ownership snapshot -- and writes/validates:

    data/2026-27/franchises.json
    data/2026-27/prekeeper_rosters.json

This script deliberately refuses to run (non-zero exit, clear message) if:
  - the exact 16-team canonical order is not found or does not match;
  - a team heading is missing;
  - total assignments != 232;
  - a player name is duplicated across team ownership in this snapshot;
  - it looks like it drifted into the projected-keeper/cut/FA-pool/
    infographic sections instead of the Section 2 teams.md block.

It does NOT parse or trust projected keeper tables, projected cuts, the
56-player FA/draft board, generated infographic text, or the August `178`
working cap figure -- those are historical/analytical, not the canonical
pre-keeper ownership source.
"""
from __future__ import annotations

import json
import os
import re
import sys

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
FRANCHISES_OUT = os.path.join(REPO_ROOT, "data", "2026-27", "franchises.json")
ROSTERS_OUT = os.path.join(REPO_ROOT, "data", "2026-27", "prekeeper_rosters.json")

SEASON = "2026-27"
SOURCE_SNAPSHOT_DATE = "2026-08-20"
SOURCE_ARTIFACT = "nba_talk_vn_dynasty_forensic_state_2026-08-20(6).md"

CANONICAL_ORDER = [
    "Hai | GTA San Antonio",
    "CrazyCat Damageee",
    "MeloBB",
    "Long con",
    "HCMC Kindergarten",
    "Dũng | Trader by Trade",
    "Maxfixe",
    "DHA | Đì troi pít tông",
    "M. Jordat | The Silver Seekers",
    "DonTrick DevilTeam",
    "Thịnh | Seattle SuperSonics",
    "sup fam | Bruised for Boozer",
    "Quan | Okay See Thunder",
    "TuLy | No Country for Old Men",
    "Bz | Putin the tank driver",
    "TT | Kratos Dynasty",
]

EXPECTED_ROSTER_COUNTS = [15, 15, 14, 15, 13, 14, 13, 15, 13, 15, 15, 15, 15, 15, 15, 15]
EXPECTED_TOTAL = 232

# Markers that indicate the parser has wandered outside Section 2 / teams.md
# into analytical territory it must never treat as ownership source.
FORBIDDEN_SECTION_MARKERS = [
    "projected keeper",
    "projected cut",
    "draft pool",
    "fa/draft",
    "56-player",
    "infographic",
    "working cap",
    "178",
]


class ForensicImportError(RuntimeError):
    pass


def extract_teams_md_block(markdown_text: str) -> str:
    """Locate the Section 2 teams.md canonical code block and return its
    raw text. Refuses if the section can't be unambiguously located."""
    # Look for a "## Section 2" (or similar) heading followed by a fenced
    # code block containing teams.md content, identified by containing the
    # first canonical team name.
    anchor = CANONICAL_ORDER[0]
    idx = markdown_text.find(anchor)
    if idx == -1:
        raise ForensicImportError(
            f"could not locate canonical team order anchor '{anchor}' in source file"
        )

    # Walk backward to the nearest fenced code block start before idx,
    # and forward to its close.
    block_start = markdown_text.rfind("```", 0, idx)
    if block_start == -1:
        raise ForensicImportError("could not find opening code fence before team order")
    block_end = markdown_text.find("```", idx)
    if block_end == -1:
        raise ForensicImportError("could not find closing code fence after team order")

    block = markdown_text[block_start:block_end]

    lowered = block.lower()
    for marker in FORBIDDEN_SECTION_MARKERS:
        if marker in lowered:
            raise ForensicImportError(
                f"refusing to import: matched block contains forbidden marker "
                f"'{marker}' -- this looks like an analytical section, not "
                f"the canonical Section 2 teams.md ownership block"
            )

    return block


def parse_teams_block(block: str):
    """Parse team headings (in canonical order) and their player lists.

    Returns list of (team_display_name, [player_name, ...]) in file order.
    """
    lines = block.splitlines()
    teams = []
    current_team = None
    current_players: list[str] = []

    def flush():
        if current_team is not None:
            teams.append((current_team, current_players[:]))

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("```"):
            continue

        matched_team = None
        for name in CANONICAL_ORDER:
            if line == name or line.lstrip("#").strip() == name or line.lstrip("-* ").strip() == name:
                matched_team = name
                break
            # allow "1. Hai | GTA San Antonio" style numbered headings
            stripped_num = re.sub(r"^\d+[.)]\s*", "", line)
            if stripped_num == name:
                matched_team = name
                break

        if matched_team is not None:
            flush()
            current_team = matched_team
            current_players = []
            continue

        if current_team is not None:
            player_line = re.sub(r"^[-*\d.)\s]+", "", line).strip()
            if player_line:
                current_players.append(player_line)

    flush()
    return teams


def validate_teams(teams):
    found_order = [t[0] for t in teams]
    if found_order != CANONICAL_ORDER:
        raise ForensicImportError(
            "team order mismatch.\n"
            f"  expected: {CANONICAL_ORDER}\n"
            f"  found:    {found_order}"
        )

    counts = [len(players) for _, players in teams]
    if counts != EXPECTED_ROSTER_COUNTS:
        raise ForensicImportError(
            f"per-team roster counts mismatch.\n"
            f"  expected: {EXPECTED_ROSTER_COUNTS}\n"
            f"  found:    {counts}"
        )

    total = sum(counts)
    if total != EXPECTED_TOTAL:
        raise ForensicImportError(
            f"total assignment count mismatch: expected {EXPECTED_TOTAL}, found {total}"
        )

    seen = {}
    for team_name, players in teams:
        for player in players:
            if player in seen:
                raise ForensicImportError(
                    f"duplicate player ownership in snapshot: '{player}' "
                    f"appears on both '{seen[player]}' and '{team_name}'"
                )
            seen[player] = team_name


def write_franchises_json():
    franchises = [
        {
            "franchiseId": f"franchise-{i+1:02d}",
            "displayOrder": i + 1,
            "displayName": name,
        }
        for i, name in enumerate(CANONICAL_ORDER)
    ]
    payload = {
        "season": SEASON,
        "sourceSnapshotDate": SOURCE_SNAPSHOT_DATE,
        "sourceArtifact": SOURCE_ARTIFACT,
        "stateType": "PRE_KEEPER_ROSTER_BASELINE",
        "franchises": franchises,
    }
    os.makedirs(os.path.dirname(FRANCHISES_OUT), exist_ok=True)
    with open(FRANCHISES_OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def write_rosters_json(teams):
    name_to_id = {
        name: f"franchise-{i+1:02d}" for i, name in enumerate(CANONICAL_ORDER)
    }
    assignments = []
    for team_name, players in teams:
        franchise_id = name_to_id[team_name]
        for player in players:
            assignments.append({
                "season": SEASON,
                "franchiseId": franchise_id,
                "playerName": player,
                "sourceState": "PRE_KEEPER",
            })

    payload = {
        "season": SEASON,
        "sourceSnapshotDate": SOURCE_SNAPSHOT_DATE,
        "sourceArtifact": SOURCE_ARTIFACT,
        "stateType": "PRE_KEEPER_ROSTER_BASELINE",
        "assignments": assignments,
    }
    os.makedirs(os.path.dirname(ROSTERS_OUT), exist_ok=True)
    with open(ROSTERS_OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main():
    if len(sys.argv) != 2:
        print(
            "usage: import_forensic_rosters.py <forensic-state-markdown-path>",
            file=sys.stderr,
        )
        sys.exit(2)

    source_path = sys.argv[1]
    with open(source_path, encoding="utf-8") as f:
        text = f.read()

    block = extract_teams_md_block(text)
    teams = parse_teams_block(block)
    validate_teams(teams)

    write_franchises_json()
    write_rosters_json(teams)

    print(f"OK: imported {EXPECTED_TOTAL} pre-keeper assignments across 16 franchises")
    print(f"  {FRANCHISES_OUT}")
    print(f"  {ROSTERS_OUT}")


if __name__ == "__main__":
    try:
        main()
    except ForensicImportError as e:
        print(f"FORENSIC IMPORT ERROR: {e}", file=sys.stderr)
        sys.exit(1)
