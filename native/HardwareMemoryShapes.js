.pragma library
.import "HardwareBoardDesigns.js" as Board

// Original static memory-module miniatures; no logos, text, filters or clocks.
// Case language is sourced in memory_appearance.py. IC blocks and edge contacts
// are schematic, not a diagram of rank, chip count or physical pin count.
// Modern known DDR/form classes use sourced nominal front-view key ratios.
// A diffuser is a physical cover, never a claim that LEDs are currently on.

var brands = ["corsair", "gskill", "kingston", "crucial", "teamgroup", "adata", "unknown"]
var ids = ["corsair_vengeance_lpx", "corsair_vengeance_rgb", "corsair_dominator_platinum",
    "gskill_ripjaws_v", "gskill_trident_z_rgb", "gskill_trident_z_royal", "gskill_flare_x5",
    "kingston_fury_beast", "kingston_fury_renegade", "kingston_valueram_dimm", "kingston_valueram_sodimm",
    "crucial_basics_udimm", "teamgroup_delta_rgb", "teamgroup_vulcan", "adata_lancer_rgb", "adata_spectrix_d60g"]

function hex(value,fallback) {
    return typeof value==="string" && /^#[0-9a-fA-F]{6}$/.test(value) ? value : fallback
}

function mix(a,b,amount) {
    var value="#"
    for(var i=1;i<7;i+=2) {
        var channel=Math.round(parseInt(a.substr(i,2),16)*(1-amount)+parseInt(b.substr(i,2),16)*amount)
        value+=("0"+channel.toString(16)).slice(-2)
    }
    return value
}

function palette(state) {
    var ink=hex(state.ink,"#425265"), accent=hex(state.accent,"#83909e")
    var dark=.2126*parseInt(ink.substr(1,2),16)+.7152*parseInt(ink.substr(3,2),16)+.0722*parseInt(ink.substr(5,2),16)>145
    var soft=state.icon_set==="soft"
    return {outline:state.icon_set==="outline",ink:ink,accent:accent,
        body:mix(soft?(dark?"#9aabb8":"#c2cfd9"):"#7d91a1",accent,soft?.09:.03),
        shade:soft?mix("#697f90",accent,.08):"#4c6578", side:"#344e63",
        metal:soft?"#dce5eb":"#becdd8",light:"#e4ecf2",glass:soft?"#edf2f5":"#d5e2ec",
        chip:dark?"#344652":"#3b505d",pcb:soft?"#7c9c98":"#527e78",gold:"#bba267"}
}

function p(d,fill,c,outlineWidth) {
    return '<path d="'+d+'" fill="'+(c.outline?"none":fill)+'"'
        +(c.outline?' stroke="'+c.ink+'" stroke-width="'+(outlineWidth||.7)+'" stroke-linejoin="round" stroke-linecap="round"':"")+'/>'
}

function r(x,y,w,h,radius,fill,c,outlineWidth) {
    return '<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" rx="'+radius
        +'" fill="'+(c.outline?"none":fill)+'"'
        +(c.outline?' stroke="'+c.ink+'" stroke-width="'+(outlineWidth||.65)+'"':"")+'/>'
}

function identity(state) {
    var id=state.series_id || ""
    return ids.indexOf(id)>=0 && id.split("_")[0]===state.board_vendor ? id : ""
}

function profile(state) {
    var shortForm=state.style==="sodimm", id=identity(state), top=8.7
    if(["corsair_dominator_platinum","gskill_trident_z_royal"].indexOf(id)>=0) top=5.6
    else if(["teamgroup_delta_rgb","adata_spectrix_d60g"].indexOf(id)>=0) top=6.2
    else if(["gskill_ripjaws_v","gskill_trident_z_rgb","adata_lancer_rgb"].indexOf(id)>=0) top=6.8
    else if(id==="corsair_vengeance_rgb" || id==="kingston_fury_renegade") top=7.4
    return {x:shortForm?4.6:2.0,w:shortForm?14.8:20.0,top:top,bottom:16.4,shortForm:shortForm}
}

