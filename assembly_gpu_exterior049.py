"""Exact Astral5090 exterior observations, not a measured PCB or CAD model.

The manufacturer gallery establishes the dark rear/side frame, silver front,
rear socket inspection window/retention frame and open distal cage. Photo
ratios below are illustrative placement; published357.6x149.3x76 envelope,
original three front rotors, fourth static fan and all electrical anchors stay
separate. Nothing here reads sensors, creates a clock or changes GPU pose.
Original geometry: repository noncommercial license, see LICENSING.md.
"""
from dataclasses import replace
import math

EXACT_ID='asus-astral-5090'
GALLERY='https://rog.asus.com/us/graphics-cards/graphics-cards/rog-astral/rog-astral-rtx5090-32g-gaming/gallery/'
REAR_PHOTO='https://dlcdnwebimgs.asus.com/gain/71E25C26-172B-4B3B-BF80-9CD8FCAB3DA6/w1000/h732'
SIDE_PHOTO='https://dlcdnwebimgs.asus.com/gain/B625A69F-626B-4451-B08B-DE635451FA0E/w1000/h732'
FRONT_PHOTO='https://dlcdnwebimgs.asus.com/gain/4820879A-7A8E-4171-A78F-FAAD61F1C06E/w1000/h732'
END_PHOTO='https://dlcdnwebimgs.asus.com/gain/D6BE479C-B386-4FAB-AC40-4582B7C6F499/w1000/h732'
FRONT_RADIUS_PHOTO='https://dlcdnwebimgs.asus.com/gain/EDD03DEA-FB86-43DA-B2B4-3EB932718D22/w1000/h732'
PCB_EDGE_PHOTO='https://dlcdnwebimgs.asus.com/gain/D1CB2D36-EDFA-4BFA-A88F-6D470784D4F9/w1000/h732'
FRONT_RADIUS_RATIO_LENGTH=.155


def _cup_height(x,z,radius,direction):
    """Bounded observed-curved blade reference, not a measured blade pitch.

    A smooth axial cup/twist leaves the original planform exactly in X/Z.
    Root and outer tip-link zones stay on their original axial plane.
    """
    radial=math.hypot(x,z);root=radius*.27;tip=radius*.82
    if radial<=root or radial>=tip:return 0.,0.,0.
    s=(radial-root)/(tip-root);w=16*s*s*(1-s)*(1-s)
    dw=32*s*(1-s)*(1-2*s)/(tip-root)
    angle=math.atan2(z,x);phase=7*direction*angle+.30
    g=.675+.325*math.sin(phase);dg=.325*7*direction*math.cos(phase)
    amplitude=min(5.4,radius*.105)
    value=amplitude*w*g
    dx=amplitude*(dw*x/radial*g+w*dg*(-z/(radial*radial)))
    dz=amplitude*(dw*z/radial*g+w*dg*( x/(radial*radial)))
    return value,dx,dz


def curve_front_rotor(vertices,radius,direction,level):
    """One static adaptive split; closed edges share the exact same midpoint.

    All coordinates are the original fan's local right-handed X/Y/Z. Only Y
    changes; count, blade outline, radius, handedness and rotor axis persist.
    The normal uses the analytic inverse-transpose of the axial shear field.
    """
    tolerance=.95 if level=='eco' else .48 if level=='balanced' else .24
    direction=-1 if direction==-1 else 1
    result=[]
    def middle(a,b):return tuple((x+y)*.5 for x,y in zip(a,b))
    def height(v):return _cup_height(v[0],v[2],radius,direction)[0]
    def split(a,b):
        mid=middle(a,b)
        return abs(height(mid)-(height(a)+height(b))*.5)>tolerance
    def emit(a,b,c):
        for vertex in (a,b,c):
            x,y,z,nx,ny,nz=vertex;value,dx,dz=_cup_height(x,z,radius,direction)
            normal=(nx-dx*ny,ny,nz-dz*ny);length=math.sqrt(sum(v*v for v in normal))
            result.extend((x,y+value,z,*(v/length for v in normal)))
    for n in range(0,len(vertices),18):
        a,b,c=(tuple(vertices[n+i:n+i+6]) for i in (0,6,12));ab,bc,ca=middle(a,b),middle(b,c),middle(c,a)
        mask=(1 if split(a,b) else 0)|(2 if split(b,c) else 0)|(4 if split(c,a) else 0)
        pieces={0:((a,b,c),),1:((a,ab,c),(ab,b,c)),2:((a,b,bc),(a,bc,c)),
                4:((a,b,ca),(ca,b,c)),3:((a,ab,bc),(ab,b,bc),(a,bc,c)),
                5:((a,ab,ca),(ab,b,c),(ab,c,ca)),6:((a,b,bc),(a,bc,ca),(ca,bc,c)),
                7:((a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca))}[mask]
        for triangle in pieces:emit(*triangle)
    return tuple(result)


