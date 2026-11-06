.pragma library
.import "HardwareSeriesShapes.js" as Series

// Original soft, two-tone hardware miniatures on the 24-unit icon grid.
// Series accents illustrate a design language, never an exact product or color.
// Only a confirmed cooler/count may produce fans. Everything is static geometry.

function mix(a, b, amount) {
    var result = "#"
    for (var offset = 1; offset < 7; offset += 2) {
        var value = Math.round(parseInt(a.substr(offset, 2), 16) * (1 - amount)
            + parseInt(b.substr(offset, 2), 16) * amount)
        result += ("0" + value.toString(16)).slice(-2)
    }
    return result
}

function palette(state) {
    var ink = /^#[0-9a-fA-F]{6}$/.test(state.ink || "") ? state.ink : "#526274"
    var accent = /^#[0-9a-fA-F]{6}$/.test(state.accent || "") ? state.accent : "#6b91ab"
    var lightInk = (parseInt(ink.substr(1, 2), 16) * .2126
        + parseInt(ink.substr(3, 2), 16) * .7152
        + parseInt(ink.substr(5, 2), 16) * .0722) > 150
    return {
        edge: mix(ink, lightInk ? "#80919f" : "#718394", .24),
        base: mix(lightInk ? "#596b79" : "#aebdc9", accent, .11),
        face: mix(lightInk ? "#b9c9d3" : "#e1e9ed", accent, .07),
        shade: mix(lightInk ? "#8093a1" : "#c5d1d9", accent, .10),
        well: mix(lightInk ? "#25313b" : "#465868", accent, .08),
        blade: lightInk ? "#bacbd5" : "#d8e3e9",
        hub: lightInk ? "#e0e8ed" : "#f3f6f8",
        accent: mix(accent, lightInk ? "#c5d4df" : "#7e94a4", .22),
        gold: lightInk ? "#bca76e" : "#b5a06a"
    }
}

function rect(x, y, w, h, radius, fill, stroke, width) {
    return '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h
        + '" rx="' + radius + '" fill="' + fill + '"'
        + (stroke ? ' stroke="' + stroke + '" stroke-width="' + (width || .55) + '"' : '') + '/>'
}

function path(d, fill, stroke, width) {
    return '<path d="' + d + '" fill="' + fill + '"'
        + (stroke ? ' stroke="' + stroke + '" stroke-width="' + (width || .55) + '"' : '') + '/>'
}

function circle(x, y, r, fill, stroke, width, cssClass) {
    return '<circle' + (cssClass ? ' class="' + cssClass + '"' : '')
        + ' cx="' + x + '" cy="' + y + '" r="' + r + '" fill="' + fill + '"'
        + (stroke ? ' stroke="' + stroke + '" stroke-width="' + (width || .5) + '"' : '') + '/>'
}

function cpu(style, p) {
    if (style === "lga_rect") {
        // A long, solid heat spreader rather than a square generic processor.
        return rect(5, 2.8, 14, 18.4, 2, p.base, p.edge, .65)
            + rect(6.25, 4, 11.5, 16, 1.45, p.shade)
            + rect(6.25, 4, 11.5, 14.9, 1.45, p.face, p.edge, .5)
            + path("M8 5.4H15.8L14.6 6.4H8Z", p.hub)
            + rect(8.4, 17.1, 4.1, .8, .4, p.accent)
            + path("M5.6 18.6H6.8V19.8H5.6Z", p.gold)
    }
    if (style === "am5") {
        // Two recesses on every edge retain the recognizable AM5 lid silhouette.
        var lid = "M7.2 5.1H8.9V6.45H10.3V5.1H13.7V6.45H15.1V5.1H16.8"
            + "Q18.9 5.1 18.9 7.2V8.9H17.55V10.3H18.9V13.7H17.55V15.1H18.9V16.8"
            + "Q18.9 18.9 16.8 18.9H15.1V17.55H13.7V18.9H10.3V17.55H8.9V18.9H7.2"
            + "Q5.1 18.9 5.1 16.8V15.1H6.45V13.7H5.1V10.3H6.45V8.9H5.1V7.2Q5.1 5.1 7.2 5.1Z"
        return rect(3.3, 3.3, 17.4, 17.4, 2.1, p.base, p.edge, .65)
            + rect(4.05, 4.05, 15.9, 15.9, 1.6, p.shade)
            + path(lid, p.face, p.edge, .55)
            + rect(8.1, 8.1, 7.8, 7.8, 1.05, p.hub)
            + rect(9.5, 14.4, 5, .8, .4, p.accent)
            + path("M18.5 3.8H20.2V5.5Z", p.gold)
    }
    var pins = ""
    for (var index = 0; index < 3; index++) {
        var v = 7.4 + index * 4.6
        pins += rect(v - .6, 2.1, 1.2, 2.3, .4, p.base)
            + rect(v - .6, 19.6, 1.2, 2.3, .4, p.base)
            + rect(2.1, v - .6, 2.3, 1.2, .4, p.base)
            + rect(19.6, v - .6, 2.3, 1.2, .4, p.base)
    }
    return pins + rect(4.1, 4.1, 15.8, 15.8, 2.35, p.base, p.edge, .65)
        + rect(5.5, 5.5, 13, 13, 1.9, p.shade)
        + rect(5.5, 5.5, 13, 11.9, 1.9, p.face)
        + rect(8.3, 8.3, 7.4, 7.4, 1.25, p.hub)
        + rect(9.4, 14.2, 5.2, .9, .45, p.accent)
}

