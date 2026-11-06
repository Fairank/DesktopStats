.pragma library
.import "HardwareSolid.js" as Solid
.import "HardwareMemoryShapes.js" as Memory
.import "HardwareBoardDesigns.js" as Board
.import "HardwareFanDesigns.js" as Fans
.import "IconData.js" as Icons

// Hand-drawn ink, not another painted object style. The reviewed cover paths,
// memory key and fan contours are shared; only long fixed casing strokes bend
// slightly. The bend is deterministic and computed when retained art is built.
// No animation, random generator, filter, network resource or sensor access.

function hex(value,fallback) {
    return typeof value==="string" && /^#[0-9a-fA-F]{6}$/.test(value)?value.toLowerCase():fallback
}
function number(value) { return Number(Number(value).toFixed(4)) }
function hash(value) {
    var result=2166136261
    for(var i=0;i<value.length;i++)result=Math.imul(result^value.charCodeAt(i),16777619)
    return result>>>0
}
function palette(state) {
    var ink=hex(state && state.ink,"#364953")
    var brightness=.2126*parseInt(ink.substr(1,2),16)+.7152*parseInt(ink.substr(3,2),16)+.0722*parseInt(ink.substr(5,2),16)
    return {ink:ink,paper:brightness>140?"#202833":"#fffef9",accent:hex(state && state.accent,ink)}
}
function attributes(text) {
    var result={}
    text.replace(/([a-zA-Z_:][\w:.-]*)\s*=\s*"([^"]*)"/g,function(all,name,value){result[name]=value;return all})
    return result
}
function scaleOf(transform) {
    var result=1
    String(transform||"").replace(/scale\(\s*([-+\d.eE]+)(?:[ ,]+([-+\d.eE]+))?\s*\)/g,function(all,x,y){
        result*=Math.sqrt(Math.abs(Number(x)*(y===undefined?Number(x):Number(y))))
        return all
    })
    return result>0 && Number.isFinite(result)?result:1
}
function identity(state) { return String(state.model_id||state.series_id||state.style||state.kind||"hardware") }
function arcLine(start,end,seed,index,amplitude) {
    var dx=end[0]-start[0],dy=end[1]-start[1],length=Math.sqrt(dx*dx+dy*dy)
    if(!(length>0))return "L"+number(end[0])+" "+number(end[1])
    var bow=((hash(seed+":"+index)%2001)/1000-1)*amplitude
    return "Q"+number((start[0]+end[0])/2-dy/length*bow)+" "+number((start[1]+end[1])/2+dx/length*bow)
        +" "+number(end[0])+" "+number(end[1])
}
function wobblyPath(input,seed,amplitude,minLength) {
    // Parse command arity: never perturb arc flags, radii or an existing curve.
    // Only long L/H/V segments gain one shallow quadratic control point.
    var tokens=String(input).match(/[a-zA-Z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?/g)
    if(!tokens || tokens.length>4096)return input
    var count={M:2,L:2,H:1,V:1,C:6,S:4,Q:4,T:2,A:7},out="",at=0,command="",current=[0,0],start=[0,0],segment=0
    while(at<tokens.length) {
        if(/^[a-zA-Z]$/.test(tokens[at]))command=tokens[at++]
        if(!command)return input
        var upper=command.toUpperCase(),relative=command!==upper
        if(upper==="Z") {out+="Z";current=start.slice();command="";continue}
        var arity=count[upper]
        if(!arity || at+arity>tokens.length)return input
        var values=[]
        for(var i=0;i<arity;i++) {
            if(/^[a-zA-Z]$/.test(tokens[at]))return input
            var value=Number(tokens[at++]);if(!Number.isFinite(value))return input
            values.push(value)
        }
        var end=current.slice()
        if(upper==="H")end[0]=(relative?current[0]:0)+values[0]
        else if(upper==="V")end[1]=(relative?current[1]:0)+values[0]
        else {end=[(relative?current[0]:0)+values[arity-2],(relative?current[1]:0)+values[arity-1]]}
        if(upper==="M") {
            out+=command+values.join(" ");start=end.slice();command=relative?"l":"L"
        } else if(["L","H","V"].indexOf(upper)>=0
                && Math.sqrt(Math.pow(end[0]-current[0],2)+Math.pow(end[1]-current[1],2))>=minLength)
            out+=arcLine(current,end,seed,segment++,amplitude)
        else out+=command+values.join(" ")
        current=end
    }
    return out
}
function rectPath(a) {
    var x=Number(a.x||0),y=Number(a.y||0),w=Number(a.width),h=Number(a.height)
    var r=Math.max(0,Math.min(Number(a.rx||0),w/2,h/2))
    return "M"+(x+r)+" "+y+"H"+(x+w-r)+"Q"+(x+w)+" "+y+" "+(x+w)+" "+(y+r)
        +"V"+(y+h-r)+"Q"+(x+w)+" "+(y+h)+" "+(x+w-r)+" "+(y+h)
        +"H"+(x+r)+"Q"+x+" "+(y+h)+" "+x+" "+(y+h-r)+"V"+(y+r)+"Q"+x+" "+y+" "+(x+r)+" "+y+"Z"
}
function linework(input,c,seed,options) {
    var o=options||{},width=o.width===undefined?.40:o.width,stack=[1],index=0,out="",skip=Number(o.skipShapes||0)
    var source=String(input).replace(/<defs\b[^>]*>[\s\S]*?<\/defs>/g,"")
    var tags=source.match(/<g\b[^>]*>|<\/g>|<(?:path|rect|circle|ellipse|line|polyline|polygon)\b[^>]*\/>/g)||[]
    for(var t=0;t<tags.length;t++) {
        var tag=tags[t]
        if(tag==="</g>"){if(stack.length>1){stack.pop();out+="</g>"}continue}
        var a=attributes(tag),transform=a.transform||""
        if(/^<g\b/.test(tag)) {
            stack.push(stack[stack.length-1]*scaleOf(transform))
            out+='<g'+(transform?' transform="'+transform+'"':"")+(a["class"]?' class="'+a["class"]+'"':"")+'>'
            continue
        }
        var type=/^<(\w+)/.exec(tag)[1],scale=stack[stack.length-1]*scaleOf(transform)
        var localWidth=width/scale,keep=o.keepTiny===true
        if(skip>0){skip--;continue}
        if(o.maxShapes!==undefined && index>=o.maxShapes)continue
        if(o.dropFaint===true && a.opacity!==undefined && Number(a.opacity)<.86)continue
        if(o.dropFaint===true && a.fill==="none" && a["stroke-width"]!==undefined
                && Number(a["stroke-width"])*scale<.18)continue
        if(type==="rect" && !keep && (Number(a.width)*scale<.34 || Number(a.height)*scale<.24))continue
        var cls=a["class"]||"",rotor=o.rotor===true
        if(rotor && cls==="hardware-fan-ridge")continue
        if(rotor)localWidth=cls==="hardware-fan-blade"?.22:cls==="hardware-fan-hub"?.24:.15
        var attributesText=(transform?' transform="'+transform+'"':"")+(cls?' class="'+cls+'"':"")
        var d=a.d
        if(type==="rect" && o.wobble!==false) {type="path";d=rectPath(a)}
        if(type==="path") {
            if(!d)continue
            if(o.wobble!==false && !rotor)d=wobblyPath(d,seed+":"+index,.60/scale,2.2/scale)
            attributesText+=' d="'+d+'"'
        } else {
            var names=type==="rect"?["x","y","width","height","rx","ry"]
                :type==="circle"?["cx","cy","r"]:type==="ellipse"?["cx","cy","rx","ry"]
                :type==="line"?["x1","y1","x2","y2"]:["points"]
            for(var k=0;k<names.length;k++)if(a[names[k]]!==undefined)attributesText+=' '+names[k]+'="'+a[names[k]]+'"'
        }
        var fill=rotor && cls==="hardware-fan-hub"?c.paper:"none"
        out+='<'+type+attributesText+' fill="'+fill+'" stroke="'+c.ink+'" stroke-width="'+number(localWidth)+'" stroke-linejoin="round" stroke-linecap="round"/>'
        index++
    }
    while(stack.length>1){stack.pop();out+="</g>"}
    return out
}
function geometry(state) {return Solid.geometry(state)}
function fan(cx,cy,radius,c,kind) {
    var target=c.rotorCollector,local=[]
    c.rotorCollector=local
    Fans.fan(cx,cy,radius,c,kind)
    if(Array.isArray(target))c.rotorCollector=target
    else delete c.rotorCollector
    var rotor=local[0]
    var transform='translate('+cx+' '+cy+') scale('+(radius/3)+')'
    var base='<g class="'+(kind==="blower"?'hardware-blower':'hardware-fan')+'" transform="'+transform+'">'
        +'<circle r="3" fill="'+c.paper+'" stroke="'+c.ink+'" stroke-width=".32"/></g>'
    // A known opening must survive even if a future profile cannot supply a
    // rotor descriptor. Its empty ring is fixed and makes no leaf-count claim.
    if(!rotor)return base
    rotor.body=linework(rotor.body,c,"rotor",{rotor:true,wobble:false,keepTiny:true})
    if(Array.isArray(target)){target.push(rotor);return base}
    return base+'<g transform="'+transform+'">'+rotor.body+'</g>'
}
function caseFeature(state,g,c,front) {
    // One narrow physical trim from the real cover, not every filled panel's
    // boundary. Whole panels and fan-bay ellipses are deliberately excluded.
    var tags=String(front).match(/<g\b[^>]*>|<\/g>|<rect\b[^>]*\/>/g)||[],groups=[],scales=[1]
    for(var i=0;i<tags.length;i++) {
        var tag=tags[i],a=attributes(tag)
        if(tag==="</g>"){groups.pop();scales.pop();continue}
        if(/^<g\b/.test(tag)) {
            groups.push(a.transform?'<g transform="'+a.transform+'">':'<g>')
            scales.push(scales[scales.length-1]*scaleOf(a.transform))
            continue
        }
        var x=Number(a.x||0),y=Number(a.y||0),w=Number(a.width),h=Number(a.height),scale=scales[scales.length-1]
        var horizontal=w/h>=4 && w*scale>=3.5 && h*scale<=1.4
        var vertical=h/w>=4 && h*scale>=3.5 && w*scale<=1.4
        if(!horizontal && !vertical)continue
        var inset=Math.min(Number(a.rx||0),Math.min(w,h)/2)
        var d=horizontal?'M'+(x+inset)+' '+(y+h/2)+'H'+(x+w-inset)
            :'M'+(x+w/2)+' '+(y+inset)+'V'+(y+h-inset)
        var fragment=groups.join('')+Solid.p(d,'none',1,c.ink,.3)
        for(var k=0;k<groups.length;k++)fragment+='</g>'
        return linework(fragment,c,identity(state)+':trim',{width:.29,maxShapes:1})
    }
    var reviewed=['asus_dual','asus_tuf','asus_rog_strix','msi_ventus','msi_gaming','msi_suprim',
        'gigabyte_windforce','gigabyte_aorus','gigabyte_aero','zotac_solo','sapphire_pulse','sapphire_nitro',
        'powercolor_hellhound','powercolor_red_devil']
    return reviewed.indexOf(state.series_id)>=0
        ?linework(Solid.trim(state,g,c),c,identity(state)+':trim',{width:.28,maxShapes:1}):''
}
function connector(state,g,c) {
    var row=Board.profile(state),bus=row && row.host_interface?row.host_interface.bus:'unknown'
    var start=g.x+g.w*.18,width=g.w*.34,length=row && row.dimensions_mm && row.dimensions_mm.length
    if(typeof length==='number' && length>0) {
        start=g.x+g.w*Math.min(.28,(bus==='agp'?28:45)/length)
        width=g.w*Math.max(.22,Math.min(.58,(bus==='agp'?62:82)/length))
    }
    // One readable connector tongue. The line does not claim a pin count or
    // expose invented PCB components, and there is no side/extrusion plane.
    var bottom=g.y+g.h,d='M'+start+' '+(bottom+.2)+'V'+(bottom+.72)+'H'+(start+width)+'V'+(bottom+.2)
    return linework(Solid.p(d,'none',1,c.ink,.27),c,identity(state)+':connector',{width:.27})
}
function passiveOutline(state,g,c,front) {
    // The GT 1030 Silent LP's first source shape is only its low PCB strip.
    // Its next shape is the exposed fin-stack base, not a fan shroud. Three
    // spaced source-fin centre lines convey the stack without drawing all
    // twelve fins as a dark wireframe or asserting a new component count.
    var out=linework(front,c,identity(state)+':passive',{width:.4,skipShapes:1,maxShapes:1})
    var positions=[4+1*7.8+1.5,4+6*7.8+1.5,4+10*7.8+1.5],d=''
    positions.forEach(function(at){var x=g.x+g.w*at/100;d+='M'+x+' '+(g.y+g.h*.02)+'V'+(g.y+g.h*.87)})
    return '<g class="hardware-sketch-passive">'+out+linework(Solid.p(d,'none',1,c.ink,.26),c,identity(state)+':fins',{width:.26})+'</g>'
}
function gpu(state,c) {
    if(state.style==="gpu_integrated")return linework(Solid.integrated(c),c,identity(state),{width:.47,dropFaint:true,maxShapes:2})
    var g=geometry(state),seed=identity(state)
    // The first major cover shape is the reviewed model's outer silhouette.
    // Keep that one outline, one trim and one connector; filled-panel seams,
    // heatsink shading, repeated rims and side planes are not a sketch style.
    var front=Solid.front(state,g,c)
    var out=(state.series_id==='gigabyte_silent_pascal' && state.fan_count===0
            ?passiveOutline(state,g,c,front)
            :linework(front,c,seed+":cover",{width:.45,dropFaint:true,maxShapes:1}))
        +caseFeature(state,g,c,front)+connector(state,g,c)
    var bracket='M'+(g.x-.43)+' '+(g.y-.25)+'H'+(g.x+.12)+'M'+(g.x-.43)+' '+(g.y-.25)+'V'+(g.y+g.h+.38)
    out+=linework(Solid.p(bracket,'none',1,c.ink,.25),c,seed+':bracket',{width:.25})
    var cy=g.y+g.h*.51
    if(state.style==="gpu_blower" && state.fan_count===1)
        out+=fan(g.centers.length?g.centers[0]:g.x+g.w-4.5,cy,Math.min(3.55,g.h*.37),c,"blower")
    else if(g.centers.length)g.centers.forEach(function(cx,index){
        out+=fan(cx,g.fan_y?g.fan_y[index]:cy,g.radii?g.radii[index]:g.radius,c,
            g.blowers && g.blowers.indexOf(index)>=0?"blower":"axial")
    })
    else if(state.fan_count!==0) {
        // Unreviewed cooling remains a plain covered board, not invented fans.
        out+=linework(Solid.p("M"+(g.x+2.3)+" "+(g.y+2.2)+"H"+(g.x+g.w-2.4)
            +"M"+(g.x+2.3)+" "+(g.y+g.h-2.1)+"H"+(g.x+g.w-4.0),"none",1,c.ink,.3),c,seed+":neutral",{width:.3})
    }
    return out
}
function memory(state,c) {
    var colors=Board.memoryColors(state,Memory.palette(state)),seed=identity(state)
    if(state.style!=="dimm" && state.style!=="sodimm")return linework(Memory.neutral(colors),c,seed,{width:.48,maxShapes:4})
    var g=Board.geometry(state,Memory.profile(state))
    // Keep the original PCB contour and contact openings verbatim. The casing
    // above it may wobble; a DDR key must not move or be smoothed over.
    return linework(Memory.board(g,colors),c,seed+":pcb",{width:.27,wobble:false,keepTiny:true})
        +linework(Memory.enclosure(state,g,colors),c,seed+":cover",{width:.43})
}
function body(state,collector) {
    if(!state || ["cpu","gpu","memory"].indexOf(state.kind)<0)return ""
    var ink=palette(state),c=state.kind==="gpu"?Board.colors(state,Solid.palette(state)):Solid.palette(state)
    c.ink=ink.ink;c.paper=ink.paper;c.fanDesignSeries=state.series_id;c.fanDesignIndex=0
    if(Array.isArray(collector))c.rotorCollector=collector
    var out=state.kind==="gpu"?gpu(state,c):state.kind==="memory"?memory(state,c)
        :linework(Solid.cpu(state,c),c,identity(state),{width:.45,dropFaint:true,maxShapes:state.style==="chip"?3:2})
    return '<g class="hardware-sketch" stroke-linecap="round" stroke-linejoin="round">'+out+'</g>'
}
function generic(kind,ink,moving) {
    var name=typeof kind==="string"?kind:"sensors",c=palette({ink:ink})
    if(name==="cpu")return body({kind:"cpu",style:"chip",ink:c.ink})
    if(name==="gpu")return body({kind:"gpu",style:"gpu_neutral",fan_count:-1,ink:c.ink})
    var aliases={board:"grid",storage:"disk",vram:"memory",swap:"memory"}
    name=aliases[name]||name
    var out=""
    if(name==="fan") {
        out=linework('<rect x="2.5" y="2.5" width="19" height="19" rx="2.5"/>',c,"fan-case",{width:.60})
        if(!moving)out+=linework(Icons.fragment("fan"),c,"fan",{width:.60,wobble:false})
    } else out=linework(Icons.fragment(name),c,"category:"+name,{width:.60})
    return '<g class="hardware-sketch"><g class="hardware-sketch-category" stroke-linejoin="round" stroke-linecap="round">'+out+'</g></g>'
}
