"""Six exact cases' observed covers/lower supports, never filled compartments.

Manufacturer photographs/manual diagrams establish the kind of material and
open bays. Unlabelled coordinates, thicknesses and vent samples below are fixed
original references, not factory CAD or manufacturing compatibility evidence.
No selected fan/radiator/PSU, current motherboard or desired clearance is input.
"""
import math


_HAF='cooler-master-haf-700-evo'
_SHADOW='be-quiet-shadow-base-800-fx'
_TUF='asus-tuf-gt302-argb'
_G500='phanteks-eclipse-g500a-drgb'
_DUBILI='inwin-dubili'
_FRAME='corsair-frame-4000d'
CASE_IDS=(_HAF,_SHADOW,_TUF,_G500,_DUBILI,_FRAME)
_ROOF_FRACTIONS={_SHADOW:.28,_TUF:.275,_G500:.28,_FRAME:.265}
_SOURCES={
 _HAF:('https://www.coolermaster.com/en-us/products/haf-700-evo.html',
  'https://www.coolermaster.com/dw/image/v2/BMJD_PRD/on/demandware.static/-/Library-Sites-coolermaster-global/default/dw378bf370/f/281110/1175x1120/6fff8bf480/d0049441574b45154eb0bba97c8b4d41.webp?sfrm=png&sw=768'),
 _SHADOW:('https://www.bequiet.com/en/case/4483',
  'https://www.bequiet.com/admin/ImageServer.php?ID=538e7a49011%40be-quiet.net&download=true&force=true&lang=2&omitPreview=true'),
 _TUF:('https://www.asus.com/us/motherboards-components/cases/tuf-gaming/tuf-gaming-gt302-argb/',
  'https://dlcdnwebimgs.asus.com/files/media/cfe7c130-c723-4bb5-a9bd-6ec4ba79af7a/v1/img/components/atx-case.png',
  'https://dlcdnets.asus.com/pub/ASUS/ODD/DC/GT302/GT302_R2R_Manual.pdf',
  'https://dlcdnets.asus.com/pub/ASUS/ODD/DC/GT302/Q27043_TUF_Gaming_GT302_ARGB_WW_UM_WEB.pdf'),
 _G500:('https://phanteks.com/product/eclipse-g500a-drgb-black/',
  'https://phanteks.com/manuals/Eclipse_G500A_Manual_v1.0.pdf',
  'https://phanteks.com/wp-content/uploads/2023/12/07_G500A_Fanless.webp',
  'https://phanteks.com/wp-content/uploads/2022/11/Tabs_Eclipse-G500A_Black_Storage-Left.webp'),
 _DUBILI:('https://www.in-win.com/en/ibuild-ishare/dubili',
  'https://www.in-win.com/uploads/Product/ibuild-ishare/dubili_new/user-manual/dubili_eum_en.pdf',
  'https://www.in-win.com/uploads/Product/ibuild-ishare/dubili_new/dubili_overview_premium_02.png'),
 _FRAME:('https://www.corsair.com/us/en/explorer/diy-builder/cases/corsair-frame-4000-series/',
  'https://www.corsair.com/us/en/explorer/diy-builder/accessories/3d-printed-frame-4000d-psu-shroud-cover-and-fan-scoop/',
  'https://d1q3zw97enxzq2.cloudfront.net/images/FRAME_4000D_PSU3_Shroud_Removal.width-1000.format-webp.webp'),
}


def _valid(case,dimensions):
    return (isinstance(case,dict) and case.get('id') in CASE_IDS
        and isinstance(dimensions,(tuple,list)) and len(dimensions)==3
        and all(type(v) in (int,float) and math.isfinite(v) for v in dimensions)
        and 60<=dimensions[0]<=800 and 60<=dimensions[1]<=900 and 150<=dimensions[2]<=900)


def _rectangle(a,b,c,d):
    return ((a,c),(b,c),(b,d),(a,d))


