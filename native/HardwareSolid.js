.pragma library
.import "HardwareSeriesShapes.js" as Series
.import "HardwareFanDesigns.js" as FanDesigns
.import "HardwareBoardDesigns.js" as Board

// Original static object illustrations. The caller supplies normalized,
// allowlisted state and owns SVG wrapping, stable keys, texture caching and
// alpha. No timers, filters, discovery, text or mutable per-frame state.

function palette(state) {
    const ink = state.ink || "#303a48"
    const brightness = .2126 * parseInt(ink.slice(1, 3), 16)
        + .7152 * parseInt(ink.slice(3, 5), 16) + .0722 * parseInt(ink.slice(5, 7), 16)
    const dark = brightness > 140
    return {ink:ink, accent:state.accent || "#81919f", caseTop:dark?"#8b9aa9":"#8593a0",
        caseBody:dark?"#718293":"#738493", caseShade:dark?"#536777":"#566a79",
        rim:dark?"#b2bfcb":"#c2cdd5", disk:"#26323d", blade:dark?"#99acbb":"#a4b5c2",
        hub:"#d3dce3", metal:dark?"#bdc9d3":"#c8d1d8", edge:dark?"#e0e6eb":"#e6ebef",
        pcb:dark?"#50696c":"#4e6969", gold:"#b79e64"}
}

function p(d, fill, opacity, stroke, width) {
    return '<path d="' + d + '" fill="' + (fill || "none") + '"'
        + (opacity === undefined ? "" : ' opacity="' + opacity + '"')
        + (stroke ? ' stroke="' + stroke + '" stroke-width="' + width + '" stroke-linejoin="round" stroke-linecap="round"' : "") + '/>'
}

function r(x, y, width, height, radius, fill, stroke, strokeWidth) {
    return '<rect x="' + x + '" y="' + y + '" width="' + width + '" height="' + height
        + '" rx="' + radius + '" fill="' + fill + '"'
        + (stroke ? ' stroke="' + stroke + '" stroke-width="' + strokeWidth + '"' : "") + '/>'
}

function am5Lid() {
    return "M7.0 5.5H8.8V6.7H10.3V5.5H13.7V6.7H15.2V5.5H17Q18.5 5.5 18.5 7"
        + "V8.8H17.3V10.3H18.5V13.7H17.3V15.2H18.5V17Q18.5 18.5 17 18.5"
        + "H15.2V17.3H13.7V18.5H10.3V17.3H8.8V18.5H7Q5.5 18.5 5.5 17"
        + "V15.2H6.7V13.7H5.5V10.3H6.7V8.8H5.5V7Q5.5 5.5 7 5.5Z"
}

function cpu(state, colors) {
    if (state.style === "lga_rect") {
        return r(5.7, 3.6, 12.6, 16.8, 1.25, colors.pcb)
            + r(7.0, 4.8, 10.0, 14.4, 1.0, colors.metal, colors.caseShade, .45)
            + p("M8 5.3H16M7.5 6V18", "none", .8, colors.edge, .6)
            + p("M8.3 18.3H12.0", "none", .6, colors.caseShade, .55)
            + r(5.9, 17.0, .7, 2.0, .15, colors.accent)
    }
    if (state.style === "am5") {
        return r(4.4, 4.4, 15.2, 15.2, 1.2, colors.pcb)
            + p(am5Lid(), colors.metal, 1, colors.caseShade, .35)
            + p("M7.2 5.9H8.4M10.8 5.9H13.2M15.7 5.9H16.8", "none", .8, colors.edge, .45)
            + r(17.9, 4.5, 1.25, .7, .1, colors.accent)
    }
    let pins = ""
    for (let index = 0; index < 4; index++) {
        const at = 7.1 + 3.25 * index
        pins += "M" + at + " 3.4V5.6M" + at + " 18.4V20.6M3.4 " + at + "H5.6M18.4 " + at + "H20.6"
    }
    return p(pins, "none", 1, colors.caseShade, 1.25)
        + r(5, 5, 14, 14, 1.6, colors.caseBody)
        + r(7.5, 7.5, 9, 9, 1.0, colors.metal)
        + p("M8.1 8H15.9", "none", .8, colors.edge, .6)
        + r(6.0, 17.4, 3, .65, .2, colors.accent)
}

function fan(cx, cy, radius, colors) {
    return FanDesigns.fan(cx,cy,radius,colors,"axial")
}

