"""Original, bounded cooling reference geometry; explicit choices only.

No detection, clocks, networking, sensor access or rendering dependencies. The
catalog distinguishes documented envelopes from reference construction. Mount
locations/tube routes are schematic and never constitute a clearance guarantee.
All input anchors are already in final case space; no second layout pose occurs.
Original code/art: PolyForm Noncommercial 1.0.0; product names retain their owners.
"""
from collections import defaultdict
import math

from cooling_catalog import get_cooler, get_fan


def _add(a,b):return tuple(a[i]+b[i] for i in range(3))
def _mul(a,s):return tuple(v*s for v in a)
def _sub(a,b):return tuple(a[i]-b[i] for i in range(3))
def _dot(a,b):return sum(a[i]*b[i] for i in range(3))
def _cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def _unit(a,default=(0.,0.,1.)):
    if not isinstance(a,(list,tuple)) or len(a)!=3 or not all(type(v) in (int,float) and math.isfinite(v) for v in a):return default
    size=math.sqrt(_dot(a,a));return _mul(a,1/size) if size>1e-9 else default


def _basis(normal,up=(0.,1.,0.)):
    n=_unit(normal);u=_sub(up,_mul(n,_dot(up,n)))
    if _dot(u,u)<1e-6:u=_cross((1.,0.,0.) if abs(n[0])<.8 else (0.,1.,0.),n)
    u=_unit(u);v=_unit(_cross(n,u));return u,v,n


def _transform(vertices,center,basis,translate=True):
    out=[]
    for start in range(0,len(vertices),6):
        for offset in (0,3):
            p=vertices[start+offset:start+offset+3]
            q=tuple(sum(p[k]*basis[k][j] for k in range(3)) for j in range(3))
            out.extend(_add(q,center) if offset==0 and translate else q)
    return tuple(out)


def _tube(points,radius,segments=8):
    """Open-ended round tube with stable per-segment rings and unit normals."""
    from assembly_geometry import _quad
    out=[]
    for a,b in zip(points,points[1:]):
        delta=_sub(b,a)
        if _dot(delta,delta)<1e-8:continue
        u,v,n=_basis(delta)
        for i in range(segments):
            angle=i*math.tau/segments;following=(i+1)*math.tau/segments
            p=_add(_mul(u,math.cos(angle)*radius),_mul(v,math.sin(angle)*radius))
            q=_add(_mul(u,math.cos(following)*radius),_mul(v,math.sin(following)*radius))
            _quad(out,_add(a,p),_add(a,q),_add(b,q),_add(b,p))
    return tuple(out)


def _curve(points,steps=12):
    a,b,c,d=points
    return [tuple((1-t)**3*a[n]+3*(1-t)**2*t*b[n]+3*(1-t)*t*t*c[n]+t**3*d[n] for n in range(3)) for t in (i/steps for i in range(steps+1))]


def _aio_sweep(points,radius,segments,start_axis,end_axis,*,straight_leads=True):
    """AIO-only shared rings; the generic reference tube remains unchanged.

    Transport one radial frame along the tangent field. Every intermediate
    ring belongs to both adjacent spans, including at bends and inflections.
    The mouth planes and the two short straight leads retain the outlet axes.
    """
    from assembly_geometry import _quad
    tangents=[_unit(start_axis)]
    tangents.extend(_unit(_add(_unit(_sub(b,a)),_unit(_sub(c,b))))
                    for a,b,c in zip(points,points[1:],points[2:]))
    tangents.append(_mul(_unit(end_axis),-1.))
    if straight_leads and len(points)>3:tangents[1]=tangents[0];tangents[-2]=tangents[-1]
    radial=_basis(tangents[0])[0];previous=tangents[0];rings=[];radials=[]
    for point,tangent in zip(points,tangents):
        turn=_cross(previous,tangent);cosine=max(-1.,min(1.,_dot(previous,tangent)))
        if _dot(turn,turn)>1e-16 and cosine>-.99999999:
            radial=_add(radial,_add(_cross(turn,radial),_mul(_cross(turn,_cross(turn,radial)),1./(1.+cosine))))
        radial=_unit(_sub(radial,_mul(tangent,_dot(radial,tangent))),_basis(tangent)[0])
        side=_unit(_cross(tangent,radial));directions=[_add(_mul(radial,math.cos(i*math.tau/segments)),_mul(side,math.sin(i*math.tau/segments))) for i in range(segments)]
        rings.append([_add(point,_mul(direction,radius)) for direction in directions]);radials.append(directions)
        previous=tangent
    vertices=[]
    for index,(first,last) in enumerate(zip(rings,rings[1:])):
        for side in range(segments):
            following=(side+1)%segments;offset=len(vertices)
            _quad(vertices,first[side],first[following],last[following],last[side])
            # Smooth radial shading changes no physical triangle or silhouette.
            normals=(radials[index][side],radials[index][following],radials[index+1][following],
                     radials[index][side],radials[index+1][following],radials[index+1][side])
            for vertex,normal in enumerate(normals):vertices[offset+vertex*6+3:offset+vertex*6+6]=normal
    return vertices,rings


def _aio_hose(builder,start,end,start_axis,end_axis,start_radius=5.,end_radius=6.,*,points=None,model_id='',nominal_length=None):
    """Join existing AIO outlet mouths without inventing a new fitting or tach.

    End rings and short leads follow each already-modelled connector axis.
    Only the middle route is illustrative; no clearance or bend-radius claim.
    Small annular end walls close the old outer-surface gap where the existing
    connector is narrower than the unchanged12.4mm reference hose envelope.
    """
    from assembly_geometry import _quad
    start_axis=_unit(start_axis);end_axis=_unit(end_axis)
    if points is None:
        distance=math.sqrt(_dot(_sub(end,start),_sub(end,start)))
        lead=min(15.,distance*.08);handle=min(45.,distance*.20)
        a=_add(start,_mul(start_axis,lead));b=_add(end,_mul(end_axis,lead))
        steps={'eco':8,'balanced':12,'close':18}[builder.level]
        points=[start,*_curve((a,_add(a,_mul(start_axis,handle)),
                               _add(b,_mul(end_axis,handle)),b),steps),end]
    segments={'eco':6,'balanced':8,'close':10}[builder.level];radius=6.2
    vertices,rings=_aio_sweep(points,radius,segments,start_axis,end_axis)
    for center,ring_points,connector_radius in ((start,rings[0],start_radius),(end,rings[-1],end_radius)):
        if connector_radius>=radius:continue
        for index in range(segments):
            outer=(ring_points[index],ring_points[(index+1)%segments])
            inner=[_add(center,_mul(_sub(point,center),connector_radius/radius)) for point in outer]
            _quad(vertices,inner[0],outer[0],outer[1],inner[1])
    builder.put('cooler-liquid-tubes',vertices,'#303e46',part='cooler:cpu')
    builder.aio_hoses.append(dict(id='cooler:cpu:hose:'+str(len(builder.aio_hoses)),model_id=model_id,
        points=[list(point) for point in points],outer_radius_mm=radius,
        centerline_length_mm=sum(math.dist(a,b) for a,b in zip(points,points[1:])),
        nominal_length_mm=nominal_length,nominal_length_preserved=nominal_length is not None,
        path_accuracy='original_routing_reference',endpoints_position_verified=False))


_LFIII_FACTORY_IDS=frozenset('arctic-liquid-freezer-iii-'+size for size in ('240','280','360','420'))
_LFIII_PORT_SOURCE='https://www.arctic.de/media/1f/c8/23/1710936380/Liquid_Freezer_III_360_Dimensions_2000x2000.jpg'


def _lfiii_hose_paths(starts,ends,start_axis,end_axis,normal,level,length_mm):
    """A paired broad guide, not two independent loops around the VRM.

    Length is a1% nominal reference. Transporting the separation frame keeps
    the pair together as the two source-observed mouth rows change direction.
    The manufacturer does not specify this installed route or bend clearance.
    """
    from liquid_clearance046 import self_overlap,route_pair_overlap
    start=_mul(_add(*starts),.5);end=_mul(_add(*ends),.5)
    first=_add(start,_mul(start_axis,12.));last=_add(end,_mul(end_axis,40.))
    steps={'eco':16,'balanced':24,'close':32}[level]
    first_spread=_sub(starts[0],start);last_spread=_sub(ends[0],end)
    def candidate(handle,roll):
        centers=_curve((first,_add(first,_mul(start_axis,handle)),_add(last,_mul(end_axis,handle*.65)),last),steps)
        tangents=[start_axis]+[_unit(_add(_unit(_sub(b,a)),_unit(_sub(c,b))))
            for a,b,c in zip(centers,centers[1:],centers[2:])]+[_mul(end_axis,-1.)]
        radial=_unit(first_spread);previous=start_axis;frames=[]
        for tangent in tangents:
            turn=_cross(previous,tangent);cosine=max(-1.,min(1.,_dot(previous,tangent)))
            if _dot(turn,turn)>1e-16 and cosine>-.99999999:
                radial=_add(radial,_add(_cross(turn,radial),_mul(_cross(turn,_cross(turn,radial)),1./(1.+cosine))))
            radial=_unit(_sub(radial,_mul(tangent,_dot(radial,tangent))))
            frames.append(radial);previous=tangent
        desired=_unit(last_spread);angle=math.atan2(_dot(_cross(frames[-1],desired),tangents[-1]),_dot(frames[-1],desired))
        paths=[[starts[0]],[starts[1]]]
        for index,(center,tangent,radial) in enumerate(zip(centers,tangents,frames)):
            t=index/steps;a=angle*t*t*(3.-2.*t)+roll*math.sin(math.pi*t)**2
            direction=_add(_mul(radial,math.cos(a)),_mul(_cross(tangent,radial),math.sin(a)))
            radius=math.dist(starts[0],start)*(1.-t)+math.dist(ends[0],end)*t
            for j,sign in enumerate((1.,-1.)):paths[j].append(_add(center,_mul(direction,sign*radius)))
        for j in (0,1):paths[j].append(ends[j])
        return paths
    measure=lambda path:sum(math.dist(a,b) for a,b in zip(path,path[1:]))
    for roll in (0.,-math.pi/4,math.pi/4,-math.pi/2,math.pi/2):
        low,high=0.,length_mm*.8
        for _ in range(18):
            handle=(low+high)/2;paths=candidate(handle,roll)
            if sum(map(measure,paths))/2<length_mm:low=handle
            else:high=handle
        if (all(abs(measure(path)-length_mm)<=length_mm*.01 for path in paths)
                and not any(self_overlap(path,6.2) for path in paths)
                and not route_pair_overlap(paths[0],6.2,paths[1],6.2)):
            return paths
    return None


def _aio_route_issues(paths,dimensions,obstacles):
    """One-build conservative rigid envelopes; no per-frame scan or CAD claim."""
    from liquid_clearance046 import self_overlap,route_pair_overlap
    radius=6.2;issues=[]
    for index,path in enumerate(paths):
        if any(abs(point[k])+radius>dimensions[k]/2 for point in path for k in range(3)):
            issues.append('case_envelope')
        if self_overlap(path,radius):issues.append('self_overlap')
        for a,b,c in zip(path,path[1:],path[2:]):
            crossed=_cross(_sub(a,b),_sub(c,b));area=math.sqrt(_dot(crossed,crossed))
            if area>1e-9 and math.dist(a,b)*math.dist(b,c)*math.dist(a,c)/(2.*area)<24.:
                issues.append('reference_curvature_too_tight')
        for span,(a,b) in enumerate(zip(path,path[1:])):
            for _part,name,bounds in obstacles:
                if name in ('cooler-radiator-fittings','cooler-lfiii-twin-hose-elbows'):continue
                if name=='cooler-lfiii-twin-elbow-bridge' and span==0:continue
                # Segment versus expanded AABB; corner false positives reject
                # the route conservatively rather than claiming a CAD fit.
                lo,hi=0.,1.
                for k in range(3):
                    delta=b[k]-a[k];lower=bounds[0][k]-radius;upper=bounds[1][k]+radius
                    if abs(delta)<1e-10:
                        if a[k]<lower or a[k]>upper:lo,hi=1.,0.;break
                    else:
                        first,last=sorted(((lower-a[k])/delta,(upper-a[k])/delta))
                        lo=max(lo,first);hi=min(hi,last)
                        if lo>hi:break
                if lo<=hi:issues.append('rigid_envelope:'+name)
    if route_pair_overlap(paths[0],radius,paths[1],radius):issues.append('pair_overlap')
    return sorted(set(issues))


