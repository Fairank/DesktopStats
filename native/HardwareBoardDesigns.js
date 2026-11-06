.pragma library
.import "HardwareBoardProfileData.js" as Data

// Static exterior structures. Never expose an invented PCB circuit, native
// socket order or hidden component count. Connector close-ups are count/type
// diagrams, not a claim about their physical order on a particular bracket.
function modelKey(input) {
    if(!input || input.confidence!=="model" || typeof input.id!=="string" || input.id.length>96)return ""
    var row=Data.models[input.id]
    return row && row.kind===input.kind && row.series_id===input.series_id ? input.id : ""
}
function profile(state) {
    var row=state && Data.models[state.model_id]
    return row && row.kind===state.kind && row.series_id===state.series_id ? row : null
}
function rect(x,y,w,h,r,fill,stroke,width) {
    return '<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" rx="'+r+'" fill="'+fill+'"'
        +(stroke?' stroke="'+stroke+'" stroke-width="'+width+'"':'')+'/>'
}
function path(d,fill,stroke,width) {
    return '<path d="'+d+'" fill="'+fill+'"'+(stroke?' stroke="'+stroke+'" stroke-width="'+width+'"':'')+'/>'
}
function copy(input) {var out={};Object.keys(input).forEach(function(key){out[key]=input[key]});return out}
function colors(state,input) {
    var out=copy(input),row=profile(state)
    if(!row)return out
    var palettes={
        dark:["#3e4a57","#65717e","#26323e","#8998a4","#8394a1","#b5c1cb"],
        light:["#d9e2e8","#f1f5f7","#9bafbc","#a7b9c5","#c4d2dc","#f6f8f9"],
        silver:["#a1afb9","#d5dfe5","#637682","#a6b8c3","#c6d2d9","#edf2f5"],
        blue:["#4e739b","#7da0c3","#2e4c6a","#8ea9bf","#a7bdce","#d8e6ee"],
        pink:["#d5b9cd","#eee0ec","#947e9b","#bea6bd","#d9cbd9","#f6eef4"],
        mixed:["#aebcc5","#d4dee5","#435562","#93a7b4","#bbc9d3","#ebf1f5"]}
    var palette=palettes[row.shroud_tone]
    if(palette){out.caseBody=palette[0];out.caseTop=palette[1];out.caseShade=palette[2];out.rim=palette[3];out.metal=palette[4];out.edge=palette[5];if(out.side)out.side=palette[2]}
    out.pcb=row.pcb_tone==="blue"?"#386e98":row.pcb_tone==="green"?"#426b60":row.pcb_tone==="dark"?"#293944":"#344c4d";out.gold="#c7a65d"
    if(row.fan_profile)out.fanOverrides=row.fan_profile
    return out
}

function variantFace(state,g,c) {
    var row=profile(state)
    if(!row || row.recipe!=="suprim_blackwell")return ""
    // Reviewed 5090 front: broad brushed-metal triangles around three dark
    // octagonal bays. This is independent of the 4090 TORX cover drawing.
    var body=rect(0,3,100,94,1.5,"#313c46")
        +path("M0 3H25L30 21L11 28L0 23Z","#8f9da7")
        +path("M25 3H76L68 18L54 28L34 28Z","#d0d9df")
        +path("M76 3H100V25L85 22Z","#7d8c97")
        +path("M0 75L15 70L29 83L33 97H0Z","#465560")
        +path("M29 83L36 69L53 72L69 81L64 97H33Z","#bdcbd3")
        +path("M69 81L83 69L100 78V97H64Z","#6e7d88")
    for(var i=0;i<g.centers.length;i++) {
        var x=(g.centers[i]-g.x)/g.w*100,y=51,rx=15.4,ry=43
        body+=path("M"+(x-rx*.68)+" "+(y-ry)+"H"+(x+rx*.68)+"L"+(x+rx)+" "+(y-ry*.58)
            +"V"+(y+ry*.58)+"L"+(x+rx*.68)+" "+(y+ry)+"H"+(x-rx*.68)+"L"+(x-rx)+" "+(y+ry*.58)
            +"V"+(y-ry*.58)+"Z","#2a343e","#82939f",.48)
    }
    body+=path("M29 23L32 50L30 74M67 25L70 50L68 76","none","#8aaec9",.65)
    return '<g class="hardware-variant-face suprim_blackwell" transform="translate('+g.x+' '+g.y+') scale('+(g.w/100)+' '+(g.h/100)+')">'+body+'</g>'
}

