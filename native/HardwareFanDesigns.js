.pragma library
.import "HardwareFanProfileData.js" as Data

// Rotor shapes are source-backed studies. Unknown blade counts stay featureless
// discs; they never silently become five/six blades. Dimensions are illustration
// proportions, not factory measurements. Only prebuilt local textures rotate.
function profile(series,index,kind) {
    var row=Data.profiles[series] || ({})
    var result={}
    Object.keys(row).forEach(function(key){if(key!=="fans")result[key]=row[key]})
    if(row.fans && row.fans[index]) Object.keys(row.fans[index]).forEach(function(key){result[key]=row.fans[index][key]})
    result.blades=Number.isInteger(result.blades)&&result.blades>=2&&result.blades<=64?result.blades:null
    result.hub_ratio=typeof result.hub_ratio==="number"&&Number.isFinite(result.hub_ratio)?Math.max(.1,Math.min(.70,result.hub_ratio)):.28
    result.shape=["swept","wide","paired","claw","radial","straight","neutral"].indexOf(result.shape)>=0?result.shape:"neutral"
    result.group_size=[1,2,3].indexOf(result.group_size)>=0?result.group_size:1
    result.direction=result.direction===-1?-1:1
    result.hub_shape=result.hub_shape==="triangle"?"triangle":"circle"
    result.tone=["light","red"].indexOf(result.tone)>=0?result.tone:"dark"
    result.paintKey=String(series).replace(/[^a-z0-9_]/g,"")+"_"+index
    result.kind=kind
    return result
}

function point(angle,radius) {
    var a=(angle-90)*Math.PI/180
    return (Math.cos(a)*radius).toFixed(4)+" "+(Math.sin(a)*radius).toFixed(4)
}

function contour(p) {
    // Sweep is independent of blade pitch: dense 11/13-blade rotors must
    // retain curved vanes instead of collapsing into almost radial spokes.
    return p.shape==="straight"?{sweep:4,lead:.32,trail:.32,root:.25}
        :p.shape==="wide"?{sweep:34,lead:.35,trail:.34,root:.23}
        :p.shape==="paired"?{sweep:34,lead:.31,trail:.30,root:.18}
        :p.shape==="claw"?{sweep:36,lead:.33,trail:.31,root:.20}
        :{sweep:34,lead:.28,trail:.28,root:.20}
}

function blade(p) {
    var pitch=360/p.blades,hub=Math.max(.45,p.hub_ratio*3*.90),g=contour(p),s=g.sweep
    if(p.kind==="blower" || p.shape==="radial")
        return "M"+point(-pitch*.19,Math.max(1.15,hub))+"L"+point(-pitch*.39,2.60)
            +"Q"+point(0,2.72)+" "+point(pitch*.30,2.54)+"L"+point(pitch*.17,Math.max(1.15,hub))+"Z"
    return "M"+point(-pitch*g.root,hub)
        +"C"+point(-s*.25-pitch*.10,1.15)+" "+point(-s*.90-pitch*(g.lead+.07),1.85)+" "+point(-s-pitch*g.lead,2.52)
        +"Q"+point(-s+pitch*.02,2.78)+" "+point(-s+pitch*g.trail,2.50)
        +"C"+point(-s*.85+pitch*(g.trail+.04),1.85)+" "+point(-s*.20+pitch*.25,1.14)+" "+point(pitch*g.root,hub)+"Z"
}

function fanPalette(p) {
    // Object colours belong to the rotor, not the CPU/board highlight palette.
    // Keep a dark recess and an independent cap; white retail fans opt in.
    return p.tone==="red"
        ? {rim:"#686c72",disk:"#302d33",blade:"#b9555d",hub:"#582f38",edge:"#c78186",ridge:"#d48d92",shade:"#743842",light:"#d37b80"}
        :p.tone==="light"
        ? {rim:"#a6b6be",disk:"#637684",blade:"#d3dde2",hub:"#bdcbd3",edge:"#eef3f6",ridge:"#a4b6c2",shade:"#acbfca",light:"#eef3f6"}
        : {rim:"#738795",disk:"#253440",blade:"#586c7b",hub:"#344450",edge:"#8297a5",ridge:"#91a3af",shade:"#3c4f5e",light:"#738b9c"}
}

