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


class TestDayHistory(unittest.TestCase):
    def run_reads(self, *reads):
        d = tempfile.mkdtemp()
        previous = None
        for f in reads:
            ll.append(d, f, IL_MAP, RANKS, f["asOf"], previous)
            previous = f
        with open(os.path.join(d, "2026-11-24.jsonl"), encoding="utf-8") as fh:
            return [json.loads(x) for x in fh.read().splitlines()]

    def test_a_day_starts_with_every_player_and_then_records_only_changes(self):
        at = lambda m: "2026-11-24T20:%02d:00Z" % m  # noqa: E731
        a = feed([row(1, "A", "PG", "", "upcoming"), row(2, "B", "BN")], [row(7, "C", "SG")], asof=at(0))
        b = feed([row(1, "A", "PG", "O", "upcoming"), row(2, "B", "BN")], [row(7, "C", "SG")], asof=at(4))
        c = feed([row(1, "A", "BN", "O", "upcoming")], [row(7, "C", "SG")], asof=at(8))                      # A moved, B dropped
        recs = self.run_reads(a, b, c)
        self.assertEqual([r["kind"] for r in recs], ["day_start", "state", "state", "state"])
        self.assertEqual(sorted(p["n"] for p in recs[0]["players"]), ["A", "B", "C"])
        self.assertEqual([(r["n"], r["slot"], r["st"]) for r in recs[1:]], [("A", "PG", "O"), ("A", "BN", "O"), ("B", None, None)])

    def test_a_long_silence_is_recorded_and_a_missing_team_drops_nobody(self):
        a = feed([row(1, "A", "PG")], [row(7, "C", "SG")], asof="2026-11-24T18:00:00Z")
        b = feed([row(1, "A", "PG")], [row(7, "C", "SG")], asof="2026-11-24T19:00:00Z")
        b["matchups"][0]["teams"] = b["matchups"][0]["teams"][:1]
        recs = self.run_reads(a, b)
        self.assertEqual([r["kind"] for r in recs], ["day_start", "gap"])
        self.assertEqual((recs[1]["from"], recs[1]["to"]), ("2026-11-24T18:00:00Z", "2026-11-24T19:00:00Z"))

    def test_a_score_update_is_not_a_change(self):
        a = feed([row(1, "A", "PG", "", "live", "10-8, 1st")], asof="2026-11-24T20:00:00Z")
        b = feed([row(1, "A", "PG", "", "live", "20-18, 2nd")], asof="2026-11-24T20:04:00Z")
        self.assertEqual([r["kind"] for r in self.run_reads(a, b)], ["day_start", "first_tip", "lock"])


class TestStatusBeforeTip(unittest.TestCase):
    def reads(self, minutes=4, before_gs="upcoming", before_day="2026-11-24"):
        before = feed([row(6, "Late Scratch", "PG", "Q", before_gs)], day=before_day, asof=before_day + "T20:00:00Z")
        after = feed([row(6, "Late Scratch", "PG", "O", "live")], asof="2026-11-24T20:%02d:00Z" % minutes)
        return [r for r in ll.records(after, set(), IL_MAP, RANKS, True, after["asOf"], before) if r["kind"] == "lock"][0]

    def test_the_status_shown_just_before_the_tip_is_kept_beside_the_status_at_capture(self):
        r = self.reads()
        self.assertEqual((r["st"], r["pre"], r["pos"]), ("O", {"st": "Q", "at": "2026-11-24T20:00:00Z"}, ["PG"]))

    def test_an_old_or_already_locked_or_other_day_read_says_nothing_about_the_lock(self):
        self.assertNotIn("pre", self.reads(minutes=ll.PRE_MAX_MINUTES + 1))
        self.assertNotIn("pre", self.reads(before_gs="live"))
        self.assertNotIn("pre", self.reads(before_day="2026-11-23"))
        f = feed([row(6, "A", "PG", "O", "live")])
        self.assertNotIn("pre", ll.records(f, set(), IL_MAP, RANKS, True, f["asOf"])[0])   # no earlier read at all

    def test_the_command_reads_the_previous_feed_and_survives_a_torn_one(self):
        with tempfile.TemporaryDirectory() as d:
            now, prev, reg = (os.path.join(d, n) for n in ("live.json", "prev.json", "reg.json"))
            for path, doc in ((now, feed([row(6, "A", "PG", "O", "live")], asof="2026-11-24T20:04:00Z")), (prev, feed([row(6, "A", "PG", "", "upcoming")])), (reg, {"players": []})):
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(doc, fh)
            args = ["--feed", now, "--previous", prev, "--registry", reg, "--log-dir"]
            self.assertEqual(ll.main(args + [os.path.join(d, "a")]), 0)
            with open(os.path.join(d, "a", "2026-11-24.jsonl"), encoding="utf-8") as fh:
                self.assertEqual(json.loads(fh.read().splitlines()[-1])["pre"]["st"], None)
            with open(prev, "w", encoding="utf-8") as fh:
                fh.write("{torn")
            self.assertEqual(ll.main(args + [os.path.join(d, "b")]), 0)


class TestAppendOnly(unittest.TestCase):
    def test_a_player_is_recorded_once_and_a_later_status_change_never_rewrites_it(self):
        with tempfile.TemporaryDirectory() as d:
            f1 = feed([row(2, "Healthy On IL", "IL", "", "live")])
            self.assertEqual(ll.append(d, f1, IL_MAP, RANKS, "2026-11-24T20:00:00Z"), 3)     # day_start + first_tip + the lock
            path = os.path.join(d, "2026-11-24.jsonl")
            with open(path, "rb") as fh:
                before = fh.read()
            f2 = feed([row(2, "Healthy On IL", "IL", "O", "final"), row(6, "Late Tip", "PG", "", "live")], asof="2026-11-24T23:00:00Z")   # now listed Out: the proof stays
            self.assertEqual(ll.append(d, f2, IL_MAP, RANKS, "2026-11-24T23:00:00Z", f1), 4)  # gap, two state changes, one new lock
            with open(path, "rb") as fh:
                after = fh.read()
            self.assertTrue(after.startswith(before))                                          # existing bytes never change
            first = next(json.loads(x) for x in after.decode().splitlines() if '"kind":"lock"' in x)
            self.assertEqual((first["st"], first["flags"]), (None, ["healthy_on_il"]))
            self.assertEqual(ll.append(d, f2, IL_MAP, RANKS, "x", f2), 0)                      # idempotent

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
        self.assertIn("cp live.json prev.json", loop)
        self.assertLess(loop.index("cp live.json prev.json"), loop.index("build_live_feed.py"))
        self.assertIn("--previous prev.json --log-dir", loop)
        body = loop.split("lineup_log() {")[1].split("\n}\n")[0]
        self.assertIn("git push -q origin lineup-log", body)
        self.assertNotIn("--force", body)
        self.assertNotIn("-f ", body)
        # runs after a successful build and before the publish, so the review of the new log goes out with that feed; neither can stop the loop
        order = [loop.index(x) for x in ("build_live_feed.py", "\n    lineup_log ", "scripts/lineup_review.py", "push -q --force")]
        self.assertEqual(order, sorted(order))
        self.assertIn('--player-log player-log.json || echo "lineup review failed"', loop)


if __name__ == "__main__":
    unittest.main()
