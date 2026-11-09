.pragma library
.import "HardwareSolid.js" as Solid
.import "HardwareMemoryShapes.js" as Memory
.import "HardwareBoardDesigns.js" as Board

// Optional illustrated hardware. Model identities, enclosures, key notches and
// fan profiles still come from the reviewed object drawings. Rounded ink and
// small expressive marks are artwork, never manufacturer markings or telemetry.
// Every paint operation happens only when a retained SVG/rotor sprite is built.
// No filters, clocks, remote images, mutable cache or sensor access.

function hex(value, fallback) {
    return typeof value === "string" && /^#[0-9a-fA-F]{6}$/.test(value) ? value.toLowerCase() : fallback
}

function mix(a, b, amount) {
    var out = "#"
    for (var at = 1; at < 7; at += 2) {
        var channel = Math.round(parseInt(a.substr(at,2),16)*(1-amount)+parseInt(b.substr(at,2),16)*amount)
        out += ("0"+channel.toString(16)).slice(-2)
    }
    return out
}

function lightness(value) {
    return .2126*parseInt(value.substr(1,2),16)+.7152*parseInt(value.substr(3,2),16)+.0722*parseInt(value.substr(5,2),16)
}

function palette(state) {
    var ink = hex(state && state.ink,"#42566f")
    var accent = hex(state && state.accent,"#789ac6")
    return {ink:ink, line:"#364d68", accent:mix(accent,"#b1c7dd",.18),
        caseBody:"#a8bed5",caseTop:"#e3ecf5",caseShade:"#7089a8",side:"#7089a8",
        rim:"#90a9c3",disk:"#30435a",blade:"#7b96b2",hub:"#c6d8e7",
        metal:"#e5e9ed",edge:"#fcfaf5",pcb:"#75a496",gold:"#dfbb71",
        blush:"#edacb8",shine:"#fffaf0"}
}

function p(d, fill, stroke, width, opacity) {
    return '<path d="'+d+'" fill="'+(fill||"none")+'"'
        +(stroke?' stroke="'+stroke+'" stroke-width="'+(width||.4)+'" stroke-linecap="round" stroke-linejoin="round"':"")
        +(opacity===undefined?"":' opacity="'+opacity+'"')+'/>'
}

function r(x,y,w,h,radius,fill,stroke,width) {
    return '<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" rx="'+radius+'" fill="'+fill+'"'
        +(stroke?' stroke="'+stroke+'" stroke-width="'+(width||.4)+'"':"")+'/>'
}

function circle(x,y,radius,fill,stroke,width) {
    return '<circle cx="'+x+'" cy="'+y+'" r="'+radius+'" fill="'+fill+'"'
        +(stroke?' stroke="'+stroke+'" stroke-width="'+(width||.4)+'"':"")+'/>'
}

function smile(cx,cy,scale,ink,blush) {
    // A quiet expression, with round eyes and a single upturned mouth. This
    // decorative ink never substitutes for a sourced cap, slot or connector.
    return '<g class="hardware-cartoon-expression" transform="translate('+cx+' '+cy+') scale('+scale+')">'
        +circle(-.95,0,.23,ink)+circle(.95,0,.23,ink)
        +p("M-.46 .48Q0 1.02 .46 .48","none",ink,.25)
        +r(-1.75,.40,.72,.31,.155,blush)+r(1.03,.40,.72,.31,.155,blush)+'</g>'
}

