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
    if(state && ((recipe==='a_msi_480_observed' && state.model_id==='msi-n480gtx-m2d15')
            || (recipe==='a_gigabyte_460_rev1_observed' && state.model_id==='gigabyte-gtx460-oc-1g-rev1')))
        return legacy052Face(state,g,c)
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

// Exact observed 2010 exteriors. Coordinates/ridge samples are reference art;
// no unreviewed blade count, hidden pipe connection or label illustration.
function legacy052Rect(x,y,w,h,tone,extra) {
    return '<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" fill="'+tone+'"'+(extra?' '+extra:'')+'/>'
}
function legacy052Path(d,tone,extra) {
    return '<path d="'+d+'" fill="'+tone+'"'+(extra?' '+extra:'')+'/>'
}
function legacy052Face(state,g,c){
 if(!state||state.kind!=='gpu'||['msi-n480gtx-m2d15','gigabyte-gtx460-oc-1g-rev1'].indexOf(state.model_id)<0)return '';
 let value='';
 if(state.model_id==='msi-n480gtx-m2d15'){
  value=p('M0 8H61L68 3H94L100 18V88L91 97H0Z',c.caseBody);
  value+=legacy052Rect(2,13,58,74,c.caseShade,'class="hardware-observed-silver-window"');
  // Bounded horizontal ridge samples, not a manufacturer's fin count.
  for(let row=0;row<16;row++)value+=legacy052Rect(3,14+row*4.5,56,1.5,c.metal,'data-reference="sampled-horizontal-ridge"');
  for(let x of[14,26,38,50])value+=legacy052Rect(x,13,1.3,74,c.metal,'data-reference="sampled-cross-support"');
  // Photo5 shows four distinct visible arcs. Middle arcs overlap;these are
  // four observed segments,not a total-pipe count or guessed hidden joins.
  value+=legacy052Path('M24 10C24 4 31 -2 34 0Q38 3 38 10M37 10C37 5 39 -1 41 1Q43 4 43 10M41 10C42 2 47 -1 50 1Q54 4 54 10M47 10C48 2 53 1 56 4Q59 7 59 10','none','stroke="'+c.metal+'" stroke-width="1.3" stroke-linecap="round" data-reference="four-observed-visible-arc-segments-not-total"');
  value+=p('M61 8L68 3H94L100 18V29L90 19H70L65 37H60Z',c.caseShade)
   +p('M61 72L69 89H94L91 97H61Z',c.caseShade);
  // Only broad observed warm label colour fields. No aeroplane,licensed
  // illustration,manufacturer wordmark bitmap or copied label artwork.
  value+=legacy052Path('M71 10H93L99 20V40L92 31L86 18Z','#a75d58','data-reference="abstract-warm-label-field"')
   +legacy052Path('M62 71L72 89H94L99 80V91L91 97H67Z','#bd795d','data-reference="abstract-warm-label-field"');
 }else{
  // Keep the CURRENT Rev1 silhouette and positions, not Rev2 inclined fans.
  value=p('M0 34Q1 12 17 6H41L49 17L58 7H83Q99 15 100 35V72Q97 89 83 94H61L50 84L39 94H16Q2 88 0 69Z',c.caseBody)
   +p('M0 34Q1 12 17 6H41L49 17L41 26L31 16H17Q7 20 6 39Z',c.caseTop)
   +p('M58 7H83Q99 15 100 35L93 42Q93 22 82 17H66L58 26L50 17Z',c.caseShade)
   +p('M0 69Q2 88 16 94H39L50 84L40 76H18L8 64Z M61 94H83Q97 89 100 72L92 64L82 82H65L58 76L50 84Z',c.caseTop)
   +legacy052Rect(43,35,13,30,c.caseShade);
 }
 return '<g class="hardware-observed-legacy052" data-exact-id="'+state.model_id+'" transform="translate('+g.x+' '+g.y+') scale('+(g.w/100)+' '+(g.h/100)+')">'+value+'</g>';
}
// Plain monoline alphabet;this is not the manufacturer italic MSI wordmark.
var legacy052Letters={M:'M0 .8V0L.32 .42L.64 0V.8',S:'M.60 .10Q.16 -.12 .06 .18Q-.03 .40 .31 .42Q.73 .44 .59 .69Q.42 .95 .02 .72',I:'M0 0H.52M.26 0V.8M0 .8H.52',N:'M0 .8V0L.62 .8V0',G:'M.62 .13Q.12 -.12 .04 .29Q-.08 .87 .51 .80L.62 .70V.44H.34',T:'M0 0H.64M.32 0V.8',X:'M0 0L.64 .8M.64 0L0 .8',4:'M.50 .8V0L0 .53H.64',8:'M.31 .39C-.06 .34 -.05 -.04 .31 0C.68 -.04 .68 .34 .31 .39C-.08 .43 -.08 .85 .31 .8C.70 .85 .70 .43 .31 .39',0:'M.31 0Q-.04 0 0 .4Q-.04 .8 .31 .8Q.68 .8 .62 .4Q.68 0 .31 0Z'};
function legacy052Word(text,color,stroke,transform,klass){
 let out='';for(let i=0;i<text.length;i++)out+='<path d="'+legacy052Letters[text[i]]+'" transform="translate('+(i*.83)+' 0)"/>';
 return '<g class="'+klass+'" transform="'+transform+'" fill="none" stroke="'+color+'" stroke-width="'+stroke+'" stroke-linecap="round" stroke-linejoin="round">'+out+'</g>';
}
function legacy052BrandCap(state,opening){
 if(state.model_id!=='msi-n480gtx-m2d15')return '';
 const k=opening.radius*.34,color=state.icon_set==='miniature'?'#edf2f5':state.icon_set==='papercut'?'#29485c':state.ink;
 return legacy052Word('MSI',color,.11,'translate('+(opening.cx-1.15*k)+' '+(opening.cy-.40*k)+') scale('+k+')','hardware-static-brand-label-vector');
}
function legacy052Badge(state,g){
 if(state.model_id!=='msi-n480gtx-m2d15')return '';
 const line=['notebook_line','notebook_color'].includes(state.icon_set),ink=line?state.ink:state.icon_set==='papercut'?'#f3dfbd':'#edf2f5';
 const x=g.x+g.w*.35,y=g.y+g.h*.44,w=g.w*.21,h=g.h*.115;
 return '<g class="hardware-source-model-badge">'+legacy052Rect(x,y,w,h,line?'none':'#26323c',line?'stroke="'+state.ink+'" stroke-width=".075"':'')+legacy052Word('N480GTX',ink,.085,'translate('+(x+w*.07)+' '+(y+h*.18)+') scale('+(w*.86/(7*.83))+')','hardware-model-code-vector')+'</g>';
}

function legacy052Fixed(state,g,holes) {
    if(!state || state.kind!=='gpu' || state.model_id!=='msi-n480gtx-m2d15')return ''
    return (holes.length===1?legacy052BrandCap(state,holes[0]):'')+legacy052Badge(state,g)
}
function legacy052FanTones(state,base) {
    if(!state || state.kind!=='gpu' || state.model_id!=='gigabyte-gtx460-oc-1g-rev1' || state.icon_set!=='papercut')return base
    // Repaint existing opening circles only; preserve their count and radii.
    return base.replace(/(<g class="hardware-fan"[^>]*>)([\s\S]*?)(<\/g>)/g,function(all,start,body,end) {
        return start+body.replace(/<circle r="3"[^>]*\/>/,function(tag){return tag.replace(/fill="[^"]*"/,'fill="#f3dfbd"')})
            .replace(/<circle r="2.90"[^>]*\/>/,function(tag){return tag.replace(/\s*\/>$/,' stroke="#d39978" stroke-width=".065"/>')})+end
    })
}
