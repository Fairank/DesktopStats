"""Construction-only bottom pose from existing generic reference material.

This corrects a datum in our schematic geometry, not a manufacturer's mounting
plane, hole position, airflow design or mechanical compatibility guarantee.
Authored bottom planes and non-generic/custom floors are never overridden.
"""
from collections.abc import Sequence
import math

MAX_MESHES=4096
MAX_SOURCE_VERTICES=32768
DRAWING_GAP_MM=.25
_REFERENCE_INSET_MM=12.
_BASIS=((1.,0.,0.),(0.,0.,1.),(0.,-1.,0.))
_LEFT_WALL_NAMES=frozenset(('left-glass','left-panel'))


def _finite(value):return type(value) in (int,float) and math.isfinite(value)


def _vector(value,*,positive=False):
    return (isinstance(value,(list,tuple)) and len(value)==3
            and all(_finite(v) and (0<v<=2000 if positive else abs(v)<=10000) for v in value))


def _source_bounds(mesh,layer_axis):
    """One bounded scan; retain bounds/two slab planes, not source arrays."""
    position=getattr(mesh,'position',None);values=getattr(mesh,'vertices',None)
    if not _vector(position) or getattr(mesh,'rotor',False) is not False:return None
    if not isinstance(values,Sequence) or isinstance(values,(str,bytes,bytearray)):return None
    size=len(values)
    if not 18<=size<=MAX_SOURCE_VERTICES*6 or size%18:return None
    low=[math.inf]*3;high=[-math.inf]*3;layers=[]
    for start in range(0,size,6):
        p=values[start:start+6]
        if len(p)!=6 or not all(_finite(v) and abs(v)<=10000 for v in p):return None
        normal_squared=sum(v*v for v in p[3:])
        if not .99<=normal_squared<=1.01:return None
        for k in range(3):
            value=p[k]+position[k]
            low[k]=min(low[k],value);high[k]=max(high[k],value)
        value=p[layer_axis]+position[layer_axis]
        if not any(abs(value-v)<=1e-6 for v in layers):
            layers.append(value)
            if len(layers)>2:return None
    if len(layers)!=2 or any(high[k]-low[k]<=1e-7 for k in range(3)):return None
    return (tuple(low),tuple(high))


