"""Exact GTX 1080 FE front reveal from its own source, not manufacturer CAD.

The eight head sites are fixed local registrations of independently observed
photo centres onto the existing authored frame; neither millimetre hole sites
nor hidden screws are verified. Existing 53-blade/rim/hub/interface data stay.
"""
import hashlib
import json
import math
from gpu_pascal_surface055 import WINDOW_UV,HEAD_UV

IDENTITY='nvidia-gtx1080-founders'
SOURCE='https://images.nvidia.com/aem-dam/Solutions/geforce/news/geforce-gtx-1080-founders-edition/nvidia-geforce-gtx-1080-Front.png'
# Actual ProfileReader map: only the dark inset / flat fin background / first
# flat fin are bound. The other three observed facet layers remain authored.
BOUND_LAYER_SHA256={0:'0c6c94910361d8c2a34ae2ea27f86766fc62ccd3bb2455fc958b399042e4cf4b',
    4:'7eae46cff4a2280517dc0f1321f535c49d526fd02d1e3d6482e41a3063bf35ab',
    5:'3d855dc8dce94185439a1dee94bfce492db0432473a25f2993edd5121739182f'}
HORIZONTAL_FIN_LAYER055_SHA256='92db219436f0f1480ba0e1a1296d1780e4d42eccd58b2f0732be2b44e1b88851'
HEAD_PHOTO_PIXELS=((518.,231.),(919.,251.),(518.,634.),(919.,614.),
                   (1101.,241.),(1573.,242.),(1101.,631.),(1573.,631.))

def front_reference(gpu,length,width,thickness,fan_holes):
    """Fixed source binding; unknown nominal dimensions never gain facts."""
    if not isinstance(gpu,dict):return {}
    appearance=gpu.get('appearance')
    if not isinstance(appearance,dict) or appearance.get('id')!=IDENTITY:return {}
    if not all(type(v) in (int,float) and 0<v<=10000 and math.isfinite(v) for v in (length,width,thickness)):return {}
    rows=gpu.get('detail_polygons')
    if not isinstance(rows,list) or len(rows)!=6:return {}
    for index,row in enumerate(rows):
        points=row.get('points') if isinstance(row,dict) else None
        if (not isinstance(points,list) or not 3<=len(points)<=512 or any(not isinstance(p,(list,tuple)) or len(p)!=2
                or any(type(v) not in (int,float) or not -.3<=v<=1.3 or not math.isfinite(v) for v in p) for p in points)):return {}
        if index in BOUND_LAYER_SHA256:
            raw=json.dumps(points,separators=(',',':'),allow_nan=False).encode()
            checksum=hashlib.sha256(raw).hexdigest()
            if checksum!=BOUND_LAYER_SHA256[index] and not(index==5 and checksum==HORIZONTAL_FIN_LAYER055_SHA256):return {}
    if (not isinstance(fan_holes,(tuple,list)) or len(fan_holes)!=1 or not isinstance(fan_holes[0],(tuple,list))
            or len(fan_holes[0])!=3 or not all(type(v) in (int,float) and abs(v)<1e6 and math.isfinite(v) for v in fan_holes[0])
            or fan_holes[0][2]<=0):return {}
    outline=tuple(((u-.5)*length,(.5-v)*width) for u,v in WINDOW_UV)
    heads=tuple(((u-.5)*length,(.5-v)*width) for u,v in HEAD_UV)
    recess=min(.5,thickness*.06);head_depth=min(.45,recess*.9)
    return dict(cutouts=(outline,),window_outline=outline,source_bound_layers=(0,4,5),fan_holes=tuple(tuple(h)for h in fan_holes),
        replaced_source_layers=(4,5),preserved_source_frame_layers=(1,2,3),
        paint_head_seats=tuple((u,v,2.35) for u,v in heads),head_centers=heads,
        head_radius=2.2,head_depth=head_depth,head_back_y=recess,
        pane_center_y=.75,pane_depth=.2,fin_front_y=1.15,fin_depth=min(8.,thickness*.12),source=SOURCE)

