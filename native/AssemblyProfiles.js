.pragma library
.import "HardwareSolid.js" as Solid
.import "HardwareNotebook.js" as Notebook
.import "HardwareNotebookParts.js" as Parts
.import "HardwareMemoryShapes.js" as Memory
.import "HardwareBoardDesigns.js" as Board
.import "HardwareFanDesigns.js" as Fans
.import "HardwareCpuPackages.js" as Cpu

// Reuse reviewed model-specific 2D construction as the source of the 3D
// silhouette and fan vanes. No sensor, renderer, animation or remote asset.
function state(input) {
    return {kind:input.kind,vendor:input.vendor,board_vendor:input.board_vendor,
        style:input.style,fan_count:input.visible_fan_count==null?input.fan_count:input.visible_fan_count,
        series_id:input.series_id,shroud:input.shroud,accent:input.accent,ink:"#455360",
        icon_set:"solid",model_id:input.confidence==="model"?input.id:""}
}
function shape(value) {return value?{d:value.d,m:value.m}:null}
function gpu(input) {
    const s=state(input),g=Solid.geometry(s),c=Board.colors(s,Solid.palette(s));c.ink="#455360"
    const front=Solid.front(s,g,c),rows=Notebook.sourceShapes(front)
    const passive=s.series_id==="gigabyte_silent_pascal"&&s.fan_count===0
    const shell=s.series_id==="msi_hd5450_passive"&&s.fan_count===0
        ?{d:"M0 17H31V6H99V91H31V84H0Z",m:[g.w/100,0,0,g.h/100,g.x,g.y]}
        :rows[passive?1:0]
    const layout=Notebook.fanLayout(s,g)
    return {bounds:{x:g.x,y:g.y,width:g.w,height:g.h},shell:shape(shell),
        physical_fan_count:input.fan_count,front_fan_count:layout.length,
        fans:layout.map(function(f,index){
            const p=Notebook.fanProfile(s,c,index,f.kind)
            const colors=Fans.fanPalette(p)
            if(p.hub_tone==="silver")colors.hub="#bdc9d0"
            else if(p.hub_tone==="dark")colors.hub="#343d44"
            else if(p.hub_tone==="light")colors.hub="#e1e6e8"
            const blades=[]
            if(p.blades!==null&&p.shape!=="neutral") {
                for(let i=0;i<p.blades;i++) {
                    const leaf=Object.assign({},p)
                    if(p.blade_pattern==="alternating")leaf.blade_variant=i%2===0?"dispersion":"traditional"
                    blades.push({d:Fans.blade(leaf),rotation:i*360/p.blades,mirror:p.direction===-1})
                }
            }
            return {cx:f.cx,cy:f.cy,radius:f.radius,kind:f.kind,
                profile:p,blade_paths:blades,
                known:p.blades!==null&&p.shape!=="neutral",direction:p.direction,
                hub_ratio:p.hub_ratio,outer_ring:p.outer_ring===true,group_size:p.group_size,
                colors:colors}
        }),colors:{body:c.caseBody,metal:c.metal,pcb:c.pcb},
        details:rows.slice(1,8).filter(function(r){return r.d!==shell?.d&&r.a.fill!=="none"
            &&(r.type==="rect"||r.type==="polygon"||/[Zz]/.test(r.d))}).slice(0,6)
            .map(function(r){return {d:r.d,m:r.m,color:r.a.fill}})}
}
function cpu(input) {
    if(Cpu.key(input))return Cpu.paths(input.cpu_package)
    const style=Object.prototype.hasOwnProperty.call(Parts.cpuPackage,input.style)?input.style:"chip"
    return {package:{d:Parts.cpuPackage[style],m:[1,0,0,1,0,0]},
            lid:{d:Parts.cpuLid[style],m:[1,0,0,1,0,0]},style:style}
}
function memory(input) {
    const s=state(input),c=Board.memoryColors(s,Memory.palette(s)),g=Board.geometry(s,Memory.profile(s))
    const rows=Notebook.sourceShapes(Memory.board(g,c)),covers=Notebook.sourceShapes(Memory.enclosure(s,g,c))
    return {pcb:shape(rows[0]),covers:covers.map(shape),
        short_form:s.style==="sodimm",diffuser:c.diffuser===true||c.memoryRgbCover===true,
        colors:{body:c.body,pcb:c.pcb,glass:c.glass}}
}
function profile(input) {
    if(!input||["cpu","gpu","memory"].indexOf(input.kind)<0)return {}
    return input.kind==="gpu"?gpu(input):input.kind==="cpu"?cpu(input):memory(input)
}