def layout_reference(case,dimensions):
    """Exact source-qualified bays, never a brand/layout-wide heuristic.

    Source states body width279mm and rear routing90–101mm. The chosen96mm
    chamber,8mm PCB offset and5mm PSU side gap are explicitly unmeasured
    original reference values. Host uses the selected PSU's real world size.
    """
    if not _valid(case,dimensions):return {}
    key=case['id'];w,h,d=map(float,dimensions)
    if key!=_HAF:
        # Generic bottom skin occupies base+16..19mm. These explicitly fixed
        # reference feet put the real selected PSU above that material; the
        # DUBILI floor support is base+19 +/-0.6mm instead of the old slab.
        floor=-h/2+(21. if key==_DUBILI else 20.)
        sources={_SHADOW:(_SOURCES[_SHADOW][1],28),_TUF:(_SOURCES[_TUF][-1],6),
            _G500:(_SOURCES[_G500][1],2),_DUBILI:(_SOURCES[_DUBILI][1],4),
            _FRAME:(_SOURCES[_FRAME][0],None)}
        source,page=sources[key]
        result=dict(case_id=key,psu=dict(basis=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.)),
                center_x_mm=0.,floor_y_mm=floor,rear_z_mm=-d/2+10.),
            positions_verified=False,dimensions_verified=False,manufacturing_cad=False,
            method='exact_case_manual_photo_horizontal_psu_reference',source_urls=_SOURCES[key],
            psu_size_from_selected_component=True,psu_fan_face_reference='down',
            psu_fan_orientation_verified=key==_FRAME,psu_orientation_source=source,
            psu_orientation_source_printed_page=page,
            psu_orientation_accuracy='explicit_manual_instruction' if key==_FRAME else 'diagram_reference_not_a_verified_requirement')
        if key in _ROOF_FRACTIONS:
            result.update(board_y_mm=h*.10,board_vertical_placement_verified=False,
                roof_depth_fraction_reference=_ROOF_FRACTIONS[key],roof_y_mm=-h*_ROOF_FRACTIONS[key])
        if key in (_DUBILI,_SHADOW):
            # The manuals locate these intakes on the front lower floor,
            # not at the centre of the PSU or on the top of its cover.
            # Absolute locations, span and drawing gaps remain references.
            dubili=key==_DUBILI
            capacity={'120':2,'140':1} if dubili else {'120':1,'140':1}
            result['mount_planes']={'bottom':dict(
                position=(0.,-h/2+(20.6 if dubili else 20.),d*(.16 if dubili else .25)),
                normal=(0.,-1.,0.),up=(0.,0.,1.),
                span_mm=(w-26.,d*.50) if dubili else (160.,160.),
                case_id=key,source=source,source_manual_pdf_page=9 if dubili else 17,
                method='official_manual_front_lower_floor_reference',
                source_capacity_count_by_size_mm=dict(capacity),reference_only=True,
                positions_verified=False,dimensions_verified=False,
                mounting_hole_positions_verified=False,span_verified=False,
                drawing_gap_mm=1. if dubili else 1.9,drawing_gap_verified=False)}
            constraint=dict(case_id=key,source_url=source,source_manual_pdf_page=4 if dubili else 17,
                max_count_by_size_mm=dict(capacity),positions_verified=False,dimensions_verified=False)
            if dubili:
                constraint.update(psu_length_threshold_mm=180.,max_count_above_psu_length_threshold=1,
                    source_max_psu_length_mm=230.,
                    source_condition='Only one 120/140 mm bottom fan when PSU length exceeds 180 mm.')
            else:
                constraint.update(source_mount_role='front_floor_under_psu_cover',
                    source_document_retrieval='manufacturer_authored_mirror_original_endpoint_unavailable',
                    source_original_bytes_verified=False)
            result['fan_constraints']={'bottom':constraint}
        return result
    tray=min(w,279.)/2-96.
    return dict(case_id=_HAF,board_x_mm=tray-8.,tray_x_mm=tray,
        board_to_tray_reference_mm=8.,support_center_y_mm=-h/2+44.,
        psu=dict(basis=((0.,1.,0.),(-1.,0.,0.),(0.,0.,1.)),align_x='left',
            boundary_x_mm=tray+5.,floor_y_mm=-h/2+46.,rear_z_mm=-d/2+10.),
        source_urls=_SOURCES[_HAF],source_body_dimensions_mm=dict(width=279.,height=540.,depth=556.),
        source_behind_tray_clearance_mm=(90.,101.),chosen_reference_chamber_mm=96.,
        positions_verified=False,dimensions_verified=False,manufacturing_cad=False,
        method='official_rear_chamber_diagram_reference',
        psu_size_from_selected_component=True,main_chamber_is_not_a_psu_bay=True,
        psu_fan_face_reference='right',psu_fan_orientation_verified=False)


