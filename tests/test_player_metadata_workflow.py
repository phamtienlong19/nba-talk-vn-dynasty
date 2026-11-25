"""The player-metadata workflow: every 4 hours, PR-only, read-only GETs, and it may only change the metadata files and the generated page."""
import os
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
YML = open(os.path.join(ROOT, ".github", "workflows", "update-player-metadata.yml"), encoding="utf-8").read()


class TestPlayerMetadataWorkflow(unittest.TestCase):
    def test_it_runs_daily_and_on_demand_only(self):
        head = YML.split("jobs:")[0]
        self.assertRegex(head, r"\non:\n  schedule:\n    - cron: \"25 1,5,9,13,17,21 \* \* \*\"")
        self.assertIn("workflow_dispatch:", head)
        for trigger in ("push:", "pull_request:", "pull_request_target:"):
            self.assertNotIn("\n  " + trigger, head, trigger)

    def test_it_refreshes_then_regenerates_validates_and_opens_a_pr_it_never_merges(self):
        self.assertIn("scripts/refresh_player_metadata.py --write", YML)
        for step in ("refresh_card_positions.py", "./validate.sh", "unittest discover -s tests"):
            self.assertIn(step, YML)
        self.assertIn("gh pr create --base main", YML)
        steps = YML.split("jobs:")[1].lower()                                  # the steps, not the comments that say there is no sign-in
        for forbidden in ("gh pr merge", "--auto", "push origin main", "yahoo_storage_state", "cookie", "playwright"):
            self.assertNotIn(forbidden, steps, forbidden)

    def test_only_the_metadata_files_and_the_page_may_change(self):
        self.assertIn("data/yahoo/player_registry\\.json|data/yahoo/player_status\\.json|index\\.html", YML)
        self.assertIn("git add data/yahoo/player_registry.json data/yahoo/player_status.json index.html", YML)
        self.assertNotIn("salary_freeze", YML)
        self.assertNotIn("data/2026-27", YML)                                  # no ownership, roster or ledger file

    def test_it_changes_nothing_unless_run_from_main(self):
        self.assertIn("github.ref == 'refs/heads/main'", YML)


if __name__ == "__main__":
    unittest.main()
