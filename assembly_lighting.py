"""Static preview of existing source-observed light zones; no device control.

Only explicit diffuser meshes are recolored. No lights are added to unknown
products, no RGB strip counts are invented, and fixed-white zones stay white.
Geometry, materials outside these zones, fan axes and clocks are unchanged.
"""
from dataclasses import replace

MODES = ('artwork', 'off', 'warm', 'mint', 'violet')
COLORS = {'off': (.13, .15, .16, 1.), 'warm': (1., .79, .53, 1.),
          'mint': (.49, .87, .78, 1.), 'violet': (.73, .62, .94, 1.)}
_EXACT_RGB = frozenset(('ram-diffuser', 'front-light-strip', 'horizontal-light-strip',
    'cooler-top-accent-bars', 'cooler-corsair-lcd-rgb-ring', 'cooler-nucleus-static-light-ring',
    'cooler-bridge-rgb-outline', 'cooler-pump-rgb-cap',
    'loop-source-observed-corner-argb-window','loop-source-observed-display-rgb-ring',
    'loop-source-observed-chamber-rgb-rim','loop-source-observed-motor-base-rgb-band',
    'loop-source-observed-pump-top-halo','loop-source-observed-photon-rear-rgb-strip',
    'loop-source-observed-reservoir-rgb-ring','loop-source-observed-r260-side-rgb-strip',
    'loop-source-observed-xd3-front-chamber-rgb-rim','loop-source-observed-mini-tank-base-halo'))
_FAN_RGB = ('-static-rgb-hub', '-static-rgb-rim', '-square-rgb-rim',
            '-stationary-polygon-light-ring', '-side-rgb', '-infinity-hub-rings')
_FIXED_WHITE = frozenset(('cooler-pump-white-light-ring','cooler-pump-fixed-white-mark'))


def light_kind(mesh):
    if mesh.name in _FIXED_WHITE or mesh.component in ('cooler','fans') and mesh.name.endswith('-fixed-white-bearing-window'):return 'fixed_white'
    if mesh.name in _EXACT_RGB:return 'rgb_reference'
    if mesh.component in ('cooler', 'fans') and mesh.name.endswith(_FAN_RGB):return 'rgb_reference'
    return ''


def apply_lighting(meshes, mode='artwork'):
    """Reuse physical arrays; the preview palette is independent of hardware RGB."""
    mode = mode if type(mode) is str and mode in MODES else 'artwork'
    rows=[];values=[]
    for index,mesh in enumerate(meshes):
        kind=light_kind(mesh)
        if kind:
            rows.append(dict(mesh_index=index, part_id=mesh.part_id, kind=kind))
            if mode != 'artwork':
                tone=COLORS['off'] if mode=='off' else (1., .96, .87, 1.) if kind=='fixed_white' else COLORS[mode]
                mesh=replace(mesh,color=(*tone[:3],mesh.color[3]))
        values.append(mesh)
    return tuple(values), dict(lighting_preview=dict(mode=mode,zones=rows,
        animated=False,device_control=False,installed_lighting_inferred=False,
        geometry_added=False,hardware_colors_are_measured=False))
