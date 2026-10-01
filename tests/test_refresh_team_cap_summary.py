import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from refresh_team_cap_summary import (  # noqa: E402
    classify_cap,
    refresh_team_cap_summary,
)


def _card(tag, cls, total, ceiling, text, caps, team_name="Some Team", small="Full Name"):
    rows = "".join(
        f'<div class="player-row"><div class="pos">PG</div><div class="pname">P{i}</div>'
        f'<div class="nba">AAA</div><div class="cap">{c}</div></div>'
        for i, c in enumerate(caps)
    )
    return (
        f'<section class="team-card" style="--team-color:#000;--team-text:#fff">\n'
        f'<header class="team-head">\n<div class="team-index">01</div>\n'
        f'<div class="team-id">\n<div class="team-name">{team_name}</div>\n'
        f'<div class="team-meta">\n<span class="identity-tag">{tag}</span>\n'
        f'<span class="picks-tag">1.01</span>\n</div>\n</div>\n'
        f'<div class="cap-box {cls}">\n<div class="cap-total">{total}<span>/{ceiling}</span></div>\n'
        f'<div class="gap-big">{text}</div>\n</div>\n</header>\n'
        f'<div class="table-head"><span>POS</span></div>\n'
        f'<div class="players">{rows}</div>\n'
        f'<footer><div class="cuts-list"></div></footer>\n</section>'
    )


def _cap_card(tag_html, cls, total, ceiling, text, small="Full Name"):
    return (
        f'<div class="cap-card {cls}" style="--team-color:#000;--team-text:#fff">\n'
        f'<div class="cap-team"><span class="cap-dot"></span><b>{tag_html}</b><small>{small}</small></div>\n'
        f'<div class="cap-num">{total}<span>/{ceiling}</span></div>'
        f'<div class="cap-gap">{text}</div></div>'
    )


class TestClassifyCap(unittest.TestCase):
    def test_under_floor(self):
        cls, text = classify_cap(100, floor=130, ceiling=176)
        self.assertEqual(cls, "gap-floor")
        self.assertEqual(text, "30 TO FLOOR")

    def test_comfortable_room(self):
        cls, text = classify_cap(145, floor=130, ceiling=176)
        self.assertEqual(cls, "gap-room")
        self.assertEqual(text, "31 ROOM")

    def test_near_ceiling(self):
        cls, text = classify_cap(174, floor=130, ceiling=176)
        self.assertEqual(cls, "gap-near")
        self.assertEqual(text, "2 ROOM")

    def test_exactly_at_ceiling(self):
        cls, text = classify_cap(176, floor=130, ceiling=176)
        self.assertEqual(cls, "gap-near")
        self.assertEqual(text, "0 ROOM")

    def test_over_ceiling(self):
        cls, text = classify_cap(177, floor=130, ceiling=176)
        self.assertEqual(cls, "gap-zero")
        self.assertEqual(text, "1 OVER")


