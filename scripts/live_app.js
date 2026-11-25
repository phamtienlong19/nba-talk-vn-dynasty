(function(){
"use strict";
/* LIVE tab: every team's lineup as Yahoo shows it now, with the facts a commissioner looks for, plus the week's lineup checks. No scores, standings or
   projections. Everything comes from scripts/build_live_feed.py (live.json on the live-data branch) and scripts/lineup_review.py; nothing is stored in
   the page, and it never touches official state. */
var dataEl=document.getElementById("live-data"),root=document.getElementById("live-root");
if(!dataEl||!root)return;
var B=JSON.parse(dataEl.textContent),TM={},RK={};
(B.rookies||[]).forEach(function(id){RK[id]=1;});
B.teams.forEach(function(t){TM[t.id]=t;});
var FEED=null,ERR=null,LOADING=false,CHECKED=null,OPEN={},REFRESH_MS=2*60*1000,STALE_MIN=30;
var OUT={O:1,INJ:1,SUSP:1,NA:1,OFS:1};   /* statuses of a player who is not playing */
var STARTING={PG:1,SG:1,G:1,SF:1,PF:1,F:1,C:1,FC:1,Util:1};
function me(){try{return window.NBA_ME?window.NBA_ME():null;}catch(e){return null;}}
function shareEl(label,get,o){return window.NBA_PLAYER&&NBA_PLAYER.shareBtn?NBA_PLAYER.shareBtn(label,get,o):null;}   /* the site's export button for one element */

function h(tag,attrs,kids){var e=document.createElement(tag);if(attrs)for(var k in attrs){if(k==="class")e.className=attrs[k];else if(k==="text")e.textContent=attrs[k];else e.setAttribute(k,attrs[k]);}
  (kids||[]).forEach(function(c){if(c!=null)e.appendChild(typeof c==="string"?document.createTextNode(c):c);});return e;}
function chip(fid,label){var t=TM[fid]||{short:label||"?",color:"#dfe4ee",text:"#12264d"},c=h("span",{class:"tchip",text:(t.crown?"\uD83D\uDC51 ":"")+(label||t.short),title:t.crown?"Defending champion":""});
  c.style.setProperty("--team-color",t.color);c.style.setProperty("--team-text",t.text);return c;}
function ago(iso){var m=Math.max(0,Math.round((Date.now()-Date.parse(iso))/60000));return m<1?"just now":m<60?m+" min ago":m<1440?Math.floor(m/60)+" h "+(m%60)+" min ago":Math.floor(m/1440)+" d ago";}
function ict(iso){try{return new Intl.DateTimeFormat("en-GB",{timeZone:"Asia/Bangkok",weekday:"short",hour:"2-digit",minute:"2-digit",hour12:false}).format(new Date(iso))+" ICT";}catch(e){return iso;}}
function ageMin(iso){return (Date.now()-Date.parse(iso))/60000;}

/* ---------- facts about a lineup as it stands now ---------- */
function ilKindOf(r){return window.NBA_IL?window.NBA_IL(r.p,r.st):null;}
/* what the commissioner looks for in the current slots: facts only, never a ruling (the ruling-relevant judgement is in the lineup checks) */
function rowFlag(r){
  if(r.n==null)return STARTING[r.s]?{t:"EMPTY",c:"warn",title:"Empty starting slot"}:null;
  if(STARTING[r.s]&&OUT[r.st]&&r.g)return {t:"OUT IN LINEUP",c:"bad",title:"Listed "+r.st+" in a starting slot, with a game today"};
  if(r.s==="IL"||r.s==="IL+"){var k=ilKindOf(r);if(k==="inel")return {t:"IL !",c:"warn",title:"On IL, not IL-eligible"+(r.st?": Yahoo status "+r.st:": no Yahoo status")};}
  return null;}
function sides(){var out=[];(FEED?FEED.matchups:[]).forEach(function(m){m.teams.forEach(function(s){out.push(s);});});return out;}
/* does this player have a game on the day shown? (the feed gives its text: a start time, a live score or a result) */
function hasGame(r){return r.n!=null&&!!r.g;}
function startersPlaying(side){var s=side.roster.filter(function(r){return STARTING[r.s];});return {n:s.filter(hasGame).length,of:s.length};}
function gameChip(r){
  if(r.n==null)return null;
  if(!r.g)return h("span",{class:"lv-g none",text:"no game"});
  var state=r.gs||"upcoming",text=String(r.g).replace(/^([WL]),\s*/,function(all,wl){return wl+" ";});
  return h("span",{class:"lv-g "+state,title:state==="live"?"Game in progress":state==="final"?"Game over":"Game still to start (Yahoo's time)",text:text});}
function flagsOf(side){return side.roster.filter(function(r){return r.s!=="--";}).map(function(r){var f=rowFlag(r);return f?{r:r,f:f}:null;}).filter(Boolean);}
function faultDays(fid){var R=FEED&&FEED.lineupReview,t=R&&R.teams[fid];return t?t.days:0;}
function ordered(){var mt=me();return sides().sort(function(a,b){return (b.team===mt)-(a.team===mt)||flagsOf(b).length-flagsOf(a).length||faultDays(b.team)-faultDays(a.team)||a.yahooId-b.yahooId;});}

/* ---------- pieces ---------- */
function head(){
  var f=FEED,stale=f&&ageMin(f.asOf)>STALE_MIN,status=!f?"NOT LOADED":f.weekStatus==="LIVE"?"LIVE":"NOT STARTED";
  var btn=h("button",{type:"button",class:"lv-btn",id:"lv-refresh",text:LOADING?"Refreshing…":"Refresh"});btn.addEventListener("click",function(){load(true);});
  return h("div",{class:"lv-hd"},[
    h("div",null,[h("h3",{text:f?"Lineups · week "+f.week:"Lineups"}),
      h("div",{class:"lv-sub"},[h("span",{class:"lv-pill "+(f&&f.weekStatus==="LIVE"?"on":"")+(stale?" stale":""),text:status}),
        h("span",{id:"lv-asof",text:f?"as of "+ict(f.asOf)+" · "+ago(f.asOf)+(CHECKED?" · checked "+ago(new Date(CHECKED).toISOString()):""):"live feed not loaded"})])]),
    h("div",{class:"lv-act"},[btn])]);}
function note(){
  if(FEED)return ageMin(FEED.asOf)>STALE_MIN?h("div",{class:"lv-note warn",role:"status",text:"The feed is "+ago(FEED.asOf)+": lineups may be out of date."}):null;
  return h("div",{class:"lv-note",role:"status",text:ERR?"Live feed unavailable ("+ERR+"). Team rosters are on the TEAMS tab.":"Loading the live feed…"});}
var KIND={out_starter:"Out player held a starting slot while an eligible bench player had a game",empty_slot:"Starting slot left empty while an eligible bench player had a game",star_benched:"Star (top 50) on the bench with a game"};
function shortDate(iso){try{return new Intl.DateTimeFormat("en-GB",{day:"numeric",month:"short",timeZone:"UTC"}).format(new Date(iso+"T12:00:00Z"));}catch(e){return iso;}}
/* the reviewed version of the same check: faults only (scripts/lineup_review.py), the same counts as the REVIEW tab */
function reviewed(R){
  var box=h("section",{class:"lv-card lv-lc"},[h("div",{class:"lv-ct",text:"LINEUP CHECKS",title:"Faults only: what a manager could have avoided, judged one hour before tip. Evidence for review, not a verdict."}),
    h("div",{class:"lv-cs",text:"Week "+R.week+". Rule count: "+R.rule.days+"+ days or "+R.rule.players+"+ players. Details in REVIEW."})]);
  var ids=Object.keys(R.teams).filter(function(id){return R.teams[id].days>0;}).sort(function(a,b){return R.teams[b].days-R.teams[a].days||R.teams[b].players-R.teams[a].players;}),mt=me();
  if(!ids.length){box.appendChild(h("div",{class:"lv-lc-none",text:"No faults this week."}));return box;}
  ids.forEach(function(id){var t=R.teams[id],det=h("details",{class:"lv-lc-t"+(id===mt?" me":"")+(t.meets?" over":"")});
    det.appendChild(h("summary",null,[chip(id),h("span",{class:"n",text:t.days+(t.days===1?" day":" days")+" · "+t.players+(t.players===1?" player":" players")}),t.meets?h("span",{class:"flag",text:"at the rule's count",title:"Meets the league's AFK count; the commissioner decides"}):null]));
    var ul=h("ul");t.items.forEach(function(i){if(i.o!=="fault")return;ul.appendChild(h("li",null,[h("b",{text:i.dates.map(shortDate).join(", ")}),h("span",{text:" "+i.n+": "+i.what+(i.fact?" ("+i.fact+")":"")})]));});
    det.appendChild(ul);box.appendChild(det);});
  if(Object.keys(R.teams).length>ids.length)box.appendChild(h("div",{class:"lv-foot",text:(Object.keys(R.teams).length-ids.length)+(Object.keys(R.teams).length-ids.length===1?" team":" teams")+": no faults."}));
  return box;}
function lineups(){
  if(FEED.lineupReview)return reviewed(FEED.lineupReview);
  var L=FEED.lineupChecks;if(!L)return null;
  var days=Object.keys(L.byDate||{}).sort(),rule=L.rule||{days:2,players:3,stars:2};
  var box=h("section",{class:"lv-card lv-lc"},[h("div",{class:"lv-ct",text:"LINEUP CHECKS",title:"What the league rules count as a misset lineup, from closed days. Evidence for review, not a verdict. A status is what Yahoo showed when the day was captured, so a late scratch can look like an out starter."}),
    h("div",{class:"lv-cs",text:days.length?"Closed days of week "+L.week+": "+days.map(shortDate).join(", ")+". Rule count: "+rule.days+"+ days or "+rule.players+"+ players in a week.":"No day of week "+L.week+" has closed yet."})]);
  if(!days.length)return box;
  var rows=(L.teams||[]).filter(function(t){return t.missetDays>0;}).sort(function(a,b){return b.missetDays-a.missetDays||b.players-a.players;});
  var clean=(L.teams||[]).length-rows.length;
  if(!rows.length){box.appendChild(h("div",{class:"lv-lc-none",text:"Nothing found: every checked lineup used its starting slots."}));return box;}
  var mt=me();
  rows.forEach(function(t){
    var det=h("details",{class:"lv-lc-t"+(t.team===mt?" me":"")+(t.meetsCount?" over":"")});
    det.appendChild(h("summary",null,[chip(t.team),h("span",{class:"n",text:t.missetDays+(t.missetDays===1?" day":" days")+" · "+t.players+(t.players===1?" player":" players")}),t.meetsCount?h("span",{class:"flag",text:"at the rule's count",title:"Meets the league's AFK count; the commissioner decides"}):null]));
    var ul=h("ul");t.days.forEach(function(d){d.issues.forEach(function(i){
      var who=i.k==="empty_slot"?"empty "+i.s+" slot":(i.p||"?")+(i.k==="out_starter"?" ("+i.s+")":" (bench"+(i.rank?", rank "+i.rank:"")+")");
      ul.appendChild(h("li",null,[h("b",{text:shortDate(d.date)}),h("span",{text:" "+KIND[i.k]+": "+who+(i.r?"; eligible bench player: "+i.r:"")})]));});});
    det.appendChild(ul);box.appendChild(det);});
  if(clean>0)box.appendChild(h("div",{class:"lv-foot",text:clean+(clean===1?" team":" teams")+": nothing found."}));
  return box;}
function rosterTable(side){
  var t=h("table",{class:"lv-r"}),tb=h("tbody");t.appendChild(h("colgroup",null,[h("col",{class:"c-sl"}),h("col"),h("col",{class:"c-fl"})]));t.appendChild(tb);   /* fixed layout takes its widths from here: the first row is a full-width heading */
  var rows=side.roster.filter(function(r){return r.s!=="--";});
  [["STARTERS",function(r){return !!STARTING[r.s];}],["BENCH",function(r){return r.s==="BN";}],["INJURED LIST",function(r){return r.s==="IL"||r.s==="IL+";}]].forEach(function(g){
    var mine=rows.filter(g[1]);if(!mine.length)return;
    tb.appendChild(h("tr",{class:"gh"},[h("td",{colspan:"3"},[h("b",{text:g[0]})])]));
    mine.forEach(function(r){var rk=r.n!=null&&r.p&&RK[r.p],flag=rowFlag(r);
      var tr=h("tr",{class:(r.n==null?"empty ":hasGame(r)?"plays ":"nogame ")+(STARTING[r.s]?"":"off ")+(rk?"rk ":"")+(flag?"flag "+flag.c:"")});
      tr.appendChild(h("td",{class:"sl",text:r.s}));
      var nm=h("td",{class:"nm"},[h("b",{text:r.n==null?"(empty)":r.n})]);
      if(r.p&&window.NBA_PLAYER){nm.classList.add("pl");nm.setAttribute("tabindex","0");nm.setAttribute("role","button");var op=function(){NBA_PLAYER.open(NBA_PLAYER.keyOf(r.p));};nm.addEventListener("click",op);nm.addEventListener("keydown",function(e){if(e.key==="Enter"){e.preventDefault();op();}});}
      if(rk){var rm=window.NBA_RK&&window.NBA_PLAYER?NBA_RK.mark(NBA_PLAYER.keyOf(r.p)):null;nm.appendChild(rm||h("span",{class:"lv-rk",title:"2026 rookie",text:"R"}));}
      if(r.n!=null){if(r.st)nm.appendChild(h("span",{class:"lv-st"+(OUT[r.st]?" out":""),text:r.st}));nm.appendChild(h("small",{text:(r.t||"")+(r.gl!=null?(r.t?" · ":"")+r.gl+" left":"")}));}
      tr.appendChild(nm);
      tr.appendChild(h("td",{class:"fl"},[flag?h("span",{class:"lv-f "+flag.c,title:flag.title,text:flag.t}):null,gameChip(r)]));
      tb.appendChild(tr);});});
  return t;}
function movesOf(fid){return (FEED.moves||[]).filter(function(m){return m.team===fid;});}
function shortDay(iso){try{return new Intl.DateTimeFormat("en-US",{timeZone:"UTC",weekday:"short"}).format(new Date(iso+"T12:00:00Z"));}catch(e){return iso;}}
function movesNode(fid){   /* adds and drops since the week began, by day: facts only */
  var ms=movesOf(fid);if(!ms.length)return null;
  var box=h("div",{class:"lv-mv"},[h("div",{class:"lv-mvh",text:"ROSTER CHANGES THIS WEEK"})]);
  ms.forEach(function(m){var line=h("div",{class:"lv-mvr"},[h("span",{class:"d",text:shortDay(m.date)})]);
    m.add.forEach(function(n,i){line.appendChild(mvName("+",n,m.addIds&&m.addIds[i]));});m.drop.forEach(function(n,i){line.appendChild(mvName("−",n,m.dropIds&&m.dropIds[i]));});box.appendChild(line);});
  return box;}
function mvName(sign,name,pid){var c=h("span",{class:"mv "+(sign==="+"?"in":"out")},[h("i",{text:sign}),document.createTextNode(name)]);
  if(pid&&window.NBA_PLAYER){c.setAttribute("role","button");c.setAttribute("tabindex","0");var op=function(){NBA_PLAYER.open(NBA_PLAYER.keyOf(pid));};c.addEventListener("click",op);c.addEventListener("keydown",function(e){if(e.key==="Enter"){e.preventDefault();op();}});}
  return c;}
function teamCard(side){
  var mine=side.team===me(),flags=flagsOf(side),days=faultDays(side.team);
  var open=OPEN[side.team]!=null?OPEN[side.team]:mine;
  var card=h("details",{class:"lv-card lv-team"+(mine?" me":""),"data-team":side.team});if(open)card.open=true;
  var sp=startersPlaying(side);
  card.appendChild(h("summary",null,[chip(side.team),
    flags.length?h("span",{class:"lv-n "+(flags.some(function(x){return x.f.c==="bad";})?"bad":"warn"),text:flags.length+" to check",title:flags.map(function(x){return (x.r.n||x.r.s)+": "+x.f.t;}).join(", ")}):null,
    days?h("span",{class:"lv-n bad",text:days+" fault day"+(days>1?"s":""),title:"This week, from the lineup checks"}):null,
    h("small",null,[h("b",{class:sp.n?"on":"",text:sp.n+" of "+sp.of+" starters play"}),side.gamesLeft==null?null:" · "+(FEED.gamesLeftComplete===false?"~":"")+side.gamesLeft+" games left"])]));
  card.addEventListener("toggle",function(){OPEN[side.team]=card.open;});
  var body=h("div",{class:"lv-body"},[movesNode(side.team),rosterTable(side)]);card.appendChild(body);return card;}

/* ---------- render ---------- */
function snapshot(){var f=document.activeElement;return f&&root.contains(f)&&f.id?"#"+f.id:null;}
function render(){
  var focus=snapshot();root.textContent="";
  root.appendChild(head());var n=note();if(n)root.appendChild(n);
  if(FEED){var lc=lineups();if(lc)root.appendChild(lc);
    var grid=h("div",{class:"lv-teams"});ordered().forEach(function(s){grid.appendChild(teamCard(s));});
    var all=h("button",{type:"button",class:"lv-all",id:"lv-all"});
    var anyShut=function(){return [].some.call(grid.querySelectorAll(".lv-team"),function(d){return !d.open;});};
    all.textContent=anyShut()?"Expand all":"Collapse all";
    all.addEventListener("click",function(){var openAll=anyShut();[].forEach.call(grid.querySelectorAll(".lv-team"),function(d){d.open=openAll;OPEN[d.getAttribute("data-team")]=openAll;});all.textContent=openAll?"Collapse all":"Expand all";});
    root.appendChild(h("div",{class:"lv-tb"},[h("div",{class:"lv-h",text:"CURRENT LINEUPS"}),all]));root.appendChild(grid);
    /* every card can be exported from where it is */
    var add=function(el,host,label,name){if(!el||!host)return;var b=shareEl(label,function(){return el;},{width:430,name:name,strip:".share-btn"});if(b){b.classList.add("lv-sh");host.appendChild(b);}};
    add(root.querySelector(".lv-lc"),root.querySelector(".lv-lc .lv-ct"),"lineup checks","lineup-checks");
    [].forEach.call(grid.querySelectorAll(".lv-team"),function(c){var t=TM[c.getAttribute("data-team")]||{short:"team"};add(c,c.querySelector(".lv-body"),t.short+" lineup","lineup-"+t.short);});}
  if(window.NBA_MONO)window.NBA_MONO(root);
  if(focus){var el=root.querySelector(focus);if(el&&el.focus)el.focus();}
  try{document.dispatchEvent(new Event("nba:live"));}catch(e){}}

/* ---------- loading ---------- */
function valid(d){return !!(d&&d.schema==="live-feed/1"&&d.asOf&&Array.isArray(d.matchups)&&d.matchups.reduce(function(n,m){return n+((m.teams||[]).filter(function(t){return Array.isArray(t.roster);}).length);},0)===16);}
function accept(d){if(!valid(d))throw new Error("unreadable feed");FEED=d;ERR=null;}
function load(manual){
  if(LOADING||!B.liveUrl)return;LOADING=true;if(manual)render();
  var ctl=window.AbortController?new AbortController():null,timer=setTimeout(function(){if(ctl)ctl.abort();},12000);
  fetch(B.liveUrl+"?t="+(manual?Date.now():Math.floor(Date.now()/60000)),{cache:"no-store",signal:ctl?ctl.signal:undefined}).then(function(r){if(!r.ok)throw new Error("HTTP "+r.status);return r.json();})
    .then(function(d){accept(d);CHECKED=Date.now();}).catch(function(e){ERR=String(e&&e.message||e);})
    .then(function(){clearTimeout(timer);LOADING=false;render();});}
function visible(){return !document.hidden&&root.closest&&!root.closest(".tab-off");}
setInterval(function(){if(visible())load(false);},REFRESH_MS);
document.addEventListener("nba:me",function(){render();});
document.addEventListener("visibilitychange",function(){if(visible()&&(!FEED||ageMin(FEED.asOf)>REFRESH_MS/60000))load(false);});

/* ---------- what the rest of the page uses ---------- */
function exportsFor(){
  if(!FEED)return [];
  var sub="Week "+FEED.week+" · as of "+ict(FEED.asOf);
  return [{id:"live-lineups",label:"Current lineups",desc:"Every team's slots and statuses, with what stands out",pages:function(){
    var cards=ordered().map(function(s){var n=flagsOf(s).length;return {team:s.team,head:n?String(n):"",sub:n?"to check":"",lines:s.roster.filter(function(r){return r.s!=="--";}).map(function(r){var f=rowFlag(r);
      return {l:r.s+"  "+(r.n==null?"(empty)":r.n)+(r.st?" · "+r.st:""),r:f?f.t:"",tone:f?(f.c==="bad"?"bad":""):STARTING[r.s]?"":"mute"};})};});
    var pages=[];for(var i=0;i<cards.length;i+=4)pages.push(cards.slice(i,i+4));
    return pages.map(function(c,i){return {label:"Lineups "+(i+1),name:"lineups-"+(i+1)+".png",alt:"Current lineups "+(i+1)+" of "+pages.length,doc:{title:"Current lineups · "+(i+1)+" of "+pages.length,sub:sub,blocks:[{t:"cards",cols:2,cards:c}],foot:"NBA Talk VN Dynasty",link:location.origin+location.pathname+"#live"}};});}}];}
window.NBA_LIVE={exports:exportsFor,render:render,source:function(){return FEED?"live":"none";},feed:function(){return FEED;},reload:function(){return load(true);},
  /* tests and tools hand a feed in directly */ set:function(d){accept(d);render();}};
render();
load(false);
document.addEventListener("nba:tab",function(e){if(e.detail==="live")load(false);});
})();
