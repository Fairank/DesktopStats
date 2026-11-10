"""Original GTX1080 FE surface study from the exact NVIDIA front photograph.

UV topology is shared with HardwareGpuPascal055.js. Relief depths are authored
display references, not measured metal, manufacturing dimensions or a fit claim.
No fan geometry, rotor state, sensor, clock, download or model cache is added.
"""
import hashlib
import json
import math
import struct

IDENTITY='nvidia-gtx1080-founders'
SOURCE='https://images.nvidia.com/aem-dam/Solutions/geforce/news/geforce-gtx-1080-founders-edition/nvidia-geforce-gtx-1080-Front.png'
REFERENCE_SHA256='493f66b6ddcc33a2bc6a052daaa63b40cad9f82d3a0771ecf193bc504ff36f10'
WINDOW_UV=((.14,.21875),(.49,.135417),(.6,.3125),(.6,.739583),(.47,.864583),(.15,.864583))
HEAD_UV=((.2258852258852259,.1397727903958016),(.4706959706959707,.07479578776420266),
         (.2258852258852259,.9298003913043478),(.4706959706959707,.9157532622906636),
         (.6414072039072038,.1826574693422519),(.9295634920634921,.1843297101449275),
         (.6414072039072038,.8348313823857302),(.9295634920634921,.8348313823857302))
# Existing source-art coordinates are retained, including the window corners.
# Third coordinate is relative relief, without claiming a measured height.
POINTS={
 'a':(0.,20.,.35),'b':(6.,2.,0.),'c':(25.,2.,0.),'d':(37.,2.,0.),
 'e':(60.,2.,0.),'f':(68.,13.,.35),'g':(60.,31.25,.6),
 'h':(49.,13.5417,.1),'i':(14.,21.875,.35),'j':(15.,86.4583,.35),
 'k':(47.,86.4583,.1),'l':(60.,98.,0.),'m':(25.,98.,0.),
 'n':(6.,98.,0.),'o':(0.,80.,.35),
 'r':(92.,2.,0.),'s':(100.,19.,.2),'t':(90.,15.,.7),
 'u':(93.,50.,.25),'v':(100.,50.,.35),'w':(100.,81.,.2),
 'x':(89.,75.,.7),'y':(92.,98.,0.),'z':(68.,85.,.35),
 'aa':(66.,27.,.25),'ab':(64.,50.,.8),'ac':(60.,73.9583,.6),
}
FACETS=(
 ('a','b','c','metal'),('a','c','i','shade'),
 ('c','d','h','light'),('c','h','i','metal'),('d','e','h','metal'),
 ('e','f','g','shade'),('e','g','h','light'),
 ('a','i','j','metal'),('a','j','o','metal'),
 ('o','j','m','shade'),('o','m','n','metal'),
 ('j','k','m','light'),('m','k','l','metal'),
 ('r','s','t','light'),('s','v','u','metal'),('s','u','t','shade'),
 ('v','w','u','metal'),('w','x','u','shade'),('w','y','x','light'),
 ('l','z','y','metal'),('z','x','y','shade'),
 ('g','aa','ab','dark'),('g','ab','ac','dark'),
)
VENTS=(((.168,.073),(.195,.068),(.186,.158),(.160,.165)),
       ((.160,.835),(.186,.842),(.195,.932),(.168,.927)))


def descriptor():
    """Bounded static source contract, also emitted in the widget JS helper."""
    return dict(id=IDENTITY,points={key:list(value)for key,value in POINTS.items()},
                facets=[list(row)for row in FACETS],vents=[[list(p)for p in row]for row in VENTS],
                source=SOURCE,source_sha256=REFERENCE_SHA256,depth_measured=False,
                window_uv=[list(p)for p in WINDOW_UV],head_uv=[list(p)for p in HEAD_UV],
                outer_path='M0 20L6 2H92L100 19V81L92 98H6L0 80Z',
                fin_row_samples=13,fin_pitch_measured=False,
                existing_blades=53,rotor_changed=False)


def descriptor_sha256():
    return hashlib.sha256(json.dumps(descriptor(),sort_keys=True,separators=(',',':')).encode()).hexdigest()


