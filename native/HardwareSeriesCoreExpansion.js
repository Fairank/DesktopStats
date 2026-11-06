.pragma library

// Source-linked representative casing language. Raw normalized SVG only;
// actual fans, contacts and the single retained texture belong to the caller.
var ids = ["asus_astral","asus_prime","asus_proart","msi_expert","msi_vanguard",
    "msi_inspire","msi_shadow","gigabyte_gaming_oc","gigabyte_eagle","zotac_twin_edge",
    "zotac_solid","zotac_amp_infinity","zotac_amp_airo","zotac_trinity",
    "sapphire_pure","powercolor_fighter","powercolor_reaper"]

function profile(id) {
    switch(id) {
    case "asus_astral":return [20.4,15.0,20.3,21.0,10.6,11.8,10.5,9.8,.252,0]
    case "asus_prime":return [19.0,13.8,19.3,20.7,9.1,10.4,9.3,8.3,.246,0]
    case "asus_proart":return [19.6,14.0,19.7,20.8,9.6,10.5,9.5,8.6,.248,0]
    case "msi_expert":return [20.2,20.4,20.4,20.8,10.1,10.2,10.0,9.1,.25,0]
    case "msi_vanguard":return [20.0,14.7,20.0,21.0,10.7,11.7,10.6,9.6,.253,0]
    case "msi_inspire":return [18.9,13.9,19.0,20.5,9.5,10.5,9.4,8.5,.25,0]
    case "msi_shadow":return [19.2,13.6,19.2,20.6,9.1,10.1,9.0,8.0,.245,0]
    case "gigabyte_gaming_oc":return [20.0,14.6,20.0,21.0,10.2,11.2,10.1,9.2,.253,0]
    case "gigabyte_eagle":return [19.0,13.4,19.0,20.6,9.0,9.9,8.9,8.0,.246,0]
    case "zotac_twin_edge":return [18.5,13.2,18.8,20.4,10.0,10.8,9.9,8.9,.255,0]
    case "zotac_solid":return [19.6,14.3,19.8,20.9,10.3,11.2,10.1,9.2,.252,0]
    case "zotac_amp_infinity":return [20.0,14.7,20.2,21.1,10.6,11.5,10.4,9.4,.252,0]
    case "zotac_amp_airo":return [19.8,14.6,20.2,21.0,10.4,11.3,10.2,9.2,.251,0]
    case "zotac_trinity":return [19.3,14.0,19.6,20.7,9.5,10.5,9.4,8.5,.249,0]
    case "sapphire_pure":return [19.4,14.0,19.5,20.7,9.7,10.8,9.6,8.7,.252,0]
    case "powercolor_fighter":return [19.0,13.6,19.0,20.5,9.5,10.4,9.3,8.4,.248,0]
    case "powercolor_reaper":return [18.8,13.4,18.9,20.5,8.8,9.9,8.9,7.9,.244,0]
    }
    return null
}

function p(d,fill){return '<path d="'+d+'" fill="'+fill+'"/>'}
function r(x,y,w,h,rx,fill){return '<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" rx="'+rx+'" fill="'+fill+'"/>'}

