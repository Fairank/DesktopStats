"""Independent reference fan release plus continuous actual-geometry sweep."""
import copy
from dataclasses import replace
import unittest
from unittest.mock import patch
from assembly_geometry import Mesh,Scene,box,color
from assembly_part_motion052 import PartMotionPlanner,PartMotion,plan_part_motion
from assembly_style import apply_model_styles

TARGET='fans:rear:0'
SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')

def solid(name,size,position,component,part=''):
 return Mesh(name,box(*size),color('#334455'),position,component,part_id=part)

def fixture():
 meshes=(solid('case-fan-frame',(120.,120.,25.),(0.,0.,0.),'fans',TARGET),
  solid('board-reference',(2.,80.,80.),(-160.,0.,0.),'board','board:0'),
  solid('cable-1-fan4-rounded-loom',(2.,2.,60.),(-30.,0.,0.),'cables','cables:all'))
 meta=dict(attachment_anchors={},cooling=dict(
  parts=[dict(id=TARGET,kind='case_fan',model_id='arctic-p12-pwm',mount='rear',compatibility='documented_fan_mount',placement_method='centered_mount_reference')],
  fans=[dict(part_id=TARGET,role='case',model_id='arctic-p12-pwm',position=(0.,0.,0.),axis=(0.,0.,-1.),direction='exhaust')],
  wire_anchors=[dict(owner=TARGET,kind='fan4',role='case')],mount_plane_sources={}),
  auxiliary=dict(cable_count=1,cables=[dict(source_owner=TARGET,target_owner='board',kind='fan4',role='case',
   mesh_prefix='cable-1-fan4',routing_failed=False,external_route=False)]))
 return Scene(meshes,(500.,500.,500.),meta)

def released(scene= None,**options):
 return plan_part_motion(scene or fixture(),TARGET,released_mounts=(TARGET,),**options)