def _cambered_leaves(vertices,model,radius):
    """Bounded original foil camber; qualitative family reference, not CFD CAD."""
    from assembly_geometry import _tri
    out=[];amplitude=radius*(.052 if model['family']=='arctic-pressure' else .035)
    count=model['blades']
    for i in range(0,len(vertices),18):
        points=[]
        for offset in (0,6,12):
            x,y,z=vertices[i+offset:i+offset+3];fraction=min(1.,math.hypot(x,y)/max(radius,1.))
            z+=amplitude*fraction*math.sin(count*math.atan2(y,x)+.65)
            points.append((x,y,z))
        if abs(vertices[i+5])>.9:
            # All cap triangles sample the same analytic foil surface. Shared
            # vertices therefore need the same normal, rather than unrelated
            # flat triangle normals that look like cracked plastic. Side walls
            # retain their real hard edges; positions and triangles are exact.
            sign=1 if vertices[i+5]>0 else -1
            for x,y,z in points:
                phi=math.atan2(y,x);psi=count*phi+.65
                grad_x=amplitude/radius*(math.cos(phi)*math.sin(psi)-count*math.sin(phi)*math.cos(psi))
                grad_y=amplitude/radius*(math.sin(phi)*math.sin(psi)+count*math.cos(phi)*math.cos(psi))
                normal=_mul(_unit((-grad_x,-grad_y,1.)),sign)
                out.extend((x,y,z,*normal))
        else:_tri(out,*points)
    return tuple(out)


def _leaf_geometry(model,radius,depth):
    from assembly_geometry import fan_rotor,ring
    profile=dict(model)
    profile['shape']={'noctua-g2':'claw','noctua-sterrox':'swept','arctic-pressure':'wide',
        'corsair-airguide':'paired','nzxt-pressure':'claw','fractal-notched':'claw',
        'lian-li-sl':'wide','lian-li-216':'paired','cm-silencio':'wide','cm-mobius':'swept',
        'thermalright-slim':'swept','thermalright-c12':'wide','msi-lcp':'swept',
        'phanteks-d30':'wide','phanteks-t30':'swept'}.get(model['family'],model.get('shape','swept'))
    # Mobius' joining ring must stay planar and rotate with its leaves. Applying
    # foil camber to a complete annulus would turn the physical ring wavy.
    profile['outer_ring']=False
    out=list(_cambered_leaves(fan_rotor(profile,radius*1.07,depth),model,radius))
    if model.get('outer_ring'):
        out.extend(ring(radius*.994,radius*.968,depth,40))
    if model.get('reverse_blade'):
        # Reverse-pitch products have a mirrored foil, not a verified reverse
        # rotation. Reflect normals and winding together; the tach policy stays.
        mirrored=[]
        for start in range(0,len(out),18):
            for offset in (0,12,6):
                x,y,z,nx,ny,nz=out[start+offset:start+offset+6]
                mirrored.extend((-x,y,z,-nx,ny,nz))
        out=mirrored
    if model['family'] in ('noctua-sterrox','noctua-g2') and model.get('blade_geometry_reviewed') and not model.get('foil_profile'):
        # Three qualitative acceleration channels per leaf, all attached to and
        # rotating with the foil. Their dimensions are reference construction.
        sweep=46 if model['family']=='noctua-g2' else 52
        for i in range(model['blades']):
            for channel in (-1,0,1):
                points=[]
                for t in (0.,.33,.66,1.):
                    r=radius*(.65+.20*t);a=math.radians(90+sweep-i*360/model['blades']+channel*3.5+4*(t-.5))
                    x,y=math.cos(a)*r,math.sin(a)*r
                    z=depth/2+.24+radius*.035*(r/radius)*math.sin(model['blades']*math.atan2(y,x)+.65)
                    points.append((x,y,z))
                out.extend(_tube(points,.30,6))
    return tuple(out)


class _Builder:
    def __init__(self,level):
        self.level=level if level in ('eco','balanced','close') else 'balanced'
        self.segments={'eco':16,'balanced':24,'close':32}[self.level]
        self.static=defaultdict(list);self.rotors=[];self.fans=[];self.parts=[];self.wire_anchors=[];self.connection_issues=[];self.aio_hoses=[]

    def put(self,name,vertices,tint,center=(0.,0.,0.),basis=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.)),component='cooler',part='cooler:cpu',alpha=1.):
        if alpha!=1.:
            from assembly_geometry import color
            tint=tuple(tint[:3])+(alpha,) if isinstance(tint,tuple) and len(tint)==4 else color(tint,alpha=alpha)
        if vertices:self.static[(name,tint,component,part)].extend(_transform(vertices,center,basis))

    def box(self,name,size,tint,center,basis,component='cooler',part='cooler:cpu',bevel=False):
        from assembly_geometry import box
        from assembly_case_detail import chamfer_box
        self.put(name,chamfer_box(*size,bevel=.7) if bevel else box(*size),tint,center,basis,component,part)

    def tube(self,name,points,radius,tint,component='cooler',part='cooler:cpu'):
        self.put(name,_tube(points,radius,{'eco':6,'balanced':8,'close':10}[self.level]),tint,component=component,part=part)

    def finish(self):
        from assembly_geometry import Mesh,color
        return tuple(Mesh(name,tuple(vertices),tint if isinstance(tint,tuple) and len(tint)==4 else color(tint),component=component,part_id=part) for (name,tint,component,part),vertices in self.static.items())+tuple(self.rotors)


def _fan(builder,model,center,normal,up,*,component='fans',part='fans:front:0',name='case-fan',role='case',direction='intake',rotor_direction=1,wire_sign_override=None):
    """A pierced static frame and a separate genuinely moving leaf/hub mesh."""
    from assembly_geometry import Mesh,color,fan_rotor,ring,box
    from assembly_detail import perforated_plate,chamfer_rect
    size=model['size_mm'];width=model.get('width_mm',size);depth=model['depth_mm'];basis=_basis(normal,up)
    radius=size*.465;corner=size*.095
    pitch=model.get('mount_pitch_mm') or {120:105.,140:124.5}.get(size,size*.83)
    axes=model.get('mount_pitch_axes_mm')
    pitch_x,pitch_y=axes if model.get('mount_pitch_axes_verified') and isinstance(axes,(list,tuple)) and len(axes)==2 else (pitch,pitch)
    hole_radius=(model.get('mount_hole_diameter_mm') or size*.036)/2
    corner=min(corner,max(1.,(width+size-pitch_x-pitch_y)/2-hole_radius*math.sqrt(2)-1.))
    if model.get('frameless'):
        pass  # A fin-supported impeller must not acquire a fictional square frame.
    elif model.get('frame')=='round':
        frame=ring(size*.50,radius,depth,builder.segments)
        builder.put(name+'-frame',frame,model['frame_color'],center,basis,component,part)
        for x in (-1,1):
            for y in (-1,1):
                p=_add(center,_add(_mul(basis[0],x*pitch_x/2),_mul(basis[1],y*pitch_y/2)))
                builder.put(name+'-frame',perforated_plate(chamfer_rect(size*.19,size*.19,1.2),[(0.,0.,hole_radius)],depth,segments=12),model['frame_color'],p,basis,component,part)
    else:
        # The large circular aperture is actual missing geometry; no solid slab
        # or dark painted disk can obscure the blades from either face.
        holes=[(0.,0.,radius)]+[(x*pitch_x/2,y*pitch_y/2,hole_radius) for x in (-1,1) for y in (-1,1)]
        frame=perforated_plate(chamfer_rect(width,size,corner),holes,depth,segments=builder.segments)
        builder.put(name+'-frame',frame,model['frame_color'],center,basis,component,part)
    if model.get('pads'):
        for x in (-1,1):
            for y in (-1,1):
                for side in (-1,1):
                    round_pad=model.get('pad_style')=='round'
                    px=x*pitch_x/2 if round_pad else x*min(width*.414,width/2-size*.08)
                    py=y*pitch_y/2 if round_pad else y*min(size*.414,size/2-size*.08)
                    p=_add(center,_add(_mul(basis[0],px),_add(_mul(basis[1],py),_mul(basis[2],side*(depth/2+.35)))))
                    pad_radius=min(size*.08,width/2-pitch_x/2-.25,size/2-pitch_y/2-.25)
                    pad=(ring(pad_radius,hole_radius,.7,12) if round_pad else
                         perforated_plate(chamfer_rect(size*.16,size*.16,2),[(x*pitch_x/2-px,y*pitch_y/2-py,hole_radius)],.7,segments=12))
                    builder.put(name+'-pads',pad,'#74584d' if model['family'].startswith('noctua') else '#141b20',p,basis,component,part)
    # Rear stator arms terminate at the frame and hub, never rotating with leaves.
    stator_z=-depth*.35;hub=size*model.get('hub_ratio',.25)*.44
    stators=model.get('stator_vanes',4)
    for i in range(stators):
        angle=i*math.tau/stators+.3
        a=(math.cos(angle)*hub,math.sin(angle)*hub,stator_z)
        b=(math.cos(angle+.16)*radius,math.sin(angle+.16)*radius,stator_z)
        builder.put(name+'-stator',_tube([a,b],size*.012,6),model['frame_color'],center,basis,component,part)
    leaf_depth=min(depth*.19,4.5)
    rotor=list(_leaf_geometry(model,radius,leaf_depth))
    rotor.extend(ring(hub,0,leaf_depth*2,builder.segments))
    builder.rotors.append(Mesh(name+'-leaves-hub',_transform(rotor,(0.,0.,0.),basis,False),color(model['blade_color']),center,component,True,-1 if rotor_direction==-1 else 1,basis[2],part))
    if model.get('rgb'):
        glow='#80c9d4'
        builder.put(name+'-static-rgb-hub',ring(hub*.85,hub*.71,.65,builder.segments),glow,_add(center,_mul(basis[2],leaf_depth+1)),basis,component,part)
        if model.get('frame_rgb_ring'):
            builder.put(name+'-static-rgb-rim',ring(size*.496,size*.481,1.,builder.segments),glow,_add(center,_mul(basis[2],depth/2+.55)),basis,component,part)
        elif model.get('frame_rgb_outline')=='square':
            for sign in (-1,1):
                for side in (-1,1):
                    builder.put(name+'-square-rgb-rim',box(width*.77,2,.8),glow,
                        _add(center,_add(_mul(basis[1],sign*size*.477),_mul(basis[2],side*(depth/2-.4)))),basis,component,part)
                    builder.put(name+'-square-rgb-rim',box(2,size*.77,.8),glow,
                        _add(center,_add(_mul(basis[0],sign*width*.477),_mul(basis[2],side*(depth/2-.4)))),basis,component,part)
        elif model.get('frame_rgb_polygon') in (6,12):
            sides=model['frame_rgb_polygon'];rad=size*.465
            points=[(rad*math.cos(i*math.tau/sides+math.pi/6),rad*math.sin(i*math.tau/sides+math.pi/6),depth/2+.7) for i in range(sides+1)]
            builder.put(name+'-stationary-polygon-light-ring',_tube(points,size*.009,6),glow,center,basis,component,part)
        elif model.get('frame_rgb_sides') or model['family'] in ('lian-li-sl','lian-li-infinity'):
            for sign in (-1,1):
                builder.put(name+'-side-rgb',box(2,size*.74,depth*.45),glow,_add(center,_mul(basis[0],sign*width*.49)),basis,component,part)
                builder.put(name+'-side-aluminium',box(2,size*.86,depth*.72),'#a6afb5',_add(center,_mul(basis[0],sign*width*.47)),basis,component,part)
        if model['family']=='lian-li-infinity':
            for layer in range(3):builder.put(name+'-infinity-hub-rings',ring(hub*(.94-layer*.18),hub*(.89-layer*.18),.4,builder.segments),glow,_add(center,_mul(basis[2],leaf_depth+1.1+layer*.25)),basis,component,part)
    if model['family']=='lian-li-p28':
        for sign in (-1,1):builder.put(name+'-brushed-side-trim',box(2,size*.80,depth*.64),'#a2abb0',_add(center,_mul(basis[0],sign*width*.485)),basis,component,part)
    if model.get('interlock_bridges'):
        # Source-observed connector covers stay outside the actual fan opening.
        for sign in (-1,1):
            builder.put(name+'-interlock-cover',box(width*.31,2,depth*.56),'#3f4a50',_add(center,_mul(basis[1],sign*(size/2-1))),basis,component,part)
    if model.get('fixed_white_hub_window') and model.get('hub_window_face')=='front':
        # Observed front bearing window; coil count/clearance are sampled.
        face=_add(center,_mul(basis[2],leaf_depth+.65))
        builder.put(name+'-bearing-window-bezel',ring(hub*.91,hub*.83,.65,builder.segments),'#aab4b6',face,basis,component,part)
        builder.put(name+'-fixed-white-bearing-window',ring(hub*.83,hub*.74,.4,builder.segments),'#f4f1dc',_add(face,_mul(basis[2],.3)),basis,component,part)
        for index in range(8):
            angle=index*math.tau/8
            location=_add(face,_add(_mul(basis[0],hub*.54*math.cos(angle)),_mul(basis[1],hub*.54*math.sin(angle))))
            builder.put(name+'-bearing-coil-sampling',box(hub*.18,hub*.25,.6),'#ad844d',location,basis,component,part)
        builder.put(name+'-bearing-spindle',ring(hub*.28,0,.7,builder.segments),'#c2b27e',_add(face,_mul(basis[2],.2)),basis,component,part)
    if model.get('hub_display'):
        # A blank, stationary screen; no invented readings or screen animation.
        face=_add(center,_mul(basis[2],depth/2+.7))
        builder.put(name+'-stationary-lcd-bezel',ring(size*.182,0,1.2,builder.segments),'#73848c',face,basis,component,part)
        builder.put(name+'-stationary-blank-lcd',ring(size*.166,0,.8,builder.segments),'#11232b',_add(face,_mul(basis[2],1)),basis,component,part)
    elif model.get('metal_hub'):
        # Circular metal cap is rotationally symmetric; no separate animation.
        builder.put(name+'-metal-hub-cap',ring(hub*.82,0,.6,builder.segments),'#a8b4b9',_add(center,_mul(basis[2],leaf_depth+1)),basis,component,part)
    if model.get('directional_grille'):
        # Original reference vane sampling, not an asserted retail vane count.
        for i in range(12 if builder.level=='eco' else 18):
            a=i*math.tau/(12 if builder.level=='eco' else 18)
            path=[(math.cos(a+t*.28)*radius*t,math.sin(a+t*.28)*radius*t,depth/2+1.2) for t in (.27,.52,.76,1.)]
            builder.put(name+'-stationary-directional-grille-reference',_tube(path,size*.008,6),model['frame_color'],center,basis,component,part)
    builder.fans.append(dict(part_id=part,model_id=model['id'],role=role,position=tuple(center),axis=tuple(basis[2]),
        diameter_mm=size,direction=direction,rpm=None,rotation_default='static',blade_count_verified=model.get('blade_count_verified',False),
        rotation_direction_verified=False,blade_geometry_reviewed=model.get('blade_geometry_reviewed',False)))
    wire_sign=-1 if component=='fans' and part.startswith(('fans:rear:','fans:bottom:')) else 1
    if type(wire_sign_override) is int and wire_sign_override in (-1,1):wire_sign=wire_sign_override
    wire_out=_mul(basis[0],wire_sign)
    if (role=='case' and model['family'] not in ('lian-li-sl','corsair-lx') and not model.get('hub_display') or role=='cpu_main' and (model['id'].startswith('noctua-') or model.get('power_connector_verified'))):
        # Standard PWM power only. Proprietary lighting/controller wiring and
        # AIO internal splitters are deliberately not invented or cross-wired.
        root=_add(center,_add(_mul(wire_out,width*.48),_mul(basis[1],size*.35)))
        end=_add(root,_mul(wire_out,11))
        builder.tube(name+'-power-lead',[root,end],1.4,'#222c33',component,part)
        builder.put(name+'-power-connector',box(7,5,3),'#273039',end,basis,component,part)
        builder.wire_anchors.append(dict(id=part+':power:'+str(len(builder.wire_anchors)),position=_add(end,_mul(wire_out,3.5)),normal=wire_out,along=basis[2],
            kind='fan4',owner=part,header='fan',model_id=model['id'],connector_rendered=True,position_verified=False,placement='schematic_attached_lead',role=role))
    if role=='case' and model.get('lighting_connector_verified') and model.get('lighting_connector')=='argb3':
        root=_add(center,_add(_mul(wire_out,width*.48),_mul(basis[1],-size*.35)));end=_add(root,_mul(wire_out,11))
        builder.tube(name+'-argb-lead',[root,end],1.2,'#222c33',component,part)
        builder.put(name+'-argb-connector',box(7,5,3),'#273039',end,basis,component,part)
        builder.wire_anchors.append(dict(id=part+':argb:'+str(len(builder.wire_anchors)),position=_add(end,_mul(wire_out,3.5)),normal=wire_out,along=basis[2],
            kind='argb3',owner=part,header='argb',model_id=model['id'],connector_rendered=True,position_verified=False,placement='schematic_attached_lead',role=role))


