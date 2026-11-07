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
    return normalized(result,series,index,kind)
}

function normalized(result,series,index,kind) {
    result.blades=Number.isInteger(result.blades)&&result.blades>=2&&result.blades<=64?result.blades:null
    result.hub_ratio=typeof result.hub_ratio==="number"&&Number.isFinite(result.hub_ratio)?Math.max(.1,Math.min(.70,result.hub_ratio)):.28
    result.shape=["swept","wide","paired","claw","radial","straight","neutral"].indexOf(result.shape)>=0?result.shape:"neutral"
    result.group_size=[1,2,3].indexOf(result.group_size)>=0?result.group_size:1
    result.direction=result.direction===-1?-1:1
    result.hub_shape=result.hub_shape==="triangle"?"triangle":"circle"
    result.tone=["light","red"].indexOf(result.tone)>=0?result.tone:"dark"
    result.blade_pattern=result.blade_pattern==="alternating" && result.blades!==null && result.blades%2===0?"alternating":"uniform"
    result.hub_mark=result.hub_mark==="gold"?"gold":""
    result.paintKey=String(series).replace(/[^a-z0-9_]/g,"")+"_"+index
    result.kind=kind
    return result
}

function point(angle,radius) {
    var a=(angle-90)*Math.PI/180
    return (Math.cos(a)*radius).toFixed(4)+" "+(Math.sin(a)*radius).toFixed(4)
}

function contour(p) {
    if(p.model_detail===true) {
        var detail=modelContour(p)
        if(detail)return detail
    }
    // Sweep is independent of blade pitch: dense 11/13-blade rotors must
    // retain curved vanes instead of collapsing into almost radial spokes.
    if(p.blade_variant==="dispersion")return {sweep:44,lead:.46,trail:.33,root:.30}
    if(p.blade_variant==="traditional")return {sweep:48,lead:.27,trail:.25,root:.20}
    return p.shape==="straight"?{sweep:4,lead:.36,trail:.33,root:.32}
        :p.shape==="wide"?{sweep:48,lead:.46,trail:.35,root:.28}
        :p.shape==="paired"?{sweep:58,lead:.37,trail:.34,root:.23}
        :p.shape==="claw"?{sweep:46,lead:.43,trail:.32,root:.27}
        :{sweep:52,lead:.35,trail:.30,root:.24}
}

function blade(p) {
    var pitch=360/p.blades,hub=Math.max(.45,p.hub_ratio*3*.88),g=contour(p),s=g.sweep
    if(p.model_detail===true && (p.kind==="blower" || p.shape==="radial"))
        return "M"+point(-pitch*.18,Math.max(1.15,hub))+"L"+point(-pitch*.25,2.61)
            +"Q"+point(-pitch*.03,2.72)+" "+point(pitch*.21,2.60)
            +"L"+point(pitch*.14,Math.max(1.15,hub))+"Z"
    if(p.kind==="blower" || p.shape==="radial")
        return "M"+point(-pitch*.19,Math.max(1.15,hub))+"L"+point(-pitch*.39,2.60)
            +"Q"+point(0,2.72)+" "+point(pitch*.30,2.54)+"L"+point(pitch*.17,Math.max(1.15,hub))+"Z"
    return "M"+point(-pitch*g.root,hub)
        +"C"+point(-s*.18-pitch*.18,1.32)+" "+point(-s*.85-pitch*(g.lead+.04),2.12)+" "+point(-s-pitch*g.lead,2.55)
        +"Q"+point(-s-pitch*.05,2.73)+" "+point(-s+pitch*g.trail,2.54)
        +"C"+point(-s*.60+pitch*(g.trail+.08),2.03)+" "+point(-s*.06+pitch*.29,1.23)+" "+point(pitch*g.root,hub)+"Z"
}

function fanPalette(p) {
    // Object colours belong to the rotor, not the CPU/board highlight palette.
    // Keep a dark recess and an independent cap; white retail fans opt in.
    return p.tone==="red"
        ? {rim:"#686c72",disk:"#302d33",blade:"#b9555d",hub:"#582f38",edge:"#c78186",ridge:"#d48d92",shade:"#743842",light:"#d37b80"}
        :p.tone==="light"
        ? {rim:"#a6b6be",disk:"#637684",blade:"#d3dde2",hub:"#bdcbd3",edge:"#eef3f6",ridge:"#a4b6c2",shade:"#acbfca",light:"#eef3f6"}
        : {rim:"#48535b",disk:"#1f262c",blade:"#45515a",hub:"#343d44",edge:"#63727d",ridge:"#809099",shade:"#2b343c",light:"#5b6974"}
}

function tipArc(start,end,color) {
    return '<path d="M'+point(start,2.55)+'A2.55 2.55 0 '+(end-start>180?1:0)+' 1 '+point(end,2.55)
        +'" fill="none" stroke="'+color+'" stroke-width=".20"/>'
}

