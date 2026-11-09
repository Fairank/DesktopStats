"""Real DIMM channels and source-correct ASUS step; software/reference only."""
import copy
from contextlib import ExitStack
from dataclasses import replace
import os
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen');os.environ.setdefault('QT_QUICK_BACKEND','software')
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtGui import QGuiApplication,QOpenGLContext
from PySide6.QtQml import QQmlEngine
from assembly_auxiliary import _segment_triangle
from assembly_geometry import Scene,build_scene
from assembly_motherboard import layout_anchors,enrich_motherboard
from assembly_detail import _boxes
from assembly_part_motion052 import PartMotionPlanner
from motherboard_catalog import MODELS,get_model

ASUS='asus-rog-strix-z790-a-wifi-d4'
OLD_M2=((.164,.506),(.688,.506),(.706,.486),(.974,.486),(.974,.549),(.922,.577),(.164,.577))
NEW_M2=((.164,.506),(.902,.506),(.920,.486),(.974,.486),(.974,.549),(.922,.577),(.164,.577))

def hit(mesh,a,b):
 return any(_segment_triangle(a,b,tuple(tuple(mesh.vertices[at+j+k]+mesh.position[k] for k in range(3)) for j in (0,6,12))) for at in range(0,len(mesh.vertices),18))
def boards(identity):
 spec=dict(board=dict(model_id=identity),memory=dict(count=0));a=layout_anchors(spec,400.,700.,600.,90.,0.,-150.)
 m,meta=enrich_motherboard((),spec,a,'balanced');return m,meta,a
def within(point,poly):
 x,y=point
 for a,b in zip(poly,(*poly[1:],poly[0])):
  if abs((x-a[0])*(b[1]-a[1])-(y-a[1])*(b[0]-a[0]))<1.e-7 and min(a[0],b[0])-1.e-7<=x<=max(a[0],b[0])+1.e-7 and min(a[1],b[1])-1.e-7<=y<=max(a[1],b[1])+1.e-7:return True
 inside=False
 for a,b in zip(poly,(*poly[1:],poly[0])):
  if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:inside=not inside
 return inside

