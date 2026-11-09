"""MOD-5's open lower fan cassette and outboard supports, not factory CAD.

The exact manufacturer's step13 shows a removable open bracket with three
120mm fans below it. The original silhouette, unlabelled placement, foot
sampling and aperture geometry here are references. No selected part is read.
This deliberately does not certify the old motherboard/PSU installation pose.
"""
import math


CASE_ID = 'jonsbo-mod-5'
PRODUCT = 'https://www.jonsbo.com/en/products/MOD-5Black.html'
MANUAL = 'https://www.jonsbo.com/Upfiles/down/MOD5.pdf'
SUPPORT_ID = 'case:mod5-base-supports'
BRACKET_ID = 'case:mod5-bottom-fan-bracket'
CRADLE_ID = 'case:mod5-psu-cradle'


def _valid(case, dimensions):
    return (isinstance(case, dict) and case.get('id') == CASE_ID
        and isinstance(dimensions, (tuple, list)) and len(dimensions) == 3
        and all(type(v) in (int, float) and math.isfinite(v) for v in dimensions)
        and 220. <= dimensions[0] <= 500. and 400. <= dimensions[1] <= 900.
        and 420. <= dimensions[2] <= 900.)


def layout_reference(case, dimensions):
    """One explicit manual option; all unlabelled coordinates are references.

    Step6's option02 exposes the PSU fan on its upper face and AC toward the
    rear. The proper half turn preserves canonical width/height/length and
    the rear face. Neither the manufacturer's inner/outer depth nor mechanical
    mounting dimensions were measured, and no current component selects them.
    """
    if not _valid(case, dimensions):
        return {}
    _, h, d = map(float, dimensions)
    return dict(case_id=CASE_ID,
        psu=dict(basis=((-1., 0., 0.), (0., -1., 0.), (0., 0., 1.)),
            center_x_mm=0., floor_y_mm=-h*.38, rear_z_mm=-d/2+10.),
        source_urls=(PRODUCT, MANUAL), source_manual_pdf_page=4, source_manual_step=6,
        source_psu_option='02_reference', method='official_manual_raised_rear_psu_reference',
        psu_fan_face_reference='up', psu_fan_orientation_verified=False,
        psu_fan_orientation_accuracy='option02_visible_diagram_reference',
        source_alternative_installation_positions=True, chosen_depth_reference=True,
        source_inside_outside_depth_verified=False, psu_size_from_selected_component=True,
        positions_verified=False, dimensions_verified=False, manufacturing_cad=False)


def describe(case, dimensions):
    """Detached source/part identities, without building or caching geometry."""
    if not _valid(case, dimensions):
        return {}
    w, h, d = map(float, dimensions)
    parts = [dict(id=identity, label=label, kind='case_structure', component='case',
        model_id=CASE_ID, assembly_state='installed',
        geometry_status='official_manual_photo_reference', source_url=MANUAL,
        source_urls=(PRODUCT, MANUAL), source_manual_pdf_page=6,
        source_manual_step=13, dimensions_verified=False, positions_verified=False,
        display_screen=False, power_sensor_bound=False)
        for identity, label in ((SUPPORT_ID, 'MOD-5 perimeter base supports'),
                               (BRACKET_ID, 'MOD-5 open bottom fan cassette'),
                               (CRADLE_ID, 'MOD-5 raised rear PSU cradle reference'))]
    parts[-1].update(source_manual_pdf_page=4, source_manual_step=6)
    return dict(case_id=CASE_ID, source_urls=(PRODUCT, MANUAL), parts=parts,
        source_manual_pdf_page=6, source_manual_step=13,
        geometry_status='official_manual_photo_reference', dimensions_verified=False,
        positions_verified=False, cad_verified=False, thickness_verified=False,
        mounting_hole_positions_verified=False, exact_foot_count_verified=False,
        exact_vent_pattern_modeled=False, selected_component_geometry_used=False,
        replaces_legacy_mod5_full_width_feet=True, chamber_is_solid=False,
        source_bottom_capacity=dict(count=3, size_mm=120),
        source_bottom_capacity_verified=True, bracket_thickness_reference_mm=1.2,
        bracket_center_y_reference_mm=-h/2+37.,
        bracket_outline_reference_mm=(140., 420.),
        original_ground_y_reference_mm=-h*.49-5.,
        reference_support_samples=4, reference_aperture_samples=1,
        source_frame_is_removable=True, mechanical_removal_direction_verified=False,
        layout_reference=layout_reference(case, dimensions),
        retained_tray_rail_reference=dict(pcb_x_mm=w*.36,prior_center_x_mm=w*.30,
            center_x_mm=w*.36+8.,behind_reference_board_mm=8.,
            positions_verified=False,tilt_verified=False),
        fan_mount_pose_unchanged=True, psu_mount_pose_verified=False,
        motherboard_mount_pose_verified=False)


