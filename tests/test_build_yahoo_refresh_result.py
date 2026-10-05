import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from build_yahoo_refresh_result import build_ranking_changes  # noqa: E402

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "build_yahoo_refresh_result.py")


def _write(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


class TestBuildRankingChanges(unittest.TestCase):
    def test_no_changes_when_names_match(self):
        current = [{"oRank": 1, "name": "A"}, {"oRank": 2, "name": "B"}]
        previous = [{"oRank": 1, "name": "A"}, {"oRank": 2, "name": "B"}]
        self.assertEqual(build_ranking_changes(current, previous), [])

    def test_detects_rank_occupant_change(self):
        current = [{"oRank": 1, "name": "A"}, {"oRank": 2, "name": "C"}]
        previous = [{"oRank": 1, "name": "A"}, {"oRank": 2, "name": "B"}]
        changes = build_ranking_changes(current, previous)
        self.assertEqual(changes, [
            {"oRank": 2, "previousPlayer": "B", "currentPlayer": "C"},
        ])

    def test_detects_rank_added_or_removed(self):
        current = [{"oRank": 1, "name": "A"}]
        previous = [{"oRank": 1, "name": "A"}, {"oRank": 2, "name": "B"}]
        changes = build_ranking_changes(current, previous)
        self.assertEqual(changes, [
            {"oRank": 2, "previousPlayer": "B", "currentPlayer": None},
        ])


class TestBuildYahooRefreshResultCLI(unittest.TestCase):
    def _run(self, tmpdir, previous_players=None):
        cap_snapshot_path = os.path.join(tmpdir, "cap_snapshot_latest.json")
        current_players_path = os.path.join(tmpdir, "players_normalized.json")
        source_config_path = os.path.join(tmpdir, "yahoo_source.json")
        output_path = os.path.join(tmpdir, "yahoo-refresh-result.json")

        _write(cap_snapshot_path, {
            "fetchedAt": "2026-09-18T000000Z",
            "roundedFloor": 130,
            "roundedCeiling": 175,
            "publishedFloor": 130,
            "publishedCeiling": 175,
        })
        _write(current_players_path, [{"oRank": 1, "name": "A"}])
        _write(source_config_path, {"leagueKey": "478.l.public"})

        args = [
            sys.executable, SCRIPT,
            "--cap-snapshot", cap_snapshot_path,
            "--current-players", current_players_path,
            "--source-config", source_config_path,
            "--output", output_path,
        ]
        if previous_players:
            previous_path = os.path.join(tmpdir, "previous_players.json")
            _write(previous_path, previous_players)
            args += ["--previous-players", previous_path]

        subprocess.run(args, check=True, capture_output=True, text=True)
        with open(output_path, encoding="utf-8") as f:
            return json.load(f)

    def test_match_status_and_no_baseline_note(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._run(tmpdir)
        self.assertEqual(result["source"], "478.l.public")
        self.assertEqual(result["status"], "MATCH")
        self.assertEqual(result["previous"], {"floor": 130, "ceiling": 175})
        self.assertEqual(result["current"], {"floor": 130, "ceiling": 175})
        self.assertEqual(result["rankingChanges"], [])
        self.assertIn("rankingChangesNote", result)

    def test_ranking_changes_populated_when_previous_given(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._run(tmpdir, previous_players=[{"oRank": 1, "name": "Z"}])
        self.assertEqual(result["rankingChanges"], [
            {"oRank": 1, "previousPlayer": "Z", "currentPlayer": "A"},
        ])
        self.assertNotIn("rankingChangesNote", result)


class TestRefreshSemanticsOfficialBand(unittest.TestCase):
    """The official 131-178 band is policy: a refresh compares the FORMULA
    band to the approved formula band, reports snapshot/export staleness,
    and never turns official 178 back into the formula's 177."""

    def _run(self, tmpdir, players, published_players=None, exports_md_text=None, snapshot_extra=None):
        snap = {"fetchedAt": "t", "roundedFloor": 131, "roundedCeiling": 177,
                "approvedFormulaFloor": 131, "approvedFormulaCeiling": 177,
                "officialFloor": 131, "officialCeiling": 178, "ceilingOverride": True,
                "overrideReason": "commissioner", "publishedFloor": 131, "publishedCeiling": 178}
        snap.update(snapshot_extra or {})
        paths = {k: os.path.join(tmpdir, k + ".json") for k in ("snap", "players", "cfg", "pub")}
        _write(paths["snap"], snap)
        _write(paths["players"], players)
        _write(paths["cfg"], {"leagueKey": "478.l.public"})
        out = os.path.join(tmpdir, "out.json")
        args = [sys.executable, SCRIPT, "--cap-snapshot", paths["snap"], "--current-players", paths["players"],
                "--source-config", paths["cfg"], "--output", out]
        if published_players is not None:
            _write(paths["pub"], published_players)
            args += ["--published-players", paths["pub"]]
        if exports_md_text is not None:
            md = os.path.join(tmpdir, "committed.md")
            with open(md, "w", encoding="utf-8") as f:
                f.write(exports_md_text)
            args += ["--exports-md", md]
        subprocess.run(args, check=True, capture_output=True, text=True)
        with open(out, encoding="utf-8") as f:
            return json.load(f)

    def test_same_formula_same_snapshot_is_match_and_official_stays_178(self):
        players = [{"oRank": 1, "name": "A", "capDollars": 1.0}]
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(tmp, players, published_players=players)
        self.assertEqual(result["status"], "MATCH")
        self.assertEqual(result["reasons"], [])
        self.assertEqual(result["official"]["ceiling"], 178)
        self.assertTrue(result["official"]["ceilingOverride"])
        self.assertEqual(result["current"]["ceiling"], 177)  # formula, not official

    def test_formula_177_vs_official_178_is_not_a_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(tmp, [{"oRank": 1, "name": "A", "capDollars": 1.0}])
        self.assertEqual(result["status"], "MATCH")
        self.assertEqual(result["previous"], {"floor": 131, "ceiling": 177})

    def test_market_change_with_same_band_is_changed(self):
        cur = [{"oRank": 1, "name": "A", "nbaTeam": "X", "eligiblePositions": ["PG"], "capDollars": 5.0}]
        pub = [{"oRank": 2, "name": "A", "nbaTeam": "X", "eligiblePositions": ["PG"], "capDollars": 5.0}]
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(tmp, cur, published_players=pub)
        self.assertEqual(result["status"], "CHANGED")
        self.assertIn("yahooSnapshotChanged", result["reasons"])
        self.assertEqual(result["official"]["ceiling"], 178)

    def test_formula_band_change_is_changed_and_official_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(tmp, [{"oRank": 1, "name": "A", "capDollars": 1.0}],
                               snapshot_extra={"roundedFloor": 132, "roundedCeiling": 179})
        self.assertEqual(result["status"], "CHANGED")
        self.assertIn("formulaBandChanged", result["reasons"])
        self.assertEqual((result["official"]["floor"], result["official"]["ceiling"]), (131, 178))

    def test_stale_committed_export_is_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(tmp, [{"oRank": 1, "name": "A", "capDollars": 1.0}], exports_md_text="# stale\n")
        self.assertEqual(result["status"], "CHANGED")
        self.assertIn("exportsStale", result["reasons"])


if __name__ == "__main__":
    unittest.main()
