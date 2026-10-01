import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from refresh_keeper_board_display import refresh_keeper_board, refresh_cut_chips  # noqa: E402


def _team_card(cuts_html):
    return (
        '<section class="team-card"><span class="identity-tag">ZZ</span>'
        '<div class="players"></div>'
        f'<footer><div class="cuts-list">{cuts_html}</div></footer></section>'
    )


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


class TestRefreshCutChips(unittest.TestCase):
    def test_updates_name_and_cap_from_yahoo_identity_match(self):
        """A player Yahoo now lists under a different display name (e.g.
        'X' -> 'X Jr.') is still the same person -- the chip must follow
        Yahoo's current name, not keep the stale one, and must not be
        treated as a second/duplicate entry."""
        html = _team_card('<span class="cut-chip">Bobby Portis</span>')
        yahoo = {"bobby portis": {"name": "Bobby Portis Jr.", "capDollars": 0.0, "oRank": 250}}
        new_html, updated = refresh_cut_chips(html, yahoo)
        self.assertEqual(updated, 1)
        self.assertIn('<span class="cut-chip">Bobby Portis Jr.</span>', new_html)
        self.assertEqual(new_html.count("cut-chip"), 1)  # still exactly one chip

    def test_nonzero_cap_renders_with_strong_tag(self):
        html = _team_card('<span class="cut-chip">Paid Guy</span>')
        yahoo = {"paid guy": {"name": "Paid Guy", "capDollars": 7.0, "oRank": 50}}
        new_html, updated = refresh_cut_chips(html, yahoo)
        self.assertEqual(updated, 1)
        self.assertIn('<span class="cut-chip">Paid Guy <strong>7</strong></span>', new_html)

    def test_cap_dropping_to_zero_removes_strong_tag(self):
        html = _team_card('<span class="cut-chip">Was Paid <strong>5</strong></span>')
        yahoo = {"was paid": {"name": "Was Paid", "capDollars": 0.0, "oRank": 200}}
        new_html, _ = refresh_cut_chips(html, yahoo)
        self.assertIn('<span class="cut-chip">Was Paid</span>', new_html)
        self.assertNotIn("<strong>", new_html)

    def test_health_badge_is_preserved(self):
        html = _team_card(
            '<span class="cut-chip">Hurt Guy'
            '<span class="health-badge inj" title="ACL">INJ</span></span>'
        )
        yahoo = {"hurt guy": {"name": "Hurt Guy", "capDollars": 3.0, "oRank": 90}}
        new_html, _ = refresh_cut_chips(html, yahoo)
        self.assertIn(
            '<span class="cut-chip">Hurt Guy<span class="health-badge inj" title="ACL">INJ</span> <strong>3</strong></span>',
            new_html,
        )

    def test_chip_untouched_when_player_missing_from_snapshot(self):
        html = _team_card('<span class="cut-chip">Nowhere Man <strong>2</strong></span>')
        new_html, updated = refresh_cut_chips(html, {})
        self.assertEqual(updated, 0)
        self.assertIn('<span class="cut-chip">Nowhere Man <strong>2</strong></span>', new_html)

    def test_chips_resorted_cap_descending_after_refresh(self):
        html = _team_card(
            '<span class="cut-chip">Low Guy <strong>1</strong></span>'
            '<span class="cut-chip">High Guy</span>'
        )
        yahoo = {
            "low guy": {"name": "Low Guy", "capDollars": 1.0, "oRank": 300},
            "high guy": {"name": "High Guy", "capDollars": 9.0, "oRank": 10},
        }
        new_html, _ = refresh_cut_chips(html, yahoo)
        self.assertLess(new_html.index("High Guy"), new_html.index("Low Guy"))

    def test_never_adds_or_removes_a_cut_or_moves_it_to_another_team(self):
        html = (
            _team_card('<span class="cut-chip">Team One Guy</span>')
            + _team_card('<span class="cut-chip">Team Two Guy</span>').replace("ZZ", "YY")
        )
        yahoo = {
            "team one guy": {"name": "Team One Guy", "capDollars": 4.0, "oRank": 20},
            "team two guy": {"name": "Team Two Guy", "capDollars": 8.0, "oRank": 5},
        }
        new_html, updated = refresh_cut_chips(html, yahoo)
        self.assertEqual(updated, 2)
        self.assertEqual(new_html.count("cut-chip"), 2)
        self.assertIn("ZZ", new_html)
        self.assertIn("YY", new_html)


if __name__ == "__main__":
    unittest.main()
