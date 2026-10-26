"""Lottery simulator in index.html: the page's own draw functions run under node against the embedded provisional data."""
import json
import os
import re
import shutil
import subprocess
import unittest

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
            rest = [f for f in L["reverseOrder"] if f not in order[:2]]
            self.assertEqual(order[2:], rest)                                              # the others stay in provisional reverse order

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
        self.assertIn("LOTTERY SIMULATOR · PROVISIONAL", HTML)
        self.assertIn("not the draft order", HTML)
        self.assertIn("not modelled (open rule)", HTML)
        self.assertEqual(DATA["lottery"]["label"][:11], "PROVISIONAL")


if __name__ == "__main__":
    unittest.main()
