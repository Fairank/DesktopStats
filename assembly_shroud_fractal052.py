"""Three exact Fractal covers, observed skins rather than filled PSU bays.

Original bounded reference meshes, not manufacturer CAD. Unlabelled thickness,
inlay boundaries and the North front step are fixed photograph proportions.
The selected fan/radiator never deforms a panel. The two documented inlays can
instead be removed as complete parts during construction, before indexing.
"""
from copy import deepcopy
import math

_NORTH='fractal-north-mesh'
_ROWS={
    _NORTH:dict(label='North',product='https://www.fractal-design.com/products/cases/north-series/north/north-chalk-white/',
        manual='https://www.fractal-design.com/app/uploads/2022/12/North-Manual-V1.2.pdf',
        photo='https://assets.fractal-design.com/images/uxzbxy2o/production/c7862b4060e14ab8f58a5f503242cdd50440ab25-2560x2560.jpg',
        pages=(6,7,33),roof_end=.28,drop=.06,inlays=False),
    'fractal-meshify-2-light-tg':dict(label='Meshify 2',
        product='https://www.fractal-design.com/products/cases/meshify-series/meshify-2/meshify-2-black-light-tg/',
        manual='https://www.fractal-design.com/app/uploads/2023/08/Meshify-2-Manual-V.4-2023-08-21.pdf',
        photo='https://assets.fractal-design.com/images/uxzbxy2o/production/ffbf4305e4ed6c5100ad12c677c871b9b9ec6601-2560x2560.jpg',
        pages=(5,44),roof_end=.18,inlay_seam=.32,inlays=True),
    'fractal-define-7-compact-solid':dict(label='Define 7 Compact',
        product='https://www.fractal-design.com/products/cases/define-series/define-7-compact/define-7-compact-black-solid/',
        manual='https://www.fractal-design.com/app/uploads/2023/08/Define-7-Compact-Manual-V.2-2023-08-21.pdf',
        photo='https://assets.fractal-design.com/images/uxzbxy2o/production/68bd61b7d050502c9980f349cc7c64c950241d5d-2560x2560.jpg',
        pages=(5,25),roof_end=.16,inlay_seam=.32,inlays=True),
}
CASE_IDS=tuple(_ROWS)
_TOP_SOURCES={
    _NORTH:'https://support.fractal-design.com/support/solutions/articles/4000189453-north-radiator-compatibility',
    'fractal-meshify-2-light-tg':'https://support.fractal-design.com/support/solutions/articles/4000174746-meshify-2',
    'fractal-define-7-compact-solid':'https://support.fractal-design.com/support/solutions/articles/4000174752-define-7-compact',
}


def layout_reference(case,dimensions):
    """Exact horizontal-PSU/ATX host references, never selected-size carving.

    The manuals depict a flat upper PSU panel and bottom filtered bay. Their
    unlabelled fan orientation/host coordinates remain references, not measured
    mounting data. The caller derives the supply center from its real size.
    """
    if not isinstance(case,dict) or case.get('id') not in _ROWS:return {}
    if (not isinstance(dimensions,(tuple,list)) or len(dimensions)!=3
            or any(type(v) not in (int,float) or not math.isfinite(v) for v in dimensions)):
        return {}
    w,h,d=dimensions
    if not (60<=w<=800 and 60<=h<=900 and 150<=d<=900):return {}
    identity=case['id'];row=_ROWS[identity];source=_TOP_SOURCES[identity]
    def limit(supported,width,height,*,height_restriction=True):
        return dict(supported=supported,max_width_mm=width,ram_height_limit_mm=height,source_url=source,
            max_width_verified=width is not None,ram_height_limit_verified=height is not None,
            ram_height_restriction_applies=height_restriction)
    if identity==_NORTH:
        sizes={'120':limit(True,122.,35.),'140':limit(False,None,None,height_restriction=False)}
    elif identity=='fractal-define-7-compact-solid':
        sizes={'120':limit(True,None,40.),'140':limit(False,None,None,height_restriction=False)}
    else:
        # Explicit manufacturer distinction: standard120mm-series uses the
        # outer rails without the RAM-height restriction of140mm-series.
        # None here means no listed restriction, not a manufactured dimension.
        sizes={'120':limit(True,124.,None,height_restriction=False),'140':limit(True,None,36.)}
    result=dict(case_id=identity,source=row['manual'],source_urls=(row['product'],row['manual'],row['photo'],source),
        reference_only=True,verified=False,dimensions_verified=False,positions_verified=False,
        board_y_mm=h*.10,board_positions_verified=False,
        roof_y_mm=-h/2+h*.24,roof_position_verified=False,
        side_bottom_y_mm=-h/2+19.,side_bottom_position_verified=False,
        source_psu_manual_pdf_page=12 if case['id']==_NORTH else 13,
        psu_fan_world_normal_reference=(0.,-1.,0.),psu_fan_orientation_verified=False,
        psu_orientation_basis='manual_flat_upper_psu_panel_and_filtered_lower_bay',
        drawing_floor_gap_mm=1.,drawing_floor_gap_verified=False,
        radiator_constraints=dict(top=dict(layout='standard_reference',source_url=source,by_fan_size_mm=sizes,
            motherboard_vrm_and_io_height_not_verified=True,
            storage_layout_implemented=False if identity=='fractal-meshify-2-light-tg' else None)),
        psu=dict(basis=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.)),center_x_mm=0.,
            floor_y_mm=-h/2+20.,rear_z_mm=-d/2+10.,
            reference_only=True,positions_verified=False,source=row['manual']))
    def plane(x,role,role_verified):
        return dict(position=(x,h/2-10.,0.),normal=(0.,1.,0.),up=(0.,0.,1.),span_mm=(w-24.,d-32.),
            source=source,reference_only=True,positions_verified=False,dimensions_verified=False,verified=False,
            source_role=role,source_rail_role_verified=role_verified,position_fraction_reference=x/w,
            offset_is_manufacturer_dimension=False)
    # North/Define's source specifies support and component-height limits,
    # not a numerical rail offset. These fixed drawing references are kept
    # separate from those facts. Meshify explicitly describes outer120 rails;
    # its unlabelled coordinate is still not a measured factory dimension.
    meshify=identity=='fractal-meshify-2-light-tg'
    result['top_mount_planes_by_fan_size_mm']={'120':plane(-w*.16,
        'outer_120mm_top_rail_standard_layout' if meshify else 'top_120mm_rail_position_reference',meshify)}
    if meshify:result['top_mount_planes_by_fan_size_mm']['140']=plane(0.,'inner_140mm_top_rail_reference',True)
    return result