def _plane(triangle):
    a,b,c=triangle
    det=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    if not math.isfinite(det)or abs(det)<1e-8:raise ValueError('Degenerate source facet')
    slope_u=((b[2]-a[2])*(c[1]-a[1])-(c[2]-a[2])*(b[1]-a[1]))/det
    slope_v=((b[0]-a[0])*(c[2]-a[2])-(c[0]-a[0])*(b[2]-a[2]))/det
    return slope_u,slope_v,a[2]-slope_u*a[0]-slope_v*a[1]


def _stitched_surface(vertices):
    """Conform clipped plate T junctions before creating the reference relief.

    The new authored surface uses a six-decimal reference grid and the actual
    float32 position domain. Zero-area numerical partitions in that domain
    contribute no surface. No old model, cutout or rotor array is changed.
    """
    def key(p):return struct.unpack('<3f',struct.pack('<3f',*(round(v,6)for v in p)))
    triangles=[tuple(key(vertices[at+n:at+n+3])for n in(0,6,12))for at in range(0,len(vertices),18)]
    points=tuple(dict.fromkeys(p for triangle in triangles for p in triangle))
    output=[]
    def cross(a,b,c):
        u=tuple(b[k]-a[k]for k in range(3));v=tuple(c[k]-a[k]for k in range(3))
        return(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
    def emit(a,b,c):
        normal=cross(a,b,c);length=math.hypot(*normal)
        if length==0.:return
        normal=tuple(v/length for v in normal)
        for p in(a,b,c):output.extend((*p,*normal))
    for triangle in triangles:
        normal=cross(*triangle)
        if math.hypot(*normal)==0.:continue
        drop=max(range(3),key=lambda n:abs(normal[n]));axes=tuple(n for n in range(3)if n!=drop)
        polygon=[]
        for a,b in zip(triangle,(*triangle[1:],triangle[0])):
            delta=tuple(b[k]-a[k]for k in range(3));squared=sum(v*v for v in delta)
            splits=[(0.,a)]
            # This is a precision bound of the already chosen float32 grid,
            # not a widening aperture or a model-dependent visual tolerance.
            magnitude=max(1.,*(abs(v)for p in(a,b)for v in p))
            tolerance=4.*math.ldexp(magnitude,-23)
            for p in points:
                ratio=sum((p[k]-a[k])*delta[k]for k in range(3))/squared
                if not 0.<ratio<1.:continue
                distance=math.hypot(*(p[k]-a[k]-ratio*delta[k]for k in range(3)))
                if distance<=tolerance:splits.append((ratio,p))
            polygon.extend(p for _,p in sorted(splits))
        polygon=list(dict.fromkeys(polygon))
        def turn(a,b,c):return(b[axes[0]]-a[axes[0]])*(c[axes[1]]-a[axes[1]])-(b[axes[1]]-a[axes[1]])*(c[axes[0]]-a[axes[0]])
        orientation=1. if normal[drop]*(1. if drop!=1 else -1.)>0. else -1.
        while len(polygon)>3:
            chosen=None
            for n,b in enumerate(polygon):
                a=polygon[n-1];c=polygon[(n+1)%len(polygon)]
                area=orientation*turn(a,b,c)
                if area<=0.:continue
                if any(all(orientation*turn(x,y,p)>=0. for x,y in((a,b),(b,c),(c,a)))
                       for j,p in enumerate(polygon)if j not in(n,(n-1)%len(polygon),(n+1)%len(polygon))):continue
                if chosen is None or area>chosen[0]:chosen=(area,n,a,b,c)
            if chosen is None:raise ValueError('Source plate boundary cannot be conformed')
            _,n,a,b,c=chosen;emit(a,b,c);polygon.pop(n)
        if len(polygon)==3:emit(*polygon)
    if len(output)//18>8192:raise ValueError('Source facet stitching exceeded its existing geometry budget')
    return tuple(output)


def _closed_source_plate(vertices):
    """Re-extrude the conformed real cap boundary, including all apertures."""
    cap=tuple(value for at in range(0,len(vertices),18)if vertices[at+5]>.999
              for value in vertices[at:at+18])
    cap=_stitched_surface(cap)
    boundary={};output=[]
    def emit(a,b,c):
        u=tuple(b[k]-a[k]for k in range(3));v=tuple(c[k]-a[k]for k in range(3))
        normal=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        length=math.hypot(*normal)
        if length==0.:return
        normal=tuple(value/length for value in normal)
        for p in(a,b,c):output.extend((*p,*normal))
    bottom=lambda p:(p[0],p[1],-p[2])
    for at in range(0,len(cap),18):
        a,b,c=(tuple(cap[at+n:at+n+3])for n in(0,6,12))
        emit(a,b,c);emit(bottom(c),bottom(b),bottom(a))
        for first,last in((a,b),(b,c),(c,a)):
            key=tuple(sorted((first,last)))
            boundary.setdefault(key,[]).append((first,last))
    for rows in boundary.values():
        if len(rows)==2:
            if rows[0]!=tuple(reversed(rows[1])):raise ValueError('Source cap has overlapping winding')
            continue
        if len(rows)!=1:raise ValueError('Source cap is not a bounded surface')
        a,b=rows[0];aa,bb=bottom(a),bottom(b)
        emit(aa,bb,b);emit(aa,b,a)
    if len(output)//18>8192:raise ValueError('Closed source facet exceeded its existing geometry budget')
    return tuple(output)


def relief_meshes(shell,reference,level):
    """Closed clipped source facets, independently retained from the rotor."""
    from assembly_geometry import Mesh,color,gpu_plane
    from assembly_gpu_panels051 import partition
    width,thickness,length=tuple(max(shell.vertices[k::6])-min(shell.vertices[k::6])for k in range(3))
    if not all(math.isfinite(value)and value>0 for value in(width,thickness,length)):return (),{}
    holes=tuple(reference['fan_holes'])+tuple(reference['paint_head_seats'])
    vents=tuple(tuple(((u-.5)*length,(.5-v)*width)for u,v in polygon)for polygon in VENTS)
    cutouts=(reference['window_outline'],*vents)
    segments=12 if level=='eco'else 28 if level=='close'else 20
    colors={'metal':'#aeb9c1','light':'#d7dde0','shade':'#77858e','dark':'#343f47'}
    values=[];triangles=0
    depth=.16
    for index,row in enumerate(FACETS):
        triangle=tuple(POINTS[key]for key in row[:3]);a,b,c=_plane(triangle)
        polygon=tuple(((u/100.-.5)*length,(.5-v/100.)*width)for u,v,_ in triangle)
        source,metadata=partition((polygon,),holes,depth,segments=segments,front_cutouts=cutouts)
        if not source[0]or metadata['omitted_source_paint']:
            raise ValueError('A source facet could not be retained')
        # An affine shear keeps each clipped closed plate closed. Its normal
        # changes by inverse transpose; source rotor/shading arrays are untouched.
        slope_x=.7*a*100./length;slope_y=-.7*b*100./width
        stitched=_closed_source_plate(source[0]);transformed=[]
        for at in range(0,len(stitched),6):
            x,y,z,nx,ny,nz=stitched[at:at+6]
            u=(x/length+.5)*100.;v=(.5-y/width)*100.
            height=.18+.7*(a*u+b*v+c)
            normal=(nx-slope_x*nz,ny-slope_y*nz,nz)
            norm=math.hypot(*normal)
            transformed.extend((x,y,z+height,*(value/norm for value in normal)))
        triangles+=len(transformed)//18
        if triangles>8192:raise ValueError('Pascal relief exceeded its total existing reference budget')
        values.append(Mesh('detail-gpu-pascal-relief055-'+str(index),gpu_plane(tuple(transformed)),
            color(colors[row[3]]),(shell.position[0],shell.position[1]-thickness/2,shell.position[2]),
            'gpu',part_id=shell.part_id or 'gpu:0'))
    return tuple(values),dict(front_relief_source=SOURCE,front_relief_descriptor_sha256=descriptor_sha256(),
        front_relief_facets=len(FACETS),front_relief_triangles=triangles,front_relief_total_triangle_limit=8192,
        front_relief_closed_source_plates=True,front_vent_notches=2,
        relief_depth_accuracy='authored_photo_reference_not_measured',relief_center_offset_mm_reference=(.18,.74),
        relief_plate_thickness_mm_reference=.16,
        front_relief_conforming_reference_grid=True,
        front_relief_no_new_rotor=True,front_relief_no_hidden_pcb=True,front_relief_manufacturer_CAD=False)
