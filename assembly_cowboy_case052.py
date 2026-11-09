"""Exact Model 8 CowBoy interior reference, not a conventional PSU tunnel.

The manufacturer family guide explicitly applies to every Model 8 finish.
Its fixed top-I/O tray, front-upper PSU and open bottom mounting floor are
shared installation facts. CowBoy's leather/aluminium exterior is untouched.
Unlabelled positions, sheet thickness and slot sampling are original reference
coordinates, never manufacturing dimensions or a chosen-component cutout.
"""
import math

EXACT_ID = 'geometric-future-model-8-cowboy'
PRODUCT = 'https://www.geometricfuture.com/product-1/3'
MANUAL = 'https://www.geometricfuture.com/uploads/20210512/M8-Dharma-Manual.pdf'
SOURCES = (PRODUCT, MANUAL)
# Columns: local X/Y/Z in world axes. det +1; local AC -Z becomes world +Y.
TOP_IO_BASIS = ((1., 0., 0.), (0., 0., 1.), (0., -1., 0.))
_FLOOR_BASIS = ((1., 0., 0.), (0., 0., -1.), (0., 1., 0.))
_SIDE_BASIS = ((0., 0., -1.), (0., 1., 0.), (1., 0., 0.))


def _valid(case, dimensions):
    return (isinstance(case, dict) and case.get('id') == EXACT_ID
            and isinstance(dimensions, (tuple, list)) and len(dimensions) == 3
            and all(type(v) in (int, float) and math.isfinite(v) for v in dimensions)
            and 60 <= dimensions[0] <= 800 and 60 <= dimensions[1] <= 900
            and 150 <= dimensions[2] <= 900)


