"""Bounded PCIe disengagement demonstration; pure math and finite state only.

This moves the selected GPU along the posed motherboard normal inside the
case. It is not a screw/latch-removal procedure, cable animation or a complete
extraction outside the enclosure. No geometry, input scene or device changes.
"""
import math


def _point(value):
    if not isinstance(value,(tuple,list)) or len(value)!=3:return None
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in value):return None
    return tuple(float(v) for v in value)


def _unit(value):
    value=_point(value)
    if value is None:return None
    length=math.hypot(*value)
    return tuple(v/length for v in value) if math.isfinite(length) and length>1e-9 else None


def _mapping(value):return value if isinstance(value,dict) else {}


def _prefix_match(name,prefix):return name==prefix or name.startswith(prefix+'-')


def _unavailable(reason):
    return dict(available=False,reason=reason,direction=(0.,0.,0.),distance_mm=0.,gpu_cable_prefixes=())


def _gpu_bounds(meshes):
    low=[float('inf')]*3;high=[-float('inf')]*3;found=False
    for mesh in meshes:
        if getattr(mesh,'component',None)!='gpu':continue
        values=getattr(mesh,'vertices',());position=_point(getattr(mesh,'position',None))
        if position is None or not values or len(values)%6:return None
        found=True;rotor=getattr(mesh,'rotor',False);axis=_unit(getattr(mesh,'axis',None)) if rotor else None
        if rotor and axis is None:return None
        axial_low=float('inf');axial_high=-float('inf');radial_squared=0.
        for offset in range(0,len(values),6):
            point=values[offset:offset+3]
            if any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in point):return None
            if rotor:
                axial=sum(point[k]*axis[k] for k in range(3))
                axial_low=min(axial_low,axial);axial_high=max(axial_high,axial)
                radial_squared=max(radial_squared,sum((point[k]-axis[k]*axial)**2 for k in range(3)))
            else:
                for k in range(3):
                    value=point[k]+position[k];low[k]=min(low[k],value);high[k]=max(high[k],value)
        if rotor:
            radius=math.sqrt(radial_squared)
            for k in range(3):
                # The whole rotor sweep, not one sampled blade phase, must fit.
                reach=radius*math.sqrt(max(0.,1.-axis[k]*axis[k]))
                ends=(axis[k]*axial_low,axis[k]*axial_high)
                low[k]=min(low[k],position[k]+min(ends)-reach)
                high[k]=max(high[k],position[k]+max(ends)+reach)
    return (tuple(low),tuple(high)) if found else None


def _gpu_cables(meshes,metadata):
    auxiliary=_mapping(metadata.get('auxiliary'));rows=auxiliary.get('cables',())
    if not isinstance(rows,(list,tuple)):return None,'gpu_cable_metadata_invalid'
    cable_meshes=[mesh for mesh in meshes if getattr(mesh,'component',None)=='cables']
    prefixes=[];other=[]
    for row in rows:
        if not isinstance(row,dict):return None,'gpu_cable_metadata_invalid'
        prefix=row.get('mesh_prefix')
        if row.get('target_owner')=='gpu':
            if not isinstance(prefix,str) or not prefix or len(prefix)>160:return None,'gpu_cable_prefix_missing'
            matched=[mesh for mesh in meshes if _prefix_match(getattr(mesh,'name',''),prefix)]
            if not matched or any(getattr(mesh,'component',None)!='cables' for mesh in matched):return None,'gpu_cable_geometry_unverified'
            if prefix in prefixes:return None,'gpu_cable_prefix_ambiguous'
            prefixes.append(prefix)
        elif isinstance(prefix,str) and prefix:other.append(prefix)
    for prefix in prefixes:
        if any(_prefix_match(prefix,value) or _prefix_match(value,prefix) for value in other):
            return None,'gpu_cable_prefix_ambiguous'
    if any(_prefix_match(a,b) or _prefix_match(b,a) for i,a in enumerate(prefixes) for b in prefixes[i+1:]):
        return None,'gpu_cable_prefix_ambiguous'
    # Older scenes may contain real GPU power geometry but no detached owner
    # mapping. Never guess which unrelated cable or plug should disappear.
    for mesh in cable_meshes:
        name=getattr(mesh,'name','').lower()
        if any(token in name for token in ('gpu6','gpu8','gpu16','gpu-power')) and not any(_prefix_match(mesh.name,p) for p in prefixes):
            return None,'gpu_cable_prefix_missing'
        if not any(_prefix_match(mesh.name,p) for p in prefixes+other):
            return None,'cable_owner_unverified'
    if auxiliary.get('cable_count',0) and not rows:return None,'gpu_cable_metadata_invalid'
    return tuple(prefixes),''


