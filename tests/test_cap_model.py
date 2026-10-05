import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from cap_model import compute_cap_model, draft_order, CapModelError, REQUIRED_PLAYERS  # noqa: E402
from export_yahoo_top300 import parse_markdown  # noqa: E402

# Frozen copy of the 2026-10-04 Yahoo Top-300 export (Player | Proj $ | Rank).
SNAPSHOT_MD = os.path.join(os.path.dirname(__file__), "fixtures", "yahoo_top300_2026-10-04.md")


def _snapshot_players():
    with open(SNAPSHOT_MD, encoding="utf-8") as f:
        rows = parse_markdown(f.read())
    return [{"name": n, "capDollars": d, "oRank": r} for n, d, r in rows]


def _flat_fixture(values_by_group):
    """16 players per group, each valued at the group's value, listed in
    salary-draft order; oRank deliberately assigned in a scrambled order so
    the test proves the model ignores O-Rank order for grouping."""
    players = []
    rank = 1
    for value in values_by_group:
        for _ in range(16):
            players.append({"oRank": rank, "capDollars": value})
            rank += 1
    return players


class TestSalaryOrderNotORankOrder(unittest.TestCase):
    def test_higher_projected_dollars_drafted_first_despite_worse_orank(self):
        # Player A: O-Rank 97, $4. Player B: O-Rank 123, $5. B must be
        # placed before A, so with 143 fillers ahead of both, B takes the
        # 144th (last) slot and A is excluded from the benchmark.
        fillers = [{"oRank": 300 + i, "capDollars": 10} for i in range(143)]
        a = {"oRank": 97, "capDollars": 4}
        b = {"oRank": 123, "capDollars": 5}
        self.assertEqual(draft_order(fillers + [a, b])[143], (5.0, 123))
        self.assertEqual(compute_cap_model(fillers + [a, b])["top144Sum"], 143 * 10 + 5)
        self.assertEqual(compute_cap_model(fillers + [b, a])["top144Sum"], 143 * 10 + 5)

    def test_orank_breaks_ties_only_inside_an_equal_dollar_tier(self):
        fillers = [{"oRank": 300 + i, "capDollars": 10} for i in range(143)]
        order = draft_order(fillers + [
            {"oRank": 50, "capDollars": 5}, {"oRank": 10, "capDollars": 5},
            {"oRank": 1, "capDollars": 4},
        ])
        self.assertEqual(order[143:], [(5.0, 10), (5.0, 50), (4.0, 1)])

    def test_row_order_does_not_matter(self):
        fixture = _snapshot_players()
        self.assertEqual(compute_cap_model(fixture), compute_cap_model(list(reversed(fixture))))

    def test_bands_follow_salary_order(self):
        result = compute_cap_model(_flat_fixture([50, 40, 30, 20, 10, 8, 4, 1, 0]))
        self.assertEqual(result["bands"], [50, 40, 30, 20, 10, 8, 4, 1, 0])
        self.assertAlmostEqual(result["benchmark"], sum(result["bands"]))
        self.assertAlmostEqual(result["benchmark"], result["top144Sum"] / 16)


class TestSnapshotRegression(unittest.TestCase):
    """Real 2026-10-04 Yahoo snapshot: 300 players. The expected numbers are
    asserted against the fixture, never baked into cap_model.py."""

    def test_snapshot_benchmark_floor_ceiling(self):
        result = compute_cap_model(_snapshot_players())
        self.assertEqual(result["top144Sum"], 2468)
        self.assertAlmostEqual(result["benchmark"], 154.25)
        self.assertAlmostEqual(result["rawFloor"], 131.1125)
        self.assertAlmostEqual(result["rawCeiling"], 177.3875)
        self.assertEqual(result["roundedFloor"], 131)
        self.assertEqual(result["roundedCeiling"], 177)

    def test_old_orank_model_would_have_been_wrong(self):
        players = _snapshot_players()
        by_rank = sorted(players, key=lambda p: p["oRank"])[:144]
        old_sum = sum(p["capDollars"] for p in by_rank)
        self.assertNotEqual(old_sum, 2468, "fixture must distinguish salary order from O-Rank order")


class TestStructuralValidation(unittest.TestCase):
    def test_insufficient_players_rejected(self):
        fixture = _flat_fixture([1] * 9)[:REQUIRED_PLAYERS - 1]
        with self.assertRaises(CapModelError):
            compute_cap_model(fixture)

    def test_duplicate_rank_rejected(self):
        fixture = _flat_fixture([1] * 9)
        fixture[1] = dict(fixture[0])
        with self.assertRaises(CapModelError):
            compute_cap_model(fixture)

    def test_non_numeric_dollars_rejected(self):
        fixture = _flat_fixture([1] * 9)
        fixture[0]["capDollars"] = "5"
        with self.assertRaises(CapModelError):
            compute_cap_model(fixture)

    def test_zero_dollar_players_accepted(self):
        result = compute_cap_model(_flat_fixture([0] * 9))
        self.assertEqual(result["benchmark"], 0)


if __name__ == "__main__":
    unittest.main()
