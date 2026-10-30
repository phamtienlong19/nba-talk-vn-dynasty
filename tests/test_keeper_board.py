"""Keeper board (What-If KEEPERS view): the stored rank -> salary table and the page behaviour, both derived from data."""
import html as html_lib
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, HERE)
import cap_model as cm  # noqa: E402
import keeper_rank_salary as krs  # noqa: E402
import test_scenario_rendering as tsr  # noqa: E402

ROOT = os.path.join(HERE, "..")
CFG = os.path.join(ROOT, "config", "keeper_salary_by_rank.json")
PLAYERS = os.path.join(ROOT, "data", "yahoo", "players_normalized.json")
INDEX = os.path.join(ROOT, "index.html")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestRankSalaryTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load(CFG)
        cls.players = load(PLAYERS)

    def test_the_table_is_the_sorted_dollar_curve(self):
        s = self.cfg["salaryByRank"]
        self.assertTrue(all(a >= b for a, b in zip(s, s[1:])), "salary never rises as rank gets worse")
        self.assertTrue(all(x > 0 for x in s))                                           # only paid ranks are listed; the rest are $0
        self.assertEqual(self.cfg["source"]["paidRanks"], len(s))
        self.assertEqual(len(self.cfg["order"]), len(set(self.cfg["order"])))

    def test_rank_follows_the_dollar_order_not_the_o_rank_column(self):
        by_key = {p["playerKey"]: p for p in self.players}
        gaps = [(abs(i + 1 - by_key[k]["oRank"]), k) for i, k in enumerate(self.cfg["order"][:len(self.cfg["salaryByRank"])]) if k in by_key]
        gap, key = max(gaps)
        self.assertGreater(gap, 5, "the Yahoo snapshot has no player whose O-Rank and dollar rank disagree")
        rank = self.cfg["order"].index(key) + 1
        self.assertEqual(self.cfg["salaryByRank"][rank - 1], by_key[key]["capDollars"])  # his salary is the one at his ACTUAL rank
        self.assertNotEqual(by_key[key]["oRank"], rank)

    def test_table_matches_the_cap_model_band(self):
        m = cm.compute_cap_model(self.players)
        self.assertEqual(self.cfg["capModel"]["top144Sum"], m["top144Sum"])
        self.assertEqual(sum(self.cfg["salaryByRank"][:144]), m["top144Sum"])         # the band depends only on the curve: re-ranking never moves it

    def test_committed_table_is_rebuilt_from_the_current_snapshot(self):
        prov = load(os.path.join(ROOT, "data", "yahoo", "provenance.json"))
        if prov.get("fetchedAt") != self.cfg["source"]["fetchedAt"]:
            self.skipTest("Yahoo snapshot has moved on: run scripts/keeper_rank_salary.py and commit the new table")
        self.assertEqual(krs.build(self.players, {k: self.cfg["source"][k] for k in ("file", "fetchedAt", "league")}), self.cfg)

    def test_ties_break_by_o_rank_then_name(self):
        rows = krs.ranked([{"playerKey": "a", "name": "B", "capDollars": 5.0, "oRank": 2}, {"playerKey": "b", "name": "A", "capDollars": 5.0, "oRank": 1},
                           {"playerKey": "c", "name": "C", "capDollars": 9.0, "oRank": 3}])
        self.assertEqual([r["playerKey"] for r in rows], ["c", "b", "a"])
        with self.assertRaises(krs.RankSalaryError):
            krs.ranked([{"playerKey": "a", "name": "A", "capDollars": 5.0, "oRank": 1}, {"playerKey": "a", "name": "B", "capDollars": 4.0, "oRank": 2}])


