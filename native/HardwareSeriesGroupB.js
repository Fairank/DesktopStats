.pragma library

// Original, static casing studies distilled from the official representative
// front views linked in hardware_catalog_group_b.py. Not factory drawings or
// geometry shared by every SKU. fan_count is never inferred here. The caller
// owns the transform, verified circular fans, bracket and contacts; face()
// returns only the casing in a normalized 100 x 100 coordinate system.

var ids = ["palit_gamerock", "palit_jetstream", "palit_gamingpro",
    "gainward_phantom", "gainward_phoenix", "gainward_ghost",
    "galax_hof", "galax_ex_gamer", "galax_sg", "inno3d_ichill_x3",
    "inno3d_ichill_x4", "inno3d_x3", "inno3d_twin_x2"]

function profile(id) {
    // Illustration width[unknown,1,2,3], height[unknown,1,2,3], inset, offset.
    // Proportions do not claim measured physical product dimensions.
    switch (id) {
    case "palit_gamerock": return [19.8,14.9,20.2,21.1, 10.4,11.4,10.2,9.4,.257,.00]
    case "palit_jetstream": return [19.5,14.5,19.8,20.9, 9.0,10.0,9.1,8.2,.242,.00]
    case "palit_gamingpro": return [19.5,14.4,19.9,20.9, 9.7,10.7,9.7,8.7,.250,.02]
    case "gainward_phantom": return [19.7,14.8,20.0,21.0, 9.9,11.0,9.9,9.0,.253,.00]
    case "gainward_phoenix": return [19.7,14.8,20.1,21.0, 10.3,11.3,10.2,9.3,.255,.00]
    case "gainward_ghost": return [18.8,13.4,19.0,20.6, 9.4,10.4,9.5,8.5,.248,.00]
    case "galax_hof": return [20.0,15.0,20.4,21.1, 10.5,11.5,10.5,9.5,.258,.00]
    case "galax_ex_gamer": return [19.4,14.1,19.8,20.8, 9.9,11.0,10.0,9.0,.252,.00]
    case "galax_sg": return [19.7,14.7,20.0,21.0, 10.2,11.2,10.2,9.3,.258,.00]
    case "inno3d_ichill_x3": return [19.7,14.5,20.0,21.0, 10.1,11.2,10.0,9.1,.253,.00]
    case "inno3d_ichill_x4": return [19.8,14.7,20.1,21.0, 10.8,11.7,10.7,9.8,.258,.00]
    case "inno3d_x3": return [19.4,14.0,19.8,20.8, 8.9,9.9,9.0,8.1,.242,.00]
    case "inno3d_twin_x2": return [18.9,13.6,19.3,20.7, 9.5,10.5,9.6,8.6,.246,.00]
    }
    return null
}

function p(d, fill) {
    return '<path d="' + d + '" fill="' + fill + '"/>'
}

function r(x,y,w,h,radius,fill) {
    return '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h
        + '" rx="' + radius + '" fill="' + fill + '"/>'
}

