"""Original bounded case mechanics; port counts require catalog evidence.

Panel rebates, folded lips and rear fasteners are schematic construction, not
manufacturer CAD or inferred installed devices. No I/O or animation lives here.
"""
import math
from dataclasses import replace


def chamfer_box(width,height,depth,bevel=.6):
    """Closed 26-face bevel box; preserve the original exterior dimensions."""
    from assembly_geometry import _tri,_quad
    x,y,z=width/2,height/2,depth/2
    b=max(.005,min(bevel,min(x,y,z)*.45));out=[]
    def face(points):
        a,c,d=points[:3]
        u=tuple(c[n]-a[n] for n in range(3));v=tuple(d[n]-a[n] for n in range(3))
        normal=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        center=tuple(sum(p[n] for p in points)/len(points) for n in range(3))
        if sum(normal[n]*center[n] for n in range(3))<0:points=tuple(reversed(points))
        if len(points)==3:_tri(out,*points)
        else:_quad(out,*points)
    for s in (-1,1):
        face(((-x+b,-y+b,s*z),(x-b,-y+b,s*z),(x-b,y-b,s*z),(-x+b,y-b,s*z)))
        face(((s*x,-y+b,-z+b),(s*x,y-b,-z+b),(s*x,y-b,z-b),(s*x,-y+b,z-b)))
        face(((-x+b,s*y,-z+b),(-x+b,s*y,z-b),(x-b,s*y,z-b),(x-b,s*y,-z+b)))
    for a in (-1,1):
        for c in (-1,1):
            face(((a*x,c*(y-b),-z+b),(a*(x-b),c*y,-z+b),(a*(x-b),c*y,z-b),(a*x,c*(y-b),z-b)))
            face(((a*x,-y+b,c*(z-b)),(a*(x-b),-y+b,c*z),(a*(x-b),y-b,c*z),(a*x,y-b,c*(z-b))))
            face(((-x+b,a*y,c*(z-b)),(-x+b,a*(y-b),c*z),(x-b,a*(y-b),c*z),(x-b,a*y,c*(z-b))))
            for e in (-1,1):
                face(((a*x,c*(y-b),e*(z-b)),(a*(x-b),c*y,e*(z-b)),(a*(x-b),c*(y-b),e*z)))
    return tuple(out)


def _translate(vertices,position):
    return tuple(value+position[index%6] if index%6<3 else value for index,value in enumerate(vertices))


def _plane(vertices,position,normal):
    """Move a local XY face onto a declared case surface, preserving normals."""
    result=[]
    for start in range(0,len(vertices),6):
        for offset in (0,3):
            x,y,z=vertices[start+offset:start+offset+3]
            if normal=='top':point=(x,z,-y)
            elif normal=='left':point=(-z,y,x)
            elif normal=='corner':
                a=math.sqrt(.5);point=(a*x-a*z,y,a*x+a*z)
            else:point=(x,y,z)
            result.extend(point[n]+(position[n] if offset==0 else 0) for n in range(3))
    return tuple(result)


def rounded_frame(width,height,wall,depth,segments=5):
    """A stadium aperture, with real inner wall, for a Type-C socket mouth."""
    from assembly_geometry import _quad
    outer=[];inner=[]
    for end in (-1,1):
        for index in range(segments+1):
            angle=(-math.pi/2 if end==1 else math.pi/2)+index*math.pi/segments
            for row,radius,half in ((inner,height/2,width/2),(outer,height/2+wall,width/2+wall)):
                row.append((end*(half-radius)+math.cos(angle)*radius,math.sin(angle)*radius))
    out=[]
    for index in range(len(outer)):
        n=(index+1)%len(outer);a,b=outer[index],outer[n];c,e=inner[index],inner[n]
        _quad(out,(*a,depth/2),(*b,depth/2),(*e,depth/2),(*c,depth/2))
        _quad(out,(*b,-depth/2),(*a,-depth/2),(*c,-depth/2),(*e,-depth/2))
        _quad(out,(*a,-depth/2),(*b,-depth/2),(*b,depth/2),(*a,depth/2))
        _quad(out,(*e,-depth/2),(*c,-depth/2),(*c,depth/2),(*e,depth/2))
    return tuple(out)


