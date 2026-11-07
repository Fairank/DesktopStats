"""Bounded original illustration treatments for the same physical 3D meshes.

Colors, retained crease ink and draw materials change. Dimensions, model silhouettes, fan
axes and tachometer data do not. No I/O, random state, images or animation.
"""
from dataclasses import replace
import math

from top_bar_config import HARDWARE_ICON_STYLES

MAX_STYLE_EDGES = 8192
MAX_MESH_EDGES = 512
MAX_GRILLE_EDGES = 4096
_PAPER = ("notebook_color", "notebook_line", "notebook_smile")
_LINE = ("outline", "notebook_line", "sketch")
_EXPRESSIVE = ("cartoon", "notebook_smile")


def rgba(value, alpha=1.):
    return tuple(int(value[n:n+2],16)/255. for n in (1,3,5))+(alpha,)


def resolve_style(value):
    return value if isinstance(value,str) and value in HARDWARE_ICON_STYLES else "miniature"


def style_for(value):
    """Detached draw policy; callers may cache it for one selected scene."""
    style=resolve_style(value)
    inks={"cartoon":"#455a64","notebook_color":"#496570","notebook_line":"#425f6c",
          "sticker":"#415d60","papercut":"#2b485a","inkwash":"#3b5874",
          "classic":"#526373","outline":"#405b6a","soft":"#748994",
          "sketch":"#61727d","notebook_smile":"#5d6576"}
    return dict(id=style,edges=style!="miniature",
        hardware_ink_only=style in ("solid","papercut"),
        ink=rgba(inks.get(style,"#46525e")),dark_ink=rgba("#c5dce4"),
        shading=1. if style=="miniature" else .45 if style in ("soft","inkwash") else 0.,
        line_only=style in _LINE,paper_grid=style in _PAPER,
        wobble=1.1 if style in _PAPER else 1.35 if style=="sketch" else 0.,
        line_width=1.6 if style in _LINE else 1.2,
        light_background=rgba("#f9f7ed" if style in _PAPER else "#fcf3e2" if style=="sticker"
                              else "#eee5d6" if style=="papercut" else "#edf3f5" if style=="inkwash"
                              else "#eff4f6"),
        dark_background=rgba("#182a35" if style in _PAPER else "#1b2530"),
        grid_light=rgba("#8db7c6"),grid_dark=rgba("#749bab"),
        contact_shadow=0. if style in _LINE else .20 if style=='miniature' else .12,
        expressions=style in _EXPRESSIVE)


def material_for(mesh,style):
    """Static roughness/reflectance classification, cached when the VBO is built."""
    if style not in ('miniature','solid'):
        return (0.,1.,1. if mesh.color[3]<.999 else 0.,0.)
    name=mesh.name.casefold();component=mesh.component
    if mesh.color[3]<.999:return (.08,.10,1.,0.)
    wood_slat=(name=='front-slat' and component=='case' and mesh.color[0]>mesh.color[1]>mesh.color[2]
               and mesh.color[0]-mesh.color[2]>.15)
    if 'wood' in name or wood_slat:return (0.,.88,0.,2.)
    if 'pcb' in name or 'motherboard' in name:return (.02,.82,0.,0.)
    if any(value in name for value in ('screw','heatsink','lid','bracket','metal','contact','fin','heatpipe','coldplate','fitting')):
        return (.82,.25,0.,1.)
    if component=='cpu':return (.65,.31,0.,1.)
    if component=='memory':return (.38,.42,0.,0.)
    return (.23,.48,0.,1. if component=='case' else 0.)


def _mix(a,b,t):return tuple(x*(1-t)+y*t for x,y in zip(a,b))


def _tone(rgb,low,mid,high):
    light=sum(c*v for c,v in zip(rgb,(.2126,.7152,.0722)))
    return rgba(low if light<.37 else mid if light<.72 else high)[:3]