function board(g,c) {
    if(c.outline) {
        // Preserve the previously selectable Outline verbatim; reviewed
        // mechanical detail belongs to the modern object illustrations.
        var ox=g.x,oe=ox+g.w,okey=ox+g.w*.49,otop=g.shortForm?8.2:9.0
        var old="M"+(ox+.7)+" "+otop+"H"+(oe-.7)+"Q"+oe+" "+otop+" "+oe+" "+(otop+.7)
            +"V11.2H"+(oe-.5)+"V12.2H"+oe+"V16.4H"+(okey+.65)+"V15.35H"+(okey-.65)
            +"V16.4H"+ox+"V12.2H"+(ox+.5)+"V11.2H"+ox+"V"+(otop+.7)+"Q"+ox+" "+otop+" "+(ox+.7)+" "+otop+"Z"
        return p(old,c.pcb,c)+r(ox+.45,16.4,okey-ox-1.1,1.15,.08,c.gold,c,.4)
            +r(okey+.65,16.4,oe-okey-1.1,1.15,.08,c.gold,c,.4)
    }
    var x=g.x,e=x+g.w,key=x+g.w*(typeof c.notchRatio==="number"?c.notchRatio:.49)
    var top=g.shortForm?8.2:9.0
    var bottom=c.outline?16.4:17.55
    var keyHalf=!c.outline && typeof c.notchWidthRatio==="number"?g.w*c.notchWidthRatio/2:.65
    var keyTop=!c.outline && typeof c.notchDepthRatio==="number"?bottom-(bottom-top)*c.notchDepthRatio:15.35
    // A visible lower notch continues through both PCB and the contact strip.
    var body="M"+(x+.7)+" "+top+"H"+(e-.7)+"Q"+e+" "+top+" "+e+" "+(top+.7)
        +"V11.2H"+(e-.5)+"V12.2H"+e+"V"+bottom+"H"+(key+keyHalf)+"V"+keyTop+"H"+(key-keyHalf)
        +"V"+bottom+"H"+x+"V12.2H"+(x+.5)+"V11.2H"+x+"V"+(top+.7)+"Q"+x+" "+top+" "+(x+.7)+" "+top+"Z"
    var result=p(body,c.pcb,c)
    result+=r(x+.45,16.4,key-x-.45-keyHalf,1.15,.04,c.gold,c,.4)
        +r(key+keyHalf,16.4,e-key-.45-keyHalf,1.15,.04,c.gold,c,.4)
    if(!c.outline) {
        // Schematic finger density, not the physical 260/288 pin count.
        for(var index=1;index<32;index++) {
            var at=x+.45+(g.w-.9)*index/32
            if(Math.abs(at-key)>keyHalf+.06) result+=r(at,16.45,.08,1.05,0,c.pcb,c)
        }
    }
    return result
}

function bare(g,c) {
    var w=g.shortForm?2.35:3.25, start=g.x+(g.shortForm?.9:1.45), step=g.shortForm?3.2:4.55
    var result=""
    for(var i=0;i<4;i++) result+=r(start+i*step,10.0,w,4.2,.3,c.chip,c,.5)
    return result
}

