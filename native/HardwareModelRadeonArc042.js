.pragma library

// Original source-linked model-view studies, PolyForm Noncommercial 1.0.0.
// See LICENSE / THIRD_PARTY_NOTICES.md. Only the exact existing AMD/Intel SKUs
// below may use these traces. They restore reviewed panel boundaries, folded
// bridges and exterior vents; they are not factory mechanical measurements.
// Coordinates are the original 100x100 cover plane. Width is in the shared
// 24-unit viewBox. The caller handles style, exact profile, transforms and fan
// hole exclusion once when building a cached SVG. No clocks or sensor access.
// Reuse identical physical covers across reviewed editions to avoid duplicate
// arrays; front fan counts/profiles always come from the original exact Board.
// BIOSTAR base/OC covers were independently reviewed from official front
// images in0.43; their nine/eleven-blade profiles and panel traces stay distinct.
// The small id gate is available immediately; large paths/URLs are allocated
// only when one of these exact GPUs is requested in model mode.
var ids = ["sapphire-pulse-7600","sapphire-nitro-9070xt-oc","powercolor-hellhound-7800xt-oc","powercolor-red-devil-7800xt-oc","asrock-phantom-7900xtx-oc","asrock-steel-legend-7800xt-oc","asrock-challenger-7600-oc","asrock-taichi-7900xtx-oc","xfx-merc310-7900xtx-black","xfx-qick319-6750xt-core-jfdr","xfx-swft210-6600-core-lfdq","yeston-atlantis-rx9070xt-16g","yeston-sakura-rx7800xt-16g","biostar-radeon-rx7600-va7606rm81","amd-reference-rx7900xtx-24g","intel-limited-arc-a770-16g","sapphire-pure-7800xt","powercolor-fighter-7800xt","powercolor-reaper-9070xt","msi-hd4870-t2d512-oc-reference","msi-hd5450-md1gd3h-lp","msi-hd5870-pm2d1g-reference","msi-hd7970-tf-3gd5-oc-be","msi-r9-290x-4gd5-reference","asus-strix-r9fury-dc3-4g","msi-rx480-8g-reference","sapphire-nitro-rx580-8g-01","msi-vega64-8g-reference","asrock-rx5500xt-challenger-d-8g","msi-rx5700xt-8g-reference","sapphire-pulse-rx6400-4g-lp","asus-tuf-rx6800xt-o16g","sapphire-pulse-rx7900xt-20g","asrock-taichi-rx9070xt-16g-oc","asrock-a380-challenger-itx-6g","sparkle-a750-titan-8g-oc","acer-bifrost-a770-16g-oc","asrock-b570-challenger-10g-oc","sparkle-b580-titan-12g-oc","asrock-taichi-7900xtx-white-oc","asrock-taichi-rx9070xt-white-16g-oc","biostar-radeon-rx7600-oc-va76s6rm81","sapphire-nitro-9070xt-phantomlink","sapphire-nitro-9070xt-phantomlink-polar","sapphire-nitro-9070xt-valor-mortis","sapphire-nitro-9070xt-crimson-desert","powercolor-hellhound-7800xt-sakura-limited","powercolor-hellhound-7800xt-sakura","powercolor-hellhound-7800xt-white","powercolor-red-devil-7800xt-limited","powercolor-red-devil-7800xt-bp","powercolor-fighter-7800xt-mini","sparkle-a770-titan-16g-oc","sparkle-b580-titan-luna-12g-oc","sparkle-b580-roc-luna-12g-oc-ultra"]
var rows = null