def paint_color(source,style,component="case"):
    """Palette changes express the chosen artwork, never factory paint claims."""
    if style=="miniature":return source
    rgb,alpha=source[:3],source[3]
    if style in _LINE:return (1.,1.,1.,alpha)
    if component=='cables':return _mix(rgb,rgba('#f3e9d7')[:3],.20)+(alpha,)
    if style=="papercut":target=_tone(rgb,"#29485c","#d39978","#f3dfbd")
    elif style=="sticker":target=_tone(rgb,"#789b9b","#bdd4c3","#fff4df")
    elif style=="inkwash":target=_tone(rgb,"#5d879e","#79a8af","#abc5cd")
    elif style=="soft":target=_mix(rgb,rgba("#dce3e5")[:3],.62)
    elif style in ("cartoon","notebook_color","notebook_smile"):
        palettes={"case":("#789ba9","#a5cbd2","#e6e4c9"),
                  "panel":("#99c7d0","#bddde1","#ebf0dc"),
                  "gpu":("#738aa9","#b7c7de","#f0d1bc"),
                  "cpu":("#b08d87","#dfbd9a","#f5e4c0"),
                  "memory":("#6f998f","#abd0ba","#e4edbe"),
                  "board":("#78998b","#b3c8b1","#e8e6bc"),
                  "cooler":("#698a9c","#aacbd1","#ebe5ce"),
                  "fans":("#6d9890","#b2d3c8","#eee2c4"),
                  "psu":("#6f7f93","#b3bdcf","#e8dfcc"),
                  "storage":("#7f9185","#bed1b2","#eee5c7"),
                  "expansion":("#829184","#c7cfad","#f0e3bf")}
        target=_tone(rgb,*palettes.get(component,palettes["case"]))
        if style=="notebook_color":target=_mix(target,rgba("#f5e9d3")[:3],.15)
        elif style=="notebook_smile":target=_mix(target,rgba("#ecc9cb")[:3],.22)
    elif style=="solid":target=_tone(rgb,"#304e63","#7295aa","#d2e0e7")
    else:target=_mix(rgb,rgba("#8b9ead")[:3],.22)
    # Glass remains glass; a line-only treatment can still see internal shapes.
    return tuple(target)+(alpha,)


def apply_colors(meshes,style):
    style=resolve_style(style)
    if style=="miniature":return tuple(meshes)
    values=[]
    for mesh in meshes:
        tone=paint_color(mesh.color,style,mesh.component)
        if mesh.rotor and style in ('papercut','solid'):
            tone=rgba('#f3dfbd' if style=='papercut' else '#bdd5e2',mesh.color[3])
        elif mesh.name=='gpu-fan-hub' and style=='papercut':tone=rgba('#d39978',mesh.color[3])
        values.append(replace(mesh,color=tone))
    return tuple(values)


def apply_model_styles(meshes,style,overrides,dimensions,panels):
    """Independent per-part treatments share geometry, one bounded draw system."""
    default=resolve_style(style);overrides=overrides if isinstance(overrides,dict) else {}
    values=[];styles=[];part_map={}
    case_style=resolve_style(overrides.get('case',default))
    for mesh in meshes:
        if mesh.name.startswith('style-'):continue
        family='case' if mesh.component=='panel' else mesh.component
        part=getattr(mesh,'part_id','')
        selected=resolve_style(overrides.get(part,overrides.get(family,default)))
        values.extend(apply_colors((mesh,),selected));styles.append(selected)
        part_map.setdefault(family,resolve_style(overrides.get(family,default)))
        if part:part_map[part]=selected
    policy=style_for(case_style)
    if policy['expressions'] and panels.get('front')!='open':
        from assembly_geometry import Mesh
        values.append(Mesh('style-case-expression',expression_vertices(dimensions),policy['ink']))
        styles.append(case_style)
    return tuple(values),dict(visual_style=default,canvas_style=case_style,mesh_style_ids=tuple(styles),
        part_style_map=part_map,decorative_expression=any(mesh.name=='style-case-expression' for mesh in values))


def expression_vertices(dimensions):
    """A tiny optional decorative case expression, kept separate from hardware."""
    w,h,d=dimensions;out=[];scale=min(w*.065,h*.035,16.);cx=0.;cy=h*.22;z=d/2+4.
    def tri(a,b,c):
        for x,y in (a,b,c):out.extend((x,y,z,0.,0.,1.))
    for x in (-scale*.60,scale*.60):
        for n in range(10):
            a,b=n*math.tau/10,(n+1)*math.tau/10;r=scale*.14
            tri((cx+x,cy),(cx+x+math.cos(a)*r,cy+math.sin(a)*r),
                (cx+x+math.cos(b)*r,cy+math.sin(b)*r))
    points=[(cx+scale*.65*math.cos(math.pi+n*math.pi/12),cy-scale*.13+scale*.55*math.sin(math.pi+n*math.pi/12)) for n in range(13)]
    for a,b in zip(points,points[1:]):
        dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy);nx,ny=-dy/length*scale*.07,dx/length*scale*.07
        p,q=(a[0]+nx,a[1]+ny),(a[0]-nx,a[1]-ny)
        r,s=(b[0]-nx,b[1]-ny),(b[0]+nx,b[1]+ny)
        tri(p,q,r);tri(p,r,s)
    return tuple(out)


