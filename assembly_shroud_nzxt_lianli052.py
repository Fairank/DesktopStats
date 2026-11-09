"""Three exact cases' lower material, from official 2024/manual photographs.

The compartment is empty space, not a closed cuboid.  Unlabelled panel
thicknesses, aperture proportions and vent sampling are original references,
not factory CAD.  Selection of a fan, radiator or power supply never deforms
these fixed surfaces.  All visual styles consume these same physical Meshes.
"""
from copy import deepcopy
import math


H5 = 'nzxt-h5-flow-2024'
H7 = 'nzxt-h7-flow-2024'
LANCOOL = 'lian-li-lancool-iii'
CASE_IDS = (H5, H7, LANCOOL)
_H5_MANUAL = 'https://cdn-g.nzxt.com/dl/1724123146-h5-flow-h5-flow-rgb-2024-digital-manual_240401_v1.pdf'
_H7_MANUAL = 'https://cdn-g.nzxt.com/dl/1716886070-h7-flow-h7-flow-rgb-2024-digital-manual_240322.pdf'
_LIAN_MANUAL = 'https://drive.google.com/file/d/1kd9ku_raF2uXWeLD7voGfT4ZZ10XOizy/view?usp=sharing'
_SOURCES = {
    H5: ('https://support.nzxt.com/hc/en-us/articles/40225168535451-H5-Flow-2024-Specs',
         _H5_MANUAL, 'https://support.nzxt.com/hc/article_attachments/40225168534043'),
    H7: ('https://support.nzxt.com/hc/en-us/articles/40379376386203-H7-Flow-2024-Specs',
         _H7_MANUAL, 'https://support.nzxt.com/hc/article_attachments/40379395663387'),
    LANCOOL: ('https://lian-li.com/product/lancool-iii/', _LIAN_MANUAL,
              'https://lian-li.com/wp-content/uploads/2022/07/lan3-036-1.jpg'),
}
_ROOF_BASIS = ((1., 0., 0.), (0., 0., -1.), (0., 1., 0.))
_SIDE_BASIS = ((0., 0., -1.), (0., 1., 0.), (1., 0., 0.))


