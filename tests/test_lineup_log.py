"""The lineup log: what each lineup looked like when each game locked. Append-only evidence."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import lineup_log as ll  # noqa: E402

ROOT = os.path.join(HERE, "..")
IL_MAP = {"1": True, "2": False, "3": False}
RANKS = {"4": 12, "5": 300}


def row(p, name, slot, st="", gs=None, g=None):
    r = {"s": slot, "n": name, "p": str(p), "t": "BOS", "pos": ["PG"], "st": st}
    if gs:
        r.update(gs=gs, g=g or "vs NYK 7:30 pm")
    return r


def feed(rows_a, rows_b=(), day="2026-11-24", asof=None):
    return {"dayDate": "2026-11-23", "asOf": asof or day + "T20:00:00Z", "matchups": [{"teams": [
        {"team": "franchise-01", "yahooId": 8, "name": "Team A", "roster": list(rows_a)},
        {"team": "franchise-02", "yahooId": 4, "name": "Team B", "roster": list(rows_b)}]}]}


class TestRecords(unittest.TestCase):
    def test_only_players_whose_game_is_live_or_final_are_recorded_with_their_slot_and_status(self):
        f = feed([row(1, "Hurt Guy", "IL", "O", "live"), row(9, "Later", "PG", "", "upcoming"), row(10, "Idle", "BN")])
        recs = ll.records(f, set(), IL_MAP, RANKS, False, f["asOf"])
        locks = [r for r in recs if r["kind"] == "lock"]
        self.assertEqual([(r["n"], r["slot"], r["st"], r["il"], r["flags"]) for r in locks], [("Hurt Guy", "IL", "O", "injured", [])])
        self.assertEqual(locks[0]["k"], "478.p.1")
        self.assertEqual(locks[0]["date"], "2026-11-24")
        late = feed([row(1, "Hurt Guy", "IL", "O", "live")], asof="2026-11-25T02:30:00Z")             # 6:30 pm Pacific on the 24th, already the 25th in UTC
        self.assertEqual(ll.records(late, set(), IL_MAP, RANKS, True, late["asOf"])[0]["date"], "2026-11-24")

    def test_flags_are_facts_the_rules_define(self):
        f = feed([row(2, "Healthy On IL", "IL", "", "live"), row(3, "Q On IL", "IL", "Q", "final"), row(4, "Star Bench", "BN", "", "live"),
                  row(5, "Nobody Bench", "BN", "", "live"), row(6, "Out Starter", "PG", "O", "live")])
        by = {r["n"]: r for r in ll.records(f, set(), IL_MAP, RANKS, True, f["asOf"])}
        self.assertEqual(by["Healthy On IL"]["flags"], ["healthy_on_il"])      # no status, registry says not IL-eligible
        self.assertEqual(by["Q On IL"]["flags"], ["healthy_on_il"])            # an ineligible status
        self.assertEqual(by["Star Bench"]["flags"], ["star_benched"])          # O-Rank 12 on the bench, healthy, with a game
        self.assertEqual(by["Nobody Bench"]["flags"], [])
        self.assertEqual(by["Out Starter"]["flags"], ["out_starter"])

    def test_a_first_tip_snapshot_of_every_team_is_written_once(self):
        f = feed([row(1, "A1", "PG", "", "live"), row(8, "A2", "BN", "", "upcoming")], [row(7, "B1", "SG")])
        first = ll.records(f, set(), IL_MAP, RANKS, False, f["asOf"])[0]
        self.assertEqual(first["kind"], "first_tip")
        self.assertEqual(sorted(first["teams"]), ["franchise-01", "franchise-02"])
        self.assertEqual([p["n"] for p in first["teams"]["franchise-01"]], ["A1", "A2"])
        self.assertFalse(any(r["kind"] == "first_tip" for r in ll.records(f, set(), IL_MAP, RANKS, True, f["asOf"])))

    def test_nothing_is_written_before_any_game_locks(self):
        f = feed([row(1, "A1", "PG", "", "upcoming")])
        self.assertEqual(ll.records(f, set(), IL_MAP, RANKS, False, f["asOf"]), [])


class TestAppendOnly(unittest.TestCase):
    def test_a_player_is_recorded_once_and_a_later_status_change_never_rewrites_it(self):
        with tempfile.TemporaryDirectory() as d:
            f1 = feed([row(2, "Healthy On IL", "IL", "", "live")])
            self.assertEqual(ll.append(d, f1, IL_MAP, RANKS, "2026-11-24T20:00:00Z"), 2)     # first_tip + the lock
            path = os.path.join(d, "2026-11-24.jsonl")
            with open(path, "rb") as fh:
                before = fh.read()
            f2 = feed([row(2, "Healthy On IL", "IL", "O", "final"), row(6, "Late Tip", "PG", "", "live")], asof="2026-11-24T23:00:00Z")   # now listed Out: the proof stays
            self.assertEqual(ll.append(d, f2, IL_MAP, RANKS, "2026-11-24T23:00:00Z"), 1)      # only the new player
            with open(path, "rb") as fh:
                after = fh.read()
            self.assertTrue(after.startswith(before))                                          # existing bytes never change
            first = json.loads(after.decode().splitlines()[1])
            self.assertEqual((first["st"], first["flags"]), (None, ["healthy_on_il"]))
            self.assertEqual(ll.append(d, f2, IL_MAP, RANKS, "x"), 0)                          # idempotent

    def test_each_day_has_its_own_file_and_an_earlier_day_is_never_touched(self):
        with tempfile.TemporaryDirectory() as d:
            ll.append(d, feed([row(1, "A", "PG", "", "live")], day="2026-11-23"), IL_MAP, RANKS, "t1")
            with open(os.path.join(d, "2026-11-23.jsonl"), "rb") as fh:
                day1 = fh.read()
            ll.append(d, feed([row(1, "A", "PG", "", "live")], day="2026-11-24"), IL_MAP, RANKS, "t2")
            self.assertEqual(sorted(os.listdir(d)), ["2026-11-23.jsonl", "2026-11-24.jsonl"])
            with open(os.path.join(d, "2026-11-23.jsonl"), "rb") as fh:
                self.assertEqual(fh.read(), day1)

    def test_a_feed_without_a_capture_time_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                ll.append(d, {"matchups": []}, IL_MAP, RANKS, "t")

    def test_the_registry_map_reads_the_il_token_and_skips_unlisted_players(self):
        m = ll.registry_il({"players": [{"playerId": "1", "eligiblePositions": ["C", "IL"]}, {"playerId": "2", "eligiblePositions": ["C"]}, {"playerId": "3", "eligiblePositions": []}]})
        self.assertEqual(m, {"1": True, "2": False})

    def test_the_loop_only_ever_pushes_the_log_normally_never_forced(self):
        loop = open(os.path.join(ROOT, "scripts", "live_feed_loop.sh"), encoding="utf-8").read()
        body = loop.split("lineup_log() {")[1].split("\n}\n")[0]
        self.assertIn("git push -q origin lineup-log", body)
        self.assertNotIn("--force", body)
        self.assertNotIn("-f ", body)
        self.assertIn("lineup_log\n    wait_for", loop)                                         # runs after every successful build, before the wait


if __name__ == "__main__":
    unittest.main()
