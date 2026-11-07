"""Bounded, original radiator shells and sampled cores; no fans or device I/O.

The documented envelope, connection count and thread label belong to the input
profile. Wall gauges, shoulders, throat radii and the sampled tube/louver core
remain reference construction, not vendor CAD, FPI or a manufacturing drawing.
All geometry is static and batched; the caller owns parts, fans, hoses and pumps.
Original code/art: PolyForm Noncommercial 1.0.0; third-party rights are unchanged.
"""
import math


TRIANGLE_BUDGETS = {'eco': 2800, 'balanced': 6500, 'close': 12500}
_LOD = {'eco': (8, 6, 18), 'balanced': (12, 11, 40), 'close': (16, 15, 64)}
_FACES = {'front': (0., 0., 1.), 'rear': (0., 0., -1.),
          'left': (-1., 0., 0.), 'right': (1., 0., 0.)}
_IDENTITY = ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.))


def _add(a, b): return tuple(x + y for x, y in zip(a, b))
def _sub(a, b): return tuple(x - y for x, y in zip(a, b))
def _mul(a, value): return tuple(x * value for x in a)
def _dot(a, b): return sum(x * y for x, y in zip(a, b))
def _cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def _finite(value): return type(value) in (int, float) and math.isfinite(value)


def _vector(value):
    if not isinstance(value, (tuple, list)) or len(value) != 3 or not all(_finite(x) for x in value):
        raise ValueError('Radiator vectors must have three finite numeric values')
    return tuple(float(x) for x in value)


def _basis(value):
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise ValueError('Radiator basis must contain three orthonormal axes')
    axes = tuple(_vector(axis) for axis in value)
    if (any(abs(_dot(axis, axis)-1.) > 1e-6 for axis in axes)
            or any(abs(_dot(axes[a], axes[b])) > 1e-6 for a, b in ((0, 1), (0, 2), (1, 2)))
            or _dot(_cross(axes[0], axes[1]), axes[2]) < 1.-1e-6):
        raise ValueError('Radiator basis must be an orientation-preserving rigid frame')
    return axes


def _world(point, center, basis, direction=False):
    result = tuple(sum(point[k]*basis[k][j] for k in range(3)) for j in range(3))
    return result if direction else _add(result, center)


def _transform(vertices, center, basis):
    result = []
    for n in range(0, len(vertices), 6):
        result.extend(_world(vertices[n:n+3], center, basis))
        result.extend(_world(vertices[n+3:n+6], center, basis, True))
    return result


def _dimensions(value):
    if not isinstance(value, dict): raise ValueError('Radiator dimensions must be a mapping')
    result = tuple(value.get(key) for key in ('length', 'width', 'thickness'))
    if not all(_finite(x) for x in result): raise ValueError('Radiator dimensions must be finite numbers')
    if not (80 <= result[0] <= 800 and 65 <= result[1] <= 250 and 12 <= result[2] <= 100):
        raise ValueError('Radiator envelope is outside the bounded reference range')
    return tuple(float(x) for x in result)


def _tint(profile, key, default):
    value = profile.get(key, default)
    if isinstance(value, str) and len(value) == 7 and value[0] == '#':
        try: int(value[1:], 16); return value
        except ValueError: pass
    return default


