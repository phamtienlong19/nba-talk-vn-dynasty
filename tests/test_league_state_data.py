import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import build_fa_draft_pool as pool  # noqa: E402
import build_league_state as bls  # noqa: E402
import league_state as ls  # noqa: E402

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
BSY, DUNG, LC, MELO, SUP, BZ = ("franchise-01", "franchise-06", "franchise-04", "franchise-03", "franchise-12", "franchise-15")


def _html():
    with open(os.path.join(REPO_ROOT, "index.html"), encoding="utf-8") as f:
        return f.read()


class TestRepoState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i = ls.load_inputs()

    def _scn(self, *ids):
        return ls.resolve(self.i, list(ids), "SCENARIO")

    # ----- registry / identity
    def test_registry_is_expanded_beyond_the_fa60(self):
        self.assertGreater(len(self.i["registry"]), 300)
        self.assertGreaterEqual(len(self.i["registry"]), 600)

    def test_registry_identity_is_the_stable_yahoo_player_key(self):
        reg = self.i["registry"]
        self.assertEqual(len(reg), len({p["playerId"] for p in reg.values()}))
        for key, p in reg.items():
            self.assertEqual(key, p["playerKey"])
            self.assertEqual(p["playerKey"], f"478.p.{p['playerId']}")
        self.assertEqual(reg["478.p.5352"]["name"], "Nikola Jokić")

    def test_trade_assets_reference_players_by_yahoo_key_and_name_matches(self):
        for t in self.i["trades"]["trades"]:
            for a in t["assets"]:
                if a["type"] == "player":
                    self.assertEqual(self.i["registry"][a["playerKey"]]["name"], a["name"])

    # ----- baseline
    def test_keeper_freeze_is_projected_not_silently_frozen(self):
        self.assertEqual(self.i["freeze"]["status"], "projected")
        self.assertIsNone(self.i["freeze"]["lockedAt"])
        self.assertFalse(ls.verify_lock(self.i["freeze"]))

    def test_baseline_matches_the_keeper_board_totals(self):
        html = _html()
        teams, _ = bls.parse_board(html)
        state = ls.initial_state(self.i)
        for fid, t in zip(sorted(self.i["franchises"]), teams):
            self.assertEqual(ls.team_cap(self.i, state, fid), sum(c for _, c in t["kept"]), t["short"])
            self.assertEqual(len(ls.team_players(self.i, state, fid)), len(t["kept"]))

    def test_picks_are_stable_ids_with_48_original_owners(self):
        picks = self.i["picks"]["picks"]
        self.assertEqual(len(picks), 48)
        self.assertEqual(picks[0]["pickId"], "2026-R1-01")
        self.assertEqual(self.i["pickIndex"]["2026-R1-03"]["originalOwner"], BSY)
        self.assertEqual(self.i["pickIndex"]["2026-R1-15"]["originalOwner"], BZ)

    def test_trade_ledger_is_all_proposed_nothing_official(self):
        self.assertEqual({t["status"] for t in self.i["trades"]["trades"]}, {"PROPOSED"})
        official = ls.resolve(self.i, [], "OFFICIAL")
        self.assertEqual(official["activeTradeIds"], [])
        self.assertEqual(official["pickOwner"]["2026-R1-03"], BSY)

    # ----- Trades A / B / C
    def test_trade_a_ownership(self):
        s = self._scn("TRADE-A")
        self.assertEqual(s["pickOwner"]["2026-R1-03"], BZ)
        self.assertEqual(s["pickOwner"]["2026-R1-15"], BSY)
        self.assertEqual(s["playerOwner"]["478.p.5197"], BZ)   # Gobert
        self.assertEqual(s["playerOwner"]["478.p.5638"], BSY)  # Murray

    def test_trade_b_ownership(self):
        s = self._scn("TRADE-B")
        self.assertEqual(s["pickOwner"]["2026-R3-06"], BZ)
        self.assertEqual(s["pickOwner"]["2026-R2-15"], DUNG)
        self.assertEqual(s["playerOwner"]["478.p.6550"], BZ)    # F. Wagner
        self.assertEqual(s["playerOwner"]["478.p.6703"], DUNG)  # Duren

    def test_trade_c_chains_and_ownership(self):
        s = self._scn("TRADE-A", "TRADE-B", "TRADE-C")
        self.assertTrue(all(r["applied"] for r in s["tradeResults"]))
        self.assertEqual(s["pickOwner"]["2026-R1-03"], SUP)
        self.assertEqual(s["pickOwner"]["2026-R3-06"], SUP)
        self.assertEqual(s["pickOwner"]["2026-R3-12"], BZ)
        self.assertEqual([(h["from"], h["to"]) for h in s["history"]["pick:2026-R1-03"]], [(BSY, BZ), (BZ, SUP)])
        self.assertEqual([(h["from"], h["to"]) for h in s["history"]["pick:2026-R3-06"]], [(DUNG, BZ), (BZ, SUP)])

    def test_pick_table_current_and_original_columns(self):
        rows = {r["label"]: r for r in ls.pick_table(self.i, self._scn("TRADE-A", "TRADE-B", "TRADE-C"))}
        expect = {"1.03": (SUP, BSY), "1.15": (BSY, BZ), "2.15": (DUNG, BZ), "3.06": (SUP, DUNG), "3.12": (BZ, SUP)}
        for label, (cur, orig) in expect.items():
            self.assertEqual((rows[label]["current"], rows[label]["original"]), (cur, orig), label)

    def test_trade_c_without_upstream_is_a_broken_dependency(self):
        for sel in (["TRADE-C"], ["TRADE-A", "TRADE-C"], ["TRADE-B", "TRADE-C"]):
            s = self._scn(*sel)
            c = [r for r in s["tradeResults"] if r["tradeId"] == "TRADE-C"][0]
            self.assertFalse(c["applied"], sel)
            self.assertEqual([e["code"] for e in c["errors"]], ["BROKEN_DEPENDENCY"], sel)
            self.assertEqual(s["pickOwner"]["2026-R1-03"], BZ if "TRADE-A" in sel else BSY)

    # ----- BZ folded + chained cap
    def test_bz_folded_summary(self):
        s = self._scn("TRADE-A", "TRADE-B", "TRADE-C")
        fold = ls.fold_team(self.i, s, BZ)
        self.assertEqual(sorted(a["n"] for a in fold["in"]), sorted(["Rudy Gobert", "Franz Wagner", "Jalen Williams", "Reed Sheppard", "3.12"]))
        self.assertEqual(sorted(a["n"] for a in fold["out"]), sorted(["Jamal Murray", "Jalen Duren", "Julius Randle", "1.15", "2.15"]))
        self.assertEqual({p["asset"]["n"]: p["chain"] for p in fold["pass"]},
                         {"1.03": ["Bsy", "Bz", "sup fam"], "3.06": ["Dũng", "Bz", "sup fam"]})
        self.assertEqual(len(fold["tradeIds"]), 3)

    def test_bz_chained_cap_uses_the_previous_resulting_state(self):
        s = self._scn("TRADE-A", "TRADE-B", "TRADE-C")
        a, b, c = (r["teams"][BZ] for r in s["tradeResults"])
        base = ls.team_cap(self.i, ls.initial_state(self.i), BZ)
        self.assertEqual(a["capBefore"], base)
        self.assertEqual(b["capBefore"], a["capAfter"])
        self.assertEqual(c["capBefore"], b["capAfter"])
        self.assertEqual(a["playerCapDelta"], 11 - 40)
        self.assertEqual(b["playerCapDelta"], 21 - 27)
        self.assertEqual(c["playerCapDelta"], (26 + 1) - 14)
        self.assertEqual(c["capAfter"], base + (11 - 40) + (21 - 27) + ((26 + 1) - 14))
        self.assertEqual(c["roomToCeiling"], 178 - c["capAfter"])

    def test_cap_numbers_are_derived_not_stored(self):
        raw = json.dumps(self.i["trades"])
        for field in ("capAfter", "capBefore", "playerCapDelta", "roomToCeiling"):
            self.assertNotIn(field, raw)

    # ----- Trade D
    def test_trade_d_is_scenario_only_and_flags_asset_count(self):
        s = self._scn("TRADE-D")
        d = s["tradeResults"][0]
        self.assertTrue(d["applied"])  # still visualisable
        w = [x for x in d["warnings"] if x["code"] == "ASSET_COUNT_UNBALANCED"]
        self.assertEqual(w[0]["detail"], {"LC": 2, "Melo": 1})
        self.assertEqual(self.i["tradeIndex"]["TRADE-D"]["status"], "PROPOSED")

    def test_pre_draft_window_trade_limit_is_surfaced_for_bz(self):
        s = self._scn("TRADE-A", "TRADE-B", "TRADE-C")
        self.assertEqual([w["detail"]["team"] for w in s["windowWarnings"]], ["Bz"])


