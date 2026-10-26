"""scripts/lottery_order.py: provisional, data-only lottery inputs from Yahoo's published rank. No draw, no order assignment."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import lottery_eligibility as le  # noqa: E402
import lottery_order as lo  # noqa: E402
import yahoo_standings as ys  # noqa: E402

CFG = le.load()


def snap(started=True, n=16):
    return {"started": started, "sourceUpdatedAt": "2026-10-26T08:00:00Z",
            "teams": [{"franchiseId": "franchise-%02d" % (i + 1), "rank": 16 - i if False else i + 1} for i in range(n)]}


class TestLotteryOrder(unittest.TestCase):
    def test_nothing_before_the_season_starts(self):
        self.assertIsNone(lo.provisional_lottery(None))
        self.assertIsNone(lo.provisional_lottery(snap(started=False)))

    def test_tickets_follow_the_configured_rank_table_and_add_up(self):
        out = lo.provisional_lottery(snap(), CFG)
        by = {t["rank"]: t for t in out["teams"]}
        self.assertEqual([t["rank"] for t in out["teams"]], list(range(16, 0, -1)))        # worst first, Yahoo's ranks untouched
        self.assertEqual(sum(t["tickets"] or 0 for t in out["teams"]), CFG["lottery"]["totalCombinations"])
        for r in range(1, 5):                                                              # ranks 1-4 never hold tickets (3/4 take the bonus, unmodelled)
            self.assertFalse(by[r]["inLottery"])
            self.assertIsNone(by[r]["tickets"])
        for r in range(5, 17):
            self.assertEqual(by[r]["tickets"], CFG["lottery"]["ticketsByRank"][str(r)])

    def test_everything_is_labelled_provisional_and_no_order_is_assigned(self):
        out = lo.provisional_lottery(snap(), CFG)
        self.assertIn("PROVISIONAL", out["label"])
        self.assertIn("not a draft order", out["label"])
        for forbidden in ("draftOrder", "finalOrder", "picks", "winner", "draw"):
            self.assertNotIn(forbidden, out)

    def test_eligibility_flags_come_from_the_rules_not_from_this_module(self):
        out = lo.provisional_lottery(snap(), CFG)
        want = le.eligibility(CFG, 2027)
        for t in out["teams"]:
            self.assertEqual(t["canPick1"], want.get(t["franchiseId"], {}).get("canPick1", True))
            self.assertEqual(t["restrictions"], want.get(t["franchiseId"], {}).get("reasons", []))

    def test_the_published_standings_produce_a_valid_provisional_view(self):
        s = ys.current_snapshot()
        out = lo.provisional_lottery(s, CFG)
        if s and s.get("started"):
            self.assertEqual(len(out["reverseOrder"]), 16)
            self.assertEqual(out["standingsSourceUpdatedAt"], s["sourceUpdatedAt"])
        else:
            self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()