class SocketGeometry052Tests(unittest.TestCase):
 def setUp(self):
  for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
   self.enterContext(patch(target,create=True,side_effect=AssertionError('No hardware/process/thread')))
 def test_every_known_board_has_real_open_dimm_channel_and_retains_housing_key_latches(self):
  for model in MODELS:
   meshes,meta,a=boards(model['id']);contact=next(m for m in meshes if m.name=='detail-board-memory-socket-contact-wells')
   self.assertEqual(contact.vertex_count//3,len(model['dimm_uv'])*24)
   expected_latches=[];expected_housing=[];bx=a['board']['x'];key_y=(.5418072740907387-.5)*133.35 if model['memory_type']=='DDR4' else (.5106861642294713-.5)*133.35
   for x,y,z in a['dimm_centers']:
    self.assertFalse(hit(contact,(bx-12.,y,z),(bx+1.,y,z)),model['id'])
    for side in (-1,1):self.assertTrue(hit(contact,(bx-12.,y,z+side*.88),(bx+1.,y,z+side*.88)),model['id'])
    expected_housing.extend((((5.,139.,1.1),(x,y,z-1.7)),((5.,139.,1.1),(x,y,z+1.7)),((2.,1.3,4.5),(bx-2.,y+key_y,z))))
    for side in (-1,1):expected_latches.append(((7.,6.,5.5),(bx-4.2,y+side*70.,z)))
   self.assertEqual(next(m.vertices for m in meshes if m.name=='detail-board-populated-memory-sockets'),_boxes(expected_housing))
   self.assertEqual(next(m.vertices for m in meshes if m.name=='board-dimm-end-latches'),_boxes(expected_latches))
   self.assertEqual(meta['dimm_contact_topology'],'split_side_banks_open_channel_reference');self.assertFalse(meta['dimm_contact_dimensions_verified'])
 def test_asus_step_changes_only_two_photo_reference_u_coordinates(self):
  row=get_model(ASUS);poly=next(c['polygon'] for c in row['heatsinks'] if c['name']=='m2-upper')
  self.assertEqual(poly,NEW_M2)
  self.assertEqual([(n,k) for n,(a,b) in enumerate(zip(poly,OLD_M2)) for k in range(2) if a[k]!=b[k]],[(1,0),(2,0)])
  self.assertEqual(tuple((min(p[k] for p in poly),max(p[k] for p in poly)) for k in range(2)),tuple((min(p[k] for p in OLD_M2),max(p[k] for p in OLD_M2)) for k in range(2)))
  self.assertEqual(row['finish_method'],'official_photo_observed');self.assertEqual(row['layout_method'],'official_manual_observed_proportions')
 def test_all_four_upper_grooves_remain_open_and_every_crown_vertex_stays_inside_real_outline(self):
  meshes,meta,a=boards(ASUS);row=get_model(ASUS);poly=NEW_M2;bh=row['dimensions_mm']['height'];bw=row['dimensions_mm']['width'];by=a['board']['y'];rear=a['board']['rear_z'];bx=a['board']['x']
  low_y=by+(.5-max(v for _,v in poly))*bh;high_y=by+(.5-min(v for _,v in poly))*bh
  crown=next(m for m in meshes if m.name=='board-heatsink-recessed-crown' and abs(min(m.vertices[1::6])+m.position[1]-low_y)<1.e-6 and abs(max(m.vertices[1::6])+m.position[1]-high_y)<1.e-6)
  for at in range(0,len(crown.vertices),6):
   u=(crown.vertices[at+2]+crown.position[2]-rear)/bw;v=.5-(crown.vertices[at+1]+crown.position[1]-by)/bh
   self.assertTrue(within((u,v),poly),(u,v))
  u0,u1=min(u for u,v in poly),max(u for u,v in poly);v=(min(v for u,v in poly)+max(v for u,v in poly))/2
  for i in range(4):
   u=u0+(u1-u0)*(.20+.60*i/3);y=by+(.5-v)*bh;z=rear+u*bw
   for delta in (-.18,0.,.18):self.assertFalse(hit(crown,(bx-9.,y,z+delta),(bx-4.5,y,z+delta)),i)
   self.assertTrue(hit(crown,(bx-9.,y,z+.60),(bx-4.5,y,z+.60)),i)
 def test_modified_socket_and_asus_upper_cap_have_unit_normals_and_no_degenerate_triangles(self):
  for model in MODELS:
   meshes,_meta,_a=boards(model['id']);contact=next(m for m in meshes if m.name=='detail-board-memory-socket-contact-wells');changed=[contact]
   if model['id']==ASUS:
    first=next(i for i,m in enumerate(meshes) if m.name=='detail-board-m2-heatsink');changed.extend(meshes[first:first+2])
   for mesh in changed:
    for at in range(0,len(mesh.vertices),18):
     a,b,c=(mesh.vertices[at+k:at+k+3] for k in (0,6,12));ab=tuple(b[k]-a[k] for k in range(3));ac=tuple(c[k]-a[k] for k in range(3))
     face=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0]);length=math.hypot(*face)
     self.assertGreater(length,1.e-10,(model['id'],mesh.name))
     for offset in (0,6,12):
      normal=mesh.vertices[at+offset+3:at+offset+6];self.assertAlmostEqual(math.hypot(*normal),1.,places=6)
      self.assertGreater(sum(face[k]*normal[k] for k in range(3))/length,.999999)

