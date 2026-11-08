"""Original static PSU, storage, expansion and routed cable illustrations.

Only explicit, registered manual selections add auxiliary hardware. All input
anchors are final case-space coordinates, after the board/case rigid pose.
No discovery, polling, I/O, clocks, textures or manufacturer assets.
Original code/art: PolyForm Noncommercial 1.0.0; see LICENSE/LICENSING.md.
"""
import heapq
import math
from dataclasses import replace

from assembly_geometry import Mesh,box,extrude,fan_rotor,ring,model_mark
from assembly_detail import bevel_extrude,chamfer_rect,perforated_plate,translated,_subtract,_area,_tri,_quad
from component_catalog import get_component

_BLACK=(.085,.10,.115,1.);_DARK=(.035,.045,.055,1.)
_METAL=(.56,.61,.65,1.);_GOLD=(.72,.55,.25,1.);_PCB=(.10,.23,.21,1.)
_PSU_SHEET=(.22,.245,.265,1.)
_IDENTITY=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))


def _add(a,b):return tuple(x+y for x,y in zip(a,b))
def _sub(a,b):return tuple(x-y for x,y in zip(a,b))
def _mul(a,value):return tuple(x*value for x in a)
def _dot(a,b):return sum(x*y for x,y in zip(a,b))
def _cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])


def _point(value,default=(0.,0.,0.)):
    if isinstance(value,dict):value=tuple(value.get(k) for k in ('x','y','z'))
    return tuple(float(v) for v in value) if (isinstance(value,(tuple,list)) and len(value)==3
        and all(type(v) in (int,float) and math.isfinite(v) and abs(v)<10000 for v in value)) else default


def _unit(value,default=(0.,0.,1.)):
    value=_point(value,default);length=math.sqrt(_dot(value,value))
    return _mul(value,1/length) if length>1e-9 else default


def _basis(normal,along=None):
    n=_unit(normal);v=_unit(along,(0.,0.,1.))
    if abs(_dot(v,n))>.95:v=(0.,1.,0.) if abs(n[1])<.95 else (1.,0.,0.)
    v=_unit(_sub(v,_mul(n,_dot(v,n))));u=_unit(_cross(v,n))
    return u,v,n


def _connector_basis(normal,along):
    """Connector `along` is the long pin-row direction, not the short axis."""
    n=_unit(normal);u=_unit(along,(1.,0.,0.))
    if abs(_dot(u,n))>.95:u=_basis(n)[0]
    u=_unit(_sub(u,_mul(n,_dot(u,n))))
    return u,_unit(_cross(n,u)),n


def _transform(vertices,basis):
    if basis==_IDENTITY:return vertices
    out=[]
    for n in range(0,len(vertices),6):
        for offset in (0,3):out.extend(sum(vertices[n+offset+k]*basis[k][axis] for k in range(3)) for axis in range(3))
    return tuple(out)


def _boxes(rows):return tuple(v for size,position in rows for v in translated(box(*size),position))


def _aperture_cell(width,height,outline,depth=.9):
    """Cap a repeated cell around one genuinely open, possibly concave hole.

    Triangulating the original hole before convex subtraction retains rounded
    three-arm vents without crossed faces or the shared helper's 24-hole cap.
    Shared cell edges have no artificial upright walls.
    """
    rectangle=((-width/2,-height/2),(width/2,-height/2),(width/2,height/2),(-width/2,height/2))
    pieces=[rectangle];hole=extrude(outline,depth)
    triangles=[tuple(tuple(hole[i+k:i+k+2]) for k in (0,6,12)) for i in range(0,len(hole),18) if hole[i+5]>.999]
    for triangle in triangles:pieces=[piece for polygon in pieces for piece in _subtract(polygon,triangle)]
    out=[];z=depth/2
    for polygon in pieces:
        if _area(polygon)<0:polygon=tuple(reversed(polygon))
        for n in range(1,len(polygon)-1):
            a,b,c=polygon[0],polygon[n],polygon[n+1]
            _tri(out,(*a,z),(*b,z),(*c,z));_tri(out,(*c,-z),(*b,-z),(*a,-z))
    for a,b in zip(outline,(*outline[1:],outline[0])):_quad(out,(*b,-z),(*a,-z),(*a,z),(*b,z))
    return tuple(out)


def _rotate2(points,angle,offset=(0.,0.)):
    c,s=math.cos(angle),math.sin(angle)
    return tuple((x*c-y*s+offset[0],x*s+y*c+offset[1]) for x,y in points)


def vent_panel(width,height,pattern,depth=1.,circle_radius=None,exclude=(),sampling=1.):
    """Source-observed grille families, sampled as original mechanical paths.

    Pitch, edge radii and screw locations remain schematic; the documented
    family (Y / triangle / quadrant slots / honeycomb) is preserved at all
    detail levels. No texture, copied silhouette or manufacturer's logo.
    """
    border=5.;inner_w,inner_h=width-2*border,height-2*border
    frame=_boxes([((width,border,depth),(0,-height/2+border/2,0)),((width,border,depth),(0,height/2-border/2,0)),
                  ((border,inner_h,depth),(-width/2+border/2,0,0)),((border,inner_h,depth),(width/2-border/2,0,0))])
    if pattern=='quadrant_slots':
        # Four independently turned banks around the fixed hub medallion.
        quarter=min(inner_w,inner_h)/2;holes=[]
        for quadrant in range(4):
            for n in range(5):
                slot=chamfer_rect(quarter*.76,quarter*.065,1.)
                points=_rotate2(slot,.25,offset=(quarter*.39,quarter*(.29+n*.125)))
                points=_rotate2(points,quadrant*math.pi/2)
                holes.append(points)
        return perforated_plate(chamfer_rect(width,height,2.),tuple(holes),depth)
    pitch=(11.5 if pattern=='rounded_y' else 16. if pattern=='triangle' else 9.)*sampling
    cols=max(1,int(inner_w/pitch));rows=max(1,int(inner_h/pitch));cw,ch=inner_w/cols,inner_h/rows
    out=list(frame);cells={}
    for row in range(rows):
        for col in range(cols):
            center=((col-(cols-1)/2)*cw,(row-(rows-1)/2)*ch)
            blocked=any(abs(center[0]-x)<ww/2+cw*.5 and abs(center[1]-y)<hh/2+ch*.5 for x,y,ww,hh in exclude)
            outside=circle_radius is not None and math.hypot(*center)>circle_radius-min(cw,ch)*.33
            if blocked or outside:
                cell=translated(box(cw,ch,depth),(*center,0.))
                # Retain caps only: no visible false grid walls between cells.
                out.extend(v for i in range(0,len(cell),18) if abs(cell[i+5])>.999 for v in cell[i:i+18]);continue
            if pattern=='rounded_y':
                r=min(cw,ch)*.43;points=[]
                # Rounded three-arm cut-out; 3 tips, six re-entrant shoulders.
                for arm in range(3):
                    a=arm*math.tau/3
                    for angle,rad in ((a-.28,r*.42),(a-.18,r*.92),(a,r),(a+.18,r*.92),(a+.28,r*.42),(a+math.pi/3,r*.29)):
                        points.append((math.cos(angle)*rad,math.sin(angle)*rad))
                outline=tuple(points)
            elif pattern=='triangle':
                radius=min(cw,ch)*.48;outline=_rotate2(tuple((math.cos(n*math.tau/3)*radius,math.sin(n*math.tau/3)*radius) for n in range(3)),math.pi/2+(row+col)%2*math.pi)
            else:
                radius=min(cw,ch)*.43;outline=tuple((math.cos(n*math.tau/6)*radius,math.sin(n*math.tau/6)*radius) for n in range(6))
            if outline not in cells:cells[outline]=_aperture_cell(cw,ch,outline,depth)
            out.extend(translated(cells[outline],(*center,0.)))
    return tuple(out)


def _hex(value):
    if isinstance(value,str) and len(value)==7 and value[0]=='#':
        try:return tuple(int(value[n:n+2],16)/255 for n in (1,3,5))+(1.,)
        except ValueError:pass
    return (.09,.11,.14,1.)


def _funnel_inlet(radius, segments):
    """A bounded original taper below the grille, not an aerodynamic CAD claim."""
    out=[]
    for index in range(segments):
        a,b=index*math.tau/segments,(index+1)*math.tau/segments
        outer=lambda angle:(math.cos(angle)*radius*.98,math.sin(angle)*radius*.98,-.2)
        inner=lambda angle:(math.cos(angle)*radius*.86,math.sin(angle)*radius*.86,-3.)
        _quad(out,outer(a),outer(b),inner(b),inner(a))
    return tuple(out)


def _endpoint(value,default_normal=(-1.,0.,0.)):
    if not isinstance(value,dict):return None
    position=_point(value.get('position'),None)
    if position is None:return None
    return dict(position=position,normal=_unit(value.get('normal'),default_normal),
                along=_unit(value.get('along'),(0.,0.,1.)),
                kind=value.get('kind') or value.get('type') or '',
                connector_rendered=value.get('connector_rendered') is True,
                position_schematic=value.get('position_schematic',True),source=value.get('source',''))


def _bounds(value):
    if not isinstance(value,dict):return None
    raw=value.get('bounds')
    if isinstance(raw,dict):low,high=_point(raw.get('min'),None),_point(raw.get('max'),None)
    elif isinstance(raw,(tuple,list)) and len(raw)==2:low,high=_point(raw[0],None),_point(raw[1],None)
    else:
        center=_point(value.get('center'),None);size=_point(value.get('size'),None)
        if center is None or size is None:return None
        low,high=_sub(center,_mul(size,.5)),_add(center,_mul(size,.5))
    return (low,high) if low is not None and high is not None and all(low[n]<high[n] for n in range(3)) else None


def _segment_box(a,b,bounds,padding=0.):
    low,high=bounds;near,far=0.,1.
    for n in range(3):
        lo,hi=low[n]-padding+1e-6,high[n]+padding-1e-6;delta=b[n]-a[n]
        if abs(delta)<1e-10:
            if not lo<a[n]<hi:return False
        else:
            x,y=(lo-a[n])/delta,(hi-a[n])/delta
            near=max(near,min(x,y));far=min(far,max(x,y))
            if near>far:return False
    return far>1e-7 and near<1-1e-7


def segment_hits_box(a,b,bounds,padding=0.):
    """Conservative boxes, or a bounded static GPU triangle narrowphase."""
    return bounds.intersects(a,b,padding) if isinstance(bounds,_GpuObstacle) else _segment_box(a,b,bounds,padding)


