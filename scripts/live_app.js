(function(){
"use strict";
/* LIVE tab: this week's matchups, the standings if the week ended now, the playoff picture and the projected reverse order.
   Every number comes precomputed from scripts/build_live_feed.py (the page only renders). Provisional by construction: it never
   reads or writes official state. The feed is fetched from the live-data branch; the embedded copy (official weeks only) is the fallback. */
var dataEl=document.getElementById("live-data"),root=document.getElementById("live-root");
if(!dataEl||!root)return;
var B=JSON.parse(dataEl.textContent),TM={},RK={};
(B.rookies||[]).forEach(function(id){RK[id]=1;});
B.teams.forEach(function(t){TM[t.id]=t;});
var FEED=B.fallback,SRC="fallback",ERR=null,LOADING=false,CHECKED=null,OPEN={},REFRESH_MS=2*60*1000,STALE_MIN=30;
var CATS=[["fgPct","FG%"],["ftPct","FT%"],["tpm","3PTM"],["pts","PTS"],["reb","REB"],["ast","AST"],["st","ST"],["blk","BLK"],["to","TO"]];
var LINE=[["fgPct","FG%"],["ftPct","FT%"],["tpm","3PM"],["pts","PTS"],["reb","REB"],["ast","AST"],["st","STL"],["blk","BLK"],["to","TO"]];   /* display order */
var OLD_KEYS=["pts","reb","ast","st","blk","tpm","to","fgPct","ftPct"];   /* the order of a feed built before lineKeys existed */
var OUT={O:1,INJ:1,SUSP:1,NA:1,OFS:1};   /* statuses of a player who is not playing */
function noStats(r,vals){return !!OUT[r.st]&&(!vals||vals.every(function(v){return !v;}));}   /* an out player with nothing recorded shows dashes, not zeros */
function cell(x,key){return x==null?"–":(key==="fgPct"||key==="ftPct"?pct(x):String(x));}
function lineOf(arr){var keys=FEED.lineKeys||OLD_KEYS;return arr?LINE.map(function(c){var i=keys.indexOf(c[0]);return i<0?null:arr[i];}):null;}
function tcolor(fid){return (TM[fid]||{}).color||"#8b95a7";}
function num(key,stats){if(key==="fgPct"||key==="ftPct"){var p=stats[key==="fgPct"?"fg":"ft"];return p&&p[1]?p[0]/p[1]:null;}var v=stats[key];return v==null?null:Number(v);}
function share(key,a,b){   /* the left side's share of the bar: a ratio for counting stats, the gap for percentages (a ratio makes .477 v .375 look level) */
  if(a==null||b==null)return 50;
  if(key==="fgPct"||key==="ftPct")return Math.round(50+50*Math.max(-1,Math.min(1,(a-b)/0.2)));
  if(a+b===0)return 50;return Math.round(100*(key==="to"?b:a)/(a+b));}
function margin(key,a,b){if(a==null||b==null||a===b)return "";var d=Math.abs(a-b);return (key==="fgPct"||key==="ftPct")?"+"+d.toFixed(3).replace(/^0/,""):"+"+d;}
function volume(key,stats){var p=(key==="fgPct"||key==="ftPct")&&stats[key==="fgPct"?"fg":"ft"];return p&&p[1]?p[0]+"/"+p[1]:"";}

function h(tag,attrs,kids){var e=document.createElement(tag);if(attrs)for(var k in attrs){if(k==="class")e.className=attrs[k];else if(k==="text")e.textContent=attrs[k];else e.setAttribute(k,attrs[k]);}
  (kids||[]).forEach(function(c){if(c!=null)e.appendChild(typeof c==="string"?document.createTextNode(c):c);});return e;}
function chip(fid,label){var t=TM[fid]||{short:label||"?",color:"#dfe4ee",text:"#12264d"},c=h("span",{class:"tchip",text:(t.crown?"\uD83D\uDC51 ":"")+(label||t.short),title:t.crown?"Defending champion":""});
  c.style.setProperty("--team-color",t.color);c.style.setProperty("--team-text",t.text);return c;}
function pct(p){return p==null?"–":p.toFixed(3).replace(/^0/,"");}
function val(key,v,stats){if(key==="fgPct"||key==="ftPct"){var pair=stats[key==="fgPct"?"fg":"ft"];return pair&&pair[1]?pct(pair[0]/pair[1]):"–";}return v==null?"–":String(v);}
function ago(iso){var m=Math.max(0,Math.round((Date.now()-Date.parse(iso))/60000));return m<1?"just now":m<60?m+" min ago":m<1440?Math.floor(m/60)+" h "+(m%60)+" min ago":Math.floor(m/1440)+" d ago";}
function ict(iso){try{return new Intl.DateTimeFormat("en-GB",{timeZone:"Asia/Bangkok",weekday:"short",hour:"2-digit",minute:"2-digit",hour12:false}).format(new Date(iso))+" ICT";}catch(e){return iso;}}
function ageMin(iso){return (Date.now()-Date.parse(iso))/60000;}

/* ---------- pieces ---------- */
function head(){
  var f=FEED,live=SRC==="live",stale=live&&ageMin(f.asOf)>STALE_MIN;
  var status=live?(f.weekStatus==="LIVE"?"LIVE":"NOT STARTED"):"OFFICIAL WEEKS ONLY";
  var btn=h("button",{type:"button",class:"lv-btn",id:"lv-refresh",text:LOADING?"Refreshing…":"Refresh"});btn.addEventListener("click",function(){load(true);});
  return h("div",{class:"lv-hd"},[
    h("div",null,[h("h3",{text:live?"Week "+f.week:"Standings from finished weeks"}),
      h("div",{class:"lv-sub"},[h("span",{class:"lv-pill "+(live&&f.weekStatus==="LIVE"?"on":"")+(stale?" stale":""),text:status}),
        h("span",{id:"lv-asof",text:live?"as of "+ict(f.asOf)+" · "+ago(f.asOf)+(CHECKED?" · checked "+ago(new Date(CHECKED).toISOString())+" (feed updates about every 4 min in game hours)":""):"live feed not loaded"})])]),
    h("div",{class:"lv-act"},[btn])]);}
function note(){
  if(SRC==="live"){var f=FEED,msgs=[];
    if(ageMin(f.asOf)>STALE_MIN)msgs.push("The feed is "+ago(f.asOf)+": numbers may be out of date.");
    if(f.notStoredYet&&f.notStoredYet.length)msgs.push("Week"+(f.notStoredYet.length>1?"s ":" ")+f.notStoredYet.join(", ")+" not stored in the repo yet (counted from Yahoo).");
    if(!msgs.length)return null;return h("div",{class:"lv-note warn",role:"status",text:msgs.join(" ")});}
  return h("div",{class:"lv-note",role:"status",text:ERR?"Live feed unavailable ("+ERR+"). Showing the official finished weeks.":"Loading the live feed…"});}
function standings(){
  var f=FEED,rows=f.table,live=SRC==="live"&&f.weekStatus==="LIVE";
  var box=h("section",{class:"lv-card lv-stand"},[h("div",{class:"lv-ct",text:live?"IF THE WEEK ENDED NOW":"FINISHED WEEKS",title:"Provisional. Equal records share a rank. 8 playoff teams: each division's winner plus the best records, seeded by overall record. GB is from the overall leader; the small number is the margin in games over (+) or behind (−) the last playoff spot."})]);
  var tb=h("table",{class:"lv-t"}),hd=h("tr");["#","Team","W-L-T","GB","Playoffs"].forEach(function(x,i){hd.appendChild(h("th",{text:x,class:i>=2&&i<4?"num":"",title:i===3?"Games behind the overall leader":i===4?"Seed if in; the small number is the margin in games over (+) or behind (−) the last playoff spot":""}));});
  tb.appendChild(h("thead",null,[hd]));var body=h("tbody"),prevIn=null;
  rows.forEach(function(r,i){
    var tr=h("tr",{class:"st-"+(r.playoff||"")+(r.tied?" tied":""),"data-team":r.team});
    if(prevIn===true&&r.playoff!=="in")tr.classList.add("cut");prevIn=r.playoff==="in";
    tr.appendChild(h("td",{class:"num rk"},[(r.tied?"T-":"")+r.rank,live&&r.moved?h("i",{class:"mv "+(r.moved>0?"up":"down"),text:r.moved>0?"▲":"▼",title:"Official rank "+r.officialRank+" ("+(r.moved>0?"up ":"down ")+Math.abs(r.moved)+")"}):null]));
    tr.appendChild(h("td",null,[chip(r.team)]));
    tr.appendChild(h("td",{class:"num",text:r.w+"-"+r.l+(r.t?"-"+r.t:"")}));
    tr.appendChild(h("td",{class:"num",text:r.gb?String(r.gb):"–"}));
    var gl=r.gbLine==null?null:-r.gbLine,m=gl==null?"":gl>0?"+"+gl:gl<0?"−"+(-gl):"0";
    tr.appendChild(h("td",{class:"po "+(r.playoff||"out")},[r.playoff==="in"?(r.seed?"#"+r.seed:"In"):r.playoff==="bubble"?"Bubble":"Out",m?h("small",{text:m}):null]));
    body.appendChild(tr);});
  tb.appendChild(body);box.appendChild(h("div",{class:"lv-wrap"},[tb]));
  return box;}
function reverse(){
  var f=FEED,box=h("section",{class:"lv-card lv-rev"},[h("div",{class:"lv-ct",text:"PROJECTED REVERSE ORDER"}),h("div",{class:"lv-cs",text:"Worst record first. Not the draft order."})]);
  var ol=h("ol",{class:"lv-ol"});f.projectedReverse.forEach(function(x){ol.appendChild(h("li",null,[chip(x.team),x.tied?h("small",{text:" tied",title:"Level with a neighbour; shown in the official order"}):null]));});
  box.appendChild(ol);return box;}
function rosterTable(side,dayDate){
  var t=h("table",{class:"lv-r"}),cg=h("colgroup");cg.appendChild(h("col",{class:"c-sl"}));cg.appendChild(h("col",{class:"c-nm"}));LINE.forEach(function(){cg.appendChild(h("col",{class:"c-n"}));});t.appendChild(cg);
  var hd=h("tr");["","Player"].concat(LINE.map(function(c){return c[1];})).forEach(function(x,i){hd.appendChild(h("th",{text:x,class:i>1?"num":""}));});
  t.appendChild(h("thead",null,[hd]));var tb=h("tbody");t.appendChild(tb);
  var haveDay=side.roster.some(function(r){return r.d;});
  var groups=[["STARTERS","week totals",function(r){return r.s!=="BN"&&r.s!=="IL";}],["BENCH","stats from "+(dayDate||"the latest day")+" only, not counted",function(r){return r.s==="BN";}],["INJURED LIST","stats from "+(dayDate||"the latest day")+" only, not counted",function(r){return r.s==="IL";}]];
  groups.forEach(function(g){var rows=side.roster.filter(g[2]);if(!rows.length)return;var bench=g[0]!=="STARTERS";
    var gh=h("tr",{class:"gh"+(bench?" off":"")}),td=h("td",{colspan:String(LINE.length+2)},[h("b",{text:g[0]}),h("small",{text:g[1]+(bench&&!haveDay?" (arrives with the next feed update)":"")})]);gh.appendChild(td);tb.appendChild(gh);
    rows.forEach(function(r){var vals=lineOf(bench?r.d:r.l);
      var rk=r.n!=null&&r.p&&RK[r.p];
      var tr=h("tr",{class:(r.n==null?"empty ":"")+(bench?"off ":"")+(rk?"rk":"")});
      tr.appendChild(h("td",{class:"sl",text:r.s}));
      var nm=h("td",{class:"nm"},[h("b",{text:r.n==null?"(empty)":r.n})]);
      if(rk)nm.appendChild(h("span",{class:"lv-rk",title:"2026 rookie",text:"R"}));
      if(r.n!=null){if(r.st)nm.appendChild(h("span",{class:"lv-st",text:r.st}));if(r.g)nm.appendChild(h("small",{class:r.gs||"",text:(r.t?r.t+" · ":"")+r.g}));}
      tr.appendChild(nm);
      var dash=r.n!=null&&noStats(r,vals);
      LINE.forEach(function(c,i){var v=vals?vals[i]:null;tr.appendChild(h("td",{class:"num"+(!dash&&v===0?" z":""),text:r.n==null||!vals?"":dash?"–":cell(v,c[0])}));});
      tb.appendChild(tr);});});
  return t;}
function matchup(m){
  var a=m.teams[0],b=m.teams[1],lead=m.score[0]>m.score[1]?0:m.score[1]>m.score[0]?1:-1;
  var card=h("section",{class:"lv-card lv-m","data-m":String(a.yahooId)});
  
  var mh=h("div",{class:"lv-mh",title:"Click to open or close the rosters"},[h("div",{class:"lv-side"+(lead===0?" lead":"")},[chip(a.team),h("b",{class:"lv-w",text:String(m.score[0])})]),
    h("div",{class:"lv-mid",text:m.score[2]?m.score[2]+" tied":"vs"}),
    h("div",{class:"lv-side flip"+(lead===1?" lead":"")},[h("b",{class:"lv-w",text:String(m.score[1])}),chip(b.team)])]);card.appendChild(mh);
  var grid=h("div",{class:"lv-cats"});
  CATS.forEach(function(c){var w=m.cats[c[0]],va=val(c[0],a.stats[c[0]],a.stats),vb=val(c[0],b.stats[c[0]],b.stats);
    var na=num(c[0],a.stats),nb=num(c[0],b.stats),mg=margin(c[0],na,nb),vola=volume(c[0],a.stats),volb=volume(c[0],b.stats);
    var row=h("div",{class:"lv-c "+(w==="a"?"wa":w==="b"?"wb":w==="t"?"wt":"")},[h("span",{class:"va"},[va,vola?h("small",{text:vola}):null]),h("span",{class:"cl"},[c[1],mg?h("small",{class:"mg",text:w==="a"?"◂ "+mg:w==="b"?mg+" ▸":mg,title:"Lead in "+c[1]+(c[0]==="to"?" (fewer is better)":"")}):null]),h("span",{class:"vb"},[vb,volb?h("small",{text:volb}):null])]);
    var tug=h("i",{class:"tug"});tug.style.setProperty("--p",share(c[0],na,nb)+"%");row.appendChild(tug);grid.appendChild(row);});
  card.appendChild(grid);
  var tp=function(s){var n=s.toPlay||{upcoming:0,live:0};return n.upcoming+n.live;};
  card.appendChild(h("div",{class:"lv-tp"},[h("span",{text:tp(a)+" to play"}),h("span",{text:tp(b)+" to play"})]));
  var det=h("details",{class:"lv-det"},[h("summary",null,[h("span",{text:"Rosters"}),h("small",{text:"tap the scores or this bar to open and close"})])]);if(OPEN[a.yahooId])det.setAttribute("open","");
  var shut=function(){det.open=false;var r=card.getBoundingClientRect(),bar=document.querySelector(".topbar"),top=bar?bar.offsetHeight:0;if(r.top<top)window.scrollTo({top:window.pageYOffset+r.top-top-8});};
  det.addEventListener("toggle",function(){OPEN[a.yahooId]=det.open;card.classList.toggle("open",det.open);});card.classList.toggle("open",!!OPEN[a.yahooId]);
  mh.addEventListener("click",function(e){if(e.target.closest("a,button"))return;if(det.open)shut();else det.open=true;});
  var bar=h("div",{class:"lv-bar"},[chip(a.team),h("span",{class:"vs",text:"vs"}),chip(b.team),h("button",{type:"button",class:"lv-x",text:"Close ✕",title:"Close the rosters (Esc)"})]);
  bar.querySelector(".lv-x").addEventListener("click",shut);
  var cols=h("div",{class:"lv-cols"});
  m.teams.forEach(function(s,i){var rc=h("div",{class:"lv-rc "+(i?"cb":"ca")},[h("div",{class:"lv-rt"},[chip(s.team)]),h("div",{class:"lv-wrap"},[rosterTable(s,FEED.dayDate)])]);cols.appendChild(rc);});
  det.appendChild(bar);det.appendChild(cols);card.appendChild(det);return card;}

/* ---------- render ---------- */
function render(){
  root.textContent="";var tb=document.querySelector(".topbar");if(tb)root.style.setProperty("--lv-nav",tb.offsetHeight+"px");
  root.appendChild(head());var n=note();if(n)root.appendChild(n);
  var grid=h("div",{class:"lv-grid"}),left=h("div",{class:"lv-left"}),right=h("div",{class:"lv-right"});
  left.appendChild(standings());left.appendChild(reverse());
  var title=SRC==="live"?"MATCHUPS":"LAST FINISHED WEEK";
  var ms=h("div",{class:"lv-ms"});FEED.matchups.forEach(function(m){ms.appendChild(matchup(m));});
  var allBtn=h("button",{type:"button",class:"lv-all",id:"lv-all"});
  var anyOpen=function(){return FEED.matchups.some(function(m){return OPEN[m.teams[0].yahooId];});};
  var setAll=function(){var open=!anyOpen();FEED.matchups.forEach(function(m){OPEN[m.teams[0].yahooId]=open;});ms.querySelectorAll(".lv-det").forEach(function(d){d.open=open;});allBtn.textContent=open?"Collapse all":"Expand all";};
  allBtn.textContent=anyOpen()?"Collapse all":"Expand all";allBtn.addEventListener("click",setAll);
  right.appendChild(h("div",{class:"lv-tb"},[h("div",{class:"lv-st",text:title}),allBtn]));right.appendChild(ms);
  grid.appendChild(left);grid.appendChild(right);root.appendChild(grid);
  if(window.NBA_MONO)window.NBA_MONO(root);
  try{document.dispatchEvent(new Event("nba:live"));}catch(e){}}

/* ---------- loading ---------- */
function valid(d){return d&&d.schema==="live-feed/1"&&Array.isArray(d.table)&&Array.isArray(d.matchups)&&d.table.length===16&&d.asOf;}
function accept(d,src){if(!valid(d))throw new Error("unreadable feed");FEED=d;SRC=src||"live";ERR=null;}
function load(manual){
  if(LOADING||!B.liveUrl)return;LOADING=true;if(manual)render();
  var ctl=window.AbortController?new AbortController():null,timer=setTimeout(function(){if(ctl)ctl.abort();},12000);
  fetch(B.liveUrl+"?t="+(manual?Date.now():Math.floor(Date.now()/60000)),{cache:"no-store",signal:ctl?ctl.signal:undefined}).then(function(r){if(!r.ok)throw new Error("HTTP "+r.status);return r.json();})
    .then(function(d){accept(d,"live");CHECKED=Date.now();}).catch(function(e){ERR=String(e&&e.message||e);if(SRC!=="live")SRC="fallback";})
    .then(function(){clearTimeout(timer);LOADING=false;render();});}
function visible(){return !document.hidden&&root.closest&&!root.closest(".tab-off");}
setInterval(function(){if(visible())load(false);},REFRESH_MS);
document.addEventListener("keydown",function(e){if(e.key!=="Escape"||!visible())return;
  var open=[].slice.call(root.querySelectorAll(".lv-det[open]"));if(!open.length)return;
  var pick=open.filter(function(d){var r=d.getBoundingClientRect();return r.bottom>80;})[0]||open[0];var x=pick.querySelector(".lv-x");if(x)x.click();});
document.addEventListener("visibilitychange",function(){if(visible()&&(SRC!=="live"||ageMin(FEED.asOf)>REFRESH_MS/60000))load(false);});

/* ---------- what the rest of the page uses ---------- */
function standingsFor(){   /* shaped like D.standings so the Teams tab can reorder by it */
  if(SRC!=="live")return null;var teams={},order=FEED.projectedReverse.map(function(x){return x.team;});
  FEED.table.forEach(function(r){teams[r.team]={rank:r.rank,place:r.rank,w:r.w,l:r.l,t:r.t,pct:r.pct,gb:r.gb,division:r.division,divRecord:"",lastWeek:"",tied:r.tied,live:true};});
  return {started:true,worstFirst:order,teams:teams,sourceUpdatedAt:FEED.asOf,capturedAt:FEED.asOf,sourceUpdatedText:"LIVE "+ict(FEED.asOf),live:true};}
function exportsFor(){
  var f=FEED,live=SRC==="live";
  return [
   {id:"live-standings",label:live?"Live standings":"Standings (finished weeks)",desc:"Records, playoff line and movement"+(live?" if the week ended now":""),pages:function(){
     var rows=f.table.map(function(r){return {tone:r.playoff==="in"?"":"mute",c:[(r.tied?"T-":"")+r.rank,{team:r.team},r.w+"-"+r.l+(r.t?"-"+r.t:""),pct(r.pct),r.moved&&live?(r.moved>0?"▲"+r.moved:"▼"+(-r.moved)):"",r.playoff==="in"?"IN #"+r.seed:r.playoff==="bubble"?"BUBBLE":"OUT"]};});
     return [{label:"Standings",name:"live-standings.png",alt:"Standings",doc:{title:live?"Standings if the week ended now":"Standings",tag:live?"PROVISIONAL":"",sub:(live?"Week "+f.week+" · as of "+ict(f.asOf)+" · ":"")+"equal records share a rank",
       blocks:[{t:"table",cols:[{h:"#",w:1,m:1},{h:"TEAM",w:3.4},{h:"W-L-T",w:2,a:"r",m:1},{h:"PCT",w:1.6,a:"r",m:1},{h:"MOVE",w:1.4,a:"r"},{h:"PLAYOFFS",w:2,a:"r"}],rh:44,rows:rows}],foot:"NBA Talk VN Dynasty",link:location.origin+location.pathname+"#live"}}];}},
   {id:"live-matchups",label:live?"This week's matchups":"Last finished week",desc:"Category score of every matchup",pages:function(){
     var cards=f.matchups.map(function(m){var a=m.teams[0],b=m.teams[1];
       return {team:a.team,head:m.score[0]+"–"+m.score[1]+(m.score[2]?"–"+m.score[2]:""),sub:"vs "+(TM[b.team]?TM[b.team].short:b.name),lines:CATS.map(function(c){var w=m.cats[c[0]];
         return {l:c[1]+"  "+val(c[0],a.stats[c[0]],a.stats)+" – "+val(c[0],b.stats[c[0]],b.stats),r:w==="a"?"✓":w==="b"?"✗":w==="t"?"=":"",tone:w==="a"?"ok":w==="b"?"bad":"mute"};})};});
     return [{label:"Matchups",name:"live-matchups.png",alt:"Matchups",doc:{title:live?"Week "+f.week+" matchups":"Last finished week",tag:live?"PROVISIONAL":"",sub:live?"as of "+ict(f.asOf):"",blocks:[{t:"cards",cols:2,cards:cards}],foot:"NBA Talk VN Dynasty",link:location.origin+location.pathname+"#live"}}];}}];}

window.NBA_LIVE={standings:standingsFor,exports:exportsFor,source:function(){return SRC;},feed:function(){return FEED;},reload:function(){return load(true);},
  /* tests and tools hand a feed in directly */ set:function(d){accept(d,"live");render();}};
render();
load(false);
document.addEventListener("nba:tab",function(e){if(e.detail==="live")load(false);});
})();
