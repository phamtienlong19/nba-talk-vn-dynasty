import os
import re
import unittest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")


def _card(html, tag):
    cards = [c for c in re.findall(r'<section class="team-card".*?</section>', html, re.S)
             if f'<span class="identity-tag">{tag}</span>' in c]
    assert len(cards) == 1, tag
    return cards[0]


def _kept(card):
    return [(re.sub(r"<span.*?</span>", "", n), float(c)) for n, c in
            re.findall(r'<div class="pname">(.*?)</div><div class="nba">[^<]*</div><div class="cap">([\d.]+)</div>', card)]


def _cuts(card):
    return re.search(r'<div class="cuts-list">(.*?)</div></footer>', card, re.S).group(1)


def _pool(html):
    return html[html.index('<div class="pool-grid">'):html.index('<section class="page" id="cap">')]


class TestExplicitKeeperOverrides(unittest.TestCase):
    """Owner/commissioner keeper-choice corrections (not ownership changes)."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO_ROOT, "index.html"), encoding="utf-8") as f:
            cls.html = f.read()
        cls.pool = _pool(cls.html)

    def test_kratos_keeps_wiggins_and_cuts_queta(self):
        card = _card(self.html, "TT")
        kept = dict(_kept(card))
        self.assertEqual(len(kept), 9)
        self.assertEqual(kept["Andrew Wiggins"], 5)
        self.assertNotIn("Neemias Queta", kept)
        self.assertEqual(sum(kept.values()), 174)
        self.assertIn('<div class="cap-total">174<span>/178</span></div>', card)
        self.assertIn("Neemias Queta <strong>2</strong>", _cuts(card))
        self.assertNotIn("Andrew Wiggins", _cuts(card))

    def test_dha_final_keepers_bilal_and_kuminga_in_nurkic_and_poeltl_cut(self):
        card = _card(self.html, "DHA")
        kept = dict(_kept(card))
        self.assertEqual(len(kept), 9)
        self.assertEqual((kept["Bilal Coulibaly"], kept["Jonathan Kuminga"]), (0, 0))
        self.assertNotIn("Jakob Poeltl", kept)
        self.assertNotIn("Jusuf Nurkić", kept)
        self.assertEqual(sum(kept.values()), 154)
        self.assertIn('<div class="cap-total">154<span>/178</span></div>', card)
        cuts = _cuts(card)
        self.assertIn("Jusuf Nurkić <strong>4</strong>", cuts)
        self.assertIn("Jakob Poeltl <strong>2</strong>", cuts)
        self.assertLess(cuts.index("Nurkić"), cuts.index("Poeltl"))  # cuts are CAP-descending

    def test_kept_players_leave_the_fa_inventory_and_cuts_enter_with_the_right_source_tag(self):
        for gone in ("Andrew Wiggins", "Kristaps Porziņģis", "Bilal Coulibaly", "Jonathan Kuminga", "Isaiah Jackson",
                     "Dennis Schröder", "Kelly Oubre Jr."):
            self.assertNotIn(f'<div class="pool-player">{gone}</div>', self.pool, gone)
        for name, team in (("Neemias Queta", "TT"), ("Davion Mitchell", "Thịnh"), ("Jusuf Nurkić", "DHA"), ("Jakob Poeltl", "DHA")):
            m = re.search(rf'<div class="pool-player">{name}</div><div class="pool-nba">[^<]*</div>'
                          rf'<div class="pool-cap">\d+</div><div class="pool-src"><span class="src src-cut">{team}</span>', self.pool)
            self.assertIsNotNone(m, f"{name} must enter the FA/DRAFT pool tagged as a {team} cut")

    def test_no_player_is_both_kept_and_in_the_pool(self):
        kept_all = {n for c in re.findall(r'<section class="team-card".*?</section>', self.html, re.S) for n, _ in _kept(c)}
        pool_names = set(re.findall(r'<div class="pool-player">(.*?)</div>', self.pool))
        import html as h
        self.assertEqual(kept_all & {h.unescape(n) for n in pool_names}, set())

    def test_every_team_total_respects_the_178_ceiling_and_is_displayed_against_it(self):
        totals = re.findall(r'<div class="cap-total">(\d+)<span>/(\d+)</span>', self.html)
        self.assertEqual(len(totals), 16)
        for total, ceiling in totals:
            self.assertEqual(ceiling, "178")
            self.assertLessEqual(int(total), 178)


if __name__ == "__main__":
    unittest.main()
