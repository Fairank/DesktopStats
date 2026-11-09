"""Bounded visible-reference CPU/DIMM/case-fan motion; no I/O or clocks.

Plans use posed source geometry. They demonstrate socket disengagement inside
an explicitly visible reference assembly, not a manufacturer's removal guide,
retention mechanism animation or full extraction outside the case.
Case-fan frames additionally require explicit reference fixing/connection release.
"""
import math
from collections import OrderedDict
from copy import deepcopy

MAX_MESHES=4096
MAX_TARGET_TRIANGLES=16000
MAX_CANDIDATE_TRIANGLES=100000
MAX_SWEEP_TESTS=160000
MAX_SELECTORS=64
CONTACT_EPS=1.e-5
CASE_MARGIN_MM=2.
CPU_RETENTION=('detail-board-retention-frame','detail-board-retention-hinge',
 'detail-board-retention-lever','board-am4-zif-locking-lever')
MEMORY_RETENTION=('board-dimm-end-latches',)

def _point(v):
 if not isinstance(v,(tuple,list)) or len(v)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) for x in v):return None
 return tuple(float(x) for x in v)
def _unit(v):
 p=_point(v)
 if p is None:return None
 length=math.hypot(*p)
 return tuple(x/length for x in p) if math.isfinite(length) and length>1.e-9 else None
def _sub(a,b):return (a[0]-b[0],a[1]-b[1],a[2]-b[2])
def _add(a,b):return (a[0]+b[0],a[1]+b[1],a[2]+b[2])
def _mul(a,t):return (a[0]*t,a[1]*t,a[2]*t)
def _dot(a,b):return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def _cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def _map(v):return v if isinstance(v,dict) else {}
def _selected(mesh,key):return getattr(mesh,'component','')==key or getattr(mesh,'part_id','')==key or key=='case' and getattr(mesh,'component','')=='panel'
def _prefix(name,prefix):return name==prefix or name.startswith(prefix+'-')
def _keys(meshes,values):
 if not isinstance(values,(tuple,list,set,frozenset)) or len(values)>MAX_SELECTORS:return None
 result=[]
 for value in values:
  if not isinstance(value,str) or not value or len(value)>160 or not any(_selected(m,value) for m in meshes):return None
  if value not in result:result.append(value)
 return tuple(result)

def _connection_names(scene,selectors):
 meshes=tuple(getattr(scene,'meshes',()) or ());rows=_map(_map(getattr(scene,'metadata',None)).get('auxiliary')).get('cables',())
 if not isinstance(rows,(tuple,list)) or len(rows)>256:return (),False
 def owner_hidden(owner):
  if not isinstance(owner,str) or not owner:return False
  if owner in selectors:return True
  owners=[m for m in meshes if getattr(m,'part_id','')==owner]
  if not owners:owners=[m for m in meshes if getattr(m,'component','')==owner]
  chosen=[any(_selected(m,key) for key in selectors) for m in owners]
  if any(chosen) and not all(chosen):return None
  return bool(owners) and all(chosen)
 prefixes=[];others=[]
 for row in rows:
  if not isinstance(row,dict):return (),False
  source,target=owner_hidden(row.get('source_owner')),owner_hidden(row.get('target_owner'))
  if source is None or target is None:return (),False
  linked=source or target
  value=row.get('mesh_prefix')
  if linked:
   if not isinstance(value,str) or not value or len(value)>160:return (),False
   matches=[m for m in meshes if _prefix(getattr(m,'name',''),value)]
   if not matches or any(getattr(m,'component','')!='cables' for m in matches):return (),False
   prefixes.append(value)
  elif isinstance(value,str) and value:others.append(value)
 if len(set(prefixes))!=len(prefixes) or any(_prefix(a,b) or _prefix(b,a) for i,a in enumerate(prefixes) for b in prefixes[i+1:]+others):return (),False
 names=tuple(sorted({getattr(m,'name','') for m in meshes if any(_prefix(getattr(m,'name',''),p) for p in prefixes)}))
 return (names,True) if len(names)<=2048 else ((),False)

def hidden_connections(scene,hidden_parts=()):
 """Exact existing cable meshes owned by explicitly hidden source parts.

 Call only when scene/hidden selection changes, including unsupported movers.
 No proximity, model-name or string-prefix owner inference is performed.
 """
 meshes=tuple(getattr(scene,'meshes',()) or ())
 if not meshes or len(meshes)>MAX_MESHES:return ()
 selectors=_keys(meshes,hidden_parts)
 if selectors is None:return ()
 names,valid=_connection_names(scene,selectors)
 return names if valid else ()

