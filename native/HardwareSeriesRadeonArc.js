.pragma library

// Original, static front-view casing studies of the reviewed Radeon / Arc
// representatives. The central renderer supplies confirmed fan geometry.
// This module returns only a raw normalized 100x100 body, without logos,
// circular fans, wrappers, transforms, imports, animation or discovery.
var ids = ["msi_hd4870_reference", "msi_hd5450_passive", "msi_hd5870_reference",
    "msi_twin_frozr_hd7970", "msi_r9_290x_reference", "asus_strix_fury",
    "msi_rx480_reference", "sapphire_nitro_polaris", "msi_vega64_reference",
    "asrock_challenger_rdna1", "msi_rx5700xt_reference", "sapphire_pulse_rdna2_lp",
    "asus_tuf_rdna2", "sapphire_pulse_rdna3", "asrock_taichi_rdna4",
    "asrock_challenger_arc_a380", "sparkle_titan_arc_a750", "acer_bifrost_arc_a770",
    "asrock_challenger_arc_b570", "sparkle_titan_arc_b580"]

function profile(id) {
    // w[unknown,1,2,3], h[unknown,1,2,3], inset, whole-layout offset.
    // Blowers sit at the right of their long duct; Pulse LP leaves PCB at left.
    // Proportions are illustration choices, not physical measurements.
    switch (id) {
    case "msi_hd4870_reference": return [19.0,19.0,19.0,20.0, 7.8,7.8,7.8,7.8, .245,5.0]
    case "msi_hd5450_passive": return [17.3,12.5,18.0,20.0, 6.4,7.8,7.0,7.0, .245,.00]
    case "msi_hd5870_reference": return [20.1,20.1,20.1,20.8, 7.4,7.4,7.4,7.4, .242,5.45]
    case "msi_twin_frozr_hd7970": return [19.5,13.8,19.5,20.5, 8.6,9.6,8.6,8.0, .254,-.08]
    case "msi_r9_290x_reference": return [20.0,20.0,20.0,20.8, 7.8,7.8,7.8,7.8, .245,5.20]
    case "asus_strix_fury": return [20.8,14.3,20.0,20.8, 8.6,10.0,9.0,8.6, .248,.00]
    case "msi_rx480_reference": return [18.4,18.4,18.4,20.0, 7.4,7.4,7.4,7.4, .245,4.65]
    case "sapphire_nitro_polaris": return [18.8,13.2,18.8,20.0, 9.8,10.3,9.8,8.7, .258,.00]
    case "msi_vega64_reference": return [20.1,20.1,20.1,20.8, 8.4,8.4,8.4,8.4, .245,5.10]
    case "asrock_challenger_rdna1": return [18.1,13.0,18.1,20.0, 8.8,9.9,8.8,8.0, .253,.00]
    case "msi_rx5700xt_reference": return [20.0,20.0,20.0,20.8, 8.0,8.0,8.0,8.0, .245,5.15]
    case "sapphire_pulse_rdna2_lp": return [18.2,18.2,18.2,20.0, 6.0,6.0,6.0,6.0, .245,4.1]
    case "asus_tuf_rdna2": return [20.5,14.5,20.0,20.5, 9.2,10.4,9.5,9.2, .253,.00]
    case "sapphire_pulse_rdna3": return [20.5,14.1,19.8,20.5, 8.5,9.9,9.1,8.5, .247,.00]
    case "asrock_taichi_rdna4": return [21.0,14.8,20.3,21.0, 9.7,11.0,10.0,9.7, .258,.00]
    case "asrock_challenger_arc_a380": return [12.4,12.4,18.0,20.0, 10.1,10.1,9.2,8.5, .255,.00]
    case "sparkle_titan_arc_a750": return [20.4,14.2,19.6,20.4, 8.8,10.0,9.2,8.8, .251,.00]
    case "acer_bifrost_arc_a770": return [18.7,13.8,18.7,20.0, 9.6,10.2,9.6,8.6, .260,.00]
    case "asrock_challenger_arc_b570": return [18.6,13.3,18.6,20.0, 9.1,10.1,9.1,8.3, .255,.00]
    case "sparkle_titan_arc_b580": return [20.3,14.1,19.5,20.3, 8.4,9.8,9.0,8.4, .248,.00]
    }
    return null
}

function p(d, fill) { return '<path d="'+d+'" fill="'+fill+'"/>' }
function r(x,y,w,h,radius,fill) {
    return '<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" rx="'+radius+'" fill="'+fill+'"/>'
}
function fins(x,y,w,h,count,fill) {
    var result="", step=w/count
    for (var i=0;i<count;i++) result+=r(x+i*step,y,Math.max(.7,step*.38),h,.3,fill)
    return result
}

