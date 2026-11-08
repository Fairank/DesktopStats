"""Source-qualified chassis limits and fixed reference structure, not CAD.

Helios tray proportions are observed from ASUS's empty-chassis photographs;
the documented60/90mm cooling limits and33mm maximum cable space are facts.
No openings depend on selected hardware or a cable that needs to pass through.
"""
SPEC = 'https://rog.asus.com/us/cases/rog-strix-helios-model/spec/'
FEATURES = 'https://rog.asus.com/us/cases/rog-strix-helios-model/'
TRAY_PHOTO = 'https://dlcdnimgs.asus.com/websites/global/products/g2Pl47nZaToiPUKg/img/pic_Multi_Function_Cover.jpg'
REAR_PHOTO = 'https://dlcdnimgs.asus.com/websites/global/products/g2Pl47nZaToiPUKg/img/pic_Rear_Cable_Cover.jpg'
HELIOS = 'asus-rog-strix-helios-gx601'


def radiator_stack_check(case,cooler,mount,fan):
    """Check documented nominal assembly thickness; never invent other limits."""
    if case.get('id') != HELIOS or mount not in ('front','top'):
        return None
    layout=cooler.get('_radiator_fan_layout','single')
    banks=0 if layout=='none' else 2 if layout=='push_pull' else 1
    thickness=float(cooler['radiator_mm']['thickness'])
    fan_depth=float(fan['depth_mm'])
    gap=.8*banks  # Existing renderer's explicit reference separation.
    required=thickness+banks*fan_depth+gap
    limit=60. if mount=='top' else 90.
    return dict(case_id=HELIOS,mount=mount,required_mm=required,limit_mm=limit,
        radiator_thickness_mm=thickness,fan_depth_mm=fan_depth,fan_banks=banks,
        reference_gap_mm=gap,within_limit=required<=limit+1e-7,
        source=SPEC,limit_verified=True,placement_verified=False,cad_fit_verified=False)


def _inside(point,polygon):
    signs=[]
    for a,b in zip(polygon,(*polygon[1:],polygon[0])):
        cross=(b[0]-a[0])*(point[1]-a[1])-(b[1]-a[1])*(point[0]-a[0])
        if abs(cross)>1e-7:signs.append(cross>0)
    return not signs or all(sign==signs[0] for sign in signs)


