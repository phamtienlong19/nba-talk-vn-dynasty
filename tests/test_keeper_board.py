"""Keeper board (What-If KEEPERS view): the stored rank -> salary table and the page behaviour, both derived from data."""
import html as html_lib
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, HERE)
import cap_model as cm  # noqa: E402
import keeper_rank_salary as krs  # noqa: E402
import test_scenario_rendering as tsr  # noqa: E402

ROOT = os.path.join(HERE, "..")
CFG = os.path.join(ROOT, "config", "keeper_salary_by_rank.json")
PLAYERS = os.path.join(ROOT, "data", "yahoo", "players_normalized.json")
INDEX = os.path.join(ROOT, "index.html")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestRankSalaryTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load(CFG)
        cls.players = load(PLAYERS)

    def test_the_table_is_the_sorted_dollar_curve(self):
        s = self.cfg["salaryByRank"]
        self.assertTrue(all(a >= b for a, b in zip(s, s[1:])), "salary never rises as rank gets worse")
        self.assertTrue(all(x > 0 for x in s))                                           # only paid ranks are listed; the rest are $0
        self.assertEqual(self.cfg["source"]["paidRanks"], len(s))
        self.assertEqual(len(self.cfg["order"]), len(set(self.cfg["order"])))

    def test_rank_follows_the_dollar_order_not_the_o_rank_column(self):
        by_key = {p["playerKey"]: p for p in self.players}
        gaps = [(abs(i + 1 - by_key[k]["oRank"]), k) for i, k in enumerate(self.cfg["order"][:len(self.cfg["salaryByRank"])]) if k in by_key]
        gap, key = max(gaps)
        self.assertGreater(gap, 5, "the Yahoo snapshot has no player whose O-Rank and dollar rank disagree")
        rank = self.cfg["order"].index(key) + 1
        self.assertEqual(self.cfg["salaryByRank"][rank - 1], by_key[key]["capDollars"])  # his salary is the one at his ACTUAL rank
        self.assertNotEqual(by_key[key]["oRank"], rank)

    def test_table_matches_the_cap_model_band(self):
        m = cm.compute_cap_model(self.players)
        self.assertEqual(self.cfg["capModel"]["top144Sum"], m["top144Sum"])
        self.assertEqual(sum(self.cfg["salaryByRank"][:144]), m["top144Sum"])         # the band depends only on the curve: re-ranking never moves it

    def test_committed_table_is_rebuilt_from_the_current_snapshot(self):
        prov = load(os.path.join(ROOT, "data", "yahoo", "provenance.json"))
        if prov.get("fetchedAt") != self.cfg["source"]["fetchedAt"]:
            self.skipTest("Yahoo snapshot has moved on: run scripts/keeper_rank_salary.py and commit the new table")
        self.assertEqual(krs.build(self.players, {k: self.cfg["source"][k] for k in ("file", "fetchedAt", "league")}), self.cfg)

    def test_ties_break_by_o_rank_then_name(self):
        rows = krs.ranked([{"playerKey": "a", "name": "B", "capDollars": 5.0, "oRank": 2}, {"playerKey": "b", "name": "A", "capDollars": 5.0, "oRank": 1},
                           {"playerKey": "c", "name": "C", "capDollars": 9.0, "oRank": 3}])
        self.assertEqual([r["playerKey"] for r in rows], ["c", "b", "a"])
        with self.assertRaises(krs.RankSalaryError):
            krs.ranked([{"playerKey": "a", "name": "A", "capDollars": 5.0, "oRank": 1}, {"playerKey": "a", "name": "B", "capDollars": 4.0, "oRank": 2}])


