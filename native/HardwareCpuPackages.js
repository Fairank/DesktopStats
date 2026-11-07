.pragma library
function profile(id) {
    return typeof id==="string" && Object.prototype.hasOwnProperty.call(profiles,id)
        ? JSON.parse(JSON.stringify(profiles[id])) : null
}
function label(value) {
    return typeof value==="string" && /^[A-Z0-9][A-Z0-9 -]{0,27}$/.test(value)?value:""
}
function key(input) {
    if(!input || input.kind!=="cpu" || input.confidence!=="model")return ""
    var package_=input.cpu_package,p=package_ && profile(package_.id)
    if(!p || p.vendor!==input.vendor || package_.vendor!==p.vendor
            || typeof input.id!=="string" || !/^[a-z][a-z0-9-]{0,63}$/.test(input.id)
            || input.id!==package_.model_id || input.style!==packageStyle(p.id))return ""
    return "cpu@"+p.id+"@"+input.id+"@"+label(package_.label_ascii)
}
function fromKey(value) {
    if(typeof value!=="string" || value.length>160)return null
    var pieces=value.split("@"),p=pieces.length===4?profile(pieces[1]):null
    return pieces[0]==="cpu" && p && /^[a-z][a-z0-9-]{0,63}$/.test(pieces[2]) && label(pieces[3])===pieces[3]
        ? {id:p.id,vendor:p.vendor,model_id:pieces[2],label_ascii:pieces[3]} : null
}
function packageStyle(id) {return id==='amd_am5'?'am5':['intel_lga1700_1851','intel_lga2011_2066','amd_tr4_family','amd_str5'].indexOf(id)>=0?'lga_rect':'chip'}
function hex(value,fallback) {return typeof value==="string" && /^#[0-9a-fA-F]{6}$/.test(value)?value:fallback}
function path(points,p) {
    var scale=18/Math.max(p.reference_size[0],p.reference_size[1]),w=p.reference_size[0]*scale,h=p.reference_size[1]*scale
    return points.map(function(v,index){return (index?"L":"M")+(12+(v[0]-.5)*w).toFixed(4)+" "+(12+(v[1]-.5)*h).toFixed(4)}).join("")+"Z"
}
function paths(descriptor) {
    var p=descriptor && profile(descriptor.id)
    return p?{package:{d:path(p.substrate,p),m:[1,0,0,1,0,0]},lid:{d:path(p.lid,p),m:[1,0,0,1,0,0]},style:p.id}:null
}
function palette(style,ink) {
    var p={pcb:"#426b60",lid:"#cbd6dd",edge:hex(ink,"#425265"),mark:"#52616b",width:.38,line:false}
    if(style==="outline"){p.line=true;p.width=.68}
    if(style==="classic"){p.line=true;p.width=.90;p.mark=p.edge}
    if(style==="solid"){p.pcb="#344e63";p.lid="#8ca7bb";p.mark="#253e50";p.width=.20}
    if(style==="soft"){p.pcb="#8ba99b";p.lid="#e5e9de";p.edge="#738e86";p.width=.24}
    if(style==="cartoon"){p.pcb="#80a7a0";p.lid="#e5e3cf";p.width=.54}
    if(style==="notebook_color" || style==="notebook_smile"){p.pcb="#a3bba8";p.lid="#dde0cb";p.width=.42}
    if(style==="notebook_line"){p.line=true;p.width=.40}
    if(style==="sketch"){p.line=true;p.width=.31}
    if(style==="sticker"){p.pcb="#9fbdb1";p.lid="#fff0d7";p.edge="#415d60";p.width=.62}
    if(style==="papercut"){p.pcb="#29485c";p.lid="#f3dfbd";p.edge="#29485c";p.mark="#29485c";p.width=.10}
    if(style==="inkwash"){p.pcb="#5d879e";p.lid="#abc5cd";p.edge="#3b5874";p.mark="#3b5874";p.width=.29}
    return p
}
function body(state) {
    var descriptor=state.cpu_package,p=descriptor && profile(descriptor.id)
    if(!p)return ""
    var c=palette(state.icon_set,state.ink),shapes=paths(descriptor)
    function polygon(d,fill,cls,width) {
        return '<path class="'+cls+'" d="'+d+'" fill="'+(c.line?'none':fill)+'" stroke="'+c.edge+'" stroke-width="'+width+'"/>'
    }
    var out=""
    if(p.carrier) {
        // A separate orange carrier frame; no retention screw/lever inference.
        out+='<g transform="translate(-.36 -.36) scale(1.03)">'+polygon(shapes.package.d,"#d88943","cpu-carrier-reference",c.width)+'</g>'
    }
    out+=polygon(shapes.package.d,c.pcb,"cpu-package-outline",c.width)
        +polygon(shapes.lid.d,c.lid,"cpu-lid-outline",c.width*.9)
    // The index triangle is a reference orientation mark, not extra pin legs.
    var scale=18/Math.max(p.reference_size[0],p.reference_size[1]),w=p.reference_size[0]*scale,h=p.reference_size[1]*scale
    out+='<path class="cpu-index-mark" d="M'+(12-w/2+.45)+' '+(12+h/2-.45)+'h1.0v-1.0Z" fill="'+(c.line?c.edge:'#d0b76d')+'"/>'
    var mark=label(descriptor.label_ascii),brand=p.vendor==='intel'?'INTEL':'AMD'
    if(mark) {
        var words=mark.split(' '),model=words[words.length-1]
        out+='<g class="cpu-model-mark" fill="'+(c.line?c.edge:c.mark)+'" font-family="Segoe UI,sans-serif" text-anchor="middle">'
            +'<text x="12" y="10.7" font-size="1.6">'+brand+'</text>'
            +'<text x="12" y="13.3" font-size="'+Math.min(1.5,w*.69/Math.max(3,model.length)*1.5)+'">'+model+'</text></g>'
    }
    if(state.icon_set==='sketch' || state.icon_set.indexOf('notebook_')===0) {
        out+='<path class="cpu-pencil-hatch" d="M'+(12-w*.22)+' '+(12+h*.29)+'l1.2-.18m.7.25l1.1-.12" fill="none" stroke="'+c.edge+'" stroke-width=".15" opacity=".45"/>'
    }
    if(state.icon_set==='cartoon' || state.icon_set==='notebook_smile') {
        out+='<g class="'+(state.icon_set==='cartoon'?'hardware-cartoon-expression':'notebook-smile')+'" fill="none" stroke="'+c.edge+'" stroke-width=".25">'
            +'<path d="M10.8 15.2v.30M13.2 15.2v.30M11.0 16.0Q12 16.9 13 16.0"/></g>'
    }
    return '<g class="hardware-cpu-package" data-package="'+p.id+'" data-contacts="'+p.contacts+'">'+out+'</g>'
}
// Original procedural CPU packages: PolyForm Noncommercial1.0.0.
// Shared contours across styles; reference proportions are not manufacturing CAD.
// No timers, random state, device access, external assets or manufacturer logos.
var profiles = {"intel_lga115x_1200":{"id":"intel_lga115x_1200","substrate":[[0.025,0.0],[0.975,0.0],[1.0,0.025],[1.0,0.975],[0.975,1.0],[0.025,1.0],[0.0,0.975],[0.0,0.025]],"lid":[[0.14500000000000002,0.1],[0.855,0.1],[0.9,0.14500000000000002],[0.9,0.855],[0.855,0.9],[0.14500000000000002,0.9],[0.1,0.855],[0.1,0.14500000000000002]],"carrier":false,"vendor":"intel","contacts":"lga","reference_size":[37.5,37.5]},"intel_lga1700_1851":{"id":"intel_lga1700_1851","substrate":[[0.025,0.0],[0.975,0.0],[1.0,0.025],[1.0,0.975],[0.975,1.0],[0.025,1.0],[0.0,0.975],[0.0,0.025]],"lid":[[0.13,0.075],[0.87,0.075],[0.915,0.12],[0.915,0.88],[0.87,0.925],[0.13,0.925],[0.085,0.88],[0.085,0.12]],"carrier":false,"vendor":"intel","contacts":"lga","reference_size":[37.5,45.0]},"intel_lga2011_2066":{"id":"intel_lga2011_2066","substrate":[[0.025,0.0],[0.975,0.0],[1.0,0.025],[1.0,0.975],[0.975,1.0],[0.025,1.0],[0.0,0.975],[0.0,0.025]],"lid":[[0.13,0.075],[0.87,0.075],[0.915,0.12],[0.915,0.88],[0.87,0.925],[0.13,0.925],[0.085,0.88],[0.085,0.12]],"carrier":false,"vendor":"intel","contacts":"lga","reference_size":[45.0,52.5]},"amd_am4":{"id":"amd_am4","substrate":[[0.025,0.0],[0.975,0.0],[1.0,0.025],[1.0,0.975],[0.975,1.0],[0.025,1.0],[0.0,0.975],[0.0,0.025]],"lid":[[0.14500000000000002,0.1],[0.855,0.1],[0.9,0.14500000000000002],[0.9,0.855],[0.855,0.9],[0.14500000000000002,0.9],[0.1,0.855],[0.1,0.14500000000000002]],"carrier":false,"vendor":"amd","contacts":"pga","reference_size":[40.0,40.0]},"amd_am5":{"id":"amd_am5","substrate":[[0.025,0.0],[0.975,0.0],[1.0,0.025],[1.0,0.975],[0.975,1.0],[0.025,1.0],[0.0,0.975],[0.0,0.025]],"lid":[[0.11,0.08],[0.24,0.08],[0.24,0.18],[0.34,0.18],[0.34,0.08],[0.66,0.08],[0.66,0.18],[0.76,0.18],[0.76,0.08],[0.89,0.08],[0.92,0.11],[0.92,0.24],[0.82,0.24],[0.82,0.34],[0.92,0.34],[0.92,0.66],[0.82,0.66],[0.82,0.76],[0.92,0.76],[0.92,0.89],[0.89,0.92],[0.76,0.92],[0.76,0.82],[0.66,0.82],[0.66,0.92],[0.34,0.92],[0.34,0.82],[0.24,0.82],[0.24,0.92],[0.11,0.92],[0.08,0.89],[0.08,0.76],[0.18,0.76],[0.18,0.66],[0.08,0.66],[0.08,0.34],[0.18,0.34],[0.18,0.24],[0.08,0.24],[0.08,0.11]],"carrier":false,"vendor":"amd","contacts":"lga","reference_size":[40.0,40.0]},"amd_tr4_family":{"id":"amd_tr4_family","substrate":[[0.025,0.0],[0.975,0.0],[1.0,0.025],[1.0,0.975],[0.975,1.0],[0.025,1.0],[0.0,0.975],[0.0,0.025]],"lid":[[0.13,0.08],[0.87,0.08],[0.915,0.125],[0.915,0.875],[0.87,0.92],[0.13,0.92],[0.085,0.875],[0.085,0.125]],"carrier":true,"vendor":"amd","contacts":"lga","reference_size":[58.5,75.4]},"amd_str5":{"id":"amd_str5","substrate":[[0.025,0.0],[0.975,0.0],[1.0,0.025],[1.0,0.975],[0.975,1.0],[0.025,1.0],[0.0,0.975],[0.0,0.025]],"lid":[[0.13,0.08],[0.87,0.08],[0.915,0.125],[0.915,0.875],[0.87,0.92],[0.13,0.92],[0.085,0.875],[0.085,0.125]],"carrier":true,"vendor":"amd","contacts":"lga","reference_size":[58.5,75.4]}}
