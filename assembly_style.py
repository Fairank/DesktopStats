"""Bounded original illustration treatments for the same physical 3D meshes.

Only colors and static crease ink change. Dimensions, model silhouettes, fan
axes and tachometer data do not. No I/O, random state, images or animation.
"""
from dataclasses import replace
import math

from top_bar_config import HARDWARE_ICON_STYLES

MAX_STYLE_EDGES = 8192
MAX_MESH_EDGES = 512
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
        light_background=rgba("#f9f7ed" if style in _PAPER else "#fcf3e2" if style=="sticker"
                              else "#eee5d6" if style=="papercut" else "#edf3f5" if style=="inkwash"
                              else "#eff4f6"),
        dark_background=rgba("#182a35" if style in _PAPER else "#1b2530"),
        grid_light=rgba("#8db7c6"),grid_dark=rgba("#749bab"),
        expressions=style in _EXPRESSIVE)


def _mix(a,b,t):return tuple(x*(1-t)+y*t for x,y in zip(a,b))


def _tone(rgb,low,mid,high):
    light=sum(c*v for c,v in zip(rgb,(.2126,.7152,.0722)))
    return rgba(low if light<.37 else mid if light<.72 else high)[:3]


def paint_color(source,style,component="case"):
    """Palette changes express the chosen artwork, never factory paint claims."""
    if style=="miniature":return source
    rgb,alpha=source[:3],source[3]
    if style in _LINE:return (1.,1.,1.,alpha)
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
                  "board":("#78998b","#b3c8b1","#e8e6bc")}
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


def crease_edges(vertices,limit=MAX_MESH_EDGES):
    """Return boundary/crease edges, excluding coplanar triangulation diagonals."""
    if type(limit) is not int or limit<=0:return ()
    limit=min(limit,MAX_MESH_EDGES);edges={}
    for start in range(0,len(vertices),18):
        row=vertices[start:start+18]
        if len(row)!=18:continue
        points=[tuple(row[n:n+3]) for n in (0,6,12)]
        normal=tuple(row[3:6])
        for a,b in ((0,1),(1,2),(2,0)):
            p,q=_key(points[a]),_key(points[b])
            if p==q:continue
            key=(p,q) if p<q else (q,p)
            edges.setdefault(key,[]).append(normal)
    threshold=math.cos(math.radians(35.));result=[]
    for edge,normals in edges.items():
        if len(normals)==1 or any(sum(a*b for a,b in zip(normals[0],n))<threshold for n in normals[1:]):
            result.append(edge)
    if len(result)>limit:
        result=[result[n*len(result)//limit] for n in range(limit)]
    return tuple(result)


def _wobble(point,seed,amount):
    if not amount:return point
    x,y,z=point
    return tuple(v+amount*math.sin(x*.071+y*.043+z*.053+seed*.17+axis*2.1)
                 for axis,v in enumerate(point))


def edge_batches(meshes,style):
    """Build immutable line vertices once; global cap also bounds hand ink."""
    policy=style_for(style)
    if not policy['edges']:return ()
    candidates=[]
    for index,mesh in enumerate(meshes):
        if mesh.name.startswith('style-'):continue
        if policy['hardware_ink_only'] and mesh.component not in ('gpu','cpu','memory','board'):continue
        edges=crease_edges(mesh.vertices)
        if edges:candidates.append((mesh,index,edges))
    total=sum(1+(bool(policy['wobble']) and math.dist(a,b)>12)
              for _,_,edges in candidates for a,b in edges)
    factor=min(1.,MAX_STYLE_EDGES/max(1,total))
    output=[];remaining=MAX_STYLE_EDGES
    for mesh,index,edges in candidates:
        count=min(remaining,max(1,int(len(edges)*factor)))
        if count<=0:break
        chosen=edges if count>=len(edges) else tuple(edges[n*len(edges)//count] for n in range(count))
        lines=[]
        for a,b in chosen:
            points=(a,b)
            if policy['wobble'] and math.dist(a,b)>12:
                points=(a,tuple((a[k]+b[k])/2 for k in range(3)),b)
            jittered=[_wobble(p,index+1,policy['wobble']) for p in points]
            # Each selected edge uses at most two segments; enforce the final
            # cap rather than multiplying draw work for hand-drawn variants.
            for p,q in zip(jittered,jittered[1:]):
                if remaining<=0:break
                lines.extend((*p,0.,0.,1.,*q,0.,0.,1.));remaining-=1
        if lines:output.append((mesh,tuple(lines)))
    return tuple(output)