@unittest.skipUnless(tsr._chrome(), "no Chrome")
class TestKeeperBoardPage(unittest.TestCase):
    def drive(self, body_js, hash_="", qs="?mode=whatif&view=keepers", head_js=""):
        with open(INDEX, encoding="utf-8") as f:
            html = f.read()
        script = ("<script>(function(){var R={};setTimeout(function(){try{" + body_js + "}catch(e){R.error=String(e&&e.stack||e);}"
                  "var p=document.createElement('pre');p.id='o';p.textContent=JSON.stringify(R);document.body.appendChild(p);},700);})();</script>")
        if head_js:
            html = html.replace("<head>", "<head><script>" + head_js + "</script>", 1)
        html = html[:html.rindex("</body>")] + script + html[html.rindex("</body>"):]
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, "index.html")
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            out = tsr._chrome_run(["--window-size=1000,1600", "--virtual-time-budget=8000", "--dump-dom", "file://" + path + qs + (hash_ if qs == "" else "")], 120).stdout
        finally:
            shutil.rmtree(d)
        m = re.search(r'<pre id="o">(.*?)</pre>', out, re.S)
        self.assertIsNotNone(m, out[-300:])
        r = json.loads(html_lib.unescape(m.group(1)))
        self.assertNotIn("error", r, r.get("error"))
        return r

    SETUP = """
      var W=JSON.parse(document.getElementById('whatif-data').textContent).keeperBoard,cfgS=W.salaryByRank;
      var rowsEl=function(){return Array.prototype.slice.call(document.querySelectorAll('#wi-root .wi-kb tbody tr'));};
      var info=function(){return rowsEl().map(function(tr){return {k:tr.getAttribute('data-k'),rank:+tr.querySelector('.wi-kb-rk').value,sal:+tr.querySelector('td.num span').textContent,off:/autooff/.test(tr.className),kept:/(^| )kept( |$)/.test(tr.className)};});};
      var ev=function(el,t){el.dispatchEvent(new Event(t));};
    """

    @staticmethod
    def board():
        with open(INDEX, encoding="utf-8") as f:
            return json.loads(re.search(r'id="whatif-data">(.*?)</script>', f.read(), re.S).group(1).replace("<\\/", "</"))["keeperBoard"]

    @staticmethod
    def ranking(board, pins):
        """Reference implementation of the page's ranking: pins sit at exactly their rank, everyone else keeps Yahoo's order."""
        uni = list(board["order"])
        seen = set(uni)
        for t in board["teams"]:
            for p in sorted(t["players"], key=lambda p: p["n"]):
                if p["k"] not in seen:
                    seen.add(p["k"])
        extra = sorted({p["k"]: p["n"] for t in board["teams"] for p in t["players"] if p["k"] not in set(board["order"])}.items(), key=lambda kv: kv[1])
        uni += [k for k, _ in extra]
        pinned = {k for k, _ in pins}
        lst = [k for k in uni if k not in pinned]
        for idx, (k, q) in sorted(enumerate(pins), key=lambda x: (x[1][1], x[0])):
            lst.insert(min(max(q, 1), len(lst) + 1) - 1, k)
        return {k: i + 1 for i, k in enumerate(lst)}

    @staticmethod
    def fit(board, team, intent, rank):
        """Reference for the automatic adjustment: fewest players off, then fewest needing review, then the worst-ranked, never a never-drop player."""
        import itertools
        sal = lambda k: (board["salaryByRank"] + [0] * 1000)[rank[k] - 1]  # noqa: E731
        ceiling = board["band"]["ceiling"]
        pay = lambda ks: sum(sal(k) for k in ks)  # noqa: E731
        if pay(intent) <= ceiling:
            return []
        cand = [k for k in intent if 0 < sal(k) < board["neverDrop"]]
        best = None
        for n in range(1, len(cand) + 1):
            for pick in itertools.combinations(cand, n):
                if pay([k for k in intent if k not in pick]) > ceiling:
                    continue
                score = (n, sum(1 for k in pick if sal(k) >= board["reviewFrom"]), -sum(rank[k] for k in pick), ",".join(sorted(pick)))
                if best is None or score < best[0]:
                    best = (score, pick)
            if best:
                break
        return list(best[1]) if best else None

    def test_salaries_follow_rank_and_a_rerank_shifts_them(self):
        r = self.drive(self.SETUP + """
          var a=info();R.n=a.length;R.ok=a.every(function(x){return x.sal===(cfgS[x.rank-1]||0);});
          R.sorted=a.every(function(x,i){return i===0||a[i-1].rank<=x.rank;});
          var first=a[0];var inp=document.querySelector('#wi-root .wi-kb tbody tr .wi-kb-rk');inp.value='200';ev(inp,'change');
          var b=info();R.moved=b.filter(function(x){return x.k===first.k;})[0];R.ok2=b.every(function(x){return x.sal===(cfgS[x.rank-1]||0);});
          R.url=location.search;""")
        self.assertGreater(r["n"], 5)
        self.assertTrue(r["ok"])
        self.assertTrue(r["sorted"])
        self.assertEqual(r["moved"]["rank"], 200)                                          # pinned to exactly the rank asked for
        self.assertEqual(r["moved"]["sal"], 0)                                             # beyond the paid ranks
        self.assertTrue(r["ok2"])
        self.assertIn("rk=" + r["moved"]["k"].split(".")[-1] + ":200", r["url"])                          # and the URL remembers it

    def test_keepers_are_capped_and_remembered(self):
        r = self.drive(self.SETUP + """
          var boxes=function(){return Array.prototype.slice.call(document.querySelectorAll('#wi-root .wi-kb tbody input[type=checkbox]'));};
          var n=boxes().length;for(var i=0;i<Math.min(n,12);i++){var b=boxes()[i];if(!b.disabled){b.checked=true;ev(b,'change');}}
          R.picked=boxes().filter(function(b){return b.checked;}).length;R.max=W.keeperMax;
          R.ls=localStorage.getItem('nbaTalkVN.keeperBoard');R.url=location.search;""")
        self.assertLessEqual(r["picked"], r["max"])                                        # a tenth keeper cannot be ticked
        self.assertIn("keep=", r["url"])
        self.assertIn('"keep"', r["ls"])

    def test_unkept_player_warnings_wait_until_a_keeper_is_chosen(self):
        r = self.drive(self.SETUP + """
          R.none=document.querySelectorAll('#wi-root .wi-kb-flag').length;""")
        self.assertEqual(r["none"], 0)                                                     # nothing chosen yet: no wall of warnings

    def test_a_shared_link_restores_the_plan_and_reset_clears_it(self):
        board = self.board()
        team = board["teams"][0]
        k1, k2 = team["players"][0]["k"], team["players"][1]["k"]
        r = self.drive(self.SETUP + """
          R.checked=Array.prototype.slice.call(document.querySelectorAll('#wi-root .wi-kb tbody tr.kept')).map(function(t){return t.getAttribute('data-k');});
          R.ranks=info().filter(function(x){return x.k==='%s';})[0];
          document.getElementById('kb-reset').click();document.getElementById('kb-reset').click();R.after=info().filter(function(x){return x.k==='%s';})[0];""" % (k1, k1),
                       qs="?mode=whatif&view=keepers&team=%s&keep=%s,%s&rk=%s:77" % (team["id"], k1, k2, k1))
        self.assertEqual(sorted(r["checked"]), sorted([k1, k2]))
        self.assertEqual(r["ranks"]["rank"], 77)
        self.assertNotEqual(r["after"]["rank"], 77)                                        # reset returns him to Yahoo's order

    def test_the_keepers_link_is_a_front_door_to_the_view(self):
        r = self.drive("""
          var a=document.querySelector('.navkeep');R.has=!!a;a.click();
          R.mode=document.body.classList.contains('whatif-mode');R.hd=!!document.querySelector('#wi-root .wi-kb-hd');R.on=a.classList.contains('on');R.hash=location.hash;""",
                       qs="")
        self.assertTrue(r["has"] and r["mode"] and r["hd"] and r["on"])
        self.assertEqual(r["hash"], "#keepers")
        r2 = self.drive("R.mode=document.body.classList.contains('whatif-mode');R.hd=!!document.querySelector('#wi-root .wi-kb-hd');", qs="", hash_="#keepers")
        self.assertTrue(r2["mode"] and r2["hd"])                                           # a bookmarked #keepers opens it directly

    def test_auto_fit_takes_the_fewest_players_off_and_matches_the_reference(self):
        board = self.board()
        base = self.ranking(board, [])
        top9 = lambda t: sorted((base[p["k"]] for p in t["players"]))[:9]  # noqa: E731
        def default_pay(t):
            sal = lambda k: (board["salaryByRank"] + [0] * 1000)[base[k] - 1]  # noqa: E731
            return sum(sorted((sal(p["k"]) for p in t["players"]), reverse=True)[:9])
        ceiling = board["band"]["ceiling"]
        found = None
        for team in board["teams"]:                                                        # a plan one rank move pushes over the ceiling, yet still fixable
            intent = [p["k"] for p in sorted(team["players"], key=lambda p: base[p["k"]])][:9]
            for mover in reversed(intent):
                for target in range(3, 61):
                    rank = self.ranking(board, [(mover, target)])
                    sal = lambda k: (board["salaryByRank"] + [0] * 1000)[rank[k] - 1]  # noqa: E731
                    if sum(sal(k) for k in intent) > ceiling:
                        expected = self.fit(board, team, intent, rank)
                        if expected:
                            found = (team, intent, mover, target, rank, expected)
                            break
                if found:
                    break
            if found:
                break
        if not found:
            self.skipTest("no roster can be pushed over the ceiling by one move and still be fixed automatically")
        team, intent, mover, target, rank, expected = found
        qs = "?mode=whatif&view=keepers&team=%s&keep=%s&rk=%s:%d" % (team["id"], ",".join(intent), mover, target)
        r = self.drive(self.SETUP + """
          var a=info();R.off=a.filter(function(x){return x.off;}).map(function(x){return x.k;});R.kept=a.filter(function(x){return x.kept;}).reduce(function(n,x){return n+x.sal;},0);
          R.tag=document.querySelectorAll('#wi-root .wi-kb-tag.auto').length;R.strip=document.querySelector('#wi-root .wi-kb-tm.on i.auto')?document.querySelector('#wi-root .wi-kb-tm.on i.auto').textContent:'';
          R.banner=document.querySelector('#wi-root .wi-kb-flag.warn')?document.querySelector('#wi-root .wi-kb-flag.warn').textContent:'';""", qs=qs)
        self.assertEqual(sorted(r["off"]), sorted(expected))                               # same fewest-change choice as the reference
        self.assertLessEqual(r["kept"], board["band"]["ceiling"])
        self.assertEqual(r["tag"], len(expected))
        self.assertEqual(r["strip"], "−%d" % len(expected))
        self.assertIn("Auto-left out", r["banner"])
        off = self.drive(self.SETUP + """
          R.flag=document.querySelector('#wi-root .wi-kb-flag.bad')?document.querySelector('#wi-root .wi-kb-flag.bad').textContent:'';R.offn=info().filter(function(x){return x.off;}).length;""", qs=qs + "&fit=0")
        self.assertEqual(off["offn"], 0)                                                   # with the switch off nothing is removed ...
        self.assertIn("Over by", off["flag"])                                     # ... and the breach is flagged instead

    def test_one_rank_move_reprices_every_player_in_between_on_every_team(self):
        board = self.board()
        team = board["teams"][0]
        base = self.ranking(board, [])
        victim = max(team["players"], key=lambda p: base[p["k"]] if base[p["k"]] > 40 and base[p["k"]] < 130 else 0)
        k, frm = victim["k"], base[victim["k"]]
        after = self.ranking(board, [(k, 30)])
        sal = lambda rk: (board["salaryByRank"] + [0] * 1000)[rk - 1]  # noqa: E731
        changed = [(t["id"], p["k"]) for t in board["teams"] for p in t["players"] if sal(base[p["k"]]) != sal(after[p["k"]])]
        r = self.drive(self.SETUP + """
          var inp=document.querySelector('#wi-root .wi-kb tbody tr[data-k="%s"] .wi-kb-rk');inp.value='30';ev(inp,'change');
          var d=document.querySelector('#wi-root .wi-kb-rip');R.sum=d?d.querySelector('summary').textContent:'';R.lines=d?d.querySelectorAll('.wi-kb-rl').length:0;
          R.lt=document.querySelectorAll('#wi-root .wi-kb-lt tbody tr').length;""" % k)
        self.assertEqual(r["lt"], 16)
        self.assertIn("re-priced %d player" % len(changed), r["sum"])
        self.assertIn("on %d team" % len({t for t, _ in changed}), r["sum"])
        self.assertEqual(r["lines"], len({t for t, _ in changed}))                         # one line per affected team
        self.assertGreater(len({t for t, _ in changed}), 1) if len({t for t, _ in changed}) > 1 else None

    def test_import_a_link_a_code_or_a_list_then_tweak_without_touching_the_original(self):
        board = self.board()
        team = board["teams"][0]
        k1, k2, k3 = [p["k"] for p in team["players"][:3]]
        n1, n2 = team["players"][0]["n"], team["players"][1]["n"]
        short = lambda k: k.split(".")[-1]  # noqa: E731
        r = self.drive(self.SETUP + """
          var imp=function(text,label){document.getElementById('kb-import-btn').click();var ta=document.getElementById('kb-paste');ta.value=text;document.getElementById('kb-label').value=label||'';document.getElementById('kb-do').click();};
          var rk=function(k){var x=info().filter(function(y){return y.k===k;})[0];return x?x.rank:null;};
          imp(%s,'Code ranking');R.code=[rk('%s'),rk('%s')];R.opts1=document.querySelectorAll('#kb-set option').length;
          var tweak=document.querySelector('#wi-root .wi-kb tbody tr[data-k="%s"] .wi-kb-rk');tweak.value='9';ev(tweak,'change');R.tweaked=rk('%s');
          R.sub=document.querySelector('#wi-root .wi-kb-sub').textContent;R.hasReset=!!document.getElementById('kb-reset');
          document.getElementById('kb-reset').click();document.getElementById('kb-reset').click();R.reset=rk('%s');
          var sel=document.getElementById('kb-set');sel.value='mine';ev(sel,'change');R.mine=rk('%s');R.mineMoves=document.querySelector('#kb-set option[value=mine]').textContent;
          imp(%s,'Pasted');R.list=[rk('%s'),rk('%s')];R.msg=document.querySelector('#wi-root .wi-kb-msg')?document.querySelector('#wi-root .wi-kb-msg').textContent:'';
          imp(%s,'');R.link=rk('%s');R.labels=Array.prototype.map.call(document.querySelectorAll('#kb-set option'),function(o){return o.textContent;});
          R.url=location.search;""" % (json.dumps("KR1:%s=2,%s=5" % (short(k1), short(k2))), k1, k2, k1, k1, k1, k1, json.dumps("1. %s\n2. %s" % (n1, n2)), k1, k2,
                                           json.dumps("https://example.test/?mode=whatif&view=keepers&rk=%s:3&rn=Friend%%20Ranking" % short(k1)), k1))
        self.assertEqual(r["code"], [2, 5])                                                # a ranking code lands exactly
        self.assertEqual(r["opts1"], 2)                                                    # as its own set next to mine
        self.assertEqual(r["tweaked"], 9)                                                  # tweaking edits the imported copy
        self.assertIn("1 tweaked", r["sub"])
        self.assertTrue(r["hasReset"])
        self.assertEqual(r["reset"], 2)                                                    # "Reset to imported" goes back to what the friend sent
        self.assertNotEqual(r["mine"], 2)                                                  # my own ranking was never touched
        self.assertTrue(r["mineMoves"].startswith("My ranking"))
        self.assertEqual(r["list"], [1, 2])                                                # a pasted list ranks in the order given
        self.assertIn("Imported 2 ranked players", r["msg"])
        self.assertEqual(r["link"], 3)                                                     # a pasted link carries its pins and its name
        self.assertTrue(any(x.startswith("Friend Ranking") for x in r["labels"]))
        self.assertIn("rn=Friend%20Ranking", r["url"])

    def top9(self, board, team, rank):
        sal = lambda k: (board["salaryByRank"] + [0] * 1000)[rank[k] - 1]  # noqa: E731
        return sum(sorted((sal(p["k"]) for p in team["players"]), reverse=True)[:board["keeperMax"]])

    def test_the_board_lists_every_ranked_player_and_the_16_caps_move_with_an_edit(self):
        board = self.board()
        base = self.ranking(board, [])
        team = board["teams"][3]
        k = max((p["k"] for p in team["players"]), key=lambda x: base[x] if base[x] < 120 else 0)
        after = self.ranking(board, [(k, 5)])
        want = [self.top9(board, t, after) for t in board["teams"]]
        before = [self.top9(board, t, base) for t in board["teams"]]
        r = self.drive(self.SETUP + """
          document.getElementById('kb-board-btn').click();
          var pays=function(){return Array.prototype.map.call(document.querySelectorAll('#kb-board .kbb-pay'),function(e){return +e.textContent;});};
          R.rows=document.querySelectorAll('#kb-board .kbb-row').length;R.before=pays();
          var inp=document.querySelector('#kb-board .kbb-row[data-k="%s"] .kbb-rk');inp.value='5';ev(inp,'change');
          R.after=pays();R.last=document.querySelector('#kb-board .kbb-last').textContent;R.moved=document.querySelectorAll('#kb-board .kbb-row.moved').length;
          R.rank=+document.querySelector('#kb-board .kbb-row[data-k="%s"] .kbb-rk').value;
          document.getElementById('kbb-team').value='%s';ev(document.getElementById('kbb-team'),'change');R.filtered=document.querySelectorAll('#kb-board .kbb-row').length;
          document.querySelector('#kb-board .kbb-x').click();R.closed=!document.getElementById('kb-board');""" % (k, k, team["id"]))
        self.assertGreaterEqual(r["rows"], 300)                                            # every ranked player is on the board
        self.assertEqual(r["before"], before)
        self.assertEqual(r["after"], want)                                                 # all 16 caps follow the edit, matching the reference
        self.assertNotEqual(r["after"], r["before"])
        self.assertEqual(r["rank"], 5)
        self.assertEqual(r["moved"], 1)
        self.assertIn("re-priced", r["last"])
        self.assertEqual(r["filtered"], len(team["players"]))                              # the team filter shows just that roster
        self.assertTrue(r["closed"])

    def test_dropping_a_row_onto_another_gives_the_dragged_player_that_rank(self):
        board = self.board()
        team = board["teams"][0]
        k = team["players"][2]["k"]
        r = self.drive(self.SETUP + """
          document.getElementById('kb-board-btn').click();
          var rows=document.querySelectorAll('#kb-board .kbb-row');var src=document.querySelector('#kb-board .kbb-row[data-k="%s"]'),dst=rows[7];
          var target=+dst.querySelector('.kbb-rk').value;ev(src,'dragstart');ev(dst,'dragover');ev(dst,'drop');
          R.target=target;R.rank=+document.querySelector('#kb-board .kbb-row[data-k="%s"] .kbb-rk').value;""" % (k, k))
        self.assertEqual(r["rank"], r["target"])

    def test_keepers_exports_cover_the_plan_the_league_and_the_ranking(self):
        board = self.board()
        team = board["teams"][0]
        k1 = team["players"][0]["k"]
        r = self.drive(self.SETUP + """
          document.getElementById('tb-export').click();
          R.ids=Array.prototype.map.call(document.querySelectorAll('#ex-hub .ex-item'),function(b){return b.getAttribute('data-ex');});
          var cat=NBA_EXPORT.catalog();var get=function(id){return cat.filter(function(i){return i.id===id;})[0];};
          var texts={};['kb-team','kb-all','kb-league','kb-rank'].forEach(function(id){var it=get(id);texts[id]={pages:it.pages().length,text:it.pages().map(function(p){return NBA_EXPORT.text(p.doc);}).join('\\n'),link:it.link()};});
          R.texts=texts;""", qs="?mode=whatif&view=keepers&team=%s&keep=%s&rk=%s:12&rn=Hai%%20ranking" % (team["id"], k1, k1))
        for want in ("kb-team", "kb-all", "kb-league", "kb-rank", "rosters", "cap"):
            self.assertIn(want, r["ids"])
        self.assertEqual(r["texts"]["kb-all"]["pages"], 2)
        self.assertEqual(r["texts"]["kb-rank"]["pages"], 2)                                # top 60, plus the players I moved
        for t in board["teams"]:
            self.assertIn(t["short"], r["texts"]["kb-league"]["text"])
        self.assertIn("YOUR ASSUMPTION", r["texts"]["kb-team"]["text"])                    # an export is never mistaken for an official record
        self.assertIn("rk=%s:12" % k1.split(".")[-1], r["texts"]["kb-rank"]["link"])                      # the link rebuilds the same ranking
        self.assertIn("rn=Hai%20ranking", r["texts"]["kb-rank"]["link"])
        self.assertNotIn("$", "".join(v["text"] for v in r["texts"].values()))

    def test_adversarial_inputs_are_ignored_confirmed_or_reported(self):
        board = self.board()
        team = board["teams"][0]
        k = team["players"][0]["k"]
        short = k.split(".")[-1]
        r = self.drive(self.SETUP + """
          var inp=document.querySelector('#wi-root .wi-kb tbody tr .wi-kb-rk');var before=inp.value;
          inp.value='';ev(inp,'change');R.blankKept=document.querySelector('#wi-root .wi-kb tbody tr .wi-kb-rk').value===before;   /* a blank entry is not a move to rank 1 */
          inp=document.querySelector('#wi-root .wi-kb tbody tr .wi-kb-rk');inp.value='abc';ev(inp,'change');R.junkKept=document.querySelector('#wi-root .wi-kb tbody tr .wi-kb-rk').value===before;
          R.nc=document.querySelector('#wi-root .wi-kb-nc')?document.querySelector('#wi-root .wi-kb-nc').textContent:'';
          document.getElementById('kb-import-btn').click();document.getElementById('kb-paste').value='KR1:%s=3,99999999=4,notaplayer=5';document.getElementById('kb-do').click();
          R.msg=document.querySelector('#wi-root .wi-kb-msg')?document.querySelector('#wi-root .wi-kb-msg').textContent:'';
          var rs=document.getElementById('kb-reset');rs.click();R.armed=rs.textContent;R.stillMoved=document.querySelectorAll('#wi-root .wi-kb-rkc.moved').length;
          R.url=location.search;""" % short)
        self.assertTrue(r["blankKept"])
        self.assertTrue(r["junkKept"])
        self.assertIn("Not checked here", r["nc"])                                         # compliant is not the same as approved
        self.assertIn("2 entries not recognised", r["msg"])                                # unknown players in a code are reported, not silently dropped
        self.assertIn("Click again", r["armed"])                                           # one stray tap cannot wipe a ranking
        self.assertGreaterEqual(r["stillMoved"], 0)

    def test_rank_change_and_cap_change_are_separate_columns_with_different_looks(self):
        board = self.board()
        team = board["teams"][0]
        k = team["players"][0]["k"]
        r = self.drive(self.SETUP + """
          document.getElementById('kb-board-btn').click();var inp=document.querySelector('#kb-board .kbb-row[data-k="%s"] .kbb-rk');inp.value='3';ev(inp,'change');
          var row=document.querySelector('#kb-board .kbb-row[data-k="%s"]');
          R.heads=Array.prototype.map.call(document.querySelectorAll('#kb-board .kbb-head span'),function(e){return e.textContent;}).filter(Boolean);
          R.rd=row.querySelector('.kbb-rd').textContent;R.cd=row.querySelector('.kbb-cd').textContent;R.sal=row.querySelector('.kbb-sal').textContent;
          R.rdCls=row.querySelector('.kbb-rd').className;R.cdCls=row.querySelector('.kbb-cd').className;R.same=row.querySelector('.kbb-rd').parentNode===row.querySelector('.kbb-cd').parentNode;
          R.headRows=document.querySelectorAll('#kb-board .kbb-row.kbb-head').length;""" % (k, k))
        for h in ("RANK", "VS YAHOO", "CAP", "CAP Δ"):
            self.assertIn(h, r["heads"])
        self.assertRegex(r["rd"], r"^[▲▼] \d+$")                                           # rank change is an arrow pill ...
        self.assertRegex(r["cd"], r"^[+−-]\d+$")                                           # ... cap change is a signed number in its own column
        self.assertNotEqual(r["rdCls"].split()[0], r["cdCls"].split()[0])
        self.assertTrue(r["same"])
        self.assertEqual(r["headRows"], 0)