function fan(cx, cy, radius, p) {
    var result = '<g transform="translate(' + cx + ' ' + cy + ') scale(' + (radius / 3.1) + ')">'
        + circle(0, 0, 3.1, p.well, p.base, .35)
    var rotating = ""
    // Five separated, filled blades: no nested rings, linked loops or gear teeth.
    var blade = "M-.33-.49C-1.12-.81-1.86-1.91-1.22-2.39"
        + "C-.52-2.95.54-2.50.64-1.86C.70-1.30.16-.86.32-.47Z"
    for (var angle = 0; angle < 360; angle += 72) {
        rotating += '<path d="' + blade + '" transform="rotate(' + angle + ')" fill="' + p.blade + '"/>'
    }
    rotating += circle(0, 0, .74, p.hub, null, null, "hardware-fan-hub")
        + circle(0, 0, .22, p.base)
    if (p.rotorCollector) {
        p.rotorCollector.push({cx:cx,cy:cy,radius:radius,kind:"axial",basis:3.1,body:rotating})
        return result + '</g>'
    }
    return result + rotating + '</g>'
}

function turbine(cx, cy, radius, p) {
    var result='<g class="hardware-blower" transform="translate('+cx+' '+cy+') scale('+(radius/3.1)+')">'
        +circle(0,0,3.1,p.well,p.base,.35)
    var rotating=""
    for(var angle=0;angle<360;angle+=36)
        rotating+='<path d="M.75-1.06L1.44-2.39L1.84-2.13L1.14-.75Z" transform="rotate('+angle+')" fill="'+p.blade+'"/>'
    rotating+=circle(0,0,1.13,p.hub,null,null,"hardware-fan-hub")
    if(p.rotorCollector) {
        p.rotorCollector.push({cx:cx,cy:cy,radius:radius,kind:"blower",basis:3.1,body:rotating})
        return result+'</g>'
    }
    return result+rotating+'</g>'
}

function series(state) {
    var id = state.series_id || ""
    // A series token cannot independently establish a board manufacturer.
    return id.split("_")[0] === state.board_vendor ? id : ""
}