def _reference_fan(cooler):
    from cooling_pack_runtime045 import bundled_fan
    bundled=bundled_fan(cooler)
    if bundled:return bundled
    fan=get_fan(cooler.get('fan_model'))
    if fan:return fan
    size=cooler.get('fan_reference_mm',120)
    return dict(id=('generic-radiator-fan-'+str(size)+'-reference') if cooler.get('_neutral_radiator_fan') else cooler['id']+'-documented-fan-reference',size_mm=size,width_mm=size,depth_mm=cooler.get('fan_reference_depth_mm',25 if size>=100 else 15),
                family=cooler.get('fan_family','stock-reference'),blades=cooler.get('fan_reference_blades',7),blade_count_verified=cooler.get('fan_blade_count_verified',False),shape='wide',
                frame='round' if cooler['kind'] in ('stock_intel','stock_amd') else 'square',frame_color='#242c30',blade_color='#3d474d',hub_ratio=.27,outer_ring=cooler.get('fan_outer_ring',False),
                rgb=cooler.get('fan_reference_rgb',cooler['kind']=='stock_prism'),frame_rgb_ring=cooler['kind']=='stock_prism',
                frameless=cooler.get('frameless_fan',False),
                dimensions_verified=cooler.get('fan_dimensions_verified',False),power_connector_verified=cooler.get('fan_power_connector_verified',False))


def _cpu_frame(anchors):
    cpu=anchors.get('cpu',{});p=cpu.get('position')
    if not isinstance(p,(tuple,list)) or len(p)!=3:p=tuple(cpu.get(axis,0.) for axis in ('x','y','z'))
    if not all(type(v) in (int,float) and math.isfinite(v) for v in p):p=(0.,0.,0.)
    return tuple(p),_basis(cpu.get('normal',(-1.,0.,0.)),cpu.get('up',cpu.get('u',(0.,1.,0.))))


def _local_point(p,basis,a,b,c):return _add(p,_add(_mul(basis[0],a),_add(_mul(basis[1],b),_mul(basis[2],c))))


def _passive(builder,cooler,p,basis):
    """Source-known thirteen widely spaced fins; hole layout is illustrative."""
    from assembly_detail import perforated_plate,chamfer_rect
    w,h,d=(cooler['dimensions_mm'][key] for key in ('width','height','depth'))
    def point(a,b,c):return _local_point(p,basis,a,b,c)
    builder.box('cooler-passive-contact',(40,40,4),'#a78c72',point(0,0,2),basis,bevel=True)
    plate_basis=(basis[1],basis[2],basis[0]);fin_height=h-28;fin_depth=d*.90
    holes=[(x*fin_depth*.25,y*fin_height*.25,4.5) for x in (-1,1) for y in (-1,1)]
    if builder.level!='eco':holes.extend((0,y*fin_height*.25,4.5) for y in (-1,0,1))
    plate=perforated_plate(chamfer_rect(fin_depth,fin_height,3),holes,1.5,segments=12)
    for index in range(cooler['documented_fin_count']):
        x=(index-(cooler['documented_fin_count']-1)/2)*(w-3)/(cooler['documented_fin_count']-1)
        builder.put('cooler-passive-perforated-fin-reference',plate,cooler.get('fin_color','#b4bec4'),point(x,0,28+fin_height/2),plate_basis)
    for index in range(cooler.get('heatpipes',0)):
        x=(index-(cooler['heatpipes']-1)/2)*18
        builder.tube('cooler-passive-heatpipes',[point(x,-d*.27,h-3),point(x,-d*.27,14),point(x,0,5),point(x,d*.27,14),point(x,d*.27,h-3)],3,'#a9b3b8')
    builder.parts.append(dict(id='cooler:cpu',label=cooler['label'],kind='air_cooler',model_id=cooler['id']))


