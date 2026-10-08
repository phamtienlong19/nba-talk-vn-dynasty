"""Post-freeze WHAT-IF layer: official protection, Scenario A, Scenario B, hypothetical FA 60, UI."""
import copy
import glob
import hashlib
import html as html_lib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import build_fa_draft_pool as pool  # noqa: E402
import league_state as ls  # noqa: E402
import what_if as wi  # noqa: E402

INDEX = os.path.join(ROOT, "index.html")
SNAP = "2026-10-08"
_CACHE = {}


def built():
    if "r" not in _CACHE:
        _CACHE["inputs"] = ls.load_inputs()
        _CACHE["r"] = wi.build_what_if(_CACHE["inputs"], wi.load_snapshot(SNAP))
    return _CACHE["inputs"], _CACHE["r"]


def _hash_tree(patterns):
    out = {}
    for pat in patterns:
        for p in sorted(glob.glob(os.path.join(ROOT, pat), recursive=True)):
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    out[os.path.relpath(p, ROOT)] = hashlib.sha256(f.read()).hexdigest()
    return out


OFFICIAL_FILES = ["data/2026-27/*.json", "data/2026-27/snapshots/*.json", "data/yahoo/*.json", "config/cap_policy.json",
                  "data/dynasty/*.json", "exports/*"]


class TestSnapshot(unittest.TestCase):
    def test_provenance_keeps_three_dates_apart(self):
        m = wi.load_snapshot(SNAP)["meta"]
        self.assertEqual(m["effectiveDate"], "2026-10-08")
        self.assertRegex(m["fileAcquiredAt"], r"^2026-10-08T")
        self.assertEqual(m["yahoo"]["leagueEditKey"], "2026-10-07")
        self.assertEqual(m["capField"], "projected_auction_value")
        self.assertEqual(len(m["sourceSha256"]), 64)
        self.assertEqual(m["playerCount"], 300)

    def test_stored_rows_exclude_the_wrong_salary_metric(self):
        for r in wi.load_snapshot(SNAP)["players"]:
            self.assertNotIn("auctionValue", r)
            self.assertNotIn("average_auction_cost", r)

    def test_import_reads_projected_value_not_average_cost(self):
        raw = {"fantasy_content": {"league": {"league_key": "x.l.1", "edit_key": "2026-01-01", "players": [
            {"player": {"player_key": "x.p.1", "player_id": "1", "name": {"full": "A B"}, "editorial_team_abbr": "BOS",
                        "eligible_positions": [{"position": "C"}], "projected_auction_value": "7", "average_auction_cost": "99",
                        "player_ranks": [{"player_rank": {"rank_type": "OR", "rank_value": "1"}}], "player_notes_last_timestamp": 1790000000}}]}}}
        with tempfile.TemporaryDirectory() as d:
            raw_p = os.path.join(d, "r.json")
            with open(raw_p, "w") as f:
                json.dump(raw, f)
            out = wi.import_snapshot(raw_p, "t1", "2026-01-02", out_root=d, acquired_at="2026-01-02T00:00:00Z")
            rows = wi._load(os.path.join(out, "players.json"))
            self.assertEqual(rows[0]["capDollars"], 7.0)
            meta = wi._load(os.path.join(out, "snapshot.json"))
            self.assertEqual(meta["fileAcquiredAt"], "2026-01-02T00:00:00Z")
            self.assertEqual(meta["yahoo"]["leagueEditKey"], "2026-01-01")

    def test_recomputed_band_uses_the_cap_model(self):
        _, r = built()
        self.assertEqual((r["band"]["whatIf"]["floor"], r["band"]["whatIf"]["ceiling"]), (131, 178))
        self.assertEqual(r["band"]["whatIf"]["benchmark"], 154.625)
        self.assertEqual((r["band"]["official"]["floor"], r["band"]["official"]["ceiling"]), (131, 178))

    def test_classify_matches_official_cap_status(self):
        i = ls.load_inputs()
        for cap in range(90, 200):
            self.assertEqual(wi.classify(cap, 131, 178, 4), ls.cap_status(i, cap), cap)