function shell(x, y, w, h, state, p) {
    var id = series(state)
    var angular = state.shroud === "angular" || id === "asus_tuf" || id === "asus_rog_strix"
        || id === "msi_gaming" || id === "msi_suprim" || id === "powercolor_red_devil"
    var box = state.shroud === "box" || id === "gigabyte_aero" || id === "sapphire_pulse"
    var r = box ? .7 : 1.55
    var shape = angular
        ? path("M" + (x + 1.4) + " " + y + "H" + (x + w - 1.4) + "L" + (x + w) + " " + (y + 1.4)
            + "V" + (y + h - 1.25) + "L" + (x + w - 1.25) + " " + (y + h)
            + "H" + (x + 1.25) + "L" + x + " " + (y + h - 1.25) + "V" + (y + 1.4) + "Z", p.face, p.edge, .6)
        : rect(x, y, w, h, r, p.face, p.edge, .6)
    // A broad lower side plane and a tiny gold contact are the only edge details.
    var result = rect(x + .25, y + .6, w - .5, h + .45, r, p.base, p.edge, .5) + shape
        + rect(x + 2, y + h + 1, Math.min(4.3, w * .27), .8, .15, p.gold)
        + rect(x - 1.1, y + .3, .85, h + 1, .3, p.base, p.edge, .45)
    var end = x + w
    if (id === "asus_tuf") {
        result += path("M" + (x + .9) + " " + (y + 1.75) + "V" + (y + .8) + "H" + (x + 3.3)
            + "L" + (x + 4.3) + " " + (y + 1.75) + "Z", p.accent)
            + path("M" + (end - 4) + " " + (y + h - .7) + "H" + (end - 1) + "V" + (y + h - 1.5)
                + "H" + (end - 3.2) + "Z", p.base)
    } else if (id === "asus_rog_strix" || id === "msi_gaming") {
        result += path("M" + (end - 5.3) + " " + (y + .7) + "H" + (end - 2) + "L" + (end - 3) + " "
            + (y + 1.65) + "H" + (end - 6.3) + "Z", p.accent)
    } else if (id === "msi_suprim" || id === "powercolor_red_devil") {
        result += path("M" + (x + 1.9) + " " + (y + .65) + "H" + (x + 5.9) + "L" + (x + 4.9)
            + " " + (y + 1.65) + "H" + (x + 1) + "Z", p.accent)
            + path("M" + (end - 1) + " " + (y + h - 2) + "L" + (end - 3.5) + " " + (y + h - .65)
                + "H" + (end - 1) + "Z", p.shade)
    } else if (id === "sapphire_nitro") {
        result += rect(x + 1.25, y + .65, w - 2.5, .8, .4, p.accent)
    } else if (id === "gigabyte_aorus") {
        // Corner lighting language, independent of the actual cooler openings.
        result += path("M" + (end - 4.2) + " " + (y + .65) + "H" + (end - 1.65) + "Q" + (end - .65)
            + " " + (y + .65) + " " + (end - .65) + " " + (y + 1.65) + "V" + (y + 2.5)
            + "H" + (end - 1.45) + "V" + (y + 1.65) + "H" + (end - 4.2) + "Z", p.accent)
    } else if (id === "asus_dual" || id === "msi_ventus" || id === "sapphire_pulse") {
        result += path("M" + (x + 1) + " " + (y + .7) + "H" + (x + 4.8) + "L" + (x + 4)
            + " " + (y + 1.45) + "H" + (x + 1) + "Z", p.accent)
    } else {
        result += rect(end - Math.min(5.1, w * .35) - 1, y + .7, Math.min(5.1, w * .35), .8, .4, p.accent)
    }
    return result
}

function integrated(p) {
    return rect(4.2, 5.2, 15.6, 13.6, 2.25, p.base, p.edge, .6)
        + rect(6.25, 7.25, 11.5, 9.5, 1.45, p.face)
        + rect(8.2, 8.8, 7.6, 6.4, 1, p.well)
        + rect(9.2, 9.8, 5.6, 4.4, .6, p.shade)
        + rect(5.7, 18.6, 3.7, .8, .25, p.gold)
        + rect(15.1, 6.1, 3.2, .8, .4, p.accent)
}

