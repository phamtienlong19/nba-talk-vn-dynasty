"""Stored finished weeks: final, reproducible from their own totals, and the capture script stores only finished, validated, never-overwritten weeks."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import update_yahoo_matchups as um  # noqa: E402
import yahoo_matchups as ym  # noqa: E402

import datetime as _dt  # noqa: E402
import update_yahoo_matchups as _um  # noqa: E402
_um._now = lambda: _dt.datetime(2026, 11, 3, 12, tzinfo=_dt.timezone.utc)   # week 3 has just begun (Pacific Mon 2026-11-02)

FIX = os.path.join(HERE, "fixtures", "yahoo")
CFG = ym.load_config()


class TestStoredWeeks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.weeks = ym.load_weeks()

    def test_weeks_one_and_two_are_stored_final_and_cover_every_team_once(self):
        for w in (1, 2):
            d = self.weeks[w]
            self.assertEqual((d["status"], d["week"], len(d["matchups"])), ("FINAL", w, 8))
            ids = sorted(t["teamId"] for m in d["matchups"] for t in m["teams"])
            self.assertEqual(ids, sorted(CFG["teamIds"]))
            self.assertEqual(d["digest"], ym._digest(d))

    def test_every_stored_result_is_reproduced_from_its_own_totals(self):
        for w, d in self.weeks.items():
            for m in d["matchups"]:
                a, b = (t["stats"] for t in m["teams"])
                res = ym.category_results(a, b)
                self.assertEqual(m["result"], {"cats": res["cats"], "a": res["a"], "b": res["b"], "t": res["t"]}, (w, m["teams"][0]["teamId"]))
                self.assertEqual((m["teams"][0]["printedWins"], m["teams"][1]["printedWins"]), (res["a"], res["b"]))

class FakeYahoo:
    """Serves the saved pages: the default page is week 3 (not started), week-1 pages by team id."""
    CURRENT = "week3_mid8_not_started_full.html"

    def __init__(self, tamper=None):
        self.tamper, self.urls = tamper, []

    def get(self, url):
        self.urls.append(url)
        if "week=" not in url:
            name = self.CURRENT
        else:
            import re
            w, mid = (int(x) for x in re.search(r"week=(\d+)&mid1=(\d+)", url).groups())
            name = "week%d_mid%d_header.html" % (w, mid)
            if w != 1 or not os.path.exists(os.path.join(FIX, "matchups", name)):
                return 404, url, ""
        with open(os.path.join(FIX, "matchups", name), encoding="utf-8") as f:
            body = f.read()
        if self.tamper and "week=1&mid1=%d" % self.tamper in url:
            body = body.replace(">528<", ">529<", 1)
        return 200, url, body


class TestCapture(unittest.TestCase):
    def go(self, fetcher, d, **k):
        lines = []
        rc = um.run(CFG, fetcher, apply=True, matchup_dir=d, sleep=lambda s: None, out=lines.append, **k)
        return rc, lines

    def test_a_finished_week_is_walked_validated_and_stored_once(self):
        with tempfile.TemporaryDirectory() as d:
            f = FakeYahoo()
            rc, lines = self.go(f, d, weeks=[1])
            self.assertEqual(rc, 0, lines)
            doc = ym.load_weeks(d)[1]
            self.assertEqual((doc["status"], len(doc["matchups"])), ("FINAL", 8))
            self.assertEqual(len([u for u in f.urls if "week=1" in u]), 8)                           # one request per pairing, not per team
            rc, lines = self.go(FakeYahoo(), d, weeks=[1])
            self.assertTrue(any("NO_CHANGE" in x for x in lines), lines)                            # same data: nothing rewritten

    def test_a_changed_finished_week_is_a_conflict_and_the_stored_week_is_kept(self):
        with tempfile.TemporaryDirectory() as d:
            self.go(FakeYahoo(), d, weeks=[1])
            before = ym.load_weeks(d)[1]["digest"]
            rc, lines = self.go(FakeYahoo(tamper=8), d, weeks=[1])
            self.assertEqual(rc, 1)
            self.assertTrue(any("FAILED" in x or "CONFLICT" in x for x in lines), lines)
            self.assertEqual(ym.load_weeks(d)[1]["digest"], before)

    def test_the_current_week_is_never_stored(self):
        with tempfile.TemporaryDirectory() as d:
            rc, lines = self.go(FakeYahoo(), d, weeks=[3])
            self.assertEqual(rc, 1)
            self.assertEqual(ym.load_weeks(d), {})

    def test_a_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            lines = []
            um.run(CFG, FakeYahoo(), weeks=[1], apply=False, matchup_dir=d, sleep=lambda s: None, out=lines.append)
            self.assertEqual(ym.load_weeks(d), {})


class TestCurrentWeek(unittest.TestCase):
    def test_weeks_are_counted_from_the_first_monday_in_pacific_time(self):
        cfg = {"seasonStartMonday": "2026-10-19"}
        orig = um._now
        try:
            for utc, week in [((2026, 10, 19, 8), 1), ((2026, 11, 2, 7), 2), ((2026, 11, 2, 8), 3), ((2026, 11, 9, 7), 3), ((2027, 6, 1, 0), 20)]:
                um._now = lambda utc=utc: _dt.datetime(*utc, tzinfo=_dt.timezone.utc)
                self.assertEqual(um.current_week(cfg), week, utc)
        finally:
            um._now = orig


if __name__ == "__main__":
    unittest.main()
