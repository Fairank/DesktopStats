"""Bounded original mechanical detail, never a claimed electrical PCB layout.

Exact product envelopes, connector counts and DDR key dimensions come from the
existing reviewed catalog. Fin sampling, screws, chip packages and motherboard
placement are schematic reference construction, not a scan of a retail PCB.
All work is static at a scene change; no hardware, network or animation state.
"""
from dataclasses import replace
import math

LEVELS=('eco','balanced','close')
TRIANGLE_BUDGETS={'eco':30000,'balanced':40000,'close':80000}


def detail_level(value):return value if isinstance(value,str) and value in LEVELS else 'balanced'


def component_level(spec,component):
    level=detail_level(spec.get('detail_level'))
    focus=spec.get('detail_focus')
    return 'balanced' if level=='close' and focus in ('case','cpu','gpu','memory','board') and focus!=component else level


def _tri(out,a,b,c):
    ab=tuple(b[n]-a[n] for n in range(3));ac=tuple(c[n]-a[n] for n in range(3))
    normal=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
    length=math.sqrt(sum(v*v for v in normal))
    if length<1e-10:return
    normal=tuple(v/length for v in normal)
    for point in (a,b,c):out.extend((*point,*normal))


def _quad(out,a,b,c,d):_tri(out,a,b,c);_tri(out,a,c,d)


def translated(vertices,position):
    out=[]
    for n in range(0,len(vertices),6):out.extend((*(vertices[n+k]+position[k] for k in range(3)),*vertices[n+3:n+6]))
    return tuple(out)


def _area(poly):return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,(*poly[1:],poly[0])))/2


def _clip(poly,a,b,inside):
    if not poly:return ()
    def side(p):return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
    def keep(v):return v>=-1e-8 if inside else v<=1e-8
    out=[];previous=poly[-1];old=side(previous)
    for point in poly:
        current=side(point)
        if keep(current)!=keep(old):
            ratio=old/(old-current)
            out.append(tuple(previous[n]+ratio*(point[n]-previous[n]) for n in range(2)))
        if keep(current):out.append(tuple(point))
        previous,old=point,current
    result=[]
    for point in out:
        if not result or math.dist(point,result[-1])>1e-7:result.append(point)
    if len(result)>1 and math.dist(result[0],result[-1])<1e-7:result.pop()
    return tuple(result) if len(result)>=3 and abs(_area(result))>1e-7 else ()


def _subtract(poly,hole):
    if not poly:return ()
    if (max(p[0] for p in poly)<min(p[0] for p in hole) or min(p[0] for p in poly)>max(p[0] for p in hole)
            or max(p[1] for p in poly)<min(p[1] for p in hole) or min(p[1] for p in poly)>max(p[1] for p in hole)):
        return (poly,)
    out=[];remaining=poly
    for a,b in zip(hole,(*hole[1:],hole[0])):
        outside=_clip(remaining,a,b,False)
        if outside:out.append(outside)
        remaining=_clip(remaining,a,b,True)
        if not remaining:break
    return tuple(out)


def _point_inside(point,poly):
    x,y=point;inside=False
    for a,b in zip(poly,(*poly[1:],poly[0])):
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:inside=not inside
    return inside


def circle(cx,cy,radius,segments=24):
    return tuple((cx+math.cos(n*math.tau/segments)*radius,cy+math.sin(n*math.tau/segments)*radius) for n in range(segments))


def chamfer_rect(width,height,corner=1.):
    x,y=width/2,height/2;c=min(corner,x*.4,y*.4)
    return ((-x+c,-y),(x-c,-y),(x,-y+c),(x,y-c),(x-c,y),(-x+c,y),(-x,y-c),(-x,-y+c))


def bevel_extrude(poly,depth,bevel=.5):
    """Preserve the outer silhouette while adding real sloped edge surfaces."""
    from assembly_geometry import extrude
    if len(poly)<3:return ()
    b=min(bevel,depth*.35);extent=[max(abs(p[n]) for p in poly) for n in range(2)]
    inner=tuple(tuple(v*(1-b/max(extent[n],b*2)) for n,v in enumerate(p)) for p in poly)
    caps=extrude(inner,depth);out=[]
    for n in range(0,len(caps),18):
        if abs(caps[n+5])>.999:out.extend(caps[n:n+18])
    for i,a in enumerate(poly):
        j=(i+1)%len(poly);c=poly[j];ia,ic=inner[i],inner[j]
        _quad(out,(*a,-depth/2+b),(*c,-depth/2+b),(*c,depth/2-b),(*a,depth/2-b))
        _quad(out,(*a,depth/2-b),(*c,depth/2-b),(*ic,depth/2),(*ia,depth/2))
        _quad(out,(*ia,-depth/2),(*ic,-depth/2),(*c,-depth/2+b),(*a,-depth/2+b))
    return tuple(out)


