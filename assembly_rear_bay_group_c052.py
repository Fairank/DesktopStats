"""Seven exact source-observed bays; fixed original material, not retail CAD.

All internal datums, vent samples and frame thicknesses are drawing references.
The selected PSU, fan or motherboard never carves these structural parts.
HS420 uses its own hybrid lower bay rather than a full-height side divider.
"""
import math

CASE_IDS=('nzxt-h9-flow-2023','jonsbo-tk2-black','deepcool-ch780','corsair-2500x',
          'lian-li-o11-vision-compact','be-quiet-light-base-600-lx','havn-hs-420')
VERTICAL=((0.,1.,0.),(-1.,0.,0.),(0.,0.,1.))
HORIZONTAL=((1.,0.,0.),(0.,0.,-1.),(0.,1.,0.))
_SOURCES={
 'nzxt-h9-flow-2023':('https://support.nzxt.com/hc/en-us/articles/37840024628891-H9-2023-Series-Specs',
  'https://cdn-g.nzxt.com/dl/1673509545-case_h9-flow_digital-manual-en-220929.pdf'),
 'jonsbo-tk2-black':('https://www.jonsbo.com/en/products/TK2Black.html',
  'https://www.jonsbo.com/Upfiles/down/TK-2%20Installation%20Manual.pdf'),
 'deepcool-ch780':('https://www.deepcool.com/products/Cases/CH780-Panoramic-Tempered-Glass-ATX-Case/2023/17534.shtml',
  'https://www.deepcool.com/download/pdf/CH780.pdf'),
 'corsair-2500x':('https://www.corsair.com/us/en/explorer/diy-builder/cases/corsair-2500-series/',
  'https://www.corsair.com/us/en/p/pc-cases/cc-9011265-ww/2500x-mid-tower-dual-chamber-pc-case-black-cc-9011265-ww'),
 'lian-li-o11-vision-compact':('https://lian-li.com/product/o11-vision-compact/',
  'https://drive.google.com/file/d/1ZDUXWT6n6VS6G5fNPQ-tn4Y_WMbrP5af/view?usp=sharing'),
 'be-quiet-light-base-600-lx':('https://www.bequiet.com/en/case/5294',
  'https://www.bequiet.com/admin/ImageServer.php?ID=62642a57793%40be-quiet.net&download=true&force=true&lang=2&omitPreview=true'),
 'havn-hs-420':('https://havn.global/products/hs-420',
  'https://havn.global/cdn/shop/files/HS_420__HS_420_VGPU_Manual.pdf?v=9458698656055923918'),
}
_PAGES={'nzxt-h9-flow-2023':(20,),'jonsbo-tk2-black':(2,),
 'deepcool-ch780':(36,37),'corsair-2500x':(),
 'lian-li-o11-vision-compact':(5,),'be-quiet-light-base-600-lx':(34,),
 'havn-hs-420':(8,20,24)}


def _valid(case,dimensions):
    return (isinstance(case,dict) and case.get('id') in CASE_IDS
        and isinstance(dimensions,(tuple,list)) and len(dimensions)==3
        and all(type(v) in (int,float) and math.isfinite(v) for v in dimensions)
        and 220<=dimensions[0]<=400 and 350<=dimensions[1]<=650 and 350<=dimensions[2]<=650)


