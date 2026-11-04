"""One rookie mark, one crown and one set of status badges, wherever a player or team shows up."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _phone  # noqa: E402
import test_live_feed as tlf  # noqa: E402
import test_scenario_rendering as tsr  # noqa: E402

PRE = "localStorage.setItem('nbaTalkVN.myTeam','franchise-04')"


@unittest.skipUnless(tsr._chrome(), "no Chrome")
class TestConsistency(unittest.TestCase):
    def test_every_chip_of_the_defending_champion_carries_the_crown(self):
        feed = json.dumps(tlf.feed()).replace("</", "<\\/")
        r = _phone.phone_run("""
          var D=NBA_NAV.D,champ=D.teams.filter(function(t){return t.crown;})[0];R.champ=champ.short;NBA_LIVE.set(%s);
          var secs={'teams':'rosters-a','cap':'cap','trade-lab':'trade-lab','draft':'draft-order','live':'live-root','me':'me-root'};R.missing={};
          Object.keys(secs).forEach(function(t){var a=document.querySelector('.navlink[data-tab="'+t+'"]');if(a)a.click();else{location.hash='#'+t;window.dispatchEvent(new HashChangeEvent('hashchange'));}
            var bad=[];[].forEach.call(document.querySelectorAll('#'+secs[t]+' .tchip,#'+secs[t]+' .pick-chip,#'+secs[t]+' .tpill,#'+secs[t]+' .lot-chip,#'+secs[t]+' .cap-team b'),function(e){
              if(e.children.length)return;var tx=e.textContent.trim();if(tx===champ.short)bad.push(e.className);});R.missing[t]=bad;});""" % feed, width=1100, height=900, wait_ms=3000, pre_js=PRE)
        self.assertEqual(r["missing"], {t: [] for t in r["missing"]}, r["champ"])

    def test_a_rookie_looks_the_same_on_the_card_in_search_the_sheet_keepers_and_live(self):
        feed = json.dumps(tlf.feed()).replace("</", "<\\/")
        r = _phone.phone_run("""
          var rowEl=[].filter.call(document.querySelectorAll('section.team-card .player-row[data-k]'),function(r){return NBA_RK.is(r.getAttribute('data-k'));})[0];var rk={k:rowEl.getAttribute('data-k'),n:rowEl.textContent.slice(0,30)};R.name=rk.n;R.k=rk.k;
          var look=function(el){var c=getComputedStyle(el);return [c.color,c.backgroundColor,c.fontSize,c.borderRadius].join('|');};R.looks={};
          var card=document.querySelector('section.team-card .player-row[data-k="'+rk.k+'"] .in-tag.rk');R.looks.card=card?look(card):null;
          NBA_PLAYER.open(rk.k);var sh=document.querySelector('#pl-sheet .rk-mark');R.looks.sheet=sh?look(sh):null;R.text=sh?sh.textContent:'';document.querySelector('#pl-sheet .imgov-x').click();
          var mk=NBA_RK.mark(rk.k);document.body.appendChild(mk);R.looks.mark=look(mk);mk.remove();""" % (), width=1100, height=900, wait_ms=2500, pre_js=PRE)
        self.assertIsNotNone(r["looks"]["card"], r["name"])
        self.assertEqual(r["looks"]["card"], r["looks"]["sheet"])
        self.assertEqual(r["looks"]["card"], r["looks"]["mark"])
        self.assertTrue(r["text"].startswith("R"))

    def test_status_badges_use_the_fixed_words(self):
        r = _phone.phone_run("""R.b={};['official','live','scenario','sketch','assumption'].forEach(function(k){R.b[k]=NBA_BADGE(k).textContent;});""", wait_ms=1500)
        self.assertEqual(r["b"], {"official": "OFFICIAL", "live": "PROVISIONAL · LIVE DATA", "scenario": "SCENARIO · NOT OFFICIAL",
                                  "sketch": "SKETCH · NOT A PROPOSAL", "assumption": "YOUR ASSUMPTION · NOT OFFICIAL"})

    def test_modes_explain_themselves_and_the_teams_titles_say_what_the_list_is(self):
        r = _phone.phone_run("""R.tips=[].map.call(document.querySelectorAll('.modeswitch button'),function(b){return b.title;});R.keep=document.querySelector('.navkeep').title;
          R.titles=[].map.call(document.querySelectorAll('#rosters-a .title,#rosters-b .title'),function(t){return t.textContent;});""", wait_ms=2000)
        self.assertTrue(all(len(t) > 20 for t in r["tips"]), r["tips"])
        self.assertIn("What If", r["keep"])
        self.assertTrue(all("STANDINGS" not in t or "TEAMS BY" in t for t in r["titles"]), r["titles"])


if __name__ == "__main__":
    unittest.main()
