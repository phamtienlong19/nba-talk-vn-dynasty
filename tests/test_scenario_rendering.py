import html as html_lib
import os
import re
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import league_state as ls  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _proposed import proposed_inputs  # noqa: E402
import refresh_team_cap_summary as cap_summary  # noqa: E402

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
INDEX = os.path.join(REPO_ROOT, "index.html")
SUP, BSY, DUNG, BZ = "franchise-12", "franchise-01", "franchise-06", "franchise-15"
ABC = ["TRADE-A", "TRADE-B", "TRADE-C"]


class TestCapStatusModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i = ls.load_inputs()

    def test_status_boundaries(self):
        i = self.i
        self.assertEqual(ls.cap_status(i, 130), "UNDER_FLOOR")
        self.assertEqual(ls.cap_status(i, 131), "AT_FLOOR")
        self.assertEqual(ls.cap_status(i, 132), "IN_RANGE")
        self.assertEqual(ls.cap_status(i, 173), "IN_RANGE")
        self.assertEqual(ls.cap_status(i, 174), "NEAR_CEILING")
        self.assertEqual(ls.cap_status(i, 177), "NEAR_CEILING")
        self.assertEqual(ls.cap_status(i, 178), "AT_CEILING")
        self.assertEqual(ls.cap_status(i, 179), "OVER_CEILING")

    def test_near_ceiling_matches_the_boards_existing_convention(self):
        self.assertEqual(ls.NEAR_CEILING_ROOM, cap_summary.NEAR_THRESHOLD)

    def test_scenario_teams_are_classified(self):
        pi = proposed_inputs(self.i)
        s = {k: ls.team_report(pi, ls.resolve(pi, ABC + ["TRADE-D"], "SCENARIO"), k) for k in (SUP, BSY, DUNG, BZ)}
        self.assertEqual((s[BSY]["cap"], s[BSY]["status"]), (178, "AT_CEILING"))
        self.assertEqual((s[SUP]["cap"], s[SUP]["status"]), (131, "AT_FLOOR"))
        self.assertEqual((s[DUNG]["cap"], s[DUNG]["status"]), (132, "IN_RANGE"))
        self.assertEqual((s[BZ]["cap"], s[BZ]["status"], s[BZ]["room"]), (151, "IN_RANGE", 27))

    def test_under_floor_fixture(self):
        rep = ls.team_report(self.i, ls.initial_state(self.i), "franchise-02")  # CrazyCat 101
        self.assertEqual((rep["status"], rep["toFloor"]), ("UNDER_FLOOR", 30))