function enclosure(state,g,c) {
    var id=identity(state), presentation=state.shroud || state.presentation || "neutral"
    if(g.shortForm) {
        return presentation==="bare" ? bare(g,c)
            : r(5.5,9.2,13,5.8,.65,c.body,c)+r(7.1,10.4,9.8,2.5,.35,c.metal,c)
    }
    switch(id) {
    case "corsair_vengeance_lpx":
        return p("M2 9.5H3.4V8.1H5V9H6.6V7.7H8.1V8.7H9.7V7.7H11.3V8.7H12.8V7.7H14.4V8.7H16V7.7H17.5V9H19V8.1H20.6V9.5H22V15.5H2Z",c.body,c)
            +r(3.2,10.6,17.6,3.4,.4,c.shade,c)
            +r(7.5,11.4,9,1.9,.3,c.metal,c)
    case "corsair_vengeance_rgb":
        return p("M2 9L4.3 7.4H19.7L22 9V15.6H2Z",c.body,c)
            +p("M3 8.3L4.7 6.7H19.3L21 8.3V9.4H3Z",c.glass,c)
            +p("M2 10H6.1L9 15.6H2ZM22 10H17.9L15 15.6H22Z",c.shade,c)
            +r(8,11.1,8,2.5,.4,c.metal,c)
    case "corsair_dominator_platinum":
        var top=r(2.5,6.7,19,8.9,.55,c.body,c)
            +r(2.5,5.6,19,2.1,.4,c.shade,c)
        for(var section=0;section<5;section++) top+=r(3.3+section*3.6,5.85,2.75,.9,.15,c.glass,c,.4)
        return top+p("M3.3 7.7H5V14.8H3.3ZM19 7.7H20.7V14.8H19Z",c.metal,c)
            +r(6.2,9,11.6,5.4,.25,c.shade,c)+r(8.1,10.1,7.8,3.2,.3,c.metal,c)
    case "gskill_ripjaws_v":
        return p("M2 10.1L4 7.4H5V8.7H7.1L8 6.8H10L10.6 8H13.4L14 6.8H16L16.9 8.7H19V7.4H20L22 10.1V15.5H2Z",c.body,c)
            +p("M2 11H7L9 13.8H15L17 11H22V15.5H2Z",c.shade,c)
            +p("M7 9.4H17L15.5 12H8.5Z",c.metal,c)
    case "gskill_trident_z_rgb":
        return p("M2 8.5L5.1 6.8H19.9L22 8.2V15.5H2Z",c.body,c)
            +p("M2.8 7.9L5.2 6.2H19.3L21.1 7.3V8.8H2.8Z",c.glass,c)
            +p("M2 10H10.5L7.8 15.5H2ZM14.1 9.5H22V15.5H11.4Z",c.shade,c)
            +p("M10.5 9.5H14.1L11.4 15.5H7.8Z",c.metal,c)
    case "gskill_trident_z_royal":
        return p("M2 8.1H22V15.5H2Z",c.metal,c)
            +p("M2.3 8.2L3.2 6.5L5.8 7.2L7.4 5.6L10 6.5L12 5.7L14.4 6.6L17 5.6L18.7 7L21 6.4L21.7 8.2Z",c.glass,c)
            +p("M3.2 6.5L5.8 7.2L7.4 5.6L8.1 8.2H4.2ZM12 5.7L14.4 6.6L17 5.6L16 8.2H13Z",c.light,c,.45)
            +p("M2 10.1L9.3 9.1L13.2 14.7H2ZM22 9.5L17.6 10.6L14.9 15.5H22Z",c.body,c)
    case "gskill_flare_x5":
        return p("M2 9.2L4 8.6H20L22 9.2V15.5H2Z",c.body,c)
            +p("M2 11H9L12 14.6H2ZM22 10.2H16L12 14.6H22Z",c.shade,c)
            +r(9.2,10.4,5.6,1.7,.3,c.metal,c)
    case "kingston_fury_beast":
        return p("M2 9.3H4V8.7H7V9.2H9V8H15V9.2H17V8.7H20V9.3H22V15.5H2Z",c.shade,c)
            +p("M2.7 10.2H8.5L10 11.6H14L15.5 10.2H21.3V14.8H2.7Z",c.body,c)
            +p("M8.4 11.6H15.6L14.4 14H9.6Z",c.metal,c)
    case "kingston_fury_renegade":
        return p("M2 9.1L4.1 7.5H19.9L22 9.1V15.5H2Z",c.shade,c)
            +p("M2.6 9.4L4.4 8H19.6L21.4 9.4L15.2 12.2H8.8Z",c.metal,c)
            +p("M2 12H8.8L12 14.5L15.2 12H22V15.5H2Z",c.body,c)
            +p("M10.2 10.4H14L12.5 12.7Z",c.accent,c,.45)
    case "kingston_valueram_dimm":
    case "kingston_valueram_sodimm":
        return bare(g,c)
    case "crucial_basics_udimm":
        // Form is reviewed; the unavailable original photo supplies no case claim.
        return r(4,10.1,16,4.2,.4,c.body,c)+r(7.2,11.1,9.6,2.2,.3,c.metal,c)
    case "teamgroup_delta_rgb":
        return p("M2 9.6L5.8 6.7H17.9L22 8.7V15.5H2Z",c.shade,c)
            +p("M2.5 8.8L6.2 5.9H18.1L21.5 7.7V9.5H3Z",c.glass,c)
            +p("M2 11.1H7.2L12 14.8L16.2 10.3H22V15.5H2Z",c.body,c)
            +p("M7.2 11.1H15.5L12 14.8Z",c.metal,c)
    case "teamgroup_vulcan":
        return p("M2 10L4.1 8.6H19.9L22 10V15.5H2Z",c.body,c)
            +p("M2 10L4.1 8.6H10L14.1 15.5H8.4Z",c.metal,c)
            +p("M14.4 8.6H19.9L22 10V15.5H18.6Z",c.shade,c)
    case "adata_lancer_rgb":
        return p("M2 9.2L4.2 7.3H18L22 9.3V15.5H2Z",c.body,c)
            +p("M3 8.4L5 6.8H17.6L21 8.4V9.3H3Z",c.glass,c)
            +p("M2 10.4H8.2L12.3 15.5H2ZM17.4 9.5H22V15.5H13.2Z",c.shade,c)
            +p("M8.2 10.4H11.3L15.3 15.5H12.3Z",c.metal,c)
    case "adata_spectrix_d60g":
        return p("M2 8.6L5.8 6.1H18.3L22 8.6V15.5H2Z",c.glass,c)
            +p("M2 8.6L8.7 10.6L12 14.6L15.3 10.6L22 8.6V10.5L17 12.1L14.1 15.5H9.9L7 12.1L2 10.5Z",c.shade,c)
            +p("M5.8 6.1H18.3L15.3 10.6H8.7Z",c.light,c)
            +p("M2 12.2L7 13.5L8.5 15.5H2ZM22 12.2L17 13.5L15.5 15.5H22Z",c.metal,c)
    }
    if(presentation==="bare") return bare(g,c)
    // Explicit DIMM form can be known without a reviewed case or lighting type.
    return r(3.5,9.8,17,5.4,.6,c.body,c)+r(7.3,11.3,9.4,2.2,.35,c.metal,c)
}