function wells(g, c, mode) {
    // These broad, polygonal shroud facets sit around confirmed fan positions.
    // No circles and no invented openings when front cooling is unknown.
    if (!g || !g.centers || !g.centers.length)
        return p("M13 26H82L89 40V75H18L11 62Z", c.caseTop)
    var result = ""
    for (var index = 0; index < g.centers.length; index++) {
        var at = (g.centers[index] - g.x) / g.w * 100
        var half = g.radius / g.w * 100 + 3.0
        var left = Math.max(2, at - half), right = Math.min(98, at + half)
        if (mode === "prism") {
            result += p("M"+left+" 26L"+(at-3)+" 8L"+right+" 26V74L"+(at+3)
                +" 93L"+left+" 74Z", c.caseTop)
                + p("M"+left+" 26L"+(at-3)+" 8L"+(at+1)+" 24L"+left+" 47Z", c.metal)
                + p("M"+right+" 52V74L"+(at+3)+" 93L"+(at-1)+" 76Z", c.caseShade)
        } else if (mode === "armor") {
            result += p("M"+left+" 28L"+(left+5)+" 15H"+(right-5)+"L"+right
                +" 28V73L"+(right-5)+" 87H"+(left+5)+"L"+left+" 73Z",c.caseShade)
                + p("M"+(left+4)+" 26L"+(left+8)+" 17H"+(right-5)+"L"+right
                +" 28L"+(right-8)+" 32H"+(left+4)+"Z",c.metal)
                + p("M"+left+" 69L"+(left+6)+" 78H"+(right-4)+"L"+(right-8)
                +" 87H"+(left+5)+"L"+left+" 73Z",c.caseTop)
        } else if (mode === "ex") {
            // EX Gamer's wider central bay and inward-pointing end facets.
            var middle = g.centers.length === 3 && index === 1
            var top = middle ? 1 : 17, bottom = middle ? 99 : 83
            result += p("M"+left+" 30L"+(left+6)+" "+top+"H"+(right-6)+"L"+right
                +" 30V70L"+(right-6)+" "+bottom+"H"+(left+6)+"L"+left+" 70Z",c.caseTop)
        }
    }
    return result
}