function paint(svg, line, width, soften) {
    // Flat, softly lifted retail tones plus ink contours. The pass keeps every
    // path/transform intact, including exact-model covers and DDR key geometry.
    // Existing outlines and very small contact/fan detail retain their widths.
    var flat=svg.replace(/#([0-9a-fA-F]{6})\b/g,function(value){
        var color=value.toLowerCase(),luma=lightness(color)
        return luma<100?mix(color,"#a3bdd9",soften?.46:.24):luma<205?mix(color,"#f5edf0",soften?.20:.13):mix(color,"#fff8ee",.06)
    })
    // Fan leaves keep their exact contour, count and cap. A flat plastic tone
    // replaces their metallic paint only in this illustrated version.
    var fanPaint={}
    flat.replace(/<linearGradient\b[^>]*\bid="(fan-leaf-[a-z0-9_]+)"[^>]*>([\s\S]*?)<\/linearGradient>/g,function(tag,id,stops){
        var middle=/offset="\.38" stop-color="(#[a-f0-9]{6})"/.exec(stops)
        if(middle)fanPaint[id]=middle[1]
        return tag
    })
    flat=flat.replace(/fill="url\(#(fan-leaf-[a-z0-9_]+)\)"/g,function(value,id){return fanPaint[id]?'fill="'+fanPaint[id]+'"':value})
    return flat.replace(/<(path|rect|circle|polygon)\b([^>]*?)\/>/g,function(tag,kind,attrs){
        if (/\bstroke=/.test(attrs) || /\bfill="(?:none|url\()/.test(attrs)) return tag
        // Dense strips are already schematic; bold outlines would merge them.
        var w=/\bwidth="([0-9.]+)"/.exec(attrs), h=/\bheight="([0-9.]+)"/.exec(attrs)
        if (w && Number(w[1])<.45 || h && Number(h[1])<.34) return tag
        var outline=/\bclass="hardware-fan-blade"/.test(attrs)?.10:width
        return '<'+kind+attrs+' stroke="'+line+'" stroke-width="'+outline+'" stroke-linejoin="round"/>'
    })
}

function geometry(state) {
    return Solid.geometry(state)
}

function cpu(state,c) {
    var out=paint(Solid.cpu(state,c),c.line,.42)
    var y=state.style==="lga_rect"?10.9:11.1
    out+=smile(12,y,1.15,c.line,c.blush)
    return out
}

function gpu(state,c) {
    if (state.style==="gpu_integrated") {
        return paint(Solid.integrated(c),c.line,.34,true)+smile(12,11.1,.94,c.line,c.blush)
    }
    var g=geometry(state),out=paint(Solid.gpu(state,c),c.line,.24,true)
    // Rounded cover ink belongs to the fixed casing. Place expression only in
    // a clear upper cover band, never over sourced rotors or cap markings.
    if (g.centers.length) {
        var gap=g.h
        for (var index=0;index<g.centers.length;index++) {
            var cy=g.fan_y?g.fan_y[index]:g.y+g.h*.51
            var radius=g.radii?g.radii[index]:g.radius
            gap=Math.min(gap,cy-radius-g.y)
        }
        if (gap>.72) {
            var scale=Math.min(.54,(gap-.16)/1.36)
            var faceInk=lightness(c.caseBody)<130?"#fff5e7":c.line
            out+=smile(g.x+g.w*.5,g.y+.11,scale,faceInk,c.blush)
        }
    } else if (state.fan_count!==0) {
        // A missing fan layout remains an abstract covered panel.
        out+=smile(g.x+g.w*.76,g.y+g.h*.48,.68,c.edge,c.blush)
    }
    return out
}

function memory(state,c) {
    var colors=Board.memoryColors(state,Memory.palette(state))
    colors.body=mix(colors.body,"#b6cbe2",.23)
    colors.shade=mix(colors.shade,"#829fba",.23)
    colors.metal=mix(colors.metal,"#fff7e8",.20)
    colors.glass=mix(colors.glass,"#fbefee",.20)
    colors.pcb=mix(colors.pcb,"#a8d3bd",.17)
    colors.gold=c.gold
    if(state.style!=="dimm" && state.style!=="sodimm")
        return paint(Memory.neutral(colors),c.line,.35)+smile(12,11.0,.75,c.line,c.blush)
    var g=Board.geometry(state,Memory.profile(state))
    var out=paint(Memory.board(g,colors)+Memory.enclosure(state,g,colors),c.line,.30)
    if(state.shroud==="bare") {
        var start=g.x+(g.shortForm?.9:1.45),step=g.shortForm?3.2:4.55,w=g.shortForm?2.35:3.25
        out+=smile(start+step+w/2,11.42,g.shortForm?.38:.52,"#f7eee0",c.blush)
    } else {
        out+=smile(g.x+g.w*.5,12.0,.68,lightness(colors.metal)>145?c.line:"#fff5e7",c.blush)
    }
    return out
}