def perforated_plate(poly,holes,depth,*,segments=24):
    """Triangulated solid plate with actual open holes, not dark painted disks.

    Each convex hole is subtracted from cap triangles using disjoint convex
    half-plane clips. Hole walls have depth; cap diagonals are not exposed.
    """
    from assembly_geometry import extrude
    hole_polys=[]
    for hole in holes[:24]:
        points=circle(*hole,segments) if len(hole)==3 and type(hole[0]) in (int,float) else tuple(hole)
        if len(points)>=3:hole_polys.append(points if _area(points)>0 else tuple(reversed(points)))
    caps=extrude(poly,depth);pieces=[]
    for n in range(0,len(caps),18):
        if caps[n+5]>.999:pieces.append(tuple(tuple(caps[n+k:n+k+2]) for k in (0,6,12)))
    for hole in hole_polys:
        pieces=[piece for poly_piece in pieces for piece in _subtract(poly_piece,hole)]
        if len(pieces)>10000:raise ValueError('Mechanical plate exceeded its bounded partition budget')
    out=[];z=depth/2
    for piece in pieces:
        if _area(piece)<0:piece=tuple(reversed(piece))
        for n in range(1,len(piece)-1):
            a,b,c=piece[0],piece[n],piece[n+1]
            _tri(out,(*a,z),(*b,z),(*c,z));_tri(out,(*c,-z),(*b,-z),(*a,-z))
    for a,b in zip(poly,(*poly[1:],poly[0])):_quad(out,(*a,-z),(*b,-z),(*b,z),(*a,z))
    for hole in hole_polys:
        for a,b in zip(hole,(*hole[1:],hole[0])):
            if _point_inside(tuple((a[n]+b[n])/2 for n in range(2)),poly):
                _quad(out,(*b,-z),(*a,-z),(*a,z),(*b,z))
    return tuple(out)


def _perforated_wall(a,b,ia,ib,depth,holes):
    """A genuinely open shell edge; coordinates are edge fraction and depth.

    The inner and outer silhouette edges may differ in length. Mapping their
    matching fractions preserves the original envelope and recomputes normals
    after that mapping, rather than treating it as a rigid normal transform.
    """
    plate=perforated_plate(((0.,-depth/2),(1.,-depth/2),(1.,depth/2),(0.,depth/2)),holes,1.)
    out=[]
    for n in range(0,len(plate),18):
        points=[]
        for offset in (0,6,12):
            fraction,z,layer=plate[n+offset:n+offset+3]
            inside=tuple(ia[k]+(ib[k]-ia[k])*fraction for k in range(2))
            outside=tuple(a[k]+(b[k]-a[k])*fraction for k in range(2))
            points.append((*(inside[k]+(outside[k]-inside[k])*(layer+.5) for k in range(2)),z))
        _tri(out,*points)
    return tuple(out)


def _clip_plane(poly,normal,offset,inside):
    """Clip a convex 3-D face, retaining its original plane and winding."""
    if not poly:return ()
    def side(point):return sum(normal[k]*point[k] for k in range(3))+offset
    def keep(value):return value>=-1e-8 if inside else value<=1e-8
    out=[];previous=poly[-1];old=side(previous)
    for point in poly:
        current=side(point)
        if keep(current)!=keep(old):
            ratio=old/(old-current)
            out.append(tuple(previous[k]+ratio*(point[k]-previous[k]) for k in range(3)))
        if keep(current):out.append(point)
        previous,old=point,current
    return tuple(out) if len(out)>=3 else ()


def clear_port_tunnels(vertices,holes,length,tunnel_depth=6.5):
    """Subtract bounded connector prisms from every overlapping shell facet.

    Port holes are in the bracket's world X/Y plane; this mesh still uses its
    canonical source U/V/depth frame. Rounded and chamfered end facets require
    the same clearance as the large end wall. The short schematic tunnel ends
    behind the recessed port housing, never at the far end of the GPU.
    """
    if not holes:return vertices
    low=-length/2-.01;high=-length/2+tunnel_depth;prisms=[]
    for hole in holes:
        cross=tuple((-x,-y) for x,y in hole)
        if _area(cross)<0:cross=tuple(reversed(cross))
        planes=[((1.,0.,0.),-low),((-1.,0.,0.),high)]
        for a,b in zip(cross,(*cross[1:],cross[0])):
            dv,dz=b[0]-a[0],b[1]-a[1]
            planes.append(((0.,-dz,dv),dz*a[0]-dv*a[1]))
        prisms.append((cross,planes))
    out=[]
    for n in range(0,len(vertices),18):
        triangle=tuple(tuple(vertices[n+offset:n+offset+3]) for offset in (0,6,12))
        if min(p[0] for p in triangle)>high or max(p[0] for p in triangle)<low:
            out.extend(vertices[n:n+18]);continue
        pieces=[triangle]
        for cross,planes in prisms:
            if (max(p[1] for p in triangle)<min(p[0] for p in cross)
                    or min(p[1] for p in triangle)>max(p[0] for p in cross)
                    or max(p[2] for p in triangle)<min(p[1] for p in cross)
                    or min(p[2] for p in triangle)>max(p[1] for p in cross)):continue
            kept=[]
            for piece in pieces:
                remaining=piece
                for normal,offset in planes:
                    outside=_clip_plane(remaining,normal,offset,False)
                    if outside:kept.append(outside)
                    remaining=_clip_plane(remaining,normal,offset,True)
                    if not remaining:break
            pieces=kept
            if len(pieces)>4096:raise ValueError('Connector clearance exceeded its bounded partition budget')
        for piece in pieces:
            for index in range(1,len(piece)-1):_tri(out,piece[0],piece[index],piece[index+1])
    return tuple(out)


