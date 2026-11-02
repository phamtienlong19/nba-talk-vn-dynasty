#!/usr/bin/env python3
"""Embed the LIVE tab into index.html (a generated block, like the What If block): the section, its CSS, its JS and a small data block
with the team colours and an official fallback built from the stored finished weeks. The live numbers themselves are fetched by the
page from the live-data branch (scripts/build_live_feed.py writes them); this block never contains a live number.

    python3 scripts/live_page.py embed        # rebuild and splice the block into index.html (before the what-if / league-data block)
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_fa_draft_pool as pool  # noqa: E402
import import_rosters as ir  # noqa: E402
import league_state as ls  # noqa: E402
import live_standings as lst  # noqa: E402
import season_state as ss  # noqa: E402
import yahoo_matchups as ym  # noqa: E402
import yahoo_rosters as yr  # noqa: E402
import yahoo_standings as ys  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
APP_JS, APP_CSS = os.path.join(HERE, "live_app.js"), os.path.join(HERE, "live.css")
INDEX_HTML = os.path.join(ls.REPO_ROOT, "index.html")
BEGIN, END = "<!--LIVE-BEGIN-->", "<!--LIVE-END-->"
LEAGUE_BEGIN = "<!--LEAGUE-DATA-BEGIN-->"
WHATIF_BEGIN = "<!--WHATIF-BEGIN-->"
LIVE_URL = "https://raw.githubusercontent.com/phamtienlong19/nba-talk-vn-dynasty/live-data/live.json"
SECTION_HTML = '<section class="page tab-off" id="live"><div class="title">LIVE</div><div id="live-root"></div></section>'


def fallback(data_dir=ss.DATA_DIR, matchup_dir=ym.MATCHUP_DIR) -> dict:
    """A feed-shaped document from the stored FINISHED weeks only (no live numbers): used until the live feed loads or when it fails."""
    cfg = yr.load_config()
    weeks = ym.load_weeks(matchup_dir)
    team_map, _ = ir.load_maps(data_dir)
    fid = lambda tid: yr.franchise_for(cfg, team_map, tid)  # noqa: E731
    snap = ys.current_snapshot(os.path.join(data_dir, "standings"))
    divisions = {t["teamId"]: t["division"] for t in (snap or {}).get("teams", [])}
    order = [t["teamId"] for t in sorted((snap or {}).get("teams", []), key=lambda t: t["rank"])]
    rows = lst.table(lst.tally(weeks), None, divisions)
    pic = lst.playoff_picture(rows, cfg.get("playoffs"))
    proj = lst.projected_snapshot(rows, order)
    table = [{"team": fid(r["teamId"]), "yahooId": r["teamId"], "name": None, "w": r["w"], "l": r["l"], "t": r["t"], "pct": r["pct"],
              "rank": r["rank"], "tied": r["tied"], "gb": r["gb"], "division": r["division"], "officialRank": r["rank"],
              "officialRecord": [r["w"], r["l"], r["t"]], "moved": 0, "playoff": pic["status"].get(r["teamId"]), "seed": pic["seeds"].get(r["teamId"])}
             for r in rows]
    matchups = []
    if weeks:
        last = weeks[max(weeks)]
        for m in last["matchups"]:
            res = m["result"]
            matchups.append({"teams": [{"team": fid(t["teamId"]), "yahooId": t["teamId"], "name": t["name"], "stats": t["stats"], "printed": t["printedWins"],
                                       "toPlay": {"upcoming": 0, "live": 0}, "roster": []} for t in m["teams"]],
                             "cats": res["cats"], "score": [res["a"], res["b"], res["t"]], "decided": True})
    return {"schema": "live-feed/1", "label": "official finished weeks", "asOf": None, "week": max(weeks) if weeks else None, "weekStatus": "OFFICIAL",
            "table": table, "playoff": {"spots": pic["spots"], "divisionTie": pic["divisionTie"], "linePct": pic["linePct"]},
            "projectedReverse": [{"team": fid(t["teamId"]), "tied": t["tied"]} for t in reversed(proj["teams"])], "tiedRanks": proj["tiedRanks"],
            "matchups": matchups}


def payload() -> dict:
    inputs = ls.load_inputs()
    teams = [{"id": t["franchiseId"], "short": t["short"], "color": t["color"], "text": t["text"],
              "crown": t["short"] == pool.DEFENDING_CHAMPION_SHORT_NAME} for t in inputs["freeze"]["teams"]]
    return {"liveUrl": LIVE_URL, "teams": teams, "fallback": fallback()}


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