def _segment_triangle(a,b,triangle):
    v0,v1,v2=triangle;direction=_sub(b,a);e1,e2=_sub(v1,v0),_sub(v2,v0)
    p=_cross(direction,e2);det=_dot(e1,p)
    if abs(det)<1e-10:return False
    inv=1/det;tvec=_sub(a,v0);u=_dot(tvec,p)*inv
    if u<0 or u>1:return False
    q=_cross(tvec,e1);v=_dot(direction,q)*inv
    if v<0 or u+v>1:return False
    t=_dot(e2,q)*inv
    return 1e-7<t<1-1e-7


class _GpuObstacle(tuple):
    """One scene-local acceleration structure over the existing GPU meshes.

    No vertex copy enters published metadata. Rotating blades remain full
    conservative swept boxes; phase-zero blade gaps never become wire routes.
    """
    def __new__(cls,bounds,meshes):
        self=super().__new__(cls,bounds);self.triangles=[];self.rotor_boxes=[]
        for mesh in meshes:
            if mesh.rotor:
                axis=_unit(mesh.axis);radius=0.;axial=[]
                for i in range(0,len(mesh.vertices),6):
                    point=mesh.vertices[i:i+3];along=_dot(point,axis);axial.append(along)
                    radius=max(radius,math.sqrt(max(0.,_dot(point,point)-along*along)))
                if axial:
                    middle=(min(axial)+max(axial))/2;half=(max(axial)-min(axial))/2
                    center=_add(mesh.position,_mul(axis,middle));extent=tuple(abs(axis[n])*half+radius*math.sqrt(max(0.,1-axis[n]*axis[n])) for n in range(3))
                    self.rotor_boxes.append((_sub(center,extent),_add(center,extent)))
                continue
            for i in range(0,len(mesh.vertices),18):
                self.triangles.append(tuple(_add(mesh.vertices[i+k:i+k+3],mesh.position) for k in (0,6,12)))
        triangle_bounds=[(tuple(min(point[n] for point in triangle) for n in range(3)),tuple(max(point[n] for point in triangle) for n in range(3))) for triangle in self.triangles]
        def node(indices):
            low=tuple(min(triangle_bounds[i][0][n] for i in indices) for n in range(3))
            high=tuple(max(triangle_bounds[i][1][n] for i in indices) for n in range(3))
            if len(indices)<=16:return (low,high,indices,None)
            axis=max(range(3),key=lambda n:high[n]-low[n]);indices.sort(key=lambda i:triangle_bounds[i][0][axis]+triangle_bounds[i][1][axis])
            middle=len(indices)//2;return (low,high,node(indices[:middle]),node(indices[middle:]))
        self.tree=node(list(range(len(self.triangles)))) if self.triangles else None
        return self

    def _ray(self,a,b):
        if self.tree is None:return False
        stack=[self.tree]
        while stack:
            low,high,left,right=stack.pop()
            if not _segment_box(a,b,(low,high),.001):continue
            if right is None:
                if any(_segment_triangle(a,b,self.triangles[i]) for i in left):return True
            else:stack.extend((left,right))
        return False

    def intersects(self,a,b,padding):
        if not _segment_box(a,b,self,padding):return False
        if padding>2.:return True  # Broad clearance candidates stay conservative.
        if any(_segment_box(a,b,box,padding) for box in self.rotor_boxes):return True
        if self._ray(a,b):return True
        if padding<=0:return False
        u,v,_=_basis(_sub(b,a))
        return any(self._ray(_add(a,offset),_add(b,offset)) for offset in
                   (_add(_mul(u,math.cos(n*math.tau/8)*padding),_mul(v,math.sin(n*math.tau/8)*padding)) for n in range(8)))


def rounded_path(points,radius=7.,steps=4):
    """Round static routing corners with bounded quadratic arcs."""
    clean=[]
    for point in points:
        point=_point(point)
        if not clean or math.dist(point,clean[-1])>1e-6:clean.append(point)
    if len(clean)<3:return tuple(clean)
    out=[clean[0]]
    for index in range(1,len(clean)-1):
        previous,corner,following=clean[index-1:index+2]
        distance=min(radius,math.dist(previous,corner)*.28,math.dist(corner,following)*.28)
        start=_add(corner,_mul(_unit(_sub(previous,corner)),distance))
        end=_add(corner,_mul(_unit(_sub(following,corner)),distance));out.append(start)
        for tick in range(1,steps+1):
            t=tick/steps;out.append(tuple((1-t)**2*start[n]+2*(1-t)*t*corner[n]+t*t*end[n] for n in range(3)))
    out.append(clean[-1]);return tuple(out)


def route_cable(start,end,start_normal,end_normal,obstacles=(),case_dimensions=(300,500,500),radius=7.,width=6.,waypoints=(),graph_boxes=(),tube_clearance=1.1):
    """Shortest static visibility route around actual padded component boxes.

    If an incompatible selection has no internal corridor, an exterior route
    remains visible and is reported, rather than clipping through the GPU.
    """
    sn,en=_unit(start_normal),_unit(end_normal)
    lead=max(14.,radius+width+3.);pad=radius+width+4.;boxes=tuple(obstacles)
    def ray_entry(point,normal,bounds):
        near,far=-float('inf'),float('inf')
        for n in range(3):
            lo,hi=bounds[0][n]-1.1,bounds[1][n]+1.1
            if abs(normal[n])<1e-9:
                if not lo<point[n]<hi:return None
            else:
                aa,bb=(lo-point[n])/normal[n],(hi-point[n])/normal[n]
                near=max(near,min(aa,bb));far=min(far,max(aa,bb))
                if near>far:return None
        return max(0.,near) if far>0 else None
    def escape(point,normal):
        entries=[entry for bounds in boxes if (entry:=ray_entry(point,normal,bounds)) is not None]
        distance=min(lead,max(3.,min(entries)-radius-width*.5-1.)) if entries else lead
        for _ in range(len(boxes)+1):
            candidate=_add(point,_mul(normal,distance));old=distance
            for low,high in boxes:
                if all(low[n]-pad<candidate[n]<high[n]+pad for n in range(3)):
                    exits=[((high[n]+pad-point[n]) if normal[n]>0 else (low[n]-pad-point[n]))/normal[n]
                           for n in range(3) if abs(normal[n])>1e-8]
                    proposed=max(distance,min(exits)+1.)
                    destination=_add(point,_mul(normal,proposed))
                    if not any(segment_hits_box(point,destination,bounds,1.1) for bounds in boxes):distance=proposed
            if distance==old:break
        return _add(point,_mul(normal,distance))
    a,b=escape(start,sn),escape(end,en);nodes=[a,b]
    for low,high in (graph_boxes or boxes):
        nodes.extend(tuple((low[n]-pad if bits&(1<<n)==0 else high[n]+pad) for n in range(3)) for bits in range(8))
    def clear(x,y):return all(not segment_hits_box(x,y,bounds,pad) for bounds in boxes)
    # Leads leave the physical connector normally. They may lie within a
    # padded clearance region while already outside the actual component.
    def visible(x,y):
        return all(not segment_hits_box(x,y,bounds,tube_clearance) for bounds in boxes)
    def solve(inside,first=a,last=b):
        if visible(first,last):return [first,last]
        # A fixed graph budget bounds explicit scene rebuilds with dense RAM
        # and cooler detail. Far-away obstacle corners do not help this leg.
        corners=list(dict.fromkeys(tuple(round(v,4) for v in p) for p in nodes[2:] if (not inside or all(abs(p[n])<case_dimensions[n]/2-3 for n in range(3)))))
        corners.sort(key=lambda p:math.dist(first,p)+math.dist(p,last))
        candidates=[first,last,*corners[:64]]
        queue=[(math.dist(first,last),0.,0)];dist={0:0.};previous={};cache={}
        edge_checks=0;expansions=0
        while queue:
            _estimated,cost,index=heapq.heappop(queue)
            if cost!=dist.get(index):continue
            if index==1:
                indices=[1]
                while indices[-1]!=0:indices.append(previous[indices[-1]])
                return [candidates[n] for n in reversed(indices)]
            expansions+=1
            if expansions>32:return None
            for target,point in enumerate(candidates):
                if target==index:continue
                key=(min(index,target),max(index,target))
                if key not in cache:
                    edge_checks+=1
                    if edge_checks>2048:return None
                    cache[key]=visible(candidates[index],point) and (index<2 or target<2 or clear(candidates[index],point))
                if not cache[key]:continue
                length=math.dist(candidates[index],point)
                value=cost+length
                if value<dist.get(target,float('inf')):
                    dist[target]=value;previous[target]=index;heapq.heappush(queue,(value+math.dist(point,last),value,target))
        return None
    middle=None;external=False;preferred_used=False
    preferred=[a,*(_point(p) for p in waypoints),b]
    if waypoints:
        staged=[]
        for first,last in zip(preferred,preferred[1:]):
            section=solve(True,first,last)
            if section is None:break
            staged.extend(section if not staged else section[1:])
        else:middle=staged;preferred_used=True
    if middle is None:middle=solve(True)
    if middle is None:middle=solve(False);external=True
    if middle is None:
        # Malformed connector normals are kept explicit, never passed off as
        # a valid internal route. Normalized production anchors avoid this.
        return (),dict(routing_failed=True,external_route=False)
    path=rounded_path((start,*middle,end),radius)
    # The normal connector leads have a known pin-row axis. An isotropic
    # bundle radius would falsely occupy the neighboring top-fan frame;
    # their actual shifted strands are checked individually by the caller.
    blocked=any(segment_hits_box(x,y,bounds,1.1 if index in (0,len(path)-2) else tube_clearance)
                for index,(x,y) in enumerate(zip(path,path[1:])) for bounds in boxes)
    if blocked and preferred_used:
        return route_cable(start,end,start_normal,end_normal,obstacles,case_dimensions,radius,width,graph_boxes=graph_boxes,tube_clearance=tube_clearance)
    return path,dict(routing_failed=blocked,external_route=external or any(abs(p[n])>case_dimensions[n]/2 for p in path for n in range(3)),preferred_waypoints_used=preferred_used)


