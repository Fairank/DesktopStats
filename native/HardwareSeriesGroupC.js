.pragma library

// Original simplified casing constructions, sourced by representative official
// models in hardware_catalog_group_c.py. Proportions are illustrative, not SKU
// measurements. The parent owns normalization, the 24-unit transform and real
// circular fans. These functions add no fan, bracket, contact, text or animation.

var ids = ["colorful_vulcan", "colorful_ultra", "colorful_advanced", "maxsun_icraft",
    "maxsun_terminator", "yeston_sakura", "yeston_atlantis", "biostar_radeon",
    "nvidia_founders", "amd_reference", "intel_limited"]

function profile(id) {
    // Unknown/zero, one, two, three confirmed fans: four widths, four heights,
    // fan inset and layout offset. A series profile never chooses a fan count.
    switch (id) {
    case "colorful_vulcan": return [19.9,14.5,20.1,21.0, 10.1,11.1,10.0,9.0, .252,.00]
    case "colorful_ultra": return [19.2,13.9,19.6,20.8, 9.4,10.5,9.4,8.5, .249,-.05]
    case "colorful_advanced": return [19.7,14.4,20.2,21.0, 10.0,11.3,10.1,9.1, .255,.00]
    case "maxsun_icraft": return [19.4,14.0,19.8,20.7, 9.5,10.6,9.5,8.6, .246,.00]
    case "maxsun_terminator": return [18.9,13.5,19.1,20.6, 9.1,10.0,9.0,8.2, .240,-.06]
    case "yeston_sakura": return [19.8,14.3,20.0,20.9, 9.7,10.8,9.8,8.8, .251,.03]
    case "yeston_atlantis": return [19.5,14.2,19.9,20.8, 10.2,11.2,10.1,9.2, .256,.00]
    case "biostar_radeon": return [18.1,12.8,18.5,20.3, 9.3,10.1,9.1,8.1, .244,.00]
    case "nvidia_founders": return [19.7,13.7,20.5,21.0, 9.2,10.6,9.4,8.4, .265,.00]
    case "amd_reference": return [19.3,13.8,19.7,20.7, 9.6,10.7,9.7,8.7, .248,.00]
    case "intel_limited": return [18.6,13.4,18.9,20.4, 9.5,10.4,9.6,8.5, .253,.00]
    }
    return null
}

function p(d, fill) {
    return '<path d="' + d + '" fill="' + fill + '"/>'
}

function r(x,y,w,h,radius,fill) {
    return '<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h
        +'" rx="'+radius+'" fill="'+fill+'"/>'
}

function fanPositions(g) {
    return g.centers.map(function(at) { return (at-g.x)/g.w*100 })
}

function metalBays(g,c) {
    if (!g.centers.length) return p("M13 28H85V73H16L10 62V40Z",c.caseShade)
    var result="", positions=fanPositions(g)
    positions.forEach(function(at) {
        var half=g.radius/g.w*100+3
        result+=p("M"+(at-half)+" 30L"+(at-half+6)+" 14H"+(at+half-6)+"L"+(at+half)
            +" 30V72L"+(at+half-6)+" 88H"+(at-half+6)+"L"+(at-half)+" 72Z",c.caseShade)
    })
    return result
}

