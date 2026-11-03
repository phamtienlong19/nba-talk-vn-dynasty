/* Roto points, ranks and all-play from one week's category totals: the page's port of scripts/roto.py (tests/test_roto.py holds both to one
   fixture). Pure functions over {teamId: stats}, stats shaped like the live feed's: fg [m,a], ft [m,a], tpm, pts, reb, ast, st, blk, to. */
(function(){
"use strict";
var CATS=[["fgPct",false],["ftPct",false],["tpm",false],["pts",false],["reb",false],["ast",false],["st",false],["blk",false],["to",true]];
function frac(stats,key){   /* an exact value {n,d}, or null when there is nothing to compare yet */
  if(key==="fgPct"||key==="ftPct"){var p=key==="fgPct"?stats.fg:stats.ft;return p&&p[1]?{n:p[0],d:p[1]}:null;}
  var v=stats[key];return v==null?null:{n:v,d:1};}
function cmp(a,b){var x=a.n*b.d,y=b.n*a.d;return x<y?-1:x>y?1:0;}
function places(vals,lower){   /* index -> points: 1 for the worst ... n for the best, level teams share the average */
  var order=vals.map(function(_,i){return i;}).sort(function(i,j){return lower?-cmp(vals[i],vals[j]):cmp(vals[i],vals[j]);}),out={},i=0;
  while(i<order.length){var j=i;while(j+1<order.length&&cmp(vals[order[j+1]],vals[order[i]])===0)j++;
    for(var k=i;k<=j;k++)out[order[k]]=(i+1+j+1)/2;i=j+1;}
  return out;}
function roto(stats){
  var ids=Object.keys(stats).map(Number).sort(function(a,b){return a-b;}),res={};
  ids.forEach(function(t){res[t]={points:{},total:0};});
  CATS.forEach(function(c){
    var vals=ids.map(function(t){return frac(stats[t],c[0]);});
    if(vals.some(function(v){return v==null;})){ids.forEach(function(t){res[t].points[c[0]]=null;});return;}
    var p=places(vals,c[1]);ids.forEach(function(t,k){res[t].points[c[0]]=p[k];res[t].total+=p[k];});});
  ids.forEach(function(t){res[t].rank=1+ids.filter(function(u){return res[u].total>res[t].total;}).length;});
  return res;}
function headToHead(a,b){
  var w=0,l=0,t=0,detail={};
  CATS.forEach(function(c){var x=frac(a,c[0]),y=frac(b,c[0]);
    if(x==null||y==null){detail[c[0]]=null;return;}
    var d=cmp(x,y);if(d===0){t++;detail[c[0]]=0;}else if((d<0)===c[1]){w++;detail[c[0]]=1;}else{l++;detail[c[0]]=-1;}});
  return {w:w,l:l,t:t,margin:w-l,detail:detail};}
function allPlay(stats){
  var ids=Object.keys(stats).map(Number).sort(function(a,b){return a-b;}),cells={},record={};
  ids.forEach(function(a){cells[a]={};var r=[0,0,0];
    ids.forEach(function(b){if(a===b)return;var c=headToHead(stats[a],stats[b]);cells[a][b]=c;r[c.margin>0?0:c.margin<0?1:2]++;});record[a]=r;});
  return {cells:cells,record:record};}
window.NBA_ROTO={roto:roto,headToHead:headToHead,allPlay:allPlay,CATS:CATS};
})();
