.pragma library
.import "HardwareSolid.js" as Solid
.import "HardwareMiniature.js" as Miniature
.import "HardwareSoft.js" as Soft
.import "HardwareCartoon.js" as Cartoon
.import "HardwareSketch.js" as Sketch
.import "HardwareNotebook.js" as Notebook
.import "HardwareVariants.js" as Variants
.import "HardwareSeriesShapes.js" as SeriesCatalog
.import "HardwareMemoryShapes.js" as Memory
.import "HardwareBoardDesigns.js" as Board

// Original simplified hardware drawings, not manufacturer logos or a claim to
// reproduce a product photograph. Geometry uses the existing 24-unit icon grid.
// No mutable cache, polling, external resources or frame work. Notebook CPU
// marks use bounded catalog text; arbitrary hardware names never enter SVG.

var vendors = ["intel", "amd", "nvidia", "unknown"]
var boards = ["asus", "msi", "gigabyte", "zotac", "sapphire", "powercolor", "asrock",
    "pny", "palit", "gainward", "galax", "inno3d", "colorful", "xfx", "evga", "leadtek",
    "maxsun", "yeston", "biostar", "sparkle", "acer", "intel", "amd", "nvidia", "unknown"]
var shrouds = ["neutral", "angular", "soft", "box", "reference"]
var seriesIds = SeriesCatalog.ids

function choice(value, allowed, fallback) {
    if (typeof value !== "string" || value.length > 40) return fallback
    const text = value.trim().toLowerCase()
    return allowed.indexOf(text) >= 0 ? text : fallback
}