def hollow_cover(poly,holes,depth,*,segments=24,open_front=False,edge_windows=None,edge_recesses=None):
    plate=min(2.2,depth*.12);front=depth/2
    extent=[max(abs(p[n]) for p in poly) for n in range(2)]
    face=tuple(tuple(v*(1-.55/max(extent[n],5)) for n,v in enumerate(p)) for p in poly)
    recess=min(.5,depth*.06)
    out=[] if open_front else list(translated(perforated_plate(face,holes,plate,segments=segments),(0,0,front-recess-plate/2)))
    inner=tuple(tuple(v*(1-1.5/max(extent[n],5)) for n,v in enumerate(p)) for p in poly)
    for i,a in enumerate(poly):
        j=(i+1)%len(poly);b=poly[j];ia,ib=inner[i],inner[j]
        windows=(edge_windows or {}).get(i)
        if windows:
            shift=(edge_recesses or {}).get(i,0.)
            if shift:
                inward=tuple((ia[k]+ib[k]-a[k]-b[k])/2 for k in range(2))
                scale=shift/math.hypot(*inward);delta=tuple(v*scale for v in inward)
                moved=lambda point:tuple(point[k]+delta[k] for k in range(2))
                ma,mb,mia,mib=map(moved,(a,b,ia,ib))
                out.extend(_perforated_wall(ma,mb,mia,mib,depth,windows))
                # The cooler wall sits behind the expansion bracket. Narrow
                # return lips keep its unchanged quoted exterior silhouette.
                _quad(out,(*a,front),(*b,front),(*mb,front),(*ma,front))
                _quad(out,(*ma,-front),(*mb,-front),(*b,-front),(*a,-front))
                _quad(out,(*a,-front),(*ma,-front),(*ma,front),(*a,front))
                _quad(out,(*mb,-front),(*b,-front),(*b,front),(*mb,front))
            else:out.extend(_perforated_wall(a,b,ia,ib,depth,windows))
        else:
            _quad(out,(*a,-depth/2),(*b,-depth/2),(*b,front),(*a,front))
            _quad(out,(*ia,front-recess-plate),(*ib,front-recess-plate),(*ib,-depth/2),(*ia,-depth/2))
            _quad(out,(*ia,-depth/2),(*ib,-depth/2),(*b,-depth/2),(*a,-depth/2))
        _quad(out,(*a,front),(*b,front),(*face[j],front-recess),(*face[i],front-recess))
    return tuple(out)


def _extent(mesh):
    return tuple(max(mesh.vertices[n::6])-min(mesh.vertices[n::6]) for n in range(3))


def _boxes(rows):
    from assembly_geometry import box
    return tuple(v for size,position in rows for v in translated(box(*size),position))


def _screws(points,radius=1.5):
    from assembly_geometry import ring,box
    bodies=[];slots=[]
    for point in points:
        bodies.extend(translated(ring(radius,0,.7,segments=12),point))
        slots.extend(translated(box(radius*1.2,.34,.12),(point[0],point[1],point[2]+.4)))
    return tuple(bodies),tuple(slots)


def _port_shape(kind,width,height):
    x,y=width/2,height/2
    if kind in ('hdmi','mini_hdmi'):return ((-x*.72,-y),(x*.72,-y),(x,y*.1),(x,y),(-x,y),(-x,-y*.1))
    if kind in ('displayport','mini_displayport'):return ((-x,-y),(x,-y),(x,y*.5),(x*.75,y),(-x,y))
    if kind in ('dvi','vga'):return ((-x*.86,-y),(x*.86,-y),(x,y),(-x,y))
    if kind=='usb_c':return chamfer_rect(width,height,min(height*.45,2.))
    if kind=='tv_out':return circle(0,0,min(width,height)/2,16)
    return chamfer_rect(width,height,.5)


