.pragma library

// Exact reviewed group-A retail versions. Original simplified casing art;
// no runtime product photographs, polling, timers, filters or fan animations.
// The common caller alone renders confirmed rotors and board connectors.
function p(d,fill,stroke,width) {
    return '<path d="'+d+'" fill="'+fill+'"'
        +(stroke?' stroke="'+stroke+'" stroke-width="'+width+'" stroke-linejoin="round"':'')+'/>'
}
function r(x,y,w,h,rx,fill) {
    return '<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" rx="'+rx+'" fill="'+fill+'"/>'
}
function wrap(recipe,g,body) {
    return '<g class="hardware-variant-face '+recipe+'" transform="translate('+g.x+' '+g.y+') scale('+(g.w/100)+' '+(g.h/100)+')">'+body+'</g>'
}
function bays(g,fill,rim,width) {
    var result=""
    for(var i=0;i<g.centers.length;i++) {
        var radius=g.radii&&g.radii[i]!==undefined?g.radii[i]:g.radius
        var x=(g.centers[i]-g.x)/g.w*100
        var y=((g.fan_y&&g.fan_y[i]!==undefined?g.fan_y[i]:g.y+g.h*.51)-g.y)/g.h*100
        result+='<ellipse cx="'+x+'" cy="'+y+'" rx="'+(radius/g.w*102)+'" ry="'+(radius/g.h*102)
            +'" fill="'+fill+'" stroke="'+rim+'" stroke-width="'+width+'"/>'
    }
    return result
}

function geometry(recipe,state,g) {
    // Only the revision with a different photographed enclosure changes the
    // common front plane. These are illustration proportions, not PCB sizes.
    if(recipe!=="a_gigabyte_460_rev2" && recipe!=="a_gigabyte_460_rev3")return null
    var width=recipe==="a_gigabyte_460_rev2"?20.1:19.7
    var height=recipe==="a_gigabyte_460_rev2"?9.5:10.0
    var x=12.15-width/2,y=11.65-height/2
    var centers=recipe==="a_gigabyte_460_rev2"?[x+width*.285,x+width*.745]:[x+width*.275,x+width*.735]
    var radius=Math.min(height*.405,width*.205)
    return {x:x,y:y,w:width,h:height,centers:centers,radius:radius,
        radii:[radius,radius],fan_y:[y+height*.52,y+height*.52],blowers:[]}
}

