import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from refresh_keeper_board_display import refresh_keeper_board  # noqa: E402


def _row(pos, name, nba, cap, extra_class=""):
    cls = f"player-row{extra_class}"
    return f'<div class="{cls}"><div class="pos">{pos}</div><div class="pname">{name}</div><div class="nba">{nba}</div><div class="cap">{cap}</div></div>'


class TestRefreshKeeperBoard(unittest.TestCase):
    def test_updates_pos_nba_cap_for_a_matched_kept_player(self):
        html = f'<div class="players">{_row("PG", "Alpha Player", "AAA", "10")}</div>'
        yahoo = {"alpha player": {"eligiblePositions": ["SG"], "nbaTeam": "BBB", "capDollars": 15.0}}
        new_html, updated = refresh_keeper_board(html, yahoo)
        self.assertEqual(updated, 1)
        self.assertIn(_row("SG", "Alpha Player", "BBB", "15"), new_html)

    def test_no_update_when_values_already_match(self):
        html = f'<div class="players">{_row("PG", "Alpha Player", "AAA", "10")}</div>'
        yahoo = {"alpha player": {"eligiblePositions": ["PG"], "nbaTeam": "AAA", "capDollars": 10.0}}
        new_html, updated = refresh_keeper_board(html, yahoo)
        self.assertEqual(updated, 0)
        self.assertEqual(new_html, html)

    def test_row_left_untouched_when_player_missing_from_snapshot(self):
        html = f'<div class="players">{_row("PG", "Nowhere Man", "AAA", "10")}</div>'
        new_html, updated = refresh_keeper_board(html, {})
        self.assertEqual(updated, 0)
        self.assertEqual(new_html, html)

    def test_roster_membership_is_never_changed(self):
        """Never adds, removes, or reorders a row -- only Yahoo-governed
        display fields on an existing row change."""
        html = (
            '<div class="players">'
            + _row("PG", "Alpha Player", "AAA", "10")
            + _row("C", "Beta Player", "CCC", "5")
            + "</div>"
        )
        yahoo = {
            "alpha player": {"eligiblePositions": ["SG"], "nbaTeam": "ZZZ", "capDollars": 1.0},
            "gamma player": {"eligiblePositions": ["PF"], "nbaTeam": "YYY", "capDollars": 99.0},
        }
        new_html, updated = refresh_keeper_board(html, yahoo)
        self.assertEqual(updated, 1)  # only Alpha matched
        self.assertEqual(new_html.count("player-row"), 2)  # still exactly 2 rows
        self.assertIn("Beta Player", new_html)
        self.assertNotIn("Gamma Player", new_html)  # never inserted

    def test_health_badge_span_is_preserved_and_does_not_break_name_matching(self):
        html = (
            '<div class="player-row health-inj"><div class="pos">PG</div>'
            '<div class="pname">Hurt Player<span class="health-badge inj" title="ACL">INJ</span></div>'
            '<div class="nba">AAA</div><div class="cap">10</div></div>'
        )
        yahoo = {"hurt player": {"eligiblePositions": ["SG"], "nbaTeam": "BBB", "capDollars": 20.0}}
        new_html, updated = refresh_keeper_board(html, yahoo)
        self.assertEqual(updated, 1)
        self.assertIn('<span class="health-badge inj" title="ACL">INJ</span>', new_html)
        self.assertIn('<div class="nba">BBB</div><div class="cap">20</div>', new_html)

    def test_fa_pool_rows_are_not_touched(self):
        """.pool-row is a different class from .player-row (kept rows) --
        the FA/DRAFT pool must be untouched by this script."""
        html = '<div class="pool-row"><div class="pool-rank">1</div></div>'
        new_html, updated = refresh_keeper_board(html, {"anyone": {"eligiblePositions": ["PG"], "nbaTeam": "X", "capDollars": 1}})
        self.assertEqual(updated, 0)
        self.assertEqual(new_html, html)

    def test_integer_cap_renders_without_decimal(self):
        html = f'<div class="players">{_row("PG", "Alpha Player", "AAA", "10")}</div>'
        yahoo = {"alpha player": {"eligiblePositions": ["PG"], "nbaTeam": "AAA", "capDollars": 11.0}}
        new_html, _ = refresh_keeper_board(html, yahoo)
        self.assertIn('<div class="cap">11</div>', new_html)
        self.assertNotIn('<div class="cap">11.0</div>', new_html)


if __name__ == "__main__":
    unittest.main()
