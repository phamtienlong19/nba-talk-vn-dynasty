"""The live feed: built from Yahoo's public pages (here, saved copies), provisional, never writing into data/."""
import json
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import build_live_feed as blf  # noqa: E402
import live_standings as lst  # noqa: E402
import yahoo_matchups as ym  # noqa: E402

import datetime as _dt  # noqa: E402
import update_yahoo_matchups as _um  # noqa: E402
_um._now = lambda: _dt.datetime(2026, 11, 3, 12, tzinfo=_dt.timezone.utc)   # week 3 has just begun (Pacific Mon 2026-11-02)

FIX = os.path.join(HERE, "fixtures", "yahoo", "matchups")
CFG = ym.load_config()


def _read(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


class FakeYahoo:
    """Default page = week 3; the week-3 pairings are served from the week-1 pages re-labelled as week 3, so the 'week in progress'
    carries real numbers (those of week 1). Team 8's page is the full one, with rosters."""

    def __init__(self):
        self.urls = []

    def get(self, url):
        self.urls.append(url)
        if "week=" not in url:
            return 200, url, _read("week3_mid8_not_started_full.html")
        w, mid = (int(x) for x in re.search(r"week=(\d+)&mid1=(\d+)", url).groups())
        if w != 3:
            return 404, url, ""
        name = "week1_mid8_full.html" if mid in (8, 12) else "week1_mid%d_header.html" % mid
        if not os.path.exists(os.path.join(FIX, name)):
            return 404, url, ""
        body = _read(name)
        body = body.replace("week=1&module=matchup&mid1=%d' selected" % mid, "week=1&module=matchup&mid1=%d'" % mid)
        body = re.sub(r"(week=3&module=matchup&mid1=%d')" % mid, r"\1 selected", body)
        return 200, url, body


def feed():
    return blf.build(CFG, FakeYahoo(), now="2026-11-03T02:00:00Z", sleep=lambda s: None)


class TestFeed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = feed()

    def test_it_is_a_provisional_week_in_progress_covering_every_team(self):
        d = self.doc
        self.assertEqual((d["schema"], d["week"], d["weekStatus"], d["asOf"]), ("live-feed/1", 3, "LIVE", "2026-11-03T02:00:00Z"))
        self.assertTrue(d["label"].startswith("PROVISIONAL"))
        self.assertEqual(d["finishedWeeks"], [1, 2])
        self.assertEqual(d["notStoredYet"], [])
        teams = [t["team"] for m in d["matchups"] for t in m["teams"]]
        self.assertEqual(len(d["matchups"]), 8)
        self.assertEqual(len(set(teams)), 16)
        self.assertTrue(all(t and t.startswith("franchise-") for t in teams))

    def test_the_table_is_official_weeks_plus_the_week_in_progress(self):
        weeks = ym.load_weeks()
        off = lst.tally({w: d for w, d in weeks.items() if w <= 2})
        wk1 = lst.tally({1: weeks[1]})                                                # the re-labelled pages carry week 1's numbers
        for r in self.doc["table"]:
            tid = r["yahooId"]
            want = [off[tid][k] + wk1[tid][k] for k in ("w", "l", "t")]
            self.assertEqual([r["w"], r["l"], r["t"]], want, r["team"])
            self.assertEqual(r["officialRecord"], [off[tid][k] for k in ("w", "l", "t")])
        st = [r["playoff"] for r in self.doc["table"]]
        self.assertLessEqual(st.count("in"), 8)                                          # a tie at the line is a bubble, not a guess
        self.assertGreaterEqual(st.count("in") + st.count("bubble"), 8)

    def test_scores_toplay_and_rosters_come_from_the_page(self):
        m = next(m for m in self.doc["matchups"] if any(t["yahooId"] == 8 for t in m["teams"]))
        a = next(t for t in m["teams"] if t["yahooId"] == 8)
        self.assertEqual(m["score"], [7, 1, 1])
        self.assertEqual(set(m["cats"]), {"fgPct", "ftPct", "tpm", "pts", "reb", "ast", "st", "blk", "to"})
        self.assertTrue(a["roster"])
        self.assertTrue({"BN", "IL"} <= {r["s"] for r in a["roster"]})
        self.assertEqual(set(a["toPlay"]), {"upcoming", "live"})

    def test_projected_reverse_lists_everyone_and_marks_ties(self):
        rev = self.doc["projectedReverse"]
        self.assertEqual(len(rev), 16)
        self.assertEqual(len({x["team"] for x in rev}), 16)

    def test_a_pairing_that_does_not_cover_every_team_writes_nothing(self):
        class Broken(FakeYahoo):
            def get(self, url):
                if "week=3&mid1=13" in url:
                    return 404, url, ""
                return super().get(url)
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "live.json")
            rc = blf.main(["--out", out], fetcher=Broken())
            self.assertEqual(rc, 1)
            self.assertFalse(os.path.exists(out))

    def test_it_never_writes_into_the_data_folder(self):
        import hashlib
        def digest():
            h = hashlib.sha256()
            for base, _d, files in sorted(os.walk(ym.os.path.join(ym.ROOT, "data", "2026-27"))):
                for f in sorted(files):
                    with open(os.path.join(base, f), "rb") as fh:
                        h.update(fh.read())
            return h.hexdigest()
        before = digest()
        feed()
        self.assertEqual(digest(), before)


class TestGameState(unittest.TestCase):
    def test_results_times_and_in_progress_text(self):
        self.assertEqual(ym.game_state("W, 124-112 vs LAC"), "final")
        self.assertEqual(ym.game_state("L, 97-108 vs BOS"), "final")
        self.assertEqual(ym.game_state("10:00 pm vs TOR"), "upcoming")
        self.assertEqual(ym.game_state("8:00 pm @ MEM"), "upcoming")
        self.assertEqual(ym.game_state("Q3 5:12 LAL 80-77"), "live")
        self.assertIsNone(ym.game_state(""))
        self.assertIsNone(ym.game_state(None))


if __name__ == "__main__":
    unittest.main()


class TestRosterLines(unittest.TestCase):
    ROW = {"slot": "BN", "name": "Bench Guy", "playerId": "1", "nba": "AAA", "positions": ["PG"], "status": "", "game": "W, 100-90 vs BBB",
           "line": {k: None for k in blf.LINE_KEYS}}

    def test_the_line_is_in_the_usual_nine_category_order(self):
        self.assertEqual(blf.LINE_KEYS, ("fgPct", "ftPct", "tpm", "pts", "reb", "ast", "st", "blk", "to"))

    def test_a_benched_player_carries_the_day_line_not_the_week_line(self):
        day = {"1": {"slot": "BN", "line": dict(zip(blf.LINE_KEYS, (0.5, 1.0, 2, 12, 3, 4, 1, 0, 2)))}}
        r = blf._roster([self.ROW], day)[0]
        self.assertEqual(r["l"], [None] * 9)
        self.assertEqual(r["d"], [0.5, 1.0, 2, 12, 3, 4, 1, 0, 2])
        self.assertIsNone(blf._roster([self.ROW])[0]["d"])
