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
var PANE_KEY="nbaTalkVN.livePane",PANE=(function(){try{var v=localStorage.getItem("nbaTalkVN.livePane");return /^(matchups|standings|roto|stats|allplay)$/.test(v)?v:"matchups";}catch(e){return "matchups";}})(),PICK=null,VIEW="week",FEED=B.fallback,SRC="fallback",ERR=null,LOADING=false,CHECKED=null,OPEN={},REFRESH_MS=2*60*1000,STALE_MIN=30;
var CATS=[["fgPct","FG%"],["ftPct","FT%"],["tpm","3PTM"],["pts","PTS"],["reb","REB"],["ast","AST"],["st","ST"],["blk","BLK"],["to","TO"]];
var LINE=[["fgPct","FG%"],["ftPct","FT%"],["tpm","3PM"],["pts","PTS"],["reb","REB"],["ast","AST"],["st","STL"],["blk","BLK"],["to","TO"]];   /* display order */
var OLD_KEYS=["pts","reb","ast","st","blk","tpm","to","fgPct","ftPct"];   /* the order of a feed built before lineKeys existed */
var OUT={O:1,INJ:1,SUSP:1,NA:1,OFS:1};   /* statuses of a player who is not playing */
function noStats(r,vals){return !!OUT[r.st]&&(!vals||vals.every(function(v){return !v;}));}   /* an out player with nothing recorded shows dashes, not zeros */
function cell(x,key){return x==null?"–":(key==="fgPct"||key==="ftPct"?pct(x):String(x));}
function lineOf(arr){var keys=FEED.lineKeys||OLD_KEYS;return arr?LINE.map(function(c){var i=keys.indexOf(c[0]);return i<0?null:arr[i];}):null;}
function me(){try{return window.NBA_ME?window.NBA_ME():null;}catch(e){return null;}}
function shareEl(label,get,o){return window.NBA_PLAYER&&NBA_PLAYER.shareBtn?NBA_PLAYER.shareBtn(label,get,o):null;}   /* the site's export button for one element */
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
  var box=h("section",{class:"lv-card lv-stand"},[h("div",{class:"lv-ct lv-ctx",text:live?"IF THE WEEK ENDED NOW":"FINISHED WEEKS",title:"Provisional. Equal records share a rank. 8 playoff teams: each division's winner plus the best records, seeded by overall record. GB is from the overall leader; the small number is the margin in games over (+) or behind (−) the last playoff spot."})]);
  var tb=h("table",{class:"lv-t"}),hd=h("tr");["#","Team","W-L-T","GB","Playoffs"].forEach(function(x,i){hd.appendChild(h("th",{text:x,class:i>=2&&i<4?"num":"",title:i===3?"Games behind the overall leader":i===4?"Seed if in; the small number is the margin in games over (+) or behind (−) the last playoff spot":""}));});
  tb.appendChild(h("thead",null,[hd]));var body=h("tbody"),prevIn=null;
  rows.forEach(function(r,i){
    var tr=h("tr",{class:"st-"+(r.playoff||"")+(r.tied?" tied":"")+(r.team===me()?" me":""),"data-team":r.team});
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
var KIND={out_starter:"Out player held a starting slot while an eligible bench player had a game",empty_slot:"Starting slot left empty while an eligible bench player had a game",star_benched:"Star (top 50) on the bench with a game"};
function shortDate(iso){try{return new Intl.DateTimeFormat("en-GB",{day:"numeric",month:"short",timeZone:"UTC"}).format(new Date(iso+"T12:00:00Z"));}catch(e){return iso;}}
function lineups(){
  var L=FEED.lineupChecks;if(!L||SRC!=="live")return null;
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
function reverse(){
  var f=FEED,box=h("section",{class:"lv-card lv-rev"},[h("div",{class:"lv-ct",text:"PROJECTED REVERSE ORDER"}),h("div",{class:"lv-cs",text:"Worst record first. Not the draft order."})]);
  var ol=h("ol",{class:"lv-ol"});f.projectedReverse.forEach(function(x){ol.appendChild(h("li",null,[chip(x.team),x.tied?h("small",{text:" tied",title:"Level with a neighbour; shown in the official order"}):null]));});
  box.appendChild(ol);return box;}
function dayOK(){return !!FEED.dayDate&&FEED.matchups.some(function(m){return m.day;});}
function dayWord(){return FEED.dayDate?shortDate(FEED.dayDate):"";}
function ratio(pair){return pair&&pair[1]?pair[0]+"/"+pair[1]:"";}
function rosterTable(side,dayDate,mode){
  mode=mode==="day"&&dayOK()?"day":"week";
  var COLS=(mode==="day"?[["min","MIN"]]:[]).concat(LINE),day=mode==="day",when=dayWord()||"the latest day";
  var t=h("table",{class:"lv-r"+(day?" dayview":"")}),cg=h("colgroup");cg.appendChild(h("col",{class:"c-sl"}));cg.appendChild(h("col",{class:"c-nm"}));COLS.forEach(function(){cg.appendChild(h("col",{class:"c-n"}));});t.appendChild(cg);
  var hd=h("tr");["","Player"].concat(COLS.map(function(c){return c[1];})).forEach(function(x,i){hd.appendChild(h("th",{text:x,class:i>1?"num":""}));});
  t.appendChild(h("thead",null,[hd]));var tb=h("tbody");t.appendChild(tb);
  var haveDay=side.roster.some(function(r){return r.d;});
  var slotOf=function(r){return day?(r.ds||r.s):r.s;};
  var groups=[["STARTERS",day?"day: "+when:"week totals, starting days only",function(r){var x=slotOf(r);return x!=="BN"&&x!=="IL";}],
    ["BENCH",day?"day: "+when:"stats from "+when+" only, not counted",function(r){return slotOf(r)==="BN";}],
    ["INJURED LIST",day?"day: "+when:"stats from "+when+" only, not counted",function(r){return slotOf(r)==="IL";}]];
  groups.forEach(function(g){var rows=side.roster.filter(function(r){return r.n==null?!day&&g[2](r):g[2](r);});if(!rows.length)return;var bench=g[0]!=="STARTERS";
    var gh=h("tr",{class:"gh"+(bench?" off":"")}),td=h("td",{colspan:String(COLS.length+2)},[h("b",{text:g[0]}),h("small",{text:g[1]+((bench||day)&&!haveDay?" (arrives with the next feed update)":"")})]);gh.appendChild(td);tb.appendChild(gh);
    rows.forEach(function(r){var useDay=day||bench,vals=lineOf(useDay?r.d:r.l),fg=useDay?r.dfg:r.wfg,ft=useDay?r.dft:r.wft;
      var rk=r.n!=null&&r.p&&RK[r.p];
      var tr=h("tr",{class:(r.n==null?"empty ":"")+(bench?"off ":"")+(rk?"rk":"")});
      tr.appendChild(h("td",{class:"sl",text:slotOf(r)}));
      var nm=h("td",{class:"nm"},[h("b",{text:r.n==null?"(empty)":r.n})]);
      if(r.p&&window.NBA_PLAYER){nm.classList.add("pl");nm.setAttribute("tabindex","0");nm.setAttribute("role","button");var op=function(){NBA_PLAYER.open(NBA_PLAYER.keyOf(r.p));};nm.addEventListener("click",op);nm.addEventListener("keydown",function(e){if(e.key==="Enter"){e.preventDefault();op();}});}
      if(rk){var rm=window.NBA_RK&&window.NBA_PLAYER?NBA_RK.mark(NBA_PLAYER.keyOf(r.p)):null;nm.appendChild(rm||h("span",{class:"lv-rk",title:"2026 rookie",text:"R"}));}
      if(r.n!=null){if(r.st)nm.appendChild(h("span",{class:"lv-st",text:r.st}));if(r.g||r.gl!=null)nm.appendChild(h("small",{class:r.gs||"",text:(r.t?r.t+" · ":"")+(r.g||"no game today")+(r.gl!=null?" · "+r.gl+" left":"")}));}
      tr.appendChild(nm);
      var dash=r.n!=null&&noStats(r,vals);
      COLS.forEach(function(c,ci){
        if(c[0]==="min"){tr.appendChild(h("td",{class:"num",text:r.n==null||dash||!r.dm?(r.n==null?"":"–"):r.dm}));return;}
        var i=LINE.indexOf(c),v=vals?vals[i]:null,ra=c[0]==="fgPct"?ratio(fg):c[0]==="ftPct"?ratio(ft):"";
        var td=h("td",{class:"num"+(!dash&&v===0?" z":"")},[r.n==null||!vals?"":dash?"–":cell(v,c[0])]);
        if(ra&&!dash)td.appendChild(h("small",{text:ra,title:(c[0]==="fgPct"?"Field goals":"Free throws")+" made/attempted"}));
        tr.appendChild(td);});
      tb.appendChild(tr);});});
  return t;}
function matchup(m){
  var a=m.teams[0],b=m.teams[1],dm=VIEW==="day"&&m.day?m.day:null;
  var sc=dm?dm.score:m.score,cats=dm?dm.cats:m.cats,sa=dm?dm.stats[0]:a.stats,sb=dm?dm.stats[1]:b.stats;
  var lead=sc[0]>sc[1]?0:sc[1]>sc[0]?1:-1;
  var mine=a.team===me()||b.team===me();
  var card=h("section",{class:"lv-card lv-m"+(mine?" me":""),"data-m":String(a.yahooId)});
  if(mine)card.appendChild(h("div",{class:"lv-ribbon",text:"YOUR MATCHUP"}));
  
  var mh=h("div",{class:"lv-mh",role:"button",tabindex:"0","aria-expanded":"false",title:"Open or close the rosters"},[h("div",{class:"lv-side"+(lead===0?" lead":"")},[chip(a.team),h("b",{class:"lv-w",text:String(sc[0])})]),
    h("div",{class:"lv-mid",text:sc[2]?sc[2]+" tied":"vs"}),
    h("div",{class:"lv-side flip"+(lead===1?" lead":"")},[h("b",{class:"lv-w",text:String(sc[1])}),chip(b.team)])]);card.appendChild(mh);
  card.appendChild(h("div",{class:"lv-cap"+(dm?" day":"")},[h("b",{text:dm?"DAY · "+shortDate(dm.date):"WEEK TOTALS"}),h("span",{text:dm?"the starters' stats that day; the week decides the matchup":"Yahoo's scoring for the matchup"})]));
  var grid=h("div",{class:"lv-cats"});
  CATS.forEach(function(c){var w=cats[c[0]],va=val(c[0],sa[c[0]],sa),vb=val(c[0],sb[c[0]],sb);
    var na=num(c[0],sa),nb=num(c[0],sb),mg=margin(c[0],na,nb),vola=volume(c[0],sa),volb=volume(c[0],sb);
    var row=h("div",{class:"lv-c "+(w==="a"?"wa":w==="b"?"wb":w==="t"?"wt":"")},[h("span",{class:"va"},[va,vola?h("small",{text:vola}):null]),h("span",{class:"cl"},[c[1],mg?h("small",{class:"mg",text:w==="a"?"◂ "+mg:w==="b"?mg+" ▸":mg,title:"Lead in "+c[1]+(c[0]==="to"?" (fewer is better)":"")}):null]),h("span",{class:"vb"},[vb,volb?h("small",{text:volb}):null])]);
    var tug=h("i",{class:"tug"});tug.style.setProperty("--p",share(c[0],na,nb)+"%");row.appendChild(tug);grid.appendChild(row);});
  card.appendChild(grid);
  var tp=function(s){var n=s.toPlay||{upcoming:0,live:0};return n.upcoming+n.live;};
  var gl=function(x){return x.gamesLeft==null?"":" · "+(FEED.gamesLeftComplete===false?"~":"")+x.gamesLeft+" games left";};
  card.appendChild(h("div",{class:"lv-tp",title:"Today's games still to start or finish, and every game left this week for the starting lineup (players who are out are not counted)"},[h("span",{text:tp(a)+" to play today"+gl(a)}),h("span",{text:tp(b)+" to play today"+gl(b)})]));
  var det=h("details",{class:"lv-det"},[h("summary",{title:"Click the scores or this bar to open and close"},[h("span",{text:"Rosters"})])]);if(OPEN[a.yahooId])det.setAttribute("open","");
  var shut=function(){det.open=false;var r=card.getBoundingClientRect(),bar=document.querySelector(".topbar"),top=bar?bar.offsetHeight:0;if(r.top<top)window.scrollTo({top:window.pageYOffset+r.top-top-8});};
  det.addEventListener("toggle",function(){OPEN[a.yahooId]=det.open;card.classList.toggle("open",det.open);mh.setAttribute("aria-expanded",det.open?"true":"false");});mh.setAttribute("aria-expanded",OPEN[a.yahooId]?"true":"false");card.classList.toggle("open",!!OPEN[a.yahooId]);
  var flip=function(e){if(e.target.closest("a,button"))return;if(det.open)shut();else det.open=true;};mh.addEventListener("click",flip);mh.addEventListener("keydown",function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();flip(e);}});
  var bar=h("div",{class:"lv-bar"},[chip(a.team),h("span",{class:"vs",text:"vs"}),chip(b.team),h("button",{type:"button",class:"lv-x",text:"Close ✕",title:"Close the rosters (Esc)"})]);
  bar.querySelector(".lv-x").addEventListener("click",shut);
  var cols=h("div",{class:"lv-cols"});
  m.teams.forEach(function(s,i){var rc=h("div",{class:"lv-rc "+(i?"cb":"ca")},[h("div",{class:"lv-rt"},[chip(s.team)]),h("div",{class:"lv-wrap"},[rosterTable(s,FEED.dayDate,VIEW)])]);cols.appendChild(rc);});
  det.appendChild(bar);det.appendChild(cols);card.appendChild(det);return card;}

/* ---------- roto / raw stats / all-play (descriptive, for the week in progress: the league is head-to-head) ---------- */
var PANES=[["matchups","Matchups"],["standings","Standings"],["roto","Roto"],["stats","Raw stats"],["allplay","All-play"]],SORT=null,FOCUS=null;
function narrow(){return !!(window.matchMedia&&!window.matchMedia("(min-width:1100px)").matches);}   /* one column: standings become a pane of their own */
function rotoData(){   /* {yahooId: stats} for all 16 teams from the matchups, once the week has numbers */
  if(SRC!=="live"||FEED.weekStatus!=="LIVE"||!window.NBA_ROTO)return null;
  var st={},side={},opp={};
  FEED.matchups.forEach(function(m){var a=m.teams[0],b=m.teams[1];
    [a,b].forEach(function(t,i){st[t.yahooId]=t.stats;side[t.yahooId]={team:t.team,printed:t.printed,wins:m.score[i],stats:t.stats};});
    opp[a.yahooId]=b.yahooId;opp[b.yahooId]=a.yahooId;});
  if(Object.keys(st).length!==16)return null;
  return {stats:st,side:side,opp:opp,roto:NBA_ROTO.roto(st),ap:NBA_ROTO.allPlay(st)};}
function heat(p){return "h"+Math.max(-3,Math.min(3,Math.round((p-8.5)/2.5)));}   /* points 1..16 -> colour step -3..3 */
function pts(p){return p==null?"–":(Math.round(p*2)/2).toString();}
function nameOf(id){var t=TM[id];return t?t.short:id;}
function order(R){   /* one team order for every view: by the chosen category's points, else by roto rank */
  return Object.keys(R.roto).map(Number).sort(function(a,b){
    if(SORT){var d=(R.roto[b].points[SORT]||0)-(R.roto[a].points[SORT]||0);if(d)return d;}
    return R.roto[a].rank-R.roto[b].rank||a-b;});}
function dayOfWeek(){try{var w=new Intl.DateTimeFormat("en-US",{timeZone:"America/Los_Angeles",weekday:"short"}).format(new Date(FEED.asOf));return ({Mon:1,Tue:2,Wed:3,Thu:4,Fri:5,Sat:6,Sun:7})[w]||null;}catch(e){return null;}}
function paneHead(title,sub,legend){
  var n=dayOfWeek(),early=n&&n<=2;
  return h("div",{class:"lv-ph"},[h("div",{class:"lv-ct"},[title,h("span",{class:"lv-tag",text:"Descriptive only · the league is head-to-head",title:"The standings are W-L-T. Yahoo corrects stats after games, so these numbers can move."})]),
    h("div",{class:"lv-cs"},[sub,n?h("span",{class:"lv-day"+(early?" early":""),text:" · Day "+n+" of 7"+(early?": early in the week, ranks swing and many teams tie":"")}):null]),legend||null]);}
function sortHead(R,key,label,i,extra){   /* a column header that sorts every view by that category */
  var on=SORT===key,th=h("th",{scope:"col",class:i?"num":"","aria-sort":on?"descending":"none"});
  if(!key){th.textContent=label;return th;}
  var b=h("button",{type:"button",class:"lv-th"+(on?" on":""),text:label,title:"Sort by "+label+(on?" (click again to go back to the roto rank)":"")});
  b.addEventListener("click",function(){SORT=on?null:key;render();});th.appendChild(b);return th;}
function rotoPane(R){
  var ids=order(R),mt=me();
  var t=h("table",{class:"lv-ro"},[h("caption",{class:"sr",text:"Roto points by category for week "+FEED.week})]),hd=h("tr");
  hd.appendChild(sortHead(R,null,"Team",0));CATS.forEach(function(c){hd.appendChild(sortHead(R,c[0],c[1],1));});hd.appendChild(sortHead(R,null,"Total",1));hd.appendChild(sortHead(R,null,"Rank",1));
  t.appendChild(h("thead",null,[hd]));var tb=h("tbody");
  ids.forEach(function(id){var r=R.roto[id],tr=h("tr",{class:R.side[id].team===mt?"me":""});
    tr.appendChild(h("th",{scope:"row",class:"tm"},[chip(R.side[id].team)]));
    CATS.forEach(function(c){var p=r.points[c[0]];tr.appendChild(h("td",{class:"num "+(p==null?"":heat(p)),text:pts(p)}));});
    var tot=r.total;tr.appendChild(h("td",{class:"num tot "+heat(tot/9),text:pts(tot)}));
    var tied=ids.filter(function(u){return R.roto[u].rank===r.rank;}).length>1;
    tr.appendChild(h("td",{class:"num rk",text:(tied?"T-":"")+r.rank}));tb.appendChild(tr);});
  t.appendChild(tb);return h("section",{class:"lv-card lv-pane"},[paneHead("ROTO · WEEK "+FEED.week,"16 points for the best in each category, 1 for the worst. Fewer turnovers is better; level teams share the average.",null),h("div",{class:"lv-wrap lv-sw"},[t])]);}
function statsPane(R){
  var ids=order(R),mt=me();
  var t=h("table",{class:"lv-ro lv-rs"},[h("caption",{class:"sr",text:"Raw category totals for week "+FEED.week})]),hd=h("tr");
  hd.appendChild(sortHead(R,null,"Team",0));CATS.forEach(function(c){hd.appendChild(sortHead(R,c[0],c[1],1));});
  var sc=sortHead(R,null,"Score",1);sc.title="Category wins in this week's matchup (Yahoo's score)";hd.appendChild(sc);
  t.appendChild(h("thead",null,[hd]));var tb=h("tbody");
  ids.forEach(function(id){var s=R.side[id],tr=h("tr",{class:s.team===mt?"me":""});
    tr.appendChild(h("th",{scope:"row",class:"tm"},[chip(s.team)]));
    CATS.forEach(function(c){var p=R.roto[id].points[c[0]],v=val(c[0],s.stats[c[0]],s.stats),vo=volume(c[0],s.stats);
      tr.appendChild(h("td",{class:"num "+(p==null?"":heat(p))},[v,vo?h("small",{text:vo}):null]));});
    tr.appendChild(h("td",{class:"num sc",text:String(s.printed!=null?s.printed:s.wins)}));tb.appendChild(tr);});
  t.appendChild(tb);return h("section",{class:"lv-card lv-pane"},[paneHead("RAW STATS · WEEK "+FEED.week,"Colour shows where the team ranks in that category (fewer turnovers is better). Score = category wins in its matchup.",null),h("div",{class:"lv-wrap lv-sw"},[t])]);}
function mstep(m){return m>=5?"g3":m>=3?"g2":m>=1?"g1":m===0?"g0":m>=-2?"r1":m>=-4?"r2":"r3";}
function wlt(c){return c.w+"–"+c.l+(c.t?"–"+c.t:"");}
function detailNode(R,a,b){   /* the nine categories of one pairing */
  var c=R.ap.cells[a][b],box=h("div",{class:"lv-dt-in"});
  box.appendChild(h("div",{class:"lv-dh"},[chip(R.side[a].team),h("b",{text:wlt(c)}),chip(R.side[b].team),R.opp[a]===b?h("small",{text:"this week's matchup"}):null]));
  var g=h("div",{class:"lv-dg"});CATS.forEach(function(cat){var d=c.detail[cat[0]],va=val(cat[0],R.stats[a][cat[0]],R.stats[a]),vb=val(cat[0],R.stats[b][cat[0]],R.stats[b]);
    g.appendChild(h("div",{class:"r "+(d===1?"wa":d===-1?"wb":"wt")},[h("span",{class:"va",text:va}),h("span",{class:"cl",text:cat[1]}),h("span",{class:"vb",text:vb})]));});
  box.appendChild(g);return box;}
function allPane(R){
  var ids=order(R),mt=me(),mineId=ids.filter(function(i){return R.side[i].team===mt;})[0];
  var legend=h("div",{class:"lv-lg",role:"list","aria-label":"Colour key"});[["g3","7–2 or better"],["g2","6–3"],["g1","5–4"],["g0","Draw"],["r1","4–5"],["r2","3–6"],["r3","2–7 or worse"]].forEach(function(x){legend.appendChild(h("span",{class:"c "+x[0],role:"listitem",text:x[1]}));});
  var box=h("section",{class:"lv-card lv-pane"},[paneHead("ALL-PLAY · WEEK "+FEED.week,"Each team against all 15 others, category by category. Outlined cells are the real matchups.",legend)]);
  var detail=h("div",{class:"lv-dt",id:"lv-dt","aria-live":"polite"});
  var fid=FOCUS!=null&&R.stats[FOCUS]?FOCUS:(mineId!=null?mineId:ids[0]);
  var pick=PICK&&R.ap.cells[PICK[0]]&&R.ap.cells[PICK[0]][PICK[1]]&&(!narrow()||PICK[0]===fid)?PICK:(narrow()?[fid,R.opp[fid]]:(mineId!=null?[mineId,R.opp[mineId]]:[ids[0],R.opp[ids[0]]]));
  function select(a,b,scroll){PICK=[a,b];detail.textContent="";detail.appendChild(detailNode(R,a,b));if(window.NBA_MONO)window.NBA_MONO(detail);
    [].forEach.call(box.querySelectorAll(".sel"),function(x){x.classList.remove("sel");});
    [].forEach.call(box.querySelectorAll('[data-a="'+a+'"][data-b="'+b+'"]'),function(x){x.classList.add("sel");});
    if(scroll){var r=detail.getBoundingClientRect(),nav=(document.querySelector(".topbar")||{}).offsetHeight||0;if(r.top<nav||r.bottom>window.innerHeight)detail.scrollIntoView({block:"nearest",behavior:"smooth"});}}
  box.appendChild(detail);
  /* wide screens: the 16 x 16 matrix, one tab stop, arrow keys move between cells */
  var t=h("table",{class:"lv-ap"},[h("caption",{class:"sr",text:"All-play matrix for week "+FEED.week+": row team's category wins and losses against the column team"})]),hd=h("tr",null,[h("th",{scope:"col"})]);
  ids.forEach(function(b){hd.appendChild(h("th",{scope:"col",class:"num",text:nameOf(R.side[b].team),title:nameOf(R.side[b].team)}));});hd.appendChild(h("th",{scope:"col",class:"num",text:"All-play",title:"Matchups won–lost–tied against all 15 other teams"}));
  t.appendChild(h("thead",null,[hd]));var tb=h("tbody"),cells=[];
  ids.forEach(function(a,ri){var tr=h("tr",{class:R.side[a].team===mt?"me":""});tr.appendChild(h("th",{scope:"row",class:"tm"},[chip(R.side[a].team)]));cells[ri]=[];
    ids.forEach(function(b,ci){if(a===b){tr.appendChild(h("td",{class:"cell self",text:"—","aria-hidden":"true"}));cells[ri][ci]=null;return;}
      var c=R.ap.cells[a][b],td=h("td",{class:"cell "+mstep(c.margin)+(R.opp[a]===b?" act":""),"data-a":String(a),"data-b":String(b),tabindex:"-1",role:"button",
        "aria-label":nameOf(R.side[a].team)+" against "+nameOf(R.side[b].team)+": "+c.w+" wins, "+c.l+" losses, "+c.t+" ties",text:wlt(c)});
      td.addEventListener("click",function(){select(a,b,true);});cells[ri][ci]=td;tr.appendChild(td);});
    var r=R.ap.record[a];tr.appendChild(h("td",{class:"num ap",text:r[0]+"–"+r[1]+"–"+r[2]}));tb.appendChild(tr);});
  t.appendChild(tb);
  var stop=null;function setStop(td){if(stop)stop.setAttribute("tabindex","-1");stop=td;td.setAttribute("tabindex","0");}
  var start=cells.reduce(function(f,row){return f||row.filter(Boolean).filter(function(td){return td.getAttribute("data-a")===String(pick[0])&&td.getAttribute("data-b")===String(pick[1]);})[0]||null;},null)||cells[0][1];setStop(start);
  t.addEventListener("focusin",function(e){if(e.target.classList&&e.target.classList.contains("cell")&&e.target.getAttribute("role")==="button")setStop(e.target);});
  t.addEventListener("keydown",function(e){var td=e.target;if(!td.classList||!td.classList.contains("cell"))return;
    if(e.key==="Enter"||e.key===" "){e.preventDefault();select(Number(td.getAttribute("data-a")),Number(td.getAttribute("data-b")),true);return;}
    var d={ArrowRight:[0,1],ArrowLeft:[0,-1],ArrowDown:[1,0],ArrowUp:[-1,0],Home:[0,-99],End:[0,99]}[e.key];if(!d)return;e.preventDefault();
    var ri=ids.indexOf(Number(td.getAttribute("data-a"))),ci=ids.indexOf(Number(td.getAttribute("data-b")));
    var nr=Math.max(0,Math.min(15,ri+d[0])),nc=Math.max(0,Math.min(15,ci+d[1])),n=cells[nr][nc];
    if(!n){nc=Math.max(0,Math.min(15,nc+(d[1]>=0?1:-1)));n=cells[nr][nc]||cells[nr][nc+(d[1]>=0?-2:2)];}
    if(n){setStop(n);n.focus();}});
  box.appendChild(h("div",{class:"lv-wrap lv-sw lv-mx"},[t]));
  /* phones: a list for one team, 44px rows instead of 40 x 26 matrix cells */
  var sel=h("select",{class:"lv-fs","aria-label":"Show all-play for"});ids.forEach(function(i){var o=h("option",{value:String(i),text:nameOf(R.side[i].team)});if(i===fid)o.selected=true;sel.appendChild(o);});
  sel.addEventListener("change",function(){FOCUS=Number(sel.value);PICK=[FOCUS,R.opp[FOCUS]];render();});
  var list=h("div",{class:"lv-fl"},[h("label",{class:"lv-fh"},[h("span",{text:"All-play for "}),sel])]);
  ids.filter(function(i){return i!==fid;}).sort(function(x,y){return R.ap.cells[fid][y].margin-R.ap.cells[fid][x].margin;}).forEach(function(o){
    var c=R.ap.cells[fid][o],row=h("button",{type:"button",class:"lv-fr "+mstep(c.margin)+(R.opp[fid]===o?" act":""),"data-a":String(fid),"data-b":String(o),"aria-label":nameOf(R.side[fid].team)+" against "+nameOf(R.side[o].team)+": "+wlt(c)},
      [chip(R.side[o].team),h("b",{text:wlt(c)}),h("span",{class:"dots","aria-hidden":"true"},CATS.map(function(cat){return h("i",{class:c.detail[cat[0]]===1?"w":c.detail[cat[0]]===-1?"l":"t",title:cat[1]});})),R.opp[fid]===o?h("small",{text:"matchup"}):null]);
    row.addEventListener("click",function(){select(fid,o,true);});list.appendChild(row);});
  box.appendChild(list);
  select(pick[0],pick[1],false);return box;}
function paneBody(R){return PANE==="roto"?rotoPane(R):PANE==="stats"?statsPane(R):allPane(R);}

/* ---------- render ---------- */
function snapshot(){   /* what the user is looking at, so a refresh does not take it away */
  var sc=[].map.call(root.querySelectorAll(".lv-wrap,.lv-cols"),function(e){return e.scrollLeft;}),f=document.activeElement,k=null;
  if(f&&root.contains(f)){k=f.id?"#"+f.id:f.getAttribute&&f.getAttribute("data-a")?'[data-a="'+f.getAttribute("data-a")+'"][data-b="'+f.getAttribute("data-b")+'"]':f.classList&&f.classList.contains("lv-mh")?".lv-mh[data-m]":null;
    if(f.classList&&f.classList.contains("lv-mh")){var c=f.closest(".lv-m");k=c?'.lv-m[data-m="'+c.getAttribute("data-m")+'"] .lv-mh':null;}}
  return {sc:sc,focus:k};}
function restore(snap){
  var els=root.querySelectorAll(".lv-wrap,.lv-cols");snap.sc.forEach(function(x,i){if(els[i]&&x)els[i].scrollLeft=x;});
  if(snap.focus){var el=root.querySelector(snap.focus);if(el&&el.focus)try{el.focus({preventScroll:true});}catch(e){el.focus();}}}
function closeness(m){return Math.abs(m.score[0]-m.score[1]);}
function render(){
  var snap=snapshot();
  root.textContent="";var tb=document.querySelector(".topbar");if(tb)root.style.setProperty("--lv-nav",tb.offsetHeight+"px");
  root.appendChild(head());var n=note();if(n)root.appendChild(n);
  var grid=h("div",{class:"lv-grid"}),left=h("div",{class:"lv-left"}),right=h("div",{class:"lv-right"});
  left.appendChild(standings());var lc=lineups();if(lc)left.appendChild(lc);left.appendChild(reverse());
  var title=SRC==="live"?"MATCHUPS":"LAST FINISHED WEEK";
  var ms=h("div",{class:"lv-ms"}),mt=me();
  FEED.matchups.slice().sort(function(x,y){var f=function(m){return m.teams.some(function(t){return t.team===mt;})?0:1;};return f(x)-f(y)||closeness(x)-closeness(y)||x.teams[0].yahooId-y.teams[0].yahooId;}).forEach(function(m){ms.appendChild(matchup(m));});
  var allBtn=h("button",{type:"button",class:"lv-all",id:"lv-all"});
  var anyOpen=function(){return FEED.matchups.some(function(m){return OPEN[m.teams[0].yahooId];});};
  var setAll=function(){var open=!anyOpen();FEED.matchups.forEach(function(m){OPEN[m.teams[0].yahooId]=open;});ms.querySelectorAll(".lv-det").forEach(function(d){d.open=open;});allBtn.textContent=open?"Collapse all":"Expand all";};
  allBtn.textContent=anyOpen()?"Collapse all":"Expand all";allBtn.addEventListener("click",setAll);
  var seg=null;
  if(dayOK()){seg=h("div",{class:"lv-seg",role:"group","aria-label":"Which stats to show"});
    [["week","Week totals"],["day","Day · "+dayWord()]].forEach(function(o){var b=h("button",{type:"button",class:VIEW===o[0]?"on":"","aria-pressed":VIEW===o[0]?"true":"false",text:o[1]});b.addEventListener("click",function(){if(VIEW!==o[0]){VIEW=o[0];render();}});seg.appendChild(b);});}
  else VIEW="week";
  var R=rotoData(),nar=narrow();
  var avail=PANES.filter(function(o){return o[0]==="matchups"||(o[0]==="standings"?nar:!!R);});
  if(!avail.some(function(o){return o[0]===PANE;}))PANE="matchups";
  if(avail.length>1){var strip=h("div",{class:"lv-views",role:"tablist","aria-label":"What to show"});
    avail.forEach(function(o){var b=h("button",{type:"button",role:"tab","data-pane":o[0],class:PANE===o[0]?"on":"","aria-selected":PANE===o[0]?"true":"false",text:o[1]});b.addEventListener("click",function(){if(PANE!==o[0]){PANE=o[0];try{localStorage.setItem(PANE_KEY,PANE);}catch(e){}render();}});strip.appendChild(b);});
    root.appendChild(strip);}
  grid.className="lv-grid pane-"+PANE;
  if(R&&PANE!=="matchups"&&PANE!=="standings")right.appendChild(paneBody(R));
  else if(PANE!=="standings"||!nar){right.appendChild(h("div",{class:"lv-tb"},[h("div",{class:"lv-st",text:title}),seg,allBtn]));right.appendChild(ms);}
  grid.appendChild(left);grid.appendChild(right);root.appendChild(grid);
  /* every card can be exported from where it is */
  var add=function(el,host,label,w,name){if(!el||!host)return;var b=shareEl(label,function(){return el;},{width:w,name:name,strip:".share-btn,.lv-det"});if(b){b.classList.add("lv-sh");host.appendChild(b);}};
  add(root.querySelector(".lv-stand"),root.querySelector(".lv-stand .lv-ct"),"live standings",430,"live-standings");
  add(root.querySelector(".lv-lc"),root.querySelector(".lv-lc .lv-ct"),"lineup checks",430,"lineup-checks");
  var pn=root.querySelector(".lv-pane");if(pn)add(pn,pn.querySelector(".lv-ph .lv-ct"),PANE==="roto"?"roto rankings":PANE==="stats"?"raw stats":"all-play",PANE==="roto"?760:PANE==="stats"?820:1000,"live-"+PANE);
  [].forEach.call(root.querySelectorAll(".lv-m"),function(c){var cap=c.querySelector(".lv-cap"),nm=[].map.call(c.querySelectorAll(".lv-mh .tchip"),function(x){return x.textContent.replace(/^\W+/,"");}).join(" v ");add(c,cap,"matchup "+nm,430,"matchup");});
  if(window.NBA_MONO)window.NBA_MONO(root);
  restore(snap);
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
document.addEventListener("nba:me",function(){render();});
if(window.matchMedia)try{window.matchMedia("(min-width:1100px)").addEventListener("change",function(){render();});}catch(e){}
(function(){var tb=document.querySelector(".topbar"),set=function(){if(tb)root.style.setProperty("--lv-nav",tb.offsetHeight+"px");};   /* the site header changes height with the window */
  if(window.ResizeObserver&&tb)new ResizeObserver(set).observe(tb);window.addEventListener("resize",set);})();
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
     var rows=f.table.map(function(r){return {c:[(r.tied?"T-":"")+r.rank,{team:r.team},r.w+"-"+r.l+(r.t?"-"+r.t:""),pct(r.pct),r.moved&&live?{t:r.moved>0?"▲"+r.moved:"▼"+(-r.moved),fg:r.moved>0?"#0f7a40":"#b42318"}:"",{t:r.playoff==="in"?"IN #"+r.seed:r.playoff==="bubble"?"BUBBLE":"OUT",pill:r.playoff==="in"?"ok":r.playoff==="bubble"?"warn":"mute"}]};});
     return [{label:"Standings",name:"live-standings.png",alt:"Standings",snap:function(){return snapFor("standings",430);},doc:{title:live?"Standings if the week ended now":"Standings",tag:live?"PROVISIONAL":"",sub:(live?"Week "+f.week+" · as of "+ict(f.asOf)+" · ":"")+"equal records share a rank",
       blocks:[{t:"table",cols:[{h:"#",w:1,m:1},{h:"TEAM",w:3.4},{h:"W-L-T",w:2,a:"r",m:1},{h:"PCT",w:1.6,a:"r",m:1},{h:"MOVE",w:1.4,a:"r"},{h:"PLAYOFFS",w:2,a:"r"}],rh:44,rows:rows}],foot:"NBA Talk VN Dynasty",link:location.origin+location.pathname+"#live"}}];}},
   {id:"live-matchups",label:live?"This week's matchups":"Last finished week",desc:"Category score of every matchup",pages:function(){
     var cards=f.matchups.map(function(m){var a=m.teams[0],b=m.teams[1];
       return {team:a.team,head:m.score[0]+"–"+m.score[1]+(m.score[2]?"–"+m.score[2]:""),sub:"vs "+(TM[b.team]?TM[b.team].short:b.name),lines:CATS.map(function(c){var w=m.cats[c[0]];
         return {l:c[1]+"  "+val(c[0],a.stats[c[0]],a.stats)+" – "+val(c[0],b.stats[c[0]],b.stats),r:w==="a"?"✓":w==="b"?"✗":w==="t"?"=":"",tone:w==="a"?"ok":w==="b"?"bad":"mute"};})};});
     return [{label:"Matchups",name:"live-matchups.png",alt:"Matchups",snap:function(){return snapFor("matchups",860);},doc:{title:live?"Week "+f.week+" matchups":"Last finished week",tag:live?"PROVISIONAL":"",sub:live?"as of "+ict(f.asOf):"",blocks:[{t:"cards",cols:2,cards:cards}],foot:"NBA Talk VN Dynasty",link:location.origin+location.pathname+"#live"}}];}}].concat(rotoExports());}
