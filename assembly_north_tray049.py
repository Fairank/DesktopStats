"""North XL's documented tray, with bounded reference machining and no I/O.

The standard TG/Mesh manual p15 shows the CPU access window, two pairs of
vertical cable openings and top-edge passages. Their simplified coordinates
are reference proportions, not factory measurements or a CAD fit certificate.
The fixed motherboard, GPU, connectors and complete cables are never moved.
"""

_MANUAL='https://assets.fractal-design.com/files/uxzbxy2o/production/b9da6c6ccec21bb0859a91f1f2f5c424048391d1.pdf'
_SHEET='https://www.fractal-design.com/products/cases/north-series/north-xl/north-xl-chalk-white-mesh/'


def shroud(case,dimensions):
    """One connected thin cover, not a filled power-supply compartment.

    Only the exact North XL Mesh is covered by these observed surfaces. The
    dark-side gallery shows the top, the viewing-side skin and a front relief;
    it does not justify adding a second full-height wall behind the PSU. The
    opposite boundary is already represented by the chassis/right-side skin.
    Unlabelled thickness and relief coordinates remain fixed photo references,
    independent of the selected fan, power supply, or a desired motion result.
    """
    if case.get('id')!='fractal-north-xl-mesh':return (),{}
    import math
    from assembly_geometry import _tri,_quad
    if (not isinstance(dimensions,(tuple,list)) or len(dimensions)!=3
            or any(type(v) not in (int,float) or not math.isfinite(v) for v in dimensions)):
        return (),{}
    w,h,d=dimensions
    if not (60<=w<=800 and 60<=h<=900 and 150<=d<=900):return (),{}
    half=(w-12.)/2;thickness=1.2;inner=-half+thickness
    bottom=-h*.49;top=-h*.32;underside=top-thickness
    rear=-(d-12.)/2;front=(d-12.)/2;end=d*.34
    # The observed side skin drops nearly vertically before a small rounded
    # inside corner. It is not a long diagonal ramp. These fixed proportions
    # and the bounded4.5mm radius are photo references, not labelled dimensions.
    low=top-h*.06;radius=min(4.5,h*.018)
    profile=tuple((end+radius+radius*math.cos(math.pi+i*math.pi/8),
                   low+radius+radius*math.sin(math.pi+i*math.pi/8)) for i in range(5))
    profile=((end,low+radius),*profile[1:-1],(end+radius,low),(front,low))
    origin=(0.,-h*.405,0.);vertices=[]
    def face(points,normal):
        points=list(points)
        a,b,c=points[:3]
        ab=tuple(b[i]-a[i] for i in range(3));ac=tuple(c[i]-a[i] for i in range(3))
        cross=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
        if sum(cross[i]*normal[i] for i in range(3))<0:points.reverse()
        points=[tuple(p[i]-origin[i] for i in range(3)) for p in points]
        if len(points)==4:_quad(vertices,*points)
        else:
            for i in range(1,len(points)-1):_tri(vertices,points[0],points[i],points[i+1])
    # The rear cover is an L cross-section. Splitting at the physical fold
    # keeps matching boundary edges at the roof/side/front-relief junction.
    xs=(-half,inner,half);ys=(bottom,low+radius,underside,top)
    solid={(0,0),(0,1),(0,2),(1,2)}
    for i,j in sorted(solid):
        x0,x1=xs[i:i+2];y0,y1=ys[j:j+2]
        face(((x0,y0,rear),(x1,y0,rear),(x1,y1,rear),(x0,y1,rear)),(0,0,-1))
        if (i,j)!=(0,0):
            face(((x0,y0,end),(x1,y0,end),(x1,y1,end),(x0,y1,end)),(0,0,1))
        for di,dj,points,normal in (
                (-1,0,((x0,y0,rear),(x0,y1,rear),(x0,y1,end),(x0,y0,end)),(-1,0,0)),
                (1,0,((x1,y0,rear),(x1,y1,rear),(x1,y1,end),(x1,y0,end)),(1,0,0)),
                (0,-1,((x0,y0,rear),(x1,y0,rear),(x1,y0,end),(x0,y0,end)),(0,-1,0)),
                (0,1,((x0,y1,rear),(x1,y1,rear),(x1,y1,end),(x0,y1,end)),(0,1,0))):
            if (i+di,j+dj) not in solid:face(points,normal)
    # Continue just the thin viewing-side skin through the front step. Every
    # station shares its complete cross-section; no floating diagonal blocks.
    for (z0,y0),(z1,y1) in zip(profile,profile[1:]):
        for x,normal in ((-half,(-1,0,0)),(inner,(1,0,0))):
            a,b,c,e=(x,bottom,z0),(x,bottom,z1),(x,y1,z1),(x,y0,z0)
            face((a,b,c,e),normal)
        face(((-half,y0,z0),(inner,y0,z0),(inner,y1,z1),(-half,y1,z1)),(0,1,0))
        face(((-half,bottom,z0),(inner,bottom,z0),(inner,bottom,z1),(-half,bottom,z1)),(0,-1,0))
    face(((-half,bottom,front),(inner,bottom,front),(inner,low,front),(-half,low,front)),(0,0,1))
    meta=dict(case_id=case['id'],method='official_gallery_observed_thin_cover_reference',
        sources=('https://www.fractal-design.com/products/cases/north-series/north-xl/north-xl-charcoal-black-mesh/',
                 'https://assets.fractal-design.com/images/uxzbxy2o/production/3e2f7cc1e6b2755c0770e70ac694caa537c4d72a-2560x2560.jpg',
                 'https://assets.fractal-design.com/images/uxzbxy2o/production/a3646ccb69cb9022bc2f3c934471833911553812-2560x2560.jpg'),
        position_mm=origin,thickness_mm=thickness,thickness_verified=False,
        normalized_reference=dict(deck_end_depth_fraction=.34,front_drop_height_fraction=.06),
        relief_corner_radius_mm=radius,relief_corner_radius_verified=False,
        relief_profile_world_yz_mm=((top,end),*tuple((y,z) for z,y in profile)),
        reference_bounds=dict(min=(-half,bottom,rear),max=(half,top,front)),
        dimensions_verified=False,positions_verified=False,cad_verified=False,
        chamber_is_solid=False,front_bay_open=True,lower_front_deck_added=False,
        far_side_wall_added=False,far_side_boundary='existing_case_right_and_motherboard_tray',
        ventilation_observed=True,exact_vent_pattern_modeled=False,
        source_photos_are_private_references=True,selected_component_geometry_used=False)
    return tuple(vertices),meta


