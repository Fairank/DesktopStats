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
        metadata=dict(exterior053_source=KEPLER_SOURCE, fixed_silver_opening_rim=True,
                      added_meshes=0, fixed_rim_geometry_preserved=True,
                      rim_tone_accuracy='official_photo_reference_not_measured_paint',
                      blade_counts_changed=False, manufacturer_dimensions_verified=False)
        return _kepler_window(values,spec,level,metadata)
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


# Original proportional trace of the visible aperture: a bowed left edge and
# a chamfered right end, never a universal rectangular GPU window. Its source
# is exact 780 Ti style-2/front and style-3/window close-up. Coordinates and
# depths below are photo-reference, not manufacturer CAD or a material BOM.
KEPLER_WINDOW_UV=((.145,.20),(.515,.20),(.55,.30),(.55,.70),(.515,.80),
                  (.145,.80),(.13,.68),(.125,.50),(.13,.32))
KEPLER_WINDOW_SOURCE='https://images.nvidia.com/geforce/sites/default/files-world/geforce-gtx-780ti-style-3.png'


def kepler_front_reference(gpu,length,width,thickness,fan_holes,source_layers):
    """Fixed reference face and visible head seats, independent of LOD/style.

    The current exact catalog has documented length/height, but no documented
    cooler thickness. The existing body thickness remains a reference input;
    this helper does not replace it or establish a real installation envelope.
    """
    if not isinstance(gpu,dict):return {}
    appearance=gpu.get('appearance') or {}
    if appearance.get('id')!=KEPLER or source_layers!=6:return {}
    facts=appearance.get('board_details') or {};nominal=facts.get('dimensions_mm') or {}
    if not all(type(nominal.get(k)) in (int,float) and math.isfinite(nominal[k]) and nominal[k]>0
               for k in ('length','height')):return {}
    if not all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in (length,width,thickness)):return {}
    if (not isinstance(fan_holes,(tuple,list)) or len(fan_holes)!=1
            or not isinstance(fan_holes[0],(tuple,list)) or len(fan_holes[0])!=3
            or not all(type(v) in (int,float) and math.isfinite(v) and abs(v)<1e6 for v in fan_holes[0])
            or fan_holes[0][2]<=0):return {}
    outline=tuple(((u-.5)*length,(.5-v)*width) for u,v in KEPLER_WINDOW_UV)
    # Four clearly visible window-rail heads. The four blower-frame heads use
    # their observed corner relation to the retained aperture, not a new hub
    # center or a claim of manufacturer hole coordinates.
    heads=[((u-.5)*length,(.5-v)*width) for u in (.235,.46) for v in (.135,.895)]
    u,v,radius=fan_holes[0]
    heads.extend((u+sx*radius*.8,v+sy*radius*.8) for sx in (-1,1) for sy in (-1,1))
    recess=min(.5,thickness*.06);head_depth=min(.45,recess*.9)
    return dict(cutouts=(outline,),window_outline=outline,
                paint_head_seats=tuple((u,v,2.35) for u,v in heads),head_centers=tuple(heads),
                head_radius=2.2,head_depth=head_depth,head_back_y=recess,
                pane_center_y=.75,pane_depth=.2,fin_front_y=1.15,fin_depth=min(8.,thickness*.12),
                replaced_source_layers=(2,3,4,5),source=KEPLER_WINDOW_SOURCE)


def _scanline_span(poly,y):
    crossings=[]
    for a,b in zip(poly,(*poly[1:],poly[0])):
        if min(a[1],b[1])<=y<max(a[1],b[1]):
            crossings.append(a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1]))
    return (min(crossings),max(crossings)) if len(crossings)>=2 else None