def _port_meshes(io,dimensions,case):
    from assembly_geometry import Mesh,box,ring,color
    w,h,d=dimensions;position=io.get('position')
    if position not in ('top','front_bottom','front_right','left_front'):return []
    normal='top' if position=='top' else 'left' if position=='left_front' else 'front'
    center=(0,h/2+.25,d*.32) if normal=='top' else (-w/2-.25,-h*.32,d*.27) if normal=='left' else (w*.27,-h*.40 if position=='front_bottom' else h*.26,d/2+.25)
    if position=='front_bottom' and 'angular_glass_corner' in case.get('features',()):
        cut=min(w*.23,d*.18);normal='corner';center=(-w/2+cut/2,-h*.41,d/2-cut/2)
    ports=[]
    for kind in ('usb_a','usb_c','audio','buttons'):
        count=io.get(kind)
        if type(count) is int and 0<=count<=8:ports.extend([kind]*count)
    total=sum(17 if kind=='usb_a' else 13 if kind=='usb_c' else 10 for kind in ports)
    cursor=-total/2;result=[]
    for kind in ports:
        pitch=17 if kind=='usb_a' else 13 if kind=='usb_c' else 10;at=cursor+pitch/2;cursor+=pitch
        def part(name,vertices,tone,local=(0,0,0)):
            values=_translate(vertices,(at+local[0],local[1],local[2]))
            result.append(Mesh('case-io-'+kind+'-'+name,_plane(values,center,normal),tone,component='case'))
        dark=color('#111b23');metal=color('#93a2aa');gold=color('#bc975a')
        if kind in ('usb_a','usb_c'):
            pw,ph=(12.5,5.5) if kind=='usb_a' else (8.8,3.5)
            part('well',chamfer_box(pw+.8,ph+.8,.5,.15),dark)
            if kind=='usb_c':part('rim',rounded_frame(pw,ph,.45,1),metal,(0,0,.3))
            else:
                for sign in (-1,1):
                    part('rim',chamfer_box(pw+1,.55,1,.12),metal,(0,sign*(ph+.55)/2,.3))
                    part('rim',chamfer_box(.55,ph,1,.12),metal,(sign*(pw+.55)/2,0,.3))
            part('tongue',box(pw*.75,.65,.7),color('#344858'),(0,-ph*.12,.45))
            for pin in range(4 if kind=='usb_a' else 5):
                part('contact',box(.35,.35,.6),gold,(-pw*.25+pin*pw*.5/(3 if kind=='usb_a' else 4),0,.7))
        else:
            radius=1.75 if kind=='audio' else 2.7
            part('rim',ring(radius+.4,radius,.65,16),metal)
            part('inset',ring(radius,0,.4,16),dark if kind=='audio' else color('#647583'),(0,0,.05))
    # Repeated socket rims and contact pads share draw ranges, not one draw
    # call per small contact. Positions are already baked on the case surface.
    batches={}
    for mesh in result:batches.setdefault((mesh.name,mesh.color),[]).extend(mesh.vertices)
    return [Mesh(name,tuple(vertices),tone,component='case') for (name,tone),vertices in batches.items()]


