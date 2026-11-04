"""The Trade Machine starts from the page's league and stacks "your sketch" trades: trade 2 is checked against the league after trade 1."""
import html as html_lib
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_scenario_rendering as tsr  # noqa: E402

INDEX = os.path.join(HERE, "..", "index.html")
PLAYER, FROM, TO = "478.p.5432", None, "franchise-01"
FIND = """
  var D=NBA_NAV.D,ts=D.teams.map(function(t){return t.id;}),found=null;
  for(var i=0;i<ts.length&&!found;i++)for(var j=i+1;j<ts.length&&!found;j++){var A=D.scenarios[''].teams[ts[i]].roster,B=D.scenarios[''].teams[ts[j]].roster;
    for(var a=0;a<A.length&&!found;a++)for(var b=0;b<B.length&&!found;b++){if(Math.abs(A[a].c-B[b].c)>2)continue;
      var mv=[{key:A[a].k,from:ts[i],to:ts[j]},{key:B[b].k,from:ts[j],to:ts[i]}],r=NBA_CHK.run(mv);if(r.status==='LEGAL')found=mv;}}
  R.found=found;"""


@unittest.skipUnless(tsr._chrome(), "no Chrome")
class TestTradeSketch(unittest.TestCase):
    def drive(self, body_js, qs="", wait=2500):
        with open(INDEX, encoding="utf-8") as f:
            page = f.read()
        script = ("<script>(function(){var R={};setTimeout(function(){try{" + body_js + "}catch(e){R.error=String(e&&e.stack||e);}"
                  "setTimeout(function(){var p=document.createElement('pre');p.id='o';p.textContent=JSON.stringify(R);document.body.appendChild(p);},%d);},500);})();</script>" % wait)
        page = page[:page.rindex("</body>")] + script + page[page.rindex("</body>"):]
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, "index.html")
            with open(path, "w", encoding="utf-8") as f:
                f.write(page)
            out = tsr._chrome_run(["--window-size=1200,1400", "--virtual-time-budget=10000", "--dump-dom", "file://" + path + qs], 150).stdout
        finally:
            shutil.rmtree(d)
        m = re.search(r'<pre id="o">(.*?)</pre>', out, re.S)
        self.assertIsNotNone(m, out[-300:])
        r = json.loads(html_lib.unescape(m.group(1)))
        self.assertNotIn("error", r, r.get("error"))
        return r

    def test_a_blocked_trade_cannot_be_stacked(self):
        r = self.drive("var b=document.getElementById('chk-stack');R.disabled=!!b&&b.disabled;R.status=document.getElementById('chk-top').textContent;", qs="?check=%s~%s" % (PLAYER, TO))
        if r["status"] == "BLOCKED":
            self.assertTrue(r["disabled"])

    def test_the_machine_says_where_it_starts_from(self):
        r = self.drive("R.base=document.querySelector('#chk .chk-base').textContent;", qs="?check=%s~%s" % (PLAYER, TO))
        self.assertIn("Starting from", r["base"])
        self.assertIn("official rosters", r["base"])

    def legal(self):
        if not hasattr(TestTradeSketch, "_legal"):
            TestTradeSketch._legal = self.drive(FIND)["found"]
        self.assertIsNotNone(TestTradeSketch._legal, "no legal one-for-one swap found")
        mv = TestTradeSketch._legal
        return mv, "?check=" + ",".join(m["key"] + "~" + m["to"] for m in mv)

    def test_a_stacked_trade_is_checked_against_the_league_after_the_first(self):
        mv, q = self.legal()
        r = self.drive("""
          R.before=NBA_CHK.owner('%(k)s');document.getElementById('chk-stack').click();
          R.after=NBA_CHK.owner('%(k)s');R.stack=NBA_CHK.stack().length;R.tag=(document.querySelector('#chk .bdg.sketch')||{}).textContent||'';
          R.param=NBA_CHK.param();
          var back=NBA_CHK.run([{key:'%(k)s',from:'%(to)s',to:R.before}]);R.status=back.status;
          R.reasons=back.rules.filter(function(x){return x.level!=='ok';}).map(function(x){return x.reason;}).join(' | ');""" % {"k": mv[0]["key"], "to": mv[0]["to"]},
                       qs=q)
        self.assertNotEqual(r["before"], mv[0]["to"])
        self.assertEqual(r["after"], mv[0]["to"])                                                   # trade 2 sees him on his new team
        self.assertEqual(r["stack"], 1)
        self.assertIn("SKETCH", r["tag"])
        self.assertIn("stack=", r["param"])
        self.assertNotEqual(r["status"], "LEGAL", r["reasons"])                            # sending him straight back: the cooldown applies

    def test_the_sketch_survives_the_link(self):
        mv, q0 = self.legal()
        first = self.drive("document.getElementById('chk-stack').click();R.param=NBA_CHK.param();", qs=q0)
        q = "?" + first["param"]
        r = self.drive("R.stack=NBA_CHK.stack().length;R.owner=NBA_CHK.owner('%s');R.list=document.querySelectorAll('#chk .chk-stack li').length;" % mv[0]["key"], qs=q)
        self.assertEqual((r["stack"], r["owner"], r["list"]), (1, mv[0]["to"], 1))

    def test_removing_a_sketch_trade_puts_the_player_back(self):
        mv, q = self.legal()
        r = self.drive("""var before=NBA_CHK.owner('%(k)s');document.getElementById('chk-stack').click();
          document.querySelector('#chk .chk-stack .chk-x').click();R.back=NBA_CHK.owner('%(k)s')===before;R.stack=NBA_CHK.stack().length;""" % {"k": mv[0]["key"]},
                       qs=q)
        self.assertTrue(r["back"])
        self.assertEqual(r["stack"], 0)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(tsr._chrome(), "no Chrome")
