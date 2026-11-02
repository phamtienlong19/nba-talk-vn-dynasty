(function(){
"use strict";
/* LIVE tab: this week's matchups, the standings if the week ended now, the playoff picture and the projected reverse order.
   Every number comes precomputed from scripts/build_live_feed.py (the page only renders). Provisional by construction: it never
   reads or writes official state. The feed is fetched from the live-data branch; the embedded copy (official weeks only) is the fallback. */
var dataEl=document.getElementById("live-data"),root=document.getElementById("live-root");
if(!dataEl||!root)return;
var B=JSON.parse(dataEl.textContent),TM={};
B.teams.forEach(function(t){TM[t.id]=t;});
var FEED=B.fallback,SRC="fallback",ERR=null,LOADING=false,OPEN={},REFRESH_MS=5*60*1000,STALE_MIN=75;
var CATS=[["fgPct","FG%"],["ftPct","FT%"],["tpm","3PTM"],["pts","PTS"],["reb","REB"],["ast","AST"],["st","ST"],["blk","BLK"],["to","TO"]];
var LINE=["PTS","REB","AST","ST","BLK","3PM","TO"],LINE_IX=[0,1,2,3,4,5,6];

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
        h("span",{id:"lv-asof",text:live?"as of "+ict(f.asOf)+" · "+ago(f.asOf):"live feed not loaded"})])]),
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
  var tb=h("table",{class:"lv-t"}),hd=h("tr");["#","","Team","W-L-T","Pct","GB","Line","Playoffs"].forEach(function(x,i){hd.appendChild(h("th",{text:x,class:i>=3&&i<7?"num":"",title:i===5?"Games behind the overall leader":i===6?"Games ahead of (+) or behind (−) the last playoff spot":""}));});
  tb.appendChild(h("thead",null,[hd]));var body=h("tbody"),prevIn=null;
  rows.forEach(function(r,i){
    var tr=h("tr",{class:"st-"+(r.playoff||"")+(r.tied?" tied":""),"data-team":r.team});
    if(prevIn===true&&r.playoff!=="in")tr.classList.add("cut");prevIn=r.playoff==="in";
    tr.appendChild(h("td",{class:"num",text:(r.tied?"T-":"")+r.rank}));
    tr.appendChild(h("td",{class:"mv "+(r.moved>0?"up":r.moved<0?"down":""),text:live&&r.moved?(r.moved>0?"▲"+r.moved:"▼"+(-r.moved)):"",title:live&&r.moved?"Official rank "+r.officialRank:""}));
    tr.appendChild(h("td",null,[chip(r.team)]));
    tr.appendChild(h("td",{class:"num",text:r.w+"-"+r.l+(r.t?"-"+r.t:"")}));
    tr.appendChild(h("td",{class:"num",text:pct(r.pct)}));
    tr.appendChild(h("td",{class:"num",text:r.gb?String(r.gb):"–"}));
    var gl=r.gbLine==null?null:-r.gbLine;
    tr.appendChild(h("td",{class:"num line "+(gl>0?"ahead":gl<0?"behind":""),text:gl==null?"":gl>0?"+"+gl:gl<0?"−"+(-gl):"0"}));
    tr.appendChild(h("td",null,[r.playoff==="in"?h("span",{class:"lv-po in",text:"IN"+(r.seed?" #"+r.seed:"")}):r.playoff==="bubble"?h("span",{class:"lv-po bubble",text:"BUBBLE"}):h("span",{class:"lv-po out",text:"OUT"})]));
    body.appendChild(tr);});
  tb.appendChild(body);box.appendChild(h("div",{class:"lv-wrap"},[tb]));
  box.appendChild(h("div",{class:"lv-foot",text:"8 playoff teams: each division's winner plus the best records; seeded by overall record. Games back is from the overall leader; Line is the margin over the last playoff spot."}));
  return box;}
