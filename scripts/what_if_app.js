(function(){
"use strict";
/* WHAT IF / GIẢ ĐỊNH renderer. (Cards are <article class="team-card"> on purpose: the Scenario Mode script rewrites every
   section.team-card from official state, and these simulated cards must never be touched by it.)
   All business numbers come precomputed from scripts/what_if.py; this file only
   renders them and re-adds a keeper set for manual swaps. It never reads or writes official state. */
var dataEl=document.getElementById("whatif-data"),root=document.getElementById("wi-root"),page=document.getElementById("what-if");
if(!dataEl||!root||!page)return;
var W=JSON.parse(dataEl.textContent);
var S={on:false,snap:W.default,view:"same",sort:"team",open:{},edits:{},tips:{},det:{},pane:"wi",animate:true,flash:null};
var MONTHS=["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"];
var ST={UNDER_FLOOR:["UNDER FLOOR","st-under","gap-floor"],AT_FLOOR:["AT FLOOR","st-floor","gap-atfloor"],IN_RANGE:["IN RANGE","st-range","gap-room"],NEAR_CEILING:["NEAR CEILING","st-near","gap-near"],AT_CEILING:["AT CEILING","st-ceiling","gap-ceiling"],OVER_CEILING:["OVER CEILING","st-over","gap-zero"]};
var COMP={WITHIN:"WITHIN",BELOW_FLOOR:"BELOW FLOOR",ABOVE_CEILING:"ABOVE CEILING"};
var CROWN="\uD83D\uDC51 ";
var reduce=window.matchMedia&&window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function h(tag,attrs,kids){var e=document.createElement(tag);if(attrs)for(var k in attrs){if(k==="class")e.className=attrs[k];else if(k==="text")e.textContent=attrs[k];else e.setAttribute(k,attrs[k]);}(kids||[]).forEach(function(c){if(c!=null)e.appendChild(typeof c==="string"?document.createTextNode(c):c);});return e;}
function sgn(n){return n>0?"+"+n:n<0?"−"+Math.abs(n):"0";}
function dcls(n){return n>0?"up":n<0?"down":"zero";}
function snap(){return W.snapshots[S.snap];}
function band(){return snap().band.whatIf;}
function fdate(iso){var p=String(iso).slice(0,10).split("-");return (+p[2])+" "+MONTHS[+p[1]-1]+" "+p[0];}
/* mirrors scripts/what_if.py classify(); parity-tested */
function classify(cap,floor,ceiling,near){
  if(cap>ceiling)return "OVER_CEILING";if(cap===ceiling)return "AT_CEILING";if(cap<floor)return "UNDER_FLOOR";if(cap===floor)return "AT_FLOOR";
  return ceiling-cap<=near?"NEAR_CEILING":"IN_RANGE";}
function compliance(cap,floor,ceiling){return cap>ceiling?"ABOVE_CEILING":cap<floor?"BELOW_FLOOR":"WITHIN";}
function gapText(st,toFloor,room){return st==="UNDER_FLOOR"?toFloor+" TO FLOOR":st==="AT_FLOOR"?"AT FLOOR":st==="AT_CEILING"?"AT CEILING":st==="OVER_CEILING"?(-room)+" OVER":room+" ROOM";}
function info(cap){var b=band();var st=classify(cap,b.floor,b.ceiling,snap().band.near);return {st:st,comp:compliance(cap,b.floor,b.ceiling),toFloor:Math.max(0,b.floor-cap),room:b.ceiling-cap};}
function teamByShort(s){var r=null;snap().teams.forEach(function(t){if(t.short===s)r=t;});return r;}
function tchip(t,label){var c=h("span",{class:"tchip",text:(t.crown?CROWN:"")+(label||t.short)});c.style.setProperty("--team-color",t.color);c.style.setProperty("--team-text",t.text);return c;}
function help(id,text){
  var wrap=document.createDocumentFragment();
  var b=h("button",{type:"button",class:"wi-help","aria-label":"Explain","aria-expanded":S.tips[id]?"true":"false",title:text,text:"?"});
  var tip=h("span",{class:"wi-tip",role:"note",text:text});tip.hidden=!S.tips[id];
  b.addEventListener("click",function(e){e.stopPropagation();S.tips[id]=!S.tips[id];tip.hidden=!S.tips[id];b.setAttribute("aria-expanded",S.tips[id]?"true":"false");});
  wrap.appendChild(b);wrap.appendChild(tip);return wrap;}
function animNum(span,from,to){
  span.textContent=String(to);
  if(!S.animate||reduce||from===to)return;
  var t0=null;span.textContent=String(from);
  function step(ts){if(t0===null)t0=ts;var p=Math.min(1,(ts-t0)/320);var v=Math.round(from+(to-from)*(1-Math.pow(1-p,3)));span.textContent=String(v);if(p<1)requestAnimationFrame(step);}
  requestAnimationFrame(step);}

/* ---------- keeper sets for Scenario B (simulation state only) ---------- */
function defaultSet(t){var s={};t.players.forEach(function(p){if(p.k1)s[p.k]=true;});return s;}
function keepSet(t){return S.edits[S.snap+"|"+t.id]||defaultSet(t);}
function setKeep(t,set){S.edits[S.snap+"|"+t.id]=set;}
function edited(t){var a=keepSet(t),b=defaultSet(t);return Object.keys(a).sort().join()!==Object.keys(b).sort().join();}
function keepTotal(t,set){var n=0;t.players.forEach(function(p){if(set[p.k])n+=p.c1;});return n;}
function keepCount(set){return Object.keys(set).length;}

/* ---------- header ---------- */
function provenance(m){
  return "Source file: "+m.sourceFile+" (sha256 "+m.sourceSha256.slice(0,10)+"…). File acquired "+m.fileAcquiredAt+". Yahoo league "+m.yahoo.leagueKey+
   ", league edit key "+m.yahoo.leagueEditKey+", newest player note "+(m.yahoo.latestPlayerNoteAt||"n/a")+". Hypothetical effective date "+m.effectiveDate+
   ". Salary = projected_auction_value ("+m.playerCount+" ranked players); players outside the list count as 0.";}
function header(){
  var s=snap(),m=s.meta,b=s.band;
  var bar=h("div",{class:"wi-bar"});
  var p1=h("span",{class:"meta-pill wi-pill-wi"},[h("span",{class:"pill-k",text:"SNAPSHOT"})," ",h("strong",{text:fdate(m.effectiveDate)}),help("prov",provenance(m))]);
  var capTxt=b.official.floor+"–"+b.official.ceiling+(b.formulaMatchesOfficial?"":"  →  "+b.whatIf.floor+"–"+b.whatIf.ceiling);
  var p2=h("span",{class:"meta-pill meta-pill-cap"},[h("span",{class:"pill-k",text:"CAP"}),h("span",{class:"pill-v",text:capTxt}),
    help("band",b.formulaMatchesOfficial?"Recomputed from the snapshot with the same top-144 benchmark model ("+b.whatIf.benchmark+" → floor "+b.whatIf.rawFloor+", ceiling "+b.whatIf.rawCeiling+"). The rounded band equals the official 131–178 band, so nothing moves.":
      "Recomputed from the snapshot with the same top-144 benchmark model: benchmark "+b.whatIf.benchmark+", floor "+b.whatIf.rawFloor+", ceiling "+b.whatIf.rawCeiling+". Differs from the official band; the official band is untouched.")]);
  var p3=h("span",{class:"meta-pill"},["SIMULATION · OFFICIAL RECORD UNCHANGED",help("sim","OFFICIAL here means the locked keeper freeze (before the pre-draft trades). Keeper selections, salaries, cuts, picks, lottery and the official FA/DRAFT 60 are read-only inputs here. Nothing on this page is written back; leaving What If shows the unchanged official board.")]);
  bar.appendChild(p1);bar.appendChild(p2);bar.appendChild(p3);
  if(W.order.length>1){var sel=h("select",{"aria-label":"Snapshot"});W.order.forEach(function(id){var o=h("option",{value:id,text:fdate(W.snapshots[id].meta.effectiveDate)});if(id===S.snap)o.selected=true;sel.appendChild(o);});
    sel.addEventListener("change",function(){S.snap=sel.value;S.open={};S.animate=true;render();});bar.appendChild(sel);}
  return bar;}
function seg(){
  var wrap=h("div");var g=h("div",{class:"wi-seg",role:"group","aria-label":"What-if view"});
  [["same","SAME KEEPERS"],["redo","REDO CUTS"],["fa","FA 60"]].concat(snap().now?[["now","NOW"]]:[]).concat(W.keeperBoard?[["keepers","KEEPERS"]]:[]).forEach(function(v){
    var b=h("button",{type:"button","aria-pressed":S.view===v[0]?"true":"false",text:v[1]});
    b.addEventListener("click",function(){S.view=v[0];S.animate=true;render();syncUrl();});g.appendChild(b);});
  wrap.appendChild(g);
  var tips={same:"Scenario A — every franchise keeps exactly its official nine, repriced at the snapshot. Deterministic.",
            redo:"Scenario B — a projection, not a reconstruction of intent: fewest-change legal keeper sets if managers had known these prices. Equally good alternatives are listed, never hidden.",
            fa:"The FA/DRAFT 60 rebuilt with the same ranking rules, once with the projected keeper/cut decisions and snapshot prices.",
            keepers:"Your own simulation of next season's keepers: re-rank players the way you expect them to be ranked and pick up to nine to keep. A player's keeper salary is the salary at his rank in Yahoo's projected-salary order (not his O-Rank). Not official; nothing is saved to league data.",
            now:"Today's rosters (current season) repriced at the snapshot. Sorted by snapshot salary; only the top "+((snap().now||{}).countTop||9)+" salaries count, IL included."};
  wrap.appendChild(help("seg-"+S.view,tips[S.view]));return wrap;}

/* ---------- Scenario A ---------- */
function teamIndex(t){var i=snap().teams.indexOf(t)+1;return (i<10?"0":"")+i;}
function sortedTeams(){
  var ts=snap().teams.slice(),k=S.sort;
  var by={team:function(a,b){return 0;},inc:function(a,b){return b.a.delta-a.a.delta;},dec:function(a,b){return a.a.delta-b.a.delta;},
    ceil:function(a,b){return a.a.room-b.a.room;},floor:function(a,b){var f=band().floor;return Math.abs(a.a.whatIf-f)-Math.abs(b.a.whatIf-f);}};
  var ord={};ts.forEach(function(t,i){ord[t.id]=i;});
  return ts.sort(function(a,b){return (by[k](a,b))||(ord[a.id]-ord[b.id]);});}
function trackFor(t,lo,hi){
  var b=band(),span=hi-lo,pc=function(v){return Math.max(0,Math.min(100,(v-lo)/span*100));};
  var wrap=h("span",{class:"wi-track","aria-hidden":"true"});
  var zone=h("i");zone.style.left=pc(b.floor)+"%";zone.style.width=(pc(b.ceiling)-pc(b.floor))+"%";wrap.appendChild(zone);
  [b.floor,b.ceiling].forEach(function(v){var u=h("u");u.style.left=pc(v)+"%";wrap.appendChild(u);});
  var a=Math.min(t.a.official,t.a.whatIf),z=Math.max(t.a.official,t.a.whatIf);
  var sg=h("s");sg.style.left=pc(a)+"%";sg.style.width=(pc(z)-pc(a))+"%";wrap.appendChild(sg);
  var o=h("b",{class:"o"});o.style.left=pc(t.a.official)+"%";wrap.appendChild(o);
  var n=h("b",{class:ST[t.a.status][1]});n.style.left=pc(t.a.whatIf)+"%";wrap.appendChild(n);return wrap;}
function cardA(t){
  var a=t.a,b=band(),st=ST[a.status];
  var card=h("article",{class:"team-card wi-card"});card.style.setProperty("--team-color",t.color);card.style.setProperty("--team-text",t.text);
  var box=h("div",{class:"cap-box "+st[2]},[h("div",{class:"cap-total",text:String(a.whatIf)},[h("span",{text:"/"+b.ceiling})]),h("div",{class:"gap-big",text:gapText(a.status,a.toFloor,a.room)})]);
  card.appendChild(h("header",{class:"team-head"},[h("div",{class:"team-index",text:teamIndex(t)}),
    h("div",{class:"team-id"},[h("div",{class:"team-name",text:(t.crown?CROWN:"")+t.name}),h("div",{class:"team-meta"},[h("span",{class:"identity-tag",text:t.short}),h("span",{class:"picks-tag",text:"OFFICIAL "+a.official+" → "+a.whatIf+" ("+sgn(a.delta)+")"})])]),box]));
  card.appendChild(h("div",{class:"table-head"},[h("span",{text:"POS"}),h("span",{text:"PLAYER"}),h("span",{text:"OFFICIAL"}),h("span",{text:S.snapShort}),h("span",{text:"Δ"})]));
  var host=h("div",{class:"players"});
  t.players.filter(function(p){return p.k0;}).sort(function(a,b2){return b2.c1-a.c1||b2.c0-a.c0||(a.n<b2.n?-1:1);}).forEach(function(p){
    var d=p.c1-p.c0,big=Math.abs(d)>=3;
    var row=h("div",{class:"player-row"+(big?" big "+dcls(d):"")});
    row.appendChild(h("div",{class:"pos",text:p.pos}));
    row.appendChild(h("div",{class:"pname",title:p.n,text:p.n},p.miss?[h("span",{class:"wi-tag miss",title:"Not in the Yahoo snapshot — counted as 0",text:"∅"})]:[]));
    row.appendChild(h("div",{class:"c0",text:String(p.c0)}));
    var c1=h("div",{class:"c1"});animNum(c1,p.c0,p.c1);row.appendChild(c1);
    row.appendChild(h("div",{class:"cd "+dcls(d),text:d?sgn(d):"·"}));host.appendChild(row);});
  card.appendChild(host);
  card.appendChild(h("div",{class:"wi-foot"},[h("span",{text:"OFFICIAL "+a.official}),h("span",{text:"Δ "+sgn(a.delta)}),h("span",{text:S.snapShort+" "+a.whatIf+" / "+b.ceiling})]));
  return card;}
function viewSame(){
  var s=snap(),b=band(),sum=s.summary,frag=document.createDocumentFragment();
  var stats=h("div",{class:"wi-stats"},[
    h("div",{class:"wi-stat ok"},[h("b",{text:String(sum.within)}),h("span",{text:"WITHIN BAND"})]),
    h("div",{class:"wi-stat"+(sum.belowFloor?" warn":"")},[h("b",{text:String(sum.belowFloor)}),h("span",{text:"BELOW FLOOR "+b.floor})]),
    h("div",{class:"wi-stat"+(sum.aboveCeiling?" bad":"")},[h("b",{text:String(sum.aboveCeiling)}),h("span",{text:"ABOVE CEILING "+b.ceiling})]),
    h("div",{class:"wi-stat"},[h("b",{text:sgn(s.teams.reduce(function(n,t){return n+t.a.delta;},0))}),h("span",{text:"NET LEAGUE Δ"})])]);
  frag.appendChild(stats);
  var sel=h("select",{id:"wi-sort","aria-label":"Sort teams"});
  [["team","Team order"],["inc","Largest increase"],["dec","Largest decrease"],["ceil","Closest to ceiling"],["floor","Closest to floor"]].forEach(function(o){var op=h("option",{value:o[0],text:o[1]});if(o[0]===S.sort)op.selected=true;sel.appendChild(op);});
  sel.addEventListener("change",function(){S.sort=sel.value;S.animate=false;render();syncUrl();});
  frag.appendChild(h("label",{class:"wi-ctl"},["SORT ",sel]));
  var teams=sortedTeams(),lo=1e9,hi=-1e9;
  teams.forEach(function(t){lo=Math.min(lo,t.a.official,t.a.whatIf);hi=Math.max(hi,t.a.official,t.a.whatIf);});
  lo=Math.min(lo,b.floor)-6;hi=Math.max(hi,b.ceiling)+6;
  var tb=h("table",{class:"wi-table"});
  tb.appendChild(h("tr",null,[h("th",{text:"TEAM"}),h("th",{text:"OFFICIAL"}),h("th",{text:S.snapShort}),h("th",{text:"Δ"}),h("th",{class:"hide-m",text:"VS BAND "+b.floor+"–"+b.ceiling}),h("th",{text:"COMPLIANCE"})]));
  teams.forEach(function(t){
    var a=t.a,open=!!S.open[t.id],st=ST[a.status];
    var btn=h("button",{type:"button",class:"wi-teambtn","aria-expanded":open?"true":"false"},[tchip(t)]);
    var tr=h("tr",{class:"wi-trow"+(open?" open":"")},[h("td",null,[btn]),h("td",{text:String(a.official)}),h("td"),
      h("td",null,[h("span",{class:"wi-d "+dcls(a.delta),text:a.delta?sgn(a.delta):"·"})]),h("td",{class:"hide-m"},[trackFor(t,lo,hi)]),
      h("td",null,[h("span",{class:"wi-comp"},[h("span",{class:"chip "+st[1],text:COMP[a.compliance]}),h("small",{text:gapText(a.status,a.toFloor,a.room)})])])]);
    var cell=tr.children[2];var n=h("span",{class:"wi-new"});animNum(n,a.official,a.whatIf);cell.appendChild(n);
    function toggle(){S.open[t.id]=!S.open[t.id];S.animate=true;render();}
    tr.addEventListener("click",toggle);btn.addEventListener("click",function(e){e.stopPropagation();toggle();});
    tb.appendChild(tr);
    if(open){var dt=h("tr",{class:"wi-detail"},[h("td",{colspan:"6"},[h("div",{class:"wi-cards one"},[cardA(t)])])]);tb.appendChild(dt);}});
  frag.appendChild(tb);return frag;}

/* ---------- NOW: current-season rosters at snapshot prices (separate from the post-keeper views) ---------- */
function cardNow(t,idx){
  var a=t.a,b=band(),st=ST[a.status],N=snap().now.countTop;
  var card=h("article",{class:"team-card wi-card"});card.style.setProperty("--team-color",t.color);card.style.setProperty("--team-text",t.text);
  card.appendChild(h("header",{class:"team-head"},[h("div",{class:"team-index",text:(idx<10?"0":"")+idx}),
    h("div",{class:"team-id"},[h("div",{class:"team-name",text:(t.crown?CROWN:"")+t.name}),h("div",{class:"team-meta"},[h("span",{class:"identity-tag",text:t.short}),h("span",{class:"picks-tag",text:"NOW "+a.official+" → "+a.whatIf+" ("+sgn(a.delta)+")"})])]),
    h("div",{class:"cap-box "+st[2]},[h("div",{class:"cap-total",text:String(a.whatIf)},[h("span",{text:"/"+b.ceiling})]),h("div",{class:"gap-big",text:gapText(a.status,a.toFloor,a.room)})])]));
  card.appendChild(h("div",{class:"table-head"},[h("span",{text:"POS"}),h("span",{text:"PLAYER"}),h("span",{text:"NOW"}),h("span",{text:S.snapShort}),h("span",{text:"Δ"})]));
  var host=h("div",{class:"players"}),div=false;
  t.players.forEach(function(p){
    if(p.x&&!div){div=true;host.appendChild(h("div",{class:"nc-div",text:"beyond top "+N+" · not counted"}));}
    var d=p.c1-p.c0,big=Math.abs(d)>=3;
    var row=h("div",{class:"player-row"+(big?" big "+dcls(d):"")+(p.x?" nc":"")+(p.rk?" rookie-row":"")});
    var tags=[];if(p.rk)tags.push(h("span",{class:"wi-tag rk",text:"R"}));if(p.s==="IL"||p.s==="IL+")tags.push(h("span",{class:"il-tag",text:p.s}));
    if(p.miss)tags.push(h("span",{class:"wi-tag miss",title:"Not in the Yahoo snapshot — counted as 0",text:"∅"}));
    row.appendChild(h("div",{class:"pos",text:p.pos}));
    row.appendChild(h("div",{class:"pname",title:p.n,text:p.n},tags));
    row.appendChild(h("div",{class:"c0",text:String(p.c0)}));
    var c1=h("div",{class:"c1"});animNum(c1,p.c0,p.c1);row.appendChild(c1);
    row.appendChild(h("div",{class:"cd "+dcls(d),text:d?sgn(d):"·"}));host.appendChild(row);});
  card.appendChild(host);
  card.appendChild(h("div",{class:"wi-foot"},[h("span",{text:"NOW "+a.official}),h("span",{text:"Δ "+sgn(a.delta)}),h("span",{text:S.snapShort+" "+a.whatIf+" / "+b.ceiling})]));
  return card;}
function viewNow(){
  var s=snap(),b=band(),teams=s.now.teams.slice(),frag=document.createDocumentFragment();
  var c={WITHIN:0,BELOW_FLOOR:0,ABOVE_CEILING:0};teams.forEach(function(t){c[t.a.compliance]++;});
  frag.appendChild(h("div",{class:"wi-stats"},[
    h("div",{class:"wi-stat ok"},[h("b",{text:String(c.WITHIN)}),h("span",{text:"WITHIN BAND"})]),
    h("div",{class:"wi-stat"+(c.BELOW_FLOOR?" warn":"")},[h("b",{text:String(c.BELOW_FLOOR)}),h("span",{text:"▼ FLOOR "+b.floor})]),
    h("div",{class:"wi-stat"+(c.ABOVE_CEILING?" bad":"")},[h("b",{text:String(c.ABOVE_CEILING)}),h("span",{text:"▲ CEILING "+b.ceiling})]),
    h("div",{class:"wi-stat"},[h("b",{text:sgn(teams.reduce(function(n,t){return n+t.a.delta;},0))}),h("span",{text:"NET Δ · TOP "+s.now.countTop})])]));
  var ord={};teams.forEach(function(t,i){ord[t.id]=i+1;});
  var by={team:function(){return 0;},inc:function(x,y){return y.a.delta-x.a.delta;},dec:function(x,y){return x.a.delta-y.a.delta;},
    ceil:function(x,y){return x.a.room-y.a.room;},floor:function(x,y){return Math.abs(x.a.whatIf-b.floor)-Math.abs(y.a.whatIf-b.floor);}};
  teams.sort(function(x,y){return (by[S.sort]||by.team)(x,y)||(ord[x.id]-ord[y.id]);});
  var sel=h("select",{"aria-label":"Sort teams"});
  [["team","Team order"],["inc","Largest increase"],["dec","Largest decrease"],["ceil","Closest to ceiling"],["floor","Closest to floor"]].forEach(function(o){var op=h("option",{value:o[0],text:o[1]});if(o[0]===S.sort)op.selected=true;sel.appendChild(op);});
  sel.addEventListener("change",function(){S.sort=sel.value;S.animate=false;render();syncUrl();});
  frag.appendChild(h("label",{class:"wi-ctl"},["SORT ",sel]));
  var lo=1e9,hi=-1e9;teams.forEach(function(t){lo=Math.min(lo,t.a.official,t.a.whatIf);hi=Math.max(hi,t.a.official,t.a.whatIf);});
  lo=Math.min(lo,b.floor)-6;hi=Math.max(hi,b.ceiling)+6;
  var tb=h("table",{class:"wi-table"});
  tb.appendChild(h("tr",null,[h("th",{text:"TEAM"}),h("th",{text:"NOW"}),h("th",{text:S.snapShort}),h("th",{text:"Δ"}),h("th",{class:"hide-m",text:b.floor+"–"+b.ceiling}),h("th",{text:""})]));
  teams.forEach(function(t){
    var a=t.a,key="now|"+t.id,open=!!S.open[key],st=ST[a.status];
    var btn=h("button",{type:"button",class:"wi-teambtn","aria-expanded":open?"true":"false"},[tchip(t)]);
    var tr=h("tr",{class:"wi-trow"+(open?" open":"")},[h("td",null,[btn]),h("td",{text:String(a.official)}),h("td"),
      h("td",null,[h("span",{class:"wi-d "+dcls(a.delta),text:a.delta?sgn(a.delta):"·"})]),h("td",{class:"hide-m"},[trackFor(t,lo,hi)]),
      h("td",null,[h("span",{class:"wi-comp"},[h("span",{class:"chip "+st[1],text:COMP[a.compliance]}),h("small",{text:gapText(a.status,a.toFloor,a.room)})])])]);
    var n=h("span",{class:"wi-new"});animNum(n,a.official,a.whatIf);tr.children[2].appendChild(n);
    function toggle(){S.open[key]=!S.open[key];S.animate=true;render();}
    tr.addEventListener("click",toggle);btn.addEventListener("click",function(e){e.stopPropagation();toggle();});
    tb.appendChild(tr);
    if(open)tb.appendChild(h("tr",{class:"wi-detail"},[h("td",{colspan:"6"},[h("div",{class:"wi-cards one"},[cardNow(t,ord[t.id])])])]));});
  frag.appendChild(tb);return frag;}

/* ---------- Scenario B ---------- */
function applySet(t,keys){var s={};keys.forEach(function(k){s[k]=true;});setKeep(t,s);S.flash=t.id;S.animate=false;render();}
function cardB(t){
  var b=band(),near=snap().band.near,ks=keepSet(t),total=keepTotal(t,ks),inf=info(total),st=ST[inf.st],max=snap().assumptions.keeperMax;
  var d=total-t.a.official,ed=edited(t),opt={};
  t.b.discretionary.forEach(function(x){opt[x.in]=x;opt[x.out]=x;});
  var card=h("article",{class:"team-card wi-card redo"});card.style.setProperty("--team-color",t.color);card.style.setProperty("--team-text",t.text);
  card.appendChild(h("header",{class:"team-head"},[h("div",{class:"team-index",text:teamIndex(t)}),
    h("div",{class:"team-id"},[h("div",{class:"team-name",title:t.name,text:(t.crown?CROWN:"")+t.name}),h("div",{class:"team-meta"},[h("span",{class:"identity-tag",text:t.short})])]),
    h("div",{class:"cap-box "+st[2]},[h("div",{class:"cap-total",text:String(total)},[h("span",{text:"/"+b.ceiling})]),h("div",{class:"gap-big",text:gapText(inf.st,inf.toFloor,inf.room)})])]));
  var ins=t.players.filter(function(p){return ks[p.k]&&!p.k0;}).length,outs=t.players.filter(function(p){return !ks[p.k]&&p.k0;}).length,swaps=Math.max(ins,outs);
  var strip=h("div",{class:"wi-strip"});
  strip.appendChild(h("div",{class:"row"},[h("span",{class:"chip "+st[1],text:COMP[inf.comp]}),
    h("span",null,[h("span",{class:"k",text:"Δ VS OFFICIAL"}),h("b",{text:sgn(d)})]),
    h("span",null,[h("span",{class:"k",text:"KEEPERS"}),h("b",{text:keepCount(ks)+"/"+max})]),
    h("span",{class:"chip",style:swaps?"background:#4a56c8;border-color:#4a56c8;color:#fff":"",text:swaps?swaps+" SWAP"+(swaps===1?"":"S"):"NO CHANGE"}),
    ed?h("span",{class:"chip",text:"EDITED"}):null]));
  if(!ed&&t.b.reasons.length)strip.appendChild(h("div",{class:"why",text:t.b.reasons[0]}));
  if(ed)strip.appendChild(h("div",{class:"why",text:"Manual simulation — cap and compliance recomputed; the projection notes below describe the default."}));
  var extra=[];
  if(t.b.reasons.length>1)extra.push(h("div",{class:"why"},t.b.reasons.slice(1).map(function(r){return h("div",{text:r});})));
  if(t.b.alternatives.length){var al=h("div",{class:"wi-alts"},[h("div",{class:"k",style:"font:800 9px Inter,Arial;letter-spacing:.07em;color:#5a6a8c",text:t.b.equalOptions+" EQUALLY MINIMAL FIXES · TOP "+t.b.alternatives.length+" SHOWN"})]);
    t.b.alternatives.forEach(function(a){var ap=h("button",{type:"button",class:"wi-apply",text:"TRY"});ap.addEventListener("click",function(){applySet(t,a.keep);});al.appendChild(h("div",{class:"wi-alt"},[h("span",{text:a.note+" → "+a.total}),ap]));});
    var dflt=h("button",{type:"button",class:"wi-apply",text:"PROJECTED"});dflt.addEventListener("click",function(){delete S.edits[S.snap+"|"+t.id];S.animate=false;render();});al.appendChild(h("div",{class:"wi-alt"},[h("span",{text:"Projected default: cut "+t.b.newlyCut.map(function(k){return nameOf(t,k);}).join(", ")+" · keep "+t.b.newlyKept.map(function(k){return nameOf(t,k);}).join(", ")+" → "+t.b.total}),dflt]));
    extra.push(al);}
  if(t.b.discretionary.length){var ol=h("div",{class:"wi-alts"},[h("div",{style:"font:800 9px Inter,Arial;letter-spacing:.07em;color:#2c3796",text:"OPTIONAL · NOT APPLIED"})]);
    t.b.discretionary.forEach(function(x){var ap=h("button",{type:"button",class:"wi-apply",text:"TRY"});
      ap.addEventListener("click",function(){var s=defaultSet(t);delete s[x.out];s[x.in]=true;setKeep(t,s);S.flash=t.id;S.animate=false;render();});
      ol.appendChild(h("div",{class:"wi-alt"},[h("span",{text:x.note}),ap]));});extra.push(ol);}
  if(extra.length){var key=S.snap+"|"+t.id,dt=h("details");if(S.det[key])dt.setAttribute("open","");
    dt.appendChild(h("summary",{text:"WHY & ALTERNATIVES"}));extra.forEach(function(e){dt.appendChild(e);});
    dt.addEventListener("toggle",function(){S.det[key]=dt.open;});strip.appendChild(dt);}
  card.appendChild(strip);
  card.appendChild(h("div",{class:"table-head"},[h("span",{text:"POS"}),h("span",{text:"PLAYER"}),h("span",{text:S.snapShort}),h("span",{text:"KEEP"})]));
  var host=h("div",{class:"players"});
  var kept=t.players.filter(function(p){return ks[p.k];}).sort(function(a,b2){return b2.c1-a.c1||(a.n<b2.n?-1:1);});
  var cut=t.players.filter(function(p){return !ks[p.k];}).sort(function(a,b2){return b2.c1-a.c1||(a.n<b2.n?-1:1);});
  function prow(p){
    var isK=!!ks[p.k],cls=isK?(p.k0?"":"in"):(p.k0?"out":"bench");
    var row=h("div",{class:"player-row "+cls+(opt[p.k]?" opt":""),"data-k":p.k});
    var tags=[];
    if(cls==="in")tags.push(h("span",{class:"wi-tag in",text:"IN"}));
    if(cls==="out")tags.push(h("span",{class:"wi-tag out",text:"OUT"}));
    if(opt[p.k]&&!ed)tags.push(h("span",{class:"wi-tag opt",title:opt[p.k].note,text:"OPT"}));
    if(p.miss)tags.push(h("span",{class:"wi-tag miss",title:"Not in the Yahoo snapshot — counted as 0",text:"∅"}));
    row.appendChild(h("div",{class:"pos",text:p.pos}));
    row.appendChild(h("div",{class:"pname",title:p.n+(p.c0!==p.c1?" — official "+p.c0:""),text:p.n},tags));
    var c1=h("div",{class:"c1"});c1.textContent=String(p.c1);if(p.c0!==p.c1)c1.appendChild(h("small",{style:"display:block;font:500 9px Roboto Mono,monospace;color:#7a869c",text:"was "+p.c0}));row.appendChild(c1);
    var lockCut=isK&&p.lock&&p.k0,full=!isK&&keepCount(ks)>=max;
    var tg=h("button",{type:"button",class:"wi-tg","aria-pressed":isK?"true":"false",text:isK?"✓ KEPT":"✕ CUT",
      title:lockCut?"A "+p.c1+" player can never be dropped":full?"Nine keepers maximum — cut someone first":(p.rev&&isK&&p.k0?"10–19 drops need commissioner review":"Toggle keep / cut (simulation only)")});
    if(lockCut||full)tg.disabled=true;
    tg.addEventListener("click",function(){var s=Object.assign({},keepSet(t));if(isK)delete s[p.k];else s[p.k]=true;setKeep(t,s);S.flash=t.id;S.flashKey=p.k;S.animate=false;render();});
    row.appendChild(h("div",{style:"text-align:center"},[tg]));return row;}
  kept.forEach(function(p){host.appendChild(prow(p));});
  if(cut.length)host.appendChild(h("div",{class:"wi-sep",text:"NOT KEPT"}));
  cut.forEach(function(p){host.appendChild(prow(p));});
  card.appendChild(host);
  var rs=h("button",{type:"button",class:"wi-reset",text:"RESET"});rs.hidden=!ed;rs.addEventListener("click",function(){delete S.edits[S.snap+"|"+t.id];S.animate=false;render();});
  card.appendChild(h("div",{class:"wi-foot"},[h("span",{text:"KEEP "+total+" / "+b.ceiling}),h("span",{text:inf.comp==="WITHIN"?"✓ LEGAL":inf.comp==="ABOVE_CEILING"?"✕ ILLEGAL":"△ UNDER FLOOR"}),rs]));
  return card;}
function nameOf(t,k){var r="";t.players.forEach(function(p){if(p.k===k)r=p.n;});return r;}
function viewRedo(){
  var s=snap(),frag=document.createDocumentFragment();
  var tot={within:0,below:0,above:0},chg=0,any=false;
  s.teams.forEach(function(t){var i=info(keepTotal(t,keepSet(t)));if(i.comp==="WITHIN")tot.within++;else if(i.comp==="BELOW_FLOOR")tot.below++;else tot.above++;if(t.b.newlyKept.length||t.b.newlyCut.length)chg++;if(edited(t))any=true;});
  frag.appendChild(h("div",{class:"wi-stats"},[
    h("div",{class:"wi-stat ok"},[h("b",{text:String(tot.within)}),h("span",{text:"WITHIN BAND"})]),
    h("div",{class:"wi-stat"+(tot.below?" warn":"")},[h("b",{text:String(tot.below)}),h("span",{text:"BELOW FLOOR"})]),
    h("div",{class:"wi-stat"+(tot.above?" bad":"")},[h("b",{text:String(tot.above)}),h("span",{text:"ABOVE CEILING"})]),
    h("div",{class:"wi-stat"},[h("b",{text:String(chg)}),h("span",{text:"TEAMS WITH PROJECTED CHANGES"})])]));
  var ctl=h("div",{class:"wi-ctl"},[h("span",{text:"TOGGLE ANY PLAYER TO TRY YOUR OWN VERSION"}),help("redo-edit","Manual swaps recompute cap and compliance only. They live in this page view, are never saved and never touch the official board. The FA 60 tab always shows the projected default.")]);
  var ra=h("button",{type:"button",class:"wi-reset",text:"RESET ALL"});ra.hidden=!any;ra.addEventListener("click",function(){S.edits={};S.animate=false;render();});ctl.appendChild(ra);
  frag.appendChild(ctl);
  var grid=h("div",{class:"wi-cards"});s.teams.forEach(function(t){grid.appendChild(cardB(t));});frag.appendChild(grid);return frag;}

/* ---------- FA 60 ---------- */
function srcBadge(r){
  if(r.src==="cut"){var t=teamByShort(r.st);return t?tchip(t):h("span",{class:"src src-cut",text:r.st});}
  return h("span",{class:"src "+(r.src==="R"?"src-r":"src-fa"),text:r.src==="R"?"R":"FA"});}
function faList(rows,mode,idx){
  var list=h("div",{class:"wi-fa-list"});
  list.appendChild(h("div",{class:"wi-fr head"},[h("div",{text:"#"}),h("div",{text:"POS"}),h("div",{class:"pl",text:"PLAYER"}),h("div",{text:"NBA"}),h("div",{text:"CAP"}),h("div",{text:"SRC"})]));
  rows.forEach(function(r,i){
    var cls="wi-fr",tag=null,mv=null,e=idx.enter[r.n],x=idx.exit[r.n],m=idx.move[r.n];
    if(mode==="wi"&&e){cls+=" enter";tag=h("span",{class:"wi-why "+e.cause.toLowerCase(),text:e.cause==="KEEPER"?"KEEPER":"MARKET"});}
    if(mode==="off"&&x){cls+=" exit";tag=h("span",{class:"wi-why "+x.cause.toLowerCase(),text:x.cause==="KEEPER"?"KEEPER":"MARKET"});}
    if(mode==="wi"&&m){mv=h("span",{class:"mv "+(m.delta>0?"up":"down"),text:(m.delta>0?"▲":"▼")+Math.abs(m.delta)});tag=h("span",{class:"wi-why "+m.cause.toLowerCase(),text:m.cause==="KEEPER"?"KEEPER":"MARKET"});}
    var pl=h("div",{class:"pl",title:r.n+(r.or?" · Y! "+r.or:"")},[r.n,mv?" ":null,mv,tag]);
    list.appendChild(h("div",{class:cls},[h("div",{class:"rk",text:String(i+1)}),h("div",{class:"ps",text:r.pos}),pl,h("div",{class:"ps",text:r.nba}),h("div",{class:"cp",text:String(r.cap)}),h("div",null,[srcBadge(r)])]));});
  return list;}
function viewFa(){
  var s=snap(),fa=s.fa,df=fa.diff,frag=document.createDocumentFragment();
  var idx={enter:{},exit:{},move:{}};df.entered.forEach(function(x){idx.enter[x.n]=x;});df.exited.forEach(function(x){idx.exit[x.n]=x;});df.moved.forEach(function(x){idx.move[x.n]=x;});
  function chips(list,fn){return list.length?list.map(fn):[h("span",{class:"none",text:"None"})];}
  function line(x,text){return h("div",null,[h("b",{text:x.n}),text," ",h("span",{class:"wi-why "+x.cause.toLowerCase(),text:x.cause==="KEEPER"?"KEEPER":"MARKET"})]);}
  frag.appendChild(h("div",{class:"wi-sum"},[
    h("div",{class:"wi-sumbox"},[h("h5",{text:"ENTERING THE 60 ("+df.entered.length+")"})].concat(chips(df.entered,function(x){return line(x," → #"+x.rank);}))),
    h("div",{class:"wi-sumbox"},[h("h5",{text:"LEAVING THE 60 ("+df.exited.length+")"})].concat(chips(df.exited,function(x){return line(x," (was #"+x.rank+")");}))),
    h("div",{class:"wi-sumbox"},[h("h5",{text:"MOVING 5+ PLACES ("+df.moved.length+")"})].concat(chips(df.moved,function(x){return line(x," #"+x.from+" → #"+x.to);})))]));
  var leg=h("div",{class:"wi-ctl"},[h("span",{class:"wi-why keeper",text:"KEEPER"}),h("span",{text:"hypothetical keep/cut decision"}),h("span",{class:"wi-why market",text:"MARKET"}),h("span",{text:"snapshot salary or Yahoo rank order"}),
    help("fa-cause","KEEPER: the player entered/left the pool, or moved, mainly because a franchise's projected keeper/cut set changed. MARKET: it happens already when the official keepers are held fixed and only the snapshot prices and ranks change. Ordering rules are unchanged: CAP descending first, then the same Yahoo/dynasty tie-break.")]);
  frag.appendChild(leg);
  var panes=h("div",{class:"wi-panes wi-seg"});
  [["off","OFFICIAL"],["wi","WHAT IF"]].forEach(function(p){var b=h("button",{type:"button","aria-pressed":S.pane===p[0]?"true":"false",text:p[1]});b.addEventListener("click",function(){S.pane=p[0];S.animate=false;render();});panes.appendChild(b);});
  frag.appendChild(panes);
  var grid=h("div",{class:"wi-fa","data-pane":S.pane});
  grid.appendChild(h("div",{class:"wi-p-off"},[h("div",{class:"wi-fa-h",text:"OFFICIAL FA 60"}),faList(fa.official,"off",idx)]));
  grid.appendChild(h("div",{class:"wi-p-wi"},[h("div",{class:"wi-fa-h"},[h("span",{text:"WHAT-IF FA 60 · "+fdate(s.meta.effectiveDate)})]),faList(fa.redo,"wi",idx)]));
  frag.appendChild(grid);return frag;}


/* ---------- KEEPERS: preview next year's keepers (your ranking, shared rankings you imported, keeper picks per team) ----------
   A simulation. Nothing is written to league data; the URL and this browser remember it.
   Salary = the salary at a player's rank in the stored table (config/keeper_salary_by_rank.json), so one small rank move
   re-prices every player between the two ranks, on every team. */
var KB={team:null,keep:{},sets:null,active:"mine",auto:true,loaded:false,uni:null,names:null,yrank:null,rank:null,last:null,msg:null,imp:false,lg:true},KB_LS="nbaTalkVN.keeperBoard",KB_MINE="My ranking";
var KB_NOT_CHECKED=["prospect and young-player keep exceptions","positional tag minimums","IL cap treatment","commissioner approval of any drop"];
function kbNewSets(){return {mine:{label:KB_MINE,pins:[],base:null}};}
function kbSet(){if(!KB.sets)KB.sets=kbNewSets();if(!KB.sets[KB.active])KB.active="mine";return KB.sets[KB.active];}
function kbSave(){try{localStorage.setItem(KB_LS,JSON.stringify({v:2,team:KB.team,keep:KB.keep,sets:KB.sets,active:KB.active,auto:KB.auto}));}catch(e){}}
function kbLoad(){KB.loaded=true;KB.sets=kbNewSets();
  try{var o=JSON.parse(localStorage.getItem(KB_LS)||"null");if(!o)return;KB.team=o.team||KB.team;KB.keep=o.keep||{};
    if(o.v===2&&o.sets){KB.sets=o.sets;KB.active=o.active||"mine";KB.auto=o.auto!==false;}else if(o.pins){KB.sets.mine.pins=o.pins;}}catch(e){}
  if(!KB.sets.mine)KB.sets.mine={label:KB_MINE,pins:[],base:null};}
function kbUniverse(){
  if(KB.uni)return KB.uni;var kb=W.keeperBoard,seen={},u=[],extra=[];KB.names=kb.names||{};
  kb.order.forEach(function(k){if(!seen[k]){seen[k]=1;u.push(k);}});
  kb.teams.forEach(function(t){t.players.forEach(function(p){KB.names[p.k]=p.n;if(!seen[p.k]){seen[p.k]=1;extra.push(p);}});});
  extra.sort(function(a,b){return a.n<b.n?-1:a.n>b.n?1:0;});extra.forEach(function(p){u.push(p.k);});KB.uni=u;
  KB.yrank={};u.forEach(function(k,i){KB.yrank[k]=i+1;});return u;}
/* a ranking from pins: every pinned player sits at exactly the rank asked for (a later edit wins a contested slot, the earlier pin slides down one); everyone else keeps Yahoo's order */
function kbRankOf(pins){
  var base=kbUniverse(),pinned={},order=pins.map(function(x,i){return {k:x[0],q:x[1],i:i};});order.forEach(function(x){pinned[x.k]=1;});
  var list=base.filter(function(k){return !pinned[k];});
  order.sort(function(a,b){return a.q-b.q||a.i-b.i;}).forEach(function(x){list.splice(Math.min(Math.max(x.q,1),list.length+1)-1,0,x.k);});
  var rank={};list.forEach(function(k,i){rank[k]=i+1;});return rank;}
function kbRanking(){KB.rank=kbRankOf(kbSet().pins);return KB.rank;}
function kbSalaryAt(rank){return W.keeperBoard.salaryByRank[rank-1]||0;}
function kbTeam(){var ts=W.keeperBoard.teams;for(var i=0;i<ts.length;i++)if(ts[i].id===KB.team)return ts[i];KB.team=ts[0].id;return ts[0];}
function kbName(k){kbUniverse();return KB.names[k]||k;}
function kbTeamOf(k){var ts=W.keeperBoard.teams;for(var i=0;i<ts.length;i++)for(var j=0;j<ts[i].players.length;j++)if(ts[i].players[j].k===k)return ts[i];return null;}
/* keeper picks stay as the manager's intent; what counts is the fitted set: when ranks move and the plan goes over the ceiling,
   the fewest players are dropped from it (never one at the never-drop line, drops needing review last, then the worst-ranked), and they return on their own when room reappears */
function kbFit(t,intent,rank,auto){
  var kb=W.keeperBoard,C=kb.band.ceiling,sal=function(k){return kbSalaryAt(rank[k]);},pay=function(a){return a.reduce(function(n,k){return n+sal(k);},0);};
  var out={eff:intent.slice(),off:[],pay:pay(intent),infeasible:false};
  if(!auto||out.pay<=C)return out;
  var cand=intent.filter(function(k){return sal(k)>0&&sal(k)<kb.neverDrop;}),best=null;
  for(var m=1;m<(1<<cand.length);m++){var pick=[];for(var i=0;i<cand.length;i++)if(m&(1<<i))pick.push(cand[i]);
    var left=intent.filter(function(k){return pick.indexOf(k)<0;});if(pay(left)>C)continue;
    var rev=pick.filter(function(k){return sal(k)>=kb.reviewFrom;}).length,worst=pick.reduce(function(n,k){return n+rank[k];},0),key=pick.slice().sort().join();
    var sc=[pick.length,rev,-worst,key];
    if(!best||kbCmp(sc,best.sc)<0)best={sc:sc,pick:pick,left:left};}
  if(!best){out.infeasible=true;return out;}
  out.eff=best.left;out.off=best.pick;out.pay=pay(best.left);return out;}
function kbCmp(a,b){for(var i=0;i<a.length;i++){if(a[i]<b[i])return -1;if(a[i]>b[i])return 1;}return 0;}
function kbTop9(t,rank){var n=W.keeperBoard.keeperMax;return t.players.map(function(p){return kbSalaryAt(rank[p.k]);}).sort(function(a,b){return b-a;}).slice(0,n).reduce(function(s,x){return s+x;},0);}
function kbIntent(t){return (KB.keep[t.id]||[]).filter(function(k){return t.players.some(function(p){return p.k===k;});});}
function kbBandStatus(pay){var b=W.keeperBoard.band;return pay>b.ceiling?"over":pay<b.floor?"under":b.ceiling-pay<=b.near?"near":"ok";}
/* what one change did: every rostered player whose salary differs between two rankings, grouped by team */
function kbRipple(before,after){
  var teams=[],ids={};W.keeperBoard.teams.forEach(function(t){var rows=[];t.players.forEach(function(p){var a=kbSalaryAt(before[p.k]),b=kbSalaryAt(after[p.k]);if(a!==b)rows.push({k:p.k,n:p.n,a:a,b:b});});
    if(rows.length){rows.sort(function(x,y){return Math.abs(y.b-y.a)-Math.abs(x.b-x.a);});teams.push({t:t,rows:rows,net:rows.reduce(function(n,r){return n+r.b-r.a;},0)});}});
  return {teams:teams,players:teams.reduce(function(n,x){return n+x.rows.length;},0)};}
function kbEdit(k,q){
  if(q===""||q==null||!isFinite(+q))return false;  /* a blank or non-numeric entry is not a move (it used to land on rank 1) */
  var before=KB.rank||kbRanking(),set=kbSet(),n=kbUniverse().length;q=Math.max(1,Math.min(n,Math.round(+q)));
  set.pins=set.pins.filter(function(x){return x[0]!==k;});set.pins.push([k,q]);
  var after=kbRanking();if(after[k]===KB.yrank[k]&&set.pins.length===1)set.pins=[];
  KB.last={k:k,from:before[k],to:after[k],rip:kbRipple(before,after)};kbSave();return true;}
function kbMoves(set){return set.pins.length;}
/* ---- sharing ---- */
function kbShort(k){var p=kbUniverse()[0].replace(/\d+$/,"");return k.indexOf(p)===0?k.slice(p.length):k;}
function kbLong(x){var p=kbUniverse()[0].replace(/\d+$/,"");return /^\d+$/.test(x)?p+x:x;}
function kbCode(set){return "KR1:"+set.pins.map(function(x){return kbShort(x[0])+"="+x[1];}).join(",");}
function kbPinsFrom(str,st){var u={};kbUniverse().forEach(function(k){u[k]=1;});st=st||{};st.n=0;
  return String(str||"").split(",").filter(function(x){return x.trim();}).map(function(x){var a=x.split(/[:=]/);return [kbLong(a[0].trim()),+a[1]];}).filter(function(x){var ok=u[x[0]]&&x[1]>=1;if(!ok)st.n++;return ok;});}
function kbLink(label){var t=kbTeam(),set=kbSet(),q="?mode=whatif&view=keepers&team="+encodeURIComponent(t.id),keep=KB.keep[t.id]||[];
  if(keep.length)q+="&keep="+keep.join(",");if(set.pins.length)q+="&rk="+set.pins.map(function(x){return kbShort(x[0])+":"+x[1];}).join(",");
  if(label)q+="&rn="+encodeURIComponent(label);if(!KB.auto)q+="&fit=0";return location.origin+location.pathname+q;}
function kbQuery(){var t=kbTeam(),set=kbSet(),q="&team="+encodeURIComponent(t.id),keep=KB.keep[t.id]||[];
  if(keep.length)q+="&keep="+keep.join(",");if(set.pins.length)q+="&rk="+set.pins.map(function(x){return kbShort(x[0])+":"+x[1];}).join(",");
  if(KB.active!=="mine")q+="&rn="+encodeURIComponent(set.label);if(!KB.auto)q+="&fit=0";return q;}
function kbAddSet(label,pins){var id="s"+Date.now().toString(36)+Math.floor(Math.random()*1e3).toString(36);KB.sets[id]={label:label,pins:pins.slice(),base:pins.slice()};KB.active=id;return id;}
function kbSetByLabel(label){for(var id in KB.sets)if(id!=="mine"&&KB.sets[id].label===label)return id;return null;}
function kbRestore(qs){kbLoad();var t=qs.get("team");if(t)KB.team=t;if(qs.get("fit")==="0")KB.auto=false;
  var k=qs.get("keep"),r=qs.get("rk"),rn=qs.get("rn");
  if(k!==null){var u={};kbUniverse().forEach(function(x){u[x]=1;});KB.keep[KB.team||t]=k.split(",").map(kbLong).filter(function(x){return u[x];}).slice(0,W.keeperBoard.keeperMax);}
  if(r!==null){var pins=kbPinsFrom(r);
    if(rn){var id=kbSetByLabel(rn);if(id){KB.sets[id].pins=pins;KB.active=id;}else kbAddSet(rn,pins);}
    else{KB.active=KB.active||"mine";kbSet().pins=pins;}}
  else if(rn){var id2=kbSetByLabel(rn);if(id2)KB.active=id2;}
  kbSave();}
/* import: a shared link, a ranking code, or a pasted list of names (best first, optionally "12. Name" or "12 Name") */
function kbParseImport(text,label){
  text=String(text||"").trim();if(!text)return {err:"Paste a link, a ranking code or a list of names first."};
  var lm=text.match(/[?&]rk=([^&\s]*)/),keep=text.match(/[?&]keep=([^&\s]*)/),team=text.match(/[?&]team=([^&\s]*)/),rn=text.match(/[?&]rn=([^&\s]*)/);
  if(lm){var st1={},pins=kbPinsFrom(decodeURIComponent(lm[1]),st1);return {dropped:st1.n,pins:pins,label:label||(rn?decodeURIComponent(rn[1].replace(/\+/g," ")):"Shared ranking"),keep:keep?decodeURIComponent(keep[1]).split(","):null,team:team?decodeURIComponent(team[1]):null,how:"link"};}
  if(/^KR1:/.test(text)){var st2={},pc=kbPinsFrom(text.slice(4),st2);return {dropped:st2.n,pins:pc,label:label||"Shared ranking",how:"code"};}
  var idx={},amb={};kbUniverse().forEach(function(k){var n=kbNorm(kbName(k));if(idx[n]&&idx[n]!==k)amb[n]=1;idx[n]=k;});
  var pins2=[],miss=[],next=1,used={};
  text.split(/\r?\n/).forEach(function(line){line=line.trim();if(!line)return;var m=line.match(/^#?\s*(\d{1,3})\s*[.):\-]?\s+(.+)$/),q=null,nm=line;if(m){q=+m[1];nm=m[2];}
    nm=nm.replace(/[,;|].*$/,"").trim();var nn=kbNorm(nm),k=idx[nn];if(!k||amb[nn]){miss.push(nm+(amb[nn]?" (two players share this name)":""));return;}if(used[k])return;used[k]=1;pins2.push([k,q||next]);next=(q||next)+1;});
  if(!pins2.length)return {err:"No player names matched. Paste a full link, a code starting KR1:, or one player name per line."};
  return {pins:pins2,label:label||"Pasted list",miss:miss,how:"names"};}
/* ---- view ---- */
function kbNorm(s){return String(s==null?"":s).normalize("NFD").replace(/[\u0300-\u036f]/g,"").replace(/\u0111/g,"d").replace(/\u0110/g,"d").toLowerCase().replace(/[.']/g,"").trim();}
function kbSure(txt,fn,id,cls){var b=kbBtn(txt,function(){if(b.dataset.arm){fn();return;}b.dataset.arm="1";b.textContent="Click again to confirm";setTimeout(function(){if(b.isConnected){delete b.dataset.arm;b.textContent=txt;}},3000);},id,cls);return b;}
function kbBtn(txt,fn,id,cls){var b=h("button",{type:"button",class:"wi-reset"+(cls?" "+cls:""),text:txt});if(id)b.id=id;b.addEventListener("click",fn);return b;}
function kbRender(){S.animate=false;render();syncUrl();}
function viewKeepers(){
  if(!KB.loaded)kbLoad();
  var kb=W.keeperBoard,t=kbTeam(),rank=kbRanking(),set=kbSet(),frag=document.createDocumentFragment(),b=kb.band,max=kb.keeperMax;
  kbUniverse();
  var fits={};kb.teams.forEach(function(x){fits[x.id]=kbFit(x,kbIntent(x),rank,KB.auto);});
  /* 1. what this is */
  frag.appendChild(h("div",{class:"wi-kb-hd"},[h("div",null,[h("h3",{text:"Preview next year's keepers"}),
    h("p",{text:"Rank the players the way you expect them to be ranked, then choose up to "+max+" keepers per team. A player's salary is the salary at his rank, so one move re-prices everyone between the two ranks, on every team."})]),
    h("span",{class:"wi-kb-pill",text:"YOUR ASSUMPTION · NOT OFFICIAL"})]));
  /* 2. ranking set: mine / imported, import, share */
  var bar=h("div",{class:"wi-kb-bar"}),sel=h("select",{id:"kb-set","aria-label":"Ranking set"});
  Object.keys(KB.sets).forEach(function(id){var o=h("option",{value:id,text:KB.sets[id].label+(KB.sets[id].pins.length?" · "+KB.sets[id].pins.length+" moved":"")});if(id===KB.active)o.selected=true;sel.appendChild(o);});
  sel.addEventListener("change",function(){KB.active=sel.value;KB.last=null;kbSave();kbRender();});
  bar.appendChild(h("label",{class:"wi-kb-lab"},[h("span",{text:"RANKING"}),sel]));
  bar.appendChild(kbBtn("Open rankings board",function(){bdOpen();},"kb-board-btn","pri"));
  bar.appendChild(kbBtn("Import",function(){KB.imp=!KB.imp;kbRender();},"kb-import-btn"));
  bar.appendChild(kbBtn("Copy link",function(){var u=kbLink(KB.active==="mine"?"Shared ranking":set.label);function done(m){var e=document.getElementById("kb-copy");if(e){e.textContent=m;setTimeout(function(){e.textContent="Copy link";},2400);}}
    var long=u.length>1800?" · long link, use Copy code":"";try{navigator.clipboard.writeText(u).then(function(){done("Copied"+long);},function(){done("Copy blocked");});}catch(e){done("Copy blocked");}},"kb-copy"));
  bar.appendChild(kbBtn("Copy code",function(){var u=kbCode(set);function done(m){var e=document.getElementById("kb-code");if(e){e.textContent=m;setTimeout(function(){e.textContent="Copy code";},1800);}}
    try{navigator.clipboard.writeText(u).then(function(){done("Copied");},function(){done("Copy blocked");});}catch(e){done("Copy blocked");}},"kb-code"));
  if(set.pins.length)bar.appendChild(kbSure(set.base?"Reset to imported":"Reset to Yahoo order",function(){set.pins=set.base?set.base.slice():[];KB.last=null;kbSave();kbRender();},"kb-reset"));
  if(KB.active!=="mine")bar.appendChild(kbSure("Delete",function(){delete KB.sets[KB.active];KB.active="mine";KB.last=null;kbSave();kbRender();},"kb-del","danger"));
  frag.appendChild(bar);
  var diff=set.base?set.pins.filter(function(x){return !set.base.some(function(y){return y[0]===x[0]&&y[1]===x[1];})}).length+set.base.filter(function(y){return !set.pins.some(function(x){return x[0]===y[0]})}).length:0;
  frag.appendChild(h("div",{class:"wi-kb-sub",text:(set.base?"Imported ranking":"Your own ranking")+": "+(set.pins.length?set.pins.length+" player"+(set.pins.length>1?"s":"")+" moved off Yahoo's order":"Yahoo's order, nothing moved")+(set.base?(diff?" · your tweaks: "+diff:" · no tweaks yet"):"")}));
  if(KB.imp){var box=h("div",{class:"wi-kb-imp"}),ta=h("textarea",{id:"kb-paste",rows:"4",placeholder:"Paste a link, a code (KR1:…), or one player per line, best first (e.g. 1. Nikola Jokić)"}),nm=h("input",{type:"text",id:"kb-label",placeholder:"Name it (optional)",maxlength:"40"}),both=h("input",{type:"checkbox",id:"kb-withkeep"});
    var go=kbBtn("Import ranking",function(){var r=kbParseImport(ta.value,nm.value.trim());if(r.err){KB.msg=r.err;kbRender();return;}
      kbAddSet(r.label,r.pins);if(both.checked&&r.keep){var uu={};kbUniverse().forEach(function(x){uu[x]=1;});KB.keep[r.team||KB.team]=r.keep.filter(function(x){return uu[x];}).slice(0,max);if(r.team)KB.team=r.team;}
      KB.msg="Imported "+r.pins.length+" ranked player"+(r.pins.length===1?"":"s")+" as “"+r.label+"”"+(r.miss&&r.miss.length?"; not found: "+r.miss.slice(0,4).join(", ")+(r.miss.length>4?"…":""):"")+(r.dropped?"; "+r.dropped+" entr"+(r.dropped>1?"ies":"y")+" not recognised (players Yahoo no longer ranks or a damaged code)":"")+". Tweak it below; yours stays untouched.";KB.imp=false;KB.last=null;kbSave();kbRender();},"kb-do");
    box.appendChild(ta);box.appendChild(h("div",{class:"wi-kb-impr"},[nm,h("label",{class:"wi-kb-chk"},[both,"also take their keeper picks (links only)"]),go,kbBtn("Cancel",function(){KB.imp=false;kbRender();},"kb-cancel")]));frag.appendChild(box);}
  if(KB.msg){frag.appendChild(h("div",{class:"wi-kb-msg",role:"status",text:KB.msg}));KB.msg=null;}
  /* 3. league strip: every team's plan at a glance */
  var strip=h("div",{class:"wi-kb-strip",role:"group","aria-label":"Teams"});
  kb.teams.forEach(function(x){var f=fits[x.id],it=kbIntent(x),on=x.id===t.id,stt=it.length?kbBandStatus(f.pay):"none",
    e=h("button",{type:"button",class:"wi-kb-tm "+stt+(on?" on":""),"aria-pressed":on?"true":"false",title:x.name},[tchip(x),h("small",{text:it.length?String(f.pay):"–"}),f.off.length?h("i",{class:"auto",title:f.off.length+" keeper"+(f.off.length>1?"s":"")+" auto-removed",text:"−"+f.off.length}):null]);
    e.addEventListener("click",function(){KB.team=x.id;kbSave();kbRender();});strip.appendChild(e);});
  frag.appendChild(strip);
  /* 4. the chosen team */
  var intent=kbIntent(t),fit=fits[t.id],effSet={},offSet={};fit.eff.forEach(function(k){effSet[k]=1;});fit.off.forEach(function(k){offSet[k]=1;});
  var rows=t.players.map(function(p){var rk=rank[p.k];return {p:p,rank:rk,sal:kbSalaryAt(rk)};}).sort(function(a,c){return a.rank-c.rank;});
  var y0=kbRankOf([]),payY=intent.reduce(function(n,k){return n+kbSalaryAt(y0[k]);},0),dY=fit.pay-fit.eff.reduce(function(n,k){return n+kbSalaryAt(y0[k]);},0);
  var stt=intent.length?kbBandStatus(fit.pay):"none",txt=fit.pay>b.ceiling?String(fit.pay-b.ceiling):String(b.ceiling-fit.pay);
  frag.appendChild(h("div",{class:"wi-stats"},[
    h("div",{class:"wi-stat"},[h("b",{text:fit.eff.length+"/"+max}),h("span",{text:"KEEPING"})]),
    h("div",{class:"wi-stat "+(stt==="over"?"bad":stt==="near"?"warn":"ok")},[h("b",{text:String(fit.pay)}),h("span",{text:"KEEPER PAYROLL"+(intent.length&&(set.pins.length)?" ("+(dY===0?"same as":sgn(dY)+" vs")+" Yahoo order)":"")})]),
    h("div",{class:"wi-stat"},[h("b",{text:b.floor+"–"+b.ceiling}),h("span",{text:"OFFICIAL BAND"})]),
    h("div",{class:"wi-stat "+(stt==="over"?"bad":stt==="near"?"warn":"ok")},[h("b",{text:txt}),h("span",{text:fit.pay>b.ceiling?"OVER CEILING":"ROOM TO CEILING"})])]));
  frag.appendChild(h("div",{class:"wi-kb-nc"},[h("b",{text:"Not checked here: "}),KB_NOT_CHECKED.join(", ")+". A plan under the ceiling is not an approved declaration."]));
  var ctl=h("div",{class:"wi-kb-fit"}),au=h("input",{type:"checkbox",id:"kb-auto"});au.checked=KB.auto;au.addEventListener("change",function(){KB.auto=au.checked;kbSave();kbRender();});
  ctl.appendChild(h("label",{class:"wi-kb-chk"},[au,"Keep this team compliant automatically"]));
  ctl.appendChild(help("kb-fit","When a rank move pushes the picked keepers over the ceiling, the fewest players are taken off the list: never one at "+kb.neverDrop+"+, drops that need review last, then the worst-ranked. They come back on their own if room reappears. Your picks are never rewritten."));
  frag.appendChild(ctl);
  if(fit.off.length)frag.appendChild(h("div",{class:"wi-kb-flag warn",role:"status",text:"Auto-adjusted: "+fit.off.map(kbName).join(", ")+" "+(fit.off.length>1?"are":"is")+" left out so "+t.short+" stays at or under "+b.ceiling+" (picked "+intent.length+", payroll would be "+(fit.pay+fit.off.reduce(function(n,k){return n+kbSalaryAt(rank[k]);},0))+")."}));
  var flags=[];
  if(fit.infeasible||fit.pay>b.ceiling)flags.push(["bad","Over the ceiling by "+(fit.pay-b.ceiling)+" and no allowed removal fixes it ("+kb.neverDrop+"+ players cannot be dropped): re-rank, pick others, or ask the commissioner."]);
  if(fit.eff.length)rows.forEach(function(x){if(effSet[x.p.k])return;if(x.sal>=kb.neverDrop)flags.push(["bad",x.p.n+" (cap "+x.sal+") is not kept: players at "+kb.neverDrop+"+ cannot be dropped without the commissioner."]);
    else if(x.sal>=kb.reviewFrom)flags.push(["warn",x.p.n+" (cap "+x.sal+") is not kept: dropping a "+kb.reviewFrom+"–"+(kb.neverDrop-1)+" player needs commissioner review."]);});
  if(flags.length){var fl=h("div",{class:"wi-kb-flags"});flags.forEach(function(f){fl.appendChild(h("div",{class:"wi-kb-flag "+f[0],text:f[1]}));});frag.appendChild(fl);}
  var tb=h("table",{class:"wi-table wi-kb"}),hd=h("tr");["Keep","Rank","vs Yahoo","Player","Cap","Cap Δ"].forEach(function(x,i){hd.appendChild(h("th",{text:x,class:i>=4?"num":""}));});tb.appendChild(h("thead",null,[hd]));
  var body=h("tbody");
  rows.forEach(function(x){var p=x.p,isPick=intent.indexOf(p.k)>=0,off=!!offSet[p.k],tr=h("tr",{class:(effSet[p.k]?"kept":"")+(off?" autooff":""),"data-k":p.k});
    var cb=h("input",{type:"checkbox","aria-label":"Keep "+p.n});cb.checked=isPick;if(!cb.checked&&intent.length>=max)cb.disabled=true;
    cb.addEventListener("change",function(){var a=(KB.keep[t.id]||[]).filter(function(k){return k!==p.k;});if(cb.checked)a.push(p.k);KB.keep[t.id]=a.slice(0,max);kbSave();kbRender();});
    var inp=h("input",{type:"number",class:"wi-kb-rk",min:"1",max:String(kbUniverse().length),value:String(x.rank),"aria-label":"Rank of "+p.n});
    inp.addEventListener("change",function(){kbEdit(p.k,inp.value);kbRender();});
    var up=h("button",{type:"button",class:"wi-kb-mv","aria-label":"Move "+p.n+" up one rank",text:"▲"}),dn=h("button",{type:"button",class:"wi-kb-mv","aria-label":"Move "+p.n+" down one rank",text:"▼"});
    up.addEventListener("click",function(){kbEdit(p.k,x.rank-1);kbRender();});dn.addEventListener("click",function(){kbEdit(p.k,x.rank+1);kbRender();});
    var moved=set.pins.some(function(q){return q[0]===p.k;}),nmc=h("td",null,[h("b",{text:p.n}),h("small",{text:" "+p.pos+(p.nba?" · "+p.nba:"")})]);
    if(p.rk)nmc.appendChild(h("span",{class:"wi-kb-tag",title:"2026 rookie",text:"R"}));if(p.s==="IL"||p.s==="IL+")nmc.appendChild(h("span",{class:"wi-kb-tag",title:"On the injured list",text:p.s}));
    if(!x.sal)nmc.appendChild(h("span",{class:"wi-kb-tag z",title:"Ranked outside the paid ranks: cap 0",text:"0"}));
    if(off)nmc.appendChild(h("span",{class:"wi-kb-tag auto",title:"Picked, but left out automatically to keep the team under the ceiling",text:"AUTO-OFF"}));
    var s0=kbSalaryAt(y0[p.k]),dr=y0[p.k]-x.rank,sc=h("td",{class:"num"},[h("span",{text:String(x.sal)})]),cd=h("td",{class:"num"},[s0!==x.sal?h("small",{class:"wi-kb-dl "+(x.sal>s0?"up":"down"),title:"Salary under Yahoo's order: "+s0,text:sgn(x.sal-s0)}):null]),
      rd=h("td",null,[dr?h("span",{class:"kbb-rd"+(dr>0?" up":" dn"),title:"Yahoo's order: #"+y0[p.k],text:(dr>0?"▲ ":"▼ ")+Math.abs(dr)}):null]);
    tr.appendChild(h("td",null,[cb]));tr.appendChild(h("td",{class:"wi-kb-rkc"+(moved?" moved":"")},[inp,up,dn]));tr.appendChild(rd);tr.appendChild(nmc);tr.appendChild(sc);tr.appendChild(cd);body.appendChild(tr);});
  tb.appendChild(body);frag.appendChild(h("div",{class:"wi-kb-wrap"},[tb]));
  var act=h("div",{class:"wi-kb-act"});act.appendChild(kbBtn("Clear this team's keepers",function(){KB.keep[t.id]=[];kbSave();kbRender();},"kb-clear"));frag.appendChild(act);
  /* 5. ripple of the last move */
  if(KB.last&&KB.last.rip.players){var L=KB.last,r=L.rip,rb=h("details",{class:"wi-kb-rip",open:"open"},[h("summary",{text:"Your last move: "+kbName(L.k)+" #"+L.from+" → #"+L.to+" re-priced "+r.players+" rostered player"+(r.players>1?"s":"")+" on "+r.teams.length+" team"+(r.teams.length>1?"s":"")})]);
    r.teams.forEach(function(g){var line=h("div",{class:"wi-kb-rl"},[tchip(g.t),h("b",{class:g.net>0?"up":"down",text:" "+sgn(g.net)+" total "}),h("span",{text:g.rows.slice(0,6).map(function(w){return w.n+" "+w.a+"→"+w.b;}).join(" · ")+(g.rows.length>6?" · +"+(g.rows.length-6)+" more":"")})]);rb.appendChild(line);});
    frag.appendChild(rb);}
  else if(KB.last)frag.appendChild(h("div",{class:"wi-kb-sub",text:"Your last move, "+kbName(KB.last.k)+" #"+KB.last.from+" → #"+KB.last.to+", changed no rostered player's salary (those ranks pay the same)."}));
  /* 6. league impact of the whole ranking */
  var lg=h("details",{class:"wi-kb-lg"},[h("summary",{text:"League impact of this ranking vs Yahoo's order"})]);if(KB.lg)lg.setAttribute("open","");
  lg.addEventListener("toggle",function(){KB.lg=lg.open;});
  var lt=h("table",{class:"wi-table wi-kb-lt"}),lh=h("tr");["Team","Top "+max+" payroll","vs Yahoo order","Keeper plan","Plan payroll"].forEach(function(x,i){lh.appendChild(h("th",{text:x,class:i>0&&i!==3?"num":""}));});lt.appendChild(h("thead",null,[lh]));
  var lb=h("tbody");
  kb.teams.forEach(function(x){var top=kbTop9(x,rank),top0=kbTop9(x,y0),f=fits[x.id],it=kbIntent(x),tr=h("tr",{class:x.id===t.id?"on":""});
    tr.appendChild(h("td",null,[tchip(x)]));tr.appendChild(h("td",{class:"num "+kbBandStatus(top),text:String(top)}));
    tr.appendChild(h("td",{class:"num "+(top>top0?"up":top<top0?"down":""),text:top===top0?"0":sgn(top-top0)}));
    tr.appendChild(h("td",{text:it.length?(f.eff.length+"/"+max+(f.off.length?" (−"+f.off.length+" auto)":"")):"no plan"}));
    tr.appendChild(h("td",{class:"num "+(it.length?kbBandStatus(f.pay):""),text:it.length?String(f.pay):"–"}));
    tr.addEventListener("click",function(){KB.team=x.id;kbSave();kbRender();});lb.appendChild(tr);});
  lt.appendChild(lb);lg.appendChild(h("div",{class:"wi-kb-wrap"},[lt]));
  lg.appendChild(h("div",{class:"wi-kb-sub",text:"Top "+max+" payroll is every rostered player ranked by this ranking, highest "+max+" salaries (the cap rule). Plan payroll is that team's picked keepers after any automatic adjustment."}));
  frag.appendChild(lg);
  frag.appendChild(h("div",{class:"wi-kb-src",text:"Rosters as of "+(kb.rosters.verifiedAt||"").slice(0,10)+" (trades applied). Rank→salary table: Yahoo Top 300 fetched "+String(kb.source.fetchedAt||"").slice(0,10)+", "+kb.source.paidRanks+" paid ranks of "+kb.source.players+". Rank is league-wide (1 = highest). Players outside the list rank after it at 0; drafted rookies are not special-cased."}));
  return frag;}

/* ---------- the rankings board: every ranked player on one big window, edit ranks and watch all 16 caps move ---------- */
var BD={open:false,q:"",team:"",moved:false,pos:"",drag:null,flash:{}};
function kbFitsAll(rank){var f={};W.keeperBoard.teams.forEach(function(x){f[x.id]=kbFit(x,kbIntent(x),rank,KB.auto);});return f;}
function kbOwnerCache(){if(KB.owner)return KB.owner;var o={};W.keeperBoard.teams.forEach(function(t){t.players.forEach(function(p){o[p.k]={t:t,p:p};});});KB.owner=o;return o;}
function bdEdit(k,q){if(!kbEdit(k,q)){bdRender();return;}BD.flash={};if(KB.last)KB.last.rip.teams.forEach(function(g){BD.flash[g.t.id]=g.net;});bdRender();syncUrl();
  var row=document.querySelector("#kb-board .kbb-row[data-k=\""+k+"\"]");if(row){row.classList.add("just");try{row.scrollIntoView({block:"center"});}catch(e){}}}
function bdRender(){
  var ov=document.getElementById("kb-board");if(!ov)return;var kb=W.keeperBoard,rank=kbRanking(),y0=kbRankOf([]),set=kbSet(),own=kbOwnerCache(),max=kb.keeperMax;
  var list=ov.querySelector(".kbb-list"),side=ov.querySelector(".kbb-side"),top=list.scrollTop;
  var moved={};set.pins.forEach(function(x){moved[x[0]]=1;});
  var rows=kbUniverse().slice().sort(function(a,b){return rank[a]-rank[b];}).filter(function(k){var o=own[k];
    if(BD.team&&(!o||o.t.id!==BD.team))return false;if(BD.moved&&!moved[k])return false;
    if(BD.pos&&!(o&&String(o.p.pos||"").split("/").indexOf(BD.pos)>=0))return false;
    if(BD.q&&kbNorm(kbName(k)).indexOf(kbNorm(BD.q))<0)return false;return true;});
  list.textContent="";var frag=document.createDocumentFragment(),paid=kb.salaryByRank.length,cutA=false,cutB=false,shown=0;
  frag.appendChild(h("div",{class:"kbb-head"},[h("span"),h("span",{text:"RANK"}),h("span"),h("span",{text:"VS YAHOO",title:"How far you moved him from Yahoo's order"}),h("span",{text:"PLAYER"}),h("span",{text:"TEAM"}),h("span",{class:"r",text:"CAP",title:"Salary at his rank"}),h("span",{class:"r",text:"CAP Δ",title:"Change in salary against Yahoo's order"})]));
  rows.forEach(function(k){var rk=rank[k],o=own[k],sal=kbSalaryAt(rk),s0=kbSalaryAt(y0[k]);
    if(!cutB&&rk>144&&!BD.team&&!BD.q){cutB=true;if(rk>paid||true){}}
    if(!cutA&&rk>paid&&!BD.q&&!BD.team&&!BD.moved){cutA=true;frag.appendChild(h("div",{class:"kbb-cut"},[h("span",{text:"Salaries end here: ranks "+(paid+1)+" and below carry 0"})]));}
    var tr=h("div",{class:"kbb-row"+(moved[k]?" moved":"")+(o?"":" fa")+(BD.team&&o&&o.t.id===BD.team?" mine":""),"data-k":k,draggable:"true"});
    var inp=h("input",{type:"number",class:"kbb-rk",min:"1",max:String(kbUniverse().length),value:String(rk),"aria-label":"Rank of "+kbName(k)});
    inp.addEventListener("change",function(){bdEdit(k,inp.value);});
    var up=h("button",{type:"button",class:"wi-kb-mv","aria-label":"Move "+kbName(k)+" up one rank",text:"▲"}),dn=h("button",{type:"button",class:"wi-kb-mv","aria-label":"Move "+kbName(k)+" down one rank",text:"▼"});
    up.addEventListener("click",function(){bdEdit(k,rk-1);});dn.addEventListener("click",function(){bdEdit(k,rk+1);});
    var nm=h("div",{class:"kbb-nm"},[h("b",{text:kbName(k)}),o?h("small",{text:" "+(o.p.pos||"")+(o.p.nba?" · "+o.p.nba:"")}):h("small",{text:" not on a roster"})]);
    if(o&&o.p.rk)nm.appendChild(h("span",{class:"wi-kb-tag",title:"2026 rookie",text:"R"}));
    var dr=y0[k]-rk,rkd=h("span",{class:"kbb-rd"+(dr>0?" up":dr<0?" dn":""),title:dr?("Yahoo's order: #"+y0[k]+(dr>0?" · you moved him up "+dr:" · you moved him down "+(-dr))):"Same rank as Yahoo's order"},[dr?(dr>0?"▲ ":"▼ ")+Math.abs(dr):""]);
    var capd=h("span",{class:"kbb-cd"+(sal>s0?" up":sal<s0?" dn":""),title:s0!==sal?"Salary under Yahoo's order: "+s0:"Same salary as Yahoo's order"},[s0!==sal?sgn(sal-s0):""]);
    tr.appendChild(h("span",{class:"kbb-grip",title:"Drag onto another row to take that rank",text:"⋮⋮"}));tr.appendChild(inp);tr.appendChild(h("span",{class:"kbb-arrows"},[up,dn]));tr.appendChild(rkd);tr.appendChild(nm);
    tr.appendChild(o?h("span",{class:"kbb-own"},[tchip(o.t)]):h("span"));tr.appendChild(h("span",{class:"kbb-sal",text:String(sal)}));tr.appendChild(capd);
    tr.addEventListener("dragstart",function(e){BD.drag=k;tr.classList.add("drag");try{e.dataTransfer.setData("text/plain",k);e.dataTransfer.effectAllowed="move";}catch(x){}});
    tr.addEventListener("dragend",function(){BD.drag=null;tr.classList.remove("drag");});
    tr.addEventListener("dragover",function(e){if(BD.drag&&BD.drag!==k){e.preventDefault();tr.classList.add("over");}});tr.addEventListener("dragleave",function(){tr.classList.remove("over");});
    tr.addEventListener("drop",function(e){e.preventDefault();tr.classList.remove("over");if(BD.drag&&BD.drag!==k){var d=BD.drag;BD.drag=null;bdEdit(d,rank[k]);}});
    frag.appendChild(tr);shown++;});
  if(!shown)frag.appendChild(h("div",{class:"kbb-empty",text:"No players match."}));
  list.appendChild(frag);list.scrollTop=top;
  /* the 16 caps, live */
  side.textContent="";var fits=kbFitsAll(rank),b=kb.band;
  side.appendChild(h("div",{class:"kbb-st",text:"TEAM CAPS · TOP "+max+" PAYROLL"}));
  if(KB.last)side.appendChild(h("div",{class:"kbb-last",text:kbName(KB.last.k)+" #"+KB.last.from+" → #"+KB.last.to+(KB.last.rip.players?": re-priced "+KB.last.rip.players+" player"+(KB.last.rip.players>1?"s":"")+" on "+KB.last.rip.teams.length+" team"+(KB.last.rip.teams.length>1?"s":""):": no salary changed")}));
  kb.teams.forEach(function(t){var top9=kbTop9(t,rank),t0=kbTop9(t,y0),st=kbBandStatus(top9),it=kbIntent(t),f=fits[t.id],pc=function(v){return Math.max(0,Math.min(1,(v-100)/110))*100;};
    var row=h("button",{type:"button",class:"kbb-t "+st+(BD.team===t.id?" on":"")+(BD.flash[t.id]?" chg":""),title:t.name},[
      h("span",{class:"kbb-t1"},[tchip(t),h("b",{class:"kbb-pay",text:String(top9)}),h("small",{class:top9>t0?"up":top9<t0?"down":"",text:top9===t0?"":sgn(top9-t0)})]),
      h("span",{class:"kbb-meter"},[h("i",{class:"band",style:"left:"+pc(b.floor)+"%;width:"+(pc(b.ceiling)-pc(b.floor))+"%"}),h("i",{class:"dot",style:"left:"+pc(top9)+"%"})]),
      it.length?h("small",{class:"kbb-plan "+kbBandStatus(f.pay),text:"plan "+f.eff.length+"/"+max+" · "+f.pay+(f.off.length?" · −"+f.off.length+" auto":"")}):null]);
    row.addEventListener("click",function(){BD.team=BD.team===t.id?"":t.id;var s=ov.querySelector("#kbb-team");if(s)s.value=BD.team;bdRender();});side.appendChild(row);});
  side.appendChild(h("div",{class:"kbb-note",text:"Band "+b.floor+"–"+b.ceiling+". Payroll is each team's "+max+" highest salaries under this ranking; the arrow is the change against Yahoo's order. Tap a team to show only its players."}));
  var cnt=ov.querySelector(".kbb-count");if(cnt)cnt.textContent=rows.length+" of "+kbUniverse().length+" players · "+set.pins.length+" moved";
}
function bdClose(){var ov=document.getElementById("kb-board");if(ov)ov.remove();BD.open=false;document.removeEventListener("keydown",bdEsc);document.body.classList.remove("kbb-open");KB.last=KB.last;kbRender();}
function bdEsc(e){
  if(e.key==="Tab"){var ov=document.getElementById("kb-board");if(ov){var f=[].slice.call(ov.querySelectorAll("button,input,select,[tabindex]")).filter(function(x){return !x.disabled&&x.offsetParent!==null;});
    if(f.length){var first=f[0],last=f[f.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}else if(!ov.contains(document.activeElement)){e.preventDefault();first.focus();}}}return;}
  if(e.key==="Escape"){var t=e.target;if(t&&/^(INPUT|SELECT)$/.test(t.tagName)&&t.type==="search"&&t.value){t.value="";BD.q="";bdRender();}else bdClose();}}
function bdOpen(){
  if(document.getElementById("kb-board"))return;if(!KB.loaded)kbLoad();BD.open=true;BD.flash={};document.body.classList.add("kbb-open");
  var kb=W.keeperBoard,set=kbSet(),ov=h("div",{class:"kbb",id:"kb-board",role:"dialog","aria-modal":"true","aria-label":"Rankings board"});
  var q=h("input",{type:"search",id:"kbb-q",placeholder:"Find a player",value:BD.q,"aria-label":"Find a player"});q.addEventListener("input",function(){BD.q=q.value;bdRender();});
  var ts=h("select",{id:"kbb-team","aria-label":"Team"},[h("option",{value:"",text:"All teams"})].concat(kb.teams.map(function(t){return h("option",{value:t.id,text:t.short});})));ts.value=BD.team;ts.addEventListener("change",function(){BD.team=ts.value;bdRender();});
  var ps=h("select",{id:"kbb-pos","aria-label":"Position"},[h("option",{value:"",text:"Any position"})].concat(["PG","SG","SF","PF","C"].map(function(x){return h("option",{value:x,text:x});})));ps.value=BD.pos;ps.addEventListener("change",function(){BD.pos=ps.value;bdRender();});
  var mv=h("input",{type:"checkbox",id:"kbb-moved"});mv.checked=BD.moved;mv.addEventListener("change",function(){BD.moved=mv.checked;bdRender();});
  var setSel=h("select",{id:"kbb-set","aria-label":"Ranking set"});Object.keys(KB.sets).forEach(function(id){var o=h("option",{value:id,text:KB.sets[id].label});if(id===KB.active)o.selected=true;setSel.appendChild(o);});
  setSel.addEventListener("change",function(){KB.active=setSel.value;KB.last=null;BD.flash={};kbSave();bdRender();syncUrl();});
  var rs=kbSure("Reset ranks",function(){var s=kbSet();s.pins=s.base?s.base.slice():[];KB.last=null;BD.flash={};kbSave();bdRender();syncUrl();},"kbb-reset");
  var ex=kbBtn("Export",function(){if(window.NBA_EXPORT)window.NBA_EXPORT.hub();},"kbb-export");
  var x=h("button",{type:"button",class:"kbb-x","aria-label":"Close the rankings board",text:"✕"});x.addEventListener("click",bdClose);
  ov.appendChild(h("div",{class:"kbb-hd"},[h("div",{class:"kbb-ti"},[h("b",{text:"RANKINGS BOARD"}),h("span",{text:"YOUR ASSUMPTION · NOT OFFICIAL"})]),h("label",{class:"wi-kb-lab"},[h("span",{text:"RANKING"}),setSel]),q,ts,ps,h("label",{class:"wi-kb-chk"},[mv,"Moved only"]),h("span",{class:"kbb-count"}),rs,ex,x]));
  ov.appendChild(h("div",{class:"kbb-body"},[h("div",{class:"kbb-list",role:"list"}),h("aside",{class:"kbb-side","aria-label":"Team caps"})]));
  document.body.appendChild(ov);document.addEventListener("keydown",bdEsc);bdRender();q.focus();}
/* ---------- exports of the keepers simulator: image, link and text for each ---------- */
function kbDocBase(title,sub,blocks,link){return {title:title,sub:sub,tag:"YOUR ASSUMPTION · NOT OFFICIAL",blocks:blocks,foot:"NBA Talk VN Dynasty · "+kbSet().label+(kbSet().pins.length?" ("+kbSet().pins.length+" moved)":" (Yahoo order)"),link:link};}
function kbExports(){
  var kb=W.keeperBoard;if(!KB.loaded)kbLoad();
  var set=function(){return kbSet();},label=function(){return KB.active==="mine"?"Shared ranking":set().label;};
  return [
   {id:"kb-team",label:"Keeper plan: "+kbTeam().short,desc:"This team's keepers, salaries and payroll against the band",link:function(){return kbLink(label());},pages:function(){
     var t=kbTeam(),rank=kbRanking(),fit=kbFit(t,kbIntent(t),rank,KB.auto),b=kb.band,intent=kbIntent(t),eff={},off={};fit.eff.forEach(function(k){eff[k]=1;});fit.off.forEach(function(k){off[k]=1;});
     var rows=t.players.map(function(p){return {p:p,rk:rank[p.k],s:kbSalaryAt(rank[p.k])};}).sort(function(a,c){return a.rk-c.rk;}).map(function(x){var st=eff[x.p.k]?"KEEP":off[x.p.k]?"AUTO-OFF":"";
       return {tone:off[x.p.k]?"warn":"",b:!!eff[x.p.k],c:[st,String(x.rk),x.p.n+(x.p.rk?" · R":""),String(x.s)]};});
     var blocks=[{t:"stats",items:[{v:fit.eff.length+"/"+kb.keeperMax,l:"KEEPING"},{v:fit.pay,l:"KEEPER PAYROLL",tone:fit.pay>b.ceiling?"bad":""},{v:b.floor+"–"+b.ceiling,l:"OFFICIAL BAND"},{v:fit.pay>b.ceiling?fit.pay-b.ceiling:b.ceiling-fit.pay,l:fit.pay>b.ceiling?"OVER CEILING":"ROOM TO CEILING",tone:fit.pay>b.ceiling?"bad":"ok"}]},
       {t:"table",cols:[{h:"",w:2},{h:"RANK",w:1.2,a:"r",m:1},{h:"PLAYER",w:5},{h:"SALARY",w:1.5,a:"r",m:1}],rows:rows}];
     if(fit.off.length)blocks.splice(1,0,{t:"note",tone:"warn",text:"Auto-adjusted: "+fit.off.map(kbName).join(", ")+" left out to stay at or under "+b.ceiling+"."});
     return [{label:t.short,name:"keepers-"+t.short+".png",alt:"Keeper plan for "+t.short,doc:kbDocBase(t.name||t.short,"Next season's keepers · rank decides salary",blocks,kbLink(label()))}];}},
   {id:"kb-all",label:"All teams' keeper plans",desc:"Every team's chosen keepers on two images",link:function(){return kbLink(label());},pages:function(){
     var rank=kbRanking(),fits=kbFitsAll(rank),cards=kb.teams.map(function(t){var f=fits[t.id],it=kbIntent(t),offs={};f.off.forEach(function(k){offs[k]=1;});
       var lines=it.length?it.slice().sort(function(a,c){return rank[a]-rank[c];}).map(function(k){return {l:kbName(k)+(offs[k]?" (auto-off)":""),r:kbSalaryAt(rank[k]),tone:offs[k]?"mute":"",b:!offs[k]};}):[{l:"no plan yet",r:"",tone:"mute"}];
       return {team:t.id,head:it.length?String(f.pay):"–",tone:it.length&&f.pay>kb.band.ceiling?"bad":"",sub:it.length?f.eff.length+"/"+kb.keeperMax+" keepers":"",lines:lines};});
     var a=cards.slice(0,8),c=cards.slice(8),mk=function(list,part){return kbDocBase("Keeper plans","Band "+kb.band.floor+"–"+kb.band.ceiling+" · teams "+part,[{t:"cards",cols:2,cards:list}],kbLink(label()));};
     return [{label:"Teams 1–8",name:"keeper-plans-1-8.png",alt:"Keeper plans, teams 1 to 8",doc:mk(a,"1–8")},{label:"Teams 9–16",name:"keeper-plans-9-16.png",alt:"Keeper plans, teams 9 to 16",doc:mk(c,"9–16")}];}},
   {id:"kb-league",label:"League impact of this ranking",desc:"Every team's payroll under this ranking against Yahoo's order",link:function(){return kbLink(label());},pages:function(){
     var rank=kbRanking(),y0=kbRankOf([]),fits=kbFitsAll(rank),max=kb.keeperMax;
     var rows=kb.teams.map(function(t){var top=kbTop9(t,rank),top0=kbTop9(t,y0),f=fits[t.id],it=kbIntent(t),st=kbBandStatus(top);
       return {tone:st==="over"?"bad":st==="near"?"warn":"",c:[{team:t.id},String(top),top===top0?"0":sgn(top-top0),it.length?f.eff.length+"/"+max+(f.off.length?" (−"+f.off.length+" auto)":""):"no plan",it.length?String(f.pay):"–"]};}).sort(function(a,c){return +c.c[1]-+a.c[1];});
     return [{label:"League",name:"keepers-league-impact.png",alt:"League impact of this ranking",doc:kbDocBase("League impact","Top "+max+" payroll under this ranking vs Yahoo's order · band "+kb.band.floor+"–"+kb.band.ceiling,[{t:"table",cols:[{h:"TEAM",w:3},{h:"TOP "+max,w:1.6,a:"r",m:1},{h:"VS YAHOO",w:1.6,a:"r",m:1},{h:"PLAN",w:2.4,a:"r"},{h:"PLAN PAY",w:1.6,a:"r",m:1}],rows:rows}],kbLink(label()))}];}},
   {id:"kb-movers",label:"Biggest salary swings",desc:"Rostered players whose cap moves most under this ranking",link:function(){return kbLink(label());},pages:function(){
     var rank=kbRanking(),y0=kbRankOf([]),own=kbOwnerCache(),rows=[];
     Object.keys(own).forEach(function(k){var a=kbSalaryAt(y0[k]),b=kbSalaryAt(rank[k]);if(a!==b)rows.push({k:k,a:a,b:b,d:b-a,o:own[k]});});
     rows.sort(function(x,y){return Math.abs(y.d)-Math.abs(x.d)||x.k.localeCompare(y.k);});
     var r=rows.slice(0,40).map(function(x){return {tone:x.d>0?"warn":"",c:[{team:x.o.t.id},kbName(x.k),"#"+y0[x.k]+" → #"+rank[x.k],String(x.b),sgn(x.d)]};});
     if(!r.length)r=[{c:["","Nothing moves: this is Yahoo's order","","",""]}];
     return [{label:"Swings",name:"keepers-salary-swings.png",alt:"Biggest salary swings",doc:kbDocBase(label(),"Cap under this ranking vs Yahoo's order · "+rows.length+" rostered players change",[{t:"table",cols:[{h:"TEAM",w:2.2},{h:"PLAYER",w:4},{h:"RANK",w:2.4,a:"r",m:1},{h:"CAP",w:1,a:"r",m:1},{h:"Δ",w:1,a:"r",m:1}],rh:42,rows:r}],kbLink(label()))}];}},
   {id:"kb-rank",label:"My ranking",desc:"The top of your ranking and every player you moved",link:function(){return kbLink(label());},pages:function(){
     var rank=kbRanking(),y0=kbRankOf([]),own=kbOwnerCache(),s=set(),movedSet={};s.pins.forEach(function(x){movedSet[x[0]]=1;});
     var order=kbUniverse().slice().sort(function(a,b){return rank[a]-rank[b];}),mk=function(k){var o=own[k],rk=rank[k],d=y0[k]-rk;return {tone:movedSet[k]?"warn":"",c:[String(rk),kbName(k),o?{team:o.t.id}:"free agent",String(kbSalaryAt(rk)),d?(d>0?"↑":"↓")+Math.abs(d):""]};};
     var cols=[{h:"RANK",w:1.2,a:"r",m:1},{h:"PLAYER",w:4.4},{h:"TEAM",w:2.2},{h:"SALARY",w:1.5,a:"r",m:1},{h:"VS YAHOO",w:1.6,a:"r"}];
     var pages=[{label:"Top 60",name:"ranking-top-60.png",alt:"Top 60 of the ranking",doc:kbDocBase(s.label,"Top 60 · highlighted rows are players you moved off Yahoo's order",[{t:"table",cols:cols,rh:42,rows:order.slice(0,60).map(mk)}],kbLink(label()))}];
     var mv=order.filter(function(k){return movedSet[k];});
     if(mv.length)pages.push({label:"Moved ("+mv.length+")",name:"ranking-moved.png",alt:"Players moved",doc:kbDocBase(s.label,"Every player moved off Yahoo's order, best rank first",[{t:"table",cols:cols,rh:42,rows:mv.map(mk)}],kbLink(label()))});
     return pages;}}
  ];}

/* ---------- render / wiring ---------- */
function render(){
  if(!S.on){root.textContent="";return;}
  var y=window.pageYOffset;
  S.snapShort=fdate(snap().meta.effectiveDate).replace(/ \d{4}$/,"").toUpperCase();
  root.textContent="";
  if(S.view==="now"&&!snap().now)S.view="same";
  if(S.view==="keepers"&&!W.keeperBoard)S.view="same";
  if(S.view==="keepers"){var back=h("button",{type:"button",class:"wi-kb-back",text:"← Other What If views"});back.addEventListener("click",function(){S.view="same";S.animate=true;render();syncUrl();});root.appendChild(back);}
  else{root.appendChild(header());root.appendChild(seg());}
  root.appendChild(S.view==="same"?viewSame():S.view==="redo"?viewRedo():S.view==="now"?viewNow():S.view==="keepers"&&W.keeperBoard?viewKeepers():viewFa());
  if(S.flash){var f=root.querySelector(".player-row[data-k=\""+(S.flashKey||"")+"\"]");if(f&&!reduce)f.classList.add("flash");S.flash=null;S.flashKey=null;}
  S.animate=false;
  if(window.NBA_MONO)window.NBA_MONO(root);
  window.scrollTo(0,y);}
function setActive(on){
  if(on===S.on)return;
  S.on=on;page.hidden=!on;
  if(on){S.animate=true;render();window.scrollTo(0,0);}else{root.textContent="";}}
function syncUrl(){try{document.dispatchEvent(new Event("whatif:change"));}catch(e){}}
function query(){return S.on?"?mode=whatif&view="+S.view+(S.sort!=="team"?"&sort="+S.sort:"")+(W.order.length>1?"&snap="+S.snap:"")+(S.view==="keepers"?kbQuery():""):"";}
function restore(qs){var v=qs.get("view");if(v==="same"||v==="redo"||v==="fa"||v==="now"||(v==="keepers"&&W.keeperBoard)){S.view=v;if(v==="keepers")kbRestore(qs);}var so=qs.get("sort");if(so)S.sort=so;var sn=qs.get("snap");if(sn&&W.snapshots[sn])S.snap=sn;}
var css=document.createElement("style");css.textContent="@keyframes wi-flash{from{background-color:#dfe3ff}to{background-color:transparent}}.wi-card .player-row.flash{animation:wi-flash .7s ease}@media (prefers-reduced-motion:reduce){.wi-card .player-row.flash{animation:none}}";
document.head.appendChild(css);
window.NBA_WHATIF={exports:function(){return S.view==="keepers"&&W.keeperBoard?kbExports():[];},openBoard:function(){if(W.keeperBoard)bdOpen();},openKeepers:function(){if(W.keeperBoard)S.view="keepers";return !!W.keeperBoard;},viewName:function(){return S.view;},setActive:setActive,isActive:function(){return S.on;},query:query,restore:restore,classify:classify,compliance:compliance,state:S};
})();
