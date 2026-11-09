.pragma library
.import "HardwareMemoryShapes.js" as Memory
.import "HardwareBoardDesigns.js" as Board
.import "IconData.js" as Icons

// Retained notebook drawings. Pen bends and pencil strokes are deterministic;
// none of these functions read hardware, create timers or perform frame work.
// The paper grid belongs to the preview surface, never the transparent icon.

var cpuModels = {
    "intel-13700kf": {vendor:"intel",style:"lga_rect",brand:"Intel",mark:"13700KF"},
    "amd-9950x": {vendor:"amd",style:"am5",brand:"RYZEN",mark:"9950X"},
    "amd-7800x3d": {vendor:"amd",style:"am5",brand:"RYZEN",mark:"7800X3D"}
}

function cpuModelKey(input) {
    if(!input || input.kind!=="cpu" || input.confidence!=="model"
            || typeof input.id!=="string" || input.id.length>40)return ""
    var model=Object.prototype.hasOwnProperty.call(cpuModels,input.id)?cpuModels[input.id]:null
    return model && model.style===input.style && model.vendor===input.vendor ? input.id : ""
}
function hex(value,fallback) {
    return typeof value==="string" && /^#[0-9a-fA-F]{6}$/.test(value)?value.toLowerCase():fallback
}
function num(value) {return Number(Number(value).toFixed(4))}
function hash(value) {
    var result=2166136261
    for(var i=0;i<value.length;i++)result=Math.imul(result^value.charCodeAt(i),16777619)
    return result>>>0
}
function palette(state) {
    var ink=hex(state && state.ink,"#455360")
    return {ink:ink,color:state && ['notebook_color','notebook_smile'].indexOf(state.icon_set)>=0,
        smile:state && state.icon_set==="notebook_smile"}
}
function pen(d,c,width,cls,opacity) {
    return '<path'+(cls?' class="'+cls+'"':'')+' d="'+d+'" fill="none" stroke="'+c.ink
        +'" stroke-width="'+(width===undefined?.43:width)+'"'
        +(opacity===undefined?'':' opacity="'+opacity+'"')+'/>'
}
function attributes(text) {
    var out={}
    String(text).replace(/([a-zA-Z_:][\w:.-]*)\s*=\s*"([^"]*)"/g,function(all,name,value){out[name]=value;return all})
    return out
}
function scaleOf(transform) {
    var value=1
    String(transform||"").replace(/scale\(\s*([-+\d.eE]+)(?:[ ,]+([-+\d.eE]+))?\s*\)/g,function(all,x,y){
        value*=Math.sqrt(Math.abs(Number(x)*(y===undefined?Number(x):Number(y))));return all
    })
    return value>0 && Number.isFinite(value)?value:1
}
function rectPath(a) {
    var x=Number(a.x||0),y=Number(a.y||0),w=Number(a.width),h=Number(a.height)
    var r=Math.max(0,Math.min(Number(a.rx||0),w/2,h/2))
    return 'M'+(x+r)+' '+y+'H'+(x+w-r)+'Q'+(x+w)+' '+y+' '+(x+w)+' '+(y+r)
        +'V'+(y+h-r)+'Q'+(x+w)+' '+(y+h)+' '+(x+w-r)+' '+(y+h)
        +'H'+(x+r)+'Q'+x+' '+(y+h)+' '+x+' '+(y+h-r)+'V'+(y+r)+'Q'+x+' '+y+' '+(x+r)+' '+y+'Z'
}
function bendPath(input,seed,amplitude) {
    // Command-aware shallow bows: preserve curves, arc flags and small teeth.
    var tokens=String(input).match(/[a-zA-Z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?/g)
    if(!tokens || tokens.length>4096)return input
    var arities={M:2,L:2,H:1,V:1,C:6,S:4,Q:4,T:2,A:7},at=0,command='',out='',point=[0,0],start=[0,0],index=0
    while(at<tokens.length) {
        if(/^[a-zA-Z]$/.test(tokens[at]))command=tokens[at++]
        var upper=command.toUpperCase(),relative=command!==upper
        if(upper==='Z'){out+='Z';point=start.slice();command='';continue}
        var count=arities[upper],values=[]
        if(!count || at+count>tokens.length)return input
        for(var i=0;i<count;i++) {
            if(/^[a-zA-Z]$/.test(tokens[at]))return input
            var value=Number(tokens[at++]);if(!Number.isFinite(value))return input;values.push(value)
        }
        var end=upper==='H'?[(relative?point[0]:0)+values[0],point[1]]
            :upper==='V'?[point[0],(relative?point[1]:0)+values[0]]
            :[(relative?point[0]:0)+values[count-2],(relative?point[1]:0)+values[count-1]]
        var dx=end[0]-point[0],dy=end[1]-point[1],length=Math.sqrt(dx*dx+dy*dy)
        if(upper==='M'){out+=command+values.join(' ');start=end.slice();command=relative?'l':'L'}
        else if(['L','H','V'].indexOf(upper)>=0 && length>2.0) {
            var bend=((hash(seed+':'+index++)%2001)/1000-1)*amplitude
            out+='Q'+num((point[0]+end[0])/2-dy/length*bend)+' '+num((point[1]+end[1])/2+dx/length*bend)
                +' '+num(end[0])+' '+num(end[1])
        } else out+=command+values.join(' ')
        point=end
    }
    return out
}
function shapes(input) {
    // Flatten only transforms, never fill/opacity state, into independent paths.
    // Source recipes are trusted local exterior drawings, not arbitrary markup.
    var tags=String(input).match(/<g\b[^>]*>|<\/g>|<(?:path|rect|circle|ellipse|line)\b[^>]*\/\s*>/g)||[]
    var groups=[],scales=[1],out=[]
    tags.forEach(function(tag){
        if(tag==='</g>'){groups.pop();scales.pop();return}
        var a=attributes(tag)
        if(/^<g\b/.test(tag)){groups.push(a.transform||'');scales.push(scales[scales.length-1]*scaleOf(a.transform));return}
        var type=/^<(\w+)/.exec(tag)[1]
        if(type==='rect'){a.d=rectPath(a);type='path'}
        if(type==='line'){a.d='M'+a.x1+' '+a.y1+'L'+a.x2+' '+a.y2;type='path'}
        out.push({type:type,a:a,groups:groups.slice(),scale:scales[scales.length-1]*scaleOf(a.transform)})
    })
    return out
}
function wrapShape(item,content) {
    var out='',groups=item.groups.slice()
    if(item.a.transform)groups.push(item.a.transform)
    groups.forEach(function(transform){if(transform)out+='<g transform="'+transform+'">'})
    out+=content
    groups.forEach(function(transform){if(transform)out+='</g>'})
    return out
}
function shapePen(item,c,width,seed,exact,cls) {
    var a=item.a,body=''
    if(item.type==='path')body=pen(exact?a.d:bendPath(a.d,seed,.52/item.scale),c,width/item.scale,cls)
    else if(item.type==='circle')body='<circle'+(cls?' class="'+cls+'"':'')+' cx="'+(a.cx||0)+'" cy="'+(a.cy||0)+'" r="'+a.r+'" fill="none" stroke="'+c.ink+'" stroke-width="'+num(width/item.scale)+'"/>'
    else if(item.type==='ellipse')body='<ellipse cx="'+(a.cx||0)+'" cy="'+(a.cy||0)+'" rx="'+a.rx+'" ry="'+a.ry+'" fill="none" stroke="'+c.ink+'" stroke-width="'+num(width/item.scale)+'"/>'
    return wrapShape(item,body)
}
function clipShape(item) {
    var a=item.a
    return item.type==='path'?wrapShape(item,'<path d="'+a.d+'"/>'):''
}
function pencil(clip,x,y,w,h,color,c,seed) {
    if(!c.color || !clip || w<=0 || h<=0)return ''
    var points=clipPolygon(clip)
    if(points.length<3)return ''
    var out='<g class="notebook-pencil" fill="none" stroke="'+color+'" opacity=".29">'
    // Broad spaced strokes retain transparent gaps instead of a flat paint fill.
    // Qt SVG has no clipPath support. Bake the safe intervals into each stroke
    // instead, sampling its full width so color cannot bridge an AM5 cutout,
    // spreader teeth, a PCB key, or the transparent outside of a slanted case.
    for(var i=0;i<9;i++) {
        var at=x+w*(i+.35)/9,width=w/9*.69,radius=width/2+.24
        var safe=verticalIntervals(points,at-radius)
        for(var k=1;k<=4;k++)safe=intersectionIntervals(safe,verticalIntervals(points,at-radius+radius*2*k/4))
        safe.forEach(function(interval){
            var low=Math.max(y+.32,interval[0]+radius),high=Math.min(y+h-.32,interval[1]-radius)
            if(high-low<.38)return
            out+='<path d="M'+num(at)+' '+num(low)+'Q'+num(at+.12)+' '+num((low+high)/2)
                +' '+num(at+.05)+' '+num(high)+'" stroke-width="'+num(width)+'"/>'
        })
    }
    return out+'</g>'
}
function clipPolygon(input) {
    if(/\btransform\s*=/.test(input))return []
    var match=/\bd="([^"]*)"/.exec(input)
    if(!match)return []
    var tokens=match[1].match(/[a-zA-Z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?/g)||[]
    var arities={M:2,L:2,H:1,V:1,Q:4,C:6},points=[],at=0,command='',p=[0,0],start=[0,0]
    while(at<tokens.length) {
        if(/^[a-zA-Z]$/.test(tokens[at]))command=tokens[at++]
        var upper=command.toUpperCase(),rel=command!==upper,count=arities[upper],v=[]
        if(upper==='Z'){points.push(start.slice());p=start.slice();command='';continue}
        if(!count || at+count>tokens.length)return []
        for(var n=0;n<count;n++){var value=Number(tokens[at++]);if(!Number.isFinite(value))return [];v.push(value)}
        var end=upper==='H'?[(rel?p[0]:0)+v[0],p[1]]:upper==='V'?[p[0],(rel?p[1]:0)+v[0]]
            :[(rel?p[0]:0)+v[count-2],(rel?p[1]:0)+v[count-1]]
        if(upper==='M'){points.push(end);start=end.slice();command=rel?'l':'L'}
        else if(upper==='Q' || upper==='C') {
            var x1=(rel?p[0]:0)+v[0],y1=(rel?p[1]:0)+v[1]
            var x2=upper==='C'?(rel?p[0]:0)+v[2]:0,y2=upper==='C'?(rel?p[1]:0)+v[3]:0
            for(var step=1;step<=12;step++) {
                var t=step/12,u=1-t
                points.push(upper==='Q'?[u*u*p[0]+2*u*t*x1+t*t*end[0],u*u*p[1]+2*u*t*y1+t*t*end[1]]
                    :[u*u*u*p[0]+3*u*u*t*x1+3*u*t*t*x2+t*t*t*end[0],u*u*u*p[1]+3*u*u*t*y1+3*u*t*t*y2+t*t*t*end[1]])
            }
        } else points.push(end)
        p=end
    }
    return points
}
function verticalIntervals(points,x) {
    var crossings=[]
    for(var i=0;i<points.length;i++) {
        var a=points[i],b=points[(i+1)%points.length]
        if((a[0]<=x && b[0]>x)||(b[0]<=x && a[0]>x))crossings.push(a[1]+(x-a[0])*(b[1]-a[1])/(b[0]-a[0]))
    }
    crossings.sort(function(a,b){return a-b})
    var out=[];for(var j=0;j+1<crossings.length;j+=2)out.push([crossings[j],crossings[j+1]])
    return out
}
function intersectionIntervals(a,b) {
    var out=[]
    a.forEach(function(left){b.forEach(function(right){var low=Math.max(left[0],right[0]),high=Math.min(left[1],right[1]);if(low<high)out.push([low,high])})})
    return out
}
function face(cx,cy,c,scale) {
    var s=scale||1
    return '<g class="notebook-smile" transform="translate('+cx+' '+cy+') scale('+s+')">'
        +pen('M-.9-.3l-.02.26M.85-.25l-.03.26',c,.27)
        +pen('M-.65.55Q0 1.25.72.52',c,.24)+'</g>'
}

