import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from issue_workflow import (
    archive_name,
    branch_name,
    classify_prefix,
    generate_active_md,
    generate_no_active_task_md,
    slugify,
)


class TestSlugify(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slugify("Fix John Collins cap"), "fix-john-collins-cap")

    def test_strips_punctuation(self):
        self.assertEqual(slugify("Team name: wrong!!"), "team-name-wrong")

    def test_caps_word_count(self):
        self.assertEqual(
            slugify("one two three four five six seven eight"),
            "one-two-three-four-five-six",
        )

    def test_empty_falls_back(self):
        self.assertEqual(slugify("???"), "issue")


class TestClassifyPrefix(unittest.TestCase):
    def test_bug_label_wins(self):
        self.assertEqual(classify_prefix("Anything", ["bug"]), "fix")

    def test_data_correction_label(self):
        self.assertEqual(classify_prefix("Anything", ["data-correction"]), "fix")

    def test_workflow_label(self):
        self.assertEqual(classify_prefix("Anything", ["workflow"]), "chore")

    def test_enhancement_label(self):
        self.assertEqual(classify_prefix("Anything", ["enhancement"]), "feat")

    def test_title_keyword_fix(self):
        self.assertEqual(classify_prefix("John Collins cap is wrong", []), "fix")

    def test_title_keyword_feat(self):
        self.assertEqual(classify_prefix("Add trade deadline tracker", []), "feat")

    def test_default_chore(self):
        self.assertEqual(classify_prefix("Something ambiguous here", []), "chore")

    def test_label_overrides_conflicting_title_keyword(self):
        # title alone would say "feat" (has "add"), but label wins
        self.assertEqual(classify_prefix("Add missing bug info", ["bug"]), "fix")


class TestBranchName(unittest.TestCase):
    def test_shape(self):
        name = branch_name(2, "Double Check Team Name and Rosters' Cap Numbers", ["bug"])
        self.assertTrue(name.startswith("fix/issue-2-"))
        self.assertNotIn(" ", name)

    def test_length_capped(self):
        long_title = "a very very very extremely long issue title that goes on and on and on"
        name = branch_name(999, long_title, [])
        self.assertLessEqual(len(name), 60)
        self.assertTrue(name.startswith("chore/issue-999-"))

    def test_deterministic(self):
        a = branch_name(5, "Same title", ["bug"])
        b = branch_name(5, "Same title", ["bug"])
        self.assertEqual(a, b)


class TestArchiveName(unittest.TestCase):
    def test_shape(self):
        name = archive_name(2, "Double Check Team Name", date="2026-09-17")
        self.assertEqual(name, "2026-09-17-issue-2-double-check-team-name.md")


class TestActiveMdTemplates(unittest.TestCase):
    def test_generate_active_md_has_required_fields(self):
        content = generate_active_md(
            12, "https://x/issues/12", "Some Title", "fix/issue-12-some-title", "2026-01-01T00:00:00Z"
        )
        self.assertIn("Issue: #12", content)
        self.assertIn("URL: https://x/issues/12", content)
        self.assertIn("Title: Some Title", content)
        self.assertIn("Branch: fix/issue-12-some-title", content)
        self.assertIn("Canonical specification: GitHub Issue #12", content)
        self.assertIn("Human-decision boundaries in `CLAUDE.md` remain active.", content)
        # Lightweight: must not balloon into a full issue-body copy.
        self.assertLess(len(content), 1000)

    def test_no_active_task_md_is_concise(self):
        content = generate_no_active_task_md()
        self.assertIn("No active task", content)
        self.assertLess(len(content), 300)


if __name__ == "__main__":
    unittest.main()