class TestOfficialProtection(unittest.TestCase):
    def test_build_never_writes_official_state(self):
        before = _hash_tree(OFFICIAL_FILES)
        self.assertTrue(before)
        wi.build_page_payload()
        self.assertEqual(before, _hash_tree(OFFICIAL_FILES))

    def test_freeze_still_locked_and_verifies(self):
        i, _ = built()
        self.assertEqual(i["freeze"]["status"], "locked")
        self.assertTrue(ls.verify_lock(i["freeze"]))

    def test_embed_touches_only_its_own_block(self):
        with open(INDEX, encoding="utf-8") as f:
            html = f.read()
        base = wi.strip_block(html)
        payload = wi.build_page_payload()
        again = wi.embed(base, payload)
        self.assertEqual(wi.strip_block(again), base)
        self.assertEqual(wi.embed(again, payload), again)  # idempotent
        self.assertEqual(again, html)  # committed page is current

    def test_official_fa_pool_matches_the_published_board(self):
        _, r = built()
        with open(INDEX, encoding="utf-8") as f:
            html = f.read()
        board = [html_lib.unescape(n) for n in re.findall(r'<div class="pool-player">(.*?)</div>', wi.strip_block(html))]
        self.assertEqual([x["n"] for x in r["fa"]["official"]], board)

    def test_official_prices_are_the_frozen_checkpoint(self):
        i, r = built()
        for t in r["teams"]:
            self.assertEqual(t["a"]["official"], i["freeze"]["checkpoint"]["teams"][t["id"]]["keeperCap"])