// Front packages: no outward pins on LGA/AM5, and no invented AM4 side pins.
// AM5 models deliberately share the same physical eight-cutout lid.
var cpuPackage={
    lga_rect:'M5.2 2.55Q11.4 2.15 18.8 2.8Q20.0 2.85 19.8 4.4L19.5 20.6Q19.5 21.9 18.0 21.7L4.9 21.4Q3.8 21.4 4.0 19.9L4.2 4.0Q4.1 2.7 5.2 2.55Z',
    am5:'M3.8 3.0Q11.7 2.55 20.4 3.2Q21.7 3.25 21.5 4.7L21.15 20.2Q21.15 21.65 19.65 21.5L3.75 21.1Q2.35 21.15 2.55 19.55L2.65 4.5Q2.6 3.2 3.8 3Z',
    am4:'M3.8 3.0Q11.8 2.6 20.0 3.15Q21.5 3.25 21.3 4.75L21.05 20.0Q21.05 21.5 19.5 21.35L3.7 21.0Q2.3 21.0 2.5 19.5L2.65 4.5Q2.6 3.1 3.8 3Z',
    chip:'M4.0 3.7Q11.5 3.2 20.1 4.0Q21.0 4.1 20.9 5.4L20.55 19.6Q20.5 21.0 19.0 20.8L3.9 20.4Q2.65 20.4 2.8 18.9L2.95 5.2Q2.9 3.9 4 3.7Z'
}
var cpuLid={
    lga_rect:'M6.6 4.45Q11.7 4.1 17.35 4.6Q18.2 4.6 18.1 5.8L17.8 19.0Q17.9 20.0 16.5 19.9L6.25 19.55Q5.2 19.6 5.3 18.4L5.5 5.8Q5.45 4.6 6.6 4.45Z',
    am5:'M5.5 4.45L7.4 4.4L7.35 6.0L9.2 5.95L9.25 4.35Q12.0 4.2 13.9 4.4L13.85 6.0L15.65 6.0L15.7 4.45L18.95 4.55Q20.0 4.6 19.9 5.9L19.85 8.15L18.25 8.1L18.2 9.95L19.8 10.0L19.7 14.25L18.1 14.2L18.05 16.05L19.65 16.1L19.6 18.2Q19.65 19.6 18.2 19.5L15.5 19.45L15.55 17.8L13.75 17.75L13.7 19.4L9.1 19.3L9.1 17.65L7.3 17.6L7.25 19.25L5.45 19.2Q4.1 19.2 4.2 17.9L4.25 15.85L5.85 15.9L5.9 14.05L4.3 14.0L4.4 9.75L5.95 9.75L6.0 7.95L4.4 7.9L4.5 5.75Q4.5 4.5 5.5 4.45Z',
    am4:'M5.65 4.65Q11.8 4.35 18.65 4.85Q19.7 4.9 19.6 6.2L19.3 18.4Q19.3 19.6 18.0 19.5L5.6 19.2Q4.4 19.25 4.5 17.9L4.7 6Q4.65 4.8 5.65 4.65Z',
    chip:'M7.0 7.0Q12.0 6.7 17.0 7.2L16.85 16.9Q12 17.2 6.9 16.7Z'
}
function cpu(state,c) {
    var style=Object.prototype.hasOwnProperty.call(cpuPackage,state.style)?state.style:'chip'
    var packagePath=cpuPackage[style],lid=cpuLid[style]
    var model=Object.prototype.hasOwnProperty.call(cpuModels,state.model_id)?cpuModels[state.model_id]:null
    if(model && (model.style!==style || model.vendor!==state.vendor))model=null
    var id='cpu-'+style,color=style==='lga_rect'?'#a3c5d4':style==='am5'?'#d9b292':'#adbdac'
    var out=pencil('<path d="'+lid+'"/>',4.5,4.3,15,15.5,color,c,id)
        +pen(packagePath,c,.49,'cpu-package-outline')+pen(lid,c,.38,'cpu-lid-outline')
        +pen(style==='lga_rect'?'M4.8 17.5l.02 2.1M4.9 20.55l.9.02':'M19.95 4l1.0.04',c,.25)
    if(model) {
        // Bounded artwork labels aid recognition; they are not factory laser art.
        out+='<g class="cpu-model-mark" fill="'+c.ink+'" font-family="Segoe Print,Segoe UI,sans-serif" text-anchor="middle">'
            +'<text x="12" y="10.45" font-size="1.65">'+model.brand+'</text>'
            +'<text x="12" y="13.4" font-size="1.48">'+model.mark+'</text></g>'
    } else out+=pen('M9 9.3Q12 8.9 15.1 9.5M9.0 11.3l4.2.1',c,.29)
    if(c.smile)out+=face(12,16.2,c,.87)
    return '<g class="hardware-notebook-cpu" data-package="'+style+'">'+out+'</g>'
}
function memory(state,c) {
    var colors=Board.memoryColors(state,Memory.palette(state)),seed=String(state.model_id||state.series_id||'memory')
    if(state.style!=='dimm' && state.style!=='sodimm')return memoryCategory(c)
    var g=Board.geometry(state,Memory.profile(state)),x=g.x,end=x+g.w,bottom=17.55
    var key=x+g.w*(typeof colors.notchRatio==='number'?colors.notchRatio:.49)
    var half=typeof colors.notchWidthRatio==='number'?g.w*colors.notchWidthRatio/2:.65
    var top=g.shortForm?8.2:9,keyTop=typeof colors.notchDepthRatio==='number'?bottom-(bottom-top)*colors.notchDepthRatio:15.35
    var pcb='M'+(x+.7)+' '+top+'H'+(end-.7)+'Q'+end+' '+top+' '+end+' '+(top+.7)
        +'V11.2H'+(end-.5)+'V12.2H'+end+'V'+bottom+'H'+(key+half)+'V'+keyTop+'H'+(key-half)
        +'V'+bottom+'H'+x+'V12.2H'+(x+.5)+'V11.2H'+x+'V'+(top+.7)+'Q'+x+' '+top+' '+(x+.7)+' '+top+'Z'
    var enclosure=shapes(Memory.enclosure(state,g,colors)),out=''
    var bare=state.shroud==='bare' || (Board.profile(state) && Board.profile(state).heat_spreader===false)
    if(enclosure.length && !bare)out+=pencil(clipShape(enclosure[0]),x,g.top,g.w,16.2-g.top,colors.body,c,seed)
    else out+=pencil('<path d="'+pcb+'"/>',x,top,g.w,7.0,colors.pcb,c,seed+':pcb')
    out+=pen(pcb,c,.28,'notebook-memory-pcb')
    // Contact bars preserve the reviewed key position and opening. The ten
    // short pen ticks are schematic density, never a physical pin-count claim.
    var contact='M'+(x+.45)+' 16.4H'+(key-half)+'M'+(key+half)+' 16.4H'+(end-.45)
    for(var i=1;i<11;i++) {
        var at=x+.45+(g.w-.9)*i/11
        if(Math.abs(at-key)>half+.18)contact+='M'+num(at)+' 16.65v.7'
    }
    out+=pen(contact,c,.17,'notebook-memory-contacts')
    var limit=bare?4:Math.min(state.series_id==='corsair_dominator_platinum'?7:4,enclosure.length)
    for(var n=0;n<limit;n++) {
        var item=enclosure[n],a=item.a
        // Drop tiny bevels/fins. The cover and diffuser silhouette carry the
        // identity; sparse broad source trims remain readable on a 22px bar.
        if(n>0 && a.opacity!==undefined && Number(a.opacity)<.8)continue
        out+=shapePen(item,c,n===0?.46:n===1?.29:.23,seed+':'+n,false,
            n===0?'notebook-memory-enclosure':'notebook-memory-trim')
    }
    if(c.smile && !bare)out+=face(12,12.1,c,.8)
    return '<g class="hardware-notebook-memory" data-form="'+state.style+'">'+out+'</g>'
}
function memoryCategory(c) {
    // A memory-bank category, not an asserted DIMM shape or motherboard key.
    var out=pen('M5 5.6Q11.7 5.15 18.9 5.8L18.7 18.1Q12 18.5 4.9 17.9Z',c,.52)
        +pen('M7.7 8.2l-.05 7.2M11.9 8.0l.1 7.6M16.2 8.4l-.1 7.1',c,.54)
    if(c.color)out=pencil('<path d="M5 5.6H19V18H5Z"/>',5,6,14,12,'#a9c6bd',c,'memory-category')+out
    if(c.smile)out+=face(12,20.2,c,.65)
    return out
}
function semantic(name,c,moving) {
    var out='',clip='',color='#a8c6d0',d=''
    if(name==='memory')return memoryCategory(c)
    if(name==='network') {
        // Network throughput category: two direction arrows, not a guessed NIC.
        d='M7.3 3.5Q6.8 10.7 7.15 20M3.9 16.7L7.15 20L10.25 16.55M16.85 20.4Q17.3 12 16.9 3.8M13.7 7.05L16.9 3.8L20.15 7.2'
        out=pen(d,c,.70);color='#abc4dc'
    } else if(name==='disk') {
        d='M4.4 7.0Q11.5 6.6 19.5 7.2L21.1 12.6L20.8 18.6Q12 19.2 3.1 18.5L3 12.4Z'
        clip='<path d="'+d+'"/>';out=pen(d,c,.54)
            +pen('M3.2 12.6Q12 12.1 20.9 12.8M6.5 15.7l.2.02M9.2 15.7l.2.02',c,.4);color='#b8c9b3'
    } else if(name==='battery') {
        d='M3.1 6.5Q10 6.1 17.8 6.7L17.65 17.9Q10 18.25 3 17.6Z'
        clip='<path d="'+d+'"/>';out=pen(d,c,.57)+pen('M21 9.6l-.05 4.3M5.5 9.1l-.1 6.0',c,.57);color='#b0c79b'
    } else if(name==='power') {
        d='M13.7 2.9L5.7 13.7L11.7 13.9L10.1 21L18.7 9.6L12.9 9.5Z'
        clip='<path d="'+d+'"/>';out=pen(d,c,.64);color='#d8bf88'
    } else if(name==='fan') {
        d='M4.5 3.0Q12 2.7 20.5 3.4L20.2 20.3Q12 21 3.4 20.1L3.1 4.5Q3.1 3.2 4.5 3Z'
        out=pen(d,c,.55)
        if(!moving) {
            for(var angle=0;angle<360;angle+=120)out+='<g transform="rotate('+angle+' 12 12)">'+pen('M11.65 11.55C8.7 9.7 8.4 5.6 11.5 5.5C14.6 5.4 16.6 8.3 13.0 11.6',c,.48)+'</g>'
            out+='<circle cx="12" cy="12" r=".8" fill="none" stroke="'+c.ink+'" stroke-width=".43"/>'
        }
        return out
    } else {
        // Remaining existing semantic symbols retain their established meaning;
        // deterministic pen bows replace long straight segments, not their UI.
        var items=shapes(Icons.fragment(name))
        items.forEach(function(item,index){out+=shapePen(item,c,.62,'semantic:'+name+':'+index,false)})
        if(!out)out=pen('M3 12.2l4.5-.2 2-6.4 4.4 13 2-6.6 5.1.2',c,.65)
    }
    if(clip)out=pencil(clip,3.2,6.5,17,12.0,color,c,'category:'+name)+out
    if(c.smile && ['disk','battery'].indexOf(name)>=0)out+=face(12,10,c,.8)
    return out
}
function body(state,collector) {
    if(!state || ['cpu','memory'].indexOf(state.kind)<0)return ''
    var c=palette(state),out=state.kind==='cpu'?cpu(state,c):memory(state,c)
    return '<g class="hardware-notebook hardware-notebook-parts" stroke-linecap="round" stroke-linejoin="round">'+out+'</g>'
}
function generic(kind,ink,moving,style) {
    var name=typeof kind==='string'?kind:'sensors',c=palette({ink:ink,icon_set:style||'notebook_line'})
    var aliases={board:'grid',storage:'disk',vram:'memory',gpu_mem:'memory',swap:'memory',ram:'memory',freq:'frequency'}
    name=aliases[name]||name
    if(name==='cpu')return body({kind:'cpu',style:'chip',ink:c.ink,icon_set:style})
    return '<g class="hardware-notebook hardware-notebook-category" stroke-linecap="round" stroke-linejoin="round">'
        +semantic(name,c,moving)+'</g>'
}
