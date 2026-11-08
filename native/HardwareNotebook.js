.pragma library
.import "HardwareSolid.js" as Solid
.import "HardwareSketch.js" as Sketch
.import "HardwareBoardDesigns.js" as Board
.import "HardwareFanDesigns.js" as Fans
.import "HardwareNotebookParts.js" as Parts

// Notebook pen studies. Only the reviewed exterior, a few trim strokes and
// source-backed open blade sweeps survive: this is not a wireframe repaint.
// The transparent retained SVG is built on identity/style changes only. There
// are no timers, filters, random numbers, sensor requests or runtime I/O here.
var cases = {
    "nvidia-founders-rtx5090-32g": {d:"M12 0H88Q100 0 100 14V86Q100 100 88 100H12Q0 100 0 86V14Q0 0 12 0Z",
        feature:"hardware-notebook-fe-xbrace",trim:[
            "M30 2H35L53 41L70 2H75L57 49L75 98H70L53 58L35 98H30L47 49Z",
            "M6 17Q6 6 15 6H28M75 6H85Q94 6 94 17M6 83Q6 94 15 94H28M75 94H85Q94 94 94 83"]},
    "asus-astral-5090": {d:"M5 6Q44 2 91 5L99 17Q97 50 99 83L91 96Q45 99 6 94L1 82Q3 45 1 17Z",trim:["M12 12Q45 10 88 12","M7 83Q46 88 92 84","M9 22L9 75M92 24L92 74"]},
    "asus-dual-4060-oc": {d:"M13 5Q47 2 87 6Q98 9 98 24L96 82Q94 96 83 94L14 97Q3 94 3 78L4 24Z",trim:["M7 27L24 8","M77 89L93 72","M39 9L48 17"]},
    "msi-suprim-x-4090-24g": {d:"M11 3L88 5L99 24L94 86L82 98Q44 96 11 98L2 79L2 21Z",trim:["M14 12L36 10M65 11L85 13","M8 24L17 13M86 14L94 29","M18 87Q45 91 79 88"]},
    "zotac-solo-4060": {d:"M20 5Q52 2 79 6Q98 9 98 29L94 78Q90 97 76 96L19 95Q3 91 4 76L6 27Q6 9 20 5Z",trim:["M15 18Q40 12 67 16","M72 84L85 75"]},
    "nvidia-gtx1080-founders": {d:"M6 4L81 6L98 26L97 76L86 97L5 95L1 77L3 20Z",trim:["M12 16L46 13L57 30L55 77L12 84Z","M16 34Q30 32 46 35M16 45L45 46M17 57L45 57M16 69L46 70","M59 13L77 10"]},
    "amd-reference-rx7900xtx-24g": {d:"M11 3L90 6L97 21L98 83L89 97L9 95L2 79L3 21Z",trim:["M10 14L35 10M68 11L91 17","M9 83L19 90M81 91L93 81","M43 7L50 13L57 7"]},
    "intel-limited-arc-a770-16g": {d:"M16 6Q50 3 84 7Q98 9 98 24L96 79Q93 95 80 95L17 93Q3 92 3 76L4 25Q4 10 16 6Z",trim:["M17 13Q46 9 80 13","M16 86Q49 91 82 87"]},
    "sapphire-pulse-rx7900xt-20g": {d:"M6 7Q45 3 93 8L97 21L96 84Q91 98 82 94L7 96L2 80L3 24Z",trim:["M12 17L35 12L40 19","M61 85L78 91L91 83","M7 27L14 21M85 16L94 28"]}
}
function n(value) {return Sketch.number(value)}
function identity(state) {return String(state.model_id||state.series_id||state.style||"gpu")}
function ink(state) {return Sketch.hex(state && state.ink,"#46535b")}
function colored(state) {return state.icon_set!=="notebook_line"}
function colorWashEnabled(state) {return state.icon_set==="notebook_color" && state.notebookColorWash!==false}
function geometry(state) {return Solid.geometry(state)}
function cpuModelKey(input) {return Parts.cpuModelKey(input)}
function path(d,color,width,opacity,extra) {
    return '<path d="'+d+'" fill="none" stroke="'+color+'" stroke-width="'+n(width)+'"'
        +(opacity===undefined?'':' opacity="'+opacity+'"')+(extra?' '+extra:'')+'/>'
}
function circle(x,y,r,color,width,extra) {
    return '<circle cx="'+n(x)+'" cy="'+n(y)+'" r="'+n(r)+'" fill="none" stroke="'+color+'" stroke-width="'+width+'"'+(extra?' '+extra:'')+'/>'
}
function group(value,transform) {return '<g'+(transform?' transform="'+transform+'"':'')+'>'+value+'</g>'}
function matrix(a,b) {
    return [a[0]*b[0]+a[2]*b[1],a[1]*b[0]+a[3]*b[1],a[0]*b[2]+a[2]*b[3],a[1]*b[2]+a[3]*b[3],
        a[0]*b[4]+a[2]*b[5]+a[4],a[1]*b[4]+a[3]*b[5]+a[5]]
}
function transformMatrix(text) {
    var out=[1,0,0,1,0,0]
    String(text||"").replace(/(translate|scale|matrix)\(([^)]+)\)/g,function(all,kind,values){
        var v=values.trim().split(/[ ,]+/).map(Number),m=[1,0,0,1,0,0]
        if(kind==="translate"){m[4]=v[0];m[5]=v.length>1?v[1]:0}
        else if(kind==="scale"){m[0]=v[0];m[3]=v.length>1?v[1]:v[0]}
        else if(v.length===6)m=v
        out=matrix(out,m);return all
    })
    return out
}
function matrixText(m) {return 'matrix('+m.map(n).join(' ')+')'}
function shapePath(type,a) {
    if(type==="path")return a.d||""
    if(type==="rect")return Sketch.rectPath(a)
    if(type==="polygon" || type==="polyline")return "M"+a.points+(type==="polygon"?"Z":"")
    if(type==="line")return "M"+a.x1+" "+a.y1+"L"+a.x2+" "+a.y2
    return ""
}
function sourceShapes(input) {
    var source=String(input).replace(/<defs\b[^>]*>[\s\S]*?<\/defs>/g,""),out=[],stack=[[1,0,0,1,0,0]]
    var tags=source.match(/<g\b[^>]*>|<\/g>|<(?:path|rect|circle|ellipse|line|polyline|polygon)\b[^>]*\/>/g)||[]
    for(var i=0;i<tags.length;i++) {
        var tag=tags[i]
        if(tag==="</g>"){if(stack.length>1)stack.pop();continue}
        var a=Sketch.attributes(tag),m=matrix(stack[stack.length-1],transformMatrix(a.transform))
        if(/^<g\b/.test(tag)){stack.push(m);continue}
        var type=/^<(\w+)/.exec(tag)[1],d=shapePath(type,a)
        if(d)out.push({d:d,m:m,a:a,type:type})
    }
    return out
}
function shapeStudy(state,g,c,front,layout) {
    var custom=cases[state.model_id],m=[g.w/100,0,0,g.h/100,g.x,g.y],seed=identity(state)
    if(custom) {
        var trims="",globalTrims=""
        custom.trim.forEach(function(d,index){
            var loose=Sketch.wobblyPath(d,seed+":trim:"+index,1.05,14)
            if(custom.feature && index===0 && layout) {
                // The FE brace sits behind the circular apertures. Bake its
                // intersections now; Qt's SVG-Tiny cannot clip it at paint.
                var points=casePolygon({d:loose,m:m})
                if(points.length)points.push(points[0])
                var region=[[g.x,g.y],[g.x+g.w,g.y],[g.x+g.w,g.y+g.h],[g.x,g.y+g.h]]
                globalTrims+=path(clippedStroke(points,region,layout,.18),c.ink,.18)
            } else trims+=path(loose,c.ink,1.0)
        })
        return {d:Sketch.wobblyPath(custom.d,seed+":case",1.75,15),m:m,
            trim:custom.feature?'<g class="'+custom.feature+'">'+globalTrims+group(trims,matrixText(m))+'</g>':group(trims,matrixText(m)),custom:true}
    }
    var shapes=sourceShapes(front),passive=state.series_id==="gigabyte_silent_pascal" && state.fan_count===0
    if(state.series_id==="msi_hd5450_passive" && state.fan_count===0) {
        // This cooler projects above/below its exposed low-profile PCB. Keep
        // both real regions, rather than mistaking the PCB for a fan shroud.
        return {d:Sketch.wobblyPath("M0 17H31V6H99V91H31V84H0Z",seed+":passive",1.2,15),m:m,
            trim:group(path("M31 18Q31.4 50 31 82",c.ink,.9),matrixText(m)),passive:true,finRange:[.40,.92]}
    }
    // This exact model front starts with a recessed dark rectangle; the next
    // shape is the actual raised metal shroud. Only the large model view opts
    // into the corrected cover; the retained small top-bar artwork stays exact.
    var mainIndex=passive || state.model_mode===true && state.series_id==='msi_twin_frozr_hd7970'?1:0
    var main=shapes[mainIndex]
    if(state.model_mode===true && state.series_id==='yeston_sakura') {
        // Source GroupC shapes0..4 together reach every outer edge: the two
        // crossing ribbons/corner panels extend beyond shape0's chamfers.
        // Their union has this perimeter; keep the real extensions attached
        // instead of leaving ribbon ink floating outside an undersized case.
        main={d:'M0 4H100V98H0Z',m:m}
    }
    if(!main)main={d:Sketch.rectPath({x:g.x,y:g.y,width:g.w,height:g.h,rx:.6}),m:[1,0,0,1,0,0]}
    var scale=Math.sqrt(Math.abs(main.m[0]*main.m[3]-main.m[1]*main.m[2]))||1
    var trims="",kept=0
    // Two short pen excerpts preserve the reviewed cover's panel language.
    // Repeated fan bays, whole filled panels and dense heatsink meshes stay out.
    for(var i=passive?shapes.length:mainIndex+1;i<Math.min(shapes.length,14) && kept<2;i++) {
        var row=shapes[i],commands=row.d.match(/[A-Za-z][^A-Za-z]*/g)||[]
        if(row.a.opacity!==undefined && Number(row.a.opacity)<.70)continue
        if(commands.length<2 || commands.length>12 || /[Aa]/.test(row.d))continue
        if(row.type==="rect") {
            var w=Number(row.a.width),h=Number(row.a.height)
            if(!(w/h>3.5 || h/w>3.5) || Math.max(w,h)*Math.sqrt(Math.abs(row.m[0]*row.m[3]))<2.8)continue
            var x=Number(row.a.x||0),y=Number(row.a.y||0)
            row.d=w>h?'M'+x+' '+(y+h/2)+'H'+(x+w):'M'+(x+w/2)+' '+y+'V'+(y+h)
        } else row.d=commands.slice(0,Math.min(3,commands.length)).join("").replace(/[Zz]/g,"")
        var localScale=Math.sqrt(Math.abs(row.m[0]*row.m[3]-row.m[1]*row.m[2]))||1
        trims+=group(path(Sketch.wobblyPath(row.d,seed+":detail:"+kept,.10/localScale,2/localScale),c.ink,.14/localScale),matrixText(row.m))
        kept++
    }
    if(!trims && !passive)trims=Sketch.caseFeature(state,g,c,front)
    if(passive && shapes[0])trims=group(path(shapes[0].d,c.ink,.15/scale),matrixText(shapes[0].m))
    return {d:Sketch.wobblyPath(main.d,seed+":case",.22/scale,2.2/scale),m:main.m,trim:trims,passive:passive}
}
function fanLayout(state,g) {
    var out=[],cy=g.y+g.h*.51
    if(state.style==="gpu_blower" && state.fan_count===1)
        return [{cx:g.centers.length?g.centers[0]:g.x+g.w-4.5,cy:cy,radius:Math.min(3.55,g.h*.37),kind:"blower"}]
    g.centers.forEach(function(cx,index){out.push({cx:cx,cy:g.fan_y?g.fan_y[index]:cy,radius:g.radii?g.radii[index]:g.radius,
        kind:g.blowers && g.blowers.indexOf(index)>=0?"blower":"axial"})})
    return out
}
function fanProfile(state,c,index,kind) {
    var p=Fans.profile(state.series_id,index,kind)
    if(c.fanOverrides) {
        Object.keys(c.fanOverrides).forEach(function(key){if(key!=="fans")p[key]=c.fanOverrides[key]})
        var fan=c.fanOverrides.fans && c.fanOverrides.fans[index]
        if(fan)Object.keys(fan).forEach(function(key){p[key]=fan[key]})
        p=Fans.normalized(p,state.series_id,index,kind)
    }
    return p
}
function rotorInk(source,c) {
    var text=String(source).replace(/<defs\b[^>]*>[\s\S]*?<\/defs>/g,""),out="",depth=0
    var tags=text.match(/<g\b[^>]*>|<\/g>|<(?:path|circle)\b[^>]*\/>/g)||[]
    for(var i=0;i<tags.length;i++) {
        var tag=tags[i]
        if(tag==="</g>"){if(depth>0){out+="</g>";depth--}continue}
        var a=Sketch.attributes(tag)
        if(/^<g\b/.test(tag)){out+='<g'+(a.transform?' transform="'+a.transform+'"':'')+'>';depth++;continue}
        var cls=a["class"]||"",type=/^<(\w+)/.exec(tag)[1]
        var link=type==="path" && !cls && String(a.d).indexOf("A2.55 2.55")>=0
        var ring=type==="circle" && a.r==="2.62"
        var hubDetail=type==="circle" && !cls && a.r!=="2.25" && a.r!=="1.95"
        if(["hardware-fan-blade","hardware-fan-hub","hardware-fan-cap-mark"].indexOf(cls)<0 && !link && !ring && !hubDetail)continue
        var extra=(a.transform?'transform="'+a.transform+'" ':"")+'class="'+(link?'hardware-fan-tip-link':ring?'hardware-fan-tip-ring':cls||'hardware-fan-cap-ring')+'"'
        if(type==="path") {
            var d=a.d
            if(cls==="hardware-fan-blade") {
                // Colour follows the same reviewed closed leaf, never a
                // generic fan disk. Its open pen contour below stays exact.
                if(c.pencilColor===true && /[Zz]\s*$/.test(d))
                    out+='<path class="hardware-notebook-color-blade-wash" d="'+d+'"'
                        +(a.transform?' transform="'+a.transform+'"':'')+' fill="'+Sketch.hex(c.blade,'#9eb4be')
                        +'" fill-opacity=".62" stroke="none"/>'
                var commands=String(d).match(/[A-Za-z][^A-Za-z]*/g)||[]
                d=commands.slice(0,3).join("")
                extra+=' data-contour="open-source-leading-edge-and-tip"'
            }
            out+=path(d,c.ink,.18,undefined,extra)
        } else out+=circle(Number(a.cx||0),Number(a.cy||0),Number(a.r),c.ink,cls==="hardware-fan-hub"?.18:.15,extra)
    }
    while(depth-->0)out+="</g>"
    return out
}
function fanInk(state,c,layout,index,collector) {
    var p=fanProfile(state,c,index,layout.kind),rotorColors=c
    if(colorWashEnabled(state))rotorColors=Object.assign({},c,{pencilColor:true,blade:pencilBladeColor(p)})
    var moving=rotorInk(Fans.rotor(p,c),rotorColors)
    var out=circle(layout.cx,layout.cy,layout.radius,c.ink,.185,'class="hardware-notebook-fan-opening" data-fan-index="'+index+'"')
    var transform='translate('+layout.cx+' '+layout.cy+') scale('+(layout.radius/3)+')'
    // Unknown blades have a static opening/cap, never an invented vane count
    // or a spinning placeholder. Known directions use the shared RPM clock.
    if(Array.isArray(collector) && p.blades!==null && p.shape!=="neutral")
        collector.push({cx:layout.cx,cy:layout.cy,radius:layout.radius,kind:layout.kind,basis:3,body:moving,direction:p.direction,
            known:true,source_index:index})
    else out+=group(moving,transform)
    return out
}
function pencilBladeColor(profile) {
    return profile && profile.tone==="red"?'#c18e9a':profile && profile.tone==="light"?'#a2c6cc':'#81adbb'
}
function casePolygon(study) {
    // Bake clipping because Qt's SVG-Tiny renderer ignores SVG clipPath. The
    // reviewed outer curves are sampled once, never while a rotor is moving.
    var tokens=study.d.match(/[a-zA-Z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?/g)||[]
    var arities={M:2,L:2,H:1,V:1,Q:4,C:6,S:4,T:2,A:7},out=[],at=0,command="",current=[0,0],start=[0,0],previous="",control=[0,0]
    function push(p) {var m=study.m;out.push([m[0]*p[0]+m[2]*p[1]+m[4],m[1]*p[0]+m[3]*p[1]+m[5]])}
    while(at<tokens.length && out.length<512) {
        if(/^[a-zA-Z]$/.test(tokens[at]))command=tokens[at++]
        var upper=command.toUpperCase(),relative=command!==upper,arity=arities[upper]
        if(upper==="Z"){current=start.slice();previous=upper;command="";continue}
        if(!arity || at+arity>tokens.length)break
        var v=[]
        for(var j=0;j<arity;j++)v.push(Number(tokens[at++]))
        var old=current.slice(),end=upper==="H"?[(relative?old[0]:0)+v[0],old[1]]
            :upper==="V"?[old[0],(relative?old[1]:0)+v[0]]
            :[(relative?old[0]:0)+v[arity-2],(relative?old[1]:0)+v[arity-1]]
        if(upper==="M"){start=end.slice();push(end);command=relative?"l":"L"}
        else if(upper==="Q" || upper==="T" || upper==="C" || upper==="S") {
            var c1,c2
            if(upper==="T")c1=previous==="Q"||previous==="T"?[2*old[0]-control[0],2*old[1]-control[1]]:old.slice()
            else if(upper==="S")c1=previous==="C"||previous==="S"?[2*old[0]-control[0],2*old[1]-control[1]]:old.slice()
            else c1=[(relative?old[0]:0)+v[0],(relative?old[1]:0)+v[1]]
            var cubic=upper==="C" || upper==="S"
            if(cubic)c2=[(relative?old[0]:0)+v[arity-4],(relative?old[1]:0)+v[arity-3]]
            for(var step=1;step<=6;step++) {
                var t=step/6,u=1-t
                push(cubic?[u*u*u*old[0]+3*u*u*t*c1[0]+3*u*t*t*c2[0]+t*t*t*end[0],u*u*u*old[1]+3*u*u*t*c1[1]+3*u*t*t*c2[1]+t*t*t*end[1]]
                    :[u*u*old[0]+2*u*t*c1[0]+t*t*end[0],u*u*old[1]+2*u*t*c1[1]+t*t*end[1]])
            }
            control=(cubic?c2:c1).slice()
        } else push(end)
        current=end;previous=upper
    }
    return out
}
function inside(point,polygon) {
    var yes=false
    for(var i=0,j=polygon.length-1;i<polygon.length;j=i++) {
        var a=polygon[i],b=polygon[j]
        if((a[1]>point[1])!==(b[1]>point[1]) && point[0]<(b[0]-a[0])*(point[1]-a[1])/(b[1]-a[1])+a[0])yes=!yes
    }
    return yes
}
function clippedStroke(points,polygon,holes,width) {
    var out="",margin=width*.5+.012
    for(var at=1;at<points.length;at++) {
        var a=points[at-1],b=points[at],dx=b[0]-a[0],dy=b[1]-a[1],length2=dx*dx+dy*dy,cuts=[0,1]
        if(length2<.000001)continue
        function cut(t) {if(t>.000001 && t<.999999)cuts.push(t)}
        function circleCuts(cx,cy,r) {
            var ox=a[0]-cx,oy=a[1]-cy,B=2*(ox*dx+oy*dy),C=ox*ox+oy*oy-r*r,D=B*B-4*length2*C
            if(D>=0){var root=Math.sqrt(D);cut((-B-root)/(2*length2));cut((-B+root)/(2*length2))}
        }
        for(var i=0,j=polygon.length-1;i<polygon.length;j=i++) {
            var p=polygon[j],q=polygon[i],ex=q[0]-p[0],ey=q[1]-p[1],den=dx*ey-dy*ex,edgeLength=Math.sqrt(ex*ex+ey*ey)
            if(edgeLength<.000001)continue
            if(Math.abs(den)>.0000001) {
                // Offsets of the finite edge and circular vertex ends form a
                // conservative stroke-width inset of the exact case polygon.
                for(var side=-1;side<=1;side+=2) {
                    var px=p[0]-ey/edgeLength*margin*side,py=p[1]+ex/edgeLength*margin*side
                    var t=((px-a[0])*ey-(py-a[1])*ex)/den
                    var u=((px-a[0])*dy-(py-a[1])*dx)/den
                    if(u>=0 && u<=1)cut(t)
                }
                cut(((p[0]-a[0])*ey-(p[1]-a[1])*ex)/den)
            }
            circleCuts(p[0],p[1],margin)
        }
        holes.forEach(function(f){circleCuts(f.cx,f.cy,f.radius+margin)})
        cuts.sort(function(x,y){return x-y})
        for(var k=1;k<cuts.length;k++) {
            var low=cuts[k-1],high=cuts[k]
            if(high-low<.000001)continue
            var t=(low+high)/2,point=[a[0]+dx*t,a[1]+dy*t]
            if(!inside(point,polygon))continue
            var allowed=true
            for(var h=0;h<holes.length;h++)if(Math.pow(point[0]-holes[h].cx,2)+Math.pow(point[1]-holes[h].cy,2)<Math.pow(holes[h].radius+margin,2)){allowed=false;break}
            if(!allowed)continue
            for(var e=0,z=polygon.length-1;e<polygon.length;z=e++) {
                var v=polygon[z],w=polygon[e],vx=w[0]-v[0],vy=w[1]-v[1],l=vx*vx+vy*vy
                var projection=l?Math.max(0,Math.min(1,((point[0]-v[0])*vx+(point[1]-v[1])*vy)/l)):0
                if(Math.pow(point[0]-v[0]-projection*vx,2)+Math.pow(point[1]-v[1]-projection*vy,2)<margin*margin){allowed=false;break}
            }
            if(allowed)out+='M'+n(a[0]+dx*low)+' '+n(a[1]+dy*low)+'L'+n(a[0]+dx*high)+' '+n(a[1]+dy*high)
        }
    }
    return out
}
function pencilCurve(start,control,end,polygon,holes,width,color,opacity,extra) {
    var points=[start]
    for(var step=1;step<=3;step++) {
        var t=step/3,u=1-t
        points.push([u*u*start[0]+2*u*t*control[0]+t*t*end[0],u*u*start[1]+2*u*t*control[1]+t*t*end[1]])
    }
    var d=clippedStroke(points,polygon,holes,width)
    return d?path(d,color,width,opacity,extra):""
}
function pencil(state,g,c,study,layout) {
    if(!colored(state))return ""
    var polygon=casePolygon(study)
    var row=Board.profile(state),tones={dark:"#9ca8b0",light:"#c2cbd0",silver:"#a9b5bb",blue:"#91a9c5",pink:"#c7a8c2",
        mixed:"#abb8c0",gold:"#c3b181",copper:"#bc9274",red:"#c08e8e"}
    var strokes="",tone=row && tones[row.shroud_tone]?tones[row.shroud_tone]:"#9ca8af",mark=tone
    if(colorWashEnabled(state)) {
        // A quiet pencil underwash, clipped with the full stroke width to the
        // actual uneven cover AND every real fan opening. Parallel marks keep
        // paper gaps; no filled rectangle, SVG clipPath or invented RGB trim.
        var washes={dark:'#7ca8b7',light:'#a7cdd2',silver:'#94bdcc',blue:'#85adcc',pink:'#d0a4c8',
            mixed:'#84b4bd',gold:'#c8b478',copper:'#ca997e',red:'#d59e98'}
        var wash=row && washes[row.shroud_tone]?washes[row.shroud_tone]:'#aebfc5'
        for(var band=0;band<28;band++) {
            var at=g.y+g.h*(.055+band*.89/27),bow=(band%3-1)*.025
            strokes+=pencilCurve([g.x+.06,at],[g.x+g.w*.49,at+bow],[g.x+g.w-.06,at+.012],
                polygon,layout,g.h*.028,wash,.65,'class="hardware-notebook-color-wash" data-coloring="illustrative-pencil"')
        }
    }
    // Only reviewed retail red trim is coloured red; UI brand accents are not
    // a claim about a card's paint or live RGB lighting.
    if(state.series_id==="sapphire_pulse" || state.series_id==="amd_reference")mark="#b87f79"
    for(var i=0;i<7;i++) {
        var y=g.y+g.h*(.105+i*.025),left=g.x+g.w*(.10+(i%2)*.01),right=g.x+g.w*(.90-i*.006)
        strokes+=pencilCurve([left,y],[g.x+g.w*.46,y-.10],[right,y+.06],polygon,layout,.42,tone,.23)
    }
    for(var j=0;j<5;j++) {
        var bottom=g.y+g.h*(.85+j*.025)
        strokes+=pencilCurve([g.x+g.w*.12,bottom],[g.x+g.w*.5,bottom+.13],[g.x+g.w*(.87-j*.008),bottom-.04],polygon,layout,.39,tone,.22)
    }
    for(var k=0;k<23;k++) {
        var px=g.x+g.w*(.06+k*.039),py=g.y+g.h*(.08+(k%4)*.015)
        strokes+=pencilCurve([px,py],[px+.18-(k%3)*.09,py+g.h*.36],[px+.27-(k%4)*.075,py+g.h*(.74+(k%3)*.025)],polygon,layout,.42+(k%3)*.045,tone,.20)
    }
    var markY=g.y+g.h*.11
    strokes+=pencilCurve([g.x+g.w*.65,markY],[g.x+g.w*.73,markY+.03],[g.x+g.w*.82,markY+.06],polygon,layout,.33,mark,.40)
    return '<g class="hardware-notebook-pencil" data-clip="baked-case-and-fan-openings">'+strokes+'</g>'
}
function connector(state,g,c) {
    var row=Board.profile(state),bus=row && row.host_interface?row.host_interface.bus:"unknown"
    var start=g.x+g.w*.18,width=g.w*.27,length=row && row.dimensions_mm && row.dimensions_mm.length
    if(typeof length==="number" && length>0) {
        start=g.x+g.w*Math.min(.28,(bus==="agp"?28:45)/length)
        width=g.w*Math.max(.22,Math.min(.52,(bus==="agp"?62:82)/length))
    }
    var y=g.y+g.h-.10,d='M'+n(start)+' '+n(y)+'l'+n(width)+' .06-.07 .74q'+n(-width*.43)+' .16 '+n(-width)+' -.06Z'
    var out=path(Sketch.wobblyPath(d,identity(state)+":edge",.04,2),c.ink,.15)
    // A few contact strokes are schematic density, not an asserted pin count.
    for(var i=1;i<5;i++)out+=path('M'+n(start+width*i/5)+' '+n(y+.16)+'l.015 .39',c.ink,.09)
    return '<g class="hardware-notebook-edge" data-bus="'+bus+'">'+out+'</g>'
}
function expression(g,layout,c) {
    var top=g.h,bottom=g.h
    layout.forEach(function(f){top=Math.min(top,f.cy-f.radius-g.y);bottom=Math.min(bottom,g.y+g.h-f.cy-f.radius)})
    var gap=Math.max(top,bottom)
    if(gap<.80)return ""
    var scale=Math.min(.54,(gap-.24)/1.35),x=g.x+g.w*.5,y=top>=bottom?g.y+.13:g.y+g.h-gap+.12
    var face=circle(-.85,0,.13,c.ink,.13)+circle(.85,.04,.13,c.ink,.13)+path('M-.48 .46Q.02 .96 .51 .42',c.ink,.17)
    return '<g class="hardware-notebook-expression" transform="translate('+n(x)+' '+n(y)+') scale('+n(scale)+')">'+face+'</g>'
}
function integrated(state,c) {
    var seed=identity(state),d=Sketch.rectPath({x:5.5,y:5.5,width:13,height:13,rx:1.15})
    var study={d:Sketch.wobblyPath(d,seed,.22,3),m:[1,0,0,1,0,0]}
    var g={x:5.5,y:5.5,w:13,h:13},out=pencil(state,g,c,study,[])
    out+=path(study.d,c.ink,.40)+path(Sketch.wobblyPath(Sketch.rectPath({x:8,y:8,width:8,height:8,rx:.6}),seed+':die',.16,3),c.ink,.22)
    out+=path('M8.6 8.7Q12 8.5 15.2 8.7',c.ink,.13)
    if(state.icon_set==="notebook_smile")out+=group(circle(-.9,0,.16,c.ink,.13)+circle(.9,0,.16,c.ink,.13)+path('M-.5 .58Q0 1 .5 .58',c.ink,.15),'translate(12 11)')
    return '<g class="hardware-notebook-integrated">'+out+'</g>'
}
function gpu(state,collector) {
    var c=Board.colors(state,Solid.palette(state));c.ink=ink(state)
    if(state.style==="gpu_integrated")return integrated(state,c)
    var g=geometry(state),layout=fanLayout(state,g),front=cases[state.model_id]?"":Solid.front(state,g,c)
    var study=shapeStudy(state,g,c,front,layout),scale=Math.sqrt(Math.abs(study.m[0]*study.m[3]-study.m[1]*study.m[2]))||1
    var out=pencil(state,g,c,study,layout)
    out+=group(path(study.d,c.ink,.43/scale),matrixText(study.m))+study.trim
    if(study.passive) {
        var fins=""
        var positions=study.finRange?[study.finRange[0],(study.finRange[0]+study.finRange[1])/2,study.finRange[1]]:[.135,.525,.837]
        positions.forEach(function(at){var x=g.x+g.w*at;fins+='M'+n(x)+' '+n(g.y+g.h*(study.finRange ? .12 : .02))+'Q'+n(x+.09)+' '+n(g.y+g.h*.48)+' '+n(x-.04)+' '+n(g.y+g.h*.87)})
        out+='<g class="hardware-notebook-passive">'+path(fins,c.ink,.16)+'</g>'
    }
    out+=connector(state,g,c)
    var bracket='M'+n(g.x-.43)+' '+n(g.y-.25)+'l-.24 .09q.10 '+n(g.h*.5)+' -.02 '+n(g.h+.6)
    out+=path(bracket,c.ink,.22)
    layout.forEach(function(f,index){out+=fanInk(state,c,f,index,collector)})
    if(!layout.length && state.fan_count!==0)
        out+=path('M'+n(g.x+g.w*.15)+' '+n(g.y+g.h*.26)+'Q'+n(g.x+g.w*.4)+' '+n(g.y+g.h*.24)+' '+n(g.x+g.w*.66)+' '+n(g.y+g.h*.26),c.ink,.16)
    if(state.icon_set==="notebook_smile")out+=expression(g,layout,c)
    // Casing ink wobbles locally; fan apertures remain true circles and rotor
    // coordinates share the exact fixed view so zero-degree layers reassemble.
    return out
}
function body(state,collector) {
    if(!state || ["cpu","gpu","memory"].indexOf(state.kind)<0)return ""
    if(state.kind!=="gpu")return Parts.body(state,collector)
    return '<g class="hardware-notebook '+state.icon_set+'" stroke-linecap="round" stroke-linejoin="round">'+gpu(state,collector)+'</g>'
}
function generic(kind,color,moving,style,colorWash) {
    if(kind==="gpu")return body({kind:"gpu",style:"gpu_neutral",fan_count:-1,ink:color,icon_set:style||"notebook_line",notebookColorWash:colorWash})
    return Parts.generic(kind,color,moving,style)
}
