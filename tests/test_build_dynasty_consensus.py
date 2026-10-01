import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from build_dynasty_consensus import build_consensus  # noqa: E402


class TestBuildConsensus(unittest.TestCase):
    def test_percentile_is_averaged_across_sources_present_in(self):
        sources = [
            {"source": "A", "players": [{"rank": 1, "name": "Star Guy"}, {"rank": 2, "name": "Other"}]},
            {"source": "B", "players": [{"rank": 2, "name": "Star Guy"}, {"rank": 1, "name": "Other"}]},
        ]
        rows = build_consensus(sources)
        by_name = {r["name"]: r for r in rows}
        # Star Guy: (1/2 + 2/2)/2 = 0.75; Other: (2/2 + 1/2)/2 = 0.75 -- tie
        self.assertAlmostEqual(by_name["Star Guy"]["percentile"], 0.75)
        self.assertAlmostEqual(by_name["Other"]["percentile"], 0.75)

    def test_absence_from_a_shorter_source_is_not_penalized(self):
        # A covers both players; B (a shorter/paywalled source) only covers
        # one. The one B doesn't cover must be scored from A alone, not
        # averaged against a fabricated "missing" penalty.
        sources = [
            {"source": "A", "players": [{"rank": 1, "name": "Covered By Both"}, {"rank": 2, "name": "Only In A"}]},
            {"source": "B", "players": [{"rank": 1, "name": "Covered By Both"}]},
        ]
        rows = build_consensus(sources)
        by_name = {r["name"]: r for r in rows}
        self.assertEqual(by_name["Only In A"]["sourcesCount"], 1)
        self.assertAlmostEqual(by_name["Only In A"]["percentile"], 2 / 2)

    def test_sorted_best_first_with_consensus_rank_assigned(self):
        sources = [{"source": "A", "players": [
            {"rank": 1, "name": "Best"}, {"rank": 2, "name": "Middle"}, {"rank": 3, "name": "Worst"},
        ]}]
        rows = build_consensus(sources)
        self.assertEqual([r["name"] for r in rows], ["Best", "Middle", "Worst"])
        self.assertEqual([r["consensusRank"] for r in rows], [1, 2, 3])

    def test_diacritic_variants_merge_into_one_entry(self):
        sources = [
            {"source": "A", "players": [{"rank": 1, "name": "Nikola Jokic"}]},
            {"source": "B", "players": [{"rank": 1, "name": "Nikola Jokić"}]},
        ]
        rows = build_consensus(sources)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sourcesCount"], 2)

    def test_known_alias_merges_across_sources(self):
        sources = [
            {"source": "A", "players": [{"rank": 1, "name": "Alexandre Sarr"}]},
            {"source": "B", "players": [{"rank": 1, "name": "Alex Sarr"}]},
        ]
        rows = build_consensus(sources)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sourcesCount"], 2)

    def test_longer_more_fully_spelled_name_wins_display_name(self):
        sources = [
            {"source": "A", "players": [{"rank": 1, "name": "Luka Doncic"}]},
            {"source": "B", "players": [{"rank": 1, "name": "Luka Dončić"}]},
        ]
        rows = build_consensus(sources)
        self.assertEqual(rows[0]["name"], "Luka Dončić")

    def test_pos_and_team_carried_through_from_first_source_that_has_them(self):
        sources = [
            {"source": "A", "players": [{"rank": 1, "name": "No Pos Guy"}]},
            {"source": "B", "players": [{"rank": 1, "name": "No Pos Guy", "pos": "PG/SG", "team": "BOS"}]},
        ]
        rows = build_consensus(sources)
        self.assertEqual(rows[0]["pos"], "PG/SG")
        self.assertEqual(rows[0]["team"], "BOS")

    def test_majority_spelling_wins_over_a_single_source_typo(self):
        # A single source with a one-off data-entry error (e.g. a
        # spreadsheet row reading "Kon Knueppel II" when every other
        # source agrees on "Kon Knueppel") must not win display-name
        # selection just by being a longer string.
        sources = [
            {"source": "A", "players": [{"rank": 1, "name": "Kon Knueppel"}]},
            {"source": "B", "players": [{"rank": 1, "name": "Kon Knueppel"}]},
            {"source": "C", "players": [{"rank": 1, "name": "Kon Knueppel"}]},
            {"source": "D", "players": [{"rank": 1, "name": "Kon Knueppel II"}]},
        ]
        rows = build_consensus(sources)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Kon Knueppel")
        self.assertEqual(rows[0]["sourcesCount"], 4)

    def test_incidental_whitespace_in_a_source_name_is_stripped(self):
        sources = [{"source": "A", "players": [{"rank": 1, "name": "Yang Hansen "}]}]
        rows = build_consensus(sources)
        self.assertEqual(rows[0]["name"], "Yang Hansen")

    def test_missing_pos_and_team_stay_none(self):
        sources = [{"source": "A", "players": [{"rank": 1, "name": "No Data Guy"}]}]
        rows = build_consensus(sources)
        self.assertIsNone(rows[0]["pos"])
        self.assertIsNone(rows[0]["team"])


if __name__ == "__main__":
    unittest.main()