function turbine(cx, cy, radius, colors) {
    return FanDesigns.fan(cx,cy,radius,colors,"blower")
}

function geometry(state) {
    return Board.geometry(state,Series.geometry(state, baseGeometry(state)))
}

function baseGeometry(state) {
    const count = state.style === "gpu_axial" ? state.fan_count : -1
    if (count === 1) return {x:5.2, y:6.7, w:14.5, h:9.5, centers:[12.45], radius:3.85}
    if (count === 2) return {x:3.0, y:7.1, w:18.9, h:9.2, centers:[7.8,17.1], radius:3.55}
    if (count === 3) return {x:1.9, y:7.6, w:20.7, h:8.4, centers:[5.65,12.25,18.85], radius:2.9}
    return {x:3.2, y:7.1, w:18.6, h:9.2, centers:[], radius:0}
}

function front(state, g, colors) {
    return Board.variantFace(state,g,colors) || (Series.known(state) ? Series.face(state, g, colors)
        : shell(g, family(state), colors) + trim(state, g, colors))
}

function underlay(state, g, colors) {
    if (!Series.known(state)) return ""
    // Open shroud sections expose a heatsink, never an empty white hole.
    let result = r(g.x+.65,g.y+g.h*.18,g.w-1.3,g.h*.66,.25,colors.caseShade)
    for (let index=1; index<9; index++) {
        const x=g.x+.65+(g.w-1.3)*index/9
        result += p("M"+x+" "+(g.y+g.h*.23)+"V"+(g.y+g.h*.78),"none",.35,colors.rim,.18)
    }
    return result
}

function family(state) {
    const id = state.series_id || ""
    if (["asus_tuf","asus_rog_strix","msi_gaming","gigabyte_aorus","powercolor_red_devil"].indexOf(id)>=0) return "armor"
    if (["msi_ventus","msi_suprim","gigabyte_windforce","gigabyte_aero","sapphire_pulse","sapphire_nitro"].indexOf(id)>=0) return "flat"
    return state.shroud === "angular" ? "armor" : state.shroud === "box" ? "flat" : "soft"
}

function shell(g, type, colors) {
    const x=g.x, y=g.y, end=x+g.w, bottom=y+g.h
    if (type === "armor") {
        return p("M"+(x+1.2)+" "+y+"H"+(end-1.5)+"L"+end+" "+(y+1.6)+"V"+(bottom-1.4)
            +"L"+(end-1.3)+" "+bottom+"H"+(x+.7)+"L"+x+" "+(bottom-1.0)+"V"+(y+1.1)+"Z", colors.caseBody)
            + p("M"+(x+1.1)+" "+(y+.6)+"H"+(end-1.8)+"L"+(end-.5)+" "+(y+1.8), "none", 1, colors.caseTop, .75)
    }
    return r(x,y,g.w,g.h,type === "flat" ? .6 : 1.35,colors.caseBody)
        + p("M"+(x+1.4)+" "+(y+.5)+"H"+(end-1.4), "none", .85, colors.caseTop, .7)
}

