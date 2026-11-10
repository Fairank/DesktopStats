"""Original low-poly assembly meshes; pure geometry, no hardware or rendering I/O.

The meshes are scaled illustrations, not manufacturing CAD or a fit guarantee.
Model dimensions/fan metadata must come from the existing reviewed catalog.
Original code/art: PolyForm Noncommercial 1.0.0; third-party rights remain intact.
"""
from dataclasses import dataclass,replace
import math
import struct


@dataclass(frozen=True)
class Mesh:
    name: str
    vertices: tuple
    color: tuple
    position: tuple = (0., 0., 0.)
    component: str = "case"
    rotor: bool = False
    direction: int = 1
    axis: tuple = (0., 0., 1.)
    part_id: str = ""

    @property
    def vertex_count(self):
        return len(self.vertices) // 6


@dataclass(frozen=True)
class Scene:
    meshes: tuple
    dimensions: tuple
    metadata: dict

    @property
    def triangle_count(self):
        return sum(mesh.vertex_count for mesh in self.meshes) // 3


def number(value, default, low, high):
    return float(value) if type(value) in (int, float) and math.isfinite(value) and low <= value <= high else float(default)


def color(value, default="#46525e", alpha=1.):
    text = value if isinstance(value, str) and len(value) == 7 and value[0] == "#" else default
    try:
        return tuple(int(text[i:i+2], 16) / 255. for i in (1, 3, 5)) + (alpha,)
    except ValueError:
        return color(default, "#46525e", alpha)


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _tri(out, a, b, c):
    normal = _cross(tuple(b[i]-a[i] for i in range(3)), tuple(c[i]-a[i] for i in range(3)))
    length = math.sqrt(sum(v*v for v in normal))
    if length < 1e-10:
        return
    normal = tuple(v/length for v in normal)
    for point in (a, b, c):
        out.extend((*point, *normal))


def _quad(out, a, b, c, d):
    _tri(out, a, b, c); _tri(out, a, c, d)


def box(width, height, depth):
    x, y, z = width/2, height/2, depth/2
    out = []
    for face in (
        ((-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)),
        ((x,-y,-z),(-x,-y,-z),(-x,y,-z),(x,y,-z)),
        ((x,-y,z),(x,-y,-z),(x,y,-z),(x,y,z)),
        ((-x,-y,-z),(-x,-y,z),(-x,y,z),(-x,y,-z)),
        ((-x,y,z),(x,y,z),(x,y,-z),(-x,y,-z)),
        ((-x,-y,-z),(x,-y,-z),(x,-y,z),(-x,-y,z)),
    ):
        _quad(out, *face)
    return tuple(out)


def ring(outer, inner=0., depth=1., segments=32):
    """An actual annulus with front/back/sides, oriented along local Z."""
    segments = max(12, min(64, int(segments)))
    outer = max(.01, float(outer)); inner = max(0., min(float(inner), outer-.001))
    out = []
    for index in range(segments):
        a, b = index*math.tau/segments, (index+1)*math.tau/segments
        p = (math.cos(a), math.sin(a)); q = (math.cos(b), math.sin(b))
        o0, o1 = (p[0]*outer,p[1]*outer), (q[0]*outer,q[1]*outer)
        i0, i1 = (p[0]*inner,p[1]*inner), (q[0]*inner,q[1]*inner)
        z = depth/2
        if inner:
            _quad(out, (*i0,z), (*o0,z), (*o1,z), (*i1,z))
            _quad(out, (*i1,-z), (*o1,-z), (*o0,-z), (*i0,-z))
            _quad(out, (*i0,-z), (*i0,z), (*i1,z), (*i1,-z))
        else:
            _tri(out, (0,0,z), (*o0,z), (*o1,z))
            _tri(out, (0,0,-z), (*o1,-z), (*o0,-z))
        _quad(out, (*o0,z), (*o0,-z), (*o1,-z), (*o1,z))
    return tuple(out)


def _area(points):
    return sum(points[i][0]*points[(i+1)%len(points)][1]-points[(i+1)%len(points)][0]*points[i][1] for i in range(len(points))) / 2


def _inside_triangle(p, a, b, c):
    def cross(x,y,z): return (y[0]-x[0])*(z[1]-x[1])-(y[1]-x[1])*(z[0]-x[0])
    return min(cross(a,b,p), cross(b,c,p), cross(c,a,p)) >= -1e-9


def extrude(points, depth):
    """Ear-clipped concave polygon: no center-fan triangles across AM5 notches."""
    polygon = []
    for point in points:
        if not polygon or sum((point[k]-polygon[-1][k])**2 for k in (0,1))>1e-16:polygon.append(point)
    if len(polygon) < 3 or len(polygon) > 1024:
        return ()
    if polygon[0] == polygon[-1]: polygon.pop()
    # Flattened source paths often retain collinear line samples. Removing
    # these does not change the silhouette and keeps concave ear clipping sound.
    for _ in range(len(polygon)):
        found=False
        for i,b in enumerate(polygon):
            a,c=polygon[i-1],polygon[(i+1)%len(polygon)]
            if abs((b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]))<1e-10:
                polygon.pop(i);found=True;break
        if not found or len(polygon)<=3:break
    if _area(polygon) < 0: polygon.reverse()
    indices = list(range(len(polygon))); faces = []
    for _ in range(len(indices)*len(indices)):
        if len(indices) <= 3: break
        found = False
        for j, current in enumerate(indices):
            before, after = indices[j-1], indices[(j+1)%len(indices)]
            a,b,c = polygon[before],polygon[current],polygon[after]
            if (b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]) <= 1e-9: continue
            if any(_inside_triangle(polygon[k],a,b,c) for k in indices if k not in (before,current,after)): continue
            faces.append((a,b,c));indices.pop(j);found=True;break
        if not found:
            return ()
    if len(indices)==3: faces.append(tuple(polygon[i] for i in indices))
    out=[];z=depth/2
    for a,b,c in faces:
        _tri(out,(*a,z),(*b,z),(*c,z));_tri(out,(*c,-z),(*b,-z),(*a,-z))
    for index,a in enumerate(polygon):
        b=polygon[(index+1)%len(polygon)]
        _quad(out,(*a,-z),(*b,-z),(*b,z),(*a,z))
    return tuple(out)


def _point(angle, radius):
    angle=math.radians(angle-90)
    return (math.cos(angle)*radius,math.sin(angle)*radius)


def _bezier(a,b,c,d=None,steps=7):
    points=[]
    for i in range(1,steps+1):
        t=i/steps;u=1-t
        points.append(tuple(u*u*a[k]+2*u*t*b[k]+t*t*c[k] if d is None else
                            u*u*u*a[k]+3*u*u*t*b[k]+3*u*t*t*c[k]+t*t*t*d[k] for k in (0,1)))
    return points


def blade_contour(profile):
    custom=profile.get('foil_profile')
    keys=('sweep_deg','leading','trailing','root')
    bounds=((-35,55),(.05,.5),(.05,.5),(.15,.5))
    if isinstance(custom,dict) and set(custom)==set(keys) and all(type(custom[key]) in (int,float) and math.isfinite(custom[key]) and lo<=custom[key]<=hi for key,(lo,hi) in zip(keys,bounds)):
        return tuple(custom[key] for key in keys)
    variants={'straight':(4,.36,.33,.32),'wide':(48,.46,.35,.28),'paired':(58,.37,.34,.23),'claw':(46,.43,.32,.27)}
    if profile.get('blade_variant')=='dispersion':return (44,.46,.33,.30)
    if profile.get('blade_variant')=='traditional':return (48,.27,.25,.20)
    return variants.get(profile.get('shape'),(52,.35,.30,.24))


def blade_polygon(profile):
    """The same reviewed parametric leading/tip/trailing curves as 2-D fans."""
    count=profile.get('blades');shape=profile.get('shape','neutral')
    if type(count) is not int or not 2<=count<=64 or shape=='neutral': return ()
    pitch=360/count;hub=max(.45,number(profile.get('hub_ratio'),.28,.1,.7)*3*.88)
    if profile.get('kind')=='blower' or shape=='radial':
        a=_point(-pitch*.19,max(1.15,hub));b=_point(-pitch*.39,2.60)
        return tuple([a,b]+_bezier(b,_point(0,2.72),_point(pitch*.30,2.54))+[_point(pitch*.17,max(1.15,hub))])
    sweep,lead,trail,root=blade_contour(profile)
    a=_point(-pitch*root,hub)
    b=_point(-sweep-pitch*lead,2.55)
    c=_point(-sweep+pitch*trail,2.54)
    return tuple([a]+_bezier(a,_point(-sweep*.18-pitch*.18,1.32),_point(-sweep*.85-pitch*(lead+.04),2.12),b)
                 +_bezier(b,_point(-sweep-pitch*.05,2.73),c)
                 +_bezier(c,_point(-sweep*.60+pitch*(trail+.08),2.03),_point(-sweep*.06+pitch*.29,1.23),_point(pitch*root,hub)))


