.pragma library

// Source-reviewed exact-edition exteriors. These are original simplified vector
// studies, not photographs, manufacturer logos or mechanical drawings. Mesh
// density, curves, fan inset and perspective are illustration estimates. The
// shared renderer owns the ROUND fans, shallow depth, brackets and contacts.
// Rear accessories are separate recipes; a supplied skin is never assumed fitted.
// No imports, I/O, caches, clocks, extra effects or frame-dependent geometry.

function p(d,fill,stroke,width,opacity) {
    return '<path d="'+d+'" fill="'+(fill||'none')+'"'
        +(stroke?' stroke="'+stroke+'" stroke-width="'+width+'"':'')
        +(opacity===undefined?'':' opacity="'+opacity+'"')+'/>'
}
function r(x,y,w,h,radius,fill,stroke,width) {
    return '<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" rx="'+radius+'" fill="'+fill+'"'
        +(stroke?' stroke="'+stroke+'" stroke-width="'+width+'"':'')+'/>'
}
function placed(recipe,g,body) {
    return '<g class="hardware-variant-face '+recipe+'" transform="translate('+g.x+' '+g.y+') scale('+(g.w/100)+' '+(g.h/100)+')">'+body+'</g>'
}
function copy(g) {
    var result={}
    Object.keys(g).forEach(function(key){result[key]=Array.isArray(g[key])?g[key].slice():g[key]})
    return result
}

function geometry(recipe,state,g) {
    if(!state || state.kind!=="gpu" || state.style!=="gpu_axial")return null
    if((recipe==="c_fighter_mini" || recipe==="c_roc_luna") && state.fan_count===2) {
        // Own compact dual-fan enclosures: do not shrink a three-fan TITAN/Fighter
        // or leave its old per-fan arrays behind. Source dimensions remain facts
        // in the profile; these bounded 24-unit proportions are artwork estimates.
        var result=copy(g),roc=recipe==="c_roc_luna"
        result.w=roc?18.6:19.3;result.h=roc?10.25:9.1
        result.x=12.15-result.w/2;result.y=11.65-result.h/2
        result.centers=[result.x+result.w*.25,result.x+result.w*.75]
        result.radius=Math.min(result.h*.41,result.w*.215)
        result.radii=[result.radius,result.radius]
        result.fan_y=[result.y+result.h*.51,result.y+result.h*.51]
        result.blowers=[]
        return result
    }
    if(["c_hellhound_sakura","c_hellhound_sakura_limited","c_hellhound_white"].indexOf(recipe)>=0
            && state.fan_count===3) {
        // Official straight-on images show a smaller, slightly lower middle fan.
        // Ratios are illustration estimates, not asserted millimetre diameters.
        var hh=copy(g),outer=Math.min(g.h*.405,g.w*.145)
        hh.centers=[g.x+g.w*.18,g.x+g.w*.50,g.x+g.w*.82]
        hh.radii=[outer,outer*.89,outer];hh.radius=outer
        hh.fan_y=[g.y+g.h*.51,g.y+g.h*.535,g.y+g.h*.51]
        hh.blowers=[]
        return hh
    }
    return null
}