class TestPlayerSheetAndShare(TestTradeSketch):
    def test_a_team_card_row_opens_the_player_sheet_with_league_facts(self):
        r = self.drive("""var row=document.querySelector('section.team-card .player-row[data-k]');R.k=row.getAttribute('data-k');R.role=row.getAttribute('role');row.click();
          var s=document.getElementById('pl-sheet');R.open=!!s;R.tiles=Array.prototype.map.call(s.querySelectorAll('.plc-t > span'),function(x){return x.textContent;});
          R.pills=Array.prototype.map.call(s.querySelectorAll('.plc-p'),function(x){return x.textContent;});
          R.btns=Array.prototype.map.call(s.querySelectorAll('.pls-b'),function(x){return x.textContent;});R.text=s.textContent;""")
        self.assertTrue(r["open"])
        self.assertEqual(r["role"], "button")
        self.assertEqual(r["tiles"], ["SALARY NOW", "NEXT YEAR", "KEEPER RANK"])
        self.assertTrue(any("Tradable" in p for p in r["pills"]), r["pills"])
        self.assertEqual(r["btns"][:3], ["Add to Trade Machine", "Show on team card", "Show in Keepers"])
        self.assertIn("Export", r["btns"])
        self.assertIn("Copy link", r["btns"])
        for word in ("should", "recommend", "fair"):                                      # facts, never advice
            self.assertNotIn(word, r["text"].lower())

    def test_add_to_trade_machine_puts_him_in_the_trade(self):
        r = self.drive("""var row=document.querySelectorAll('section.team-card .player-row[data-k]')[3];R.k=row.getAttribute('data-k');row.click();
          document.querySelector('#pl-sheet .pls-b.pri').click();R.param=NBA_CHK.param();R.tab=document.querySelector('.navlink.on').dataset.tab;R.sheet=!!document.getElementById('pl-sheet');""")
        self.assertIn(r["k"] + "~", r["param"])
        self.assertEqual(r["tab"], "trade-lab")
        self.assertFalse(r["sheet"])

    def test_every_team_card_and_the_cap_grid_have_a_share_button_that_opens_its_own_image(self):
        r = self.drive("""R.cards=document.querySelectorAll('section.team-card').length;R.btns=document.querySelectorAll('section.team-card .share-btn').length;
          R.cap=!!document.querySelector('#cap .title .share-btn');document.querySelector('section.team-card .share-btn').click();
          setTimeout(function(){var ov=document.getElementById('chk-imgov');R.ov=!!ov;R.ttl=ov?(ov.querySelector('.imgov-ttl')||{}).textContent:'';},5000);""", wait=7000)
        self.assertEqual(r["btns"], r["cards"])
        self.assertTrue(r["cap"])
        self.assertTrue(r["ov"])
        self.assertIn("roster", r["ttl"])
