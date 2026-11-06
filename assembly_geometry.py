"""Original low-poly assembly meshes; pure geometry, no hardware or rendering I/O.

The meshes are scaled illustrations, not manufacturing CAD or a fit guarantee.
Model dimensions/fan metadata must come from the existing reviewed catalog.
Original code/art: PolyForm Noncommercial 1.0.0; third-party rights remain intact.
"""
from dataclasses import dataclass
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
    spec=spec if isinstance(spec,dict) else {};case=spec.get('case') or {};dims=case.get('dimensions_mm') or {}
    w=number(dims.get('width'),230,120,650);h=number(dims.get('height'),470,150,900);d=number(dims.get('depth'),460,150,900)
    meshes=[];steel=color(case.get('color'),'#4d5965');edge=color('#a9b8c4');dark=color('#25313e');green=color('#2f5960');gold=color('#d7b36d')
    features=case.get('features') or []
    corner='curved_front_glass' if 'curved_front_glass' in features else 'angular_glass_corner' if 'angular_glass_corner' in features else ''
    cut=min(w*.23,d*.18) if corner else 0.
    def add(name,vertices,tone,position=(0,0,0),component='case',**kw):
        if vertices:meshes.append(Mesh(name,vertices,tone,position,component,**kw))
    def cube(name,size,pos,tone=steel,component='case'):add(name,box(*size),tone,pos,component)
    # Actual case proportions, a light structural frame and removable side.
    rail=max(5.,min(9.,w*.028))
    body_h=h-16;body_y=8;bottom=-h/2+16
    for x in (-(w-rail)/2,(w-rail)/2):
        for z in (-(d-rail)/2,(d-rail)/2):
            if not(corner and x<0 and z>0):cube('case-upright',(rail,body_h,rail),(x,body_y,z))
    for y in (bottom+rail/2,h/2-rail/2):
        for z in (-(d-rail)/2,(d-rail)/2):cube('case-width-rail',(w-cut if corner and z>0 else w,rail,rail),(cut/2 if corner and z>0 else 0,y,z))
        for x in (-(w-rail)/2,(w-rail)/2):cube('case-depth-rail',(rail,rail,d-cut if corner and x<0 else d),(x,y,-cut/2 if corner and x<0 else 0))
    if corner:
        footprint=((-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2+cut,d/2),(-w/2,d/2-cut))
        add('case-bottom',rotate_vertices(extrude(footprint,3),'down'),dark,(0,bottom+1.5,0))
    else:cube('case-bottom',(w,3,d),(0,bottom+1.5,0),dark)
    cube('case-back',(w,body_h,2),(0,body_y,-d/2+1),dark)
    cube('case-right',(2,body_h,d),(w/2-1,body_y,0),steel)
    panels=case.get('panels') or {};front=panels.get('front','mesh');left=panels.get('left','glass')
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
    else:cube('front-panel',(w-rail*2,body_h-rail*2,2),(0,body_y,d/2-1),steel)
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
    if 'octagonal_front' in features:
        for sign in (-1,1):
            vertices=box(w*.30,7,6);out=[];angle=sign*math.pi/6;co,si=math.cos(angle),math.sin(angle)
            for n in range(0,len(vertices),6):
                for offset in (0,3):
                    x,y,z=vertices[n+offset:n+offset+3];out.extend((co*x-si*y,si*x+co*y,z))
            for yy in (-h*.44,h*.44):add('octagonal-frame',tuple(out),edge,(sign*w*.30,yy,d/2+3))
    # Top vent rails suggest the panel construction, never invented mounted fans.
    for i in range(12):cube('top-vent',(w*.78,1.6,2),(0,h/2-.8,-d*.4+i*d*.8/11),edge)
    for x in (-w*.34,w*.34):
        for z in (-d*.34,d*.34):cube('case-foot',(23,12,30),(x,-h/2+6,z),dark)
    layout=case.get('layout','tower');dual=layout=='dual_chamber'
    board_x=w*(.10 if dual else .36)
    if dual:cube('rear-chamber-divider',(2,h-12,d-12),(w*.19,0,0),steel)
    if dual:
        cube('rear-chamber-shroud',(w*.28,h*.23,d*.44),(w*.34,-h*.32,-d*.25),dark)
    elif layout not in ('compact','horizontal'):
        cube('psu-shroud',(w-12,h*.17,d-12),(0,-h*.405,0),dark)
    board=spec.get('board') or {};board_dims=board.get('dimensions_mm') or {}
    board_h=number(board_dims.get('height'),305,70,370);board_d=number(board_dims.get('width'),244,70,370)
    cube('motherboard-reference',(1.6,board_h,board_d),(board_x,h*.02,-d*.10),green,'board')
    for yy in (-.29,-.20,-.11):cube('board-expansion-slot',(7,5,board_d*.52),(board_x-6,board_h*yy,-d*.10),dark,'board')
    cpu=spec.get('cpu') or {};style=cpu.get('style','chip');cpu_y=h*.20;cpu_z=-d*.17
    pw,ph=(37.5,45.) if style=='lga_rect' else (40.,40.)
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
    if mark and mark[0]==style:
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
    memory_models=[];modules=memory.get('modules')
    for index in range(count):
        module=dict(memory)
        if isinstance(modules,list) and index<len(modules) and isinstance(modules[index],dict):module.update(modules[index])
        memory_appearance=module.get('appearance') or {};memory_models.append(memory_appearance.get('id',''))
        short=module.get('style',memory_appearance.get('style'))=='sodimm' or module.get('short_form') is True
        memory_w=number(module.get('length_mm'),69.6 if short else 133.35,50,160)
        memory_h=number(module.get('height_mm'),30 if short else 31,15,70)
        pcb=unit_polygon(module.get('pcb_polygon'),memory_w,memory_h)
        case_polygon=unit_polygon(module.get('case_polygon'),memory_w,memory_h,margin=2.)
        bare=module.get('heat_spreader') is False or memory_appearance.get('shroud')=='bare'
        tones=module.get('colors') or {};pcb_color=color(tones.get('pcb'),'#2f5960')
        cover_color=color(tones.get('body'),'#879caa');diffuser_color=color(tones.get('glass'),'#d4e5e5')
        mx=board_x-8-index*10;mz=cpu_z+57
        if pcb:add('ram-pcb',rotate_vertices(extrude(pcb,1.2),'left'),pcb_color,(mx,cpu_y,mz),'memory')
        else:cube('ram-pcb',(1.2,memory_h,memory_w),(mx,cpu_y,mz),pcb_color,'memory')
        if not bare:
            if case_polygon:add('ram-spreader',rotate_vertices(extrude(case_polygon,3.2),'left'),cover_color,(mx,cpu_y,mz),'memory')
            else:cube('ram-spreader',(3.2,memory_h*.81,memory_w*.96),(mx,cpu_y+3,mz),cover_color,'memory')
            if module.get('rgb_diffuser') is True or module.get('diffuser') is True:cube('ram-diffuser',(3.8,3,memory_w*.94),(mx,cpu_y+memory_h*.55,mz),diffuser_color,'memory')
    gpu=spec.get('gpu') or {};appearance=gpu.get('appearance') or {}
    fan_count=0
    if gpu and gpu.get('present',True) is not False and appearance.get('style')!='gpu_integrated':
        length=number(gpu.get('length_mm'),min(310,d*.70),80,450)
        width=number(gpu.get('width_mm'),135,50,190);thickness=number(gpu.get('thickness_mm'),55,8,110)
        gx=board_x-width*.48;gy=-h*.13;gz=-d*.11
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
    # Case layout changes pose, never component dimensions. Known ATX/GPU sizes
    # can protrude from an incompatible compact case instead of shrinking.
    vertical_gpu='vertical_gpu_mount' in features
    if layout in ('vertical','horizontal') or vertical_gpu:
        transformed=[]
        def pose(p):
            x,y,z=p
            return (x,z,-y) if layout=='vertical' else (y,-x,z)
        for mesh in meshes:
            if mesh.component in ('board','cpu','memory','gpu'):
                if vertical_gpu and layout not in ('vertical','horizontal'):
                    if mesh.component!='gpu':transformed.append(mesh);continue
                    pivot=(gx,gy,gz)
                    def point_pose(p):
                        x,y,z=p;return (y,-x,z)
                    local=[]
                    for n in range(0,len(mesh.vertices),6):local.extend((*point_pose(mesh.vertices[n:n+3]),*point_pose(mesh.vertices[n+3:n+6])))
                    relative=tuple(mesh.position[i]-pivot[i] for i in range(3));rotated=point_pose(relative)
                    mesh=Mesh(mesh.name,tuple(local),mesh.color,tuple(rotated[i]+pivot[i] for i in range(3)),mesh.component,mesh.rotor,mesh.direction,point_pose(mesh.axis))
                    transformed.append(mesh);continue
                out=[]
                for n in range(0,len(mesh.vertices),6):out.extend((*pose(mesh.vertices[n:n+3]),*pose(mesh.vertices[n+3:n+6])))
                mesh=Mesh(mesh.name,tuple(out),mesh.color,pose(mesh.position),mesh.component,mesh.rotor,mesh.direction,pose(mesh.axis))
            transformed.append(mesh)
        meshes=transformed
    rear_count=sum(row.get('face')=='rear' for row in (gpu.get('fans') or []) if isinstance(row,dict))
    physical_count=appearance.get('fan_count') if type(appearance.get('fan_count')) is int else None
    meta=dict(case_id=case.get('id',''),schematic=True,geometry_unit='mm',installed_case_fans_assumed=0,
              front_fan_count=fan_count-rear_count,rear_fan_count=rear_count,rotor_count=sum(mesh.rotor for mesh in meshes),memory_count=actual_count,memory_rendered_count=count,
              physical_total_fans=physical_count,unplaced_fans=max(0,physical_count-fan_count) if physical_count is not None else None,
              memory_models=memory_models,cpu_model_mark=cpu_id if mark and mark[0]==style else '',
              cpu_style=style,board_is_reference=board.get('schematic',True) is not False,gpu_model=appearance.get('id',''),case_layout=layout,
              gpu_mount='vertical' if vertical_gpu else 'case_vertical' if layout=='vertical' else 'horizontal',
              board_layout_schematic=True,connector_positions_schematic=True,
              dimensions_verified=case.get('dimensions_verified') is True,cad_or_fit_guarantee=False)
    return Scene(tuple(meshes),(w,h,d),meta)


def vertex_bytes(scene):
    vertices=tuple(value for mesh in scene.meshes for value in mesh.vertices)
    return struct.pack('<'+str(len(vertices))+'f',*vertices)