def _air(builder,cooler,p,basis):
    if cooler['kind']=='passive_tower':
        _passive(builder,cooler,p,basis)
        return
    if cooler['kind'] in ('dual_top_flow','radial_tower') or cooler.get('c_shape'):
        _special_air(builder,cooler,p,basis)
        return
    from assembly_geometry import box,ring
    w,h,d=(cooler['dimensions_mm'][key] for key in ('width','height','depth'))
    kind=cooler['kind'];fan=_reference_fan(cooler);u,v,n=basis
    def point(a,b,c):return _local_point(p,basis,a,b,c)
    builder.box('cooler-copper-contact',(38,38,4),'#a58264',point(0,0,2),basis,bevel=True)
    builder.box('cooler-mounting-bridge',(65,13,4),'#9da6ab',point(0,0,6),basis)
    fin_count={'eco':12,'balanced':24,'close':44}[builder.level]
    if kind in ('stock_intel','stock_amd','stock_prism'):
        finheight=max(8,h-fan['depth_mm']-8);r=min(w,d)*.43
        if kind=='stock_prism':
            for i in range(fin_count):builder.put('cooler-prism-fins',box(w*.88,d*.88,.65),'#aab4bb',point(0,0,8+i*(finheight-2)/max(1,fin_count-1)),basis)
        else:
            # Radial aluminium fins surround a real cylindrical centre.
            radial=28 if builder.level=='eco' else 48 if builder.level=='balanced' else 72
            for i in range(radial):
                angle=i*math.tau/radial;radial_dir=_add(_mul(u,math.cos(angle)),_mul(v,math.sin(angle)))
                tangent=_cross(n,radial_dir);fb=(radial_dir,tangent,n)
                center=_add(point(0,0,6+finheight/2),_mul(radial_dir,r*.68))
                builder.box('cooler-radial-fins',(r*.62,.65,finheight),'#aab4bb',center,fb)
            builder.put('cooler-core',ring(r*.36,0,finheight,builder.segments),'#a58264' if kind=='stock_intel' else '#8c969d',point(0,0,6+finheight/2),basis)
        center=point(0,0,h-fan['depth_mm']/2)
        _fan(builder,fan,center,n,u,component='cooler',part='cooler:cpu',name='cooler-stock-fan',role='cpu_main')
        if kind=='stock_intel':builder.put('cooler-intel-blue-rim',ring(fan['size_mm']*.50,fan['size_mm']*.474,.7,builder.segments),'#377fa8',point(0,0,h+.35),basis)
    elif kind=='low_profile':
        top=h-fan['depth_mm'];bottom=5
        for i in range(fin_count):
            x=-w*.48+w*.96*i/max(1,fin_count-1)
            builder.put('cooler-low-profile-fins',box(.5,d*.96,max(1,top-bottom-.5)),cooler.get('fin_color','#aab4bb'),point(x,0,(top+bottom)/2),basis)
        _fan(builder,fan,point(0,0,h-fan['depth_mm']/2),n,u,component='cooler',part='cooler:cpu',name='cooler-slim-fan',role='cpu_main')
    else:
        # Tower width is tangent to the board; outward height is along CPU normal.
        bank_depth=cooler.get('heatsink_depth_mm',cooler.get('heatsink_dimensions_mm',{}).get('depth',d if cooler.get('fan_layout')=='center' else d-25))
        bank_offset=-fan['depth_mm']/2 if cooler.get('fan_layout')=='center_rear' else 0
        gap=fan['depth_mm']+4 if kind=='dual_tower' else 0
        bank_thickness=(bank_depth-gap)/2 if gap else bank_depth
        banks=(-gap/2-bank_thickness/2,gap/2+bank_thickness/2) if gap else (0.,)
        finbottom=max(25,h-fan['size_mm']+3);fintop=h-5
        for bank_index,bank in enumerate(banks):
            for i in range(fin_count):
                z=finbottom+(fintop-finbottom)*i/max(1,fin_count-1)
                width=w*.95
                if cooler.get('fin_style')=='checker_cut' and i%4 in (0,1):width*=.93
                if cooler.get('asymmetric') and bank_index==0:width*=.93
                builder.put('cooler-tower-fins',box(width,bank_thickness,.55),cooler.get('fin_color','#abb5bd'),point(0,bank+bank_offset,z),basis)
            if cooler.get('top_style') in ('matrix_caps','dark_caps','brushed_caps','stealth_caps'):
                builder.box('cooler-tower-top-caps',(w*.96,bank_thickness,3),'#232c32',point(0,bank,h-2),basis,bevel=True)
                if cooler.get('top_style')=='matrix_caps':
                    for a in range(6):
                        for b in range(3):builder.box('cooler-matrix-inlays',(w*.095,bank_thickness*.18,.65),'#425059',point((a-2.5)*w*.135,bank+(b-1)*bank_thickness*.26,h-.12),basis)
                elif cooler.get('top_style')=='brushed_caps':
                    for line in range(5):builder.box('cooler-brushed-top-inlays',(w*.77,.38,.2),'#5a666e',point(0,bank+(line-2)*bank_thickness*.12,h-.38),basis)
                elif cooler.get('top_style')=='stealth_caps':
                    builder.box('cooler-stealth-top-inlay',(w*.78,bank_thickness*.64,.5),'#3d494f',point(0,bank,h-.30),basis,bevel=True)
        fan_z=(finbottom+fintop)/2
        for i in range(cooler['fan_count']):
            fan_models=cooler.get('fan_models',[])
            selected_fan=get_fan(fan_models[i]) if i<len(fan_models) else dict(fan)
            if not selected_fan:selected_fan=dict(fan)
            if i<len(cooler.get('fan_sizes',[])):
                selected_fan['size_mm']=selected_fan['width_mm']=cooler['fan_sizes'][i]
                if cooler['fan_sizes'][i]!=fan['size_mm']:
                    selected_fan['id']=cooler['id']+'-documented-'+str(cooler['fan_sizes'][i])+'mm-fan'
                    selected_fan['blade_geometry_reviewed']=False
                    selected_fan['blade_count_verified']=False
            if i<len(cooler.get('fan_depths',[])):selected_fan['depth_mm']=cooler['fan_depths'][i]
            selected_z=min(fan_z,h-selected_fan['size_mm']/2-.5)
            fd=selected_fan['depth_mm']
            if cooler.get('fan_layout')=='center':y=0.
            elif cooler.get('fan_layout')=='center_rear':y=bank_offset if i==0 else bank_depth/2+fd/2+bank_offset
            else:y=-bank_depth/2-fd/2 if i==0 else (0 if kind=='dual_tower' else bank_depth/2+fd/2)
            relative=cooler.get('fan_relative_directions',[]) if cooler.get('relative_rotation_verified') else []
            rotor_direction=relative[i] if i<len(relative) else 1
            _fan(builder,selected_fan,point(0,y,selected_z),_mul(v,-1),u,component='cooler',part='cooler:cpu',name='cooler-tower-fan',role='cpu_main',rotor_direction=rotor_direction)
            # A pair of bent retaining wires is static, separate from the rotor.
            for sign in (-1,1):builder.tube('cooler-fan-wire-clips',[point(sign*w*.48,y-8,selected_z-30),point(sign*w*.5,y+7,selected_z-30),point(sign*w*.5,y+7,selected_z+30),point(sign*w*.48,y-8,selected_z+30)],.7,'#9da8b0')
        if cooler.get('top_style') in ('mesh_bridge','mesh_bridge_rgb','assassin_shell'):
            from assembly_detail import perforated_plate,chamfer_rect
            holes=[]
            for index in range(12):
                x=(index-5.5)*w*.065
                holes.append(tuple((x+a,b) for a,b in chamfer_rect(w*.028,bank_depth*.68,1)))
            builder.put('cooler-mesh-top-cover',perforated_plate(chamfer_rect(w*.98,bank_depth,3),holes,2,segments=12),'#1e292f',point(0,bank_offset,h-1),basis)
            if cooler.get('top_style')=='mesh_bridge_rgb':
                for sign in (-1,1):builder.box('cooler-top-accent-bars',(w*.83,2,.8),'#80b8c5',point(0,bank_offset+sign*bank_depth*.43,h+.15),basis)
            if cooler.get('top_style')=='assassin_shell':
                for sign in (-1,1):builder.box('cooler-assassin-side-shell',(2,bank_depth,h-finbottom),'#29353c',point(sign*(w/2-1),bank_offset,(h+finbottom)/2),basis,bevel=True)
                builder.box('cooler-assassin-turquoise-mark',(8,8,.8),'#65aab2',point(w*.32,bank_offset+bank_depth*.25,h+.25),basis)
    pipes=cooler.get('heatpipes',0)
    if pipes:
        for i in range(pipes):
            a=(i-(pipes-1)/2)*min(11,w/(pipes+2))
            if kind in ('low_profile','stock_prism'):
                points=[point(a,-d*.32,h*.48),point(a,-d*.32,5),point(a,d*.32,5),point(a,d*.32,h*.48)]
            else:points=[point(a,-d*.28,h-1),point(a,-d*.28,12),point(a,0,4),point(a,d*.28,12),point(a,d*.28,h-1)]
            builder.tube('cooler-heatpipes',points,2.8,cooler.get('pipe_color','#9fa8ad' if kind.startswith('dual') or kind=='single_tower' else '#af8868'))
            if kind in ('single_tower','dual_tower'):
                for side in (-1,1):builder.put('cooler-pipe-caps',ring(3.2,0,2,builder.segments),'#89969f',point(a,side*d*.28,h-1),basis)
    builder.parts.append(dict(id='cooler:cpu',label=cooler['label'],kind='air_cooler',model_id=cooler['id']))


def _special_air(builder,cooler,p,basis):
    """C-shaped top-flow stacks and circular fin banks; dimensions beyond the
    documented envelope remain original reference construction, not vendor CAD.
    """
    from assembly_geometry import box,ring,extrude
    from assembly_detail import chamfer_rect
    w,h,d=(cooler['dimensions_mm'][key] for key in ('width','height','depth'))
    u,v,n=basis;fan=_reference_fan(cooler)
    def point(a,b,c):return _local_point(p,basis,a,b,c)
    builder.box('cooler-special-copper-contact',(38,38,4),'#a98d70',point(0,0,2),basis,bevel=True)
    builder.box('cooler-special-mounting-bridge',(62,14,4),'#9aa7ae',point(0,0,6),basis)
    if cooler['kind']=='radial_tower':
        outer=cooler.get('radial_outer_reference_mm',126)/2;inner=cooler.get('radial_inner_reference_mm',74)/2
        fb=_basis(_mul(v,-1),u);count={'eco':28,'balanced':44,'close':64}[builder.level]
        center_z=h-outer-3;bank_depth=d*.18
        for side in (-1,1):
            center=point(0,side*d*.32,center_z)
            radius=outer*.84 if side<0 else outer
            bore=31. if side<0 else inner
            for index in range(count):
                a=index*math.tau/count;radial=_add(_mul(u,math.cos(a)),_mul(n,math.sin(a)))
                tangent=_cross(fb[2],radial)
                builder.put('cooler-radial-tower-fin-reference',box(radius-bore,.55,bank_depth),cooler.get('fin_color','#879198'),
                    _add(center,_mul(radial,(radius+bore)/2)),(radial,tangent,fb[2]))
            builder.put('cooler-radial-tower-inner-rim-reference',ring(bore+1,bore-1,bank_depth,builder.segments),cooler.get('pipe_color','#8d969b'),center,fb)
        _fan(builder,fan,point(0,0,center_z),_mul(v,-1),u,component='cooler',part='cooler:cpu',name='cooler-frameless-middle-fan',role='cpu_main')
        for index in range(cooler.get('heatpipes',0)):
            x=(index-(cooler['heatpipes']-1)/2)*12
            builder.tube('cooler-radial-heatpipe-reference',[point(x,-d*.32,center_z-outer+5),point(x,-d*.32,13),point(x,0,5),point(x,d*.32,13),point(x,d*.32,center_z-outer+5)],3,cooler.get('pipe_color','#9ea8ad'))
    else:
        dual=cooler['kind']=='dual_top_flow'
        if dual:
            banks=[(h*.19,h*.36,w*.70,d*.73),(h*.57,h-fan['depth_mm']-2,w*.96,d*.90)]
            placements=[h-fan['depth_mm']/2,(h*.36+h*.57)/2]
        elif cooler.get('fan_placement')=='under':
            lower=h-22.;banks=[(lower,h,w*.96,d*.94)]
            placements=[lower-fan['depth_mm']/2-2]
        else:
            upper=h-fan['depth_mm']-1;lower=max(22.,upper-min(36.,h*.29))
            banks=[(lower,upper,w*.96,d*.94)];placements=[h-fan['depth_mm']/2]
        fin_count={'eco':12,'balanced':32,'close':48}[builder.level]
        for bottom,top,width,depth in banks:
            plate=extrude(chamfer_rect(depth,top-bottom,2.),.5)
            for i in range(fin_count):
                x=-width/2+.25+(width-.5)*i/max(1,fin_count-1)
                builder.put('cooler-top-flow-fin-reference',plate,cooler.get('fin_color','#aeb8bf'),point(x,0,(top+bottom)/2),(v,n,u))
        for i,z in enumerate(placements):
            models=cooler.get('fan_models',[]);selected=get_fan(models[i]) if i<len(models) else dict(fan)
            if not selected:selected=dict(fan)
            _fan(builder,selected,point(0,0,z),n,u,component='cooler',part='cooler:cpu',name='cooler-top-flow-fan',role='cpu_main')
        for i in range(cooler.get('heatpipes',0)):
            x=(i-(cooler['heatpipes']-1)/2)*min(10.,w/(cooler['heatpipes']+2))
            z=(banks[-1][0]+banks[-1][1])/2
            # Curved, continuous C bends meet the contact and fin bank, rather
            # than a pair of sharp hanging elbows. Routing is still reference.
            route=_curve([point(x,0,5),point(x,-d*.25,5),point(x,-d*.44,5),point(x,-d*.44,18)],5)
            route+=_curve([route[-1],point(x,-d*.44,z-14),point(x,-d*.44,z),point(x,-d*.32,z)],6)[1:]
            pipe_default='#aab4b8' if cooler['id'].startswith('noctua-') else '#333e45'
            builder.tube('cooler-c-shaped-heatpipes',route,2.8,cooler.get('pipe_color',pipe_default))
    builder.parts.append(dict(id='cooler:cpu',label=cooler['label'],kind='air_cooler',model_id=cooler['id']))


_MOUNT_NORMALS={'front':(0.,0.,1.),'rear':(0.,0.,-1.),'top':(0.,1.,0.),'bottom':(0.,-1.,0.),'side':(1.,0.,0.)}


def _mount_plane(mount,dimensions,inset,planes=None):
    w,h,d=dimensions;n=_MOUNT_NORMALS[mount]
    plane=planes.get(mount) if isinstance(planes,dict) else None
    if isinstance(plane,dict):
        p=plane.get('position');normal=plane.get('normal');up=plane.get('up',(0.,1.,0.))
        if isinstance(p,(tuple,list)) and len(p)==3 and all(type(v) in (int,float) and math.isfinite(v) for v in p):
            n=_unit(normal,n);long_axis=_unit(up,(0.,0.,1.) if mount in ('top','bottom') else (0.,1.,0.))
            long_axis=_sub(long_axis,_mul(n,_dot(long_axis,n)))
            if _dot(long_axis,long_axis)<1e-8:long_axis=(0.,0.,1.) if abs(n[1])>.8 else (0.,1.,0.)
            long_axis=_mul(_unit(long_axis),-1.)
            width_axis=_unit(_cross(long_axis,n));long_axis=_unit(_cross(n,width_axis))
            basis=(width_axis,long_axis,n)
            default_span=(w-24,d-32) if mount in ('top','bottom') else (w-24,h-40) if mount in ('front','rear') else (max(0,d*.47),h-40)
            span=plane.get('span_mm',default_span)
            # A source-qualified plane denotes the OUTWARD hardware face; the
            # actual fan/radiator thickness extends inward. No legacy10mm gap.
            return _sub(p,_mul(n,max(0.,inset-10.))),basis,span
    if mount in ('top','bottom'):
        p=(0.,n[1]*(h/2-inset),0.);basis=_basis(n,(1.,0.,0.));span=(w-24,d-32)
    elif mount in ('front','rear'):
        p=(0.,0.,n[2]*(d/2-inset));basis=_basis(n,(1.,0.,0.));span=(w-24,h-40)
    else:
        p=(w/2-inset,0.,d*.23);basis=_basis(n,(0.,0.,1.));span=(max(0,d*.47),h-40)
    return p,basis,span