def _conforming_panel_edges(panels):
    from bisect import bisect_left,bisect_right
    from assembly_detail import _tri
    # Merge only floating clipping duplicates, using the first original
    # coordinate as canonical representative rather than moving to a grid.
    if sum(len(v) for v in panels)>8192*18:raise ValueError('GPU bevel input budget exceeded')
    aliases={};canonical=[]
    for vertices in panels:
        values=[]
        for at in range(0,len(vertices),6):
            p=tuple(vertices[at:at+3]);key=tuple(round(x,9) for x in p)
            q=aliases.setdefault(key,p)
            if math.dist(p,q)>2e-9:raise ValueError('GPU canonical point exceeded tolerance')
            values.extend((*q,*vertices[at+3:at+6]))
        canonical.append(tuple(values))
    panels=tuple(canonical)
    points={tuple(vertices[n:n+3]) for vertices in panels for n in range(0,len(vertices),6)}
    edges={tuple(sorted((tuple(v[n+k:n+k+3]),tuple(v[n+j:n+j+3]))))
           for v in panels for n in range(0,len(v),18) for k,j in ((0,6),(6,12),(12,0))}
    if len(points)>8192 or len(edges)>32768:raise ValueError('Bounded GPU bevel edge refinement exceeded budget')
    ordered=[sorted(points,key=lambda p:p[k]) for k in range(3)]
    coords=[[p[k] for p in ordered[k]] for k in range(3)]
    splits={};tolerance=1e-8;candidate_checks=0
    for a,b in edges:
        delta=tuple(b[k]-a[k] for k in range(3));den=sum(q*q for q in delta)
        if den<1e-18:continue
        axis=max(range(3),key=lambda k:abs(delta[k]))
        candidates=ordered[axis][bisect_left(coords[axis],min(a[axis],b[axis])):bisect_right(coords[axis],max(a[axis],b[axis]))]
        candidate_checks+=len(candidates)
        if candidate_checks>2000000:raise ValueError('GPU bevel scan budget exceeded')
        found=[]
        for p in candidates:
            if p==a or p==b or any(p[k]<min(a[k],b[k])-tolerance or p[k]>max(a[k],b[k])+tolerance for k in range(3)):continue
            t=sum((p[k]-a[k])*delta[k] for k in range(3))/den
            if 1e-8<t<1.-1e-8 and math.dist(p,tuple(a[k]+t*delta[k] for k in range(3)))<tolerance:found.append((t,p))
        if found:
            unique=[]
            for t,p in sorted(found):
                if not unique or math.dist(p,unique[-1])>tolerance:unique.append(p)
            splits[(a,b)]=tuple(unique)
    result=[]
    for vertices in panels:
        out=[]
        for n in range(0,len(vertices),18):
            corners=[tuple(vertices[n+k:n+k+3]) for k in (0,6,12)];boundary=[]
            for a,b in zip(corners,(*corners[1:],corners[0])):
                key=tuple(sorted((a,b)));inner=splits.get(key,())
                boundary.extend((a,*(inner if key[0]==a else tuple(reversed(inner)))))
            if len(boundary)==3:out.extend(vertices[n:n+18]);continue
            # Convex source triangle boundary: retain every inserted edge
            # vertex without adding a center point or a cap fan T junction.
            normal=vertices[n+3:n+6];remaining=list(boundary)
            while len(remaining)>3:
                for j,b in enumerate(remaining):
                    a,c=remaining[j-1],remaining[(j+1)%len(remaining)]
                    ab=tuple(b[k]-a[k] for k in range(3));ac=tuple(c[k]-a[k] for k in range(3))
                    cross=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
                    if sum(cross[k]*normal[k] for k in range(3))>1e-10:
                        def contained(p):
                            for u,v in ((a,b),(b,c),(c,a)):
                                uv=tuple(v[k]-u[k] for k in range(3));up=tuple(p[k]-u[k] for k in range(3))
                                cr=(uv[1]*up[2]-uv[2]*up[1],uv[2]*up[0]-uv[0]*up[2],uv[0]*up[1]-uv[1]*up[0])
                                if sum(cr[k]*normal[k] for k in range(3))<-1e-8:return False
                            return True
                        if any(contained(p) for p in remaining if p not in (a,b,c)):continue
                        _tri(out,a,b,c);remaining.pop(j);break
                else:raise ValueError('GPU bevel edge refinement found a degenerate boundary')
            _tri(out,*remaining)
        result.append(tuple(out))
    if sum(len(v)//18 for v in result)>min(8192,2*sum(len(v)//18 for v in panels)+64):raise ValueError('GPU bevel output budget exceeded')
    return tuple(result)


def _bevel_silver_panel(vertices,outer,holes,depth):
    """Shallow true facet at the structural perimeter and real fan mouths.

    The same transform applies to all disjoint sourcepaint pieces, so a color
    boundary is not turned into an invented gap. Only real structural outer
    edges and fan apertures receive a bounded original reference chamfer.
    """
    from assembly_detail import _area,_tri
    signed=1. if _area(outer)>0 else -1.;edges=[]
    for a,b in zip(outer,(*outer[1:],outer[0])):
        dx,dy=b[0]-a[0],b[1]-a[1];size=math.hypot(dx,dy)
        edges.append((a,b,(-dy/size*signed,dx/size*signed),size))
    # One transient shared-point guard for all source paint pieces. A cap
    # vertex moves by at most 1/8 of the minimum incident cap altitude;
    # both front and rear copies use the same deterministic position map.
    limits={}
    for at in range(0,len(vertices),18):
        points=[tuple(vertices[at+k:at+k+3]) for k in (0,6,12)]
        if abs(vertices[at+5])<.999:continue
        ab=tuple(points[1][k]-points[0][k] for k in range(3))
        ac=tuple(points[2][k]-points[0][k] for k in range(3))
        cross=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
        area2=math.sqrt(sum(q*q for q in cross))
        edge=max(math.dist(a,b) for a,b in zip(points,(*points[1:],points[0])))
        bound=area2/max(edge,1e-20)/8.
        for p in points:limits[p]=min(limits.get(p,bound),bound)
    def point(v):
        x,y,z=v;front=max(0.,min(1.,z/depth+.5));bevel=.35*front
        inward=[]
        for a,b,normal,size in edges:
            cross=(b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0])
            t=((x-a[0])*(b[0]-a[0])+(y-a[1])*(b[1]-a[1]))/(size*size)
            if abs(cross)/size<1e-6 and -1e-6<=t<=1+1e-6:inward.append(normal)
        if inward:
            nx,ny=inward[0]
            if len(inward)>1:
                bx,by=inward[-1];det=nx*by-ny*bx
                if abs(det)>1e-8:dx,dy=bevel*(by-ny)/det,bevel*(nx-bx)/det
                else:dx,dy=nx*bevel,ny*bevel
            else:dx,dy=nx*bevel,ny*bevel
            # Do not move a structural chamfer into a real fan aperture.
            # Chord intersections are inside its circumscribed circle and
            # must retain their original position; true mouth vertices still
            # receive the separate outward chamfer below.
            distance=math.hypot(dx,dy)
            clearance=min((max(0.,math.hypot(v[0]-hx,v[1]-hy)-radius)
                           for hx,hy,radius in holes),default=distance)
            if distance>clearance:
                scale=clearance/distance;dx*=scale;dy*=scale
            x+=dx;y+=dy
        for hx,hy,radius in holes:
            old=math.hypot(v[0]-hx,v[1]-hy)
            if abs(old-radius)<1e-5:
                scale=(radius+.40*front)/max(1e-9,math.hypot(x-hx,y-hy));x=hx+(x-hx)*scale;y=hy+(y-hy)*scale
        # Do not fold a source cap sliver while preserving its topology.
        move=math.hypot(x-v[0],y-v[1]);limit=limits.get(tuple(v),move)
        if move>limit:
            scale=limit/move;x=v[0]+(x-v[0])*scale;y=v[1]+(y-v[1])*scale
        return x,y,z
    result=[]
    for n in range(0,len(vertices),18):
        _tri(result,*(point(vertices[n+i:n+i+3]) for i in (0,6,12)))
    return tuple(result)


