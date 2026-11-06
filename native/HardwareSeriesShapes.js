.pragma library
.import "HardwareSeriesGroupA.js" as GroupA
.import "HardwareSeriesGroupB.js" as GroupB
.import "HardwareSeriesGroupC.js" as GroupC
.import "HardwareSeriesCoreExpansion.js" as Core
.import "HardwareSeriesNvidiaLegacy.js" as NvidiaLegacy
.import "HardwareSeriesRadeonArc.js" as RadeonArc

// Static, original series illustrations, using the representative design
// language sourced in hardware_series.py. These are not factory drawings or
// dimensions shared by every SKU. A series never establishes a cooler/count.
// Coordinates inside face() are normalized only for the non-circular casing;
// callers draw the confirmed circular fans separately, in the 24-unit grid.

var ids = ["asus_dual", "asus_tuf", "asus_rog_strix", "msi_ventus", "msi_suprim",
    "msi_gaming", "gigabyte_aorus", "gigabyte_aero", "gigabyte_windforce", "zotac_solo",
    "sapphire_pulse", "sapphire_nitro", "powercolor_hellhound", "powercolor_red_devil"]
    .concat(GroupA.ids, GroupB.ids, GroupC.ids, Core.ids, NvidiaLegacy.ids, RadeonArc.ids)

function known(state) {
    return !!state && typeof state.series_id === "string"
        && ids.indexOf(state.series_id) >= 0
        && state.series_id.split("_")[0] === state.board_vendor
}

function profile(id) {
    if (GroupA.ids.indexOf(id)>=0) return GroupA.profile(id)
    if (GroupB.ids.indexOf(id)>=0) return GroupB.profile(id)
    if (GroupC.ids.indexOf(id)>=0) return GroupC.profile(id)
    if (Core.ids.indexOf(id)>=0) return Core.profile(id)
    if (NvidiaLegacy.ids.indexOf(id)>=0) return NvidiaLegacy.profile(id)
    if (RadeonArc.ids.indexOf(id)>=0) return RadeonArc.profile(id)
    // Widths and heights for unknown/zero, one, two and three confirmed fans.
    // They are illustration proportions, not measured product dimensions.
    // The last two entries are fan inset and a small whole-layout offset.
    switch (id) {
    case "asus_dual": return [18.8,13.6,19.0,20.7, 9.4,10.4,9.5,8.5, .245,-.10]
    case "asus_tuf": return [19.5,14.5,20.0,21.0, 10.3,11.4,10.2,9.2, .255,.00]
    case "asus_rog_strix": return [19.9,14.7,20.3,21.1, 9.8,10.8,9.7,8.7, .250,.10]
    case "msi_ventus": return [18.7,13.4,19.2,20.6, 9.1,10.0,9.2,8.1, .242,-.05]
    case "msi_suprim": return [19.6,14.8,20.1,20.9, 10.0,11.2,9.9,9.0, .258,.00]
    case "msi_gaming": return [19.3,14.1,19.7,20.8, 9.6,10.6,9.5,8.6, .247,.08]
    case "gigabyte_aorus": return [20.0,15.0,20.4,21.0, 10.7,11.7,10.6,9.6, .260,.00]
    case "gigabyte_aero": return [19.7,14.6,20.2,20.9, 9.7,10.7,9.8,8.8, .252,.00]
    case "gigabyte_windforce": return [18.5,13.0,18.8,20.4, 8.8,9.6,8.7,7.8, .236,-.08]
    case "zotac_solo": return [17.9,12.7,18.3,20.2, 9.5,10.5,9.3,8.3, .250,.00]
    case "sapphire_pulse": return [19.0,13.9,19.4,20.5, 9.9,10.9,9.8,8.9, .253,-.03]
    case "sapphire_nitro": return [19.8,14.9,20.3,21.0, 10.1,11.1,10.0,9.1, .252,.00]
    case "powercolor_hellhound": return [19.2,14.2,19.6,20.7, 9.3,10.3,9.4,8.4, .246,.00]
    case "powercolor_red_devil": return [19.7,14.4,20.0,21.0, 10.2,11.3,10.1,9.3, .256,.05]
    }
    return null
}

