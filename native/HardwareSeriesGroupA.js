.pragma library

// Original static casing illustrations of the reviewed Group A representatives.
// The central renderer supplies normalized geometry, real confirmed fans and
// all hardware connections. This module draws only a raw 100x100 casing body.
// No logos, fan circles, transforms, textures, timers or imports.
var ids = ["asrock_phantom", "asrock_steel_legend", "asrock_challenger", "asrock_taichi",
    "xfx_merc", "xfx_qick", "xfx_swft", "pny_xlr8", "pny_verto",
    "evga_ftw3", "evga_xc3", "leadtek_hurricane"]

function profile(id) {
    // Illustration w[unknown,1,2,3], h[unknown,1,2,3], inset, center offset.
    // These proportions do not establish factory dimensions or fan count.
    switch (id) {
    case "asrock_phantom": return [19.5,14.0,19.9,21.0, 9.6,10.5,9.6,8.5, .247,.02]
    case "asrock_steel_legend": return [19.0,14.4,19.7,20.9, 10.0,11.0,10.0,9.0, .257,.00]
    case "asrock_challenger": return [18.6,13.8,19.2,20.5, 9.4,10.5,9.5,8.4, .248,.00]
    case "asrock_taichi": return [19.8,14.9,20.3,21.1, 10.4,11.6,10.4,9.4, .257,.00]
    case "xfx_merc": return [20.0,14.7,20.0,21.1, 8.9,10.0,9.0,7.9, .239,.00]
    case "xfx_qick": return [19.7,14.4,19.9,20.9, 9.2,10.2,9.3,8.2, .242,.00]
    case "xfx_swft": return [18.5,13.7,19.0,20.5, 9.1,10.1,9.2,8.1, .244,.00]
    case "pny_xlr8": return [19.3,14.3,19.7,20.8, 9.4,10.4,9.5,8.3, .245,.00]
    case "pny_verto": return [18.9,13.8,19.3,20.5, 9.0,10.0,9.1,8.0, .243,.00]
    case "evga_ftw3": return [19.9,14.8,20.2,21.0, 10.2,11.3,10.2,9.1, .249,.00]
    case "evga_xc3": return [19.5,14.1,19.7,20.8, 8.5,9.5,8.6,7.6, .236,.00]
    case "leadtek_hurricane": return [19.8,14.7,20.1,21.0, 10.1,11.1,10.2,9.0, .252,.00]
    }
    return null
}

function p(d, fill) { return '<path d="'+d+'" fill="'+fill+'"/>' }
function r(x,y,w,h,radius,fill) {
    return '<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" rx="'+radius+'" fill="'+fill+'"/>'
}

