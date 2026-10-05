#!/usr/bin/env python3
"""Generate the commissioner-facing Yahoo Top 300 Markdown table.

Chain: live Yahoo -> normalized snapshot -> THIS Markdown ->
scripts/export_yahoo_top300_xlsx.py (the XLSX is derived from the
Markdown, never rebuilt from Yahoo independently).

Row order is salary-draft order: projected $ descending, Yahoo O-Rank
ascending within an equal-dollar tier (same ordering the cap model uses;
see scripts/cap_model.py). The Rank column is the Yahoo O-Rank. This file
is commissioner reference material -- the cap model never reads it.

Standard library only. Output is deterministic and overwritten whole.

Usage:
    python3 scripts/export_yahoo_top300.py [normalized-players.json] [out.md]
"""
from __future__ import annotations

import json
import os
import re
import sys

REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DEFAULT_PLAYERS = os.path.join(REPO_ROOT, "local_data", "yahoo", "players_normalized.json")
DEFAULT_OUT = os.path.join(REPO_ROOT, "exports", "yahoo_top300_proj_dollar_rank.md")

TITLE = "# Yahoo Top 300 — Projected $ / Rank"
HEADER = "| Player | Proj $ | Rank |"
DIVIDER = "|---|---:|---:|"
EXPECTED_ROWS = 300

ROW_RE = re.compile(r"^\| (.+) \| (\d+) \| (\d+) \|$")


class ExportError(ValueError):
    pass


def build_rows(players) -> list:
    """Return [(name, proj_dollar:int, rank:int)] in export order, validated."""
    rows = []
    for p in players:
        dollars = p["capDollars"]
        if float(dollars) != int(dollars):
            raise ExportError(f"non-integer projected $ for {p['name']}: {dollars!r}")
        rows.append((p["name"], int(dollars), int(p["oRank"])))
    rows.sort(key=lambda r: (-r[1], r[2], r[0]))

    if len(rows) != EXPECTED_ROWS:
        raise ExportError(f"expected {EXPECTED_ROWS} players, got {len(rows)}")
    names = [r[0] for r in rows]
    if len(set(names)) != len(names):
        raise ExportError("duplicate player names in Yahoo snapshot")
    if sorted(r[2] for r in rows) != list(range(1, EXPECTED_ROWS + 1)):
        raise ExportError(f"ranks are not exactly 1..{EXPECTED_ROWS} (missing or duplicate rank)")
    return rows


def render_markdown(rows) -> str:
    lines = [TITLE, "", HEADER, DIVIDER]
    lines += [f"| {name} | {dollars} | {rank} |" for name, dollars, rank in rows]
    return "\n".join(lines) + "\n"


def parse_markdown(text: str) -> list:
    """Parse the exported table back into [(name, proj_dollar, rank)]."""
    rows = []
    for line in text.splitlines():
        m = ROW_RE.match(line)
        if m and m.group(1) != "Player":
            rows.append((m.group(1), int(m.group(2)), int(m.group(3))))
    return rows


def write_markdown(players_path: str = DEFAULT_PLAYERS, out_path: str = DEFAULT_OUT) -> list:
    with open(players_path, encoding="utf-8") as f:
        players = json.load(f)
    rows = build_rows(players)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_markdown(rows))
    os.replace(tmp, out_path)
    return rows


def main():
    players_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYERS
    out_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT
    try:
        rows = write_markdown(players_path, out_path)
    except ExportError as e:
        print(f"YAHOO TOP-300 EXPORT ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Wrote {len(rows)} rows -> {out_path}")


if __name__ == "__main__":
    main()