function face(state,g,c) {
    var id=state.series_id
    if (ids.indexOf(id)<0 || id.split("_")[0]!==state.board_vendor) return ""
    var result=""
    switch (id) {
    case "colorful_vulcan":
        // 4070 Ti Vulcan: deep angular armor and the separate upper LCD module.
        result=p("M0 29L9 10H61V0H88L94 10L100 22V83L89 100H12L0 82Z",c.caseShade)
            +p("M0 29L9 10H61L57 22H25L15 39H0Z",c.caseTop)
            +p("M0 62H14L29 83H78L87 69H100V83L89 100H12L0 82Z",c.caseBody)
            +p("M60 0H88L94 10H59Z",c.metal)
            +r(65,2,19,7,1,c.disk)
            +p("M84 23H100V48L91 60H84Z",c.metal)
            +p("M8 28L17 16H25L16 28Z",c.accent)
        break
    case "colorful_ultra":
        // Ultra W's broad pop-art diagonal fields and asymmetric chamfered ends.
        result=p("M0 12H86L100 28V90L90 100H9L0 84Z",c.metal)
            +p("M0 12H44L22 45H0Z",c.edge)
            +p("M44 12H65L15 90H0V78Z",c.caseTop)
            +p("M75 12H86L100 28V53L76 91H55Z",c.caseShade)
            +p("M20 100L46 61H63L38 100Z",c.caseBody)
            +p("M82 13H90L100 25V38Z",c.accent)
        break
    case "colorful_advanced":
        // Three-fan representative has a larger central fan. The parent may
        // supply separate radii; this wide center chamber leaves that space.
        result=p("M0 22L10 8H34L40 0H62L69 8H90L100 22V80L89 94H68L62 100H38L32 94H10L0 80Z",c.caseShade)
            +p("M0 22L10 8H34L40 0H62L69 8H90L100 22V31H82L72 20H65L59 11H44L38 20H20L10 34H0Z",c.metal)
            +p("M0 68H10L20 82H34L41 92H60L67 82H81L90 69H100V80L89 94H68L62 100H38L32 94H10L0 80Z",c.caseTop)
        if (g.centers.length) {
            var positions=fanPositions(g), middle=positions[Math.floor(positions.length/2)]
            if (positions.length===2) middle=(positions[0]+positions[1])/2
            var half=Math.min(27,g.radius/g.w*100*1.18+3)
            result+=p("M"+(middle-half)+" 27L"+(middle-half+6)+" 6H"+(middle+half-6)+"L"+(middle+half)
                +" 27V75L"+(middle+half-6)+" 95H"+(middle-half+6)+"L"+(middle-half)+" 75Z",c.accent)
            result+=p("M"+(middle-half+3)+" 28L"+(middle-half+8)+" 11H"+(middle+half-8)+"L"+(middle+half-3)
                +" 28V74L"+(middle+half-8)+" 90H"+(middle-half+8)+"L"+(middle-half+3)+" 74Z",c.disk)
        } else {
            result+=p("M32 23H68L77 42V68L66 80H34L24 67V42Z",c.caseBody)
        }
        break
    case "maxsun_icraft":
        // iCraft GT: smooth uninterrupted face, soft corners and long upper rim.
        result=p("M0 19Q0 2 17 2H87Q100 2 100 18V83Q100 98 85 98H16Q0 98 0 81Z",c.caseTop)
            +p("M3 23Q3 9 18 9H85Q97 9 97 22V78Q97 88 85 88H17Q3 88 3 77Z",c.metal)
            +p("M0 75H5Q5 87 17 87H85Q96 87 96 75H100V83Q100 98 85 98H16Q0 98 0 81Z",c.caseShade)
            +r(7,10,87,5,2,c.edge) +r(55,1,34,3,1,c.accent)
        break
    case "maxsun_terminator":
        // Terminator X3: hard end slopes and large oblique connecting planes.
        result=p("M0 22L12 4H89L100 17V83L88 98H9L0 85Z",c.caseShade)
            +p("M0 22L12 4H41L31 23H18L8 39H0Z",c.caseTop)
            +p("M65 4H89L100 17V30H84L72 47H55Z",c.metal)
            +p("M0 70H16L26 55H42L21 98H9L0 85Z",c.caseBody)
            +p("M64 55H80L91 72H100V83L88 98H45Z",c.caseTop)
            +p("M41 4H50L36 30H27Z",c.accent)
        break
    case "yeston_sakura":
        // RX 7800 XT Sakura: two broad crossing, curved ribbon supports.
        result=p("M0 20L8 4H89L100 16V80L90 98H6L0 84Z",c.caseTop)
            +p("M8 17H90L97 27V73L87 87H9L4 76V31Z",c.caseShade)
            +p("M0 17Q35 22 100 85V98Q67 77 44 56Q21 37 0 34Z",c.edge)
            +p("M0 80Q46 61 91 4H100V21Q66 66 12 98H0Z",c.metal)
            +p("M0 4H14L8 23H0ZM87 98L94 77H100V98Z",c.accent)
        break
    case "yeston_atlantis":
        // Atlantis: layered horizontal ribbon rails and rounded end windows.
        result=p("M0 25Q0 11 9 3H90Q100 11 100 27V76Q100 90 89 98H10Q0 89 0 74Z",c.caseTop)
            +p("M5 29Q5 20 14 16H86Q95 22 95 31V70Q95 81 86 86H14Q5 80 5 70Z",c.caseShade)
            +p("M0 30Q19 23 44 27Q68 30 100 18V29Q72 43 44 38Q18 34 0 43Z",c.edge)
            +p("M0 64Q31 79 58 70Q83 62 100 71V84Q79 74 58 82Q29 92 0 76Z",c.metal)
            +p("M5 4H90L96 13H11ZM9 98L3 88H88L95 79V91L89 98Z",c.metal)
            +r(12,7,25,4,1,c.accent)
        break
    case "biostar_radeon":
        // A deliberately restrained product-line enclosure, not an invented
        // marketing series. The reviewed model currently keeps cooling unknown.
        result=p("M0 12H90L100 22V88H11L0 77Z",c.caseShade)
            +p("M5 17H86L94 27V80H15L5 70Z",c.caseBody)
            +p("M0 12H18V88H11L0 77Z",c.caseTop)
            +p("M82 12H90L100 22V88H82V77H91V28H82Z",c.metal)
            +p("M18 17H80L72 28H18Z",c.metal)
            +r(85,35,6,20,1,c.accent)
        if (!g.centers.length) result+=p("M27 39H68L76 50V66H27Z",c.caseTop)
        break
    case "nvidia_founders":
        // 5090 FE's continuous rounded perimeter and central rigid X brace.
        // Unknown FE models still get a neutral solid face, never fake openings.
        result=r(0,0,100,100,12,c.metal) +r(3,4,94,92,9,c.disk)
            +p("M0 17Q0 0 14 0H33L51 40L69 0H86Q100 0 100 17H94Q94 6 85 6H74L57 49L75 94H85Q94 94 94 82H100Q100 100 86 100H69L51 58L33 100H14Q0 100 0 83H6Q6 94 15 94H28L45 49L28 6H15Q6 6 6 17Z",c.caseTop)
            +p("M30 2H35L53 41L70 2H75L57 49L75 98H70L53 58L35 98H30L47 49Z",c.edge)
        if (!g.centers.length) result+=p("M12 24H33L44 49L32 76H12ZM72 24H88V76H71L60 49Z",c.caseShade)
        break
    case "amd_reference":
        // RX 7900 XTX: scalloped armor shoulders and an inset wave-like rim.
        result=p("M0 13H13L20 19L28 8H42L49 18L57 8H72L80 18L88 8H96L100 21V82L92 95H79L71 87L62 98H49L42 88L33 98H18L11 89H0Z",c.caseShade)
            +p("M0 13H13L20 19L28 8H42L49 18L57 8H72L80 18L88 8H96L100 21V31H88L80 25L72 33H58L49 27L41 34H26L18 28H0Z",c.caseTop)
            +p("M0 72H12L20 80H32L41 72L49 80H62L71 72L80 81H91L100 70V82L92 95H79L71 87L62 98H49L42 88L33 98H18L11 89H0Z",c.metal)
            +p("M88 8H94L100 20V31H94V22Z",c.accent)
        break
    case "intel_limited":
        // A770 Limited Edition: soft unibody corners and a continuous light rim.
        result=r(0,0,100,100,15,c.caseTop) +r(2,2,96,96,13,c.edge)
            +r(4,5,92,90,11,c.disk)
            +p("M4 29Q4 5 25 5H76Q96 5 96 29V38H92V29Q92 10 76 10H25Q8 10 8 29V38H4Z",c.caseBody)
            +p("M4 67H8V73Q8 90 25 90H76Q92 90 92 73V67H96V73Q96 95 76 95H25Q4 95 4 73Z",c.caseShade)
            +r(40,2,35,3,1,c.accent)
        if (!g.centers.length) result+=r(15,29,70,44,7,c.caseBody)
        break
    }
    return result
}