def enrich_case(meshes,dimensions,case,level='balanced'):
    """Replace crude case surfaces and append bounded batched mechanical detail."""
    if level=='eco':
        # A lower detail level may simplify machining, but a source-known
        # physical connector must remain present if cables attach to it.
        details=case.get('exterior_details') or {};io=details.get('io') if isinstance(details,dict) else None
        ports=_port_meshes(io,dimensions,case) if isinstance(io,dict) else ()
        return tuple((*meshes,*ports))
    from assembly_geometry import Mesh,box,ring,color
    w,h,d=dimensions;close=level=='close';result=[];batches={}
    def batch(name,vertices,tone,position=(0,0,0),component='case'):
        key=(name,tone,component);batches.setdefault(key,[]).extend(_translate(vertices,position))
    bevel_names=('case-upright','case-width-rail','case-depth-rail','case-foot','case-right','case-back',
        'front-panel','left-panel','left-glass','front-glass','top-glass','top-panel','front-slat',
        'external-frame-upright','carry-handle','wood-front','front-diagonal','glass-standoff')
    mesh_surfaces={}
    for mesh in meshes:
        if mesh.name in ('front-vent','left-mesh-vent'):
            mesh_surfaces.setdefault(mesh.name,[]).append(mesh);continue
        if mesh.name in ('front-grid-column','front-triangle-line'):continue
        if mesh.component in ('case','panel') and mesh.name.startswith(bevel_names) and len(mesh.vertices)==216:
            if all(sum(abs(mesh.vertices[n+a])>.00001 for a in (3,4,5))==1 for n in range(0,216,6)):
                bounds=[(min(mesh.vertices[a::6]),max(mesh.vertices[a::6])) for a in range(3)]
                size=[high-low for low,high in bounds]
                if all(abs(low+high)<1e-6 for low,high in bounds):
                    mesh=replace(mesh,vertices=chamfer_box(*size,bevel=min(.85,min(size)*.15)))
        result.append(mesh)
    # Real perforation spacing replaces the old sparse, blind-like rails.
    # All bars of one panel are batched, so denser detail adds no draw loop.
    for name,rows in mesh_surfaces.items():
        left=name=='left-mesh-vent';first=rows[0]
        center_y=(min(row.position[1] for row in rows)+max(row.position[1] for row in rows))/2
        panel_height=max(row.position[1] for row in rows)-min(row.position[1] for row in rows)
        span=(max(first.vertices[2::6])-min(first.vertices[2::6])) if left else (max(first.vertices[0::6])-min(first.vertices[0::6]))
        pitch=8. if close else 12.;across=max(4,min(70,round(span/pitch)));vertical=max(6,min(90,round(panel_height/pitch)))
        tone=color(case.get('color'),'#4d5965');component='panel' if left else 'case'
        for index in range(vertical+1):
            at=-panel_height/2+index*panel_height/vertical
            size=(1.4,1.6,span) if left else (span,1.6,1.4)
            pos=(first.position[0],center_y+at,0) if left else (0,center_y+at,first.position[2])
            batch('case-perforation',box(*size),tone,pos,component)
        triangular=not left and any(flag in case.get('features',()) for flag in ('triangular_front_mesh','front_triangle_grid'))
        if triangular:
            for slope in (-math.sqrt(3),math.sqrt(3)):
                reach=panel_height/2+abs(slope)*span/2
                for index in range(-min(90,math.ceil(reach/pitch)),min(90,math.ceil(reach/pitch))+1):
                    offset=index*pitch;points=[]
                    for x in (-span/2,span/2):
                        y=slope*x+offset
                        if -panel_height/2<=y<=panel_height/2:points.append((x,y))
                    for y in (-panel_height/2,panel_height/2):
                        x=(y-offset)/slope
                        if -span/2<=x<=span/2:points.append((x,y))
                    if len(points)<2:continue
                    a,b=points[0],max(points[1:],key=lambda p:math.dist(points[0],p))
                    length=math.dist(a,b)
                    if length<.1:continue
                    angle=math.atan2(b[1]-a[1],b[0]-a[0]);co,si=math.cos(angle),math.sin(angle);values=[]
                    vertices=box(length,1.3,1.4)
                    for n in range(0,len(vertices),6):
                        for axis in (0,3):
                            x,y,z=vertices[n+axis:n+axis+3];values.extend((co*x-si*y,si*x+co*y,z))
                    batch('case-perforation',tuple(values),tone,((a[0]+b[0])/2,center_y+(a[1]+b[1])/2,first.position[2]),component)
        else:
            for index in range(across+1):
                at=-span/2+index*span/across
                size=(1.4,panel_height,1.6) if left else (1.6,panel_height,1.4)
                pos=(first.position[0],center_y,at) if left else (at,center_y,first.position[2])
                batch('case-perforation',box(*size),tone,pos,component)
    metal=color('#8b9ba5');dark=color('#202b34')
    # Folded return lips and spaced rear chassis fasteners are references, not
    # invented visible screw mounts on tool-free retail glass panels.
    for x in (-w*.455,w*.455):
        batch('case-rear-fold',chamfer_box(3,h*.90,5,.4),metal,(x,0,-d/2+2.5))
        for y in (-h*.36,0,h*.36):
            batch('case-rear-fastener',ring(2.1,.7,1.1,12),metal,(x,y,-d/2-.2))
            batch('case-rear-fastener-slot',box(2.7,.45,1.2),dark,(x,y,-d/2-.85))
    # Existing source-backed exposed glass standoffs get actual annular ends.
    if 'side_glass_standoffs' in case.get('features',()):
        for y in (-h*.37,h*.37):
            for z in (-d*.37,d*.37):
                values=_plane(ring(4.2,1.5,1.1,16),(-w/2-.3,y,z),'left')
                batch('case-standoff-end',values,metal,component='panel')
    for (name,tone,component),vertices in batches.items():
        if vertices:result.append(Mesh(name,tuple(vertices),tone,component=component))
    details=case.get('exterior_details') or {};io=details.get('io') if isinstance(details,dict) else None
    if isinstance(io,dict):result.extend(_port_meshes(io,dimensions,case))
    return tuple(result)