class ActualReferenceMotion052Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  import hardware_packs
  from hardware_packs import PackStore
  from assembly_parts import reference_preset
  from assembly_profiles import bake_profiles
  from assembly_spec import build_spec
  from assembly_scene_cache import SceneCache
  from stats_config import DEFAULT
  cls.app=QGuiApplication.instance() or QGuiApplication([])
  if cls.app.platformName()!='offscreen':raise unittest.SkipTest('Only software/offscreen reference construction')
  cls.stack=ExitStack();folder=Path(cls.stack.enter_context(tempfile.TemporaryDirectory()))
  cls.stack.enter_context(patch.object(hardware_packs,'_store',PackStore(folder/'packs')))
  for name in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):cls.stack.enter_context(patch(name,side_effect=AssertionError('No hardware/network/thread/process')))
  cls.engine=QQmlEngine();cls.warnings=[];cls.engine.warnings.connect(lambda rs:cls.warnings.extend(r.toString() for r in rs))
  cfg=copy.deepcopy(DEFAULT);cfg['assembly']=dict(reference_preset({},'aio'),case_model='asus-rog-strix-helios-gx601',appearance_style='miniature',cooler_mount='front',case_fans=[dict(model='arctic-p12-pwm',mount='top',count=2,direction='exhaust'),dict(model='arctic-p12-pwm',mount='rear',count=1,direction='exhaust')])
  cls.spec=bake_profiles(build_spec({},cfg,{},[]),cls.engine);cls.spec['visual_style']='miniature';cache=SceneCache();cls.scene=cache.build(cls.spec);cache.clear()
 @classmethod
 def tearDownClass(cls):
  cls.scene=None;cls.engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);cls.stack.close()
  if cls.app.topLevelWindows() or QOpenGLContext.currentContext() is not None:raise AssertionError('No native window/GL context allowed')
 def test_real_reference_cpu_requires_cooler_hidden_and_both_dimms_clear_entire_translation(self):
  for level in ('eco','balanced','close'):
   scene=self.scene if level=='balanced' else build_scene(dict(self.spec,detail_level=level))
   planner=PartMotionPlanner(scene)
   try:
    p=planner.plan('cpu:0',inspection_cutaway=True);self.assertFalse(p['available']);self.assertEqual(p['reason'],'cooler_must_be_hidden_or_moved_first')
    p=planner.plan('cpu:0',hidden_parts=('cooler',),inspection_cutaway=True);self.assertTrue(p['available'],(level,p));self.assertEqual(p['distance_mm'],12.)
    for target in ('memory:0','memory:1'):
     p=planner.plan(target,inspection_cutaway=True);self.assertTrue(p['available'],(level,p));self.assertEqual(p['blocked_by'],());self.assertTrue(p['clearance']['continuous_full_path_checked']);self.assertGreater(p['distance_mm'],40.)
    self.assertEqual(self.warnings,[]);self.assertEqual(scene.metadata['visual_style'],'miniature')
   finally:planner.clear()
 def test_old_m2_step_and_old_solid_contact_each_produce_real_triangle_blockers(self):
  legacy=get_model(ASUS);next(c for c in legacy['heatsinks'] if c['name']=='m2-upper')['polygon']=OLD_M2
  with patch('assembly_motherboard.resolve',return_value=legacy):old=build_scene(self.spec)
  planner=PartMotionPlanner(old)
  try:
   p=planner.plan('memory:0',inspection_cutaway=True);self.assertFalse(p['available']);self.assertTrue(any(r['mesh_name'] in ('detail-board-m2-heatsink','board-heatsink-recessed-crown') for r in p['blocked_by']))
  finally:planner.clear()
  for family in ('cpu','memory'):
   a=[m for m in self.scene.meshes if m.component==family];b=[m for m in old.meshes if m.component==family]
   self.assertEqual([(m.vertices,m.position,m.part_id) for m in a],[(m.vertices,m.position,m.part_id) for m in b])
  a=self.scene.metadata['attachment_anchors'];bx=a['board']['x'];old_contacts=_boxes([((.28,132.,1.9),(bx-1.9,y,z)) for x,y,z in a['dimm_centers']])
  stale=replace(self.scene,meshes=tuple(replace(m,vertices=old_contacts) if m.name=='detail-board-memory-socket-contact-wells' else m for m in self.scene.meshes))
  planner=PartMotionPlanner(stale)
  try:
   p=planner.plan('memory:0',inspection_cutaway=True);self.assertFalse(p['available']);self.assertEqual(p['blocked_by'][0]['mesh_name'],'detail-board-memory-socket-contact-wells')
  finally:planner.clear()

if __name__=='__main__':unittest.main()