function reverse(){
  var f=FEED,box=h("section",{class:"lv-card lv-rev"},[h("div",{class:"lv-ct",text:"PROJECTED REVERSE ORDER"}),h("div",{class:"lv-cs",text:"Worst record first. Not the draft order: the lottery and penalties still apply."})]);
  var ol=h("ol",{class:"lv-ol"});f.projectedReverse.forEach(function(x){ol.appendChild(h("li",null,[chip(x.team),x.tied?h("small",{text:" tied",title:"Level with a neighbour; shown in the official order"}):null]));});
  box.appendChild(ol);return box;}
function matchup(m){
  var a=m.teams[0],b=m.teams[1],lead=m.score[0]>m.score[1]?0:m.score[1]>m.score[0]?1:-1;
  var card=h("section",{class:"lv-card lv-m","data-m":String(a.yahooId)});
  card.appendChild(h("div",{class:"lv-mh"},[h("div",{class:"lv-side"+(lead===0?" lead":"")},[chip(a.team),h("b",{class:"lv-w",text:String(m.score[0])})]),
    h("div",{class:"lv-mid",text:m.score[2]?"– "+m.score[2]+" tied –":"–"}),
    h("div",{class:"lv-side flip"+(lead===1?" lead":"")},[h("b",{class:"lv-w",text:String(m.score[1])}),chip(b.team)])]));
  var grid=h("div",{class:"lv-cats"});
  CATS.forEach(function(c){var w=m.cats[c[0]],va=val(c[0],a.stats[c[0]],a.stats),vb=val(c[0],b.stats[c[0]],b.stats);
    grid.appendChild(h("div",{class:"lv-c "+(w==="a"?"wa":w==="b"?"wb":w==="t"?"wt":"")},[h("span",{class:"va",text:va}),h("span",{class:"cl",text:c[1]}),h("span",{class:"vb",text:vb})]));});
  card.appendChild(grid);
  var tp=function(s){var n=s.toPlay||{upcoming:0,live:0};return n.upcoming+n.live;};
  card.appendChild(h("div",{class:"lv-tp"},[h("span",{text:tp(a)+" to play"}),h("span",{text:tp(b)+" to play"})]));
  var det=h("details",{class:"lv-det"},[h("summary",{text:"Rosters"})]);if(OPEN[a.yahooId])det.setAttribute("open","");
  det.addEventListener("toggle",function(){OPEN[a.yahooId]=det.open;});
  var cols=h("div",{class:"lv-cols"});
  m.teams.forEach(function(s){var t=h("table",{class:"lv-r"}),hd=h("tr");["","Player"].concat(LINE).forEach(function(x,i){hd.appendChild(h("th",{text:x,class:i>1?"num":""}));});
    t.appendChild(h("thead",null,[hd]));var tbd=h("tbody");
    s.roster.forEach(function(r){var tr=h("tr",{class:r.n==null?"empty":(r.s==="BN"?"bench":r.s==="IL"?"il":"")});
      tr.appendChild(h("td",{class:"sl",text:r.s}));
      var nm=h("td",{class:"nm"},[h("b",{text:r.n==null?"(empty)":r.n})]);
      if(r.n!=null){if(r.st)nm.appendChild(h("span",{class:"lv-st",text:r.st}));if(r.g)nm.appendChild(h("small",{class:r.gs||"",text:r.g}));}
      tr.appendChild(nm);
      LINE_IX.forEach(function(ix){tr.appendChild(h("td",{class:"num",text:r.n==null||r.l[ix]==null?"":String(r.l[ix])}));});
      tbd.appendChild(tr);});
    t.appendChild(tbd);cols.appendChild(h("div",{class:"lv-rc"},[h("div",{class:"lv-rt"},[chip(s.team)]),h("div",{class:"lv-wrap"},[t])]));});
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
  fetch(B.liveUrl+"?t="+Math.floor(Date.now()/300000),{cache:"no-store",signal:ctl?ctl.signal:undefined}).then(function(r){if(!r.ok)throw new Error("HTTP "+r.status);return r.json();})
    .then(function(d){accept(d,"live");}).catch(function(e){ERR=String(e&&e.message||e);if(SRC!=="live")SRC="fallback";})
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