def prepare_front_fans(meshes,spec):
    """Exact-model photo reference radius, then all front apertures follow it.

    The generic2D UV drawing is deliberately conservative. Mapping its two
    axes to this unusually deep card produced45.47mm reference radius; the
    manufacturer's front photograph supports a larger circle(.15-.17L), not
    a measured manufacturing diameter. Keep current centers/leaf profiles and
    resize ONLY the complete matching four-submesh front fan assemblies.
    """
    gpu=spec.get('gpu') or {};appearance=gpu.get('appearance') or {}
    facts=appearance.get('board_details') or {}
    if not(appearance.get('id')==EXACT_ID and appearance.get('fan_count')==4 and facts.get('backplate') is True):return meshes,{}
    from assembly_detail import _extent
    shroud=next((m for m in meshes if m.name=='gpu-shroud'),None)
    if shroud is None:return meshes,{}
    width,_,length=_extent(shroud);gx,gy,gz=shroud.position
    openings=[m for m in meshes if m.name=='gpu-fan-opening' and m.position[1]<gy]
    if len(openings)!=3:return meshes,{}
    changes=[]
    for opening in openings:
        old=max(math.hypot(opening.vertices[n],opening.vertices[n+2]) for n in range(0,len(opening.vertices),6))
        target=length*FRONT_RADIUS_RATIO_LENGTH
        target=min(target,width/2-abs(opening.position[0]-gx)-1.2,length/2-abs(opening.position[2]-gz)-1.2)
        for other in openings:
            if other is not opening:
                target=min(target,math.hypot(other.position[0]-opening.position[0],other.position[2]-opening.position[2])*.49)
        if not old>0 or target<5:return meshes,{}
        changes.append((opening.position[0],opening.position[2],old,target))
    result=[]
    for mesh in meshes:
        if mesh.name.startswith('gpu-fan-') and mesh.position[1]<gy:
            cx,cz,old,target=min(changes,key=lambda row:(row[0]-mesh.position[0])**2+(row[1]-mesh.position[2])**2)
            if abs(cx-mesh.position[0])<1e-6 and abs(cz-mesh.position[2])<1e-6:
                scale=target/old;values=[]
                for n in range(0,len(mesh.vertices),6):
                    x,y,z,nx,ny,nz=mesh.vertices[n:n+6];normal=(nx/scale,ny,nz/scale)
                    magnitude=math.sqrt(sum(v*v for v in normal))
                    values.extend((x*scale,y,z*scale,*(v/magnitude for v in normal)))
                mesh=replace(mesh,vertices=tuple(values))
        result.append(mesh)
    return tuple(result),dict(front_radius_observation=dict(source=FRONT_RADIUS_PHOTO,
        geometry='photo_reference_not_measured_diameter',radius_ratio_length=FRONT_RADIUS_RATIO_LENGTH,
        previous_radius_mm=tuple(row[2] for row in changes),reference_radius_mm=tuple(row[3] for row in changes),
        centers_changed=False,blade_profile_changed=False,rotation_direction_changed=False,
        generic_147_radius_mapping_changed=False))