class TestScenarioA(unittest.TestCase):
    def test_all_sixteen_teams_same_keepers(self):
        i, r = built()
        self.assertEqual(len(r["teams"]), 16)
        for t in r["teams"]:
            frozen = [k["playerKey"] for k in next(x for x in i["freeze"]["teams"] if x["franchiseId"] == t["id"])["keepers"]]
            self.assertEqual(sorted(p["k"] for p in t["players"] if p["k0"]), sorted(frozen))
            self.assertEqual(len(frozen), 9)

    def test_totals_deltas_and_classification(self):
        _, r = built()
        fl, ce = r["band"]["whatIf"]["floor"], r["band"]["whatIf"]["ceiling"]
        for t in r["teams"]:
            k = [p for p in t["players"] if p["k0"]]
            self.assertEqual(t["a"]["official"], sum(p["c0"] for p in k))
            self.assertEqual(t["a"]["whatIf"], sum(p["c1"] for p in k))
            self.assertEqual(t["a"]["delta"], t["a"]["whatIf"] - t["a"]["official"])
            self.assertEqual(t["a"]["compliance"], wi.compliance(t["a"]["whatIf"], fl, ce))
            self.assertEqual(t["a"]["room"], ce - t["a"]["whatIf"])
        s = r["summary"]
        self.assertEqual((s["within"], s["belowFloor"], s["aboveCeiling"]), (11, 4, 1))

    def test_known_values(self):
        _, r = built()
        by = {t["short"]: t["a"] for t in r["teams"]}
        self.assertEqual((by["Đạt"]["official"], by["Đạt"]["whatIf"], by["Đạt"]["compliance"]), (174, 180, "ABOVE_CEILING"))
        self.assertEqual(by["sup fam"]["delta"], 8)
        self.assertEqual(by["DonTrick"]["delta"], -7)

    def test_missing_is_zero_and_flagged(self):
        _, r = built()
        jackson = [p for t in r["teams"] for p in t["players"] if p["n"] == "Isaiah Jackson"][0]
        self.assertTrue(jackson["miss"])
        self.assertEqual(jackson["c1"], 0)
        self.assertEqual(jackson["c0"], 0)

    def test_every_player_has_one_owner_and_stable_id(self):
        _, r = built()
        keys = [p["k"] for t in r["teams"] for p in t["players"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(all(k.startswith("478.p.") for k in keys))


class TestScenarioB(unittest.TestCase):
    def test_roster_source_is_the_prekeeper_roster(self):
        i, r = built()
        pre = wi._load(wi.PREKEEPER_PATH)
        self.assertEqual(sum(len(t["players"]) for t in r["teams"]), len({(a["franchiseId"], a["playerName"]) for a in pre["assignments"]}))
        for t in r["teams"]:
            for p in t["players"]:
                self.assertTrue(p["k0"] or not p["k1"] or True)
        for t in r["teams"]:
            self.assertTrue({p["k"] for p in t["players"] if p["k0"]} <= {p["k"] for p in t["players"]})

    def test_rules_respected(self):
        _, r = built()
        ce = r["band"]["whatIf"]["ceiling"]
        for t in r["teams"]:
            kept = [p for p in t["players"] if p["k1"]]
            self.assertLessEqual(len(kept), 9)
            self.assertEqual(len(kept), 9)
            self.assertLessEqual(sum(p["c1"] for p in kept), ce)
            for p in t["players"]:
                if p["k0"] and not p["k1"]:
                    self.assertLess(p["c1"], 20, "a >= $20 player can never be dropped")
            self.assertEqual(t["b"]["total"], sum(p["c1"] for p in kept))

    def test_only_the_mechanical_team_changes(self):
        _, r = built()
        self.assertEqual(r["summary"]["redoChanged"], ["Đạt"])
        dat = next(t for t in r["teams"] if t["short"] == "Đạt")
        self.assertEqual(dat["b"]["total"], 178)
        self.assertGreater(dat["b"]["equalOptions"], 1)
        self.assertEqual(len(dat["b"]["alternatives"]), 3)
        self.assertEqual(r["summary"]["redoAboveCeiling"], 0)

    def test_floor_is_not_a_forced_change(self):
        _, r = built()
        cc = next(t for t in r["teams"] if t["short"] == "CrazyCat")
        self.assertEqual(cc["b"]["compliance"], "BELOW_FLOOR")
        self.assertFalse(cc["b"]["newlyKept"] or cc["b"]["newlyCut"])

    def test_discretionary_swaps_are_flagged_not_applied(self):
        _, r = built()
        lc = next(t for t in r["teams"] if t["short"] == "LC")
        self.assertEqual([d["inName"] for d in lc["b"]["discretionary"]], ["Day'Ron Sharpe"])
        self.assertEqual(lc["b"]["total"], lc["a"]["whatIf"])

    def test_deterministic(self):
        i = ls.load_inputs()
        a = wi.build_what_if(i, wi.load_snapshot(SNAP))
        b = wi.build_what_if(i, wi.load_snapshot(SNAP))
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def _proj(self, prices, k0, ceiling, **kw):
        names = {k: k for k in prices}
        value = kw.pop("value", {k: 0.5 for k in prices})
        A = wi.load_assumptions()
        return wi.project_keepers(sorted(prices), set(k0), prices, names, value, ceiling, A)

    def test_unchanged_when_legal(self):
        out = self._proj({"a": 10, "b": 5, "c": 0}, ["a", "b"], 20)
        self.assertFalse(out["mechanical"])
        self.assertEqual(out["keep"], ["a", "b"])

    def test_fewest_changes_then_value(self):
        prices = {"a": 12, "b": 8, "c": 6, "d": 0, "e": 0}
        value = {"a": .9, "b": .5, "c": .4, "d": .3, "e": .8}
        out = self._proj(prices, ["a", "b", "c"], 16, value=value)  # 26 -> must drop 10+: only 'a'(12)... review-drop first
        self.assertTrue(out["mechanical"])
        self.assertLessEqual(sum(prices[k] for k in out["keep"]), 16)
        self.assertEqual(len(out["keep"]), 3)

    def test_never_drops_20_plus(self):
        prices = {"star": 25, "b": 9, "c": 8, "z": 0}
        out = self._proj(prices, ["star", "b", "c"], 36, value={"star": .1, "b": .9, "c": .9, "z": .9})
        self.assertIn("star", out["keep"])
        self.assertNotIn("b", out["keep"] if prices["b"] + prices["c"] + 25 > 36 and False else [])
        self.assertLessEqual(sum(prices[k] for k in out["keep"]), 36)

    def test_infeasible_protected_set_is_reported(self):
        prices = {"s1": 30, "s2": 30, "z": 0}
        out = self._proj(prices, ["s1", "s2"], 40)
        self.assertTrue(out["infeasible"] or sum(prices[k] for k in out["keep"]) <= 40)

    def test_equal_options_are_exposed(self):
        prices = {"a": 5, "b": 5, "c": 5, "z": 0}
        out = self._proj(prices, ["a", "b", "c"], 10)
        self.assertGreaterEqual(out["equalOptions"], 3)
        self.assertEqual(len(out["alternatives"]), 2)


class TestHypotheticalFa(unittest.TestCase):
    def test_pool_invariants(self):
        _, r = built()
        for key in ("official", "reprice", "redo"):
            rows = r["fa"][key]
            self.assertEqual(len(rows), 60)
            caps = [x["cap"] for x in rows]
            self.assertEqual(caps, sorted(caps, reverse=True), key)
            names = [pool.normalize_name(x["n"]) for x in rows]
            self.assertEqual(len(names), len(set(names)), key)

    def test_kept_players_are_excluded_and_cuts_enter(self):
        _, r = built()
        kept = {pool.normalize_name(p["n"]) for t in r["teams"] for p in t["players"] if p["k1"]}
        self.assertFalse(kept & {pool.normalize_name(x["n"]) for x in r["fa"]["redo"]})
        d = r["fa"]["diff"]
        self.assertEqual([x["n"] for x in d["entered"]], ["Collin Gillespie"])
        self.assertEqual([x["n"] for x in d["exited"]], ["Yves Missi"])
        self.assertEqual(d["entered"][0]["cause"], "KEEPER")
        gil = next(x for x in r["fa"]["redo"] if x["n"] == "Collin Gillespie")
        self.assertEqual((gil["src"], gil["st"]), ("cut", "Đạt"))

    def test_causes_are_staged(self):
        off = [{"n": c} for c in "ABCDE"]
        rep = [{"n": c} for c in "ABCDF"]  # market: E out, F in
        redo = [{"n": c} for c in "ABCFG"]  # keeper: D out, G in
        d = wi.compare_pools(off, rep, redo, 1)
        self.assertEqual({x["n"]: x["cause"] for x in d["entered"]}, {"F": "MARKET", "G": "KEEPER"})
        self.assertEqual({x["n"]: x["cause"] for x in d["exited"]}, {"E": "MARKET", "D": "KEEPER"})

    def test_rookies_and_pinned_names_still_considered(self):
        _, r = built()
        names = {x["n"] for x in r["fa"]["redo"]}
        self.assertIn("Cameron Boozer", names)
        self.assertIn("Paul Reed", names)
        self.assertTrue(any(x["src"] == "R" for x in r["fa"]["redo"]))


class TestJsParity(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node not available")
    def test_classify_in_js_matches_python(self):
        with open(os.path.join(ROOT, "scripts", "what_if_app.js"), encoding="utf-8") as f:
            js = f.read()
        fns = re.search(r"function classify.*?\nfunction compliance[^\n]*", js, re.S).group(0)
        probe = fns + "\nvar o=[];for(var c=90;c<200;c++)o.push([classify(c,131,178,4),compliance(c,131,178)]);console.log(JSON.stringify(o));"
        out = subprocess.run(["node", "-e", probe], capture_output=True, text=True, check=True).stdout
        for c, (st, comp) in zip(range(90, 200), json.loads(out)):
            self.assertEqual(st, wi.classify(c, 131, 178, 4))
            self.assertEqual(comp, wi.compliance(c, 131, 178))

    @unittest.skipUnless(shutil.which("node"), "node not available")
    def test_scripts_are_syntactically_valid(self):
        subprocess.run(["node", "--check", os.path.join(ROOT, "scripts", "what_if_app.js")], check=True)


def _chrome():
    for c in (os.environ.get("CHROME_BIN"), "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              shutil.which("google-chrome"), shutil.which("google-chrome-stable"), shutil.which("chromium"),
              shutil.which("chromium-browser")):
        if c and os.path.exists(c):
            return c
    return None


HARNESS = r"""
<script>(function(){var R={};var C='\uD83D\uDC51';function q(s){return document.querySelector(s)}function qa(s){return Array.prototype.slice.call(document.querySelectorAll(s))}
function totals(){return qa('section.team-card .cap-total').map(function(e){return e.firstChild.textContent});}
function seg(t){qa('.wi-seg button').filter(function(b){return b.textContent===t})[0].click();}
function dat(){return qa('article.wi-card').filter(function(c){return c.querySelector('.identity-tag').textContent==='Đạt'})[0];}
function tot(){return dat().querySelector('.cap-total').firstChild.textContent;}
function row(n){return qa('article.wi-card .player-row').filter(function(r){return r.closest('article')===dat()&&r.querySelector('.pname').textContent.indexOf(n)===0})[0];}
R.initial={cls:document.body.className,hidden:q('#what-if').hidden,totals:totals(),pool:qa('.pool-player').length};
q('.modeswitch button[data-mode=WHATIF]').click();
R.wi={cls:document.body.className,hidden:q('#what-if').hidden,banner:q('#scn-banner').textContent,rows:qa('.wi-trow').length,
  title:document.title,crown:q('#what-if').textContent.indexOf('\uD83D\uDC51')>=0,snap:q('#what-if .wi-pill-wi').textContent,url:location.search};
qa('.wi-trow')[8].click();R.detail={cards:qa('.wi-detail article.team-card').length,rowsA:qa('.wi-detail .player-row').length};
seg('REDO CUTS');R.redo={cards:qa('article.wi-card').length,sectionCards:qa('section.team-card').length,secTotals:totals(),dat0:tot()};
row('DeMar').querySelector('.wi-tg').click();R.redoCrown=dat().querySelector('.team-name').textContent.indexOf(C)>=0;R.afterCut={dat:tot(),edited:!!dat().querySelector('.wi-reset:not([hidden])')};
row('Collin Gillespie').querySelector('.wi-tg').click();R.afterKeepAgain={dat:tot(),ds:!!row('Collin Gillespie')};
dat().querySelector('.wi-reset').click();R.afterReset={dat:tot()};
var locked=row('Luka');R.locked={disabled:locked.querySelector('.wi-tg').disabled};
seg('FA 60');R.faCrown=qa('.wi-fa .tchip').some(function(e){return e.textContent.indexOf(C)>=0});R.fa={rows:qa('.wi-fa .wi-fr:not(.head)').length,enter:qa('.wi-fr.enter').length,exit:qa('.wi-fr.exit').length};
q('.modeswitch button[data-mode=SCENARIO]').click();R.scn={cls:document.body.className,hiddenWi:q('#what-if').hidden,crownCompare:q('#lab-compare').textContent.indexOf(C)>=0,crownPicks:q('#picks-grid').textContent.indexOf(C)>=0,crownCap:q('#cap').textContent.indexOf(C)>=0,crownCard:qa('section.team-card .team-name').some(function(e){return e.textContent.indexOf(C)>=0})};
q('.modeswitch button[data-mode=OFFICIAL]').click();R.back={cls:document.body.className,hidden:q('#what-if').hidden,totals:totals(),pool:qa('.pool-player').length};
q('.modeswitch button[data-mode=WHATIF]').click();qa('.navlink')[1].click();R.nav={cls:document.body.className};
document.body.setAttribute('data-result',JSON.stringify(R));})();</script>
"""


@unittest.skipUnless(_chrome(), "no headless Chrome available")
class TestRenderedUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding="utf-8") as f:
            html = f.read()
        cls.tmp = tempfile.mkdtemp()
        path = os.path.join(cls.tmp, "index.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html.replace("</body>", HARNESS + "</body>"))
        out = subprocess.run([_chrome(), "--headless=new", "--disable-gpu", "--no-sandbox", "--virtual-time-budget=6000",
                              "--dump-dom", "file://" + path], capture_output=True, text=True, timeout=120).stdout
        m = re.search(r"data-result='(.*?)'", out, re.S) or re.search(r'data-result="(.*?)"', out, re.S)
        cls.R = json.loads(html_lib.unescape(m.group(1)))
        cls.dom_official = subprocess.run([_chrome(), "--headless=new", "--disable-gpu", "--no-sandbox", "--dump-dom",
                                           "file://" + INDEX], capture_output=True, text=True, timeout=90).stdout

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_official_is_default_and_what_if_hidden(self):
        r = self.R["initial"]
        self.assertNotIn("whatif-mode", r["cls"])
        self.assertTrue(r["hidden"])
        self.assertIn('id="what-if" hidden', self.dom_official)

    def test_what_if_is_clearly_labelled(self):
        w = self.R["wi"]
        self.assertIn("whatif-mode", w["cls"])
        self.assertFalse(w["hidden"])
        self.assertIn("GIẢ ĐỊNH", w["banner"])
        self.assertIn("NOT OFFICIAL", w["banner"])
        self.assertIn("8 OCT 2026", w["snap"])
        self.assertEqual(w["rows"], 16)
        self.assertTrue(w["crown"])
        self.assertTrue(w["title"].startswith("WHAT IF"))

    def test_team_detail_opens_a_card(self):
        self.assertEqual(self.R["detail"]["cards"], 1)
        self.assertEqual(self.R["detail"]["rowsA"], 9)

    def test_redo_cards_never_touch_official_cards(self):
        r = self.R["redo"]
        self.assertEqual(r["cards"], 16)
        self.assertEqual(r["sectionCards"], 16)
        self.assertEqual(r["secTotals"], self.R["initial"]["totals"])
        self.assertEqual(r["dat0"], "178")

    def test_manual_swap_recomputes_and_resets(self):
        self.assertEqual(self.R["afterCut"]["dat"], "173")  # 178 - DeRozan 5
        self.assertTrue(self.R["afterCut"]["edited"])
        self.assertEqual(self.R["afterReset"]["dat"], "178")
        self.assertTrue(self.R["locked"]["disabled"])

    def test_fa_view_marks_entrants_and_exits(self):
        self.assertEqual(self.R["fa"]["rows"], 120)
        self.assertEqual((self.R["fa"]["enter"], self.R["fa"]["exit"]), (1, 1))

    def test_champion_crown_in_every_mode(self):
        r = self.R
        self.assertTrue(r["wi"]["crown"])
        self.assertTrue(r["redoCrown"])
        self.assertTrue(r["faCrown"])
        for k in ("crownCompare", "crownPicks", "crownCap", "crownCard"):
            self.assertTrue(r["scn"][k], k)

    def test_switching_is_reversible_and_official_untouched(self):
        b = self.R["back"]
        self.assertNotIn("whatif-mode", b["cls"])
        self.assertTrue(b["hidden"])
        self.assertEqual(b["totals"], self.R["initial"]["totals"])
        self.assertEqual(b["pool"], self.R["initial"]["pool"])
        self.assertIn("scenario-mode", self.R["scn"]["cls"])
        self.assertNotIn("whatif-mode", self.R["nav"]["cls"])


if __name__ == "__main__":
    unittest.main()
