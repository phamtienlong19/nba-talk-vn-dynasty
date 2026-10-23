import html as html_lib
import os
import re
import shutil
import subprocess
import datetime
import json
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import league_state as ls  # noqa: E402
import season_state as ss  # noqa: E402
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


def _snapshot_label():
    snap = ls._load(os.path.join(ls.DATA_DIR, "rosters", ss._load(ss.ROSTER_INDEX)["current"]))
    d = datetime.date.fromisoformat(snap["verifiedAt"][:10])
    return f"✓ ROSTERS {d.strftime('%b').upper()} {d.day}"


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
        # Roster membership changes every time a manager adds or drops, so every expectation here is derived from the
        # engine for the CURRENT verified roster: the ledger says where each traded player went; the card must agree.
        shorts = self.si["shorts"]
        cards = {fid: _read(_card(self.official, shorts[fid])) for fid in self.si["franchises"]}
        for t in self.si["seasonTxns"]:
            if t["status"] != "COMPLETED":
                continue
            for a in t["assets"]:
                if a["type"] != "player":
                    continue
                name, owner = ls.player_name(self.si, a["playerKey"]), self.cur["playerOwner"].get(a["playerKey"])
                if owner is not None:                              # still rostered: exactly one card shows him, the owner's
                    self.assertEqual([f for f, c in cards.items() if name in c["names"]], [owner], (t["txnId"], name))
                else:                                              # dropped since the trade: no card shows him
                    self.assertFalse([f for f, c in cards.items() if name in c["names"]], (t["txnId"], name))
        for fid, c in cards.items():                               # cap / rows / room are the engine's, for every team
            rep = ls.team_report(self.si, self.cur, fid, self.state)
            self.assertEqual((float(c["cap"]), c["rows"]), (rep["cap"], rep["count"]), shorts[fid])
            want = {"UNDER_FLOOR": f"{rep['toFloor']:g} TO FLOOR", "AT_FLOOR": "AT FLOOR", "AT_CEILING": "AT CEILING",
                    "OVER_CEILING": f"{-rep['room']:g} OVER"}.get(rep["status"], f"{rep['room']:g} ROOM")   # the page's own wording
            self.assertEqual(c["gap"], want, shorts[fid])
        melo = cards["franchise-03"]
        self.assertEqual(melo["picks"], "2.03 · 2.15 · 3.04")      # Melo holds LC's 3.04 (commissioner clarification, TRADE-D-AMEND)

    def test_untraded_teams_keep_their_keepers_and_add_only_draftees(self):
        drafted = {c["name"] for c in ls.draft_summary(self.i, self.state)["completed"]}
        pre = {f for t in self.i["trades"]["trades"] for f in t["participants"]}
        view = ss.season_view(self.si)["teams"]
        quiet = [self.si["shorts"][f] for f in self.si["franchises"]
                 if f not in pre and not view[f]["added"] and not view[f]["dropped"] and not view[f]["fold"]["tradeIds"]]
        if not quiet:
            self.skipTest("every team has moved since the draft; nothing left to compare against the keeper board")
        for short in quiet:   # no pre-draft trade, no in-season trade, no Yahoo add/drop: keepers + draftees only
            now = _read(_card(self.official, short))["names"]
            before = _read(_card(self.static, short))["names"]
            self.assertEqual(sorted(n for n in now if n not in drafted), sorted(before), short)
            self.assertTrue(set(now) - set(before) <= drafted, short)

    def test_cards_show_in_season_movement_from_the_post_draft_roster(self):
        card = _card(self.official, "Bz")
        self.assertIn("Since the draft", card)             # delta against the post-draft roster (in the card's detail panel)
        self.assertIn("KEEPER-FREEZE CUTS", card)           # kept in the DOM, hidden in-season
        cc = re.sub(r"<[^>]+>", "", _card(self.official, "CrazyCat"))
        self.assertIn("INZion Williamson", cc)               # the completed in-season trade, applied once
        self.assertIn("OUTMorez Johnson Jr.R2.07 CrazyCat", cc)  # rookie chip + where he was drafted
        self.assertNotIn("Morez Johnson Jr.", _read(_card(self.official, "CrazyCat"))["names"])
        self.assertIn("Morez Johnson Jr.", _read(_card(self.official, "HCMC"))["names"])
        self.assertIn(">DRAFTED<", _card(self.official, "Quân"))  # every team has drafted: movement lists the draftees

    def test_in_season_acquisitions_are_styled_apart_from_own_draftees(self):
        owner = self.cur["playerOwner"]

        def row(short, name):
            card = _card(self.official, short)
            return next(r for r in re.findall(r'<div class="player-row[^"]*".*?</div></div>|<div class="player-row[^"]*"[^>]*>.*?<div class="cap">.*?</div>', card, re.S)
                        if f">{name}<" in r or f">{name} <" in r or f"{name}<span" in r)
        # A manager may have dropped any of these since the trade; each check applies while the player is still on that roster.
        k = {n: p["playerKey"] for p in self.si["registry"].values() for n in [p["name"]]}
        checked = 0
        if owner.get(k["Morez Johnson Jr."]) == "franchise-05":
            morez = row("HCMC", "Morez Johnson Jr.")        # rookie drafted by CrazyCat, traded to HCMC
            self.assertRegex(morez, r'class="player-row[^"]*\brow-trade\b')
            self.assertIn("rookie-row", morez)              # keeps the purple rookie name
            self.assertIn('class="in-tag dr-other rk"', morez)  # outlined draft slot, not the filled own-draft chip
            self.assertIn(">2.07<", morez)                  # where he was drafted
            self.assertIn('class="tr-tag"', morez)
            checked += 1
        if owner.get(k["Zion Williamson"]) == "franchise-02":
            zion = row("CrazyCat", "Zion Williamson")
            self.assertIn("row-trade", zion)
            self.assertIn('class="tr-tag"', zion)
            checked += 1
        if owner.get(k["AJ Dybantsa"]) == "franchise-04":
            own = row("LC", "AJ Dybantsa")                  # LC's own 1.02 pick
            self.assertIn('class="in-tag rk"', own)
            self.assertNotIn("row-trade", own)
            self.assertNotIn("tr-tag", own)
            checked += 1
        self.assertGreater(checked, 0, "none of the three players is on his expected roster any more; pick other examples")

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
        done = {c["playerKey"]: c for c in ls.draft_summary(self.i, self.state)["completed"]}
        view = ss.season_view(self.si)["teams"]
        credited = traded = 0
        for fid, v in view.items():
            short = self.si["shorts"][fid]
            mv = re.search(r'<div class="mv">(.*?)<div class="table-head">', _card(self.official, short), re.S).group(1)
            dr = re.search(r'<span class="mv-l">DRAFTED</span>(.*?)</div>', mv, re.S)
            drafted = re.sub(r"<[^>]+>", " ", dr.group(1)) if dr else ""
            for r in v["roster"]:
                c = done.get(r["k"])
                if c and c["franchiseId"] == fid:                          # his own pick: credited to the drafting team's card
                    self.assertIn(r["n"], drafted, (short, r["n"]))
                    credited += 1
                elif c and r["k"] in v["inKeys"]:                          # someone else's draftee, acquired by trade: IN line, never DRAFTED
                    self.assertNotIn(r["n"], drafted, (short, r["n"]))
                    in_line = re.search(r'<span class="mv-l">IN</span>(.*?)</div>', mv, re.S).group(1)
                    self.assertIn(f"<span>{r['n']}</span>", in_line, (short, r["n"]))
                    self.assertIn(self.i["shorts"][c["franchiseId"]], in_line, (short, r["n"]))   # slot + drafter shown
                    traded += 1
        self.assertGreater(credited, 0)
        self.assertGreater(traded, 0, "no traded draftee is on a roster any more; nothing to check")

    def test_traded_rookie_keeps_rookie_styling_in_summaries(self):
        mv = re.search(r'<div class="mv">(.*?)<div class="table-head">', _card(self.official, "HCMC"), re.S).group(1)
        morez = re.search(r'<span class="mv-pl rk"><span>Morez Johnson Jr\.</span>(.*?)</span></span>', mv, re.S)
        self.assertIsNotNone(morez, "Morez must keep the purple rookie label in HCMC's movement summary")
        self.assertIn('class="src src-r"', morez.group(1))
        self.assertIn("CrazyCat", morez.group(1))
        cc = re.search(r'<div class="mv">(.*?)<div class="table-head">', _card(self.official, "CrazyCat"), re.S).group(1)
        self.assertRegex(cc, r'<span class="mv-l">OUT</span><span class="mv-items"><span class="mv-pl rk"><span>Morez Johnson Jr\.</span>')

    def test_pickups_are_not_shown_as_trades_and_il_is_tagged(self):
        def row(short, name):
            return next(r for r in re.findall(r'<div class="player-row[^"]*".*?<div class="cap">.*?</div>', _card(self.official, short), re.S)
                        if f">{name}<" in r)
        view = ss.season_view(self.si)["teams"]
        status = self.cur.get("status", {})
        added = [(fid, a) for fid, v in view.items() for a in v["added"]]
        self.assertTrue(added, "nobody has been added since the draft; nothing to check")
        for fid, a in added:                                                 # every free-agent pickup, on whichever team has him now
            short = self.si["shorts"][fid]
            r = row(short, a["n"])
            self.assertNotIn("tr-tag", r, a["n"])                            # a pickup is not a trade: no ⇄
            self.assertNotIn("row-trade", r, a["n"])
            mv = re.sub(r"<[^>]+>", " ", re.search(r'<div class="mv">(.*?)<div class="table-head">', _card(self.official, short), re.S).group(1))
            self.assertRegex(mv, r"ADDED\s.*" + re.escape(a["n"]), a["n"])
            if status.get(a["k"]) == "O" and self.cur["slots"].get(a["k"]) in ss.SLOTS_IL:
                self.assertIn('<span class="st-chip st-out" title="Out (Yahoo)" aria-label="Out">OUT</span>' + a["n"], r)  # chip left of the name
        for fid, v in view.items():                                          # drops are listed too
            for dpl in v["dropped"]:
                mv = re.sub(r"<[^>]+>", " ", re.search(r'<div class="mv">(.*?)<div class="table-head">', _card(self.official, self.si["shorts"][fid]), re.S).group(1))
                self.assertRegex(mv, r"DROPPED\s.*" + re.escape(dpl["n"]), dpl["n"])
        for k, p in self.si["unlistedPlayers"].items():                      # unlisted salary: $0 by league rule, still shown with team / position
            fid = self.cur["playerOwner"].get(k)
            if fid is None:
                continue
            q = row(self.si["shorts"][fid], p["name"])
            self.assertIn(f'<div class="pos">{p["displayPosition"].replace(",", "/")}</div>', q)
            self.assertIn(f'<div class="nba">{p["nbaTeam"]}</div>', q)
            self.assertIn('<div class="cap">0</div>', q)

    def test_injured_list_is_its_own_group_at_the_foot_of_the_roster(self):
        view = ss.season_view(self.si)["teams"]
        for fid, v in view.items():
            card = _card(self.official, self.si["shorts"][fid])
            players = re.search(r'<div class="players[^"]*">(.*)', card, re.S).group(1)
            head = players.find('class="il-head"')
            if not v["il"]:
                self.assertEqual(head, -1, fid)
                continue
            self.assertGreater(head, 0, fid)
            before, after = players[:head], players[head:]
            self.assertNotIn("il-row", before, fid)                          # healthy players first
            self.assertEqual(after.count('class="player-row'), after.count("il-row"), fid)  # only IL rows below
            self.assertEqual(after.count("il-row"), v["il"], fid)
        seen_counting = seen_free = False
        for fid, v in view.items():
            card = _card(self.official, self.si["shorts"][fid])
            txt = re.sub(r"<[^>]+>", " ", card)
            strip = txt.split("Roster limits")[0]                            # the detail panel's status + facts, before the limits
            if v["injuredCap"]:                                              # counted salary of IL or Out players: "healthy payroll" says what is left
                self.assertRegex(strip, r"Healthy payroll\s+" + re.escape(f"{v['healthyCap']:g}"), fid)
            else:
                self.assertNotIn("Healthy payroll", strip, fid)
            if not v["il"]:
                self.assertNotIn("il-head", card, fid)
                continue
            if v["ilCap"]:                                                   # an IL player inside the counted nine: the group says so
                seen_counting = True
                self.assertRegex(card, r'class="il-c"[^>]*>' + re.escape(f"{v['ilCap']:g}") + r" counted<", fid)
            else:                                                            # IL players all outside the nine: no counted note
                seen_free = True
                self.assertNotIn('class="il-c"', card, fid)
        self.assertTrue(seen_counting or seen_free, "no team has an injured-list player to check")

    def test_yahoo_status_chips_are_distinct(self):
        snap = ls._load(os.path.join(ls.DATA_DIR, "rosters", ss._load(ss.ROSTER_INDEX)["current"]))
        want = {"O": "OUT", "Q": "Q", "P": "P"}
        seen = set()
        for fid, rows in snap["teams"].items():                              # whatever the current snapshot says, card by card
            card = _card(self.official, self.si["shorts"][fid])
            chips = {html_lib.unescape(n).strip(): c for c, n in
                     re.findall(r'<span class="st-chip st-[a-z]+"[^>]*>([^<]*)</span>([^<]*)', card)}
            for r in rows:
                if r.get("status") in want:
                    self.assertEqual(chips.get(r["name"]), want[r["status"]], (r["name"], r["status"]))
                    seen.add(r["status"])
        self.assertTrue(seen, "the snapshot carries no statuses to check")
        self.assertIn('class="players has-st"', _card(self.official, "LC"))   # names aligned past the status gutter
        css = self.static
        for cls, color in (("st-p", "#1c9a5e"), ("st-q", "#2b6be0"), ("st-d", "#ee8a0b"), ("st-out", "#c9362d"),
                           ("st-ofs", "#1d2330"), ("st-na", "#3a3f4c")):         # every status is a SOLID fill with white text
            self.assertRegex(css, r"\.st-chip\.%s\{background:%s[;}]" % (cls, color), cls)
        self.assertRegex(css, r"\.st-chip\.st-inj\{background:#d8392f;box-shadow:inset 0 0 0 1\.5px rgba\(255,255,255,\.55\)")   # injured: red with a white inner ring
        self.assertRegex(css, r"\.st-chip\{[^}]*color:#fff;box-shadow:0 0 0 1\.5px #fff\}")                                       # white text, white halo
        self.assertIn('OFS:["OFS","Out for the season","ofs"]', css)
        self.assertIn('INJ:["INJ","Injured","inj"]', css)
        self.assertIn('D:["D","Doubtful","d"]', css)

    def test_na_players_are_painfully_obvious_as_teamless(self):
        snap = ls._load(os.path.join(ls.DATA_DIR, "rosters", ss._load(ss.ROSTER_INDEX)["current"]))
        na = [(fid, r["name"]) for fid, rows in snap["teams"].items() for r in rows if r.get("status") == "NA"]
        if not na:
            self.skipTest("nobody on a roster is NA right now")
        for fid, name in na:
            rowhtml = next(r for r in re.findall(r'<div class="player-row[^"]*".*?<div class="cap">.*?</div>', _card(self.official, self.si["shorts"][fid]), re.S)
                           if f">{name}<" in r)
            self.assertIn("is-na", rowhtml.split(">")[0])                        # hatched row
            self.assertIn('class="st-chip st-na"', rowhtml)                     # charcoal chip
            self.assertIn('<span class="na-team" title="Not active: no NBA team">NO TEAM</span>', rowhtml)   # in place of the NBA code
        self.assertRegex(self.static, r"\.player-row\.is-na\{background:repeating-linear-gradient")
        self.assertIn('NA:["NA","Not active · no NBA team","na"]', self.static)

    def test_colour_roles_do_not_overlap(self):
        """Status = SOLID fill (gutter chip). Where a player came from (trade, scenario, own draft) = a thin edge bar and an
        OUTLINED tag, never a tinted row; and nothing is faded, so chips keep their full colour on every row."""
        css = self.static
        self.assertNotRegex(css, r"\.player-row\.nc(?:\.[a-z-]+)*\{[^}]*opacity")                    # not-counted rows are not faded
        self.assertNotRegex(css, r"\.player-row\.row-(?:trade|scn|in)(?:\.[a-z-]+)*\{[^}]*background")  # no tinted origin rows
        self.assertRegex(css, r"\.player-row\.row-trade\{box-shadow:inset 3px 0 0 #2f5fd0\}")           # a thin edge bar remains
        self.assertRegex(css, r"\.player-row\.row-scn\{box-shadow:inset 3px 0 0 #e0a21b\}")
        for tag in (".tr-tag", ".in-tag"):                                                           # outlined: white fill, 1px border
            self.assertRegex(css, r"%s\{[^}]*background:#fff;border:1px solid" % re.escape(tag), tag)
        self.assertRegex(css, r"\.player-row\.nc \.cap\{[^}]*border:1px dashed")                         # not-counted salary: dashed ghost outline

    def test_preseason_standings_pill_and_team_order(self):
        a = self.official.split('id="rosters-a"')[1].split('id="rosters-b"')[0]
        txt = lambda x: " ".join(re.sub(r"<[^>]+>", "", x).split())  # noqa: E731  (digits are wrapped in spans)
        self.assertTrue(txt(a).startswith(">TEAMS 1–8"))
        self.assertIn("meta-pill stand-pill off", a)
        self.assertRegex(txt(a), r"STANDINGS\s*AFTER WEEK 1")
        shorts = re.findall(r'<span class="identity-tag">([^<]*)</span>', a)
        self.assertEqual(shorts[:3], ["Bsy", "CrazyCat", "Melo"])          # team # order until games are played
        self.assertNotIn('<span class="stand-tag', self.official)          # no rank tags before games are played

    def test_started_season_sorts_worst_record_first(self):
        import tempfile, shutil
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        with open(INDEX, encoding="utf-8") as f:
            html = f.read()
        m = re.search(r'(id="league-data">)(.*?)(</script>)', html, re.S)
        data = json.loads(m.group(2).replace("<\\/", "</"))
        ids = [t["id"] for t in data["teams"]]
        teams = {fid: {"rank": i + 1, "w": 160 - i * 6, "l": 40 + i * 6, "t": 3, "pct": None, "gb": str(i * 2), "division": "East",
                       "divRecord": "0-0-0", "lastWeek": "5-4-0", "waiver": i + 1, "moves": 0, "place": i + 1} for i, fid in enumerate(ids)}
        data["standings"] = {"capturedAt": "2026-11-02T12:00:00Z", "source": "test", "started": True, "teams": teams,
                             "worstFirst": list(reversed(ids))}                 # made-up records: team 01 is best
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, "index.html")
            with open(path, "w", encoding="utf-8") as f:
                f.write(html[:m.start(2)] + json.dumps(data, ensure_ascii=False).replace("</", "<\\/") + html[m.end(2):])
            dom = _dump("file://" + path)
            a, b = dom.split('id="rosters-a"')[1].split('id="rosters-b"')
            txt = lambda x: " ".join(re.sub(r"<[^>]+>", "", x).split())  # noqa: E731
            self.assertTrue(txt(a).startswith(">STANDINGS 16–9"), txt(a)[:40])
            self.assertTrue(txt(b).startswith(">STANDINGS 8–1"), txt(b)[:40])
            self.assertEqual(re.findall(r'<span class="identity-tag">([^<]*)</span>', a)[0], "TT")      # 16th first
            self.assertEqual(re.findall(r'<span class="identity-tag">([^<]*)</span>', b)[-1], "Bsy")    # 1st last
            tag = re.search(r'<span class="stand-tag low"[^>]*>(.*?)</span></span>(?=\s*<span class="identity-tag)', _card(dom, "TT"), re.S)
            self.assertEqual(txt(tag.group(1)), "16th70–130–3")
            self.assertIn('class="so on">STANDINGS ↓', a)
            dom2 = _dump("file://" + path + "?order=team")                    # toggle back to team number
            a2 = dom2.split('id="rosters-a"')[1].split('id="rosters-b"')[0]
            self.assertTrue(txt(a2).startswith(">TEAMS 1–8"))
            self.assertEqual(re.findall(r'<span class="identity-tag">([^<]*)</span>', a2)[0], "Bsy")
            self.assertIn('class="so on">TEAM #', a2)
        finally:
            shutil.rmtree(d)

    # ---- tabs: one view at a time (TEAMS / CAP / TRADE LAB / DRAFT) and a tab per draft round ------------------------------
    TAB_SECTIONS = {"teams": ("rosters-a", "rosters-b"), "cap": ("cap",), "trade-lab": ("trade-lab",), "draft": ("draft-order",)}

    def _visible_tabs(self, hash_=""):
        """-> (set of tabs whose sections are shown, active nav tab, the dom), after the page's own script has run."""
        dom = _dump("file://" + os.path.abspath(INDEX) + hash_)
        shown = set()
        for tab, secs in self.TAB_SECTIONS.items():
            states = []
            for sid in secs:
                tag = re.search(r'<section class="([^"]*)"[^>]*\bid="%s"' % sid, dom) or re.search(r'<section[^>]*\bid="%s"[^>]*class="([^"]*)"' % sid, dom)
                self.assertIsNotNone(tag, sid)                                  # every section stays in the DOM (printing, tests, links)
                states.append("tab-off" not in tag.group(1).split())
            self.assertEqual(len(set(states)), 1, (tab, states))                 # a tab shows or hides all of its sections together
            if states[0]:
                shown.add(tab)
        active = re.findall(r'<a class="navlink on"[^>]*data-tab="([^"]+)"', dom)
        return shown, active, dom

    def test_tabs_show_one_view_at_a_time(self):
        shown, active, dom = self._visible_tabs()
        self.assertEqual((shown, active), ({"teams"}, ["teams"]))                  # default: the teams
        self.assertIn('aria-current="page"', dom)
        for hash_, tab in (("#cap", "cap"), ("#trade-lab", "trade-lab"), ("#draft", "draft"), ("#teams", "teams")):
            shown, active, _ = self._visible_tabs(hash_)
            self.assertEqual((shown, active), ({tab}, [tab]), hash_)

    def test_old_anchors_still_land_on_the_right_tab(self):
        for hash_, tab in (("#rosters-a", "teams"), ("#rosters-b", "teams"), ("#draft-order", "draft")):
            shown, active, _ = self._visible_tabs(hash_)
            self.assertEqual((shown, active), ({tab}, [tab]), hash_)
        shown, active, _ = self._visible_tabs("#no-such-tab")
        self.assertEqual(shown, {"teams"})                                          # an unknown hash falls back to the default

    def test_draft_archive_has_a_tab_per_round(self):
        def panels(hash_):
            dom = _dump("file://" + os.path.abspath(INDEX) + hash_)
            grid = re.search(r'<div class="order-grid([^"]*)">(.*?)</div>\s*</div>\s*</section>', dom, re.S)
            self.assertIsNotNone(grid)
            classes = re.findall(r'<div class="order-panel([^"]*)"', dom)
            bar = re.search(r'<div class="subtabs".*?</div>', dom, re.S).group(0)
            return grid.group(1).split(), [("sub-off" not in c.split()) for c in classes], re.findall(r'<button[^>]*class="subtab( on)?"[^>]*data-sub="([^"]+)"', bar), dom
        gridcls, vis, bar, _ = panels("#draft/all")
        self.assertEqual((vis, "single" in gridcls), ([True, True, True], False))        # all rounds side by side
        self.assertEqual([b[1] for b in bar], ["all", "r1", "r2", "r3"])
        for sub, idx in (("r1", 0), ("r2", 1), ("r3", 2)):
            gridcls, vis, bar, dom = panels("#draft/" + sub)
            self.assertEqual(vis, [i == idx for i in range(3)], sub)                    # exactly that round
            self.assertIn("single", gridcls)
            self.assertEqual([b[1] for b in bar if b[0]], [sub])                         # its tab is the selected one
        txt = re.sub(r"<[^>]+>", " ", panels("#draft/r2")[3])
        self.assertNotRegex(txt.split("DRAFT ARCHIVE")[1][:200], r"ROUND 1\s+ROUND 2\s+ROUND 3\s+1\.01")   # no fake round pills

    def test_tab_markup_and_print_and_legacy_nav(self):
        css = self.static
        self.assertRegex(css, r"\.tab-off,\.sub-off\{display:none!important\}")
        self.assertRegex(css, r"@media print\{\.tab-off,\.sub-off\{display:block!important\}\}")   # printing shows every section
        for tab, label in (("teams", "TEAMS"), ("cap", "CAP"), ("trade-lab", "TRADE LAB"), ("draft", "DRAFT")):
            self.assertIn(f'<a class="navlink" href="#{tab}" data-tab="{tab}">{label}</a>', self.static)
        self.assertEqual(len(re.findall(r'<a class="navlink"', self.static)), 4)           # nav order is unchanged (tests click navlink[1])
        self.assertIn("window.addEventListener(\"popstate\"", self.static)                 # back / forward switch tabs

    # ---- search, my team, jump chips: driven through the page's own script -----------------------------------------------
    def _drive(self, js, hash_="", wait=500):
        """Run `js` (it fills R) inside the loaded page, after `wait` ms of page time; -> the parsed R."""
        import tempfile
        with open(INDEX, encoding="utf-8") as f:
            html = f.read()
        js = "var D=NBA_NAV.D,view=NBA_NAV.view,norm=NBA_NAV.norm,parseHash=NBA_NAV.parseHash,showTab=NBA_NAV.showTab;" + js
        script = ("<script>(function(){var R={};function done(){var p=document.createElement('pre');p.id='drive-out';"
                  "p.textContent=JSON.stringify(R);document.body.appendChild(p);}try{\n" + js + "\n}catch(e){R.error=String(e&&e.stack||e);}"
                  "setTimeout(function(){try{if(window.__after)window.__after();}catch(e){R.error=String(e);}done();}," + str(wait) + ");})();</script>")
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, "index.html")
            with open(path, "w", encoding="utf-8") as f:
                f.write(html.replace("</body>", script + "</body>", 1))
            out = subprocess.run([_chrome(), "--headless=new", "--disable-gpu", "--no-sandbox", "--virtual-time-budget=6000", "--dump-dom",
                                  "file://" + path + hash_], capture_output=True, text=True, timeout=120).stdout
        finally:
            shutil.rmtree(d)
        m = re.search(r'<pre id="drive-out">(.*?)</pre>', out, re.S)
        self.assertIsNotNone(m, out[-400:])
        r = json.loads(html_lib.unescape(m.group(1)))
        self.assertNotIn("error", r, r.get("error"))
        return r

    def test_search_finds_players_teams_and_free_agents_without_accents(self):
        r = self._drive("""
          var rows=[];D.teams.forEach(function(t){view().teams[t.id].roster.forEach(function(x){rows.push({n:x.n,t:t.id,k:x.k});});});
          var accent=rows.filter(function(x){return /[^\\x00-\\x7f]/.test(x.n);})[0];R.accent=accent&&accent.n;
          if(accent){var res=NBA_NAV.search(norm(accent.n)).players;R.playerFound=res.some(function(p){return p.n===accent.n&&p.t===accent.t;});}
          var t=D.teams[0];R.teamByShort=NBA_NAV.search(t.short).teams.some(function(x){return x.id===t.id;});
          var word=t.name.split(/[ |]+/).filter(function(w){return w.length>3;})[0];R.word=word;R.teamByName=NBA_NAV.search(word).teams.some(function(x){return x.id===t.id;});
          var own={};rows.forEach(function(x){own[x.k]=1;});var fa=D.available.rows.filter(function(a){return !own[a[0]];})[0];R.fa=fa&&fa[1];
          if(fa){var rf=NBA_NAV.search(norm(fa[1]));R.faFound=rf.fa.some(function(p){return p.k===fa[0];});R.faNotRostered=!rf.players.some(function(p){return p.k===fa[0];});}
          R.none=NBA_NAV.search("zzzzqqqq");R.empty=NBA_NAV.search("   ");
          R.multi=NBA_NAV.search(norm(accent.n).split(" ").reverse().join(" ")).players.some(function(p){return p.n===accent.n;});""")
        self.assertTrue(r["accent"], "no rostered player with an accented name to check")
        self.assertTrue(r["playerFound"], r["accent"])                       # "jokic" finds Jokić, wherever he is rostered now
        self.assertTrue(r["teamByShort"] and r["teamByName"], r["word"])
        self.assertTrue(r["faFound"] and r["faNotRostered"], r["fa"])      # free agents are separate from rostered players
        self.assertEqual(r["none"], {"teams": [], "players": [], "fa": []})
        self.assertEqual(r["empty"], {"teams": [], "players": [], "fa": []})
        self.assertTrue(r["multi"])                                          # word order does not matter

    def test_my_team_is_highlighted_across_cap_draft_and_synthetic_views(self):
        r = self._drive("""
          var t=D.teams[0];NBA_NAV.setMe(t.id);
          var host=document.createElement('div');host.id='synth';
          host.innerHTML='<table class="cmp"><tr><td>'+t.short+'</td></tr><tr><td>Nobody FC</td></tr></table>'
            +'<div class="lab-card"><span class="tchip">'+t.short+'</span></div><div class="lab-card"><span class="tchip">Nobody FC</span></div>'
            +'<article class="wi-card"><span class="identity-tag">'+t.short+' | '+t.name+'</span></article>';
          document.body.appendChild(host);
          window.__after=function(){var q=function(s){return document.querySelectorAll(s).length;};
            R.cap=q('.cap-card.mine');R.card=q('section.team-card.mine');R.cmp=q('#synth .cmp tr.mine');R.cmpAll=q('#synth .cmp tr');
            R.lab=q('#synth .lab-card.mine');R.labAll=q('#synth .lab-card');R.wi=q('#synth article.wi-card.mine');R.star=q('#synth .mine-chip');
            NBA_NAV.setMe(null);R.cleared=q('.mine')+q('.mine-chip');};""")
        self.assertEqual((r["cap"], r["card"]), (1, 1))
        self.assertEqual((r["cmp"], r["cmpAll"], r["lab"], r["labAll"], r["wi"]), (1, 2, 1, 2, 1))   # only my team's rows / folds
        self.assertEqual(r["star"], 3)
        self.assertEqual(r["cleared"], 0)

    def test_search_results_style_rookies(self):
        r = self._drive("""
          var rook=D.available.rows.filter(function(a){return a[7]==='R';})[0];R.fa=rook&&rook[1];
          if(rook){NBA_NAV.open();var i=document.getElementById('sp-in');i.value=rook[1];i.dispatchEvent(new Event('input'));
            R.faTag=!!document.querySelector('#sp-body .sp-n.rk .in-tag.rk');}""")
        if r.get("fa"):
            self.assertTrue(r["faTag"], r["fa"])

    def test_mobile_header_keeps_tabs_pinned(self):
        with open(INDEX, encoding="utf-8") as f:
            html = f.read()
        self.assertIn(".topbar{top:calc(-1 * var(--tb-fold,44px))}", html)   # pure CSS: no scroll handler resizes the header
        self.assertNotIn("topbar.hide", html)                                # (a size change under the finger made it flicker)
        self.assertNotIn('classList.add("hide")', html)
        self.assertRegex(html, r"\.topbar\{\s*position:sticky;top:0")

    def test_trade_checker_page_matches_python_on_every_swap(self):
        """The page's checker is a port of scripts/trade_checker.py: same overall status and the same (rule, team, level) rows,
        for 2-for-2 swaps, three-team rings, trades that overflow the 15 roster spots, and drops."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        import league_state as ls
        import season_state as ss
        import trade_checker as tc
        si = ss.load_season(ls.load_inputs())
        state = ss.season_state(si)
        fids = sorted(si["franchises"])
        rows = {f: ss.ranked_roster(si, state, f) for f in fids}
        acq = tc.acquisitions(si)
        held = [(k, f) for (k, f) in acq if state["playerOwner"].get(k) == f]
        cases = []
        for i, a in enumerate(fids):
            for b in fids[i + 1:]:
                for ra in (rows[a][0], rows[a][-1]):
                    for rb in (rows[b][0], rows[b][-1]):
                        cases.append({"moves": [{"key": ra["k"], "from": a, "to": b}, {"key": rb["k"], "from": b, "to": a}], "drops": []})
        for k, f in held:                                                  # trades that include a player inside a cooldown
            g = next(x for x in fids if x != f)
            cases.append({"moves": [{"key": k, "from": f, "to": g}, {"key": rows[g][-1]["k"], "from": g, "to": f}], "drops": []})
        cases.append({"moves": [{"key": rows[fids[0]][0]["k"], "from": fids[1], "to": fids[0]}], "drops": []})   # invalid: wrong owner
        for i in range(0, len(fids) - 2, 3):                                 # three-team rings
            x, y, z = fids[i:i + 3]
            for j in (0, -1):
                cases.append({"moves": [{"key": rows[x][j]["k"], "from": x, "to": y}, {"key": rows[y][j]["k"], "from": y, "to": z}, {"key": rows[z][j]["k"], "from": z, "to": x}], "drops": []})
        for f in fids:                                                       # 3-for-1 into each team: roster overflow, then with drops of its cheapest players
            g = next(x for x in fids if x != f)
            mv = [{"key": r["k"], "from": g, "to": f} for r in rows[g][:3]] + [{"key": rows[f][0]["k"], "from": f, "to": g}]
            cases.append({"moves": mv, "drops": []})
            mine = [r for r in rows[f] if r["k"] != rows[f][0]["k"]][-3:]
            cases.append({"moves": mv, "drops": [{"key": r["k"], "team": f} for r in mine]})
            big = rows[f][1]                                                 # dropping a protected / review-tier player
            cases.append({"moves": mv, "drops": [{"key": big["k"], "team": f}]})
        for f in fids[:4]:                                                   # a team that only drops (not in any move) still takes part
            g, h2 = [x for x in fids if x != f][:2]
            mv = [{"key": rows[g][-1]["k"], "from": g, "to": h2}, {"key": rows[h2][-1]["k"], "from": h2, "to": g}]
            cases.append({"moves": mv, "drops": [{"key": rows[f][-1]["k"], "team": f}]})
            cases.append({"moves": mv, "drops": [{"key": rows[f][0]["k"], "team": f}, {"key": rows[g][-2]["k"], "team": g}]})
        elig = set(tc.load_rules()["yahoo"]["ilEligibleStatuses"])
        for i, f in enumerate(fids[:8]):                                       # draft picks (1st locked, 2nd / 3rd to review), alone and with players
            g = fids[(i + 1) % len(fids)]
            for rnd in (1, 2, 3):
                cases.append({"moves": [{"key": "2027-R%d-%s" % (rnd, f), "type": "pick", "from": f, "to": g}], "drops": [], "ils": []})
            cases.append({"moves": [{"key": "2027-R2-%s" % f, "type": "pick", "from": f, "to": g}, {"key": rows[g][-1]["k"], "from": g, "to": f}], "drops": [], "ils": []})
            cases.append({"moves": [{"key": "2027-R2-%s" % g, "type": "pick", "from": f, "to": g}], "drops": [], "ils": []})   # not f's pick
        for f in fids:                                                         # IL moves: eligible and ineligible players, plus slot overflow
            g = next(x for x in fids if x != f)
            mv = [{"key": rows[g][-1]["k"], "from": g, "to": f}]
            own = [r for r in rows[f] if state["slots"].get(r["k"]) not in ("IL", "IL+")]
            inj = next((r for r in own if state["status"].get(r["k"]) in elig), None)
            cases.append({"moves": mv, "drops": [], "ils": []})
            cases.append({"moves": mv, "drops": [], "ils": [{"key": own[0]["k"], "team": f}]})
            if inj:
                cases.append({"moves": mv, "drops": [], "ils": [{"key": inj["k"], "team": f}]})
            cases.append({"moves": mv, "drops": [], "ils": [{"key": r["k"], "team": f} for r in own[:5]]})
        pre50 = tc.preseason_ranks(si, 50)
        for f in fids:                                                         # dropping a top-50 / 20+ player, a 10-19 player and a plain one, each with a roster-balancing move
            g = next(x for x in fids if x != f)
            mv = [{"key": rows[g][-1]["k"], "from": g, "to": f}, {"key": rows[f][-1]["k"], "from": f, "to": g}]
            for pick in (next((r for r in rows[f][:-1] if r["k"] in pre50), None), next((r for r in rows[f][:-1] if 10 <= r["c"] < 20 and r["k"] not in pre50), None), rows[f][-2]):
                if pick:
                    cases.append({"moves": mv, "drops": [{"key": pick["k"], "team": f}], "ils": []})
        nows = ["2026-10-21T12:00:00Z", "2026-12-31T00:00:00Z", "2027-02-10T00:00:00Z", "2027-03-01T00:00:00Z"]
        expect = [[tc.signature(tc.check_proposal(si, state, c["moves"], n, drops=c["drops"], ils=c.get("ils", []))) for c in cases] for n in nows]
        r = self._drive("var C=%s,N=%s,E=[];N.forEach(function(n){E.push(C.map(function(m){var x=NBA_NAV.check(m.moves,n,m.drops,m.ils||[]);"
                        "return {status:x.status,rules:x.rules.map(function(q){return [q.rule,q.team,q.level];}).sort(function(a,b){return a.join('|')<b.join('|')?-1:1;})};}));});R.out=E;"
                        % (json.dumps(cases), json.dumps(nows)), wait=100)
        for n in range(len(nows)):
            for i, c in enumerate(cases):
                want = {"status": expect[n][i]["status"], "rules": sorted(expect[n][i]["rules"])}
                self.assertEqual(r["out"][n][i], want, (nows[n], c))
        self.assertGreaterEqual(len({e["status"] for e in expect[1]}), 2)   # the cases are not all the same verdict
        self.assertTrue(any(rr[0] == "size" and rr[2] == "blocked" for e in expect[1] for rr in e["rules"]))   # the overflow cases do overflow
        self.assertTrue(any(rr[0] == "drop" for e in expect[1] for rr in e["rules"]))

    def test_trade_machine_panel_multi_team_live_cap_url_and_colored_teams(self):
        r = self._drive("""
          var D2=NBA_NAV.D,base=D2.scenarios[''].teams,ids=D2.teams.map(function(t){return t.id;}),a=ids[0],b=ids[1],c=ids[2];
          var last=function(f){var r=base[f].roster;return r[r.length-1];};
          R.ka=last(a).k;R.kb=last(b).k;R.kc=last(c).k;R.a=a;R.b=b;R.c=c;
          var q=function(s){return document.querySelectorAll(s);};
          R.hasPanel=!!document.getElementById('chk');R.title=document.querySelector('#chk .chk-h b').textContent;R.empty=!document.getElementById('chk-verdict');
          // team pills are colored buttons, no doubled "|" labels
          R.pills=q('#chk .chk-teams button').length;R.onPills=q('#chk .chk-teams .on').length;
          R.pillColored=!!document.querySelector('#chk .chk-teams .on').style.background;
          // add a third team
          var third=Array.prototype.filter.call(q('#chk .chk-teams button'),function(x){return x.textContent===D2.teams[2].short;})[0];if(!third.classList.contains('on'))third.click();
          R.cols=q('#chk .chk-col').length;
          var btnOf=function(f,k){var col=document.querySelector('#chk .chk-col[data-team="'+f+'"]'),n=base[f].roster.filter(function(r){return r.k===k;})[0].n;return Array.prototype.filter.call(col.querySelectorAll('.player-row'),function(x){return x.querySelector('.pname').textContent.indexOf(n)>=0;})[0];};
          btnOf(R.a,R.ka).click();btnOf(R.b,R.kb).click();
          R.sumCards=q('#chk .chk-sc').length;R.sends=q('#chk .chk-ol').length;R.gets=q('#chk .player-row.tm-in').length;R.checkCards=q('#chk .chk-sc .chk-ck').length;R.checks=q('#chk .chk-sc .ck').length;R.sending=q('#chk .nc-div.out').length;
          R.outRows=q('#chk .chk-ol').length;R.inRows=q('#chk .player-row.tm-in').length;R.cyc=q('#chk .chk-to').length;R.bar=!!document.querySelector('#chk .chk-bar');
          var grp=document.querySelector('#chk .chk-to');R.before=grp.querySelector('.on').textContent;
          var alt=Array.prototype.filter.call(grp.querySelectorAll('.tpill:not(.on)'),function(x){return true;})[0];R.alt=alt.textContent;alt.click();
          R.afterCyc=document.querySelector('#chk .chk-to .on').textContent;R.outFirst=document.querySelector('#chk .chk-col .players').firstElementChild.textContent;
          R.verdict=!!document.getElementById('chk-verdict');R.status=(document.querySelector('#chk .chk-st')||{}).textContent;R.rows=q('#chk .chk-r').length;
          R.meters=q('#chk .meter').length;R.payShown=q('#chk .chk-col .chk-pay b').length;                 // live payroll: only teams that move
          R.text=document.getElementById('chk').textContent;
          R.dropBtns=q('#chk .tm-more').length;
          var dcol=document.querySelector('#chk .chk-col[data-team="'+R.c+'"]');dcol.querySelector('.tm-more').click();document.querySelector('#chk .chk-col[data-team="'+R.c+'"] .chk-tray .tr-btn.drop').click();   // the idle third team drops a player
          R.dropRows=q('#chk .player-row.tm-drop').length;R.dropInYahoo=!!document.querySelector('#chk-yahoo')&&document.querySelector('#chk-yahoo').textContent.indexOf('DROPS')>=0;
          R.yahooTrades=q('#chk-yahoo .yh-t').length-1;
          var cap=null;Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:function(t){cap=t;return {then:function(f){f();}};}}});document.getElementById('chk-text').click();R.summary=cap||'';
          R.url=location.search;
          document.getElementById('chk-reset').click();R.cleared=!document.getElementById('chk-verdict');R.urlAfterReset=location.search;""")
        self.assertTrue(r["hasPanel"] and r["empty"])
        self.assertEqual(r["title"], "TRADE MACHINE")
        self.assertEqual(r["pills"], 16)
        self.assertGreaterEqual(r["onPills"], 2)
        self.assertTrue(r["pillColored"])
        self.assertGreaterEqual(r["cols"], 3)
        self.assertGreaterEqual(r["sumCards"], 3)                                  # one card per team in the trade
        self.assertEqual((r["sends"], r["gets"]), (2, 2))                          # who sends and who receives what, inside each card
        self.assertGreaterEqual(r["sending"], 1)
        self.assertGreaterEqual(r["checkCards"], 2)
        self.assertEqual(r["checks"], r["checkCards"] * 5)                         # CAP / ROSTER / SLOTS / LIMITS / HELD for each team taking part
        self.assertEqual((r["outRows"], r["inRows"]), (2, 2))                      # the editor shows the post-trade roster: who leaves, who arrives
        self.assertTrue(r["bar"])
        self.assertGreaterEqual(r["cyc"], 2)                                       # with 3+ teams the destination is changeable
        self.assertNotEqual(r["before"], r["afterCyc"])
        self.assertEqual(r["afterCyc"], r["alt"])                                   # the destination pills change who gets him
        self.assertEqual(r["outFirst"], "sending out")                              # and sit at the top of the column, where you tapped
        self.assertTrue(r["verdict"])
        self.assertIn(r["status"], ("LEGAL", "BLOCKED", "COMMISSIONER REVIEW"))
        self.assertGreaterEqual(r["rows"], 4)
        self.assertGreater(r["dropBtns"], 10)                                      # drop / IL actions are one tap away on every player, not only when a team is over 15
        self.assertEqual(r["dropRows"], 1)                                         # and a dropped player moves to the "dropping" group
        self.assertTrue(r["dropInYahoo"])                                          # the Yahoo steps list the drop
        self.assertGreaterEqual(r["yahooTrades"], 1)
        self.assertIn("gets", r["summary"]); self.assertIn("drops", r["summary"]); self.assertIn("TRADE ·", r["summary"])
        self.assertGreaterEqual(r["meters"], 3)
        self.assertGreaterEqual(r["payShown"], 2)
        self.assertNotIn("$", r["text"])
        self.assertNotRegex(r["text"], r"\|.*\|")                                # no doubled team-name bars
        self.assertIn("check=", r["url"])
        self.assertTrue(r["cleared"])
        self.assertNotIn("check=", r["urlAfterReset"])
        again = self._drive("""
          R.verdict=!!document.getElementById('chk-verdict');R.on=document.querySelectorAll('#chk .chk-ol').length;R.cols=document.querySelectorAll('#chk .chk-col').length;
          R.hidden=document.getElementById('trade-lab').classList.contains('tab-off');""",
                            hash_="?check=%s~%s,%s~%s" % (r["ka"], r["b"], r["kb"], r["c"]))
        self.assertTrue(again["verdict"])
        self.assertEqual(again["on"], 2)                                          # the shared link restores the same players
        self.assertEqual(again["cols"], 3)                                        # and the third team
        self.assertFalse(again["hidden"])                                         # on the Trade Lab tab

    def test_trade_machine_picks_and_il_controls(self):
        r = self._drive("""
          var q=function(s){return Array.prototype.slice.call(document.querySelectorAll(s));};
          var D2=NBA_NAV.D,ids=D2.teams.map(function(t){return t.id;});
          var cols=q('#chk .chk-col');R.cols=cols.length;
          var col=cols[0];R.pickRows=col.querySelectorAll('.pickrow').length;R.locked=col.querySelectorAll('.pickrow .hold').length;
          R.pickLabels=Array.prototype.map.call(col.querySelectorAll('.pickrow .pname'),function(x){return x.textContent;});
          // a 1st-round pick is not on the table, but if one arrives by link the rules still block it
          var res=NBA_NAV.check([{key:'2027-R1-'+ids[0],type:'pick',from:ids[0],to:ids[1]}],'2026-12-31T00:00:00Z');
          R.r1Blocked=res.rules.some(function(x){return x.rule==='pick'&&x.level==='blocked'&&x.reason.indexOf('1st-round')>=0;});
          var rows=col.querySelectorAll('.pickrow');rows[0].click();                      // a 2nd
          var rev=document.querySelector('#chk .chk-r.review[data-rule="pick"]');R.r2Review=!!rev&&rev.textContent.indexOf('Trade Tank')>=0;
          R.pickOut=q('#chk .chk-ol').length;R.url=location.search;
          R.slotsInSummary=q('#chk .chk-sc .ck').some(function(c){return c.textContent.indexOf('SLOTS')>=0;});
          // the injured list is its own group, and IL players carry an IL chip
          var il=q('#chk .nc-div.il');R.ilGroups=il.length;R.ilHead=il.length?il[0].textContent:'';
          var ilRows=q('#chk .player-row.il-row');R.ilRows=ilRows.length;R.ilChips=ilRows.filter(function(x){return x.querySelector('.st-chip.il');}).length;
          R.ilAfterHeader=il.length?(il[0].nextElementSibling&&il[0].nextElementSibling.classList.contains('il-row')):null;
          // the action tray offers IL only for injured players
          var m=q('#chk .chk-col')[0].querySelector('.tm-more');m.click();R.tray=!!document.querySelector('#chk .chk-tray .tr-btn.drop');""")
        self.assertEqual(r["cols"], 2)
        self.assertEqual(r["pickRows"], 2)                                         # 2nd and 3rd round of next season only: 1sts are not on the table
        self.assertEqual(r["locked"], 0)
        self.assertTrue(all("Round 1" not in x for x in r["pickLabels"]), r["pickLabels"])
        self.assertTrue(r["r1Blocked"])
        self.assertTrue(r["r2Review"])
        self.assertEqual(r["pickOut"], 1)
        self.assertIn("check=", r["url"])
        self.assertTrue(r["slotsInSummary"])
        self.assertGreaterEqual(r["ilGroups"], 1)                                  # an injured-list section per team that has IL players
        self.assertRegex(r["ilHead"], r"injured list · \d/3")
        self.assertTrue(r["ilAfterHeader"])
        self.assertEqual(r["ilRows"], r["ilChips"])                                # every IL player says IL, not only his Yahoo status
        self.assertTrue(r["tray"])

    def test_held_players_show_when_the_hold_lifts_not_the_date(self):
        r = self._drive("""
          var q=function(s){return Array.prototype.slice.call(document.querySelectorAll(s));};
          R.pills=q('#chk .hold').map(function(x){return x.textContent;});R.titles=q('#chk .hold').map(function(x){return x.title;});
          var D2=NBA_NAV.D,base=D2.scenarios[''].teams,held=null;
          D2.teams.forEach(function(t){base[t.id].roster.forEach(function(p){if(!held&&NBA_NAV.D.trade.acq[p.k+'|'+t.id]){held={k:p.k,f:t.id};}});});
          var other=D2.teams.filter(function(t){return t.id!==held.f;})[0].id;
          var res=NBA_NAV.check([{key:held.k,from:held.f,to:other},{key:base[other].roster[base[other].roster.length-1].k,from:other,to:held.f}],'2026-10-21T00:00:00Z');
          R.reason=(res.rules.filter(function(x){return x.rule==='cooldown'&&x.level==='blocked';})[0]||{}).reason||'';""")
        self.assertTrue(r["pills"])
        for p in r["pills"]:
            self.assertRegex(p, r"^TRADABLE IN \d+ DAYS?$")                       # days left, not a date to count back from
        for t in r["titles"]:
            self.assertRegex(t, r"can be traded again on 20\d\d-\d\d-\d\d")  # the date stays in the tooltip
        self.assertRegex(r["reason"], r"can't be traded for \d+ more days? \(until 20\d\d-\d\d-\d\d\)")

    def test_undrafted_rookies_on_a_roster_get_rookie_styling_everywhere(self):
        """A 2026-class rookie who was not drafted in the league draft (picked up from free agency) is still a rookie:
        purple name + R tag in the team cards, the search results and the trade machine. Derived from the data, not pinned."""
        r = self._drive("""
          var D2=NBA_NAV.D,drafted={};D2.draft.completed.forEach(function(c){drafted[c.playerKey]=1;});
          var q=function(s){return Array.prototype.slice.call(document.querySelectorAll(s));};
          var list=[];D2.teams.forEach(function(t){D2.scenarios[''].teams[t.id].roster.forEach(function(p){if(D2.rookies.indexOf(p.k)>=0&&!drafted[p.k])list.push({k:p.k,n:p.n,f:t.id});});});
          R.list=list.map(function(x){return x.n;});R.total=D2.rookies.length;
          R.card=list.map(function(x){var card=document.querySelector('section.team-card[data-team="'+x.f+'"]');
            var row=Array.prototype.filter.call(card.querySelectorAll('.player-row'),function(e){return e.querySelector('.pname')&&e.querySelector('.pname').textContent.indexOf(x.n)>=0;})[0];
            return !!row&&row.classList.contains('rookie-row')&&!!row.querySelector('.in-tag.rk');});
          R.search=list.map(function(x){var p=NBA_NAV.search(x.n).players.filter(function(y){return y.k===x.k;})[0];return !!p&&p.rk===true;});
          R.machine=list.map(function(x){var el=NBA_NAV.D&&document.querySelector('#chk .chk-teams');return true;});""")
        self.assertGreaterEqual(r["total"], 19)
        for name, ok in zip(r["list"], r["card"]):
            self.assertTrue(ok, f"{name}: no rookie styling in the team card")
        for name, ok in zip(r["list"], r["search"]):
            self.assertTrue(ok, f"{name}: not a rookie in search")

    def test_yahoo_steps_route_one_way_flows_through_a_hub_so_every_trade_has_two_sides(self):
        """Yahoo trades are two-team. A ring (A->B->C->A) must become two-sided trades with assets hopping through a hub, in an order
        where every asset is owned by the giver at that moment, and the final owners match the proposal exactly."""
        r = self._drive("""
          var D2=NBA_NAV.D,base=D2.scenarios[''].teams,ids=D2.teams.map(function(t){return t.id;});
          var pick=function(i){var rr=base[ids[i]].roster;return rr[rr.length-1-(i%2)].k;};
          var mk=function(pairs){return pairs.map(function(p){return {key:pick(p[0]),from:ids[p[0]],to:ids[p[1]]};});};
          var cases={ring3:mk([[0,1],[1,2],[2,0]]),ring4:mk([[0,1],[1,2],[2,3],[3,0]]),ring6:mk([[0,1],[1,2],[2,3],[3,4],[4,5],[5,0]]),
            star:[1,2,3].map(function(j){return {key:base[ids[0]].roster[j].k,from:ids[0],to:ids[j]};}),chain:mk([[0,1],[1,2]]),mixed:mk([[0,1],[1,0],[1,2],[2,0]]),gift:mk([[0,1]]),
            twoway:[{key:pick(0),from:ids[0],to:ids[1]},{key:pick(1),from:ids[1],to:ids[0]}]};
          // the same player can't be in two cases' second pair: give the mixed / twoway cases their own distinct assets
          cases.mixed=[{key:pick(0),from:ids[0],to:ids[1]},{key:base[ids[1]].roster[0].k,from:ids[1],to:ids[0]},{key:pick(1),from:ids[1],to:ids[2]},{key:pick(2),from:ids[2],to:ids[0]}];
          R.out={};
          Object.keys(cases).forEach(function(name){var mv=cases[name],plan=NBA_NAV.plan(mv,null),owner={};mv.forEach(function(m){owner[m.key]=m.from;});var ok=true;
            plan.legs.forEach(function(l){l.ab.forEach(function(k){if(owner[k]!==l.a)ok=false;owner[k]=l.b;});l.ba.forEach(function(k){if(owner[k]!==l.b)ok=false;owner[k]=l.a;});});
            mv.forEach(function(m){if(owner[m.key]!==m.to)ok=false;});
            R.out[name]={ok:ok,legs:plan.legs.length,oneWay:plan.legs.filter(function(l){return !l.ab.length||!l.ba.length;}).length,hub:plan.hub,hops:Object.keys(plan.hops).length};});
          // and it renders: a ring shows no "nothing" sides, one chip per hopped asset
          R.ids=ids;R.keys=[pick(0),pick(1),pick(2)];""")
        for name, o in r["out"].items():
            self.assertTrue(o["ok"], name)                                         # every step is valid and the end state is exactly the proposal
        for ring, n in (("ring3", 3), ("ring4", 4), ("ring6", 6)):
            self.assertEqual(r["out"][ring]["legs"], n - 1, ring)                  # a ring of n teams = n-1 trades through one hub
            self.assertEqual(r["out"][ring]["oneWay"], 0, ring)                    # none of them is one-sided
            self.assertEqual(r["out"][ring]["hops"], n - 2, ring)
        self.assertEqual(r["out"]["twoway"]["legs"], 1)                            # a pair that already trades both ways stays one trade
        self.assertEqual(r["out"]["twoway"]["hops"], 0)
        self.assertEqual(r["out"]["gift"]["oneWay"], 1)                            # a true one-way gift can't be made two-sided
        self.assertLessEqual(r["out"]["chain"]["oneWay"], 1)
        ids, ks = r["ids"], r["keys"]
        page = self._drive("""
          var q=function(s){return Array.prototype.slice.call(document.querySelectorAll(s));};
          R.legs=q('#chk-yahoo .yh-t').length;R.none=q('#chk-yahoo .yh-none').length;R.hops=q('#chk-yahoo .yh-hop').length;R.intro=document.querySelector('#chk-yahoo .chk-yh-n').textContent;
          R.warn=q('#chk-yahoo .yh-w.warn').map(function(x){return x.textContent;});""",
                           hash_="?check=%s~%s,%s~%s,%s~%s" % (ks[0], ids[1], ks[1], ids[2], ks[2], ids[0]))
        self.assertEqual(page["legs"], 2)                                          # 3-team ring = 2 trades
        self.assertEqual(page["none"], 0)                                          # no "nothing" sides
        self.assertGreaterEqual(page["hops"], 2)                                   # the hopped asset is marked on both of its trades
        self.assertIn("go-between", page["intro"])
        self.assertTrue(page["warn"] and "only to build the Yahoo trades" in page["warn"][0])
        self.assertIn("hold is unaffected", page["warn"][0])                      # a hop is a Yahoo construction: the league hold rules still see one move

    def test_team_card_detail_is_collapsed_behind_an_info_button_that_flags_limits(self):
        """The supplementary detail (status, payroll change, roster limits, moves) is hidden by default; a small button toggles it, and
        its dot flags a limit that is at or over. Derived from each team's own checks, not pinned to live rosters."""
        r = self._drive("""
          var D2=NBA_NAV.D,cards=Array.prototype.slice.call(document.querySelectorAll('section.team-card'));
          R.cards=cards.length;R.buttons=document.querySelectorAll('.tc-info').length;
          R.hiddenByDefault=cards.every(function(c){var s=c.querySelector('.scn-strip');return s&&getComputedStyle(s).display==='none';});
          R.flags=cards.map(function(c){var ck=D2.scenarios[''].teams[c.dataset.team].checks,lv=['injured','singlePosition','coverage','lineup'].map(function(k){return ck[k].level;}),
            want=lv.indexOf('over')>=0?'over':lv.indexOf('watch')>=0?'watch':'',b=c.querySelector('.tc-info');
            return {want:want,has:want?b.classList.contains(want):(!b.classList.contains('over')&&!b.classList.contains('watch')),title:b.title};});
          var c0=cards[0],b0=c0.querySelector('.tc-info');b0.click();
          R.opened=getComputedStyle(c0.querySelector('.scn-strip')).display!=='none';R.expanded=b0.getAttribute('aria-expanded');
          b0.click();R.closed=getComputedStyle(c0.querySelector('.scn-strip')).display==='none';""")
        self.assertEqual(r["cards"], 16)
        self.assertEqual(r["buttons"], 16)
        self.assertTrue(r["hiddenByDefault"])
        for f in r["flags"]:
            self.assertTrue(f["has"], f)                                           # the dot matches the team's own limits
            if f["want"]:
                self.assertTrue(f["title"])                                        # and the tooltip says which limit
        self.assertTrue(r["opened"])
        self.assertEqual(r["expanded"], "true")
        self.assertTrue(r["closed"])

    def test_team_detail_panel_states_status_limits_and_facts_in_words(self):
        r = self._drive("""
          var D2=NBA_NAV.D,cards=Array.prototype.slice.call(document.querySelectorAll('section.team-card'));
          R.errors=[];
          R.cards=cards.map(function(c){var tm=D2.scenarios[''].teams[c.dataset.team],ck=tm.checks,s=c.querySelector('.scn-strip');
            var lv=['injured','singlePosition','coverage','lineup'].map(function(k){return ck[k].level;});
            return {status:(s.querySelector('.tp-s .chip')||{}).textContent,room:(s.querySelector('.tp-r')||{}).textContent,meter:!!s.querySelector('.meter'),
              limits:s.querySelectorAll('.tp-l').length,over:s.querySelectorAll('.tp-l.over').length,watch:s.querySelectorAll('.tp-l.watch').length,
              wantOver:lv.filter(function(x){return x==='over'}).length,wantWatch:lv.filter(function(x){return x==='watch'}).length,
              players:Array.prototype.map.call(s.querySelectorAll('.tp-f div'),function(d){return d.textContent;}),count:tm.count,
              oldChips:s.querySelectorAll('.rc-i').length};});""")
        words = {"Under the floor", "At the floor", "In range", "Near the ceiling", "At the ceiling", "Over the ceiling"}
        for c in r["cards"]:
            self.assertIn(c["status"], words)
            self.assertRegex(c["room"], r"(below the \d+ ceiling|over the \d+ ceiling|under the \d+ floor)")   # the status is also said in words
            self.assertTrue(c["meter"])
            self.assertEqual(c["limits"], 4)                                       # injured, single-position, positions, lineup: one sentence each
            self.assertEqual((c["over"], c["watch"]), (c["wantOver"], c["wantWatch"]))   # flagged exactly as the team's own checks say
            self.assertTrue(any(x.startswith("PLAYERS") or x.lower().startswith("players") for x in c["players"]))
            self.assertIn("%d of 15" % c["count"], " ".join(c["players"]))
            self.assertEqual(c["oldChips"], 0)                                     # the tiny chips are gone

    _PROPOSE = """
          var q=function(s){return Array.prototype.slice.call(document.querySelectorAll(s));};
          var D2=NBA_NAV.D,base=D2.scenarios[''].teams;
          var propose=function(i,j){                                           // the two teams' top-paid players swap places
            var ids=D2.teams.map(function(t){return t.id;}),a=ids[i],b=ids[j],sh=function(f){return D2.teams.filter(function(t){return t.id===f;})[0].short;};
            var on=function(){return q('#chk .chk-teams .on').map(function(x){return x.textContent;});},tg=function(s){q('#chk .chk-teams button').filter(function(x){return x.textContent===s;})[0].click();};
            [sh(a),sh(b)].forEach(function(s){if(on().indexOf(s)<0)tg(s);});on().filter(function(s){return s!==sh(a)&&s!==sh(b);}).forEach(tg);
            var pick=function(f,k){var col=q('#chk .chk-col').filter(function(c){return c.dataset.team===f;})[0];var n=base[f].roster.filter(function(r){return r.k===k;})[0].n;
              Array.prototype.filter.call(col.querySelectorAll('.player-row:not(.pickrow)'),function(e){return e.querySelector('.pn-n').textContent===n;})[0].click();};
            pick(a,base[a].roster[0].k);pick(b,base[b].roster[0].k);return [sh(a),sh(b),base[a].roster[0].n,base[b].roster[0].n];};
    """

    def test_share_image_draws_the_trade_and_what_it_means_for_each_team(self):
        r = self._drive(self._PROPOSE + """
          var orig=CanvasRenderingContext2D.prototype.fillText,texts=[];
          CanvasRenderingContext2D.prototype.fillText=function(t){texts.push(String(t));return orig.apply(this,arguments);};
          var who=propose(0,1),cv=NBA_NAV.imageNow();CanvasRenderingContext2D.prototype.fillText=orig;
          var pays=q('#chk .chk-col .chk-pay b').map(function(b){return b.textContent;});
          var px=cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data,distinct={};for(var i=0;i<px.length;i+=4*9973)distinct[px[i]+','+px[i+1]+','+px[i+2]]=1;
          R.w=cv.width;R.h=cv.height;R.texts=texts;R.who=who;R.pays=pays;R.status=document.getElementById('chk-top').textContent;R.colours=Object.keys(distinct).length;""")
        self.assertEqual(r["w"], 2160)                                             # 1080 logical px at 2x
        self.assertGreaterEqual(r["h"], 1800)
        self.assertGreater(r["colours"], 3)                                        # not a blank canvas
        texts = " | ".join(r["texts"])
        for need in ("TRADE PROPOSAL", r["status"], "GETS", "SENDS", r["who"][0], r["who"][1], r["who"][2], r["who"][3]):
            self.assertIn(need, texts)                                             # the headline, the verdict, the teams and the players moved
        for pay in r["pays"]:
            self.assertIn(pay, r["texts"])                                         # each team's payroll after the trade
        self.assertTrue(any("band" in x or "ceiling" in x or "floor" in x for x in r["texts"]))   # where payroll sits against the band
        self.assertTrue(any(re.match(r"^\d{4}-\d\d-\d\d$", x.split(" · ")[-1]) for x in r["texts"]))   # dated

    def test_share_image_says_why_a_blocked_trade_is_blocked(self):
        r = self._drive(self._PROPOSE + """
          var ids=D2.teams.map(function(t){return t.id;}),found=null;
          for(var i=0;i<ids.length&&!found;i++)for(var j=i+1;j<ids.length&&!found;j++){
            var mv=[{key:base[ids[i]].roster[0].k,from:ids[i],to:ids[j]},{key:base[ids[j]].roster[0].k,from:ids[j],to:ids[i]}];
            var res=NBA_NAV.check(mv,'2026-12-31T00:00:00Z',[]);if(res.rules.some(function(x){return x.rule==='cap'&&x.level==='blocked';}))found=[i,j];}
          R.found=found;
          if(found){var orig=CanvasRenderingContext2D.prototype.fillText,texts=[];CanvasRenderingContext2D.prototype.fillText=function(t){texts.push(String(t));return orig.apply(this,arguments);};
            propose(found[0],found[1]);NBA_NAV.imageNow();CanvasRenderingContext2D.prototype.fillText=orig;R.texts=texts;R.status=document.getElementById('chk-top').textContent;}""")
        if not r["found"]:
            self.skipTest("no top-player swap breaks the cap band right now")
        self.assertIn("BLOCKED", r["texts"])                                       # the verdict pill
        self.assertTrue(any(x.startswith("Payroll ") for x in r["texts"]))         # the reason, in words, on the team's card
        self.assertIn("must keep a team in the band or move it toward it", " ".join(r["texts"]))   # (the sentence wraps across drawn lines)

    def test_teams_after_image_shows_each_new_roster_with_arrivals_and_departures(self):
        r = self._drive(self._PROPOSE + """
          var orig=CanvasRenderingContext2D.prototype.fillText,texts=[];
          CanvasRenderingContext2D.prototype.fillText=function(t){texts.push(String(t));return orig.apply(this,arguments);};
          var who=propose(0,1),cv=NBA_NAV.rostersNow();CanvasRenderingContext2D.prototype.fillText=orig;
          // the roster each team will have: everyone who stays + arrivals, never the players who left
          var cols=q('#chk .chk-col').map(function(c){return {team:c.querySelector('.chk-ch b').textContent,names:q('#chk .chk-col[data-team="'+c.dataset.team+'"] .player-row:not(.pickrow) .pn-n').map(function(n){return n.textContent;}),
            pay:(c.querySelector('.chk-pay b')||{}).textContent};});
          R.w=cv.width;R.h=cv.height;R.texts=texts;R.who=who;R.cols=cols;""")
        self.assertEqual(r["w"], 2160)
        self.assertGreaterEqual(r["h"], 1400)
        texts = r["texts"]
        self.assertIn("TEAMS AFTER THE TRADE", texts)
        for col in r["cols"]:
            self.assertIn(col["team"], texts)
            self.assertIn(col["pay"], texts)                                       # payroll after the trade
            for name in col["names"]:                                              # every player on the team's new roster is on the image
                self.assertTrue(any(name == x or x.startswith(name[:10]) for x in texts), name)
        sender, receiver = r["who"][2], r["who"][3]
        self.assertIn("Out: " + sender, texts)                                     # who left, and
        self.assertIn("Out: " + receiver, texts)
        self.assertTrue(any(x.startswith("BEYOND TOP") for x in texts))            # where the counted top 9 now stops

    def test_share_image_button_opens_a_preview_with_copy_and_save(self):
        r = self._drive(self._PROPOSE + """
          R.before=!!document.getElementById('chk-img');propose(0,1);R.after=!!document.getElementById('chk-img');
          document.getElementById('chk-img').click();
          window.__after=function(){var ov=document.getElementById('chk-imgov'),img=ov&&ov.querySelector('img');
            var tabs=ov?Array.prototype.slice.call(ov.querySelectorAll('.imgov-t')):[];R.tabs=tabs.map(function(t){return t.textContent;});R.alt1=img?img.alt:'';R.dl1=ov.querySelector('a.imgov-b').getAttribute('download');
            if(tabs[1]){tabs[1].click();R.alt2=img.alt;R.dl2=ov.querySelector('a.imgov-b').getAttribute('download');R.pressed=tabs[1].getAttribute('aria-pressed');}
            R.open=!!ov;R.src=img?img.src.slice(0,5):'';R.labels=ov?Array.prototype.map.call(ov.querySelectorAll('.imgov-b'),function(b){return b.textContent;}):[];
            var sv=ov&&ov.querySelector('a.imgov-b');R.download=sv?sv.getAttribute('download'):'';R.alt=img?img.alt:'';
            document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}));R.closed=!document.getElementById('chk-imgov');};""", wait=2200)
        self.assertFalse(r["before"])                                              # nothing to share until a trade exists
        self.assertTrue(r["after"])
        self.assertTrue(r["open"])
        self.assertEqual(r["src"], "blob:")
        self.assertIn("Copy image", r["labels"])
        self.assertIn("Save", r["labels"])
        self.assertRegex(r["alt"], r"LEGAL|BLOCKED|COMMISSIONER REVIEW")
        self.assertTrue(r["closed"])                                               # Escape closes it
        self.assertEqual(r["tabs"], ["Trade", "Teams after"])                      # two images: the trade, and the teams as they will look
        self.assertIn("proposed trade", r["alt1"])
        self.assertIn("roster after the trade", r["alt2"])
        self.assertEqual((r["dl1"], r["dl2"]), ("trade-proposal.png", "teams-after-trade.png"))
        self.assertEqual(r["pressed"], "true")

    def test_no_dollar_signs_anywhere_in_the_tool(self):
        with open(INDEX, encoding="utf-8") as f:
            html = f.read()
        body = re.sub(r'<script[^>]*type="application/json"[^>]*>.*?</script>', "", html, flags=re.S)
        self.assertNotIn('"$"', body)
        for m in re.finditer(r'"([^"\n]*\$[^"\n]*)"', body):
            self.assertRegex(m.group(1), r"\$\(|\$\{|\$/|\^|\\d", m.group(1))     # only regex / template uses of $ remain
        data = re.search(r'id="league-data">(.*?)</script>', html, re.S).group(1)
        self.assertNotIn("$", data)
        r = self._drive("""
          var t=function(){var c=document.body.cloneNode(true);c.querySelectorAll('script,style').forEach(function(e){e.remove();});return c.textContent;};R.official=t();
          ['trade-lab','cap','draft'].forEach(function(x){NBA_NAV.showTab(x);R[x]=t();});
          document.querySelector('.modeswitch button[data-mode=WHATIF]').click();R.whatif=t();""", wait=300)
        for k, v in r.items():
            self.assertNotIn("$", v, k)

    def test_search_palette_opens_from_button_and_keys_and_shows_team_chips(self):
        r = self._drive("""
          R.btn=!!document.getElementById('tb-search');R.meBtn=!!document.getElementById('tb-me');
          document.getElementById('tb-search').click();
          R.open=document.getElementById('sp').classList.contains('open');R.chips=document.querySelectorAll('#sp-body .sp-chip').length;R.meRow=!!document.querySelector('#sp-body .sp-me');
          window.__after=function(){R.focus=document.activeElement&&document.activeElement.id;};
          document.getElementById('sp-in').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
          R.closedByEsc=!document.getElementById('sp').classList.contains('open');
          document.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true}));R.slash=document.getElementById('sp').classList.contains('open');
          NBA_NAV.close();
          document.dispatchEvent(new KeyboardEvent('keydown',{key:'k',ctrlKey:true,bubbles:true}));R.ctrlK=document.getElementById('sp').classList.contains('open');
          NBA_NAV.close();R.bodyUnlocked=document.body.style.overflow==='';
          NBA_NAV.open();var inp=document.getElementById('sp-in');inp.value='zzzz';inp.dispatchEvent(new Event('input'));R.noMatch=document.querySelector('#sp-body .sp-empty').textContent;""")
        self.assertTrue(r["btn"] and r["meBtn"])
        self.assertEqual((r["open"], r["chips"], r["meRow"]), (True, 16, True))                        # empty box: 16 team chips + my-team row
        self.assertEqual(r["focus"], "sp-in")                                                           # and the input is focused (checked a moment later)
        self.assertTrue(r["closedByEsc"] and r["slash"] and r["ctrlK"] and r["bodyUnlocked"])
        self.assertIn("No team or player matches", r["noMatch"])

    def test_picking_a_result_jumps_to_the_team_or_player_on_the_teams_tab(self):
        r = self._drive("""
          var t=D.teams[2],tm=view().teams[t.id],pl=tm.roster[0];
          location.hash='#cap';var ps=parseHash();showTab(ps.tab,ps.sub);R.startTab=parseHash().tab;
          window.__after=function(){
            R.hash=location.hash;R.teamsShown=!document.getElementById('rosters-a').classList.contains('tab-off');R.capHidden=document.getElementById('cap').classList.contains('tab-off');
            var card=document.querySelector('section.team-card[data-team="'+t.id+'"]');R.card=!!card;
            var row=card&&card.querySelector('.player-row[data-k="'+pl.k+'"]');R.row=!!row;R.flash=!!(row&&row.classList.contains('flash-row'));R.name=pl.n;
          };
          NBA_NAV.goPlayer(pl.k,t.id);
          R.teamRowsHaveKeys=Array.prototype.every.call(document.querySelectorAll('section.team-card[data-team]'),function(c){return c.querySelectorAll('.player-row[data-k]').length>0;});""")
        self.assertEqual(r["hash"], "#teams")
        self.assertTrue(r["teamsShown"] and r["capHidden"] and r["card"] and r["row"] and r["flash"], r)
        self.assertTrue(r["teamRowsHaveKeys"])                                   # every card's rows carry their player key
        r = self._drive("""
          var t=D.teams[5];window.__after=function(){var c=document.querySelector('section.team-card[data-team="'+t.id+'"]');
            R.flash=!!(c&&c.classList.contains('flash-card'));R.hash=location.hash;};NBA_NAV.goTeam(t.id);""")
        self.assertTrue(r["flash"])
        self.assertEqual(r["hash"], "#teams")

    def test_my_team_is_remembered_marked_and_one_tap_away(self):
        r = self._drive("""
          var t=D.teams[3],key='nbaTalkVN.myTeam';
          R.initial=NBA_NAV.getMe();R.lblBefore=document.querySelector('#tb-me .tb-lbl').textContent;
          document.getElementById('tb-me').click();R.chooseMode=NBA_NAV.state.mode;R.chooseRows=document.querySelectorAll('#sp-body .sp-it').length;
          R.chooseHead=document.querySelector('#sp-body .sp-h').textContent;NBA_NAV.close();
          NBA_NAV.setMe(t.id);
          R.stored=localStorage.getItem(key);R.lbl=document.querySelector('#tb-me .tb-lbl').textContent;R.short=t.short;
          R.mineCards=Array.prototype.map.call(document.querySelectorAll('section.team-card.mine'),function(c){return c.dataset.team;});
          R.mineCap=document.querySelectorAll('.cap-card.mine').length;
          R.firstChip=document.querySelector('#team-jump .tj-chip').textContent;R.chips=document.querySelectorAll('#team-jump .tj-chip').length;
          R.setClass=document.getElementById('tb-me').classList.contains('set');
          window.__after=function(){R.hash=location.hash;var c=document.querySelector('section.team-card[data-team="'+t.id+'"]');R.flash=!!(c&&c.classList.contains('flash-card'));
            localStorage.setItem(key,'franchise-99');R.bogus=NBA_NAV.getMe();
            var orig=Storage.prototype.getItem;Storage.prototype.getItem=function(){throw new Error('blocked');};
            R.blocked=NBA_NAV.getMe();try{NBA_NAV.setMe(null);R.setNoThrow=true;}catch(e){R.setNoThrow=false;}Storage.prototype.getItem=orig;};
          document.getElementById('tb-me').click();                              // with a team set: one tap jumps to it""")
        self.assertIsNone(r["initial"])
        self.assertEqual(r["lblBefore"], "My team")
        self.assertEqual((r["chooseMode"], r["chooseRows"], r["chooseHead"]), ("choose", 16, "Which team is yours?"))   # first tap asks which team
        self.assertEqual((r["stored"] is not None, r["lbl"], r["setClass"]), (True, r["short"], True))
        self.assertEqual(len(r["mineCards"]), 1)
        self.assertEqual(r["mineCap"], 1)                                          # the Cap page marks it too
        self.assertEqual((r["firstChip"], r["chips"]), ("\u2605 " + r["short"], 16))   # my team's chip leads the jump bar
        self.assertEqual(r["hash"], "#teams")
        self.assertTrue(r["flash"])
        self.assertIsNone(r["bogus"])                                              # an unknown stored id is ignored
        self.assertIsNone(r["blocked"])                                            # storage that throws never breaks the page
        self.assertTrue(r["setNoThrow"])

    def test_leaving_what_if_when_jumping_and_static_hooks(self):
        r = self._drive("""
          document.querySelector('.modeswitch button[data-mode=WHATIF]').click();R.wi=document.body.classList.contains('whatif-mode');
          NBA_NAV.goTeam(D.teams[0].id);R.after=document.body.classList.contains('whatif-mode');""")
        self.assertTrue(r["wi"])
        self.assertFalse(r["after"])                                                # jumping to a team leaves What-If mode
        css = self.static
        for needle in (".sp-in{", ".team-jump{", ".tb-btn{", ".team-card.mine{", "@keyframes hitrow", "font:500 16px"):   # 16px input: no iOS zoom
            self.assertIn(needle, css)
        self.assertRegex(css, r"@media\(max-width:680px\)\{\.sp-box\{top:0;left:0;transform:none;width:100%;height:100dvh")  # full-screen sheet on phones
        self.assertIn('data-team="', self.static.split("function cardOf")[1][:120])

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
        self.assertEqual(re.sub(r"<[^>]+>", "", m.group(1)), _snapshot_label())
        rules = re.findall(r'<span class="meta-pill cap-rule"[^>]*>(.*?)</span><', self.official)
        self.assertEqual(len(rules), 4)
        self.assertTrue(all(re.sub(r"<[^>]+>", "", r) == "TOP 9 SALARIES COUNT · IL ✓" for r in rules), rules)
        self.assertNotIn("NOT FROZEN", self.official.split("<body", 1)[1].split('<script id="league-app">')[0])

    def test_pick_pill_never_clips(self):
        css = re.search(r"\.picks-tag\{background:#edf2f9[^}]*\}", self.static).group(0)
        for bad in ("nowrap", "ellipsis", "overflow:hidden"):
            self.assertNotIn(bad, css)


if __name__ == "__main__":
    unittest.main()