def _mount_check(case,mount,size,count):
    mounts=case.get('fan_mounts',[]) if isinstance(case,dict) else []
    matches=[m for m in mounts if isinstance(m,dict) and m.get('position')==mount]
    if not matches:return 'unverified'
    valid=[m for m in matches if size in m.get('size_mm',[]) and type(m.get('count')) is int and count<=m['count']]
    return 'documented_fan_mount' if valid else 'unsupported'


def _radiator(builder,cooler,mount,dimensions,part='cooler:radiator',planes=None):
    from assembly_geometry import ring
    from assembly_radiator044 import build_radiator_detail
    rad=cooler['radiator_mm'];length,width,thick=(rad[k] for k in ('length','width','thickness'))
    fan=_reference_fan(cooler);layout=cooler.get('_radiator_fan_layout','single')
    extra=fan['depth_mm']+.8 if layout=='push_pull' else 0.
    p,basis,span=_mount_plane(mount,dimensions,thick/2+10+extra,planes)
    if width>span[0]+1 or length>span[1]+1:return None
    lfiii_front=bool(cooler.get('id') in _LFIII_FACTORY_IDS and mount=='top')
    if lfiii_front:basis=(_mul(basis[0],-1.),_mul(basis[1],-1.),basis[2])
    profile=cooler.get('_radiator_profile')
    # A standalone radiator's photographed front ports face the case interior.
    # Rotate about the long axis (proper rigid pose), never mirror its geometry.
    detail_basis=(_mul(basis[0],-1),basis[1],_mul(basis[2],-1)) if profile else basis
    detail=build_radiator_detail(builder,dict(rad,fan_size_mm=fan['size_mm'],fan_count=cooler['fan_count'],fan_mount_pitch_mm=fan.get('mount_pitch_mm')),p,detail_basis,part,profile)
    if cooler.get('pump_location')=='radiator':
        builder.box('cooler-radiator-integrated-pump',(38,38,thick),'#202b32',p,basis,part=part,bevel=True)
        for sign in (-1,1):
            builder.box('cooler-radiator-pump-service-cover',(34,34,.3),'#3c4951',_add(p,_mul(basis[2],sign*(thick/2+.15))),basis,part=part,bevel=True)
    # Separate physical fans keep their own identity, picking and style. Both
    # faces have the same through-flow orientation; a pull fan is not mirrored.
    sides=() if layout=='none' else (('front',-1),('rear',1)) if layout=='push_pull' else (('front',-1),)
    for face,sign in sides:
        for i in range(cooler['fan_count']):
            offset=(i-(cooler['fan_count']-1)/2)*fan['size_mm']
            center=_add(p,_add(_mul(basis[1],offset),_mul(basis[2],sign*((thick+fan['depth_mm'])/2+.8))))
            identity=part+':'+face+':'+str(i)
            _fan(builder,fan,center,_mul(basis[2],-1),basis[0],component='cooler',part=identity,name='cooler-radiator-fan',role='radiator',direction='exhaust')
            builder.parts.append(dict(id=identity,label=fan.get('label',str(fan['size_mm'])+' mm 参考风扇')+' · '+('内侧' if face=='front' else '外侧')+' '+str(i+1),
                kind='radiator_fan',model_id=fan['id'],radiator_part_id=part,face=face,
                size_mm=fan['size_mm'],depth_mm=fan['depth_mm'],telemetry_bound=False,
                geometry_verified=fan.get('blade_geometry_reviewed',False)))
    ports=detail.get('ports') or []
    active=[port for port in ports if port.get('open') is not False and not port.get('capped') and port.get('role') not in ('capped','plugged','auxiliary')][:2]
    barbs=[]
    if len(active)==2:
        for port in active:
            normal=_unit(port['normal']);position=tuple(port['position']);out=position if cooler.get('_retail_loop_parts') else _add(position,_mul(normal,10.))
            # Original hollow collar; thread designation comes only from the
            # reviewed radiator. Thread teeth/compression fitting SKU is unknown.
            collar_basis=_basis(normal,basis[0])
            if not cooler.get('_retail_loop_parts'):
                builder.put('cooler-radiator-reference-hose-collars',ring(7.,4.,10.,builder.segments),'#687882',
                    _add(position,_mul(normal,5.)),collar_basis,part=part)
            barbs.append(out)
    elif profile is None:
        # Existing sealed-AIO or explicitly generic-reference hose outlets, schematic. No universal
        # G1/4 thread or user-replaceable AIO radiator is inferred.
        # The LFIII factory drawing shows a close pair near the width centre,
        # unlike this generic67.2mm pair on a120mm radiator.13mm is an original
        # photo-reference half-spacing, not a dimensioned manufacturer pitch.
        half_spacing=13. if cooler.get('id') in _LFIII_FACTORY_IDS else width*.28
        for sign in (-1,1):
            b=_add(p,_add(_mul(basis[0],sign*half_spacing),_add(_mul(basis[1],length/2-12),_mul(basis[2],-thick/2))))
            axis=_mul(basis[2],-1);end=_add(b,_mul(axis,9))
            builder.put('cooler-radiator-fittings',ring(6.,3.8,9.,builder.segments),'#687882',
                _add(b,_mul(axis,4.5)),_basis(axis,basis[0]),part=part);barbs.append(end)
    if profile is not None and len(barbs)!=2:
        builder.connection_issues.append(dict(part_id=part,model_id=profile['id'],reason='radiator_ports_unverified'))
    builder.parts.append(dict(id=part,label=cooler.get('radiator_model',cooler['label'])+' · '+mount+' 冷排',kind='radiator',
        model_id=profile['id'] if profile else cooler['id'],dimensions_mm=dict(rad),mount=mount,
        hose_connections_ready=len(barbs)==2,
        fan_size_mm=fan['size_mm'],fan_capacity_per_face=cooler['fan_count'],fan_layout=layout,
        installed_fan_count=len(sides)*cooler['fan_count'],ports_count=profile.get('ports_count') if profile else 2,
        port_thread=profile.get('port_thread') if profile else None,telemetry_bound=False,
        detail_metadata=detail.get('metadata',{})))
    if profile is None and cooler.get('id') in _LFIII_FACTORY_IDS:
        builder.parts[-1]['hose_port_reference']=dict(position_verified=False,source=_LFIII_PORT_SOURCE,
            spacing_mm=26.,previous_generic_spacing_mm=width*.56,
            accuracy='photo_reference_not_dimensioned_pitch',face='fan_side',axis='negative_mount_normal',
            long_offset_from_end_mm=12.,long_offset_verified=False,
            family_source_scope='LFIII360 factory drawing; shared-family reference for240/280/420')
        builder.parts[-1]['hose_port_reference']['radiator_rigid_rotation_degrees']=180 if lfiii_front else 0
        builder.parts[-1]['hose_port_reference']['mount_clocking_verified']=False
    if cooler.get('_retail_loop_parts'):
        thread=profile.get('port_thread') if profile else None
        thread='G1/4' if thread and 'G1/4' in thread else thread
        builder.parts[-1]['connection_ports']=[dict(port,thread=thread,
            thread_gender='female' if profile and profile.get('port_thread_verified') else 'unknown',
            position_verified=False,role_verified=False) for port in ports
            if port.get('open') is not False and not port.get('capped')]
    return barbs


def _gpu_block(builder,pcb):
    """Explicit generic full-cover reference, never a matched retail block."""
    from assembly_geometry import ring
    p=pcb.get('position',pcb.get('center'));width=pcb.get('width_mm');length=pcb.get('length_mm')
    if not isinstance(p,(tuple,list)) or len(p)!=3 or not all(type(v) in (int,float) and math.isfinite(v) for v in p):return None
    if not all(type(v) in (int,float) and math.isfinite(v) and 45<=v<=500 for v in (width,length)):return None
    basis=_basis(pcb.get('normal',(0.,-1.,0.)),pcb.get('up',(1.,0.,0.)))
    w,d=width*.94,length*.90;part='gpu:waterblock';u,v,n=basis
    def point(a,b,c):return _local_point(p,basis,a,b,c)
    builder.box('gpu-waterblock-nickel-base',(w,d,4),'#a6b8c5',point(0,0,3.2),basis,'gpu',part,True)
    builder.box('gpu-waterblock-channel-bed',(w*.80,d*.83,1),'#405d6d',point(0,0,5.8),basis,'gpu',part,True)
    for i in range(18 if builder.level=='close' else 12 if builder.level=='balanced' else 7):
        span=18 if builder.level=='close' else 12 if builder.level=='balanced' else 7
        builder.box('gpu-waterblock-microfins',(w*.005,d*.39,2.5),'#aec1cb',point((i-(span-1)/2)*w*.025,-d*.08,7.6),basis,'gpu',part)
    for sign in (-1,1):
        path=[point(sign*w*.32,-d*.33,7),point(sign*w*.32,d*.22,7),point(sign*w*.15,d*.30,7)]
        builder.tube('gpu-waterblock-channel-runs',path,2.7,'#6b929e','gpu',part)
    # Clear cover is a separate transparent material over visible internal fins.
    builder.box('gpu-waterblock-clear-cover',(w*.97,d*.97,2),(.62,.80,.87,.30),point(0,0,12),basis,'gpu',part,True)
    for a in (-1,1):
        for b in (-1,1):builder.put('gpu-waterblock-fasteners',ring(2,0,1,builder.segments),'#596e7b',point(a*w*.43,b*d*.43,13.5),basis,'gpu',part)
    builder.box('gpu-waterblock-terminal',(w*.55,22,17),'#48606d',point(0,d*.41,17),basis,'gpu',part,True)
    ports=[]
    for sign in (-1,1):
        port=point(sign*w*.145,d*.41,31)
        builder.put('gpu-waterblock-gquarter-fittings',ring(7,4,10,builder.segments),'#9aaeb9',_add(port,_mul(n,-5)),basis,'gpu',part)
        ports.append(port)
    builder.parts.append(dict(id=part,label='显卡全覆盖水冷头 · 通用透明镀镍参考',kind='gpu_waterblock',model_id='generic-gpu-waterblock-reference',
        dimensions_verified=False,fit_verified=False,geometry_accuracy='explicit_generic_reference',notes='Rendered PCB reference envelope only; no retail block compatibility or manufacturing CAD.'))
    return ports


