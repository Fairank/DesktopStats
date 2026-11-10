"""Fixed COSMOS C700M body, tray and regular lower-assembly references.

The C700M manual PDF20/22 shows a separate cooling frame and declares only
two bottom 120/140 fans. The store's universal bracket photograph supplies
folded/slotted construction cues, not exact stock geometry or dimensions.
All sheet sizes, sampling, positions and drawing gaps below are original
reference coordinates. No selected component is an input to their shape.
The external wrap handles do not define the internal motherboard rear datum.
Rear I/O/PCIe machining and alternative PSU/tray orientations remain unverified.
"""
from copy import deepcopy
import math

EXACT_ID = 'cooler-master-cosmos-c700m'
FLOOR_ID = 'case:cosmos-bottom-intake-floor'
BRACKET_ID = 'case:cosmos-bottom-cooling-bracket'
SUPPORT_ID = 'case:cosmos-regular-psu-support'
TRAY_ID = 'case:tray'
PRODUCT = 'https://www.coolermaster.com/en-au/products/cosmos-c700m.html'
MANUAL = 'https://coolermaster.egnyte.com/dl/5drrDN4vIT'
ACCESSORY = 'https://store.coolermaster.eu/products/cooling-bracket-cosmos-c700p'
SOURCES = (PRODUCT, MANUAL, ACCESSORY)
IDENTITY = ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.))
FLOOR_BASIS = ((1., 0., 0.), (0., 0., -1.), (0., 1., 0.))


def _valid(case, dimensions):
    return (isinstance(case, dict) and case.get('id') == EXACT_ID
            and isinstance(dimensions, (tuple, list)) and len(dimensions) == 3
            and all(type(v) in (int, float) and math.isfinite(v) for v in dimensions)
            and 250 <= dimensions[0] <= 380 and 550 <= dimensions[1] <= 760
            and 550 <= dimensions[2] <= 760)


def _rect(x0, x1, y0, y1, bevel=0.):
    if not bevel:
        return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    b = min(bevel, (x1 - x0) / 3., (y1 - y0) / 3.)
    return ((x0 + b, y0), (x1 - b, y0), (x1, y0 + b),
            (x1, y1 - b), (x1 - b, y1), (x0 + b, y1),
            (x0, y1 - b), (x0, y0 + b))


def _plate(polygon, holes, thickness, y, z=0.):
    from assembly_detail import perforated_plate
    values = perforated_plate(polygon, holes, thickness, segments=8, clip_walls=True)
    result = []
    for start in range(0, len(values), 6):
        for offset in (0, 3):
            point = values[start + offset:start + offset + 3]
            origin = (0., y, z) if offset == 0 else (0., 0., 0.)
            result.extend(sum(point[k] * FLOOR_BASIS[k][axis] for k in range(3))
                          + origin[axis] for axis in range(3))
    return tuple(result)


def _translated_box(size, position):
    from assembly_geometry import box
    return tuple(value + position[index % 6] if index % 6 < 3 else value
                 for index, value in enumerate(box(*size)))


def _reference(dimensions):
    w, h, d = map(float, dimensions)
    # The existing C700M BODY floor, not the outer handle/foot extremum.
    body_w, body_d = w * .88, d * .94
    floor_top = -h * .44 + 1.5
    # Fixed drawing references: neither follows fan thickness nor PSU length.
    bracket_top = floor_top + 8.
    bracket_width, bracket_length = 166., 454.
    bracket_front = body_d / 2. - 12.
    bracket_z = bracket_front - bracket_length / 2.
    bottom_span = (150., 300.)
    bottom_z = bracket_front - 150.
    return dict(body_width_mm=body_w, body_depth_mm=body_d,
                floor_top_y_mm=floor_top, floor_thickness_mm=1.2,
                bracket_top_y_mm=bracket_top, bracket_width_mm=bracket_width,
                bracket_length_mm=bracket_length, bracket_center_z_mm=bracket_z,
                bottom_plane_position=(0., bracket_top + 1., bottom_z),
                bottom_plane_span_mm=bottom_span,
                psu_floor_y_mm=floor_top + 14.,
                psu_rear_z_mm=-body_d / 2. + 3.)


