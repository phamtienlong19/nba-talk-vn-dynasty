(function(){
"use strict";
/* LIVE tab: this week's matchups, the standings if the week ended now, the playoff picture and the projected reverse order.
   Every number comes precomputed from scripts/build_live_feed.py (the page only renders). Provisional by construction: it never
   reads or writes official state. The feed is fetched from the live-data branch; the embedded copy (official weeks only) is the fallback. */
var dataEl=document.getElementById("live-data"),root=document.getElementById("live-root");
if(!dataEl||!root)return;
var B=JSON.parse(dataEl.textContent),TM={};
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
function share(key,va,vb){var a=Number(va),b=Number(vb);if(!(a>=0)||!(b>=0)||a+b===0)return 50;return Math.round(100*(key==="to"?b:a)/(a+b));}

function h(tag,attrs,kids){var e=document.createElement(tag);if(attrs)for(var k in attrs){if(k==="class")e.className=attrs[k];else if(k==="text")e.textContent=attrs[k];else e.setAttribute(k,attrs[k]);}
  (kids||[]).forEach(function(c){if(c!=null)e.appendChild(typeof c==="string"?document.createTextNode(c):c);});return e;}
function chip(fid,label){var t=TM[fid]||{short:label||"?",color:"#dfe4ee",text:"#12264d"},c=h("span",{class:"tchip",text:label||t.short});
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
  var box=h("section",{class:"lv-card lv-stand"},[h("div",{class:"lv-ct",text:live?"STANDINGS IF THE WEEK ENDED NOW":"STANDINGS"}),
    h("div",{class:"lv-cs",text:live?"Provisional. Equal records share a rank.":"Finished weeks. Equal records share a rank."})]);
  var tb=h("table",{class:"lv-t"}),hd=h("tr");["#","Team","W-L-T","Pct","GB","Playoffs"].forEach(function(x,i){hd.appendChild(h("th",{text:x,class:i>=2&&i<5?"num":"",title:i===4?"Games behind the overall leader":i===5?"In or out of the playoffs; the number is the margin over (+) or behind (−) the last playoff spot, in games":""}));});
  tb.appendChild(h("thead",null,[hd]));var body=h("tbody"),prevIn=null;
  rows.forEach(function(r,i){
    var tr=h("tr",{class:"st-"+(r.playoff||"")+(r.tied?" tied":""),"data-team":r.team});
    if(prevIn===true&&r.playoff!=="in")tr.classList.add("cut");prevIn=r.playoff==="in";
    tr.appendChild(h("td",{class:"num rk"},[(r.tied?"T-":"")+r.rank,live&&r.moved?h("i",{class:"mv "+(r.moved>0?"up":"down"),text:r.moved>0?"▲":"▼",title:"Official rank "+r.officialRank+" ("+(r.moved>0?"up ":"down ")+Math.abs(r.moved)+")"}):null]));
    tr.appendChild(h("td",null,[chip(r.team)]));
    tr.appendChild(h("td",{class:"num",text:r.w+"-"+r.l+(r.t?"-"+r.t:"")}));
    tr.appendChild(h("td",{class:"num",text:pct(r.pct)}));
    tr.appendChild(h("td",{class:"num",text:r.gb?String(r.gb):"–"}));
    var gl=r.gbLine==null?null:-r.gbLine,m=gl==null?"":gl>0?"+"+gl:gl<0?"−"+(-gl):"0";
    tr.appendChild(h("td",{class:"po "+(r.playoff||"out")},[r.playoff==="in"?"In"+(r.seed?" #"+r.seed:""):r.playoff==="bubble"?"Bubble":"Out",m?h("small",{text:m}):null]));
    body.appendChild(tr);});
  tb.appendChild(body);box.appendChild(h("div",{class:"lv-wrap"},[tb]));
  box.appendChild(h("div",{class:"lv-foot",text:"8 playoff teams: each division's winner plus the best records; seeded by overall record. Games back is from the overall leader; Line is the margin over the last playoff spot."}));
  return box;}
function reverse(){
  var f=FEED,box=h("section",{class:"lv-card lv-rev"},[h("div",{class:"lv-ct",text:"PROJECTED REVERSE ORDER"}),h("div",{class:"lv-cs",text:"Worst record first. Not the draft order: the lottery and penalties still apply."})]);
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
      var tr=h("tr",{class:(r.n==null?"empty ":"")+(bench?"off ":"")});
      tr.appendChild(h("td",{class:"sl",text:r.s}));
      var nm=h("td",{class:"nm"},[h("b",{text:r.n==null?"(empty)":r.n})]);
      if(r.n!=null){if(r.st)nm.appendChild(h("span",{class:"lv-st",text:r.st}));if(r.g)nm.appendChild(h("small",{class:r.gs||"",text:(r.t?r.t+" · ":"")+r.g}));}
      tr.appendChild(nm);
      var dash=r.n!=null&&noStats(r,vals);
      LINE.forEach(function(c,i){var v=vals?vals[i]:null;tr.appendChild(h("td",{class:"num"+(!dash&&v===0?" z":""),text:r.n==null||!vals?"":dash?"–":cell(v,c[0])}));});
      tb.appendChild(tr);});});
  return t;}