def _bounds(mesh,shift=(0.,0.,0.)):
 values=getattr(mesh,'vertices',());p=_point(getattr(mesh,'position',None))
 if p is None or not values or len(values)%18:return None
 low=[float('inf')]*3;high=[-float('inf')]*3
 rotor=getattr(mesh,'rotor',False);axis=_unit(getattr(mesh,'axis',None)) if rotor else None
 if rotor and axis is None:return None
 axial_low=float('inf');axial_high=-float('inf');radial=0.
 for at in range(0,len(values),6):
  point=values[at:at+3]
  if any(type(x) not in (int,float) or not math.isfinite(x) for x in values[at:at+6]):return None
  if rotor:
   projection=_dot(point,axis);axial_low=min(axial_low,projection);axial_high=max(axial_high,projection)
   radial=max(radial,_dot(_sub(point,_mul(axis,projection)),_sub(point,_mul(axis,projection))))
  else:
   for k in range(3):
    value=point[k]+p[k]+shift[k];low[k]=min(low[k],value);high[k]=max(high[k],value)
 if rotor:
  radius=math.sqrt(radial)
  for k in range(3):
   reach=radius*math.sqrt(max(0.,1.-axis[k]*axis[k]));ends=(axis[k]*axial_low,axis[k]*axial_high)
   low[k]=p[k]+shift[k]+min(ends)-reach;high[k]=p[k]+shift[k]+max(ends)+reach
 return tuple(low),tuple(high)
def _union(bounds):
 # Six scalar comparisons per item avoid six generator rescans at every
 # temporary BVH branch; this changes no geometric or contact tolerance.
 lo=list(bounds[0][0]);hi=list(bounds[0][1])
 for a,b in bounds[1:]:
  if a[0]<lo[0]:lo[0]=a[0]
  if a[1]<lo[1]:lo[1]=a[1]
  if a[2]<lo[2]:lo[2]=a[2]
  if b[0]>hi[0]:hi[0]=b[0]
  if b[1]>hi[1]:hi[1]=b[1]
  if b[2]>hi[2]:hi[2]=b[2]
 return tuple(lo),tuple(hi)
def _overlap(a,b,epsilon=CONTACT_EPS):
 return a[0][0]<=b[1][0]+epsilon and b[0][0]<=a[1][0]+epsilon and a[0][1]<=b[1][1]+epsilon and b[0][1]<=a[1][1]+epsilon and a[0][2]<=b[1][2]+epsilon and b[0][2]<=a[1][2]+epsilon
def _boundary_separated(a,b):
 # Closed half-space separation proves no positive-volume intersection.
 # Equality permits pure tangential contact, never a finite penetration:
 # a is already the entire continuous sweep, not just its final endpoint.
 return any(a[1][k]<=b[0][k] or b[1][k]<=a[0][k] for k in range(3))
def _contains(a,b):return all(a[0][k]-CONTACT_EPS<=b[0][k] and a[1][k]+CONTACT_EPS>=b[1][k] for k in range(3))
def _shift_bounds(b,p):return tuple(tuple(b[i][k]+p[k] for k in range(3)) for i in (0,1))
def _project_box(b,n):
 center=tuple((a+v)/2 for a,v in zip(*b));reach=sum((b[1][k]-b[0][k])*.5*abs(n[k]) for k in range(3));value=_dot(center,n)
 return value-reach,value+reach
def _project_mesh(mesh,bounds,direction):
 if max(abs(v) for v in direction)>1.-1.e-12:return _project_box(bounds,direction)
 low=float('inf');high=-float('inf');v=mesh.vertices;offset=_dot(mesh.position,direction)
 for at in range(0,len(v),6):
  value=v[at]*direction[0]+v[at+1]*direction[1]+v[at+2]*direction[2]+offset
  low=min(low,value);high=max(high,value)
 return low,high
def _swept(bounds,direction,distance):
 end=tuple(direction[k]*distance for k in range(3))
 return tuple(tuple(bounds[side][k]+(min(0.,end[k]) if side==0 else max(0.,end[k])) for k in range(3)) for side in (0,1))
def _triangle(a,b,c):
 edges=(_sub(b,a),_sub(c,b),_sub(a,c));normal=_cross(edges[0],_sub(c,a))
 if _dot(normal,normal)<1.e-20:return None
 bounds=(tuple(min(a[k],b[k],c[k]) for k in range(3)),tuple(max(a[k],b[k],c[k]) for k in range(3)))
 return a,b,c,edges,normal,bounds
def _triangles(mesh,shift,bounds,region=None):
 if getattr(mesh,'rotor',False):
  lo,hi=bounds;points=[(x,y,z) for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])]
  faces=((0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3));result=[]
  for a,b,c,d in faces:
   for ids in ((a,b,c),(a,c,d)):
    tri=_triangle(*(points[i] for i in ids))
    if tri:result.append(tri)
  return result
 p=_add(_point(mesh.position),shift);v=mesh.vertices;result=[]
 for at in range(0,len(v),18):
  if region is not None and any(max(v[at+k],v[at+6+k],v[at+12+k])+p[k]<region[0][k]-CONTACT_EPS or min(v[at+k],v[at+6+k],v[at+12+k])+p[k]>region[1][k]+CONTACT_EPS for k in range(3)):continue
  tri=_triangle(*(tuple(v[at+offset+k]+p[k] for k in range(3)) for offset in (0,6,12)))
  if tri:result.append(tri)
 return result

