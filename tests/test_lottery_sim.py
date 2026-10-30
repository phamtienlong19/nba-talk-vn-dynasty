"""Lottery simulator in index.html: the page's own draw functions run under node against the embedded provisional data."""
import json
import os
import re
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(os.path.dirname(__file__), "..", "index.html")
HTML = open(INDEX, encoding="utf-8").read()
DATA = json.loads(re.search(r'id="league-data">(.*?)</script>', HTML, re.S).group(1).replace("<\\/", "</"))
FUNCS = re.search(r"(function lotPick\(.*?)function renderLottery\(\)", HTML, re.S).group(1)


def node(script):
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@unittest.skipUnless(shutil.which("node"), "node not installed")
class TestLotterySim(unittest.TestCase):
    def sim(self, lottery, n):
        return node(FUNCS + "var L=%s,r=[];for(var i=0;i<%d;i++)r.push(lotDraw(L));console.log(JSON.stringify(r));" % (json.dumps(lottery), n))

    def test_each_draw_is_a_full_order_with_the_rules_applied(self):
        L = DATA["lottery"]
        self.assertIsNotNone(L)
        el = {t["franchiseId"]: t for t in L["teams"]}
        for order in self.sim(L, 3000):
            self.assertEqual(sorted(order), sorted(el))                                    # everyone exactly once
            self.assertTrue(el[order[0]]["inLottery"] and el[order[1]]["inLottery"])       # only lottery teams win 1.01 / 1.02
            self.assertTrue(el[order[0]]["canPick1"], order[0])                            # ineligible results were redrawn
            self.assertTrue(el[order[1]]["canPickTop2"], order[1])
            self.assertNotEqual(order[0], order[1])
            bonus = [next(t["franchiseId"] for t in L["teams"] if t["rank"] == r) for r in L["bonus"]["ranks"]]
            at = L["bonus"]["firstPick"] - 1
            self.assertEqual(order[at:at + 2], bonus)                                      # rank 3 then rank 4 take the first two block slots
            rest = [f for f in L["reverseOrder"] if f not in order[:2] and f not in bonus]
            self.assertEqual([f for f in order[2:] if f not in bonus], rest)               # the others stay in provisional reverse order
            self.assertEqual({t["franchiseId"] for t in L["teams"] if not t["inLottery"]} - set(bonus), set(order[-2:]))   # ranks 2 and 1 stay last

    def test_unrestricted_odds_match_the_ticket_share(self):
        L = json.loads(json.dumps(DATA["lottery"]))
        for t in L["teams"]:
            t["canPick1"] = t["canPickTop2"] = True
        n = 20000
        wins = {}
        for order in self.sim(L, n):
            wins[order[0]] = wins.get(order[0], 0) + 1
        for t in L["teams"]:
            share = t["tickets"] / L["totalCombinations"] if t["inLottery"] else 0
            self.assertAlmostEqual(wins.get(t["franchiseId"], 0) / n, share, delta=0.02, msg=t["franchiseId"])

    def test_page_shows_the_provisional_simulator_with_its_caveats(self):
        self.assertIn('id="lottery-sim"', HTML)
        self.assertIn("Draft lottery simulator", HTML)
        self.assertIn("not the draft order", HTML)
        self.assertIn("Rank 3/4 bonus:", HTML)
        self.assertLess(HTML.index('id="lottery-sim"'), HTML.index('class="order-grid"'))   # above the draft results
        self.assertEqual(DATA["lottery"]["label"][:11], "PROVISIONAL")


if __name__ == "__main__":
    unittest.main()


def _chrome_ready():
    import test_scenario_rendering as tsr
    return tsr, tsr._chrome()


class TestLotteryOnAPhone(unittest.TestCase):
    """One column: the draw result must sit directly under the buttons, above the odds table, and the pressed button keeps focus."""

    def drive(self, click):
        import html as html_lib
        import tempfile
        tsr, chrome = _chrome_ready()
        if not chrome:
            self.skipTest("no Chrome")
        script = ("<script>(function(){var R={};setTimeout(function(){try{var b=document.querySelectorAll('#lottery-sim .lot-bar button')[%d];b.click();"
                  "var res=document.getElementById('lot-res'),odds=document.getElementById('lot-odds'),bar=document.querySelector('#lottery-sim .lot-bar');"
                  "R.resTop=res.getBoundingClientRect().top;R.oddsTop=odds.getBoundingClientRect().top;R.barBottom=bar.getBoundingClientRect().bottom;"
                  "R.picks=res.querySelectorAll('.lot-pick').length;R.focus=document.activeElement.textContent;R.scroll=document.body.innerText.length>0;"
                  "}catch(e){R.error=String(e)}var p=document.createElement('pre');p.id='o';p.textContent=JSON.stringify(R);document.body.appendChild(p);},400);})();</script>") % click
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, "index.html")
            with open(path, "w", encoding="utf-8") as f:
                f.write(HTML.replace("</body>", script + "</body>", 1))
            out = tsr._chrome_run(["--window-size=390,844", "--virtual-time-budget=6000", "--dump-dom", "file://" + path + "#draft"], 120).stdout
        finally:
            shutil.rmtree(d)
        m = re.search(r'<pre id="o">(.*?)</pre>', out, re.S)
        self.assertIsNotNone(m, out[-300:])
        r = json.loads(html_lib.unescape(m.group(1)))
        self.assertNotIn("error", r, r.get("error"))
        return r

    def test_the_draw_result_is_above_the_odds_table_and_the_button_keeps_focus(self):
        r = self.drive(0)
        self.assertEqual(r["picks"], 16)
        self.assertLess(r["resTop"], r["oddsTop"])                       # results first when the columns stack
        self.assertGreaterEqual(r["resTop"], r["barBottom"] - 1)         # and directly beneath the buttons
        self.assertIn("Sim lottery", r["focus"])                         # the re-render did not drop focus to <body>