function copyGeometry(base) {
    var input = base || {x:3.2,y:7.1,w:18.6,h:9.2,centers:[],radius:0}
    return {x:input.x,y:input.y,w:input.w,h:input.h,
        centers:input.centers ? input.centers.slice() : [],radius:input.radius || 0}
}

function geometry(state, base) {
    if (!known(state)) return copyGeometry(base)
    var spec = profile(state.series_id)
    var count = state.fan_count
    if (count !== 1 && count !== 2 && count !== 3) count = 0
    // The caller's normalized neutral/integrated identity takes precedence.
    if (state.style === "gpu_neutral" || state.style === "gpu_integrated") count = 0
    var w = spec[count], h = spec[4 + count]
    var x = 12.15 - w / 2, y = 11.65 - h / 2
    var centers = [], radius = 0
    if (count === 1) {
        centers.push(x + w / 2 + spec[9])
        radius = Math.min(h * .395, w * .295)
    } else if (count > 1) {
        var inset = count === 3 ? spec[8] - .075 : spec[8]
        var left = x + w * inset + spec[9], right = x + w * (1 - inset) + spec[9]
        var step = (right - left) / (count - 1)
        radius = Math.min(h * .39, step * .44, (left - x) * .86, (x + w - right) * .86)
        for (var index = 0; index < count; index++) centers.push(left + step * index)
    }
    if (state.series_id === "msi_expert" && count === 1) centers[0]=x+w*.75
    if (state.style === "gpu_blower" && count === 1 && spec[9] === 0)
        centers[0]=x+w-4.5
    var radii=centers.map(function(){return radius})
    var fanY=centers.map(function(){return y+h*.51})
    if (state.series_id === "gigabyte_fx5200" && count === 1) radii[0]*=.65
    if (state.series_id === "colorful_advanced" && count === 3)
        radii=[radius*.88,radius*1.10,radius*.88]
    if (state.series_id === "galax_ex_gamer" && count === 3)
        radii=[radius*.94,radius*.94*102/92,radius*.94]
    if (state.series_id === "evga_ftw3" && count === 3) fanY[1]+=h*.08
    var blowers=[]
    if (state.series_id === "acer_bifrost_arc_a770" && count === 2) {
        // Official front view: smaller left turbine, larger right axial fan.
        // The illustration ratio is visual, not a claimed physical diameter.
        radii=[radius*.78,radius]
        blowers=[0]
    }
    return {x:x,y:y,w:w,h:h,centers:centers,radius:radius,radii:radii,fan_y:fanY,blowers:blowers}
}

function p(d, fill) {
    return '<path d="' + d + '" fill="' + fill + '"/>'
}

function r(x,y,w,h,radius,fill) {
    return '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h
        + '" rx="' + radius + '" fill="' + fill + '"/>'
}

function bays(g, colors, type) {
    // Polygonal casing facets around actual fan positions, not extra fans.
    // With unknown cooling there is one neutral panel and no implied openings.
    if (!g.centers.length)
        return p("M14 27H82L89 39V73H18L11 61Z", colors.caseTop)
    var result = ""
    for (var index = 0; index < g.centers.length; index++) {
        var cx = (g.centers[index] - g.x) / g.w * 100
        var rx = g.radius / g.w * 100 + 3.3
        if (type === "bevel") {
            result += p("M"+(cx-rx)+" 26L"+(cx-rx+5)+" 13H"+(cx+rx-5)+"L"+(cx+rx)
                +" 26V76L"+(cx+rx-5)+" 88H"+(cx-rx+5)+"L"+(cx-rx)+" 76Z", colors.caseShade)
            result += p("M"+(cx-rx+5)+" 17H"+(cx+rx-5)+"L"+(cx+rx-1)+" 28H"+(cx-rx+1)+"Z", colors.edge)
        } else {
            result += p("M"+(cx-rx)+" 29L"+(cx-2)+" 15L"+(cx+rx)+" 29V73L"+(cx+2)
                +" 88L"+(cx-rx)+" 73Z", colors.caseTop)
        }
    }
    return result
}