def _tree(triangles):
 bounds=_union([t[5] for t in triangles])
 if len(triangles)<=24:return bounds,None,None,tuple(triangles)
 axis=max(range(3),key=lambda k:bounds[1][k]-bounds[0][k]);ordered=sorted(triangles,key=lambda t:t[5][0][axis]+t[5][1][axis]);mid=len(ordered)//2
 return bounds,_tree(ordered[:mid]),_tree(ordered[mid:]),()
def _query(tree,bounds):
 stack=[tree]
 while stack:
  node=stack.pop()
  if not _overlap(node[0],bounds):continue
  if node[3]:
   for tri in node[3]:
    if _overlap(tri[5],bounds):yield tri
  else:stack.extend((node[1],node[2]))

def _sweep_triangle(a,b,direction,distance):
 """Continuous translation SAT, including coplanar in-plane separators."""
 axes=[a[4],b[4]];axes.extend(_cross(x,y) for x in a[3] for y in b[3])
 if _dot(_cross(a[4],b[4]),_cross(a[4],b[4]))<1.e-14*_dot(a[4],a[4])*_dot(b[4],b[4]):
  axes.extend(_cross(a[4],edge) for edge in (*a[3],*b[3]))
 near,far=0.,distance
 for axis in axes:
  square=_dot(axis,axis)
  if square<1.e-20:continue
  pa=(_dot(a[0],axis),_dot(a[1],axis),_dot(a[2],axis));pb=(_dot(b[0],axis),_dot(b[1],axis),_dot(b[2],axis))
  al,ah=min(pa),max(pa);bl,bh=min(pb),max(pb);velocity=_dot(direction,axis);eps=1.e-8*math.sqrt(square)
  if abs(velocity)<1.e-12*math.sqrt(square):
   if ah<bl-eps or bh<al-eps:return None
  else:
   x,y=(bl-ah-eps)/velocity,(bh-al+eps)/velocity
   near=max(near,min(x,y));far=min(far,max(x,y))
   if near>far+1.e-8:return None
 if far<0 or near>distance:return None
 if far<=CONTACT_EPS:
  # A real leading face entering a closed rigid body is blocked even when
  # surfaces initially touch. A trailing face separating from its socket is
  # permitted; no finite new motion step can tunnel through a future surface.
  if _dot(direction,a[4])>1.e-8 and _dot(direction,b[4])<-1.e-8:return 0.
  return None
 return max(0.,near)


def _box_sweep_possible(bounds,tri,direction,distance):
 center=tuple((a+b)/2 for a,b in zip(*bounds));half=tuple((b-a)/2 for a,b in zip(*bounds))
 axes=[(1.,0.,0.),(0.,1.,0.),(0.,0.,1.),tri[4]]
 axes.extend(_cross(edge,axis) for edge in tri[3] for axis in ((1.,0.,0.),(0.,1.,0.),(0.,0.,1.)))
 near,far=0.,distance
 for axis in axes:
  square=_dot(axis,axis)
  if square<1.e-20:continue
  value=_dot(center,axis);radius=sum(half[k]*abs(axis[k]) for k in range(3));al,ah=value-radius,value+radius
  projected=(_dot(tri[0],axis),_dot(tri[1],axis),_dot(tri[2],axis));bl,bh=min(projected),max(projected);velocity=_dot(direction,axis);eps=1.e-8*math.sqrt(square)
  if abs(velocity)<1.e-12*math.sqrt(square):
   if ah<bl-eps or bh<al-eps:return False
  else:
   a,b=(bl-ah-eps)/velocity,(bh-al+eps)/velocity;near=max(near,min(a,b));far=min(far,max(a,b))
   if near>far+1.e-8:return False
 return far>=0. and near<=distance

def _ray_triangle(origin,direction,tri):
 a,b,c=tri[:3];e1=_sub(b,a);e2=_sub(c,a);h=_cross(direction,e2);det=_dot(e1,h)
 if abs(det)<1.e-12:return None
 inv=1./det;s=_sub(origin,a);u=_dot(s,h)*inv
 if u<-1.e-8 or u>1.+1.e-8:return None
 q=_cross(s,e1);v=_dot(direction,q)*inv
 if v<-1.e-8 or u+v>1.+1.e-8:return None
 value=_dot(e2,q)*inv
 return value if value>CONTACT_EPS else None