class TestRefreshTeamCapSummary(unittest.TestCase):
    def test_recomputes_total_and_room_from_player_rows(self):
        html = _card("AA", "gap-room", 999, 177, "stale text", [100, 50, 4])
        new_html, summary = refresh_team_cap_summary(html, floor=130, ceiling=176)
        self.assertEqual(summary["AA"]["total"], 154)
        self.assertIn('<div class="cap-total">154<span>/176</span></div>', new_html)
        self.assertIn('<div class="gap-big">22 ROOM</div>', new_html)
        self.assertIn('<div class="cap-box gap-room">', new_html)

    def test_over_ceiling_switches_to_gap_zero_and_over_text(self):
        html = _card("TH", "gap-near", 176, 177, "1 ROOM", [61, 49, 33, 16, 14, 4, 0, 0, 0])
        new_html, summary = refresh_team_cap_summary(html, floor=130, ceiling=176)
        self.assertEqual(summary["TH"]["total"], 177)
        self.assertIn('<div class="cap-box gap-zero">', new_html)
        self.assertIn('<div class="gap-big">1 OVER</div>', new_html)

    def test_cap_page_card_uses_the_same_total_as_the_team_card(self):
        card = _card("AA", "gap-room", 999, 177, "stale", [100, 50, 4])
        cap_card = _cap_card("AA", "gap-room", 999, 177, "stale text")
        html = card + cap_card
        new_html, summary = refresh_team_cap_summary(html, floor=130, ceiling=176)
        self.assertIn('<div class="cap-num">154<span>/176</span></div><div class="cap-gap">22 ROOM</div>', new_html)

    def test_crown_prefixed_tag_is_preserved_and_still_matched(self):
        card = _card("Đạt", "gap-near", 175, 177, "2 ROOM", [61, 49, 33, 16, 14, 4, 0, 0, 0])
        cap_card = _cap_card("👑 Đạt", "gap-near", 175, 177, "2 ROOM")
        html = card + cap_card
        new_html, summary = refresh_team_cap_summary(html, floor=130, ceiling=176)
        self.assertIn("<b>👑 Đạt</b>", new_html)  # crown preserved verbatim
        self.assertEqual(summary["Đạt"]["total"], 177)
        self.assertIn('<div class="cap-gap">1 OVER</div>', new_html)

    def test_only_cap_summary_fields_change_roster_rows_untouched(self):
        html = _card("AA", "gap-room", 100, 177, "77 ROOM", [60, 40, 0])
        new_html, _ = refresh_team_cap_summary(html, floor=130, ceiling=176)
        self.assertEqual(
            re.findall(r'<div class="player-row.*?</div></div>', html, re.S),
            re.findall(r'<div class="player-row.*?</div></div>', new_html, re.S),
        )


REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
INDEX_HTML = os.path.join(REPO_ROOT, "index.html")


class TestIndexHtmlCapConsistencyRegressions(unittest.TestCase):
    """Regression checks against the committed index.html: the ceiling
    shown in every per-team cap-total/cap-num denominator and the
    page-level CAP meta-pill must all agree with each other -- there is
    exactly one current ceiling, displayed in several places."""

    @classmethod
    def setUpClass(cls):
        with open(INDEX_HTML, encoding="utf-8") as f:
            cls.html = f.read()

    def test_every_team_card_and_cap_page_denominator_matches(self):
        denominators = set(re.findall(r'<div class="cap-total">\d+(?:\.\d+)?<span>/(\d+)</span>', self.html))
        denominators |= set(re.findall(r'<div class="cap-num">\d+(?:\.\d+)?<span>/(\d+)</span>', self.html))
        self.assertEqual(len(denominators), 1, f"ceiling denominators disagree: {denominators}")

    def test_meta_pill_cap_ceiling_matches_team_denominators(self):
        ceiling = re.search(r'<div class="cap-total">\d+(?:\.\d+)?<span>/(\d+)</span>', self.html).group(1)
        pill_values = set(re.findall(r'class="pill-v">(\d+)–(\d+)</span>', self.html))
        self.assertTrue(pill_values, "no CAP meta-pill found")
        for _floor, pill_ceiling in pill_values:
            self.assertEqual(pill_ceiling, ceiling, "meta-pill-cap ceiling is stale vs. the board's own totals")

    def test_meta_pill_cap_floor_matches_a_to_floor_team(self):
        pill_floor = next(iter(re.findall(r'class="pill-v">(\d+)–\d+</span>', self.html)))
        to_floor = re.search(r'<div class="cap-total">(\d+(?:\.\d+)?)<span>/\d+</span></div>\s*'
                              r'<div class="gap-big">(\d+(?:\.\d+)?) TO FLOOR</div>', self.html)
        self.assertIsNotNone(to_floor, "no gap-floor team found to cross-check the meta-pill floor against")
        total, deficit = (float(x) for x in to_floor.groups())
        self.assertEqual(str(int(total + deficit)), pill_floor)


if __name__ == "__main__":
    unittest.main()