class TestEmbeddedPageData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = _html()
        cls.js = re.search(r'<script id="league-app">(.*?)</script>', cls.html, re.S).group(1)
        m = re.search(r'<script type="application/json" id="league-data">(.*?)</script>', cls.html, re.S)
        cls.data = json.loads(m.group(1).replace("<\\/", "</"))
        cls.i = ls.load_inputs()

    def test_embedded_data_is_exactly_what_the_engine_derives(self):
        fresh = bls.build_page_data(self.i, self.html)
        self.assertEqual(self.data, fresh)

    def test_all_scenario_combinations_are_present(self):
        self.assertEqual(len(self.data["scenarios"]), 2 ** len(ls.selectable_trades(self.i)))
        self.assertIn("TRADE-A,TRADE-B,TRADE-C", self.data["scenarios"])

    def test_official_view_has_no_movement_and_scenario_view_has_it(self):
        self.assertEqual(self.data["scenarios"][""]["teams"], {})
        self.assertIn(BZ, self.data["scenarios"]["TRADE-A,TRADE-B,TRADE-C"]["teams"])

    def test_legal_universe_is_larger_than_the_recommendation_board(self):
        rows = self.data["available"]["rows"]
        self.assertGreater(len(rows), 60)
        on_board = [r for r in rows if r[6] is not None]
        self.assertEqual(len(on_board), 60)
        outside = [r for r in rows if r[6] is None and r[5] and r[5] > 300]
        self.assertTrue(outside, "a Yahoo-ranked player outside the recommendation board must be selectable")

    def test_kept_players_are_not_available(self):
        keys = {r[0] for r in self.data["available"]["rows"]}
        kept = {k["playerKey"] for t in self.i["freeze"]["teams"] for k in t["keepers"]}
        self.assertFalse(keys & kept)

    def test_dynasty_rank_is_not_exposed_in_the_operational_data(self):
        self.assertEqual(self.data["available"]["cols"], ["key", "name", "nba", "pos", "cap", "yahooOr", "board", "src"])
        keys = set(re.findall(r'"([A-Za-z_]+)":', json.dumps(self.data)))
        self.assertFalse([k for k in keys if "dynasty" in k.lower() or "consensus" in k.lower()])

    def test_board_rank_in_the_universe_matches_the_fa60(self):
        pool_names = re.findall(r'<div class="pool-rank">(\d+)</div><div class="pool-pos">[^<]*</div><div class="pool-player">(.*?)</div>', self.html)
        import html as h
        by_rank = {int(r): h.unescape(n) for r, n in pool_names}
        for row in self.data["available"]["rows"]:
            if row[6] is not None:
                self.assertEqual(by_rank[row[6]], row[1])

    def test_page_exposes_the_new_surfaces_and_existing_ones_remain(self):
        for anchor in ('id="trade-lab"', 'id="picks"', 'id="draft-pool"', 'id="cap"', 'id="rosters-a"', 'id="draft-order"'):
            self.assertIn(anchor, self.html)
        for label in (">TRADE LAB<", ">PICKS<", ">OFFICIAL<", ">SCENARIO<", 'id="scn-banner"', "SCENARIO VIEW — NOT OFFICIAL"):
            self.assertIn(label, self.html + self.js)
        self.assertIn('id="avail"', self.html)
        self.assertIn("exports/yahoo_top300_proj_dollar_rank.xlsx", self.html)

    def test_embed_is_idempotent(self):
        once = bls.embed(self.html, self.data)
        self.assertEqual(once, self.html)
        self.assertEqual(bls.embed(once, self.data), once)


if __name__ == "__main__":
    unittest.main()