def _inside(point,tree):
 if not all(tree[0][0][k]+CONTACT_EPS<point[k]<tree[0][1][k]-CONTACT_EPS for k in range(3)):return False
 direction=_unit((1.,.371,.517));length=sum(tree[0][1][k]-tree[0][0][k] for k in range(3))+1.
 bounds=_swept((point,point),direction,length);hits=[]
 for tri in _query(tree,bounds):
  value=_ray_triangle(point,direction,tri)
  if value is not None:hits.append(value)
 if not hits:return False
 hits.sort();unique=[hits[0]]
 for value in hits[1:]:
  if value-unique[-1]>CONTACT_EPS:unique.append(value)
 return len(unique)%2==1

def _unavailable(reason,target='',**extra):
 return dict(available=False,target=target,part_ids=(),direction=(0.,0.,0.),distance_mm=0.,disengagement_mm=0.,safe_distance_mm=0.,
  scope='visible_reference_clearance',full_case_extraction=False,mechanical_installation_complete=False,manual_release_required=True,
  allowed_opened_mesh_names=(),hide_mesh_names=(),hidden_connection_mesh_names=(),blocked_by=(),required_first=(),reason=reason,**extra)

def _plan_part_motion(scene,target,*,offsets=None,hidden_parts=(),opened_mesh_names=(),released_mounts=(),inspection_cutaway=False,show_psu=False,_data=None):
 """Reference disengagement; cache until explicit scene/pose changes.

 Hidden parts are a reference inspection aid, not a claim of physical removal.
 ``offsets`` must be exactly the currently drawn translations. Overlapping
 selectors are rejected. Target translations are reported but the full original
 insertion/removal path is validated so returning to its socket remains safe.
 """
 if scene is None:return _unavailable('scene_unavailable')
 if type(inspection_cutaway) is not bool or type(show_psu) is not bool:return _unavailable('visibility_state_unverified',target)
 meshes=tuple(getattr(scene,'meshes',()) or ())
 if not meshes or len(meshes)>MAX_MESHES:return _unavailable('scene_geometry_unverified')
 if not isinstance(target,str) or len(target)>160:return _unavailable('target_unverified')
 families={kind:tuple(dict.fromkeys(getattr(m,'part_id','') for m in meshes if getattr(m,'component','')==kind and getattr(m,'part_id',''))) for kind in ('cpu','memory','fans')}
 if target in families:
  if len(families[target])!=1:return _unavailable('choose_individual_part',target)
  target=families[target][0]
 selected=[m for m in meshes if getattr(m,'part_id','')==target and not getattr(m,'name','').startswith('style-')]
 if not selected:return _unavailable('target_unavailable',target)
 kinds={getattr(m,'component','') for m in selected}
 if len(kinds)!=1:return _unavailable('part_motion_not_implemented',target)
 mount=None;kind=next(iter(kinds))
 if kind not in ('cpu','memory'):
  from assembly_mount_frames052 import mount_descriptor
  mount=mount_descriptor(scene,target)
  if not mount.get('available'):return _unavailable(mount['reason'],target)
  if kind!='fans':return _unavailable('case_fan_geometry_unverified',target)
  # Current case-fan producer draws open fixing holes/pads, not independent
  # mounting screws. Never guess that a future same-part fastener can travel
  # with the fan, or hide it merely because its name sounds mechanical.
  if any(any(word in getattr(m,'name','').lower() for word in ('screw','bolt','fastener')) for m in selected):
   return _unavailable('case_fan_fasteners_unverified',target)
 kind=next(iter(kinds));selected_ids={id(m) for m in selected};hidden=_keys(meshes,hidden_parts)
 if hidden is None:return _unavailable('hidden_selection_unverified',target)
 if any(_selected(m,key) for m in selected for key in hidden):return _unavailable('target_hidden',target)
 whitelist=CPU_RETENTION if kind=='cpu' else MEMORY_RETENTION if kind=='memory' else ()
 allowed=tuple(name for name in whitelist if any(getattr(m,'name','')==name for m in meshes))
 if not isinstance(opened_mesh_names,(tuple,list,set,frozenset)) or len(opened_mesh_names)>16 or any(name not in allowed for name in opened_mesh_names):
  return _unavailable('retention_selection_unverified',target,allowed_release_candidates=allowed)
 if not isinstance(released_mounts,(tuple,list,set,frozenset)) or len(released_mounts)>MAX_SELECTORS:
  return _unavailable('mount_release_selection_unverified',target)
 if any(not isinstance(key,str) or key!=target or mount is None for key in released_mounts):
  return _unavailable('mount_release_selection_unverified',target)
 released=target in released_mounts
 if mount is not None and not released:
  return _unavailable('case_fan_release_required',target,allowed_mount_release_part_ids=(target,),
    mount_released=False,mount_frame=deepcopy(mount['mount_frame']),release_requirements=mount['release_requirements'],
    fixed_fastener_mesh_names=(),fasteners_drawn=False)
 opened=tuple(dict.fromkeys(opened_mesh_names));meta=_map(getattr(scene,'metadata',None));anchors=_map(meta.get('attachment_anchors'))
 board=_map(anchors.get('board'));cpu=_map(anchors.get('cpu'));direction=_unit(mount['direction'] if mount else cpu.get('normal') if kind=='cpu' else board.get('normal'))
 if direction is None or mount is None and _unit(board.get('normal')) is None:return _unavailable('board_normal_unverified',target)
 if kind=='cpu' and _dot(direction,_unit(board['normal']))<.99999:return _unavailable('cpu_anchor_normal_mismatch',target)
 dimensions=_point(getattr(scene,'dimensions',None))
 if dimensions is None or any(x<=0 or x>10000. for x in dimensions):return _unavailable('case_dimensions_unverified',target)
 applied={}
 if offsets is not None:
  if not isinstance(offsets,dict) or len(offsets)>MAX_SELECTORS:return _unavailable('offsets_unverified',target)
  keys=_keys(meshes,tuple(offsets))
  if keys is None:return _unavailable('offsets_unverified',target)
  for key in keys:
   point=_point(offsets[key])
   if point is None or any(abs(v)>2000. for v in point):return _unavailable('offsets_unverified',target)
   applied[key]=point
  if any(sum(_selected(m,key) for key in applied)>1 for m in meshes):return _unavailable('overlapping_offset_selectors',target)
 def shift(mesh):return next((value for key,value in applied.items() if _selected(mesh,key)),(0.,0.,0.))
 from assembly_visibility048 import mesh_visible
 if any(not mesh_visible(m,inspection_cutaway,show_psu) for m in selected):return _unavailable('target_hidden',target)
 hidden_names,valid_hidden=_connection_names(scene,hidden);target_names,valid_target=_connection_names(scene,(target,))
 if not valid_hidden or not valid_target:return _unavailable('connection_ownership_unverified',target)
 if mount is not None and set(target_names)!=set(mount['hide_mesh_names']):return _unavailable('connection_ownership_unverified',target)
 target_boxes=[];target_geometry=[];all_bounds={};budget=0;coarse_tests=0
 if _data is not None and not _data.valid:return _unavailable('scene_geometry_unverified',target)
 for mesh in meshes:
  if getattr(mesh,'name','').startswith('style-'):continue
  move=(0.,0.,0.) if id(mesh) in selected_ids else shift(mesh)
  original=_data.bounds[id(mesh)] if _data is not None else _bounds(mesh)
  if original is None:return _unavailable('scene_geometry_unverified',target)
  bounds=_shift_bounds(original,move);all_bounds[id(mesh)]=bounds
  if id(mesh) in selected_ids:target_boxes.append(bounds);target_geometry.append((mesh,bounds))
 if sum(len(m.vertices)//18 for m in selected)>MAX_TARGET_TRIANGLES:return _unavailable('clearance_budget_exceeded',target)
 bounds=_union(target_boxes)
 if any(bounds[0][k]<-dimensions[k]/2-CONTACT_EPS or bounds[1][k]>dimensions[k]/2+CONTACT_EPS for k in range(3)):
  return _unavailable('target_outside_case_envelope',target)
 if kind=='memory':
  pcbs=[m for m in selected if getattr(m,'name','')=='ram-pcb']
  slots=anchors.get('dimm_centers')
  if len(pcbs)!=1 or not isinstance(slots,(tuple,list)) or not slots or len(slots)>16:return _unavailable('memory_slot_anchor_unverified',target)
  pcb=pcbs[0];points=[_point(v) for v in slots]
  if any(p is None for p in points):return _unavailable('memory_slot_anchor_unverified',target)
  p=_point(pcb.position);tangential=lambda q:math.sqrt(max(0.,_dot(_sub(p,q),_sub(p,q))-_dot(_sub(p,q),direction)**2))
  if min(map(tangential,points))>3.:return _unavailable('memory_slot_anchor_mismatch',target)
  projections=[_dot(pcb.vertices[i:i+3],direction) for i in range(0,len(pcb.vertices),6)]
  if max(projections)-min(projections)<8.:return _unavailable('sodimm_release_orientation_unverified',target)
 host_names=('board-socket-carrier','board-socket-spring-heads','detail-board-retention-frame','board-am4-pga-receiving-wells','board-reference-socket-rail') if kind=='cpu' else ('detail-board-populated-memory-sockets','detail-board-memory-socket-contact-wells') if kind=='memory' else ()
 host=[m for m in meshes if getattr(m,'name','') in host_names]
 if not host and mount is None:return _unavailable('socket_geometry_unverified',target)
 projections=[_project_mesh(m,b,direction) for m,b in target_geometry]
 projection_low=min(p[0] for p in projections);projection_high=max(p[1] for p in projections)
 if any(shift(m)!=(0.,0.,0.) for m in host):return _unavailable('socket_host_displaced',target)
 if mount is None:
  host_high=max(_project_mesh(m,all_bounds[id(m)],direction)[1] for m in host)
  disengagement=max(2.,host_high-projection_low+2.)
  distance=max(disengagement+4.,projection_high-projection_low+8.,12. if kind=='cpu' else 16.)
 else:
  # One complete actual axial envelope plus8mm is an illustrative inward
  # disengagement, not a guessed screw length, latch depth or case extraction.
  disengagement=projection_high-projection_low
  distance=max(16.,disengagement+8.)
 if distance>2000.:return _unavailable('reference_motion_too_large',target)
 case_available=float('inf')
 for k,axis in enumerate(direction):
  if axis>1.e-9:case_available=min(case_available,(dimensions[k]/2-CASE_MARGIN_MM-bounds[1][k])/axis)
  elif axis<-1.e-9:case_available=min(case_available,(-dimensions[k]/2+CASE_MARGIN_MM-bounds[0][k])/axis)
 base=dict(target=target,part_ids=(target,),direction=direction,distance_mm=distance,disengagement_mm=disengagement,
  safe_distance_mm=max(0.,case_available),scope='visible_reference_clearance',full_case_extraction=False,mechanical_installation_complete=False,
  manual_release_required=True,retention_mechanism_simulated=False,allowed_opened_mesh_names=allowed,opened_mesh_names=opened,
  hide_mesh_names=target_names,hidden_connection_mesh_names=hidden_names,hidden_parts=hidden,
  existing_target_offset=next((value for key,value in applied.items() if any(_selected(m,key) for m in selected)),(0.,0.,0.)),
  blocked_by=(),required_first=(),clearance=dict(method='continuous_triangle_translation_with_rotor_sweep_bounds',scope='currently_visible_reference_parts',triangle_tests=0,scene_or_selection_change_only=True))
 if mount is not None:
  base.update(kind='case_fan',allowed_mount_release_part_ids=(target,),mount_released=True,
    mount=mount['mount'],mount_frame=deepcopy(mount['mount_frame']),release_requirements=mount['release_requirements'],
    connection_prefixes=mount['connection_prefixes'],disengagement_depth_verified=False,
    fixed_fastener_mesh_names=(),fasteners_drawn=False,boundary_contact_reference=False)
 sweep=_swept(bounds,direction,distance);contacts=[];candidate_count=0;scanned_triangles=0
 def geometry(mesh,move,box,region=None):
  if _data is not None:return _data.geometry(mesh,move,box,region)
  triangles=_triangles(mesh,move,box,region)
  return triangles,_tree(triangles) if triangles else None
 for mesh in sorted(meshes,key=lambda m:0 if kind=='cpu' and getattr(m,'component','')=='cooler' else 1):
  name=getattr(mesh,'name','')
  if id(mesh) in selected_ids or name.startswith('style-') or name in target_names or name in hidden_names or name in opened or any(_selected(mesh,key) for key in hidden) or not mesh_visible(mesh,inspection_cutaway,show_psu):continue
  obstacle_bounds=all_bounds.get(id(mesh))
  if obstacle_bounds is None or not _overlap(sweep,obstacle_bounds):continue
  if mount is not None and _boundary_separated(sweep,obstacle_bounds):
   if any(sweep[1][k]==obstacle_bounds[0][k] or obstacle_bounds[1][k]==sweep[0][k] for k in range(3)):
    base['boundary_contact_reference']=True
    base['clearance']['boundary_aabb_candidates']=base['clearance'].get('boundary_aabb_candidates',0)+1
   continue
  # Clip a disjoint batched-board mesh to this reference sweep before building
  # its tree. Keep the whole closed mesh if containment needs parity testing.
  contained=any(_contains(obstacle_bounds,box) for box in target_boxes)
  tris,tree=geometry(mesh,shift(mesh),obstacle_bounds,None if contained else sweep)
  scanned_triangles+=len(tris);candidate_count+=1
  if scanned_triangles>MAX_CANDIDATE_TRIANGLES:return dict(base,available=False,reason='clearance_budget_exceeded',distance_mm=0.)
  if not tris:continue
  hit=None
  for moving,box in target_geometry:
   local_sweep=_swept(box,direction,distance)
   if not _overlap(local_sweep,obstacle_bounds):continue
   first=tuple(moving.vertices[k]+moving.position[k] for k in range(3))
   if _contains(obstacle_bounds,box) and _inside(first,tree):hit=0.;break
   if _contains(box,obstacle_bounds):
    moving_triangles,moving_tree=geometry(moving,(0.,0.,0.),box)
    probe=tris[0][0]
    if moving_tree and _inside(probe,moving_tree):hit=0.;break
   possible=False
   for obstacle in _query(tree,local_sweep):
    coarse_tests+=1
    if coarse_tests>MAX_SWEEP_TESTS:return dict(base,available=False,reason='clearance_budget_exceeded',distance_mm=0.)
    if _box_sweep_possible(box,obstacle,direction,distance):possible=True;break
   if not possible:continue
   moving_triangles,_unused=geometry(moving,(0.,0.,0.),box)
   for tri in moving_triangles:
    for obstacle in _query(tree,_swept(tri[5],direction,distance if hit is None else hit)):
     budget+=1
     if budget>MAX_SWEEP_TESTS:return dict(base,available=False,reason='clearance_budget_exceeded',distance_mm=0.)
     at=_sweep_triangle(tri,obstacle,direction,distance if hit is None else hit)
     if at is not None:hit=at if hit is None else min(hit,at)
    if hit is not None and hit<=CONTACT_EPS:break
   if hit is not None and hit<=CONTACT_EPS:break
  if hit is not None:
   contacts.append(dict(part_id=getattr(mesh,'part_id',''),component=getattr(mesh,'component',''),mesh_name=name,first_contact_mm=hit))
   if hit<=CONTACT_EPS:
    # One proven zero-travel collision is sufficient to refuse animation.
    # Re-plan after an explicit dependency mask change rather than spending
    # work certifying an already blocked path or pretending it was clear.
    row=contacts[-1]
    base['clearance'].update(triangle_tests=budget,coarse_box_tests=coarse_tests,candidate_meshes=candidate_count,
        candidate_triangles=scanned_triangles,continuous_full_path_checked=False,proven_zero_travel_blocker=True)
    return dict(base,available=False,reason='cooler_must_be_hidden_or_moved_first' if kind=='cpu' and row['component']=='cooler' else 'motion_path_blocked',
        distance_mm=0.,safe_distance_mm=0.,blocked_by=(row,),required_first=(row['part_id'] or row['component'],))
 contacts.sort(key=lambda row:(row['first_contact_mm'],row['part_id'],row['mesh_name']))
 base['clearance'].update(triangle_tests=budget,coarse_box_tests=coarse_tests,candidate_meshes=candidate_count,candidate_triangles=scanned_triangles,continuous_full_path_checked=True)
 if contacts:
  first=contacts[0]['first_contact_mm'];base['safe_distance_mm']=max(0.,min(case_available,first-CONTACT_EPS))
  base['blocked_by']=tuple(contacts[:16]);base['required_first']=tuple(dict.fromkeys(row['part_id'] or row['component'] for row in contacts[:16]))
  reason='cooler_must_be_hidden_or_moved_first' if any(row['component']=='cooler' for row in contacts) and kind=='cpu' else 'motion_path_blocked'
  return dict(base,available=False,reason=reason,distance_mm=0.)
 if case_available+CONTACT_EPS<distance:return dict(base,available=False,reason='insufficient_case_clearance',distance_mm=0.)
 base['safe_distance_mm']=distance
 return dict(base,available=True,reason='case_fan_mount_disengagement_reference' if mount is not None else 'socket_disengagement_reference')


class PartMotionPlanner:
 """Scene-owned explicit-change cache. Clear on close or physical scene change.

 At most four detached plans and4096 candidate triangles are retained. No
 cached result owns geometry beyond this owner's source meshes; clear drops
 all source, metadata, bounds and temporary-tree references together.
 """
 MAX_PLAN_CACHE=4;MAX_CACHED_TRIANGLES=4096
 def __init__(self,scene):
  self.scene=scene;self.bounds={};self.valid=True;self._geometry=OrderedDict();self._triangle_count=0;self._plans=OrderedDict()
  meshes=tuple(getattr(scene,'meshes',()) or ())
  if not meshes or len(meshes)>MAX_MESHES or sum(len(getattr(m,'vertices',()))//18 for m in meshes)>320000:self.valid=False;return
  for mesh in meshes:
   if getattr(mesh,'name','').startswith('style-'):continue
   value=_bounds(mesh)
   if value is None:self.valid=False;break
   self.bounds[id(mesh)]=value
 def geometry(self,mesh,move,bounds,region=None):
  key=(id(mesh),move,region)
  if key in self._geometry:
   value=self._geometry.pop(key);self._geometry[key]=value;return value
  triangles=_triangles(mesh,move,bounds,region);value=(triangles,_tree(triangles) if triangles else None)
  size=len(triangles)
  if size<=self.MAX_CACHED_TRIANGLES:
   while self._geometry and self._triangle_count+size>self.MAX_CACHED_TRIANGLES:
    _key,old=self._geometry.popitem(last=False);self._triangle_count-=len(old[0])
   if len(self._geometry)>=64:
    _key,old=self._geometry.popitem(last=False);self._triangle_count-=len(old[0])
   self._geometry[key]=value;self._triangle_count+=size
  return value
 def plan(self,target,**options):
  try:
   # This bounded key is made only from explicit UI state, never vertex data.
   key=(target,tuple((name,tuple(sorted(value.items())) if isinstance(value,dict) else tuple(value) if isinstance(value,(list,set,frozenset)) else value) for name,value in sorted(options.items())))
   hash(key)
  except (TypeError,ValueError):key=None
  if key is not None and key in self._plans:
   value=self._plans.pop(key);self._plans[key]=value;return deepcopy(value)
  value=_plan_part_motion(self.scene,target,_data=self,**options)
  if key is not None:
   if len(self._plans)>=self.MAX_PLAN_CACHE:self._plans.popitem(last=False)
   self._plans[key]=deepcopy(value)
  return value
 def clear(self):
  self.scene=None;self.bounds.clear();self._geometry.clear();self._plans.clear();self._triangle_count=0;self.valid=False
 def discard_geometry_cache(self):
  """Release temporary triangle/BVH objects on explicit hidden/off changes.

  The small bounds index and detached plans remain reusable. Nothing runs on
  a timer; a different future query may rebuild only its bounded candidates.
  """
  changed=bool(self._geometry);self._geometry.clear();self._triangle_count=0
  return changed
 def rebind_scene(self,scene):
  """Reuse a physical index only for exact shared-array style wrappers."""
  if self.scene is None or scene is None or getattr(scene,'dimensions',None)!=getattr(self.scene,'dimensions',None):return False
  old=[m for m in getattr(self.scene,'meshes',()) if not getattr(m,'name','').startswith('style-')]
  new=[m for m in getattr(scene,'meshes',()) if not getattr(m,'name','').startswith('style-')]
  if len(old)!=len(new):return False
  fields=('name','component','part_id','position','axis','rotor','direction')
  if any(a.vertices is not b.vertices or any(getattr(a,key,None)!=getattr(b,key,None) for key in fields) for a,b in zip(old,new)):return False
  ids={id(a):id(b) for a,b in zip(old,new)}
  if any(key not in ids for key in self.bounds):return False
  bounds={ids[key]:value for key,value in self.bounds.items()}
  geometry=OrderedDict(((ids[key[0]],key[1],key[2]),value) for key,value in self._geometry.items())
  self.scene=scene;self.bounds=bounds;self._geometry=geometry;self._plans.clear()
  return True
 def cache_info(self):return dict(bounds=len(self.bounds),plans=len(self._plans),triangles=self._triangle_count,geometry_entries=len(self._geometry),plan_limit=self.MAX_PLAN_CACHE,triangle_limit=self.MAX_CACHED_TRIANGLES)

def plan_part_motion(scene,target,*,offsets=None,hidden_parts=(),opened_mesh_names=(),released_mounts=(),inspection_cutaway=False,show_psu=False):
 """One-shot convenience. Use PartMotionPlanner for cached UI operations."""
 planner=PartMotionPlanner(scene)
 try:return planner.plan(target,offsets=offsets,hidden_parts=hidden_parts,opened_mesh_names=opened_mesh_names,released_mounts=released_mounts,inspection_cutaway=inspection_cutaway,show_psu=show_psu)
 finally:planner.clear()

class PartMotion:
 """Finite smoothstep state driven only by the caller's existing clock."""
 DURATION_MS=960.;MAX_TICK_MS=136.
 def __init__(self):self._progress=0.;self._active=False;self._target=0.;self._from=0.;self._elapsed=0.;self._duration=self.DURATION_MS
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
  self._target=target;self._from=self._progress;self._elapsed=0.;self._duration=self.DURATION_MS*abs(target-self._progress);self._active=self._duration>1.e-9
  if not self._active:self._progress=target
  return True
 def advance(self,elapsed_ms):
  if not self._active or type(elapsed_ms) not in (int,float) or not math.isfinite(elapsed_ms) or elapsed_ms<=0:return False
  self._elapsed=min(self._duration,self._elapsed+min(elapsed_ms,self.MAX_TICK_MS));phase=self._elapsed/self._duration;smooth=phase*phase*(3.-2.*phase)
  self._progress=self._from+(self._target-self._from)*smooth
  if self._elapsed>=self._duration:self._progress=self._target;self._active=False
  return True
 def reset(self):
  changed=self._progress!=0. or self._active or self._target!=0.;self.__init__();return changed
 def offset(self,plan):
  if not isinstance(plan,dict) or plan.get('available') is not True:return (0.,0.,0.)
  direction=_unit(plan.get('direction'));distance=plan.get('distance_mm')
  if direction is None or type(distance) not in (int,float) or not math.isfinite(distance) or not 0.<distance<=2000.:return (0.,0.,0.)
  original=_point(plan.get('direction'))
  if abs(_dot(original,original)-1.)>1.e-6:return (0.,0.,0.)
  return _mul(direction,distance*self._progress)
