.pragma library

// Generated original source-reference topology; no I/O, timers or sensors.
// Canonical gpu_pascal_surface055.py; photo-derived, not measured CAD.
var descriptorSHA256="8fbc9eaf2c8643eab79dcea47e52c32138e72400a8563f38ccdd811823fc7c47"
var data={"id":"nvidia-gtx1080-founders","points":{"a":[0.0,20.0,0.35],"b":[6.0,2.0,0.0],"c":[25.0,2.0,0.0],"d":[37.0,2.0,0.0],"e":[60.0,2.0,0.0],"f":[68.0,13.0,0.35],"g":[60.0,31.25,0.6],"h":[49.0,13.5417,0.1],"i":[14.0,21.875,0.35],"j":[15.0,86.4583,0.35],"k":[47.0,86.4583,0.1],"l":[60.0,98.0,0.0],"m":[25.0,98.0,0.0],"n":[6.0,98.0,0.0],"o":[0.0,80.0,0.35],"r":[92.0,2.0,0.0],"s":[100.0,19.0,0.2],"t":[90.0,15.0,0.7],"u":[93.0,50.0,0.25],"v":[100.0,50.0,0.35],"w":[100.0,81.0,0.2],"x":[89.0,75.0,0.7],"y":[92.0,98.0,0.0],"z":[68.0,85.0,0.35],"aa":[66.0,27.0,0.25],"ab":[64.0,50.0,0.8],"ac":[60.0,73.9583,0.6]},"facets":[["a","b","c","metal"],["a","c","i","shade"],["c","d","h","light"],["c","h","i","metal"],["d","e","h","metal"],["e","f","g","shade"],["e","g","h","light"],["a","i","j","metal"],["a","j","o","metal"],["o","j","m","shade"],["o","m","n","metal"],["j","k","m","light"],["m","k","l","metal"],["r","s","t","light"],["s","v","u","metal"],["s","u","t","shade"],["v","w","u","metal"],["w","x","u","shade"],["w","y","x","light"],["l","z","y","metal"],["z","x","y","shade"],["g","aa","ab","dark"],["g","ab","ac","dark"]],"vents":[[[0.168,0.073],[0.195,0.068],[0.186,0.158],[0.16,0.165]],[[0.16,0.835],[0.186,0.842],[0.195,0.932],[0.168,0.927]]],"source":"https://images.nvidia.com/aem-dam/Solutions/geforce/news/geforce-gtx-1080-founders-edition/nvidia-geforce-gtx-1080-Front.png","source_sha256":"493f66b6ddcc33a2bc6a052daaa63b40cad9f82d3a0771ecf193bc504ff36f10","depth_measured":false,"window_uv":[[0.14,0.21875],[0.49,0.135417],[0.6,0.3125],[0.6,0.739583],[0.47,0.864583],[0.15,0.864583]],"head_uv":[[0.2258852258852259,0.1397727903958016],[0.4706959706959707,0.07479578776420266],[0.2258852258852259,0.9298003913043478],[0.4706959706959707,0.9157532622906636],[0.6414072039072038,0.1826574693422519],[0.9295634920634921,0.1843297101449275],[0.6414072039072038,0.8348313823857302],[0.9295634920634921,0.8348313823857302]],"outer_path":"M0 20L6 2H92L100 19V81L92 98H6L0 80Z","fin_row_samples":13,"fin_pitch_measured":false,"existing_blades":53,"rotor_changed":false}

