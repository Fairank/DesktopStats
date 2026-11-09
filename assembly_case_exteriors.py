"""Bounded original enclosures for source-reviewed 0.39 structural families.

Overall case dimensions are catalog facts. Fin pitch, weave, machining, mounting
points and edge radii are qualitative references, never vendor CAD dimensions.
No I/O, sensors, timers, installed devices or per-frame work lives here.
"""
import math


_FULL_SHELL = frozenset(("tubular_open_frame", "horizontal_test_bench",
                         "passive_finned_cube", "fabric_column"))
_EXTRAS = frozenset(("front_gpu_chamber", "wood_top_panel",
                     "origami_vent_tabs", "reversible_u_frame"))


def _translated(vertices, position):
    return tuple(value + position[index % 6] if index % 6 < 3 else value
                 for index, value in enumerate(vertices))


def _rounded_loop(width, depth, radius, steps):
    """An original rounded rectangular XZ footprint, bounded by width/depth."""
    radius = min(radius, width / 3, depth / 3)
    result = []
    for cx, cz, begin in ((width / 2 - radius, depth / 2 - radius, 0),
                          (-width / 2 + radius, depth / 2 - radius, 90),
                          (-width / 2 + radius, -depth / 2 + radius, 180),
                          (width / 2 - radius, -depth / 2 + radius, 270)):
        for index in range(steps + 1):
            angle = math.radians(begin + index * 90 / steps)
            result.append((cx + math.cos(angle) * radius,
                           cz + math.sin(angle) * radius))
    return result