def _rectangle(x0, x1, y0, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _plate(polygon, holes, thickness, origin, basis):
    from assembly_detail import perforated_plate
    local = perforated_plate(polygon, holes, thickness, segments=8, clip_walls=True)
    result = []
    for index in range(0, len(local), 6):
        for offset in (0, 3):
            point = local[index + offset:index + offset + 3]
            result.extend(sum(point[k] * basis[k][axis] for k in range(3))
                          + (origin[axis] if offset == 0 else 0.) for axis in range(3))
    return tuple(result)


def layout_reference(case, dimensions):
    """Finite host contract; caller rigidly poses actual hardware and anchors.

    board_pose is Ctarget + R * (Pcanonical - Ccanonical), where
    Ctarget=(old board X, io_y-board_width/2, rear_z+board_height/2).
    The shared host must transform CPU/RAM/GPU/board and every attachment
    anchor together. Merely changing the shell or rotating about world zero
    leaves the actual top I/O in the wrong place.

    PSU center=(0, ceiling-world_height/2, front-world_depth/2). World size is
    (actual PSU width, actual PSU length, actual PSU housing height); no size
    is changed. Intake direction is only an installation drawing reference.
    """
    if not _valid(case, dimensions):
        return {}
    w, h, d = map(float, dimensions)
    floor_top = -h / 2. + 20.
    return dict(case_id=EXACT_ID, source=MANUAL, source_urls=SOURCES,
                reference_only=True, verified=False, cad_verified=False,
                dimensions_verified=False, positions_verified=False,
                board_pose=dict(kind='top_io_90', io_y_mm=h * .40,
                    rear_z_mm=-d / 2. + 18., source=MANUAL,
                    positions_verified=False, reference_only=True,
                    source_manual_pdf_pages=(8, 9),
                    rigid_basis_reference=TOP_IO_BASIS,
                    transform_components=('board', 'cpu', 'memory', 'gpu'),
                    transform_attachment_anchors=True),
                psu=dict(basis=TOP_IO_BASIS, ceiling_y_mm=h * .40,
                    front_z_mm=d / 2. - 12., center_x_mm=0.,
                    source=MANUAL, source_manual_pdf_pages=(21, 22),
                    reference_only=True, positions_verified=False,
                    ac_world_normal_reference=(0., 1., 0.),
                    fan_world_normal_reference=(0., 0., -1.),
                    fan_orientation_verified=False,
                    source_length_limit_mm_exclusive=220.),
                floor_top_y_mm=floor_top,
                mount_planes=dict(bottom=dict(position=(0., floor_top + 1., 0.),
                    normal=(0., -1., 0.), up=(0., 0., 1.),
                    span_mm=(w - 24., d - 32.), source=MANUAL,
                    source_manual_pdf_page=19, source_capacity_count=3,
                    source_capacity_sizes_mm=(120, 140),
                    reference_only=True, positions_verified=False,
                    dimensions_verified=False, verified=False,
                    drawing_gap_mm=1., drawing_gap_verified=False)))


def build(case, dimensions, tone):
    """Return fixed thin material and detached case-part provenance only.

    No component choices, fan count, GPU size or LOD are read from case. The
    caller replaces its old bottom slab AND old PSU tunnel, then consumes the
    pose contract; these three material pieces alone are not full-host fit.
    """
    if not _valid(case, dimensions):
        return (), {}
    from assembly_geometry import Mesh
    w, h, d = map(float, dimensions)
    layout = layout_reference(case, dimensions)
    left, right = -(w - 12.) / 2., (w - 12.) / 2.
    rear, front = -(d - 12.) / 2., (d - 12.) / 2.
    thickness = 1.2
    floor_top = layout['floor_top_y_mm']
    upper, lower, bay_rear = h * .40, -h * .16, d * .28
    meshes, parts = [], []

    def add(identity, name, label, vertices, role, kind, pages):
        if not vertices:
            raise ValueError('Observed CowBoy material must not silently vanish')
        meshes.append(Mesh(name, vertices, tuple(tone), component='case', part_id=identity))
        parts.append(dict(id=identity, label=label, kind=kind, component='case',
            model_id=EXACT_ID, assembly_state='installed',
            geometry_status='official_photo_reference', observed_role=role,
            source_url=PRODUCT, source_urls=SOURCES, source_manual_pdf_pages=pages,
            positions_verified=False, dimensions_verified=False,
            reference_only=True, cad_verified=False,
            power_sensor_bound=False, display_screen=False))

    # PDF9/21: only the observed near-side folded vertical skin. Leave the
    # PSU bay's interior/end open; never fabricate an unseen far duplicate
    # or a filled solid volume behind this skin.
    skin = _plate(_rectangle(-front, -bay_rear, lower, upper), (), thickness,
                  (left + thickness / 2., 0., 0.), _SIDE_BASIS)
    add('case:psu-cover', 'psu-shroud', 'Model 8 CowBoy 前上电源侧皮', skin,
        'thin_front_upper_psu_bay_viewing_side_skin', 'case_cover', (9, 21, 22))

    # PDF21: an open AC mounting frame, above the PSU, not a cap through its
    # body. The fixed rectangular opening is reference material layout; no
    # screw pattern or PSU-specific IEC aperture is claimed or selected.
    opening = _rectangle(-w * .31, w * .31, -(front - 12.), -(bay_rear + 18.))
    mount = _plate(_rectangle(left, right, -front, -bay_rear), (opening,), thickness,
                   (0., upper + thickness / 2., 0.), _FLOOR_BASIS)
    add('case:front-psu-mount', 'case-front-psu-mount', 'Model 8 CowBoy 顶向电源安装框', mount,
        'open_front_upper_ac_mount_support', 'case_structure', (21, 22))

    # PDF19: broad real slots and narrow supporting webs, with the filter
    # below. Five samples describe the visible slot field, not a measured
    # factory aperture count or exact mounting-hole positions.
    usable_rear, usable_front = rear + 16., front - 16.
    pitch = (usable_front - usable_rear) / 5.
    holes = tuple(_rectangle(left + 14., right - 14.,
                    -(usable_rear + (i + 1) * pitch - 3.),
                    -(usable_rear + i * pitch + 3.)) for i in range(5))
    floor = _plate(_rectangle(left, right, -front, -rear), holes, thickness,
                   (0., floor_top - thickness / 2., 0.), _FLOOR_BASIS)
    add('case:bottom-intake-frame', 'case-bottom-intake-frame', 'Model 8 CowBoy 开放底部安装架', floor,
        'slotted_bottom_fan_radiator_support', 'case_structure', (19,))

    triangles = sum(mesh.vertex_count // 3 for mesh in meshes)
    if len(meshes) > 3 or triangles > 1200:
        raise ValueError('CowBoy fixed material exceeded finite construction budget')
    meta = dict(case_id=EXACT_ID, parts=parts, removed_parts=[],
        source_urls=SOURCES, source_manual_pdf_pages=(8, 9, 19, 21, 22),
        geometry_status='official_photo_reference', reference_only=True,
        dimensions_verified=False, positions_verified=False, thickness_verified=False,
        cad_verified=False, selected_component_geometry_used=False,
        chamber_is_solid=False, horizontal_psu_cover_present=False,
        front_upper_psu_bay_observed=True, far_side_wall_added=False,
        mainboard_rotation_requires_exact_host_pose=True,
        psu_layout_requires_exact_host_pose=True,
        replaces_case_bottom=True, replaces_generic_psu_shroud=True,
        thickness_mm=thickness, floor_top_y_mm=floor_top,
        front_bay_reference_mm=dict(rear_z=bay_rear, front_z=front,
            bottom_y=lower, top_y=upper, near_side_x=left),
        exact_vent_pattern_modeled=False, exact_fixings_modeled=False,
        source_mounts_are_capacities_not_installed_fans=True,
        assembly_state='installed', mesh_count=len(meshes), triangle_count=triangles,
        unknown=['Internal mount datums, thickness and vent density are reference.',
                 'PSU intake roll/clearance is not mechanically verified.',
                 'Top I/O/bracket pose and whole-host collision must be consumed and tested.',
                 'Bottom cooling changes the source GPU-length limit.'])
    return tuple(meshes), meta
