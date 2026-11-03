"""Export hub: every view can be exported as an image, a link and chat-ready text. Driven in headless Chrome; expectations come from the data."""
import html as html_lib
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_live_feed as tlf  # noqa: E402
import test_scenario_rendering as tsr  # noqa: E402

INDEX = os.path.join(HERE, "..", "index.html")


@unittest.skipUnless(tsr._chrome(), "no Chrome")
class TestExportHub(unittest.TestCase):
    def drive(self, body_js, qs="", wait=2500):
        with open(INDEX, encoding="utf-8") as f:
            html = f.read()
        script = ("<script>(function(){var R={};setTimeout(function(){try{" + body_js + "}catch(e){R.error=String(e&&e.stack||e);}"
                  "setTimeout(function(){var p=document.createElement('pre');p.id='o';p.textContent=JSON.stringify(R);document.body.appendChild(p);},%d);},400);})();</script>" % wait)
        html = html[:html.rindex("</body>")] + script + html[html.rindex("</body>"):]
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, "index.html")
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            out = tsr._chrome_run(["--window-size=1000,1400", "--virtual-time-budget=12000", "--dump-dom", "file://" + path + qs], 150).stdout
        finally:
            shutil.rmtree(d)
        m = re.search(r'<pre id="o">(.*?)</pre>', out, re.S)
        self.assertIsNotNone(m, out[-300:])
        r = json.loads(html_lib.unescape(m.group(1)))
        self.assertNotIn("error", r, r.get("error"))
        return r

    def test_the_hub_lists_exports_and_each_has_an_image_a_link_and_text(self):
        r = self.drive("""
          var teams=NBA_NAV.D.teams.length;R.teams=teams;
          document.getElementById('tb-export').click();
          R.items=Array.prototype.map.call(document.querySelectorAll('#ex-hub .ex-item'),function(b){return b.getAttribute('data-ex');});
          document.querySelector('#ex-hub .ex-item[data-ex=rosters]').click();""")
        self.assertEqual(r["teams"], 16)
        for want in ("rosters", "cap", "standings"):
            self.assertIn(want, r["items"])

    def test_the_roster_export_draws_two_images_and_the_text_names_every_team_and_salary(self):
        r = self.drive("""
          document.getElementById('tb-export').click();
          document.querySelector('#ex-hub .ex-item[data-ex=rosters]').click();
          setTimeout(function(){var ov=document.getElementById('chk-imgov');R.ov=!!ov;if(!ov)return;
            R.tabs=ov.querySelectorAll('.imgov-t').length;var im=ov.querySelector('img.imgov-img');R.w=im.naturalWidth;R.h=im.naturalHeight;
            R.btns=Array.prototype.map.call(ov.querySelectorAll('.imgov-b'),function(b){return b.textContent;});},1800);""", wait=4000)
        self.assertTrue(r["ov"])
        self.assertEqual(r["tabs"], 4)                                                     # four teams an image, readable on a phone
        self.assertGreaterEqual(r["w"], 1080)
        self.assertGreater(r["h"], 1000)
        for label in ("Copy link", "Copy text", "Save"):
            self.assertIn(label, r["btns"])

    def test_every_catalog_item_and_every_team_builds_images_and_text(self):
        r = self.drive("""
          var cat=NBA_EXPORT.catalog();R.ids=cat.map(function(i){return i.id;});R.bad=[];R.texts={};
          cat.forEach(function(it){try{var pg=it.pages();if(!pg.length)R.bad.push(it.id+': empty');pg.forEach(function(p){if(!p.doc&&!p.cv)R.bad.push(it.id+': no doc');if(p.doc){var t=NBA_EXPORT.text(p.doc);if(!t||t.indexOf('undefined')>=0||t.indexOf('NaN')>=0)R.bad.push(it.id+': bad text');R.texts[it.id]=t;}});}catch(e){R.bad.push(it.id+': '+e);}});
          document.getElementById('tb-export').click();R.chips=document.querySelectorAll('#ex-hub .ex-teams .tp-btn').length;
          document.querySelector('#ex-hub .ex-teams .tp-btn').click();
          setTimeout(function(){var ov=document.getElementById('chk-imgov');R.ov=!!ov;},1800);""", wait=4000)
        for want in ("rosters", "cap", "trades", "il", "salaries", "picks"):
            self.assertIn(want, r["ids"])
        self.assertEqual(r["bad"], [])
        self.assertEqual(r["chips"], 16)                                                   # one chip per team
        self.assertTrue(r["ov"])
        self.assertIn("PLAYER", r["texts"]["salaries"])

    def test_the_trade_machine_proposal_is_an_export_with_three_images(self):
        r = self.drive("""
          var it=NBA_EXPORT.catalog().filter(function(i){return i.id==='trade';})[0];R.has=!!it;
          if(it){document.getElementById('tb-export').click();document.querySelector('#ex-hub .ex-item[data-ex=trade]').click();
            setTimeout(function(){var ov=document.getElementById('chk-imgov');R.tabs=ov?ov.querySelectorAll('.imgov-t').length:0;},2000);}""",
                       qs="?check=478.p.5432~franchise-01", wait=4500)
        self.assertTrue(r["has"])
        self.assertEqual(r["tabs"], 3)                                                     # proposal, teams after, both

    def test_text_is_derived_from_the_same_document(self):
        r = self.drive("""
          var item=NBA_EXPORT.catalog().filter(function(i){return i.id==='cap';})[0];
          var pg=item.pages()[0];R.text=NBA_EXPORT.text(pg.doc);R.link=item.link();""")
        data = json.loads(re.search(r'id="league-data">(.*?)</script>', open(INDEX, encoding="utf-8").read(), re.S).group(1).replace("<\\/", "</"))
        for t in data["teams"]:
            self.assertIn(t["short"], r["text"])
        self.assertEqual(r["text"].count("\n") >= 18, True)                                # title + header + 16 rows
        self.assertTrue(r["link"].endswith("#cap"))
        self.assertNotIn("$", r["text"])                                                   # house rule: no dollar signs, here too

    SMOKE = """
      var out=[];NBA_EXPORT.catalog().forEach(function(it){var r={id:it.id,pages:0,bad:[]};
        try{var ps=it.pages();r.pages=ps.length;ps.forEach(function(p){
          if(p.doc){var cv=NBA_EXPORT.canvas(p.doc);if(!(cv.width>=1000&&cv.height>200))r.bad.push('canvas '+cv.width+'x'+cv.height);
            [NBA_EXPORT.text(p.doc),NBA_EXPORT.list(p.doc)].forEach(function(t){if(/undefined|NaN|\\[object/.test(t))r.bad.push('text: '+t.slice(0,80));});}
          else if(!p.cv)r.bad.push('no doc and no canvas');});}catch(e){r.bad.push(String(e));}
        if(!r.pages)r.bad.push('no pages');out.push(r);});R.items=out;"""

    def _smoke(self, r):
        self.assertGreater(len(r["items"]), 5)
        for it in r["items"]:
            self.assertEqual(it["bad"], [], it["id"])

    def test_every_export_draws_and_reads_cleanly_in_the_official_view(self):
        self._smoke(self.drive(self.SMOKE))

    def test_every_export_draws_and_reads_cleanly_in_a_scenario(self):
        self._smoke(self.drive(self.SMOKE, qs="?mode=scenario"))

    def test_every_export_draws_and_reads_cleanly_in_keepers_mode(self):
        r = self.drive(self.SMOKE + "R.ids=R.items.map(function(i){return i.id;});", qs="?mode=whatif&view=keepers")
        self._smoke(r)
        self.assertTrue(any(i.startswith("kb-") for i in r["ids"]), r["ids"])

    def test_every_export_draws_and_reads_cleanly_with_a_live_feed(self):
        feed = json.dumps(tlf.feed()).replace("</", "<\\/")
        r = self.drive("NBA_LIVE.set(" + feed + ");" + self.SMOKE + "R.ids=R.items.map(function(i){return i.id;});")
        self._smoke(r)
        for want in ("live-standings", "live-matchups"):
            self.assertIn(want, r["ids"])

    def test_the_hub_groups_exports_puts_this_page_first_and_traps_focus(self):
        r = self.drive("""
          var b=document.getElementById('tb-export');b.focus();b.click();var hub=document.getElementById('ex-hub');
          R.heads=Array.prototype.map.call(hub.querySelectorAll('.ex-h'),function(x){return x.textContent;});
          var f=Array.prototype.filter.call(hub.querySelectorAll('button'),function(x){return x.offsetParent!==null;});
          f[f.length-1].focus();document.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true}));R.wrapped=hub.contains(document.activeElement);
          document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));R.closed=!document.getElementById('ex-hub');R.back=document.activeElement&&document.activeElement.id;""")
        self.assertTrue(r["heads"][0].endswith("this page"), r["heads"])
        self.assertIn("One team", r["heads"])
        self.assertTrue(r["wrapped"] and r["closed"])
        self.assertEqual(r["back"], "tb-export")                                     # focus returns to what opened it

    def test_from_the_rankings_board_the_hub_owns_tab_and_esc(self):
        r = self.drive("""
          NBA_WHATIF.openBoard();setTimeout(function(){document.getElementById('kbb-export').click();var hub=document.getElementById('ex-hub');R.hub=!!hub;
            var it=hub.querySelector('.ex-item');it.focus();document.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true}));R.stays=hub.contains(document.activeElement);
            document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));R.hubGone=!document.getElementById('ex-hub');R.boardStays=!!document.getElementById('kb-board');},300);""",
            qs="?mode=whatif&view=keepers", wait=2500)
        self.assertTrue(r["hub"] and r["stays"])
        self.assertTrue(r["hubGone"] and r["boardStays"])                            # Esc closed the export, not the board under it

    def test_saved_files_carry_the_date_links_keep_the_mode_and_there_is_a_list_text(self):
        r = self.drive("""
          document.getElementById('tb-export').click();document.querySelector('#ex-hub .ex-item[data-ex=cap]').click();
          setTimeout(function(){var ov=document.getElementById('chk-imgov');R.name=ov.querySelector('a[download]').getAttribute('download');
            R.btns=Array.prototype.map.call(ov.querySelectorAll('.imgov-b'),function(b){return b.textContent;});R.full=!!ov.querySelector('.imgov-full');
            R.alt=ov.querySelector('img').getAttribute('alt');},1800);
          R.link=NBA_EXPORT.catalog().filter(function(i){return i.id==='cap';})[0].link();""", qs="?mode=scenario", wait=4000)
        self.assertRegex(r["name"], r"^cap-table-\d{4}-\d{2}-\d{2}\.png$")
        self.assertIn("Copy as list", r["btns"])
        self.assertTrue(r["full"])
        self.assertGreater(len(r["alt"]), 40)                                         # the alt text carries the content, not just "Cap table"
        self.assertIn("mode=scenario", r["link"])                                     # the link opens the scenario the image shows

    def test_image_text_is_large_enough_to_read_when_a_phone_shrinks_it(self):
        with open(INDEX, encoding="utf-8") as f:
            src = f.read()
        body = src[src.index("function exRun(c,doc,draw,W){"):src.index("function exCanvas(doc){")]
        sizes = [int(x) for x in re.findall(r'"\d{3} (\d+)px "', body)]
        self.assertGreaterEqual(min(sizes), 20, sorted(set(sizes)))                   # 20px of 1080 is about 7px on a phone: the floor