function face(state, g, c) {
    if (!state || ids.indexOf(state.series_id) < 0) return ""
    var id=state.series_id, body=""
    switch (id) {
    case "msi_hd4870_reference":
        // Red-era long duct with an enlarged, rounded terminal fan chamber.
        body=p("M0 16L5 8H68Q96 3 100 28V76Q97 99 76 99H8L0 88Z",c.caseShade)
            +p("M2 20L7 12H64L70 20V83L62 93H8L2 86Z",c.caseTop)
            +p("M10 17H61L67 28V77L58 88H10Z",c.caseBody)
            +p("M63 12Q93 5 98 29V74Q94 95 74 97H63L70 83V24Z",c.accent)
            +p("M0 16L5 8H64V15H8V84L0 88Z",c.metal)
            +r(9,23,3,53,.5,c.edge)
        break
    case "msi_hd5450_passive":
        // Bare low-profile board at left, projecting finned heatsink at right.
        body=p("M0 17H95V84H0Z",c.caseShade)
            +r(1,22,30,55,1,c.caseBody)
            +r(31,6,68,85,1,c.metal)
            +p("M31 6H99V16H37V91H31Z",c.edge)
            +fins(38,18,58,68,10,c.caseShade)
            +r(7,28,9,20,1,c.metal)+r(21,58,6,13,.5,c.edge)
        break
    case "msi_hd5870_reference":
        // Very long narrow rectangular duct, bevelled end and straight spine.
        body=p("M0 14L8 3H94L100 15V88L94 97H7L0 84Z",c.caseShade)
            +p("M8 3H94L100 15H10L0 25V14Z",c.caseTop)
            +p("M8 17H66L71 25V84H9L3 76V24Z",c.caseBody)
            +p("M0 77L9 85H93L100 76V88L94 97H7L0 84Z",c.metal)
            +r(10,14,55,4,.5,c.accent)
            +r(10,83,51,3,.5,c.caseTop)
        break
    case "msi_twin_frozr_hd7970":
        // Open metal bridge rather than a full modern armored face plate.
        body=r(2,18,96,63,1,c.caseShade)
            +p("M0 30L7 8H91L100 23V77L94 90H8L0 71Z",c.metal)
            +p("M7 8H91L100 23H91L84 16H17L7 34H0Z",c.edge)
            +p("M0 65L10 79H86L95 69H100L94 90H8L0 71Z",c.caseTop)
            +p("M45 12H55L60 84H48Z",c.caseShade)
            +p("M87 12L99 23V74L92 83L88 69Z",c.caseBody)
            +r(90,25,4,30,.5,c.accent)
            +p("M12 91H83V95H14L8 88H12Z",c.metal)
        break
    case "msi_r9_290x_reference":
        // Broad sweeping shoulder surrounding the terminal blower well.
        body=p("M0 14L6 5H94L100 15V89L93 98H6L0 88Z",c.caseShade)
            +p("M6 5H94L100 15V26H78Q64 26 53 44L24 81H0V14Z",c.caseTop)
            +p("M0 80H23L51 42Q63 22 80 22H99V27H80Q65 27 55 46L28 85H0Z",c.accent)
            +p("M0 86H29L55 50Q64 36 68 35V86H92L100 77V89L93 98H6L0 88Z",c.caseBody)
            +r(9,16,43,4,.5,c.metal)
        break
    case "asus_strix_fury":
        // Early STRIX: narrow upper rail and a bowed pointed lower wing.
        body=p("M0 24L8 6H90L99 18V75L89 91H71L56 100H25L9 88L0 72Z",c.caseShade)
            +p("M0 24L8 6H90L99 18L93 26H77L68 18H22L12 31H0Z",c.caseTop)
            +p("M0 65L13 77H29L47 69H65L79 78H99L89 91H71L56 100H25L9 88L0 72Z",c.caseBody)
            +p("M9 78L28 87L56 89L73 80H90L84 88H70L55 96H26L11 85Z",c.accent)
            +p("M30 15H36L42 78H34Z",c.caseTop)
            +p("M62 15H69L64 80H57Z",c.caseTop)
            +p("M3 22L10 11H18L10 29Z",c.metal)
        break
    case "msi_rx480_reference":
        // Compact rectangular perforated face; one continuous straight duct.
        body=r(0,6,100,89,3,c.caseShade)
            +r(3,10,94,81,2,c.caseBody)
            +r(0,10,5,81,1,c.accent)
            +r(7,10,58,7,1,c.caseTop)
            +r(7,84,58,4,.5,c.metal)
            +fins(12,30,48,4,9,c.caseTop)
            +fins(12,65,48,4,9,c.caseTop)
        break
    case "sapphire_nitro_polaris":
        // Short soft rectangle and two large exposed wells with a slim waist.
        body=r(0,5,100,92,5,c.caseShade)
            +p("M4 9H96V20H92Q76 7 60 23H40Q24 7 8 21H4Z",c.caseTop)
            +p("M4 79H9Q25 94 40 78H60Q76 94 92 79H96V93H4Z",c.caseBody)
            +p("M45 16H55L60 84H41Z",c.metal)
            +r(1,25,5,50,2,c.caseTop)+r(94,25,5,50,2,c.caseTop)
            +r(8,11,3,7,.5,c.edge)+r(89,84,3,7,.5,c.edge)
        break
    case "msi_vega64_reference":
        // Longer, thicker continuous slab than Polaris; no angular armor.
        body=r(0,3,100,96,2,c.caseShade)
            +r(3,8,94,84,1,c.caseBody)
            +r(0,6,5,89,.5,c.accent)
            +r(7,8,88,5,.5,c.caseTop)
            +r(7,87,88,5,.5,c.metal)
            +p("M10 19H62V23H10ZM10 76H62V80H10Z",c.caseTop)
        break
    case "asrock_challenger_rdna1":
        // Compact two-well shell with opposing triangular center bridges.
        body=p("M0 21L9 4H91L100 20V82L90 97H10L0 81Z",c.caseShade)
            +p("M9 4H91L100 20H78L64 34H36L22 19H0Z",c.caseTop)
            +p("M0 64L21 82H36L50 65L65 81H82L100 66V82L90 97H10L0 81Z",c.caseBody)
            +p("M34 15H45L64 83H52Z",c.metal)
            +p("M52 16H64L46 82H36Z",c.caseTop)
            +p("M5 15L13 8H25L17 17Z",c.edge)
            +p("M74 88H88L94 79H84Z",c.edge)
        break
    case "msi_rx5700xt_reference":
        // The distinctive dented upper edge and fine horizontal duct ribs.
        body=p("M0 12Q1 4 10 4H58Q63 5 69 13Q74 20 80 14L91 4H96L100 13V88L94 97H8L0 87Z",c.caseShade)
            +p("M0 12Q1 4 10 4H58Q63 5 69 13Q74 20 80 14L91 4H96L100 13V20H91L81 24Q73 30 65 22L58 14H7L0 21Z",c.metal)
            +p("M3 22H63V87H95L99 81V88L94 97H8L3 87Z",c.caseBody)
            +r(8,27,53,3,.4,c.caseTop)+r(8,39,53,3,.4,c.caseTop)
            +r(8,51,53,3,.4,c.caseTop)+r(8,63,53,3,.4,c.caseTop)
            +r(8,75,53,3,.4,c.caseTop)
        break
    case "sapphire_pulse_rdna2_lp":
        // Very low-profile PCB left, with the single fan in the right heatsink.
        body=r(0,16,100,72,1,c.caseShade)
            +r(2,21,31,60,1,c.caseBody)
            +p("M31 13H95L100 22V82L93 93H31Z",c.caseTop)
            +p("M36 21H92L97 29V77L88 85H36Z",c.caseShade)
            +p("M32 14H95L100 22V29H94L90 22H43L35 33H31Z",c.metal)
            +p("M36 77L44 85H89L95 77H100V82L93 93H31V80Z",c.accent)
            +r(8,29,10,18,1,c.metal)+r(21,54,7,17,.5,c.edge)
        break
    case "asus_tuf_rdna2":
        // Broad metal plates and diagonal partitions; modest raised top cap.
        body=p("M0 18L10 4H70L76 0H93L100 13V83L89 98H11L0 85Z",c.caseShade)
            +p("M0 18L10 4H70L76 0H93L100 13V24H83L74 15H16L6 31H0Z",c.metal)
            +p("M0 69L13 82H87L100 66V83L89 98H11L0 85Z",c.caseTop)
            +p("M28 13H36L43 86H35Z",c.edge)
            +p("M60 13H69L63 86H54Z",c.metal)
            +p("M9 85H25L19 94H11ZM38 85H49L44 94H33ZM67 85H79L73 94H61Z",c.caseShade)
        break
    case "sapphire_pulse_rdna3":
        // Flat long face with stepped end blocks and thin angular lower trim.
        body=p("M0 15H9V5H92V13H100V85H91V96H8V87H0Z",c.caseShade)
            +p("M9 5H92V13H100V22H83L78 16H21L16 22H0V15H9Z",c.caseTop)
            +p("M0 76H18L23 83H76L83 76H100V85H91V96H8V87H0Z",c.caseBody)
            +p("M10 87H30L35 92H70L77 85H91V89H79L72 96H32L27 91H10Z",c.accent)
            +p("M32 17H38L43 82H35ZM62 17H68L63 82H56Z",c.caseTop)
            +r(2,25,4,47,.5,c.metal)+r(94,25,4,47,.5,c.metal)
        break
    case "asrock_taichi_rdna4":
        // Angular cage with an elevated central hexagonal collar and fins.
        body=p("M0 25L9 7H29L37 15L43 0H58L64 15L74 7H92L100 24V79L91 97H72L64 88L58 100H43L36 88L27 97H8L0 79Z",c.caseShade)
            +p("M0 25L9 7H29L37 15L43 0H58L64 15L74 7H92L100 24L88 30L78 19H70L61 30H39L31 20H19L9 36Z",c.metal)
            +p("M0 64L13 76H29L37 66L44 82H57L64 65H72L84 78H100V79L91 97H72L64 88L58 100H43L36 88L27 97H8L0 79Z",c.caseTop)
            +p("M40 15L34 35V65L42 85H46L39 63V37L46 15ZM56 15L64 35V65L57 85H53L59 63V37L52 15Z",c.edge)
            +p("M3 25L11 12H19L10 30ZM82 85L90 71L97 78L88 92Z",c.accent)
        break
    case "asrock_challenger_arc_a380":
        // Short ITX square with two broad opposing diagonal shoulder plates.
        body=p("M0 19L12 3H85L100 19V84L86 98H14L0 83Z",c.caseShade)
            +p("M0 19L12 3H85L100 19V34H86L70 17H28L12 35H0Z",c.caseTop)
            +p("M0 64H14L30 82H69L86 64H100V84L86 98H14L0 83Z",c.caseBody)
            +p("M7 19L18 9H35L20 25H7Z",c.metal)
            +p("M67 91L80 77H93L84 91Z",c.edge)
            +r(2,36,5,27,1,c.caseTop)+r(93,36,5,27,1,c.caseTop)
        break
    case "sparkle_titan_arc_a750":
        // A rectangular rail frame with three projecting octagonal chambers.
        body=p("M0 17L6 6H94L100 17V85L94 96H6L0 85Z",c.caseShade)
            +p("M0 17L6 6H94L100 17V27H94L85 16H75L67 26H61L53 16H43L35 26H28L19 16H9L0 30Z",c.caseTop)
            +p("M0 71L9 83H19L28 74H35L43 83H53L61 74H67L75 83H85L94 72H100V85L94 96H6L0 85Z",c.caseBody)
            +p("M29 19H35V81H29ZM62 19H68V81H62Z",c.metal)
            +r(7,8,85,4,.5,c.edge)
        break
    case "acer_bifrost_arc_a770":
        // Smaller blower chamber left and larger axial opening right. The
        // central renderer supplies their distinct fan types and unequal sizes.
        body=p("M0 15L9 4H91L100 16V86L89 97H9L0 85Z",c.caseShade)
            +p("M0 15L9 4H91L100 16H63L54 25H5L0 31Z",c.metal)
            +p("M0 73H46L55 83H98L89 97H9L0 85Z",c.caseTop)
            +p("M44 21H54L61 35V69L52 83H43L50 68V35Z",c.caseBody)
            +p("M4 31H10V68H4ZM94 27H99V76H94Z",c.edge)
            +r(10,10,29,4,.5,c.accent)
        break
    case "asrock_challenger_arc_b570":
        // Open long wells, a folded Z bridge and an inset upper-left shoulder.
        body=p("M0 28L13 6H90L100 19V82L88 98H12L0 82Z",c.caseShade)
            +p("M0 28L13 6H90L100 19V26H74L65 17H25L16 30H0Z",c.caseTop)
            +p("M0 67L15 81H39L49 70H64L77 83H100L88 98H12L0 82Z",c.caseBody)
            +p("M38 16H53L61 33L51 66L65 84H51L40 67L50 33Z",c.metal)
            +p("M4 29L17 12H31L23 23H18L12 32Z",c.edge)
            +r(15,87,66,5,.7,c.caseTop)
        break
    case "sparkle_titan_arc_b580":
        // New TITAN's shallow, separately beveled metal panels and broad forks.
        body=p("M0 19L10 4H93L100 15V84L90 97H9L0 85Z",c.caseShade)
            +p("M0 19L10 4H93L100 15V23H86L79 15H69L62 26H54L46 15H36L28 26H18L10 17L0 30Z",c.metal)
            +p("M0 70L10 81H19L28 71H36L44 83H54L62 71H70L78 83H88L100 70V84L90 97H9L0 85Z",c.caseTop)
            +p("M28 15H36L43 31L35 48L43 82H35L27 49L35 31ZM62 15H70L63 34L71 51L63 83H55L63 51L55 34Z",c.caseBody)
            +r(10,5,82,4,.4,c.accent)
        break
    }
    return body
}