def fan_rotor(profile, radius, depth=1.1):
    count=profile.get('blades');result=[]
    polygons=profile.get('blade_polygons')
    if isinstance(polygons,list) and type(profile.get('blades')) is int and 2<=profile['blades']<=64 and len(polygons)==profile['blades']:
        for polygon in polygons:
            if not isinstance(polygon,list) or not 3<=len(polygon)<=256:continue
            if not all(isinstance(p,(list,tuple)) and len(p)==2 and all(type(v) in (int,float) and math.isfinite(v) and abs(v)<=4 for v in p) for p in polygon):continue
            result.extend(extrude(tuple((x*radius/3,-y*radius/3) for x,y in polygon),depth))
    else:
        base=blade_polygon(profile)
        if not base:return ()
        for index in range(count):
            p=dict(profile)
            if profile.get('blade_pattern')=='alternating' and count%2==0:
                p['blade_variant']='dispersion' if index%2==0 else 'traditional'
            leaf=blade_polygon(p);angle=index*math.tau/count;co,si=math.cos(angle),math.sin(angle)
            points=[((co*x-si*y)*radius/3,(si*x+co*y)*radius/3) for x,y in leaf]
            if profile.get('direction')==-1:points=[(-x,y) for x,y in points]
            points=[(x,-y) for x,y in points]
            result.extend(extrude(points,depth))
    if not result:return ()
    # Exact full outer ring and TORX-style grouped tip links remain 3-D geometry.
    if profile.get('outer_ring') is True:result.extend(ring(radius*2.73/3,radius*2.51/3,depth))
    elif type(profile.get('group_size')) is int and profile['group_size']>1 and count%profile['group_size']==0:
        group=profile['group_size'];pitch=360/count
        for start in range(0,count,group):
            sweep,lead,trail,_=blade_contour(profile)
            a=start*pitch-sweep-lead*pitch;b=(start+group-1)*pitch-sweep+trail*pitch
            for step in range(8):
                aa=math.radians(a+(b-a)*step/8-90);bb=math.radians(a+(b-a)*(step+1)/8-90)
                r0,r1=radius*2.45/3,radius*2.65/3
                points=((math.cos(aa)*r0,math.sin(aa)*r0),(math.cos(bb)*r0,math.sin(bb)*r0),
                        (math.cos(bb)*r1,math.sin(bb)*r1),(math.cos(aa)*r1,math.sin(aa)*r1))
                if profile.get('direction')==-1:points=tuple((-x,y) for x,y in points)
                points=tuple((x,-y) for x,y in points)
                result.extend(extrude(points,depth))
    return tuple(result)


def rotate_vertices(vertices, axis):
    """Rotate local Z-facing mesh to face X-negative or Y-negative."""
    def point(x,y,z):
        if axis=='left':return (-z,y,x)
        if axis=='down':return (x,-z,y)
        return (x,y,z)
    out=[]
    for i in range(0,len(vertices),6):out.extend((*point(*vertices[i:i+3]),*point(*vertices[i+3:i+6])))
    return tuple(out)


def gpu_plane(vertices, rear=False):
    """Source-right runs +Z, source-down runs +X toward the board contacts.

    Source polygons have already changed SVG-down into local Y-up. The rigid
    right-handed transform points the front face to -Y (the card underside).
    """
    out=[]
    for n in range(0,len(vertices),6):
        for start in (0,3):
            x,y,z=vertices[n+start:n+start+3];out.extend((-y,z,-x) if rear else (-y,-z,x))
    return tuple(out)


def memory_plane(vertices):
    """A DIMM stands perpendicular to the board: length Y, height -X."""
    out=[]
    for n in range(0,len(vertices),6):
        for start in (0,3):
            x,y,z=vertices[n+start:n+start+3];out.extend((-y,x,z))
    return tuple(out)


def unit_polygon(value,width,height,margin=.1):
    if not isinstance(value,list) or not 3<=len(value)<=512:return ()
    if not all(isinstance(p,(list,tuple)) and len(p)==2 and all(type(v) in (int,float) and math.isfinite(v) and -margin<=v<=1+margin for v in p) for p in value):return ()
    return tuple(((x-.5)*width,(.5-y)*height) for x,y in value)


_GLYPHS={
    '0':('111','101','101','101','111'),'1':('010','110','010','010','111'),
    '2':('111','001','111','100','111'),'3':('111','001','111','001','111'),
    '4':('101','101','111','001','001'),'5':('111','100','111','001','111'),
    '6':('111','100','111','101','111'),'7':('111','001','010','010','010'),
    '8':('111','101','111','101','111'),'9':('111','101','111','001','111'),
    'I':('111','010','010','010','111'),'N':('1001','1101','1011','1001','1001'),
    'T':('111','010','010','010','010'),'E':('111','100','111','100','111'),
    'L':('100','100','100','100','111'),'R':('110','101','110','101','101'),
    'Y':('101','101','010','010','010'),'Z':('111','001','010','100','111'),
    'X':('101','101','010','101','101'),'D':('110','101','101','101','110'),
    'K':('101','101','110','101','101'),'F':('111','100','110','100','100'),
    'B':('110','101','110','101','110'),
    'A':('010','101','111','101','101'),'C':('011','100','100','100','011'),
    'G':('011','100','101','101','011'),'H':('101','101','111','101','101'),
    'M':('10001','11011','10101','10001','10001'),'O':('010','101','101','101','010'),
    'P':('110','101','110','100','100'),'S':('011','100','010','001','110'),
    'U':('101','101','101','101','111'),'V':('101','101','101','101','010'),
    'W':('10001','10001','10101','11011','10001'),'-':('000','000','111','000','000'),
    'J':('001','001','001','101','010'),'Q':('010','101','101','111','011'),
    ' ':('0','0','0','0','0'),
}


def model_mark(text,pixel=.42):
    """Small original grid lettering, used only for allowlisted CPU model marks."""
    rows=[_GLYPHS.get(c) for c in text]
    if not rows or any(row is None for row in rows):return ()
    total=sum(len(row[0])+1 for row in rows)-1;left=-total*pixel/2;out=[]
    for glyph in rows:
        for y,line in enumerate(glyph):
            for x,filled in enumerate(line):
                if filled!='1':continue
                vertices=box(pixel*.83,pixel*.83,.06)
                for index in range(0,len(vertices),6):
                    out.extend((vertices[index]+left+(x+.5)*pixel,vertices[index+1]+(2-y)*pixel,
                                vertices[index+2],*vertices[index+3:index+6]))
        left+=(len(glyph[0])+1)*pixel
    return tuple(out)


def known_fan_profiles(appearance):
    """Use guarded existing exact-model metadata without reading a device."""
    if not isinstance(appearance,dict) or appearance.get('kind')!='gpu' or appearance.get('confidence')!='model':return []
    from hardware_fan_profiles import PROFILES,profile_for
    from hardware_variants import READY
    from hardware_variant_art import ART
    if not profile_for(appearance):return []
    row=dict(PROFILES.get(appearance.get('series_id'),{}))
    identity=appearance.get('id')
    row.update(READY.get(identity,{}).get('overrides',{}).get('fan_profile',{}))
    row.update(ART.get(identity,{}).get('fan_profile',{}))
    total=appearance.get('visible_fan_count')
    if type(total) is not int:total=appearance.get('fan_count')
    if type(total) is not int or not 0<=total<=3:return []
    fans=[]
    for index in range(total):
        p={k:v for k,v in row.items() if k!='fans'}
        if index<len(row.get('fans',())):p.update(row['fans'][index])
        p['direction']=-1 if p.get('direction')==-1 else 1
        p['kind']='blower' if appearance.get('style')=='gpu_blower' else 'axial'
        fans.append(p)
    return fans


AM5_LID=((-20,-20),(-13,-20),(-13,-16),(-9,-16),(-9,-20),(9,-20),(9,-16),(13,-16),(13,-20),(20,-20),
         (20,-13),(16,-13),(16,-9),(20,-9),(20,9),(16,9),(16,13),(20,13),(20,20),(13,20),
         (13,16),(9,16),(9,20),(-9,20),(-9,16),(-13,16),(-13,20),(-20,20),(-20,13),(-16,13),
         (-16,9),(-20,9),(-20,-9),(-16,-9),(-16,-13),(-20,-13))


