"""Original bounded 0.40 case shells: no I/O, sampling, clocks or CAD claims.

Retail outer dimensions and structural cues come from each case's catalog
sources. All hole/fin/weave repetition, chamfers, bracket positions and the
Torque angle below are qualitative references, not manufacturer measurements.
Called after the retained 0.39 exterior pass. Never creates installed hardware.
"""
import math


TORQUE_TILT_DEGREES = 12.0  # Original reference only; no official measured angle.
TORQUE_PIVOT = (0.0, 0.0, 0.0)
FULL_SHELL_FLAGS = frozenset(("angular_modular_shell", "forward_tilted_open_frame",
                             "striker_open_frame", "expandable_itx_shell", "cosmos_wrap_handles"))
DETAIL_FLAGS = frozenset(("nas_twelve_bay", "elevated_glass_shell", "infinirail_fan_mounts",
                         "split_glass_mesh_side", "fabric_front_insert"))


def torque_pose(point, *, vector=False):
    """Rigid +X rotation around case centre; top +Y moves toward front +Z.

    Zero pivot means points and vectors currently share the same calculation.
    The explicit vector parameter keeps the interface safe if a pivot is added.
    """
    angle = math.radians(TORQUE_TILT_DEGREES)
    co, si = math.cos(angle), math.sin(angle)
    px, py, pz = (0., 0., 0.) if vector else TORQUE_PIVOT
    x, y, z = (point[0]-px, point[1]-py, point[2]-pz)
    return (x+px, co*y-si*z+py, si*y+co*z+pz)


def hardware_pose(case):
    if "forward_tilted_open_frame" not in case.get("features", ()):
        return None
    return dict(rotation_axis=(1., 0., 0.), reference_degrees=TORQUE_TILT_DEGREES,
                pivot=TORQUE_PIVOT, angle_verified=False, dimensions_scaled=False,
                method="official_forward_tilt_with_original_reference_angle",
                source=(case.get("sources") or ("https://www.antec.com/product/case/torque",))[0])


def _translate(vertices, position):
    return tuple(value + position[index % 6] if index % 6 < 3 else value
                 for index, value in enumerate(vertices))


def _rotate(vertices, pose):
    return tuple(value for start in range(0, len(vertices), 6)
                 for block in (0, 3) for value in pose(vertices[start+block:start+block+3]))


