"""CPU/DIMM visible-reference plans: continuous geometry, bounded owned state."""
import copy
from dataclasses import replace
import gc
import math
import unittest
import weakref
from unittest.mock import patch
from assembly_geometry import Mesh,Scene,box,color,ring
from assembly_style import apply_model_styles
import assembly_part_motion052 as motion

SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')

def solid(name,size,position,component,part):
 return Mesh(name,box(*size),color('#778899'),position,component,part_id=part)
def cpu_scene():
 meshes=(solid('cpu-lid',(10.,20.,20.),(40.,0.,0.),'cpu','cpu:0'),
  solid('board-socket-carrier',(2.,28.,28.),(48.,0.,0.),'board','board:0'))
 return Scene(meshes,(500.,400.,300.),dict(attachment_anchors=dict(cpu=dict(position=(40.,0.,0.),normal=(-1.,0.,0.)),board=dict(normal=(-1.,0.,0.))),auxiliary=dict(cables=[],cable_count=0)))
def ram_scene():
 rows=[];slots=[]
 for index,z in enumerate((10.,30.)):
  rows.append(solid('ram-pcb',(31.,133.35,1.2),(40.,20.,z),'memory','memory:'+str(index)))
  for side in (-1,1):rows.append(solid('detail-board-populated-memory-sockets',(4.,139.,1.1),(56.,20.,z+side*1.7),'board','board:0'))
  rows.append(solid('board-dimm-end-latches',(7.,6.,5.5),(55.,92.,z),'board','board:0'));slots.append((56.,20.,z))
 return Scene(tuple(rows),(500.,400.,300.),dict(attachment_anchors=dict(board=dict(normal=(-1.,0.,0.)),dimm_centers=slots),auxiliary=dict(cables=[],cable_count=0)))
def with_mesh(scene,mesh):return replace(scene,meshes=scene.meshes+(mesh,))
def posed(scene,turn):
 def vector(p):
  if turn==4:return (math.cos(.31)*p[0]-math.sin(.31)*p[1],math.sin(.31)*p[0]+math.cos(.31)*p[1],p[2])
  return (p[1],-p[0],p[2]) if turn==1 else (-p[1],p[0],p[2]) if turn==2 else (p[2],p[1],-p[0])
 meshes=[]
 for m in scene.meshes:
  values=[]
  for at in range(0,len(m.vertices),6):values.extend((*vector(m.vertices[at:at+3]),*vector(m.vertices[at+3:at+6])))
  meshes.append(replace(m,vertices=tuple(values),position=vector(m.position),axis=vector(m.axis)))
 meta=copy.deepcopy(scene.metadata);a=meta['attachment_anchors'];a['board']['normal']=vector(a['board']['normal'])
 if 'cpu' in a:
  a['cpu']['normal']=vector(a['cpu']['normal']);a['cpu']['position']=vector(a['cpu']['position'])
 if 'dimm_centers' in a:a['dimm_centers']=[vector(p) for p in a['dimm_centers']]
 dims=(scene.dimensions[1],scene.dimensions[0],scene.dimensions[2]) if turn in (1,2) else scene.dimensions if turn==4 else (scene.dimensions[2],scene.dimensions[1],scene.dimensions[0])
 return Scene(tuple(meshes),dims,meta)

