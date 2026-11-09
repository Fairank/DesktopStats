"""Five exact dual-chamber rear bays, drawn from official open-case sources.

These are bounded original thin-material references, not manufacturer CAD.
PSU mounts, vent samples and storage frames remain fixed to each chassis;
neither selected parts nor a desired collision result can carve the model.
The NZXT record is the 2023 H6, whose PSU is in the upper rear chamber.
"""
import math

CASE_IDS=('lian-li-o11d-evo-rgb','nzxt-h6-flow-2023','corsair-6500x',
          'hyte-y60','asus-tuf-gt502')
_VERTICAL=((0.,1.,0.),(-1.,0.,0.),(0.,0.,1.))
_HORIZONTAL=((1.,0.,0.),(0.,0.,-1.),(0.,1.,0.))
_SIDE=((0.,0.,1.),(0.,1.,0.),(-1.,0.,0.))
_SOURCES={
    'lian-li-o11d-evo-rgb':(
        'https://lian-li.com/product/o11d-evo-rgb/',
        'https://lian-li.com/wp-content/uploads/2023/12/O11D-EVO-RBG_35.webp'),
    'nzxt-h6-flow-2023':(
        'https://support.nzxt.com/hc/en-us/articles/40183529624347-H6-Flow-2023-Specs',
        'https://support.nzxt.com/hc/en-us/articles/19797361854747-Building-in-the-NZXT-H6-Series',
        'https://cdn-g.nzxt.com/dl/1698993634-h6-flow_digital-manual_231027_v2-pdf.pdf'),
    'corsair-6500x':(
        'https://www.corsair.com/ca/en/p/pc-cases/cc-9011258-ww/6500x-mid-tower-dual-chamber-pc-case-white-cc-9011258-ww',
        'https://www.corsair.com/us/en/explorer/diy-builder/cases/corsair-6500-series/'),
    'hyte-y60':('https://hyte.com/store/y60/cs-hyte-y60-b',
        'https://content.ibuypower.com/hyte/product-page-pdfs/y60.pdf'),
    'asus-tuf-gt502':(
        'https://www.asus.com/motherboards-components/cases/tuf-gaming/tuf-gaming-gt502/',
        'https://www.asus.com/motherboards-components/cases/tuf-gaming/tuf-gaming-gt502/techspec/',
        'https://dlcdnets.asus.com/pub/ASUS/ODD/DC/GT502/Q27042_TUF_Gaming_GT502_A5_WW_UM_WEB.pdf'),
}
_LOWER_FLOOR_REFERENCE={'lian-li-o11d-evo-rgb':35.,'corsair-6500x':64.,
                        'hyte-y60':28.,'asus-tuf-gt502':24.}
_BOTTOM_CAPACITY={'lian-li-o11d-evo-rgb':{'120':3,'140':3},
                  'nzxt-h6-flow-2023':{'140':2},'corsair-6500x':{'120':3,'140':3},
                  'hyte-y60':{'120':2,'140':2},'asus-tuf-gt502':{'120':3}}


def _valid(case,dimensions):
    return (isinstance(case,dict) and case.get('id') in CASE_IDS
        and isinstance(dimensions,(tuple,list)) and len(dimensions)==3
        and all(type(v) in (int,float) and math.isfinite(v) for v in dimensions)
        and 250<=dimensions[0]<=400 and 350<=dimensions[1]<=600 and 350<=dimensions[2]<=650)


def _rect(a,b,c,d):return ((a,c),(b,c),(b,d),(a,d))


def _transform(vertices,origin,basis):
    out=[]
    for at in range(0,len(vertices),6):
        for offset in (0,3):
            p=vertices[at+offset:at+offset+3]
            out.extend(sum(p[k]*basis[k][axis] for k in range(3))
                +(origin[axis] if offset==0 else 0.) for axis in range(3))
    return tuple(out)


def _plate(poly,holes,origin,basis,thickness=1.2):
    from assembly_detail import perforated_plate
    return _transform(perforated_plate(poly,holes,thickness,clip_walls=True),origin,basis)


def _floor_shape(case,dimensions):
    w,_,d=dimensions;edge=4.
    if case['id']=='hyte-y60':
        cut=min(w*.23,d*.18)
        return ((-w/2+edge,-d/2+edge),(w/2-edge,-d/2+edge),(w/2-edge,d/2-edge),
                (-w/2+cut+edge,d/2-edge),(-w/2+edge,d/2-cut-edge))
    return _rect(-w/2+edge,w/2-edge,-d/2+edge,d/2-edge)


def _floor(case,dimensions):
    w,h,d=dimensions;divider=w*.10+5.;x0=-w/2+13.;x1=divider-9.
    # Three long sampled openings describe a universal perforated intake deck.
    # They are deliberately not an assertion about the manufacturer's vent grid.
    cx=(x0+x1)/2;width=x1-x0;holes=[]
    for a,b in ((-.46,-.34),(-.27,.27),(.34,.46)):
        holes.append(_rect(cx+a*width,cx+b*width,-d/2+33.,d/2-33.))
    # In Y60 the front corner follows the actual chamfer. Clip every reference
    # opening to that same fixed outline instead of cutting a floating rectangle.
    outer=_floor_shape(case,dimensions)
    from assembly_detail import _clip
    clipped=[]
    for hole in holes:
        for a,b in zip(outer,(*outer[1:],outer[0])):hole=_clip(hole,a,b,True)
        if hole:clipped.append(tuple(hole))
    local=lambda poly:tuple(reversed(tuple((x,-z) for x,z in poly)))
    return _plate(local(outer),[local(p) for p in clipped],(0.,-h/2+18.4,0.),_HORIZONTAL),tuple(clipped)


