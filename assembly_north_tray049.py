"""North XL's documented tray, with bounded reference machining and no I/O.

The standard TG/Mesh manual p15 shows the CPU access window, two pairs of
vertical cable openings and top-edge passages. Their simplified coordinates
are reference proportions, not factory measurements or a CAD fit certificate.
The fixed motherboard, GPU, connectors and complete cables are never moved.
"""

_MANUAL='https://assets.fractal-design.com/files/uxzbxy2o/production/b9da6c6ccec21bb0859a91f1f2f5c424048391d1.pdf'
_SHEET='https://www.fractal-design.com/products/cases/north-series/north-xl/north-xl-chalk-white-mesh/'


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