function rotoExports(){   /* roto, raw stats and all-play as images/text, once the week has numbers */
  var R=rotoData();if(!R)return [];
  var ids=Object.keys(R.roto).map(Number).sort(function(a,b){return R.roto[a].rank-R.roto[b].rank||a-b;}),sub="Week "+FEED.week+" · as of "+ict(FEED.asOf)+" · descriptive only, the league is head-to-head";
  var HEAT={"h3":["#a4e4b9","#17492b"],"h2":["#d0f1dd","#17492b"],"h1":["#ebf8f0","#1d3b2a"],"h0":["#ffffff","#12264d"],"h-1":["#fdecee","#5c1f2a"],"h-2":["#f6cbd1","#6a1f2c"],"h-3":["#efadb8","#6a1f2c"]};
  function hc(t,p){if(p==null)return t;var x=HEAT[heat(p)];return {t:t,bg:x[0],fg:x[1]};}   /* the page's heat colours, in the image too */
  function page(name,label,title,cols,rows,kind,width){return [{label:label,name:name+".png",alt:label,snap:kind?function(){return snapFor(kind,width);}:null,doc:{title:title,tag:"PROVISIONAL",sub:sub,blocks:[{t:"table",cols:cols,rh:40,rows:rows}],foot:"NBA Talk VN Dynasty",link:location.origin+location.pathname+"#live"}}];}
  var catCols=CATS.map(function(c){return {h:c[1],w:1.25,a:"c",m:1};});
  return [
   {id:"live-roto",label:"Roto rankings",desc:"Roto points for the week in progress",pages:function(){
     return page("live-roto","Roto","Week "+FEED.week+" roto rankings",[{h:"#",w:1,m:1},{h:"TEAM",w:3.2}].concat(catCols,[{h:"TOTAL",w:1.5,a:"c",m:1}]),
       ids.map(function(i){var r=R.roto[i];return {c:[String(r.rank),{team:R.side[i].team}].concat(CATS.map(function(c){return hc(pts(r.points[c[0]]),r.points[c[0]]);}),[hc(pts(r.total),r.total/9)])};}),"roto",760);}},
   {id:"live-rawstats",label:"Raw stats",desc:"Category totals of all 16 teams",pages:function(){
     return page("live-rawstats","Raw stats","Week "+FEED.week+" raw stats",[{h:"#",w:1,m:1},{h:"TEAM",w:3.2}].concat(catCols,[{h:"SCORE",w:1.4,a:"r",m:1}]),
       ids.map(function(i){var sd=R.side[i];return {c:[String(R.roto[i].rank),{team:sd.team}].concat(CATS.map(function(c){return hc(val(c[0],sd.stats[c[0]],sd.stats),R.roto[i].points[c[0]]);}),[String(sd.printed!=null?sd.printed:sd.wins)])};}),"stats",820);}},
   {id:"live-allplay",label:"All-play records",desc:"Each team against all 15 others, category by category",pages:function(){
     var order=ids.slice().sort(function(a,b){var x=R.ap.record[a],y=R.ap.record[b];return (y[0]-x[0])||(x[1]-y[1])||(R.roto[a].rank-R.roto[b].rank);});
     return page("live-allplay","All-play","Week "+FEED.week+" all-play",[{h:"#",w:1,m:1},{h:"TEAM",w:3.4},{h:"ALL-PLAY W-L-T",w:2.2,a:"c",m:1},{h:"ROTO",w:1.4,a:"c",m:1},{h:"MATCHUP",w:2.8,a:"r"}],
       order.map(function(i,k){var r=R.ap.record[i],o=R.opp[i],c=R.ap.cells[i][o];return {c:[String(k+1),{team:R.side[i].team},hc(r[0]+"-"+r[1]+"-"+r[2],1+15*(r[0]+r[2]/2)/15),hc(pts(R.roto[i].total),R.roto[i].total/9),{t:wlt(c)+" v "+nameOf(R.side[o].team),pill:c.margin>0?"ok":c.margin<0?"bad":"mute"}]};}),"allplay",1000);}}];}