def layout_reference(case,dimensions):
    if not _valid(case,dimensions):return {}
    identity=case['id'];w,h,d=map(float,dimensions);source=_SOURCES[identity]
    psu=dict(basis=VERTICAL,align_x='right',boundary_x_mm=w/2-9.,rear_z_mm=-d/2+10.)
    if identity=='nzxt-h9-flow-2023':psu['ceiling_y_mm']=h/2-32.
    else:
        psu['floor_y_mm']=(-h/2+24. if identity=='jonsbo-tk2-black' else
            -h/2+64. if identity=='deepcool-ch780' else
            -h/2+28. if identity=='corsair-2500x' else
            -.15*h+2.2 if identity=='lian-li-o11-vision-compact' else
            (20./2-.14*(h-20.)+2.2) if identity=='be-quiet-light-base-600-lx' else -h/2+12.)
    result=dict(case_id=identity,source=source[0],source_urls=source,source_manual_pdf_pages=_PAGES[identity],
        reference_only=True,positions_verified=False,dimensions_verified=False,
        psu=psu,psu_orientation_source='manufacturer_installation_portrait_side_inlet',
        psu_fan_orientation_verified=identity in ('nzxt-h9-flow-2023','corsair-2500x'),
        source_rear_bracket_projection_mm=15. if identity=='lian-li-o11-vision-compact' else None,
        source_rear_bracket_projection_applied_to_psu_pose=False,
        source_psu_length_mm={'nzxt-h9-flow-2023':200.,'jonsbo-tk2-black':220.,
            'deepcool-ch780':180.,'corsair-2500x':225.,'be-quiet-light-base-600-lx':200.,
            'havn-hs-420':220.}.get(identity),
        source_limit_is_whole_fit_certificate=False)
    result['source_psu_limit_operator']='less_than' if identity=='be-quiet-light-base-600-lx' else 'at_most'
    result['air_cooler_constraints']=dict(case_id=identity,source_url=source[0],
        max_height_mm={'nzxt-h9-flow-2023':165.,'jonsbo-tk2-black':155.,'deepcool-ch780':132.,
            'corsair-2500x':180.,'lian-li-o11-vision-compact':167.,
            'be-quiet-light-base-600-lx':170.,'havn-hs-420':185.}[identity])
    if identity=='jonsbo-tk2-black':
        conflict=dict(field='air_cooler_height_mm',product=165.,manual=155.,resolved=False)
        result['source_conflicts']=[conflict]
        result['air_cooler_constraints'].update(source_conflict=True,manufacturer_values_mm=(155.,165.),
            effective_limit_policy='lower_published_value_until_resolved_not_product_incompatibility_proof')
    if identity=='be-quiet-light-base-600-lx':
        result.update(source_body_height_mm=h-20.,source_feet_height_mm=20.,
            body_center_y_mm=10.,holder_reference_uses_body_height=True)
    if identity=='lian-li-o11-vision-compact':
        result['source_conflicts']=[dict(field='psu_length_mm',product_exclusive=220.,manual_inclusive=200.,
            resolved=False,add_projection_to_clearance=False)]
    if identity=='corsair-2500x':
        result['source_conflicts']=[dict(field='case_depth_mm',catalog_product=469.,series_guide=479.,
            resolved=False,selected_catalog_dimensions_preserved=True)]
    # A hybrid tray ends above the low PSU. That lower bay is narrower than
    # the upper motherboard volume; do not force either into a full-height wall.
    if identity=='havn-hs-420':
        result.update(board_x_mm=w*.23,board_y_mm=h*.08,rear_divider_bottom_y_mm=-h*.20,
            board_positions_verified=False,hybrid_lower_bay_reference=True)
    elif identity=='deepcool-ch780':
        # The manual's raised motherboard tray ends above the open lower
        # intake. Retain a fixed reference edge; a full-height generic sheet
        # would bisect the documented broad bottom fan bank. This datum is
        # unmeasured and is never derived from a selected fan or PSU.
        result.update(board_x_mm=w*.05,board_positions_verified=False,
            rear_divider_bottom_y_mm=-h/2+64.,
            raised_tray_lower_edge_reference=True)
    divider=result.get('board_x_mm',w*.10)+5.
    x0=-w/2+13.;x1=(w/2-96.) if identity=='havn-hs-420' else divider-9.
    if identity=='deepcool-ch780':
        # The source supports a broad lower intake below the raised PSU
        # bracket, including200mm frames. It is not the upper tray's width.
        x0,x1=-w/2+12.,w/2-12.
    floor_top=-h/2+(9. if identity=='havn-hs-420' else 21.2 if identity=='be-quiet-light-base-600-lx' else 19.)
    result['mount_planes']=dict(bottom=dict(position=((x0+x1)/2,floor_top+1.25,0.),
        normal=(0.,-1.,0.),up=(0.,0.,-1.) if identity=='havn-hs-420' else (0.,0.,1.),span_mm=(x1-x0,d-36.),
        source=source[0],method='official_architecture_fixed_original_intake_reference',
        reference_only=True,positions_verified=False,dimensions_verified=False))
    if identity=='havn-hs-420':
        result['mount_planes']['bottom'].update(
            installation_roll_reference_degrees=180.,installation_roll_manufacturer_verified=False,
            tail_direction_role='towards_open_main_chamber_not_psu_side_skin')
    result.update(lower_floor_top_y_mm=floor_top,main_floor_xz_reference=(x0,x1,-d/2+22.,d/2-22.))
    return result