function descriptor() {return JSON.parse(JSON.stringify(data))}
function sourceHash() {return descriptorSHA256}
function point(key) {return data.points[key]}
function triangle(row) {return "M"+point(row[0])[0]+" "+point(row[0])[1]+"L"+point(row[1])[0]+" "+point(row[1])[1]+"L"+point(row[2])[0]+" "+point(row[2])[1]+"Z"}
function vent(row) {return "M"+row.map(function(p){return (p[0]*100)+" "+(p[1]*100)}).join("L")+"Z"}
function windowPath() {return vent(data.window_uv)}
function outerPath() {return data.outer_path}
function finPaths() {
    var out=[]
    for(var n=0;n<data.fin_row_samples;n++) {
        var y=28+44*n/(data.fin_row_samples-1)
        out.push("M18 "+y+"H56")
    }
    return out
}
function headPaths() {
    return data.head_uv.map(function(p){
        var x=p[0]*100,y=p[1]*100,rx=.71,ry=1.61
        return "M"+(x-rx)+" "+y+"Q"+(x-rx)+" "+(y-ry)+" "+x+" "+(y-ry)
            +"Q"+(x+rx)+" "+(y-ry)+" "+(x+rx)+" "+y+"Q"+(x+rx)+" "+(y+ry)+" "+x+" "+(y+ry)
            +"Q"+(x-rx)+" "+(y+ry)+" "+(x-rx)+" "+y+"Z"
    })
}
function fins(c) {
    // Keep the known background as source layer4; only layer5's first fin is
    // versioned from the old vertical sample to the photo's horizontal stack.
    var out='<rect x="17" y="27" width="35" height="45" rx="1" fill="'+c.caseShade+'"/>'
    for(var n=0;n<data.fin_row_samples;n++)out+='<rect class="hardware-pascal055-fin-sample" x="18" y="'+(27.7+43.6*n/(data.fin_row_samples-1))
        +'" width="38" height=".65" rx=".25" fill="'+c.metal+'"/>'
    return out
}
function plane(row) {
    var a=point(row[0]),b=point(row[1]),c=point(row[2])
    var det=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    var x=((b[2]-a[2])*(c[1]-a[1])-(c[2]-a[2])*(b[1]-a[1]))/det
    var y=((b[0]-a[0])*(c[2]-a[2])-(c[0]-a[0])*(b[2]-a[2]))/det
    return [x,y,a[2]-x*a[0]-y*a[1]]
}
function creasePaths() {
    var edges={},out=[]
    data.facets.forEach(function(row){
        [[0,1],[1,2],[2,0]].forEach(function(pair){
            var keys=[row[pair[0]],row[pair[1]]].sort(),key=keys.join(":")
            if(!edges[key])edges[key]={keys:keys,planes:[],roles:[]}
            edges[key].planes.push(plane(row));edges[key].roles.push(row[3])
        })
    })
    Object.keys(edges).sort().forEach(function(key){
        var e=edges[key],p=e.planes
        // Existing outer casing/window strokes own the boundaries. Do not
        // expose the triangulation diagonal inside one flat metal region.
        if(p.length<2)return
        if(e.roles[0]===e.roles[1]&&p[0].every(function(v,n){return Math.abs(v-p[1][n])<1e-9}))return
        var a=point(e.keys[0]),b=point(e.keys[1])
        out.push("M"+a[0]+" "+a[1]+"L"+b[0]+" "+b[1])
    })
    data.vents.forEach(function(row){out.push(vent(row))})
    return out
}
function face(c) {
    function blend(a,b,t) {
        var x=parseInt(a.slice(1),16),y=parseInt(b.slice(1),16),value="#"
        for(var n=16;n>=0;n-=8)value+=Math.round(((x>>n)&255)*(1-t)+((y>>n)&255)*t).toString(16).padStart(2,"0")
        return value
    }
    var colors={metal:c.metal,light:blend(c.metal,"#ffffff",.32),shade:blend(c.metal,c.caseShade,.28),dark:c.caseShade},out=""
    data.facets.forEach(function(row,index){out+='<path class="hardware-pascal055-facet" data-facet="'+index+'" d="'+triangle(row)+'" fill="'+colors[row[3]]+'"/>'})
    data.vents.forEach(function(row){out+='<path class="hardware-pascal055-vent" d="'+vent(row)+'" fill="'+c.disk+'"/>'})
    data.head_uv.forEach(function(p){var x=p[0]*100,y=p[1]*100
        out+='<ellipse class="hardware-pascal055-fixed-head" cx="'+x+'" cy="'+y+'" rx=".71" ry="1.61" fill="'+c.metal+'" stroke="'+c.caseShade+'" stroke-width=".25"/>'
            +'<ellipse cx="'+x+'" cy="'+y+'" rx=".23" ry=".52" fill="'+c.disk+'"/>'})
    return out
}