def _gpu_detail(meshes,spec,level):
    from assembly_geometry import Mesh,color,gpu_plane,ring,unit_polygon
    gpu=spec.get('gpu') or {};appearance=gpu.get('appearance') or {};facts=appearance.get('board_details') or {}
    shroud=next((m for m in meshes if m.name=='gpu-shroud'),None)
    if shroud is None:return tuple(meshes),dict(heatsink_fins=0,ports=0,layout_schematic=True)
    width,thickness,length=_extent(shroud);gx,gy,gz=shroud.position
    outer=unit_polygon(gpu.get('shell_polygon'),length,width) or chamfer_rect(length,width,min(7.,width*.07))
    openings=[m for m in meshes if m.name=='gpu-fan-opening' and m.position[1]<gy]
    holes=[(m.position[2]-gz,-(m.position[0]-gx),max(abs(v) for v in m.vertices[0::6])*1.005) for m in openings]
    segments=32 if level=='close' else 20
    revised=[];detail=[];dark=color('#202a32');metal=color('#acb8bf');gold=color('#c5a257');pcb=color('#284b48')
    def add(name,vertices,tone,position=(gx,gy,gz)):
        if vertices:detail.append(Mesh(name,vertices,tone,position,'gpu'))
    backplate=facts.get('backplate');cover_index=0
    observed_rear=(appearance.get('id')=='asus-astral-5090' and appearance.get('fan_count')==4 and backplate is True)
    rear_u=(589.-45.)/659.;rear_v=(370.-238.)/256.
    rear_radius=min(105./659.*length,105./256.*width)
    rear_hole=((rear_u-.5)*length,(.5-rear_v)*width,rear_radius*1.005)
    for mesh in meshes:
        if mesh.name=='gpu-cover-panel':
            rows=gpu.get('detail_polygons') or ()
            row=rows[cover_index] if cover_index<len(rows) else None;cover_index+=1
            points=row.get('points') if isinstance(row,dict) else row
            polygon=unit_polygon(points,length,width,margin=.3)
            if polygon:
                mesh=replace(mesh,vertices=gpu_plane(perforated_plate(polygon,holes,.3,segments=segments)),
                             position=(gx,gy-thickness/2+.2,gz))
        elif mesh.name=='gpu-pcb':
            mesh=replace(mesh,position=(gx,gy+thickness/2-3.3,gz))
            if observed_rear:
                mesh=replace(mesh,vertices=gpu_plane(perforated_plate(chamfer_rect(length*.96,width*.94,1.),(rear_hole,),1.6,segments=segments)))
        elif mesh.name=='gpu-backplate':
            if backplate is not True:continue
            back=perforated_plate(chamfer_rect(length*.99,width*.98,3.),(rear_hole,),2.,segments=segments) if observed_rear else bevel_extrude(chamfer_rect(length*.94,width*.96,3.),2.,.5)
            mesh=replace(mesh,vertices=gpu_plane(back),
                         position=(gx,gy+thickness/2-1.,gz))
        elif mesh.name in ('gpu-bracket','gpu-gold-contacts') or mesh.name.startswith('gpu-reference-port'):continue
        elif mesh.name.startswith('gpu-fan-'):
            rear=mesh.position[1]>gy;shift=-7.4 if rear else 3.9
            mesh=replace(mesh,position=(mesh.position[0],mesh.position[1]+shift,mesh.position[2]))
            if mesh.name=='gpu-fan-recess':
                radius=max(abs(v) for v in mesh.vertices[0::6])
                mesh=replace(mesh,vertices=gpu_plane(ring(radius,radius*.82,.5,segments=24),rear))
        revised.append(mesh)
    if observed_rear:
        from assembly_geometry import fan_rotor
        center=(gx+(rear_v-.5)*width,gy+thickness/2-2.4,gz+(rear_u-.5)*length)
        # The official orthographic rear photograph establishes seven broad,
        # swept blades and placement. It cannot establish rotation direction,
        # individual RPM or exact manufacturing dimensions. Remain static.
        profile=dict(blades=7,shape='wide',hub_ratio=.31,outer_ring=False,direction=1)
        add('detail-gpu-rear-observed-blades',gpu_plane(fan_rotor(profile,rear_radius),True),color('#333d43'),center)
        add('detail-gpu-rear-observed-frame',gpu_plane(ring(rear_radius,rear_radius*.93,1.7,segments=32),True),metal,
            (center[0],gy+thickness/2-1.0,center[2]))
        add('detail-gpu-rear-observed-hub',gpu_plane(ring(rear_radius*.31,0,2.7,segments=24),True),dark,
            (center[0],center[1]+.8,center[2]))
    dimensions=facts.get('dimensions_mm') or {}
    known=all(type(dimensions.get(key)) in (int,float) and dimensions[key]>0 for key in ('length','height','thickness'))
    known=known or gpu.get('dimensions_verified') is True and all(type(gpu.get(key)) in (int,float) and gpu[key]>0 for key in ('length_mm','width_mm','thickness_mm'))
    fin_count=0
    if known and appearance.get('style') in ('gpu_axial','gpu_hybrid','gpu_blower') and appearance.get('fan_count')!=0:
        fin_count=80 if level=='close' else 36
        fins=[((width*.84,thickness*.60,.38),(0,1.,-length*.41+n*length*.82/(fin_count-1))) for n in range(fin_count)]
        add('detail-gpu-heatsink-fins',_boxes(fins),metal)
    # Layer edges are reference geometry; the catalog does not establish PCB
    # length, copper-layer count, GPU die or memory-chip positions.
    layers=[]
    for side in (-1,1):
        layers.append(((.22,.25,length*.94),(side*width*.47,thickness/2-3.3,0)))
    add('detail-gpu-pcb-stack-edge',_boxes(layers),color('#bd9c62'))
    bus=(facts.get('host_interface') or {}).get('bus')
    contact_count=0
    if bus in ('pcie','agp'):
        contact_count=48 if level=='close' else 28
        span=min(89. if bus=='pcie' else 81.,length*.78);pitch=span/contact_count
        start=-length/2+15.
        pads=[((7.5,.20,pitch*.68),(width*.48-5.2,thickness/2-3.22,start+(n+.5)*pitch)) for n in range(contact_count)]
        add('detail-gpu-separated-edge-contacts',_boxes(pads),gold)
    ports=[]
    supported={'displayport':(15.5,7.),'mini_displayport':(8.,5.5),'hdmi':(15.,6.),'mini_hdmi':(10.,4.5),
               'dvi':(25.,9.),'vga':(18.,9.),'usb_c':(9.,4.),'tv_out':(8.,8.)}
    for group in facts.get('ports') or ():
        if isinstance(group,dict) and group.get('type') in supported and type(group.get('count')) is int and 0<group['count']<=6:
            ports.extend([group['type']]*group['count'])
    ports=ports[:12];bracket_w=min(width,122.);bracket_h=max(14.,thickness-1.2)
    rows=[];row=[];occupied=0.
    for port in ports:
        pw,ph=supported[port]
        if row and occupied+pw+4>bracket_w-5:rows.append(row);row=[];occupied=0.
        row.append((port,pw,ph));occupied+=pw+4
    if row:rows.append(row)
    port_holes=[];housings=[];port_boxes=[]
    for ri,row in enumerate(rows):
        total=sum(pw for _,pw,_ in row)+4*(len(row)-1);cursor=-total/2
        cy=(ri-(len(rows)-1)/2)*12.
        for port,pw,ph in row:
            cx=cursor+pw/2;cursor+=pw+4
            polygon=_port_shape(port,pw,ph);hole=tuple((x+cx,y+cy) for x,y in polygon)
            port_holes.append(hole)
            frame=perforated_plate(chamfer_rect(pw+2,ph+2,.7),(polygon,),1.2,segments=16)
            add('gpu-reference-port-'+port,frame,metal,(gx+cx,gy+cy,gz-length/2+1.0))
            port_boxes.append(((pw,ph,3.),(cx,cy,-length/2+3.7)))
    vents=[]
    for n in range(8 if level=='close' else 5):
        cx=-bracket_w*.39+n*bracket_w*.78/(7 if level=='close' else 4)
        cy=-bracket_h*.37;slot=tuple((x+cx,y+cy) for x,y in chamfer_rect(2.2,max(3.,min(8.,bracket_h*.18)),.6))
        if not any(abs(cx-sum(x for x,_ in hole)/len(hole))<14 and abs(cy-sum(y for _,y in hole)/len(hole))<8 for hole in port_holes):vents.append(slot)
    add('gpu-bracket',perforated_plate(chamfer_rect(bracket_w,bracket_h,1.),(*port_holes,*vents),1.2),metal,
        (gx,gy,gz-length/2+.6))
    add('detail-gpu-port-recesses',_boxes(port_boxes),dark)
    # A bracket hole needs clearance through the cooler's end wall too. The
    # port layout is reference placement of documented counts; both layers use
    # exactly the same apertures rather than hiding them behind a second cap.
    edge_windows={};edge_recesses={}
    for i,a in enumerate(outer):
        b=outer[(i+1)%len(outer)];windows=[]
        if abs(a[0]+length/2)<1e-5 and abs(b[0]+length/2)<1e-5 and abs(b[1]-a[1])>1e-5:
            for aperture in (*port_holes,*vents):
                window=tuple(((-x-a[1])/(b[1]-a[1]),-y) for x,y in aperture)
                windows.append(window if _area(window)>0 else tuple(reversed(window)))
            if port_holes:edge_recesses[i]=1.4
        # The Astral official outer-side photograph shows exposed fins between
        # the front rail and rear PCB/backplate. These conservative opening
        # ratios are photo-observed schematic construction, never CAD/mm facts.
        if observed_rear and abs(a[1]-width/2)<1e-5 and abs(b[1]-width/2)<1e-5:
            windows.append(((.04,-thickness*.38),(.96,-thickness*.38),
                            (.96,thickness*.23),(.04,thickness*.23)))
        if windows:edge_windows[i]=tuple(windows)
    body=hollow_cover(outer,holes,thickness,segments=segments,
        open_front=appearance.get('fan_count')==0,edge_windows=edge_windows,edge_recesses=edge_recesses)
    body=gpu_plane(clear_port_tunnels(body,port_holes,length))
    revised=[replace(mesh,vertices=body) if mesh.name=='gpu-shroud' else mesh for mesh in revised]
    # Only a documented backplate receives reference fasteners. They do not
    # pretend to locate the real cooler's exact screw pattern.
    if backplate is True:
        screw_points=[(x*length*.36,y*width*.31,0) for x in (-1,1) for y in (-1,1)]
        caps,slots=_screws(screw_points,1.5)
        add('detail-gpu-backplate-fasteners',gpu_plane(caps,True),metal,(gx,gy+thickness/2-.6,gz))
        add('detail-gpu-fastener-slots',gpu_plane(slots,True),dark,(gx,gy+thickness/2-.6,gz))
    return tuple((*revised,*detail)),dict(heatsink_fins=fin_count,ports=len(ports),port_types=tuple(ports),
        connector_pads=contact_count,backplate=backplate,layout_schematic=True,pcb_dimensions_schematic=True,
        fin_count_is_sampling=True,ports_count_documented=bool(ports),connector_pad_count_is_sampling=True,
        observed_rear_fans=1 if observed_rear else 0,rear_blades=7 if observed_rear else None,
        rear_rotation_direction='unverified' if observed_rear else None,rear_independent_tachometer=False,
        rear_geometry='official_photo_observed_schematic' if observed_rear else None,
        rear_photo_source='https://dlcdnwebimgs.asus.com/gain/71E25C26-172B-4B3B-BF80-9CD8FCAB3DA6/w1000/h732' if observed_rear else None,
        rear_photo_ratios=dict(center_u=rear_u,center_v=rear_v,radius_u=105./659.,radius_v=105./256.) if observed_rear else None,
        pcb_pass_through_cutaway_schematic=observed_rear,
        port_shell_clearance=bool(port_holes),port_shell_recess_mm=1.4 if port_holes else 0.,
        port_clearance_tunnel_mm=6.5 if port_holes else 0.,observed_side_fin_window=observed_rear,
        side_window_geometry='official_photo_observed_schematic' if observed_rear else None,
        side_window_source='https://dlcdnwebimgs.asus.com/gain/B625A69F-626B-4451-B08B-DE635451FA0E/w1000/h732' if observed_rear else None,
        side_window_ratios=dict(edge_fraction_min=.04,edge_fraction_max=.96,
            depth_min=-.38,depth_max=.23) if observed_rear else None)