def replace_shell(meshes, dimensions, case, level="balanced"):
    """Return untouched old tuples, or bounded case-only material batches.

    Complete new shells replace only case/panel components. Additive references
    remove specific obsolete surfaces, leaving selected hardware objects intact.
    """
    from assembly_geometry import Mesh, box, color, extrude, _quad
    flags = frozenset(case.get("features") or ())
    if not flags & (FULL_SHELL_FLAGS | DETAIL_FLAGS):
        return meshes if isinstance(meshes, tuple) else tuple(meshes)
    w, h, d = dimensions
    detail = 0 if level == "eco" else 2 if level == "close" else 1
    complete = bool(flags & FULL_SHELL_FLAGS)
    kept = [m for m in meshes if not complete or m.component not in ("case", "panel")]
    batches = {}
    steel = color(case.get("color"), "#63717b")
    silver, dark, glass = color("#aebbc3"), color("#24343e"), color("#9ab7c5", alpha=.17)

    def add(name, vertices, tone=steel, position=(0, 0, 0), component="case", pose=None):
        values = _translate(vertices, position)
        if pose:
            values = _rotate(values, pose)
        if values:
            batches.setdefault((name, tone, component), []).extend(values)

    def cube(name, size, position, tone=steel, component="case", pose=None):
        add(name, box(*size), tone, position, component, pose)

    def side(name, points_zy, thickness, x, tone=steel, component="case", pose=None):
        # +90 around Y: local XY becomes a YZ panel without a handedness flip.
        vertices = extrude(points_zy, thickness)
        oriented = tuple(value for start in range(0, len(vertices), 6)
                         for block in (0, 3)
                         for value in (-vertices[start+block+2], vertices[start+block+1], vertices[start+block]))
        add(name, oriented, tone, (x, 0, 0), component, pose)

    def tube(name, points, radius, tone=steel, component="case"):
        from assembly_cooling import _tube
        add(name, _tube(points, radius, (6, 8, 10)[detail]), tone, component=component)

    def bar(name, a, b, width, thickness, tone=steel, component="case"):
        # A flat strip between XY endpoints on the front face, not a solid grille.
        dx, dy = b[0]-a[0], b[1]-a[1]
        length = math.hypot(dx, dy)
        if length < .001:
            return
        co, si = dx/length, dy/length
        def turn(p):
            x, y, z = p
            return (co*x-si*y, si*x+co*y, z)
        values = _rotate(box(length, width, thickness), turn)
        add(name, values, tone, ((a[0]+b[0])/2, (a[1]+b[1])/2, (a[2]+b[2])/2), component)

    if "angular_modular_shell" in flags:
        # MOD-5: distinct separated armour pieces around an exposed central bay.
        for x in (-w/2+2., w/2-2.):
            side("case-mod5-reference-upper-armour", ((-d*.48,h*.31),(-d*.22,h*.49),
                 (d*.22,h*.43),(d*.48,h*.17),(d*.37,h*.12),(d*.12,h*.32),(-d*.26,h*.36)),
                 4., x, steel)
            side("case-mod5-reference-lower-armour", ((-d*.45,-h*.26),(-d*.22,-h*.49),
                 (d*.29,-h*.43),(d*.47,-h*.24),(d*.29,-h*.21),(d*.12,-h*.34),(-d*.24,-h*.35)),
                 4., x, dark)
            side("case-mod5-side-glass", ((-d*.34,-h*.24),(-d*.38,h*.18),(-d*.20,h*.32),
                 (d*.22,h*.28),(d*.36,h*.10),(d*.30,-h*.23)), 2., x*.98, glass, "panel")
        for y in (-h*.36,h*.36):
            cube("case-mod5-reference-crossmembers", (w*.84,9.,d*.40), (0,y,-d*.08), silver)
        for z in (-d*.27,d*.29):
            cube("case-mod5-reference-feet", (w*.82,10.,42.), (0,-h*.49,z), dark)
        # Empty removable tray, with a large opening: no fabricated installed PCB.
        for y in (-h*.27,h*.27):
            cube("case-mod5-reference-tray-rails", (5.,8.,d*.64), (w*.30,y,0), steel)

    elif "forward_tilted_open_frame" in flags:
        # Support/tray coordinates share exactly the hardware's reference tilt.
        for x in (-w*.42,w*.42):
            side("case-torque-reference-alloy", ((-d*.38,-h*.30),(-d*.34,h*.30),
                 (-d*.18,h*.41),(d*.28,h*.37),(d*.38,h*.16),(d*.29,h*.12),
                 (d*.20,h*.29),(-d*.22,h*.31),(-d*.27,-h*.28)), 5., x, steel, pose=torque_pose)
            side("case-torque-reference-crimson", ((-d*.32,-h*.30),(-d*.20,-h*.40),
                 (d*.29,-h*.33),(d*.36,-h*.12),(d*.29,-h*.08),(d*.22,-h*.23)),
                 4., x, color("#9c424c"), pose=torque_pose)
            side("case-torque-side-glass", ((-d*.29,-h*.25),(-d*.29,h*.24),(-d*.15,h*.32),
                 (d*.25,h*.28),(d*.30,-h*.20)), 3., x*1.06, glass, "panel", torque_pose)
        for y in (-h*.27,h*.27):
            cube("case-torque-reference-tray-support", (6.,8.,d*.60), (w*.30,y,-d*.04), silver, pose=torque_pose)
        for z in (-d*.30,d*.31):
            cube("case-torque-reference-base", (w*.83,12.,d*.16), (0,-h*.46,z), dark)

    elif "striker_open_frame" in flags:
        # Rear ITX space and empty forward GPU fork remain visibly separate.
        for x in (-w*.43,w*.43):
            side("case-striker-reference-forks", ((-d*.40,-h*.40),(-d*.43,h*.28),
                 (-d*.25,h*.44),(-d*.12,h*.40),(-d*.28,h*.22),(-d*.25,-h*.27),
                 (d*.31,-h*.29),(d*.35,h*.37),(d*.44,h*.40),(d*.43,-h*.40)),
                 7., x, silver)
            side("case-striker-side-glass", ((-d*.32,-h*.24),(-d*.33,h*.20),
                 (-d*.20,h*.34),(d*.23,h*.27),(d*.26,-h*.25)), 3., x*.94, glass, "panel")
        z = d/2-min(96.,d*.24)
        for x in (-w*.39,w*.39):
            cube("case-striker-empty-gpu-rails", (5.,h*.77,6.), (x,h*.03,z), dark)
        for y in (-h*.35,h*.415):
            cube("case-striker-empty-gpu-rails", (w*.80,5.,8.), (0,y,z), dark)
        for z in (-d*.31,d*.31):
            cube("case-striker-reference-base", (w*.88,13.,32.), (0,-h*.47,z), dark)

    elif "expandable_itx_shell" in flags:
        low, high = -h/2+9., h/2-38.
        for x in (-w/2+2.,w/2-2.):
            for y in (low,high):
                cube("case-shift-reference-aluminium", (4.,5.,d-8.), (x,y,0), steel)
            for z in (-d/2+4.,d/2-4.):
                cube("case-shift-reference-aluminium", (4.,high-low,8.), (x,(low+high)/2,z), steel)
        for z in (-d/2+2.,d/2-2.):
            cube("case-shift-reference-aluminium", (w-6.,high-low,4.), (0,(low+high)/2,z), steel)
        for x in (-w/2+3.,w/2-3.):
            for row in range((12,20,28)[detail]):
                y = low+5.+row*(high-low-10.)/((12,20,28)[detail]-1)
                cube("case-shift-reference-side-mesh", (1.5,1.3,d-22.), (x,y,0), dark, "panel")
            for column in range((10,16,22)[detail]):
                z=-d*.45+column*d*.90/((10,16,22)[detail]-1)
                cube("case-shift-reference-side-mesh", (1.5,high-low-6.,1.2), (x,(high+low)/2,z), dark, "panel")
        for x in (-w*.43,w*.43):
            for z in (-d*.43,d*.43):
                cube("case-shift-reference-extension-posts", (6.,35.,6.), (x,h/2-19.,z), silver)
        for row in range((10,16,22)[detail]):
            z=-d*.45+row*d*.90/((10,16,22)[detail]-1)
            cube("case-shift-reference-top-mesh", (w-12.,3.,2.), (0,h/2-2.,z), steel, "panel")
        cube("case-shift-infinity-mirror", (w*.72,(high-low)*.58,1.8),
             (0,(low+high)/2+4.,d/2-.5), color("#152c35"), "panel")
        for scale in (.90,.75,.60):
            for sign in (-1,1):
                cube("case-shift-static-infinity-reference", (w*.64*scale,1.,.7),
                     (0,(low+high)/2+4.+sign*(high-low)*.25*scale,d/2+.65), color("#84aeb7"), "panel")
                cube("case-shift-static-infinity-reference", (1.,(high-low)*.5*scale,.7),
                     (sign*w*.32*scale,(low+high)/2+4.,d/2+.65), color("#84aeb7"), "panel")

    elif "cosmos_wrap_handles" in flags:
        bodyw, bodyh, bodyd = w*.88,h*.88,d*.94
        cube("case-cosmos-metal-body", (bodyw,3.,bodyd), (0,-bodyh/2,0), dark)
        cube("case-cosmos-metal-body", (2.,bodyh,bodyd), (bodyw/2,0,0), steel)
        cube("case-cosmos-metal-body", (bodyw,bodyh,2.), (0,0,-bodyd/2), dark)
        cube("case-cosmos-front-aluminium", (bodyw,bodyh,3.), (0,0,bodyd/2), steel, "panel")
        for index in range((10,16,22)[detail]):
            z=-bodyd*.43+index*bodyd*.86/((10,16,22)[detail]-1)
            cube("case-cosmos-reference-top-grille", (bodyw-12.,2.,3.), (0,bodyh/2,z), dark, "panel")
        # A continuous curved side front edge, not a curved glass front panel.
        pane=[];radius=22.;cx=-bodyw/2+radius;cz=bodyd/2-radius
        points=[(-bodyw/2,-bodyd/2+9.),(-bodyw/2,cz)]
        for index in range(1,(4,6,8)[detail]+1):
            a=math.pi-index*math.pi/2/(4,6,8)[detail]
            points.append((cx+radius*math.cos(a),cz+radius*math.sin(a)))
        for a,b in zip(points,points[1:]):
            _quad(pane,(a[0],-bodyh*.47,a[1]),(b[0],-bodyh*.47,b[1]),
                  (b[0],bodyh*.47,b[1]),(a[0],bodyh*.47,a[1]))
        add("case-cosmos-curved-side-glass",tuple(pane),glass,component="panel")
        for x in (-w*.46,w*.46):
            for sign in (-1,1):
                y=sign*(h/2-8.)
                tube("case-cosmos-reference-silver-wraps", ((x,sign*bodyh*.40,-d*.45),
                    (x,y-sign*9.,-d*.46),(x,y,-d*.40),(x,y,d*.40),
                    (x,y-sign*9.,d*.46),(x,sign*bodyh*.40,d*.45)),6.,silver)

    if "nas_twelve_bay" in flags:
        # Twelve EMPTY tray-frame references; no drive bodies or activity LEDs.
        for row in range(4):
            y=-h*.38+row*h*.09
            for column in range(3):
                x=(column-1)*w*.29
                for side_sign in (-1,1):
                    cube("case-nas12-empty-tray-reference", (w*.27,2.,6.),
                         (x,y+side_sign*h*.035,d/2-9.), dark)
                    cube("case-nas12-empty-tray-reference", (2.,h*.07,6.),
                         (x+side_sign*w*.135,y,d/2-9.), dark)

    if "elevated_glass_shell" in flags:
        kept=[m for m in kept if m.name not in ("case-foot","case-bottom")]
        cube("case-elevated-reference-floor",(w-9.,3.,d-9.),(0,-h/2+32.,0),silver)
        cube("case-elevated-reference-plinth",(w*.93,6.,d*.93),(0,-h/2+3.,0),dark)
        for x in (-w*.39,w*.39):
            for z in (-d*.39,d*.39):
                cube("case-elevated-reference-supports",(7.,26.,7.),(x,-h/2+18.,z),steel)

    if "infinirail_fan_mounts" in flags:
        double="dual_column_fan_rails" in flags
        centers=(-w*.215,w*.215) if double else (0.,)
        half=48. if double else w*.34
        for center in centers:
            for sign in (-1,1):
                x=center+sign*half
                cube("case-reference-infinirail-slides",(4.,h*.82,5.),(x,0,d/2-12.),silver)
                cube("case-reference-infinirail-slides",(4.,5.,d*.82),(x,h/2-12.,0),silver)
            for y in (-h*.35,h*.35):
                cube("case-reference-infinirail-clamps",(half*2+8.,7.,8.),(center,y,d/2-12.),dark)
        if "front_y_airflow" in flags:
            kept=[m for m in kept if m.name not in ("front-vent","front-grid-column","front-triangle-line")]
            cols,rows=(3,5,7)[detail],(6,10,14)[detail]
            for col in range(cols):
                for row in range(rows):
                    x=-w*.39+(col+.5)*w*.78/cols
                    y=-h*.42+(row+.5)*h*.84/rows
                    reach=min(w*.30/cols,h*.30/rows)
                    p=(x,y,d/2-1.)
                    for dx,dy in ((0,-reach),(reach*.85,reach*.50),(-reach*.85,reach*.50)):
                        bar("case-reference-y-airflow-web",p,(x+dx,y+dy,p[2]),1.5,1.2,steel)

    if "split_glass_mesh_side" in flags:
        kept=[m for m in kept if m.name not in ("left-glass","left-panel","left-mesh-vent","case-right")]
        for sign in (-1,1):
            x=sign*(w/2-1.)
            cube("case-q58-upper-glass-reference",(1.7,h*.43,d*.91),(x,h*.25,0),glass,"panel")
            cube("case-q58-half-panel-seam",(2.,3.,d*.94),(x,h*.015,0),dark,"panel")
            count=(8,14,20)[detail]
            for row in range(count):
                cube("case-q58-lower-reference-mesh",(1.6,1.4,d*.91),
                     (x,-h*.43+row*h*.40/(count-1),0),steel,"panel")
            for column in range(count):
                cube("case-q58-lower-reference-mesh",(1.6,h*.40,1.3),
                     (x,-h*.23,-d*.445+column*d*.89/(count-1)),steel,"panel")

    if "fabric_front_insert" in flags:
        kept=[m for m in kept if m.name not in ("front-vent","front-grid-column")]
        cube("case-fabric-front-insert",(w*.78,h*.87,1.8),(0,h*.015,d/2-.6),color("#9b9c98"),"panel")
        for row in range((10,16,22)[detail]):
            y=-h*.39+row*h*.80/((10,16,22)[detail]-1)
            cube("case-fabric-front-reference-weave",(w*.73,.55,.2),(0,y,d/2+.35),color("#b2b3ad"),"panel")

    additions=tuple(Mesh(name,tuple(vertices),tone,component=component)
                    for (name,tone,component),vertices in batches.items())
    return tuple((*kept,*additions))
