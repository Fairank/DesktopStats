.pragma library
.import "HardwareGpuPascal055.js" as Pascal055

// Original era-specific casing/board illustrations, distilled from the exact
// official front views in hardware_catalog_nvidia_legacy.py. Raw 100 x 100
// casing only: the caller transforms it and owns all confirmed circular fans,
// contacts and brackets. No current-generation shell is renamed or imported.

var ids = ["nvidia_founders_pascal", "msi_aero_itx_pascal", "msi_low_profile_pascal",
    "msi_gaming_pascal", "msi_lightning_pascal", "gigabyte_silent_pascal",
    "msi_gaming_maxwell", "nvidia_reference_kepler", "msi_lightning_kepler",
    "msi_twinfrozr_kepler", "msi_lightning_fermi", "msi_blower_fermi",
    "gigabyte_windforce_fermi", "msi_lightning_tesla", "msi_blower_g80", "gigabyte_fx5200"]

function profile(id) {
    // Illustration widths[unknown,1,2,3], heights[unknown,1,2,3], inset, offset.
    // Long radial cards intentionally stay long when they contain one fan.
    switch (id) {
    case "nvidia_founders_pascal": return [20.0,20.8,20.8,21.0, 9.1,9.1,9.1,8.7,.250,0]
    case "msi_aero_itx_pascal": return [15.0,13.2,18.8,20.6, 10.2,11.1,9.8,8.6,.247,.15]
    case "msi_low_profile_pascal": return [18.4,13.2,18.8,20.5, 7.1,8.1,7.1,6.8,.246,0]
    case "msi_gaming_pascal": return [19.5,14.4,20.1,20.9, 10.1,11.0,10.1,9.0,.255,0]
    case "msi_lightning_pascal": return [20.0,15.0,20.3,21.1, 10.4,11.4,10.3,9.3,.255,0]
    case "gigabyte_silent_pascal": return [18.5,13.5,19.0,20.7, 7.5,9.0,8.0,7.3,.245,0]
    case "msi_gaming_maxwell": return [19.1,14.1,19.8,20.7, 10.0,10.8,10.0,8.8,.253,0]
    case "nvidia_reference_kepler": return [20.0,20.8,20.8,21.0, 9.0,9.0,9.0,8.6,.250,0]
    case "msi_lightning_kepler": return [19.6,14.8,20.0,20.8, 9.9,11.0,9.9,8.8,.253,0]
    case "msi_twinfrozr_kepler": return [18.3,13.7,18.9,20.6, 9.0,10.1,9.1,8.0,.247,0]
    case "msi_lightning_fermi": return [20.0,14.7,20.3,21.0, 8.9,10.0,9.0,8.0,.247,0]
    case "msi_blower_fermi": return [19.8,20.7,20.7,21.0, 8.9,8.9,8.9,8.6,.250,0]
    case "gigabyte_windforce_fermi": return [18.5,14.0,19.2,20.6, 9.6,10.5,9.6,8.6,.251,0]
    case "msi_lightning_tesla": return [19.8,14.6,20.2,20.9, 8.7,10.0,8.8,7.9,.247,0]
    case "msi_blower_g80": return [18.5,18.8,19.5,20.8, 9.1,9.1,9.2,8.5,.250,0]
    case "gigabyte_fx5200": return [16.8,16.8,18.5,20.0, 9.4,9.4,9.2,8.2,.250,-1.0]
    }
    return null
}

function p(d,fill) { return '<path d="'+d+'" fill="'+fill+'"/>' }
function r(x,y,w,h,radius,fill,tag) {
    return '<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" rx="'+radius+'" fill="'+fill+'"'+(tag?' class="'+tag+'"':'')+'/>'
}

function fins(x,y,w,h,count,c) {
    var result=r(x,y,w,h,1,c.caseShade)
    for (var index=0;index<count;index++)
        result+=r(x+1+index*(w-2)/count,y+.7,Math.max(1.0,(w-2)/count*.42),h-1.4,.25,c.metal)
    return result
}