class PartMotion052Tests(unittest.TestCase):
 def setUp(self):
  for name in ('builtins.open','ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start'):
   self.enterContext(patch(name,create=True,side_effect=AssertionError('Pure math: no I/O, device, process or clock worker')))
 def test_cpu_and_each_dimm_have_independent_detached_plans(self):
  for scene,targets in ((cpu_scene(),('cpu:0',)),(ram_scene(),('memory:0','memory:1'))):
   before=copy.deepcopy(scene)
   for target in targets:
    p=motion.plan_part_motion(scene,target)
    self.assertTrue(p['available'],p);self.assertEqual(p['part_ids'],(target,));self.assertEqual(p['direction'],(-1.,0.,0.))
    self.assertGreater(p['distance_mm'],p['disengagement_mm']);self.assertFalse(p['full_case_extraction']);self.assertFalse(p['mechanical_installation_complete'])
    self.assertTrue(p['manual_release_required']);self.assertTrue(p['clearance']['continuous_full_path_checked'])
    p['direction']=(0.,1.,0.)
   self.assertEqual(scene,before)
  self.assertEqual(motion.plan_part_motion(ram_scene(),'memory')['reason'],'choose_individual_part')
 def test_midpath_thin_gpu_and_hose_blocks_even_when_endpoint_is_clear(self):
  base=ram_scene();gpu=solid('gpu-thin-obstacle',(.1,180.,50.),(20.,20.,20.),'gpu','gpu:0');scene=with_mesh(base,gpu)
  p=motion.plan_part_motion(scene,'memory:0');self.assertFalse(p['available']);self.assertLess(p['safe_distance_mm'],5.)
  self.assertEqual(p['blocked_by'][0]['part_id'],'gpu:0')
  clear=motion.plan_part_motion(scene,'memory:0',hidden_parts=('gpu',));self.assertTrue(clear['available'])
  self.assertTrue(motion.plan_part_motion(scene,'memory:0',offsets={'gpu:0':(-100.,0.,0.)})['available'])
  from assembly_cooling import _tube
  tube=Mesh('cooler-liquid-tubes',_tube(((20.,-60.,10.),(20.,110.,10.)),2.,8),color('#222222'),component='cooler',part_id='cooler:pump')
  p=motion.plan_part_motion(with_mesh(base,tube),'memory:0');self.assertFalse(p['available']);self.assertIn('cooler:pump',p['required_first'])
 def test_initial_contact_with_cooler_is_blocked_and_hidden_scope_is_explicit(self):
  scene=with_mesh(cpu_scene(),solid('cooler-copper-contact',(2.,30.,30.),(34.,0.,0.),'cooler','cooler:pump'))
  p=motion.plan_part_motion(scene,'cpu:0');self.assertFalse(p['available']);self.assertEqual(p['reason'],'cooler_must_be_hidden_or_moved_first')
  self.assertTrue(p['clearance']['proven_zero_travel_blocker']);self.assertFalse(p['clearance']['continuous_full_path_checked'])
  p=motion.plan_part_motion(scene,'cpu:0',hidden_parts=('cooler',));self.assertTrue(p['available']);self.assertEqual(p['scope'],'visible_reference_clearance')
 def test_closed_body_containment_and_future_case_wall_cannot_be_ignored(self):
  scene=with_mesh(cpu_scene(),solid('solid-foreign-enclosure',(40.,80.,80.),(40.,0.,0.),'gpu','gpu:0'))
  self.assertFalse(motion.plan_part_motion(scene,'cpu:0')['available'])
  scene=replace(cpu_scene(),dimensions=(100.,400.,300.))
  # An intact plate along the path remains an obstacle unless the same
  # explicit cutaway gate actually hides it in all render/pick passes.
  scene=with_mesh(scene,solid('side-glass',(.2,80.,80.),(25.,0.,0.),'panel',''))
  self.assertFalse(motion.plan_part_motion(scene,'cpu:0')['available'])
  self.assertTrue(motion.plan_part_motion(scene,'cpu:0',inspection_cutaway=True)['available'])
 def test_real_aperture_is_not_filled_by_its_aabb(self):
  aperture=Mesh('open-fixture',ring(24.,16.,2.,24),color('#333333'),(20.,0.,0.),'gpu',part_id='gpu:0')
  # ring localZ becomes worldX; CPU20x20 section fits its real inner opening.
  values=[]
  for at in range(0,len(aperture.vertices),6):
   x,y,z=aperture.vertices[at:at+3];a,b,c=aperture.vertices[at+3:at+6];values.extend((z,y,-x,c,b,-a))
  aperture=replace(aperture,vertices=tuple(values))
  p=motion.plan_part_motion(with_mesh(cpu_scene(),aperture),'cpu:0');self.assertTrue(p['available'],p)
 def test_persisted_pose_normals_work_for_rigid_case_layout_rotations(self):
  for turn,normal in ((1,(0.,1.,0.)),(2,(0.,-1.,0.)),(3,(0.,0.,1.)),(4,(-math.cos(.31),-math.sin(.31),0.))):
   for scene,target in ((cpu_scene(),'cpu:0'),(ram_scene(),'memory:1')):
    original=motion.plan_part_motion(scene,target);p=motion.plan_part_motion(posed(scene,turn),target)
    self.assertTrue(p['available'],p);self.assertEqual(p['direction'],normal);self.assertAlmostEqual(p['distance_mm'],original['distance_mm'])
 def test_unsupported_sodimm_unknown_normals_and_offsets_fail_closed(self):
  scene=ram_scene();first=scene.meshes[0];scene=replace(scene,meshes=(replace(first,vertices=box(3.,69.6,30.)),*scene.meshes[1:]))
  self.assertEqual(motion.plan_part_motion(scene,'memory:0')['reason'],'sodimm_release_orientation_unverified')
  for value in ((0.,0.,0.),(float('nan'),0.,0.),None):
   scene=cpu_scene();scene.metadata['attachment_anchors']['board']['normal']=value
   self.assertFalse(motion.plan_part_motion(scene,'cpu:0')['available'])
  self.assertFalse(motion.plan_part_motion(cpu_scene(),'cpu:0',offsets={'unknown':(0.,0.,0.)})['available'])
  self.assertFalse(motion.plan_part_motion(cpu_scene(),'cpu:0',offsets={'cpu':(0.,0.,0.),'cpu:0':(0.,0.,0.)})['available'])
  self.assertFalse(motion.plan_part_motion(cpu_scene(),'cpu:0',offsets={'cpu:0':(2001.,0.,0.)})['available'])
  self.assertFalse(motion.plan_part_motion(cpu_scene(),'cpu:0',hidden_parts=('unknown',))['available'])
  self.assertEqual(motion.plan_part_motion(cpu_scene(),'cpu:0',hidden_parts=('cpu',))['reason'],'target_hidden')
 def test_only_listed_existing_retention_meshes_can_be_opened(self):
  frame=solid('detail-board-retention-frame',(2.,30.,30.),(32.,0.,0.),'board','board:0');scene=with_mesh(cpu_scene(),frame)
  p=motion.plan_part_motion(scene,'cpu:0');self.assertFalse(p['available']);self.assertIn(frame.name,p['allowed_opened_mesh_names'])
  p=motion.plan_part_motion(scene,'cpu:0',opened_mesh_names=(frame.name,));self.assertTrue(p['available']);self.assertFalse(p['retention_mechanism_simulated'])
  p=motion.plan_part_motion(scene,'cpu:0',opened_mesh_names=('board-socket-carrier',));self.assertFalse(p['available'])
 def test_hidden_connections_exact_owner_and_prefix_no_neighbour_guessing(self):
  scene=with_mesh(cpu_scene(),solid('cooler-body',(10.,10.,10.),(-30.,50.,0.),'cooler','cooler:pump'))
  a=solid('cable-1-fan4-rounded-loom',(1.,1.,1.),(0.,0.,80.),'cables','cables:all');b=replace(a,name='cable-10-eps8-rounded-loom')
  scene=replace(scene,meshes=scene.meshes+(a,b));scene.metadata['auxiliary']=dict(cable_count=2,cables=[dict(source_owner='cooler:pump',target_owner='board',mesh_prefix='cable-1-fan4'),dict(source_owner='psu',target_owner='board',mesh_prefix='cable-10-eps8')])
  before=copy.deepcopy(scene);self.assertEqual(motion.hidden_connections(scene,('cooler',)),(a.name,));self.assertEqual(scene,before)
  self.assertEqual(motion.hidden_connections(scene,('missing',)),())
  scene.metadata['auxiliary']['cables'][0]['mesh_prefix']='cable'
  self.assertEqual(motion.hidden_connections(scene,('cooler',)),())
  # A legacy family owner spanning several DIMMs does not identify which
  # stick owns this cable. Refuse motion rather than disconnect its neighbour.
  scene=ram_scene();scene=replace(scene,meshes=scene.meshes+(a,))
  scene.metadata['auxiliary']=dict(cables=[dict(source_owner='memory',target_owner='board',mesh_prefix='cable-1-fan4')])
  self.assertEqual(motion.plan_part_motion(scene,'memory:0')['reason'],'connection_ownership_unverified')
  self.assertEqual(motion.hidden_connections(scene,('memory:0',)),())
  self.assertEqual(motion.hidden_connections(scene,('memory',)),(a.name,))
 def test_rotor_sweep_has_no_current_phase_gaps(self):
  verts=(0.,-30.,0.,0.,0.,1.,1.,30.,0.,0.,0.,1.,-1.,30.,0.,0.,0.,1.)
  rotor=Mesh('foreign-rotor',verts,color('#333333'),(25.,0.,0.),'fans',True,axis=(1.,0.,0.),part_id='fans:0')
  self.assertFalse(motion.plan_part_motion(with_mesh(cpu_scene(),rotor),'cpu:0')['available'])
 def test_six_styles_keep_geometry_and_reference_plan_identical(self):
  scene=ram_scene();plans=[]
  for style in SIX:
   meshes,meta=apply_model_styles(scene.meshes,style,{},scene.dimensions,{'front':'open'})
   changed=Scene(meshes,scene.dimensions,dict(scene.metadata,**meta));p=motion.plan_part_motion(changed,'memory:1');plans.append(p)
   self.assertTrue(p['available']);self.assertTrue(all(a.vertices is b.vertices for a,b in zip(scene.meshes,changed.meshes)))
  self.assertTrue(all(p==plans[0] for p in plans))
 def test_index_caches_are_bounded_detached_and_clear_releases_scene(self):
  scene=cpu_scene();ref=weakref.ref(scene);planner=motion.PartMotionPlanner(scene)
  with patch.object(motion,'_bounds',side_effect=AssertionError('Bounds cannot rescan on selection')):
   p=planner.plan('cpu:0');p['direction']=(0.,1.,0.);self.assertEqual(planner.plan('cpu:0')['direction'],(-1.,0.,0.))
  for i in range(10):planner.plan('cpu:0',show_psu=bool(i%2),opened_mesh_names=())
  info=planner.cache_info();self.assertLessEqual(info['plans'],4);self.assertLessEqual(info['triangles'],4096)
  del scene;planner.clear();gc.collect();self.assertIsNone(ref());self.assertEqual(planner.cache_info()['bounds'],0)
 def test_style_rebind_reuses_physical_indices_and_releases_old_wrappers(self):
  scene=cpu_scene();ref=weakref.ref(scene);mesh_ref=weakref.ref(scene.meshes[0]);planner=motion.PartMotionPlanner(scene);p=planner.plan('cpu:0')
  changed=replace(scene,meshes=tuple(replace(m,color=(.2,.3,.4,1.)) for m in scene.meshes),metadata=copy.deepcopy(scene.metadata))
  with patch.object(motion,'_bounds',side_effect=AssertionError('No geometry rescan on exact style wrappers')):
   self.assertTrue(planner.rebind_scene(changed));self.assertEqual(planner.plan('cpu:0'),p)
  bad=replace(changed,meshes=(replace(changed.meshes[0],vertices=tuple(list(changed.meshes[0].vertices))),*changed.meshes[1:]))
  self.assertFalse(planner.rebind_scene(bad));self.assertIs(planner.scene,changed)
  del scene;gc.collect();self.assertIsNone(ref());self.assertIsNone(mesh_ref());planner.clear()
 def test_explicit_hide_discards_only_temporary_geometry_and_keeps_small_detached_plans(self):
  # A genuine mid-path blocker creates both target and obstacle BVH data.
  # Its detached refusal must survive cache eviction just like a clear plan.
  scene=with_mesh(cpu_scene(),solid('thin-wall',(.1,50.,50.),(25.,0.,0.),'gpu','gpu:0'));ref=weakref.ref(scene)
  planner=motion.PartMotionPlanner(scene);plan=planner.plan('cpu:0');before=planner.cache_info()
  self.assertFalse(plan['available']);self.assertEqual(plan['reason'],'motion_path_blocked')
  self.assertGreater(before['triangles'],0);self.assertGreater(before['geometry_entries'],0)
  self.assertTrue(planner.discard_geometry_cache());after=planner.cache_info()
  self.assertEqual(after['triangles'],0);self.assertEqual(after['geometry_entries'],0)
  self.assertEqual(after['plans'],before['plans']);self.assertEqual(after['bounds'],before['bounds'])
  with patch.object(motion,'_triangles',side_effect=AssertionError('Cached plan survives hidden transition')):
   self.assertEqual(planner.plan('cpu:0'),plan)
  with patch.object(motion,'_bounds',side_effect=AssertionError('Small bounds survive hidden transition')):
   self.assertEqual(planner.plan('cpu:0',show_psu=True),plan)
  self.assertGreater(planner.cache_info()['triangles'],0);planner.discard_geometry_cache()
  self.assertFalse(planner.discard_geometry_cache());del scene;planner.clear();gc.collect();self.assertIsNone(ref())
 def test_budget_limit_refuses_unproved_clearance(self):
  scene=with_mesh(cpu_scene(),solid('thin-wall',(.1,50.,50.),(25.,0.,0.),'gpu','gpu:0'))
  with patch.object(motion,'MAX_SWEEP_TESTS',0):self.assertEqual(motion.plan_part_motion(scene,'cpu:0')['reason'],'clearance_budget_exceeded')
 def test_finite_state_uses_existing_ticks_no52mm_cap_and_reverses_without_jump(self):
  state=motion.PartMotion();plan=dict(available=True,direction=(-1.,0.,0.),distance_mm=80.)
  self.assertTrue(state.start(True));state.advance(200.);point=state.progress;self.assertGreater(point,0.)
  self.assertTrue(state.start(False));self.assertEqual(state.progress,point)
  for _ in range(20):state.advance(100.)
  self.assertEqual(state.progress,0.);self.assertFalse(state.active)
  state.start(True)
  for _ in range(20):state.advance(100.)
  self.assertEqual(state.offset(plan),(-80.,0.,0.));self.assertFalse(state.active)
  self.assertEqual(state.offset(dict(plan,distance_mm=2001.)),(0.,0.,0.));self.assertEqual(state.offset(dict(plan,direction=(-2.,0.,0.))),(0.,0.,0.))
  self.assertTrue(state.reset());self.assertFalse(state.reset());self.assertFalse(state.start(1))

if __name__=='__main__':unittest.main()
