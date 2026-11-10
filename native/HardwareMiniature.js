.pragma library
.import "HardwareSolid.js" as Solid
.import "HardwareBoardDesigns.js" as Board

// Original tiny physical objects: a thin upper edge, a right-side thickness and
// one fixed polygon shadow. Fan faces remain circles; no SVG filters, skewed
// fans, animation, extra textures or mutable render state. Shared helpers keep
// the same verified cooler-family identity in the two selectable treatments.

function palette(state) {
    const colors=Solid.palette(state)
    colors.caseTop="#d2dee7"
    colors.caseBody="#8195a5"
    colors.caseShade="#526b7e"
    colors.side="#3d566c"
    colors.rim="#cfdae2"
    colors.disk="#263846"
    colors.blade="#9fb5c4"
    colors.metal="#c7d4de"
    colors.pcb="#557571"
    colors.edge="#edf2f5"
    return colors
}

function shadow(g, depth) {
    const x=g.x,y=g.y,b=y+g.h,e=x+g.w
    const dx=.20+depth*.35,dy=.22+depth*.20
    return Solid.p("M"+(x+.25)+" "+(b+.16)+"L"+(e+dx)+" "+(b+.04)
        +"L"+(e+dx+.18)+" "+(b+dy)+"L"+(x+.60)+" "+(b+dy+.16)+"Z", "#182735", .09)
}

function fan(cx, cy, radius, colors) {
    return Solid.fan(cx,cy,radius,colors)
}

function cpu(state, colors) {
    if(state.style==="lga_rect") {
        return Solid.r(6.3,5.0,12.3,16.2,1.1,"#263e45")
            +Solid.p("M5.5 4.9L6.4 3.6H18.7L17.8 4.9Z",colors.caseTop)
            +Solid.r(5.5,4.7,12.3,15.5,1.0,colors.pcb)
            +Solid.p("M7 5.4L8.05 4.05H17.25L16.2 5.4Z",colors.caseTop)
            +Solid.p("M16.2 5.4L17.25 4.05V17.6L16.2 18.95Z",colors.caseShade)
            +Solid.r(7.0,5.4,9.2,13.55,.7,colors.metal)
            +Solid.p("M7.65 5.9H15.6","none",.9,colors.edge,.55)
            +Solid.p("M9.2 11.4H13.7M9.2 12.8H12.1","none",.43,colors.caseShade,.45)
            +Solid.r(5.8,6.5,.6,1.1,.1,colors.gold)
            +Solid.r(5.8,17.7,.65,1.3,.15,colors.accent)
    }
    if(state.style==="am5") {
        return Solid.r(4.9,5.1,15.0,15.0,1.1,"#263e45")
            +Solid.p("M4.5 5.2L5.3 4.3H19.3L18.5 5.2Z",colors.caseTop)
            +Solid.r(4.5,4.8,14.8,14.8,1.0,colors.pcb)
            +'<g transform="translate(.9 1.15)">'+Solid.p(Solid.am5Lid(),colors.caseShade)+'</g>'
            +Solid.p(Solid.am5Lid(),colors.metal,1,colors.rim,.25)
            +Solid.p("M7.2 5.9H8.4M10.8 5.9H13.2M15.7 5.9H16.8","none",.9,colors.edge,.45)
            +Solid.p("M9.1 11.2H13.9M9.1 12.5H12.4","none",.38,colors.caseShade,.4)
            +Solid.r(17.9,4.8,1.0,.65,.1,colors.accent)
    }
    let pins=""
    for(let index=0;index<4;index++) {
        const at=7.1+3.25*index
        pins+="M"+at+" 3.6V5.5M"+at+" 18.5V20.6M3.5 "+at+"H5.4M18.6 "+at+"H20.7"
    }
    return Solid.p(pins,"none",1,colors.caseShade,1.2)
        +Solid.r(5.4,5.7,14,14,1.4,colors.side)
        +Solid.p("M5 6L5.9 5H18.7L17.8 6Z",colors.caseTop)
        +Solid.r(5,5.6,13.6,13.2,1.4,colors.caseBody)
        +Solid.r(7.9,8.5,9.2,8.9,.9,colors.caseShade)
        +Solid.p("M7 7.3L7.9 6.1H17.1L16.2 7.3Z",colors.caseTop)
        +Solid.r(7.0,7.3,9.2,8.9,.9,colors.metal)
        +Solid.p("M7.6 7.8H15.5","none",.8,colors.edge,.55)
        +Solid.r(6.1,17.2,2.6,.6,.2,colors.accent)
}