def _face(out,points,normal):
    from assembly_geometry import _quad
    points=list(points);a,b,c=points[:3]
    ab=tuple(b[i]-a[i] for i in range(3));ac=tuple(c[i]-a[i] for i in range(3))
    cross=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
    if sum(cross[i]*normal[i] for i in range(3))<0:points.reverse()
    _quad(out,*points)


def _flat_cover(half,bottom,top,rear,end,front,thickness):
    """Connected L plus the observed side apron; no far wall or front deck."""
    xs=(-half,-half+thickness,half);ys=(bottom,top-thickness,top);zs=(rear,end,front)
    solid={(0,j,k) for j in range(2) for k in range(2)}|{(1,1,0)}
    out=[]
    for i,j,k in sorted(solid):
        x0,x1=xs[i:i+2];y0,y1=ys[j:j+2];z0,z1=zs[k:k+2]
        for neighbor,points,normal in (
            ((i-1,j,k),((x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1)),(-1,0,0)),
            ((i+1,j,k),((x1,y0,z0),(x1,y1,z0),(x1,y1,z1),(x1,y0,z1)),(1,0,0)),
            ((i,j-1,k),((x0,y0,z0),(x1,y0,z0),(x1,y0,z1),(x0,y0,z1)),(0,-1,0)),
            ((i,j+1,k),((x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1)),(0,1,0)),
            ((i,j,k-1),((x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0)),(0,0,-1)),
            ((i,j,k+1),((x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)),(0,0,1))):
            if neighbor not in solid:_face(out,points,normal)
    return tuple(out)


def _north_cover(half,bottom,top,rear,end,front,thickness,drop):
    """North's own observed vertical drop and small rounded side transition."""
    inner=-half+thickness;under=top-thickness;low=top-drop;radius=4.
    profile=((end,low+radius),*tuple((end+radius+radius*math.cos(math.pi+i*math.pi/8),
        low+radius+radius*math.sin(math.pi+i*math.pi/8)) for i in range(1,4)),(end+radius,low),(front,low))
    xs=(-half,inner,half);ys=(bottom,low+radius,under,top)
    solid={(0,0),(0,1),(0,2),(1,2)};out=[]
    for i,j in sorted(solid):
        x0,x1=xs[i:i+2];y0,y1=ys[j:j+2]
        _face(out,((x0,y0,rear),(x1,y0,rear),(x1,y1,rear),(x0,y1,rear)),(0,0,-1))
        if (i,j)!=(0,0):_face(out,((x0,y0,end),(x1,y0,end),(x1,y1,end),(x0,y1,end)),(0,0,1))
        for neighbor,points,normal in (
            ((i-1,j),((x0,y0,rear),(x0,y1,rear),(x0,y1,end),(x0,y0,end)),(-1,0,0)),
            ((i+1,j),((x1,y0,rear),(x1,y1,rear),(x1,y1,end),(x1,y0,end)),(1,0,0)),
            ((i,j-1),((x0,y0,rear),(x1,y0,rear),(x1,y0,end),(x0,y0,end)),(0,-1,0)),
            ((i,j+1),((x0,y1,rear),(x1,y1,rear),(x1,y1,end),(x0,y1,end)),(0,1,0))):
            if neighbor not in solid:_face(out,points,normal)
    for (z0,y0),(z1,y1) in zip(profile,profile[1:]):
        for x,n in ((-half,(-1,0,0)),(inner,(1,0,0))):
            _face(out,((x,bottom,z0),(x,bottom,z1),(x,y1,z1),(x,y0,z0)),n)
        _face(out,((-half,y0,z0),(inner,y0,z0),(inner,y1,z1),(-half,y1,z1)),(0,1,0))
        _face(out,((-half,bottom,z0),(inner,bottom,z0),(inner,bottom,z1),(-half,bottom,z1)),(0,-1,0))
    _face(out,((-half,bottom,front),(inner,bottom,front),(inner,low,front),(-half,low,front)),(0,0,1))
    return tuple(out),profile


