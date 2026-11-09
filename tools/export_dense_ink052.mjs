// Offline authoring only: no browser, window, sensor, package download or runtime import.
// Original geometric ink treatment: PolyForm Noncommercial 1.0.0; see LICENSE.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const NATIVE=path.join(ROOT,'native'),cache=new Map();
function load(name){
 if(cache.has(name))return cache.get(name);
 const raw=fs.readFileSync(path.join(NATIVE,name),'utf8'),context=vm.createContext({},{codeGeneration:{strings:false,wasm:false}});cache.set(name,context);
 for(const [,target,alias]of raw.matchAll(/^\.import\s+"([^"]+)"\s+as\s+(\w+)\s*$/gm))context[alias]=load(target);
 new vm.Script(raw.replace(/^\.(?:pragma|import)[^\r\n]*(?:\r?\n|$)/gm,''),{filename:name}).runInContext(context,{timeout:4000});return context;
}
// All curve root solving and verification below execute in this authoring tool,
// never in the generated runtime module. Degree<=6 and finite bisection only.
function number(v){return Number(v).toFixed(7).replace(/\.?0+$/,'')||'0'}
function attributes(tag){var a={};tag.replace(/([\w:-]+)="([^"]*)"/g,function(_,k,v){a[k]=v});return a}
function value(poly,t){var r=0;for(var i=poly.length-1;i>=0;i--)r=r*t+poly[i];return r}
function roots(poly){
 var p=poly.slice();while(p.length>1&&Math.abs(p[p.length-1])<1e-13)p.pop();
 if(p.length<=1)return [];
 if(p.length===2){var t=-p[0]/p[1];return t>0&&t<1?[t]:[]}
 var derivative=[];for(var i=1;i<p.length;i++)derivative.push(i*p[i]);
 var critical=roots(derivative),cuts=[0].concat(critical,[1]),out=[],epsilon=1e-11*(1+Math.max.apply(null,p.map(Math.abs)));
 function add(t){if(t>1e-10&&t<1-1e-10&&!out.some(function(v){return Math.abs(t-v)<1e-8}))out.push(t)}
 for(var j=1;j<cuts.length;j++){
  var lo=cuts[j-1],hi=cuts[j],a=value(p,lo),b=value(p,hi);
  if(Math.abs(a)<epsilon)add(lo);if(Math.abs(b)<epsilon)add(hi);
  if(a*b>=0)continue;
  for(var step=0;step<48;step++){var mid=(lo+hi)/2,c=value(p,mid);if(a*c<=0){hi=mid;b=c}else{lo=mid;a=c}}
  add((lo+hi)/2);
 }
 return out.sort(function(a,b){return a-b});
}
function coefficients(points,k){
 var a=points.map(function(p){return p[k]});
 return a.length===4?[a[0],3*(a[1]-a[0]),3*(a[0]-2*a[1]+a[2]),-a[0]+3*a[1]-3*a[2]+a[3]]
  :a.length===3?[a[0],2*(a[1]-a[0]),a[0]-2*a[1]+a[2]]:[a[0],a[1]-a[0]];
}
function circlePolynomial(points,r){
 var x=coefficients(points,0),y=coefficients(points,1),p=Array(2*x.length-1).fill(0);
 for(var i=0;i<x.length;i++)for(var j=0;j<x.length;j++)p[i+j]+=x[i]*x[j]+y[i]*y[j];p[0]-=r*r;return p;
}
function point(points,t){var row=points.map(function(p){return p.slice()});while(row.length>1){var next=[];for(var i=1;i<row.length;i++)next.push([(1-t)*row[i-1][0]+t*row[i][0],(1-t)*row[i-1][1]+t*row[i][1]]);row=next}return row[0]}
function split(points,t){var rows=[points.map(function(p){return p.slice()})];while(rows[rows.length-1].length>1){var r=rows[rows.length-1],next=[];for(var i=1;i<r.length;i++)next.push([(1-t)*r[i-1][0]+t*r[i][0],(1-t)*r[i-1][1]+t*r[i][1]]);rows.push(next)}return [rows.map(function(r){return r[0]}),rows.map(function(r){return r[r.length-1]}).reverse()]}
function segment(points,a,b){var left=b===1?points:split(points,b)[0];return a===0?left:split(left,a/b)[1]}
function parse(d){
 var commands=String(d).match(/[A-Za-z][^A-Za-z]*/g)||[];if(commands.length!==3||commands[0][0]!=='M'||commands[1][0]!=='C'||commands[2][0]!=='Q')return null;
 function nums(c){return (c.slice(1).match(/[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?/g)||[]).map(Number)}
 var m=nums(commands[0]),c=nums(commands[1]),q=nums(commands[2]);if(m.length!==2||c.length!==6||q.length!==4)return null;
 return [[m,[c[0],c[1]],[c[2],c[3]],[c[4],c[5]]],[[c[4],c[5]],[q[0],q[1]],[q[2],q[3]]]];
}
function clip(d,cap,pen){
 var curves=parse(d);if(!curves)return null;
 // Keep the entire stroke's round end outside the real cap; no opaque fill.
 var r=cap+pen/2+.000001,out='',kept=[],removed=0,max_error=0,last=null;
 for(var c=0;c<curves.length;c++){
  var points=curves[c],poly=circlePolynomial(points,r),cuts=[0].concat(roots(poly),[1]);
  for(var i=1;i<cuts.length;i++){
   var a=cuts[i-1],b=cuts[i];if(b-a<1e-9)continue;
   if(value(poly,(a+b)/2)<0){removed++;continue}
   var part=segment(points,a,b),command=part.length===4?'C':'Q';
   if(!last||Math.hypot(last[0]-part[0][0],last[1]-part[0][1])>1e-8)out+='M'+part[0].map(number).join(' ');
   out+=command+part.slice(1).map(function(p){return p.map(number).join(' ')}).join(' ');last=part[part.length-1];
   for(var t=0;t<=20;t++){var u=t/20,A=point(points,a+(b-a)*u),B=point(part,u);max_error=Math.max(max_error,Math.hypot(A[0]-B[0],A[1]-B[1]))}
   kept.push({points:part,original:points,interval:[a,b]});
  }
 }
 return {d:out,kept:kept,removed_intervals:removed,cap_radius:cap,clip_radius:r,pen:pen,max_curve_error:max_error};
}

const RUNTIME="// Generated by tools/export_dense_ink052.mjs; original ink, not retail CAD.\n// Runtime: finite exact-source lookup only. No root solver, stats, cache,\n// textures, clocks or I/O. Unmatched/unknown geometry retains its original ink.\nfunction attributes(tag) {\n    var out={}\n    tag.replace(/([\\w:-]+)=\"([^\"]*)\"/g,function(all,key,value){out[key]=value})\n    return out\n}\nfunction apply(source,state,profile) {\n    if(typeof source!=='string' || source.length>60000 || !state || state.kind!=='gpu'\n            || state.model_mode!==true || state.icon_set!=='notebook_line' || !profile\n            || !Number.isInteger(profile.blades) || profile.blades<11 || profile.blades>64\n            || profile.kind!=='axial' || profile.shape==='neutral')return source\n    var hubs=source.match(/<circle\\b[^>]*class=\"hardware-fan-hub\"[^>]*\\/>/g)||[]\n    if(hubs.length!==1)return source\n    var hub=attributes(hubs[0]),radius=Number(hub.r)\n    if(!Number.isFinite(radius) || radius<=0 || Number(hub.cx||0)!==0 || Number(hub.cy||0)!==0)return source\n    var leaves=source.match(/<path\\b[^>]*class=\"hardware-fan-blade\"[^>]*\\/>/g)||[]\n    if(leaves.length!==profile.blades)return source\n    var patches=[]\n    for(var i=0;i<leaves.length;i++) {\n        var original=attributes(leaves[i]),trim=template(radius,original.d)\n        // Never half-convert an unfamiliar rotor or merely thin unknown ink.\n        if(trim===null)return source\n        patches.push(leaves[i].replace(/\\bd=\"[^\"]*\"/,'d=\"'+trim+'\"')\n            .replace(/stroke-width=\"[^\"]*\"/,'stroke-width=\".15\"')\n            .replace(/data-contour=\"[^\"]*\"/,'data-contour=\"cap-occluded-source-leading-edge-and-tip\"'))\n    }\n    var result=source\n    for(var j=0;j<leaves.length;j++)result=result.replace(leaves[j],patches[j])\n    return result.replace(hubs[0],hubs[0].replace(/stroke-width=\"[^\"]*\"/,'stroke-width=\".16\"'))\n}\n";

const fan=load('HardwareFanDesigns.js'),notebook=load('HardwareNotebook.js'),board=load('HardwareBoardDesigns.js');
const catalog={...load('HardwareModelNvidia042.js').records(),...load('HardwareModelRadeonArc042.js').records()};
const templates=new Map(),covered=[],skipped=[];let rotorCount=0,leafCount=0,maxError=0;
for(const id of Object.keys(catalog).sort()){
 const row=catalog[id],front=row.fan_ref.front_count,hit=[];
 if(!Number.isInteger(front)||front<1||front>3)continue;
 const state={kind:'gpu',model_id:id,series_id:row.series_id,board_vendor:row.series_id.split('_')[0],
  fan_count:front,style:'gpu_axial',icon_set:'notebook_line',model_mode:true,ink:'#1f242b'};
 const colors=board.colors(state,{});
 for(let index=0;index<front;index++){
  const p=notebook.fanProfile(state,colors,index,'axial');
  if(!Number.isInteger(p.blades)||p.blades<11||p.blades>64||['neutral','radial'].includes(p.shape))continue;
  const ink=notebook.rotorInk(fan.modelRotor(p),{ink:'#1f242b'}),hubs=ink.match(/<circle\b[^>]*class="hardware-fan-hub"[^>]*\/>/g)||[];
  if(hubs.length!==1){skipped.push({id,index,reason:'not_one_actual_round_cap'});continue;}
  const cap=Number(attributes(hubs[0]).r),leaves=ink.match(/<path\b[^>]*class="hardware-fan-blade"[^>]*\/>/g)||[];
  if(leaves.length!==p.blades)throw Error('Known source leaf count mismatch:'+id+index);
  const local=[];
  for(const leaf of leaves){
   const d=attributes(leaf).d,trim=clip(d,cap,.15);if(!trim||!trim.d)throw Error('Unsupported dense path;extend explicit compiler/fallback audit:'+id+index);
   maxError=Math.max(maxError,trim.max_curve_error);
   for(const k of trim.kept)for(let t=0;t<=128;t++){const xy=point(k.points,t/128);if(Math.hypot(...xy)<trim.clip_radius-1e-7)throw Error('Ink crosses cap');}
   const key=String(cap)+'|'+d;
   if(templates.has(key)&&templates.get(key)!==trim.d)throw Error('Nonunique source template key');
   local.push([key,trim.d]);
  }
  for(const [key,trim]of local)templates.set(key,trim);
  rotorCount++;leafCount+=p.blades;hit.push({source_index:index,blades:p.blades,hub_radius:cap});
 }
 if(hit.length)covered.push({id,rotors:hit});
}
const dependencies=['HardwareFanDesigns.js','HardwareFanProfileData.js','HardwareBoardProfileData.js','HardwareNotebook.js','HardwareModelNvidia042.js','HardwareModelRadeonArc042.js'];
const manifest={format:1,catalog_models:Object.keys(catalog).length,known_round_axial_models:covered.length,
 known_front_rotors:rotorCount,source_leaf_instances:leafCount,templates:templates.size,
 covered,skipped,cap_ink_policy:'original_circle_radius_plus_half_pen_and_1e-6',leaf_pen:.15,hub_pen:.16,
 generation_max_curve_error:maxError,positions_or_blade_counts_changed:false,
 source_sha256:Object.fromEntries(dependencies.map(file=>['native/'+file,crypto.createHash('sha256').update(fs.readFileSync(path.join(NATIVE,file))).digest('hex')]))};
const lines=[...templates.entries()].sort(([a],[b])=>a.localeCompare(b,'en'));
let text='.pragma library\n\n'+RUNTIME+'\nfunction template(radius,sourceLeadingPath) {\n    switch(String(radius)+"|"+sourceLeadingPath) {\n';
for(const [key,trim]of lines)text+='    case '+JSON.stringify(key)+':return '+JSON.stringify(trim)+';\n';
text+='    default:return null\n    }\n}\n\nfunction coverage() {return '+JSON.stringify(manifest)+'}\n';
const args=process.argv.slice(2),outputIndex=args.indexOf('--output'),reportIndex=args.indexOf('--report');
const destination=outputIndex>=0?path.resolve(args[outputIndex+1]):path.join(NATIVE,'HardwareDenseInk052.js');
if(args.includes('--check')){
 if(!fs.existsSync(destination)||fs.readFileSync(destination,'utf8')!==text)throw Error('Generated dense-ink table is stale');
}else fs.writeFileSync(destination,text,'utf8');
const result={...manifest,module_bytes:Buffer.byteLength(text),module_sha256:crypto.createHash('sha256').update(text).digest('hex'),runtime_root_solving:false,runtime_dynamic_cache:false};
if(reportIndex>=0)fs.writeFileSync(path.resolve(args[reportIndex+1]),JSON.stringify(result,null,2),'utf8');
console.log(JSON.stringify({status:args.includes('--check')?'current':'generated',templates:templates.size,
 covered_models:covered.length,known_front_rotors:rotorCount,source_leaves:leafCount,bytes:result.module_bytes,sha256:result.module_sha256}));