def insertion_plan(scene):
    """Return a detached one-scene plan. Cache it; do not rescan per frame.

    Prefixes denote exact names or ``prefix + '-'`` descendants, not arbitrary
    string prefixes. The caller may temporarily hide only these GPU power
    meshes; all fixed hardware and all physical arrays remain unchanged.
    """
    if scene is None:return _unavailable('scene_unavailable')
    metadata=_mapping(getattr(scene,'metadata',None));meshes=getattr(scene,'meshes',())
    if metadata.get('gpu_mount') not in ('horizontal','direct'):return _unavailable('gpu_mount_unsupported')
    cooling=_mapping(metadata.get('cooling'))
    if metadata.get('gpu_cooler_replaced') or cooling.get('replace_gpu_cooler') or any(
            getattr(mesh,'part_id',None)=='gpu:waterblock' or getattr(mesh,'name','').startswith('gpu-waterblock') for mesh in meshes):
        return _unavailable('gpu_waterblock_unsupported')
    board=_mapping(_mapping(metadata.get('attachment_anchors')).get('board'))
    direction=_unit(board.get('normal'))
    if direction is None:return _unavailable('board_normal_unverified')
    dimensions=_point(getattr(scene,'dimensions',None))
    if dimensions is None or any(v<=0 for v in dimensions):return _unavailable('case_dimensions_unverified')
    bounds=_gpu_bounds(meshes)
    if bounds is None:return _unavailable('gpu_geometry_unverified')
    low,high=bounds
    if any(low[k]<-dimensions[k]/2-1e-6 or high[k]>dimensions[k]/2+1e-6 for k in range(3)):
        return _unavailable('gpu_outside_case_envelope')
    available=52.
    for k,axis in enumerate(direction):
        if axis>1e-9:available=min(available,(dimensions[k]/2-8.-high[k])/axis)
        elif axis<-1e-9:available=min(available,(-dimensions[k]/2+8.-low[k])/axis)
    if not math.isfinite(available) or available<16.:return _unavailable('insufficient_side_clearance')
    prefixes,reason=_gpu_cables(meshes,metadata)
    if prefixes is None:return _unavailable(reason)
    return dict(available=True,reason='pcie_disengagement_reference',direction=direction,
                distance_mm=available,gpu_cable_prefixes=prefixes)


class GpuInsertion:
    """One finite smoothstep transition driven only by an existing clock.

    ``advance`` accepts elapsed *delta* milliseconds, capped at136 per tick.
    A full traversal takes960ms; a reversal keeps the current position and
    uses at most960ms. No loops, clock, timer, scene or mesh references live here.
    ``target`` is the numeric0/1 endpoint (inserted/disengaged).
    """
    DURATION_MS=960.
    MAX_TICK_MS=136.

    def __init__(self):
        self._progress=0.;self._active=False;self._target=0.;self._from=0.;self._elapsed=0.;self._duration=self.DURATION_MS

    @property
    def progress(self):return self._progress

    @property
    def active(self):return self._active

    @property
    def target(self):return self._target

    def start(self,removed):
        if type(removed) is not bool:return False
        target=1. if removed else 0.
        if target==self._target and (self._active or self._progress==target):return False
        self._target=target;self._from=self._progress;self._elapsed=0.
        self._duration=self.DURATION_MS*abs(target-self._progress)
        self._active=self._duration>1e-9
        if not self._active:self._progress=target
        return True

    def advance(self,elapsed_ms):
        if not self._active or type(elapsed_ms) not in (int,float) or not math.isfinite(elapsed_ms) or elapsed_ms<=0:return False
        self._elapsed=min(self._duration,self._elapsed+min(elapsed_ms,self.MAX_TICK_MS))
        phase=self._elapsed/self._duration;smooth=phase*phase*(3.-2.*phase)
        self._progress=self._from+(self._target-self._from)*smooth
        if self._elapsed>=self._duration:self._progress=self._target;self._active=False
        return True

    def reset(self):
        changed=self._progress!=0. or self._active or self._target!=0.
        self._progress=0.;self._target=0.;self._active=False;self._from=0.;self._elapsed=0.;self._duration=self.DURATION_MS
        return changed

    def offset(self,plan):
        if not isinstance(plan,dict) or plan.get('available') is not True:return (0.,0.,0.)
        direction=_point(plan.get('direction'));distance=plan.get('distance_mm')
        if direction is None or type(distance) not in (int,float) or not math.isfinite(distance) or not 0.<distance<=52.:return (0.,0.,0.)
        if abs(sum(v*v for v in direction)-1.)>1e-6:return (0.,0.,0.)
        return tuple(v*distance*self._progress for v in direction)
