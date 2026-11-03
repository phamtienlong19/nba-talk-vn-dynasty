"""Lineup-integrity evidence: out starters, empty slots and benched stars, read from closed days."""
import datetime
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import live_lineups as ll  # noqa: E402
import update_yahoo_matchups as um  # noqa: E402
import yahoo_rosters as yr  # noqa: E402

CFG = dict(yr.load_config(), requestDelaySeconds=0)


def row(slot, name=None, pid=None, pos=("PG",), status="", game="W, 100-90 vs AAA", stats=True):
    line = {k: (5 if stats else None) for k in ("fgPct", "ftPct", "tpm", "pts", "reb", "ast", "st", "blk", "to")}
    return {"slot": slot, "name": name, "playerId": pid, "positions": list(pos), "status": status, "game": game if name else None, "line": line if name else {}}


class TestMisses(unittest.TestCase):
    def test_an_out_starter_with_an_eligible_healthy_bench_player_is_a_misset(self):
        rows = [row("PG", "Out Guy", "1", status="O", stats=False), row("BN", "Bench Guy", "2", pos=("PG", "SG"))]
        got = ll.misses(rows, {})
        self.assertEqual([(i["k"], i["p"], i["r"]) for i in got], [("out_starter", "Out Guy", "Bench Guy")])

    def test_no_misset_without_a_healthy_eligible_replacement_with_a_game(self):
        wrong_position = [row("C", "Out Big", "1", pos=("C",), status="O", stats=False), row("BN", "Guard", "2", pos=("PG",))]
        replacement_also_out = [row("PG", "Out PG", "3", status="INJ", stats=False), row("BN", "Hurt", "4", status="O", stats=False)]
        replacement_idle = [row("SG", "Out SG", "5", pos=("SG",), status="O", stats=False), row("BN", "Idle", "6", pos=("SG",), game=None)]
        for rows in (wrong_position, replacement_also_out, replacement_idle):
            self.assertEqual(ll.misses(rows, {}), [])

    def test_an_out_player_who_recorded_stats_is_not_a_misset(self):
        rows = [row("PG", "Played", "1", status="O", stats=True), row("BN", "Bench Guy", "2")]
        self.assertEqual(ll.misses(rows, {}), [])

    def test_an_empty_starting_slot_with_a_bench_player_who_could_fill_it(self):
        rows = [row("Util"), row("BN", "Bench Guy", "2", pos=("PF",))]
        self.assertEqual([i["k"] for i in ll.misses(rows, {})], ["empty_slot"])

    def test_composite_slots_accept_their_positions_and_each_replacement_is_used_once(self):
        rows = [row("G", "Out A", "1", pos=("PG",), status="O", stats=False), row("F", "Out B", "2", pos=("SF",), status="O", stats=False),
                row("BN", "Only Wing", "3", pos=("SF",))]
        got = ll.misses(rows, {})
        self.assertEqual([i["p"] for i in got], ["Out B"])                           # the guard slot has no eligible replacement

    def test_a_healthy_star_on_the_bench_with_a_game_is_counted_by_rank(self):
        rows = [row("BN", "Star", "10", pos=("C",)), row("BN", "Role", "11", pos=("C",))]
        got = ll.misses(rows, {"10": 12, "11": 180})
        self.assertEqual([(i["k"], i["p"], i["rank"]) for i in got], [("star_benched", "Star", 12)])


class TestChecks(unittest.TestCase):
    NOW = datetime.datetime(2026, 11, 5, 12, tzinfo=datetime.timezone.utc)            # Thursday 04:00 Pacific: Mon and Tue... closed (Mon 11-02, Tue 11-03, Wed 11-04)
    PAGES = [{"teams": [{"teamId": 1}, {"teamId": 2}]}]

    def setUp(self):
        self.calls = []
        self._orig = um.fetch_page

        def fake(cfg, fetcher, url, **kw):
            self.calls.append(url)
            return {"rosters": {1: [row("PG", "Out Guy", "1", status="O", stats=False), row("BN", "Bench Guy", "2")], 2: [row("PG", "Fine", "3")]}}
        um.fetch_page = fake

    def tearDown(self):
        um.fetch_page = self._orig

    def test_closed_days_are_summarised_per_team_against_the_rule(self):
        out = ll.checks(CFG, 3, self.PAGES, None, self.NOW, {}, None, lambda x: None)
        self.assertEqual(sorted(out["byDate"]), ["2026-11-02", "2026-11-03", "2026-11-04"])
        t = {x["yahooId"]: x for x in out["teams"]}
        self.assertEqual((t[1]["missetDays"], t[1]["players"], t[1]["meetsCount"]), (3, 1, True))      # 2+ days reaches the rule's count
        self.assertEqual((t[2]["missetDays"], t[2]["meetsCount"]), (0, False))

    def test_days_already_in_the_previous_feed_are_not_captured_again(self):
        first = ll.checks(CFG, 3, self.PAGES, None, self.NOW, {}, None, lambda x: None)
        n = len(self.calls)
        ll.checks(CFG, 3, self.PAGES, None, self.NOW + datetime.timedelta(hours=1), {}, {"lineupChecks": first}, lambda x: None)
        self.assertEqual(len(self.calls), n)
        ll.checks(CFG, 3, self.PAGES, None, self.NOW + datetime.timedelta(days=1), {}, {"lineupChecks": first}, lambda x: None)
        self.assertEqual(len(self.calls), n + 1)                                   # only the newly closed day

    def test_a_day_yahoo_cannot_serve_is_reported_missing(self):
        def boom(cfg, fetcher, url, **kw):
            raise ll.ym.MatchupError("HTTP_404", url)
        um.fetch_page = boom
        out = ll.checks(CFG, 3, self.PAGES, None, self.NOW, {}, None, lambda x: None)
        self.assertEqual(len(out["missing"]), 3)
        self.assertEqual(out["byDate"], {})


if __name__ == "__main__":
    unittest.main()