function body(state,rotorCollector) {
    if(!state || ["cpu","gpu","memory"].indexOf(state.kind)<0)return ""
    var c=state.kind==="gpu"?Board.colors(state,palette(state)):palette(state)
    c.fanDesignSeries=state.series_id;c.fanDesignIndex=0
    if(Array.isArray(rotorCollector))c.rotorCollector=rotorCollector
    var out=state.kind==="gpu"?gpu(state,c):state.kind==="memory"?memory(state,c):cpu(state,c)
    if(Array.isArray(rotorCollector))rotorCollector.forEach(function(rotor){
        // Same sampled RPM and direction, same number of retained rotor layers.
        rotor.body=paint(rotor.body,c.line,.24,true)
    })
    return '<g class="hardware-cartoon" stroke-linecap="round" stroke-linejoin="round">'+out+'</g>'
}

function generic(kind,ink,moving) {
    // Quantity/device-category symbols, not claims to identify an installed
    // SSD, network adapter, motherboard, battery or chassis-fan retail model.
    var c=palette({ink:ink}),edge=c.line,soft="#e4edf6",blue="#a8c8e3",green="#afd4c2",pink="#efbdca",gold="#ebcf8a"
    var out="",arrow=""
    if(kind==="cpu")return cpu({style:"chip"},c)
    if(kind==="gpu")return gpu({style:"gpu_neutral",fan_count:-1},c)
    if(["memory","vram","swap"].indexOf(kind)>=0) {
        out=r(3.0,5.2,18,13.6,2.0,green,edge,.65)
            +r(5,7.5,3.5,7.9,.65,"#85b6a2",edge,.45)
            +r(10.25,7.5,3.5,7.9,.65,soft,edge,.45)
            +r(15.5,7.5,3.5,7.9,.65,"#85b6a2",edge,.45)
            +smile(12,10.75,.60,edge,pink)
    } else if(["disk","disk_read","disk_write","storage"].indexOf(kind)>=0) {
        out=r(3.5,4.5,17,15.4,2.15,blue,edge,.65)
            +r(5.5,6.4,13,9.6,1.35,soft,edge,.45)
            +r(6.2,17.4,3.3,1.15,.25,gold,edge,.35)
            +r(10.1,17.4,6.9,1.15,.25,gold,edge,.35)
            +smile(12,10.5,1.07,edge,pink)
        if(kind==="disk_read" || kind==="disk_write") {
            var read=kind==="disk_read"
            arrow=p(read?"M16.8 3.2V8.8M14.7 6.9L16.8 9L18.9 6.9":"M16.8 9V3.4M14.7 5.3L16.8 3.2L18.9 5.3","none",edge,.9)
        }
    } else if(["network","download","upload"].indexOf(kind)>=0) {
        out=r(3,6.4,18,12,2.0,blue,edge,.65)
            +p("M8.1 6.5V4.3H15.9V6.5",soft,edge,.6)
            +r(7.2,8.6,9.6,5.8,.75,soft,edge,.45)
            +p("M8.9 8.8V10.2M11 8.8V10.2M13 8.8V10.2M15.1 8.8V10.2","none",edge,.45)
            +smile(12,11.2,.55,edge,pink)
            +circle(6,16.4,.65,green,edge,.3)+circle(18,16.4,.65,gold,edge,.3)
        if(kind==="download" || kind==="upload") {
            var down=kind==="download"
            arrow=p(down?"M19.7 2.4V6.8M18 5.3L19.7 7L21.4 5.3":"M19.7 7V2.6M18 4.1L19.7 2.4L21.4 4.1","none",edge,.8)
        }
    } else if(kind==="fan") {
        out=r(3.2,3.2,17.6,17.6,3.3,blue,edge,.65)
            +circle(12,12,6.4,soft,edge,.5)
        ;[[5.7,5.7],[18.3,5.7],[5.7,18.3],[18.3,18.3]].forEach(function(pos){out+=circle(pos[0],pos[1],.55,"#d0deec",edge,.25)})
        if(!moving) {
            // Generic decorative fan symbol, independent of physical GPU blades.
            for(var i=0;i<3;i++)out+='<g transform="rotate('+(i*120)+' 12 12)">'+p("M11.3 10.6C8.1 8.7 9.0 5.7 11.3 6.1C14.2 6.4 14.9 8.2 13.0 10.7Z",green,edge,.45)+'</g>'
            out+=circle(12,12,1.95,soft,edge,.4)+smile(12,11.55,.46,edge,pink)
        }
    } else if(kind==="battery") {
        out=r(2.7,6,17.6,12,2.3,green,edge,.65)+r(20.3,9.1,1.5,5.8,.6,green,edge,.55)
            +r(5,8.1,12.6,7.8,1.25,soft,edge,.4)+smile(11.25,10.5,1.04,edge,pink)
    } else if(kind==="power" || kind==="voltage") {
        out=circle(12,12,8.8,soft,edge,.6)
        if(kind==="power")out+=p("M12.9 3.7L6.8 12.8H11L10.1 20.3L17.7 10.1H13.2Z",gold,edge,.55)
        else out+=p("M6.8 8L12 17L17.2 8","none",edge,1.5)+circle(18.5,5.5,1.5,gold,edge,.4)
        out+=r(4.3,13.8,1.8,.6,.3,pink)+r(17.9,13.8,1.8,.6,.3,pink)
    } else if(kind==="frequency") {
        out=r(3.0,4.7,18,14.6,2.3,blue,edge,.65)
            +p("M5.1 12H7.2L9.3 8.5L12.4 15.5L14.5 10.3L16.1 12H18.9","none",edge,1)
            +r(6,17.0,2.0,.55,.25,pink)+r(16,17.0,2.0,.55,.25,pink)
    } else if(kind==="temperature") {
        out=p("M9 14.4V5.5Q9 2.9 12 2.9Q15 2.9 15 5.5V14.4A5.3 5.3 0 1 1 9 14.4Z",soft,edge,.65)
            +p("M12 7.0V16.2","none",pink,1.6)+circle(12,17.6,2.8,pink,edge,.4)
            +p("M16.8 6.0H19M16.8 9.0H18.2M16.8 12H19","none",edge,.6)
            +smile(12,17.0,.55,edge,"#fff4e4")
    } else if(kind==="time") {
        out=circle(12,12,9.0,blue,edge,.65)+circle(12,12,7.0,soft,edge,.4)
            +p("M12 7.0V12L15.5 13.8","none",edge,.85)
            +r(6.3,14.5,1.8,.55,.25,pink)+r(15.9,14.5,1.8,.55,.25,pink)
    } else if(kind==="noise") {
        out=p("M3.0 9H7.0L12.2 5V19L7.0 15H3Z",blue,edge,.65)
            +p("M15 8.0Q18.9 12 15 16M18 5.8Q23.6 12 18 18.2","none",edge,.85)
            +r(5.0,11.0,.55,1.6,.25,edge)+r(8,11,.55,1.6,.25,edge)+r(5.2,13.5,2.8,.55,.25,pink)
    } else {
        // Board/grid/sensors and unknown categories share a neutral controller
        // symbol; no inferred retail motherboard, socket or storage technology.
        out=r(3.0,3.7,18,16.6,2.3,green,edge,.65)
            +r(6.0,6.7,9.0,9.0,1.4,soft,edge,.45)
            +r(17.2,6.7,1.5,5.2,.45,blue,edge,.35)
            +r(17.2,13.4,1.5,3.4,.45,gold,edge,.35)
            +p("M6.2 17.6H14.6M4.5 9.0H6M4.5 12H6M9 5.0V6.7M12.1 5V6.7","none",edge,.45)
            +smile(10.5,10.1,.90,edge,pink)
    }
    return '<g class="hardware-cartoon-category" stroke-linejoin="round" stroke-linecap="round">'+out+arrow+'</g>'
}
