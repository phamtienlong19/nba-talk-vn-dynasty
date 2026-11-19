"""Auto-healing of the generated data blocks of index.html: only those conflicts, only toward main's side, never main itself."""
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import resolve_generated_conflicts as rgc  # noqa: E402

LEAGUE_A = '<!--LEAGUE-DATA-BEGIN--><script type="application/json" id="league-data">{"v":"branch"}</script><!--LEAGUE-DATA-END-->'
LEAGUE_B = '<!--LEAGUE-DATA-BEGIN--><script type="application/json" id="league-data">{"v":"main"}</script><!--LEAGUE-DATA-END-->'
WHATIF_A = '</style><script type="application/json" id="whatif-data">{"v":"branch"}</script>'
WHATIF_B = '</style><script type="application/json" id="whatif-data">{"v":"main"}</script>'


def conflict(a, b):
    return "<<<<<<< HEAD\n%s\n=======\n%s\n>>>>>>> origin/main\n" % (a, b)


class TestResolve(unittest.TestCase):
    def test_generated_blocks_take_mains_side(self):
        text = "<p>top</p>\n" + conflict(WHATIF_A, WHATIF_B) + "<p>mid</p>\n" + conflict(LEAGUE_A, LEAGUE_B) + "<p>end</p>\n"
        out = rgc.resolve(text)
        self.assertEqual(out, "<p>top</p>\n" + WHATIF_B + "\n<p>mid</p>\n" + LEAGUE_B + "\n<p>end</p>\n")
        self.assertNotIn("<<<<<<<", out)
        self.assertNotIn("branch", out)

    def test_a_hand_edited_conflict_is_never_resolved(self):
        for text in (conflict("<h1>mine</h1>", "<h1>theirs</h1>"),
                     conflict(LEAGUE_A, LEAGUE_B) + conflict("<p>mine</p>", "<p>theirs</p>"),         # one real hunk spoils the whole file
                     conflict(LEAGUE_A + "\n<p>extra</p>", LEAGUE_B)):                                # a multi-line side is not a one-line data block
            self.assertIsNone(rgc.resolve(text))

    def test_no_conflict_means_nothing_to_resolve(self):
        self.assertIsNone(rgc.resolve("<p>clean</p>\n"))

    def test_the_command_leaves_an_unresolvable_file_untouched(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "index.html")
            text = conflict("<h1>mine</h1>", "<h1>theirs</h1>")
            open(p, "w", encoding="utf-8").write(text)
            self.assertEqual(rgc.main([p]), 4)
            self.assertEqual(open(p, encoding="utf-8").read(), text)
            open(p, "w", encoding="utf-8").write(conflict(LEAGUE_A, LEAGUE_B))
            self.assertEqual(rgc.main([p]), 0)
            self.assertEqual(open(p, encoding="utf-8").read(), LEAGUE_B + "\n")


class TestWorkflow(unittest.TestCase):
    YML = open(os.path.join(ROOT, ".github", "workflows", "heal-generated-conflicts.yml"), encoding="utf-8").read()
    SH = open(os.path.join(ROOT, "scripts", "heal_open_prs.sh"), encoding="utf-8").read()

    def test_it_runs_after_every_push_to_main_hourly_and_on_demand(self):
        head = self.YML.split("jobs:")[0]
        self.assertIn("push:\n    branches: [main]", head)
        self.assertIn('cron: "50 * * * *"', head)
        self.assertIn("workflow_dispatch:", head)

    def test_the_roster_run_starts_the_healer_because_bot_merges_do_not_trigger_it(self):
        wf = open(os.path.join(ROOT, ".github", "workflows", "update-yahoo-rosters.yml"), encoding="utf-8").read()
        self.assertIn("gh workflow run heal-generated-conflicts.yml", wf)

    def test_it_never_pushes_to_main_and_never_merges(self):
        steps = self.YML.split("jobs:")[1] + self.SH
        for forbidden in ("gh pr merge", "--auto", "HEAD:main", "heal:main", "--force"):
            self.assertNotIn(forbidden, steps, forbidden)
        pushes = [line for line in steps.splitlines() if "git push" in line and not line.lstrip().startswith("#")]
        self.assertTrue(pushes)
        for line in pushes:
            self.assertIn('origin "heal:$b"', line)                              # the only push is to the PR's own branch

    def test_it_only_acts_on_same_repo_conflicting_prs_and_leaves_real_conflicts(self):
        self.assertIn('select(.mergeable=="CONFLICTING" and .isCrossRepository==false)', self.SH)
        self.assertIn("left for a human", self.SH)
        self.assertIn("resolve_generated_conflicts.py index.html", self.SH)
        self.assertIn("./validate.sh", self.SH)                                  # validated before anything is pushed

    def test_it_can_start_the_checks_on_the_branch_it_pushed(self):
        validate = open(os.path.join(ROOT, ".github", "workflows", "validate.yml"), encoding="utf-8").read()
        self.assertIn("  workflow_dispatch:", validate.split("jobs:")[0])
        self.assertIn('gh workflow run validate.yml --ref "$b"', self.SH)


if __name__ == "__main__":
    unittest.main()