def build(case,dimensions,tone):
    if not _valid(case,dimensions):return (),{}
    from assembly_geometry import Mesh,box
    from assembly_rear_bay_group_a052 import _plate,_rect,_transform
    identity=case['id'];w,h,d=map(float,dimensions);layout=layout_reference(case,dimensions)
    psu=layout['psu'];right=psu['boundary_x_mm'];left=right-86.
    low=psu.get('floor_y_mm',psu.get('ceiling_y_mm',0.)-150.);high=low+150.;rear=psu['rear_z_mm']
    meshes=[];parts=[];sheet=1.2
    def add(key,label,vertices,role,kind='case_structure'):
        if not vertices:raise ValueError('Source-observed case material must not vanish')
        meshes.append(Mesh('case-rear-source-'+key,tuple(vertices),tuple(tone),component='case',part_id='case:'+key))
        parts.append(dict(id='case:'+key,label=label,kind=kind,component='case',model_id=identity,
            assembly_state='installed',geometry_status='official_photo_reference',observed_role=role,
            source_urls=_SOURCES[identity],source_url=_SOURCES[identity][0],
            source_manual_pdf_pages=_PAGES[identity],dimensions_verified=False,positions_verified=False,
            exact_fasteners_modeled=False,exact_vent_pattern_verified=False))
    def boxes(rows):
        return tuple(v for size,position in rows for v in _transform(box(*size),position,
            ((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))))
    # Retain the case's existing corner footprint as a reference. The source
    # does not give a manufacturing bend radius for either curved glass model.
    cut=min(w*.23,d*.18) if 'curved_front_glass' in case.get('features',()) else 0.
    outer=((-w/2+4.,-d/2+4.),(w/2-4.,-d/2+4.),(w/2-4.,d/2-4.),
        (-w/2+cut+4.,d/2-4.),(-w/2+4.,d/2-cut-4.)) if cut else _rect(-w/2+4.,w/2-4.,-d/2+4.,d/2-4.)
    x0,x1,z0,z1=layout['main_floor_xz_reference'];cx=(x0+x1)/2;span=x1-x0
    holes=[_rect(cx+a*span,cx+b*span,z0,z1) for a,b in ((-.46,-.34),(-.27,.27),(.34,.46))]
    from assembly_detail import _clip
    clipped=[]
    for hole in holes:
        for a,b in zip(outer,(*outer[1:],outer[0])):hole=_clip(hole,a,b,True)
        if hole:clipped.append(tuple(hole))
    local=lambda poly:tuple(reversed(tuple((x,-z) for x,z in poly)))
    floor=_plate(local(outer),[local(p) for p in clipped],
        (0.,layout['lower_floor_top_y_mm']-sheet/2,0.),HORIZONTAL)
    add('open-floor','开放底部承托板',floor,'fixed_perforated_floor_reference')
    if identity in ('havn-hs-420','be-quiet-light-base-600-lx'):
        foot_height=7.8 if identity=='havn-hs-420' else 20.
        supports=list(boxes([((10.,foot_height,28.),(x,-h/2+foot_height/2,z))
            for x in (-w/2+14.,w/2-14.) for z in (-d/2+22.,d/2-22.)
            if identity!='havn-hs-420' or not (x<0 and z>0)]))
        if identity=='havn-hs-420':
            # Follow the retained clipped corner. A rectangular foot at the
            # old interior corner sits outside this reference floor outline.
            unit=math.sqrt(.5);cx=-w/2+cut/2+4.+9.*unit;cz=d/2-cut/2-4.-9.*unit
            supports.extend(_transform(box(28.,foot_height,10.),(cx,-h/2+foot_height/2,cz),
                ((unit,0.,unit),(0.,1.,0.),(-unit,0.,unit))))
        add('base-support-samples','外缘底座参考支承',supports,
            'unmeasured_perimeter_support_samples_not_factory_foot_count')
    add('psu-rear-frame','独立电源后框',_plate(_rect(left-3.5,right+3.5,low-5.,high+5.),
        [_rect(left-1.5,right+1.5,low-2.,high+2.)],(0.,0.,rear-1.5),
        ((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))),'portrait_removable_mount_frame_reference')
    add('psu-bearing-lands','独立电源承托',boxes([((5.,1.2,112.),(x,low-1.2,rear+62.))
        for x in (left+8.,right-8.)]),'independent_psu_holder_or_bearing_reference')
    if identity=='havn-hs-420':
        # The known low PSU compartment has a separate thin cover below the
        # motherboard. Its dimensions are fixed, not carved around a PSU.
        end=rear+240.;top=-h*.20
        side=_plate(_rect(-end,-rear,-h/2+10.,top),(),(left-1.2,0.,0.),
            ((0.,0.,-1.),(0.,1.,0.),(1.,0.,0.)))
        roof=_plate(_rect(left-1.8,right+2.,-end,-rear),(),(0.,top-.6,0.),HORIZONTAL)
        add('psu-cover','下部独立电源薄罩',(*side,*roof),'hybrid_lower_psu_skin_reference','case_cover')
        # Retained visibility consumers identify covers by this stable name.
        meshes[-1]=Mesh('psu-shroud',meshes[-1].vertices,meshes[-1].color,
            component='case',part_id=meshes[-1].part_id)
    else:
        if identity in ('nzxt-h9-flow-2023','lian-li-o11-vision-compact','be-quiet-light-base-600-lx'):
            a,b=-h/2+30.,min(low-18.,-h*.17)
        else:a,b=max(high+20.,h*.05),h*.34
        if b>a+10.:
            z0,z1=rear+26.,rear+132.;lx,rx=left+3.,right-3.;rows=[]
            for y in (a,b):
                for x in (lx,rx):rows.append(((1.2,1.2,z1-z0),(x,y,(z0+z1)/2)))
                for z in (z0,z1):rows.append(((rx-lx,1.2,1.2),((lx+rx)/2,y,z)))
            for x in (lx,rx):
                for z in (z0,z1):rows.append(((1.2,b-a,1.2),(x,(a+b)/2,z)))
            add('storage-frame','独立空置硬盘支架',boxes(rows),'empty_storage_frame_reference_no_drives')
    return tuple(meshes),dict(case_id=identity,source_urls=_SOURCES[identity],parts=parts,removed_parts=[],
        method='exact_manual_portrait_psu_and_fixed_thin_bay_reference',layout_reference=layout,
        replaces_rear_chamber_shroud=True,replaces_case_bottom=True,
        replaces_case_feet=identity in ('havn-hs-420','be-quiet-light-base-600-lx'),
        chamber_is_solid=False,psu_chamber_is_solid=False,selected_component_geometry_used=False,
        reference_only=True,positions_verified=False,dimensions_verified=False,thickness_verified=False,
        cad_verified=False,source_internal_datums_measured=False,source_curve_radius_verified=False,
        source_conflicts=layout.get('source_conflicts',[]),sheet_thickness_mm=sheet,
        actual_rear_projection_modeled=False,actual_external_rear_apertures_modeled=False)