def _lfiii_pump(builder,p,basis,part):
    """Photo-observed radial crown over an unverified internal60mm rotor.

    The visible vent crown stays static pending motion verification. Its sampled
    rib count is illustrative, not an asserted internal impeller count or tach.
    Manufacturer envelope includes the adjacent hose elbows; no logo copied.
    """
    from assembly_geometry import Mesh,color,ring,_quad
    u,v,n=basis
    def point(a,b,c):return _local_point(p,basis,a,b,c)
    builder.box('cooler-lfiii-copper-contact',(48,48,3),'#a38b76',point(0,0,1.5),basis,part=part,bevel=True)
    builder.box('cooler-lfiii-contact-base',(62,68,15),'#39474f',point(0,0,11.5),basis,part=part,bevel=True)
    builder.put('cooler-lfiii-motor-body',ring(26,0,25,builder.segments),'#25323a',point(0,0,31),basis,part=part)
    for sign in (-1,1):
        builder.box('cooler-lfiii-undercut-cheeks',(11,67,32),'#34434b',point(sign*27,0,31),basis,part=part,bevel=True)
        for offset in (-19,19):
            # Faceted buttresses beneath the circular cap preserve the open
            # undercut visible in the manufacturer's three-quarter closeup.
            a=(sign*30,offset,17);b=(sign*36,offset,49)
            builder.put('cooler-lfiii-crown-supports',_tube([a,b],3.3,{'eco':6,'balanced':8,'close':10}[builder.level]),'#45545d',p,basis,part=part)
    builder.put('cooler-lfiii-crown-outer-rim',ring(45.5,38,18,builder.segments),'#28363e',point(0,0,59.5),basis,part=part)
    builder.put('cooler-lfiii-recessed-air-chamber',ring(38,17,3,builder.segments),'#1d2b33',point(0,0,47),basis,part=part)
    builder.put('cooler-lfiii-crown-inner-rim',ring(20.5,18.5,4,builder.segments),'#34434c',point(0,0,65),basis,part=part)
    ribs=[]
    for i in range(30):
        a=i*math.tau/30
        poly=((21*math.cos(a-.016),21*math.sin(a-.016)),(38*math.cos(a+.022),38*math.sin(a+.022)),
              (38*math.cos(a+.075),38*math.sin(a+.075)),(21*math.cos(a+.045),21*math.sin(a+.045)))
        lower=[(*xy,52 if j in (0,3) else 54) for j,xy in enumerate(poly)]
        upper=[(*xy,64 if j in (0,3) else 61) for j,xy in enumerate(poly)]
        _quad(ribs,*upper);_quad(ribs,*tuple(reversed(lower)))
        for j in range(4):k=(j+1)%4;_quad(ribs,lower[j],lower[k],upper[k],upper[j])
    builder.put('cooler-lfiii-static-radial-crown',tuple(ribs),'#53616a',p,basis,part=part)
    builder.put('cooler-lfiii-blank-center-cap',ring(18.5,0,3,builder.segments),'#26343d',point(0,0,66.3),basis,part=part)
    # ARCTIC documents60mm, not our former40mm reference. Actual internal
    # blade topology remains unverified; only explicit demo may move this mesh.
    model=dict(id='arctic-lfiii-internal60-reference',family='arctic-vrm-reference',size_mm=60,width_mm=60,depth_mm=9,
        blades=7,shape='wide',hub_ratio=.35,blade_count_verified=False,blade_geometry_reviewed=False)
    rotor=list(_leaf_geometry(model,28,1.5));rotor.extend(ring(9,0,4,builder.segments))
    center=point(0,0,54)
    builder.rotors.append(Mesh('cooler-vrm-internal-leaves-hub',_transform(rotor,(0,0,0),basis,False),color('#46565f'),center,'cooler',True,1,n,part))
    builder.fans.append(dict(part_id=part,model_id=model['id'],role='vrm_independent',position=center,axis=n,diameter_mm=60,
        rpm=None,rotation_default='static',blade_count_verified=False,blade_geometry_reviewed=False,rotation_direction_verified=False,
        visibility='behind_photo_observed_radial_vent_crown',crown_rib_count_is_reference=True,crown_motion_verified=False))
    builder.box('cooler-lfiii-twin-elbow-bridge',(52,23,24),'#283740',point(0,45.5,21),basis,part=part,bevel=True)
    # Manufacturer side view: the side outlet turns90degrees away from the
    # board before the hose sleeve, rather than continuing in the cap plane.
    # Unlabelled elbow centres are original references inside the documented
    #91x108.5x68.5mm enclosure; they are not measured manufacturing coordinates.
    ports=[];sides={'eco':12,'balanced':16,'close':20}[builder.level]
    bends={'eco':3,'balanced':4,'close':5}[builder.level]
    for sign in (-1,1):
        route=[(sign*13,45.5+9.*math.sin(i*math.pi/(2*bends)),39.-9.*math.cos(i*math.pi/(2*bends))) for i in range(bends+1)]
        route.extend(((sign*13,54.5,53.),(sign*13,54.5,68.5)))
        outer,outer_rings=_aio_sweep(route,8.,sides,(0.,1.,0.),(0.,0.,-1.),straight_leads=False)
        inner,inner_rings=_aio_sweep(route,5.,sides,(0.,1.,0.),(0.,0.,-1.),straight_leads=False)
        hollow=list(outer)
        for offset in range(0,len(inner),18):
            for j in (0,12,6):hollow.extend((*inner[offset+j:offset+j+3],*_mul(inner[offset+j+3:offset+j+6],-1.)))
        for outside,inside in ((outer_rings[0],inner_rings[0]),(outer_rings[-1],inner_rings[-1])):
            for i in range(sides):
                j=(i+1)%sides;_quad(hollow,inside[i],outside[i],outside[j],inside[j])
        builder.put('cooler-lfiii-twin-hose-elbows',hollow,'#4b5c65',p,basis,part=part)
        ports.append(point(sign*13,54.5,68.5))
    return ports


def _family_pump(builder,cooler,p,basis,part):
    """Photo-observed outer silhouettes, blank original caps and no logo art.

    Internal construction and cap feature dimensions remain illustrative. The
    source-qualified enclosure is preserved; no animated screen or pump tach
    is fabricated. Return False for established families handled elsewhere.
    """
    from assembly_geometry import ring,extrude
    from assembly_detail import perforated_plate,chamfer_rect
    style=cooler['pump_style'];dims=cooler['pump_reference_mm']
    w,h,d=(dims[k] for k in ('width','height','depth'))
    def point(a,b,c):return _local_point(p,basis,a,b,c)
    def outline(name,poly,z,tint):
        inner=tuple((x*.91,y*.91) for x,y in poly)
        builder.put(name,perforated_plate(poly,[inner],.7,segments=12),tint,point(0,0,z),basis,part=part)
    if style in ('cm_dual_chamber','id_white_ring','aorus_round_lcd','fractal_lumen'):
        radius=min(w,d)/2
        builder.put('cooler-pump-round-base',ring(radius,0,h,builder.segments),'#28343c',point(0,0,h/2+4),basis,part=part)
        builder.put('cooler-pump-recessed-cap',ring(radius*.92,0,1.4,builder.segments),'#17252d',point(0,0,h+4.7),basis,part=part)
        if style=='id_white_ring':
            builder.put('cooler-pump-white-light-ring',ring(radius*.86,radius*.82,.7,builder.segments),'#d5e1e5',point(0,0,h+5.8),basis,part=part)
        elif style=='aorus_round_lcd':
            builder.put('cooler-circular-lcd-bezel',ring(32,30,1.5,builder.segments),'#81939d',point(0,0,h+5.5),basis,part=part)
            builder.put('cooler-blank-circular-lcd',ring(30,0,1.,builder.segments),'#0b1822',point(0,0,h+6.5),basis,part=part)
        else:
            builder.put('cooler-pump-round-cap-lip',ring(radius*.96,radius*.91,.8,builder.segments),'#46565f',point(0,0,h+5.5),basis,part=part)
            if style=='fractal_lumen':
                builder.put('cooler-lumen-translucent-reference-cap',ring(radius*.83,0,.8,builder.segments),'#a6c0c6',point(0,0,h+5.9),basis,part=part)
    elif style=='corsair_lcd':
        radius=min(w,d)*.48
        builder.box('cooler-corsair-lcd-rounded-pedestal',(w*.90,d*.90,h*.67),'#27343c',point(0,0,h*.335+4),basis,part=part,bevel=True)
        builder.put('cooler-corsair-lcd-display-housing',ring(radius,0,h*.34,builder.segments),'#28333b',point(0,0,h*.83+4),basis,part=part)
        builder.put('cooler-corsair-lcd-rgb-ring',ring(radius*.94,radius*.88,.7,builder.segments),'#8ac4c8',point(0,0,h+4.6),basis,part=part)
        builder.put('cooler-corsair-lcd-inner-bezel',ring(radius*.88,radius*.83,.7,builder.segments),'#69777f',point(0,0,h+4.7),basis,part=part)
        builder.put('cooler-corsair-blank-circular-screen',ring(radius*.83,0,.6,builder.segments),'#101e28',point(0,0,h+5.1),basis,part=part)
    elif style in ('xpg_infinity','deepcool_lt_mirror'):
        builder.box('cooler-mirror-pump-base',(w*.90,d*.90,h*.77),'#25353e',point(0,0,h*.385+4),basis,part=part,bevel=True)
        builder.box('cooler-mirror-blank-top',(w*.89,d*.89,h*.20),'#152c36',point(0,0,h*.87+4),basis,part=part,bevel=True)
        for i in range(3):
            ratio=.84-i*.14
            outline('cooler-static-mirror-top-rings',chamfer_rect(w*ratio,d*ratio,min(w,d)*.09),h*.98+4.5+i*.16,'#83b6c5')
        if style=='deepcool_lt_mirror':
            # Original side-window reference gives the LT head its third face;
            # no proprietary light data, moving pattern or logo is sampled.
            for sign in (-1,1):
                builder.box('cooler-lt-side-mirror-window',(1.3,d*.77,h*.37),'#496a76',point(sign*w*.455,0,h*.72+4),basis,part=part,bevel=True)
    elif style=='tryx_panorama':
        # Original L-shaped screen over the documented envelope. Two broad
        # curved display faces meet without a fabricated live readout or logo.
        builder.box('cooler-panorama-pump-base',(w*.78,d*.78,h*.42),'#26363f',point(0,0,h*.21+4),basis,part=part,bevel=True)
        radius=min(w,d)*.16;screen_height=h*.56
        contour=[(-w/2,-d/2),(-w/2,d/2-radius)]
        for step in range(9):
            a=math.pi-step*math.pi/16
            contour.append((-w/2+radius+radius*math.cos(a),d/2-radius+radius*math.sin(a)))
        contour.append((w/2,d/2))
        for a,b in zip(contour,contour[1:]):
            from assembly_geometry import _quad
            vertices=[]
            _quad(vertices,(a[0],a[1],h*.44+4),(b[0],b[1],h*.44+4),(b[0],b[1],h+4),(a[0],a[1],h+4))
            builder.put('cooler-panorama-blank-l-shaped-screen',tuple(vertices),'#173540',p,basis,part=part)
        for z in (h*.44+3.5,h+4.5):
            builder.put('cooler-panorama-screen-edge',_tube([(a,b,z) for a,b in contour],1.2,6),'#82959d',p,basis,part=part)
    elif style in ('alphacool_square','ek_nucleus'):
        builder.box('cooler-pump-family-housing',(w,d,h),'#28363e',point(0,0,h/2+4),basis,part=part,bevel=True)
        if style=='ek_nucleus':
            builder.put('cooler-nucleus-offset-cap',ring(min(w,d)*.43,0,3,builder.segments),'#3e505b',point(w*.04,0,h+4),basis,part=part)
            builder.put('cooler-nucleus-static-light-ring',ring(min(w,d)*.37,min(w,d)*.35,.8,builder.segments),'#9bc8cd',point(w*.04,0,h+6),basis,part=part)
        else:
            builder.box('cooler-alphacool-service-cap',(w*.85,d*.85,1.5),'#4c626c',point(0,0,h+4.8),basis,part=part,bevel=True)
            for a in (-1,1):
                for b in (-1,1):builder.put('cooler-alphacool-cap-fasteners',ring(1.8,.7,.8,12),'#93a9b2',point(a*w*.34,b*d*.34,h+6),basis,part=part)
    elif style in ('enermax_square_mirror','deepcool_square_mirror','msi_lcd','phanteks_bridge'):
        builder.box('cooler-pump-family-housing',(w,d,h),'#29363e',point(0,0,h/2+4),basis,part=part,bevel=True)
        if style=='msi_lcd':
            builder.box('cooler-ips-lcd-bezel',(w*.90,d*.90,2),'#53646f',point(0,0,h+4.6),basis,part=part,bevel=True)
            builder.box('cooler-blank-ips-lcd',(w*.77,d*.64,1),'#0a1720',point(0,0,h+6.3),basis,part=part,bevel=True)
            for sign in (-1,1):
                for slot in range(6):builder.box('cooler-embedded-fan-static-vents',(1.6,d*.09,h*.18),'#121f28',point(sign*(w/2+.1),(slot-2.5)*d*.12,h*.38),basis,part=part)
        elif style=='phanteks_bridge':
            cap=chamfer_rect(w*.94,d*.94,6)
            builder.put('cooler-bridge-top-cap',extrude(cap,1.5),'#43515a',point(0,0,h+4.8),basis,part=part)
            outline('cooler-bridge-rgb-outline',cap,h+5.8,'#83baca')
            for i in range(3):builder.box('cooler-bridge-fine-stripes',(w*.61,.65,.5),'#8abfc9',point(0,(i-1)*3,h+6.2),basis,part=part)
        else:
            builder.box('cooler-infinity-dark-cap',(w*.86,d*.86,1.5),'#14232c',point(0,0,h+4.6),basis,part=part,bevel=True)
            for layer in range(3):
                scale=.86-layer*.09
                outline('cooler-square-mirror-outlines',chamfer_rect(w*scale,d*scale,min(w,d)*.13),h+5.8+layer*.16,'#7aabb9')
    elif style in ('asus_tuf_hex','msi_radiator_pump'):
        # TUF's actual cap is a six-sided bevel over a round Asetek base.
        sides=6 if style=='asus_tuf_hex' else 8
        radius=min(w,d)/2
        builder.put('cooler-pump-round-base',ring(radius,0,h*.88,builder.segments),'#27343c',point(0,0,h*.44+4),basis,part=part)
        poly=tuple((math.cos(i*math.tau/sides)*w*.49,math.sin(i*math.tau/sides)*d*.49) for i in range(sides))
        builder.put('cooler-faceted-blank-cover',extrude(poly,h*.14),'#495861',point(0,0,h*.93+4),basis,part=part)
        outline('cooler-faceted-cap-lip',poly,h+4.5,'#71838c')
    else:return False
    return True


