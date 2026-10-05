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

    def test_absence_from_a_non_informative_source_is_not_penalized(self):
        # B is a non-informative-absence source (e.g. a paywalled or
        # domain-restricted board, informativeAbsence omitted/false) --
        # the player it doesn't cover must be scored from A alone, not
        # averaged against a fabricated "missing" penalty.
        sources = [
            {"source": "A", "players": [{"rank": 1, "name": "Covered By Both"}, {"rank": 2, "name": "Only In A"}]},
            {"source": "B", "players": [{"rank": 1, "name": "Covered By Both"}]},
        ]
        rows = build_consensus(sources)
        by_name = {r["name"]: r for r in rows}
        self.assertEqual(by_name["Only In A"]["sourcesCount"], 1)
        self.assertAlmostEqual(by_name["Only In A"]["percentile"], 2 / 2)

    def test_absence_from_an_informative_source_is_penalized(self):
        # B is informativeAbsence=true (a complete/curated board) -- not
        # appearing in it is B's own opinion about the player, and must
        # drag their average down, not be skipped for free.
        sources = [
            {"source": "A", "informativeAbsence": True,
             "players": [{"rank": 1, "name": "Covered By Both"}, {"rank": 2, "name": "Only In A"}]},
            {"source": "B", "informativeAbsence": True,
             "players": [{"rank": 1, "name": "Covered By Both"}]},
        ]
        rows = build_consensus(sources)
        by_name = {r["name"]: r for r in rows}
        # Only In A: A-percentile 2/2=1.0, plus B's absence penalty 1.0 -> avg 1.0
        self.assertAlmostEqual(by_name["Only In A"]["percentile"], 1.0)
        # sourcesCount only reflects sources that actually ranked the player
        self.assertEqual(by_name["Only In A"]["sourcesCount"], 1)

    def test_informative_absence_does_not_affect_a_player_present_everywhere(self):
        sources = [
            {"source": "A", "informativeAbsence": True, "players": [{"rank": 1, "name": "Star"}]},
            {"source": "B", "informativeAbsence": True, "players": [{"rank": 1, "name": "Star"}]},
        ]
        rows = build_consensus(sources)
        self.assertAlmostEqual(rows[0]["percentile"], 1.0)  # rank 1 of 1 in both -> 1.0 either way
        self.assertEqual(rows[0]["sourcesCount"], 2)

    def test_mixed_informative_and_non_informative_sources(self):
        # A player ranked decently by two broad informative boards but
        # absent from a curated informative top-10, and also absent from
        # a paywalled non-informative board, should be dragged down by
        # the top-10 absence but NOT by the paywalled one.
        broad1_others = [{"rank": i, "name": f"P{i}"} for i in range(2, 60)]  # 58 filler players
        broad2_others = [{"rank": i, "name": f"Q{i}"} for i in range(2, 40)]  # 38 filler players
        sources = [
            {"source": "Broad1", "informativeAbsence": True,
             "players": [{"rank": 1, "name": "Role Player"}] + broad1_others},  # count=59, rank 1
            {"source": "Broad2", "informativeAbsence": True,
             "players": [{"rank": 1, "name": "Role Player"}] + broad2_others},  # count=39, rank 1
            {"source": "CuratedTop10", "informativeAbsence": True,
             "players": [{"rank": i, "name": f"R{i}"} for i in range(1, 11)]},  # Role Player absent
            {"source": "Paywalled", "informativeAbsence": False,
             "players": [{"rank": i, "name": f"S{i}"} for i in range(1, 11)]},  # Role Player absent, not penalized
        ]
        rows = build_consensus(sources)
        by_name = {r["name"]: r for r in rows}
        role = by_name["Role Player"]
        self.assertEqual(len(sources[0]["players"]), 59)
        self.assertEqual(len(sources[1]["players"]), 39)
        self.assertEqual(role["sourcesCount"], 2)  # only Broad1 + Broad2 actually ranked them
        # (1/59 + 1/39 + 1.0 penalty from CuratedTop10) / 3 -- Paywalled contributes nothing
        expected = (1 / 59 + 1 / 39 + 1.0) / 3
        self.assertAlmostEqual(role["percentile"], expected)

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
