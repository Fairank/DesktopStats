"""Exact non-Touch Y70 cold-floor structure, not a filled cooling/PSU bay.

HYTE's product and build guide establish the removable lower tray,32mm fan
capacity and separate rear chamber. Unlabelled frame, vent and foot dimensions
are bounded original drawing references, never factory CAD or selected-fit
carving. The existing fan, motherboard and GPU mounting references stay put.
"""
import math

CASE_ID='hyte-y70'
CASE_IDS=(CASE_ID,)
PRODUCT='https://hyte.com/store/y70/cs-hyte-y70-b'
BUILD_GUIDE='https://support.hyte.com/hc/en-us/articles/27797939292436-Build-Guide'
FEATURES='https://support.hyte.com/hc/en-us/articles/27763636224532-Meet-The-Y70'
SOURCES=(PRODUCT,BUILD_GUIDE,FEATURES)
RELATED_MANUAL='https://content.ibuypower.com/hyte/product-page-pdfs/y70-touch-15-language.pdf'
_HORIZONTAL=((1.,0.,0.),(0.,0.,-1.),(0.,1.,0.))


def _valid(case,dimensions):
    return (isinstance(case,dict) and case.get('id')==CASE_ID
        and isinstance(dimensions,(tuple,list)) and len(dimensions)==3
        and all(type(v) in (int,float) and math.isfinite(v) for v in dimensions)
        and 240<=dimensions[0]<=500 and 350<=dimensions[1]<=700 and 350<=dimensions[2]<=700)


def _rect(a,b,c,d):return ((a,c),(b,c),(b,d),(a,d))


def _ccw(poly):
    area=sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(poly,(*poly[1:],poly[0])))
    return tuple(poly) if area>0 else tuple(reversed(poly))


def _transform(vertices,origin,basis):
    out=[]
    for at in range(0,len(vertices),6):
        for offset in (0,3):
            p=vertices[at+offset:at+offset+3]
            out.extend(sum(p[k]*basis[k][axis] for k in range(3))
                +(origin[axis] if offset==0 else 0.) for axis in range(3))
    return tuple(out)


def _plate_xz(poly,holes,y,thickness):
    from assembly_detail import perforated_plate
    local=lambda p:_ccw(tuple((x,-z) for x,z in p))
    vertices=perforated_plate(local(poly),[local(hole) for hole in holes],thickness,clip_walls=True)
    return _transform(vertices,(0.,y,0.),_HORIZONTAL)


def _beam(a,b,width,y0,y1):
    from assembly_geometry import box
    dx,dz=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dz)
    tangent=(dx/length,0.,dz/length);normal=(-dz/length,0.,dx/length)
    return _transform(box(length,y1-y0,width),((a[0]+b[0])/2,(y0+y1)/2,(a[1]+b[1])/2),
        (tangent,(0.,1.,0.),normal))


def layout_reference(case,dimensions):
    if not _valid(case,dimensions):return {}
    w,h,d=map(float,dimensions);divider=w*.10+5.
    center=(-w/2+divider)/2;span=divider+w/2-16.
    def plane(position,normal,up,method,**values):
        return dict(case_id=CASE_ID,position=position,normal=normal,up=up,source=PRODUCT,
            source_urls=SOURCES,method=method,reference_only=True,dimensions_verified=False,
            positions_verified=False,mounting_hole_positions_verified=False,**values)
    return dict(case_id=CASE_ID,source=PRODUCT,source_urls=SOURCES,
        method='non_touch_official_gallery_and_build_guide_reference',reference_only=True,
        positions_verified=False,dimensions_verified=False,manufacturing_cad=False,
        mount_planes=dict(
            bottom=plane((center,-h/2+10.,0.),(0.,-1.,0.),(0.,0.,1.),
                'official_non_touch_cold_floor_architecture_original_plane_reference',span_mm=(span,d-32.),
                source_capacity_count_by_size_mm={'120':3,'140':2},source_max_fan_depth_mm=32.,
                source_capacity_verified=True,source_fan_depth_limit_verified=True,
                related_manual=RELATED_MANUAL,related_manual_pdf_pages=(7,8),
                related_manual_manufacturing_identity_verified=False),
            top=plane((center,h/2-12.,0.),(0.,1.,0.),(0.,0.,1.),
                'observed_shared_frame_unverified',span_mm=(span,d-32.),
                source_capacity_verified=True,shared_frame_dimensions_verified=False),
            side=plane((w*.34,0.,d*.23),(1.,0.,0.),(0.,1.,0.),
                'observed_shared_frame_unverified',stack_direction=(-1.,0.,0.),
                source_capacity_verified=True,shared_frame_dimensions_verified=False)),
        fan_constraints=dict(bottom=dict(case_id=CASE_ID,source_url=PRODUCT,
            max_count_by_size_mm={'120':3,'140':2},max_depth_mm=32.,
            source_capacity_verified=True,positions_verified=False,dimensions_verified=False)),
        # Identical to the existing dual-chamber PSU reference; only the
        # fictitious filled chamber volume is replaced by real thin material.
        psu=dict(basis=((0.,1.,0.),(-1.,0.,0.),(0.,0.,1.)),align_x='right',
            boundary_x_mm=w/2-9.,floor_y_mm=-h/2+12.,rear_z_mm=-d/2+10.),
        source_max_psu_length_mm=235.,psu_fan_orientation_verified=False)