function face(recipe,g,c,state) {
    var body=""
    if(recipe==="a_asus_dual_white") {
        // White lower shell and smoked blue-grey upper band are both visible
        // in this SKU's own front view. No dark rotor is inherited.
        body=p("M1 10L5 2H42L48 8H89Q99 8 100 23V91L96 98H4L0 90V30Z",c.caseBody)
            +p("M1 10L5 2H42L48 8H89Q99 8 100 23V29H52L44 34H0V18Z","#647a88")
            +p("M4 8H41L46 14H89L96 20V24H52L44 29H3Z","#8194a0")
            +p("M0 31H14L17 36V81L24 94H43L48 99H4L0 90Z",c.caseTop)
            +p("M47 32L53 39L51 76L59 94H96L100 89V91L96 98H54L45 84Z",c.caseTop)
            +p("M2 35H9V73L15 83M47 36H54L51 72L57 85M92 35H98V81H93","none","#99aab5",.65)
            +bays(g,"#596872",c.edge,.8)
    } else if(recipe==="a_asus_strix_white") {
        // Source: almost rectangular white frame, silver diagonal facets and
        // the narrow luminous end window. Simplified without licensed marks.
        body=r(0,2,100,96,3,c.caseBody)
            +r(1,3,97,7,2,c.caseTop)+r(1,90,97,7,2,c.caseTop)
            +p("M58 10H77L70 18H65L59 38H54Z M77 10H96V20L92 24H78Z","#b8c2c9")
            +p("M26 82L30 68L45 91H38Z M60 76L73 89H95V82H76L66 65Z","#b8c2c9")
            +p("M4 12H9L5 25H2Z M11 12H17L12 22H7Z M19 12H24L20 20H15Z",c.rim)
            +r(97,4,2.4,92,1,c.accent)+bays(g,"#63717a",c.edge,.7)
    } else if(recipe==="a_asus_astral_white") {
        // Same exact white SKU's front and rear confirm three front and one
        // opposite fan; this face draws only the photographed front plane.
        body=p("M0 6L3 0H97L100 7V93L97 100H3L0 94Z",c.caseTop)
            +p("M2 8L5 4H56L64 20H94L98 9V91L94 96H5L2 91Z",c.metal)
            +r(4,14,91,73,3,c.caseBody)
            +p("M57 3H64L71 21H94V29H68Z M58 74L64 72L74 96H68Z",c.caseTop)
            +p("M4 4H19L18 8H4Z M21 4H56L58 8H21Z","#8194a3")
            +p("M4 94H95V97H4Z",c.edge)+bays(g,"#6b7881",c.edge,.8)
    } else if(recipe==="a_msi_golden980ti") {
        // Copper left C-frame, black right frame, copper fins/heatpipes. The
        // fourteen alternating black TORX leaves are owned by FanDesigns.
        var black="#30383f",blackTop="#4d5963",copper="#c38453",copperLight="#e1ad77",copperDark="#996139"
        body=p("M0 19L7 4H40L47 0H64L71 8H96L100 23V84L93 99H61L55 93H37L28 100H6L0 84Z",black)
            +p("M0 19L7 4H40L47 0H57L46 19H23L13 34V68L25 83H45L57 100H27L19 93H6L0 84Z",copper)
            +p("M7 4H40L47 0H57L51 8H12L5 21H1Z",copperLight)
            +p("M47 5H63L71 8H96L100 23L96 30H76L67 18H55Z",blackTop)
            +p("M60 74L70 85H94L99 73V84L93 99H61L55 93Z",blackTop)
            +p("M3 86H8V94H94V87H98V100H3Z",copperDark)
        for(var j=0;j<6;j++) {
            var at=61+j*6
            body+=p("M"+at+" 8L"+(at+2)+" 9L"+(at+5)+" 23L"+(at+3)+" 22Z",copper)
                +p("M"+(at-4)+" 82L"+(at-2)+" 81L"+(at+1)+" 95H"+(at-1)+"Z",copper)
        }
        body+=bays(g,"#3c332d",copperDark,.55)
    } else if(recipe==="a_gigabyte_460_rev2") {
        // Reviewed Rev2 has a continuous smooth trough rather than Rev1's
        // two raised round lobes. Copper tubing is externally visible.
        body=p("M2 8H96L100 17V84L96 94H3L0 87V18Z","#303b45")
            +p("M2 8H96L100 17V27L94 19H8L0 27V18Z","#46515c")
            +p("M0 66Q18 88 31 85Q46 81 49 72Q58 88 74 85Q90 82 100 63V84L96 94H3L0 87Z","#65727b")
            +p("M1 78Q23 97 46 84L50 78Q72 98 99 77V87L96 94H3Z","#38434d")
            +p("M14 5Q17 0 25 1H69Q78 1 81 5M21 5Q25 1 34 2H64Q70 2 73 5","none","#bc8051",1.5)
            +bays(g,"#29343d","#56646f",.6)
    } else if(recipe==="a_gigabyte_460_rev3") {
        // Rev3's own image shows the raised circular mouths, curved bridge
        // and blue PCB edge. Unconfirmed rotor leaves remain static discs.
        body=p("M0 27L6 9H40L48 16L57 8H91L100 26V82L92 95H59L50 84L41 95H8L0 82Z","#303b45")
            +p("M1 27L6 9H40L48 16L40 23H18Q7 24 5 44Z","#53616c")
            +p("M57 8H91L100 26L96 44Q92 24 79 21H63L55 27L48 17Z","#4d5c67")
            +p("M0 72Q13 95 31 83L43 75L50 84L41 95H8L0 82Z M60 78Q78 95 99 71V82L92 95H59L50 84Z","#4b5964")
            +p("M45 25L51 20L56 29V70L50 77L43 70Z","#28343e")
            +bays(g,"#26323b","#64727d",.7)
    } else if(recipe==="a_zotac_infinity_10a") {
        // Exact10A sheet supplies this triple-fan Infinity layout, but its
        // original blade photo was unavailable. No10P leaf count is reused.
        body=r(0,2,100,96,12,c.caseShade)+r(3,6,94,88,10,c.metal)
            +r(6,13,88,74,8,c.caseBody)+r(9,5,82,4,2,c.accent)
            +r(10,91,80,4,2,c.rim)+bays(g,"#2a3540",c.caseShade,.6)
    } else {
        // a_zotac_twin_oc / a_zotac_twin_white use the independently checked
        // same-size rounded Twin Edge shell. Their own finish and exact
        // eleven-leaf fan metadata come from the ART row, never suffix logic.
        return ""
    }
    return wrap(recipe,g,body)
}

function back(recipe,g,c,state) {
    if(recipe!=="a_msi_golden980ti_back")return ""
    // The exact Golden PDF's rear view shows a BLACK metal plate with copper
    // decoration and a perforated right field. The branded dragon is omitted;
    // these arcs abstract only the copper printed region. Holes are a texture
    // approximation, never an assertion of internal PCB or fastener counts.
    var body=p("M0 4H96L100 10V94L96 98H24L20 87H0Z","#353e44","#6b767d",.55)
        +p("M4 16Q25 9 38 34Q19 29 5 47M3 56Q22 35 36 54Q16 50 6 72M8 78Q22 70 34 82L26 96",
            "none","#c89a53",2.2)
    for(var row=0;row<5;row++)for(var col=0;col<7;col++) {
        var x=44+col*7.4+(row%2)*2.6,y=16+row*14
        body+=p("M"+x+" "+y+"H"+(x+3)+"L"+(x+4)+" "+(y+2.8)+"L"+(x+3)+" "+(y+5.6)
            +"H"+x+"L"+(x-1)+" "+(y+2.8)+"Z","#202d35")
    }
    body+=p("M25 99Q45 107 88 99","none","#b8794d",1.8)
    return wrap(recipe,g,body)
}