function face(state,g,c) {
    if (!state || ids.indexOf(state.series_id)<0
            || state.series_id.split("_")[0]!==state.board_vendor) return ""
    switch (state.series_id) {
    case "nvidia_founders_pascal":
        // Pascal FE's tessellated metal frame surrounds a tapered dark window.
        return p("M0 20L6 2H92L100 19V81L92 98H6L0 80Z",c.metal)
            + p("M14 23L49 15L60 32V73L47 85H15Z",c.disk)
            + p("M0 20L6 2H35L24 16L14 23H4Z M49 15L35 2H60L68 13L60 32Z",c.caseTop)
            + p("M60 2H92L100 19L90 15L81 26L68 13Z M89 75L100 81L92 98H61L68 85Z",c.caseShade)
            + p("M6 98L14 77L47 85L60 98Z M24 16L35 2L49 15Z",c.edge)
            + Pascal055.fins(c)
            + Pascal055.face(c)
    case "msi_aero_itx_pascal":
        // AERO ITX is a truly short card with a broad end panel and round bay.
        return p("M0 9H24L30 2H84L98 15V86L87 98H3L0 87Z",c.caseBody)
            + p("M0 9H24L30 2H60L50 16H26L14 31H0Z",c.caseShade)
            + p("M76 5L88 10L98 24V78L91 87L88 30Z",c.caseTop)
            + p("M0 80L24 66L32 72L14 86H4Z",c.metal)
            + p("M16 90H42L49 98H3L0 87Z",c.caseShade)
            + p("M30 3H52L47 10H27Z",c.accent)
    case "msi_low_profile_pascal":
        // 69 mm low-profile PCB: thin rectangular guard, very shallow rails.
        return r(0,5,100,90,3,c.caseShade)
            + r(2,11,96,77,3,c.caseBody)
            + p("M0 5H100V16H62L55 24H44L36 16H0Z",c.caseTop)
            + p("M0 84H36L44 76H55L62 84H100V95H0Z",c.caseTop)
            + r(46,29,7,40,1,c.caseShade)
            + r(4,8,13,3,1,c.accent)
    case "msi_gaming_pascal":
        // Twin Frozr VI: asymmetric red/black zones and four claw-like rails.
        return p("M0 25L7 8H36L44 0H66L74 7H94L100 21V80L92 98H68L59 91H33L25 98H7L0 83Z",c.caseBody)
            + p("M0 25L7 8H36L44 0H59L49 17H29L19 35H0Z M0 67H18L29 84H49L59 100H27L20 94H7L0 83Z",c.accent)
            + p("M58 0H66L74 7H94L100 21L95 34H79L71 22H56Z",c.caseShade)
            + p("M66 73L72 84H91L100 70V80L92 98H68L59 91Z",c.caseShade)
            + p("M55 9H61L53 29H47Z M65 12H71L64 31H58Z M69 71H75L69 91H63Z M80 73H85L78 94H73Z",c.caseTop)
    case "msi_lightning_pascal":
        // Tri-Frozr's dark three-bay frame and broad silver intersecting braces.
        return p("M0 18L7 2H28L33 8H58L64 0H93L100 15V83L92 99H66L59 93H34L28 100H7L0 82Z",c.caseBody)
            + p("M7 2H28L36 14L45 4H58L47 22L34 30L22 13H4Z",c.metal)
            + p("M64 0H93L100 15H78L65 29L54 21Z",c.caseShade)
            + p("M0 82L7 99H28L40 80L51 95H64L47 69L35 76L23 88H4Z",c.metal)
            + p("M65 73L79 88H97L92 99H66L57 90Z",c.caseTop)
            + p("M0 25H5V73H0Z M95 24H100V75H95Z",c.caseShade)
            + p("M67 4H79L75 10H63Z",c.accent)
    case "gigabyte_silent_pascal":
        // The actual GT1030 Silent LP has an exposed, tall fin stack, no shroud.
        var passive=r(0,81,100,14,2,c.pcb || c.caseShade)
            + r(3,16,94,69,1,c.caseTop)
        for (var i=0;i<12;i++) {
            var at=4+i*7.8
            passive+=p("M"+at+" 9L"+(at+3)+" 2V80L"+(at+1)+" 89H"+at+"Z",c.metal)
        }
        return passive+r(3,87,21,4,1,c.caseShade)
    case "msi_gaming_maxwell":
        // Twin Frozr V has a simpler large red C-frame around its left fan.
        return p("M0 21L7 6H39L48 0H63L71 7H96L100 20V85L93 99H62L55 92H36L27 99H6L0 84Z",c.caseBody)
            + p("M0 21L7 6H39L48 0H58L45 19H23L13 35V67L24 82H45L58 99H26L18 92H6L0 84Z",c.accent)
            + p("M52 3H63L71 7H96L100 20L95 31H77L68 18H57Z",c.caseShade)
            + p("M68 75L79 89H97L93 99H62L55 92Z",c.caseShade)
            + p("M58 14L65 15L60 28H54Z M73 18L79 20L74 32H68Z M62 74H68L74 88H67Z",c.caseTop)
    case "nvidia_reference_kepler":
        // Kepler's smooth metal window frame is distinct from Pascal facets.
        return r(0,2,100,96,5,c.metal)
            + p("M8 13H51L60 25V75L51 87H8Z",c.disk)
            + r(10,17,44,66,3,c.caseShade)
            + fins(13,20,38,60,11,c)
            + p("M59 10L68 3H94L99 15V85L94 97H68L59 89L67 77V23Z",c.caseTop)
            + r(1,3,7,94,2,c.caseShade)
            + r(9,6,43,5,1,c.edge) + r(9,89,43,5,1,c.edge)
    case "msi_lightning_kepler":
        // Twin Frozr IV's broad asymmetric yellow shoulder and rising right end.
        return p("M0 24L13 1H39L48 10H72L79 4H95L100 19V82L91 97H67L60 91H31L24 98H4L0 82Z",c.caseBody)
            + p("M0 24L13 1H39L48 10H72L79 4H95L100 19L78 17H47L36 10H19L9 28Z",c.accent)
            + p("M4 92H25L31 84H57L65 96H91L85 100H62L55 92H31L24 98H4Z",c.metal)
            + p("M41 10L48 10L46 33L38 29Z M71 10H78L73 31L66 28Z",c.caseShade)
            + p("M0 32H5V73H0Z M96 25H100V76H96Z",c.caseTop)
    case "msi_twinfrozr_kepler":
        // Compact silver Twin Frozr III hood with two exposed lower heatpipes.
        return p("M0 24L12 4H86L100 24V76L88 91H11L0 77Z",c.metal)
            + p("M1 25L13 4H86L99 24H61L52 15H29L19 26Z",c.caseTop)
            + p("M12 5H86L80 15H19Z",c.caseShade)
            + p("M47 14H55L60 34H47Z M45 70H57L60 91H40Z",c.caseBody)
            + p("M8 84H89L94 93H5Z M16 94H85V99H16Z",c.caseShade)
            + p("M7 78H13V90H88V82H94V96H7Z",c.metal)
            + r(74,8,15,3,1,c.accent)
    case "msi_lightning_fermi":
        // Long, shallow silver hood with a bridge and visible copper pipes.
        return p("M0 17L8 7H91L100 20V78L91 89H8L0 78Z",c.metal)
            + p("M0 17L8 7H91L100 20H65L56 12H12L5 25Z",c.caseTop)
            + p("M44 10H56L59 34H42Z M43 69H58L55 88H45Z",c.caseShade)
            + p("M8 89H91V94H6Z M12 96H87V100H12Z",c.caseShade)
            + p("M4 76H9V88H93V78H98V96H4Z",c.metal)
            + p("M59 8H75L70 15H54Z",c.accent)
    case "msi_blower_fermi":
        // Fermi's distinctive exposed longitudinal fin block and closed end.
        return p("M0 8H61L68 3H94L100 18V88L91 97H0Z",c.caseBody)
            + fins(0,12,61,76,15,c)
            + p("M61 8L68 3H94L100 18V29L90 19H70L65 37H60Z",c.caseShade)
            + p("M61 72L69 89H94L91 97H61Z",c.caseShade)
            + p("M92 9L98 17V27L89 17Z M91 81L98 73V87L92 94H85Z",c.accent)
    case "gigabyte_windforce_fermi":
        // Early anti-turbulence Windforce has an open center and curved lobes.
        return p("M0 34Q1 12 17 6H41L49 17L58 7H83Q99 15 100 35V72Q97 89 83 94H61L50 84L39 94H16Q2 88 0 69Z",c.caseBody)
            + p("M0 34Q1 12 17 6H41L49 17L41 26L31 16H17Q7 20 6 39Z",c.caseTop)
            + p("M58 7H83Q99 15 100 35L93 42Q93 22 82 17H66L58 26L50 17Z",c.caseShade)
            + p("M0 69Q2 88 16 94H39L50 84L40 76H18L8 64Z M61 94H83Q97 89 100 72L92 64L82 82H65L58 76L50 84Z",c.caseTop)
            + r(43,35,13,30,2,c.caseShade)
    case "msi_lightning_tesla":
        // First Lightning: a straight, thin brushed-metal beam and exposed fins.
        return p("M0 5H100V79L91 90H7L0 78Z",c.metal)
            + r(0,5,100,13,1,c.edge)
            + p("M0 19H100V29H65L58 20H43L36 29H0Z",c.caseTop)
            + p("M43 20H57L62 44H41Z M41 66H60L64 89H38Z",c.caseShade)
            + p("M3 82H97V89H3Z M12 94H86V99H12Z",c.caseShade)
            + p("M4 76H10V91H92V78H98V97H4Z",c.metal)
            + r(7,9,19,3,1,c.accent)
    case "msi_blower_g80":
        // G80's illustrated sticker panel is represented by a simple broad
        // inset. No licensed character/logo is copied from the factory label.
        return r(0,4,100,92,8,c.caseBody)
            + p("M0 15Q0 4 10 4H59L66 17V83L57 96H10Q0 96 0 85Z",c.caseTop)
            + p("M8 13H53L60 24V76L52 87H8Z",c.accent)
            + p("M12 17H48L55 28L25 76H12Z",c.caseBody)
            + p("M63 9H91Q100 9 100 22V80Q100 91 91 91H63L68 78V23Z",c.caseShade)
    case "gigabyte_fx5200":
        // Exact GV-N52128D REV:1.0 photo, manufacturer manual p5. Only this
        // visible front layout is studied; heights/positions are reference,
        // tiny unreadable SMD circuits and branded chip text are not invented.
        var result=p("M0 0H100V90H80V100H65.8V90H64.7V100H53.5V90H52.5V100H38.5V90H0Z",c.pcb || c.caseBody)
        var memory=[[35.9,16.7,6.8,23.3],[46.9,16.7,6.8,23.3],[62.1,16.7,6.8,23.3],[72.3,16.7,6.8,23.3],
                    [91.4,20.8,13.5,12.6],[91.4,39.9,13.5,12.6],[91.4,68.1,13.5,12.6],[91.4,87.4,13.5,12.6]]
        memory.forEach(function(v){result+=r(v[0]-v[2]/2,(v[1]-v[3]/2)*.9,v[2],v[3]*.9,.5,c.disk,'hardware-fx052-memory')})
        var caps=[[9,6.8,1.8],[11.3,18.5,2.7],[27.1,7.7,2.8],[27.2,33.6,2.2],[31.1,44.9,2.7],[31.2,57.1,2.7]]
        caps.forEach(function(v){result+='<ellipse class="hardware-fx052-capacitor" cx="'+v[0]+'" cy="'+(v[1]*.9)+'" rx="'+v[2]+'" ry="'+(v[2]*1.8)+'" fill="'+c.metal+'" stroke="'+c.caseShade+'" stroke-width=".7"/>'})
        result+=r(17.1,27.6,5.8,5.3,.5,c.caseShade)
            +'<ellipse cx="20" cy="50.4" rx="2.5" ry="4.5" fill="none" stroke="'+c.gold+'" stroke-width="1.5"/>'
            +r(31,83.7,6.1,4,.5,c.edge)
            +'<path d="M52.5 83.7Q49 102 31 101Q23 99 27 91L34 85.9" fill="none" stroke="'+c.caseShade+'" stroke-width=".8"/>'
            +'<path d="M52.5 84.4Q49 102.7 31 101.7Q23 99.7 27 91.7L34 86.6" fill="none" stroke="'+c.accent+'" stroke-width=".7"/>'
        // A fixed heatsink edge is not a made-up rotating blade count.
        result+='<ellipse cx="55.6" cy="61.0" rx="15.4" ry="27.5" fill="'+c.caseShade+'"/>'
        ;[[.385,.525],[.535,.647],[.658,.800]].forEach(function(v,i){
            result+='<g class="hardware-fx052-agp-segment" data-u0="'+v[0]+'" data-u1="'+v[1]+'">'
            // Eight readable pad samples per section are not a claimed pin count.
            for(var j=0;j<8;j++)result+=r(v[0]*100+(v[1]-v[0])*100*(j+.15)/8,91.2,(v[1]-v[0])*100*.70/8,8,.05,c.gold)
            result+='</g>'
        })
        return result
    }
    return ""
}