def tube(vertices,radius=1.2,sides=6):
    """Closed small polygon tube; no per-frame tessellation or ribbons."""
    from assembly_detail import _tri
    if len(vertices)<2:return ()
    rings=[]
    for index,point in enumerate(vertices):
        direction=_unit(_sub(vertices[min(index+1,len(vertices)-1)],vertices[max(0,index-1)]))
        u,v,_=_basis(direction)
        rings.append(tuple(_add(point,_add(_mul(u,math.cos(n*math.tau/sides)*radius),_mul(v,math.sin(n*math.tau/sides)*radius))) for n in range(sides)))
    out=[]
    for first,second in zip(rings,rings[1:]):
        for n in range(sides):
            k=(n+1)%sides;_tri(out,first[n],first[k],second[k]);_tri(out,first[n],second[k],second[n])
    for index,reverse in ((0,True),(-1,False)):
        for n in range(sides):
            a,b=rings[index][n],rings[index][(n+1)%sides]
            _tri(out,vertices[index],b if reverse else a,a if reverse else b)
    return tuple(out)


def add_auxiliary(spec,anchors,level='balanced'):
    """Build both stages synchronously for legacy callers, without I/O."""
    stages=auxiliary_stages(spec,anchors,level)
    try:
        next(stages)
        return finish_auxiliary(stages,anchors)
    finally:stages.close()


def finish_auxiliary(stages,anchors):
    """Resume a single construction with final cooling/cable anchors."""
    try:stages.send(anchors)
    except StopIteration as result:return result.value
    raise RuntimeError('Auxiliary construction yielded more than one body stage')