function face(state, g, c) {
    if (!state || ids.indexOf(state.series_id) < 0) return ""
    var id=state.series_id, body=""
    switch (id) {
    case "asrock_phantom":
        // Long diagonal cutouts / unequal, swept armor planes.
        body=p("M0 24L12 3H41L47 10H75L83 0H95L100 17V77L88 98H58L51 90H23L13 100H2L0 83Z",c.caseShade)
            +p("M0 24L12 3H41L47 10H75L83 0H95L88 22H66L51 42H28L15 64H0Z",c.caseTop)
            +p("M1 82L18 61H42L58 39H78L100 17V77L88 98H58L51 90H23L13 100H2Z",c.caseBody)
            +p("M17 6H27L9 35H0V25Z",c.metal)
            +p("M75 92L96 62V77L88 98H68Z",c.metal)
            +p("M45 11H54L32 42H23Z",c.accent)
            +p("M63 58H72L51 90H42Z",c.accent)
        break
    case "asrock_steel_legend":
        // Broad light facets, raised center shoulders and unequal end bevels.
        body=p("M0 25L8 7H26L31 0H45L51 11H69L77 0H91L100 22V78L91 97H72L66 88H45L37 100H16L0 86Z",c.metal)
            +p("M8 7H26L31 0H45L51 11H69L77 0H91L100 22H82L72 32H54L43 19H30L19 34H0V25Z",c.edge)
            +p("M0 71L17 80H35L44 68H61L72 81H88L100 67V78L91 97H72L66 88H45L37 100H16L0 86Z",c.caseTop)
            +p("M23 18L31 22L42 81L34 92L28 57Z",c.caseShade)
            +p("M68 20L75 14L70 59L79 89H69L61 57Z",c.caseShade)
        break
    case "asrock_challenger":
        // An angular compact H-shaped bridge and heavy, squared end caps.
        body=p("M0 19L11 2H34L43 14H67L77 2H91L100 20V82L89 98H67L58 87H34L24 98H10L0 80Z",c.caseShade)
            +p("M0 19L11 2H34L43 14H67L77 2H91L100 20H78L65 34H42L28 20H13L0 37Z",c.caseTop)
            +p("M0 63L15 80H34L46 67H60L74 81H89L100 64V82L89 98H67L58 87H34L24 98H10L0 80Z",c.caseBody)
            +p("M37 25H48L64 75H52Z",c.metal)
            +p("M42 18H62L55 29H35Z",c.edge)
        break
    case "asrock_taichi":
        // Separate broad metallic, folded chambers and a raised center crown.
        body=p("M0 25L12 5H28L37 12H42L45 0H59L64 12H74L82 5H91L100 24V79L88 98H73L65 89H59L55 100H43L38 89H28L20 98H9L0 80Z",c.caseShade)
            +p("M0 25L12 5H28L37 12H42L45 0H59L64 12H74L82 5H91L100 24L88 29L77 19H68L60 29H41L32 20H19L9 35Z",c.metal)
            +p("M0 66L12 76H26L36 64H43L49 78H57L64 63H73L83 77H94L100 65V79L88 98H73L65 89H59L55 100H43L38 89H28L20 98H9L0 80Z",c.caseTop)
            +p("M32 17H41L32 40V61L42 83H32L24 61V41Z",c.edge)
            +p("M62 17H72L79 40V62L70 84H60L70 61V41Z",c.metal)
            +r(44,7,13,5,1,c.accent)
        break
    case "xfx_merc":
        // Long smooth, uninterrupted slab with a narrow metal return frame.
        body=p("M0 12Q0 3 10 3H92L100 11V89L93 97H9Q0 97 0 87Z",c.metal)
            +p("M2 15Q2 7 11 7H92L97 13V86L91 93H11Q3 93 3 85Z",c.caseBody)
            +p("M2 15Q2 7 11 7H92L97 13V21H9V81H3Z",c.caseTop)
            +p("M92 7L97 13V86L91 93H82L88 81V20Z",c.caseShade)
            +r(6,9,3,77,1,c.edge)
        break
    case "xfx_qick":
        // A floating plate with flat projecting top/bottom lips and soft ends.
        body=p("M0 13Q0 6 8 6H91Q100 6 100 16V85Q100 93 91 93H7Q0 93 0 85Z",c.caseShade)
            +p("M0 13H100V22H96V79H100V88H0V78H4V23H0Z",c.caseTop)
            +r(6,20,88,60,3,c.caseBody)
            +p("M0 13Q0 6 8 6H91Q100 6 100 16V19H0Z",c.metal)
            +p("M0 82H100V85Q100 93 91 93H7Q0 93 0 85Z",c.edge)
            +r(3,30,4,15,1,c.metal)+r(93,55,4,15,1,c.metal)
        break
    case "xfx_swft":
        // Compact gently tapered enclosure and wide continuous dark face.
        body=p("M0 23Q0 13 9 11L88 5Q100 5 100 18V81Q100 94 88 94L9 88Q0 87 0 77Z",c.caseShade)
            +p("M4 25Q4 19 11 18L88 12Q95 12 95 21V77Q95 86 88 86L11 81Q4 80 4 74Z",c.caseBody)
            +p("M0 23Q0 13 9 11L88 5Q100 5 100 18V25L91 20L11 25V76L0 77Z",c.caseTop)
            +p("M9 88L88 94Q100 94 100 81V75L90 82L10 77L0 77Q0 87 9 88Z",c.metal)
        break
    case "pny_xlr8":
        // Stepped, triangular end fins and wide crossing zigzag armor bridges.
        body=p("M0 27L8 9H22L28 0H43L49 9H66L74 0H89L95 12H100V80L91 96H73L65 87H49L40 98H17L8 88H0Z",c.caseShade)
            +p("M0 27L8 9H22L28 0H43L49 9H66L74 0H89L95 12H100L89 29H75L64 40H47L35 25H22L9 45H0Z",c.caseTop)
            +p("M0 64L14 78H29L41 61H57L70 77H85L100 55V80L91 96H73L65 87H49L40 98H17L8 88H0Z",c.caseBody)
            +p("M29 17H41L63 82H51Z",c.metal)
            +p("M58 15H70L46 85H34Z",c.caseTop)
            +p("M28 12H35L43 32H36Z",c.accent)
            +p("M61 67H68L61 88H54Z",c.accent)
        break
    case "pny_verto":
        // Shallow rectangular frame with broad sculpted diagonal corners.
        body=p("M0 15L12 2H87L100 17V85L88 98H12L0 84Z",c.caseBody)
            +p("M0 15L12 2H87L100 17H77L68 30H51L43 17H21L8 35H0Z",c.caseTop)
            +p("M0 68L19 81H40L49 68H67L77 83H100V85L88 98H12L0 84Z",c.caseShade)
            +p("M41 16H51L63 81H52Z",c.metal)
            +p("M5 19L16 7H27L12 24Z",c.edge)
            +p("M73 91L84 77H95L85 91Z",c.caseTop)
        break
    case "evga_ftw3":
        // Thick bowed upper light canopy and a deep, curved lower belly.
        body=p("M0 21Q2 6 16 6H85Q98 6 100 23V83L95 96H77Q53 100 26 98H6L0 87Z",c.caseBody)
            +p("M0 21Q2 6 16 6H85Q98 6 100 23V29H91Q81 20 66 26Q51 33 34 25Q20 18 9 29H0Z",c.caseTop)
            +p("M14 6H87L84 17Q54 30 19 17Z",c.accent)
            +p("M18 7H83L78 15Q54 22 23 15Z",c.edge)
            +p("M0 74Q15 79 25 89Q50 98 77 88Q90 78 100 77V83L95 96H77Q53 100 26 98H6L0 87Z",c.caseShade)
        break
    case "evga_xc3":
        // Very narrow opposed scalloped rails and open waist, unlike FTW3.
        body=p("M0 20L5 6H94L100 19V83L94 95H6L0 83Z",c.caseShade)
            +p("M5 6H94L100 19V26H91Q78 8 65 23Q52 7 38 23Q23 6 10 26H0V20Z",c.caseTop)
            +p("M0 72H10Q24 90 38 74Q52 91 65 74Q78 90 91 72H100V83L94 95H6L0 83Z",c.metal)
            +r(0,26,5,46,1,c.caseBody)+r(95,26,5,46,1,c.caseBody)
        break
    case "leadtek_hurricane":
        // Broad interleaving curved metal blades meet in a swept center X.
        body=p("M0 24L14 0H88L100 18V78L87 100H12L0 80Z",c.caseShade)
            +p("M0 24L14 0H38Q42 27 62 39Q79 48 100 18V37Q82 61 61 55Q43 49 30 18L9 41Z",c.metal)
            +p("M0 64Q20 40 40 45Q60 51 72 82L90 61L100 78L87 100H64Q60 73 40 61Q22 51 0 80Z",c.caseTop)
            +p("M7 30L16 13H27L15 37Z",c.edge)
            +p("M73 85L85 64L94 76L84 91H74Z",c.metal)
        break
    }
    return body
}