function blossom(x,y,size) {
    var shape=""
    for(var i=0;i<5;i++)shape+=p("M0 0C-2-2-2.7-5-.5-6.1L0-5.2L.5-6.1C2.7-5 2-2 0 0Z","#edb7cd")
        .replace('/>',' transform="rotate('+(i*72)+')"/>')
    return '<g transform="translate('+x+' '+y+') scale('+size+')">'+shape+'</g>'
}
function nitroFront(recipe,c) {
    var polar=recipe==="c_nitro_polar",face=polar?"#eef0ec":"#85877d",edge=polar?"#c7cfcc":"#aeb1a5"
    var body=r(0,3,100,94,1.2,face,edge,.8)+r(1.1,5,97.8,89,.7,face)
    // A subdued perforated metal texture lives between the independently drawn
    // round fan openings; it must not resemble exposed vertical heatsink fins.
    for(var row=0;row<7;row++)for(var col=0;col<22;col++)
        body+='<circle cx="'+(2.8+col*4.45+(row%2)*1.1)+'" cy="'+(10+row*13)+'" r=".30" fill="'
            +(polar?'#9caaa7':'#525e54')+'" opacity=".55"/>'
    return body+p("M1 4H99M1 96H99","none",polar?"#ffffff":"#d1d2c6",.55)
        +p("M.4 14V86M99.6 14V86","none",edge,1.1)
}
function hellhoundFront(recipe,c) {
    var body=r(0,3,100,94,1.8,"#ebeeef","#b5c0c5",.8)
        +p("M1 6H99M1 94H99","none","#ffffff",1.5)
    if(recipe!=="c_hellhound_white")body+=blossom(64,10,.60)+blossom(29,88,.28)
        +p("M31 87Q32 84 34 84Q34 87 31 87Z","#edb7cd")
    return body
}
function devilFront(c) {
    return p("M0 21L7 5H94L100 18V84L94 98H5L0 84Z","#353b3e")
        +p("M0 21L7 5H94L100 18H91L87 12H10L4 25Z","#555d60")
        +p("M4 4H96V9H8Z","#b8474b")
        +p("M27 14L38 37L35 42L25 17ZM65 65L77 88H67L62 73Z","#bb4d51")
        +p("M0 84L5 98H94L100 84V72L95 88H6L0 74Z","#202c34")
        +p("M94 98L100 84V77L97 79L91 98Z","#a94c53")
}
function face(recipe,g,c,state) {
    var body=""
    if(["c_nitro_phantom","c_nitro_polar","c_nitro_valor","c_nitro_crimson"].indexOf(recipe)>=0)
        body=nitroFront(recipe,c)
    else if(["c_hellhound_sakura","c_hellhound_sakura_limited","c_hellhound_white"].indexOf(recipe)>=0)
        body=hellhoundFront(recipe,c)
    else if(recipe==="c_devil_limited" || recipe==="c_devil_bp")body=devilFront(c)
    else if(recipe==="c_fighter_mini")body=r(0,3,100,94,.5,"#262c2e","#394145",.8)
        +r(1.4,7,97.2,86,.4,"#292f31","#42484a",.35)
    else if(recipe==="c_roc_luna") {
        body=r(0,1,100,98,5.5,"#edf0ef","#b9c5cb",.9)
            +r(1.2,3,97.6,94,4.5,"#e7edeb")
            +r(31,2,53,3.2,1.3,"#d1cddc") // Physical diffuser, no invented live RGB.
        for(var i=0;i<4;i++)body+=p("M"+(1.6+i*.75)+" 10V88","none","#c8d1d2",.35)
    }
    return body?placed(recipe,g,body):""
}

