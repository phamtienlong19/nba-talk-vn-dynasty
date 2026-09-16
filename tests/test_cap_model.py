import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from cap_model import compute_cap_model, CapModelError, REQUIRED_RANKS  # noqa: E402


def _band_fixture():
    """16 players per band, each valued at the band's expected average.

    A band of 16 identical values has that value as its mean, so this is a
    legitimate (not reverse-engineered-only) way to hit the regression
    targets in docs/CAP_MODEL.md exactly.
    """
    band_values = [
        51.0625,  # R1
        32.2500,  # R2
        24.4375,  # R3
        18.1875,  # R4
        14.0625,  # R5
        7.8125,   # R6
        4.0000,   # R7
        0.7500,   # R8
        0.0000,   # R9
    ]
    players = []
    rank = 1
    for value in band_values:
        for _ in range(16):
            players.append({"oRank": rank, "capDollars": value})
            rank += 1
    return players


class TestCapModelRegression(unittest.TestCase):
    def test_band_averages_and_benchmark(self):
        result = compute_cap_model(_band_fixture())
        expected_bands = [
            51.0625, 32.2500, 24.4375, 18.1875,
            14.0625, 7.8125, 4.0000, 0.7500, 0.0000,
        ]
        for i, (actual, expected) in enumerate(zip(result["bands"], expected_bands), start=1):
            self.assertAlmostEqual(actual, expected, places=6, msg=f"R{i}")

        self.assertAlmostEqual(result["benchmark"], 152.5625, places=6)
        self.assertAlmostEqual(result["rawFloor"], 129.678125, places=6)
        self.assertAlmostEqual(result["rawCeiling"], 175.446875, places=6)
        self.assertEqual(result["roundedFloor"], 130)
        self.assertEqual(result["roundedCeiling"], 175)

    def test_row_order_does_not_matter(self):
        fixture = _band_fixture()
        shuffled = list(reversed(fixture))
        result_a = compute_cap_model(fixture)
        result_b = compute_cap_model(shuffled)
        self.assertEqual(result_a, result_b)

    def test_zero_dollar_player_accepted(self):
        fixture = _band_fixture()
        result = compute_cap_model(fixture)
        self.assertEqual(result["bands"][8], 0.0)

    def test_insufficient_rankings_rejected(self):
        fixture = _band_fixture()[:REQUIRED_RANKS - 1]
        with self.assertRaises(CapModelError):
            compute_cap_model(fixture)

    def test_missing_rank_rejected(self):
        fixture = _band_fixture()
        # Remove rank 72 without reducing total count, leaving a gap.
        fixture = [p for p in fixture if p["oRank"] != 72]
        fixture.append({"oRank": 999, "capDollars": 1.0})
        with self.assertRaises(CapModelError):
            compute_cap_model(fixture)

    def test_duplicate_rank_rejected(self):
        fixture = _band_fixture()
        fixture[1] = dict(fixture[0])  # duplicate oRank 1
        with self.assertRaises(CapModelError):
            compute_cap_model(fixture)


if __name__ == "__main__":
    unittest.main()