function memoryColors(state,input) {
    var row=profile(state)
    if(!row || input.outline)return input
    var model=colors(state,{}),out=copy(input)
    if(model.caseBody){out.body=model.caseBody;out.shade=model.caseShade;out.side=model.caseShade;out.metal=model.metal;out.light=model.edge}
    if(row.pcb_tone!=="unknown")out.pcb=model.pcb
    out.gold=model.gold
    if(typeof row.notch_ratio==="number" && row.notch_ratio>0 && row.notch_ratio<1)out.notchRatio=row.notch_ratio
    if(typeof row.notch_width_ratio==="number")out.notchWidthRatio=row.notch_width_ratio
    if(typeof row.notch_depth_ratio==="number")out.notchDepthRatio=row.notch_depth_ratio
    return out
}

function depth(state,g) {
    var row=profile(state),size=row && row.dimensions_mm
    var value=size && typeof size.thickness==="number" && typeof size.height==="number" && size.height>0
        ? g.h*size.thickness/size.height*.45:1.45
    // A shallow illustration projection follows documented card thickness;
    // it never skews the circular fan plane or exceeds the 24-unit canvas.
    return Math.max(.55,Math.min(2.05,23.72-g.x-g.w,value))
}

function base(state,g,c) {
    var row=profile(state),bus=row && row.host_interface ? row.host_interface.bus:"unknown"
    var x=g.x,y=g.y,b=y+g.h,e=x+g.w,bx=Math.max(.12,x-.74)
    // A visible connector tongue, never a fabricated full-length bare board.
    var start=x+g.w*.18,width=g.w*.34
    var length=row && row.dimensions_mm && row.dimensions_mm.length
    if(typeof length==="number" && length>0) {
        // Visual calibration against the documented outer envelope, not
        // manufactured PCB dimensions or an electrical-lane-length inference.
        start=x+g.w*Math.min(.28,(bus==="agp"?28:45)/length)
        width=g.w*Math.max(.22,Math.min(.58,(bus==="agp"?62:82)/length))
    }
    var keys=bus==="pcie"?1:bus==="agp" && Number.isInteger(row.edge_key_count)?row.edge_key_count:0
    var result='<g class="hardware-board-base">'
        +path("M"+bx+" "+(y-.55)+"H"+(x+.7)+"V"+(y-.08)+"H"+(bx+.42)+"V"+(b+.52)+"H"+bx+"Z",c.rim)
        +rect(bx+.14,y+.35,.30,Math.max(.4,g.h-.6),.10,c.metal)
        +rect(x+.35,b-.10,g.w-.7,.72,.12,c.caseShade)
        +rect(start-.28,b+.17,width+.58,.85,.10,c.pcb)
    // Gold strips are a readable schematic density, not a physical pin count.
    for(var i=0;i<14;i++) {
        var at=start+width*i/14,notch=false
        for(var k=0;k<keys;k++)if(Math.abs((i+.5)/14-(k+1)/(keys+2))<.045)notch=true
        if(!notch)result+=rect(at,b+.52,width/14*.69,.64,.035,c.gold)
    }
    if(keys)for(var j=0;j<keys;j++)result+=rect(start+width*(j+1)/(keys+2)-.11,b+.39,.22,.78,0,c.caseShade)
    // Bracket vents and the small mounting ear are drawn on the side plane.
    // Native video sockets are shown separately where their types are legible.
    result+=path("M"+(bx+.1)+" "+(y-.3)+"H"+(x+.4),"none",c.edge,.14)
    for(var v=0;v<3;v++)result+=rect(bx+.14,y+g.h*.25+v*.62,.26,.30,.08,c.caseShade)
    // A narrow exposed fin edge gives depth without drawing through the cover.
    var fins=""
    for(var f=1;f<18;f++){var fx=x+.55+(g.w-1.1)*f/18;fins+="M"+fx+" "+(b+.06)+"V"+(b+.43)}
    result+=path(fins,"none",c.metal,.095)
    return result+'</g>'
}

function finish(state,g,c) {
    var row=profile(state)
    if(!row)return ""
    var out='<g class="hardware-board-finish">'
    // A seam follows the shroud rim. It does not invent fastener positions or
    // claim which die, VRM or memory components sit below the closed cover.
    out+=path("M"+(g.x+.45)+" "+(g.y+.22)+"H"+(g.x+g.w-.65),"none",c.edge,.105)
    if(row.power_position==="top" && row.power_connectors) {
        var count=row.power_connectors.reduce(function(total,item){return total+item.count},0)
        var begin=g.x+g.w*.63
        for(var i=0;i<count;i++)out+=rect(begin+i*1.05,g.y-.50,.92,.55,.10,"#283642",c.metal,.08)
    }
    return out+'</g>'
}