function bridges(g, colors, type) {
    var result = ""
    var points = []
    for (var index = 1; index < g.centers.length; index++)
        points.push(((g.centers[index - 1] + g.centers[index]) / 2 - g.x) / g.w * 100)
    if (!points.length) points.push(50)
    points.forEach(function(at) {
        if (type === "v") {
            result += p("M"+(at-12)+" 7L"+at+" 35L"+(at+12)+" 7H"+(at+6)+"L"+at+" 20L"+(at-6)+" 7Z", colors.metal)
                + p("M"+(at-11)+" 94L"+at+" 69L"+(at+11)+" 94H"+(at+4)+"L"+at+" 83L"+(at-4)+" 94Z", colors.caseShade)
        } else if (type === "slash") {
            result += p("M"+(at-5)+" 6H"+(at+6)+"L"+(at-1)+" 94H"+(at-12)+"Z", colors.caseTop)
        } else {
            result += p("M"+(at-8)+" 5H"+(at+3)+"L"+(at+9)+" 32L"+(at+2)+" 50L"+(at+7)
                +" 74L"+(at-1)+" 96H"+(at-11)+"L"+(at-3)+" 73L"+(at-8)+" 48L"+at+" 29Z", colors.caseTop)
        }
    })
    return result
}

function face(state, g, colors) {
    if (!known(state)) return ""
    var c=colors, result="", id=state.series_id
    if (GroupA.ids.indexOf(id)>=0) result=GroupA.face(state,g,colors)
    else if (GroupB.ids.indexOf(id)>=0) result=GroupB.face(state,g,colors)
    else if (GroupC.ids.indexOf(id)>=0) result=GroupC.face(state,g,colors)
    else if (Core.ids.indexOf(id)>=0) result=Core.face(state,g,colors)
    else if (NvidiaLegacy.ids.indexOf(id)>=0) result=NvidiaLegacy.face(state,g,colors)
    else if (RadeonArc.ids.indexOf(id)>=0) result=RadeonArc.face(state,g,colors)
    else switch (id) {
    case "asus_dual":
        // Asymmetric two-zone enclosure with a stepped shoulder.
        result = p("M0 21L7 6H48L56 0H94L100 14V87L90 100H48L40 94H5L0 82Z",c.caseBody)
            + p("M7 6H48L56 0H94L100 14V27H61L48 39H0V21Z",c.metal)
            + p("M54 4H66L54 97H43Z",c.caseShade)
            + p("M83 29H100V87L90 100H79L86 81Z",c.caseTop)
            + p("M5 78H39L47 94H5L0 82Z",c.caseShade)
            + r(77,7,15,5,1,c.accent)
        break
    case "asus_tuf":
        // Thick armored end caps and broad folded rails.
        result = p("M0 22L10 4H35L40 11H60L65 4H91L100 21V82L90 100H65L60 93H40L35 100H10L0 82Z",c.caseBody)
            + p("M0 22L10 4H21L15 33V72L22 100H10L0 82Z",c.caseShade)
            + p("M80 4H91L100 21V82L90 100H78L85 70V34Z",c.caseShade)
            + p("M11 4H35L40 11H60L65 4H90L80 20H67L60 28H40L33 20H20Z",c.caseTop)
            + p("M12 100H35L40 93H60L65 100H89L79 83H67L60 76H40L33 83H22Z",c.metal)
            + r(6,37,5,24,1,c.accent)
        break
    case "asus_rog_strix":
        // A diagonal continuous armor plane, with unequal angular ends.
        result = p("M0 24L13 2H88L100 15V70L86 100H8L0 85Z",c.caseShade)
            + p("M0 24L13 2H88L100 15L83 42H40L19 77H0Z",c.caseTop)
            + p("M8 100L26 69H68L87 34H100V70L86 100Z",c.caseBody)
            + p("M39 3H53L31 41H17Z",c.metal)
            + p("M67 62H80L58 100H44Z",c.metal)
            + p("M80 6H91L85 16H74Z",c.accent)
        break
    case "msi_ventus":
        // Recessed shoulders and prominent opposed V-shaped connecting bridges.
        result = p("M0 17L8 5H35L42 13H59L66 5H92L100 18V85L92 96H65L59 88H42L35 96H8L0 85Z",c.caseBody)
            + p("M0 17L8 5H24L14 26V74L24 96H8L0 85Z",c.caseShade)
            + p("M78 5H92L100 18V85L92 96H78L88 74V27Z",c.caseShade)
            + bridges(g,c,"v") + r(80,10,12,4,1,c.accent)
        break
    case "msi_suprim":
        // A beveled metal octagon and separate polygonal fan chambers.
        result = p("M0 21L12 0H87L100 20V80L87 100H12L0 80Z",c.caseShade)
            + p("M4 23L14 5H85L96 23V77L85 95H14L4 77Z",c.metal)
            + bays(g,c,"bevel")
            + p("M12 0H87L81 8H18Z",c.edge)
            + p("M12 100H87L81 91H18Z",c.caseTop)
            + r(78,8,12,4,1,c.accent)
        break
    case "msi_gaming":
        // Three stepped exterior sections are styling, not a fan-count claim.
        result = p("M0 25L10 6H30L36 15H64L70 4H91L100 20V78L88 98H68L62 87H39L33 98H9L0 82Z",c.caseShade)
            + p("M0 25L10 6H30L36 15H64L70 4H91L84 24H70L62 34H40L29 24H14L0 47Z",c.caseTop)
            + p("M0 60L14 78H30L40 68H61L70 79H85L100 58V78L88 98H68L62 87H39L33 98H9L0 82Z",c.caseBody)
            + bridges(g,c,"dynamic")
            + p("M4 31L11 20H20L13 31Z",c.accent)
        break
    case "gigabyte_aorus":
        // Broad stepped shoulders and thick wraparound edges.
        result = p("M0 14L14 0H32L37 10H63L68 0H87L100 14V87L87 100H68L63 90H37L32 100H14L0 87Z",c.caseShade)
            + p("M0 14L14 0H32L37 10H63L68 0H87L100 14V30H84L77 20H70L64 28H36L30 20H22L15 30H0Z",c.metal)
            + p("M0 70H15L22 81H30L36 73H64L70 81H77L84 70H100V87L87 100H68L63 90H37L32 100H14L0 87Z",c.caseTop)
            + r(0,30,9,40,2,c.caseBody) + r(91,30,9,40,2,c.caseBody)
            + p("M72 5H85L91 11H77Z",c.accent)
        break
    case "gigabyte_aero":
        // A calm, nearly monolithic metal slab, without armored notches.
        result = r(0,0,100,100,7,c.metal)
            + r(2,3,96,91,5,c.edge)
            + r(2,11,96,79,3,c.metal)
            + r(85,11,13,79,2,c.caseTop)
            + r(88,20,7,32,1,c.caseShade)
            + r(88,66,7,13,1,c.accent)
        break
    case "gigabyte_windforce":
        // Narrow rails and exposed straight airflow space instead of full armor.
        result = p("M0 13H12L18 22H82L88 13H100V87H88L82 78H18L12 87H0Z",c.caseShade)
        if (g.centers.length) {
            result = '<path d="M0 13H12L18 22H82L88 13H100V87H88L82 78H18L12 87H0Z '
                + 'M7 33V67H93V33Z" fill="'+c.caseShade+'" fill-rule="evenodd"/>'
                + bridges(g,c,"slash")
        } else {
            result += r(13,33,74,34,2,c.caseTop)
        }
        result += p("M0 13H12L18 22H82L88 13H100V24H89L83 31H17L11 24H0Z",c.caseTop)
            + p("M0 76H11L17 69H83L89 76H100V87H88L82 78H18L12 87H0Z",c.metal)
            + r(89,30,6,12,1,c.accent)
        break
    case "zotac_solo":
        // A compact, softly chamfered enclosing frame with a wide left return.
        result = p("M0 25Q0 3 20 3H82Q100 3 100 24V77Q100 97 80 97H20Q0 97 0 76Z",c.caseShade)
            + p("M8 27Q8 11 23 11H81Q92 11 92 25V75Q92 89 79 89H23Q8 89 8 74Z",c.caseTop)
            + p("M0 25Q0 3 20 3H29V16H21Q13 16 13 28V72Q13 84 24 84H29V97H20Q0 97 0 76Z",c.metal)
            + r(73,8,13,5,2,c.accent)
        break
    case "sapphire_pulse":
        // Square end blocks and a strong offset two-zone division.
        result = p("M0 7H17V0H82V7H100V93H82V100H17V93H0Z",c.caseBody)
            + r(0,7,17,86,1,c.caseShade) + r(82,7,18,86,1,c.metal)
            + p("M17 0H82V17H52L45 29H17Z",c.caseTop)
            + p("M17 100H82V83H54L47 71H17Z",c.caseShade)
            + p("M48 18H57L49 82H40Z",c.metal)
            + r(89,20,5,24,1,c.accent)
        break
    case "sapphire_nitro":
        // Integrated box frame, a deep center and full-length side beams.
        result = p("M0 15Q0 0 15 0H85Q100 0 100 15V85Q100 100 85 100H15Q0 100 0 85Z",c.caseShade)
            + r(5,17,90,66,5,c.caseBody)
            + p("M0 15Q0 0 15 0H85Q100 0 100 15V24H0Z",c.metal)
            + p("M0 76H100V85Q100 100 85 100H15Q0 100 0 85Z",c.caseTop)
            + r(8,5,84,7,3,c.accent)
            + r(0,24,7,52,2,c.metal) + r(93,24,7,52,2,c.metal)
        break
    case "powercolor_hellhound":
        // One rounded, restrained shroud with a broad connected dark opening.
        result = p("M0 25Q0 8 15 8H85Q100 8 100 25V76Q100 95 81 95H19Q0 95 0 76Z",c.caseBody)
            + p("M6 29Q6 18 19 18H81Q94 18 94 29V71Q94 84 80 84H20Q6 84 6 71Z",
                g.centers.length ? c.disk : c.caseShade)
            + p("M14 8H85Q100 8 100 25V34H94V29Q94 18 81 18H19Q6 18 6 29V34H0V25Q0 8 14 8Z",c.caseTop)
            + r(74,9,12,5,2,c.accent)
        break
    case "powercolor_red_devil":
        // Irregular hard end angles and large interlocking armor facets.
        result = p("M0 31L7 11L23 0H41L48 9H74L84 0L97 14L100 45L95 88L79 100H59L52 91H22L9 100L0 78Z",c.caseShade)
            + p("M7 11L23 0H41L48 9H74L84 0L97 14L91 31H73L65 23H45L36 34H19L0 48V31Z",c.caseTop)
            + p("M0 65L17 77H35L44 67H64L72 79H90L100 58L95 88L79 100H59L52 91H22L9 100L0 78Z",c.caseBody)
            + p("M0 31L7 11L18 5L14 34L8 54L14 87L9 100L0 78Z",c.metal)
            + p("M84 0L97 14L100 45L95 88L83 97L88 70L94 46L85 22Z",c.metal)
            + p("M25 4H37L32 17H20Z",c.accent)
        break
    }
    return '<g class="hardware-series-face '+id+'" transform="translate('+g.x+' '+g.y+') scale('+(g.w/100)+' '+(g.h/100)+')">'
        + result + '</g>'
}