def _liquid(builder,cooler,p,basis,mount,dimensions,gpu_pcb=None,secondary_mount='side',planes=None,floor_deck=None,secondary_cooler=None,occupied_meshes=()):
    from assembly_geometry import ring,extrude
    barbs=_radiator(builder,cooler,mount,dimensions,planes=planes)
    if barbs is None:return False
    dims=cooler['pump_reference_mm'];width,height,depth=(dims[k] for k in ('width','height','depth'));u,v,n=basis
    center=_add(p,_mul(n,height/2+4));style=cooler['pump_style'];part='cooler:cpu' if cooler['kind']=='custom_loop' else 'cooler:pump'
    aio_start_axis=v
    if style=='arctic_vrm':
        # Intel1700 manual faces the paired elbows toward the PCIe-slot side.
        # Apply one proper rigid rotation to the complete head, not just hoses.
        pump_basis=(v,_mul(u,-1.),n);ports=_lfiii_pump(builder,p,pump_basis,part);aio_start_axis=n
    elif _family_pump(builder,cooler,p,basis,part):
        pass
    elif style in ('nzxt_lcd','nzxt_infinity','round','lianli_infinity','thermaltake_mirror'):
        builder.put('cooler-pump-housing',ring(min(width,depth)/2,0,height,builder.segments),'#212c33',center,basis,part=part)
        if style=='nzxt_infinity':
            for ratio in (.84,.64,.46):builder.put('cooler-static-infinity-reference-rings',ring(width*ratio/2,width*(ratio-.035)/2,.5,builder.segments),'#8aabb6',_add(center,_mul(n,height/2+1)),basis,part=part)
        if style=='nzxt_lcd':
            builder.put('cooler-pump-bezel',ring(width*.49,width*.43,2,builder.segments),'#8a969e',_add(p,_mul(n,height+4)),basis,part=part)
            builder.put('cooler-blank-lcd',ring(width*.425,0,1.,builder.segments),'#10191f',_add(p,_mul(n,height+5.1)),basis,part=part)
        elif style in ('lianli_infinity','thermaltake_mirror'):
            for layer in range(3 if style=='lianli_infinity' else 1):builder.put('cooler-pump-mirror-rings',ring(width*(.45-layer*.085),width*(.425-layer*.085),1,builder.segments),'#7dbbc7',_add(p,_mul(n,height+4.5+layer*.4)),basis,part=part)
    else:
        builder.box('cooler-pump-housing',(width,depth,height),'#27343c',center,basis,part=part,bevel=True)
        if style.startswith('corsair') and cooler.get('pump_fixed_white'):
            builder.box('cooler-pump-dark-cap',(width*.88,depth*.88,1.3),'#27343c',_add(p,_mul(n,height+4.5)),basis,part=part,bevel=True)
            builder.box('cooler-pump-fixed-white-mark',(width*.24,depth*.06,.6),'#efeee2',_add(p,_mul(n,height+5.5)),basis,part=part)
        elif style.startswith('corsair'):
            sides=8 if style=='corsair_octagon' else 4
            poly=tuple((math.cos(i*math.tau/sides+math.pi/4)*width*.46,math.sin(i*math.tau/sides+math.pi/4)*depth*.46) for i in range(sides))
            builder.put('cooler-pump-rgb-cap',extrude(poly,1.3),'#79bfc8',_add(p,_mul(n,height+4.5)),basis,part=part)
        elif style in ('deepcool_lcd','asus_lcd'):
            builder.box('cooler-lcd-bezel',(width*.91,depth*.91,2),'#7b8e9a',_add(p,_mul(n,height+4.5)),basis,part=part,bevel=True)
            builder.box('cooler-blank-lcd',(width*.84,depth*.83,1),'#0e1920',_add(p,_mul(n,height+6.1)),basis,part=part,bevel=True)
        else:builder.box('cooler-cpu-waterblock-window',(width*.73,depth*.67,2),'#68939d',_add(p,_mul(n,height+4.8)),basis,part=part,bevel=True)
    if style!='arctic_vrm':
        ports=[_local_point(p,basis,sign*width*.27,depth*.40,height*.55+4) for sign in (-1,1)]
        for port in ports:builder.tube('cooler-block-fittings',[port,_add(port,_mul(v,12))],5,'#778d98',part=part)
    gpu_ports=None;second_barbs=None
    if cooler['kind']=='custom_loop':
        if gpu_pcb:
            second_barbs=_radiator(builder,secondary_cooler or cooler,secondary_mount,dimensions,'cooler:gpu-radiator',planes)
            if second_barbs and barbs:gpu_ports=_gpu_block(builder,gpu_pcb)
        reservoir=cooler['reservoir_mm'];r=reservoir['diameter']/2;rh=reservoir['height'];w,h,d=dimensions
        reservoir_y=-h/2+rh/2+35
        if isinstance(floor_deck,dict):
            floor_position=floor_deck.get('position');thickness=floor_deck.get('thickness_mm',2.)
            if isinstance(floor_position,(tuple,list)) and len(floor_position)==3 and type(floor_position[1]) in (int,float) and math.isfinite(floor_position[1]) and type(thickness) in (int,float) and math.isfinite(thickness):
                # The D5 body's lower face is rp.y-height/2+1mm. Preserve the
                # selected200mm assembly and leave2mm above a known deck top.
                reservoir_y=max(reservoir_y,floor_position[1]+thickness/2+rh/2+1)
        rp=(-w*.22,reservoir_y,d*.25);rb=_basis((0.,1.,0.),(1.,0.,0.))
        builder.put('cooler-reservoir-shell',ring(r,r-2,rh-44,builder.segments),'#79949e',_add(rp,(0.,12.,0.)),rb,part='cooler:reservoir',alpha=.22)
        builder.put('cooler-reservoir-fluid-core',ring(r-4,0,rh-52,builder.segments),'#497681',_add(rp,(0.,12.,0.)),rb,part='cooler:reservoir',alpha=.55)
        for sign in (-1,1):builder.put('cooler-reservoir-caps',ring(r+2,0,15,builder.segments),'#26343c',_add(rp,(0.,sign*(rh-32)/2+12,0.)),rb,part='cooler:reservoir')
        builder.put('cooler-d5-pump',ring(r*.94,0,34,builder.segments),'#1c282f',_add(rp,(0.,-rh/2+18,0.)),rb,part='cooler:reservoir')
        for sign in (-1,1):builder.box('cooler-reservoir-clamps',(reservoir['diameter']+8,5,8),'#75858e',_add(rp,(0.,sign*rh*.26,-r)),((1.,0.,0.),(0.,1.,0.),(0.,0.,1.)),part='cooler:reservoir')
        targets=[barbs[0],_add(rp,(0.,-rh/2+19,r+8))] if barbs else [];extra_start=barbs[1] if barbs else None;extra_end=_add(rp,(0.,rh/2+5,0.))
        builder.parts.append(dict(id='cooler:reservoir',label=cooler['reservoir_model'],kind='pump_reservoir',model_id=cooler['id']))
    else:targets=barbs;extra_start=extra_end=None
    lfiii_paths=None;lfiii_route_issue=None
    if cooler.get('id') in _LFIII_FACTORY_IDS and cooler['kind']=='aio' and len(ports)==len(targets)==2:
        from case_fan_clearance047 import blockers
        radiator_axis=_mul(_mount_plane(mount,dimensions,0.,planes)[1][2],-1.)
        lfiii_paths=_lfiii_hose_paths(ports,targets,aio_start_axis,radiator_axis,n,builder.level,450.)
        lfiii_route_issue=(['source_length_cannot_fit_reference_guide'] if lfiii_paths is None else
            _aio_route_issues(lfiii_paths,dimensions,blockers(occupied_meshes,builder.static,builder.rotors)))
        if lfiii_route_issue:
            builder.connection_issues.append(dict(part_id='cooler:cpu',model_id=cooler['id'],reason='aio_hose_route_unverified',
                nominal_length_mm=450.,details=lfiii_route_issue,hoses_omitted=True))
    for index,(start,end) in enumerate(zip(ports,targets)):
        if cooler['kind']=='aio':
            # LFIII returns the end of its hollow elbow. The generic pump
            # connector above starts at port and extends12mm along v.
            pump_end=start if style=='arctic_vrm' else _add(start,_mul(v,12))
            radiator_axis=_mul(_mount_plane(mount,dimensions,0.,planes)[1][2],-1.)
            if not lfiii_route_issue:
                _aio_hose(builder,pump_end,end,aio_start_axis,radiator_axis,8. if style=='arctic_vrm' else 5.,
                    points=lfiii_paths[index] if lfiii_paths is not None else None,model_id=cooler['id'],
                    nominal_length=450. if lfiii_paths is not None else None)
        else:
            a=_add(start,_mul(v,15));c1=_add(a,_mul(n,45));c2=_add(end,_mul(n,25))
            builder.tube('cooler-liquid-tubes',_curve((a,c1,c2,end),{'eco':8,'balanced':12,'close':18}[builder.level]),6.2,'#303e46',part='cooler:cpu')
    if extra_start:
        pairs=[(extra_start,extra_end)] if not gpu_ports else [(extra_start,gpu_ports[0]),(gpu_ports[1],second_barbs[0]),(second_barbs[1],extra_end)]
        for start,end in pairs:
            builder.tube('cooler-liquid-tubes',_curve((start,_add(start,(0.,-35.,0.)),_add(end,(0.,45.,0.)),end),12),6.2,'#303e46',part='cooler:cpu')
    kind='cpu_waterblock' if cooler['kind']=='custom_loop' else 'aio_cpu_block' if cooler.get('pump_location')=='radiator' else 'aio_pump'
    builder.parts.append(dict(id=part,label=cooler.get('cpu_block_model',cooler['label'])+' · CPU 冷头',kind=kind,model_id=cooler['id']))
    if style=='arctic_vrm':
        builder.parts[-1]['factory_pose_reference']=dict(source='https://support.arctic.de/products/liquid-freezer-iii-360/Intel/Installation/018.jpg',
            elbow_source=_LFIII_PORT_SOURCE,clocking='complete_head_basis_v_negative_u_n',hose_exit_axis=list(n),
            position_verified=False,elbow_shape_reference=True,coordinate_scope='Intel1700 illustration; reference on other sockets',
            enclosure_reference_mm=dict(u=91.,v=108.5,normal=68.5))
    return True