def _cut_box(vertices,low,high):
    """Subtract one bounded clearance box, retaining only real surface facets."""
    from assembly_detail import _clip_plane,_tri
    planes=(((1.,0.,0.),-low[0]),((-1.,0.,0.),high[0]),
            ((0.,1.,0.),-low[1]),((0.,-1.,0.),high[1]),
            ((0.,0.,1.),-low[2]),((0.,0.,-1.),high[2]))
    result=[]
    for n in range(0,len(vertices),18):
        triangle=tuple(tuple(vertices[n+i:n+i+3]) for i in (0,6,12))
        if any(max(p[a] for p in triangle)<low[a] or min(p[a] for p in triangle)>high[a] for a in range(3)):
            result.extend(vertices[n:n+18]);continue
        remaining=triangle
        for normal,offset in planes:
            outside=_clip_plane(remaining,normal,offset,False)
            if outside:
                for index in range(1,len(outside)-1):_tri(result,outside[0],outside[index],outside[index+1])
            remaining=_clip_plane(remaining,normal,offset,True)
            if not remaining:break
    return tuple(result)


def refine(meshes,spec,level,*,outer,front_holes,rear_hole,edge_windows,edge_recesses,front_cutouts,port_holes):
    """Unmatched models are returned byte-for-byte and by tuple identity.

    Called in canonical GPU coordinates before the existing rigid case pose.
    Rings/rotor profiles are not approximated or replaced by a generic fan.
    """
    gpu=spec.get('gpu') or {};appearance=gpu.get('appearance') or {}
    facts=appearance.get('board_details') or {}
    if not(appearance.get('id')==EXACT_ID and appearance.get('fan_count')==4 and facts.get('backplate') is True):
        return meshes,{}
    from assembly_geometry import Mesh,color,gpu_plane,ring,unit_polygon
    from assembly_detail import (_area,_boxes,_extent,_screws,chamfer_rect,clear_port_tunnels,
                                 hollow_cover,perforated_plate)
    shroud=next((m for m in meshes if m.name=='gpu-shroud'),None)
    if shroud is None:return meshes,{}
    width,thickness,length=_extent(shroud);gx,gy,gz=shroud.position
    segments=32 if level=='close' else 12 if level=='eco' else 20
    graphite=color('#353b40');frame=color('#434a4e');fins=color('#262c30');silver=color('#b5babd');dark=color('#20282d')

    # The existing two-dimensional fan artwork remains unchanged. Only this
    # exact3D exterior uses the near-rectangular chamfered observed frame.
    # Corner/port/end-window dimensions are ORIGINAL PHOTO REFERENCE, not CAD.
    shell=chamfer_rect(length,width,min(length*.023,width*.055))
    windows={};recesses={}
    for index,a in enumerate(shell):
        b=shell[(index+1)%len(shell)]
        # Long outer face: exposed fin stack between the narrow front rail and
        # rear PCB/backplate, as directly visible in the exact side photograph.
        if abs(a[1]-width/2)<1e-6 and abs(b[1]-width/2)<1e-6:
            windows[index]=(((.015,-thickness*.385),(.985,-thickness*.385),
                              (.985,thickness*.33),(.015,thickness*.33)),)
        # The exact opposite/PCIe-edge photograph also exposes the fin stack
        # and board edge. Keeping a complete far wall behind the outer-side
        # gaps made the card look like a flat slab. Retain only observed top/
        # bottom rails and end posts; no painted black depth card is inserted.
        if abs(a[1]+width/2)<1e-6 and abs(b[1]+width/2)<1e-6:
            windows[index]=(((.025,-thickness*.46),(.975,-thickness*.46),
                              (.975,thickness*.32),(.025,thickness*.32)),)
        # Source-right/non-I/O end has a genuinely open cage between end posts;
        # do not add a solid endcap behind a merely dark painted rectangle.
        if abs(a[0]-length/2)<1e-6 and abs(b[0]-length/2)<1e-6:
            windows[index]=(((.10,-thickness*.34),(.90,-thickness*.34),
                              (.90,thickness*.30),(.10,thickness*.30)),)
        # Preserve ALL reference output-port apertures/recesses in the new
        # matching I/O wall, without deriving port locations from a photo.
        if abs(a[0]+length/2)<1e-6 and abs(b[0]+length/2)<1e-6:
            previous=[]
            for old_index,old_a in enumerate(outer):
                old_b=outer[(old_index+1)%len(outer)]
                if abs(old_a[0]+length/2)<1e-6 and abs(old_b[0]+length/2)<1e-6:
                    for hole in edge_windows.get(old_index,()):
                        # Edge fractions change when corner chamfers change;
                        # preserve the old aperture's actual sourceY/depth.
                        mapped=tuple(((old_a[1]+(old_b[1]-old_a[1])*u-a[1])/(b[1]-a[1]),v) for u,v in hole)
                        previous.append(mapped if _area(mapped)>0 else tuple(reversed(mapped)))
                    if old_index in edge_recesses:recesses[index]=edge_recesses[old_index]
            if previous:windows[index]=tuple(previous)
    body=hollow_cover(shell,front_holes,thickness,segments=segments,edge_windows=windows,
                      edge_recesses=recesses,front_cutouts=front_cutouts)
    body=gpu_plane(clear_port_tunnels(body,port_holes,length))
    # Same exact-id reference socket depth as the final-anchor adapter. The
    # photograph proves its PCB/backplate layer; it does not measure X/Y/Z.
    # Preserve the independently modeled socket casing/holes as actual geometry
    # from auxiliary, rather than painting an inlet on a closed cooler wall.
    port_z=length*.08;port_y=thickness*.40
    port_low=(-width/2-.5,port_y-7.1,port_z-11.2)
    port_high=(-width/2+5.0,min(thickness/2+.1,port_y+7.1),port_z+11.2)
    body=_cut_box(body,port_low,port_high)

    # Observe central opening and four-ear retention frame from exact rear
    # photograph, whose full card extent is x45..704,y238..494. The PCB visible
    # behind this hole stays the old explicitly schematic PCB; no IC array is
    # invented from the tiny photograph.
    def photo(x,y):return ((x-45.)/659.-.5)*length,(.5-(y-238.)/256.)*width
    socket=tuple(photo(x,y) for x,y in ((207,319),(286,319),(286,392),(207,392)))
    power_notch=((port_z-11.2,width*.44),(port_z+11.2,width*.44),
                 (port_z+11.2,width*.51),(port_z-11.2,width*.51))
    back=perforated_plate(chamfer_rect(length*.99,width*.98,min(6.,width*.04)),
                          (rear_hole,socket,power_notch),1.4,segments=segments,clip_walls=True)
    clamp=tuple(photo(x,y) for x,y in ((180,277),(199,277),(202,303),(290,303),
        (294,277),(316,277),(316,322),(307,332),(307,387),(316,399),
        (316,439),(294,439),(290,410),(202,410),(199,439),(180,439),
        (180,399),(190,387),(190,332),(180,322)))
    # This silhouette is concave. perforated_plate uses the existing ear-cut
    # triangulator and its real cap-hole subtraction, never a triangle fan.
    clamp_mesh=perforated_plate(clamp,(socket,),1.5,segments=segments,clip_walls=True)
    bracket_screws=[photo(x,y) for x,y in ((189,286),(306,286),(189,429),(306,429))]
    clamp_caps,clamp_slots=_screws([(x,y,0.) for x,y in bracket_screws],1.45)
    # Sample only visibly observed exterior fasteners; this is not a claim to
    # reproduce all screws, thread pitch, torque or exact manufacturing holes.
    visible=[photo(x,y) for x,y in ((60,252),(692,252),(692,481),(60,481),(469,307),(469,410))]
    caps,slots=_screws([(x,y,0.) for x,y in visible],1.35)
    # The old six sourcepaint polygons share one Z plane. Preserve their
    # original painter order through true disjoint geometry, so perspective
    # depth interpolation cannot turn the silver cover into random triangles.
    panel_rows=[]
    for row in gpu.get('detail_polygons') or ():
        points=row.get('points') if isinstance(row,dict) else row
        polygon=unit_polygon(points,length,width,margin=.3)
        if polygon:panel_rows.append(polygon)
    # Source paint contains T junctions. Split only those existing edges
    # before the shared deformation so a bevel cannot pull a long edge away
    # from its short neighbors. No additional hardware or material is added.
    panel_depth=1.1
    raw_panels=tuple(perforated_plate(poly,(*front_holes,*panel_rows[i+1:]),panel_depth,
                                     segments=segments,clip_walls=True)
                     for i,poly in enumerate(panel_rows))
    bevel_fallback=False
    try:
        conforming=_conforming_panel_edges(raw_panels)
        beveled_vertices=_bevel_silver_panel(tuple(v for panel in conforming for v in panel),
                                  panel_rows[0],front_holes,panel_depth) if panel_rows else ()
        silver_panels=[];offset=0
        for panel in conforming:
            silver_panels.append(beveled_vertices[offset:offset+len(panel)]);offset+=len(panel)
    except (ValueError,OverflowError,ZeroDivisionError):
        # Preserve the complete original through-hole plate on a bounded
        # refinement failure; never apply a nonconforming bevel as fallback.
        silver_panels=raw_panels;bevel_fallback=True
    panel_index=0
    fin_count=128 if level=='close' else 12 if level=='eco' else 96
    fin_rows=[((width*.84,thickness*.60,.25),(0,1.,-length*.41+n*length*.82/(fin_count-1))) for n in range(fin_count)]
    # Exact same closed sampled sheets, partitioned by existing geometric face
    # normal. Photo-observed dark broad surfaces and brighter thin cut edges
    # make individual fins readable without inserting a black backing card,
    # overlay decal, extra physical rail or invented material specification.
    fin_faces=[];fin_edges=[];all_fin_faces=_boxes(fin_rows)
    for n in range(0,len(all_fin_faces),18):
        (fin_edges if abs(all_fin_faces[n+3])>.999 else fin_faces).extend(all_fin_faces[n:n+18])
    front_openings=[m for m in meshes if m.name=='gpu-fan-opening' and m.position[1]<gy]
    curved_triangles_before=curved_triangles_after=0
    result=[]
    for mesh in meshes:
        if mesh.name=='gpu-shroud':mesh=replace(mesh,vertices=body,color=frame)
        elif mesh.name=='gpu-cover-panel':
            if panel_index<len(silver_panels):
                panel=silver_panels[panel_index];panel_index+=1
                if not panel:continue
                mesh=replace(mesh,vertices=gpu_plane(panel),position=(gx,gy-thickness/2+panel_depth/2+.12,gz))
        elif mesh.name=='gpu-fan-rotor' and mesh.position[1]<gy:
            opening=min(front_openings,key=lambda m:(m.position[0]-mesh.position[0])**2+(m.position[2]-mesh.position[2])**2)
            radius=max(math.hypot(opening.vertices[n],opening.vertices[n+2]) for n in range(0,len(opening.vertices),6))
            curved=curve_front_rotor(mesh.vertices,radius,mesh.direction,level)
            curved_triangles_before+=len(mesh.vertices)//18;curved_triangles_after+=len(curved)//18
            mesh=replace(mesh,vertices=curved)
        elif mesh.name=='gpu-fan-recess' and mesh.position[1]<gy:
            # The stationary cavity's back ring must sit behind the cupped
            # leaf sweep, rather than cutting through a newly curved blade.
            mesh=replace(mesh,position=(mesh.position[0],gy-thickness/2+11.,mesh.position[2]))
        elif mesh.name=='gpu-backplate':mesh=replace(mesh,vertices=gpu_plane(back),color=graphite,position=(gx,gy+thickness/2-1.65,gz))
        elif mesh.name=='gpu-pcb':mesh=replace(mesh,color=color('#252d2c'))
        elif mesh.name=='detail-gpu-heatsink-fins':mesh=replace(mesh,vertices=tuple(fin_faces),color=fins)
        elif mesh.name=='detail-gpu-backplate-fasteners':mesh=replace(mesh,vertices=gpu_plane(caps),color=dark,position=(gx,gy+thickness/2-.75,gz))
        elif mesh.name=='detail-gpu-fastener-slots':mesh=replace(mesh,vertices=gpu_plane(slots),color=silver,position=(gx,gy+thickness/2+.05,gz))
        result.append(mesh)
    def add(name,vertices,tone,y):
        if vertices:result.append(Mesh(name,gpu_plane(vertices),tone,(gx,y,gz),'gpu'))
    result.append(Mesh('detail-gpu-heatsink-cut-edges',tuple(fin_edges),color('#717a80'),(gx,gy,gz),'gpu'))
    add('detail-gpu-observed-retention-frame',clamp_mesh,dark,gy+thickness/2-1.35)
    add('detail-gpu-observed-retention-screws',clamp_caps,silver,gy+thickness/2-.55)
    add('detail-gpu-observed-retention-slots',clamp_slots,dark,gy+thickness/2+.20)

    # Thin end-post inner ribs make the open end read as an exoskeleton. They
    # occupy the existing envelope; they are not an installed support stand.
    ribs=[((2.2,thickness*.53,2.2),(side*width*.36,-thickness*.01,length/2-2.8)) for side in (-1,1)]
    if ribs:result.append(Mesh('detail-gpu-observed-end-cage-ribs',_boxes(ribs),graphite,(gx,gy,gz),'gpu'))
    # The exact front photographs show fine silver hub rims and a silver ring
    # on the distal third fan; the first two outer rims stay dark. Batch all
    # static trim in one material mesh, with no logo, text texture or clock.
    from assembly_detail import translated
    trims=[];ring_segments=24 if level=='close' else 12 if level=='eco' else 16
    for mesh in meshes:
        if mesh.name!='gpu-fan-hub' or mesh.position[1]>=gy:continue
        radius=max(math.hypot(mesh.vertices[n],mesh.vertices[n+2]) for n in range(0,len(mesh.vertices),6))
        local=gpu_plane(ring(radius*1.015,radius*.94,.24,segments=ring_segments))
        position=(mesh.position[0]-gx,mesh.position[1]-gy-1.42,mesh.position[2]-gz)
        trims.extend(translated(local,position))
    front=[m for m in meshes if m.name=='gpu-fan-opening' and m.position[1]<gy]
    if front:
        distal=max(front,key=lambda m:m.position[2])
        radius=max(math.hypot(distal.vertices[n],distal.vertices[n+2]) for n in range(0,len(distal.vertices),6))
        local=gpu_plane(ring(radius*1.003,radius*.962,.24,segments=ring_segments))
        position=(distal.position[0]-gx,distal.position[1]-gy-1.12,distal.position[2]-gz)
        trims.extend(translated(local,position))
    if trims:result.append(Mesh('detail-gpu-observed-front-metal-rings',tuple(trims),silver,(gx,gy,gz),'gpu'))
    metadata=dict(exterior_model_id=EXACT_ID,exterior_geometry='official_photo_observed_reference',
        exterior_sources=(GALLERY,REAR_PHOTO,SIDE_PHOTO,FRONT_PHOTO,END_PHOTO,FRONT_RADIUS_PHOTO,PCB_EDGE_PHOTO),
        factory_palette='illustrative_graphite_side_rear_silver_front',exterior_palette_measured=False,
        rear_socket_window=True,retention_frame=True,retention_frame_is_support_stand=False,
        fin_sampling_count=fin_count,front_panels_partitioned=True,
        fin_faces_partitioned_by_existing_normals=True,fin_tones_are_observed_reference=True,
        silver_panel_depth_reference_mm=1.1,silver_panel_bevel_reference_mm=.35,fan_mouth_bevel_reference_mm=.40,
        front_blade_curvature='photo_observed_curvature_original_reference',front_blade_curvature_source=FRONT_RADIUS_PHOTO,
        front_blade_cup_peak_reference_mm=5.4,front_manufacturer_blade_pitch_verified=False,
        front_rotor_triangles_before_curving=curved_triangles_before,front_rotor_triangles_after_curving=curved_triangles_after,
        fan_cavity_back_reference_mm=11.,
        front_hub_rims=True,distal_front_metal_ring=True,
        end_cage_open=True,photo_coordinates_are_cad=False,pcb_internal_layout_verified=False,
        pcb_edge_open=True,pcb_edge_window_source=PCB_EDGE_PHOTO,fin_gaps_have_opaque_far_wall=False,
        source_backplate_fasteners_sampled=len(visible),source_retention_fasteners_observed=len(bracket_screws),
        electrical_anchor_changed=False,power_socket_clearance=True,power_socket_clearance_is_reference=True,
        power_socket_depth_reference=.4,front_fan_reference_radius_resized=True,front_blade_profile_retained=True,front_fans_reoriented=False,
        rear_rpm_verified=False,retail_pcb_outline_verified=False)
    if bevel_fallback:
        metadata.update(silver_panel_bevel_reference_mm=0.,fan_mouth_bevel_reference_mm=0.,
                        silver_panel_bevel_fallback='safe_unbeveled_source_plate_refinement_budget')
    return tuple(result),metadata
