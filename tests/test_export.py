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
        self.assertEqual(r["tabs"], 2)                                                     # teams 1-8 and 9-16
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
