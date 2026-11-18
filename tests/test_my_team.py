"""The My team page and My team as the default across features."""
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
from _drive import drive_page  # noqa: E402

INDEX = os.path.join(HERE, "..", "index.html")


@unittest.skipUnless(tsr._chrome(), "no Chrome")
class TestMyTeam(unittest.TestCase):
    def drive(self, body_js, qs="", wait=2500, me="franchise-04"):
        pre = "<script>try{localStorage.setItem('nbaTalkVN.myTeam','%s')}catch(e){}</script>" % me if me else "<script>try{localStorage.removeItem('nbaTalkVN.myTeam')}catch(e){}</script>"
        return drive_page(body_js, qs=qs, wait=wait, start=600, size="1200,1400", budget=10000, head=pre)

    def test_the_star_opens_the_my_team_page_with_every_block(self):
        feed = json.dumps(tlf.feed()).replace("</", "<\\/")
        r = self.drive("NBA_LIVE.set(" + feed + ");document.getElementById('tb-me').click();"
                       "R.tab=document.querySelector('#me-page').classList.contains('tab-off');R.hash=location.hash;"
                       "R.heads=Array.prototype.map.call(document.querySelectorAll('#me-root .me-ch b'),function(b){return b.textContent;});R.card=!!document.querySelector('#me-root .me-card');"
                       "R.team=document.querySelector('#me-root .me-t b').textContent;")
        self.assertFalse(r["tab"])
        self.assertEqual(r["hash"], "#me")
        for want in ("Cap", "Trades and cooldowns", "This week", "Draft", "Roster"):
            self.assertIn(want, r["heads"])
        self.assertTrue(any(h.startswith("Keepers") for h in r["heads"]), r["heads"])
        self.assertTrue(r["card"])

    def test_view_as_changes_the_page_but_not_the_saved_team(self):
        r = self.drive("""document.getElementById('tb-me').click();var sel=document.querySelector('#me-root .me-sel');R.before=document.querySelector('#me-root .me-t .tchip').textContent;
          var other=Array.prototype.filter.call(sel.options,function(o){return o.value!=='franchise-04';})[0].value;sel.value=other;sel.dispatchEvent(new Event('change'));
          R.after=document.querySelector('#me-root .me-t .tchip').textContent;R.saved=localStorage.getItem('nbaTalkVN.myTeam');R.note=(document.querySelector('#me-root .me-note')||{}).textContent||'';
          R.back=!!Array.prototype.filter.call(document.querySelectorAll('#me-root .me-go'),function(b){return b.textContent==='Back to my team';})[0];""")
        self.assertNotEqual(r["before"], r["after"])
        self.assertEqual(r["saved"], "franchise-04")
        self.assertIn("Your saved team is still", r["note"])
        self.assertTrue(r["back"])

    def test_without_a_team_the_page_invites_you_to_choose_one(self):
        r = self.drive("window.location.hash='#me';setTimeout(function(){R.empty=!!document.querySelector('#me-root .me-empty');},400);", me=None, wait=3000)
        self.assertTrue(r["empty"])

    def test_cap_keepers_and_search_start_from_my_team(self):
        r = self.drive("""var g=document.querySelector('#cap .cap-grid');R.capFirst=g.firstChild.querySelector('.cap-team b').textContent.replace(/^\\W+/,'').trim();R.me=NBA_NAV.D.teams.filter(function(t){return t.id==='franchise-04';})[0].short;
          R.kb=NBA_WHATIF.plan('franchise-04')!==null;""")
        self.assertEqual(r["capFirst"], r["me"])
        self.assertTrue(r["kb"])

    def test_keepers_opens_on_my_team(self):
        r = self.drive("R.team=(document.querySelector('#wi-root .wi-kb-tm.on')||{}).title||'';R.me=NBA_NAV.D.teams.filter(function(t){return t.id==='franchise-04';})[0].name;", qs="?mode=whatif&view=keepers")
        self.assertEqual(r["team"], r["me"])


if __name__ == "__main__":
    unittest.main()