def add_helios_tray(meshes,case,dimensions):
    """A single real pierced mesh plus bounded conservative solid cells."""
    if case.get('id') != HELIOS:
        return meshes,{}
    from assembly_geometry import Mesh,rotate_vertices,_tri,_quad
    from assembly_detail import _clip,_subtract,chamfer_rect
    w,h,d=dimensions
    x=w*.36+8.;depth=1.2;by=h*.02;rear=-d/2+14.
    z0,z1=rear-6.,d*.28
    y0,y1=by-305./2-26.,by+305./2+4.
    outer=tuple((a+(z0+z1)/2,b+(y0+y1)/2) for a,b in chamfer_rect(z1-z0,y1-y0,6.))
    # The visibly octagonal CPU access window differs from North's rectangle.
    cz,cy=rear+d*.24,h*.13
    cpu=tuple((a+cz,b+cy) for a,b in chamfer_rect(190.,170.,24.))
    column=rear+244.+45.
    holes=[cpu]
    openings=[dict(role='cpu_backplate_access',polygon=cpu)]
    for center,height in ((h*.20,82.),(0.,112.),(-h*.20,88.)):
        polygon=((column-14.,center-height/2),(column+14.,center-height/2),
                 (column+14.,center+height/2),(column-14.,center+height/2))
        holes.append(polygon);openings.append(dict(role='vertical_cable_passage',polygon=polygon))
    # Cells conservatively include the chamfer-corner material. They never
    # fill an entire access opening or omit a real material wedge as air.
    zs=sorted({z0,z1,*[max(z0,min(z1,p[0])) for poly in (outer,*holes) for p in poly]})
    ys=sorted({y0,y1,*[max(y0,min(y1,p[1])) for poly in (outer,*holes) for p in poly]})
    # A common cap grid and correspondingly split walls keep all T junctions
    # physically connected. Independent polygon subtraction otherwise leaves
    # unpaired triangulation edges that look like invented ribs in line art.
    cap=[]
    for lo,hi in zip(ys,ys[1:]):
        for a,b in zip(zs,zs[1:]):
            poly=((a,lo),(b,lo),(b,hi),(a,hi))
            for first,last in zip(outer,(*outer[1:],outer[0])):poly=_clip(poly,first,last,True)
            pieces=(poly,) if poly else ()
            for hole in holes:
                # Boundary-only contact removes no material. Avoid splitting
                # that neighboring cap along infinite extensions of hole edges.
                children=[]
                for piece in pieces:
                    contact=any(max(p[k] for p in piece)<=min(p[k] for p in hole)+1e-7
                        or min(p[k] for p in piece)>=max(p[k] for p in hole)-1e-7 for k in (0,1))
                    children.extend((piece,) if contact else _subtract(piece,hole))
                pieces=tuple(children)
            for piece in pieces:
                for i in range(1,len(piece)-1):
                    a,b,c=piece[0],piece[i],piece[i+1]
                    _tri(cap,(*a,depth/2),(*b,depth/2),(*c,depth/2))
                    _tri(cap,(*c,-depth/2),(*b,-depth/2),(*a,-depth/2))
    for poly,is_hole in ((outer,False),*((hole,True) for hole in holes)):
        for a,b in zip(poly,(*poly[1:],poly[0])):
            values={0.,1.}
            for axis,grid in ((0,zs),(1,ys)):
                if abs(b[axis]-a[axis])>1e-8:
                    values.update((value-a[axis])/(b[axis]-a[axis]) for value in grid if 1e-8<(value-a[axis])/(b[axis]-a[axis])<1-1e-8)
            values=sorted(values)
            for low,high in zip(values,values[1:]):
                p=tuple(a[k]+low*(b[k]-a[k]) for k in (0,1))
                q=tuple(a[k]+high*(b[k]-a[k]) for k in (0,1))
                if is_hole:p,q=q,p
                _quad(cap,(*p,-depth/2),(*q,-depth/2),(*q,depth/2),(*p,depth/2))
    vertices=rotate_vertices(cap,'left')
    mesh=Mesh('case-motherboard-tray-reference',vertices,(.24,.28,.31,1.),(x,0.,0.),'case',part_id='case:tray')
    strips=[]
    for lo,hi in zip(ys,ys[1:]):
        start=None
        for i in range(len(zs)):
            filled=False
            if i<len(zs)-1:
                a,b=zs[i:i+2]
                corners=((a,lo),(b,lo),(b,hi),(a,hi))
                filled=not any(all(_inside(p,hole) for p in corners) for hole in holes)
            if filled and start is None:start=i
            if not filled and start is not None:
                strips.append((zs[start],zs[i],lo,hi));start=None
    merged=[]
    for a,b,c,e in strips:
        index=next((i for i,row in enumerate(merged) if row[:2]==(a,b) and row[3]==c),None)
        if index is None:merged.append((a,b,c,e))
        else:merged[index]=(a,b,merged[index][2],e)
    if len(merged)>64:raise ValueError('Helios reference tray exceeded its collision-cell budget')
    solid=[dict(min=(x-depth/2,c,a),max=(x+depth/2,e,b)) for a,b,c,e in merged]
    meta=dict(case_id=HELIOS,plane_x_mm=x,thickness_mm=depth,
        bounds=dict(min=(x-depth/2,y0,z0),max=(x+depth/2,y1,z1)),outer_polygon=outer,openings=openings,solid_bounds=solid,
        collision_method='conservative_chamfer_material_cells',method='official_empty_chassis_photo_reference',
        manual=FEATURES,sources=(SPEC,TRAY_PHOTO,REAR_PHOTO),dimensions_verified=False,
        mounting_holes_verified=False,cad_verified=False,documented_cable_space_mm=33.,
        plane_is_reference=True,front_entry_z_mm=z1+12.,top_lane_y_mm=y1+8.,
        cable_columns_z_mm=(column,),factory_hole_positions_verified=False)
    return tuple((*meshes,mesh)),meta
