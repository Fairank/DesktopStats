.pragma library
.import "HardwareCpuPackages.js" as Cpu

// Original retained desktop-model artwork: PolyForm Noncommercial 1.0.0.
// Contours/proportions come ONLY from the existing reviewed Cpu profile/paths.
// Bevel depth, metal finish, engraving placement and pen strokes are original
// visual references, not measured CAD, exact printing or an electrical map.
// No backside contacts, SMD count/layout, attached cooler, timer, cache or I/O.

var styles = ["miniature","cartoon","notebook_color","notebook_line","sticker",
    "papercut","inkwash","classic","outline","solid","soft","sketch","notebook_smile"]

function n(value) { return String(Number(Number(value).toFixed(4))) }
function hex(value,fallback) { return Cpu.hex(value,fallback) }
function hash(text) {
    var value=2166136261
    for(var i=0;i<text.length;i++)value=Math.imul(value^text.charCodeAt(i),16777619)
    return value>>>0
}
function penPath(input,seed,amount) {
    // Cpu.paths emits a bounded polygon. Shared endpoints preserve all actual
    // notches; only long edges get a gentle deterministic quadratic pen bow.
    var values=input.match(/[-+]?(?:\d*\.\d+|\d+\.?)/g)||[],points=[]
    for(var i=0;i+1<values.length;i+=2)points.push([Number(values[i]),Number(values[i+1])])
    if(points.length<3 || points.length>64)return input
    var out="M"+n(points[0][0])+" "+n(points[0][1])
    for(var j=1;j<=points.length;j++) {
        var a=points[j-1],b=points[j%points.length],dx=b[0]-a[0],dy=b[1]-a[1]
        var length=Math.sqrt(dx*dx+dy*dy),bow=((hash(seed+":"+j)%2001)/1000-1)*amount
        out+=(length>2.2?"Q"+n((a[0]+b[0])/2-dy/length*bow)+" "+n((a[1]+b[1])/2+dx/length*bow)+" ":"L")
            +n(b[0])+" "+n(b[1])
    }
    return out+"Z"
}
function paint(style,ink) {
    var brightness=.2126*parseInt(ink.slice(1,3),16)+.7152*parseInt(ink.slice(3,5),16)+.0722*parseInt(ink.slice(5,7),16)
    var c={pcb:"#47796a",pcbSide:"#2c5149",lid:"#d5dfe3",low:"#9aaeb8",light:"#f4f7f8",
        edge:"#4c646d",mark:"#3b505b",carrier:"#ca844b",width:.13,hand:false,line:false,gradient:true,paper:brightness>145?"#202a34":"#fffdf6"}
    if(style==="solid") {c.pcb="#365d58";c.lid="#a9bbc6";c.light="#c8d7de";c.low="#718b9b";c.gradient=false;c.width=.11}
    if(style==="soft") {c.pcb="#b2c7bd";c.pcbSide="#819d95";c.lid="#eff1e6";c.light="#fcfcf5";c.low="#ccd8cc";c.edge="#82988f";c.width=.105}
    if(style==="cartoon") {c.pcb="#a4c6bb";c.pcbSide="#71998c";c.lid="#f1e9d8";c.light="#fff8ec";c.low="#d3cabb";c.edge="#56757a";c.mark="#50636e";c.width=.22}
    if(style==="sticker") {c.pcb="#adc6b8";c.lid="#f5e6cc";c.light="#fff6df";c.low="#d6c7ac";c.edge="#466267";c.width=.23}
    if(style==="papercut") {c.pcb="#356477";c.pcbSide="#24495d";c.lid="#f0dfbc";c.light="#fbefd4";c.low="#c9b78d";c.mark="#34515e";c.edge="#34515e";c.gradient=false;c.width=.08}
    if(style==="notebook_color" || style==="notebook_smile") {c.pcb="#adc2ae";c.pcbSide="#7f9a88";c.lid="#e8e6d1";c.light="#f8f4e4";c.low="#bfc5af";c.edge="#485c61";c.gradient=false;c.hand=true;c.width=.17}
    if(style==="inkwash") {c.pcb="#82a6b4";c.pcbSide="#517784";c.lid="#c7dae0";c.light="#e6eff0";c.low="#94b3c2";c.edge="#3f6178";c.mark="#3f6178";c.gradient=false;c.hand=true;c.width=.145}
    if(style==="notebook_line" || style==="sketch" || style==="classic" || style==="outline") {
        c.line=true;c.gradient=false;c.pcb=c.paper;c.lid=c.paper;c.light=c.paper;c.low=c.paper
        c.edge=ink;c.mark=ink;c.pcbSide=c.paper;c.carrier=c.paper
        c.hand=style==="notebook_line" || style==="sketch"
        c.width=style==="classic"?.215:style==="outline"?.155:style==="sketch"?.14:.17
    }
    return c
}
function path(d,fill,stroke,width,extra) {
    return '<path d="'+d+'" fill="'+fill+'" stroke="'+stroke+'" stroke-width="'+n(width)+'"'+(extra?' '+extra:'')+'/>'
}
function scaled(value) {return 'translate(12 12) scale('+n(value)+') translate(-12 -12)'}