def refine(meshes,spec,level):
    """One static reveal; existing rotor/fixed rim/hub/ports are never edited."""
    gpu=spec.get('gpu') or {}
    if (gpu.get('appearance') or {}).get('id')!=IDENTITY:return meshes,{}
    shell=next((m for m in meshes if m.component=='gpu' and m.name=='gpu-shroud'),None)
    if shell is None:return meshes,dict(pascal_front_unavailable='missing_existing_shell')
    width,thickness,length=tuple(max(shell.vertices[k::6])-min(shell.vertices[k::6]) for k in range(3))
    gx,gy,gz=shell.position
    openings=[m for m in meshes if m.component=='gpu' and m.name=='gpu-fan-opening' and m.position[1]<gy]
    holes=[(m.position[2]-gz,-(m.position[0]-gx),max(abs(v) for v in m.vertices[0::6])*1.005) for m in openings]
    ref=front_reference(gpu,length,width,thickness,holes)
    if not ref:return meshes,dict(pascal_front_unavailable='source_profile_binding_or_reference_bounds_unavailable')
    from assembly_geometry import Mesh,box,color,extrude,gpu_plane,ring
    # The existing pure scanline implementation stays byte-for-byte unchanged.
    from assembly_gpu_exterior053 import _scanline_span
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
    head=gpu_plane(ring(ref['head_radius'],.65,ref['head_depth'],segments=segments))
    recess=gpu_plane(ring(.64,0.,.05,segments=segments));heads=[];recesses=[]
    for u,v in ref['head_centers']:
        for source,target,y in ((head,heads,ref['head_back_y']-ref['head_depth']/2),(recess,recesses,ref['head_back_y']-.025)):
            offset=(-v,-thickness/2+y,u)
            for n in range(0,len(source),6):target.extend((*(source[n+k]+offset[k] for k in range(3)),*source[n+3:n+6]))
    part=shell.part_id or 'gpu:0'
    added=(Mesh('detail-gpu-pascal-fin-samples',tuple(fins),color('#2b3338'),shell.position,'gpu',part_id=part),
        Mesh('detail-gpu-pascal-clear-reference',gpu_plane(extrude(ref['window_outline'],ref['pane_depth'])),color('#c2d4df',alpha=.12),
             (gx,gy-thickness/2+ref['pane_center_y'],gz),'gpu',part_id=part),
        Mesh('detail-gpu-pascal-fixed-heads',tuple(heads),color('#bac1c7'),shell.position,'gpu',part_id=part),
        Mesh('detail-gpu-pascal-head-recesses',tuple(recesses),color('#242a2e'),shell.position,'gpu',part_id=part))
    from gpu_pascal_surface055 import relief_meshes
    relief,relief_metadata=relief_meshes(shell,ref,level)
    return tuple((*meshes,*added,*relief)),dict(pascal_front_source=SOURCE,front_window_geometry='exact_source_profile_photo_reference_not_CAD',
        front_window_uv=WINDOW_UV,source_bound_layers=(0,4,5),original_source_frame_layers_preserved=(1,2,3),
        replaced_flat_fin_source_layers=(4,5),added_meshes=4+len(relief),fin_sampling_count=count,
        source_observed_screw_heads=8,head_photo_pixels=HEAD_PHOTO_PIXELS,head_reference_uv=HEAD_UV,
        head_reference_projection='Fixed local source-art registration, photo-window edge / captured fan-centre landmarks; not calibrated manufactured holes',
        screw_positions_accuracy='photo_reference_unmeasured',screw_geometry='visible_heads_and_unidentified_recesses_only',
        window_face_accuracy='visually_clear_photo_reference_chemistry_and_thickness_unverified',
        reference_depth_unmeasured=True,manufacturer_dimensions_verified=False,hidden_heatpipes_modelled=False,
        source_existing_blade_count=53,rotor_geometry_changed=False,blade_counts_changed=False,fixed_rim_geometry_preserved=True,
        full_tessellated_body_3D_modelled=False,rear_split_geometry_modelled=False,**relief_metadata)