def layout_reference(case,dimensions):
    """Fixed chassis datums; real selected PSU envelope is applied by the host."""
    if not _valid(case,dimensions):return {}
    identity=case['id'];w,h,d=map(float,dimensions);sources=_SOURCES[identity]
    placement=dict(basis=_VERTICAL,align_x='right',boundary_x_mm=w/2-10.,rear_z_mm=-d/2+10.)
    if identity=='nzxt-h6-flow-2023':placement['ceiling_y_mm']=h/2-18.
    else:placement['floor_y_mm']=-h/2+_LOWER_FLOOR_REFERENCE[identity]
    x0=-w/2+13.;x1=w*.10-4.;span=x1-x0
    plane=dict(case_id=identity,position=((x0+x1)/2,-h/2+20.25,0.),
        normal=(0.,-1.,0.),up=(0.,0.,1.),span_mm=(span,d-36.),source=sources[0],source_urls=sources,
        method='official_intake_architecture_fixed_original_drawing_reference',reference_only=True,
        positions_verified=False,dimensions_verified=False,mounting_hole_positions_verified=False,
        source_capacity_verified=identity in _BOTTOM_CAPACITY)
    if identity in _BOTTOM_CAPACITY:plane['source_capacity_count_by_size_mm']=dict(_BOTTOM_CAPACITY[identity])
    planes=dict(bottom=plane)
    if identity=='asus-tuf-gt502':
        # The exact manual's printed35/36 shows the top bank in the main
        # chamber. The generic world-X0 row crosses the motherboard tray.
        # This fixed drawing datum shares the lower main-chamber width;
        # neither the tray nor the fan is cut or rescaled for a selection.
        planes['top']=dict(plane,position=((x0+x1)/2,h/2-6.,0.),
            normal=(0.,1.,0.),source_capacity_count_by_size_mm={'120':3,'140':2},
            source_manual_pdf_pages=(37,38),source_capacity_verified=True)
    return dict(case_id=identity,source=sources[0],source_urls=sources,
        method='official_exact_variant_open_rear_chamber_reference',reference_only=True,
        dimensions_verified=False,positions_verified=False,manufacturing_cad=False,
        board_datum_changed=False,psu=placement,mount_planes=planes,
        psu_orientation='portrait_side_inlet_outward_reference',psu_portrait_orientation_source_verified=True,
        psu_fan_orientation_verified=identity!='lian-li-o11d-evo-rgb',
        psu_bay='upper_rear' if identity=='nzxt-h6-flow-2023' else 'lower_rear',
        mounting_position_accuracy='unlabelled_photo_reference',
        source_max_psu_length_mm={'lian-li-o11d-evo-rgb':220.,'nzxt-h6-flow-2023':200.,
            'corsair-6500x':225.,'hyte-y60':235.,'asus-tuf-gt502':200.}[identity],
        source_psu_limit_operator='less_than' if identity=='lian-li-o11d-evo-rgb' else 'at_most',
        source_rear_bracket_projection_mm=15. if identity=='lian-li-o11d-evo-rgb' else None,
        source_rear_bracket_projection_applied_to_psu_pose=False)


