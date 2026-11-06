.pragma library
// Original drawing code: PolyForm Noncommercial 1.0.0. See LICENSE, NOTICE
// and LICENSING.md for scope, retained notices and third-party exceptions.
.import "HardwareSolid.js" as Solid
.import "HardwareMemoryShapes.js" as Memory
.import "HardwareBoardDesigns.js" as Board
.import "HardwareNotebook.js" as Notebook
.import "HardwareNotebookParts.js" as Parts

// Optional illustration treatments of the same reviewed hardware catalog.
// Colour is illustrative, not a claim about factory paint or current lighting.
// Geometry, DDR keys, fan contours and relative directions are never replaced.
// All work is call-local when a retained SVG is built. No clocks, filters,
// runtime I/O, background work, random state or mutable artwork cache.
var styles = ["sticker", "papercut", "inkwash"]

function copy(input) {
    var result={}
    Object.keys(input||{}).forEach(function(key){result[key]=input[key]})
    return result
}
function hex(input,fallback) {
    return typeof input==="string" && /^#[0-9a-fA-F]{6}$/.test(input)?input.toLowerCase():fallback
}
function luma(value) {
    return .2126*parseInt(value.substr(1,2),16)+.7152*parseInt(value.substr(3,2),16)+.0722*parseInt(value.substr(5,2),16)
}
function palette(style,ink) {
    var dark=luma(hex(ink,"#455360"))>140
    if(style==="papercut")return {style:style,edge:dark?"#dfb48d":"#2b485a",deep:"#29485c",mid:"#d39978",paper:"#f3dfbd",blade:"#f3dfbd",gold:"#d39978"}
    if(style==="inkwash")return {style:style,edge:dark?"#c9ddeb":"#3b5874",deep:"#5d879e",mid:"#79a8af",paper:"#abc5cd",blade:dark?"#b8d5df":"#486a86",gold:"#b29873"}
    return {style:"sticker",edge:"#415d60",deep:"#789b9b",mid:"#bdd4c3",paper:"#fff4df",blade:"#fff0d7",gold:"#d6b47e"}
}
function color(value,p) {
    var v=hex(value,"#83949c"),r=parseInt(v.substr(1,2),16),g=parseInt(v.substr(3,2),16),b=parseInt(v.substr(5,2),16)
    var light=luma(v)
    if(p.style==="papercut")return light<92?p.deep:light<181?p.mid:p.paper
    if(p.style==="inkwash") {
        if(r>g*1.12 && r>b*1.08)return "#b58f9f"
        if(r>b*1.16 && g>b*1.06)return p.gold
        return light<110?p.deep:light<188?p.mid:p.paper
    }
    if(r>g*1.14 && r>b*1.10)return "#dfb2a1"
    if(r>b*1.17 && g>b*1.08)return p.gold
    if(b>r*1.12 && b>g*1.03)return light>185?"#d4e5e6":"#abcbd5"
    return light<95?p.deep:light<188?p.mid:p.paper
}
function attributes(text) {
    var result={}
    String(text).replace(/([a-zA-Z_:][\w:.-]*)\s*=\s*"([^"]*)"/g,function(all,key,value){result[key]=value;return all})
    return result
}
function paint(source,p) {
    // Flatten the existing static fan gradient into a retained paper shape.
    // The exact source blade path, transform, hub and linked-tip geometry stay.
    var out=String(source).replace(/<linearGradient\b[^>]*>[\s\S]*?<\/linearGradient>/g,"")
        .replace(/fill="url\(#fan-leaf-[a-z0-9_]+\)"/g,'fill="'+p.blade+'"')
    out=out.replace(/<(path|rect|circle|ellipse|polygon|polyline)\b([^>]*?)\/>/g,function(tag,kind,text){
        var a=attributes(text),cls=a["class"]||"",fill=a.fill,stroke=a.stroke
        if(fill && /^#[0-9a-fA-F]{6}$/.test(fill))fill=color(fill,p)
        if(stroke && /^#[0-9a-fA-F]{6}$/.test(stroke))stroke=p.edge
        if(cls==="hardware-fan-blade")fill=p.blade
        if(cls==="hardware-fan-hub")fill=p.style==="papercut"?p.mid:p.paper
        if(cls==="hardware-fan-cap-mark" && fill && fill!=="none")fill=p.edge
        var result=text
        if(a.fill!==undefined)result=result.replace(/\bfill="[^"]*"/,'fill="'+fill+'"')
        if(a.stroke!==undefined)result=result.replace(/\bstroke="[^"]*"/,'stroke="'+stroke+'"')
        if(p.style==="sticker" && fill && fill!=="none" && a.stroke===undefined) {
            // Tiny contacts and fins remain clean; only large closed pieces get
            // sticker ink. No offset halo can escape the existing icon bounds.
            var w=Number(a.width),h=Number(a.height),tiny=(Number.isFinite(w)&&w<.55)||(Number.isFinite(h)&&h<.38)
            if(!tiny)result+=' stroke="'+p.edge+'" stroke-width="'+(cls==="hardware-fan-blade"?.10:.22)+'" stroke-linejoin="round"'
        }
        return '<'+kind+result+'/>'
    })
    return out
}
function knownRotor(state,index,kind) {
    var colors=Board.colors(state,Solid.palette(state))
    var profile=Notebook.fanProfile(state,colors,index,kind)
    return profile.blades!==null && profile.shape!=="neutral"
}
function rotorGroup(rotor,body) {
    return '<g transform="translate('+rotor.cx+' '+rotor.cy+') scale('+(rotor.radius/rotor.basis)+')">'+body+'</g>'
}
function gpu(state,p,collector) {
    var retained=[],fixed=paint(Solid.body(state,retained),p)
    retained.forEach(function(rotor,index){
        var body=paint(rotor.body,p)
        if(Array.isArray(collector) && knownRotor(state,index,rotor.kind)) {
            var moving=copy(rotor);moving.body=body;collector.push(moving)
        } else fixed+=rotorGroup(rotor,body)
    })
    return fixed
}
function cpuModelKey(input) {return Parts.cpuModelKey(input)}
function cpu(state,p) {
    var packageStyle=Object.prototype.hasOwnProperty.call(Parts.cpuPackage,state.style)?state.style:"chip"
    var pen=copy(state);pen.icon_set="notebook_line"
    // The package front and eight AM5 cutouts come from the same reviewed pen
    // drawing. Recognition marks use only the three bounded catalog strings.
    var out='<path class="variants-cpu-substrate" d="'+Parts.cpuPackage[packageStyle]+'" fill="'+p.deep+'"/>'
        +'<path class="variants-cpu-spreader" d="'+Parts.cpuLid[packageStyle]+'" fill="'+p.paper+'"/>'
        +Parts.cpu(pen,{ink:p.edge,color:false,smile:false})
    return out
}
function inkwash(source,p) {
    // Notebook already bakes clipping into each stroke for Qt SVG. Recolour
    // only: changing stroke width here would violate those transparent holes.
    return String(source).replace(/(stroke|fill)="(#[0-9a-fA-F]{6})"/g,function(all,kind,value){
        return kind+'="'+(value.toLowerCase()==="#455360"?p.edge:color(value,p))+'"'
    })
}
function body(state,collector) {
    if(!state || ["cpu","gpu","memory"].indexOf(state.kind)<0 || styles.indexOf(state.icon_set)<0)return ""
    var selected=state.icon_set,p=palette(selected,state.ink),normalized=copy(state),out=""
    if(selected==="inkwash") {
        normalized.icon_set="notebook_color";normalized.ink="#455360"
        var moving=[],fixed=Notebook.body(normalized,moving)
        out=inkwash(fixed,p)
        moving.forEach(function(rotor){
            var converted=copy(rotor);converted.body=inkwash(rotor.body,p)
            if(Array.isArray(collector))collector.push(converted)
            else out+=rotorGroup(converted,converted.body)
        })
    } else if(state.kind==="gpu")out=gpu(normalized,p,collector)
    else if(state.kind==="cpu")out=cpu(normalized,p)
    else {
        normalized.icon_set="solid"
        out=paint(Memory.body(normalized),p)
    }
    return '<g class="hardware-variants '+selected+'" stroke-linecap="round" stroke-linejoin="round">'+out+'</g>'
}
function generic(kind,ink,moving,style) {
    if(styles.indexOf(style)<0)return ""
    var p=palette(style,ink)
    if(kind==="gpu")return body({kind:"gpu",style:"gpu_neutral",fan_count:-1,ink:ink,icon_set:style})
    // Category symbols never assert an installed retail product. The face-free
    // notebook set covers the established semantic names without new polling.
    var value=Notebook.generic(kind,"#455360",moving,"notebook_color")
    return '<g class="hardware-variants '+style+'">'+(style==="inkwash"?inkwash(value,p):paint(value,p))+'</g>'
}
