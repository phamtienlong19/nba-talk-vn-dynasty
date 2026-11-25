#!/usr/bin/env python3
"""Embed the LIVE tab into index.html (a generated block, like the What If block): the section, its CSS, its JS and a small data block
with the team colours and rookie ids. The lineups themselves are fetched by the page from the live-data branch
(scripts/build_live_feed.py writes them); this block never contains a live fact.

    python3 scripts/live_page.py embed        # rebuild and splice the block into index.html (before the what-if / league-data block)
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_fa_draft_pool as pool  # noqa: E402
import build_league_state as bls  # noqa: E402
import import_rosters as ir  # noqa: E402
import league_state as ls  # noqa: E402
import season_state as ss  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
APP_JS, APP_CSS = os.path.join(HERE, "live_app.js"), os.path.join(HERE, "live.css")
INDEX_HTML = os.environ.get("NBA_INDEX_HTML") or os.path.join(ls.REPO_ROOT, "index.html")
BEGIN, END = "<!--LIVE-BEGIN-->", "<!--LIVE-END-->"
LEAGUE_BEGIN = "<!--LEAGUE-DATA-BEGIN-->"
WHATIF_BEGIN = "<!--WHATIF-BEGIN-->"
LIVE_URL = "https://raw.githubusercontent.com/phamtienlong19/nba-talk-vn-dynasty/live-data/live.json"
SECTION_HTML = '<section class="page tab-off" id="live"><div class="title">LIVE</div><div id="live-root"></div></section>'


def payload() -> dict:
    inputs = ls.load_inputs()
    teams = [{"id": t["franchiseId"], "short": t["short"], "color": t["color"], "text": t["text"],
              "crown": t["short"] == pool.DEFENDING_CHAMPION_SHORT_NAME} for t in inputs["freeze"]["teams"]]
    prefix = ir.GAME_KEY + ".p."                                     # Yahoo player ids of the 2026 rookies (same set as the rest of the site)
    rookies = sorted(k[len(prefix):] for k in bls.rookie_keys(ss.load_season(inputs)) if k.startswith(prefix))
    return {"liveUrl": LIVE_URL, "teams": teams, "rookies": rookies}


def render_block(data: dict) -> str:
    with open(APP_JS, encoding="utf-8") as f:
        js = f.read()
    with open(APP_CSS, encoding="utf-8") as f:
        css = f.read()
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (BEGIN + SECTION_HTML + '<style id="live-css">' + css + "</style>" + '<script type="application/json" id="live-data">' + blob + "</script>"
            + '<script id="live-app">' + js + "</script>" + END + "\n")


def _end(html: str) -> int:
    e = html.index(END) + len(END)
    return e + 1 if html[e:e + 1] == "\n" else e


def embed(html: str, data: dict) -> str:
    block = render_block(data)
    if BEGIN in html:
        return html[:html.index(BEGIN)] + block + html[_end(html):]
    anchor = WHATIF_BEGIN if WHATIF_BEGIN in html else LEAGUE_BEGIN
    if anchor not in html:
        raise ValueError("index.html has no what-if or league-data block to anchor the live block before")
    return html.replace(anchor, block + anchor, 1)


def strip_block(html: str) -> str:
    return html if BEGIN not in html else html[:html.index(BEGIN)] + html[_end(html):]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("embed",))
    ap.parse_args(argv)
    with open(INDEX_HTML, encoding="utf-8") as f:
        html = f.read()
    new = embed(html, payload())
    if new != html:
        with open(INDEX_HTML, "w", encoding="utf-8") as f:
            f.write(new)
    print("live block embedded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