def auxiliary_stages(spec,anchors,level='balanced'):
    """Yield actual bodies once, then finish cables with updated anchors.

    A selected loop can reserve each already-built PSU/drive/card before
    choosing a pump pose. The suspended frame belongs only to this scene
    construction and its caller must close it in a finally block. Neither
    Mesh objects nor this generator enter serializable scene metadata.
    """
    level=level if level in ('eco','balanced','close') else 'balanced'
    anchors=anchors if isinstance(anchors,dict) else {};options=spec.get('auxiliary') or {}
    dimensions=_point(anchors.get('case_dimensions'),(300.,500.,500.));w,h,d=dimensions
    case=anchors.get('case') or spec.get('case') or {};features=case.get('features') or ()
    meshes=[];issues=[];rejected=[];omitted_routes=[];devices=[];cables=[];storage_endpoints=[];gpu_endpoints=[];active_part=''
    connectors=anchors.get('connectors') or {};segments=16 if level=='eco' else 24 if level=='balanced' else 32
    def add(name,vertices,tone,position=(0.,0.,0.),component='psu',basis=None,rotor=False,axis=(0.,0.,1.)):
        if vertices:
            extra=dict(part_id=active_part) if 'part_id' in Mesh.__dataclass_fields__ else {}
            meshes.append(Mesh(name,_transform(vertices,basis or _IDENTITY),tone,tuple(position),component,rotor,1,axis,**extra))
    def cube(name,size,position,tone=_BLACK,component='psu',basis=None):add(name,box(*size),tone,position,component,basis)
    def face(name,width,height,depth,point,normal,tone,component,holes=()):
        vertices=perforated_plate(chamfer_rect(width,height,.8),holes,depth,segments=segments) if holes else bevel_extrude(chamfer_rect(width,height,.8),depth,.18)
        add(name,vertices,tone,point,component,_basis(normal,(0.,1.,0.)))
    def endpoint_record(point,normal,kind,owner,along=(0.,0.,1.)):
        return dict(position=tuple(point),normal=_unit(normal),kind=kind,owner=owner,along=_unit(along))
    def pose_part(part_id,center,basis,endpoints=()):
        for index,mesh in enumerate(meshes):
            if mesh.part_id!=part_id:continue
            relative=_sub(mesh.position,center)
            point=tuple(sum(relative[k]*basis[k][axis] for k in range(3)) for axis in range(3))
            axis=tuple(sum(mesh.axis[k]*basis[k][n] for k in range(3)) for n in range(3))
            meshes[index]=replace(mesh,vertices=_transform(mesh.vertices,basis),position=_add(center,point),axis=axis)
        for endpoint in endpoints:
            relative=_sub(endpoint['position'],center)
            endpoint['position']=_add(center,tuple(sum(relative[k]*basis[k][n] for k in range(3)) for n in range(3)))
            for key in ('normal','along'):endpoint[key]=tuple(sum(endpoint[key][k]*basis[k][n] for k in range(3)) for n in range(3))
    def plug(endpoint,kind,prefix,component='cables'):
        layouts={'atx24':(12,2),'eps8':(4,2),'pcie8':(4,2),'pcie6':(3,2),'aux4':(2,2),'gpu12':(6,2),'gpu16':(6,2),
                 'sata_power':(15,1),'sata_data':(7,1),'front_io':(5,2),'usb3':(10,2),'usb_c':(10,2),'audio':(5,2),
                 'fan4':(4,1),'argb3':(4,1),'modular':(4,2)}
        shape=endpoint.get('pin_kind',kind);columns,rows=layouts.get(shape,(4,2))
        pitch=1.05 if kind.startswith('sata') or shape in ('usb3','usb_c') else 2.54 if shape in ('fan4','argb3') else 4.2 if shape in ('atx24','eps8','pcie8','pcie6','aux4') else 3.0 if shape in ('gpu12','gpu16') else 3.4
        width,height=columns*pitch+(1 if shape in ('atx24','eps8') else 3),rows*pitch+2+(3.2 if shape=='gpu16' else 0);depth=6. if kind.startswith('sata') else 9.
        basis=_connector_basis(endpoint['normal'],endpoint.get('along'));point=endpoint['position']
        add(prefix+'-plug-shell',bevel_extrude(chamfer_rect(width,height,1.),depth,.35),_BLACK,_add(point,_mul(endpoint['normal'],depth/2)),component,basis)
        if level!='eco':
            pins=[((.55,.55,1.),((col-(columns-1)/2)*pitch,(row-(rows-1)/2)*pitch,-depth*.43)) for row in range(rows) for col in range(columns) if not(shape=='argb3' and col==2)]
            if shape=='gpu16':pins.extend(((.35,.35,1.),((col-1.5)*1.8,5.,-depth*.43)) for col in range(4))
            add(prefix+'-plug-pins',_boxes(pins),_GOLD,_add(point,_mul(endpoint['normal'],depth/2)),component,basis)
        return _add(point,_mul(endpoint['normal'],depth))

    psu_options=options.get('psu') or {};psu=get_component(psu_options.get('model_id'))
    psu_bounds=None;psu_sockets=[];psu_harness_bounds=[]
    if psu_options.get('model_id') and (not psu or psu['category']!='psu'):
        rejected.append(dict(kind='psu',model_id=psu_options.get('model_id'),reason='unknown_component_model'))
    if psu and psu['category']=='psu':
        active_part='psu:0'
        size=psu['dimensions_mm'];length,width,height=(size[k] for k in ('length','width','height'))
        explicit=anchors.get('psu') or {};center=_point(explicit.get('position'),None) if isinstance(explicit,dict) else None
        back=case.get('layout') in ('dual_chamber','panoramic') or 'dual_chamber' in features
        psu_basis=((0.,1.,0.),(-1.,0.,0.),(0.,0.,1.)) if back else _IDENTITY
        if isinstance(explicit.get('basis'),(list,tuple)) and len(explicit['basis'])==3:psu_basis=tuple(_unit(row) for row in explicit['basis'])
        world_width,world_height,_=tuple(sum(abs(psu_basis[k][n])*(width,height,length)[k] for k in range(3)) for n in range(3))
        if center is None:
            center=(w/2-world_width/2-9 if back else 0.,h/2-world_height/2-12 if 'top_psu_shroud' in features else -h/2+world_height/2+12,
                    -d/2+length/2+10)
        psu_bounds=(_sub(center,(width/2,height/2,length/2)),_add(center,(width/2,height/2,length/2)))
        passive=not psu['fan_count'];pattern=psu.get('grille_pattern','honeycomb')
        psu_sheet=_hex(psu['housing_color']) if psu.get('housing_color') else _PSU_SHEET
        frame=[((1.4,height,length),(-width/2+.7,0,0)),((1.4,height,length),(width/2-.7,0,0)),
               ((width,1.4,length),(0,height/2-.7,0))] if not passive else [
               ((1.4,height,5.),(x,0,z)) for x in (-width/2+.7,width/2-.7) for z in (-length/2+2.5,length/2-2.5)]
        if passive:frame.extend(((width,5.,1.2),(0,y,z)) for y in (-height/2+2.5,height/2-2.5) for z in (-length/2+.6,length/2-.6))
        add('psu-shell',_boxes(frame),psu_sheet,center)
        bottom=_add(center,(0,-height/2+.6,0));fan_basis=((1.,0.,0.),(0.,0.,-1.),(0.,-1.,0.))
        radius=psu['fan_diameter_mm']/2 if psu['fan_count'] else 0.
        sampling=1.8 if level=='eco' else 1.15 if level=='balanced' else 1.
        add('psu-fan-panel' if radius else 'psu-passive-panel',vent_panel(width,length,pattern,1.2,circle_radius=radius*.98 if radius else None,sampling=sampling),psu_sheet,bottom,'psu',fan_basis)
        if passive:
            add('psu-passive-upper-honeycomb',vent_panel(width,length,'honeycomb',1.2,sampling=sampling),psu_sheet,_add(center,(0,height/2-.6,0)),'psu',fan_basis)
            for side in (-1,1):add('psu-passive-side-honeycomb',vent_panel(length,height,'honeycomb',1.2,sampling=sampling),psu_sheet,_add(center,(side*(width/2-.6),0,0)),'psu',_basis((side,0,0),(0,1,0)))
            # Do not invent the manufacturer's hidden transformer/PCB layout.
            cube('psu-passive-internal-reference',(width*.70,height*.53,length*.70),_add(center,(0,0,0)),_DARK)
        if radius:
            rotor_point=_add(bottom,(0,1.7,0))
            if psu.get('funnel_inlet'):
                add('psu-fan-inlet-funnel-reference',_funnel_inlet(radius,segments),_BLACK,bottom,'psu',fan_basis)
            if psu.get('frameless_fan'):
                # Open motor supports, without an independent square fan cage.
                # Their routing/count remains an original reference, not CAD.
                supports=[]
                for index in range(3):
                    angle=index*math.tau/3;co,si=math.cos(angle),math.sin(angle)
                    turn=((co,si,0.),(-si,co,0.),(0.,0.,1.))
                    supports.extend(translated(_transform(box(radius*.72,3.4,1.5),turn),
                                               (radius*.53*co,radius*.53*si,-6.)))
                add('psu-frameless-motor-supports-reference',tuple(supports),_BLACK,bottom,'psu',fan_basis)
                add('psu-frameless-stationary-motor',ring(radius*.22,0,2.,segments=segments),_BLACK,
                    _add(bottom,(0,6.,0)),'psu',fan_basis)
            add('psu-fan-dark-recess',ring(radius*.94,0,.6,segments=segments),_DARK,_add(rotor_point,(0,1.2,0)),'psu',fan_basis)
            profile=dict(blades=psu.get('fan_blades',7),shape='wide',hub_ratio=.27,outer_ring=psu.get('outer_ring') is True)
            leaf_color=(.59,.75,.78,1.) if psu.get('rgb_fan') else (.37,.40,.42,1.)
            add('psu-fan-blades',fan_rotor(profile,radius*.94),leaf_color,rotor_point,'psu',fan_basis,True,(0.,-1.,0.))
            add('psu-fan-hub',ring(radius*.25,0,1.2,segments=segments),(.31,.34,.35,1.),_add(rotor_point,(0,-.3,0)),'psu',fan_basis,True,(0.,-1.,0.))
        # Fixed sheet-metal grille, four fasteners; only blades/hub rotate.
        screws=tuple(v for x in (-width/2+7,width/2-7) for y in (-length/2+7,length/2-7)
                     for v in translated(ring(2.5,1.1,.65,segments=12),(x,y,0)))
        add('psu-fan-panel-fasteners',screws,_METAL,_add(bottom,(0,-.7,0)),'psu',fan_basis)
        rear=_add(center,(0,0,-length/2+.6));iec=(width*.28,-height*.17);switch=(width*.28,height*.25)
        rear_basis=_basis((0,0,-1),(0,1,0));vent_width=width*.60
        add('psu-rear-vent-panel',vent_panel(vent_width,height,pattern if pattern=='rounded_y' else 'honeycomb',1.2,sampling=sampling),psu_sheet,_add(rear,(-width*.20,0,0)),'psu',rear_basis)
        io_center=width*.30;io_width=width*.40
        rear_holes=tuple(tuple((x-(cx-io_center),y+cy) for x,y in chamfer_rect(pw,ph,1.)) for cx,cy,pw,ph in ((*iec,28.,21.),(*switch,13.,16.)))
        face('psu-rear-io-frame',io_width,height,1.2,_add(rear,(io_center,0,0)),(0,0,-1),psu_sheet,'psu',rear_holes)
        face('psu-iec-c14-cavity',26,19,1.5,_add(rear,(*iec,2.)),(0,0,-1),_DARK,'psu')
        add('psu-iec-c14-three-pins',_boxes([((2.,4.,3.),(x,y,0)) for x,y in ((-6,-2),(6,-2),(0,4))]),_METAL,_add(rear,(*iec,.5)))
        face('psu-rocker-switch',11,14,2.,_add(rear,(*switch,-.4)),(0,0,-1),_BLACK,'psu')
        cube('psu-rocker-on-mark',(.8,3.,.15),_add(rear,(switch[0],switch[1]+2.,-1.5)),(.8,.83,.83,1.))
        if psu.get('manual_fan_knob'):add('psu-manual-fan-knob',ring(5.,0,3.,segments=16),_BLACK,_add(rear,(width*.125,-height*.28,-1.)))
        front=_add(center,(0,0,length/2-.6));dc_holes=[]
        power_count=len(connectors.get('atx24') or ())+len(connectors.get('eps8') or ())+len(connectors.get('eps4') or ())
        raw_gpu=(anchors.get('gpu') or {}).get('power') or ()
        if isinstance(raw_gpu,(tuple,list)):power_count+=len(raw_gpu)
        power_count+=sum(row.get('count',1) for row in options.get('storage') or () if isinstance(row,dict)
                         and type(row.get('count',1)) is int and 1<=row.get('count',1)<=4
                         and (record:=get_component(row.get('model_id'))) and record['form_factor'].startswith('sata'))
        socket_count=max(8,power_count);socket_rows=math.ceil(socket_count/4)
        modular=psu.get('modular') is True
        fixed_harness=not modular or psu.get('semi_modular') is True
        fixed_endpoints=[]
        if modular:
            for index in range(socket_count):
                row,col=divmod(index,4)
                cx=(col-1.5)*width*.21;cy=(row-(socket_rows-1)/2)*height*.78/socket_rows
                socket_h=min(height*.24,height*.65/socket_rows)
                if fixed_harness:cx=cx*.70+width*.10
                hole=tuple((x+cx,y+cy) for x,y in chamfer_rect(width*.15,socket_h,.5));dc_holes.append(hole)
                point=_add(front,(cx,cy,0));psu_sockets.append(endpoint_record(point,(0,0,1),'modular','psu',(1,0,0)))
                face('psu-modular-dark-socket',width*.14,socket_h*.92,1.,_add(point,(0,0,-1.5)),(0,0,1),_DARK,'psu')
        if fixed_harness:
            # One schematic factory harness exits a grommet. A non-modular
            # supply must never acquire a bank of detachable modular sockets.
            exit_x,exit_y=-width*.35,height*.27
            hole=tuple((x+exit_x,y+exit_y) for x,y in chamfer_rect(18.,12.,3.))
            dc_holes.append(hole)
            point=_add(front,(exit_x,exit_y,0))
            add('psu-fixed-harness-grommet',ring(9.,6.,2.,segments=segments),_BLACK,_add(point,(0,0,.8)))
            wires=[]
            for x,y in ((-2.,-1.5),(2.,-1.5),(-2.,1.5),(2.,1.5)):
                path=tuple(_add(point,(x,y,z)) for z in (1.,7.,14.))
                wires.extend(tube(path,1.1,6))
            add('psu-fixed-harness-reference',tuple(wires),_BLACK)
            for index in range(socket_count):
                x,y=((-2.,-1.5),(2.,-1.5),(-2.,1.5),(2.,1.5))[index%4]
                entry=endpoint_record(_add(point,(x,y,14.)),(0,0,1),'fixed_harness','psu',(1,0,0))
                entry.update(connector_rendered=True,position_schematic=True)
                fixed_endpoints.append(entry)
            if not modular:psu_sockets=fixed_endpoints
        face('psu-modular-connector-panel' if modular else 'psu-fixed-cable-panel',width,height,1.2,front,(0,0,1),psu_sheet,'psu',tuple(dc_holes))
        label_point=_add(center,(-width/2-.11,0,0));label_basis=_basis((-1,0,0),(0,1,0))
        if passive:label_point=_add(label_point,(0,-height*.36,0))
        face('psu-neutral-rating-label',length*.82,height*.16 if passive else height*.60,.2,label_point,(-1,0,0),(.045,.055,.065,1.),'psu')
        add('psu-original-model-mark',model_mark(psu.get('model_mark',''),1.25),(.83,.85,.86,1.),_add(label_point,(-.18,4.,0)),'psu',label_basis)
        if psu.get('oled_display'):
            display=_add(label_point,(-.4,-height*.21,length*.15))
            face('psu-oled-reference-bezel',min(72.,length*.42),height*.24,1.,display,(-1,0,0),_BLACK,'psu')
            face('psu-oled-unread-blank',min(68.,length*.39),height*.19,.2,_add(display,(-.65,0,0)),(-1,0,0),(.035,.075,.09,1.),'psu')
        else:add('psu-label-rule',box(length*.68,.6,.08),(.38,.42,.45,1.),_add(label_point,(-.18,-height*.13,0)),'psu',label_basis)
        if psu.get('accent_color'):
            add('psu-series-accent-strip',box(.2,1.7,length*.65),_hex(psu['accent_color']),_add(label_point,(-.28,height*.26,0)),'psu')
        if psu_basis!=_IDENTITY:pose_part(active_part,center,psu_basis,psu_sockets if not modular else (*psu_sockets,*fixed_endpoints))
        psu_meshes=[mesh for mesh in meshes if mesh.part_id==active_part and mesh.name!='psu-fixed-harness-reference']
        psu_bounds=tuple(tuple((min if side==0 else max)((min if side==0 else max)(mesh.vertices[n::6])+mesh.position[n] for mesh in psu_meshes) for n in range(3)) for side in (0,1))
        # Fixed wires occupy their narrow real corridor. Expanding the whole
        # PSU AABB to their ends would incorrectly swallow adjacent modular
        # plugs on a semi-modular supply and make otherwise clear routes fail.
        for mesh in meshes:
            if mesh.part_id==active_part and mesh.name=='psu-fixed-harness-reference':
                psu_harness_bounds.append(tuple(tuple((min if side==0 else max)(mesh.vertices[n::6])+mesh.position[n] for n in range(3)) for side in (0,1)))
        devices.append(dict(category='psu',part_id=active_part,model_id=psu['id'],label=psu['label'],center=center,dimensions_mm=size,
            source='manual',fan_count=psu['fan_count'],fan_blades_schematic=True,fan_rpm_available=False,
            capacity_w=psu['capacity_w'],live_power_w=None,modular_socket_layout_schematic=True,
            grille_pattern=pattern,grille_hole_count_is_sampling=True,basis=psu_basis))
        devices[-1].update(modular=modular,semi_modular=bool(psu.get('semi_modular')),fixed_harness=fixed_harness,
            modular_socket_layout_schematic=modular,fixed_harness_layout_schematic=fixed_harness,
            oled_display_available=bool(psu.get('oled_display')),oled_live_reading=None,rgb_lighting_live=False,
            fan_inlet_profile='funnel_reference' if psu.get('funnel_inlet') else 'reference',
            frameless_fan=bool(psu.get('frameless_fan')))
        if case.get('psu_form_factors') and psu['form_factor'] not in case['psu_form_factors']:issues.append('psu_form_factor_not_supported')

    m2_slots=list(connectors.get('m2') or ());sata_slots=list(connectors.get('sata') or ());m2_used=set();sata_index=0
    rear_storage=case.get('layout') in ('dual_chamber','panoramic') or 'dual_chamber' in features
    rear_cursor=-h/2+45.;rear_column=0
    for selection in options.get('storage') or ():
        record=get_component(selection.get('model_id')) if isinstance(selection,dict) else None
        count=selection.get('count',1) if isinstance(selection,dict) else 0
        if not record or record['category']!='storage' or type(count) is not int or not 1<=count<=4:
            issues.append('invalid_storage_selection');rejected.append(dict(kind='storage',model_id=selection.get('model_id','') if isinstance(selection,dict) else '',reason='unknown_component_model' if not record else 'invalid_component_count'));continue
        for instance in range(count):
            identity=record['id'];size=record['dimensions_mm'];length,width,height=(size[k] for k in ('length','width','height'))
            index=len([row for row in devices if row['category']=='storage']);prefix='storage-'+str(index)
            occurrence=sum(row['category']=='storage' and row['model_id']==identity for row in devices)
            active_part='storage:'+identity+':'+str(occurrence)
            if record['form_factor']=='m2_nvme':
                nominal_length=int(record.get('m2_size','2280')[2:])
                available=[(n,row) for n,row in enumerate(m2_slots) if n not in m2_used]
                compatible=[(n,row) for n,row in available if not row.get('allowed_lengths_mm')
                    or any(abs(distance-nominal_length)<1 for distance in row['allowed_lengths_mm'])]
                selected=compatible[0] if compatible else None
                raw=selected[1] if selected else None;slot=_endpoint(raw)
                if slot is None and anchors.get('model'):
                    rejected.append(dict(kind='storage',model_id=identity,
                        reason='no_supported_m2_length' if available else 'no_m2_slot'));continue
                if selected:m2_used.add(selected[0])
                length_verified=bool(raw and raw.get('allowed_lengths_mm'))
                if raw and not length_verified and anchors.get('model'):issues.append('m2_length_support_unverified')
                if slot is None:
                    slot=dict(position=(-w*.16,h*.12-index*30,d*.12),normal=(-1.,0.,0.),along=(0.,0.,1.));issues.append('m2_mount_position_unverified')
                normal=slot['normal'];along=slot['along'];basis=_basis(normal,along)
                center=_add(slot['position'],_add(_mul(along,length/2),_mul(normal,height/2+1.)))
                heatsink=record.get('factory_heatsink') is True
                pcb_width=22. if heatsink else width  # Nominal M.2 board; outer shell is separately dimensioned.
                key=pcb_width*.225;r=1.8
                keys=(-key,key) if record.get('m2_key')=='b_m' else (key,)
                pcb_outline=[(-pcb_width/2,-length/2)]
                for at in keys:
                    pcb_outline.extend(((at-.70,-length/2),(at-.70,-length/2+3.),
                        (at+.70,-length/2+3.),(at+.70,-length/2)))
                pcb_outline.extend(((pcb_width/2,-length/2),(pcb_width/2,length/2),(r,length/2)))
                pcb_outline.extend((r*math.cos(n*math.pi/12),length/2-r*math.sin(n*math.pi/12)) for n in range(1,13))
                pcb_outline.append((-pcb_width/2,length/2))
                pcb=bevel_extrude(tuple(pcb_outline),.8,.10)
                add(prefix+'-m2-pcb',pcb,(.065,.073,.070,1.) if record.get('pcb_color')=='black' else _PCB,_add(center,_mul(normal,-height/2+.4)),'storage',basis)
                package_h=min(1.5,max(.3,height-.8)) if heatsink else max(.3,height-.8)
                package_z=-height/2+.8+package_h/2
                rows=[((pcb_width*.70,length*.20,package_h),(0,-length*.23,package_z)),
                      ((pcb_width*.70,length*.20,package_h),(0,length*.06,package_z)),
                      ((pcb_width*.52,length*.12,package_h),(0,length*.32,package_z))]
                add(prefix+'-m2-reference-packages-controller',_boxes(rows),_BLACK,center,'storage',basis)
                if heatsink:
                    # Envelopes and observed shell families are source-linked;
                    # groove pitch, screw positions and fin count are sampling.
                    bottom=-height/2+min(2.4,height*.32);top=height/2
                    tone=_hex(record.get('body_color','#293039'))
                    style=record.get('heatsink_style','reference_parallel')
                    base_h=min(.9,(top-bottom)*.3)
                    add(prefix+'-m2-factory-heatsink-base',bevel_extrude(chamfer_rect(width,length,1.4),base_h,.15),
                        tone,_add(center,_mul(normal,bottom+base_h/2)),'storage',basis)
                    fin_h=max(.3,top-bottom-base_h-.12)
                    if style in ('smooth_low','reference'):
                        add(prefix+('-m2-smooth-heatsink-shell' if style=='smooth_low' else '-m2-reference-heatsink-envelope'),bevel_extrude(chamfer_rect(width,length,1.6),fin_h,.35),
                            tone,_add(center,_mul(normal,bottom+base_h+fin_h/2)),'storage',basis)
                        for sign in ((-1,1) if style=='smooth_low' else ()):
                            pos=_add(center,_add(_mul(basis[0],sign*(width/2+.05)),_mul(normal,bottom+fin_h*.55)))
                            add(prefix+'-m2-reference-side-fastener',ring(.9,.3,.18,segments=12),_METAL,pos,'storage',
                                (basis[1],basis[2],_mul(basis[0],sign)))
                    else:
                        count=5 if level=='eco' else 8 if level=='balanced' else 10
                        across=record.get('fin_axis','length')=='width'
                        pitch=(length if across else width)/(count+1)
                        fins=[]
                        for n in range(count):
                            at=(n-(count-1)/2)*pitch
                            if style.startswith('diagonal'):
                                # Alternating oblique endings retain this shell
                                # family without claiming an exact groove map.
                                run=length*(.78 if n%2 else .92);shift=length*(.045 if n%2 else -.025)
                                poly=((at-pitch*.21,-run/2+shift),(at+pitch*.21,-run/2+shift+pitch),
                                      (at+pitch*.21,run/2+shift),(at-pitch*.21,run/2+shift-pitch))
                                fins.extend(translated(extrude(poly,fin_h),(0,0,bottom+base_h+fin_h/2)))
                            else:
                                fin_size=(width*.96,pitch*.42,fin_h) if across else (pitch*.42,length*.96,fin_h)
                                pos=(0,at,bottom+base_h+fin_h/2) if across else (at,0,bottom+base_h+fin_h/2)
                                fins.extend(translated(box(*fin_size),pos))
                        add(prefix+'-m2-heatsink-reference-fins',tuple(fins),tone,center,'storage',basis)
                label_style=record.get('label_style');label_tone=_hex(record['label_color']) if record.get('label_color') else (.07,.074,.08,1.) if label_style!='t500_reference' else (.25,.28,.30,1.)
                label_position=_add(center,_mul(normal,height/2+.08))
                label=bevel_extrude(chamfer_rect(width*.76 if heatsink else width*.86,length*.26 if heatsink else length*.83,.9),.10,.015)
                add(prefix+'-m2-label-heatspreader' if record.get('low_profile_heatspreader') else prefix+'-m2-product-label',label,label_tone,label_position,'storage',basis)
                text_basis=(basis[1],_mul(basis[0],-1),basis[2])
                mark_position=_add(label_position,_add(_mul(normal,.09),_mul(along,0 if heatsink else -length*.13)))
                mark_ink=(.09,.12,.14,1.) if sum(c*v for c,v in zip(label_tone,(.2126,.7152,.0722)))>.52 else (.86,.87,.86,1.)
                add(prefix+'-m2-original-model-mark',model_mark(record.get('model_mark','NVME'),min(.78,length*.70/max(1,len(record.get('model_mark','NVME'))*5))),mark_ink,mark_position,'storage',text_basis)
                if label_style=='samsung_990' and not heatsink:
                    add(prefix+'-m2-red-model-rule',box(length*.48,.65,.07),(.74,.12,.11,1.),_add(mark_position,_mul(basis[0],3.)),'storage',text_basis)
                    add(prefix+'-m2-capacity-mark',model_mark('2TB',.55),(.8,.82,.82,1.),_add(label_position,_add(_mul(normal,.09),_mul(along,length*.26))),'storage',text_basis)
                elif label_style=='kc3000' and not heatsink:
                    # Original sparse gold line motif, not a reproduction of
                    # Kingston's printed trace artwork or manufacturer logo.
                    line=tube(((-length*.29,-width*.25,0.),(-length*.05,-width*.25,0.),(length*.05,width*.04,0.),(length*.26,width*.04,0.)),.14,4)
                    add(prefix+'-m2-original-film-lines',line,(.65,.57,.38,1.),_add(label_position,_mul(normal,.10)),'storage',text_basis)
                pads=[((pcb_width*.027,3.,.12),((n-8.5)*pcb_width*.045,-length/2+1.6,-height/2+.9)) for n in range(18)
                      if all(abs((n-8.5)*pcb_width*.045-at)>.95 for at in keys)]
                add(prefix+'-m2-reference-edge-contacts',_boxes(pads),_GOLD,center,'storage',basis)
                if not anchors.get('model'):add(prefix+'-m2-socket',box(width+2,4,3),_DARK,slot['position'],'storage',basis)
                fixing=_add(center,_mul(along,length/2))
                add(prefix+'-m2-fixing-screw',ring(2.,0,1.,segments=16),_METAL,_add(fixing,_mul(normal,-height/2+1.3)),'storage',basis)
                placement='board_socket' if raw is not None else 'reference_position'
            else:
                if rear_storage:
                    if rear_cursor+length>h/2-18.:rear_cursor=-h/2+45.;rear_column+=1
                    center=(w/2-height/2-8,rear_cursor+length/2,d/2-width/2-18-rear_column*114.)
                    rear_cursor+=length+12.
                else:center=(w*.20,-h/2+height/2+18+sata_index*(height+9),d/2-length/2-14)
                sata_index+=1
                basis=((1.,0.,0.),(0.,0.,1.),(0.,-1.,0.))
                hdd=record['form_factor']=='sata_35_hdd'
                body_height=height-1.2 if hdd else height;body_center=_add(center,(0,.6,0)) if hdd else center
                add(prefix+'-drive-body',bevel_extrude(chamfer_rect(width,length,3.5 if hdd else 1.5),body_height,.65 if hdd else .35),_BLACK,body_center,'storage',basis)
                top=_add(center,(0,height/2+.12,0));top_basis=((-1.,0.,0.),(0.,0.,1.),(0.,1.,0.));cover=record['form_factor']=='sata_35_hdd'
                add(prefix+'-hdd-sealed-cover' if cover else prefix+'-ssd-label-panel',bevel_extrude(chamfer_rect(width*.94,length*.94,2.),.25,.04),_METAL if cover else (.26,.28,.30,1.),top,'storage',top_basis)
                if cover:
                    # Closed stamped top cover: no transparent platter fiction.
                    add(prefix+'-hdd-cover-pressed-border',perforated_plate(chamfer_rect(width*.90,length*.90,7.),(chamfer_rect(width*.84,length*.84,7.),),.22),(.43,.48,.51,1.),_add(top,(0,.17,0)),'storage',top_basis)
                    add(prefix+'-hdd-cover-reference-stamp',ring(width*.33,width*.316,.22,segments=segments),(.42,.46,.49,1.),_add(top,(0,.20,-length*.10)),'storage',top_basis)
                    fasteners=tuple(v for x,z in ((-width*.43,-length*.43),(width*.43,-length*.43),(-width*.43,length*.43),(width*.43,length*.43),(-width*.43,0),(width*.43,0))
                                   for v in translated(ring(2.5,.85,.65,segments=12),(x,z,0)))
                    add(prefix+'-hdd-cover-fasteners',fasteners,_DARK,_add(top,(0,.40,0)),'storage',top_basis)
                    label_center=_add(top,(0,.53,length*.10))
                    label_tone=_hex(record['label_color']) if record.get('label_color') else (.07,.31,.57,1.)
                    label_ink=(.09,.12,.14,1.) if sum(c*v for c,v in zip(label_tone,(.2126,.7152,.0722)))>.52 else (.93,.95,.95,1.)
                    add(prefix+'-hdd-blue-label' if record.get('label_style')=='wd_blue' else prefix+'-hdd-product-label',
                        bevel_extrude(chamfer_rect(width*.68,length*.65,2.),.10,.02),
                        label_tone,label_center,'storage',top_basis)
                    add(prefix+'-hdd-label-model',model_mark(record.get('model_mark','HDD'),min(1.35,width*.62/max(1,len(record.get('model_mark','HDD'))*5))),label_ink,_add(label_center,(0,.11,-length*.06)),'storage',top_basis)
                    add(prefix+'-hdd-label-capacity',model_mark(str(record['capacity_gb']//1000)+'TB' if record['capacity_gb']%1000==0 else str(record['capacity_gb'])+'GB',.95),label_ink,_add(label_center,(0,.11,length*.15)),'storage',top_basis)
                    underside=_add(center,(0,-height/2+.6,0))
                    ribs=[((2.0,1.2,length*.90),(x,0,0)) for x in (-width*.44,width*.44)]
                    ribs.extend(((width*.88,1.2,2.2),(0,0,z)) for z in (-length*.43,-length*.15,length*.43))
                    add(prefix+'-hdd-cast-reference-ribs',_boxes(ribs),(.30,.34,.35,1.),underside,'storage')
                    add(prefix+'-hdd-cast-motor-boss',ring(width*.22,width*.12,2.0,segments=segments),(.32,.36,.38,1.),_add(underside,(0,-.15,-length*.18)),'storage',basis)
                    add(prefix+'-hdd-cast-bearing-center',ring(width*.10,0,1.2,segments=segments),(.48,.51,.52,1.),_add(underside,(0,-1.,-length*.18)),'storage',basis)
                    cube(prefix+'-hdd-reference-controller-pcb',(width*.73,.7,length*.40),_add(underside,(0,-.15,length*.21)),_PCB,'storage')
                    cube(prefix+'-hdd-reference-controller',(width*.20,.45,length*.10),_add(underside,(0,-.40,length*.20)),_BLACK,'storage')
                    add(prefix+'-hdd-controller-fasteners',tuple(v for x,z in ((-width*.32,length*.03),(width*.32,length*.03),(-width*.32,length*.37),(width*.32,length*.37)) for v in translated(ring(2.,.8,.6,segments=12),(x,z,0))),_METAL,_add(underside,(0,-.65,0)),'storage',basis)
                else:
                    add(prefix+'-ssd-original-model-mark',model_mark(record.get('model_mark','SSD'),1.15),(.86,.87,.87,1.),_add(top,(0,.20,0)),'storage',top_basis)
                    # The 870 EVO's restrained dark square is a family cue,
                    # with no copied Samsung logotype or certification label.
                    cube(prefix+'-ssd-accent-square',(7.,.15,7.),_add(top,(-width*.27,.17,length*.27)),(.26,.29,.29,1.),'storage')
                rear=_add(center,(0,0,-length/2-.15))
                power=endpoint_record(_add(rear,(-width*.16,0,0)),(0,0,-1),'sata_power',prefix,(1,0,0))
                data=endpoint_record(_add(rear,(width*.24,0,0)),(0,0,-1),'sata_data',prefix,(1,0,0))
                face(prefix+'-sata-power',19,4,1.2,power['position'],power['normal'],_DARK,'storage')
                face(prefix+'-sata-data',9,4,1.2,data['position'],data['normal'],_DARK,'storage')
                for endpoint,pins,span in ((power,15,16.),(data,7,7.)):
                    rows=[((span/pins*.58,1.5,.15),((n-(pins-1)/2)*span/pins,0,0)) for n in range(pins)]
                    add(prefix+'-'+endpoint['kind']+'-contacts',_boxes(rows),_GOLD,_add(endpoint['position'],(0,0,-.8)),'storage')
                if rear_storage:pose_part(active_part,center,((0.,0.,1.),(1.,0.,0.),(0.,1.,0.)),(power,data))
                storage_endpoints.append((power,data));placement='reference_case_bay'
            devices.append(dict(category='storage',part_id=active_part,model_id=identity,label=record['label'],instance=occurrence,center=center,
                dimensions_mm=size,source='manual',placement=placement,package_layout_schematic=True,live_activity=None,
                factory_heatsink=bool(record.get('factory_heatsink')),heatsink_fins_are_sampling=bool(record.get('factory_heatsink')),
                m2_key=record.get('m2_key','m') if record['form_factor']=='m2_nvme' else None,
                m2_length_supported=length_verified if record['form_factor']=='m2_nvme' else None,
                electrical_compatibility_verified=False,heatsink_clearance_verified=False))

    pcie_slots=list(connectors.get('pcie') or ());used_slots=set();gpu_anchor=anchors.get('gpu') or {};gpu_bounds=_bounds(gpu_anchor)
    gpu_clearance=None
    if gpu_bounds and pcie_slots:used_slots.add(0)
    for selection in options.get('expansion_cards') or ():
        record=get_component(selection.get('model_id')) if isinstance(selection,dict) else None
        if not record or record['category']!='expansion':
            issues.append('invalid_expansion_selection');rejected.append(dict(kind='expansion',model_id=selection.get('model_id','') if isinstance(selection,dict) else '',reason='unknown_component_model'));continue
        if case.get('id') in ('hyte-y70','hyte-y60') or 'low_profile_only' in features:
            rejected.append(dict(kind='expansion',model_id=record['id'],reason='low_profile_bracket_required'));continue
        if 'no_expansion_slots' in features:
            rejected.append(dict(kind='expansion',model_id=record['id'],reason='no_expansion_slot'));continue
        occurrence=sum(row['category']=='expansion' and row['model_id']==record['id'] for row in devices)
        active_part='expansion:'+record['id']+':'+str(occurrence)
        size=record['dimensions_mm'];length,thickness,height=(size[k] for k in ('length','width','height'))
        pcb_h=min(height*.65,57. if record['form_factor']=='sound' else 55.)
        available=[(n,row) for n,row in enumerate(pcie_slots) if n not in used_slots and (record['host_interface']=='pcie_x1' or row.get('kind')!='x1')]
        raw=None;slot=None;obstructed=False
        for index,candidate in available:
            proposed=_endpoint(candidate)
            if proposed is None:continue
            out,axis=proposed['normal'],proposed['along'];up=_unit(_cross(out,axis))
            rear_position=_point(candidate.get('rear_position'),_sub(proposed['position'],_mul(axis,23.)))
            midpoint=_add(rear_position,_add(_mul(out,pcb_h/2),_add(_mul(axis,length/2),_mul(up,thickness/2))))
            extent=tuple((abs(out[n])*pcb_h+abs(axis[n])*length+abs(up[n])*thickness)/2 for n in range(3))
            bounds=(_sub(midpoint,extent),_add(midpoint,extent))
            if gpu_bounds and all(bounds[0][n]<gpu_bounds[1][n]-.1 and bounds[1][n]>gpu_bounds[0][n]+.1 for n in range(3)):
                obstructed=True;continue
            raw=candidate;slot=proposed;used_slots.add(index);break
        if slot is None:
            if anchors.get('model'):
                rejected.append(dict(kind='expansion',model_id=record['id'],reason='expansion_slot_obstructed' if obstructed else 'no_expansion_slot'));continue
            slot=dict(position=(-w*.12,-h*.22-len(used_slots)*25,-d*.25),normal=(-1.,0.,0.),along=(0.,0.,1.));issues.append('expansion_mount_position_unverified')
        outward,along=slot['normal'],slot['along'];surface=_unit(_cross(outward,along));basis=(outward,along,surface)
        rear_point=_point(raw.get('rear_position'),None) if isinstance(raw,dict) else None
        if rear_point is None:rear_point=_sub(slot['position'],_mul(along,23.))
        center=_add(rear_point,_add(_mul(outward,pcb_h/2),_mul(along,length/2)))
        prefix='expansion-'+str(len([row for row in devices if row['category']=='expansion']))
        pcb_tone=(.24,.055,.075,1.) if record.get('pcb_color')=='dark_red' else (.075,.08,.075,1.)
        add(prefix+'-pcb',bevel_extrude(chamfer_rect(pcb_h,length,1.),1.4,.15),pcb_tone,center,'expansion',basis)
        add(prefix+'-reference-packages',_boxes([((pcb_h*.27,length*.17,2.),(-pcb_h*.06,-length*.1,1.9)),
            ((pcb_h*.20,length*.17,1.6),(pcb_h*.14,length*.24,1.7))]),_BLACK,center,'expansion',basis)
        if record['form_factor']=='wifi':
            add(prefix+'-red-heatsink-base',bevel_extrude(chamfer_rect(pcb_h*.91,length*.87,1.4),2.0,.35),(.58,.075,.15,1.),_add(center,_mul(surface,2.3)),'expansion',basis)
            fins=[((1.0,length*.83,5.5),((n-7)*pcb_h*.057,0,5.7)) for n in range(15)]
            add(prefix+'-red-parallel-heatsink-fins',_boxes(fins),(.63,.085,.17,1.),center,'expansion',basis)
            add(prefix+'-original-model-mark',model_mark('TX3000E',.65),(.88,.81,.81,1.),_add(center,_mul(surface,8.65)),'expansion',basis)
        elif record['form_factor']=='capture':
            cover_w,cover_l=pcb_h*.98,length*.94
            holes=tuple(tuple((x+cx,y+cy) for x,y in chamfer_rect(cover_w*.055,cover_l*.15,.5)) for cy in (-cover_l*.32,cover_l*.32) for cx in (-cover_w*.27,-cover_w*.135,0,cover_w*.135,cover_w*.27))
            add(prefix+'-vented-shield-cover',perforated_plate(chamfer_rect(cover_w,cover_l,2.0),holes,1.),(.24,.28,.31,1.),_add(center,_mul(surface,7.0)),'expansion',basis)
            edges=[((1.,cover_l,6.),(-cover_w/2,0,3.5)),((1.,cover_l,6.),(cover_w/2,0,3.5)),((cover_w,1.,6.),(0,cover_l/2,3.5))]
            add(prefix+'-shield-folded-lips',_boxes(edges),(.24,.28,.31,1.),center,'expansion',basis)
            add(prefix+'-original-model-mark',model_mark('4K PRO',.95),(.83,.85,.86,1.),_add(center,_mul(surface,7.65)),'expansion',basis)
        elif record['form_factor']=='sound':
            capacitors=[]
            for x,y in ((-pcb_h*.30,-length*.22),(pcb_h*.25,-length*.12),(-pcb_h*.27,length*.24),(pcb_h*.27,length*.24),(-pcb_h*.30,length*.13),(-pcb_h*.30,length*.02),(pcb_h*.18,-length*.34)):
                capacitors.extend(translated(ring(2.1,0,4.5,segments=12),(x,y,3.6)))
            add(prefix+'-reference-audio-capacitors',tuple(capacitors),(.35,.40,.42,1.),center,'expansion',basis)
            add(prefix+'-original-model-mark',model_mark('AUDIGY FX V2',.58),(.73,.75,.72,1.),_add(center,_add(_mul(surface,1.),_mul(outward,pcb_h*.30))),'expansion',basis)
        edge_pads=[((5.,1.,.2),(-pcb_h/2+2.5,-length/2+17+n*1.6,1.0)) for n in range(14 if record['host_interface']=='pcie_x1' else 30)]
        add(prefix+'-reference-pcie-contacts',_boxes(edge_pads),_GOLD,center,'expansion',basis)
        bracket_center=_add(rear_point,_mul(outward,height/2));bracket_basis=(outward,surface,_mul(along,-1.))
        port_count=sum(row['count'] for row in record['ports']);port_kind=record['ports'][0]['type'];pw,ph=(7.,7.) if port_kind in ('sma','audio_3_5') else (15.,7.)
        port_holes=[]
        for n in range(port_count):
            at=(pcb_h-height)/2+(n-(port_count-1)/2)*min(12.,pcb_h/(port_count+1))
            # Jacks sit above the component side of the PCB. Centering their
            # openings on the PCB plane would leave board material in front
            # of the rear cavities, despite a genuinely pierced bracket.
            port_offset=4.2
            polygon=tuple((x+at,y+port_offset) for x,y in chamfer_rect(pw,ph,.8));port_holes.append(polygon)
            point=_add(bracket_center,_add(_mul(outward,at),_mul(surface,port_offset)))
            add(prefix+'-port-dark-cavity',box(pw,ph,2.4),_DARK,_add(point,_mul(along,1.5)),'expansion',bracket_basis)
            if port_kind in ('sma','audio_3_5'):
                add(prefix+'-round-port-rim',ring(pw/2,pw/2-1.,1.3,segments=16),_GOLD if port_kind=='sma' else _METAL,point,'expansion',bracket_basis)
        add(prefix+'-io-bracket',perforated_plate(chamfer_rect(height,thickness,1.),tuple(port_holes),1.0,segments=segments),_METAL,bracket_center,'expansion',bracket_basis)
        devices.append(dict(category='expansion',part_id=active_part,model_id=record['id'],label=record['label'],center=center,dimensions_mm=size,
            source='manual',host_interface=record['host_interface'],ports=record['ports'],placement_schematic=True,live_activity=None))

    active_part=''
    power_rows=gpu_anchor.get('power') or ()
    if isinstance(power_rows,dict):power_rows=power_rows.get('connectors') or power_rows.get('inlets') or ()
    power_map={'pcie_8pin':'pcie8','pcie8':'pcie8','8pin':'pcie8','pcie_6pin':'pcie6','pcie6':'pcie6','6pin':'pcie6','4pin':'aux4','12pin':'gpu12',
               '12vhpwr':'gpu16','12v_2x6':'gpu16','12v-2x6':'gpu16','16pin':'gpu16','gpu16':'gpu16'}
    for index,raw in enumerate(power_rows if isinstance(power_rows,(tuple,list)) else ()):
        endpoint=_endpoint(raw);kind=power_map.get(raw.get('type')) if isinstance(raw,dict) else None
        if endpoint is None or kind is None:continue
        endpoint.update(kind=kind,owner='gpu');gpu_endpoints.append(endpoint)
        columns=6 if kind in ('gpu12','gpu16') else 4 if kind=='pcie8' else 3 if kind=='pcie6' else 2
        pitch=3.0 if kind in ('gpu12','gpu16') else 4.2
        holes=[tuple((x+(col-(columns-1)/2)*pitch,y+(row-.5)*pitch) for x,y in chamfer_rect(2.3,2.3,.3))
               for row in range(2) for col in range(columns)]
        if kind=='gpu16':holes.extend(tuple((x+(col-1.5)*1.8,y+5.) for x,y in chamfer_rect(1.,1.,.1)) for col in range(4))
        vertices=perforated_plate(chamfer_rect(columns*pitch+3,13. if kind=='gpu16' else 10.4,.8),tuple(holes),3.,segments=segments)
        add('gpu-power-inlet-'+str(index),vertices,_DARK,_sub(endpoint['position'],_mul(endpoint['normal'],1.5)),'gpu',_connector_basis(endpoint['normal'],endpoint['along']))

    updated_anchors=yield tuple(meshes)
    if isinstance(updated_anchors,dict):anchors=updated_anchors
    # The final posed/replaced GPU and newly constructed cooling bodies are
    # available only after the body stage. Build the cable obstacle once here.
    gpu_bounds=_bounds(anchors.get('gpu') or {})
    if options.get('cables_enabled') is True and gpu_bounds and isinstance(anchors.get('_gpu_clearance_meshes'),(tuple,list)):
        gpu_clearance=_GpuObstacle(gpu_bounds,anchors['_gpu_clearance_meshes'])
    if options.get('cables_enabled') is True:
        active_part='cables:all'
        targets=[]
        for key,kind in (('atx24','atx24'),('eps8','eps8'),('eps4','aux4')):
            for raw in connectors.get(key) or ():
                endpoint=_endpoint(raw)
                if endpoint is not None:endpoint.update(kind=kind,owner='board');targets.append(endpoint)
        targets.extend(gpu_endpoints)
        targets.extend(power for power,_data in storage_endpoints)
        obstacles=[]
        if psu_bounds:obstacles.append(psu_bounds)
        obstacles.extend(psu_harness_bounds)
        if gpu_bounds:obstacles.append(gpu_clearance if gpu_clearance is not None else gpu_bounds)
        for raw in anchors.get('obstacles') or ():
            bounds=_bounds(raw)
            if bounds and bounds not in obstacles:obstacles.append(bounds)
        graph_groups={}
        for raw in anchors.get('obstacles') or ():
            bounds=_bounds(raw)
            if bounds:graph_groups.setdefault(raw.get('part_id') or raw.get('kind') or raw.get('name'),[]).append(bounds)
        graph_boxes=[tuple(tuple((min if side==0 else max)(bounds[side][n] for bounds in group) for n in range(3)) for side in (0,1)) for group in graph_groups.values()]
        if psu_bounds:graph_boxes.append(psu_bounds)
        graph_boxes.extend(psu_harness_bounds)
        if gpu_bounds:graph_boxes.append(gpu_bounds)
        # Close detail refines the same loom; it never widens the physical
        # envelope merely because more illustrative samples are available.
        cable_tone=_hex(options.get('cable_color'));strands=2 if level=='eco' else 3
        board=anchors.get('board') or {};board_point=_point(board.get('position'),None)
        trunk_supported=bool(board_point and _point(board.get('normal'))==(-1.,0.,0.) and _point(board.get('up'))==(0.,1.,0.))
        case_fan_owners={row.get('owner') for row in ((anchors.get('cooling') or {}).get('wire_anchors') or ())
                         if isinstance(row,dict) and row.get('role')=='case' and isinstance(row.get('owner'),str)}
        def tray_waypoints(source,target,start,end):
            if not trunk_supported:return ()
            bx,by,bz=board_point;board_h=board.get('height',305.);board_w=board.get('width',244.)
            dual=case.get('layout') in ('dual_chamber','panoramic') or 'dual_chamber' in features
            rear_x=min(w/2-12.,bx+18.);front_x=bx-(22. if dual else 36.);aperture_z=bz+board_w/2+31.
            source_y=start[1];target_y=end[1]
            points=[]
            owner=source.get('owner','')
            case_fan=isinstance(owner,str) and owner in case_fan_owners
            if case_fan and owner.startswith('fans:rear:'):
                # A short reference lane behind the rear fan plane, then the
                # actual tray side. No factory grommet location is claimed.
                rear_lane_z=-d/2+6.
                points.extend(((start[0],source_y,rear_lane_z),(rear_x,source_y,rear_lane_z)))
                # Stay near the rear mounting frame instead of traversing to
                # the front-case aperture. All sections use the same solver.
                edge_y=by+board_h/2+8.
                points.extend(((rear_x,edge_y,rear_lane_z),(front_x,edge_y,rear_lane_z)))
                if target_y>by+board_h/2-24.:
                    points.append((front_x,edge_y,end[2]))
                else:
                    points.extend(((front_x,target_y,rear_lane_z),(front_x,target_y,end[2])))
                return tuple(points)
            elif source.get('owner')=='case' or case_fan and owner.startswith('fans:front:'):
                # Traverse the actual front-side opening beyond the GPU,
                # then stay behind the tray. Avoid crossing the divider at
                # its solid bottom or routing diagonally across the card.
                case_entry_z=min(d/2-22.,max(aperture_z+30.,(gpu_bounds[1][2]+24.) if gpu_bounds else aperture_z+30.))
                points.append((rear_x,source_y,case_entry_z))
            if source.get('owner')=='board':points.append((front_x,source_y,aperture_z))
            points.append((rear_x,source_y,aperture_z))
            if target.get('owner') in ('board','gpu'):
                if target_y>by+board_h/2-24.:
                    edge_y=by+board_h/2+(8. if case_fan else 22.)
                    points.extend(((rear_x,edge_y,aperture_z),(front_x,edge_y,aperture_z),(front_x,edge_y,end[2])))
                elif target_y<by-board_h/2+20.:
                    edge_y=by-board_h/2-20.
                    points.extend(((rear_x,edge_y,aperture_z),(front_x,edge_y,aperture_z),(front_x,edge_y,end[2])))
                elif target.get('owner')=='board' and end[2]<bz+board_w/2-30.:
                    # The lower case-fan header is reached around the observed
                    # pump-elbow envelope, not through a diagonal detour.
                    edge_y=by+board_h/2+(8. if case_fan else 22.)
                    if case_fan:
                        approach_z=end[2]-24.
                        points.extend(((rear_x,edge_y,aperture_z),(front_x,edge_y,aperture_z),
                                       (front_x,edge_y,approach_z),(front_x,target_y,approach_z),
                                       (front_x,target_y,end[2])))
                    else:
                        points.extend(((rear_x,edge_y,aperture_z),(front_x,edge_y,aperture_z),(front_x,edge_y,end[2])))
                else:points.extend(((rear_x,target_y+18. if target.get('owner')=='gpu' else target_y,aperture_z),
                                   (front_x,target_y+18. if target.get('owner')=='gpu' else target_y,aperture_z)))
            else:points.append((rear_x,target_y,aperture_z))
            return tuple(points)
        def connect(source,target,kind,index):
            mesh_start=len(meshes)
            prefix='cable-'+str(index)+'-'+kind
            start=source['position'] if source.get('connector_rendered') else plug(source,'modular' if source.get('owner')=='psu' else source['kind'],prefix+'-source')
            end=plug(target,kind,prefix+'-target')
            slim=kind in ('sata_data','front_io','fan4','argb3')
            preferred=tray_waypoints(source,target,start,end)
            # An already modeled fan plug is the attachment surface, not a
            # foreign obstacle. Retain the cooler/fan body and every other
            # part; ignore only that matching connector's padded boundary.
            own_connector_bounds=[]
            if source.get('connector_rendered'):
                for raw in anchors.get('obstacles') or ():
                    bounds=_bounds(raw)
                    if (bounds and raw.get('part_id')==source.get('owner') and 'connector' in raw.get('name','')
                            and all(bounds[0][n]-1.2<=start[n]<=bounds[1][n]+1.2 for n in range(3))):own_connector_bounds.append(bounds)
            cable_strands=min(strands,2) if slim else strands
            clearance=1.1+(cable_strands-1)*.85
            route_obstacles=[]
            for bounds in obstacles:
                if bounds in own_connector_bounds:continue
                if source.get('kind')=='fixed_harness' and bounds in psu_harness_bounds:
                    # A cable starts on its already-rendered factory wire end.
                    # Allow padding to touch only that terminal cap; retain the
                    # PSU body and the rest of the harness for all routes.
                    axis=max(range(3),key=lambda n:abs(source['normal'][n]))
                    sign=source['normal'][axis]
                    side=1 if sign>0 else 0
                    face=bounds[side][axis]
                    if abs(sign)>.99999 and abs(start[axis]-face)<1e-5:
                        low,high=list(bounds[0]),list(bounds[1])
                        if sign>0:high[axis]=start[axis]-clearance-.2
                        else:low[axis]=start[axis]+clearance+.2
                        if all(a<b for a,b in zip(low,high)):bounds=(tuple(low),tuple(high))
                route_obstacles.append(bounds)
            path,state=route_cable(start,end,source['normal'],target['normal'],route_obstacles,dimensions,width=5. if slim else 10.,radius=4. if slim else 7.,waypoints=preferred,graph_boxes=graph_boxes,tube_clearance=clearance)
            if not path or state['routing_failed']:
                del meshes[mesh_start:];issues.append('cable_clearance_requires_review')
                omitted_routes.append(dict(kind=kind,count=1,reason='cable_route_unavailable',source_owner=source.get('owner'),target_owner=target.get('owner')))
                return
            if state['external_route']:issues.append('cable_reference_route_exceeds_case')
            vertices=[]
            source_u=_connector_basis(source['normal'],source.get('along'))[0];target_u=_connector_basis(target['normal'],target.get('along'))[0]
            cumulative=[0.]
            for a,b in zip(path,path[1:]):cumulative.append(cumulative[-1]+math.dist(a,b))
            def strand_axis(t):
                dot=max(-1.,min(1.,_dot(source_u,target_u)))
                if dot<-.999:
                    orthogonal=_basis(source_u)[0]
                    return _add(_mul(source_u,math.cos(t*math.pi)),_mul(orthogonal,math.sin(t*math.pi)))
                angle=math.acos(dot)
                if angle<1e-5:return source_u
                return _mul(_add(_mul(source_u,math.sin((1-t)*angle)),_mul(target_u,math.sin(t*angle))),1/math.sin(angle))
            shifted_paths=[]
            for strand in range(cable_strands):
                offset=(strand-(cable_strands-1)/2)*1.7
                shifted=tuple(_add(point,_mul(strand_axis(cumulative[n]/max(cumulative[-1],1.)),offset)) for n,point in enumerate(path))
                shifted_paths.append(shifted);vertices.extend(tube(shifted,1.,6 if level!='close' else 8))
            if any(segment_hits_box(a,b,bounds,1.1) for shifted in shifted_paths for a,b in zip(shifted,shifted[1:]) for bounds in route_obstacles):
                del meshes[mesh_start:];omitted_routes.append(dict(kind=kind,count=1,reason='cable_route_unavailable',source_owner=source.get('owner'),target_owner=target.get('owner')))
                issues.append('cable_clearance_requires_review');return
            add(prefix+'-rounded-loom',tuple(vertices),cable_tone,component='cables')
            cables.append(dict(kind=kind,source_owner=source.get('owner'),target_owner=target.get('owner'),
                source_socket=source['position'],target_socket=target['position'],start=start,end=end,path=path,
                rendered_strands=cable_strands,strand_count_is_sampling=True,layout_schematic=True,
                routing_policy='rear_tray_grommet_reference' if state.get('preferred_waypoints_used') else 'clearance_visibility_reference',**state))
        if psu_sockets:
            for index,target in enumerate(targets):
                source=psu_sockets[index]
                if modular and fixed_endpoints and target['kind'] in psu.get('fixed_cable_groups',()):
                    source=fixed_endpoints[index]
                connect(source,target,target['kind'],len(cables))
        elif targets:
            issues.append('psu_not_selected_power_cables_not_inferred')
            omitted_routes.extend(dict(kind=target['kind'],count=1,reason='psu_not_selected',target_owner=target.get('owner')) for target in targets)
        sata_sources=[endpoint for raw in sata_slots if (endpoint:=_endpoint(raw)) is not None]
        for index,(_power,target) in enumerate(storage_endpoints):
            if index<len(sata_sources):
                source=sata_sources[index];source.update(kind='sata_data',owner='board');connect(source,target,'sata_data',len(cables))
            else:
                issues.append('sata_data_header_unverified');omitted_routes.append(dict(kind='sata_data',count=1,reason='header_not_verified',target_owner=target.get('owner')))
        case_io=[endpoint for raw in anchors.get('case_front_io') or () if (endpoint:=_endpoint(raw,(0.,0.,-1.))) is not None]
        for external,header,capacity in (('usb_a','usb3',2),('usb_c','usb_c',1),('audio','audio',2),('buttons','front_io',2)):
            sources=[row for row in case_io if row['kind']==external]
            targets=[endpoint for raw in connectors.get(header) or () if (endpoint:=_endpoint(raw)) is not None]
            groups=[sources[n:n+capacity] for n in range(0,len(sources),capacity)]
            for group,target in zip(groups,targets):
                source=dict(group[0]);source['position']=tuple(sum(row['position'][n] for row in group)/len(group) for n in range(3))
                source['normal']=_mul(source['normal'],-1.);source['position']=_add(source['position'],_mul(source['normal'],6.))
                source.update(kind='front_io',pin_kind=header,owner='case');target.update(kind='front_io',pin_kind=header,owner='board')
                connect(source,target,'front_io',len(cables))
            if len(groups)>len(targets):
                issues.append('front_io_header_capacity_unverified');omitted_routes.append(dict(kind='front_io',count=len(groups)-len(targets),reason='header_capacity_unverified'))
        cooling=anchors.get('cooling') or {};header_indices={'fan':0,'argb':0}
        for raw in cooling.get('wire_anchors') or ():
            source=_endpoint(raw)
            if source is None or raw.get('kind') not in ('fan4','argb3'):continue
            key='argb' if raw['kind']=='argb3' else 'fan';headers=[endpoint for item in connectors.get(key) or () if (endpoint:=_endpoint(item)) is not None]
            if header_indices[key]>=len(headers):
                omitted_routes.append(dict(kind=raw['kind'],count=1,reason='header_capacity_unverified',source_owner=raw.get('owner')));continue
            target=headers[header_indices[key]];header_indices[key]+=1
            source.update(kind=raw['kind'],owner=raw.get('owner','cooling'));target.update(kind=raw['kind'],owner='board')
            connect(source,target,raw['kind'],len(cables))
    outside=[]
    for device in devices:
        part_meshes=[mesh for mesh in meshes if mesh.part_id==device['part_id']]
        low=[min(min(mesh.vertices[n::6])+mesh.position[n] for mesh in part_meshes) for n in range(3)]
        high=[max(max(mesh.vertices[n::6])+mesh.position[n] for mesh in part_meshes) for n in range(3)]
        if any(low[n]<-dimensions[n]/2-.8 or high[n]>dimensions[n]/2+.8 for n in range(3)):
            outside.append(dict(kind=device['category'],model_id=device['model_id'],part_id=device['part_id'],reason='part_outside_case_reference',bounds=dict(min=low,max=high)))
    metadata=dict(manual_selection=True,devices=devices,device_counts={category:sum(row['category']==category for row in devices) for category in ('psu','storage','expansion')},
        cables=cables,cable_count=len(cables),gpu_power_inlets=len(gpu_endpoints),issues=sorted(set(issues)),
        psu_fan_tachometer_available=False,layout_schematic=True,electrical_pinout_not_modeled=True,
        cable_length_is_installed_routing=False,actual_installed_devices_inferred=False,
        rejected=rejected,warnings=sorted(set(issues)),outside_reference=outside,omitted_routes=omitted_routes,
        omitted_route_count=sum(row['count'] for row in omitted_routes),
        triangles=sum(mesh.vertex_count//3 for mesh in meshes),idle_work=False,
        parts=[dict(id=row['part_id'],label=row['label'],kind=row['category'],model_id=row['model_id'],
                    dimensions_mm=row['dimensions_mm'],selection_source='manual') for row in devices]
              +([dict(id='cables:all',label='线缆',kind='cables',model_id='',routes=len(cables))] if cables else []))
    return tuple(meshes),metadata