function records() {
    if(rows===null) {
        var studies = {
  "sapphire_pulse":[
    {
      "d":"M17 0H82V17H52L45 29H17Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesShapes.js:sapphire_pulse/sourceShapes[3]"
    },
    {
      "d":"M17 100H82V83H54L47 71H17Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesShapes.js:sapphire_pulse/sourceShapes[4]"
    },
    {
      "d":"M48 18H57L49 82H40Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesShapes.js:sapphire_pulse/sourceShapes[5]"
    },
    {
      "d":"M1 7H16Q17 7 17 8V92Q17 93 16 93H1Q0 93 0 92V8Q0 7 1 7Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesShapes.js:sapphire_pulse/sourceShapes[1]"
    },
    {
      "d":"M83 7H99Q100 7 100 8V92Q100 93 99 93H83Q82 93 82 92V8Q82 7 83 7Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesShapes.js:sapphire_pulse/sourceShapes[2]"
    }
  ],
  "sapphire_nitro":[
    {
      "d":"M10 17H90Q95 17 95 22V78Q95 83 90 83H10Q5 83 5 78V22Q5 17 10 17Z",
      "role":"vent",
      "width":0.11,
      "source_field":"native/HardwareSeriesShapes.js:sapphire_nitro/sourceShapes[1]"
    },
    {
      "d":"M0 15Q0 0 15 0H85Q100 0 100 15V24H0Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesShapes.js:sapphire_nitro/sourceShapes[2]"
    },
    {
      "d":"M0 76H100V85Q100 100 85 100H15Q0 100 0 85Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesShapes.js:sapphire_nitro/sourceShapes[3]"
    },
    {
      "d":"M2 24H5Q7 24 7 26V74Q7 76 5 76H2Q0 76 0 74V26Q0 24 2 24Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesShapes.js:sapphire_nitro/sourceShapes[5]"
    },
    {
      "d":"M95 24H98Q100 24 100 26V74Q100 76 98 76H95Q93 76 93 74V26Q93 24 95 24Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesShapes.js:sapphire_nitro/sourceShapes[6]"
    }
  ],
  "powercolor_hellhound":[
    {
      "d":"M6 29Q6 18 19 18H81Q94 18 94 29V71Q94 84 80 84H20Q6 84 6 71Z",
      "role":"vent",
      "width":0.11,
      "source_field":"native/HardwareSeriesShapes.js:powercolor_hellhound/sourceShapes[1]"
    },
    {
      "d":"M14 8H85Q100 8 100 25V34H94V29Q94 18 81 18H19Q6 18 6 29V34H0V25Q0 8 14 8Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesShapes.js:powercolor_hellhound/sourceShapes[2]"
    }
  ],
  "powercolor_red_devil":[
    {
      "d":"M0 65L17 77H35L44 67H64L72 79H90L100 58L95 88L79 100H59L52 91H22L9 100L0 78Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesShapes.js:powercolor_red_devil/sourceShapes[2]"
    },
    {
      "d":"M0 31L7 11L18 5L14 34L8 54L14 87L9 100L0 78Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesShapes.js:powercolor_red_devil/sourceShapes[3]"
    },
    {
      "d":"M84 0L97 14L100 45L95 88L83 97L88 70L94 46L85 22Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesShapes.js:powercolor_red_devil/sourceShapes[4]"
    },
    {
      "d":"M25 4H37L32 17H20Z",
      "role":"trim",
      "width":0.09,
      "source_field":"native/HardwareSeriesShapes.js:powercolor_red_devil/sourceShapes[5]"
    }
  ],
  "asrock_phantom":[
    {
      "d":"M0 24L12 3H41L47 10H75L83 0H95L88 22H66L51 42H28L15 64H0Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupA.js:asrock_phantom/sourceShapes[1]"
    },
    {
      "d":"M1 82L18 61H42L58 39H78L100 17V77L88 98H58L51 90H23L13 100H2Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupA.js:asrock_phantom/sourceShapes[2]"
    },
    {
      "d":"M45 11H54L32 42H23Z",
      "role":"trim",
      "width":0.09,
      "source_field":"native/HardwareSeriesGroupA.js:asrock_phantom/sourceShapes[5]"
    },
    {
      "d":"M63 58H72L51 90H42Z",
      "role":"trim",
      "width":0.09,
      "source_field":"native/HardwareSeriesGroupA.js:asrock_phantom/sourceShapes[6]"
    }
  ],
  "asrock_steel_legend":[
    {
      "d":"M8 7H26L31 0H45L51 11H69L77 0H91L100 22H82L72 32H54L43 19H30L19 34H0V25Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupA.js:asrock_steel_legend/sourceShapes[1]"
    },
    {
      "d":"M0 71L17 80H35L44 68H61L72 81H88L100 67V78L91 97H72L66 88H45L37 100H16L0 86Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupA.js:asrock_steel_legend/sourceShapes[2]"
    },
    {
      "d":"M23 18L31 22L42 81L34 92L28 57Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupA.js:asrock_steel_legend/sourceShapes[3]"
    },
    {
      "d":"M68 20L75 14L70 59L79 89H69L61 57Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupA.js:asrock_steel_legend/sourceShapes[4]"
    }
  ],
  "asrock_challenger":[
    {
      "d":"M0 19L11 2H34L43 14H67L77 2H91L100 20H78L65 34H42L28 20H13L0 37Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupA.js:asrock_challenger/sourceShapes[1]"
    },
    {
      "d":"M0 63L15 80H34L46 67H60L74 81H89L100 64V82L89 98H67L58 87H34L24 98H10L0 80Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupA.js:asrock_challenger/sourceShapes[2]"
    },
    {
      "d":"M37 25H48L64 75H52Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupA.js:asrock_challenger/sourceShapes[3]"
    },
    {
      "d":"M42 18H62L55 29H35Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupA.js:asrock_challenger/sourceShapes[4]"
    }
  ],
  "asrock_taichi":[
    {
      "d":"M0 25L12 5H28L37 12H42L45 0H59L64 12H74L82 5H91L100 24L88 29L77 19H68L60 29H41L32 20H19L9 35Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupA.js:asrock_taichi/sourceShapes[1]"
    },
    {
      "d":"M0 66L12 76H26L36 64H43L49 78H57L64 63H73L83 77H94L100 65V79L88 98H73L65 89H59L55 100H43L38 89H28L20 98H9L0 80Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupA.js:asrock_taichi/sourceShapes[2]"
    },
    {
      "d":"M32 17H41L32 40V61L42 83H32L24 61V41Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupA.js:asrock_taichi/sourceShapes[3]"
    },
    {
      "d":"M62 17H72L79 40V62L70 84H60L70 61V41Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupA.js:asrock_taichi/sourceShapes[4]"
    },
    {
      "d":"M45 7H56Q57 7 57 8V11Q57 12 56 12H45Q44 12 44 11V8Q44 7 45 7Z",
      "role":"trim",
      "width":0.09,
      "source_field":"native/HardwareSeriesGroupA.js:asrock_taichi/sourceShapes[5]"
    }
  ],
  "xfx_merc":[
    {
      "d":"M2 15Q2 7 11 7H92L97 13V86L91 93H11Q3 93 3 85Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupA.js:xfx_merc/sourceShapes[1]"
    },
    {
      "d":"M92 7L97 13V86L91 93H82L88 81V20Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupA.js:xfx_merc/sourceShapes[3]"
    },
    {
      "d":"M7 9H8Q9 9 9 10V85Q9 86 8 86H7Q6 86 6 85V10Q6 9 7 9Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupA.js:xfx_merc/sourceShapes[4]"
    }
  ],
  "xfx_qick":[
    {
      "d":"M0 13H100V22H96V79H100V88H0V78H4V23H0Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupA.js:xfx_qick/sourceShapes[1]"
    },
    {
      "d":"M9 20H91Q94 20 94 23V77Q94 80 91 80H9Q6 80 6 77V23Q6 20 9 20Z",
      "role":"vent",
      "width":0.11,
      "source_field":"native/HardwareSeriesGroupA.js:xfx_qick/sourceShapes[2]"
    },
    {
      "d":"M4 30H6Q7 30 7 31V44Q7 45 6 45H4Q3 45 3 44V31Q3 30 4 30Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupA.js:xfx_qick/sourceShapes[5]"
    },
    {
      "d":"M94 55H96Q97 55 97 56V69Q97 70 96 70H94Q93 70 93 69V56Q93 55 94 55Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupA.js:xfx_qick/sourceShapes[6]"
    }
  ],
  "xfx_swft":[
    {
      "d":"M4 25Q4 19 11 18L88 12Q95 12 95 21V77Q95 86 88 86L11 81Q4 80 4 74Z",
      "role":"vent",
      "width":0.11,
      "source_field":"native/HardwareSeriesGroupA.js:xfx_swft/sourceShapes[1]"
    },
    {
      "d":"M0 23Q0 13 9 11L88 5Q100 5 100 18V25L91 20L11 25V76L0 77Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupA.js:xfx_swft/sourceShapes[2]"
    },
    {
      "d":"M9 88L88 94Q100 94 100 81V75L90 82L10 77L0 77Q0 87 9 88Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupA.js:xfx_swft/sourceShapes[3]"
    }
  ],
  "yeston_atlantis":[
    {
      "d":"M0 30Q19 23 44 27Q68 30 100 18V29Q72 43 44 38Q18 34 0 43Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupC.js:yeston_atlantis/sourceShapes[2]"
    },
    {
      "d":"M0 64Q31 79 58 70Q83 62 100 71V84Q79 74 58 82Q29 92 0 76Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupC.js:yeston_atlantis/sourceShapes[3]"
    },
    {
      "d":"M5 4H90L96 13H11ZM9 98L3 88H88L95 79V91L89 98Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupC.js:yeston_atlantis/sourceShapes[4]"
    }
  ],
  "yeston_sakura":[
    {
      "d":"M0 17Q35 22 100 85V98Q67 77 44 56Q21 37 0 34Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupC.js:yeston_sakura/sourceShapes[2]"
    },
    {
      "d":"M0 80Q46 61 91 4H100V21Q66 66 12 98H0Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupC.js:yeston_sakura/sourceShapes[3]"
    },
    {
      "d":"M0 4H14L8 23H0ZM87 98L94 77H100V98Z",
      "role":"trim",
      "width":0.09,
      "source_field":"native/HardwareSeriesGroupC.js:yeston_sakura/sourceShapes[4]"
    }
  ],
  "biostar_radeon":[{"d":"M4 9Q26 6 33 10H65Q73 6 96 9M4 91H31L36 87H67L72 91H96","role":"edge","width":0.1,"source_field":"native/HardwareVariantGroupB.js:b_biostar7600_base/sourceShapes[1]"},{"d":"M7 5H29L33 8H67L71 5H93M7 95H30L35 91H67L73 95H93","role":"edge","width":0.1,"source_field":"native/HardwareVariantGroupB.js:b_biostar7600_base/sourceShapes[2]"}],
  "amd_reference":[
    {
      "d":"M0 13H13L20 19L28 8H42L49 18L57 8H72L80 18L88 8H96L100 21V31H88L80 25L72 33H58L49 27L41 34H26L18 28H0Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupC.js:amd_reference/sourceShapes[1]"
    },
    {
      "d":"M0 72H12L20 80H32L41 72L49 80H62L71 72L80 81H91L100 70V82L92 95H79L71 87L62 98H49L42 88L33 98H18L11 89H0Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupC.js:amd_reference/sourceShapes[2]"
    },
    {
      "d":"M88 8H94L100 20V31H94V22Z",
      "role":"trim",
      "width":0.09,
      "source_field":"native/HardwareSeriesGroupC.js:amd_reference/sourceShapes[3]"
    }
  ],
  "intel_limited":[
    {
      "d":"M15 2H85Q98 2 98 15V85Q98 98 85 98H15Q2 98 2 85V15Q2 2 15 2Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupC.js:intel_limited/sourceShapes[1]"
    },
    {
      "d":"M4 29Q4 5 25 5H76Q96 5 96 29V38H92V29Q92 10 76 10H25Q8 10 8 29V38H4Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupC.js:intel_limited/sourceShapes[3]"
    },
    {
      "d":"M4 67H8V73Q8 90 25 90H76Q92 90 92 73V67H96V73Q96 95 76 95H25Q4 95 4 73Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesGroupC.js:intel_limited/sourceShapes[4]"
    }
  ],
  "sapphire_pure":[
    {
      "d":"M11 16H89Q93 16 93 20V80Q93 84 89 84H11Q7 84 7 80V20Q7 16 11 16Z",
      "role":"vent",
      "width":0.11,
      "source_field":"native/HardwareSeriesCoreExpansion.js:sapphire_pure/sourceShapes[1]"
    },
    {
      "d":"M2 12H7Q9 12 9 14V86Q9 88 7 88H2Q0 88 0 86V14Q0 12 2 12Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesCoreExpansion.js:sapphire_pure/sourceShapes[2]"
    },
    {
      "d":"M93 12H98Q100 12 100 14V86Q100 88 98 88H93Q91 88 91 86V14Q91 12 93 12Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesCoreExpansion.js:sapphire_pure/sourceShapes[3]"
    },
    {
      "d":"M0 0H100V15H60L51 24H36L26 15H0Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesCoreExpansion.js:sapphire_pure/sourceShapes[4]"
    }
  ],
  "powercolor_fighter":[
    {
      "d":"M12 0H89L82 14H19L8 29H0V14Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesCoreExpansion.js:powercolor_fighter/sourceShapes[1]"
    },
    {
      "d":"M0 71L14 87H81L100 70V86L89 100H12L0 86Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesCoreExpansion.js:powercolor_fighter/sourceShapes[2]"
    },
    {
      "d":"M48 0H53Q53 0 53 0V100Q53 100 53 100H48Q48 100 48 100V0Q48 0 48 0Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesCoreExpansion.js:powercolor_fighter/sourceShapes[3]"
    }
  ],
  "powercolor_reaper":[
    {
      "d":"M12 18H88Q96 18 96 26V74Q96 82 88 82H12Q4 82 4 74V26Q4 18 12 18Z",
      "role":"vent",
      "width":0.11,
      "source_field":"native/HardwareSeriesCoreExpansion.js:powercolor_reaper/sourceShapes[1]"
    },
    {
      "d":"M0 28Q0 8 20 8H80Q100 8 100 28H90L83 19H17L10 28Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesCoreExpansion.js:powercolor_reaper/sourceShapes[2]"
    },
    {
      "d":"M0 73H11L18 83H82L90 73H100Q99 92 81 92H19Q1 92 0 73Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesCoreExpansion.js:powercolor_reaper/sourceShapes[3]"
    }
  ],
  "msi_hd4870_reference":[
    {
      "d":"M10 17H61L67 28V77L58 88H10Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_hd4870_reference/sourceShapes[2]"
    },
    {
      "d":"M63 12Q93 5 98 29V74Q94 95 74 97H63L70 83V24Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_hd4870_reference/sourceShapes[3]"
    },
    {
      "d":"M0 16L5 8H64V15H8V84L0 88Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_hd4870_reference/sourceShapes[4]"
    }
  ],
  "msi_hd5450_passive":[
    {
      "d":"M32 6H98Q99 6 99 7V90Q99 91 98 91H32Q31 91 31 90V7Q31 6 32 6Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_hd5450_passive/sourceShapes[2]"
    },
    {
      "d":"M31 6H99V16H37V91H31Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_hd5450_passive/sourceShapes[3]"
    },
    {
      "d":"M38.3 18H39.904Q40.204 18 40.204 18.3V85.7Q40.204 86 39.904 86H38.3Q38 86 38 85.7V18.3Q38 18 38.3 18Z",
      "role":"vent",
      "width":0.11,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_hd5450_passive/sourceShapes[4]"
    },
    {
      "d":"M61.5 18H63.104Q63.404 18 63.404 18.3V85.7Q63.404 86 63.104 86H61.5Q61.2 86 61.2 85.7V18.3Q61.2 18 61.5 18Z",
      "role":"vent",
      "width":0.11,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_hd5450_passive/sourceShapes[8]"
    },
    {
      "d":"M90.5 18H92.104Q92.404 18 92.404 18.3V85.7Q92.404 86 92.104 86H90.5Q90.2 86 90.2 85.7V18.3Q90.2 18 90.5 18Z",
      "role":"vent",
      "width":0.11,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_hd5450_passive/sourceShapes[13]"
    }
  ],
  "msi_hd5870_reference":[
    {
      "d":"M8 3H94L100 15H10L0 25V14Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_hd5870_reference/sourceShapes[1]"
    },
    {
      "d":"M8 17H66L71 25V84H9L3 76V24Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_hd5870_reference/sourceShapes[2]"
    },
    {
      "d":"M0 77L9 85H93L100 76V88L94 97H7L0 84Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_hd5870_reference/sourceShapes[3]"
    },
    {
      "d":"M10.5 14H64.5Q65 14 65 14.5V17.5Q65 18 64.5 18H10.5Q10 18 10 17.5V14.5Q10 14 10.5 14Z",
      "role":"trim",
      "width":0.09,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_hd5870_reference/sourceShapes[4]"
    },
    {
      "d":"M10.5 83H60.5Q61 83 61 83.5V85.5Q61 86 60.5 86H10.5Q10 86 10 85.5V83.5Q10 83 10.5 83Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_hd5870_reference/sourceShapes[5]"
    }
  ],
  "msi_twin_frozr_hd7970":[
    {
      "d":"M7 8H91L100 23H91L84 16H17L7 34H0Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_twin_frozr_hd7970/sourceShapes[2]"
    },
    {
      "d":"M0 65L10 79H86L95 69H100L94 90H8L0 71Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_twin_frozr_hd7970/sourceShapes[3]"
    },
    {
      "d":"M45 12H55L60 84H48Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_twin_frozr_hd7970/sourceShapes[4]"
    },
    {
      "d":"M87 12L99 23V74L92 83L88 69Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_twin_frozr_hd7970/sourceShapes[5]"
    },
    {
      "d":"M12 91H83V95H14L8 88H12Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_twin_frozr_hd7970/sourceShapes[7]"
    }
  ],
  "msi_r9_290x_reference":[
    {
      "d":"M6 5H94L100 15V26H78Q64 26 53 44L24 81H0V14Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_r9_290x_reference/sourceShapes[1]"
    },
    {
      "d":"M0 80H23L51 42Q63 22 80 22H99V27H80Q65 27 55 46L28 85H0Z",
      "role":"trim",
      "width":0.09,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_r9_290x_reference/sourceShapes[2]"
    },
    {
      "d":"M0 86H29L55 50Q64 36 68 35V86H92L100 77V89L93 98H6L0 88Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_r9_290x_reference/sourceShapes[3]"
    }
  ],
  "asus_strix_fury":[
    {
      "d":"M0 24L8 6H90L99 18L93 26H77L68 18H22L12 31H0Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asus_strix_fury/sourceShapes[1]"
    },
    {
      "d":"M0 65L13 77H29L47 69H65L79 78H99L89 91H71L56 100H25L9 88L0 72Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asus_strix_fury/sourceShapes[2]"
    },
    {
      "d":"M9 78L28 87L56 89L73 80H90L84 88H70L55 96H26L11 85Z",
      "role":"trim",
      "width":0.09,
      "source_field":"native/HardwareSeriesRadeonArc.js:asus_strix_fury/sourceShapes[3]"
    },
    {
      "d":"M30 15H36L42 78H34Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asus_strix_fury/sourceShapes[4]"
    },
    {
      "d":"M62 15H69L64 80H57Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asus_strix_fury/sourceShapes[5]"
    }
  ],
  "msi_rx480_reference":[
    {
      "d":"M5 10H95Q97 10 97 12V89Q97 91 95 91H5Q3 91 3 89V12Q3 10 5 10Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_rx480_reference/sourceShapes[1]"
    },
    {
      "d":"M1 10H4Q5 10 5 11V90Q5 91 4 91H1Q0 91 0 90V11Q0 10 1 10Z",
      "role":"trim",
      "width":0.09,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_rx480_reference/sourceShapes[2]"
    },
    {
      "d":"M8 10H64Q65 10 65 11V16Q65 17 64 17H8Q7 17 7 16V11Q7 10 8 10Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_rx480_reference/sourceShapes[3]"
    },
    {
      "d":"M7.5 84H64.5Q65 84 65 84.5V87.5Q65 88 64.5 88H7.5Q7 88 7 87.5V84.5Q7 84 7.5 84Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_rx480_reference/sourceShapes[4]"
    }
  ],
  "sapphire_nitro_polaris":[
    {
      "d":"M4 9H96V20H92Q76 7 60 23H40Q24 7 8 21H4Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:sapphire_nitro_polaris/sourceShapes[1]"
    },
    {
      "d":"M4 79H9Q25 94 40 78H60Q76 94 92 79H96V93H4Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:sapphire_nitro_polaris/sourceShapes[2]"
    },
    {
      "d":"M45 16H55L60 84H41Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:sapphire_nitro_polaris/sourceShapes[3]"
    },
    {
      "d":"M3 25H4Q6 25 6 27V73Q6 75 4 75H3Q1 75 1 73V27Q1 25 3 25Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:sapphire_nitro_polaris/sourceShapes[4]"
    },
    {
      "d":"M96 25H97Q99 25 99 27V73Q99 75 97 75H96Q94 75 94 73V27Q94 25 96 25Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:sapphire_nitro_polaris/sourceShapes[5]"
    }
  ],
  "msi_vega64_reference":[
    {
      "d":"M4 8H96Q97 8 97 9V91Q97 92 96 92H4Q3 92 3 91V9Q3 8 4 8Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_vega64_reference/sourceShapes[1]"
    },
    {
      "d":"M0.5 6H4.5Q5 6 5 6.5V94.5Q5 95 4.5 95H0.5Q0 95 0 94.5V6.5Q0 6 0.5 6Z",
      "role":"trim",
      "width":0.09,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_vega64_reference/sourceShapes[2]"
    },
    {
      "d":"M7.5 8H94.5Q95 8 95 8.5V12.5Q95 13 94.5 13H7.5Q7 13 7 12.5V8.5Q7 8 7.5 8Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_vega64_reference/sourceShapes[3]"
    },
    {
      "d":"M7.5 87H94.5Q95 87 95 87.5V91.5Q95 92 94.5 92H7.5Q7 92 7 91.5V87.5Q7 87 7.5 87Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_vega64_reference/sourceShapes[4]"
    },
    {
      "d":"M10 19H62V23H10ZM10 76H62V80H10Z",
      "role":"vent",
      "width":0.11,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_vega64_reference/sourceShapes[5]"
    }
  ],
  "asrock_challenger_rdna1":[
    {
      "d":"M9 4H91L100 20H78L64 34H36L22 19H0Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asrock_challenger_rdna1/sourceShapes[1]"
    },
    {
      "d":"M0 64L21 82H36L50 65L65 81H82L100 66V82L90 97H10L0 81Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asrock_challenger_rdna1/sourceShapes[2]"
    },
    {
      "d":"M34 15H45L64 83H52Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asrock_challenger_rdna1/sourceShapes[3]"
    },
    {
      "d":"M52 16H64L46 82H36Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asrock_challenger_rdna1/sourceShapes[4]"
    }
  ],
  "msi_rx5700xt_reference":[
    {
      "d":"M0 12Q1 4 10 4H58Q63 5 69 13Q74 20 80 14L91 4H96L100 13V20H91L81 24Q73 30 65 22L58 14H7L0 21Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_rx5700xt_reference/sourceShapes[1]"
    },
    {
      "d":"M3 22H63V87H95L99 81V88L94 97H8L3 87Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_rx5700xt_reference/sourceShapes[2]"
    },
    {
      "d":"M8.4 27H60.6Q61 27 61 27.4V29.6Q61 30 60.6 30H8.4Q8 30 8 29.6V27.4Q8 27 8.4 27Z",
      "role":"vent",
      "width":0.11,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_rx5700xt_reference/sourceShapes[3]"
    },
    {
      "d":"M8.4 51H60.6Q61 51 61 51.4V53.6Q61 54 60.6 54H8.4Q8 54 8 53.6V51.4Q8 51 8.4 51Z",
      "role":"vent",
      "width":0.11,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_rx5700xt_reference/sourceShapes[5]"
    },
    {
      "d":"M8.4 75H60.6Q61 75 61 75.4V77.6Q61 78 60.6 78H8.4Q8 78 8 77.6V75.4Q8 75 8.4 75Z",
      "role":"vent",
      "width":0.11,
      "source_field":"native/HardwareSeriesRadeonArc.js:msi_rx5700xt_reference/sourceShapes[7]"
    }
  ],
  "sapphire_pulse_rdna2_lp":[
    {
      "d":"M31 13H95L100 22V82L93 93H31Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:sapphire_pulse_rdna2_lp/sourceShapes[2]"
    },
    {
      "d":"M36 21H92L97 29V77L88 85H36Z",
      "role":"vent",
      "width":0.11,
      "source_field":"native/HardwareSeriesRadeonArc.js:sapphire_pulse_rdna2_lp/sourceShapes[3]"
    },
    {
      "d":"M32 14H95L100 22V29H94L90 22H43L35 33H31Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:sapphire_pulse_rdna2_lp/sourceShapes[4]"
    },
    {
      "d":"M36 77L44 85H89L95 77H100V82L93 93H31V80Z",
      "role":"trim",
      "width":0.09,
      "source_field":"native/HardwareSeriesRadeonArc.js:sapphire_pulse_rdna2_lp/sourceShapes[5]"
    }
  ],
  "asus_tuf_rdna2":[
    {
      "d":"M0 18L10 4H70L76 0H93L100 13V24H83L74 15H16L6 31H0Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asus_tuf_rdna2/sourceShapes[1]"
    },
    {
      "d":"M0 69L13 82H87L100 66V83L89 98H11L0 85Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asus_tuf_rdna2/sourceShapes[2]"
    },
    {
      "d":"M28 13H36L43 86H35Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asus_tuf_rdna2/sourceShapes[3]"
    },
    {
      "d":"M60 13H69L63 86H54Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asus_tuf_rdna2/sourceShapes[4]"
    },
    {
      "d":"M9 85H25L19 94H11ZM38 85H49L44 94H33ZM67 85H79L73 94H61Z",
      "role":"vent",
      "width":0.11,
      "source_field":"native/HardwareSeriesRadeonArc.js:asus_tuf_rdna2/sourceShapes[5]"
    }
  ],
  "sapphire_pulse_rdna3":[
    {
      "d":"M9 5H92V13H100V22H83L78 16H21L16 22H0V15H9Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:sapphire_pulse_rdna3/sourceShapes[1]"
    },
    {
      "d":"M0 76H18L23 83H76L83 76H100V85H91V96H8V87H0Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:sapphire_pulse_rdna3/sourceShapes[2]"
    },
    {
      "d":"M10 87H30L35 92H70L77 85H91V89H79L72 96H32L27 91H10Z",
      "role":"trim",
      "width":0.09,
      "source_field":"native/HardwareSeriesRadeonArc.js:sapphire_pulse_rdna3/sourceShapes[3]"
    },
    {
      "d":"M32 17H38L43 82H35ZM62 17H68L63 82H56Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:sapphire_pulse_rdna3/sourceShapes[4]"
    }
  ],
  "asrock_taichi_rdna4":[
    {
      "d":"M0 25L9 7H29L37 15L43 0H58L64 15L74 7H92L100 24L88 30L78 19H70L61 30H39L31 20H19L9 36Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asrock_taichi_rdna4/sourceShapes[1]"
    },
    {
      "d":"M0 64L13 76H29L37 66L44 82H57L64 65H72L84 78H100V79L91 97H72L64 88L58 100H43L36 88L27 97H8L0 79Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asrock_taichi_rdna4/sourceShapes[2]"
    },
    {
      "d":"M40 15L34 35V65L42 85H46L39 63V37L46 15ZM56 15L64 35V65L57 85H53L59 63V37L52 15Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asrock_taichi_rdna4/sourceShapes[3]"
    },
    {
      "d":"M3 25L11 12H19L10 30ZM82 85L90 71L97 78L88 92Z",
      "role":"trim",
      "width":0.09,
      "source_field":"native/HardwareSeriesRadeonArc.js:asrock_taichi_rdna4/sourceShapes[4]"
    }
  ],
  "asrock_challenger_arc_a380":[
    {
      "d":"M0 19L12 3H85L100 19V34H86L70 17H28L12 35H0Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asrock_challenger_arc_a380/sourceShapes[1]"
    },
    {
      "d":"M0 64H14L30 82H69L86 64H100V84L86 98H14L0 83Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asrock_challenger_arc_a380/sourceShapes[2]"
    },
    {
      "d":"M7 19L18 9H35L20 25H7Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asrock_challenger_arc_a380/sourceShapes[3]"
    },
    {
      "d":"M67 91L80 77H93L84 91Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asrock_challenger_arc_a380/sourceShapes[4]"
    },
    {
      "d":"M3 36H6Q7 36 7 37V62Q7 63 6 63H3Q2 63 2 62V37Q2 36 3 36Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asrock_challenger_arc_a380/sourceShapes[5]"
    },
    {
      "d":"M94 36H97Q98 36 98 37V62Q98 63 97 63H94Q93 63 93 62V37Q93 36 94 36Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asrock_challenger_arc_a380/sourceShapes[6]"
    }
  ],
  "sparkle_titan_arc_a750":[
    {
      "d":"M0 17L6 6H94L100 17V27H94L85 16H75L67 26H61L53 16H43L35 26H28L19 16H9L0 30Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:sparkle_titan_arc_a750/sourceShapes[1]"
    },
    {
      "d":"M0 71L9 83H19L28 74H35L43 83H53L61 74H67L75 83H85L94 72H100V85L94 96H6L0 85Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:sparkle_titan_arc_a750/sourceShapes[2]"
    },
    {
      "d":"M29 19H35V81H29ZM62 19H68V81H62Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:sparkle_titan_arc_a750/sourceShapes[3]"
    },
    {
      "d":"M7.5 8H91.5Q92 8 92 8.5V11.5Q92 12 91.5 12H7.5Q7 12 7 11.5V8.5Q7 8 7.5 8Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:sparkle_titan_arc_a750/sourceShapes[4]"
    }
  ],
  "acer_bifrost_arc_a770":[
    {
      "d":"M0 15L9 4H91L100 16H63L54 25H5L0 31Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:acer_bifrost_arc_a770/sourceShapes[1]"
    },
    {
      "d":"M0 73H46L55 83H98L89 97H9L0 85Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:acer_bifrost_arc_a770/sourceShapes[2]"
    },
    {
      "d":"M44 21H54L61 35V69L52 83H43L50 68V35Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:acer_bifrost_arc_a770/sourceShapes[3]"
    },
    {
      "d":"M4 31H10V68H4ZM94 27H99V76H94Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:acer_bifrost_arc_a770/sourceShapes[4]"
    }
  ],
  "asrock_challenger_arc_b570":[
    {
      "d":"M0 28L13 6H90L100 19V26H74L65 17H25L16 30H0Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asrock_challenger_arc_b570/sourceShapes[1]"
    },
    {
      "d":"M0 67L15 81H39L49 70H64L77 83H100L88 98H12L0 82Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asrock_challenger_arc_b570/sourceShapes[2]"
    },
    {
      "d":"M38 16H53L61 33L51 66L65 84H51L40 67L50 33Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asrock_challenger_arc_b570/sourceShapes[3]"
    },
    {
      "d":"M4 29L17 12H31L23 23H18L12 32Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asrock_challenger_arc_b570/sourceShapes[4]"
    },
    {
      "d":"M15.7 87H80.3Q81 87 81 87.7V91.3Q81 92 80.3 92H15.7Q15 92 15 91.3V87.7Q15 87 15.7 87Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:asrock_challenger_arc_b570/sourceShapes[5]"
    }
  ],
  "sparkle_titan_arc_b580":[
    {
      "d":"M0 19L10 4H93L100 15V23H86L79 15H69L62 26H54L46 15H36L28 26H18L10 17L0 30Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:sparkle_titan_arc_b580/sourceShapes[1]"
    },
    {
      "d":"M0 70L10 81H19L28 71H36L44 83H54L62 71H70L78 83H88L100 70V84L90 97H9L0 85Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:sparkle_titan_arc_b580/sourceShapes[2]"
    },
    {
      "d":"M28 15H36L43 31L35 48L43 82H35L27 49L35 31ZM62 15H70L63 34L71 51L63 83H55L63 51L55 34Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareSeriesRadeonArc.js:sparkle_titan_arc_b580/sourceShapes[3]"
    },
    {
      "d":"M10.4 5H91.6Q92 5 92 5.4V8.6Q92 9 91.6 9H10.4Q10 9 10 8.6V5.4Q10 5 10.4 5Z",
      "role":"trim",
      "width":0.09,
      "source_field":"native/HardwareSeriesRadeonArc.js:sparkle_titan_arc_b580/sourceShapes[4]"
    }
  ],
  "b_taichi7900_white":[
    {
      "d":"M2 1H30L33 10H67L70 1H98L95 10H76L70 16H30L24 10H5Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupB.js:b_taichi7900_white/sourceShapes[1]"
    },
    {
      "d":"M2 99H30L33 90H67L70 99H98L95 90H76L70 84H30L24 90H5Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupB.js:b_taichi7900_white/sourceShapes[2]"
    },
    {
      "d":"M28 21L35 13H65L72 21L68 27H32ZM28 79L35 87H65L72 79L68 73H32Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupB.js:b_taichi7900_white/sourceShapes[3]"
    },
    {
      "d":"M29 29L34 20H38M62 20H66L71 29M29 71L34 80H38M62 80H66L71 71",
      "role":"trim",
      "width":0.09,
      "source_field":"native/HardwareVariantGroupB.js:b_taichi7900_white/sourceShapes[4]"
    },
    {
      "d":"M3 5H21L25 10M75 10L79 5H97M3 95H21L25 90M75 90L79 95H97",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupB.js:b_taichi7900_white/sourceShapes[5]"
    }
  ],
  "b_taichi9070_white_lcd":[
    {
      "d":"M2 1H30L34 12H66L70 1H97L100 12L93 19L82 10H74L70 18H30L26 10H18L7 19L0 12Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupB.js:b_taichi9070_white_lcd/sourceShapes[1]"
    },
    {
      "d":"M0 90L7 80L18 90H26L30 83H70L74 90H82L93 80L100 90L97 100H70L66 93H34L30 100H3Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupB.js:b_taichi9070_white_lcd/sourceShapes[2]"
    },
    {
      "d":"M30 16L34 8H66L70 16L68 22H32ZM30 84L34 92H66L70 84L68 78H32Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupB.js:b_taichi9070_white_lcd/sourceShapes[3]"
    },
    {
      "d":"M78.1 -5.4H94.4Q95.5 -5.4 95.5 -4.3V1.3Q95.5 2.4 94.4 2.4H78.1Q77 2.4 77 1.3V-4.3Q77 -5.4 78.1 -5.4ZM79.6 -4H92.9Q93.5 -4 93.5 -3.4V-0Q93.5 0.6 92.9 0.6H79.6Q79 0.6 79 -0V-3.4Q79 -4 79.6 -4Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupB.js:b_taichi9070_white_lcd/sourceShapes[4,5]",
      "feature":"external_display"
    },
    {
      "d":"M29 29L34 20H38M62 20H66L71 29M29 71L34 80H38M62 80H66L71 71",
      "role":"trim",
      "width":0.09,
      "source_field":"native/HardwareVariantGroupB.js:b_taichi9070_white_lcd/sourceShapes[6]"
    },
    {
      "d":"M3 5H21L25 10M75 10L79 5H97M3 95H21L25 90M75 90L79 95H97",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupB.js:b_taichi9070_white_lcd/sourceShapes[7]"
    }
  ],
  "b_biostar7600_oc":[{"d":"M0 28L20 2H44L34 14H13L0 39Z","role":"material","width":0.1,"source_field":"native/HardwareVariantGroupB.js:b_biostar7600_oc/sourceShapes[1]"},{"d":"M59 2H96L100 7V48L86 26H73Z","role":"material","width":0.1,"source_field":"native/HardwareVariantGroupB.js:b_biostar7600_oc/sourceShapes[2]"},{"d":"M0 58L17 80H36L42 99H5L0 95Z","role":"material","width":0.1,"source_field":"native/HardwareVariantGroupB.js:b_biostar7600_oc/sourceShapes[3]"},{"d":"M64 85H84L100 70V94L96 99H56Z","role":"material","width":0.1,"source_field":"native/HardwareVariantGroupB.js:b_biostar7600_oc/sourceShapes[4]"},{"d":"M4 28L17 12H35M66 9H92L96 15M5 72L20 91H36M65 93H88L96 82","role":"edge","width":0.1,"source_field":"native/HardwareVariantGroupB.js:b_biostar7600_oc/sourceShapes[5]"}],
  "nitroFront":[
    {
      "d":"M1.8 5H98.2Q98.9 5 98.9 5.7V93.3Q98.9 94 98.2 94H1.8Q1.1 94 1.1 93.3V5.7Q1.1 5 1.8 5Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupC.js:nitroFront/sourceShapes[1]"
    },
    {
      "d":"M1 4H99M1 96H99",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupC.js:nitroFront/sourceShapes[2]"
    },
    {
      "d":"M0.4 14V86M99.6 14V86",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupC.js:nitroFront/sourceShapes[3]"
    }
  ],
  "hellhoundSakuraFront":[
    {
      "d":"M1.8 3H98.2Q100 3 100 4.8V95.2Q100 97 98.2 97H1.8Q0 97 0 95.2V4.8Q0 3 1.8 3Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupC.js:hellhoundSakuraFront/sourceShapes[0]"
    },
    {
      "d":"M1 6H99M1 94H99",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupC.js:hellhoundSakuraFront/sourceShapes[1]"
    },
    {
      "d":"M64 10C62.8 8.8 62.38 7 63.7 6.34L64 6.88L64.3 6.34C65.62 7 65.2 8.8 64 10ZM64 10C64.7704474 8.4879118 66.352562 7.5322375 67.3881618 8.5836808L66.9672963 9.035867L67.5735719 9.1543148C67.3537771 10.6136606 65.5120882 10.7704474 64 10ZM64 10C65.6761627 10.2654781 67.0739633 11.4748389 66.3939991 12.7846666L65.83389 12.524133L65.9085889 13.1373378C64.4527482 13.3792631 63.7345219 11.6761627 64 10ZM64 10C64.2654781 11.6761627 63.5472518 13.3792631 62.0914111 13.1373378L62.16611 12.524133L61.6060009 12.7846666C60.9260367 11.4748389 62.3238373 10.2654781 64 10ZM64 10C62.4879118 10.7704474 60.6462229 10.6136606 60.4264281 9.1543148L61.0327037 9.035867L60.6118382 8.5836808C61.647438 7.5322375 63.2295526 8.4879118 64 10Z",
      "role":"trim",
      "width":0.09,
      "source_field":"native/HardwareVariantGroupC.js:hellhoundSakuraFront/blossom(64,10,.60)/all5petals-baked"
    },
    {
      "d":"M29 88C28.44 87.44 28.244 86.6 28.86 86.292L29 86.544L29.14 86.292C29.756 86.6 29.56 87.44 29 88ZM29 88C29.3595421 87.2943588 30.0978623 86.8483775 30.5811422 87.3390511L30.3847383 87.5500713L30.6676669 87.6053469C30.565096 88.2863749 29.7056412 88.3595421 29 88ZM29 88C29.7822093 88.1238898 30.4345162 88.6882581 30.1171996 89.2995111L29.8558153 89.1779287L29.8906748 89.464091C29.2112825 89.5769894 28.8761102 88.7822093 29 88ZM29 88C29.1238898 88.7822093 28.7887175 89.5769894 28.1093252 89.464091L28.1441847 89.1779287L27.8828004 89.2995111C27.5654838 88.6882581 28.2177907 88.1238898 29 88ZM29 88C28.2943588 88.3595421 27.434904 88.2863749 27.3323331 87.6053469L27.6152617 87.5500713L27.4188578 87.3390511C27.9021377 86.8483775 28.6404579 87.2943588 29 88Z",
      "role":"trim",
      "width":0.09,
      "source_field":"native/HardwareVariantGroupC.js:hellhoundSakuraFront/blossom(29,88,.28)/all5petals-baked"
    },
    {
      "d":"M31 87Q32 84 34 84Q34 87 31 87Z",
      "role":"trim",
      "width":0.09,
      "source_field":"native/HardwareVariantGroupC.js:hellhoundSakuraFront/sourceShapes[12]"
    }
  ],
  "c_hellhound_white":[
    {
      "d":"M1.8 3H98.2Q100 3 100 4.8V95.2Q100 97 98.2 97H1.8Q0 97 0 95.2V4.8Q0 3 1.8 3Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupC.js:c_hellhound_white/sourceShapes[0]"
    },
    {
      "d":"M1 6H99M1 94H99",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupC.js:c_hellhound_white/sourceShapes[1]"
    }
  ],
  "devilFront":[
    {
      "d":"M0 21L7 5H94L100 18H91L87 12H10L4 25Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupC.js:devilFront/sourceShapes[1]"
    },
    {
      "d":"M4 4H96V9H8Z",
      "role":"trim",
      "width":0.09,
      "source_field":"native/HardwareVariantGroupC.js:devilFront/sourceShapes[2]"
    },
    {
      "d":"M27 14L38 37L35 42L25 17ZM65 65L77 88H67L62 73Z",
      "role":"trim",
      "width":0.09,
      "source_field":"native/HardwareVariantGroupC.js:devilFront/sourceShapes[3]"
    },
    {
      "d":"M0 84L5 98H94L100 84V72L95 88H6L0 74Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupC.js:devilFront/sourceShapes[4]"
    },
    {
      "d":"M94 98L100 84V77L97 79L91 98Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupC.js:devilFront/sourceShapes[5]"
    }
  ],
  "c_fighter_mini":[
    {
      "d":"M0.5 3H99.5Q100 3 100 3.5V96.5Q100 97 99.5 97H0.5Q0 97 0 96.5V3.5Q0 3 0.5 3Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupC.js:c_fighter_mini/sourceShapes[0]"
    },
    {
      "d":"M1.8 7H98.2Q98.6 7 98.6 7.4V92.6Q98.6 93 98.2 93H1.8Q1.4 93 1.4 92.6V7.4Q1.4 7 1.8 7Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupC.js:c_fighter_mini/sourceShapes[1]"
    }
  ],
  "c_roc_luna":[
    {
      "d":"M5.7 3H94.3Q98.8 3 98.8 7.5V92.5Q98.8 97 94.3 97H5.7Q1.2 97 1.2 92.5V7.5Q1.2 3 5.7 3Z",
      "role":"edge",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupC.js:c_roc_luna/sourceShapes[1]"
    },
    {
      "d":"M32.3 2H82.7Q84 2 84 3.3V3.9Q84 5.2 82.7 5.2H32.3Q31 5.2 31 3.9V3.3Q31 2 32.3 2Z",
      "role":"material",
      "width":0.12,
      "source_field":"native/HardwareVariantGroupC.js:c_roc_luna/sourceShapes[2]"
    },
    {
      "d":"M1.6 10V88M2.35 10V88M3.1 10V88M3.85 10V88",
      "role":"vent",
      "width":0.11,
      "source_field":"native/HardwareVariantGroupC.js:c_roc_luna/sourceShapes[3,4,5,6]"
    }
  ]
}
        rows = {
    "sapphire-pulse-7600":{"series_id":"sapphire_pulse","profile_ref":"sapphire-pulse-7600","recipe":"","fan_ref":{"series_id":"sapphire_pulse","physical_count":2,"front_count":2,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.sapphiretech.com/en/consumer/pulse-radeon-rx-7600-8g-gddr6"],"traces":studies["sapphire_pulse"]},
    "sapphire-nitro-9070xt-oc":{"series_id":"sapphire_nitro","profile_ref":"sapphire-nitro-9070xt-oc","recipe":"","fan_ref":{"series_id":"sapphire_nitro","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.sapphiretech.com/en/consumer/nitro-radeon-rx-9070-xt-16g-gddr6"],"traces":studies["sapphire_nitro"]},
    "powercolor-hellhound-7800xt-oc":{"series_id":"powercolor_hellhound","profile_ref":"powercolor-hellhound-7800xt-oc","recipe":"","fan_ref":{"series_id":"powercolor_hellhound","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.powercolor.com/product-detail31.htm"],"traces":studies["powercolor_hellhound"]},
    "powercolor-red-devil-7800xt-oc":{"series_id":"powercolor_red_devil","profile_ref":"powercolor-red-devil-7800xt-oc","recipe":"","fan_ref":{"series_id":"powercolor_red_devil","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.powercolor.com/product-detail32.htm","https://www.powercolor.com/news-detail31.htm"],"traces":studies["powercolor_red_devil"]},
    "asrock-phantom-7900xtx-oc":{"series_id":"asrock_phantom","profile_ref":"asrock-phantom-7900xtx-oc","recipe":"","fan_ref":{"series_id":"asrock_phantom","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://pg.asrock.com/Graphics-Card/AMD/Radeon%20RX%207900%20XTX%20Phantom%20Gaming%2024GB%20OC/","https://www.asrock.com/Graphics-Card/photo/Radeon%20RX%207900%20XTX%20Phantom%20Gaming%2024GB%20OC%28L2%29.png"],"traces":studies["asrock_phantom"]},
    "asrock-steel-legend-7800xt-oc":{"series_id":"asrock_steel_legend","profile_ref":"asrock-steel-legend-7800xt-oc","recipe":"","fan_ref":{"series_id":"asrock_steel_legend","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.asrock.com/Graphics-Card/AMD/Radeon%20RX%207800%20XT%20Steel%20Legend%2016GB%20OC/","https://www.asrock.com/Graphics-Card/features/AxialFan-Radeon%20RX%207800%20XT%20Steel%20Legend%2016GB%20OC.jpg"],"traces":studies["asrock_steel_legend"]},
    "asrock-challenger-7600-oc":{"series_id":"asrock_challenger","profile_ref":"asrock-challenger-7600-oc","recipe":"","fan_ref":{"series_id":"asrock_challenger","physical_count":2,"front_count":2,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.asrock.com/Graphics-Card/AMD/Radeon%20RX%207600%20Challenger%208GB%20OC/","https://www.asrock.com/Graphics-Card/features/AxialFan-Radeon%20RX%207600%20Challenger%208GB%20OC.jpg"],"traces":studies["asrock_challenger"]},
    "asrock-taichi-7900xtx-oc":{"series_id":"asrock_taichi","profile_ref":"asrock-taichi-7900xtx-oc","recipe":"","fan_ref":{"series_id":"asrock_taichi","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.asrock.com/Graphics-Card/AMD/Radeon%20RX%207900%20XTX%20Taichi%2024GB%20OC/","https://www.asrock.com/Graphics-Card/photo/Radeon%20RX%207900%20XTX%20Taichi%2024GB%20OC%28L2%29.png"],"traces":studies["asrock_taichi"]},
    "xfx-merc310-7900xtx-black":{"series_id":"xfx_merc","profile_ref":"xfx-merc310-7900xtx-black","recipe":"","fan_ref":{"series_id":"xfx_merc","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.xfxforce.com/shop/xfx-speedster-merc-310-7900xtx-black-edition","https://cdn.prod.website-files.com/5d1911406ad3cbdb9924a753/639736d43e89781c8b59f26d_03.jpg"],"traces":studies["xfx_merc"]},
    "xfx-qick319-6750xt-core-jfdr":{"series_id":"xfx_qick","profile_ref":"xfx-qick319-6750xt-core-jfdr","recipe":"","fan_ref":{"series_id":"xfx_qick","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.xfxforce.com/shop/xfx-speedster-qick-319-amd-radeon-tm-rx-6750-xt-core-2"],"traces":studies["xfx_qick"]},
    "xfx-swft210-6600-core-lfdq":{"series_id":"xfx_swft","profile_ref":"xfx-swft210-6600-core-lfdq","recipe":"","fan_ref":{"series_id":"xfx_swft","physical_count":2,"front_count":2,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.xfxforce.com/shop/xfx-speedster-swft-210-amd-radeon-tm-rx-6600-core","https://cdn.prod.website-files.com/5d1911406ad3cbdb9924a753/6164513e798bee946064d2c2_01.jpg"],"traces":studies["xfx_swft"]},
    "yeston-atlantis-rx9070xt-16g":{"series_id":"yeston_atlantis","profile_ref":"yeston-atlantis-rx9070xt-16g","recipe":"","fan_ref":{"series_id":"yeston_atlantis","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://yestonstore.com/products/yeston-sakura-atlantis-radeon-rx-9070-xt-16g-gddr6-256bit-4nm-video-cards-desktop-computer-pc-graphics-card"],"traces":studies["yeston_atlantis"]},
    "yeston-sakura-rx7800xt-16g":{"series_id":"yeston_sakura","profile_ref":"yeston-sakura-rx7800xt-16g","recipe":"","fan_ref":{"series_id":"yeston_sakura","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://yestonstore.com/products/yeston-sakura-radeon-rx-7800-xt-16g-gddr6-256bit-desktop-computer-graphics-card"],"traces":studies["yeston_sakura"]},
    "biostar-radeon-rx7600-va7606rm81":{"series_id":"biostar_radeon","profile_ref":"biostar-radeon-rx7600-va7606rm81","recipe":"b_biostar7600_base","fan_ref":{"series_id":"biostar_radeon","physical_count":2,"front_count":2,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation","connector_positions"],"sources":["https://www.biostar.com.tw/app/en/vga/introduction.php?S_ID=316","https://www.biostar.com.tw/app/en/vga/export/spec_export.php?S_ID=316","https://www.biostar.com.tw/upload/Egate/bRX7600-TOP_f65T.png"],"traces":studies["biostar_radeon"]},
    "amd-reference-rx7900xtx-24g":{"series_id":"amd_reference","profile_ref":"amd-reference-rx7900xtx-24g","recipe":"","fan_ref":{"series_id":"amd_reference","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation","outer_dimensions_partial"],"sources":["https://www.amd.com/en/products/graphics/desktops/radeon/7000-series/amd-radeon-rx-7900xtx.html","https://www.amd.com/en/products/graphics/radeon-for-creators.html","https://www.amd.com/content/dam/amd/en/images/products/graphics/2648997-amd-radeon-7900xtx.jpg"],"traces":studies["amd_reference"]},
    "intel-limited-arc-a770-16g":{"series_id":"intel_limited","profile_ref":"intel-limited-arc-a770-16g","recipe":"","fan_ref":{"series_id":"intel_limited","physical_count":2,"front_count":2,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://game.intel.com/stories/intel-arc-graphics-overclocking-101/","https://www.intel.com/content/www/us/en/support/articles/000092523/graphics.html","https://www.intel.com/content/www/us/en/support/articles/000092554/graphics.html","https://builders.intel.com/docs/networkbuilders/intel-arc-graphics-empowers-medical-imaging-ai-inference-solution-1722407149.pdf","https://download.intel.com/newsroom/2022/2022innovation/Intel-Arc-A770-gpu.zip"],"traces":studies["intel_limited"]},
    "sapphire-pure-7800xt":{"series_id":"sapphire_pure","profile_ref":"sapphire-pure-7800xt","recipe":"","fan_ref":{"series_id":"sapphire_pure","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.sapphiretech.com/en/consumer/pure-radeon-rx-7800-xt-16g-gddr6"],"traces":studies["sapphire_pure"]},
    "powercolor-fighter-7800xt":{"series_id":"powercolor_fighter","profile_ref":"powercolor-fighter-7800xt","recipe":"","fan_ref":{"series_id":"powercolor_fighter","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.powercolor.com/product-detail33.htm"],"traces":studies["powercolor_fighter"]},
    "powercolor-reaper-9070xt":{"series_id":"powercolor_reaper","profile_ref":"powercolor-reaper-9070xt","recipe":"","fan_ref":{"series_id":"powercolor_reaper","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.powercolor.com/product-detail212.htm","https://www.powercolor.com/cn/product-detail212.htm"],"traces":studies["powercolor_reaper"]},
    "msi-hd4870-t2d512-oc-reference":{"series_id":"msi_hd4870_reference","profile_ref":"msi-hd4870-t2d512-oc-reference","recipe":"","fan_ref":{"series_id":"msi_hd4870_reference","physical_count":1,"front_count":1,"profile_status":"pending"},"unknown":["pcb_internal","absolute_rotation","fan_blade_count","fan_blade_geometry","outer_dimensions_partial"],"sources":["https://storage-asset.msi.com/datasheet/vga/global/R4870T2D512OC.pdf","https://de.msi.com/Graphics-Card/R4870T2D512OC/Specification","https://ua.msi.com/Graphics-card/R4870T2D512OC/Specification"],"traces":studies["msi_hd4870_reference"]},
    "msi-hd5450-md1gd3h-lp":{"series_id":"msi_hd5450_passive","profile_ref":"msi-hd5450-md1gd3h-lp","recipe":"","fan_ref":{"series_id":"msi_hd5450_passive","physical_count":0,"front_count":0,"profile_status":"not_applicable"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://storage-asset.msi.com/datasheet/vga/my/R5450-MD1GD3HLP.pdf"],"traces":studies["msi_hd5450_passive"]},
    "msi-hd5870-pm2d1g-reference":{"series_id":"msi_hd5870_reference","profile_ref":"msi-hd5870-pm2d1g-reference","recipe":"","fan_ref":{"series_id":"msi_hd5870_reference","physical_count":1,"front_count":1,"profile_status":"pending"},"unknown":["pcb_internal","absolute_rotation","fan_blade_count","fan_blade_geometry","outer_dimensions_partial"],"sources":["https://storage-asset.msi.com/datasheet/vga/ua/R5870PM2D1G.pdf","https://www.msi.com/Graphics-Card/R5870PM2D1G/Specification"],"traces":studies["msi_hd5870_reference"]},
    "msi-hd7970-tf-3gd5-oc-be":{"series_id":"msi_twin_frozr_hd7970","profile_ref":"msi-hd7970-tf-3gd5-oc-be","recipe":"","fan_ref":{"series_id":"msi_twin_frozr_hd7970","physical_count":2,"front_count":2,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://storage-asset.msi.com/datasheet/vga/global/R7970_TF_3GD5OC_BE.pdf","https://www.msi.com/Graphics-Card/R7970_TF_3GD5OC_BE/Specification","https://www.msi.com/Graphics-Card/R7970_TF_3GD5OC_BE/Gallery"],"traces":studies["msi_twin_frozr_hd7970"]},
    "msi-r9-290x-4gd5-reference":{"series_id":"msi_r9_290x_reference","profile_ref":"msi-r9-290x-4gd5-reference","recipe":"","fan_ref":{"series_id":"msi_r9_290x_reference","physical_count":1,"front_count":1,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://storage-asset.msi.com/datasheet/vga/global/R9-290X-4GD5.pdf"],"traces":studies["msi_r9_290x_reference"]},
    "asus-strix-r9fury-dc3-4g":{"series_id":"asus_strix_fury","profile_ref":"asus-strix-r9fury-dc3-4g","recipe":"","fan_ref":{"series_id":"asus_strix_fury","physical_count":3,"front_count":3,"profile_status":"pending"},"unknown":["pcb_internal","absolute_rotation","fan_blade_count","fan_blade_geometry"],"sources":["https://www.asus.com/it/news/ohcitiw9wqe49eh8/","https://www.asus.com/event/2016/productguide/id/fa_pg_mobovga_vol.1_2016.pdf","https://rog.asus.com/articles/hands-on/unboxing-strix-r9-fury/"],"traces":studies["asus_strix_fury"]},
    "msi-rx480-8g-reference":{"series_id":"msi_rx480_reference","profile_ref":"msi-rx480-8g-reference","recipe":"","fan_ref":{"series_id":"msi_rx480_reference","physical_count":1,"front_count":1,"profile_status":"pending"},"unknown":["pcb_internal","absolute_rotation","fan_blade_count","fan_blade_geometry"],"sources":["https://storage-asset.msi.com/datasheet/vga/global/AMD-Radeon-RX-480-8G.pdf"],"traces":studies["msi_rx480_reference"]},
    "sapphire-nitro-rx580-8g-01":{"series_id":"sapphire_nitro_polaris","profile_ref":"sapphire-nitro-rx580-8g-01","recipe":"","fan_ref":{"series_id":"sapphire_nitro_polaris","physical_count":2,"front_count":2,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.sapphiretech.com/en/consumer/nitro-rx-580-8g-g5"],"traces":studies["sapphire_nitro_polaris"]},
    "msi-vega64-8g-reference":{"series_id":"msi_vega64_reference","profile_ref":"msi-vega64-8g-reference","recipe":"","fan_ref":{"series_id":"msi_vega64_reference","physical_count":1,"front_count":1,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://storage-asset.msi.com/datasheet/vga/global/Radeon-RX-Vega-64-8G.pdf"],"traces":studies["msi_vega64_reference"]},
    "asrock-rx5500xt-challenger-d-8g":{"series_id":"asrock_challenger_rdna1","profile_ref":"asrock-rx5500xt-challenger-d-8g","recipe":"","fan_ref":{"series_id":"asrock_challenger_rdna1","physical_count":2,"front_count":2,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://asrock.com/Graphics-Card/AMD/Radeon%20RX%205500%20XT%20Challenger%20D%208G%20OC/","https://www.asrock.com/Graphics-Card/photo/Radeon%20RX%205500%20XT%20Challenger%20D%208G%20OC%28L2%29.png"],"traces":studies["asrock_challenger_rdna1"]},
    "msi-rx5700xt-8g-reference":{"series_id":"msi_rx5700xt_reference","profile_ref":"msi-rx5700xt-8g-reference","recipe":"","fan_ref":{"series_id":"msi_rx5700xt_reference","physical_count":1,"front_count":1,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://storage-asset.msi.com/datasheet/vga/global/Radeon-RX-5700-XT-8G.pdf"],"traces":studies["msi_rx5700xt_reference"]},
    "sapphire-pulse-rx6400-4g-lp":{"series_id":"sapphire_pulse_rdna2_lp","profile_ref":"sapphire-pulse-rx6400-4g-lp","recipe":"","fan_ref":{"series_id":"sapphire_pulse_rdna2_lp","physical_count":1,"front_count":1,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.sapphiretech.com/en/consumer/pulse-radeon-rx-6400-4g-gddr6"],"traces":studies["sapphire_pulse_rdna2_lp"]},
    "asus-tuf-rx6800xt-o16g":{"series_id":"asus_tuf_rdna2","profile_ref":"asus-tuf-rx6800xt-o16g","recipe":"","fan_ref":{"series_id":"asus_tuf_rdna2","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.asus.com/motherboards-components/graphics-cards/tuf-gaming/tuf-rx6800xt-o16g-gaming/","https://www.asus.com/ie/motherboards-components/graphics-cards/tuf-gaming/tuf-rx6800xt-o16g-gaming/techspec/","https://www.asus.com/bt/motherboards-components/graphics-cards/tuf-gaming/tuf-rx6800xt-o16g-gaming/"],"traces":studies["asus_tuf_rdna2"]},
    "sapphire-pulse-rx7900xt-20g":{"series_id":"sapphire_pulse_rdna3","profile_ref":"sapphire-pulse-rx7900xt-20g","recipe":"","fan_ref":{"series_id":"sapphire_pulse_rdna3","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.sapphiretech.com/en/consumer/pulse-radeon-rx-7900-xt-20g-gddr6"],"traces":studies["sapphire_pulse_rdna3"]},
    "asrock-taichi-rx9070xt-16g-oc":{"series_id":"asrock_taichi_rdna4","profile_ref":"asrock-taichi-rx9070xt-16g-oc","recipe":"","fan_ref":{"series_id":"asrock_taichi_rdna4","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.asrock.com/Graphics-Card/AMD/Radeon%20RX%209070%20XT%20Taichi%2016GB%20OC/","https://www.asrock.com/Graphics-Card/photo/Radeon%20RX%209070%20XT%20Taichi%2016GB%20OC%28L2%29.png"],"traces":studies["asrock_taichi_rdna4"]},
    "asrock-a380-challenger-itx-6g":{"series_id":"asrock_challenger_arc_a380","profile_ref":"asrock-a380-challenger-itx-6g","recipe":"","fan_ref":{"series_id":"asrock_challenger_arc_a380","physical_count":1,"front_count":1,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.asrock.com/Graphics-Card/Intel/Intel%20Arc%20A380%20Challenger%20ITX%206GB%20OC/index.asp","https://www.asrock.com/Graphics-Card/Intel/Intel%20Arc%20A380%20Challenger%20ITX%206GB%20OC/index.us.asp","https://www.asrock.com/Graphics-Card/features/AxialFan-Intel%20Arc%20A380%20Challenger%20ITX%206GB%20OC.jpg"],"traces":studies["asrock_challenger_arc_a380"]},
    "sparkle-a750-titan-8g-oc":{"series_id":"sparkle_titan_arc_a750","profile_ref":"sparkle-a750-titan-8g-oc","recipe":"","fan_ref":{"series_id":"sparkle_titan_arc_a750","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.sparkle.com.tw/files/20240202122437352.pdf"],"traces":studies["sparkle_titan_arc_a750"]},
    "acer-bifrost-a770-16g-oc":{"series_id":"acer_bifrost_arc_a770","profile_ref":"acer-bifrost-a770-16g-oc","recipe":"","fan_ref":{"series_id":"acer_bifrost_arc_a770","physical_count":2,"front_count":2,"profile_status":"pending"},"unknown":["pcb_internal","absolute_rotation","fan_blade_count","fan_blade_geometry","outer_dimensions_partial"],"sources":["https://www.acer.com/us-en/predator/desktops-and-all-in-ones/components/predator-bifrost-intel-arc-a770-oc","https://www.acer.com/ca-en/predator/desktops-and-all-in-ones/components/predator-bifrost-intel-arc-a770-oc/pdp/DP.BKCWW.P02","https://community.acer.com/en/kb/articles/16303-troubleshooting-the-acer-predator-bifrost-a770-video-card","https://store.acer.com/en-us/predator-bifrost-intel-arc-a770-oc-graphics-card"],"traces":studies["acer_bifrost_arc_a770"]},
    "asrock-b570-challenger-10g-oc":{"series_id":"asrock_challenger_arc_b570","profile_ref":"asrock-b570-challenger-10g-oc","recipe":"","fan_ref":{"series_id":"asrock_challenger_arc_b570","physical_count":2,"front_count":2,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.asrock.com/Graphics-Card/Intel/Intel%20Arc%20B570%20Challenger%2010GB%20OC/","https://asrock.com/Graphics-Card/Intel/Intel%20Arc%20B570%20Challenger%2010GB%20OC/"],"traces":studies["asrock_challenger_arc_b570"]},
    "sparkle-b580-titan-12g-oc":{"series_id":"sparkle_titan_arc_b580","profile_ref":"sparkle-b580-titan-12g-oc","recipe":"","fan_ref":{"series_id":"sparkle_titan_arc_b580","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.sparkle.com.tw/files/20241203213858182.pdf"],"traces":studies["sparkle_titan_arc_b580"]},
    "asrock-taichi-7900xtx-white-oc":{"series_id":"asrock_taichi","profile_ref":"asrock-taichi-7900xtx-white-oc","recipe":"b_taichi7900_white","fan_ref":{"series_id":"asrock_taichi","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.asrock.com/Graphics-Card/AMD/Radeon%20RX%207900%20XTX%20Taichi%20White%2024GB%20OC/index.asp","https://www.asrockchina.com.cn/Graphics-Card/photo/Radeon%20RX%207900%20XTX%20Taichi%20White%2024GB%20OC(L2).png","https://asrock.com/news/images/20230406-1.jpg"],"traces":studies["b_taichi7900_white"]},
    "asrock-taichi-rx9070xt-white-16g-oc":{"series_id":"asrock_taichi_rdna4","profile_ref":"asrock-taichi-rx9070xt-white-16g-oc","recipe":"b_taichi9070_white_lcd","fan_ref":{"series_id":"asrock_taichi_rdna4","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation","outer_dimensions_partial"],"sources":["https://www.asrock.com/Graphics-Card/AMD/Radeon%20RX%209070%20XT%20Taichi%20White%2016GB%20OC/index.asp","https://www.asrockchina.com.cn/Graphics-Card/photo/Radeon%20RX%209070%20XT%20Taichi%20White%2016GB%20OC(L2).png","https://www.asrockchina.com.cn/Graphics-Card/photo/Radeon%20RX%209070%20XT%20Taichi%20White%2016GB%20OC(L3).png"],"traces":studies["b_taichi9070_white_lcd"]},
    "biostar-radeon-rx7600-oc-va76s6rm81":{"series_id":"biostar_radeon","profile_ref":"biostar-radeon-rx7600-oc-va76s6rm81","recipe":"b_biostar7600_oc","fan_ref":{"series_id":"biostar_radeon","physical_count":2,"front_count":2,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation","connector_positions"],"sources":["https://www.biostar.com.tw/app/en/vga/introduction.php?S_ID=334","https://www.biostar.com.tw/app/en/vga/export/spec_export.php?S_ID=334","https://www.biostar.com.tw/upload/Egate/bBIOSTAR_RX7600_OC_T_XOJQ.png"],"traces":studies["b_biostar7600_oc"]},
    "sapphire-nitro-9070xt-phantomlink":{"series_id":"sapphire_nitro","profile_ref":"sapphire-nitro-9070xt-phantomlink","recipe":"c_nitro_phantom","fan_ref":{"series_id":"sapphire_nitro","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.sapphiretech.com/en/consumer/nitro-radeon-rx-9070-xt-ple-16g-gddr6"],"traces":studies["nitroFront"]},
    "sapphire-nitro-9070xt-phantomlink-polar":{"series_id":"sapphire_nitro","profile_ref":"sapphire-nitro-9070xt-phantomlink-polar","recipe":"c_nitro_polar","fan_ref":{"series_id":"sapphire_nitro","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.sapphiretech.com/en/consumer/nitro-radeon-rx-9070-xt-ple-polar-16g-gddr6"],"traces":studies["nitroFront"]},
    "sapphire-nitro-9070xt-valor-mortis":{"series_id":"sapphire_nitro","profile_ref":"sapphire-nitro-9070xt-valor-mortis","recipe":"c_nitro_valor","fan_ref":{"series_id":"sapphire_nitro","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.sapphiretech.com/en/consumer/nitro-radeon-rx-9070-xt-vme-16g-gddr6"],"traces":studies["nitroFront"]},
    "sapphire-nitro-9070xt-crimson-desert":{"series_id":"sapphire_nitro","profile_ref":"sapphire-nitro-9070xt-crimson-desert","recipe":"c_nitro_crimson","fan_ref":{"series_id":"sapphire_nitro","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.sapphiretech.com/en/consumer/nitro-radeon-rx-9070-xt-cde-16g-gddr6"],"traces":studies["nitroFront"]},
    "powercolor-hellhound-7800xt-sakura-limited":{"series_id":"powercolor_hellhound","profile_ref":"powercolor-hellhound-7800xt-sakura-limited","recipe":"c_hellhound_sakura_limited","fan_ref":{"series_id":"powercolor_hellhound","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://powercolor.com/product-detail34.htm"],"traces":studies["hellhoundSakuraFront"]},
    "powercolor-hellhound-7800xt-sakura":{"series_id":"powercolor_hellhound","profile_ref":"powercolor-hellhound-7800xt-sakura","recipe":"c_hellhound_sakura","fan_ref":{"series_id":"powercolor_hellhound","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://powercolor.com/product-detail35.htm"],"traces":studies["hellhoundSakuraFront"]},
    "powercolor-hellhound-7800xt-white":{"series_id":"powercolor_hellhound","profile_ref":"powercolor-hellhound-7800xt-white","recipe":"c_hellhound_white","fan_ref":{"series_id":"powercolor_hellhound","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://powercolor.com/product-detail36.htm"],"traces":studies["c_hellhound_white"]},
    "powercolor-red-devil-7800xt-limited":{"series_id":"powercolor_red_devil","profile_ref":"powercolor-red-devil-7800xt-limited","recipe":"c_devil_limited","fan_ref":{"series_id":"powercolor_red_devil","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://powercolor.com/product-detail39.htm"],"traces":studies["devilFront"]},
    "powercolor-red-devil-7800xt-bp":{"series_id":"powercolor_red_devil","profile_ref":"powercolor-red-devil-7800xt-bp","recipe":"c_devil_bp","fan_ref":{"series_id":"powercolor_red_devil","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://powercolor.com/product-detail256.htm"],"traces":studies["devilFront"]},
    "powercolor-fighter-7800xt-mini":{"series_id":"powercolor_fighter","profile_ref":"powercolor-fighter-7800xt-mini","recipe":"c_fighter_mini","fan_ref":{"series_id":"powercolor_fighter","physical_count":2,"front_count":2,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://powercolor.com/cn/product-detail37.htm"],"traces":studies["c_fighter_mini"]},
    "sparkle-a770-titan-16g-oc":{"series_id":"sparkle_titan_arc_a750","profile_ref":"sparkle-a770-titan-16g-oc","recipe":"","fan_ref":{"series_id":"sparkle_titan_arc_a750","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.sparkle.com.tw/files/20240507153541749.pdf"],"traces":studies["sparkle_titan_arc_a750"]},
    "sparkle-b580-titan-luna-12g-oc":{"series_id":"sparkle_titan_arc_b580","profile_ref":"sparkle-b580-titan-luna-12g-oc","recipe":"","fan_ref":{"series_id":"sparkle_titan_arc_b580","physical_count":3,"front_count":3,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.sparkle.com.tw/files/20250116155909862.pdf"],"traces":studies["sparkle_titan_arc_b580"]},
    "sparkle-b580-roc-luna-12g-oc-ultra":{"series_id":"sparkle_titan_arc_b580","profile_ref":"sparkle-b580-roc-luna-12g-oc-ultra","recipe":"c_roc_luna","fan_ref":{"series_id":"sparkle_titan_arc_b580","physical_count":2,"front_count":2,"profile_status":"reviewed"},"unknown":["pcb_internal","absolute_rotation"],"sources":["https://www.sparkle.com.tw/files/20250519101812700.pdf","https://www.sparkle.com.tw/en/B580-ROC-Luna","https://www.sparkle.com.tw/files/20250519102004865.png","https://www.sparkle.com.tw/files/20250519102016351.png"],"traces":studies["c_roc_luna"]}
        }
    }
    return rows
}

function profile(state) {
    if(!state || state.kind!=="gpu" || typeof state.model_id!=="string" || state.model_id.length>96
            || typeof state.series_id!=="string" || ids.indexOf(state.model_id)<0)return null
    var row=records()[state.model_id]
    return row && row.profile_ref===state.model_id && row.series_id===state.series_id ? row : null
}