class TestScenarioStateIsOneObject(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i = proposed_inputs()
        cls.base = ls.initial_state(cls.i)
        cls.state = ls.resolve(cls.i, ABC, "SCENARIO")
        cls.sup = ls.team_report(cls.i, cls.state, SUP, cls.base)

    def names(self):
        return [r["n"] for r in self.sup["roster"]]

    def test_sup_fam_scenario_roster(self):
        self.assertNotIn("Jalen Williams", self.names())
        self.assertNotIn("Reed Sheppard", self.names())
        self.assertIn("Julius Randle", self.names())
        self.assertEqual(self.sup["count"], 8)
        self.assertEqual(len(self.sup["roster"]), 8)

    def test_cap_count_and_roster_agree_with_each_other(self):
        self.assertEqual(self.sup["cap"], 131)
        self.assertEqual(self.sup["cap"], sum(r["c"] for r in self.sup["roster"]))
        self.assertEqual(self.sup["count"], len(self.sup["roster"]))
        self.assertEqual(self.sup["room"], 178 - 131)

    def test_scenario_picks(self):
        self.assertEqual(self.sup["picks"], ["1.03", "1.14", "2.12", "3.06"])
        self.assertNotIn("3.12", self.sup["picks"])

    def test_official_sup_fam_is_unchanged(self):
        off = ls.team_report(self.i, ls.resolve(self.i, ABC, "OFFICIAL"), SUP, self.base)
        self.assertEqual((off["cap"], off["count"]), (144, 9))
        self.assertEqual(off["picks"], ["1.14", "2.12", "3.12"])
        self.assertIn("Jalen Williams", [r["n"] for r in off["roster"]])
        self.assertEqual(off["inKeys"], [])

    def test_received_players_are_marked_in(self):
        self.assertEqual(self.sup["inKeys"], ["478.p.5318"])  # Randle only

    def test_official_view_is_exactly_the_keeper_baseline(self):
        for fid in self.i["franchises"]:
            a = ls.team_report(self.i, ls.resolve(self.i, [], "OFFICIAL"), fid, self.base)
            self.assertEqual(a["roster"], ls.team_roster(self.i, self.base, fid))
            self.assertEqual(a["cap"], a["baselineCap"])


def _chrome():
    for c in (os.environ.get("CHROME_BIN"), "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              shutil.which("google-chrome"), shutil.which("google-chrome-stable"), shutil.which("chromium"),
              shutil.which("chromium-browser")):
        if c and os.path.exists(c):
            return c
    return None


def _dump(url):
    out = subprocess.run([_chrome(), "--headless=new", "--disable-gpu", "--no-sandbox", "--dump-dom", url],
                         capture_output=True, text=True, timeout=90)
    return out.stdout


def _card(dom, short):
    for card in re.findall(r'<section class="team-card[^"]*".*?</section>', dom, re.S):
        if f'<span class="identity-tag">{short}</span>' in card:
            return card
    raise AssertionError(short)


def _read(card):
    names = [html_lib.unescape(re.sub(r'<span class="st-chip[^"]*"[^>]*>[^<]*</span>', "", n).split("<span")[0]).strip()
             for n in re.findall(r'<div class="pname">(.*?)</div>', card, re.S)]  # the left status chip is not part of the name
    cap = re.search(r'<div class="cap-total">(.*?)<span>/(\d+)</span>', card, re.S)
    return {"names": names, "cap": cap.group(1), "ceiling": cap.group(2),
            "gap": re.search(r'<div class="gap-big">(.*?)</div>', card).group(1),
            "picks": re.search(r'<span class="picks-tag">(.*?)</span>', card).group(1),
            "rows": len(re.findall(r'class="player-row', card))}


@unittest.skipUnless(_chrome(), "no headless Chrome available")
class TestRenderedCards(unittest.TestCase):
    """Default page = the CURRENT SEASON (verified roster snapshot + completed in-season trades), same derived-state path."""

    @classmethod
    def setUpClass(cls):
        cls.official = _dump("file://" + os.path.abspath(INDEX))
        with open(INDEX, encoding="utf-8") as f:
            cls.static = f.read()
        cls.i = ls.load_inputs()
        cls.state = ls.resolve(cls.i, (), "OFFICIAL")
        cls.base = ls.initial_state(cls.i)
        cls.shorts = {t["franchiseId"]: t["short"] for t in cls.i["freeze"]["teams"]}
        import season_state as ss
        cls.si = ss.load_season(cls.i)
        cls.cur = ss.season_state(cls.si)

    def test_default_view_renders_the_current_season_state_for_all_16_teams(self):
        for fid, short in self.shorts.items():
            rep = ls.team_report(self.si, self.cur, fid, self.state)
            c = _read(_card(self.official, short))
            self.assertEqual(sorted(c["names"]), sorted(r["n"] for r in rep["roster"]), short)
            self.assertEqual(c["rows"], rep["count"], short)
            self.assertEqual(float(c["cap"]), rep["cap"], short)
            self.assertEqual(c["picks"], " · ".join(rep["picks"]), short)

    def test_known_post_trade_rosters(self):
        sup = _read(_card(self.official, "sup fam"))
        self.assertNotIn("Jalen Williams", sup["names"])
        self.assertIn("Julius Randle", sup["names"])
        # completed Bsy <-> sup fam trade: sup fam 141 -> 144 (Castle $13 + Mitchell $0 in; Coward $10 + Beringer $0 out)
        self.assertEqual((sup["cap"], sup["rows"], sup["gap"]), ("144", 15, "34 ROOM"))   # + 3 IL pickups at $0 (Yahoo 2026-10-19)
        self.assertIn("Stephon Castle", sup["names"])
        self.assertNotIn("Cedric Coward", sup["names"])
        bsy = _read(_card(self.official, "Bsy"))
        self.assertEqual((bsy["cap"], bsy["rows"], bsy["gap"]), ("176", 13, "2 ROOM"))
        self.assertIn("Cedric Coward", bsy["names"])
        self.assertIn("Joan Beringer", bsy["names"])
        self.assertNotIn("Stephon Castle", bsy["names"])
        for n in ("Nikola Jokić", "Oso Ighodaro", "Victor Wembanyama"):   # completed Bsy <-> Thịnh
            self.assertIn(n, bsy["names"] if n != "Victor Wembanyama" else _read(_card(self.official, "Thịnh"))["names"])
        thinh = _read(_card(self.official, "Thịnh"))
        self.assertEqual((thinh["cap"], thinh["rows"], thinh["gap"]), ("176", 13, "2 ROOM"))
        self.assertIn("Jaylon Tyson", thinh["names"])
        self.assertNotIn("Nikola Jokić", thinh["names"])
        bz = _read(_card(self.official, "Bz"))
        self.assertIn("Derrick White", bz["names"])
        self.assertNotIn("Franz Wagner", bz["names"])
        self.assertEqual(sum(1 for n in bz["names"] if n == "Derrick White"), 1)
        melo = _read(_card(self.official, "Melo"))
        self.assertNotIn("Aaron Gordon", melo["names"])   # commissioner clarification (TRADE-D-AMEND): Gordon stays with LC
        self.assertIn("Aaron Gordon", _read(_card(self.official, "LC"))["names"])
        self.assertEqual(melo["picks"], "2.03 · 2.15 · 3.04")  # Melo holds LC's 3.04

    def test_untraded_teams_keep_their_keepers_and_add_only_draftees(self):
        drafted = {c["name"] for c in ls.draft_summary(self.i, self.state)["completed"]}
        for short in ("DHA", "Đạt", "TuLy", "TT"):   # no pre-draft trade, no in-season trade, no Yahoo add/drop
            now = _read(_card(self.official, short))["names"]
            before = _read(_card(self.static, short))["names"]
            self.assertEqual(sorted(n for n in now if n not in drafted), sorted(before), short)
            self.assertTrue(set(now) - set(before) <= drafted, short)

    def test_cards_show_in_season_movement_from_the_post_draft_roster(self):
        card = _card(self.official, "Bz")
        self.assertIn("vs draft", card)                     # delta against the post-draft roster
        self.assertIn("KEEPER-FREEZE CUTS", card)           # kept in the DOM, hidden in-season
        cc = re.sub(r"<[^>]+>", "", _card(self.official, "CrazyCat"))
        self.assertIn("INZion Williamson", cc)               # the completed in-season trade, applied once
        self.assertIn("OUTMorez Johnson Jr.R2.07 CrazyCat", cc)  # rookie chip + where he was drafted
        self.assertNotIn("Morez Johnson Jr.", _read(_card(self.official, "CrazyCat"))["names"])
        self.assertIn("Morez Johnson Jr.", _read(_card(self.official, "HCMC"))["names"])
        self.assertIn(">DRAFTED<", _card(self.official, "Quân"))  # every team has drafted: movement lists the draftees

    def test_in_season_acquisitions_are_styled_apart_from_own_draftees(self):
        def row(short, name):
            card = _card(self.official, short)
            return next(r for r in re.findall(r'<div class="player-row[^"]*".*?</div></div>|<div class="player-row[^"]*"[^>]*>.*?<div class="cap">.*?</div>', card, re.S)
                        if f">{name}<" in r or f">{name} <" in r or f"{name}<span" in r)
        morez = row("HCMC", "Morez Johnson Jr.")        # rookie drafted by CrazyCat, traded to HCMC
        self.assertRegex(morez, r'class="player-row[^"]*\brow-trade\b')
        self.assertIn("rookie-row", morez)              # keeps the purple rookie name
        self.assertIn('class="in-tag dr-other rk"', morez)  # outlined draft slot, not the filled own-draft chip
        self.assertIn(">2.07<", morez)                  # where he was drafted
        self.assertIn('class="tr-tag"', morez)
        zion = row("CrazyCat", "Zion Williamson")
        self.assertIn("row-trade", zion)
        self.assertIn('class="tr-tag"', zion)
        own = row("LC", "AJ Dybantsa")                  # LC's own 1.02 pick
        self.assertIn('class="in-tag rk"', own)
        self.assertNotIn("row-trade", own)
        self.assertNotIn("tr-tag", own)

    def test_trade_lab_separates_proposals_from_completed_trades(self):
        lab = re.search(r'id="lab-trades">(.*?)<div id="lab-window"', self.official, re.S).group(1)
        self.assertEqual(lab.count('class="tcard prop'), 0)           # nothing is pending any more
        self.assertEqual(lab.count('<input type="checkbox">'), 0)
        text = re.sub(r"<[^>]+>", " ", lab)
        self.assertIn("No proposals", text)
        for name in ("Stephon Castle", "Victor Wembanyama"):
            self.assertNotIn(name, text)                               # completed trades are not proposals
        self.assertNotIn("DIRECTION CHECK", lab)                       # internal notes are never published
        self.assertNotIn("AMENDMENT", lab)                             # withdrawn: not actionable
        done = re.search(r'id="lab-done">(.*?)</details>', self.official, re.S).group(1)
        self.assertEqual(done.count('class="tcard done'), 3)
        self.assertIn("Morez Johnson Jr.", done)
        self.assertIn("Stephon Castle", done)
        self.assertIn("Cedric Coward", done)
        self.assertIn("Nikola Jokić", done)
        done_text = re.sub(r"<[^>]+>", " ", done)
        self.assertRegex(done_text, r"178\s*→\s*175")                # Bsy ↔ sup fam
        self.assertRegex(done_text, r"175\s*→\s*176")                # Bsy ↔ Thịnh, applied after it
        self.assertIn("✓ DONE", done)
        self.assertNotIn("WITHDRAWN", done)                            # withdrawn entries are not shown
        hist = re.sub(r"<[^>]+>", " ", done.split("Pre-draft")[1])
        self.assertIn("Alperen Şengün", hist)                          # LC ↔ Melo shown as one aggregated trade:
        self.assertNotIn("Aaron Gordon", hist)                         # Gordon moved and moved back nets out
        self.assertRegex(hist, r"Alperen Şengün\s+3\.\s*04")

    def test_movement_credits_the_drafting_team(self):
        mv = re.search(r'<div class="mv">(.*?)</details>', _card(self.official, "Bsy"), re.S).group(1)
        drafted = re.search(r'<div class="mv-dr">(.*?)</div>', mv, re.S).group(1)
        self.assertNotIn("Joan Beringer", drafted)          # drafted by sup fam at 3.06, not by Bsy
        self.assertIn("Aaron Nesmith", drafted)             # Bsy's own 2.01 pick
        in_line = re.search(r'<span class="mv-l">IN</span>(.*?)</div>', mv, re.S).group(1)
        self.assertIn("Cedric Coward", in_line)
        self.assertIn('<span class="mv-pl"><span>Joan Beringer</span>', in_line)   # veteran draftee: slot + drafter, no purple
        self.assertRegex(in_line, r'Joan Beringer</span>.*?3.*?06.*?sup fam')
        sup = re.search(r'<div class="mv">(.*?)</details>', _card(self.official, "sup fam"), re.S).group(1)
        self.assertRegex(sup, r'<span class="mv-l">OUT</span>.*?Joan Beringer')

    def test_traded_rookie_keeps_rookie_styling_in_summaries(self):
        mv = re.search(r'<div class="mv">(.*?)</details>', _card(self.official, "HCMC"), re.S).group(1)
        morez = re.search(r'<span class="mv-pl rk"><span>Morez Johnson Jr\.</span>(.*?)</span></span>', mv, re.S)
        self.assertIsNotNone(morez, "Morez must keep the purple rookie label in HCMC's movement summary")
        self.assertIn('class="src src-r"', morez.group(1))
        self.assertIn("CrazyCat", morez.group(1))
        cc = re.search(r'<div class="mv">(.*?)</details>', _card(self.official, "CrazyCat"), re.S).group(1)
        self.assertRegex(cc, r'<span class="mv-l">OUT</span><span class="mv-items"><span class="mv-pl rk"><span>Morez Johnson Jr\.</span>')

    def test_pickups_are_not_shown_as_trades_and_il_is_tagged(self):
        def row(short, name):
            return next(r for r in re.findall(r'<div class="player-row[^"]*".*?<div class="cap">.*?</div>', _card(self.official, short), re.S)
                        if f">{name}<" in r)
        miller = row("Bsy", "Jordan Miller")
        self.assertNotIn("tr-tag", miller)                                   # free-agent pickup: no ⇄
        self.assertNotIn("row-trade", miller)
        self.assertIn('<div class="pname"><span class="st-chip il" title="Injured list">IL</span>Jordan Miller', miller)  # chip on the left
        self.assertIn("tr-tag", row("Bsy", "Nikola Jokić"))                  # trade acquisition keeps ⇄
        mv = re.sub(r"<[^>]+>", " ", re.search(r'<div class="mv">(.*?)</details>', _card(self.official, "Bsy"), re.S).group(1))
        self.assertRegex(mv, r"ADDED\s.*Jordan Miller")
        self.assertRegex(mv, r"DROPPED\s.*Zaccharie Risacher")
        q = row("sup fam", "Jayden Quaintance")                              # unlisted salary: $0 by league rule
        self.assertIn('<div class="pos">PF</div>', q)
        self.assertIn('<div class="nba">SAS</div>', q)
        self.assertIn('class="st-chip il"', q)

    def test_injured_list_is_its_own_group_at_the_foot_of_the_roster(self):
        for short in ("Bsy", "sup fam", "CrazyCat", "LC", "Maxfixe", "DonTrick"):
            card = _card(self.official, short)
            players = re.search(r'<div class="players">(.*)', card, re.S).group(1)
            head = players.find('class="il-head"')
            self.assertGreater(head, 0, short)
            before, after = players[:head], players[head:]
            self.assertNotIn("il-row", before, short)                        # healthy players first
            self.assertEqual(after.count('class="player-row'), after.count("il-row"), short)  # only IL rows below
        cc = _card(self.official, "CrazyCat")                                # Nurkić ($4) is on IL and inside the nine
        self.assertRegex(cc, r'class="il-head">.*?Injured list.*?class="il-c"[^>]*>4 counted<')
        self.assertIn('<div class="nc-div">not counted</div>', cc)           # no "top 9" divider when IL counts
        self.assertRegex(re.sub(r"<[^>]+>", " ", cc), r"healthy\s+141")     # 145 counted, 4 of it on IL
        bsy = _card(self.official, "Bsy")                                    # Miller ($0) is outside the nine
        self.assertIn("beyond top 9 · not counted", re.sub(r"<[^>]+>", "", bsy))
        self.assertNotIn("healthy", re.sub(r"<[^>]+>", " ", bsy.split('class="players"')[0]))
        self.assertNotIn('class="il-c"', bsy)

    def test_full_team_names_and_no_health_badges(self):
        bsy = _card(self.official, "Bsy")
        self.assertIn('<div class="team-name">Hai | Bulls Dynasty</div>', bsy)    # one style, no lighter manager part
        self.assertNotIn("tn-m", self.official)
        self.assertIn('Long con dynasty</div>', _card(self.official, "LC"))
        for badge in ("health-badge", ">REC<", ">INJ<", "health-rec", "health-inj"):
            self.assertNotIn(badge, self.official.split("<body", 1)[1].split("<script", 1)[0], badge)

    def test_internal_notes_are_not_published(self):
        data = re.search(r'id="league-data">(.*?)</script>', self.static, re.S).group(1)
        for internal in ("directionCheck", "DISCREPANCY", "ownership-consistent", "Direction verified",
                         '"note":', '"flag":', "confirmed in chat"):
            self.assertNotIn(internal, data, internal)

    def test_pass_through_lists_players_by_name_and_picks_with_pick_prefix(self):
        card = re.sub(r"<[^>]+>", "", _card(self.official, "Bz"))  # digits are wrapped in <span class="num">
        self.assertNotIn("Pick Franz Wagner", card)
        self.assertRegex(self.static, r'p\.asset\.t==="p"\?p\.asset\.n:"Pick "\+p\.asset\.n')  # players by name, picks prefixed
        self.assertNotRegex(self.static, r'"Pick "\+p\.asset\.n\+" \("')  # old unconditional "Pick " prefix is gone

    def test_public_ui_shows_the_verified_roster_snapshot(self):
        m = re.search(r'id="lab-keeper-status"[^>]*>(.*?)</span><span class="meta-pill cap-rule"', self.official)
        self.assertEqual(re.sub(r"<[^>]+>", "", m.group(1)), "✓ ROSTERS OCT 19")
        rules = re.findall(r'<span class="meta-pill cap-rule"[^>]*>(.*?)</span><', self.official)
        self.assertEqual(len(rules), 4)
        self.assertTrue(all(re.sub(r"<[^>]+>", "", r) == "TOP 9 $ COUNT · IL ✓" for r in rules), rules)
        self.assertNotIn("NOT FROZEN", self.official.split("<body", 1)[1].split('<script id="league-app">')[0])

    def test_pick_pill_never_clips(self):
        css = re.search(r"\.picks-tag\{background:#edf2f9[^}]*\}", self.static).group(0)
        for bad in ("nowrap", "ellipsis", "overflow:hidden"):
            self.assertNotIn(bad, css)


if __name__ == "__main__":
    unittest.main()
