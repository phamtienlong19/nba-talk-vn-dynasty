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
   ". Salary = projected_auction_value ("+m.playerCount+" ranked players); players outside the list count as $0.";}
function header(){
  var s=snap(),m=s.meta,b=s.band;
  var bar=h("div",{class:"wi-bar"});
  var p1=h("span",{class:"meta-pill wi-pill-wi"},[h("span",{class:"pill-k",text:"SNAPSHOT"})," ",h("strong",{text:fdate(m.effectiveDate)}),help("prov",provenance(m))]);
  var capTxt=b.official.floor+"–"+b.official.ceiling+(b.formulaMatchesOfficial?"":"  →  "+b.whatIf.floor+"–"+b.whatIf.ceiling);
  var p2=h("span",{class:"meta-pill meta-pill-cap"},[h("span",{class:"pill-k",text:"CAP"}),h("span",{class:"pill-v",text:capTxt}),
    help("band",b.formulaMatchesOfficial?"Recomputed from the snapshot with the same top-144 benchmark model ("+b.whatIf.benchmark+" → floor "+b.whatIf.rawFloor+", ceiling "+b.whatIf.rawCeiling+"). The rounded band equals the official 131–178 band, so nothing moves.":
      "Recomputed from the snapshot with the same top-144 benchmark model: benchmark "+b.whatIf.benchmark+", floor "+b.whatIf.rawFloor+", ceiling "+b.whatIf.rawCeiling+". Differs from the official band; the official band is untouched.")]);
  var p3=h("span",{class:"meta-pill"},["SIMULATION · OFFICIAL RECORD UNCHANGED",help("sim","Keeper selections, salaries, cuts, picks, lottery and the official FA/DRAFT 60 are read-only inputs here. Nothing on this page is written back; leaving What If shows the unchanged official board.")]);
  bar.appendChild(p1);bar.appendChild(p2);bar.appendChild(p3);
  if(W.order.length>1){var sel=h("select",{"aria-label":"Snapshot"});W.order.forEach(function(id){var o=h("option",{value:id,text:fdate(W.snapshots[id].meta.effectiveDate)});if(id===S.snap)o.selected=true;sel.appendChild(o);});
    sel.addEventListener("change",function(){S.snap=sel.value;S.open={};S.animate=true;render();});bar.appendChild(sel);}
  return bar;}
function seg(){
  var wrap=h("div");var g=h("div",{class:"wi-seg",role:"group","aria-label":"What-if view"});
  [["same","SAME KEEPERS"],["redo","REDO CUTS"],["fa","FA 60"]].forEach(function(v){
    var b=h("button",{type:"button","aria-pressed":S.view===v[0]?"true":"false",text:v[1]});
    b.addEventListener("click",function(){S.view=v[0];S.animate=true;render();syncUrl();});g.appendChild(b);});
  wrap.appendChild(g);
  var tips={same:"Scenario A — every franchise keeps exactly its official nine, repriced at the snapshot. Deterministic.",
            redo:"Scenario B — a projection, not a reconstruction of intent: fewest-change legal keeper sets if managers had known these prices. Equally good alternatives are listed, never hidden.",
            fa:"The FA/DRAFT 60 rebuilt with the same ranking rules, once with the projected keeper/cut decisions and snapshot prices."};
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
  t.players.filter(function(p){return p.k0;}).forEach(function(p){
    var d=p.c1-p.c0,big=Math.abs(d)>=3;
    var row=h("div",{class:"player-row"+(big?" big "+dcls(d):"")});
    row.appendChild(h("div",{class:"pos",text:p.pos}));
    row.appendChild(h("div",{class:"pname",title:p.n,text:p.n},p.miss?[h("span",{class:"wi-tag miss",title:"Not in the Yahoo snapshot — counted as $0",text:"∅"})]:[]));
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
    if(p.miss)tags.push(h("span",{class:"wi-tag miss",title:"Not in the Yahoo snapshot — counted as $0",text:"∅"}));
    row.appendChild(h("div",{class:"pos",text:p.pos}));
    row.appendChild(h("div",{class:"pname",title:p.n+(p.c0!==p.c1?" — official "+p.c0:""),text:p.n},tags));
    var c1=h("div",{class:"c1"});c1.textContent=String(p.c1);if(p.c0!==p.c1)c1.appendChild(h("small",{style:"display:block;font:500 9px Roboto Mono,monospace;color:#7a869c",text:"was "+p.c0}));row.appendChild(c1);
    var lockCut=isK&&p.lock&&p.k0,full=!isK&&keepCount(ks)>=max;
    var tg=h("button",{type:"button",class:"wi-tg","aria-pressed":isK?"true":"false",text:isK?"✓ KEPT":"✕ CUT",
      title:lockCut?"A $"+p.c1+" player can never be dropped":full?"Nine keepers maximum — cut someone first":(p.rev&&isK&&p.k0?"$10–19 drops need commissioner review":"Toggle keep / cut (simulation only)")});
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

/* ---------- render / wiring ---------- */
function render(){
  if(!S.on){root.textContent="";return;}
  var y=window.pageYOffset;
  S.snapShort=fdate(snap().meta.effectiveDate).replace(/ \d{4}$/,"").toUpperCase();
  root.textContent="";
  root.appendChild(header());root.appendChild(seg());
  root.appendChild(S.view==="same"?viewSame():S.view==="redo"?viewRedo():viewFa());
  if(S.flash){var f=root.querySelector(".player-row[data-k=\""+(S.flashKey||"")+"\"]");if(f&&!reduce)f.classList.add("flash");S.flash=null;S.flashKey=null;}
  S.animate=false;
  window.scrollTo(0,y);}
function setActive(on){
  if(on===S.on)return;
  S.on=on;page.hidden=!on;
  if(on){S.animate=true;render();window.scrollTo(0,0);}else{root.textContent="";}}
function syncUrl(){try{document.dispatchEvent(new Event("whatif:change"));}catch(e){}}
function query(){return S.on?"?mode=whatif&view="+S.view+(S.sort!=="team"?"&sort="+S.sort:"")+(W.order.length>1?"&snap="+S.snap:""):"";}
function restore(qs){var v=qs.get("view");if(v==="same"||v==="redo"||v==="fa")S.view=v;var so=qs.get("sort");if(so)S.sort=so;var sn=qs.get("snap");if(sn&&W.snapshots[sn])S.snap=sn;}
var css=document.createElement("style");css.textContent="@keyframes wi-flash{from{background-color:#dfe3ff}to{background-color:transparent}}.wi-card .player-row.flash{animation:wi-flash .7s ease}@media (prefers-reduced-motion:reduce){.wi-card .player-row.flash{animation:none}}";
document.head.appendChild(css);
window.NBA_WHATIF={setActive:setActive,isActive:function(){return S.on;},query:query,restore:restore,classify:classify,compliance:compliance,state:S};
})();