def _translate(vertices, position):
    return tuple(value + position[index % 6] if index % 6 < 3 else value
                 for index, value in enumerate(vertices))


def build(case, dimensions, tone):
    """Three independent material batches; no installed hardware is invented."""
    meta = describe(case, dimensions)
    if not meta:
        return (), {}
    from assembly_geometry import Mesh, box, rotate_vertices
    from assembly_detail import perforated_plate
    w, h, d = map(float, dimensions)
    ground = -h*.49-5.
    supports = []
    # The old two full-width planks passed through the declared bottom bank.
    # These fixed outboard samples touch the retained lower-armour contour;
    # their form/count are explicitly unmeasured original drawing choices.
    for z, top in ((-d*.22, -h*.49+1.2), (d*.29, -h*.43+1.2)):
        for side in (-1., 1.):
            supports.extend(_translate(box(w*.08, top-ground, 42.),
                (side*w*.46, (ground+top)/2, z)))
    # The original low broad slab also filled the raised PSU bay. Retain
    # narrow side connections and its forward tie, but leave the rear open
    # as shown by the AC/exhaust and cassette views. The upper member remains
    # byte-identical in the exterior producer.
    for side in (-1., 1.):
        supports.extend(_translate(box(8., 9., d*.40),
            (side*(w*.42-4.), -h*.36, -d*.08)))
        reach = w/2-(w*.42-4.)
        supports.extend(_translate(box(reach, 9., 12.),
            (side*(w*.42-4.+reach/2), -h*.36, -d*.23)))
    supports.extend(_translate(box(w*.84-16., 9., 8.),
        (0., -h*.36, d*.12-4.)))
    # Local XY is the horizontal XZ frame; a proper rotation maps local +Z
    # to world -Y. The manual shows an open perimeter frame, not a solid
    # sheet with three painted fan disks. Its centre is real absent material.
    polygon = ((-70., -210.), (70., -210.), (70., 210.), (-70., 210.))
    holes = (((-55., -195.), (55., -195.), (55., 195.), (-55., 195.)),)
    sheet = rotate_vertices(perforated_plate(polygon, holes, 1.2,
        segments=16, clip_walls=True), 'down')
    y = meta['bracket_center_y_reference_mm']
    bracket = list(_translate(sheet, (0., y, 0.)))
    # Side ears terminate inside the existing armour, outside the fan bank.
    # They do not occupy the three cooling apertures or span the whole base.
    reach = w/2-70.
    for z in (-d*.20, d*.10):
        for side in (-1., 1.):
            bracket.extend(_translate(box(reach, 1.2, 12.),
                (side*(70.+reach/2), y, z)))
    layout = meta['layout_reference']['psu']
    floor, rear = layout['floor_y_mm'], layout['rear_z_mm']
    cradle = []
    # A fixed 150x86 ATX opening plus reference drawing margins. The model
    # never expands or carves around a selected PSU, fan or cable.
    rear_frame = perforated_plate(((-89., -13.), (89., -13.), (89., 99.), (-89., 99.)),
        (((-77., -2.), (77., -2.), (77., 88.), (-77., 88.)),), 1.2, clip_walls=True)
    cradle.extend(_translate(rear_frame, (0., floor, rear-2.)))
    for side in (-1., 1.):
        # Fixed ATX bearing lands are within its nominal150mm lower skin,
        # not outside it. The reference rear frame is not the only support.
        cradle.extend(_translate(box(5., 1.2, 220.),
            (side*67.5, floor-.6, rear+110.)))
        x = side*(w*.42-4.)
        reach = abs(x)-67.5
        cradle.extend(_translate(box(reach, 1.2, 12.),
            (side*(67.5+reach/2), floor-.6, -d*.23)))
        top = -h*.36-4.5
        cradle.extend(_translate(box(8., top-(floor-1.2), 12.),
            (x, (top+floor-1.2)/2, -d*.23)))
    meshes = (Mesh('case-mod5-perimeter-base-supports', tuple(supports), tone,
                   component='case', part_id=SUPPORT_ID),
              Mesh('case-mod5-open-bottom-fan-bracket', tuple(bracket), tone,
                   component='case', part_id=BRACKET_ID),
              Mesh('case-mod5-raised-open-psu-cradle', tuple(cradle), tone,
                   component='case', part_id=CRADLE_ID))
    return meshes, meta