def add_tray(meshes,case,dimensions):
    """Return original meshes unchanged for every other catalogued chassis."""
    if case.get('id')!='fractal-north-xl-mesh':return meshes,{}
    from assembly_geometry import Mesh,_quad
    w,h,d=dimensions
    # These are fixed case-space reference proportions. Never derive cutouts
    # from the selected board, CPU, headers or a cable that needs a passage.
    bx,by=w*.36,h*.02;bh,bw=305.,244.;rear=-d/2+14.
    # The existing PCB pose is schematic. Preserve it: a reference spacer gap
    # locates the tray between its back and the current rear routing corridor.
    # The documented29mm cable-space specification is not used as factory CAD.
    x=bx+8.;thickness=1.2
    z0,z1=rear-7.,rear+330.+38.
    y0,y1=by-bh/2-20.,by+bh/2+22.
    front=rear+bw;column1=front+31.;column2=front+102.
    holes=[dict(role='cpu_backplate_access',z0=rear+bw*.41-95.,z1=rear+bw*.41+95.,
                y0=by+bh*.22-65.,y1=by+bh*.22+65.)]
    for column in (column1,column2):
        for center,height in ((by+bh*.25,110.),(by-bh*.26,115.)):
            holes.append(dict(role='vertical_cable_passage',z0=column-15.,z1=column+15.,y0=center-height/2,y1=center+height/2))
    for a,b in ((rear+15.,rear+115.),(rear+145.,front+64.)):
        holes.append(dict(role='top_edge_cable_passage',z0=a,z1=b,y0=by+bh/2+2.,y1=y1+1.))
    zs=sorted({z0,z1,*[max(z0,min(z1,h[k])) for h in holes for k in ('z0','z1')]})
    ys=sorted({y0,y1,*[max(y0,min(y1,h[k])) for h in holes for k in ('y0','y1')]})
    solid=set()
    for j,(a,b) in enumerate(zip(ys,ys[1:])):
        for i,(c,d) in enumerate(zip(zs,zs[1:])):
            cy,cz=(a+b)/2,(c+d)/2
            if not any(h['y0']<cy<h['y1'] and h['z0']<cz<h['z1'] for h in holes):solid.add((i,j))
    vertices=[];rectangles=[]
    for i,j in sorted(solid):
        lo,hi=ys[j:j+2];a,b=zs[i:i+2]
        front_points=((x-thickness/2,lo,a),(x-thickness/2,lo,b),(x-thickness/2,hi,b),(x-thickness/2,hi,a))
        back_points=tuple((x+thickness/2,p[1],p[2]) for p in front_points)
        _quad(vertices,*front_points);_quad(vertices,*reversed(back_points))
        # Only true perimeter/hole walls: internal grid cells have no walls,
        # so the crease pass cannot invent a lattice of structural ribs.
        for edge,neighbor in enumerate(((i,j-1),(i+1,j),(i,j+1),(i-1,j))):
            if neighbor not in solid:
                n=(edge+1)%4
                _quad(vertices,front_points[edge],back_points[edge],back_points[n],front_points[n])
    # Merge each contiguous solid strip before making the collision boxes.
    # A hole is never replaced with the entire tray's filled AABB.
    for j in range(len(ys)-1):
        start=None
        for i in range(len(zs)):
            filled=(i,j) in solid
            if filled and start is None:start=i
            if not filled and start is not None:
                rectangles.append((zs[start],zs[i],ys[j],ys[j+1]));start=None
    merged=[]
    for rectangle in rectangles:
        a,b,c,d=rectangle
        previous=next((n for n,row in enumerate(merged) if row[:2]==(a,b) and row[3]==c),None)
        if previous is None:merged.append(rectangle)
        else:merged[previous]=(a,b,merged[previous][2],d)
    assert len(merged)<=64
    bounds=[dict(min=(x-thickness/2,c,a),max=(x+thickness/2,d,b)) for a,b,c,d in merged]
    meta=dict(case_id=case['id'],plane_x_mm=x,thickness_mm=thickness,bounds=dict(min=(x-thickness/2,y0,z0),max=(x+thickness/2,y1,z1)),
        openings=holes,solid_bounds=bounds,collision_method='exact_rectangular_plate_cells',
        method='official_manual_observed_reference',manual=_MANUAL,manual_page=15,sources=(_MANUAL,_SHEET),
        dimensions_verified=False,mounting_holes_verified=False,cad_verified=False,documented_cable_space_mm=29.,
        plane_is_reference=True,front_entry_z_mm=z1+18.,top_lane_y_mm=by+bh/2+8.,cable_columns_z_mm=(column1,column2))
    mesh=Mesh('case-motherboard-tray-reference',tuple(vertices),(.27,.31,.35,1.),component='case')
    return tuple((*meshes,mesh)),meta


def add_obstacles(anchors,meta):
    """Use the same physical solid cells in each existing attachment stage."""
    if not meta:return anchors
    anchors['case_tray']=meta
    anchors.setdefault('obstacles',[]).extend(dict(bounds=row,kind='case',part_id='case:tray',name='case-motherboard-tray-reference',
        conservative_mesh_aabb=False,source=meta['manual']) for row in meta['solid_bounds'])
    return anchors