function integrated(colors) {
    return Solid.r(6,6.2,12.4,12.4,1.2,colors.side)
        +Solid.p("M5.5 6.5L6.3 5.5H18.5L17.7 6.5Z",colors.caseTop)
        +Solid.r(5.5,6,12.3,12.0,1.2,colors.pcb)
        +Solid.r(8.5,9.1,7.8,7.6,.8,colors.caseShade)
        +Solid.p("M7.7 8L8.5 6.9H16.3L15.5 8Z",colors.caseTop)
        +Solid.r(7.7,8.0,7.8,7.6,.8,colors.metal)
        +Solid.p("M8.2 8.5H14.8","none",.85,colors.edge,.5)
        +Solid.r(6.2,16.6,2.1,.6,.15,colors.accent)
}

function gpu(state, colors) {
    if(state.style==="gpu_integrated")return integrated(colors)
    const g=Solid.geometry(state)
    // Front stays parallel to the image plane so every physical fan stays round.
    // Thickness is expressed by separate top/right planes, not by distorting it.
    g.x-=.8
    g.centers=g.centers.map(function(value){return value-.8})
    g.y+=.75
    g.h-=.3
    if(g.fan_y)g.fan_y=g.fan_y.map(function(value){return value+.75-.3*.51})
    const x=g.x,y=g.y,e=x+g.w,b=y+g.h
    const depth=Board.depth(state,g)
    const rise=depth*.56
    let result=shadow(g,depth)+Board.base(state,g,colors)
        +Solid.p("M"+(x+.7)+" "+(y+.06)+"L"+(x+.7+depth)+" "+(y-rise)+"H"+(e+depth)+"L"+e+" "+(y+.06)+"Z",colors.caseTop)
        +Solid.p("M"+(e-.08)+" "+(y+.16)+"L"+(e+depth)+" "+(y-rise)+"V"+(b-rise-.08)+"L"+(e-.08)+" "+(b-.03)+"Z",colors.side)
        +Solid.underlay(state,g,colors)+Solid.front(state,g,colors)
    result+=Solid.p("M"+(x+.7+depth)+" "+(y-rise+.10)+"H"+(e+depth-.35),"none",.50,colors.edge,.12)
    const cy=y+g.h*.51
    if(state.style==="gpu_blower"&&state.fan_count===1) {
        result+=Solid.turbine(g.centers.length?g.centers[0]:e-4.5,cy,Math.min(3.5,g.h*.37),colors)
        if(!(state.model_id==="nvidia-gtx1080-founders"&&state.series_id==="nvidia_founders_pascal"))
            result+=Solid.p("M"+(x+2)+" "+(y+2.3)+"H"+(x+7.5)+"M"+(x+2)+" "+(y+4)+"H"+(x+7.5)
                +"M"+(x+2)+" "+(y+5.7)+"H"+(x+7.5),"none",.8,colors.side,.8)
    } else if(g.centers.length) {
        g.centers.forEach(function(cx,index){result+=(g.blowers && g.blowers.indexOf(index)>=0?Solid.turbine:fan)(cx,g.fan_y?g.fan_y[index]:cy,(g.radii?g.radii[index]:g.radius)*.97,colors)})
    } else if (state.fan_count !== 0) {
        // A neutral backplate with a beveled inset and diagonal vent slots.
        // Neither an unverified series nor a missing count creates fan circles.
        result+=Solid.p("M"+(x+2.1)+" "+(y+2.0)+"H"+(e-3.5)+"L"+(e-1.9)+" "+(y+3.6)
            +"V"+(b-2.0)+"H"+(x+2.1)+"Z",colors.side,.43)
        result+=Solid.p("M"+(x+4.0)+" "+(y+3.0)+"L"+(x+3.1)+" "+(y+6.3)
            +"M"+(x+6.1)+" "+(y+3.0)+"L"+(x+5.2)+" "+(y+6.3)
            +"M"+(x+8.2)+" "+(y+3.0)+"L"+(x+7.3)+" "+(y+6.3),"none",.72,colors.caseTop,.8)
    }
    return result+Board.finish(state,g,colors)
}

function body(state, rotorCollector) {
    const normalized=state || ({})
    const colors=normalized.kind==="gpu"?Board.colors(normalized,palette(normalized)):palette(normalized)
    colors.fanDesignSeries=normalized.series_id
    colors.fanDesignIndex=0
    if(Array.isArray(rotorCollector))colors.rotorCollector=rotorCollector
    return normalized.kind==="gpu"?gpu(normalized,colors):cpu(normalized,colors)
}