def floor_mesh(case, dimensions, tone):
    """Replace only the old 3-mm floor primitive; never the shared rear wall."""
    if not _valid(case, dimensions):
        return None
    from assembly_geometry import Mesh
    r = _reference(dimensions)
    x, z = r['body_width_mm'] / 2., r['body_depth_mm'] / 2.
    # Sixteen sampled open cells stand for the manual's ventilated lower
    # lattice. Cell shape/count are reference sampling, not exact hex CAD.
    holes = []
    for column in (-1., 1.):
        for row in range(8):
            cx, cz = column * x * .42, (row - 3.5) * (2. * z - 54.) / 8.
            holes.append(_rect(cx - x * .35, cx + x * .35,
                               cz - (2. * z - 54.) / 8. * .43,
                               cz + (2. * z - 54.) / 8. * .43, 6.))
    vertices = _plate(_rect(-x, x, -z, z), holes,
                      r['floor_thickness_mm'],
                      r['floor_top_y_mm'] - r['floor_thickness_mm'] / 2.)
    return Mesh('case-cosmos-reference-open-bottom-floor', vertices, tuple(tone),
                component='case', part_id=FLOOR_ID)


def _bracket_mesh(dimensions, tone):
    from assembly_geometry import Mesh
    r = _reference(dimensions)
    x, z = r['bracket_width_mm'] / 2., r['bracket_length_mm'] / 2.
    holes = [_rect(-50., 50., -209., 209., 5.)]
    # Two reference slot lanes on each long rail. They remain genuine open
    # slots; count, lane pitch and screw centres are explicitly unverified.
    for side in (-1., 1.):
        for lane in (53., 63.):
            for start, end in ((-205., -5.), (5., 205.)):
                holes.append(_rect(side * lane - 2.5, side * lane + 2.5,
                                   start, end, 2.4))
    for end in (-1., 1.):
        holes.append(_rect(-25., 25., end * 219. - 2.5, end * 219. + 2.5, 2.4))
    thickness = 1.2
    values = list(_plate(_rect(-x, x, -z, z, 5.), holes, thickness,
                         r['bracket_top_y_mm'] - thickness / 2.,
                         r['bracket_center_z_mm']))
    # Folded side lips meet the plate at its underside. End attachment ears
    # are separate solid sheet regions in this same selectable bracket part.
    for side in (-1., 1.):
        values.extend(_translated_box((thickness, 4.8, 444.),
            (side * (x - thickness / 2.), r['bracket_top_y_mm'] - thickness - 2.4,
             r['bracket_center_z_mm'])))
        for end in (-1., 1.):
            values.extend(_translated_box((7., thickness, 16.),
                (side * (x + 3.5), r['bracket_top_y_mm'] - thickness / 2.,
                 r['bracket_center_z_mm'] + end * (z - 13.))))
    return Mesh('case-cosmos-reference-bottom-cooling-bracket', tuple(values),
                tuple(tone), component='case', part_id=BRACKET_ID)


def _psu_support_mesh(dimensions, tone):
    """Two fixed regular-ATX edge supports, not a selected PSU-shaped cavity."""
    from assembly_geometry import Mesh
    r = _reference(dimensions)
    height = r['psu_floor_y_mm'] - r['floor_top_y_mm']
    rear = -r['body_depth_mm'] / 2. + 6.
    # This short rear support stops before the independent cooling bracket.
    # Edge rails leave the down-facing PSU fan intake open. All coordinates
    # are authored references, not the manufacturer's unlabelled pad centres.
    vertices = tuple(value for x in (-73., 73.) for value in _translated_box(
        (4., height, 130.), (x, r['floor_top_y_mm'] + height / 2., rear + 65.)))
    return Mesh('case-cosmos-regular-psu-edge-support-reference', vertices,
                tuple(tone), component='case', part_id=SUPPORT_ID)


