import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import build_fa_draft_pool as pool  # noqa: E402

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")


class TestSeattleKeeperSetAtCorrectedCeiling(unittest.TestCase):
    """Corrected cap band is 131/177. Seattle (Thịnh) must use the full
    ceiling: Porziņģis ($4) kept over Davion Mitchell ($3), total exactly
    $177, still nine legal slots."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO_ROOT, "index.html"), encoding="utf-8") as f:
            cls.html = f.read()
        cards = [c for c in re.findall(r'<section class="team-card".*?</section>', cls.html, re.S)
                 if '<span class="identity-tag">Thịnh</span>' in c]
        assert len(cards) == 1
        cls.card = cards[0]

    def _kept(self):
        return re.findall(r'<div class="pname">(.*?)</div><div class="nba">[^<]*</div><div class="cap">([\d.]+)</div>', self.card)

    def test_nine_kept_totalling_exactly_the_177_ceiling(self):
        kept = self._kept()
        self.assertEqual(len(kept), 9)
        self.assertEqual(sum(float(c) for _, c in kept), 177)
        self.assertIn('<div class="cap-total">177<span>/177</span></div>', self.card)
        self.assertIn("0 ROOM", self.card)

    def test_porzingis_kept_and_davion_cut(self):
        kept_names = [re.sub(r"<span.*?</span>", "", n) for n, _ in self._kept()]
        self.assertIn("Kristaps Porziņģis", kept_names)
        self.assertNotIn("Davion Mitchell", kept_names)
        cuts = re.search(r'<div class="cuts-list">(.*?)</div></footer>', self.card, re.S).group(1)
        self.assertIn("Davion Mitchell <strong>3</strong>", cuts)
        self.assertNotIn("Porziņģis", cuts)

    def test_kept_rows_are_cap_descending(self):
        caps = [float(c) for _, c in self._kept()]
        self.assertEqual(caps, sorted(caps, reverse=True))

    def test_downstream_pool_follows_the_new_keeper_set(self):
        block = self.html[self.html.index('<div class="pool-grid">'):self.html.index('<section class="page" id="cap">')]
        self.assertNotIn("Porziņģis", block)
        m = re.search(r'<div class="pool-player">Davion Mitchell</div><div class="pool-nba">([^<]*)</div>'
                      r'<div class="pool-cap">3</div><div class="pool-src"><span class="src src-cut">Thịnh</span>', block)
        self.assertIsNotNone(m, "Davion Mitchell ($3, cut by Thịnh) must enter the FA/DRAFT 60 with his Yahoo metadata")
        self.assertEqual(m.group(1), "MIA")


if __name__ == "__main__":
    unittest.main()