def _capsule(x, y, radius, half_length, segments):
    # Rounded mounting slots are missing geometry, not a painted ellipse.
    half = max(3, segments//2-1)
    return tuple((x+radius*math.cos(angle), y+offset+radius*math.sin(angle))
                 for offset, angles in ((half_length, (i*math.pi/half for i in range(half+1))),
                                        (-half_length, (math.pi+i*math.pi/half for i in range(half+1))))
                 for angle in angles)


def _ports(profile, dimensions):
    length, width, thickness = dimensions
    raw = profile.get('ports', ())
    if not isinstance(raw, (tuple, list)) or len(raw) > 12:
        raise ValueError('Radiator ports must be a bounded list')
    count = profile.get('ports_count')
    if count is not None and (type(count) is not int or not 0 <= count <= 12):
        raise ValueError('Radiator total port count is invalid')
    if count is not None and len(raw) > count: raise ValueError('Port observations exceed the documented total')
    thread = profile.get('port_thread')
    known_thread = (profile.get('port_thread_verified') is True and isinstance(thread, str)
                    and thread.replace(' ', '').casefold() in ('g1/4', 'g1/4bspp', 'g1/4inch'))
    result = []; unknown = []
    if not raw and count: unknown.append('Individual port positions are unknown; no mouths inferred from ports_count')
    if raw and not known_thread:
        unknown.append('Thread is not explicitly verified G1/4; port observations retained as metadata only')
        return [], unknown
    seen = set()
    for index, row in enumerate(raw):
        if not isinstance(row, dict): raise ValueError('Each radiator port must be a mapping')
        identity = row.get('id', 'port-'+str(index+1))
        if not isinstance(identity, str) or not identity or len(identity) > 96 or identity in seen:
            raise ValueError('Radiator port IDs must be unique bounded strings')
        seen.add(identity); face = row.get('face'); normal = _FACES.get(face)
        if face == 'end':
            end = row.get('end')
            if type(end) is not int or end not in (-1, 1): raise ValueError('End ports require an explicit +1/-1 end')
            normal = (0., float(end), 0.)
        if normal is None: raise ValueError('Radiator port face is unknown')
        normalized = _vector(row.get('position_normalized'))
        if any(abs(x) > .500001 for x in normalized): raise ValueError('Port observations must lie within normalized envelope ±.5')
        axis = next(i for i, x in enumerate(normal) if x)
        if abs(normalized[axis]-normal[axis]*.5) > .035:
            raise ValueError('Port observation does not match its declared surface')
        point = [normalized[0]*width, normalized[1]*length, normalized[2]*thickness]
        point[axis] = normal[axis]*(width, length, thickness)[axis]/2
        capped = row.get('capped', False)
        if type(capped) is not bool: raise ValueError('Port capped state must be explicit boolean')
        result.append(dict(id=identity, face=face, normal=normal, local_position=tuple(point),
                           position_normalized=normalized, role=row.get('role', 'unknown'),
                           positions_verified=row.get('positions_verified') is True,
                           source=row.get('source'), thread=thread, capped=capped))
    if count is not None and len(result) < count:
        unknown.append('Some documented ports have no observed position and are not invented')
    return result, unknown


def _plate(poly, holes, depth, center, basis, segments):
    from assembly_detail import perforated_plate
    return _transform(perforated_plate(poly, holes, depth, segments=segments), center, basis)


def _fin_segment(a, b, depth, louver=False):
    """A sampled zero-thickness foil, not a thick solid triangular shutter.

    The renderer already draws unculled thin surfaces. A single well-defined
    normal/winding avoids coincident reversed faces and spends the budget on
    closer folds instead of invisible tiny side walls. No foil gauge is claimed.
    """
    from assembly_geometry import _quad
    levels = (-depth/2, -depth*.10, depth*.10, depth/2) if louver else (-depth/2, depth/2)
    offsets = (0., .28, -.28, 0.) if louver else (0., 0.)
    points = [((a[0], a[1]+shift, z), (b[0], b[1]+shift, z)) for z,shift in zip(levels,offsets)]
    out = []
    for lower, upper in zip(points, points[1:]):
        _quad(out, lower[0], lower[1], upper[1], upper[0])
    return out


def _foil_plate(poly, holes, center, basis, segments):
    """One genuinely pierced thin face; unverified metal gauge is not modelled."""
    from assembly_detail import perforated_plate
    full = perforated_plate(poly, holes, .1, segments=segments)
    top = []
    for n in range(0,len(full),18):
        if full[n+5] > .999:
            for k in (0,6,12):top.extend((full[n+k],full[n+k+1],0.,*full[n+k+3:n+k+6]))
    return _transform(top,center,basis)


def build_radiator_detail(builder, radiator_mm, center, basis, part, profile=None):
    """Append a bounded static radiator body and return source-qualified anchors.

    Local X spans width, Y length, Z thickness. ``profile=None`` deliberately
    returns no connection ports: the caller retains the AIO's known barbs and
    radiator pump. ``fan_faces`` describe vacant bay faces, not installed fans.
    The function never changes builder.parts/fans/rotors or appends a part.
    Invalid inputs and budget failures occur before the first builder mutation.
    """
    from assembly_geometry import box, ring, _quad
    from assembly_detail import chamfer_rect
    dimensions = _dimensions(radiator_mm); length, width, thickness = dimensions
    center = _vector(center); basis = _basis(basis)
    if not isinstance(part, str) or not part or len(part) > 160: raise ValueError('Radiator part ID is invalid')
    if profile is not None and not isinstance(profile, dict): raise ValueError('Radiator profile must be a mapping or None')
    source = profile or {}
    if source.get('dimensions_mm') is not None:
        documented = _dimensions(source['dimensions_mm'])
        if any(abs(a-b) > 1e-6 for a, b in zip(dimensions, documented)):
            raise ValueError('Radiator profile and caller dimensions disagree; no implicit scaling is allowed')
    level = getattr(builder, 'level', 'balanced')
    if level not in _LOD: level = 'balanced'
    segments, tubes, folds = _LOD[level]
    hole_segments = {'eco': 6, 'balanced': 8, 'close': 12}[level]
    size = source.get('fan_size_mm', radiator_mm.get('fan_size_mm'))
    capacity = source.get('fan_count', radiator_mm.get('fan_count'))
    if size is None and capacity is None: size, capacity = None, 0
    elif not (_finite(size) and 65 <= size <= 200 and type(capacity) is int and 1 <= capacity <= 4):
        raise ValueError('Radiator fan capacity must be explicit, bounded and independent of installed fans')
    if capacity and (capacity-1)*size+size*.9 > length:
        raise ValueError('Documented fan bays cannot fit the radiator envelope')
    ports, unknown = _ports(source, dimensions) if profile is not None else ([], [])
    if level == 'eco' and (capacity >= 3 or len(ports) >= 4):
        tubes, folds = 5, 16
    if profile is None: unknown.append('AIO connections and any radiator-integrated pump remain caller-owned; no thread or removable ports inferred')
    family = source.get('shell_family', 'aio_reference_frame')
    features = source.get('shell_features', ())
    if not isinstance(features, (tuple, list)) or len(features) > 24: raise ValueError('Radiator shell features must be a bounded list')
    if not all(isinstance(x, str) and len(x) <= 96 for x in features): raise ValueError('Radiator shell feature names must be bounded strings')
    # Supported mechanical treatments are qualitative observations, not logo art
    # or hidden manufacturer-specific internals guessed from a brand name.
    brushed = family == 'watercool_brushed_endplates'
    silver_core = family == 'aqua_radical_tube_stack'
    if silver_core:tubes = {'eco':4,'balanced':6,'close':8}[level]
    thick_caps = family in ('ek_surface_aluminium_caps', 'tt_pacific_stainless_panels')
    round_shoulders = family in ('hwlabs_nemesis', 'alphacool_split_tanks')
    frame = _tint(source, 'frame_color', '#303b43')
    tank = _tint(source, 'tank_color', '#29343c')
    body = _tint(source, 'body_color', '#24313a')
    contrasting = 'contrasting_aluminium_endcaps' in features
    colors = {'folded-rails': frame, 'rail-lips': '#929ca2' if brushed or contrasting else '#3c4a53',
              'end-tanks': tank, 'tank-seams': '#14232b',
              'flat-tube-samples': '#976747' if silver_core else '#3a4952',
              'folded-fin-samples': '#bbc3c6' if silver_core else '#56656e',
              'port-collars': '#657780', 'port-throats': '#26353d', 'explicit-port-plugs': body}
    batches = {key: [] for key in colors}
    def put(key, vertices, position=(0., 0., 0.), axes=_IDENTITY):
        batches[key].extend(_transform(vertices, position, axes))
    def block(key, size3, point): put(key, box(*size3), point)
    sheet = .8; half_w, half_l, half_t = width/2, length/2, thickness/2
    # Tank shoulders reserve real sheet around observed mouths. They do not
    # shorten the separate mounting flanges: a middle port must not displace
    # the source fan-hole pattern at the two outer edges of a 360mm radiator.
    tank_depth = {}
    for sign in (-1, 1):
        value = min(24., max(14., length*.055))
        for port in ports:
            x, y, z = port['local_position']
            if port['face'] != 'end' and y*sign > 0: value = max(value, half_l-y*sign+8.)
        if value > length*.24: raise ValueError('Observed port is in the fin field, not an end tank')
        tank_depth[sign] = value
    rail_low, rail_high = -half_l, half_l
    pitch = source.get('fan_mount_pitch_mm')
    pitch_flag = source.get('fan_mount_pitch_verified')
    if pitch is None:
        pitch = radiator_mm.get('fan_mount_pitch_mm')
        pitch_flag = radiator_mm.get('fan_mount_pitch_verified')
    pitch_supplied = pitch is not None
    if pitch_supplied and not _finite(pitch): raise ValueError('Radiator fan mounting pitch must be finite')
    pitch_verified = pitch_flag is True and _finite(pitch)
    if pitch is None: pitch = size*.875 if capacity else None
    if pitch is not None and not (0 < pitch < width-4 and pitch <= size):
        raise ValueError('Fan mounting pitch is outside the radiator envelope')
    flange = max(9., half_w-pitch/2+3.3) if capacity else min(12., width*.10)
    if flange > width*.25: raise ValueError('Radiator mounting flange would cover the core')
    holes = []
    if capacity:
        for bay in range(capacity):
            y = (bay-(capacity-1)/2)*size
            for sign in (-1, 1): holes.append((y+sign*pitch/2, bay))
    holes.sort()
    if any(not rail_low+2.6 <= y <= rail_high-2.6 for y, bay in holes):
        raise ValueError('Fan mounting holes escape the documented envelope')
    # Each small cap cell contains at most one hole. This avoids the explosive
    # all-holes/global polygon subtraction of a long densely drilled plate.
    mount_anchors = []
    for sign in (-1, 1):
        xc = sign*(half_w-flange/2); xh = sign*pitch/2 if capacity else 0.
        for face in (-1, 1):
            z = face*(half_t-sheet/2)
            boundaries = [rail_low]+[(a[0]+b[0])/2 for a, b in zip(holes, holes[1:])]+[rail_high]
            if not holes:
                cutouts = [(p['local_position'][0]-xc, p['local_position'][1], 5.9) for p in ports
                           if p['face'] == ('front' if face > 0 else 'rear')
                           and abs(p['local_position'][0]-xc) < flange/2+5.9]
                polygon = ((-flange/2, rail_low), (flange/2, rail_low),
                           (flange/2, rail_high), (-flange/2, rail_high))
                put('folded-rails', _plate(polygon, cutouts, sheet, (xc, 0., z), _IDENTITY, hole_segments))
            for i, (y, bay) in enumerate(holes):
                low, high = boundaries[i:i+2]; cy = (low+high)/2
                opening = ((xh-xc, y-cy, 1.65) if pitch_verified else
                           _capsule(xh-xc, y-cy, 1.65, .9, hole_segments))
                cutouts = [opening]
                for port in ports:
                    if port['face'] != ('front' if face > 0 else 'rear'): continue
                    px, py, pz = port['local_position']
                    if abs(px-xc) < flange/2+5.9 and low-5.9 < py < high+5.9:
                        cutouts.append((px-xc, py-cy, 5.9))
                polygon = ((-flange/2, -(high-low)/2), (flange/2, -(high-low)/2),
                           (flange/2, (high-low)/2), (-flange/2, (high-low)/2))
                if level != 'eco' and 'scalloped_mount_rails' in features:
                    # Qualitative observed scallop at the inner rail edge.
                    # Its small recess stays away from the actual open hole.
                    cut = min(1.7, (high-low)*.12)
                    polygon = ((-flange/2+cut, -(high-low)/2), (flange/2, -(high-low)/2),
                               (flange/2, (high-low)/2), (-flange/2+cut, (high-low)/2),
                               (-flange/2, (high-low)/2-cut), (-flange/2, -(high-low)/2+cut))
                    if sign < 0: polygon = tuple((-x, y) for x, y in reversed(polygon))
                put('folded-rails', _plate(polygon, cutouts, sheet, (xc, cy, z), _IDENTITY, hole_segments))
                mount_anchors.append(dict(position=_world((xh, y, face*half_t), center, basis),
                                          normal=_world((0., 0., float(face)), center, basis, True),
                                          bay=bay, reference=True))
        # C-channel web is pierced too if a documented side port passes through
        # it. No hidden solid rail is allowed to plug a connection mouth.
        side_ports = [p for p in ports if p['face'] == ('right' if sign > 0 else 'left')]
        web_holes = [(p['local_position'][1], p['local_position'][2], 5.9) for p in side_ports]
        axes = ((0., 1., 0.), (0., 0., float(sign)), (float(sign), 0., 0.))
        polygon = ((-half_l, -half_t), (half_l, -half_t), (half_l, half_t), (-half_l, half_t))
        # Local web Y flips with sign; preserve its holes in that same frame.
        web_holes = [(y, z*sign, r) for y, z, r in web_holes]
        put('folded-rails', _plate(polygon, web_holes, sheet, (sign*(half_w-sheet/2), 0., 0.), axes, segments))
        # Return lips expose the fold under oblique inspection without becoming
        # broad filled side slabs or adding fictitious fan screws.
        for face in (-1, 1):
            lip_x = sign*(half_w-flange+sheet/2); intervals = []
            for port in ports:
                if port['face'] != ('front' if face > 0 else 'rear'): continue
                px, py, pz = port['local_position']; distance = max(0., abs(px-lip_x)-sheet/2)
                if distance < 5.9:
                    reach = math.sqrt(5.9**2-distance**2)
                    intervals.append((max(rail_low, py-reach), min(rail_high, py+reach)))
            cursor = rail_low
            for low, high in sorted(intervals)+[(rail_high, rail_high)]:
                if low > cursor:
                    block('rail-lips', (sheet, low-cursor, min(2.6, thickness*.13)),
                          (lip_x, (cursor+low)/2, face*(half_t-sheet-min(2.6, thickness*.13)/2)))
                cursor = max(cursor, high)
    corner = 3.2 if round_shoulders else 2.4 if thick_caps else 1.3
    # The terminal is a shoulder between the two separate mounting rails, not
    # a second full-width solid plate hidden across every screw hole. A wider
    # observed edge socket (airplex/TX/RX) reserves its own surrounding sheet.
    tank_half_width = max(half_w-flange-.6,
                          max((abs(p['local_position'][0])+8. for p in ports), default=0.))
    tank_half_width = min(half_w-sheet, tank_half_width)
    for sign in (-1, 1):
        depth = tank_depth[sign]; cy = sign*(half_l-depth/2)
        poly = chamfer_rect(tank_half_width*2, depth, corner)
        for face in (-1, 1):
            matching = [p for p in ports if p['face'] == ('front' if face > 0 else 'rear') and p['local_position'][1]*sign > 0]
            cutouts = [(p['local_position'][0], p['local_position'][1]-cy, 5.9) for p in matching]
            put('end-tanks', _plate(poly, cutouts, sheet, (0., cy, face*(half_t-sheet/2)), _IDENTITY, segments))
        for a, b in zip(poly, (*poly[1:], poly[0])):
            dx, dy = b[0]-a[0], b[1]-a[1]; span = math.hypot(dx, dy)
            u = (dx/span, dy/span, 0.); n = (dy/span, -dx/span, 0.)
            middle = ((a[0]+b[0])/2, cy+(a[1]+b[1])/2, 0.)
            axes = (u, (0., 0., 1.), n); cutouts = []
            for port in ports:
                if _dot(n, port['normal']) > .999:
                    delta = _sub(port['local_position'], middle)
                    if abs(_dot(delta, n)) < sheet+1e-5 and abs(_dot(delta, u)) < span/2-6.:
                        cutouts.append((_dot(delta, u), delta[2], 5.9))
            rectangle = ((-span/2, -half_t+sheet), (span/2, -half_t+sheet),
                         (span/2, half_t-sheet), (-span/2, half_t-sheet))
            batch = 'rail-lips' if (brushed or contrasting) and n[1]*sign > .999 else 'end-tanks'
            put(batch, _plate(rectangle, cutouts, sheet, _sub(middle, _mul(n, sheet/2)), axes, segments))
        # Narrow shoulder/seam bands sit at the core join. They cannot cover the
        # source port faces and are not invented logos or brand text.
        join = sign*(half_l-depth)
        for face in (-1, 1):
            block('tank-seams', (width-2*flange, .7, .25), (0., join+sign*.45, face*(half_t-.18)))
            if thick_caps or brushed or 'split_shoulder_tanks' in features:
                block('rail-lips', (width-2*flange, 1.5, .45), (0., join+sign*2., face*(half_t-.3)))
    core_low, core_high = -half_l+tank_depth[-1], half_l-tank_depth[1]
    core_length = core_high-core_low-1.6; core_y = (core_low+core_high)/2
    core_width = width-2*flange-1.2; tube_width = max(1., min(2.2, core_width/(tubes*7)))
    positions = [-core_width/2+tube_width/2+i*(core_width-tube_width)/(tubes-1) for i in range(tubes)]
    core_depth = max(5., thickness-sheet*2-2.)
    louver_samples = 0
    if silver_core:
        # This sourced family has copper coolant tubes and an unsoldered silver
        # aluminium plate stack, unlike the folded copper/brass reference core.
        # Sample counts and tube radii stay explicitly unverified. Each sampled
        # fin has actual clearance holes around the sampled round copper tubes.
        plate_rows = {'eco': 8, 'balanced': 32, 'close': 52}[level]
        radius = 2.; axes = ((1., 0., 0.), (0., 0., -1.), (0., 1., 0.))
        for x in positions:
            put('flat-tube-samples', ring(radius, 0., core_length, segments), (x, core_y, 0.), axes)
        half_core = core_width/2+radius+.2
        plate = ((-half_core, -core_depth*.46), (half_core, -core_depth*.46),
                 (half_core, core_depth*.46), (-half_core, core_depth*.46))
        perforations = [(x, 0., radius+.15) for x in positions]
        for row in range(plate_rows):
            y = core_low+.8+(row+.5)*core_length/plate_rows
            put('folded-fin-samples', _foil_plate(plate, perforations, (0., y, 0.), axes, max(6, segments-4)))
    else:
        for x in positions:
            block('flat-tube-samples', (tube_width, core_length, core_depth), (x, core_y, 0.))
        dy = core_length/folds
        for gap, (left, right) in enumerate(zip(positions, positions[1:])):
            a, b = left+tube_width/2+.12, right-tube_width/2-.12
            for row in range(folds):
                y = core_low+.8+row*dy
                louver = row == folds//2 and gap % 2 == 0
                if louver: louver_samples += 1
                for first, second in (((a, y), (b, y+dy/2)), ((b, y+dy/2), (a, y+dy))):
                    put('folded-fin-samples', _fin_segment(first, second, core_depth*.92, louver))
    for port in ports:
        point = port['local_position']; normal = port['normal']
        up = (0., 1., 0.) if abs(normal[1]) < .9 else (1., 0., 0.)
        u = _cross(up, normal); u = _mul(u, 1/math.sqrt(_dot(u, u)))
        v = _cross(normal, u); axes = (u, v, normal)
        collar = []; throat = []
        # The metal tank supplies the backing. One top annulus, its outside
        # shoulder, a real internal chamfer and an open throat avoid duplicate
        # hidden annulus caps and never put a disk over a connection mouth.
        def polar(angle, radius, z): return (math.cos(angle)*radius, math.sin(angle)*radius, z)
        for segment in range(segments):
            a, b = segment*math.tau/segments, (segment+1)*math.tau/segments
            _quad(collar, polar(a, 5.6, 0.), polar(a, 7., 0.), polar(b, 7., 0.), polar(b, 5.6, 0.))
            _quad(collar, polar(a, 7., -.8), polar(a, 7., 0.), polar(b, 7., 0.), polar(b, 7., -.8))
            _quad(throat, polar(a, 5.6, 0.), polar(b, 5.6, 0.), polar(b, 5.15, -1.2), polar(a, 5.15, -1.2))
            _quad(throat, polar(a, 5.15, -1.2), polar(b, 5.15, -1.2), polar(b, 5.15, -4.8), polar(a, 5.15, -4.8))
        put('port-collars', collar, point, axes)
        put('port-throats', throat, point, axes)
        if port['capped']:
            put('explicit-port-plugs', ring(5.55, 0., .8, segments), _sub(point, _mul(normal, .65)), axes)
    count = sum(len(vertices)//18 for vertices in batches.values())
    if count > TRIANGLE_BUDGETS[level]:
        raise ValueError('Radiator detail exceeded its bounded '+level+' triangle budget')
    # Check every primitive before exposing any geometry to the caller. Ports
    # and reference fold sheets stay within the documented body envelope.
    extents = (half_w, half_l, half_t)
    for vertices in batches.values():
        for i in range(0, len(vertices), 6):
            if any(abs(vertices[i+k]) > extents[k]+1e-5 for k in range(3)):
                raise ValueError('Radiator detail escaped its documented body envelope')
    fan_faces = []
    for bay in range(capacity):
        for sign in (-1, 1):
            point = (0., (bay-(capacity-1)/2)*size, sign*half_t)
            fan_faces.append(dict(bay=bay, side='front' if sign > 0 else 'rear',
                                  center=_world(point, center, basis),
                                  normal=_world((0., 0., float(sign)), center, basis, True),
                                  up=_world((1., 0., 0.), center, basis, True),
                                  installed=False, size_mm=size, position_reference=True))
    anchors = []
    for row in ports:
        anchor = dict(row)
        anchor.pop('local_position')
        anchor.update(position=_world(row['local_position'], center, basis),
                      normal=_world(row['normal'], center, basis, True),
                      throat_shape_reference=True, open=not row['capped'])
        anchors.append(anchor)
    for name, vertices in batches.items():
        if vertices: builder.put('cooler-radiator044-'+name, tuple(vertices), colors[name], center, basis, component='cooler', part=part)
    return dict(ports=anchors, fan_faces=fan_faces, mount_holes=mount_anchors,
                metadata=dict(profile_id=source.get('id'), shell_family=family, level=level,
                              envelope_mm=dict(zip(('length', 'width', 'thickness'), dimensions)),
                              triangle_count=count, mesh_count=sum(bool(v) for v in batches.values()),
                              fan_capacity_per_face=capacity, fan_count_is_installed=False,
                              port_owner='profile' if profile is not None else 'caller_aio',
                              documented_total_ports=source.get('ports_count'), modelled_ports=len(anchors),
                              undocumented_ports_invented=False, g1_4_thread_profile_modelled=False,
                              mount_pitch_mm=pitch, mount_pitch_source='source_or_caller' if pitch_supplied else 'nominal_reference',
                              mount_pitch_verified=pitch_verified, mount_positions_reference=True,
                              tank_depth_reference_mm=tank_depth,
                              tank_width_reference_mm=tank_half_width*2,
                              tube_sample_count=tubes, fold_sample_rows=folds,
                              fin_sample_plate_rows=plate_rows if silver_core else None,
                              louver_sample_cells=louver_samples, actual_tube_count=None, actual_fin_count=None,
                              foil_is_zero_thickness_reference=True,
                              fpi=source.get('fpi') if source.get('fpi_verified') is True else None,
                              core_construction='sampled copper round tubes / aluminium plate stack' if silver_core else 'sampled flat tubes / folded louvered fins',
                              reference_features=['sheet gauges, tank shoulders/seams', 'sampled flat tubes and folded/louvered core',
                                                  'mount hole diameter and unsourced positions', 'port collar/throat shape; no helical thread'],
                              unknown=unknown, static=True, new_fans=0, new_rotors=0, new_parts=0))