def _memory_detail(meshes,spec,level):
    from assembly_geometry import Mesh,color,memory_plane,rotate_vertices,unit_polygon
    memory=spec.get('memory') or {};modules=memory.get('modules') or ();index=0;out=[];extras=[];records=[]
    pcbs=[m for m in meshes if m.name=='ram-pcb']
    for mesh in meshes:
        if mesh.name not in ('ram-pcb','ram-spreader'):out.append(mesh);continue
        if mesh.name=='ram-pcb':
            index=pcbs.index(mesh);module=dict(memory)
            if index<len(modules) and isinstance(modules[index],dict):module.update(modules[index])
        else:
            # Covers follow their retained PCB center, even when some modules
            # are bare and therefore have no spreader of their own.
            index=min(range(len(pcbs)),key=lambda n:math.dist(pcbs[n].position,mesh.position));module=dict(memory)
            if index<len(modules) and isinstance(modules[index],dict):module.update(modules[index])
        appearance=module.get('appearance') or {};facts=appearance.get('board_details') or {}
        short=module.get('short_form') is True or module.get('style',appearance.get('style'))=='sodimm'
        pcb=pcbs[index];extent=_extent(pcb);length=extent[2] if short else extent[1];height=extent[1] if short else extent[0]
        orient=(lambda vertices:rotate_vertices(vertices,'left')) if short else memory_plane
        poly=unit_polygon(module.get('pcb_polygon' if mesh.name=='ram-pcb' else 'case_polygon'),length,height,margin=.3)
        if not poly:
            if mesh.name=='ram-spreader':
                cover_extent=_extent(mesh)
                cover_length=cover_extent[2] if short else cover_extent[1]
                cover_height=cover_extent[1] if short else cover_extent[0]
                poly=chamfer_rect(cover_length,cover_height,1.2)
            else:
                ratio=facts.get('notch_ratio');notch_width=facts.get('notch_width_ratio');notch_depth=facts.get('notch_depth_ratio')
                if all(type(v) in (int,float) for v in (ratio,notch_width,notch_depth)):
                    key=-length/2+ratio*length;half=notch_width*length/2;bottom=-height/2;top=bottom+notch_depth*height
                    poly=((-length/2,bottom),(key-half,bottom),(key-half,top),(key+half,top),(key+half,bottom),
                          (length/2,bottom),(length/2,height/2),(-length/2,height/2))
                else:poly=chamfer_rect(length,height,.6)
        out.append(replace(mesh,vertices=orient(bevel_extrude(poly,1.2 if mesh.name=='ram-pcb' else 3.2,.12 if mesh.name=='ram-pcb' else .45))))
        if mesh.name!='ram-pcb':continue
        ratio=facts.get('notch_ratio');ratio=ratio if type(ratio) in (int,float) and 0<ratio<1 else None
        pins=facts.get('pins');pins=pins if type(pins) is int and 1<pins<=400 else None
        count=min(144,pins//2) if level=='close' and pins else 48 if level=='close' else 32
        gap=(facts.get('notch_width_ratio') or 0)*length if ratio is not None else 0
        key=-length/2+ratio*length if ratio is not None else 0
        segments=((-length/2+1.2,key-gap/2-.20),(key+gap/2+.20,length/2-1.2)) if ratio is not None else ((-length/2+1.2,length/2-1.2),)
        pads=[];actual_pads=0
        for left,right in segments:
            quantity=max(1,round(count*(right-left)/(length-2.4)))
            pitch=(right-left)/quantity
            for n in range(quantity):
                for sign in (-1,1):pads.append(((pitch*.68,2.8,.12),(left+(n+.5)*pitch,-height/2+1.5,sign*.66)))
            actual_pads+=quantity*2
        extras.append(Mesh('detail-ram-separated-contacts',orient(_boxes(pads)),color('#c7a45a'),mesh.position,'memory'))
        # These package samples illustrate a bare memory module. They are not
        # used to claim actual IC count, rank, capacity, manufacturer or routing.
        bare=module.get('heat_spreader') is False or appearance.get('shroud')=='bare'
        if bare:
            quantity=4 if short else 8;package_width=min(12.,length*.78/quantity)
            packages=[];leads=[]
            for n in range(quantity):
                cx=-length*.39+(n+.5)*length*.78/quantity
                packages.extend(translated(bevel_extrude(chamfer_rect(package_width,9.,.65),1.4,.25),(cx,2.,1.4)))
                for side in (-1,1):leads.append(((package_width*.92,.35,.35),(cx,2+side*4.7,1.0)))
            extras.append(Mesh('detail-ram-reference-ic-packages',orient(tuple(packages)),color('#2a3339'),mesh.position,'memory'))
            extras.append(Mesh('detail-ram-reference-package-leads',orient(_boxes(leads)),color('#99a2a5'),mesh.position,'memory'))
        records.append(dict(short_form=short,nominal_pins=pins,contact_samples=actual_pads,
                            key_ratio=ratio,ic_layout_schematic=True,contact_samples_are_not_pin_count=True))
    return tuple((*out,*extras)),records


def _board_detail(meshes,spec,level):
    from assembly_geometry import Mesh,color,rotate_vertices
    base=next((m for m in meshes if m.name=='motherboard-reference'),None)
    if base is None:return tuple(meshes),{}
    board_w=_extent(base)[2];board_h=_extent(base)[1];bx,by,bz=base.position
    board=spec.get('board') or {};known=board.get('detail_profile')=='asus_z790_a_d4'
    dark=color('#252e35');metal=color(board.get('heatsink_color'),'#a5afb5') if known else color('#a5afb5')
    copper=color('#bc9c61');out=[];extras=[]
    def add(name,vertices,tone,position=(bx,by,bz)):
        if vertices:extras.append(Mesh(name,vertices,tone,position,'board'))
    holes=[(x*(board_w/2-7),y*(board_h/2-7),1.6) for x in (-1,1) for y in (-1,1)]
    if board_h>200:holes.extend((x*(board_w/2-7),0.,1.6) for x in (-1,1))
    board_plate=rotate_vertices(perforated_plate(chamfer_rect(board_w,board_h,1.),holes,1.6,segments=12),'left')
    for mesh in meshes:
        if mesh.name=='motherboard-reference':
            mesh=replace(mesh,vertices=board_plate,color=color(board.get('pcb_color'),'#242a2d') if known else mesh.color)
        elif mesh.name=='board-expansion-slot':
            _,slot_w,slot_length=_extent(mesh)
            pieces=[((1.1,slot_w,slot_length),(2.8,0,0)),((6.,1.1,slot_length),(0,-slot_w/2+.55,0)),
                    ((6.,1.1,slot_length),(0,slot_w/2-.55,0)),((6.,slot_w,1.2),(0,0,-slot_length/2+.6))]
            mesh=replace(mesh,vertices=_boxes(pieces))
            add('detail-board-pcie-contact-well',_boxes([((.25,slot_w*.65,slot_length*.88),(2.,0,0))]),copper,mesh.position)
            add('detail-board-pcie-latch',_boxes([((6.,slot_w+2,5.),(0,0,slot_length/2+1.5))]),dark,mesh.position)
        elif mesh.name in ('board-reference-vrm-top','board-reference-vrm-side'):
            sx,sy,sz=_extent(mesh);fins=[];count=16 if level=='close' else 8
            if sy<sz:
                fins=[((sx,sy,.65),(0,0,-sz*.46+n*sz*.92/(count-1))) for n in range(count)]
                fins.append(((2.,sy,sz),(sx/2-1,0,0)))
            else:
                fins=[((sx,.65,sz),(0,-sy*.46+n*sy*.92/(count-1),0)) for n in range(count)]
                fins.append(((2.,sy,sz),(sx/2-1,0,0)))
            mesh=replace(mesh,vertices=_boxes(fins),color=metal if known else mesh.color)
        out.append(mesh)
    pads=[]
    from assembly_geometry import ring
    for x,y,radius in holes:pads.extend(translated(ring(3.1,radius,.20,segments=16),(x,y,1.0)))
    add('detail-board-copper-mount-pads',rotate_vertices(tuple(pads),'left'),copper)
    cpu=next((m for m in meshes if m.name=='cpu-substrate'),None)
    if cpu is not None:
        _,ch,cw=_extent(cpu);_,cy,cz=cpu.position
        add('detail-board-retention-frame',_boxes([((3.2,2.2,cw+9),(-3.5,sign*(ch/2+3),0)) for sign in (-1,1)]),metal,(bx,cy,cz))
        add('detail-board-retention-hinge',_boxes([((3.8,ch+8,2.2),(-3.5,0,-cw/2-4))]),dark,(bx,cy,cz))
        add('detail-board-retention-lever',_boxes([((1.5,ch+6,1.5),(-5.,0,cw/2+4))]),metal,(bx,cy,cz))
    # Readable reference component groupings, with no asserted retail PCB map.
    packages=[];caps=[]
    for n in range(6 if level=='close' else 4):
        packages.append(((3.,7.,7.),(-3.,-board_h*.37+n*11,board_w*.38)))
    for n in range(8 if level=='close' else 5):
        caps.extend(translated(rotate_vertices(ring(2.1,0,5.,segments=10),'left'),(-4.,-board_h*.08+n*9,-board_w*.35)))
    add('detail-board-reference-small-packages',_boxes(packages),dark)
    add('detail-board-reference-capacitors',tuple(caps),metal)
    # Populate sockets only for drawn modules; do not infer unused DIMM slots.
    modules=[m for m in meshes if m.name=='ram-pcb'];slot_parts=[];slot_leads=[]
    memory=spec.get('memory') or {};module_rows=memory.get('modules') or ()
    target_slots=4 if known else len(modules)
    for index in range(target_slots):
        row=dict(memory)
        if index<len(module_rows) and isinstance(module_rows[index],dict):row.update(module_rows[index])
        appearance=row.get('appearance') or {};short=row.get('short_form') is True or row.get('style',appearance.get('style'))=='sodimm'
        module=modules[index] if index<len(modules) else modules[0] if modules else None
        extent=_extent(module) if module is not None else (31.25,133.35,1.2)
        mx,my,mz=module.position if module is not None else (bx-18.,cpu.position[1]-8 if cpu is not None else by+board_h*.25,bz+board_w*.25)
        if index>=len(modules):mz+=index*10
        if short:
            length=extent[2];slot_parts.extend([((3.5,3.5,length),(bx-3.0,my-extent[1]/2,mz))])
            continue
        length=extent[1]
        for side in (-1,1):slot_parts.append(((5.,length+4,1.1),(bx-3.,my,mz+side*1.7)))
        for sign in (-1,1):slot_parts.append(((6.,6.,5.),(bx-4.,my+sign*(length/2+2),mz)))
        slot_leads.append(((.3,length*.94,2.2),(bx-1.6,my,mz)))
    add('detail-board-populated-memory-sockets',_boxes(slot_parts),dark,position=(0,0,0))
    add('detail-board-memory-socket-contact-wells',_boxes(slot_leads),copper,position=(0,0,0))
    if known:
        # The exact profile establishes counts and finishes, not positions or
        # routing. Empty M.2 sockets/covers are not fabricated installed SSDs.
        pcie=[m for m in meshes if m.name=='board-expansion-slot']
        short_length=29.;position=(bx-6,by+board_h*.01,bz-board_w*.15)
        add('detail-board-pcie-x1',_boxes([((1.1,5,short_length),(2.8,0,0)),
            ((6.,1.1,short_length),(0,-1.95,0)),((6.,1.1,short_length),(0,1.95,0))]),dark,position)
        ys=sorted((m.position[1] for m in pcie),reverse=True)
        m2_ys=[ys[0]+28.,(ys[0]+ys[1])/2,(ys[1]+ys[2])/2,ys[2]-25.] if len(ys)>=3 else [by+board_h*v for v in (.05,-.12,-.28,-.40)]
        m2_parts=[];m2_posts=[]
        for n,yy in enumerate(m2_ys):
            m2_parts.append(((3.2,4.5,22.),(-3.,yy-by,board_w*.30)))
            m2_posts.extend(translated(rotate_vertices(ring(2.6,1.1,2.,segments=12),'left'),(-2.4,yy-by,-board_w*.05)))
            if n<3:
                cover=rotate_vertices(bevel_extrude(chamfer_rect(85.,14.,2.),4.2,.7),'left')
                add('detail-board-m2-heatsink',cover,metal,(bx-4.5,yy,bz+board_w*.10))
        add('detail-board-m2-sockets',_boxes(m2_parts),dark)
        add('detail-board-m2-mount-posts',tuple(m2_posts),metal)
        for n in range(4):
            pos=(bx-5.-(n//2)*7.,by-board_h*.38+(n%2)*11.5,bz+board_w*.44)
            housing=perforated_plate(chamfer_rect(9.5,9.5,.8),(_port_shape('sata',6.8,4.3),),2.)
            add('detail-board-sata-socket',housing,dark,pos)
        io_origin=(bx-21.,by+board_h*.22,bz-board_w/2-1.2)
        port_rows=[]
        for n in range(8):port_rows.append(('usb_a',(-9. if n%2==0 else 9.),47.-(n//2)*18.,12.8,5.6))
        for n in range(2):port_rows.append(('usb_c',-9.+n*18.,-25.,8.5,3.5))
        port_rows.extend((('hdmi',-9.,-43.,14.5,5.8),('displayport',9.,-43.,14.5,6.5),
                          ('lan',-9.,-62.,14.,12.),('spdif',9.,-62.,8.,8.)))
        for n in range(5):port_rows.append(('audio_3_5',19.,55.-n*20.,6.,6.))
        for n in range(2):port_rows.append(('buttons',-19.5,66.-n*13.,3.7,3.7))
        io_holes=[];recesses=[];io_frames={}
        for kind,x,y,pw,ph in port_rows:
            shape=circle(0,0,pw/2,12) if kind in ('audio_3_5','buttons') else _port_shape(kind,pw,ph)
            io_holes.append(tuple((px+x,py+y) for px,py in shape))
            frame=perforated_plate(chamfer_rect(pw+1.2,ph+1.2,.7),(shape,),.8)
            io_frames.setdefault(kind,[]).extend(translated(frame,(x,y,0)))
            recesses.append(((pw,ph,2.),(x,y,1.8)))
        add('detail-board-rear-io-shield',perforated_plate(chamfer_rect(45.,158.,2.),io_holes,1.),metal,io_origin)
        add('detail-board-rear-io-recesses',_boxes(recesses),dark,io_origin)
        for kind,frames in io_frames.items():add('detail-board-rear-'+kind,tuple(frames),metal,io_origin)
    return tuple((*out,*extras)),dict(layout_schematic=True,chip_count_schematic=True,mount_positions_schematic=True,
        populated_memory_sockets=min(len(modules),target_slots),rendered_memory_sockets=target_slots,unused_socket_capacity_inferred=False,
        memory_population_exceeds_documented_slots=known and len(modules)>target_slots,
        exact_profile=board.get('detail_profile') if known else '',
        documented_slot_counts=dict(board.get('slot_counts') or {}) if known else {},
        documented_rear_ports=dict(board.get('rear_ports') or {}) if known else {},
        m2_heatsinks=3 if known else 0,installed_ssd_count_inferred=False,rear_io_layout_schematic=True)


def enrich_components(meshes,spec):
    """Refine in canonical component axes, before the case's rigid pose change."""
    from assembly_geometry import rotate_vertices,unit_polygon
    level=detail_level(spec.get('detail_level'));metadata=dict(level=level,layout_schematic=True)
    if level=='eco':return tuple(meshes),metadata
    cpu=spec.get('cpu') or {};base=next((m for m in meshes if m.name=='cpu-lid'),None)
    if base is not None:
        _,height,width=_extent(base);package='lga_rect' if cpu.get('style')=='lga_rect' else 'am5' if cpu.get('style')=='am5' else 'chip'
        pw,ph=(37.5,45.) if package=='lga_rect' else (40.,40.)
        polygon=unit_polygon(cpu.get('lid_polygon'),pw,ph)
        if not polygon:
            if package=='am5':
                from assembly_geometry import AM5_LID
                polygon=tuple((x*.84,y*.84) for x,y in AM5_LID)
            else:polygon=chamfer_rect(width,height,.6)
        meshes=tuple(replace(m,vertices=rotate_vertices(bevel_extrude(polygon,2.4,.42),'left')) if m is base else m for m in meshes)
    meshes,gpu_meta=_gpu_detail(meshes,spec,component_level(spec,'gpu'))
    meshes,memory_meta=_memory_detail(meshes,spec,component_level(spec,'memory'))
    meshes,board_meta=_board_detail(meshes,spec,component_level(spec,'board'))
    metadata.update(gpu=gpu_meta,memory=memory_meta,board=board_meta,
                    pcb_routing_verified=False,mechanical_details_are_schematic=True)
    return tuple(meshes),metadata
