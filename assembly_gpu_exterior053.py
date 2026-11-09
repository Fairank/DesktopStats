"""Source-observed exterior details; no new rotor evidence.

Original reference construction, not manufacturer CAD. The N480 front window
comes from its own MSI source front and the already authored 0..100 window
rectangle; nominal product bounds remain in the existing catalog. Fins are
bounded visual samples, not a claimed manufactured count, pitch or hidden route.
No I/O, device access, clock, style-specific geometry, pose or socket changes.
"""
from dataclasses import replace
import math

N480 = 'msi-n480gtx-m2d15'
KEPLER = 'nvidia-gtx780ti-reference'
N480_SOURCE = 'https://storage-asset.msi.com/datasheet/vga/global/N480GTXM2D15.pdf'
KEPLER_SOURCE = 'https://images.nvidia.com/geforce/sites/default/files-world/geforce-gtx-780ti-style-2.png'
N480_WINDOW_UV = ((.03, .14), (.59, .14), (.59, .86), (.03, .86))


def _documented_n480(appearance):
    if not isinstance(appearance, dict) or appearance.get('id') != N480:
        return False
    dims = (appearance.get('board_details') or {}).get('dimensions_mm') or {}
    return all(type(dims.get(key)) in (int, float) and math.isfinite(dims[key]) and dims[key] > 0
               for key in ('length', 'height', 'thickness'))


def front_cutouts(appearance, length, width):
    """Return one fixed, source-authored front aperture for this exact card.

    UV is the original front's artwork coordinate system; no selected part,
    cable, collision result or rotor position can change this rectangle.
    """
    if not _documented_n480(appearance):
        return ()
    if not all(type(x) in (int, float) and math.isfinite(x) and x > 0 for x in (length, width)):
        return ()
    return (tuple(((u-.5)*length, (.5-v)*width) for u, v in N480_WINDOW_UV),)


def refine(meshes, spec, level):
    """Reuse existing independent meshes; an unknown rotor remains unknown."""
    appearance = ((spec.get('gpu') or {}).get('appearance') or {})
    identity = appearance.get('id')
    if identity == KEPLER:
        # The existing mouth ring is already fixed. Correct only its source
        # metal tone; never duplicate it or move it into a rotating mesh.
        from assembly_geometry import color
        values = tuple(replace(m, color=color('#c6ccd0'))
                       if m.component == 'gpu' and m.name == 'gpu-fan-opening' and not m.rotor else m
                       for m in meshes)
        return values, dict(exterior053_source=KEPLER_SOURCE, fixed_silver_opening_rim=True,
                            added_meshes=0, fixed_rim_geometry_preserved=True,
                            rim_tone_accuracy='official_photo_reference_not_measured_paint',
                            blade_counts_changed=False, manufacturer_dimensions_verified=False)
    if not _documented_n480(appearance):
        return meshes, {}
    shell = next((m for m in meshes if m.component == 'gpu' and m.name == 'gpu-shroud'), None)
    existing = next((m for m in meshes if m.component == 'gpu' and m.name == 'detail-gpu-heatsink-fins'), None)
    if shell is None or existing is None:
        return meshes, dict(exterior053_source=N480_SOURCE, prepared_exterior_unavailable='missing_existing_source_shell_or_fin_mesh')
    from assembly_geometry import box, color
    width, thickness, length = tuple(max(shell.vertices[k::6])-min(shell.vertices[k::6]) for k in range(3))
    if not all(math.isfinite(x) and x > 0 for x in (width, thickness, length)):
        return meshes, {}
    # Horizontal source ridges run along card length, not an arbitrary full
    # card fin bank behind an opaque painted cap. The window is opened by the
    # caller in BOTH structural shell and the existing disjoint paint layers.
    count = 8 if level == 'eco' else 24 if level == 'close' else 16
    rows = []
    depth = thickness*.16
    for index in range(count):
        x = width*(-.345 + .690*index/(count-1))
        center = (x, -thickness/2+.8+depth/2, -length*.19)
        rows.append((box(width*.006, depth, length*.56), center))
    # The four narrow front cross-supports are visible in the same photo and
    # pre-existing source drawing. Their back faces meet the sampled fin front
    # plane; no manufacturer join, hidden heatpipe or screw is invented.
    for u in (.14, .26, .38, .50):
        rows.append((box(width*.72, .65, length*.013),
                     (0., -thickness/2+.475, (u-.5)*length)))
    vertices = []
    for shape, offset in rows:
        for n in range(0, len(shape), 6):
            vertices.extend((shape[n]+offset[0], shape[n+1]+offset[1], shape[n+2]+offset[2],
                             *shape[n+3:n+6]))
    values = tuple(replace(m, vertices=tuple(vertices), color=color('#acb7bf')) if m is existing else m
                   for m in meshes)
    return values, dict(exterior053_source=N480_SOURCE, exposed_front_fin_window=True,
                        front_window_uv=N480_WINDOW_UV, fin_sampling_count=count,
                        fin_count_is_sampling=True, source_observed_fixed_cross_supports=4,
                        front_window_geometry='original_photo_reference_not_CAD',
                        manufacturer_dimensions_verified=False, reference_depth_unmeasured=True,
                        added_meshes=0, original_ports_pose_and_rotor_meshes_preserved=True,
                        blade_counts_changed=False, bounds_expansion_intended=False)


LEADTEK = 'leadtek-hurricane-4090-24g'
LEADTEK_SOURCE = 'https://www.leadtek.com/eng/products/graphics_cards(1)/WinFast_RTX_4090_HURRICANE_24G(40950)/detail'


def fixed_front_layers(gpu, polygon_count, fan_holes):
    """Exact source's two existing fixed X paint regions cross its middle bay.

    Their original U/V contours stay unchanged. Front depth .2 and center .1
    are an original photo-reference layer strategy, not measured frame metal,
    a manufacturer's clearance or an exemption for a colliding hub. Unknown
    middle blades and every original rotor/hub/port remain untouched.
    """
    if not isinstance(gpu, dict) or (gpu.get('appearance') or {}).get('id') != LEADTEK:
        return {}
    if type(polygon_count) is not int or polygon_count != 4 or len(fan_holes) != 3:
        return {}
    if not all(isinstance(h, (tuple, list)) and len(h) == 3
               and all(type(v) in (int, float) and math.isfinite(v) and abs(v) <= 1e6 for v in h)
               and h[2] > 0 for h in fan_holes):
        return {}
    order=sorted(range(3), key=lambda n: fan_holes[n][0])
    if not fan_holes[order[0]][0] < fan_holes[order[1]][0] < fan_holes[order[2]][0]:
        return {}
    center=order[1];outer=tuple(n for n in range(3) if n != center)
    return dict(fan_indices=(outer, outer, (0, 1, 2), (0, 1, 2)),
                depths=(.2, .2, .3, .3), center_offsets=(.1, .1, .2, .2),
                metadata=dict(fixed_center_x_frame=True, fixed_x_source=LEADTEK_SOURCE,
                              fixed_x_source_layer_indices=(0, 1), fixed_x_center_fan_index=center,
                              fixed_x_depth_mm_reference=.2, fixed_x_center_offset_mm_reference=.1,
                              fixed_x_depth_accuracy='official_photo_reference_unmeasured',
                              fixed_x_manufacturer_clearance_verified=False,
                              fixed_x_blade_counts_changed=False))