function matchup(m){
  var a=m.teams[0],b=m.teams[1],lead=m.score[0]>m.score[1]?0:m.score[1]>m.score[0]?1:-1;
  var card=h("section",{class:"lv-card lv-m","data-m":String(a.yahooId)});
  
  card.appendChild(h("div",{class:"lv-mh"},[h("div",{class:"lv-side"+(lead===0?" lead":"")},[chip(a.team),h("b",{class:"lv-w",text:String(m.score[0])})]),
    h("div",{class:"lv-mid",text:m.score[2]?m.score[2]+" tied":"vs"}),
    h("div",{class:"lv-side flip"+(lead===1?" lead":"")},[h("b",{class:"lv-w",text:String(m.score[1])}),chip(b.team)])]));
  var grid=h("div",{class:"lv-cats"});
  CATS.forEach(function(c){var w=m.cats[c[0]],va=val(c[0],a.stats[c[0]],a.stats),vb=val(c[0],b.stats[c[0]],b.stats);
    var row=h("div",{class:"lv-c "+(w==="a"?"wa":w==="b"?"wb":w==="t"?"wt":"")},[h("span",{class:"va",text:va}),h("span",{class:"cl",text:c[1]}),h("span",{class:"vb",text:vb})]);
    var tug=h("i",{class:"tug"});tug.style.setProperty("--p",share(c[0],a.stats[c[0]],b.stats[c[0]])+"%");row.appendChild(tug);grid.appendChild(row);});
  card.appendChild(grid);
  var tp=function(s){var n=s.toPlay||{upcoming:0,live:0};return n.upcoming+n.live;};
  card.appendChild(h("div",{class:"lv-tp"},[h("span",{text:tp(a)+" to play"}),h("span",{text:tp(b)+" to play"})]));
  var det=h("details",{class:"lv-det"},[h("summary",{text:"Rosters"})]);if(OPEN[a.yahooId])det.setAttribute("open","");
  det.addEventListener("toggle",function(){OPEN[a.yahooId]=det.open;card.classList.toggle("open",det.open);});card.classList.toggle("open",!!OPEN[a.yahooId]);
  var cols=h("div",{class:"lv-cols"});
  m.teams.forEach(function(s,i){var rc=h("div",{class:"lv-rc "+(i?"cb":"ca")},[h("div",{class:"lv-rt"},[chip(s.team)]),h("div",{class:"lv-wrap"},[rosterTable(s,FEED.dayDate)])]);cols.appendChild(rc);});
  det.appendChild(cols);card.appendChild(det);return card;}

/* ---------- render ---------- */
function render(){
  root.textContent="";
  root.appendChild(head());var n=note();if(n)root.appendChild(n);
  var grid=h("div",{class:"lv-grid"}),left=h("div",{class:"lv-left"}),right=h("div",{class:"lv-right"});
  left.appendChild(standings());left.appendChild(reverse());
  var title=SRC==="live"?"MATCHUPS":"LAST FINISHED WEEK";
  right.appendChild(h("div",{class:"lv-st",text:title}));
  var ms=h("div",{class:"lv-ms"});FEED.matchups.forEach(function(m){ms.appendChild(matchup(m));});right.appendChild(ms);
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