function snapFor(kind,width){   /* a detached copy of one LIVE view, for the export hub's snapshot images */
  var R=rotoData(),node=null;
  if(kind==="standings")node=standings();
  else if(kind==="matchups"){node=h("div",{class:"lv-ms"});FEED.matchups.forEach(function(m){var c=matchup(m);var d=c.querySelector("details");if(d)d.remove();node.appendChild(c);});}
  else if(R&&kind==="roto")node=rotoPane(R);else if(R&&kind==="stats")node=statsPane(R);else if(R&&kind==="allplay"){node=allPane(R);var fl=node.querySelector(".lv-fl");if(fl)fl.remove();}
  if(!node)return null;if(window.NBA_MONO)window.NBA_MONO(node);
  return {node:node,wrap:[{tag:"section",id:"live",cls:"page"},{tag:"div",id:"live-root",cls:"",style:"--lv-nav:0px"}],width:width,foot:"NBA Talk VN Dynasty · LIVE · as of "+ict(FEED.asOf)};}
window.NBA_LIVE={standings:standingsFor,exports:exportsFor,snap:snapFor,source:function(){return SRC;},feed:function(){return FEED;},reload:function(){return load(true);},
  /* tests and tools hand a feed in directly */ set:function(d){accept(d,"live");render();}};
render();
load(false);
document.addEventListener("nba:tab",function(e){if(e.detail==="live")load(false);});
})();