class CaseFanMotion052Tests(unittest.TestCase):
 def setUp(self):
  for name in ('builtins.open','ctypes.WinDLL','subprocess.Popen','threading.Thread.start','socket.socket'):
   self.enterContext(patch(name,create=True,side_effect=AssertionError('Pure math: no native I/O or clock')))
 def test_descriptor_is_not_motion_and_exact_explicit_release_hides_only_owned_wire(self):
  scene=fixture();before=copy.deepcopy(scene);p=plan_part_motion(scene,TARGET)
  self.assertFalse(p['available']);self.assertEqual(p['reason'],'case_fan_release_required')
  self.assertEqual(p['allowed_mount_release_part_ids'],(TARGET,));self.assertFalse(p['mount_released'])
  p=released(scene);self.assertTrue(p['available'],p);self.assertTrue(p['mount_released'])
  self.assertEqual(p['direction'],(0.,0.,1.));self.assertEqual(p['hide_mesh_names'],('cable-1-fan4-rounded-loom',))
  self.assertEqual(p['distance_mm'],33.);self.assertTrue(p['manual_release_required']);self.assertFalse(p['mechanical_installation_complete'])
  self.assertFalse(p['full_case_extraction']);self.assertFalse(p['disengagement_depth_verified'])
  self.assertEqual(p['fixed_fastener_mesh_names'],());self.assertFalse(p['fasteners_drawn']);self.assertEqual(scene,before)
 def test_midpath_gpu_and_unhidden_frame_remain_solid_after_release(self):
  for kind in ('gpu','case'):
   scene=fixture();obstacle=solid('actual-thin-obstacle',(150.,150.,.1),(0.,0.,20.),kind,'gpu:0' if kind=='gpu' else '')
   scene=replace(scene,meshes=scene.meshes+(obstacle,));p=released(scene)
   self.assertFalse(p['available']);self.assertEqual(p['reason'],'motion_path_blocked');self.assertLess(p['safe_distance_mm'],8.)
   self.assertEqual(p['blocked_by'][0]['mesh_name'],obstacle.name)
   self.assertTrue(released(scene,hidden_parts=(kind,))['available'])
 def test_exact_tangent_half_space_is_safe_but_any_positive_overlap_still_blocks(self):
  scene=fixture();neighbour=solid('neighbour-frame',(120.,120.,25.),(120.,0.,0.),'fans','other-fan:0')
  scene=replace(scene,meshes=scene.meshes+(neighbour,));p=released(scene)
  self.assertTrue(p['available'],p);self.assertTrue(p['boundary_contact_reference'])
  overlap=replace(neighbour,position=(119.99,0.,0.));scene=replace(scene,meshes=(*scene.meshes[:-1],overlap))
  p=released(scene);self.assertFalse(p['available']);self.assertEqual(p['blocked_by'][0]['part_id'],'other-fan:0')
  entering=solid('normal-crossing-wall',(150.,150.,.1),(0.,0.,12.55),'case')
  scene=fixture();scene=replace(scene,meshes=scene.meshes+(entering,));p=released(scene)
  self.assertFalse(p['available']);self.assertEqual(p['safe_distance_mm'],0.)
 def test_real_producer_frame_rotor_and_attached_lead_move_as_independent_rigid_reference(self):
  from assembly_cooling import _Builder,_fan
  from cooling_catalog import get_fan
  builder=_Builder('balanced');_fan(builder,get_fan('arctic-p12-pwm'),(0.,0.,0.),(0.,0.,1.),(0.,1.,0.),part=TARGET)
  scene=fixture();scene=replace(scene,meshes=(*builder.finish(),*scene.meshes[1:]))
  p=released(scene);self.assertTrue(p['available'],p);self.assertGreater(p['distance_mm'],30.)
  self.assertTrue(any(m.rotor for m in scene.meshes));self.assertTrue(p['clearance']['continuous_full_path_checked'])
  state=PartMotion();state.start(True)
  for _ in range(20):state.advance(100.)
  self.assertEqual(state.offset(p),tuple(x*p['distance_mm'] for x in p['direction']))
 def test_direction_uses_authored_mount_instead_of_intake_or_rotor_axis(self):
  scene=fixture();scene.metadata['attachment_anchors']['case_mount_planes']=dict(rear=dict(position=(0.,0.,0.),normal=(1.,1.,0.)))
  # Rigidly orient the actual frame to the authored mounting plane, rather
  # than leaving a120mm side masquerading as its axial depth.
  frame=scene.meshes[0];vertices=[];q=2**-.5
  for at in range(0,len(frame.vertices),3):
   x,y,z=frame.vertices[at:at+3];vertices.extend(((-x+z)*q,(x+z)*q,y))
  scene=replace(scene,meshes=(replace(frame,vertices=tuple(vertices)),*scene.meshes[1:]))
  scene.metadata['cooling']['fans'][0].update(axis=None,direction='intake')
  p=released(scene);self.assertTrue(p['available'],p)
  self.assertAlmostEqual(p['direction'][0],-2**-.5);self.assertAlmostEqual(p['direction'][1],-2**-.5)
  self.assertAlmostEqual(p['distance_mm'],33.)
  self.assertEqual(p['mount_frame']['source_kind'],'authored_case_mount_plane_reference')
 def test_release_scope_hidden_target_and_offsets_are_fail_closed(self):
  for value in ((True,),('fans',),('other',),TARGET,('cpu:0',)):
   self.assertFalse(plan_part_motion(fixture(),TARGET,released_mounts=value)['available'])
  self.assertEqual(released(hidden_parts=(TARGET,))['reason'],'target_hidden')
  self.assertFalse(released(offsets={'other':(0.,0.,0.)})['available'])
  self.assertEqual(released(opened_mesh_names=('case-fan-frame',))['reason'],'retention_selection_unverified')
 def test_radiator_harness_missing_wiring_or_unknown_same_part_fastener_never_moves(self):
  for change,reason in (('radiator','radiator_fan_internal_harness_unverified'),('wire','fan_connections_unverified'),('fastener','case_fan_fasteners_unverified')):
   scene=fixture()
   if change=='radiator':scene.metadata['cooling']['parts'][0]['kind']='radiator_fan'
   elif change=='wire':scene.metadata['cooling']['wire_anchors']=[]
   else:scene=replace(scene,meshes=scene.meshes+(solid('case-fan-unknown-screw',(2.,2.,4.),(45.,45.,0.),'fans',TARGET),))
   p=released(scene);self.assertFalse(p['available']);self.assertEqual(p['reason'],reason)
 def test_all_six_styles_share_motion_geometry_and_bounded_event_cache(self):
  base=fixture();plans=[];owner=PartMotionPlanner(base)
  try:
   for style in SIX:
    meshes,meta=apply_model_styles(base.meshes,style,{},base.dimensions,{'front':'open'})
    styled=Scene(meshes,base.dimensions,dict(base.metadata,**meta));self.assertTrue(owner.rebind_scene(styled))
    p=owner.plan(TARGET,released_mounts=(TARGET,));plans.append(p)
    self.assertTrue(p['available'],p);self.assertTrue(all(a.vertices is b.vertices for a,b in zip(base.meshes,styled.meshes)))
    p['mount_frame']['position_verified']=True
    self.assertFalse(owner.plan(TARGET,released_mounts=(TARGET,))['mount_frame']['position_verified'])
   # Compare detached, unmodified values rather than the intentional local mutation.
   for p in plans:p['mount_frame']['position_verified']=False
   self.assertTrue(all(p==plans[0] for p in plans))
   self.assertLessEqual(owner.cache_info()['plans'],4);self.assertLessEqual(owner.cache_info()['triangles'],4096)
  finally:owner.clear()

if __name__=='__main__':unittest.main()