function trim(state, g, colors) {
    const x=g.x,y=g.y,e=x+g.w,b=y+g.h
    const motifs = {
        asus_dual:"M"+(x+.7)+" "+(y+1.3)+"H"+(x+2.7)+"M"+(e-2.8)+" "+(b-.6)+"H"+(e-1.0),
        asus_tuf:"M"+(x+.6)+" "+(y+1.9)+"L"+(x+2.1)+" "+(y+.5)+"H"+(x+4.2),
        asus_rog_strix:"M"+(e-6.6)+" "+(y+1.1)+"L"+(e-5.4)+" "+(y+.2)+"M"+(e-4.7)+" "+(y+1.1)+"L"+(e-3.5)+" "+(y+.2),
        msi_ventus:"M"+(x+.6)+" "+(y+1.9)+"L"+(x+1.8)+" "+(y+.6)+"H"+(x+3),
        msi_gaming:"M"+(x+g.w*.36)+" "+(y+.3)+"L"+(x+g.w*.45)+" "+(y+1)+"H"+(x+g.w*.58),
        msi_suprim:"M"+(x+2)+" "+(y+.65)+"H"+(e-2)+"M"+(x+3)+" "+(b-.55)+"H"+(e-3),
        gigabyte_windforce:"M"+(x+1)+" "+(y+1.4)+"L"+(x+1.8)+" "+(y+.5)+"M"+(x+2.4)+" "+(y+1.4)+"L"+(x+3.2)+" "+(y+.5),
        gigabyte_aorus:"M"+(x+.6)+" "+(y+1.5)+"L"+(x+2)+" "+(y+.4)+"H"+(x+4)+"M"+(e-4)+" "+(y+.4)+"H"+(e-2)+"L"+(e-.6)+" "+(y+1.5),
        gigabyte_aero:"M"+(x+1)+" "+(y+.65)+"H"+(e-1),
        zotac_solo:"M"+(x+1)+" "+(y+1.7)+"Q"+(x+1)+" "+(y+.7)+" "+(x+2.4)+" "+(y+.7),
        sapphire_pulse:"M"+(x+.7)+" "+(y+.6)+"H"+(x+3.4)+"M"+(e-3.4)+" "+(b-.5)+"H"+(e-.7),
        sapphire_nitro:"M"+(x+1.5)+" "+(y+.65)+"H"+(e-1.5),
        powercolor_hellhound:"M"+(x+.9)+" "+(y+1.2)+"L"+(x+2.8)+" "+(y+.5),
        powercolor_red_devil:"M"+(x+.8)+" "+(y+1.4)+"L"+(x+1.9)+" "+(y+.3)+"M"+(x+2.5)+" "+(y+1.4)+"L"+(x+3.6)+" "+(y+.3)
    }
    const d=motifs[state.series_id] || "M"+(e-3.3)+" "+(y+.65)+"H"+(e-1.3)
    return p(d,"none",.9,colors.accent,state.series_id === "sapphire_nitro" ? .8 : .65)
}

function integrated(colors) {
    return r(5.5,5.5,13,13,1.55,colors.pcb)
        + r(8,8,8,8,.9,colors.metal)
        + p("M8.6 8.5H15.4", "none", .75, colors.edge, .6)
        + r(6.2,16.8,2.2,.65,.15,colors.accent)
}

function gpu(state, colors) {
    if (state.style === "gpu_integrated") return integrated(colors)
    const g=geometry(state), x=g.x, y=g.y, end=x+g.w, bottom=y+g.h
    let result = Board.base(state,g,colors) + underlay(state,g,colors) + front(state,g,colors)
    const cy=y+g.h*.51
    if (state.style === "gpu_blower" && state.fan_count === 1) {
        result += turbine(g.centers.length?g.centers[0]:end-4.5,cy,Math.min(3.55,g.h*.37),colors)
            + p("M"+(x+2)+" "+(y+2.4)+"H"+(x+7.5)+"M"+(x+2)+" "+(y+4.1)+"H"+(x+7.5)
                +"M"+(x+2)+" "+(y+5.8)+"H"+(x+7.5),"none",.7,colors.disk,.85)
    } else if (g.centers.length) {
        g.centers.forEach(function(cx,index){result+=(g.blowers && g.blowers.indexOf(index)>=0?turbine:fan)(cx,g.fan_y?g.fan_y[index]:cy,g.radii?g.radii[index]:g.radius,colors)})
    } else if (state.fan_count !== 0) {
        // A backplate-like vented panel, never a made-up cooler assembly.
        result += p("M"+(x+3.6)+" "+(y+2.5)+"L"+(x+2.5)+" "+(y+6.6)
            +"M"+(x+5.9)+" "+(y+2.5)+"L"+(x+4.8)+" "+(y+6.6)
            +"M"+(x+8.2)+" "+(y+2.5)+"L"+(x+7.1)+" "+(y+6.6),"none",.65,colors.caseShade,1.0)
        result += p("M"+(end-6)+" "+(y+2.8)+"H"+(end-2.1)+"V"+(y+6.2)+"H"+(end-5.2)+"Z",colors.caseShade,.52)
    }
    return result+Board.finish(state,g,colors)
}

function body(state, rotorCollector) {
    const normalized=state || ({})
    const colors=normalized.kind==="gpu"?Board.colors(normalized,palette(normalized)):palette(normalized)
    colors.fanDesignSeries=normalized.series_id
    colors.fanDesignIndex=0
    // Optional call-local collection; ordinary static output is unchanged.
    if (Array.isArray(rotorCollector)) colors.rotorCollector=rotorCollector
    return normalized.kind === "gpu" ? gpu(normalized,colors) : cpu(normalized,colors)
}
