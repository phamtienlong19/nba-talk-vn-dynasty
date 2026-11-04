"""Per-player averages from Yahoo's player list: the parser, the capture, and the Form table on the player card."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import _phone  # noqa: E402
import test_scenario_rendering as tsr  # noqa: E402
import update_yahoo_player_stats as up  # noqa: E402
import yahoo_matchups as ym  # noqa: E402
import yahoo_player_stats as ps  # noqa: E402
import yahoo_rosters as yr  # noqa: E402

FIX = os.path.join(HERE, "fixtures", "yahoo", "players")
CFG = dict(yr.load_config(), requestDelaySeconds=0)


def page(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


class TestParser(unittest.TestCase):
    def test_a_season_page_gives_each_players_averages(self):
        rows = ps.parse_page(page("season_2026_taken.html"))
        self.assertEqual(len(rows), 3)
        luka = rows[0]
        self.assertEqual((luka["playerId"], luka["name"], luka["gp"], luka["pts"], luka["reb"], luka["ast"]), ("6014", "Luka Dončić", 7, 38.3, 8.0, 8.1))
        self.assertEqual((luka["min"], luka["fgPct"], luka["ftPct"], luka["tpm"], luka["to"], luka["ros"], luka["rank"]), (35.7, 0.497, 0.887, 5.9, 5.0, 100, 1))

    def test_the_last_7_and_a_previous_season_page_read_the_same_way(self):
        self.assertEqual(ps.parse_page(page("last7_free.html"))[0]["name"], "Isaiah Stewart")
        self.assertEqual(ps.parse_page(page("season_2024_free.html"))[0]["gp"], 57)

    def test_dashes_are_missing_never_zero(self):
        html = page("last7_free.html").replace(">18.7<", ">-<", 1)
        self.assertIsNone(ps.parse_page(html)[0]["pts"])

    def test_a_table_without_rows_is_the_end_of_the_list_and_no_table_is_an_error(self):
        head = page("season_2026_taken.html")
        head = head[:head.index("<tbody>") + 7] + "</tbody></table></body></html>"
        self.assertEqual(ps.parse_page(head), [])
        with self.assertRaises(ym.MatchupError):
            ps.parse_page("<html><body>no table</body></html>")

    def test_a_changed_column_layout_is_refused(self):
        with self.assertRaises(ym.MatchupError):
            ps.parse_page(page("season_2026_taken.html").replace(">TO<", ">XX<"))

    def test_the_document_keeps_the_rows_as_arrays_in_a_fixed_order(self):
        doc = ps.build({"season": ps.parse_page(page("season_2026_taken.html"))}, "2026-11-04T10:00:00Z")
        self.assertEqual(doc["keys"], list(ps.KEEP))
        self.assertEqual(doc["windows"]["season"]["6014"][ps.KEEP.index("pts")], 38.3)


class FakeYahoo:
    """Serves the fixture page for the first page of every window and an empty page after it."""
    def __init__(self, status=200, rows=None):
        self.urls, self.status = [], status
        head = page("season_2026_taken.html")
        self.empty = head[:head.index("<tbody>") + 7] + "</tbody></table></body></html>"
        self.full = page("season_2026_taken.html")

    def get(self, url):
        self.urls.append(url)
        if self.status != 200:
            return self.status, url, ""
        return 200, url, self.full if url.endswith("count=0") else self.empty


class TestCapture(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.path = os.path.join(self.d, "player_stats.json")
        self.out = []
        self.min = up.MIN_PLAYERS
        up.MIN_PLAYERS = 1

    def tearDown(self):
        up.MIN_PLAYERS = self.min

    def run_it(self, fetcher):
        return up.run(CFG, fetcher, self.path, sleep=lambda s: None, out=self.out.append)

    def test_every_window_is_walked_until_an_empty_page_and_written_once(self):
        f = FakeYahoo()
        self.assertEqual(self.run_it(f), 0)
        self.assertEqual(len(f.urls), 12)                                           # six windows, a full page and an empty one
        self.assertTrue(all("status=T" in u for u in f.urls))
        doc = json.load(open(self.path, encoding="utf-8"))
        self.assertEqual(sorted(doc["windows"]), sorted(k for k, _ in ps.WINDOWS))

    def test_a_failure_writes_nothing_and_keeps_the_previous_file(self):
        with open(self.path, "w") as fh:
            fh.write("previous")
        self.assertEqual(self.run_it(FakeYahoo(status=404)), 1)
        self.assertEqual(open(self.path).read(), "previous")

    def test_a_short_season_window_is_not_trusted(self):
        up.MIN_PLAYERS = 150
        self.assertEqual(self.run_it(FakeYahoo()), 1)
        self.assertFalse(os.path.exists(self.path))


@unittest.skipUnless(tsr._chrome(), "no Chrome")
class TestCard(unittest.TestCase):
    DOC = {"schema": "yahoo-player-stats/1", "capturedAt": "2026-11-04T10:00:00Z", "keys": list(ps.KEEP),
           "windows": {"season": {}, "l7": {}, "l30": {}}}

    K, NONE = "478.p.10572", "478.p.1"                                             # a rostered player, and an id that has no averages

    def js(self):
        return ("var k='%s',id='10572',doc=%s;doc.windows.season[id]=[7,35.7,38.3,8,8.1,1.9,0.7,5.9,0.497,0.887,5];doc.windows.l7[id]=[3,31,22.5,6,4,1,0,2,0.4,0.9,3];"
                "NBA_PLAYER.formSet(doc);var c=NBA_PLAYER.card(k);document.body.appendChild(c);"
                "var sec=c.querySelector('.plc-form');R.shown=!sec.hidden;R.rows=sec.querySelectorAll('tbody tr').length;R.head=[].map.call(sec.querySelectorAll('thead th'),function(x){return x.textContent;});"
                "R.first=[].map.call(sec.querySelector('tbody tr').children,function(x){return x.textContent;});R.title=sec.querySelector('.plc-k').textContent;"
                "R.text=NBA_PLAYER.text(k);R.sw=document.documentElement.scrollWidth;R.cw=document.documentElement.clientWidth;"
                "var o=NBA_PLAYER.card('478.p.6014');R.other=o?o.querySelector('.plc-form').hidden:null;") % (self.K, json.dumps(self.DOC))

    def test_the_form_table_shows_the_windows_that_exist_and_hides_for_a_player_without_any(self):
        r = _phone.phone_run(self.js(), pre_js="localStorage.setItem('nbaTalkVN.myTeam','franchise-05')", wait_ms=2500)
        self.assertIsNone(r.get("error"), r)
        self.assertTrue(r["shown"])
        self.assertEqual(r["rows"], 2)                                              # season and last 7 only; empty windows are left out
        self.assertEqual(r["head"][:4], ["", "GP", "MIN", "PTS"])
        self.assertEqual(r["first"][:4], ["This season", "7", "35.7", "38.3"])
        self.assertIn("AS OF", r["title"])
        self.assertIn("This season: 7 GP · 38.3 PTS", r["text"])
        self.assertTrue(r["other"])
        self.assertLessEqual(r["sw"], r["cw"], "the table scrolls inside the card, not the page")


if __name__ == "__main__":
    unittest.main()