def _key(point):return tuple(round(v,5) for v in point)


def _edge_groups(edges):
    """Deterministic connected contours, retaining only existing surface edges."""
    touching={}
    for index,edge in enumerate(edges):
        for point in edge:touching.setdefault(point,[]).append(index)
    seen=set();groups=[]
    for first in range(len(edges)):
        if first in seen:continue
        pending=[first];seen.add(first);indices=[];low=list(edges[first][0]);high=low.copy()
        while pending:
            index=pending.pop();indices.append(index)
            for point in edges[index]:
                for axis,value in enumerate(point):
                    low[axis]=min(low[axis],value);high[axis]=max(high[axis],value)
                for neighbor in touching[point]:
                    if neighbor not in seen:seen.add(neighbor);pending.append(neighbor)
        groups.append((tuple(sorted(indices)),max(b-a for a,b in zip(low,high))))
    return groups


def _individual_sample(edges,limit):
    prominent=sorted(range(len(edges)),key=lambda n:(-math.dist(*edges[n]),n))[:max(1,limit//4)]
    chosen=set(prominent);others=[n for n in range(len(edges)) if n not in chosen]
    count=limit-len(chosen)
    chosen.update(others[n*len(others)//count] for n in range(count))
    return tuple(edge for n,edge in enumerate(edges) if n in chosen)


def _stitch_boundaries(candidates,edge_normals,vertices):
    """Cancel coplanar T-junctions before spending ink on a clipped plate.

    A long triangle edge may meet several shorter ones. Exact endpoint keys
    alone call all of those boundaries; interval coverage restores the actual
    crease. Endpoints remain existing vertices and only collinear runs merge.
    """
    wanted={point for edge in candidates for point in edge};positions={}
    for start in range(0,len(vertices),6):
        point=tuple(vertices[start:start+3]);key=_key(point)
        if key in wanted and key not in positions:positions[key]=point
    lines={}
    for edge in candidates:
        p,q=(positions[point] for point in edge);delta=tuple(b-a for a,b in zip(p,q));length=math.sqrt(sum(v*v for v in delta))
        if length<1e-8:continue
        direction=tuple(v/length for v in delta)
        if next(v for v in direction if abs(v)>1e-10)<0:direction=tuple(-v for v in direction)
        distance=sum(a*b for a,b in zip(p,direction));origin=tuple(p[n]-distance*direction[n] for n in range(3))
        key=tuple(round(v,7) for v in direction)+tuple(round(v,5) for v in origin)
        item=lines.setdefault(key,[direction,{},{}]);axis,events,points=item
        ends=sorted((round(sum(a*b for a,b in zip(point,axis)),6),original) for point,original in zip((p,q),edge))
        if ends[0][0]==ends[1][0]:continue
        for (value,point),sign in zip(ends,(1,-1)):
            points.setdefault(value,point)
            for normal in edge_normals[edge]:events.setdefault(value,[]).append((normal,sign))
    threshold=math.cos(math.radians(35.));result=[];seen=set()
    for axis,events,points in lines.values():
        active={};values=sorted(events);begin=end=None
        for i,value in enumerate(values):
            for normal,sign in events[value]:
                count=active.get(normal,0)+sign
                if count:active[normal]=count
                else:active.pop(normal,None)
            keep=False
            if i+1<len(values) and active:
                normals=tuple(active);first=normals[0]
                keep=(sum(active.values())==1 or any(sum(a*b for a,b in zip(first,n))<threshold for n in normals[1:]))
            if keep:
                if begin is None:begin=points[value]
                end=points[values[i+1]]
            elif begin is not None:
                edge=(begin,end) if begin<end else (end,begin)
                if begin!=end and edge not in seen:result.append(edge);seen.add(edge)
                begin=end=None
    return result


def _contour_sample(edges,limit):
    groups=_edge_groups(edges)
    # One very complex joined shell retains the established bounded fallback.
    # Separate blades, hub circles and perforations can instead remain whole.
    if max(len(indices) for indices,_ in groups)>limit:return _individual_sample(edges,limit)
    span=max(value for _,value in groups);threshold=max(span*.14,min(12.,span*.30))
    chosen=set()
    for indices,size in sorted(groups,key=lambda group:(-group[1],group[0][0])):
        if size>=threshold and len(chosen)+len(indices)<=limit:chosen.update(indices)
    remaining=[indices for indices,_ in groups if indices[0] not in chosen]
    # Sample complete small holes across the panel, rather than scattering
    # isolated segments. This changes ink density, never physical geometry.
    room=limit-len(chosen)
    if remaining:
        count=min(len(remaining),room//min(map(len,remaining)))
        order=[n*len(remaining)//count for n in range(count)] if count else []
        for index in order:
            indices=remaining[index]
            if len(indices)<=room:chosen.update(indices);room-=len(indices)
    return tuple(edge for n,edge in enumerate(edges) if n in chosen)


def crease_edges(vertices,limit=MAX_MESH_EDGES,*,repair_partitions=False):
    """Return boundary/crease edges, excluding coplanar triangulation diagonals."""
    if type(limit) is not int or limit<=0:return ()
    limit=min(limit,MAX_STYLE_EDGES);edges={}
    for start in range(0,len(vertices),18):
        row=vertices[start:start+18]
        if len(row)!=18:continue
        points=[tuple(row[n:n+3]) for n in (0,6,12)]
        keyed=[_key(point) for point in points]
        normal=tuple(row[3:6])
        for a,b in ((0,1),(1,2),(2,0)):
            p,q=keyed[a],keyed[b]
            if p==q:continue
            key=(p,q) if p<q else (q,p)
            edges.setdefault(key,[]).append(normal)
    threshold=math.cos(math.radians(35.));result=[]
    for edge,normals in edges.items():
        if len(normals)==1 or any(sum(a*b for a,b in zip(normals[0],n))<threshold for n in normals[1:]):
            result.append(edge)
    if len(result)>limit:
        groups=_edge_groups(result)
        if repair_partitions or max(len(indices) for indices,_ in groups)>limit:
            result=_stitch_boundaries(result,edges,vertices)
    if len(result)>limit:
        result=_contour_sample(result,limit)
    return tuple(result)


def edge_batches(meshes,style,styles=None):
    """Build immutable line vertices once; global cap also bounds hand ink."""
    default=style_for(style)
    if styles is None and not default['edges']:return ()
    candidates=[]
    for index,mesh in enumerate(meshes):
        policy=style_for(styles[index]) if isinstance(styles,(tuple,list)) and index<len(styles) else default
        if not policy['edges']:continue
        if mesh.name.startswith('style-'):continue
        if policy['hardware_ink_only'] and mesh.component in ('case','panel'):continue
        # These sampled physical PSU grilles contain complete repeated Y/slot
        # apertures. Permit bounded preparation candidates while the final
        # whole-scene VBO still obeys the same8192-segment limit.
        contour_limit=(MAX_GRILLE_EDGES if mesh.name=='psu-fan-panel' else
                       MAX_GRILLE_EDGES//2 if mesh.name=='psu-rear-vent-panel' else MAX_MESH_EDGES)
        # A fan's eight front/back corner pads are batched together. Each
        # rounded pad has clipped coplanar partitions, so repair those before
        # sampling rather than silently omitting several complete corners.
        edges=crease_edges(mesh.vertices,contour_limit,
                           repair_partitions=mesh.name.endswith('fan-pads'))
        if edges:candidates.append((mesh,index,edges,policy))
    fine_words=('spring-head','small-smd','small-package','pins','contacts','silkscreen','model-mark',
                'label-rule','fastener','screw','water-channel','stator')
    plans=[]
    for mesh,index,edges,policy in candidates:
        name=mesh.name.casefold();micro=any(word in name for word in fine_words)
        dense=any(word in name for word in ('perforat','grille','vent','mesh','floor-deck','fins','-fin'))
        span=max(max(mesh.vertices[axis::6])-min(mesh.vertices[axis::6]) for axis in range(3))
        structural=(not micro and mesh.component!='cables' and not dense and span>=20 and
                    (mesh.component in ('case','panel','cpu','memory') or any(word in name for word in
                     ('shroud','backplate','pcb','motherboard','frame','rim','rail','tank','housing','shell','load-plate'))))
        costs=tuple(1+int(bool(policy['wobble']) and math.dist(a,b)>12) for a,b in edges)
        ordered=sorted(range(len(edges)),key=lambda n:(-math.dist(*edges[n]),n))
        cap=(len(edges) if len(edges)<=64 else 256 if name=='gpu-shroud' else 128) if structural else 0
        if dense and mesh.component in ('case','panel') and span>=80:cap=32
        desired=set(ordered[:cap])
        if mesh.rotor:
            groups=_edge_groups(edges)
            span=max(value for _,value in groups);threshold=max(span*.14,min(12.,span*.30))
            desired={n for indices,size in groups if size>=threshold for n in indices}
        weight=(.035 if micro else .10 if mesh.component=='cables' else .22 if dense else 2.5 if mesh.rotor else 1.)
        if policy['line_only'] and micro:weight=0.
        plans.append(dict(mesh=mesh,index=index,edges=edges,policy=policy,costs=costs,ordered=ordered,
                          desired=desired,selected=set(),weight=weight))
    reserved=sum(sum(row['costs'][n] for n in row['desired']) for row in plans)
    remaining=MAX_STYLE_EDGES
    if sum(sum(row['costs']) for row in plans)<=MAX_STYLE_EDGES:
        # A single model frequently fits comfortably. Do not thin its already
        # bounded connected contours a second time merely because one material
        # has a lower weight than another.
        for row in plans:row['selected'].update(range(len(row['edges'])))
        remaining=0
    # Keep one trace for every mesh when possible, then close important frames.
    for row in plans:
        n=row['ordered'][0]
        if row['costs'][n]<=remaining:row['selected'].add(n);remaining-=row['costs'][n]
    if reserved<=MAX_STYLE_EDGES*.80:
        for row in plans:
            for n in sorted(row['desired']):
                if n not in row['selected'] and row['costs'][n]<=remaining:
                    row['selected'].add(n);remaining-=row['costs'][n]
    else:
        # On crowded builds retain complete main blade/hub groups when they
        # fit, before using the residual budget for grooves, pins and cables.
        for row in plans:
            if not row['mesh'].rotor:continue
            missing=row['desired']-row['selected'];cost=sum(row['costs'][n] for n in missing)
            if cost<=remaining:row['selected'].update(missing);remaining-=cost
    weighted=sum(sum(cost for n,cost in enumerate(row['costs']) if n not in row['selected'])*row['weight'] for row in plans)
    allowance=remaining
    for row in plans:
        available=[n for n in row['ordered'] if n not in row['selected']]
        share=int(allowance*sum(row['costs'][n] for n in available)*row['weight']/max(1.,weighted))
        # Alternate long contours with distributed arcs; fan rims and blades
        # remain recognizable without tracing every pin or cable strand.
        head=available[:min(len(available),share//4)];taken=set(head)
        rest=[n for n in range(len(row['edges'])) if n not in row['selected'] and n not in taken]
        count=min(len(rest),share)
        spread=[rest[n*len(rest)//count] for n in range(count)] if count else []
        for n in (*head,*spread):
            cost=row['costs'][n]
            if cost<=share and cost<=remaining:
                row['selected'].add(n);share-=cost;remaining-=cost
    output=[];remaining=MAX_STYLE_EDGES
    for row in plans:
        mesh,index,edges,policy=(row[key] for key in ('mesh','index','edges','policy'))
        chosen=[edges[n] for n in sorted(row['selected'])]
        lines=[]
        for a,b in chosen:
            points=(a,b)
            if policy['wobble'] and math.dist(a,b)>12:
                points=(a,tuple((a[k]+b[k])/2 for k in range(3)),b)
            # Keep physical ink on its actual crease. A millimetre-scale 3-D
            # pen displacement can sink through a thin lid and disappear in
            # the depth test. The renderer supplies subpixel view-plane ink
            # variation without modifying the surface or its occlusion mesh.
            # Each selected edge uses at most two segments; enforce the final
            # cap rather than multiplying draw work for hand-drawn variants.
            for p,q in zip(points,points[1:]):
                if remaining<=0:break
                lines.extend((*p,0.,0.,1.,*q,0.,0.,1.));remaining-=1
        if lines:output.append((mesh,tuple(lines)))
    return tuple(output)