function rotor(p,c) {
    c=fanPalette(p)
    if(p.hub_tone==="silver"){c.hub="#bdc9d0";c.edge="#e1e8ed"}
    else if(p.hub_tone==="dark"){c.hub="#343d44";c.edge="#63727d"}
    else if(p.hub_tone==="light"){c.hub="#e1e6e8";c.edge="#f0f3f4"}
    var out="",count=p.blades
    if(count!==null && p.shape!=="neutral") {
        // A small static SVG paint gives the curved plastic a raised face.
        // It is baked into the same retained sprite, never a live shader.
        var paint="fan-leaf-"+p.paintKey
        out+='<defs><linearGradient id="'+paint+'" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="'+c.shade+'"/><stop offset=".38" stop-color="'+c.blade+'"/><stop offset=".62" stop-color="'+c.light+'"/><stop offset="1" stop-color="'+c.shade+'"/></linearGradient></defs>'
        var path=blade(p)
        // TORX/TORX 2.0's confirmed 7+7 alternating leaves remain fourteen
        // blades. The wider dispersion and narrow traditional leaves are two
        // static contours, not extra spokes or additional moving layers.
        var alternating=p.blade_pattern==="alternating" && count%2===0 && p.kind!=="blower"
        var leaves=[]
        if(alternating)for(var variant=0;variant<2;variant++) {
            var variantProfile={}
            Object.keys(p).forEach(function(key){variantProfile[key]=p[key]})
            variantProfile.blade_variant=variant===0?"dispersion":"traditional"
            leaves.push(blade(variantProfile))
        }
        for(var i=0;i<count;i++) {
            out+='<path class="hardware-fan-blade" d="'+(alternating?leaves[i%2]:path)+'" transform="rotate('+(i*360/count)+')" fill="url(#'+paint+')"/>'
            if(p.model_detail===true && p.kind!=="blower" && p.shape!=="radial") {
                var shaped=alternating?modelContour(Object.assign({},p,{blade_variant:i%2===0?"dispersion":"traditional"})):contour(p)
                var edge="M"+point(-shaped.sweep*.18,Math.max(1.24,p.hub_ratio*3+.10))
                    +"Q"+point(-shaped.sweep*.77,2.06)+" "+point(-shaped.sweep+360/count*shaped.trail*.58,2.53)
                out+='<path class="hardware-model-leaf-bevel" d="'+edge+'" transform="rotate('+(i*360/count)+')" fill="none" stroke="'+c.ridge+'" stroke-opacity=".42" stroke-width=".045"/>'
            }
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
    if(p.hub_mark==="gold")out+='<path class="hardware-fan-cap-mark" d="M-.22 0L0 -.23L.22 0L0 .23Z" fill="none" stroke="#bd9c53" stroke-width=".065"/>'
    return out
}

function fan(cx,cy,radius,c,kind) {
    var index=c.fanDesignIndex || 0
    c.fanDesignIndex=index+1
    var p=profile(c.fanDesignSeries,index,kind)
    if(c.fanOverrides) {
        Object.keys(c.fanOverrides).forEach(function(key){if(key!=="fans")p[key]=c.fanOverrides[key]})
        var single=c.fanOverrides.fans && c.fanOverrides.fans[index]
        if(single)Object.keys(single).forEach(function(key){p[key]=single[key]})
        p=normalized(p,c.fanDesignSeries,index,kind)
    }
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

// Model-only qualitative contours from the already reviewed family studies.
// These are illustration proportions, never measured blade pitch or CAD.
// No caller of profile()/rotor()/fan() opts in implicitly: the bar stays exact.
function modelContour(p) {
    if(p.blade_variant==="dispersion")return {sweep:41,lead:.55,trail:.31,root:.31}
    if(p.blade_variant==="traditional")return {sweep:49,lead:.22,trail:.19,root:.16}
    if(p.technology==="dual_flow_through_blackwell")return {sweep:43,lead:.48,trail:.33,root:.38}
    if(p.technology==="axial_tech_ada_strix")return {sweep:55,lead:.38,trail:.26,root:.23}
    if(p.technology==="amd_reference_axial")return {sweep:36,lead:.43,trail:.27,root:.29}
    if(p.technology==="torx_5")return {sweep:57,lead:.36,trail:.31,root:.25}
    if(p.technology==="torx_original")return {sweep:46,lead:.34,trail:.25,root:.24}
    if(p.technology==="icestorm_2_twin_edge")return {sweep:48,lead:.37,trail:.29,root:.26}
    return null
}

function modelRotor(profile,details) {
    var p=Object.assign({},profile,{model_detail:true}),out=rotor(p),hub=p.hub_ratio*3
    var c=fanPalette(p),silver=p.hub_tone==="silver"
    if(silver || details && details.machined_hub) {
        var edge=silver?"#83939e":c.edge
        out+='<g class="hardware-model-cap-finish"><circle r="'+(hub*.88)+'" fill="none" stroke="'+edge+'" stroke-opacity=".8" stroke-width=".045"/>'
            +'<path d="M'+point(-68,hub*.73)+'A'+(hub*.73)+' '+(hub*.73)+' 0 0 1 '+point(48,hub*.73)+'" fill="none" stroke="'+(silver?'#edf2f5':c.ridge)+'" stroke-opacity=".6" stroke-width=".055"/></g>'
    }
    if(details && details.red_label_edge)
        out+='<circle class="hardware-model-label-edge" r="'+(hub*.89)+'" fill="none" stroke="#9b4148" stroke-width=".055"/>'
    return out
}