def reference_bottom_pose(meshes,dimensions,fan_half_extents,existing_planes):
    """Return None or detached ``center/basis/span/meta`` for a generic floor.

    ``fan_half_extents`` are conservative LOCAL width/length/axis half extents,
    supplied by the existing fan geometry envelope function. Only the axial
    value affects height. The X window derives from fixed case material, never
    selected GPU/PSU/fan width. The caller must reject whole groups that exceed
    this span or collide with other actual material; this is no fit approval.
    """
    if not isinstance(existing_planes,dict) or 'bottom' in existing_planes:return None
    if (not _vector(dimensions,positive=True) or any(v<60 for v in dimensions)
            or not _vector(fan_half_extents,positive=True)):
        return None
    if not isinstance(meshes,(list,tuple)) or not 1<=len(meshes)<=MAX_MESHES:return None
    floor=[];divider=[];left_wall=[]
    for mesh in meshes:
        name=getattr(mesh,'name',None);owner=getattr(mesh,'component',None)
        if not isinstance(name,str) or not isinstance(owner,str):return None
        if name=='case-bottom':
            if owner!='case':return None
            floor.append(mesh)
        elif name=='rear-chamber-divider':
            if owner!='case':return None
            divider.append(mesh)
        elif name in _LEFT_WALL_NAMES:
            if owner not in ('case','panel'):return None
            left_wall.append(mesh)
    if len(floor)!=1 or len(divider)>1 or len(left_wall)>1:return None
    w,h,d=map(float,dimensions);fb=_source_bounds(floor[0],1)
    if fb is None:return None
    thickness=fb[1][1]-fb[0][1]
    # A generic floor is a wide, shallow horizontal slab in the lower case.
    # A small hardware box, tall block, raised deck or arbitrary named surface
    # cannot silently become this datum.
    if (not 0<thickness<=8. or fb[1][0]-fb[0][0]<w*.5 or fb[1][2]-fb[0][2]<d*.5
            or fb[0][1]<-h/2-2. or fb[1][1]>-h*.15
            or abs(fb[0][0]+w/2)>2. or abs(fb[1][0]-w/2)>2.
            or abs(fb[0][2]+d/2)>2. or abs(fb[1][2]-d/2)>2.):
        return None
    span_z=min(d-32.,fb[1][2]-fb[0][2]-32.)
    center_x=0.;span_x=min(w-24.,fb[1][0]-fb[0][0]-24.)
    names=['case-bottom'];db=None;wb=None;window=None
    left_basis='canonical_centered_generic_floor_window'
    if divider:
        db=_source_bounds(divider[0],0)
        if db is None:return None
        if (db[1][0]-db[0][0]>8. or db[1][1]-db[0][1]<h*.45
                or db[1][2]-db[0][2]<d*.45 or db[0][0]<=fb[0][0]+24.
                or db[1][0]>=fb[1][0] or db[0][1]<-h/2-2. or db[1][1]>h/2+2.
                or db[0][2]<-d/2-2. or db[1][2]>d/2+2.):
            return None
        names.append('rear-chamber-divider')
        left=max(fb[0][0],-w/2)+_REFERENCE_INSET_MM
        left_basis='generic_floor_left_extent_plus_12mm_reference'
        if left_wall:
            wb=_source_bounds(left_wall[0],0)
            if wb is None:return None
            if (wb[1][0]-wb[0][0]>8. or wb[1][1]-wb[0][1]<h*.45
                    or wb[1][2]-wb[0][2]<d*.45 or abs(wb[0][0]+w/2)>8.
                    or wb[1][0]>=db[0][0] or wb[0][1]<-h/2-2. or wb[1][1]>h/2+2.
                    or wb[0][2]<-d/2-2. or wb[1][2]>d/2+2.):
                return None
            left=max(fb[0][0],wb[1][0])+DRAWING_GAP_MM
            left_basis='actual_current_left_skin_inner_surface_plus_reference_gap'
            names.append(left_wall[0].name)
        right=db[0][0]-DRAWING_GAP_MM
        if right<=left:return None
        window=(left,right);span_x=right-left;center_x=(left+right)/2
    if span_x<=0 or span_z<=0:return None
    center=(center_x,fb[1][1]+float(fan_half_extents[2])+DRAWING_GAP_MM,0.)
    if (center[1]+float(fan_half_extents[2])>h/2 or abs(center_x)>w/2):return None
    meta=dict(method='existing_generic_reference_floor_and_main_bay_datum',
        reference_only=True,positions_verified=False,mounting_holes_verified=False,
        manufacturer_plane_verified=False,mechanical_installation_verified=False,
        complete_fit_verified=False,airflow_design_verified=False,
        source_geometry_names=tuple(names),floor_bounds_mm=fb,divider_bounds_mm=db,
        left_skin_bounds_mm=wb,left_boundary_basis=left_basis,main_bay_x_window_mm=window,
        floor_top_y_mm=fb[1][1],conservative_fan_axis_half_extent_mm=float(fan_half_extents[2]),
        drawing_gap_mm=DRAWING_GAP_MM,drawing_gap_verified=False,
        canonical_basis_preserved=True,fan_order_world_axis=(0.,0.,1.),
        center_x_independent_of_selected_components=True,
        whole_group_span_and_actual_material_check_required=True,
        maximum_meshes=MAX_MESHES,maximum_source_vertices=MAX_SOURCE_VERTICES,
        source_geometry_scans=len(names),new_meshes=0,new_clocks=0,new_pollers=0)
    return dict(center=center,basis=_BASIS,span=(span_x,span_z),meta=meta)