function hex(value, fallback) {
    if (value && typeof value.r === "number" && typeof value.g === "number" && typeof value.b === "number") {
        if (![value.r, value.g, value.b].every(Number.isFinite)) return fallback
        return "#" + [value.r, value.g, value.b].map(function (channel) {
            return Math.round(Math.max(0, Math.min(1, channel)) * 255).toString(16).padStart(2, "0")
        }).join("")
    }
    if (typeof value !== "string") return fallback
    if (/^#[0-9a-fA-F]{6}$/.test(value)) return value.toLowerCase()
    if (/^#[0-9a-fA-F]{3}$/.test(value))
        return "#" + value.slice(1).split("").map(function (digit) { return digit + digit }).join("")
    return fallback
}

function key(appearance, ink) {
    const input = appearance && typeof appearance === "object" && !Array.isArray(appearance) ? appearance : ({})
    const kind = choice(input.kind, ["cpu", "gpu", "memory"], "cpu")
    const vendor = choice(input.vendor, vendors, "unknown")
    const board = choice(input.board_vendor, kind === "memory" ? Memory.brands : boards, "unknown")
    const styles = kind === "cpu" ? ["chip", "lga_rect", "am5"]
        : kind === "memory" ? ["memory_neutral", "dimm", "sodimm"]
        : ["gpu_neutral", "gpu_axial", "gpu_blower", "gpu_hybrid", "gpu_integrated"]
    const style = choice(input.style, styles, kind === "cpu" ? "chip" : kind === "memory" ? "memory_neutral" : "gpu_neutral")
    // A neutral family never asserts a cooler. Counts are used only after an
    // explicit axial/blower match; string/boolean/out-of-range counts stay unknown.
    const physical = typeof input.fan_count === "number" && Number.isInteger(input.fan_count)
        && input.fan_count >= 0 && input.fan_count <= 4 ? input.fan_count : -1
    // Python None can arrive as undefined through QVariantMap. Both nullish
    // forms mean an unknown total; neither invalid strings nor booleans do.
    const visible = typeof input.visible_fan_count === "number" && Number.isInteger(input.visible_fan_count)
        && input.visible_fan_count >= 0 && input.visible_fan_count <= 3
        && (physical >= input.visible_fan_count || input.fan_count == null && input.confidence === "model")
        ? input.visible_fan_count : physical <= 3 ? physical : -1
    const count = kind === "memory" ? -1 : style === "gpu_integrated" ? 0
        : style === "gpu_neutral" ? -1
        : visible
    const allowedSeries = kind === "memory" ? Memory.ids : seriesIds
    const shroud = choice(input.shroud, kind === "memory" ? ["neutral", "bare", "low", "spreader", "rgb"] : shrouds, "neutral")
    let series = kind !== "cpu" ? choice(input.series_id, allowedSeries, "") : ""
    if (series && series.split("_")[0] !== board) series = ""
    const requestedMotif = choice(input.motif, allowedSeries, series)
    const motif = requestedMotif === series ? series : ""
    if (!motif) series = ""
    const defaults = {intel: "#2479b5", amd: "#c65b56", nvidia: "#729b42", unknown: "#77818f"}
    const parts = [kind, vendor, board, style, count, shroud,
        hex(input.accent, defaults[vendor]), hex(ink, "#69788c"), series, motif,
        choice(input.icon_set, ["outline", "solid", "miniature", "soft", "cartoon", "sketch",
            "notebook_line", "notebook_color", "notebook_smile", "sticker", "papercut", "inkwash"], "outline")]
    // Original Outline keys and art stay byte-stable. Exact exterior details
    // require an independently guarded model identity, including on old cards.
    const model=kind==="cpu" && (parts[10].indexOf("notebook_")===0 || Variants.styles.indexOf(parts[10])>=0)
        ? Notebook.cpuModelKey({kind:kind,id:input.id,style:style,vendor:vendor,confidence:input.confidence})
        : parts[10]!=="outline"?Board.modelKey({kind:kind,series_id:series,id:input.id,confidence:input.confidence}):""
    if(model)parts.push(model)
    return parts.join("|")
}

function inputFromParts(parts) {
    return {kind:parts[0],vendor:parts[1],board_vendor:parts[2],style:parts[3],
        fan_count:Number(parts[4]),shroud:parts[5],accent:parts[6],series_id:parts[8],motif:parts[9],icon_set:parts[10],
        id:parts[11]||"",confidence:parts.length===12?"model":""}
}

function path(d, ink, width, opacity) {
    return '<path d="' + d + '" fill="none" stroke="' + ink + '" stroke-width="'
        + (width === undefined ? 1.25 : width) + '" opacity="' + (opacity === undefined ? 1 : opacity) + '"/>'
}

function rect(x, y, width, height, radius, ink, fillOpacity, strokeWidth) {
    return '<rect x="' + x + '" y="' + y + '" width="' + width + '" height="' + height
        + '" rx="' + radius + '" fill="' + ink + '" fill-opacity="' + fillOpacity
        + '" stroke="' + ink + '" stroke-width="' + (strokeWidth === undefined ? 1.25 : strokeWidth) + '"/>'
}

function cpu(style, ink, accent) {
    if (style === "lga_rect") {
        return rect(5.1, 3.8, 13.8, 16.4, 1.7, ink, .035, 1.05)
            + rect(7.0, 5.0, 10.0, 14.0, 1.25, ink, .085, 1.25)
            + path("M9 7.1H15M9 16.9H12.4", ink, .85, .45)
            + path("M6.3 6.4V8M17.7 16V17.6", accent, 1.2, .95)
            + '<path d="M5.8 18.4h1.1v.8H5.8z" fill="' + accent + '" opacity=".7"/>'
    }
    if (style === "am5") {
        // Two edge notches per side keep the AM5 eight-cutout silhouette.
        const lid = "M7 5.3H8.8V6.6H10.3V5.3H13.7V6.6H15.2V5.3H17"
            + "Q18.7 5.3 18.7 7V8.8H17.4V10.3H18.7V13.7H17.4V15.2H18.7V17"
            + "Q18.7 18.7 17 18.7H15.2V17.4H13.7V18.7H10.3V17.4H8.8V18.7H7"
            + "Q5.3 18.7 5.3 17V15.2H6.6V13.7H5.3V10.3H6.6V8.8H5.3V7Q5.3 5.3 7 5.3Z"
        return rect(4.2, 4.2, 15.6, 15.6, 1.6, ink, .035, 1.0)
            + '<path d="' + lid + '" fill="' + ink + '" fill-opacity=".09" stroke="' + ink + '" stroke-width="1.15"/>'
            + rect(8.6, 8.6, 6.8, 6.8, .8, ink, .035, .7)
            + path("M17.9 4.3H19.7V6.1", accent, 1.25, .95)
    }
    let pins = ""
    for (let index = 0; index < 4; index++) {
        const p = 7.2 + index * 3.2
        pins += "M" + p + " 2.7V4.7M" + p + " 19.3V21.3M2.7 " + p + "H4.7M19.3 " + p + "H21.3"
    }
    return path(pins, ink, 1.2, .8) + rect(4.8, 4.8, 14.4, 14.4, 1.8, ink, .045)
        + rect(8, 8, 8, 8, 1, ink, .07, 1.05) + path("M9.5 17.5H14.5", accent, 1.35, .9)
}

function fan(cx, cy, radius, ink) {
    const scale = radius / 3
    let result = '<g transform="translate(' + cx + ' ' + cy + ') scale(' + scale + ')">'
        + '<circle r="3" fill="none" stroke="' + ink + '" stroke-width="1.0"/>'
    for (let rotation = 0; rotation < 360; rotation += 120) {
        result += '<path d="M-.32-.48C-.88-1.02-1.10-2.10-.30-2.36C.45-2.62 1.19-2.12 1.42-1.72'
            + 'C.75-1.82.40-.99.38-.48" transform="rotate(' + rotation + ')" fill="none" stroke="'
            + ink + '" stroke-width=".7" opacity=".85"/>'
    }
    return result + '<circle r=".51" fill="' + ink + '"/></g>'
}

function boardMark(board, accent, shroud) {
    const marks = {
        asus: "M4.9 6.6H7.1M17 15.1H19.2",
        msi: "M4.6 7.2L5.5 6.4H7M17.8 15.2L19.3 13.8",
        gigabyte: "M4.4 8V6.4H7.2M18 15.1H19.6",
        zotac: "M4.4 7L5.3 6.4H7M18 15.1L19.4 14.3",
        sapphire: "M4.5 7Q5.4 6.3 7.1 6.5M17.6 15.0H19.4",
        powercolor: "M4.5 8.1V6.5H6.5M17.7 15.1H19.5V13.4",
        asrock: "M4.5 7.6L5.6 6.5M5.9 7.6L7 6.5",
        pny: "M4.5 6.5H7.2M18.3 14V15.2",
        palit: "M4.6 6.5H6.3M5.4 7.6H7.2",
        gainward: "M4.5 6.4H7.2M4.5 6.4V7.8",
        galax: "M4.5 7.2L5.8 6.4L7.1 7.2",
        inno3d: "M4.5 7.5L5.2 6.5M5.7 7.5L6.4 6.5M6.9 7.5L7.6 6.5",
        colorful: "M4.5 6.5H5.3M6 6.5H6.8M7.5 6.5H8.3"
    }
    return path(marks[board] || "M4.8 6.5H7.2", accent, shroud === "angular" ? 1.05 : .95, .9)
}

function seriesShell(motif, fallback) {
    if (["asus_dual", "zotac_solo", "powercolor_hellhound"].indexOf(motif) >= 0) return "soft"
    if (["asus_tuf", "asus_rog_strix", "msi_gaming", "gigabyte_aorus", "powercolor_red_devil"].indexOf(motif) >= 0) return "angular"
    if (["msi_ventus", "msi_suprim", "gigabyte_windforce", "gigabyte_aero", "sapphire_pulse", "sapphire_nitro"].indexOf(motif) >= 0) return "box"
    return fallback
}

function seriesTrim(motif, ink, accent) {
    // Small geometric cues from the cooler family; no printed logos, text,
    // lighting claims or exact paint simulation. They do not imply fan count.
    const trims = {
        asus_dual: ["M4.8 6.5H7.2M4.8 7.5H6.6M17.3 15.2H19.3", "M8.5 15.2H15.2"],
        asus_tuf: ["M4.7 7.1L6.2 5.7H9.2M15.2 15.7H18.2L20.0 13.9", "M10.6 5.7H13.4"],
        asus_rog_strix: ["M8.1 6.8L9.8 5.5M10.6 6.8L12.3 5.5M13.1 6.8L14.8 5.5", "M4.7 15.3L7.2 14.5M16.7 15.3H19.5"],
        msi_ventus: ["M4.4 8L5.5 6.3H7.4M17.3 15.3H19L20 13.8", "M8.8 6.3H14.5"],
        msi_gaming: ["M8.4 5.7L10.7 6.7H13.4L15.7 5.7", "M4.4 7.5L5.7 6.4M18.4 15.1L19.7 13.8"],
        msi_suprim: ["M6 6.4H18M8 15.3H16", "M4.4 7.8L5.5 6.4M18.7 15.3L20 13.9"],
        gigabyte_windforce: ["M4.6 7.5L5.4 6.5M6 7.5L6.8 6.5M17.7 15.1H19.5", "M9 6.1H15.2"],
        gigabyte_aorus: ["M4.7 7.4L6.5 5.6H9M15 5.6H17.9L20 7.5", "M20.2 9.6V12.2M9.6 15.4H14.4"],
        gigabyte_aero: ["M4.8 6.5H19.3M4.8 15.2H19.3", "M18.4 7.3H19.3"],
        zotac_solo: ["M5.2 7.6Q5.6 6.4 7.2 6.4M17.6 15.1Q19 15.1 19.4 13.6", "M7.9 15.3H11.2"],
        sapphire_pulse: ["M4.8 6.5H8.2M15.5 15.2H19.5", "M4.8 15.2H7.2M17.5 6.5H19.4"],
        sapphire_nitro: ["M5.3 6.5H19", "M4.5 8V13.8M19.7 8V13.8M6 15.2H18.2"],
        powercolor_hellhound: ["M4.6 7.2L6.8 6.4M17.6 15.1L19.6 14.3", "M8 6.2H10M14.3 15.5H16.1"],
        powercolor_red_devil: ["M4.6 7.1L5.7 5.9M6.3 7.1L7.4 5.9M8 7.1L9.1 5.9", "M16 15.4H19.3V13.4"]
    }
    const trim = trims[motif]
    if (!trim) return ""
    return path(trim[0], accent, .95, .95) + path(trim[1], ink, .7, .44)
}

function gpu(style, count, shroud, board, ink, accent, motif) {
    if (style === "gpu_integrated") {
        return rect(4.2, 6.2, 15.6, 10.6, 2, ink, .045)
            + rect(8.3, 8.4, 7.4, 6.2, .9, ink, .075, 1)
            + path("M7.2 17V19M10.4 17V19M13.6 17V19M16.8 17V19", ink, 1.1, .75)
            + path("M6.1 7H8.2", accent, 1.1, .95)
    }
    shroud = seriesShell(motif, shroud)
    let result = path("M2.1 4.4V18.2H4.0", ink, 1.3)
        + path("M7.7 17.2V18.8H16.3V17.2M10.1 17.2V18.8M13.1 17.2V18.8", ink, 1.0, .85)
    if (shroud === "angular") {
        result += '<path d="M4.4 5.4H18.8L21.1 7.4V14.5L19.4 16.3H4.1L2.9 15.1V6.9Z"'
            + ' fill="' + ink + '" fill-opacity=".045" stroke="' + ink + '" stroke-width="1.25"/>'
    } else {
        result += rect(3.1, 5.5, 18.0, 10.8, shroud === "soft" ? 2.4 : shroud === "box" ? .9 : 1.55,
                       ink, .045, 1.25)
    }
    if (motif) result += seriesTrim(motif, ink, accent)
    if (style === "gpu_blower" && count === 1) {
        result += fan(16.9, 10.95, 3.4, ink)
        result += path("M5.3 8.1H10.9M5.3 10H10.9M5.3 11.9H10.9M5.3 13.8H10.9", ink, .85, .55)
    } else if (count > 0 && style === "gpu_axial") {
        const positions = count === 1 ? [12.1] : count === 2 ? [7.9, 16.1] : [6.4, 12.1, 17.8]
        // Leave an actual gap between three fan rings at 18px. Touching rings
        // would read as a chain instead of three independent cooler fans.
        const radius = count === 1 ? 3.9 : count === 2 ? 3.35 : 2.15
        positions.forEach(function (x) { result += fan(x, 10.95, radius, ink) })
    } else {
        // Unknown fan count is intentionally a fin stack, with no fan circles.
        result += path("M5.7 8.2V13.6M8.2 8.2V13.6M10.7 8.2V13.6M13.2 8.2V13.6M15.7 8.2V13.6M18.2 8.2V13.6",
                       ink, 1.0, .6)
        result += path("M5.7 14.8H18.2", ink, .75, .4)
    }
    return result + (motif ? "" : boardMark(board, accent, shroud))
}

function source(geometryKey) {
    const parts = typeof geometryKey === "string" ? geometryKey.split("|") : []
    if (parts.length !== 11 && parts.length !== 12) return source(key({}, "#69788c"))
    // Validate public input again; no untrusted text is inserted into XML.
    const canonical = key(inputFromParts(parts), parts[7])
    if (canonical !== geometryKey) return source(canonical)
    const ink = parts[7], accent = parts[6]
    const outlineBody = parts[10] === "outline" && parts[0] !== "memory" ? (parts[0] === "cpu" ? cpu(parts[3], ink, accent)
        : gpu(parts[3], Number(parts[4]), parts[5], parts[2], ink, accent, parts[9])) : ""
    const state = {kind:parts[0],vendor:parts[1],board_vendor:parts[2],style:parts[3],
        fan_count:Number(parts[4]),shroud:parts[5],accent:accent,ink:ink,series_id:parts[9],icon_set:parts[10],model_id:parts[11]||""}
    const body = Variants.styles.indexOf(parts[10])>=0 ? Variants.body(state)
        : parts[10].indexOf("notebook_")===0 ? Notebook.body(state)
        : parts[10] === "sketch" ? Sketch.body(state)
        : parts[10] === "cartoon" ? Cartoon.body(state)
        : parts[0] === "memory" ? Memory.body(state) : parts[10] === "solid" ? Solid.body(state)
        : parts[10] === "miniature" ? Miniature.body(state)
        : parts[10] === "soft" ? Soft.body(state)
        : outlineBody
    const svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">'
        + '<g stroke-linecap="round" stroke-linejoin="round">' + body + '</g></svg>'
    return "data:image/svg+xml;utf8," + encodeURIComponent(svg)
}

function layers(geometryKey) {
    const parts = typeof geometryKey === "string" ? geometryKey.split("|") : []
    if (parts.length !== 11 && parts.length !== 12) return {baseSource:source(key({}, "#69788c")),rotors:[]}
    // This public API accepts only the same canonical, allowlisted fields as
    // source(). No SVG or caller-supplied descriptor body is parsed or trusted.
    const canonical = key(inputFromParts(parts), parts[7])
    if (canonical !== geometryKey) return layers(canonical)
    const count = Number(parts[4])
    if (parts[0] !== "gpu" || ["solid","miniature","soft","cartoon","sketch",
            "notebook_line","notebook_color","notebook_smile","sticker","papercut","inkwash"].indexOf(parts[10]) < 0
            || ["gpu_axial","gpu_blower","gpu_hybrid"].indexOf(parts[3]) < 0
            || [1,2,3].indexOf(count) < 0)
        return {baseSource:source(canonical),rotors:[]}

    const state = {kind:parts[0],vendor:parts[1],board_vendor:parts[2],style:parts[3],
        fan_count:count,shroud:parts[5],accent:parts[6],ink:parts[7],series_id:parts[9],icon_set:parts[10],model_id:parts[11]||""}
    // One normal style body pass supplies fixed casing/discs and final fan
    // coordinates. The collector is local, including all per-style offsets and
    // each fan's reviewed radius/type. No complete-card regeneration per frame.
    const collector = []
    const body = Variants.styles.indexOf(parts[10])>=0 ? Variants.body(state,collector)
        : parts[10].indexOf("notebook_")===0 ? Notebook.body(state,collector)
        : parts[10] === "sketch" ? Sketch.body(state,collector)
        : parts[10] === "cartoon" ? Cartoon.body(state,collector)
        : parts[10] === "solid" ? Solid.body(state,collector)
        : parts[10] === "miniature" ? Miniature.body(state,collector)
        : Soft.body(state,collector)
    const baseSvg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">'
        + '<g stroke-linecap="round" stroke-linejoin="round">' + body + '</g></svg>'
    const rotors = collector.map(function(rotor) {
        // Every small image has a local origin and identical six-unit box.
        // Normalize legacy collector bases inside the static sprite.
        const scaled = rotor.basis === 3 ? rotor.body
            : '<g transform="scale(' + (3 / rotor.basis) + ')">' + rotor.body + '</g>'
        const svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-3 -3 6 6" width="6" height="6">'
            + '<g stroke-linecap="round" stroke-linejoin="round">' + scaled + '</g></svg>'
        return {cx:rotor.cx,cy:rotor.cy,radius:rotor.radius,kind:rotor.kind,
            direction:rotor.direction===-1?-1:1,
            source:"data:image/svg+xml;utf8," + encodeURIComponent(svg)}
    })
    return {baseSource:"data:image/svg+xml;utf8," + encodeURIComponent(baseSvg),rotors:rotors}
}

// Generic quantity/device symbols deliberately carry no retail identity.
function genericSource(kind, ink, moving, style) {
    const body = Variants.styles.indexOf(style)>=0 ? Variants.generic(kind, hex(ink,"#69788c"), moving===true, style)
        : ["notebook_line","notebook_color","notebook_smile"].indexOf(style)>=0
        ? Notebook.generic(kind, hex(ink,"#69788c"), moving === true, style)
        : style === "sketch" ? Sketch.generic(kind, hex(ink,"#69788c"), moving === true)
        : Cartoon.generic(kind, hex(ink,"#69788c"), moving === true)
    if (!body) return ""
    return "data:image/svg+xml;utf8," + encodeURIComponent(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">'
        + '<g stroke-linecap="round" stroke-linejoin="round">' + body + '</g></svg>')
}