def replace_shell(meshes, dimensions, case, level="balanced"):
    """Replace specific case/panel geometry only; unsupported cases are untouched.

    Each feature family emits at most eight material batches. Compatible hardware
    Mesh objects remain exactly the same objects. Empty brackets do not imply an
    installed GPU/fan. The viewer's existing panel controls can peel fabric/fins.
    """
    from assembly_geometry import Mesh, box, color, ring, _quad

    features = frozenset(case.get("features") or ())
    if not features & (_FULL_SHELL | _EXTRAS):
        return meshes if isinstance(meshes, tuple) else tuple(meshes)
    w, h, d = dimensions
    detail = 0 if level == "eco" else 2 if level == "close" else 1
    full = bool(features & _FULL_SHELL)
    kept = [mesh for mesh in meshes if not full or mesh.component not in ("case", "panel")]
    batches = {}
    steel = color(case.get("color"), "#65717a")
    edge, dark = color("#a9b4bb"), color("#27343d")

    def add(name, vertices, tone, position=(0, 0, 0), component="case"):
        if vertices:
            batches.setdefault((name, tone, component), []).extend(_translated(vertices, position))

    def cube(name, size, pos, tone=steel, component="case"):
        add(name, box(*size), tone, pos, component)

    def tube(name, points, radius, tone=steel, component="case"):
        # Local import avoids geometry -> enrich_case -> exterior import cycles.
        from assembly_cooling import _tube
        add(name, _tube(points, radius, (6, 8, 10)[detail]), tone, component=component)

    if "tubular_open_frame" in features:
        # DA6's reviewed 19 mm tube forms the outer body, feet and handles.
        radius = 9.5
        for z in (-d / 2 + radius, d / 2 - radius):
            loop = _rounded_loop(w - 2 * radius, h - 2 * radius, 22., (2, 4, 6)[detail])
            points = [(x, y, z) for x, y in loop]
            tube("case-tubular-metal-frame", points + points[:1], radius, edge)
        for x in (-w / 2 + radius, w / 2 - radius):
            for y in (-h / 2 + 37., h / 2 - 37.):
                tube("case-tubular-metal-frame", ((x, y, -d / 2 + radius),
                                                  (x, y, d / 2 - radius)), radius, edge)
        # Narrow mounting strips leave the open frame open; no invented back wall.
        for x in (-w * .24, w * .24):
            cube("case-da6-reference-brackets", (8., h * .63, 3.),
                 (x, -h * .015, -d * .08), dark)
        for y in (-h * .28, 0, h * .28):
            cube("case-da6-reference-brackets", (w * .56, 6., 4.),
                 (0, y, -d * .08), dark)
        for x in (-w * .38, w * .38):
            for y in (-h * .27, h * .27):
                cube("case-da6-reference-clamps", (19., 12., 24.),
                     (x, y, -d * .30), steel)

    elif "horizontal_test_bench" in features:
        # BC1 V2: the empty frame is 115 mm tall; mounted hardware is above it.
        top = h / 2
        plate_y = top - 4.
        # Open machining references give a thin table, not a tower wall.
        for x in (-w * .25, w * .25):
            cube("case-bench-metal-platform", (w * .48, 8., d * .86),
                 (x, plate_y, -d * .035), steel)
        cube("case-bench-metal-platform", (w, 8., d * .08),
             (0, plate_y, -d * .46), steel)
        for x in (-w * .39, w * .39):
            cube("case-bench-metal-platform", (w * .22, 8., d * .10),
                 (x, plate_y, d * .45), steel)
        for x in (-w * .36, w * .36):
            for z in (-d * .34, d * .34):
                cube("case-bench-reference-legs", (7., h - 8., 23.),
                     (x, -4., z), dark)
            cube("case-bench-reference-legs", (15., 5., d * .80),
                 (x, -h / 2 + 2.5, 0), dark)
        # Positions are a mounting reference; eight support pins are documented.
        for x, z in ((-.32, -.30), (-.32, 0), (-.32, .30),
                     (0, -.30), (0, .30), (.32, -.30), (.32, 0), (.32, .30)):
            values = ring(2.9, 1.2, 8., (12, 16, 20)[detail])
            # ring local Z becomes vertical Y.
            vertical = []
            for offset in range(0, len(values), 6):
                for block in (0, 3):
                    px, py, pz = values[offset + block:offset + block + 3]
                    vertical.extend((px, pz, -py))
            add("case-bench-reference-standoffs", tuple(vertical), edge,
                (x * w, top + 4., z * d))

    elif "passive_finned_cube" in features:
        count = (8, 12, 18)[detail]
        # Four identical extruded aluminium faces are the actual cooling shell.
        # The reviewed panel is 13 mm thick; fin repetition is a reference only.
        for side in (-1, 1):
            cube("case-passive-metal-backing", (w, h - 20., 3.),
                 (0, 0, side * (d / 2 - 11.5)), steel, "panel")
            cube("case-passive-metal-backing", (3., h - 20., d - 26.),
                 (side * (w / 2 - 11.5), 0, 0), steel, "panel")
            for index in range(count):
                across = -.45 + index * .90 / (count - 1)
                cube("case-passive-reference-fins", (3.5, h - 20., 10.),
                     (across * (w - 26.), 0, side * (d / 2 - 5.)), edge, "panel")
                cube("case-passive-reference-fins", (10., h - 20., 3.5),
                     (side * (w / 2 - 5.), 0, across * (d - 26.)), edge, "panel")
        cube("case-passive-base", (w * .90, 10., d * .90), (0, -h / 2 + 5., 0), dark)
        cube("case-passive-lid", (w - 26., 3., d - 26.), (0, h / 2 - 1.5, 0), steel, "panel")

    elif "fabric_column" in features:
        # Mood has a rounded square footprint, not a circular cylinder.
        loop = _rounded_loop(w, d, 16., (3, 5, 7)[detail])
        inner = _rounded_loop(w - 4., d - 4., 14., (3, 5, 7)[detail])
        walls = []
        low, high = -h / 2 + 15., h / 2 - 5.
        for index, a in enumerate(loop):
            following = (index + 1) % len(loop)
            b, ia, ib = loop[following], inner[index], inner[following]
            rear = abs(a[1] + d / 2) < .001 and abs(b[1] + d / 2) < .001
            if not rear:
                _quad(walls, (a[0], low, a[1]), (a[0], high, a[1]),
                      (b[0], high, b[1]), (b[0], low, b[1]))
                _quad(walls, (ia[0], low, ia[1]), (ib[0], low, ib[1]),
                      (ib[0], high, ib[1]), (ia[0], high, ia[1]))
            _quad(walls, (a[0], high, a[1]), (ia[0], high, ia[1]),
                  (ib[0], high, ib[1]), (b[0], high, b[1]))
        add("case-fabric-rounded-cover", tuple(walls), color("#929597"), component="panel")
        for index in range((10, 16, 22)[detail]):
            y = low + index * (high - low) / ((10, 16, 22)[detail] - 1)
            cube("case-fabric-rear-reference-mesh", (w - 32., 2., 2.),
                 (0, y, -d / 2 + 1.), dark, "panel")
        for x in (-(w - 34.) / 2, (w - 34.) / 2):
            cube("case-fabric-rear-reference-mesh", (3., high - low, 2.),
                 (x, (high + low) / 2, -d / 2 + 1.), dark, "panel")
        for index in range((8, 14, 20)[detail]):
            y = low + 8 + index * (high - low - 16) / ((8, 14, 20)[detail] - 1)
            cube("case-fabric-reference-weave", (w - 34., .6, .25),
                 (0, y, d / 2 + .03), color("#a0a3a4"), "panel")
            cube("case-fabric-reference-weave", (.25, .6, d - 34.),
                 (-w / 2 - .03, y, 0), color("#a0a3a4"), "panel")
        for index in range((7, 11, 15)[detail]):
            at = -.43 + index * .86 / ((7, 11, 15)[detail] - 1)
            cube("case-fabric-top-reference-grille", (w - 22., 3., 2.),
                 (0, h / 2 - 2., at * d), dark, "panel")
        cube("case-fabric-base", (w - 8., 12., d - 8.), (0, -h / 2 + 6., 0), dark)

    if "front_gpu_chamber" in features:
        # Empty support space only: never create a GPU, rotor or fan from a case.
        z = d / 2 - min(96., d * .24)
        for x in (-w * .39, w * .39):
            cube("case-front-gpu-reference-rails", (5., h * .77, 6.), (x, h * .03, z), dark)
        for y in (-h * .35, h * .415):
            cube("case-front-gpu-reference-rails", (w * .80, 5., 8.), (0, y, z), dark)
        for x in (-w * .37, w * .37):
            cube("case-front-gpu-reference-bridge", (10., 7., min(84., d * .20)),
                 (x, -h * .35, d / 2 - min(52., d * .13)), edge)

    if "wood_top_panel" in features:
        kept = [mesh for mesh in kept if mesh.name not in ("top-panel", "top-glass")]
        count = (7, 11, 15)[detail]
        for index in range(count):
            at = -.43 + index * .86 / (count - 1)
            cube("case-wood-top-reference-slats", (w * .84, 4., d * .86 / count * .70),
                 (0, h / 2 - 2., at * d), color("#977758"), "panel")

    if "origami_vent_tabs" in features:
        kept = [mesh for mesh in kept if mesh.name not in ("left-side-slat", "front-slat", "case-right")]
        folds = []
        rows, columns = (7, 10, 14)[detail], (4, 5, 6)[detail]
        for side in (-1, 1):
            for row in range(rows):
                for column in range(columns):
                    y = -h * .38 + row * h * .76 / (rows - 1)
                    z = -d * .35 + column * d * .70 / (columns - 1)
                    span = min(18., d * .52 / columns)
                    x = side * (w / 2 - 1.)
                    # Original folded triangular vent cells; pitch is schematic.
                    _quad(folds, (x, y - 8, z - span / 2), (x, y + 8, z - span / 2),
                          (x - side * 5., y, z + span / 2), (x - side * 5., y - 1., z + span / 2))
        # The front also retains a folded, ventilated surface instead of becoming
        # an empty opening after removing the old shutter-like vertical bars.
        for row in range(rows):
            for column in range(columns):
                y = -h * .38 + row * h * .76 / (rows - 1)
                x = -w * .37 + column * w * .74 / (columns - 1)
                span = min(18., w * .52 / columns)
                z = d / 2 - 1.
                _quad(folds, (x - span / 2, y - 8, z), (x + span / 2, y, z - 5.),
                      (x + span / 2, y + 1., z - 5.), (x - span / 2, y + 8, z))
        add("case-origami-reference-folded-tabs", tuple(folds), edge, component="panel")

    if "reversible_u_frame" in features:
        kept = [mesh for mesh in kept if mesh.name not in ("case-foot", "external-frame-upright")]
        # Feet orientation is explicit; do not simultaneously show the handle mode.
        for x in (-w * .46, w * .46):
            for z in (-d * .37, d * .37):
                cube("case-u-frame-reference-feet", (9., 32., 18.), (x, -h / 2 + 16., z), edge)
            cube("case-u-frame-reference-feet", (9., 7., d * .78),
                 (x, -h / 2 + 3.5, 0), edge)

    result = tuple(Mesh(name, tuple(vertices), tone, component=component)
                   for (name, tone, component), vertices in batches.items())
    return tuple((*kept, *result))
