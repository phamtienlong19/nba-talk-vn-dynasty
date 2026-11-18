#!/usr/bin/env python3
"""Resolve the one kind of merge conflict that is not a real conflict: the GENERATED one-line JSON data blocks of index.html
(league-data, whatif-data, live ...). Every roster / standings / metadata refresh regenerates them, so any open PR that also regenerates them collides
the moment another refresh merges. The blocks are derived from data/ and config/ by scripts/build_league_state.py, what_if.py and live_page.py, so the
right resolution is mechanical: take main's line, then re-run the embeds (scripts/heal_open_prs.sh does both).

    python3 scripts/resolve_generated_conflicts.py index.html     # exit 0: resolved in place; exit 4: a conflict that is NOT only generated blocks (left untouched)

It refuses (and changes nothing) when ANY conflict hunk is something else, e.g. hand-edited markup: a human decides those.
"""
from __future__ import annotations

import re
import sys

HUNK = re.compile(r"<<<<<<< [^\n]*\n(.*?)\n=======\n(.*?)\n>>>>>>> [^\n]*\n", re.S)


def is_generated(side: str) -> bool:
    return "\n" not in side and 'type="application/json" id="' in side


def resolve(text: str):
    """-> the text with every conflict hunk resolved to the incoming (main) side, or None when a hunk is not a generated data block."""
    hunks = HUNK.findall(text)
    if not hunks:
        return None
    if not all(is_generated(a) and is_generated(b) for a, b in hunks):
        return None
    return HUNK.sub(lambda m: m.group(2) + "\n", text)


def main(argv=None) -> int:
    path = (argv or sys.argv[1:] or ["index.html"])[0]
    with open(path, encoding="utf-8") as f:
        text = f.read()
    out = resolve(text)
    if out is None:
        print("not only generated data blocks: left untouched")
        return 4
    with open(path, "w", encoding="utf-8") as f:
        f.write(out)
    print("resolved %d generated block(s)" % len(HUNK.findall(text)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