def _part(case_id,row,identity,label,bounds,removable):
    return dict(id=identity,label=row['label']+' '+label,kind='case_cover',component='case',model_id=case_id,
        mesh_name='psu-shroud',assembly_state='installed',geometry_status='official_photo_reference',
        dimensions_verified=False,positions_verified=False,thickness_verified=False,source_url=row['product'],
        source_urls=(row['product'],row['manual'],row['photo']),factory_removable=removable,
        factory_removal_purpose=('fan_or_radiator_space' if removable else None),
        reference_bounds_world_mm=bounds,display_screen=False,power_sensor_bound=False)


def build(case,dimensions,tone):
    """Return exact supported covers and detached construction metadata.

    Caller defers ``deferred_part_ids`` until finish(), so the documented
    removable inlays cannot prematurely reject an otherwise valid front fan.
    """
    if not isinstance(case,dict) or case.get('id') not in _ROWS:return (),{}
    if (not isinstance(dimensions,(tuple,list)) or len(dimensions)!=3
            or any(type(v) not in (int,float) or not math.isfinite(v) for v in dimensions)):
        return (),{}
    w,h,d=dimensions
    if not (60<=w<=800 and 60<=h<=900 and 150<=d<=900):return (),{}
    from assembly_geometry import Mesh,box
    case_id=case['id'];row=_ROWS[case_id];half=(w-12.)/2;layout=layout_reference(case,dimensions)
    bottom=layout['side_bottom_y_mm'];top=layout['roof_y_mm']
    rear=-(d-12.)/2;front=-rear;end=d*row['roof_end'];thickness=1.2
    bounds=dict(min=(-half,bottom,rear),max=(half,top,front));profile=None
    if case_id==_NORTH:
        # North's own printed7 orthographic build view: the drop is about
        #77.4% of total case depth (rear85/front395/drop325 image pixels).
        # Its unlabelled end is NOT North XL's separate .34D reference.
        vertices,profile=_north_cover(half,bottom,top,rear,end,front,thickness,h*row['drop'])
    else:vertices=_flat_cover(half,bottom,top,rear,end,front,thickness)
    meshes=[Mesh('psu-shroud',vertices,tone,component='case',part_id='case:psu-cover')]
    parts=[_part(case_id,row,'case:psu-cover','固定电源罩',bounds,False)];deferred=[]
    if row['inlays']:
        seam=d*row['inlay_seam']
        for i,(a,b) in enumerate(((end,seam),(seam,front))):
            identity='case:psu-front-inlay:'+str(i);deferred.append(identity)
            # The L side is already one closed solid. Each removable top
            # inlay starts at its inner face, rather than overlapping it.
            x0=-half+thickness;x1=half;bound=dict(min=(x0,top-thickness,a),max=(x1,top,b))
            meshes.append(Mesh('psu-shroud',box(x1-x0,thickness,b-a),tone,
                ((x0+x1)/2,top-thickness/2,(a+b)/2),'case',part_id=identity))
            parts.append(_part(case_id,row,identity,'前顶盖 '+str(i+1),bound,True))
    meta=dict(case_id=case_id,method='official_manual_and_gallery_thin_cover_reference',
        source_urls=(row['product'],row['manual'],row['photo']),manual_printed_pages=row['pages'],
        dimensions_verified=False,positions_verified=False,thickness_verified=False,cad_verified=False,
        thickness_mm=thickness,chamber_is_solid=False,far_side_wall_added=False,
        far_side_boundary='existing_case_right_or_tray',front_bay_open=True,
        ventilation_observed=True,exact_vent_pattern_modeled=False,exact_fasteners_modeled=False,
        selected_component_geometry_used=False,
        normalized_reference=dict(roof_end_depth_fraction=row['roof_end'],front_drop_height_fraction=row.get('drop'),
            inlay_seam_depth_fraction=row.get('inlay_seam'),roof_height_case_height_fraction=.24),
        roof_world_y_mm=top,reference_bounds_world_mm=bounds,relief_profile_world_zy_mm=profile,
        layout_reference=layout,psu_fan_orientation_verified=False,
        parts=parts,removed_parts=[],deferred_part_ids=tuple(deferred),
        assembly_state='awaiting_actual_cooling' if deferred else 'fixed_cover_installed',
        unknown=['factory_thickness','unlabelled_panel_positions','precise_vent_and_fastener_pattern'],
        source_photos_are_private_references=True)
    return tuple(meshes),meta