function face(s,g,c) {
    switch(s.series_id) {
    case "asus_astral":
        return p("M0 18L10 0H90L100 17V83L90 100H10L0 83Z",c.caseShade)
            +p("M6 22L17 9H83L94 22V78L83 91H17L6 78Z",c.metal)
            +r(8,23,84,54,4,c.caseBody)+r(10,3,80,6,2,c.edge)
            +r(10,91,80,6,2,c.accent)+r(0,27,7,47,2,c.caseTop)+r(93,27,7,47,2,c.caseTop)
    case "asus_prime":
        return r(0,4,100,92,13,c.caseBody)+p("M0 25Q0 4 20 4H80Q100 4 100 25H58L48 15H15L7 25Z",c.metal)
            +p("M0 76H7L16 86H49L58 76H100V80Q100 96 81 96H19Q0 96 0 80Z",c.caseShade)
            +r(76,5,12,5,2,c.accent)
    case "asus_proart":
        return r(0,0,100,100,6,c.caseShade)+r(5,11,90,78,5,c.caseBody)
            +r(0,0,100,12,3,c.metal)+r(0,88,100,12,3,c.metal)
            +r(1,14,5,72,1,c.caseTop)+r(94,14,5,72,1,c.caseTop)+r(64,3,24,5,1,c.gold)
    case "msi_expert": {
        // One visible fan on this plane; the second physical fan is opposite.
        var out=r(0,0,100,100,9,c.metal)+r(4,9,92,82,6,c.caseBody)
            +r(4,9,47,82,5,c.caseShade)+p("M49 0H58L49 100H40Z",c.metal)
        for(var i=0;i<8;i++)out+=p("M"+(8+i*5)+" 18H"+(10+i*5)+"V81H"+(8+i*5)+"Z",c.rim)
        return out+r(66,3,20,5,2,c.accent)
    }
    case "msi_vanguard":
        return p("M0 23L12 0H35L43 11H63L70 0H91L100 22V78L88 100H70L63 88H43L35 100H10L0 78Z",c.caseShade)
            +p("M12 0H35L43 11H63L70 0H91L82 20H69L60 32H46L35 20H22Z",c.metal)
            +p("M0 35L14 24V76L29 100H10L0 78Z",c.caseBody)
            +p("M100 32L87 23V75L73 100H88L100 78Z",c.caseBody)+r(45,3,17,5,1,c.accent)
    case "msi_inspire":
        return r(0,0,100,100,4,c.caseBody)+r(0,0,100,14,2,c.metal)+r(0,86,100,14,2,c.caseShade)
            +r(0,0,15,100,2,c.caseTop)+r(83,0,17,100,2,c.metal)
            +r(14,0,4,100,0,c.caseShade)+r(48,0,4,100,0,c.caseShade)+r(82,0,4,100,0,c.caseShade)
            +r(19,5,22,5,0,c.accent)
    case "msi_shadow":
        return p("M0 15L9 2H91L100 15V88L91 98H9L0 88Z",c.caseShade)
            +p("M9 2H91L83 17H17Z",c.caseTop)+p("M9 98H91L81 83H19Z",c.caseBody)
            +p("M0 15L9 2H17L8 30V72L17 98H9L0 88Z",c.metal)
            +r(72,4,14,4,1,c.accent)
    case "gigabyte_gaming_oc":
        return p("M0 21L9 0H35L43 9H73L81 0H94L100 20V81L92 100H67L59 91H28L20 100H6L0 81Z",c.caseBody)
            +p("M9 0H35L43 9H73L81 0H94L87 23H69L58 34H40L32 22H14Z",c.caseTop)
            +p("M6 100H20L28 91H59L67 100H92L84 78H66L57 67H36L27 78H14Z",c.metal)
            +r(2,29,7,43,1,c.caseShade)+r(91,29,7,43,1,c.caseShade)+r(79,4,10,5,1,c.accent)
    case "gigabyte_eagle":
        return p("M0 21L13 0H94L100 13V77L87 100H6L0 87Z",c.caseBody)
            +p("M13 0H94L87 15H29L14 38H0V21Z",c.metal)
            +p("M100 64V77L87 100H6L15 86H71L86 64Z",c.caseShade)
            +p("M37 0H45L23 35H15Z",c.accent)+p("M66 100H74L96 65H88Z",c.caseTop)
    case "zotac_twin_edge":
        return p("M0 30Q0 7 23 7H79Q100 7 100 28V75Q100 96 79 96H22Q0 96 0 74Z",c.caseBody)
            +p("M0 31Q0 7 23 7H79Q100 7 100 28L84 21H22L8 37Z",c.metal)
            +p("M0 69L15 82H79L100 69V75Q100 96 79 96H22Q0 96 0 74Z",c.caseShade)
            +p("M47 8H56L48 95H40Z",c.caseTop)+r(76,10,14,5,2,c.accent)
    case "zotac_solid":
        return p("M0 15L9 0H91L100 15V87L91 100H9L0 87Z",c.caseShade)
            +r(7,12,86,76,4,c.caseBody)+r(13,0,74,10,1,c.metal)
            +p("M0 15L9 0H17L13 100H9L0 87Z",c.metal)+p("M83 0H91L100 15V87L91 100H87Z",c.caseTop)
            +r(21,91,58,6,1,c.accent)
    case "zotac_amp_infinity":
        return r(0,0,100,100,14,c.caseShade)+r(4,6,92,88,12,c.metal)
            +r(9,15,82,70,8,c.caseBody)+r(10,4,80,7,3,c.accent)
            +r(10,89,80,7,3,c.rim)+r(1,24,7,52,3,c.caseTop)+r(92,24,7,52,3,c.caseTop)
    case "zotac_amp_airo":
        return p("M0 47Q0 14 22 5Q47-4 79 4Q100 10 100 48Q100 88 76 96Q48 105 21 96Q0 87 0 47Z",c.caseShade)
            +p("M0 47Q0 14 22 5Q47-4 79 4Q100 10 100 48L92 34Q82 16 59 16H25Q9 20 0 47Z",c.metal)
            +p("M0 64Q17 83 39 83H73Q91 81 100 59Q98 91 76 96Q48 105 21 96Q5 91 0 64Z",c.caseBody)
            +p("M16 10Q47 0 82 10L78 16Q49 7 20 16Z",c.accent)
    case "zotac_trinity":
        return p("M0 42Q0 9 24 8H78Q100 9 100 42V70Q97 93 75 95H24Q2 92 0 70Z",c.caseBody)
            +p("M0 43Q0 9 24 8H78Q100 9 100 42L88 25H23L9 43Z",c.metal)
            +p("M0 67Q11 81 26 82H77Q89 80 100 65V70Q97 93 75 95H24Q2 92 0 70Z",c.caseShade)
            +r(43,8,15,6,3,c.accent)
    case "sapphire_pure":
        return r(0,0,100,100,6,c.metal)+r(7,16,86,68,4,c.caseBody)
            +r(0,12,9,76,2,c.caseTop)+r(91,12,9,76,2,c.caseTop)
            +p("M0 0H100V15H60L51 24H36L26 15H0Z",c.rim)+r(79,4,13,6,1,c.accent)
    case "powercolor_fighter":
        return p("M0 14L12 0H89L100 14V86L89 100H12L0 86Z",c.caseBody)
            +p("M12 0H89L82 14H19L8 29H0V14Z",c.caseTop)
            +p("M0 71L14 87H81L100 70V86L89 100H12L0 86Z",c.caseShade)
            +r(48,0,5,100,0,c.metal)+r(73,3,13,4,1,c.accent)
    case "powercolor_reaper":
        return r(0,8,100,84,9,c.caseBody)+r(4,18,92,64,8,c.caseShade)
            +p("M0 28Q0 8 20 8H80Q100 8 100 28H90L83 19H17L10 28Z",c.caseTop)
            +p("M0 73H11L18 83H82L90 73H100Q99 92 81 92H19Q1 92 0 73Z",c.metal)
            +r(78,10,11,4,2,c.accent)
    }
    return ""
}