def _kepler_window(meshes,spec,level,metadata):
    gpu=spec.get('gpu') or {}
    shell=next((m for m in meshes if m.name=='gpu-shroud'),None)
    if shell is None:return meshes,metadata
    width,thickness,length=tuple(max(shell.vertices[k::6])-min(shell.vertices[k::6]) for k in range(3))
    gx,gy,gz=shell.position
    openings=[m for m in meshes if m.name=='gpu-fan-opening' and m.position[1]<gy]
    holes=[(m.position[2]-gz,-(m.position[0]-gx),max(abs(v) for v in m.vertices[0::6])*1.005) for m in openings]
    ref=kepler_front_reference(gpu,length,width,thickness,holes,len(gpu.get('detail_polygons') or ()))
    if not ref:return meshes,metadata
    from assembly_geometry import Mesh,box,color,extrude,gpu_plane,ring
    # Fin count/pitch and hidden cooling paths are not established by the
    # photograph. These are bounded samples of the visible longitudinal bank.
    count=16 if level=='eco' else 48 if level=='close' else 32
    fins=[]
    for index in range(count):
        v=width*.56*(.5-index/(count-1));span=_scanline_span(ref['window_outline'],v)
        if span is None:continue
        low,high=span[0]+.6,span[1]-.6
        if high<=low:continue
        shape=box(.35,ref['fin_depth'],high-low)
        offset=(-v,-thickness/2+ref['fin_front_y']+ref['fin_depth']/2,(low+high)/2)
        for n in range(0,len(shape),6):fins.extend((*(shape[n+k]+offset[k] for k in range(3)),*shape[n+3:n+6]))
    segments=12 if level=='eco' else 28 if level=='close' else 20
    heads=[];recesses=[]
    head=gpu_plane(ring(ref['head_radius'],.65,ref['head_depth'],segments=segments))
    cavity=gpu_plane(ring(.64,0.,.05,segments=segments))
    for u,v in ref['head_centers']:
        # Head back meets the retained structural front reference face. Seats
        # remove only the former paint volume; no hidden shaft/thread is drawn.
        for source,target,y in ((head,heads,ref['head_back_y']-ref['head_depth']/2),
                                (cavity,recesses,ref['head_back_y']-.025)):
            offset=(-v,-thickness/2+y,u)
            for n in range(0,len(source),6):target.extend((*(source[n+k]+offset[k] for k in range(3)),*source[n+3:n+6]))
    pane=gpu_plane(extrude(ref['window_outline'],ref['pane_depth']))
    part=shell.part_id or 'gpu:0'
    additions=(Mesh('detail-gpu-window-fin-samples',tuple(fins),color('#2b3338'),(gx,gy,gz),'gpu',part_id=part),
               Mesh('detail-gpu-window-face',pane,color('#c2d4df',alpha=.12),
                    (gx,gy-thickness/2+ref['pane_center_y'],gz),'gpu',part_id=part),
               Mesh('detail-gpu-window-screw-heads',tuple(heads),color('#bac1c7'),(gx,gy,gz),'gpu',part_id=part),
               Mesh('detail-gpu-window-screw-recesses',tuple(recesses),color('#242a2e'),(gx,gy,gz),'gpu',part_id=part))
    info=dict(metadata)
    info.update(added_meshes=4,front_window_geometry='original_photo_reference_not_CAD',
                front_window_uv=KEPLER_WINDOW_UV,front_window_source=KEPLER_WINDOW_SOURCE,
                original_source_frame_layers_preserved=(0,1),replaced_flat_fin_source_layers=ref['replaced_source_layers'],
                fin_sampling_count=count,fin_count_is_sampling=True,source_observed_screw_heads=8,
                screw_geometry='visible_head_and_unidentified_recess_only_no_hidden_shaft_or_thread',
                screw_positions_accuracy='photo_reference_unmeasured_not_manufacturer_holes',
                window_face_accuracy='visually_clear_photo_reference_material_chemistry_and_thickness_unverified',
                reference_depth_unmeasured=True,manufacturer_thickness_verified=False,
                original_ports_pose_and_rotor_meshes_preserved=True,blade_counts_changed=False,
                hidden_heatpipes_modelled=False,visible_fin_fold_shape_not_reproduced=True)
    return tuple((*meshes,*additions)),info
