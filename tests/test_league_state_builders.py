import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import build_league_state as bls  # noqa: E402
import build_player_registry as reg  # noqa: E402
import league_state as ls  # noqa: E402

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")


def raw(players):
    return {"fantasy_content": {"league": {"league_key": "478.l.public", "players": [{"player": p} for p in players]}}}


def yp(pid, name, cap, rank):
    return {"player_id": str(pid), "player_key": f"478.p.{pid}", "name": {"full": name}, "editorial_team_abbr": "XXX",
            "display_position": "PG", "eligible_positions": [{"position": "PG"}, {"position": "Util"}],
            "projected_auction_value": str(cap), "headshot": {"url": f"https://img/{pid}.png"},
            "player_ranks": [{"player_rank": {"rank_type": "OR", "rank_value": str(rank)}}]}


class TestPlayerRegistryBuilder(unittest.TestCase):
    def test_builds_stable_identity_and_sorts_by_yahoo_or(self):
        r = reg.build_registry(raw([yp(2, "B", 3, 20), yp(1, "A", 9, 5), yp(3, "C", 0, 450)]), "t")
        self.assertEqual([p["playerKey"] for p in r["players"]], ["478.p.1", "478.p.2", "478.p.3"])
        self.assertEqual(r["players"][0]["projectedAuctionValue"], 9.0)
        self.assertEqual(r["players"][2]["oRank"], 450)  # beyond the top 300: still in the registry
        self.assertEqual(r["players"][0]["headshotUrl"], "https://img/1.png")
        self.assertEqual(r["playerCount"], 3)

    def test_duplicate_yahoo_player_key_is_rejected(self):
        with self.assertRaises(reg.RegistryError):
            reg.build_registry(raw([yp(1, "A", 1, 1), yp(1, "A again", 1, 2)]))

    def test_committed_registry_has_600_players_with_unique_keys(self):
        with open(os.path.join(REPO_ROOT, "data", "yahoo", "player_registry.json"), encoding="utf-8") as f:
            r = json.load(f)
        self.assertEqual(r["playerCount"], 600)
        self.assertEqual(len({p["playerKey"] for p in r["players"]}), 600)
        self.assertEqual(max(p["oRank"] for p in r["players"]), 600)

    def test_registry_is_separate_from_the_300_player_market_snapshot(self):
        with open(os.path.join(REPO_ROOT, "data", "yahoo", "players_normalized.json"), encoding="utf-8") as f:
            self.assertEqual(len(json.load(f)), 300)


class TestKeeperLockWorkflow(unittest.TestCase):
    def test_baseline_refuses_to_overwrite_a_locked_freeze(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("franchises.json", "keeper_freeze.json", "picks.json", "trades.json", "draft_state.json"):
                shutil.copy(os.path.join(ls.DATA_DIR, name), tmp)
            path = os.path.join(tmp, "keeper_freeze.json")
            unlocked = ls._load(path)
            unlocked["status"] = "projected"
            locked = ls.lock_keepers(unlocked, "2026-10-09T00:00:00Z")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(locked, f)
            old = bls.DATA_DIR
            bls.DATA_DIR = tmp
            try:
                bls.cmd_baseline(None)
            finally:
                bls.DATA_DIR = old
            after = ls._load(path)
            self.assertEqual(after["status"], "locked")
            self.assertTrue(ls.verify_lock(after))

    def test_baseline_rebuild_is_deterministic(self):
        with open(os.path.join(REPO_ROOT, "index.html"), encoding="utf-8") as f:
            html = f.read()
        r = ls._load(ls.REGISTRY_PATH)
        fr = ls._load(os.path.join(ls.DATA_DIR, "franchises.json"))["franchises"]
        a = bls.build_baseline(html, r, fr)
        self.assertEqual(a, bls.build_baseline(html, r, fr))
        self.assertEqual(a[0]["teams"], ls._load(os.path.join(ls.DATA_DIR, "keeper_freeze.json"))["teams"])
        self.assertEqual(a[1], ls._load(os.path.join(ls.DATA_DIR, "picks.json")))


class TestPageScript(unittest.TestCase):
    def test_inline_app_script_is_syntactically_valid_javascript(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not available")
        with open(os.path.join(REPO_ROOT, "index.html"), encoding="utf-8") as f:
            js = re.search(r'<script id="league-app">(.*?)</script>', f.read(), re.S).group(1)
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as t:
            t.write(js)
        try:
            res = subprocess.run([node, "--check", t.name], capture_output=True, text=True)
        finally:
            os.unlink(t.name)
        self.assertEqual(res.returncode, 0, res.stderr)


if __name__ == "__main__":
    unittest.main()