function vents(x,y,w,rows,fill) {
    var result=""
    for(var i=0;i<rows;i++)result+=r(x,y+i*12,w,8,2.5,fill,"#b1b9b7",.55)
    return result
}
function mountingFrame() {
    // A visible exterior retention frame, never the hidden chip/VRM layout.
    var frame=p("M22 23L48 77M48 23L22 77","none","#adb9bd",3.8)
        +r(27,34,16,32,2.2,"#adb9bd","#6b787e",.5)
        +r(29,38,12,24,1.5,"#435158")
    var points=[[22,23],[48,23],[22,77],[48,77]]
    points.forEach(function(at){frame+='<ellipse cx="'+at[0]+'" cy="'+at[1]+'" rx="1.7" ry="3.4" fill="#bac4c7"/>'})
    return frame
}
function sapphireRear(recipe,c) {
    var polar=recipe==="c_nitro_polar_back",valor=recipe==="c_nitro_valor_back",crimson=recipe==="c_nitro_crimson_back"
    var body=r(0,3,100,94,.8,polar?"#eff1ee":"#a4a69c","#bdc2b8",.8)
    if(valor || crimson) {
        // Broad printed colour fields abstract the factory MagniPlate artwork;
        // no copied game logos/characters and no fictitious PCB under the cover.
        body+=r(1.4,5,92,89,0,valor?"#242b2f":"#375060")
        if(valor)body+=p("M2 8H45L67 40L54 58L68 94H2Z","#4b2b2c")
            +p("M25 27L49 43L63 60L54 72L35 45Z","#956055")
            +p("M45 14L57 27L54 48L63 63L59 93H43L39 62L43 43Z","#1d2e35")
        else body+=p("M2 5H44L58 27L46 48L56 74L39 94H2Z","#b2a190")
            +p("M42 24L58 7L72 29L64 48L69 75L56 94H41L52 62L39 48Z","#76818a")
            +p("M44 39L53 29L63 45L58 64L48 68L43 55Z","#5b5650")
        body+=vents(71,20,20,5,"#1c292f")
    } else {
        for(var row=0;row<7;row++)for(var col=0;col<21;col++)
            body+='<circle cx="'+(4+col*3.9)+'" cy="'+(10+row*12.5)+'" r=".38" fill="'+(polar?'#8f9998':'#6c756e')+'"/>'
        body+=p("M44 30L57 41L70 30L65 54L57 68L49 54Z","none",polar?"#9aa5a2":"#737e72",.8)
            +vents(72,21,18,5,"#303c3e")
    }
    return body+p("M94 3V97","none",polar?"#cad2cd":"#777f75",.9)
}
function hellhoundRear(recipe) {
    var body=r(0,3,100,94,.8,"#e8eceb","#b3c0c5",.7)+mountingFrame()
        +p("M78 11L94 40L78 70L83 86H95V14Z","#5c6a70")
        +p("M80 17L92 41L83 58M87 68L93 80","none","#dce5e5",2)
    if(recipe==="c_hellhound_sakura_back")body+=blossom(15,80,.58)+blossom(61,16,.38)
        +p("M48 61Q54 53 58 58Q55 64 48 61ZM56 78Q61 69 66 73Q64 78 56 78Z","#e5b7ca")
    return body
}
function devilRear() {
    return p("M0 6H93L100 18V87L94 97H0Z","#545c62","#76838a",.7)+mountingFrame()
        +p("M8 12L20 24L31 26M5 34L17 40M9 76L26 64M43 20L54 33M48 79L62 62M65 16L72 27M72 72L86 84",
            "none","#29393f",1.7)
        +p("M76 35L89 43L83 61L75 67L68 57L70 44Z","#7e4d52")
        +p("M95 57L97 83L88 90Z","#23343b")
}
function devilSkin(recipe) {
    if(recipe==="c_devil_intrusive_skin") {
        var flat=r(0,4,100,92,4,"#46535c","#73828b",.7)
            +p("M9 6L31 33L53 52L73 62L91 94","none","#293b45",.7)
            +p("M47 22Q63 32 63 52L59 69L54 74L51 68L51 49L45 34Z","#263b46")
        for(var i=0;i<6;i++)flat+=p("M"+(64+i*4.8)+" 58V88","none","#98a8ae",1.9)
        return flat
    }
    var body=p("M0 11L15 0H93L100 13V87L89 100H8L0 85Z","#4b535a")
        +p("M0 11L30 32L48 20L69 59L46 79L17 62Z","#65717a")
        +p("M30 32L48 20L47 56L17 62Z","#404a54")
        +p("M47 56L69 59L82 84L46 79Z","#303e48")
        +p("M72 42L91 44L91 82L77 88L67 68Z","#263941")
    for(var row=0;row<7;row++)for(var col=0;col<9;col++) {
        var x=3+col*3.0,y=10+row*10
        body+=p("M"+x+" "+y+"L"+(x+2.2)+" "+(y+4)+"H"+(x-.1)+"Z","#26353d")
    }
    return body
}
function back(recipe,g,c,state) {
    var body=""
    if(["c_nitro_phantom_back","c_nitro_polar_back","c_nitro_valor_back","c_nitro_crimson_back"].indexOf(recipe)>=0)
        body=sapphireRear(recipe,c)
    else if(recipe==="c_hellhound_sakura_back" || recipe==="c_hellhound_white_back")body=hellhoundRear(recipe)
    else if(recipe==="c_devil_factory_back")body=devilRear()
    else if(recipe==="c_devil_le_skin" || recipe==="c_devil_intrusive_skin")body=devilSkin(recipe)
    else if(recipe==="c_fighter_mini_back")body=r(0,3,100,94,.5,"#303b40","#52636b",.7)+mountingFrame()
    else if(recipe==="c_roc_luna_back") {
        // Exact official 2000px rear photo: white metal cover, four large black
        // screw heads, straight right-hand vents interrupted by a diagonal band.
        // No exposed X brace, chip layout, or imagined rear circuit is added.
        body=r(0,3,100,94,3.3,"#e9eeed","#bfcbce",.65)
        for(var slot=0;slot<8;slot++)body+=r(76+slot*2.55,21,1.10,60,.25,"#556269")
        body+=p("M73 76L98 22V28L73 82Z","#e9eeed")
            +p("M1 66L19 91H59L65 94H73M61 85L96 31","none","#cad3d5",.65)
            +p("M75 97V87Q75 84 78 84H94Q97 84 97 87V97Z","#839299")
        var screws=[[24,27],[52,27],[24,72],[52,72]]
        screws.forEach(function(at){body+='<ellipse cx="'+at[0]+'" cy="'+at[1]+'" rx="1.25" ry="2.25" fill="#303b41"/>'})
    }
    return body?placed(recipe,g,body):""
}