def _rectangle(x0, x1, y0, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _plate(polygon, holes, thickness, origin, basis):
    # The existing finite plate subtraction produces actual open material,
    # including aperture walls; no painted black circles or invisible solids.
    from assembly_detail import perforated_plate
    local = perforated_plate(polygon, holes, thickness, segments=8, clip_walls=True)
    out = []
    for index in range(0, len(local), 6):
        for offset in (0, 3):
            point = local[index + offset:index + offset + 3]
            out.extend(sum(point[k] * basis[k][axis] for k in range(3))
                       + (origin[axis] if offset == 0 else 0.) for axis in range(3))
    return tuple(out)


def _valid(case, dimensions):
    return (isinstance(case, dict) and case.get('id') in CASE_IDS
            and isinstance(dimensions, (tuple, list)) and len(dimensions) == 3
            and all(type(v) in (int, float) and math.isfinite(v) for v in dimensions)
            and 60 <= dimensions[0] <= 800 and 60 <= dimensions[1] <= 900
            and 150 <= dimensions[2] <= 900)


def _part(case_id, identity, label, role, **values):
    return dict(id=identity, label=label, kind='case_cover', component='case',
                model_id=case_id, assembly_state='installed',
                geometry_status='official_photo_reference', dimensions_verified=False,
                positions_verified=False, source_url=_SOURCES[case_id][0],
                source_urls=_SOURCES[case_id], observed_role=role,
                display_screen=False, power_sensor_bound=False, **values)


def layout_reference(case, dimensions):
    """Exact-model fixed host references; no component construction/guessing.

    The manuals establish the different PSU orientations and lower fan bays.
    Their unlabelled coordinates and 1-mm drawing gaps are original references.
    The caller derives the PSU center from the selected supply's rigid world
    dimensions; a larger or incompatible selection must still be checked.
    """
    if not _valid(case, dimensions):
        return {}
    w,h,d=map(float,dimensions)
    key=case['id']
    if key in (H5,LANCOOL):
        roof=-h*(.26 if key==H5 else .29)
        manual=_H5_MANUAL if key==H5 else _LIAN_MANUAL
        # H5 manual p2 explicitly requires fan-up. LANCOOL p6 shows the
        # opposite, fan-down, with the upper cover blank: do not share a flip.
        psu_basis=((-1.,0.,0.),(0.,-1.,0.),(0.,0.,1.)) if key==H5 else ((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))
        result=dict(case_id=key,source=manual,source_urls=_SOURCES[key],reference_only=True,
            verified=False,dimensions_verified=False,positions_verified=False,
            board_y_mm=h*.10,board_positions_verified=False,
            source_manual_pdf_page=2 if key==H5 else 6,roof_world_y_mm=roof,
            psu=dict(basis=psu_basis,align_x='center',center_x_mm=0.,
                floor_y_mm=-h/2.+(20. if key==H5 else 21.),rear_z_mm=-d/2.+10.,
                source=manual,reference_only=True,positions_verified=False),mount_planes={})
        if key==H5:
            result.update(psu_fan_world_normal_reference=(0.,1.,0.),
                          source_psu_fan_orientation='Manual p2 explicitly says fan facing up.')
            result['mount_planes']['bottom']=dict(position=(0.,roof+1.,0.),normal=(0.,-1.,0.),
                up=(0.,0.,1.),span_mm=(w-24.,d-32.),source=manual,reference_only=True,
                dimensions_verified=False,positions_verified=False,verified=False,
                drawing_gap_mm=1.,drawing_gap_verified=False,source_capacity_count=2,
                source_capacity_size_mm=120,source_role='Two bottom fans mount ABOVE the perforated PSU roof.')
        else:
            result.update(psu_fan_world_normal_reference=(0.,-1.,0.),
                          source_psu_fan_orientation='Manual p6 PSU installation drawing: blank upper face, fan underneath.')
            # Manual p9 gives three 120-mm fans after the three covers are
            # removed.  This frame follows the SAME fixed authored bracket
            # used by build(); it is not derived from a selected GPU or fan.
            left,right=-(w-12.)/2.,(w-12.)/2.
            rear,front=-(d-12.)/2.,(d-12.)/2.
            usable_left,usable_right=left+7.,right-w*.22
            tray_rear=rear+d*.07
            tray_front=front-d*.125-d*.025
            result['mount_planes']['above_psu_shroud']=dict(
                position=((usable_left+usable_right)/2.,roof+1.,0.),
                normal=(0.,-1.,0.),up=(0.,0.,1.),
                span_mm=(usable_right-usable_left,tray_front-tray_rear),
                source=manual,source_manual_pdf_page=9,reference_only=True,
                dimensions_verified=False,positions_verified=False,verified=False,
                drawing_gap_mm=1.,drawing_gap_verified=False,
                source_capacity_count=3,source_capacity_size_mm=120,
                source_role='Manual p9: three 120-mm fans on the independent upper PSU bracket after removing its mounting plates.',
                supported_part_kinds=('case_fan',),radiator_runtime_supported=False,
                source_radiator_capacity_mm=360,motion_supported=False,
                mechanical_removal_direction_verified=False)
        return result
    left,right=-(w-12.)/2.,(w-12.)/2.
    partition=right-94.
    bay_left,bay_right=left+5.,partition-5.
    floor=-h/2.+18.
    return dict(case_id=H7,source=_H7_MANUAL,source_urls=_SOURCES[H7],
                source_manual_pdf_page=2,reference_only=True,verified=False,
                dimensions_verified=False,positions_verified=False,
                board_y_mm=h*.10,board_positions_verified=False,
                floor_frame_y_mm=floor,floor_frame_top_y_mm=floor+.6,
                lower_partition_x_mm=partition,lower_partition_top_y_mm=-h*.19,
                lower_partition_front_z_mm=(d-12.)/2.-d*.11,
                lower_main_chamber_x_mm=(bay_left,bay_right),
                psu=dict(basis=((0.,1.,0.),(-1.,0.,0.),(0.,0.,1.)),
                    align_x='right',boundary_x_mm=w/2.-9.,floor_y_mm=-h/2.+12.,
                    rear_z_mm=-d/2.+10.,reference_only=True,positions_verified=False,
                    source=_H7_MANUAL),
                mount_planes=dict(bottom=dict(position=((bay_left+bay_right)/2.,floor+.6+1.,0.),
                    normal=(0.,-1.,0.),up=(0.,0.,-1.),span_mm=(bay_right-bay_left,d-32.),
                    source=_H7_MANUAL,reference_only=True,positions_verified=False,
                    halfturn_for_main_chamber_lead=True,installation_orientation_reference=True,
                    dimensions_verified=False,verified=False,drawing_gap_mm=1.,drawing_gap_verified=False)))


def build(case, dimensions, tone):
    """Return fixed thin skins/supports and detached provenance/part metadata.

    The tuple is empty for every other case.  No caller options, selected parts,
    hardware sampling, timers or caches are used by this construction function.
    H7's upright PSU needs the caller's exact-model lower-bay pose hook; this
    helper does not move the PSU, board, or installed fans itself.
    """
    if not _valid(case, dimensions):
        return (), {}
    from assembly_geometry import Mesh
    key = case['id']
    w, h, d = map(float, dimensions)
    left, right = -(w - 12.) / 2., (w - 12.) / 2.
    rear, front = -(d - 12.) / 2., (d - 12.) / 2.
    layout = layout_reference(case, dimensions)
    bottom, top, thickness = -h * .49, layout.get('roof_world_y_mm',-h*.32), 1.2
    meshes = []
    meta = dict(case_id=key, method='exact_case_fixed_observed_thin_material_reference',
                source_urls=_SOURCES[key], geometry_status='official_photo_reference',
                dimensions_verified=False, positions_verified=False,
                thickness_verified=False, cad_verified=False,
                thickness_mm=thickness, chamber_is_solid=False,
                exact_vent_pattern_modeled=False, exact_fixings_modeled=False,
                vent_pattern_is_bounded_reference=True,
                selected_component_geometry_used=False, parts=[], removed_parts=[],
                replaces_case_bottom=False,
                reference_regions=[], assembly_state='installed')

    def add(identity, label, vertices, role, *, name='psu-shroud', kind='case_cover', **values):
        if not vertices:
            raise ValueError('An observed lower material part may not silently vanish')
        meshes.append(Mesh(name, vertices, tuple(tone),
                           component='case', part_id=identity))
        if not any(row['id'] == identity for row in meta['parts']):
            meta['parts'].append(dict(_part(key, identity, label, role, **values),kind=kind))

    if key == H5:
        # Exact 2024 photograph: round-perforated roof, perforated viewing-side
        # skin, two back cable apertures and an open front U recess.  The old
        # 2022 H5's diagonal intake funnel must not be substituted here.
        notch_half = w * .36
        notch_rear = front - d * .135
        roof_poly = ((left, -front), (-notch_half, -front),
                     (-notch_half, -notch_rear), (notch_half, -notch_rear),
                     (notch_half, -front), (right, -front),
                     (right, -rear), (left, -rear))
        holes = [(x, -(rear + d * .17 + j * d * .103), 8.)
                 for x in (-w * .255, 0., w * .255) for j in range(5)]
        # Back-edge rectangular cable passages are visible in the exact photo.
        holes.extend(_rectangle(right - w * .17, right - w * .04, -z - d * .075, -z)
                     for z in (rear + d * .12, rear + d * .48))
        roof = _plate(roof_poly, holes, thickness, (0., top - thickness / 2., 0.), _ROOF_BASIS)
        side_holes = [(z, bottom + (top - bottom) * f, 6.)
                      for z in (-rear - d * .18, -rear - d * .39, -rear - d * .60, -rear - d * .81)
                      for f in (.30, .68)]
        side = _plate(_rectangle(-front, -rear, bottom, top - thickness), side_holes,
                      thickness, (left + thickness / 2., 0., 0.), _SIDE_BASIS)
        add('case:psu-cover', 'H5 Flow 2024 通风电源罩', roof, 'perforated_roof_with_front_recess')
        add('case:psu-cover', 'H5 Flow 2024 通风电源罩', side, 'perforated_viewing_side')
        meta.update(horizontal_psu_cover_present=True, main_lower_bay_open=False,
                    front_recess_observed=True, front_recess_dimensions_verified=False,
                    old_diagonal_gpu_intake_added=False, far_side_wall_added=False,
                    roof_world_y_mm=top, front_recess_world_mm=dict(x=(-notch_half, notch_half),
                    z=(notch_rear, front)), roof_notch_depth_fraction_reference=.135,
                    roof_notch_half_width_fraction_reference=.36,
                    manual_spec_conflict='Use current support dimensions/clearances, not superseded manual clearances.',
                    reference_regions=[dict(kind='perforated_roof', y_mm=(top-thickness, top)),
                                       dict(kind='perforated_side', x_mm=(left, left+thickness))])
    elif key == H7:
        # H7 2024 has an upright PSU behind only the LOWER motherboard region.
        # The front photo shows a vertical lower back partition with a narrow
        # fold over that pocket and an open three-fan main-chamber floor.
        # Do not add the old, full-width horizontal filled shroud or turn the
        # whole case into a full-height dual chamber (CPU clearance stays 185).
        partition_x = layout['lower_partition_x_mm']
        # Fixed photograph proportion, NOT computed from the selected PSU.
        # This lower-only reference leaves room for an upright 150-mm ATX
        # width under the fold and the separately posed ATX board above it.
        partition_top = layout['lower_partition_top_y_mm']
        partition_front = layout['lower_partition_front_z_mm']
        side = _plate(_rectangle(-partition_front, -rear, bottom, partition_top-thickness), (),
                      thickness, (partition_x + thickness/2., 0., 0.), _SIDE_BASIS)
        fold = _plate(_rectangle(partition_x, right, -partition_front, -rear), (), thickness,
                      (0., partition_top-thickness/2., 0.), _ROOF_BASIS)
        add('case:psu-cover', 'H7 Flow 2024 下背电源隔板', (*side, *fold), 'lower_rear_upright_psu_partition')
        # Fixed perimeter frame, not a plate over the bottom intake opening.
        floor = layout['floor_frame_y_mm']
        floor_holes = []
        bay_left, bay_right = layout['lower_main_chamber_x_mm']
        for index in range(3):
            z0 = rear + 10. + index * (front-rear-20.)/3.
            z1 = rear + 10. + (index+1) * (front-rear-20.)/3. - 5.
            floor_holes.append(_rectangle(bay_left+3., bay_right-3., -z1, -z0))
        floor_values = _plate(_rectangle(bay_left, bay_right, -front+5., -rear-5.),
                             floor_holes, thickness, (0., floor, 0.), _ROOF_BASIS)
        add('case:bottom-intake-frame', 'H7 Flow 2024 底部开放扇架', floor_values,
            'open_bottom_intake_support',name='case-bottom-intake-frame',kind='case_structure')
        meta.update(horizontal_psu_cover_present=False, main_lower_bay_open=True,
                    replaces_case_bottom=True,
                    far_side_wall_added=False, lower_partition_world_x_mm=partition_x,
                    lower_partition_top_world_y_mm=partition_top,
                    lower_partition_front_world_z_mm=partition_front,
                    floor_world_y_mm=floor,
                    lower_main_chamber_x_reference_mm=(bay_left, bay_right),
                    psu_layout_requires_exact_host_pose=True,
                    psu_basis_reference=((0.,1.,0.),(-1.,0.,0.),(0.,0.,1.)),
                    psu_fan_world_normal_reference=(1.,0.,0.),
                    bottom_fan_center_world_x_reference_mm=(bay_left+bay_right)/2.,
                    psu_positions_verified=False, bottom_fan_positions_verified=False,
                    source_psu_installation_manual_pdf_page=2,
                    source_bottom_fan_capacity=dict(size_mm=120,count=3,installed_count_unknown=True),
                    reference_regions=[dict(kind='lower_vertical_partition',x_mm=(partition_x,partition_x+thickness),
                        y_mm=(bottom,partition_top-thickness),z_mm=(rear,partition_front)),
                        dict(kind='lower_psu_pocket_fold',x_mm=(partition_x,right),
                        y_mm=(partition_top-thickness,partition_top),z_mm=(rear,partition_front))])
    else:
        # Manual p2/p9: an independent upper fan bracket, THREE mounting/SSD
        # plates, and hinged lower mesh doors.  The empty PSU/HDD compartment
        # underneath is not three solid boxes.  Front bracket p12 has four
        # physical modes; this helper does not silently choose a fan-dependent
        # fifth mode or change the caller's mounted hardware.
        roof_end = front - d * .125
        usable_left, usable_right = left+7., right-w*.22
        tray_rear, tray_front = rear+d*.07, roof_end-d*.025
        span = (tray_front-tray_rear)/3.
        openings = []
        for index in range(3):
            z0, z1 = tray_rear+index*span+3., tray_rear+(index+1)*span-3.
            openings.append(_rectangle(usable_left+3.,usable_right-3.,-z1,-z0))
        bracket = _plate(_rectangle(left,right,-roof_end,-rear),openings,thickness,
                         (0.,top-thickness/2.,0.),_ROOF_BASIS)
        add('case:psu-top-bracket','LANCOOL III 上方通风托架',bracket,'removable_upper_fan_ssd_bracket',
            source_manual_pdf_pages=(2,9),removable_observed=True)
        for index in range(3):
            z0, z1 = tray_rear+index*span+1.5,tray_rear+(index+1)*span-1.5
            # Rectangular sampled ventilation slots are geometry, not an
            # assertion of the exact manufacturer's repeating slot count.
            slots=[_rectangle(usable_left+10.,usable_right-10.,-z-2.,-z+2.)
                   for z in (z0+(z1-z0)*f for f in (.19,.34,.49,.64,.79))]
            values=_plate(_rectangle(usable_left+1.,usable_right-1.,-z1,-z0),slots,thickness,
                          (0.,top+thickness/2.,0.),_ROOF_BASIS)
            add('case:psu-mounting-plate:'+str(index), 'LANCOOL III 独立安装盖板 '+str(index+1),
                values,'removable_fan_ssd_mounting_plate',source_manual_pdf_pages=(2,9),
                removable_observed=True,installed_cover_is_fan=False)
        for side in (-1,1):
            x=left+thickness/2. if side<0 else right-thickness/2.
            holes=[_rectangle(-z-d*.035,-z+d*.035,bottom+(top-bottom)*.20,bottom+(top-bottom)*.80)
                   for z in (rear+d*.14+j*d*.115 for j in range(7))]
            door=_plate(_rectangle(-front,-rear,bottom,top-thickness),holes,thickness,
                        (x,0.,0.),_SIDE_BASIS)
            add('case:psu-side-door:'+('left' if side<0 else 'right'),
                'LANCOOL III '+('左' if side<0 else '右')+'侧下方翻网门',door,
                'hinged_lower_mesh_door',hinged_observed=True,removable_observed=True)
        meta.update(horizontal_psu_cover_present=True,main_lower_bay_open=False,
                    far_side_wall_added=False,lower_mesh_doors_observed=2,
                    roof_world_y_mm=top,roof_end_world_z_mm=roof_end,
                    front_gap_depth_fraction_reference=.125,
                    source_manual_pdf_pages=(2,6,9,12),source_front_bracket_modes=4,
                    installed_mounting_plates=3,mounting_plates_removable_for_cooling=True,
                    deferred_part_ids=tuple('case:psu-mounting-plate:'+str(index) for index in range(3)),
                    reference_regions=[dict(kind='upper_open_fan_bracket',y_mm=(top-thickness,top),z_mm=(rear,roof_end)),
                        dict(kind='two_thin_hinged_mesh_doors',x_mm=((left,left+thickness),(right-thickness,right)))])
    if len(meshes)>8 or sum(mesh.vertex_count//3 for mesh in meshes)>4500:
        raise ValueError('Fixed observed shroud exceeded its construction budget')
    meta.update(mesh_count=len(meshes),triangle_count=sum(mesh.vertex_count//3 for mesh in meshes))
    return tuple(meshes),meta


def finish(meshes, cooling_meshes, cooling_meta, meta):
    """Remove only Lancool III's documented plates for ACTUAL upper cooling.

    Manual p9 explicitly requires removing the mounting plates before fitting
    fans/a radiator to this bracket. Rejected/requested choices alone are not
    a physical installation. The bracket and both hinged doors remain.
    """
    if not isinstance(meta,dict) or meta.get('case_id')!=LANCOOL:
        return meshes,meta
    state=deepcopy(meta)
    rows=cooling_meta.get('parts',()) if isinstance(cooling_meta,dict) else ()
    actual_ids={mesh.part_id for mesh in cooling_meshes if mesh.vertices}
    actual=[row for row in rows if isinstance(row,dict)
            and row.get('mount')=='above_psu_shroud'
            and row.get('kind') in ('case_fan','radiator') and row.get('id') in actual_ids]
    if not actual:
        return meshes,state
    removed=[dict(row,assembly_state='removed_reference',physical_mesh_present=False,
                  reason='manual_p9_remove_mounting_plates_for_upper_fan_or_radiator')
             for row in state['parts'] if row['id'].startswith('case:psu-mounting-plate:')]
    identities={row['id'] for row in removed}
    state['parts']=[row for row in state['parts'] if row['id'] not in identities]
    state.update(removed_parts=removed,installed_mounting_plates=0,
                 assembly_state='mounting_plates_removed_for_actual_upper_cooling',
                 upper_cooling_part_ids=[row['id'] for row in actual])
    result=tuple(mesh for mesh in meshes if mesh.part_id not in identities)
    own=[mesh for mesh in result if mesh.part_id in {row['id'] for row in state['parts']}]
    state.update(mesh_count=len(own),triangle_count=sum(mesh.vertex_count//3 for mesh in own))
    return result,state
