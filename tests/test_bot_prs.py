import os
import re
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
WF = {n: open(os.path.join(ROOT, ".github", "workflows", f), encoding="utf-8").read() for n, f in
      (("rosters", "update-yahoo-rosters.yml"), ("standings", "update-yahoo-standings.yml"), ("metadata", "update-player-metadata.yml"))}
HELPER = open(os.path.join(ROOT, "scripts", "bot_pr.sh"), encoding="utf-8").read()


class TestBotPrs(unittest.TestCase):
    def test_every_data_workflow_opens_its_pr_through_the_shared_helper_and_the_owners_token(self):
        for name, yml in WF.items():
            self.assertIn("ROSTER_PR_TOKEN: ${{ secrets.ROSTER_PR_TOKEN }}", yml, name)
            self.assertIn("source scripts/bot_pr.sh", yml, name)
            self.assertIn("bot_pr_token", yml, name)
            self.assertIn("bot_pr_merge", yml, name)

    def test_merging_happens_only_in_the_helper_and_only_with_the_owners_token(self):
        for name, yml in WF.items():
            self.assertNotIn("gh pr merge", yml, name)
            self.assertNotIn("--admin", yml, name)
            self.assertNotIn("push origin main", yml, name)
        self.assertEqual(len(re.findall(r"gh pr merge", HELPER)), 2)                    # auto-merge, then the wait-for-checks squash
        self.assertLess(HELPER.index('"$BOT_PR_CHECKS" != "yes"'), HELPER.index("gh pr merge"))   # no token -> return before any merge
        self.assertNotIn("--admin", HELPER)

    def test_standings_and_metadata_merge_only_after_their_path_guard(self):
        for name, guard in (("standings", "Only standings data and the generated site may have changed"), ("metadata", "Only the metadata files and the generated page may have changed")):
            yml = WF[name]
            self.assertIn(guard, yml, name)
            self.assertLess(yml.index(guard), yml.index("bot_pr_merge"), name)

    def test_the_docs_and_claude_md_record_the_owner_decision(self):
        claude = open(os.path.join(ROOT, "CLAUDE.md"), encoding="utf-8").read()
        self.assertIn("2026-11-24", claude)
        self.assertIn("Update Player Metadata", claude)
        self.assertTrue(os.path.exists(os.path.join(ROOT, "docs", "BOT_PRS.md")))


if __name__ == "__main__":
    unittest.main()