def layout_reference(case, dimensions):
    if not _valid(case, dimensions):
        return {}
    r = _reference(dimensions)
    return dict(case_id=EXACT_ID, source=MANUAL, source_urls=SOURCES,
                reference_only=True, positions_verified=False,
                dimensions_verified=False, manufacturing_fit_verified=False,
                board_rear_z_mm=-r['body_depth_mm'] / 2. + 14.,
                board_rear_datum='fixed_body_rear_not_outer_wrap_extremum',
                routing_body_dimensions_mm=(r['body_width_mm'], float(dimensions[1]) * .88, r['body_depth_mm']),
                routing_body_bounds_verified=False,
                board_positions_verified=False,
                rear_io_and_pcie_apertures_modelled=False,
                body_floor_reference=deepcopy(r),
                psu=dict(basis=IDENTITY, floor_y_mm=r['psu_floor_y_mm'],
                    rear_z_mm=r['psu_rear_z_mm'], center_x_mm=0., source=MANUAL,
                    source_manual_pdf_pages=(7, 8), source_role='regular_rear_bottom_ATX',
                    ac_world_normal_reference=(0., 0., -1.),
                    fan_world_normal_reference=(0., -1., 0.),
                    fan_orientation_verified=False, positions_verified=False,
                    support_height_reference_mm=14., support_height_verified=False),
                mount_planes=dict(bottom=dict(position=r['bottom_plane_position'],
                    normal=(0., -1., 0.), up=(0., 0., 1.),
                    span_mm=r['bottom_plane_span_mm'], source=MANUAL,
                    source_manual_pdf_page=22, source_capacity_count=2,
                    source_capacity_sizes_mm=(120, 140), reference_only=True,
                    positions_verified=False, dimensions_verified=False,
                    drawing_gap_mm=1., drawing_gap_verified=False,
                    required_reference_part_id=BRACKET_ID,
                    usable_region_not_complete_bracket_envelope=True)),
                fan_constraints=dict(bottom=dict(case_id=EXACT_ID,
                    source_url=MANUAL, source_manual_pdf_page=22,
                    max_count_by_size_mm={'120': 2, '140': 2})),
                bottom_radiator_reference=dict(normal_nominal_sizes_mm=(120, 140, 240),
                    conditional_nominal_sizes_mm=(360,), bottom_360_supported=False,
                    requires_alternative_psu_location=True,
                    alternative_psu_pose_verified=False, source=MANUAL,
                    source_manual_pdf_page=22,
                    construction_guard='fixed_300mm_usable_plane_rejects_360_without_rescaling'))


