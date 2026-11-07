.pragma library
.import "HardwareFanDesigns.js" as Fans
.import "HardwareSolid.js" as Solid
.import "HardwareBoardDesigns.js" as Board
.import "HardwareSketch.js" as Sketch
.import "HardwareNotebook.js" as Notebook
.import "HardwareCartoon.js" as Cartoon
.import "HardwareVariants.js" as Variants
.import "HardwareModelNvidia042.js" as Nvidia
.import "HardwareModelRadeonArc042.js" as RadeonArc

// Original model-view artwork: PolyForm Noncommercial 1.0.0; see LICENSE.
// Exact-board contours use the existing reviewed profiles, not a ten-card gate.
// Unknown blades stay unknown. Added lips and cap glints
// are schematic material contours, not new RGB, parts, logos or dimensions.
// This module is called only while a model SVG is built, never on a frame.
var capDetails={
    "nvidia-founders-rtx5090-32g":"nvidia_founders",
    "nvidia-gtx1080-founders":"nvidia_founders_pascal",
    "nvidia-gtx780ti-reference":"nvidia_reference_kepler",
    "msi-gtx980ti-gaming-6g":"msi_gaming_maxwell",
    "amd-reference-rx7900xtx-24g":"amd_reference",
    "intel-limited-arc-a770-16g":"intel_limited",
    "asus-rog-strix-4090-oc":"asus_rog_strix",
    "msi-suprim-x-4090-24g":"msi_suprim",
    "zotac-twin-4060ti-oc-white":"zotac_twin_edge",
    "msi-vega64-8g-reference":"msi_vega64_reference"
}
function modelProfile(state) {
    return Nvidia.profile(state) || RadeonArc.profile(state)
}
function faceGeometry(state) {
    var g=Solid.geometry(state)
    // Miniature has the same parallel front plane as the retained legacy art.
    // Its separate top/right planes must not shift the source panel traces.
    if(state.icon_set==="miniature") {
        g.x-=.8;g.y+=.75;g.h-=.3
        g.centers=g.centers.map(function(x){return x-.8})
        if(g.fan_y)g.fan_y=g.fan_y.map(function(y){return y+.75-.3*.51})
    }
    return g
}
function contours(state,row,holes) {
    if(!row || !row.traces || !row.traces.length)return ''
    var g=faceGeometry(state),matrix=[g.w/100,0,0,g.h/100,g.x,g.y]
    var hand=["sketch","notebook_color","notebook_line","notebook_smile","inkwash"].indexOf(state.icon_set)>=0
    var line=hand || ["classic","outline"].indexOf(state.icon_set)>=0
    var color=line?state.ink:state.icon_set==="papercut"?'#2b485a':state.icon_set==="sticker"?'#415d60':Board.colors(state,Solid.palette(state)).edge
    var out='',region=contourRegion(state,g,holes)
    row.traces.forEach(function(trace,index){
        var m=trace.m?Notebook.matrix(matrix,trace.m):matrix
        var width=Math.max(.055,Math.min(.14,Number(trace.width)||.09))
        if(hand)width=Math.max(.095,width)
        var d=hand?Sketch.wobblyPath(trace.d,state.model_id+':model-panel:'+index,.35,14):trace.d
        // Build clipped paths once. Holes remain true circles and no seam can
        // pass over a rotating leaf. No SVG clipPath/filter dependency on Qt.
        // The reviewed White Taichi LCD frame projects above the main cover.
        // Keep only this explicitly sourced external component outside it;
        // normal panel seams still stop at the hand-drawn casing boundary.
        var external=row.recipe==='b_taichi9070_white_lcd' && trace.feature==='external_display'
        var traceRegion=external?[[0,0],[24,0],[24,24],[0,24]]:region
        var parts=d.match(/[Mm][^Mm]*/g)||[],clipped=''
        parts.forEach(function(part){
            var points=Notebook.casePolygon({d:part,m:m})
            if(/[Zz]\s*$/.test(part) && points.length)points.push(points[0])
            clipped+=Notebook.clippedStroke(points,traceRegion,holes,width)
        })
        if(clipped)out+='<path'+(external?' data-model-feature="external_display"':'')+' d="'+clipped+'" fill="none" stroke="'+color+'" stroke-width="'+n(width)+'" stroke-opacity="'+(line?'.78':'.55')+'"/>'
    })
    return out?'<g class="hardware-model-sku-contours" data-model="'+state.model_id+'">'+out+'</g>':''
}
function contourRegion(state,g,holes) {
    // Earlier notebook studies intentionally have their own slightly uneven
    // silhouette. Clip added source facets inside that exact silhouette too:
    // a straight Pascal panel must not protrude beyond the hand-drawn cover.
    if(state.icon_set.indexOf('notebook_')===0 || state.icon_set==='inkwash') {
        var c=Board.colors(state,Solid.palette(state));c.ink=state.ink
        var front=Object.prototype.hasOwnProperty.call(Notebook.cases,state.model_id)?'':Solid.front(state,g,c)
        var study=Notebook.shapeStudy(state,g,c,front,holes)
        var polygon=Notebook.casePolygon(study)
        if(polygon.length>=3)return polygon
    }
    return [[0,0],[24,0],[24,24],[0,24]]
}
function n(value){return Number(value).toFixed(5).replace(/\.?0+$/,"")||"0"}
function profile(state,index,kind) {
    var p=Notebook.fanProfile(state,Board.colors(state,Solid.palette(state)),index,kind)
    // Existing Pascal review notes explicitly describe the silver cap. This
    // material correction adds no claim about the uncountable dark blades.
    if(state.model_id==="nvidia-gtx1080-founders")p.hub_tone="silver"
    return p
}
function monochrome(source,state) {
    var line=state.icon_set==="outline",ink=state.ink
    var out=source.replace(/fill="url\(#[^"]+\)"/g,'fill="'+(line?'#f4f6f8':'#9aa7b5')+'"')
        .replace(/fill="(#[0-9a-fA-F]{6})"/g,function(all,color){
            var luma=.2126*parseInt(color.slice(1,3),16)+.7152*parseInt(color.slice(3,5),16)+.0722*parseInt(color.slice(5,7),16)
            return 'fill="'+(line?'#f4f6f8':luma<90?'#485666':luma<170?'#9aa7b5':'#e2e8ed')+'"'
        })
        .replace(/stroke="#[0-9a-fA-F]{6}"/g,'stroke="'+ink+'"')
        .replace(/stroke-width="([0-9.]+)"/g,function(all,width){return 'stroke-width="'+Math.min(Number(width),.15)+'"'})
    return '<g stroke="'+ink+'" stroke-width=".13">'+out+'</g>'
}
function paint(source,state) {
    var style=state.icon_set
    if(["classic","outline"].indexOf(style)>=0)return monochrome(source,state)
    if(["notebook_line","notebook_color","notebook_smile"].indexOf(style)>=0)
        return Notebook.rotorInk(source,{ink:state.ink})
    if(style==="sketch")return Sketch.linework(source,Sketch.palette(state),"model-rotor",{rotor:true,wobble:false,keepTiny:true})
    if(style==="inkwash")return Variants.inkwash(Notebook.rotorInk(source,{ink:"#455360"}),Variants.palette(style,state.ink))
    if(Variants.styles.indexOf(style)>=0)return Variants.paint(source,Variants.palette(style,state.ink))
    if(style==="cartoon")return Cartoon.paint(source,Cartoon.palette(state).line,.24,true)
    return source
}
function apertures(base,collector) {
    if(collector.length)return collector.map(function(r){return {cx:r.cx,cy:r.cy,radius:r.radius,kind:r.kind}})
    var out=[],pattern=/<g class="hardware-(fan|blower)" transform="translate\(([-+.0-9eE]+) ([-+.0-9eE]+)\) scale\(([-+.0-9eE]+)\)">/g,match
    while((match=pattern.exec(base))!==null)out.push({cx:Number(match[2]),cy:Number(match[3]),radius:Number(match[4])*3,kind:match[1]==="blower"?"blower":"axial"})
    if(out.length)return out
    var circles=base.match(/<circle\b[^>]*class="hardware-notebook-fan-opening"[^>]*\/>/g)||[]
    circles.forEach(function(tag){var a=Sketch.attributes(tag);out.push({cx:Number(a.cx),cy:Number(a.cy),radius:Number(a.r),kind:"axial"})})
    return out
}
function inverse(m) {
    var d=m[0]*m[3]-m[1]*m[2]
    if(!Number.isFinite(d) || Math.abs(d)<.00000001)return null
    return [m[3]/d,-m[1]/d,-m[2]/d,m[0]/d,(m[2]*m[5]-m[3]*m[4])/d,(m[1]*m[4]-m[0]*m[5])/d]
}
function strokeScale(m) {
    // Maximum singular value: an oblique/nonuniform cover transform must not
    // leave its wider stroke edge inside the circular opening.
    var a=m[0]*m[0]+m[1]*m[1],b=m[0]*m[2]+m[1]*m[3],d=m[2]*m[2]+m[3]*m[3]
    return Math.sqrt(Math.max(0,(a+d+Math.sqrt((a-d)*(a-d)+4*b*b))/2))
}
function transformedPath(d,m) {
    return d.replace(/([ML])([-+.0-9eE]+) ([-+.0-9eE]+)/g,function(all,command,x,y){
        return command+n(m[0]*Number(x)+m[2]*Number(y)+m[4])+' '+n(m[1]*Number(x)+m[3]*Number(y)+m[5])
    })
}
function clipPath(d,m,holes,width) {
    // Input is generated casing ink, never rotor geometry. Preserve untouched
    // curves verbatim; bake only a path that actually enters an aperture.
    // The hand renderers use M/L/H/V/Q/C here. Unknown arc/relative-subpath
    // syntax is left alone rather than being guessed into a different outline.
    if(/[Aa]/.test(d) || (d.match(/[Mm]/g)||[]).slice(1).indexOf('m')>=0)return null
    var inverseMatrix=inverse(m)
    if(!inverseMatrix)return null
    var parts=d.match(/[Mm][^Mm]*/g)||[],region=[[0,0],[24,0],[24,24],[0,24]],out='',changed=false
    parts.forEach(function(part){
        var points=Notebook.casePolygon({d:part,m:m})
        if(/[Zz]\s*$/.test(part) && points.length)points.push(points[0])
        var crossing=false,margin=width*.5+.012
        for(var i=1;i<points.length && !crossing;i++) {
            var a=points[i-1],b=points[i],dx=b[0]-a[0],dy=b[1]-a[1],length2=dx*dx+dy*dy
            holes.forEach(function(h){
                var t=length2?Math.max(0,Math.min(1,((h.cx-a[0])*dx+(h.cy-a[1])*dy)/length2)):0
                if(Math.pow(a[0]+dx*t-h.cx,2)+Math.pow(a[1]+dy*t-h.cy,2)<Math.pow(h.radius+margin,2))crossing=true
            })
        }
        if(crossing){out+=transformedPath(Notebook.clippedStroke(points,region,holes,width),inverseMatrix);changed=true}
        else out+=part
    })
    return changed?out:null
}
function casingInk(base,holes) {
    if(!holes.length)return base
    var stack=[{m:[1,0,0,1,0,0],skip:false,width:.2}]
    return base.replace(/<g\b[^>]*>|<\/g>|<path\b[^>]*\/>/g,function(tag){
        if(tag==='</g>'){if(stack.length>1)stack.pop();return tag}
        var a=Sketch.attributes(tag),parent=stack[stack.length-1]
        var m=Notebook.matrix(parent.m,Notebook.transformMatrix(a.transform))
        var cls=a['class']||'',skip=parent.skip || /hardware-(?:fan|blower)(?:\s|$)/.test(cls)
            || /\b(?:rotate|skewX|skewY)\s*\(/.test(a.transform||'')
        // Unknown notebook rotors may have no collected descriptor. Their
        // local cap/link drawing still lives in a normalized fan transform.
        if(/^<g\b/.test(tag)) {
            if(a.transform && holes.some(function(h){return Math.abs(m[4]-h.cx)<.0001 && Math.abs(m[5]-h.cy)<.0001
                    && Math.abs(Math.abs(m[0])-h.radius/3)<.0001 && Math.abs(Math.abs(m[3])-h.radius/3)<.0001}))skip=true
            stack.push({m:m,skip:skip,width:a['stroke-width']===undefined?parent.width:Number(a['stroke-width'])});return tag
        }
        if(skip || a.fill!=='none' || !a.d || /^hardware-fan-/.test(cls))return tag
        var width=(a['stroke-width']===undefined?parent.width:Number(a['stroke-width']))*strokeScale(m)
        if(!Number.isFinite(width))return tag
        var clipped=clipPath(a.d,m,holes,width)
        if(clipped===null)return tag
        if(!clipped)return ''
        return tag.replace(/\bd="[^"]*"/,'d="'+clipped+'"').replace(/\s*\/>$/,' data-model-casing-clip="fan-openings"/>')
    })
}
function notebookBand(state,holes) {
    if(state.model_id!=='zotac-twin-4060ti-oc-white')return ''
    // Exact existing Twin Edge cover path, not a new decorative stripe. Its
    // two sloping sides stay visible between the same two physical apertures.
    var g=Solid.geometry(state),m=[g.w/100,0,0,g.h/100,g.x,g.y]
    var d=Sketch.wobblyPath('M47 8H56L48 95H40Z',state.model_id+':model-band',.45,14)
    var world=Notebook.casePolygon({d:d,m:m});if(world.length)world.push(world[0])
    return '<g class="hardware-model-twin-edge-band"><path d="'+Notebook.clippedStroke(world,[[0,0],[24,0],[24,24],[0,24]],holes,.16)
        +'" fill="none" stroke="'+state.ink+'" stroke-width=".16" stroke-linejoin="round" stroke-linecap="round"/></g>'
}
function body(state,base,collector) {
    if(!state || state.kind!=="gpu" || typeof base!=="string" || !Array.isArray(collector)
            || !Board.profile(state))return base
    var row=modelProfile(state)
    if(!row)return base
    var hand=["sketch","notebook_line","notebook_color","notebook_smile","inkwash"].indexOf(state.icon_set)>=0
    var openings=Notebook.fanLayout(state,faceGeometry(state))
    if(hand) {
        // All reviewed model covers get the same physical hole exclusion,
        // including partial/unknown rotor collections. Filled paper and fixed
        // circular frames remain untouched. Ordinary topbar never calls here.
        base=casingInk(base,openings)
        if(capDetails[state.model_id]===state.series_id)base+=notebookBand(state,openings)
    }
    // Per-SKU source panels survive every style. Entries with unverified
    // casing retain the neutral original and explicitly have no new traces.
    base+=contours(state,row,openings)
    var holes=apertures(base,collector)
    var physical=collector.slice().sort(function(a,b){return a.cx-b.cx})
    var complete=collector.length===state.fan_count && physical.every(function(r,index){
        return [r.cx,r.cy,r.radius].every(Number.isFinite) && r.radius>0
            && (index===0 || r.cx-physical[index-1].cx>.0001)
    })
    collector.forEach(function(rotor){
        // Notebook/inkwash may omit an unreviewed rotor. A partial list is not
        // a physical fan index: leave it untouched instead of shifting a
        // middle fan's model/relative direction onto another aperture.
        if(!complete)return
        var p=profile(state,physical.indexOf(rotor),rotor.kind)
        // Unknown geometry is never replaced by a sampled generic leaf count.
        // A cap-only descriptor remains cap-only and cannot enable live RPM.
        var hints={machined_hub:state.model_id==="nvidia-founders-rtx5090-32g",
            red_label_edge:["msi-gtx980ti-gaming-6g","msi-vega64-8g-reference"].indexOf(state.model_id)>=0}
        rotor.body=paint(Fans.modelRotor(p,hints),state)
    })
    var line=["outline","sketch","notebook_line","notebook_color","notebook_smile","inkwash"].indexOf(state.icon_set)>=0
    var fixed=""
    holes.forEach(function(h,index){
        if(![h.cx,h.cy,h.radius].every(Number.isFinite) || h.radius<=0)return
        // This lip is outside the maximum leaf tip (2.73 / local basis 3).
        // It stays fixed while leaves rotate inside the original aperture.
        fixed+='<g class="hardware-model-intake-lip" data-model="'+state.model_id+'">'
            +'<circle cx="'+n(h.cx)+'" cy="'+n(h.cy)+'" r="'+n(h.radius*.955)+'" fill="none" stroke="'+(line?state.ink:'#9aa9b4')+'" stroke-opacity="'+(line?'.42':'.72')+'" stroke-width=".065"/></g>'
        if(!collector.length && state.model_id==="nvidia-gtx1080-founders") {
            var p=profile(state,index,h.kind),r=h.radius*p.hub_ratio
            fixed+='<circle class="hardware-model-static-metal-cap" cx="'+n(h.cx)+'" cy="'+n(h.cy)+'" r="'+n(r)+'" fill="'+(line?'none':'#bdc9d0')+'" stroke="'+(line?state.ink:'#8c9eaa')+'" stroke-width=".065"/>'
        }
    })
    return base+fixed
}