function neutral(c) {
    // An abstract memory bank symbol: no asserted module form, key or contacts.
    return r(4.5,6.7,15,10.6,1.6,c.body,c)
        +r(6.4,8.6,2.8,6.6,.5,c.shade,c)
        +r(10.6,8.6,2.8,6.6,.5,c.metal,c)
        +r(14.8,8.6,2.8,6.6,.5,c.shade,c)
        +r(8.2,18.4,7.6,.8,.4,c.accent,c,.5)
}

function body(state) {
    if(!state || state.kind!=="memory") return ""
    var c=Board.memoryColors(state,palette(state))
    if(state.style!=="dimm" && state.style!=="sodimm") return neutral(c)
    var g=profile(state), result="",e=g.x+g.w
    if(state.icon_set==="miniature") {
        result='<path d="M'+(g.x+.4)+' 17.8H'+(e+.35)+'L'+(e+.6)+' 18.8H'+(g.x+1.4)+'Z" fill="#233b4d" opacity=".13"/>'
            +p("M"+e+" "+(g.top+.4)+"L"+(e+.65)+" "+(g.top+1)+"V16.5L"+e+" 17.1Z",c.side,c)
    }
    return '<g stroke-linejoin="round" stroke-linecap="round">'+result+board(g,c)+enclosure(state,g,c)+'</g>'
}