function contact(type,x,y,scale) {
    var shape="",edge="#a5b5c2",hole="#23323e",tongue="#718793"
    if(type==="displayport"||type==="mini_displayport") {
        shape=path("M0 0H12L15 3V10H0Z",hole,edge,.8)+rect(3,4,8,2,.25,tongue)
    } else if(type==="hdmi"||type==="mini_hdmi") {
        shape=path("M2 0H13L15 3L12 9H3L0 3Z",hole,edge,.8)+rect(4,3,7,1.8,.3,tongue)
    } else if(type==="usb_c") {
        shape=rect(1,1,13,8,4,hole,edge,.8)+rect(4,4,7,1.5,.7,tongue)
    } else if(type==="dvi") {
        shape=rect(-2,-1,19,12,1.5,edge)+rect(0,1,15,8,.6,hole)+rect(2,3,8,4,.2,tongue)+rect(12,3,1,4,.1,edge)
    } else if(type==="vga") {
        shape=path("M0 0H15L13 10H2Z","#537ba4",edge,.8)
        for(var r=0;r<3;r++)for(var k=0;k<5;k++)shape+='<circle cx="'+(3+k*2.2)+'" cy="'+(2.4+r*2.3)+'" r=".52" fill="'+hole+'"/>'
    } else if(type==="tv_out") {
        shape='<circle cx="7.5" cy="5" r="5" fill="'+hole+'" stroke="'+edge+'" stroke-width=".8"/>'+rect(5.5,3.6,4,2.2,.6,tongue)
    } else if(["4pin","6pin","8pin","12pin","16pin"].indexOf(type)>=0) {
        var cols=type==="4pin"?2:type==="6pin"?3:type==="8pin"?4:6
        var w=cols*3.2+2
        shape=rect(-1,-1,w,11,1.2,hole,edge,.8)+rect(w*.38,-2.5,w*.24,1.8,.3,edge)
        for(var py=0;py<2;py++)for(var px=0;px<cols;px++)shape+=rect(1+px*3.2,1+py*4,2.2,2.7,.35,"#101c25",tongue,.35)
        if(type==="16pin")for(var sense=0;sense<4;sense++)shape+=rect(4+sense*2.7,10.7,1.7,1.6,.2,hole,edge,.3)
    } else shape=rect(0,0,15,10,1.5,hole,edge,.8)
    return '<g class="hardware-socket '+type+'" transform="translate('+x+' '+y+') scale('+scale+')">'+shape+'</g>'
}

function technicalSource(model,view) {
    var row=typeof model==="string" && model.length<=96 ? Data.models[model]:null
    var svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 70" width="320" height="140">'
    if(!row || row.kind!=="gpu" || ["ports","power"].indexOf(view)<0)return "data:image/svg+xml;utf8,"+encodeURIComponent(svg+'</svg>')
    var items=view==="power"?row.power_connectors:row.ports
    if(!Array.isArray(items))return "data:image/svg+xml;utf8,"+encodeURIComponent(svg+'</svg>')
    var total=items.reduce(function(sum,item){return sum+item.count},0),index=0
    if(total>0) {
        var columns=Math.min(total,4),rows=Math.ceil(total/4),step=140/columns
        svg+=rect(5,6,150,58,6,"#7e909e")+rect(6,7,148,56,5,"#a8b6c1")
        items.forEach(function(group){for(var i=0;i<group.count;i++){
            var scale=view==="power"?1.18:1.36
            var cx=10+(index%columns+.5)*step,cy=rows===1?30:17+Math.floor(index/columns)*27
            svg+=contact(group.form==="unconfirmed"?"unknown":group.type,cx-(group.type==="16pin"?11:7.5)*scale,cy,scale);index++
        }})
        svg+='<circle cx="11" cy="12" r="1.4" fill="#526776"/><circle cx="149" cy="58" r="1.4" fill="#526776"/>'
        if(view==="ports" && row.auxiliary_button==="hyper_boost")
            svg+='<circle class="hardware-aux-button hyper-boost" cx="80" cy="16" r="3.3" fill="#253947" stroke="#ccd7de" stroke-width=".9"/>'
    }
    return "data:image/svg+xml;utf8,"+encodeURIComponent(svg+'</svg>')
}