def _plate(polygon,holes,thickness,origin,basis):
    from assembly_detail import perforated_plate
    values=perforated_plate(polygon,holes,thickness,clip_walls=True)
    result=[]
    for at in range(0,len(values),6):
        for offset in (0,3):
            p=values[at+offset:at+offset+3]
            result.extend(sum(p[k]*basis[k][axis] for k in range(3))
                          +(origin[axis] if offset==0 else 0.) for axis in range(3))
    return tuple(result)


def _part(case_id,identity,label,kind='case_cover'):
    return dict(id=identity,label=label,kind=kind,component='case',model_id=case_id,
        assembly_state='installed',geometry_status='official_photo_reference',
        dimensions_verified=False,positions_verified=False,source_url=_SOURCES[case_id][0],
        source_urls=_SOURCES[case_id],display_screen=False,power_sensor_bound=False)


def build(case,dimensions,tone):
    """Return exact-model fixed material Meshes and detached source metadata.

    A recognized model can have no horizontal PSU cover: HAF700EVO's rear
    chamber and DUBILI's open lower bay must not acquire a fictitious full-width
    cover. Their observed lower vented supports remain real mesh geometry.
    """
    if not _valid(case,dimensions):return (),{}
    from assembly_geometry import Mesh
    key=case['id'];w,h,d=map(float,dimensions);thickness=1.2
    meta=dict(case_id=key,method='exact_case_fixed_observed_material_reference',
        source_urls=_SOURCES[key],geometry_status='official_photo_reference',
        dimensions_verified=False,positions_verified=False,thickness_verified=False,cad_verified=False,
        chamber_is_solid=False,selected_component_geometry_used=False,far_side_wall_added=False,
        exact_vent_pattern_modeled=False,exact_fixings_modeled=False,
        thickness_mm=thickness,parts=[],removed_parts=[],reference_regions=[],
        layout_reference=layout_reference(case,dimensions))
    meshes=[]
    def add(identity,label,vertices,kind='case_cover',name='psu-shroud'):
        if not vertices:raise ValueError('An observed material part may not silently disappear')
        meshes.append(Mesh(name,vertices,tuple(tone),component='case',part_id=identity))
        meta['parts'].append(_part(key,identity,label,kind))
    if key in (_HAF,_DUBILI):
        # Actual bottom fan/radiator brackets have an open interior and small
        # perimeter/cross rails. The slotted sample is not a filled lower bay.
        body_width=min(w,279.) if key==_HAF else w
        left=-body_width/2+8.
        right=body_width/2-(96. if key==_HAF else 8.)
        rear=-d/2+22.;front=d/2-(66. if key==_HAF else 22.)
        floor=-h/2+(44. if key==_HAF else 19.)
        width=right-left;length=front-rear
        holes=[]
        for index in range(3):
            lo=rear+8.+index*(length-16.)/3
            hi=rear+8.+(index+1)*(length-16.)/3-4.
            holes.append(_rectangle(left+5.,right-5.,-hi,-lo))
        values=_plate(_rectangle(left,right,-front,-rear),holes,thickness,
            (0.,floor,0.),((1.,0.,0.),(0.,0.,-1.),(0.,1.,0.)))
        add('case:bottom-cooling-support','底部通风安装框',values,'case_structure','case-bottom-cooling-support')
        meta.update(horizontal_psu_cover_present=False,front_bay_open=True,
            replaces_case_bottom=True,
            lower_support_role='vented_fan_radiator_bracket' if key==_HAF else 'open_vented_floor_support',
            support_world_y_mm=floor,source_observation='Rear PSU chamber and open main-chamber lower cooling bracket.' if key==_HAF else
                'Official exploded parts and unobstructed bottom intake show no full-width PSU cover.',
            reference_regions=[dict(kind='vented_lower_support',world_y_mm=floor,
                bounds_xz_mm=((left,rear),(right,front)))])
        if key==_HAF:
            layout=layout_reference(case,dimensions);tray_x=layout['tray_x_mm']
            poly=((-d*.20,-h*.42),(d*.46,-h*.42),(d*.46,h*.34),(-d*.20,h*.34))
            holes=(((d*.12,h*.015),(d*.42,h*.015),(d*.42,h*.285),(d*.12,h*.285)),
                   ((d*.035,-h*.22),(d*.09,-h*.22),(d*.09,h*.20),(d*.035,h*.20)),
                   ((d*.10,h*.29),(d*.38,h*.29),(d*.38,h*.32),(d*.10,h*.32)))
            tray=_plate(poly,holes,thickness,(tray_x,0.,0.),
                ((0.,0.,-1.),(0.,1.,0.),(1.,0.,0.)))
            add('case:motherboard-tray','后舱主板托盘',tray,'case_structure','case-haf-motherboard-tray')
            meta.update(psu_chamber='behind_motherboard_lower_rear',
                source_body_dimensions_mm=dict(width=279.,height=540.,depth=556.),
                source_behind_tray_clearance_mm=(90.,101.),hardware_chamber_pose_requires_reference_review=True,
                layout_reference=layout,tray_openings_reference_polygon=poly,tray_openings_reference_holes=holes,
                unverified_details='Fixed support/tray proportions and rear chamber hardware pose are original references, not labelled manufacturing dimensions.')
        else:meta.update(manual_pdf_page=4,source_bottom_structure_manual_pdf_page=9,
            source_bottom_fans=dict(count_120=2,count_140=1),
            cable_shields_are_psu_cover=False)
        return tuple(meshes),meta

    left=-(w-12.)/2;right=-left;bottom=-h*.49;top=-h*_ROOF_FRACTIONS[key]
    rear=-(d-12.)/2;front=-rear
    # These constants are manual/photo observations, not a function of which
    # fan happens to be selected, its count, or a tested collision result.
    front_gap={_SHADOW:.18,_TUF:.16,_G500:.17,_FRAME:.23}[key]*d
    roof_end=front-front_gap;side_end=front-2.
    side_holes=[]
    if key==_G500:
        z0=rear+d*.065;z1=rear+d*.37;y0=bottom+(top-bottom)*.20;y1=bottom+(top-bottom)*.77
        side_holes.append(((-z0,y0),(-z1,y0),(-z1+6.,y1),(-z0-6.,y1)))
        meta['psu_observation_window_open']=True
    side=_plate(_rectangle(-side_end,-rear,bottom,top-thickness),side_holes,thickness,
        (left+thickness/2,0.,0.),((0.,0.,-1.),(0.,1.,0.),(1.,0.,0.)))
    roof_holes=[]
    # Bounded vent samples preserve an actual open material surface. Neither
    # the hole count nor the manufacturing mesh pattern is asserted exact.
    vent_samples=0 if key==_G500 else 7 if key in (_TUF,_FRAME) else 5
    for index in range(vent_samples):
        z=rear+d*.14+index*d*.036
        roof_holes.append(_rectangle(left+w*.15,right-w*.15,-z-2.,-z+2.))
    roof_holes.append(_rectangle(right-w*.23,right-w*.06,-(roof_end-d*.12),-(roof_end-d*.21)))
    roof=_plate(_rectangle(left,right,-roof_end,-rear),roof_holes,thickness,
        (0.,top-thickness/2,0.),((1.,0.,0.),(0.,0.,-1.),(0.,1.,0.)))
    add('case:psu-cover','电源舱薄板罩',(*side,*roof))
    meta.update(horizontal_psu_cover_present=True,front_bay_open=True,
        front_gap_reference_mm=front_gap,roof_end_world_z_mm=roof_end,
        roof_world_y_mm=top,side_world_x_mm=left,side_end_world_z_mm=side_end,
        normalized_reference=dict(front_gap_depth_fraction={_SHADOW:.18,_TUF:.16,_G500:.17,_FRAME:.23}[key],
            roof_height_fraction=_ROOF_FRACTIONS[key]),
        reference_regions=[dict(kind='viewing_side_skin',x_mm=(left,left+thickness),
            y_mm=(bottom,top-thickness),z_mm=(rear,side_end)),
            dict(kind='perforated_roof',x_mm=(left,right),y_mm=(top-thickness,top),z_mm=(rear,roof_end))],
        side_holes_local_zy=tuple(side_holes),roof_vent_sampling='not_inferred_solid_psu_roof' if key==_G500 else 'bounded_reference',
        roof_reference_vent_samples=vent_samples,
        unverified_details='Unlabelled plate thickness, exact seams, vent pattern and gap proportions are original references.')
    if key==_SHADOW:
        # Manual printed p8 item J is a distinct ventilated airflow guide, not
        # a solid vertical end cap that seals off the lowest front fan.
        z0=roof_end;y0=top-thickness;z1=front-2.;y1=bottom+6.
        length=math.hypot(z1-z0,y1-y0)
        along=(0.,(y1-y0)/length,(z1-z0)/length)
        normal=(0.,-along[2],along[1])
        # x cross along = normal; all primitive normals remain geometric.
        origin=(0.,(y0+y1)/2,(z0+z1)/2)
        slots=tuple(_rectangle(-w*.30,w*.30,-length*.34+i*length*.14,
            -length*.34+i*length*.14+3.) for i in range(5))
        ramp=_plate(_rectangle(-w*.38,w*.38,-length/2,length/2),slots,thickness,
            origin,((1.,0.,0.),along,normal))
        add('case:psu-airflow-cover','前段通风导流盖',ramp)
        # The printed p15 bottom-fan installation shows the vented chassis
        # floor below this separate guide. Fixed slots are a bounded original
        # sample, not a selected-fan-dependent aperture or factory mesh copy.
        floor_left=-w/2+3.;floor_right=w/2-3.
        floor_rear=-d/2+3.;floor_front=d/2-3.
        floor_holes=[]
        for row in range(8):
            z0=floor_rear+4.+row*(floor_front-floor_rear-8.)/8
            z1=floor_rear+4.+(row+1)*(floor_front-floor_rear-8.)/8-4.
            for column in range(3):
                x0=floor_left+5.+column*(floor_right-floor_left-10.)/3
                x1=floor_left+5.+(column+1)*(floor_right-floor_left-10.)/3-5.
                floor_holes.append(_rectangle(x0,x1,-z1,-z0))
        floor_y=-h/2+17.5
        floor=_plate(_rectangle(floor_left,floor_right,-floor_front,-floor_rear),floor_holes,
            thickness,(0.,floor_y,0.),((1.,0.,0.),(0.,0.,-1.),(0.,1.,0.)))
        add('case:bottom-intake-floor','底部通风底板',floor,'case_structure','case-bottom-cooling-support')
        meta.update(manual_printed_page=8,manual_items=('G PSU Shroud Panel','J Airflow Cover PSU Shroud'),
            front_airflow_guide_reference=True,airflow_guide_endpoints_yz_mm=((y0,z0),(y1,z1)),
            manual_retrieval='manufacturer_authored_manual_mirror_original_endpoint_unavailable',
            manual_mirror_url='https://gzhls.at/blob/ldb/e/1/9/d/7717a7368e44bb283d8ff4f2fc2886c99ae9.pdf',
            original_server_byte_identity_verified=False)
        meta.update(replaces_case_bottom=True,bottom_floor_world_y_mm=floor_y,
            bottom_floor_top_world_y_mm=floor_y+thickness/2,bottom_floor_vent_samples=24,
            exact_bottom_vent_pattern_verified=False,bottom_mount_role='front_floor_under_psu_cover',
            source_bottom_fan_manual_pdf_page=17,source_bottom_fan_manual_printed_page=15)
        meta['reference_regions'].append(dict(kind='vented_bottom_floor',world_y_mm=floor_y,
            bounds_xz_mm=((floor_left,floor_rear),(floor_right,floor_front))))
    elif key==_TUF:meta.update(source_observation='Thin viewing-side skin, perforated top and open lowest front intake bay.')
    elif key==_G500:meta.update(manual_printed_pages=(2,3),source_observation='Open PSU observation cutout, solid PSU roof with reference cable passage and fixed front cooling bay.')
    elif key==_FRAME:meta.update(manual_section='4.1 STANDARD PSU SHROUD REMOVAL',
        source_observation='Stock standard shroud with permanent front cut-away; not the compact LCD/WOOD/Vault cover.',
        stock_front_cutaway=True)
    return tuple(meshes),meta