def build(case, dimensions, tone):
    """Return fixed floor plus a deferred *candidate* bracket and plain metadata.

    The bracket is NOT assumed installed. Shared host excludes the deferred
    candidate from cooling blockers, then finish retains it only when actual
    generated bottom hardware requires it. It is reused/optional reference,
    never a detected third stock bracket.
    """
    if not _valid(case, dimensions):
        return (), {}
    floor, bracket = floor_mesh(case, dimensions, tone), _bracket_mesh(dimensions, tone)
    support = _psu_support_mesh(dimensions, tone)
    parts = []
    for mesh, label, state, pages in (
            (floor, 'C700M ventilated body floor reference', 'installed', (7, 20)),
            (support, 'C700M regular rear ATX edge-support reference', 'installed', (7, 8)),
            (bracket, 'C700M reused or optional bottom cooling bracket reference',
             'reference_candidate_not_installed', (20, 22))):
        parts.append(dict(id=mesh.part_id, label=label, kind='case_structure',
            component='case', model_id=EXACT_ID, assembly_state=state,
            geometry_status='official_photo_reference', source_urls=SOURCES,
            source_manual_pdf_pages=pages, positions_verified=False,
            dimensions_verified=False, thickness_verified=False, slot_centres_verified=False,
            manufacturer_cad=False, selected_component_geometry_used=False))
    meta = dict(case_id=EXACT_ID, source=MANUAL, source_urls=SOURCES,
        reference_only=True, positions_verified=False, dimensions_verified=False,
        thickness_verified=False, chamber_is_solid=False, selected_component_geometry_used=False,
        replaces_full_shell_floor_primitive=True, preserves_batched_rear_wall=True,
        keep_in_full_shell_replacement_part_ids=(FLOOR_ID, SUPPORT_ID),
        deferred_part_ids=(BRACKET_ID,), bracket_installed=False,
        bracket_inventory_detected=False, included_brackets_documented=2,
        reference_bracket_origin='reuse_or_optional_unknown_not_third_stock',
        accessory_photo_is_not_identical_stock_geometry=True,
        bottom_capacity_count=2, bottom_capacity_sizes_mm=(120, 140),
        normal_bottom_radiator_mm=(120, 140, 240), bottom_360_supported=False,
        alternate_psu_pose_verified=False, parts=parts,
        floor_reference=deepcopy(_reference(dimensions)),
        floor_sampling='sixteen_qualitative_open_lattice_cells_not_actual_hole_count',
        slot_sampling='bounded_long_slots_not_exact_manufacturing_positions',
        maximum_candidate_triangles=4096)
    triangles = sum(mesh.vertex_count // 3 for mesh in (floor, bracket, support))
    if triangles > meta['maximum_candidate_triangles']:
        raise ValueError('C700M reference exceeded its fixed construction budget')
    meta['candidate_triangle_count'] = triangles
    return (floor, support, bracket), meta


def finish(meshes, cooling_meshes, cooling_meta, metadata):
    """Presence selection only: never change a point, pose or fan/PSU size."""
    if not isinstance(metadata, dict) or metadata.get('case_id') != EXACT_ID:
        return meshes, metadata
    meta = deepcopy(metadata)
    parts = cooling_meta.get('parts', ()) if isinstance(cooling_meta, dict) else ()
    actual_ids = {m.part_id for m in cooling_meshes}
    actual_bottom = any(isinstance(p, dict) and p.get('mount') == 'bottom'
                        and p.get('kind') in ('case_fan', 'radiator')
                        and p.get('id') in actual_ids for p in parts)
    bracket_count = sum(m.part_id == BRACKET_ID for m in meshes)
    if actual_bottom and bracket_count != 1:
        # Host integration error must be explicit, never silently draw a fan
        # unsupported by its required authored reference assembly part.
        raise ValueError('Actual C700M bottom assembly requires exactly one deferred bracket')
    result = tuple(m for m in meshes if actual_bottom or m.part_id != BRACKET_ID)
    meta['bracket_installed'] = actual_bottom
    meta['parts'] = [dict(p, assembly_state='installed',
        inventory_status='reused_or_optional_reference_not_detected')
        if p['id'] == BRACKET_ID else p for p in meta['parts']
        if p['id'] != BRACKET_ID or actual_bottom]
    meta['deferred_part_ids'] = ()
    meta['actual_case_structure_triangles'] = sum(m.vertex_count // 3 for m in result
        if m.part_id in (FLOOR_ID, SUPPORT_ID, TRAY_ID, BRACKET_ID))
    return result, meta


def add_tray(meshes, case, dimensions):
    """A fixed pierced modular-tray reference, with matching solid cells.

    Manual PDF6/20 shows the access window and cable passages. Their sizes,
    sheet thickness and tie positions are original reference proportions;
    no selected board, socket, wire or desired clearance changes the cutouts.
    """
    if not _valid(case, dimensions):
        return meshes, {}
    from assembly_geometry import Mesh, _quad
    w, h, d = map(float, dimensions)
    r = _reference(dimensions)
    board_x, board_y = w * .36, h * .02
    rear = -r['body_depth_mm'] / 2. + 14.
    x, thickness = board_x + 8., 1.2
    y0, y1 = board_y - 305. / 2. - 20., board_y + 305. / 2. + 22.
    z0, z1 = rear - 7., r['body_depth_mm'] * .15
    column = rear + 244. + 40.
    holes = [dict(role='cpu_backplate_access', z0=rear + 15., z1=rear + 195.,
                  y0=board_y + 5., y1=board_y + 165.)]
    for center, height in ((board_y + 88., 100.), (board_y - 72., 110.)):
        holes.append(dict(role='vertical_cable_passage', z0=column - 15., z1=column + 15.,
                          y0=center - height / 2., y1=center + height / 2.))
    for a, b in ((rear + 15., rear + 115.), (rear + 145., column + 20.)):
        holes.append(dict(role='top_edge_cable_passage', z0=a, z1=b,
                          y0=board_y + 305. / 2. + 2., y1=y1 + 1.))
    zs = sorted({z0, z1, *[max(z0, min(z1, hole[k])) for hole in holes for k in ('z0', 'z1')]})
    ys = sorted({y0, y1, *[max(y0, min(y1, hole[k])) for hole in holes for k in ('y0', 'y1')]})
    solid = set()
    for j, (low, high) in enumerate(zip(ys, ys[1:])):
        for i, (a, b) in enumerate(zip(zs, zs[1:])):
            cy, cz = (low + high) / 2., (a + b) / 2.
            if not any(hole['y0'] < cy < hole['y1'] and hole['z0'] < cz < hole['z1'] for hole in holes):
                solid.add((i, j))
    vertices = []
    rectangles = []
    for i, j in sorted(solid):
        low, high = ys[j:j+2]
        a, b = zs[i:i+2]
        front = ((x-thickness/2., low, a), (x-thickness/2., low, b),
                 (x-thickness/2., high, b), (x-thickness/2., high, a))
        back = tuple((x+thickness/2., point[1], point[2]) for point in front)
        _quad(vertices, *front)
        _quad(vertices, *reversed(back))
        for edge, neighbour in enumerate(((i, j-1), (i+1, j), (i, j+1), (i-1, j))):
            if neighbour not in solid:
                following = (edge + 1) % 4
                _quad(vertices, front[edge], back[edge], back[following], front[following])
    for j in range(len(ys)-1):
        start = None
        for i in range(len(zs)):
            if (i, j) in solid and start is None:
                start = i
            if (i, j) not in solid and start is not None:
                rectangles.append((zs[start], zs[i], ys[j], ys[j+1]))
                start = None
    merged = []
    for a, b, low, high in rectangles:
        previous = next((i for i, row in enumerate(merged) if row[:2] == (a, b) and row[3] == low), None)
        if previous is None:
            merged.append((a, b, low, high))
        else:
            merged[previous] = (a, b, merged[previous][2], high)
    bounds = [dict(min=(x-thickness/2., low, a), max=(x+thickness/2., high, b))
              for a, b, low, high in merged]
    # Fixed small attachment ties touch the retained side skin and tray back.
    # They never enter the motherboard side or vary with the selected board.
    side_inner = r['body_width_mm'] / 2. - 1.
    tie_width = side_inner - (x + thickness / 2.)
    if tie_width <= 0:
        raise ValueError('C700M tray reference lies outside its retained body')
    for cy in (y0 + 8., y1 - 8.):
        for cz in (z0 + 12., z1 - 12.):
            center = (x + thickness / 2. + tie_width / 2., cy, cz)
            size = (tie_width, 6., 10.)
            vertices.extend(_translated_box(size, center))
            bounds.append(dict(min=tuple(center[k]-size[k]/2. for k in range(3)),
                               max=tuple(center[k]+size[k]/2. for k in range(3))))
    mesh = Mesh('case-cosmos-motherboard-tray-reference', tuple(vertices), (.27, .31, .35, 1.),
                component='case', part_id=TRAY_ID)
    if mesh.vertex_count // 3 > 2048 or len(bounds) > 64:
        raise ValueError('C700M tray exceeded its fixed reference budget')
    part = dict(id=TRAY_ID, label='C700M modular tray reference', kind='case_structure', component='case',
                model_id=EXACT_ID, assembly_state='installed', source_urls=SOURCES,
                source_manual_pdf_pages=(6, 20), positions_verified=False, dimensions_verified=False,
                manufacturer_cad=False, selected_component_geometry_used=False)
    meta = dict(case_id=EXACT_ID, plane_x_mm=x, thickness_mm=thickness,
                bounds=dict(min=(x-thickness/2., y0, z0), max=(side_inner, y1, z1)),
                openings=holes, solid_bounds=bounds, collision_method='fixed_rectangular_plate_and_tie_cells',
                method='official_manual_observed_modular_tray_reference', manual=MANUAL,
                manual_pages=(6, 20), sources=SOURCES, parts=[part],
                dimensions_verified=False, mounting_holes_verified=False, cad_verified=False,
                factory_hole_positions_verified=False, plane_is_reference=True,
                front_entry_z_mm=z1+18., top_lane_y_mm=board_y+305./2.+8.,
                cable_columns_z_mm=(column,), fixed_ties_to_retained_side_skin=True,
                selected_component_geometry_used=False, rear_io_and_pcie_apertures_modelled=False)
    return tuple((*meshes, mesh)), meta