def _triangle_box_overlap(mesh,low,high):
    """Strict material-surface witness, not the empty L compartment's AABB."""
    vertices=mesh.vertices;position=mesh.position
    if len(vertices)//18>64000:raise ValueError('Front inlay occupancy exceeds bounded reference check')
    if any(max(vertices[k::6])+position[k]<=low[k] or min(vertices[k::6])+position[k]>=high[k] for k in range(3)):
        return None
    for at in range(0,len(vertices),18):
        polygon=[tuple(vertices[at+j+k]+position[k] for k in range(3)) for j in (0,6,12)]
        for axis in range(3):
            for edge,sign in ((low[axis],1.),(high[axis],-1.)):
                result=[]
                for a,b in zip(polygon,polygon[1:]+polygon[:1]):
                    da=sign*(a[axis]-edge)-1e-6;db=sign*(b[axis]-edge)-1e-6
                    if da>=0:result.append(a)
                    if (da<0)!=(db<0):
                        t=da/(da-db);result.append(tuple(a[k]+t*(b[k]-a[k]) for k in range(3)))
                polygon=result
                if not polygon:break
            if not polygon:break
        area=0.
        for j in range(1,len(polygon)-1):
            a,b,c=polygon[0],polygon[j],polygon[j+1]
            ab=tuple(b[k]-a[k] for k in range(3));ac=tuple(c[k]-a[k] for k in range(3))
            area+=math.hypot(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])*.5
        if area>1e-8:return dict(mesh_name=mesh.name,part_id=mesh.part_id,triangle_index=at//18,strict_material_surface_mm2=area)
    return None


def finish(meshes,cooling_meshes,cooling_meta,meta):
    """Install or remove whole documented inlays before final indices/anchors.

    Only an actual built, front-mounted case fan/radiator with a strict
    material witness can remove an inlay. Requested/rejected rows, top parts,
    hoses and flexible wire tails do not establish this assembly state.
    Cooling rows/meshes remain unmodified, including their exact IDs.
    """
    if not isinstance(meta,dict) or meta.get('case_id') not in _ROWS:return meshes,meta
    result=deepcopy(meta);deferred=set(meta.get('deferred_part_ids',()))
    if not deferred:return meshes,result
    parts=cooling_meta.get('parts',()) if isinstance(cooling_meta,dict) else ()
    front_ids={r.get('id') for r in parts if isinstance(r,dict) and r.get('mount')=='front'
        and r.get('kind') in ('case_fan','radiator') and isinstance(r.get('id'),str)}
    actual_ids={m.part_id for m in cooling_meshes if m.vertices}
    front_radiators={r['id'] for r in parts if isinstance(r,dict) and r.get('mount')=='front'
        and r.get('kind')=='radiator' and isinstance(r.get('id'),str) and r['id'] in actual_ids}
    # Radiator fans have explicit ownership rather than their own mount field.
    # A thick inner fan can occupy a second inlay even when the tank does not.
    # Never infer that relationship from a name prefix or physical distance.
    front_ids.update(r['id'] for r in parts if isinstance(r,dict) and r.get('kind')=='radiator_fan'
        and isinstance(r.get('id'),str) and r.get('radiator_part_id') in front_radiators)
    actual=[m for m in cooling_meshes if m.part_id in front_ids and m.vertices
        and not any(s in m.name for s in ('wire','lead','connector','hose','tube'))]
    removed=[]
    for row in result['parts']:
        if row['id'] not in deferred:continue
        bounds=row['reference_bounds_world_mm'];proof=next((p for m in actual
            if (p:=_triangle_box_overlap(m,bounds['min'],bounds['max']))),None)
        if proof:
            removed.append(dict(row,assembly_state='removed_reference',physical_mesh_present=False,
                reason='front_inlay_removed_for_fan_or_radiator_space',removal_basis='actual_built_front_component_material',proof=proof))
    ids={row['id'] for row in removed}
    result['parts']=[row for row in result['parts'] if row['id'] not in ids]
    result['removed_parts']=removed;result['assembly_state']='front_inlay_removed_reference' if removed else 'all_covers_installed'
    return tuple(m for m in meshes if m.part_id not in ids),result