def build(case,dimensions,tone):
    if not _valid(case,dimensions):return (),{}
    from assembly_geometry import Mesh,box
    identity=case['id'];w,h,d=map(float,dimensions);sources=_SOURCES[identity]
    layout=layout_reference(case,dimensions);mount=layout['psu'];sheet=1.2;meshes=[];parts=[]
    # Standard ATX rear interface dimensions locate a reference mounting frame.
    # The frame is fixed even when a different selected PSU needs an adapter.
    right=mount['boundary_x_mm'];left=right-86.;cx=(left+right)/2
    low=mount.get('floor_y_mm',mount.get('ceiling_y_mm',0.)-150.);high=low+150.
    rear=mount['rear_z_mm']
    def add(part,label,vertices,role,**facts):
        if not vertices:raise ValueError('Exact rear bay material cannot silently disappear')
        name='case-rear-bay-'+part
        part_id='case:'+part
        meshes.append(Mesh(name,tuple(vertices),tuple(tone),component='case',part_id=part_id))
        parts.append(dict(id=part_id,label=label,kind='case_structure',component='case',model_id=identity,
            assembly_state='installed',geometry_status='official_photo_reference',observed_role=role,
            source_url=sources[0],source_urls=sources,dimensions_verified=False,positions_verified=False,
            manufacturing_cad=False,exact_fasteners_modeled=False,**facts))
    def boxes(rows):
        values=[]
        for size,position in rows:values.extend(_transform(box(*size),position,((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))))
        return tuple(values)
    floor,openings=_floor(case,dimensions)
    add('open-floor','开放底部托盘',floor,'perforated_floor_with_fixed_sampled_intake_openings',
        exact_vent_pattern_verified=False)
    # A thin pierced mounting ring, not a solid prism through the PSU volume.
    frame_outer=_rect(left-3.5,right+3.5,low-5.,high+5.)
    aperture=_rect(left-1.5,right+1.5,low-2.,high+2.)
    add('psu-rear-frame','电源后部安装框',
        _plate(frame_outer,[aperture],(0.,0.,rear-1.5),((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))),
        'removable_rear_psu_mounting_frame' if identity=='lian-li-o11d-evo-rgb' else 'rear_psu_mounting_flange',
        removable_reference=identity=='lian-li-o11d-evo-rgb')
    # Short bearing lands sit below the ATX interface; their exact width,
    # depth and bend profile are unlabelled observations, not measured facts.
    rails=boxes([((5.,1.2,112.),(x,low-1.2,rear+62.)) for x in (left+8.,right-8.)])
    add('psu-bearing-lands','电源承托轨',rails,'short_reference_bearing_lands_below_psu')
    # Storage hardware is kept as empty thin material, not installed drives.
    if identity=='nzxt-h6-flow-2023':cage=(-h/2+35.,-h/2+125.,rear+30.,rear+135.)
    elif identity=='corsair-6500x':cage=(h*.11,h*.37,rear+24.,rear+140.)
    elif identity=='lian-li-o11d-evo-rgb':cage=(h*.05,h*.29,rear+24.,rear+136.)
    elif identity=='hyte-y60':cage=(h*.13,h*.29,rear+22.,rear+105.)
    else:cage=None
    if cage:
        a,b,z0,z1=cage;lx=left+3.;rx=right-3.;rows=[]
        for y in (a,b):
            for x in (lx,rx):rows.append(((1.2,1.2,z1-z0),(x,y,(z0+z1)/2)))
            for z in (z0,z1):rows.append(((rx-lx-1.2,1.2,1.2),((lx+rx)/2,y,z)))
        for x in (lx,rx):
            for z in (z0,z1):rows.append(((1.2,b-a-1.2,1.2),(x,(a+b)/2,z)))
        add('storage-frame','空置硬盘支架',boxes(rows),
            'lower_rear_removable_storage_cage' if identity=='nzxt-h6-flow-2023' else
            'independent_upper_storage_sled_frame' if identity=='hyte-y60' else 'independent_upper_empty_drive_cage',
            drive_devices_installed=False,exact_storage_revision_verified=False)
    else:
        # GT502's upper multifunction bracket is separate from the lower PSU.
        z0,z1=-d/2+26.,d/2-26.;y0,y1=h*.13,h*.39
        holes=[_rect(z0+8.+i*(z1-z0-16.)/3,z0-4.+(i+1)*(z1-z0-16.)/3,y0+8.,y1-8.)
               for i in range(3)]
        add('rear-hybrid-bracket','后舱多用途安装架',
            _plate(_rect(z0,z1,y0,y1),holes,(w/2-7.,0.,0.),_SIDE),
            'independent_upper_360_radiator_fan_or_storage_bracket',source_capacity_mm=360.,
            reference_opening_samples=3,installed_accessories=False)
    meta=dict(case_id=identity,source_urls=sources,geometry_status='official_photo_reference',
        layout_reference=layout,parts=parts,removed_parts=[],replaces_rear_chamber_shroud=True,
        replaces_case_bottom=True,replaced_generic_mesh_names=('rear-chamber-shroud','case-bottom'),
        dimensions_verified=False,positions_verified=False,thickness_verified=False,cad_verified=False,
        chamber_is_solid=False,psu_chamber_is_solid=False,selected_component_geometry_used=False,
        psu_bay=layout['psu_bay'],source_variant={'lian-li-o11d-evo-rgb':'normal_mode_evo_rgb',
            'nzxt-h6-flow-2023':'2023_231027_v2','corsair-6500x':'6500x_standard_atx',
            'hyte-y60':'y60_non_y70','asus-tuf-gt502':'original_non_horizon'}[identity],
        thickness_mm=sheet,bottom_pan_top_world_y_mm=-h/2+19.,
        source_manual_pdf_pages={'nzxt-h6-flow-2023':(2,),'hyte-y60':(2,),
            'asus-tuf-gt502':(9,)}.get(identity,()),
        intake_openings_xz_reference=openings,exact_vent_pattern_modeled=False,
        original_board_divider_preserved=True,psu_reference_bounds_mm=((left,low,rear),(right,high,rear+160.)),
        retained_existing_structure=('rear-chamber-divider','case-back','case-right','case-upright',
            'case-depth-rail','case-width-rail','case-foot'),
        pending_details=('Unlabelled support, vent, cage and mounting coordinates are original photo references; '
            'factory tolerances, reversible configurations, alternative PSU adapters and storage revisions are not verified.'),
        new_clocks=0,new_pollers=0)
    return tuple(meshes),meta