def add_cooling(meshes,spec,level='balanced',anchors=None):
    """Return detached additions/metadata; never infer installed hardware.

    Missing/invalid choices add nothing. Unsupported documented mounts are
    rejected, never resized or silently truncated. Unknown mount compatibility
    may be illustrated at full scale and is explicitly labelled unverified.
    """
    anchors=anchors if isinstance(anchors,dict) else {};spec=spec if isinstance(spec,dict) else {}
    selection=spec.get('cooling',{});selection=selection if isinstance(selection,dict) else {}
    dimensions=anchors.get('case_dimensions',(320.,470.,470.))
    if not isinstance(dimensions,(tuple,list)) or len(dimensions)!=3 or not all(type(v) in (int,float) and math.isfinite(v) and 60<=v<=2000 for v in dimensions):dimensions=(320.,470.,470.)
    dimensions=tuple(dimensions);case=anchors.get('case',spec.get('case',{}));case=case if isinstance(case,dict) else {}
    planes=anchors.get('case_mount_planes',{})
    if not isinstance(planes,dict):planes={}
    builder=_Builder(level);meta=dict(parts=[],fans=[],rejected=[],warnings=[],geometry_accuracy='original_schematic_reference',
        sources=[],cpu_fan_tach_usable=False,real_cpu_rotor_parts=[],replace_gpu_cooler=False,fan_tach_mapping='No selected air cooler; CPU_FAN tachometer is not assigned.',
        automatic_detection=False,new_pollers=0,default_fan_motion='static_without_fresh_group_tach',mount_positions_schematic=True)
    cooler=get_cooler(selection.get('cpu_cooler'));occupied=set()
    if selection.get('cpu_cooler') not in (None,'','none') and not cooler:meta['rejected'].append(dict(kind='cooler',reason='unknown_model'))
    if cooler:
        p,basis=_cpu_frame(anchors);kind=cooler['kind'];mount=selection.get('radiator_mount','top')
        if kind in ('aio','custom_loop'):
            from liquid_selection044 import resolve_liquid_choices
            selected,secondary_cooler,selection_issues=resolve_liquid_choices(cooler,selection)
            meta['rejected'].extend(dict(row,kind='cooling_selection') for row in selection_issues if row.get('severity')!='review')
            meta['mounting_issues']=[dict(row) for row in selection_issues if row.get('severity')=='review']
            if selected is None:
                cooler=None
            else:cooler=selected
            fan=_reference_fan(cooler) if cooler else None
            check=_mount_check(case,mount,fan['size_mm'],cooler['fan_count']) if cooler and mount in _MOUNT_NORMALS else 'unsupported'
            gpu_pcb=None;secondary_mount='side' if mount!='side' else 'top'
            if cooler and secondary_cooler and selection.get('gpu_waterblock') is True:
                pcb=(anchors.get('gpu') or {}).get('pcb',{})
                valid_position=pcb.get('position',pcb.get('center')) if isinstance(pcb,dict) else None
                valid_size=all(type(pcb.get(k)) in (int,float) and math.isfinite(pcb[k]) and 45<=pcb[k]<=500 for k in ('width_mm','length_mm')) if isinstance(pcb,dict) else False
                secondary_fan=_reference_fan(secondary_cooler)
                supported=_mount_check(case,secondary_mount,secondary_fan['size_mm'],secondary_cooler['fan_count'])!='unsupported'
                _,_,span=_mount_plane(secondary_mount,dimensions,0,planes)
                fits=secondary_cooler['radiator_mm']['width']<=span[0]+1 and secondary_cooler['radiator_mm']['length']<=span[1]+1
                if kind=='custom_loop' and valid_size and isinstance(valid_position,(tuple,list)) and len(valid_position)==3 and all(type(v) in (int,float) and math.isfinite(v) for v in valid_position) and supported and fits:
                    gpu_pcb=pcb
                else:meta['warnings'].append('GPU block omitted: requires custom loop, explicit posed PCB reference and a separate supported full-size radiator mount; original GPU cooler retained.')
            manual_loop=kind=='custom_loop' and selection.get('loop_components_mode')=='selected'
            if cooler is not None and manual_loop and check!='unsupported':
                from assembly_loop046 import add_selected_loop
                loop=add_selected_loop(builder,cooler,selection,spec,anchors,dimensions,planes,p,basis,mount,meshes)
                meta['selected_loop']=loop;meta['cooler']=cooler
                meta['rejected'].extend(dict(row,kind='loop_component') for row in loop['issues'] if row['severity']=='error')
                meta['loop_issues']=[row for row in loop['issues'] if row['severity']!='error']
                occupied.update(row['mount'] for row in builder.parts if row['kind']=='radiator')
                meta['fan_tach_mapping']='Independent loop components have no bound water temperature, flow or pump/fan tach.'
            elif cooler is None:pass
            elif check=='unsupported' :meta['rejected'].append(dict(kind='cooler',model_id=cooler['id'],reason='unsupported_radiator_mount'))
            elif _liquid(builder,cooler,p,basis,mount,dimensions,gpu_pcb,secondary_mount,planes,anchors.get('case_floor_deck'),secondary_cooler,meshes):
                occupied.add(mount);meta['cooler']=cooler;meta['radiator_mount_compatibility']=check
                occupied.update(row['mount'] for row in builder.parts if row['kind']=='radiator')
                meta['replace_gpu_cooler']=any(part['kind']=='gpu_waterblock' for part in builder.parts)
                if meta['replace_gpu_cooler']:
                    occupied.add(secondary_mount);meta['secondary_radiator_mount']=secondary_mount
                    meta['warnings'].append('GPU waterblock is an explicit generic full-cover reference sized to schematic PCB; no retail compatibility is established.')
                meta['fan_tach_mapping']='Not assigned: AIO/custom CPU_FAN can report pump RPM; radiator and VRM fans have no verified independent tachometer.'
                meta['warnings'].append('Radiator fan-mount support does not verify radiator clearance; hose routes, fittings and pump internals are schematic.')
            else:meta['rejected'].append(dict(kind='cooler',model_id=cooler['id'],reason='radiator_exceeds_mount_plane'))
        else:
            _air(builder,cooler,p,basis);meta['cooler']=cooler;meta['cpu_fan_tach_usable']=cooler['fan_count']>0
            meta['fan_tach_mapping']=('Passive cooler: no installed fan or assigned CPU_FAN tachometer.' if cooler['fan_count']==0 else
                'Selected air-cooler main fan(s): fresh CPU_FAN tach is a representative header only; multiple fans do not have independently measured RPM.')
            main_fans=[fan for fan in builder.fans if fan['role']=='cpu_main']
            if main_fans and all(fan.get('blade_geometry_reviewed') for fan in main_fans):
                meta['real_cpu_rotor_parts']=['cooler:cpu']
            elif cooler['fan_count']>0:meta['warnings'].append('Air-cooler leaf contours/count are reference geometry pending primary-photo review; real-RPM rotation is gated off, explicit demo remains available.')
        if 'cooler' in meta:
            meta['sources'].extend(cooler['sources'])
            if kind=='custom_loop' and meta.get('replace_gpu_cooler') and secondary_cooler:meta['sources'].extend(secondary_cooler['sources'])
    groups=selection.get('case_fans',[]);groups=groups if isinstance(groups,(tuple,list)) else []
    from case_fan_clearance047 import blockers,envelope,conflicts,half_extents
    fan_obstacles=blockers(meshes,builder.static,builder.rotors,gpu_replaced=meta['replace_gpu_cooler']) if groups else []
    used_mounts=set()
    for group in groups[:12]:
        if not isinstance(group,dict):meta['rejected'].append(dict(kind='case_fan',reason='invalid_group'));continue
        model=get_fan(group.get('model'));mount=group.get('mount');count=group.get('count');direction=group.get('direction','intake')
        reason=''
        if not model:reason='unknown_model'
        elif mount not in _MOUNT_NORMALS:reason='invalid_mount'
        elif type(count) is not int or not 1<=count<=4:reason='invalid_count'
        elif direction not in ('intake','exhaust'):reason='invalid_direction'
        elif mount in occupied:reason='radiator_occupies_mount'
        elif mount in used_mounts:reason='duplicate_mount_selection'
        elif _mount_check(case,mount,model['size_mm'],count)=='unsupported':reason='unsupported_fan_mount'
        if not reason:
            center,basis,span=_mount_plane(mount,dimensions,model['depth_mm']/2+10,planes)
            half=half_extents(model)
            stack_length=(count-1)*model['size_mm']+half[1]*2
            if half[0]*2>span[0]+1 or stack_length>span[1]+1:reason='fans_exceed_mount_plane'
            # A legacy central rear plane put the exhaust fan directly through
            # expansion cards. Use an explicitly schematic upper-rear position
            # only when there is no authored mount plane; never move that plane.
            if not reason and mount=='rear' and not planes.get('rear'):
                horizontal_reach=sum(abs(basis[k][0])*half[k] for k in range(3))
                center=(-dimensions[0]/2+horizontal_reach+8.,(span[1]-stack_length)/2,center[2])
        placement_source=None
        if not reason and mount=='rear' and not planes.get('rear') and case.get('id')=='fractal-torrent-tg':
            # Torrent has its PSU at the top. The official possible-fan diagram
            # places both rear sizes below that bay, not at the generic top.
            # This ratio is a diagram observation, never measured screw holes.
            center=(center[0],dimensions[1]*.14,center[2])
            placement_source='https://assets.fractal-design.com/files/uxzbxy2o/production/af5f587352e8fa20cb09151326dae43796eebb44.pdf'
        positions=[];blocked=set()
        if not reason:
            positions=[_add(center,_mul(basis[1],(i-(count-1)/2)*model['size_mm'])) for i in range(count)]
            for position in positions:blocked.update(conflicts(envelope(model,position,basis),fan_obstacles))
            if blocked:reason='case_fan_clearance_conflict'
        if reason:
            meta['rejected'].append(dict(kind='case_fan',model_id=group.get('model'),mount=mount,reason=reason,
                **(dict(conflicting_parts=sorted(blocked),omitted_count=count) if blocked else {})))
            continue
        used_mounts.add(mount)
        for i,position in enumerate(positions):
            part='fans:'+mount+':'+str(i)
            fan_normal=basis[2] if direction=='intake' else _mul(basis[2],-1)
            wire_basis=_basis(fan_normal,basis[0]);default_sign=-1 if mount in ('rear','bottom') else 1
            def reference_tail(sign):
                outward=_mul(wire_basis[0],sign)
                return _add(position,_add(_mul(outward,model.get('width_mm',model['size_mm'])*.48+14.5),_mul(wire_basis[1],model['size_mm']*.35)))
            old_tail=reference_tail(default_sign);new_tail=reference_tail(-default_sign)
            inside=lambda point:all(abs(point[k])<=dimensions[k]/2 for k in range(3))
            wire_sign_override=-default_sign if not inside(old_tail) and inside(new_tail) else None
            _fan(builder,model,position,fan_normal,basis[0],component='fans',part=part,role='case',direction=direction,wire_sign_override=wire_sign_override)
            builder.parts.append(dict(id=part,label=model['label']+' · '+mount+' '+str(i+1),kind='case_fan',model_id=model['id'],mount=mount,
                compatibility=_mount_check(case,mount,model['size_mm'],count),
                placement_method='authored_mount_plane' if planes.get(mount) else 'official_manual_rear_below_psu_reference' if placement_source else 'upper_rear_reference' if mount=='rear' else 'centered_mount_reference',
                clearance_check='conservative_selected_solid_envelopes',cad_fit_verified=False,
                **(dict(placement_source=placement_source,placement_source_page=39,mounting_hole_positions_verified=False) if placement_source else {})))
            fan_obstacles.append((part,'case-fan-swept-envelope',envelope(model,position,basis)))
        meta['sources'].extend(model['sources'])
        if placement_source:meta['sources'].append(placement_source)
    if meta.get('cooler',{}).get('vrm_fan') and not any(f['role']=='vrm_independent' for f in builder.fans):
        meta['known_unplaced_vrm_fans']=1
        meta['warnings'].append('Manufacturer documents an embedded VRM fan; its unverified internal pose is not invented in this reference model.')
    if 'cooler' in meta:
        selected=meta['cooler']
        meta['documented_cooler_fans']=(selected['fan_count']+int(bool(selected.get('vrm_fan')))) if selected['kind']!='custom_loop' else None
        meta['radiator_fan_count']=sum(f['role']=='radiator' for f in builder.fans)
        meta['radiators']=[dict(row) for row in builder.parts if row['kind']=='radiator']
        meta['rendered_cooler_fans']=sum(f['role']!='case' for f in builder.fans)
        meta['fin_sampling']=dict(documented_per_tower=selected.get('documented_fin_count'),rendered_reference_per_bank={'eco':12,'balanced':24,'close':44}[builder.level],exact_internal_construction=False)
    meta['aio_hoses']=builder.aio_hoses
    meta['connection_issues']=builder.connection_issues
    if any(row.get('reason')=='aio_hose_route_unverified' for row in builder.connection_issues):
        meta['warnings'].append('Factory-length AIO hoses could not be routed within the checked reference envelopes; hoses are omitted, never shortened or moved through hardware to claim a fit.')
    if any(row.get('reason')!='aio_hose_route_unverified' for row in builder.connection_issues):
        meta['warnings'].append('Some standalone radiator port positions are unverified; associated hoses and GPU-block replacement are omitted, never assigned invented connections.')
    additions=builder.finish();meta['parts']=builder.parts;meta['fans']=builder.fans;meta['wire_anchors']=builder.wire_anchors;meta['sources']=list(dict.fromkeys(meta['sources']))
    meta['triangle_count']=sum(mesh.vertex_count for mesh in additions)//3
    meta['mesh_count']=len(additions)
    meta['mount_plane_sources']={key:dict(source=value.get('source'),method=value.get('method'),dimensions_verified=False)
        for key,value in planes.items() if key in occupied or key in used_mounts} if isinstance(planes,dict) else {}
    return additions,meta
