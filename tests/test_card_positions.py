import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import refresh_card_positions as rcp  # noqa: E402

ROOT = os.path.join(HERE, "..")


class TestCardPositions(unittest.TestCase):
    def test_a_row_takes_the_registry_position_and_team_but_never_the_cap_or_order(self):
        html = ('<div class="players"><div class="player-row"><div class="pos">PG/SG</div><div class="pname">Dylan Harper</div><div class="nba">SAS</div><div class="cap">11</div></div>'
                '<div class="player-row"><div class="pos">C</div><div class="pname">Unknown Guy</div><div class="nba">BOS</div><div class="cap">3</div></div></div>')
        reg = [{"name": "Dylan Harper", "eligiblePositions": ["PG", "SG", "G", "SF", "F", "Util"], "nbaTeam": "SAS", "projectedAuctionValue": 99}]
        new, changed = rcp.refresh(html, reg)
        self.assertIn('<div class="pos">PG/SG/SF</div><div class="pname">Dylan Harper', new)
        self.assertIn('<div class="cap">11</div>', new)                        # cap is untouched even though the registry says 99
        self.assertIn("Unknown Guy", new)                                      # a player the registry lacks is left alone
        self.assertEqual(len(changed), 1)

    def test_the_cards_on_the_page_match_the_registry(self):
        """The registry is refreshed daily; a card that disagrees is the 'eligibility never updated' bug. Fix: python3 scripts/refresh_card_positions.py"""
        with open(os.path.join(ROOT, "data", "yahoo", "player_registry.json"), encoding="utf-8") as f:
            reg = json.load(f)["players"]
        with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
            _, changed = rcp.refresh(f.read(), reg)
        self.assertEqual(changed, [])

    def test_the_metadata_workflow_runs_it(self):
        with open(os.path.join(ROOT, ".github", "workflows", "update-player-metadata.yml"), encoding="utf-8") as f:
            self.assertIn("scripts/refresh_card_positions.py", f.read())


if __name__ == "__main__":
    unittest.main()
