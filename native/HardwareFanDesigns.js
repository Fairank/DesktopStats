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
    result.hub_ratio=typeof result.hub_ratio==="number"&&Number.isFinite(result.hub_ratio)?Math.max(.1,Math.min(.55,result.hub_ratio)):.28
    result.shape=["swept","wide","paired","claw","radial","neutral"].indexOf(result.shape)>=0?result.shape:"neutral"
    result.group_size=[1,2,3].indexOf(result.group_size)>=0?result.group_size:1
    result.direction=result.direction===-1?-1:1
    result.hub_shape=result.hub_shape==="triangle"?"triangle":"circle"
    result.kind=kind
    return result
}

function point(angle,radius) {
    var a=(angle-90)*Math.PI/180
    return (Math.cos(a)*radius).toFixed(4)+" "+(Math.sin(a)*radius).toFixed(4)
}

function blade(p) {
    var pitch=360/p.blades,hub=Math.max(.45,p.hub_ratio*3*.90)
    if(p.kind==="blower" || p.shape==="radial")
        return "M"+point(-pitch*.19,Math.max(1.15,hub))+"L"+point(-pitch*.39,2.60)
            +"Q"+point(0,2.72)+" "+point(pitch*.30,2.54)+"L"+point(pitch*.17,Math.max(1.15,hub))+"Z"
    var width=p.shape==="wide"?.43:p.shape==="claw"?.42:.35
    return "M"+point(-pitch*.18,hub)+"Q"+point(-pitch*.57,1.66)+" "+point(-pitch*.46,2.53)
        +"Q"+point(-pitch*.06,2.94)+" "+point(pitch*width,2.54)
        +"Q"+point(pitch*.49,1.75)+" "+point(pitch*.19,hub)+"Z"
}

function tipArc(start,end,color) {
    return '<path d="M'+point(start,2.55)+'A2.55 2.55 0 '+(end-start>180?1:0)+' 1 '+point(end,2.55)
        +'" fill="none" stroke="'+color+'" stroke-width=".20"/>'
}

function rotor(p,c) {
    var out="",count=p.blades
    if(count!==null && p.shape!=="neutral") {
        var path=blade(p)
        for(var i=0;i<count;i++)out+='<path d="'+path+'" transform="rotate('+(i*360/count)+')" fill="'+c.blade+'"/>'
        if(p.outer_ring===true)out+='<circle r="2.62" fill="none" stroke="'+c.blade+'" stroke-width=".22"/>'
        else if(p.group_size>1 && count%p.group_size===0)
            for(var j=0;j<count;j+=p.group_size)out+=tipArc((j-.38)*360/count,(j+p.group_size-.62)*360/count,c.blade)
    } else {
        // Known rotor presence with unreviewed blades: broad shaded disc,
        // no arbitrary repeated spokes that could be mistaken for a count.
        out+='<circle r="2.25" fill="'+c.disk+'"/><circle r="1.95" fill="none" stroke="'+c.blade+'" stroke-opacity=".25" stroke-width=".32"/>'
        if(p.outer_ring===true)out+='<circle r="2.62" fill="none" stroke="'+c.blade+'" stroke-width=".22"/>'
    }
    if(p.direction===-1)out='<g transform="scale(-1 1)">'+out+'</g>'
    var hub=p.hub_ratio*3
    if(p.hub_shape==="triangle")out+='<path class="hardware-fan-hub" d="M'+point(0,hub*1.15)+'L'+point(120,hub*1.15)+'L'+point(240,hub*1.15)+'Z" fill="'+c.hub+'"/>'
    else out+='<circle class="hardware-fan-hub" r="'+hub+'" fill="'+c.hub+'"/>'
    return out
}

function fan(cx,cy,radius,c,kind) {
    var index=c.fanDesignIndex || 0
    c.fanDesignIndex=index+1
    var p=profile(c.fanDesignSeries,index,kind)
    var moving=rotor(p,c)
    var base='<g class="'+(kind==="blower"?'hardware-blower':'hardware-fan')+'" transform="translate('+cx+' '+cy+') scale('+(radius/3)+')">'
        +'<circle r="3" fill="'+c.rim+'"/><circle r="2.76" fill="'+c.disk+'"/>'
    if(c.rotorCollector) {
        c.rotorCollector.push({cx:cx,cy:cy,radius:radius,kind:kind,basis:3,body:moving,direction:p.direction})
        return base+'</g>'
    }
    return base+moving+'</g>'
}