function familyMark(value) {
    // Read the supplied SKU label; never infer a CPU family from live load,
    // a socket, an abbreviated number or another processor's identity.
    var text=Cpu.label(value),match
    if((match=/^INTEL CORE ULTRA ([579]) /.exec(text)))return "CORE ULTRA "+match[1]
    if((match=/^INTEL CORE (I[3579])(?:-| )/.exec(text)))return "CORE "+match[1]
    if(/^INTEL PENTIUM /.test(text))return "PENTIUM"
    if(/^INTEL CELERON /.test(text))return "CELERON"
    if((match=/^AMD RYZEN ([3579]) /.exec(text)))return "RYZEN "+match[1]
    if(/^AMD THREADRIPPER PRO /.test(text))return "THREADRIPPER PRO"
    if(/^AMD THREADRIPPER /.test(text))return "THREADRIPPER"
    if(/^AMD ATHLON /.test(text))return "ATHLON"
    return ""
}

function lidInsetPoints(descriptor,amount) {
    // Parallel visual bevel inside the existing reviewed lid polygon. Scaling
    // around its centre distorts AM5's inward notches. This is original finish
    // artwork, not an additional measured IHS contour or manufacturing depth.
    var p=descriptor && Cpu.profile(descriptor.id)
    if(!p || !Number.isFinite(amount) || amount<=0 || amount>.25)return []
    var factor=18/Math.max(p.reference_size[0],p.reference_size[1])
    var points=p.lid.map(function(v){return [12+(v[0]-.5)*p.reference_size[0]*factor,
        12+(v[1]-.5)*p.reference_size[1]*factor]})
    var area=0,result=[],count=points.length
    for(var at=0;at<count;at++)area+=points[at][0]*points[(at+1)%count][1]-points[(at+1)%count][0]*points[at][1]
    if(!Number.isFinite(area) || area===0)return []
    var direction=area>0?1:-1
    for(var index=0;index<count;index++) {
        var previous=points[(index+count-1)%count],point=points[index],next=points[(index+1)%count]
        var ax=point[0]-previous[0],ay=point[1]-previous[1],bx=next[0]-point[0],by=next[1]-point[1]
        var al=Math.hypot(ax,ay),bl=Math.hypot(bx,by)
        if(!(al>0 && bl>0))return []
        ax/=al;ay/=al;bx/=bl;by/=bl
        var first=[point[0]-direction*ay*amount,point[1]+direction*ax*amount]
        var second=[point[0]-direction*by*amount,point[1]+direction*bx*amount]
        var cross=ax*by-ay*bx
        if(Math.abs(cross)<1e-10)return []
        var t=((second[0]-first[0])*by-(second[1]-first[1])*bx)/cross
        var inset=[first[0]+t*ax,first[1]+t*ay]
        if(!Number.isFinite(inset[0]) || !Number.isFinite(inset[1])
                || Math.hypot(inset[0]-point[0],inset[1]-point[1])>amount*3)return []
        result.push(inset)
    }
    return result
}

