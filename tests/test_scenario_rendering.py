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
            want = f"{rep['toFloor']:g} TO FLOOR" if rep["toFloor"] > 0 else f"{rep['room']:g} ROOM"
            self.assertEqual(c["gap"], want, shorts[fid])
        melo = cards["franchise-03"]
        self.assertEqual(melo["picks"], "2.03 · 2.15 · 3.04")      # Melo holds LC's 3.04 (commissioner clarification, TRADE-D-AMEND)

    def test_untraded_teams_keep_their_keepers_and_add_only_draftees(self):
        drafted = {c["name"] for c in ls.draft_summary(self.i, self.state)["completed"]}
        pre = {f for t in self.i["trades"]["trades"] for f in t["participants"]}
        view = ss.season_view(self.si)["teams"]
        quiet = [self.si["shorts"][f] for f in self.si["franchises"]
                 if f not in pre and not view[f]["added"] and not view[f]["dropped"] and not view[f]["fold"]["tradeIds"]]
        self.assertTrue(quiet, "every team has moved since the draft; this check has nothing to compare")
        for short in quiet:   # no pre-draft trade, no in-season trade, no Yahoo add/drop: keepers + draftees only
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
        self.assertIn('<div class="pname"><span class="st-chip st-out" title="Out (Yahoo)" aria-label="Out">OUT</span>Jordan Miller', miller)  # status chip on the left
        self.assertIn("tr-tag", row("Bsy", "Nikola Jokić"))                  # trade acquisition keeps ⇄
        mv = re.sub(r"<[^>]+>", " ", re.search(r'<div class="mv">(.*?)</details>', _card(self.official, "Bsy"), re.S).group(1))
        self.assertRegex(mv, r"ADDED\s.*Jordan Miller")
        self.assertRegex(mv, r"DROPPED\s.*Zaccharie Risacher")
        q = row("sup fam", "Jayden Quaintance")                              # unlisted salary: $0 by league rule
        self.assertIn('<div class="pos">PF</div>', q)
        self.assertIn('<div class="nba">SAS</div>', q)
        self.assertIn('class="st-chip st-out"', q)                           # on IL and Out on Yahoo

    def test_injured_list_is_its_own_group_at_the_foot_of_the_roster(self):
        for short in ("Bsy", "sup fam", "CrazyCat", "LC", "Maxfixe", "DonTrick"):
            card = _card(self.official, short)
            players = re.search(r'<div class="players[^"]*">(.*)', card, re.S).group(1)
            head = players.find('class="il-head"')
            self.assertGreater(head, 0, short)
            before, after = players[:head], players[head:]
            self.assertNotIn("il-row", before, short)                        # healthy players first
            self.assertEqual(after.count('class="player-row'), after.count("il-row"), short)  # only IL rows below
        view = ss.season_view(self.si)["teams"]
        seen_counting = seen_free = False
        for fid, v in view.items():
            card = _card(self.official, self.si["shorts"][fid])
            if not v["il"]:
                self.assertNotIn("il-head", card, fid)
                continue
            txt = re.sub(r"<[^>]+>", " ", card)
            if v["ilCap"]:                                                   # an IL player inside the counted nine: group says so
                seen_counting = True
                self.assertRegex(card, r'class="il-c"[^>]*>' + re.escape(f"{v['ilCap']:g}") + r" counted<", fid)
                self.assertRegex(txt, r"healthy\s+" + re.escape(f"{v['healthyCap']:g}"), fid)
            else:                                                            # IL players all outside the nine: no counted note, no healthy figure
                seen_free = True
                self.assertNotIn('class="il-c"', card, fid)
                self.assertNotIn("healthy", txt.split("moves")[0], fid)
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
        for cls, color in (("st-p", "#17734c"), ("st-q", "#1f5fbf"), ("st-d", "#b45a09"), ("st-inj", "#b3261e")):
            self.assertIn(f".st-chip.{cls}{{color:{color}", css)
        self.assertIn(".st-chip.st-out{color:#fff;background:#c9362d}", css)   # out: solid red
        self.assertIn(".st-chip.st-ofs{color:#fff;background:#1d2330}", css)   # out for the season: ink
        self.assertIn('OFS:["OFS","Out for the season","ofs"]', css)
        self.assertIn('INJ:["INJ","Injured","inj"]', css)
        self.assertIn('D:["D","Doubtful","d"]', css)

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
            tag = re.search(r'<span class="stand-tag low"[^>]*>(.*?)</span></span>(?=<span class="chip)', _card(dom, "TT"), re.S)
            self.assertEqual(txt(tag.group(1)), "16th70–130–3")
            self.assertIn('class="so on">STANDINGS ↓', a)
            dom2 = _dump("file://" + path + "?order=team")                    # toggle back to team number
            a2 = dom2.split('id="rosters-a"')[1].split('id="rosters-b"')[0]
            self.assertTrue(txt(a2).startswith(">TEAMS 1–8"))
            self.assertEqual(re.findall(r'<span class="identity-tag">([^<]*)</span>', a2)[0], "Bsy")
            self.assertIn('class="so on">TEAM #', a2)
        finally:
            shutil.rmtree(d)

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
        self.assertTrue(all(re.sub(r"<[^>]+>", "", r) == "TOP 9 $ COUNT · IL ✓" for r in rules), rules)
        self.assertNotIn("NOT FROZEN", self.official.split("<body", 1)[1].split('<script id="league-app">')[0])

    def test_pick_pill_never_clips(self):
        css = re.search(r"\.picks-tag\{background:#edf2f9[^}]*\}", self.static).group(0)
        for bad in ("nowrap", "ellipsis", "overflow:hidden"):
            self.assertNotIn(bad, css)


if __name__ == "__main__":
    unittest.main()