def build_scene(spec=None):
    """Build bounded component meshes once per selected case/component identity.

    case uses chassis_catalog record verbatim. gpu.appearance is existing
    appearance_for() output; gpu.fans may supply reviewed layout/profile
    overrides (x_ratio along length, radius_mm, profile). No fan-mount support
    is interpreted as an installed case fan.
    """
    from memory_dimensions052 import enrich as enrich_memory_dimensions
    # Direct/baked callers receive the same exact-model facts as build_spec.
    # This construction-only detached copy never changes the caller's PCB scale.
    spec=dict(spec) if isinstance(spec,dict) else {}
    spec['memory']=enrich_memory_dimensions(spec.get('memory'))
    case=spec.get('case') or {};dims=case.get('dimensions_mm') or {}
    w=number(dims.get('width'),230,60,800);h=number(dims.get('height'),470,60,900);d=number(dims.get('depth'),460,150,900)
    meshes=[];steel=color(case.get('color'),'#4d5965');edge=color('#a9b8c4');dark=color('#25313e');green=color('#2f5960');gold=color('#d7b36d')
    features=case.get('features') or []
    open_frame=case.get('layout')=='open_frame'
    winged=open_frame and 'winged_open_frame' in features
    corner='curved_front_glass' if 'curved_front_glass' in features else 'angular_glass_corner' if 'angular_glass_corner' in features else ''
    cut=min(w*.23,d*.18) if corner else 0.
    def add(name,vertices,tone,position=(0,0,0),component='case',**kw):
        if vertices:meshes.append(Mesh(name,vertices,tone,position,component,**kw))
    def cube(name,size,pos,tone=steel,component='case'):add(name,box(*size),tone,pos,component)
    # Actual case proportions, a light structural frame and removable side.
    rail=max(5.,min(9.,w*.028))
    # BGW67 lists435mm body plus20mm stands,455mm total. Its source body
    # datum must not borrow the generic16mm base inside that external height.
    body_base=20. if case.get('id')=='be-quiet-light-base-600-lx' else 16.
    body_h=h-body_base;body_y=body_base/2;bottom=-h/2+body_base
    for x in (-(w-rail)/2,(w-rail)/2):
        for z in (-(d-rail)/2,(d-rail)/2):
            if (not open_frame and not((corner or 'pillarless_glass_corner' in features)
                    and x<0 and z>0)):
                cube('case-upright',(rail,body_h,rail),(x,body_y,z))
    for y in (bottom+rail/2,h/2-rail/2):
        for z in (-(d-rail)/2,(d-rail)/2):cube('case-width-rail',(w-cut if corner and z>0 else w,rail,rail),(cut/2 if corner and z>0 else 0,y,z))
        for x in (-(w-rail)/2,(w-rail)/2):cube('case-depth-rail',(rail,rail,d-cut if corner and x<0 else d),(x,y,-cut/2 if corner and x<0 else 0))
    if corner:
        footprint=((-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2+cut,d/2),(-w/2,d/2-cut))
        add('case-bottom',rotate_vertices(extrude(footprint,3),'down'),dark,(0,bottom+1.5,0))
    else:cube('case-bottom',(w,3,d),(0,bottom+1.5,0),dark)
    if not open_frame:
        cube('case-back',(w,body_h,2),(0,body_y,-d/2+1),dark)
        cube('case-right',(2,body_h,d),(w/2-1,body_y,0),steel)
    else:
        if winged:
            cube('open-frame-tray',(w*.45,body_h*.86,3),(0,body_y,-d*.10),steel)
            for side in (-1,1):
                for index in range(9):
                    cube('hinged-wing-grid',(w*.22,2,4),(side*w*.37,-h*.36+index*h*.72/8,-d*.07),edge)
                for at in (-.10,.10):cube('hinged-wing-edge',(4,h*.76,6),(side*w*(.37+at),0,-d*.07),steel)
        else:cube('open-frame-tray',(3,body_h*.86,d*.80),(w*.36,body_y,-d*.04),steel)
        for z in (-d*.37,d*.37):
            cube('open-frame-support',(w*.65,rail,rail),(0,-h*.35,z),edge)
    panels=case.get('panels') or {};front=panels.get('front','mesh');left=panels.get('left','glass')
    if open_frame and not winged:front='open'
    glass=color('#9fc2d0',alpha=.13)
    if left in ('glass','angled_glass'):
        cube('left-glass',(2,body_h-rail*2,d-rail*2-cut),(-w/2+1,body_y,-cut/2),glass,'panel')
    elif left=='mesh':
        for i in range(22):cube('left-mesh-vent',(2,2,d-rail*2),(-w/2+1,body_y-body_h*.44+i*body_h*.88/21,0),steel,'panel')
    elif left in ('slotted','vented'):
        for i in range(20):cube('left-side-slat',(2,body_h-rail*2,2),(-w/2+1,body_y,-d*.44+i*d*.88/19),steel,'panel')
    elif left not in ('open',None):cube('left-panel',(2,body_h-rail*2,d-rail*2),(-w/2+1,body_y,0),steel,'panel')
    if front in ('glass','angled_glass'):
        cube('front-glass',(w-rail*2-cut,body_h-rail*2,2),(cut/2,body_y,d/2-1),glass,'panel')
    elif front in ('wood','slotted'):
        for i in range(13):cube('front-slat',(max(3,w/26),body_h-rail*2,5),(-w*.43+i*w*.86/12,body_y,d/2-2.5),color('#b89a77') if front=='wood' else edge)
    elif front=='mesh':
        for i in range(22):cube('front-vent',(w-rail*2,1.5,2),(0,body_y-body_h*.44+i*body_h*.88/21,d/2-1),edge)
    elif front not in ('open',None):cube('front-panel',(w-rail*2,body_h-rail*2,2),(0,body_y,d/2-1),steel)
    if corner=='angular_glass_corner':
        vertices=box(cut*math.sqrt(2),h-rail*2,2);out=[];a=math.sqrt(.5)
        for n in range(0,len(vertices),6):
            for offset in (0,3):
                x,y,z=vertices[n+offset:n+offset+3];out.extend((a*x-a*z,y,a*x+a*z))
        add('angled-corner-glass',tuple(out),glass,(-w/2+cut/2,0,d/2-cut/2),'panel')
        for yy in (bottom+rail/2,h/2-rail/2):
            vertices=box(cut*math.sqrt(2),rail,rail);rail_vertices=[]
            for n in range(0,len(vertices),6):
                for offset in (0,3):
                    x,y,z=vertices[n+offset:n+offset+3];rail_vertices.extend((a*x-a*z,y,a*x+a*z))
            add('angled-corner-rail',tuple(rail_vertices),steel,(-w/2+cut/2,yy,d/2-cut/2))
    elif corner=='curved_front_glass':
        out=[];cx,cz=-w/2+cut,d/2-cut
        for i in range(16):
            a,b=math.pi-i*math.pi/32,math.pi-(i+1)*math.pi/32
            p=(cx+cut*math.cos(a),cz+cut*math.sin(a));q=(cx+cut*math.cos(b),cz+cut*math.sin(b))
            _quad(out,(p[0],-h/2+rail,p[1]),(q[0],-h/2+rail,q[1]),(q[0],h/2-rail,q[1]),(p[0],h/2-rail,p[1]))
        add('curved-corner-glass',tuple(out),glass,component='panel')
        rail_vertices=[]
        for i in range(16):
            a,b=math.pi-i*math.pi/32,math.pi-(i+1)*math.pi/32
            r0,r1=cut-rail,cut
            points=((cx+r0*math.cos(a),cz+r0*math.sin(a)),(cx+r1*math.cos(a),cz+r1*math.sin(a)),
                    (cx+r1*math.cos(b),cz+r1*math.sin(b)),(cx+r0*math.cos(b),cz+r0*math.sin(b)))
            rail_vertices.extend(rotate_vertices(extrude(points,rail),'down'))
        for yy in (bottom+rail/2,h/2-rail/2):add('curved-corner-rail',tuple(rail_vertices),steel,(0,yy,0))
    if 'front_round_display' in features:
        add('front-display-ring',ring(min(w*.15,34),min(w*.13,30),3),edge,(0,h*.18,d/2-3))
        add('front-display-screen',ring(min(w*.13,30),0,2),dark,(0,h*.18,d/2-1))
    if 'front_wood_strip' in features:cube('front-wood-strip',(w*.08,h-rail*2,4),(-w*.32,0,d/2+2),color('#b89a77'))
    if 'external_exoskeleton' in features:
        for x in (-w*.46,w*.46):cube('external-frame-upright',(11,h,14),(x,0,d*.46),edge)
    if 'carry_handle' in features:
        for z in (-d*.13,d*.13):cube('carry-handle-post',(8,14,7),(0,h/2+3,z),edge)
        cube('carry-handle-grip',(10,7,d*.26+7),(0,h/2+10,0),dark)
    if 'fabric_carry_straps' in features:
        # Original eight-section fabric reference, not a separate fastener or
        # a manufacturer strap profile. Both short flat feet rest on the
        # existing depth rails; adjacent solids share their full end section.
        half=(w-rail)/2;arch_half=half-rail/2
        peak=7.+16.*(1.-(.4/(7*.45))**2)+1.5  # Preserve the previous peak.
        sections=[(-half,h/2),*((-arch_half+i*arch_half/3,
            h/2+(peak-3.)*(1.-((-arch_half+i*arch_half/3)/arch_half)**2))
            for i in range(7)),(half,h/2)]
        for at in (-d*.24,d*.24):
            for (xa,ya),(xb,yb) in zip(sections,sections[1:]):
                a,b,c,e=(xa,ya,-9.5),(xb,yb,-9.5),(xb,yb+3.,-9.5),(xa,ya+3.,-9.5)
                f,g,j,k=(xa,ya,9.5),(xb,yb,9.5),(xb,yb+3.,9.5),(xa,ya+3.,9.5)
                vertices=[]
                for face in ((f,g,j,k),(b,a,e,c),(g,b,c,j),(a,f,k,e),(k,j,c,e),(a,b,g,f)):
                    _quad(vertices,*face)
                add('fabric-carry-strap',tuple(vertices),dark,(0.,0.,at))
    if 'side_glass_standoffs' in features:
        for y in (-h*.37,h*.37):
            for z in (-d*.37,d*.37):cube('glass-standoff',(w*.78,7,7),(0,y,z),edge)
    if 'front_wood_frame' in features:
        wood=color('#b49776')
        for x in (-w*.45,w*.45):cube('wood-front-rim',(10,body_h*.92,5),(x,body_y,d/2+1),wood)
        for y in (-h*.44,h*.46):cube('wood-front-rim',(w*.91,9,5),(0,y,d/2+1),wood)
    if 'front_wood_panel' in features:
        cube('wood-front-upper',(w*.90,h*.36,3),(0,h*.22,d/2+1),color('#aa8964'))
    if 'nas_split_chamber' in features:
        cube('nas-chamber-divider',(w-12,3,d-12),(0,-h*.04,0),steel)
        cube('nas-front-seam',(w*.94,2,4),(0,-h*.01,d/2+2),dark)
    if 'front_wood_io_trim' in features:
        cube('wood-io-trim',(w*.12,h*.28,4),(w*.37,h*.29,d/2+2),color('#b49776'))
    if 'side_status_screen' in features:
        cube('side-status-frame',(4,h*.08,d*.23),(-w/2-1,-h*.32,d*.13),edge,'panel')
        cube('side-status-off',(2,h*.065,d*.21),(-w/2-3,-h*.32,d*.13),dark,'panel')
    if 'translucent_base' in features:
        cube('translucent-stand',(w*.94,12,d*.90),(0,-h/2+6,0),color('#b9b0d4',alpha=.30),'panel')
    if 'front_screen' in features:
        cube('front-screen-frame',(w*.77,h*.16,4),(0,h*.27,d/2+1),edge)
        cube('front-screen-off',(w*.73,h*.14,2),(0,h*.27,d/2+3),dark)
    if 'side_bottom_mesh_band' in features:
        for index in range(9):cube('side-lower-mesh',(2,1.3,d*.86),(-w/2-.3,-h*.43+index*h*.018,0),edge,'panel')
    if 'vertical_front_light_strips' in features:
        for x in (-w*.43,w*.43):cube('front-light-strip',(2.5,body_h*.9,2),(x,body_y,d/2+1),color('#9dc9d4'))
    if 'top_bottom_light_strips' in features:
        for y in (-h*.46,h*.46):cube('horizontal-light-strip',(w*.86,2.5,2),(0,y,d/2+1),color('#9dc9d4'))
    if 'front_square_grid' in features:
        for index in range(12):cube('front-grid-column',(1.2,body_h*.9,2),(-w*.43+index*w*.86/11,body_y,d/2+.5),steel)
    if 'front_triangle_grid' in features or 'triangular_front_mesh' in features:
        for side in (-1,1):
            for index in range(7):
                vertices=box(w*.48,1.5,2);out=[];angle=side*math.pi/7;co,si=math.cos(angle),math.sin(angle)
                for n in range(0,len(vertices),6):
                    for offset in (0,3):
                        x,y,z=vertices[n+offset:n+offset+3];out.extend((co*x-si*y,si*x+co*y,z))
                add('front-triangle-line',tuple(out),edge,(side*w*.23,body_y-body_h*.35+index*body_h*.7/6,d/2+1))
    if 'front_diagonal_rails' in features:
        for side in (-1,1):
            vertices=box(w*.43,7,6);out=[];angle=side*math.pi/8;co,si=math.cos(angle),math.sin(angle)
            for n in range(0,len(vertices),6):
                for offset in (0,3):
                    x,y,z=vertices[n+offset:n+offset+3];out.extend((co*x-si*y,si*x+co*y,z))
            add('front-diagonal-rail',tuple(out),edge,(side*w*.23,-h*.20,d/2+2))
    if 'octagonal_front' in features:
        for sign in (-1,1):
            vertices=box(w*.30,7,6);out=[];angle=sign*math.pi/6;co,si=math.cos(angle),math.sin(angle)
            for n in range(0,len(vertices),6):
                for offset in (0,3):
                    x,y,z=vertices[n+offset:n+offset+3];out.extend((co*x-si*y,si*x+co*y,z))
            for yy in (-h*.44,h*.44):add('octagonal-frame',tuple(out),edge,(sign*w*.30,yy,d/2+3))
    # Top vent rails suggest the panel construction, never invented mounted fans.
    if not open_frame:
        top=panels.get('top','mesh')
        if top=='glass':cube('top-glass',(w-rail*2,2,d-rail*2),(0,h/2-1,0),glass,'panel')
        elif top=='solid':cube('top-panel',(w-rail*2,2,d-rail*2),(0,h/2-1,0),steel)
        else:
            for i in range(12):cube('top-vent',(w*.78,1.6,2),(0,h/2-.8,-d*.4+i*d*.8/11),edge)
    for x in (-w*.34,w*.34):
        for z in (-d*.34,d*.34):cube('case-foot',(23,12,30),(x,-h/2+6,z),dark)
    layout=case.get('layout','tower');dual=layout=='dual_chamber';shroud_meta={};helios_front_cover=None
    reference_shroud=False;deferred_shroud=();case_pose={}
    board_x=0 if winged else -h*.12 if 'nas_split_chamber' in features else w*(.10 if dual else .36)
    if dual:
        from assembly_case_shrouds052 import build as build_case_shroud,remove_replaced_parts
        covers,shroud_meta=build_case_shroud(case,(w,h,d),dark)
        reference_shroud=bool(shroud_meta)
        if reference_shroud:
            meshes=remove_replaced_parts(meshes,shroud_meta)
            meshes.extend(covers)
        else:cube('rear-chamber-shroud',(w*.28,h*.23,d*.44),(w*.34,-h*.32,-d*.25),dark)
    elif 'top_psu_shroud' in features:
        from assembly_case_shrouds052 import build as build_case_shroud
        covers,shroud_meta=build_case_shroud(case,(w,h,d),dark)
        reference_shroud=bool(shroud_meta)
        if reference_shroud:
            from assembly_case_shrouds052 import remove_replaced_parts
            meshes=remove_replaced_parts(meshes,shroud_meta)
            meshes.extend(covers)
        else:cube('top-psu-shroud',(w-12,h*.15,d-12),(0,h*.405,0),dark)
    elif layout not in ('compact','horizontal','open_frame'):
        shroud_vertices=()
        if case.get('id')=='asus-rog-strix-helios-gx601':
            from assembly_helios_shroud052 import prepare
            covers,helios_front_cover,shroud_meta=prepare(case,(w,h,d),dark)
            meshes.extend(covers)
        elif case.get('id')=='fractal-north-xl-mesh':
            from assembly_north_tray049 import shroud
            shroud_vertices,shroud_meta=shroud(case,(w,h,d))
        else:
            from assembly_case_shrouds052 import build as build_case_shroud
            covers,shroud_meta=build_case_shroud(case,(w,h,d),dark)
            reference_shroud=bool(shroud_meta)
            from assembly_case_shrouds052 import remove_replaced_parts
            meshes=remove_replaced_parts(meshes,shroud_meta)
            deferred_ids=frozenset(shroud_meta.get('deferred_part_ids',()))
            deferred_shroud=tuple(m for m in covers if m.part_id in deferred_ids)
            meshes.extend(m for m in covers if m.part_id not in deferred_ids)
        if shroud_vertices:add('psu-shroud',shroud_vertices,dark,shroud_meta['position_mm'])
        elif helios_front_cover is None and not reference_shroud:cube('psu-shroud',(w-12,h*.17,d-12),(0,-h*.405,0),dark)
    board=spec.get('board') or {};board_dims=board.get('dimensions_mm') or {}
    board_h=number(board_dims.get('height'),305,70,370);board_d=number(board_dims.get('width'),244,70,370)
    board_rear=-d/2+14.;board_z=board_rear+board_d/2;board_y=h*.02
    if case.get('id')=='jonsbo-mod-5' and 'angular_modular_shell' in features:
        # This open-frame case has a raised rear PSU option of its own. It
        # must not inherit a closed tower's floor12 mounting datum. The
        # exact helper declares a fixed original option02 reference, not a
        # detected installation, measured CAD or a selected-part carve-out.
        from assembly_mod5_bottom052 import layout_reference as mod5_layout_reference
        case_pose=mod5_layout_reference(case,(w,h,d))
    if reference_shroud:
        from assembly_case_shrouds052 import layout_reference
        case_pose=layout_reference(case,(w,h,d))
        if 'board_x_mm' in case_pose:board_x=number(case_pose['board_x_mm'],board_x,-w/2,w/2)
        if 'board_y_mm' in case_pose:board_y=number(case_pose['board_y_mm'],board_y,-h/2,h/2)
        if case.get('id')=='cooler-master-cosmos-c700m' and 'board_rear_z_mm' in case_pose:
            # The COSMOS external wraps are deeper than its metal body.
            # One fixed body datum moves board/CPU/GPU/RAM and every anchor
            # together; no selected hardware dimensions or ports are changed.
            board_rear=number(case_pose['board_rear_z_mm'],board_rear,-d/2,d/2)
            board_z=board_rear+board_d/2
        from assembly_rear_panel052 import build as build_rear_panel
        back,rear_panel_meta=build_rear_panel(case,(w,h,d),case_pose,dark)
        indexes=[i for i,m in enumerate(meshes) if m.component=='case' and m.name=='case-back']
        if back is not None and len(indexes)==1:
            # Keep the original draw position/order. This fixed source case
            # aperture is independent of every selected PSU/GPU/board.
            meshes[indexes[0]]=back
            shroud_meta=dict(shroud_meta,parts=[*shroud_meta.get('parts',()),*rear_panel_meta.get('parts',())],
                             rear_panel_reference=rear_panel_meta)
    from assembly_motherboard import (layout_anchors,enrich_motherboard,memory_slot_indices,final_anchors,
                                     augment_attachment_anchors,attachment_bounds)
    anchors=layout_anchors(spec,w,h,d,board_x,board_y,board_rear)
    if anchors:
        board_h=anchors['board']['height'];board_d=anchors['board']['width'];board_z=anchors['board']['z']
    divider_aperture=None;divider_reference={}
    if dual:
        # A side-fan mounting bay is a physical opening, not a full opaque wall
        # in front of every optional radiator. Its dimensions remain reference
        # machining; documented fan support does not establish factory CAD.
        from assembly_detail import perforated_plate,chamfer_rect
        holes=[];side_mounts=[row for row in case.get('fan_mounts',()) if isinstance(row,dict) and row.get('position')=='side']
        sizes=[value for row in side_mounts for value in row.get('size_mm',()) if isinstance(value,(int,float))]
        if sizes:
            aperture_w=min(d-36.,max(sizes)+8.);aperture_h=h-64.;center_z=d*.23
            holes.append(tuple((x+center_z,y) for x,y in chamfer_rect(aperture_w,aperture_h,6.)))
            divider_aperture=dict(center=(board_x+5.,0.,center_z),width_mm=aperture_w,height_mm=aperture_h,
                method='documented_mount_reference_aperture',factory_cad_verified=False)
        if case.get('id')=='hyte-y70' and anchors:
            # These additional visible openings were observed in the official
            # empty-case gallery; proportions and machining are simplified.
            cp=anchors['cpu']['position']
            holes.append(tuple((x+cp[2],y+cp[1]) for x,y in chamfer_rect(140.,150.,16.)))
            for zz in (-d*.31,-d*.10):
                holes.append(tuple((x+zz,y+h*.38) for x,y in chamfer_rect(82.,25.,4.)))
        divider_top=case_pose.get('rear_divider_top_y_mm')
        divider_bottom=case_pose.get('rear_divider_bottom_y_mm');source_divider_bounds=None
        if (case.get('id')=='phanteks-nv7' and case_pose.get('case_id')==case['id']
                and type(divider_top) in (int,float) and math.isfinite(divider_top)
                and -h/2+20.<divider_top<h/2-10.):
            # This fixed upper-bay edge comes from the NV7 architecture, not
            # the chosen PSU. Its motherboard tray stops below the upper PSU
            # compartment; a full-height generic divider cuts through it.
            source_divider_bounds=(-h/2+6.,divider_top)
        elif (case.get('id') in ('havn-hs-420','deepcool-ch780') and case_pose.get('case_id')==case['id']
                and type(divider_bottom) in (int,float) and math.isfinite(divider_bottom)
                and -h/2+20.<divider_bottom<h/2-10.):
            # HS420's hybrid lower bay and CH780's raised tray have their
            # own fixed source-reference edges above the broad lower intake.
            # Neither is a full-height divider carved around selected parts.
            source_divider_bounds=(divider_bottom,h/2-6.)
        if source_divider_bounds:
            divider_bottom,divider_top=source_divider_bounds;center_y=(divider_bottom+divider_top)/2
            outer=tuple((z,y+center_y) for z,y in chamfer_rect(d-12,divider_top-divider_bottom,2.))
            shape=perforated_plate(outer,holes,2.,clip_walls=True)
            divider_reference=dict(case_id=case['id'],top_y_mm=divider_top,
                bottom_y_mm=divider_bottom,source=case_pose.get('source',''),
                positions_verified=False,dimensions_verified=False,selected_component_geometry_used=False)
        else:shape=perforated_plate(chamfer_rect(d-12,h-12,2.),holes,2.)
        add('rear-chamber-divider',rotate_vertices(shape,'left'),steel,(board_x+5.,0.,0.))
        if case.get('id')=='hyte-y70' and divider_aperture:
            # Manual B17/18 shows the removable side mounting frame stepped
            # back from the motherboard tray. The observed offset is a
            # proportion, never an asserted factory dimension or fit guarantee.
            plane_x=w*.34;az=divider_aperture['center'][2];aw=divider_aperture['width_mm'];ah=divider_aperture['height_mm']
            for sign in (-1,1):
                cube('case-side-mount-vertical-rail',(3.,ah+8.,5.),(plane_x,0.,az+sign*(aw/2+2.5)),steel)
                cube('case-side-mount-horizontal-rail',(3.,5.,aw),(plane_x,sign*(ah/2+2.5),az),steel)
            # The cold-floor fan bay sits below a raised, genuinely vented
            # main-chamber deck. External case height includes this bay/base.
            main_width=board_x+5.+w/2;deck_center=(-w/2+board_x+5.)/2
            slots=[]
            for index in range(12):
                xx=-main_width*.44+index*main_width*.88/11
                slots.append(tuple((x+xx,y) for x,y in chamfer_rect(main_width*.052,d-56.,1.)))
            deck=perforated_plate(chamfer_rect(main_width-10.,d-28.,2.),slots,2.)
            add('case-cold-floor-deck',rotate_vertices(deck,'down'),steel,(deck_center,-h/2+45.,0.))
    primary_pcie_y=board_y-board_h*.10;pcie_length=min(89.,board_d*.78)
    pcie_z=board_rear+15.+pcie_length/2
    if anchors:primary_pcie_y=anchors['primary_pcie_y'];pcie_z=anchors['pcie_z']
    cube('motherboard-reference',(1.6,board_h,board_d),(board_x,board_y,board_z),green,'board')
    for index in range(3):
        cube('board-expansion-slot',(7,5,pcie_length),(board_x-6,primary_pcie_y-index*40.64,pcie_z),dark,'board')
    cpu=spec.get('cpu') or {};style=cpu.get('style','chip');cpu_y=board_y+board_h*.27;cpu_z=board_z-board_d*.13
    if anchors:cpu_y=anchors['cpu']['y'];cpu_z=anchors['cpu']['z']
    from assembly_cpu import build_cpu_meshes
    cpu_meshes,cpu_package_meta=build_cpu_meshes(cpu,position=(board_x-6,cpu_y,cpu_z),
        level=spec.get('detail_level','balanced'))
    pw,ph=(cpu_package_meta['width_mm'],cpu_package_meta['length_mm']) if cpu_package_meta.get('available') else (37.5,45.) if style=='lga_rect' else (40.,40.)
    if cpu_package_meta.get('available'):
        meshes.extend(cpu_meshes)
    else:
        cube('cpu-substrate',(2,ph,pw),(board_x-3,cpu_y,cpu_z),green,'cpu')
        lid_polygon=unit_polygon(cpu.get('lid_polygon'),pw,ph)
        lid=extrude(lid_polygon,2.4) if lid_polygon else extrude(tuple((x*.84,y*.84) for x,y in AM5_LID),2.4) if style=='am5' else box(pw*.75,ph*.84,2.4)
        add('cpu-lid',rotate_vertices(lid,'left'),color('#cbd6dd'),(board_x-6,cpu_y,cpu_z),'cpu')
    cpu_identity=cpu.get('appearance') or {}
    cpu_id=cpu.get('model_id',cpu_identity.get('id',''))
    if not isinstance(cpu_id,str):cpu_id=''
    marks={'intel-13700kf':('lga_rect','INTEL','13700KF'),'amd-9950x':('am5','RYZEN','9950X'),
           'amd-7800x3d':('am5','RYZEN','7800X3D')}
    mark=marks.get(cpu_id)
    if not cpu_package_meta.get('available') and mark and mark[0]==style:
        for line,offset in zip(mark[1:],(4.,-.8)):
            add('cpu-model-mark',rotate_vertices(model_mark(line),'left'),color('#5c6b75'),(board_x-7.25,cpu_y+offset,cpu_z),'cpu')
    # These are deliberately reference board assemblies, not claimed PCB ICs or
    # a traced retail motherboard. Verified board dimensions remain unchanged.
    cube('board-reference-vrm-top',(9,20,84),(board_x-6,cpu_y+49,cpu_z),edge,'board')
    cube('board-reference-vrm-side',(9,68,18),(board_x-6,cpu_y,cpu_z-48),edge,'board')
    for yy in (-1,1):cube('board-reference-socket-rail',(5,3,pw+10),(board_x-3,cpu_y+yy*(ph/2+5),cpu_z),dark,'board')
    # Memory population comes from the cached inventory, not DIMM-slot capacity.
    memory=spec.get('memory') or {};actual_count=memory.get('count',0)
    actual_count=actual_count if type(actual_count) is int and 0<=actual_count<=256 else 0
    count=memory.get('rendered_count',min(actual_count,8))
    count=count if type(count) is int and 0<=count<=min(actual_count,8) else min(actual_count,8)
    from memory_geometry052 import layout as memory_layout
    memory_models=[];memory_geometry=[];modules=memory.get('modules')
    for index in range(count):
        module=dict(memory)
        if isinstance(modules,list) and index<len(modules) and isinstance(modules[index],dict):module.update(modules[index])
        memory_appearance=module.get('appearance') or {};memory_models.append(memory_appearance.get('id',''))
        short=module.get('style',memory_appearance.get('style'))=='sodimm' or module.get('short_form') is True
        shape=memory_layout(module,short)
        memory_w=shape['pcb_width_mm'];memory_h=shape['pcb_height_mm']
        memory_geometry.append(dict(model_id=memory_appearance.get('id',''),
            **{key:value for key,value in shape.items() if key!='cover_polygon'}))
        pcb=unit_polygon(module.get('pcb_polygon'),memory_w,memory_h)
        case_polygon=unit_polygon(shape['cover_polygon'],shape['cover_width_mm'],memory_h,
                                  margin=shape['required_polygon_margin'])
        bare=not shape['has_cover'];pcb_thickness=shape['pcb_thickness_mm'];cover_thickness=shape['cover_thickness_mm']
        tones=module.get('colors') or {};pcb_color=color(tones.get('pcb'),'#2f5960')
        cover_color=color(tones.get('body'),'#879caa');diffuser_color=color(tones.get('glass'),'#d4e5e5')
        mx=board_x-4 if short else board_x-memory_h/2-2
        my=cpu_y-index*(memory_h+4) if short else cpu_y-8
        mz=cpu_z+57 if short else cpu_z+57+index*10
        if anchors and not short:
            slots=anchors['dimm_centers'];slot_index=memory_slot_indices(count,len(slots))[index]
            if slot_index<len(slots):my,mz=slots[slot_index][1:]
            else:my,mz=slots[-1][1],slots[-1][2]+(slot_index-len(slots)+1)*9.
        orient=(lambda vertices:rotate_vertices(vertices,'left')) if short else memory_plane
        if pcb:add('ram-pcb',orient(extrude(pcb,pcb_thickness)),pcb_color,(mx,my,mz),'memory')
        else:cube('ram-pcb',(pcb_thickness,memory_h,memory_w) if short else (memory_h,memory_w,pcb_thickness),(mx,my,mz),pcb_color,'memory')
        if not bare:
            if case_polygon:add('ram-spreader',orient(extrude(case_polygon,cover_thickness)),cover_color,(mx,my,mz),'memory')
            else:cube('ram-spreader',(cover_thickness,memory_h*.81,memory_w*.96) if short else (memory_h*.81,memory_w*.96,cover_thickness),
                      (mx,my+3,mz) if short else (mx-3,my,mz),cover_color,'memory')
            if shape['has_cap']:
                cap_height=shape['cap_height_mm'];cap_offset=shape['cap_center_from_pcb_center_mm']
                cube('ram-diffuser',(3.8,cap_height,shape['cover_width_mm']*.94) if short else (cap_height,shape['cover_width_mm']*.94,3.8),
                     (mx,my+cap_offset,mz) if short else (mx-cap_offset,my,mz),diffuser_color,'memory')
    gpu=spec.get('gpu') or {};appearance=gpu.get('appearance') or {}
    fan_count=0;gpu_anchor_position=None;gpu_anchor_size=None
    if gpu and gpu.get('present',True) is not False and appearance.get('style')!='gpu_integrated':
        facts=appearance.get('board_details') or {};nominal=facts.get('dimensions_mm') or {}
        length=number(gpu.get('length_mm'),number(nominal.get('length'),min(310,d*.70),80,450),80,450)
        width=number(gpu.get('width_mm'),number(nominal.get('height'),135,50,190),50,190)
        thickness=number(gpu.get('thickness_mm'),number(nominal.get('thickness'),55,8,110),8,110)
        gx=board_x-width*.48;gy=primary_pcie_y-thickness/2+3.3;gz=board_rear+length/2
        gpu_anchor_position=(gx,gy,gz);gpu_anchor_size=(width,thickness,length)
        tones=gpu.get('colors') or {};body_color=color(tones.get('body'),'#536779')
        pcb_color=color(tones.get('pcb'),'#2f5960');metal_color=color(tones.get('metal'),'#b2c0cb')
        shell=unit_polygon(gpu.get('shell_polygon'),length,width)
        if shell:add('gpu-shroud',gpu_plane(extrude(shell,thickness)),body_color,(gx,gy,gz),'gpu')
        else:cube('gpu-shroud',(width,thickness,length),(gx,gy,gz),body_color,'gpu')
        details=gpu.get('detail_polygons')
        if isinstance(details,list):
            for polygon in details[:6]:
                points=polygon.get('points') if isinstance(polygon,dict) else polygon
                tone=color(polygon.get('color'),tones.get('metal') or '#b2c0cb') if isinstance(polygon,dict) else metal_color
                panel=unit_polygon(points,length,width,margin=.25)
                if panel:add('gpu-cover-panel',gpu_plane(extrude(panel,.3)),tone,(gx,gy-thickness/2-.1,gz),'gpu')
        cube('gpu-pcb',(width*.94,1.6,length*.96),(gx,gy+thickness/2+1.5,gz),pcb_color,'gpu')
        cube('gpu-backplate',(width*.96,2,length*.94),(gx,gy+thickness/2+4,gz),metal_color,'gpu')
        cube('gpu-bracket',(width+8,thickness+10,2),(gx,gy,gz-length/2-2),edge,'gpu')
        facts=appearance.get('board_details') or {};ports=[]
        for port in facts.get('ports',()):
            if isinstance(port,dict) and type(port.get('count')) is int and 0<port['count']<=8 and port.get('type') in ('displayport','hdmi','dvi','vga'):
                ports.extend([port['type']]*port['count'])
        if len(ports)<=12:
            for pi,port in enumerate(ports):
                px=gx+((pi%6)-(min(len(ports),6)-1)/2)*19
                py=gy+(pi//6)*13
                port_width=24 if port=='dvi' else 18 if port=='vga' else 15
                cube('gpu-reference-port-'+port,(port_width+2,10,2),(px,py,gz-length/2-3.5),dark,'gpu')
                cube('gpu-reference-port-inset',(port_width,5,1),(px,py,gz-length/2-4.7),color('#19232d'),'gpu')
        cube('gpu-gold-contacts',(width*.47,2.2,length*.28),(gx+width*.26,gy+thickness/2+3,gz-length*.15),gold,'gpu')
        profiles=known_fan_profiles(appearance);provided=gpu.get('fans')
        if isinstance(provided,list) and len(provided)<=4:
            profiles=[dict(row.get('profile') or {},**{key:row[key] for key in ('blades','blade_polygons','shape','direction','hub_ratio','kind','blade_pattern','outer_ring','group_size') if key in row},
                           **({'blades':row['blade_count']} if 'blade_count' in row else {})) for row in provided]
        fan_count=len(profiles)
        for i,profile in enumerate(profiles):
            at=(i+.5)/fan_count;across=.5;rear=False
            radius=min(width*.41,length/max(1,fan_count)*.42)
            if isinstance(provided,list):
                row=provided[i];uv=row.get('center_uv')
                at=number(uv[0] if isinstance(uv,(list,tuple)) and len(uv)==2 else row.get('x_ratio'),at,0,1)
                across=number(uv[1] if isinstance(uv,(list,tuple)) and len(uv)==2 else None,.5,0,1)
                radius=number(row.get('radius_mm'),radius,5,75);rear=row.get('face')=='rear'
                if isinstance(row.get('radius_uv'),(list,tuple)) and len(row['radius_uv'])==2:
                    radius=min(number(row['radius_uv'][0],radius/length,.005,.5)*length,number(row['radius_uv'][1],radius/width,.005,.5)*width)
            pos=(gx+(across-.5)*width,gy+(thickness/2+5 if rear else -thickness/2-1.5),gz-length/2+length*at)
            def fan_plane(vertices):return gpu_plane(vertices,rear)
            fan_colors=provided[i].get('colors',{}) if isinstance(provided,list) else {}
            add('gpu-fan-opening',fan_plane(ring(radius,radius*.92,2)),color(fan_colors.get('rim'),'#25313e'),pos,'gpu')
            add('gpu-fan-recess',fan_plane(ring(radius*.91,0,.5)),color(fan_colors.get('disk'),'#263340'),(pos[0],pos[1]+(-1 if rear else 1),pos[2]),'gpu')
            blades=fan_rotor(profile,radius)
            add('gpu-fan-rotor',fan_plane(blades),color(fan_colors.get('blade'),'#afc0ca'),pos,'gpu',rotor=True,direction=-1 if profile.get('direction')==-1 else 1,axis=(0,-1 if rear else 1,0))
            hub=radius*number(profile.get('hub_ratio'),.28,.1,.7)
            hub_mesh=extrude(tuple((x,-y) for x,y in (_point(angle,hub*1.15) for angle in (0,120,240))),2.7) if profile.get('hub_shape')=='triangle' else ring(hub,0,2.7)
            add('gpu-fan-hub',fan_plane(hub_mesh),color(fan_colors.get('hub'),'#c3cdd3' if profile.get('hub_tone')=='silver' else '#8095a6'),(pos[0],pos[1]+(.8 if rear else -.8),pos[2]),'gpu')
        if appearance.get('fan_count')==0:
            for i in range(20):cube('passive-gpu-fin',(width,thickness*.94,1.2),(gx,gy,gz-length*.44+length*.88*i/19),edge,'gpu')
    from assembly_detail import enrich_components,detail_level,component_level,TRIANGLE_BUDGETS
    level=detail_level(spec.get('detail_level'))
    meshes,component_details=enrich_components(meshes,dict(spec,_cpu_package_geometry=cpu_package_meta.get('available',False)))
    meshes,motherboard_meta=enrich_motherboard(meshes,spec,anchors,component_level(spec,'board'))
    if motherboard_meta:component_details['board']=motherboard_meta
    # The same physical component keeps a stable identity across all of its
    # submeshes, styles and rigid case poses. No extra instance is introduced.
    memory_pcbs=[m for m in meshes if m.name=='ram-pcb']
    identified=[]
    for mesh in meshes:
        part_id=mesh.part_id
        if not part_id:
            if mesh.component in ('cpu','gpu','board'):part_id=mesh.component+':0'
            elif mesh.component=='memory' and memory_pcbs:
                part_id='memory:'+str(min(range(len(memory_pcbs)),key=lambda n:sum((memory_pcbs[n].position[k]-mesh.position[k])**2 for k in range(3))))
        identified.append(replace(mesh,part_id=part_id) if part_id!=mesh.part_id else mesh)
    meshes=tuple(identified)
    if anchors is None:
        anchors=dict(case=case,case_dimensions=(w,h,d),
            board=dict(x=board_x,y=board_y,z=board_z,position=(board_x,board_y,board_z),height=board_h,width=board_d,
                rear_z=board_rear,normal=(-1.,0.,0.),up=(0.,1.,0.),along=(0.,0.,1.)),
            cpu=dict(x=board_x-6.,y=cpu_y,z=cpu_z,position=(board_x-6.,cpu_y,cpu_z),normal=(-1.,0.,0.),
                up=(0.,1.,0.),u=(0.,1.,0.),v=(0.,0.,-1.)),connectors={})
    # Case layout changes pose, never component dimensions. Known ATX/GPU sizes
    # can protrude from an incompatible compact case instead of shrinking.
    vertical_gpu='vertical_gpu_mount' in features;front_gpu='front_gpu_chamber' in features;gpu_mount_observation={}
    identity_pose=lambda p:tuple(p)
    board_pose=identity_pose;gpu_pose=identity_pose;gpu_vector=identity_pose;board_vector=identity_pose
    bench='horizontal_test_bench' in features
    tilted='forward_tilted_open_frame' in features
    if tilted:
        from assembly_case_exteriors040 import torque_pose,hardware_pose
    top_io_reference=case_pose.get('board_pose') or {}
    top_io=(case.get('id')=='geometric-future-model-8-cowboy'
            and top_io_reference.get('kind')=='top_io_90'
            and all(type(top_io_reference.get(k)) in (int,float) and math.isfinite(top_io_reference[k])
                    for k in ('io_y_mm','rear_z_mm')))
    if top_io:
        original_center=(board_x,board_y,board_z)
        target_center=(board_x,top_io_reference['io_y_mm']-board_d/2,
                       top_io_reference['rear_z_mm']+board_h/2)
    if layout in ('vertical','horizontal') or vertical_gpu or front_gpu or winged or bench or tilted or top_io:
        transformed=[]
        def vector_pose(p):
            if tilted:return torque_pose(p,vector=True)
            x,y,z=p
            return (z,y,-x) if winged else (x,-z,y) if layout=='vertical' or top_io else (y,-x,z)
        def pose(p):
            if top_io:
                relative=tuple(p[k]-original_center[k] for k in range(3))
                rotated=vector_pose(relative)
                return tuple(target_center[k]+rotated[k] for k in range(3))
            x,y,z=vector_pose(p)
            return (x-board_y,y+board_x+66.3,z-board_z) if bench else (x,y,z)
        board_pose=pose;gpu_pose=pose;gpu_vector=vector_pose;board_vector=vector_pose
        if (vertical_gpu or front_gpu) and layout not in ('vertical','horizontal'):
            board_pose=identity_pose
            board_vector=identity_pose
            def gpu_vector(p):
                x,y,z=p
                return (x,z,-y) if front_gpu else (y,-x,z)
            target=gpu_anchor_position
            if front_gpu and gpu_anchor_size:
                gw,gt,gl=gpu_anchor_size
                target=(0.,h*.03,d/2-min(96.,d*.24)+gt/2-3.3)
                gpu_mount_observation=dict(method='official_front_gpu_layout_with_schematic_rail_position',
                    source=(case.get('sources') or [''])[0],cad_verified=False,position_dimensions_verified=False)
            elif case.get('id')=='hyte-y70' and gpu_anchor_size:
                # Source-observed factory riser: PCB plane near 1/3 of case
                # width from the glass, contact row near the cold-floor mount.
                # This is a rigid pose, never a card-envelope adjustment.
                gw,gt,gl=gpu_anchor_size
                target=(-w*.16-(gt/2-3.3),-h/2+75.+gw*.48-5.2,gpu_anchor_position[2])
                gpu_mount_observation=dict(method='official_photo_observed_factory_riser_reference',
                    source='https://hyte.com/store/y70/cs-hyte-y70-ww',pcb_plane_x_mm=-w*.16,
                    contact_row_y_mm=-h/2+75.,cad_verified=False,position_dimensions_verified=False)
            def gpu_pose(p):
                relative=tuple(p[i]-gpu_anchor_position[i] for i in range(3));rotated=gpu_vector(relative)
                return tuple(rotated[i]+target[i] for i in range(3))
        for mesh in meshes:
            if mesh.component in ('board','cpu','memory','gpu'):
                if (vertical_gpu or front_gpu) and layout not in ('vertical','horizontal'):
                    if mesh.component!='gpu':transformed.append(mesh);continue
                    def point_pose(p):
                        return gpu_vector(p)
                    local=[]
                    for n in range(0,len(mesh.vertices),6):local.extend((*point_pose(mesh.vertices[n:n+3]),*point_pose(mesh.vertices[n+3:n+6])))
                    mesh=Mesh(mesh.name,tuple(local),mesh.color,gpu_pose(mesh.position),mesh.component,mesh.rotor,mesh.direction,point_pose(mesh.axis),mesh.part_id)
                    transformed.append(mesh);continue
                out=[]
                for n in range(0,len(mesh.vertices),6):out.extend((*vector_pose(mesh.vertices[n:n+3]),*vector_pose(mesh.vertices[n+3:n+6])))
                mesh=Mesh(mesh.name,tuple(out),mesh.color,pose(mesh.position),mesh.component,mesh.rotor,mesh.direction,vector_pose(mesh.axis),mesh.part_id)
            transformed.append(mesh)
        meshes=transformed
    attachment_anchors=final_anchors(anchors,board_pose,gpu_pose,gpu_anchor_position,gpu_anchor_size,spec,gpu_vector=gpu_vector,board_vector=board_vector)
    if appearance.get('id')=='asus-astral-5090' and gpu_anchor_size:
        # The official side photo puts the socket near the PCB/backplate, not
        # halfway through the76mm cooler. Only depth is photo-observed here;
        # longitudinal placement remains the existing unverified reference.
        source='https://dlcdnwebimgs.asus.com/gain/B625A69F-626B-4451-B08B-DE635451FA0E/w1000/h732'
        depth_shift=gpu_vector((0.,gpu_anchor_size[1]*.40,0.))
        for inlet in attachment_anchors.get('gpu',{}).get('power',()):
            if inlet.get('type') not in ('16pin','12vhpwr','12v_2x6'):continue
            inlet['position']=tuple(inlet['position'][n]+depth_shift[n] for n in range(3))
            inlet.update(position_verified=False,position_schematic=True,
                         position_source='official_photo_observed_depth_reference',source=source)
        attachment_anchors['gpu']['power_depth_observation']=dict(source=source,method='official_photo_observed_reference',
            canonical_depth_fraction=.40,position_verified=False,dimensions_verified=False,
            longitudinal_position_verified=False)
    cooling_meta={};auxiliary_meta={}
    from assembly_case_detail import enrich_case
    meshes=enrich_case(meshes,(w,h,d),case,component_level(spec,'case'))
    tray_meta={}
    if case.get('id')=='fractal-north-xl-mesh':
        from assembly_north_tray049 import add_tray,add_obstacles
        meshes,tray_meta=add_tray(meshes,case,(w,h,d))
    elif case.get('id')=='asus-rog-strix-helios-gx601':
        from assembly_case_layout051 import add_helios_tray
        from assembly_north_tray049 import add_obstacles
        meshes,tray_meta=add_helios_tray(meshes,case,(w,h,d))
    elif case.get('id')=='cooler-master-cosmos-c700m':
        from assembly_c700m_case055 import add_tray
        from assembly_north_tray049 import add_obstacles
        meshes,tray_meta=add_tray(meshes,case,(w,h,d))
        shroud_meta=dict(shroud_meta,parts=[*shroud_meta.get('parts',()),*tray_meta.get('parts',())])
    attachment_anchors=augment_attachment_anchors(attachment_anchors,meshes)
    if tray_meta:attachment_anchors=add_obstacles(attachment_anchors,tray_meta)
    if case.get('id')=='hyte-y70':
        main_center=(-w/2+board_x+5.)/2;main_span=board_x+5.+w/2-16.
        attachment_anchors['case_floor_deck']=dict(position=(main_center,-h/2+45.,0.),normal=(0.,1.,0.),
            thickness_mm=2.,method='official_photo_observed_raised_floor_reference',dimensions_verified=False,
            source='https://hyte.com/store/y70/cs-hyte-y70-ww')
        attachment_anchors['case_mount_planes']=dict(side=dict(position=(w*.34,0.,d*.23),
            normal=(1.,0.,0.),up=(0.,1.,0.),stack_direction=(-1.,0.,0.),
            method='official_manual_observed_recessed_mount_reference',dimensions_verified=False,
            source='https://content.ibuypower.com/hyte/product-page-pdfs/y70-touch-15-language.pdf',page=11))
        for mount,y,normal in (('top',h/2-12.,(0.,1.,0.)),('bottom',-h/2+10.,(0.,-1.,0.))):
            attachment_anchors['case_mount_planes'][mount]=dict(position=(main_center,y,0.),normal=normal,up=(0.,0.,1.),
                span_mm=(main_span,d-32.),method='official_manual_observed_main_chamber_mount_reference',
                dimensions_verified=False,source='https://content.ibuypower.com/hyte/product-page-pdfs/y70-touch-15-language.pdf',page=11 if mount=='top' else 8)
    if case_pose:
        from assembly_case_shrouds052 import apply_layout_anchors
        attachment_anchors=apply_layout_anchors(attachment_anchors,spec,case_pose)
    from assembly_cooling import add_cooling
    from assembly_auxiliary import add_auxiliary
    auxiliary_stage=None;collision_meshes=meshes
    try:
        selected_cooling=spec.get('cooling') or {}
        stage_auxiliary=bool(selected_cooling.get('case_fans'))
        if not stage_auxiliary and selected_cooling.get('loop_components_mode')=='selected':
            from cooling_catalog import get_cooler
            selected_cooler=get_cooler(selected_cooling.get('cpu_cooler'))
            stage_auxiliary=bool(selected_cooler and selected_cooler.get('kind')=='custom_loop')
        if stage_auxiliary:
            from assembly_auxiliary import auxiliary_stages,finish_auxiliary
            # Construct selected bodies once before either loop placement or
            # case-fan clearance, including ordinary air/AIO configurations.
            # Resume this same construction later for final cable anchors.
            auxiliary_stage=auxiliary_stages(spec,attachment_anchors,level)
            auxiliary_bodies=next(auxiliary_stage)
            collision_meshes=tuple((*meshes,*auxiliary_bodies))
        cooling_meshes,cooling_meta=add_cooling(collision_meshes,spec,level,attachment_anchors)
        gpu_cooler_replaced=cooling_meta.get('replace_gpu_cooler') is True
        if gpu_cooler_replaced:
            kept_gpu={'gpu-pcb','gpu-bracket','gpu-gold-contacts','detail-gpu-separated-edge-contacts',
                      'detail-gpu-pcb-stack-edge','detail-gpu-port-recesses'}
            meshes=tuple(m for m in meshes if m.component!='gpu' or m.name in kept_gpu or m.name.startswith('gpu-reference-port-'))
        meshes=tuple((*meshes,*cooling_meshes))
        if reference_shroud:
            from assembly_case_shrouds052 import finish as finish_case_shroud
            meshes,shroud_meta=finish_case_shroud(case,tuple((*meshes,*deferred_shroud)),
                                               cooling_meshes,cooling_meta,shroud_meta)
        if helios_front_cover is not None:
            from assembly_helios_shroud052 import finish
            meshes,shroud_meta,cooling_meta=finish(meshes,helios_front_cover,cooling_meshes,cooling_meta,shroud_meta)
        attachment_anchors['cooling']=cooling_meta
        attachment_anchors=augment_attachment_anchors(attachment_anchors,meshes)
        if tray_meta:attachment_anchors=add_obstacles(attachment_anchors,tray_meta)
        # A transient reference supplies exact hollow GPU geometry for bounded
        # cable clearance; it never enters serializable metadata.
        attachment_anchors['_gpu_clearance_meshes']=tuple(m for m in meshes if m.component=='gpu')
        if auxiliary_stage is None:auxiliary_meshes,auxiliary_meta=add_auxiliary(spec,attachment_anchors,level)
        else:auxiliary_meshes,auxiliary_meta=finish_auxiliary(auxiliary_stage,attachment_anchors)
        attachment_anchors.pop('_gpu_clearance_meshes',None)
    finally:
        if auxiliary_stage is not None:auxiliary_stage.close()
    meshes=tuple((*meshes,*auxiliary_meshes))
    added_bounds,added_notices=attachment_bounds(meshes,(w,h,d),case)
    budget=TRIANGLE_BUDGETS[level]-64
    triangles=sum(mesh.vertex_count//3 for mesh in meshes);removed=0
    if triangles>budget:
        kept=list(meshes)
        optional_reference={'detail-board-reference-small-packages','detail-board-reference-capacitors',
                            'detail-ram-reference-ic-packages','detail-ram-reference-package-leads'}
        for index in range(len(kept)-1,-1,-1):
            mesh=kept[index]
            if mesh.name in optional_reference and triangles>budget:
                triangles-=mesh.vertex_count//3;kept.pop(index);removed+=1
        if triangles>budget:
            raise ValueError('Mechanical illustration exceeds its detail budget; use a lower detail level')
        meshes=kept
    observed_rear=component_details.get('gpu',{}).get('observed_rear_fans',0)
    fan_count+=observed_rear
    rear_count=sum(row.get('face')=='rear' for row in (gpu.get('fans') or []) if isinstance(row,dict))+observed_rear
    physical_count=appearance.get('fan_count') if type(appearance.get('fan_count')) is int else None
    original_gpu_air_cooler_fans=physical_count
    if gpu_cooler_replaced:fan_count=0;rear_count=0;physical_count=0
    meta=dict(case_id=case.get('id',''),schematic=True,geometry_unit='mm',installed_case_fans_assumed=0,
              front_fan_count=fan_count-rear_count,rear_fan_count=rear_count,rotor_count=sum(mesh.rotor for mesh in meshes),memory_count=actual_count,memory_rendered_count=count,
              physical_total_fans=physical_count,unplaced_fans=max(0,physical_count-fan_count) if physical_count is not None else None,
              memory_models=memory_models,memory_geometry=memory_geometry,cpu_model_mark=cpu_id if cpu_package_meta.get('model_mark_lines') or mark and mark[0]==style else '',
              cpu_style=style,board_is_reference=board.get('schematic',True) is not False,gpu_model=appearance.get('id',''),case_layout=layout,
              gpu_mount='front_vertical' if front_gpu else 'vertical' if vertical_gpu else 'case_top_io' if top_io else 'case_vertical' if layout=='vertical' else 'horizontal',
              board_layout_schematic=True,connector_positions_schematic=True,
              dimensions_verified=case.get('dimensions_verified') is True,cad_or_fit_guarantee=False)
    if tilted:meta['hardware_pose_reference']=hardware_pose(case)
    meta.update(detail_level=level,detail_focus=spec.get('detail_focus'),detail=component_details,
                triangle_budget=TRIANGLE_BUDGETS[level],optional_detail_meshes_removed=removed,
                memory_orientation='standing_dimm_or_flat_sodimm',case_detail_schematic=True,
                canonical_board_rear_mm=board_rear,canonical_gpu_bracket_mm=board_rear,
                mechanical_alignment_schematic=True,motherboard=motherboard_meta,
                attachment_anchors=attachment_anchors,cooling=cooling_meta,auxiliary=auxiliary_meta,cpu_package=cpu_package_meta,
                attachment_bounds=added_bounds,attachment_notices=added_notices,
                attachments_outside_reference=added_notices,divider_aperture=divider_aperture,
                gpu_mount_observation=gpu_mount_observation,
                gpu_air_cooler_replaced=gpu_cooler_replaced,original_gpu_air_cooler_fans=original_gpu_air_cooler_fans)
    if tray_meta:meta['case_tray']=tray_meta
    if shroud_meta:meta['case_shroud']=shroud_meta
    if case_pose:meta['case_pose_reference']=case_pose
    if divider_reference:meta['rear_divider_reference']=divider_reference
    hardware_parts=[]
    for component,identity,label in (('cpu','cpu:0',(spec.get('cpu') or {}).get('label','CPU')),
            ('gpu','gpu:0',gpu.get('label','GPU')),('board','board:0',motherboard_meta.get('model_label',board.get('label','Motherboard')))):
        if any(m.part_id==identity for m in meshes):hardware_parts.append(dict(id=identity,label=label or component.upper(),kind=component,model_id=motherboard_meta.get('model_id','') if component=='board' else ''))
    for index in range(len(memory_pcbs)):
        module=modules[index] if isinstance(modules,list) and index<len(modules) and isinstance(modules[index],dict) else {}
        hardware_parts.append(dict(id='memory:'+str(index),label=(module.get('label') or 'Memory')+' '+str(index+1),kind='memory',model_id=memory_models[index] if index<len(memory_models) else ''))
    case_part_ids={m.part_id for m in meshes if m.component=='case' and m.part_id}
    hardware_parts.extend(dict(row) for row in shroud_meta.get('parts',())
                          if isinstance(row,dict) and row.get('id') in case_part_ids)
    if case.get('id')=='jonsbo-mod-5' and case_part_ids:
        from assembly_mod5_bottom052 import describe as describe_mod5_bottom
        bottom_reference=describe_mod5_bottom(case,(w,h,d))
        actual_parts=[dict(row) for row in bottom_reference.get('parts',())
                      if isinstance(row,dict) and row.get('id') in case_part_ids]
        if actual_parts:
            # Metadata follows only rendered independent structures. Do not
            # build a second model or register absent reference-only parts.
            hardware_parts.extend(actual_parts)
            meta['case_bottom_reference']=bottom_reference
    meta['hardware']=dict(parts=hardware_parts)
    from assembly_style import apply_model_styles
    meshes,style_meta=apply_model_styles(meshes,spec.get('visual_style'),spec.get('part_styles',{}),(w,h,d),panels,spec.get('lighting_preview','artwork'),
        finish_materials=component_details.get('board',{}).get('finish_materials'))
    meta.update(style_meta)
    return Scene(tuple(meshes),(w,h,d),meta)


def vertex_bytes(scene):
    # Keep exact little-endian f32 packing without flattening the whole scene
    # into a second tuple of Python references and one giant argument vector.
    return b''.join(struct.pack('<'+str(len(mesh.vertices))+'f',*mesh.vertices)
                    for mesh in scene.meshes)