@unittest.skipUnless(tsr._chrome(), "no Chrome")
class TestKeeperBoardPage(unittest.TestCase):
    def drive(self, body_js, hash_="#whatif", qs="?mode=whatif&view=keepers", head_js=""):
        with open(INDEX, encoding="utf-8") as f:
            html = f.read()
        script = ("<script>(function(){var R={};setTimeout(function(){try{" + body_js + "}catch(e){R.error=String(e&&e.stack||e);}"
                  "var p=document.createElement('pre');p.id='o';p.textContent=JSON.stringify(R);document.body.appendChild(p);},700);})();</script>")
        if head_js:
            html = html.replace("<head>", "<head><script>" + head_js + "</script>", 1)
        html = html[:html.rindex("</body>")] + script + html[html.rindex("</body>"):]
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, "index.html")
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            out = tsr._chrome_run(["--window-size=1000,1600", "--virtual-time-budget=8000", "--dump-dom", "file://" + path + qs], 120).stdout
        finally:
            shutil.rmtree(d)
        m = re.search(r'<pre id="o">(.*?)</pre>', out, re.S)
        self.assertIsNotNone(m, out[-300:])
        r = json.loads(html_lib.unescape(m.group(1)))
        self.assertNotIn("error", r, r.get("error"))
        return r

    SETUP = """
      var W=JSON.parse(document.getElementById('whatif-data').textContent).keeperBoard,cfgS=W.salaryByRank;
      var rowsEl=function(){return Array.prototype.slice.call(document.querySelectorAll('#wi-root .wi-kb tbody tr'));};
      var info=function(){return rowsEl().map(function(tr){return {k:tr.getAttribute('data-k'),rank:+tr.querySelector('.wi-kb-rk').value,sal:+tr.lastChild.textContent};});};
    """

    def test_salaries_follow_rank_and_a_rerank_shifts_them(self):
        r = self.drive(self.SETUP + """
          var a=info();R.n=a.length;R.ok=a.every(function(x){return x.sal===(cfgS[x.rank-1]||0);});
          R.sorted=a.every(function(x,i){return i===0||a[i-1].rank<=x.rank;});
          var first=a[0];var inp=document.querySelector('#wi-root .wi-kb tbody tr .wi-kb-rk');inp.value='200';inp.dispatchEvent(new Event('change'));
          var b=info();R.moved=b.filter(function(x){return x.k===first.k;})[0];R.ok2=b.every(function(x){return x.sal===(cfgS[x.rank-1]||0);});
          R.firstSal=first.sal;R.url=location.search;""")
        self.assertGreater(r["n"], 5)
        self.assertTrue(r["ok"])
        self.assertTrue(r["sorted"])
        self.assertEqual(r["moved"]["rank"], 200)                                          # pinned to exactly the rank asked for
        self.assertEqual(r["moved"]["sal"], 0)                                             # beyond the paid ranks
        self.assertTrue(r["ok2"])
        self.assertIn("rk=" + r["moved"]["k"] + ":200", r["url"])                          # and the URL remembers it

    def test_keepers_are_capped_checked_against_the_band_and_remembered(self):
        r = self.drive(self.SETUP + """
          var boxes=function(){return Array.prototype.slice.call(document.querySelectorAll('#wi-root .wi-kb tbody input[type=checkbox]'));};
          var n=boxes().length;for(var i=0;i<Math.min(n,12);i++){var b=boxes()[i];if(!b.disabled){b.checked=true;b.dispatchEvent(new Event('change'));}}
          R.kept=boxes().filter(function(b){return b.checked;}).length;R.max=W.keeperMax;
          R.stat=document.querySelector('#wi-root .wi-stats').textContent;
          R.pay=info().filter(function(x,i){return boxes()[i].checked;}).reduce(function(s,x){return s+x.sal;},0);
          R.ls=localStorage.getItem('nbaTalkVN.keeperBoard');R.url=location.search;R.band=W.band;""")
        self.assertEqual(r["kept"], min(r["max"], r["kept"]))
        self.assertLessEqual(r["kept"], r["max"])                                          # a tenth keeper cannot be ticked
        self.assertIn("KEEPER PAYROLL", r["stat"])
        self.assertIn(str(r["pay"]), r["stat"])
        self.assertIn("keep=", r["url"])
        self.assertIn('"keep"', r["ls"])

    def test_unkept_player_warnings_wait_until_a_keeper_is_chosen(self):
        r = self.drive(self.SETUP + """
          R.none=document.querySelectorAll('#wi-root .wi-kb-flag').length;
          var b=document.querySelector('#wi-root .wi-kb tbody input[type=checkbox]');b.checked=true;b.dispatchEvent(new Event('change'));
          R.some=document.querySelectorAll('#wi-root .wi-kb-flag').length;""")
        self.assertEqual(r["none"], 0)                                                     # nothing chosen yet: no wall of warnings

    def test_a_shared_link_restores_the_plan_and_reset_clears_it(self):
        board = None
        with open(INDEX, encoding="utf-8") as f:
            board = json.loads(re.search(r'id="whatif-data">(.*?)</script>', f.read(), re.S).group(1).replace("<\\/", "</"))["keeperBoard"]
        team = board["teams"][0]
        k1, k2 = team["players"][0]["k"], team["players"][1]["k"]
        r = self.drive(self.SETUP + """
          R.checked=Array.prototype.slice.call(document.querySelectorAll('#wi-root .wi-kb tbody tr.kept')).map(function(t){return t.getAttribute('data-k');});
          R.ranks=info().filter(function(x){return x.k==='%s';})[0];
          document.getElementById('kb-reset').click();R.after=info().filter(function(x){return x.k==='%s';})[0];""" % (k1, k1),
                       qs="?mode=whatif&view=keepers&team=%s&keep=%s,%s&rk=%s:77" % (team["id"], k1, k2, k1))
        self.assertEqual(sorted(r["checked"]), sorted([k1, k2]))
        self.assertEqual(r["ranks"]["rank"], 77)
        self.assertNotEqual(r["after"]["rank"], 77)                                        # reset returns him to Yahoo's order