function lidInset(descriptor,amount) {
    var points=lidInsetPoints(descriptor,amount)
    return points.length?points.map(function(point,index){return (index?"L":"M")+n(point[0])+" "+n(point[1])}).join("")+"Z":""
}

function engravingText(id,css,text,y,size,widthScale,weight,tracking) {
    // Lay out glyphs at a usable font size, then scale the vector text into
    // the 24-unit drawing. A 1px font can have bounds but empty hinted glyphs.
    var factor=size/16
    return '<text id="'+id+'"'+(css?' class="'+css+'"':'')+' x="0" y="0" font-size="16"'
        +' transform="translate(12 '+n(y)+') scale('+n(factor*widthScale)+' '+n(factor)+')"'
        +' font-weight="'+weight+'" letter-spacing="'+n(tracking/factor)+'">'+text+'</text>'
}

function modelBody(state) {
    var descriptor=state && state.cpu_package,p=descriptor && Cpu.profile(descriptor.id)
    if(!p || descriptor.vendor!==p.vendor)return ""
    var shapes=Cpu.paths(descriptor),style=styles.indexOf(state.icon_set)>=0?state.icon_set:"miniature"
    var ink=hex(state.ink,"#425564"),c=paint(style,ink)
    var label=Cpu.label(descriptor.label_ascii),mark=label?label.split(' ').pop():"",family=familyMark(label)
    var brand=p.vendor==="intel"?"INTEL":"AMD"
    var scale=18/Math.max(p.reference_size[0],p.reference_size[1]),w=p.reference_size[0]*scale,h=p.reference_size[1]*scale
    var seed=p.id+":"+style,packagePath=shapes.package.d,lidPath=shapes.lid.d
    var out='<g class="hardware-cpu-model" data-package="'+p.id+'" data-detail-status="original-reference"'
        +' data-view="top" data-package-outline="'+packagePath+'" data-lid-outline="'+lidPath+'"'
        +' stroke-linejoin="round" stroke-linecap="round">'
    if(c.gradient)out+='<defs><linearGradient id="cpuModelMetal" x1="0" y1="0" x2=".82" y2="1">'
        +'<stop offset="0" stop-color="'+c.light+'"/><stop offset=".44" stop-color="'+c.lid+'"/>'
        +'<stop offset=".76" stop-color="'+c.light+'"/><stop offset="1" stop-color="'+c.low+'"/></linearGradient></defs>'
    if(style==="sticker")out+=path(packagePath,"none","#fffdf5",.9,'class="cpu-model-sticker-rim"')
    if(p.carrier)out+='<g class="cpu-model-carrier-reference" transform="'+scaled(1.06)+'">'
        +path(packagePath,c.carrier,c.edge,c.width)+'</g>'
    // A modest visual rim supplies depth without inventing electrical legs.
    out+='<g class="cpu-model-substrate-edge-reference" transform="translate(0 .34)">'
        +path(packagePath,c.pcbSide,c.edge,c.width)+'</g>'
    out+=path(packagePath,c.pcb,c.hand?'none':c.edge,c.width,'class="cpu-model-package-outline"')
    out+='<g class="cpu-model-substrate-inset" transform="'+scaled(.963)+'">'
        +path(c.hand?penPath(packagePath,seed+":inset",.16):packagePath,"none",c.line?c.edge:c.light,c.width*.65,'opacity="'+(c.hand?'.32':'.5')+'"')+'</g>'
    out+='<g class="cpu-model-lid-lip-reference" transform="translate(0 .17)">'
        +path(lidPath,c.line?c.paper:c.low,c.edge,c.width*.75)+'</g>'
    out+=path(lidPath,c.gradient?'url(#cpuModelMetal)':c.lid,c.hand?'none':c.edge,c.width,'class="cpu-model-lid-outline"')
    var bevel=lidInset(descriptor,.14)
    if(bevel)out+='<g class="cpu-model-metal-bevel-reference" data-bevel="parallel-reference">'
        +path(c.hand?penPath(bevel,seed+":bevel",.14):bevel,"none",c.line?c.edge:c.light,c.width*.72,'opacity="'+(c.line?'.34':'.88')+'"')+'</g>'
    if(c.hand) {
        out+=path(penPath(packagePath,seed+":pcb",style==='sketch'?.34:.25),"none",c.edge,c.width,'class="cpu-model-hand-contour"')
            +path(penPath(lidPath,seed+":lid",style==='sketch'?.30:.22),"none",c.edge,c.width,'class="cpu-model-hand-contour"')
        if(style!=="inkwash")out+='<g transform="translate(.045 -.025)">'
            +path(penPath(lidPath,seed+":retrace",.06),"none",c.edge,.055,'class="cpu-model-pencil-retrace" opacity=".38"')+'</g>'
    }
    // Sparse finish strokes, deliberately no plausible SMD array or fake serial.
    var finish="M"+n(12-w*.22)+" "+n(12+h*.25)+"l"+n(w*.12)+" -.035m.22 .29l"+n(w*.13)+" -.025"
    if(c.hand)finish="M"+n(12-w*.23)+" "+n(12+h*.27)+"l.40 -.48m.16 .55l.48 -.56m.14 .59l.43 -.51"
    if(style==="papercut")finish="M"+n(12-w*.20)+" "+n(12+h*.27)+"h"+n(w*.40)
    out+=path(finish,"none",c.line?c.edge:c.mark,c.hand?.105:.07,'class="cpu-model-finish-reference" opacity="'+(c.line?'.45':'.24')+'"')
    if(style==="inkwash")out+=path("M"+n(12-w*.24)+" "+n(12+h*.15)+"q"+n(w*.23)+" .18 "+n(w*.45)+" -.08",
        "none",c.edge,.65,'class="cpu-model-ink-wash" opacity=".065"')
    var indexX=12-w/2+.32,indexY=12+h/2-.32
    out+=path("M"+n(indexX)+" "+n(indexY)+"h.75v-.75Z",c.line?c.edge:"#d1b672","none",0,'class="cpu-model-index-reference"')
    if(mark) {
        var fontSize=Math.min(1.65,w*.61/Math.max(4,mark.length)*1.6)
        out+='<g class="cpu-model-engraving-reference" text-anchor="middle" fill="'+c.mark+'" font-family="Segoe UI,Arial,sans-serif">'
            +engravingText('cpu-model-vendor','',brand,family?9.25:9.8,1.03,1,500,.18)
        if(family) {
            // QtSvg can quantize sub-unit fonts to a whole pixel. Keep a clear
            // 1-unit face and fit long family names inside this actual lid.
            var lidLow=1,lidHigh=0
            for(var position=0;position<p.lid.length;position++) {
                lidLow=Math.min(lidLow,p.lid[position][0]);lidHigh=Math.max(lidHigh,p.lid[position][0])
            }
            var familyScale=Math.min(1,((lidHigh-lidLow)*w-.8)/(family.length*.79))
            out+=engravingText('cpu-model-family','cpu-model-family-reference',family,10.8,1,familyScale,400,.04)
        }
        out+=engravingText('cpu-model-sku','',mark,family?12.6:12.15,fontSize,1,600,0)+'</g>'
    }
    if(style==="cartoon" || style==="notebook_smile")out+='<g class="cpu-model-cute-face" fill="none" stroke="'+c.edge+'" stroke-width=".20">'
        +'<path d="M10.9 13.75v.32M13.1 13.75v.32M11.1 14.55Q12 15.2 12.9 14.55"/></g>'
    return out+'</g>'
}