function gpu(state, p) {
    if (state.style === "gpu_integrated") return integrated(p)
    var count = state.style === "gpu_neutral" ? -1 : state.fan_count
    if (count !== 0 && count !== 1 && count !== 2 && count !== 3) count = -1
    if (Series.known(state)) return seriesGpu(state, p, count)
    if (count < 0) {
        // Unknown cooling: a quiet backplate with rectangular insets, never fans.
        return shell(3, 6.15, 19.1, 10.2, state, p)
            + rect(4.45, 8.65, 10, 5.4, 1.1, p.shade)
            + path("M5.6 9.65H12.8L11.85 10.6H5.6Z", p.face)
            + rect(16, 9.2, 3.9, 1, .45, p.base)
            + rect(16, 11.15, 3.9, 1, .45, p.base)
            + rect(16, 13.1, 3.9, 1, .45, p.base)
    }
    if (count === 0) {
        return shell(3, 6.15, 19.1, 10.2, state, p)
            + rect(5, 8.6, 15.2, 5.8, 1, p.shade)
            + rect(6, 9.45, 13.2, .7, .3, p.base)
            + rect(6, 11.15, 13.2, .7, .3, p.base)
            + rect(6, 12.85, 13.2, .7, .3, p.base)
    }
    if (state.style === "gpu_blower" && count === 1) {
        return shell(3, 6.15, 19.1, 10.2, state, p)
            + rect(4.5, 9.5, 7.2, 4.2, 1.2, p.shade)
            + rect(5.4, 10.4, 5, .65, .3, p.base)
            + rect(5.4, 12.1, 5, .65, .3, p.base)
            + turbine(16.4, 11.5, 3.6, p)
    }
    if (count === 1)
        return shell(6.1, 4.9, 13.1, 12.1, state, p) + fan(12.65, 11.2, 4.35, p)
    if (count === 2)
        return shell(2.8, 6.05, 19.5, 10.3, state, p)
            + fan(8.05, 11.4, 3.65, p) + fan(17.05, 11.4, 3.65, p)
    return shell(2, 7.0, 20.5, 8.6, state, p)
        + fan(5.8, 11.45, 2.72, p) + fan(12.25, 11.45, 2.72, p) + fan(18.7, 11.45, 2.72, p)
}

function seriesGpu(state, p, count) {
    var base = count === 1 ? {x:6.1,y:4.9,w:13.1,h:12.1,centers:[12.65],radius:4.35}
        : count === 2 ? {x:2.8,y:6.05,w:19.5,h:10.3,centers:[8.05,17.05],radius:3.65}
        : count === 3 ? {x:2,y:7,w:20.5,h:8.6,centers:[5.8,12.25,18.7],radius:2.72}
        : {x:3,y:6.15,w:19.1,h:10.2,centers:[],radius:0}
    var g = Series.geometry(state, base)
    var colors = {caseBody:p.face,caseTop:p.hub,caseShade:p.shade,disk:p.well,
        rim:p.base,metal:p.face,ink:p.edge,accent:p.accent,edge:p.hub,gold:p.gold,pcb:p.base}
    var result = rect(g.x+.2,g.y+.7,g.w-.4,g.h,.8,p.base,p.edge,.45)
        + rect(g.x-1.05,g.y+.3,.85,g.h+.7,.25,p.base,p.edge,.4)
        + rect(g.x+g.w*.27,g.y+g.h+.7,g.w*.18,.7,.12,p.gold)
        + rect(g.x+.65,g.y+g.h*.18,g.w-1.3,g.h*.66,.3,p.shade)
        + Series.face(state,g,colors)
    var cy = g.y+g.h*.51
    if (state.style === "gpu_blower" && count === 1)
        return result + turbine(g.centers.length?g.centers[0]:g.x+g.w-4.5,cy,Math.min(3.4,g.h*.37),p)
    if (g.centers.length) {
        g.centers.forEach(function(x,index){result += (g.blowers && g.blowers.indexOf(index)>=0?turbine:fan)(x,g.fan_y?g.fan_y[index]:cy,g.radii?g.radii[index]:g.radius,p)})
    } else if (state.fan_count !== 0) {
        // Unknown cooling retains a neutral vented panel, never fan openings.
        result += rect(g.x+g.w*.14,g.y+g.h*.26,g.w*.66,g.h*.48,.7,p.shade)
            + path("M"+(g.x+g.w*.22)+" "+(g.y+g.h*.42)+"H"+(g.x+g.w*.68),"none",p.base,.75)
    }
    return result
}

function body(state, rotorCollector) {
    if (!state || (state.kind !== "cpu" && state.kind !== "gpu")) return ""
    var p = palette(state)
    if (Array.isArray(rotorCollector)) p.rotorCollector=rotorCollector
    return '<g stroke-linejoin="round" stroke-linecap="round">'
        + (state.kind === "cpu" ? cpu(state.style, p) : gpu(state, p)) + '</g>'
}
