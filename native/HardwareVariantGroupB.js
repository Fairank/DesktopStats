.pragma library

// Exact-version exterior studies. No timers, queries, text, logos or live RGB.
// The caller draws all rotors and PCB contacts. These are external covers only.
function p(d,fill,stroke,width) {
    return '<path d="'+d+'" fill="'+fill+'"'+(stroke?' stroke="'+stroke+'" stroke-width="'+width+'" stroke-linejoin="round"':'')+'/>'
}
function r(x,y,w,h,rad,fill,stroke,width) {
    return '<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" rx="'+rad+'" fill="'+fill+'"'+(stroke?' stroke="'+stroke+'" stroke-width="'+width+'"':'')+'/>'
}
function copy(g) {
    var out={};Object.keys(g).forEach(function(k){out[k]=Array.isArray(g[k])?g[k].slice():g[k]});return out
}
function geometry(recipe,state,g) {
    var memoryTops={b_beast_rgb:6.0,b_renegade_rgb:5.5,b_valueram_kit:9.0,
        b_delta_white:4.95,b_vulcan_red:8.6,b_lancer_white_single:6.6,b_d60g_kit:5.0}
    if(Object.prototype.hasOwnProperty.call(memoryTops,recipe)) {
        var m=copy(g);m.top=memoryTops[recipe];return m
    }
    if(['b_taichi7900_white','b_taichi9070_white_lcd','b_inno4070_white','b_inno4070_white_stealth','b_biostar7600_base','b_biostar7600_oc'].indexOf(recipe)<0)return null
    var out=copy(g),triple=recipe.indexOf('b_taichi')===0
    out.x=triple?1.8:2.8;out.w=triple?20.8:19.0
    out.h=triple?8.3:9.0;out.y=11.65-out.h/2
    var biostar=recipe==='b_biostar7600_base'||recipe==='b_biostar7600_oc'
    if(biostar){out.x=2.6;out.w=19.1;out.h=9.2;out.y=11.65-out.h/2}
    out.centers=triple?[out.x+out.w*.17,out.x+out.w*.50,out.x+out.w*.83]:[out.x+out.w*.25,out.x+out.w*.75]
    out.radius=triple?3.02:biostar?4.0:3.55
    out.radii=triple?[out.radius,recipe==='b_taichi7900_white'?out.radius*100/110:out.radius,out.radius]:[out.radius,out.radius]
    out.fan_y=out.centers.map(function(){return out.y+out.h*.51});out.blowers=[]
    return out
}
function gpuWrap(recipe,g,body) {
    return '<g class="hardware-variant-face '+recipe+'" transform="translate('+g.x+' '+g.y+') scale('+(g.w/100)+' '+(g.h/100)+')">'+body+'</g>'
}
function bays(g,c) {
    var out=''
    for(var i=0;i<g.centers.length;i++) {
        var x=(g.centers[i]-g.x)/g.w*100,y=((g.fan_y?g.fan_y[i]:g.y+g.h*.51)-g.y)/g.h*100
        var radius=g.radii?g.radii[i]:g.radius
        out+='<ellipse cx="'+x+'" cy="'+y+'" rx="'+((radius+.10)/g.w*100)+'" ry="'+((radius+.10)/g.h*100)+'" fill="#35424c" stroke="'+c.metal+'" stroke-width=".7"/>'
    }
    return out
}
function taichi(recipe,g,c) {
    var newer=recipe==='b_taichi9070_white_lcd'
    var out=p('M2 0H98L100 6V94L98 100H2L0 94V6Z',c.caseBody)
    if(newer) {
        out+=p('M2 1H30L34 12H66L70 1H97L100 12L93 19L82 10H74L70 18H30L26 10H18L7 19L0 12Z',c.caseTop)
            +p('M0 90L7 80L18 90H26L30 83H70L74 90H82L93 80L100 90L97 100H70L66 93H34L30 100H3Z',c.caseTop)
            +p('M30 16L34 8H66L70 16L68 22H32ZM30 84L34 92H66L70 84L68 78H32Z',c.rim)
            // The real LCD sits on the top edge. A closed, unlit panel contains
            // no invented telemetry and does not become a fourth front fan.
            +r(77,-5.4,18.5,7.8,1.1,c.caseTop,c.rim,.5)+r(79,-4,14.5,4.6,.6,'#344754')
    } else {
        out+=p('M2 1H30L33 10H67L70 1H98L95 10H76L70 16H30L24 10H5Z',c.caseTop)
            +p('M2 99H30L33 90H67L70 99H98L95 90H76L70 84H30L24 90H5Z',c.caseTop)
            +p('M28 21L35 13H65L72 21L68 27H32ZM28 79L35 87H65L72 79L68 73H32Z',c.metal)
    }
    out+=bays(g,c)
    // Gold printed accents are on the outside of the white shroud.
    out+=p('M29 29L34 20H38M62 20H66L71 29M29 71L34 80H38M62 80H66L71 71','none','#b99b67',.65)
        +p('M3 5H21L25 10M75 10L79 5H97M3 95H21L25 90M75 90L79 95H97','none',c.rim,.65)
    return gpuWrap(recipe,g,out)
}
function inno(recipe,g,c) {
    var out=p('M1 3H97L100 10V90L97 97H1L0 94V6Z',c.caseBody)
        +p('M1 3H49L51 97H1L0 94V6Z',c.caseTop)
        +p('M49 3H97L100 10V90L97 97H51Z',c.metal)
        +p('M1 3H49L51 97M50 3H97L100 10M51 97H97L100 90','none',c.rim,.7)
    // The STEALTH version retains this front. Its real rear connector cover is
    // drawn separately by back(); no top connector is fabricated on its face.
    out+=bays(g,c)
    for(var i=0;i<4;i++) {
        var sx=i%2?95:54,sy=i<2?9:91
        out+='<circle cx="'+sx+'" cy="'+sy+'" r="1.2" fill="#74838d"/>'
    }
    return gpuWrap(recipe,g,out)
}
function memoryWrap(recipe,body) {return '<g class="hardware-variant-memory '+recipe+'">'+body+'</g>'}
function memory(recipe,g,c) {
    var out='',glass='#d8e0e4',dark=c.shade||'#44515c'
    switch(recipe) {
    case 'b_beast_rgb':
        out=p('M2 8.0L2.6 7.0H7L7.5 7.4H12.8L13.2 6.0H17.3L18.2 6.5H21.2L22 8.2V15.8H2Z',c.body)
            +p('M2.6 7.0H7L7.5 7.4H12.8L13.2 6H17.3L18.2 6.5H21.2L21.5 7.2H18L17 6.9H13.7L13.4 8H7.3L6.8 7.6H2.6Z',glass)
            +p('M3 14.8L11.5 9.2L11 11L5 15.8H3ZM12 13.9H20.3L21 15.4H10.3ZM13.4 9.1L12.6 12H13.3L14 9.1Z',dark)
            +p('M14.8 9.3L14.1 11.7M16 9.4L15.3 11.8M17.2 9.7L16.6 12.0','none',c.metal,.22)
        break
    case 'b_renegade_rgb':
        out=p('M2 6.2H3L4.1 5.5L7.2 6.2H16.8L19.9 5.5L21 6.2H22V15.8H2Z',dark)
            +p('M2.5 6.2H3L4.1 5.5L7.2 6.2H16.8L19.9 5.5L21 6.2H21.5V7.0H17L16.4 7.6H7.6L7 7H2.5Z',glass)
            +p('M2 7.2H4.6L8.4 10.8L7.8 12.3L9.4 14H8.5L6.8 12.7L4.6 9.4H3.4L6.4 13.6H5.0L2 10.0Z',c.metal)
            +p('M22 7.2H19.4L15.6 10.8L16.2 12.3L14.6 14H15.5L17.2 12.7L19.4 9.4H20.6L17.6 13.6H19L22 10Z',c.metal)
            +p('M8.4 8H15.6L14.4 10L15.1 12L13.8 13.4H10.2L8.9 12L9.6 10Z',c.body)
        break
    case 'b_valueram_kit':
        // Schematic packages deliberately do not promise rank or chip count.
        for(var ic=0;ic<4;ic++)out+=r(3.4+ic*4.55,10,3.25,4.2,.23,c.chip||'#36434a')
        break
    case 'b_delta_white':
        out=p('M1.2 7.0L5 5.0L8.6 6.1L12 6.7L18.5 5.1L22.8 6.6L22.1 15.7L14.0 16L12 15.5L10 16L1.9 15.7Z',c.body)
            +p('M1.2 7L5 5L8.6 6.1L12 6.7L18.5 5.1L22.8 6.6L22.6 7.5L18.4 6.1L12 7.7L8.5 7.2L5.1 6.1L1.4 8.1Z',glass)
            +p('M2.8 9.8L8.3 11.1L12 11.5L15.7 10.9L21.3 9.3L20.8 14.8L14.2 15.4L12 14.8L9.8 15.4L3.2 14.8Z',c.light)
            +p('M3.2 9.1L8.1 10.4M15.9 10.1L21 8.7M3.4 14.2L9.7 14.9L12 14.3L14.3 14.9L20.5 14.2','none',c.rim||'#a4b1ba',.18)
        break
    case 'b_vulcan_red':
        out=p('M1.5 8.6H7.7V8.9H15.1V8.6H22.5L21.7 15.6H14.5L12 14.8L9.5 15.6H2.3Z',c.body)
            +p('M2 9.2L4.2 11.6L5.3 10.8L9.4 13.4L12 14.2L14.6 13.4L18.7 10.8L19.8 11.6L22 9.2','none',dark,.25)
            +p('M3.4 12.1L8.3 14.9H3ZM20.6 12.1L15.7 14.9H21Z',dark)
        break
    case 'b_lancer_white_single':
        out=p('M2 6.6H22V15.9H2Z',c.body)
            +p('M2 6.6H18L2 15.1Z',c.light)
            +p('M6 6.6H16.4L13.3 9.1Z',glass,'#b6c3cb',.16)
            +p('M2.7 8.4L5.4 6.9M2.7 9.6L7.7 6.9M2.7 10.8L9.6 7.0M2.7 12L11.1 7.6M2.7 13.2L11.3 8.6M2.7 14.4L11.1 9.8','none','#a8b9c4',.15)
            +p('M2.3 15.5H21.7','none',c.metal,.2)
        break
    case 'b_d60g_kit':
        out=p('M2 7.1L3.1 5.0L12 5.6L20.9 5L22 7.1V15.8H2Z',glass)
            +p('M3.1 5L8.1 9.3L2 7.1ZM20.9 5L15.9 9.3L22 7.1ZM2 13.3L8.3 11.9L5.4 15.8H2ZM22 13.3L15.7 11.9L18.6 15.8H22Z',c.light)
            +p('M2 7.3L8.4 9.4L12 10.5L15.6 9.4L22 7.3V9.2L15.7 11.6L12 12.7L8.3 11.6L2 9.2Z',c.metal)
            +p('M2 9.2L8.3 11.6L12 12.7L15.7 11.6L22 9.2V10.1L16 12.3L12 13.5L8 12.3L2 10.1Z',dark)
            +p('M3.3 5.4L8.4 9.4M20.7 5.4L15.6 9.4M5.4 15.4L8.3 12.2M18.6 15.4L15.7 12.2','none','#b5c1cb',.18)
        break
    default:return ''
    }
    return memoryWrap(recipe,out)
}
function face(recipe,g,c,state) {
    if(recipe==='b_taichi7900_white'||recipe==='b_taichi9070_white_lcd')return taichi(recipe,g,c)
    if(recipe==='b_inno4070_white'||recipe==='b_inno4070_white_stealth')return inno(recipe,g,c)
    if(recipe==='b_biostar7600_base') {
        // VA7606RM81: softly rounded ends, small middle shoulder steps and
        // shallow upper/lower relief. Two open wells, not connected tip rings.
        var body=p('M5 1H31L34 3H66L69 1H95Q100 1 100 6V94Q100 99 95 99H66L64 97H36L34 99H5Q0 99 0 94V6Q0 1 5 1Z',c.caseShade)
            +p('M4 9Q26 6 33 10H65Q73 6 96 9M4 91H31L36 87H67L72 91H96','none',c.rim,.65)
            +p('M7 5H29L33 8H67L71 5H93M7 95H30L35 91H67L73 95H93','none',c.caseBody,.8)
        return gpuWrap(recipe,g,body+bays(g,c))
    }
    if(recipe==='b_biostar7600_oc') {
        // VA76S6RM81 OC has a separately reviewed angular/faceted front.
        var body=p('M5 2H96L100 7V94L96 99H5L0 95V8Z',c.caseShade)
            +p('M0 28L20 2H44L34 14H13L0 39Z',c.caseBody)
            +p('M59 2H96L100 7V48L86 26H73Z',c.caseBody)
            +p('M0 58L17 80H36L42 99H5L0 95Z',c.caseBody)
            +p('M64 85H84L100 70V94L96 99H56Z',c.caseBody)
            +p('M4 28L17 12H35M66 9H92L96 15M5 72L20 91H36M65 93H88L96 82','none',c.rim,.48)
        return gpuWrap(recipe,g,body+bays(g,c))
    }
    return memory(recipe,g,c)
}
function back(recipe,g,c,state) {
    if(recipe!=='b_inno_stealth_back')return ''
    // Official rear view: white plate, open GPU mounting window and right
    // triangular exhaust framework. The small closed hatch covers rear 8-pin.
    var out=r(1,3,98,94,1.2,c.caseBody||c.body)
        +r(27,25,22,49,1.0,'#283640')
        +p('M26 22H23V76H26M50 22H53V76H50','none',c.metal,.8)
        +p('M65 14H95V86H65Z','#394750')
        +p('M65 14H95L84 30L95 56L82 70L95 86H65L78 66L69 45L80 25Z',c.caseTop||c.light)
        +r(64,37,12,37,1.8,c.caseTop||c.light,c.rim||c.metal,.7)
        +p('M65 44V66M74 44V66','none',c.rim||c.metal,.5)
    for(var i=0;i<4;i++)out+='<circle cx="'+(i%2?49:27)+'" cy="'+(i<2?21:79)+'" r="1.8" fill="#46545d"/>'
    for(var fin=0;fin<8;fin++)out+=p('M'+(66+fin*3.5)+' 16V84','none','#a2b0b8',.35)
    // Re-cover hatch after the exhaust fin strokes.
    out+=r(64,37,12,37,1.8,c.caseTop||c.light,c.rim||c.metal,.7)
    return gpuWrap(recipe,g,out)
}