def build(case,dimensions,tone):
    if not _valid(case,dimensions):return (),{}
    from assembly_geometry import Mesh
    from assembly_detail import _clip
    w,h,d=map(float,dimensions);base=-h/2;sheet=1.2
    cut=min(w*.23,d*.18);edge=3.
    outer=((-w/2+edge,-d/2+edge),(w/2-edge,-d/2+edge),(w/2-edge,d/2-edge),
           (-w/2+cut+edge,d/2-edge),(-w/2+edge,d/2-cut-edge))
    reference=layout_reference(case,dimensions);cx=reference['mount_planes']['bottom']['position'][0]
    tray_width=reference['mount_planes']['bottom']['span_mm'][0]-8.
    tray_length=d-46.
    tray_rectangle=_rect(cx-tray_width/2,cx+tray_width/2,-tray_length/2,tray_length/2)
    tray=tray_rectangle
    for a,b in zip(outer,(*outer[1:],outer[0])):tray=_clip(tray,a,b,True)
    # The large opening is fixed to the chassis, not whichever fan is picked.
    # A universal bracket has long lands for both105 and124.5mm pitch rows;
    # three longitudinal clear regions are explicitly sampled, not exact vents.
    slots=tuple(_rect(cx+a,cx+b,-d/2+38.,d/2-38.) for a,b in ((-81.,-66.),(-44.,44.),(66.,81.)))
    pan_y=base+8.4;pan_top=base+9.;pan_bottom=base+7.8
    frame=list(_plate_xz(outer,(tray_rectangle,),pan_y,sheet))
    for a,b in zip(outer,(*outer[1:],outer[0])):frame.extend(_beam(a,b,sheet,pan_top,base+16.))
    meshes=[];parts=[]
    def add(identity,label,name,vertices,role):
        if not vertices:raise ValueError('Observed Y70 structure cannot silently disappear')
        meshes.append(Mesh(name,tuple(vertices),tuple(tone),component='case',part_id=identity))
        parts.append(dict(id=identity,label=label,kind='case_structure',component='case',model_id=CASE_ID,
            assembly_state='installed',geometry_status='official_photo_reference',observed_role=role,
            source_url=PRODUCT,source_urls=SOURCES,dimensions_verified=False,positions_verified=False,
            exact_manufacturing_pattern_verified=False,display_screen=False,power_sensor_bound=False))
    add('case:base-frame','底部开放框架','case-y70-base-frame',frame,'perimeter_and_open_rear_psu_floor')
    add('case:bottom-fan-tray','底部可拆风扇托盘','case-y70-bottom-fan-tray',
        _plate_xz(tray,slots,pan_y,sheet),'removable_universal_cold_floor_tray')
    # Perimeter support samples follow the chamfered shell, never the old
    # inward0.34W/0.34D cube positions that intersected the intake fan frame.
    feet=[((-w/2+14.,-d/2+7.),(-w/2+14.,-d/2+37.)),
          ((w/2-14.,-d/2+7.),(w/2-14.,-d/2+37.)),
          ((w/2-14.,d/2-37.),(w/2-14.,d/2-7.))]
    unit=1/math.sqrt(2);middle=(-w/2+cut*.78+9*unit,d/2-cut*.22-9*unit)
    feet.append(((middle[0]-15*unit,middle[1]-15*unit),(middle[0]+15*unit,middle[1]+15*unit)))
    for index,(a,b) in enumerate(feet):
        add('case:base-support:'+str(index),'外缘支脚 '+str(index+1),'case-y70-perimeter-foot',
            _beam(a,b,10.,base,pan_bottom),'unmeasured_perimeter_support_sample')
    meta=dict(case_id=CASE_ID,method='non_touch_official_cold_floor_material_reference',source_urls=SOURCES,
        source_variant='non_touch',geometry_status='official_photo_reference',layout_reference=reference,
        parts=parts,removed_parts=[],replaces_case_bottom=True,replaces_case_feet=True,
        replaces_rear_chamber_shroud=True,replaced_generic_mesh_names=('case-bottom','case-foot','rear-chamber-shroud'),
        dimensions_verified=False,positions_verified=False,thickness_verified=False,cad_verified=False,
        manufacturing_cad=False,chamber_is_solid=False,psu_chamber_is_solid=False,selected_component_geometry_used=False,
        horizontal_psu_cover_present=False,exact_vent_pattern_modeled=False,exact_foot_count_verified=False,
        source_bottom_fan_capacity_verified=True,source_max_bottom_fan_depth_mm=32.,
        reference_slot_samples=3,reference_support_samples=4,thickness_mm=sheet,
        bottom_pan_top_world_y_mm=pan_top,bottom_pan_bottom_world_y_mm=pan_bottom,
        tray_polygon_xz_reference=tuple(tray),tray_clear_regions_xz_reference=slots,
        reference_drawing_gap_mm=1.,drawing_gap_verified=False,
        retained_existing_structure=('case-cold-floor-deck','rear-chamber-divider','case-back','case-right',
                                     'case-depth-rail','case-width-rail'),
        rear_chamber_role='Open PSU space above thin base, bounded by retained walls/divider, never a filled box.',
        unverified_details='Tray/foot coordinates, bends, fastenings and vent pattern are original bounded references, not labelled manufacturing dimensions.')
    return tuple(meshes),meta