function tipArc(start,end,color) {
    return '<path d="M'+point(start,2.55)+'A2.55 2.55 0 '+(end-start>180?1:0)+' 1 '+point(end,2.55)
        +'" fill="none" stroke="'+color+'" stroke-width=".20"/>'
}

function rotor(p,c) {
    c=fanPalette(p)
    if(p.hub_tone==="silver"){c.hub="#bdc9d0";c.edge="#e1e8ed"}
    var out="",count=p.blades
    if(count!==null && p.shape!=="neutral") {
        // A small static SVG paint gives the curved plastic a raised face.
        // It is baked into the same retained sprite, never a live shader.
        var paint="fan-leaf-"+p.paintKey
        out+='<defs><linearGradient id="'+paint+'" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="'+c.shade+'"/><stop offset=".38" stop-color="'+c.blade+'"/><stop offset=".62" stop-color="'+c.light+'"/><stop offset="1" stop-color="'+c.shade+'"/></linearGradient></defs>'
        var path=blade(p)
        for(var i=0;i<count;i++) {
            out+='<path class="hardware-fan-blade" d="'+path+'" transform="rotate('+(i*360/count)+')" fill="url(#'+paint+')"/>'
            if(p.shape==="claw") {
                // The documented surface ridges stay on the leaf, never
                // become extra blades or a second full-size rotating plane.
                var sweep=contour(p).sweep,pitch=360/count
                var ridge="M"+point(-sweep*.58,1.40)+"Q"+point(-sweep*.82,1.95)+" "+point(-sweep+pitch*.10,2.39)
                out+='<g transform="rotate('+(i*360/count)+')"><path class="hardware-fan-ridge" d="'+ridge+'" fill="none" stroke="'+c.ridge+'" stroke-opacity=".44" stroke-width=".065"/></g>'
            }
        }
        if(p.outer_ring===true)out+='<circle r="2.62" fill="none" stroke="'+c.blade+'" stroke-width=".22"/>'
        else if(p.group_size>1 && count%p.group_size===0)
            for(var j=0;j<count;j+=p.group_size) {
                var geometry=contour(p),step=360/count
                out+=tipArc(j*step-geometry.sweep-geometry.lead*step,
                    (j+p.group_size-1)*step-geometry.sweep+geometry.trail*step,c.blade)
            }
    } else {
        // Known rotor presence with unreviewed blades: broad shaded disc,
        // no arbitrary repeated spokes that could be mistaken for a count.
        out+='<circle r="2.25" fill="'+c.blade+'" fill-opacity=".24"/><circle r="1.95" fill="none" stroke="'+c.blade+'" stroke-opacity=".3" stroke-width=".32"/>'
        if(p.outer_ring===true)out+='<circle r="2.62" fill="none" stroke="'+c.blade+'" stroke-width=".22"/>'
    }
    if(p.direction===-1)out='<g transform="scale(-1 1)">'+out+'</g>'
    var hub=p.hub_ratio*3
    if(p.hub_shape==="triangle")out+='<path class="hardware-fan-hub" d="M'+point(0,hub*1.15)+'L'+point(120,hub*1.15)+'L'+point(240,hub*1.15)+'Z" fill="'+c.hub+'"/>'
    else out+='<circle class="hardware-fan-hub" r="'+hub+'" fill="'+c.hub+'" stroke="'+c.edge+'" stroke-width=".06"/>'
    if(p.hub_tone==="silver")out+='<circle r="'+(hub*.78)+'" fill="none" stroke="#8c9eaa" stroke-width=".065"/>'
    return out
}

function fan(cx,cy,radius,c,kind) {
    var index=c.fanDesignIndex || 0
    c.fanDesignIndex=index+1
    var p=profile(c.fanDesignSeries,index,kind)
    if(c.fanOverrides)Object.keys(c.fanOverrides).forEach(function(key){p[key]=c.fanOverrides[key]})
    var colors=fanPalette(p)
    var moving=rotor(p,c)
    var base='<g class="'+(kind==="blower"?'hardware-blower':'hardware-fan')+'" transform="translate('+cx+' '+cy+') scale('+(radius/3)+')">'
        +'<circle r="3" fill="'+colors.rim+'"/><circle r="2.90" fill="'+colors.disk+'"/>'
    if(c.rotorCollector) {
        c.rotorCollector.push({cx:cx,cy:cy,radius:radius,kind:kind,basis:3,body:moving,direction:p.direction})
        return base+'</g>'
    }
    return base+moving+'</g>'
}