function face(state, g, c) {
    if (!state || ids.indexOf(state.series_id) < 0
            || state.series_id.split("_")[0] !== state.board_vendor) return ""
    switch (state.series_id) {
    case "palit_gamerock":
        // GameRock's crystalline surround: large unequal triangular facets.
        return p("M0 19L9 4L28 9L38 0L57 7L74 2L91 9L100 22V81L91 98L72 91L58 100L38 93L23 99L6 89Z",c.caseBody)
            + p("M0 19L9 4L28 9L19 30Z M28 9L38 0L57 7L48 30Z M57 7L74 2L91 9L80 30Z",c.metal)
            + p("M9 4L19 30L28 9L37 29L38 0Z M74 2L80 30L91 9L100 22L94 40Z",c.caseTop)
            + p("M6 89L20 70L23 99L38 93L31 76Z M38 93L48 75L58 100L72 91L63 73Z M72 91L81 73L91 98L100 81Z",c.caseShade)
            + p("M3 36L10 25L12 70L5 81Z M89 26L98 39L96 73L87 84Z",c.caseTop)
            + p("M40 4L48 8L45 17Z M77 91L83 84L88 91Z",c.accent)
    case "palit_jetstream":
        // JetStream's restrained jet-black block pattern and long flat rails.
        return r(0,4,100,92,3,c.caseBody)
            + p("M0 4H100V20H77V13H52V23H26V15H0Z",c.caseShade)
            + p("M0 80H25V88H53V78H78V85H100V96H0Z",c.caseShade)
            + r(0,19,5,61,1,c.caseTop) + r(95,20,5,65,1,c.caseTop)
            + p("M7 5H26V12H7Z M54 5H77V11H54Z M27 89H51V95H27Z M79 86H94V95H79Z",c.caseTop)
            + r(43,5,14,3,1,c.accent)
    case "palit_gamingpro":
        // GamingPro's broad iron/silver industrial diagonals, not pinstripes.
        return p("M3 0H91L100 17V88L91 100H5L0 88V13Z",c.caseBody)
            + p("M3 0H41L30 30H0V13Z M53 0H72L61 25H42Z",c.metal)
            + p("M65 0H91L100 17V34H80L88 12H61Z M0 63H20L7 100H5L0 88Z",c.caseShade)
            + p("M32 74H51L40 100H21Z M63 76H100V88L91 100H53Z",c.caseTop)
            + p("M35 0H42L30 30H23Z M51 74H58L47 100H40Z",c.edge)
            + p("M67 84H75L68 98H60Z M78 84H84L77 98H71Z",c.accent)
    case "gainward_phantom":
        // Phantom: two broad lightning shoulders on a dark, low armor frame.
        return p("M0 18L7 5H29L34 10H60L66 3H91L100 20V80L93 96H68L62 90H37L31 98H8L0 81Z",c.caseBody)
            + p("M0 18L7 5H29L39 27L31 35L24 19H8L3 36Z M60 10L66 3H91L100 20L92 31L86 17H70L64 29Z",c.caseTop)
            + p("M8 96L19 71L30 66L24 85H37L31 98Z M62 90L76 67L85 65L79 84H93L88 96H68Z",c.caseShade)
            + p("M29 5L40 26L33 35L27 20H17L22 14H29Z M66 95L76 74L82 72L77 86H88L84 92H77Z",c.metal)
            + p("M31 9L37 22L34 25L28 13Z M71 88L77 77L81 75L75 89Z",c.accent)
    case "gainward_phoenix":
        // Phoenix's prismatic, interlocked front panels and beveled openings.
        return p("M0 26L11 2H29L35 9H64L71 2H90L100 25V76L90 98H71L64 90H35L29 98H10L0 76Z",c.caseBody)
            + wells(g,c,"prism")
            + p("M0 27L11 2H20L12 23L5 42Z M88 77L96 61L100 75L90 98H81Z",c.metal)
            + p("M32 7H37L42 21H37Z M64 79H69L74 94H69Z",c.accent)
            + p("M0 52L5 45V74L12 88L8 94L0 76Z M92 8L100 25V48L95 54V28L88 14Z",c.caseShade)
    case "gainward_ghost":
        // Ghost's compact, squared two-zone enclosure with a broad diagonal.
        return r(0,4,100,92,4,c.caseBody)
            + p("M0 4H56L38 31H0Z M67 70H100V96H49Z",c.caseShade)
            + p("M54 4H66L42 39H31Z M46 63H58L35 96H23Z",c.caseTop)
            + r(0,25,5,51,1,c.caseShade) + r(95,24,5,52,1,c.caseShade)
            + r(66,8,23,4,1,c.caseTop) + r(11,86,22,4,1,c.caseTop)
            + r(74,8,13,3,1,c.accent)
    case "galax_hof":
        // The cited HOF Extreme uses a flowing crystalline front, not the
        // separate older crown cooler. The fourth fan is on the back plane.
        return p("M0 29Q3 9 18 8Q29 1 43 8Q57 0 70 7Q92 0 99 20L100 74Q97 95 79 94Q65 101 51 93Q34 101 20 93Q2 96 0 79Z",c.metal)
            + p("M0 29Q5 11 18 8Q31 5 43 8L36 22Q24 16 16 28L8 55L0 66Z",c.caseTop)
            + p("M42 8Q58 1 70 7Q86 3 99 20L94 41Q81 19 65 20L56 26L61 8Z",c.edge)
            + p("M0 74Q14 91 29 79L43 74Q35 93 20 93Q2 96 0 79Z M51 93L63 78Q84 85 100 62V74Q97 95 79 94Q65 101 51 93Z",c.caseTop)
            + p("M32 9L43 8L36 22L29 20Z M67 7L78 7L67 20L61 21Z M79 94L86 84L96 82L91 92Z",c.caseBody)
            + p("M13 83L22 88L28 84L22 81Z",c.accent)
    case "galax_ex_gamer":
        // EX Gamer's tall central bay with inward-pointing endcap shoulders.
        return p("M6 5H92L100 20L95 38L100 59L96 82L91 95H7L0 80L6 61L0 41L2 22Z",c.caseBody)
            + wells(g,c,"ex")
            + p("M6 5H34L26 20L14 13L4 31L2 22Z M68 5H92L100 20L95 31L85 14L76 22Z",c.metal)
            + p("M0 80L7 95H34L26 80L14 88L6 69Z M68 95H91L96 82L95 70L85 87L77 79Z",c.caseShade)
            + p("M31 19L37 7H42L36 23Z M62 77L68 81L63 94H58Z",c.caseShade)
            + p("M42 5H57V9H42Z",c.accent)
    case "galax_sg":
        // SG's deep octagonal bays and thick stepped armor end caps.
        return p("M0 25L10 4H31L37 0H64L69 5H91L100 26V77L90 97H66L61 100H34L29 95H9L0 77Z",c.caseBody)
            + wells(g,c,"armor")
            + p("M0 25L10 4H16L10 29V72L16 96H9L0 77Z M91 5L100 26V77L90 97H84L90 73V29L84 5Z",c.caseTop)
            + p("M0 32H7V67H0Z M93 32H100V67H93Z",c.caseShade)
            + p("M29 5L35 0H44L36 14H25Z M61 86H72L65 98L61 100H54Z",c.metal)
            + p("M31 6L36 2H40L35 11H28Z M63 89H68L64 96H59Z",c.accent)
    case "inno3d_ichill_x3":
        // iCHILL X3's asymmetric multi-level armor and angular wing sections.
        return p("M0 26L6 7H27L35 13L49 4H75L84 0H96L100 20L96 38L100 66L91 88H72L64 98H41L33 91H12L2 77Z",c.caseBody)
            + p("M6 7H27L35 13L27 30H2Z M49 4H75L84 0H96L100 20L66 20L57 33L39 27Z",c.caseShade)
            + p("M35 13L49 4L57 13L43 32L27 30Z M66 20H87L96 8L99 20L96 31H75Z",c.caseTop)
            + p("M2 77L12 88L31 74L41 98H33L27 89H12Z M64 98L72 78L91 75L100 66L91 88H72Z",c.metal)
            + p("M25 9L31 12L22 26H16Z M73 82L78 79L73 92H68Z",c.accent)
    case "inno3d_ichill_x4":
        // X4's raised long side plate occupies the roof. The real side fan is
        // perpendicular to this front view and is deliberately not pictured.
        return p("M0 31L6 12H36L44 3H91L100 15L94 32L100 50L96 76L87 91H68L59 100H36L29 91H10L0 75Z",c.caseBody)
            + p("M6 12H36L44 3H91L100 15L93 29H48L38 20H3Z",c.metal)
            + p("M44 3H91L100 15L95 23H50L40 15Z",c.caseTop)
            + p("M50 9H86L92 15L88 20H47Z",c.accent)
            + p("M0 31L9 21H27L35 33L27 39H8L2 56Z M69 32H94L100 50L92 59L86 40H63Z",c.caseShade)
            + p("M0 75L10 91H29L36 100H47L35 79L18 76L9 64Z M59 100L68 91H87L96 76L86 72L76 83H65Z",c.caseTop)
            + p("M35 79L42 85L47 100H41L31 86Z M73 84L79 80L86 82L80 89H69Z",c.metal)
    case "inno3d_x3":
        // The actual X3 OC has a large black/silver diagonal split, covering
        // roughly the right two-thirds; it is not an iCHILL armor drawing.
        return p("M0 5H94L100 17L96 95H3L0 87Z",c.caseBody)
            + p("M42 5H94L100 17L96 95H31Z",c.metal)
            + p("M0 5H42L38 20H0Z M3 82H33L31 95H3L0 87Z",c.caseShade)
            + p("M42 5H94L100 17H38Z",c.caseTop)
            + p("M35 28L42 5H46L35 52H30Z",c.edge)
            + p("M95 29H99L97 80H93Z",c.caseTop)
            + r(74,7,13,3,1,c.accent)
    case "inno3d_twin_x2":
        // TWIN X2: shorter/taller two-zone slab and an almost central division.
        return p("M0 5H91L100 18L96 95H2L0 86Z",c.caseBody)
            + p("M48 5H91L100 18L96 95H44Z",c.metal)
            + p("M0 5H48L46 18H0Z M48 5H91L100 18H47Z",c.caseTop)
            + p("M0 76H44V95H2L0 86Z",c.caseShade)
            + p("M46 20H50L47 86H43Z M95 23H99L97 81H93Z",c.caseTop)
            + p("M8 8H28V11H8Z M70 8H84V11H70Z",c.accent)
    }
    return ""
}
