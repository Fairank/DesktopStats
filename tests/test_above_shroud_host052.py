"""Real LANCOOL III AIR/fan consumer and focused software Backend contracts.

No manufacturing compatibility, AIO route, board wiring or extraction claim.
This constructs the public cached-reference pipeline without private poses.
"""
import copy
from contextlib import ExitStack
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtGui import QGuiApplication,QOpenGLContext,QVector3D
from PySide6.QtQml import QQmlEngine

import hardware_packs
from hardware_packs import PackStore
from assembly_cooling import add_cooling,_MOUNT_NORMALS
from assembly_geometry import Mesh,Scene,box,build_scene
from assembly_inspection import part_family
from assembly_mount_frames052 import mount_descriptor
from assembly_part_motion052 import plan_part_motion
from assembly_parts import reference_preset
from assembly_profiles import bake_profiles
from assembly_scene_cache import SceneCache
from assembly_shroud_nzxt_lianli052 import finish
from assembly_spec import build_spec
from assembly_viewer import AssemblyViewport,GL_TRIANGLES
from stats_config import DEFAULT
from top_bar_config import HARDWARE_ICON_STYLES
import test_case_layout_hosts052 as material
from test_gpu_insertion_renderer049 import viewport as clock_host
from test_part_pose_renderer052 import renderer as software_renderer

CASE='lian-li-lancool-iii'
MOUNT='above_psu_shroud'
IDS={'fans:above-psu-shroud:'+str(i) for i in range(3)}
PLATES={'case:psu-mounting-plate:'+str(i) for i in range(3)}
SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')


class AboveShroudHost052Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        if cls.app.platformName()!='offscreen':
            raise unittest.SkipTest('Only software/offscreen reference construction')
        cls.stack=ExitStack();cls.addClassCleanup(cls.stack.close)
        folder=Path(cls.stack.enter_context(tempfile.TemporaryDirectory()))
        cls.stack.enter_context(patch.object(hardware_packs,'_store',PackStore(folder/'packs')))
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            cls.stack.enter_context(patch(target,create=True,side_effect=AssertionError('No native/device/network/worker')))
        cls.engine=QQmlEngine();cls.warnings=[]
        cls.engine.warnings.connect(lambda rows:cls.warnings.extend(row.toString() for row in rows))
        config=copy.deepcopy(DEFAULT)
        config['assembly']=dict(reference_preset({},'air'),case_model=CASE,
            detail_level='balanced',appearance_style='miniature',part_styles={},
            cables_enabled=False,case_fans=[dict(model='arctic-p12-pwm',mount=MOUNT,count=3,direction='intake')])
        original=copy.deepcopy(config)
        cls.spec=bake_profiles(build_spec({},config,{},[]),cls.engine)
        cls.cache=SceneCache();cls.scene=cls.cache.build(cls.spec)
        if config!=original:raise AssertionError('Public construction mutated fresh configuration')
        base=copy.deepcopy(cls.spec);base['cooling']['case_fans']=[]
        cls.baseline=build_scene(base)
        cls.geometry={}

    @classmethod
    def tearDownClass(cls):
        cls.scene=None;cls.baseline=None;cls.spec=None;cls.geometry.clear();cls.cache.clear()
        cls.engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        if cls.warnings:raise AssertionError(cls.warnings)
        if cls.app.topLevelWindows() or QOpenGLContext.currentContext() is not None:
            raise AssertionError('No native window or GL context allowed')

    def shape(self,mesh):
        key=id(mesh)
        if key not in self.geometry:self.geometry[key]=material._geometry(mesh)
        return self.geometry[key]

    def test_actual_safe_ids_three_complete_fans_and_retained_reference_core(self):
        scene=self.scene;meta=scene.metadata;cooling=meta['cooling']
        self.assertEqual(meta['case_id'],CASE);self.assertEqual(cooling['rejected'],[])
        self.assertEqual(meta['auxiliary']['rejected'],[])
        self.assertEqual(meta['auxiliary']['device_counts']['psu'],1)
        self.assertEqual(meta['auxiliary']['cable_count'],0)
        self.assertEqual([sum(p['kind']==kind for p in meta['hardware']['parts'])
                          for kind in ('cpu','gpu','memory')],[1,1,2])
        self.assertEqual(self.spec['cpu']['appearance']['id'],'intel-13700kf')
        self.assertEqual(self.spec['gpu']['appearance']['id'],'asus-astral-5090')
        self.assertEqual(meta['memory_models'],['gskill-f4-3200c16d-16gtzr']*2)
        self.assertTrue(all(c['state']=='within_limit' for c in self.spec['checks']))
        rows=[p for p in cooling['parts'] if p['kind']=='case_fan']
        self.assertEqual({p['id'] for p in rows},IDS)
        for row in rows:
            self.assertEqual(row['mount'],MOUNT);self.assertFalse(row['cad_fit_verified'])
            self.assertEqual(row['compatibility'],'documented_fan_mount')
            selected=[m for m in scene.meshes if m.part_id==row['id']]
            for name in ('case-fan-frame','case-fan-leaves-hub','case-fan-power-connector','case-fan-power-lead'):
                self.assertEqual(sum(m.name==name for m in selected),1,(row,name))
            self.assertEqual(sum(m.rotor for m in selected),1)
            self.assertEqual(part_family(row['id'],meta),'fans')
        plane=meta['attachment_anchors']['case_mount_planes'][MOUNT]
        self.assertEqual(plane['source_manual_pdf_page'],9)
        self.assertFalse(plane['positions_verified']);self.assertFalse(plane['dimensions_verified'])
        self.assertFalse(plane['motion_supported']);self.assertFalse(plane['radiator_runtime_supported'])
        self.assertEqual(plane['source_capacity_count'],3);self.assertEqual(plane['source_capacity_size_mm'],120)

    def test_actual_every_fan_surface_and_full_rotor_sweep_clear_gpu_psu_and_case_material(self):
        from case_fan_clearance047 import _bounds
        scene=self.scene
        obstacles=[m for m in scene.meshes if m.component in ('case','panel','gpu','psu')]
        fan_meshes=[m for m in scene.meshes if m.part_id in IDS]
        for fan in fan_meshes:
            for other in obstacles:
                self.assertIsNone(material._positive_overlap(self.shape(fan),self.shape(other)),
                    (fan.part_id,fan.name,other.part_id,other.name))
        # The actual rotor's radius and axial extrema bound every phase, not
        # only the phase-zero blades. Here retained hardware is strictly out
        # of that full bound; ambiguous material pairs above use real faces.
        for rotor in (m for m in fan_meshes if m.rotor):
            self.assertEqual(abs(rotor.axis[1]),1.)
            radial=max((x*x+z*z)**.5 for x,z in zip(rotor.vertices[0::6],rotor.vertices[2::6]))
            actual=_bounds(rotor.vertices,rotor.position)
            swept=((rotor.position[0]-radial,actual[0][1],rotor.position[2]-radial),
                   (rotor.position[0]+radial,actual[1][1],rotor.position[2]+radial))
            for hardware in (m for m in obstacles if m.component in ('gpu','psu')):
                self.assertFalse(material._overlap(swept,self.shape(hardware)[2],strict=True),
                    ('full swept rotor bound',rotor.part_id,hardware.name))

    def test_real_finish_removes_only_three_plates_and_keeps_bracket_doors_and_other_hardware(self):
        meta=self.scene.metadata['case_shroud'];baseline=self.baseline
        self.assertEqual({row['id'] for row in meta['removed_parts']},PLATES)
        self.assertTrue(all(row['physical_mesh_present']is False for row in meta['removed_parts']))
        self.assertEqual({m.part_id for m in baseline.meshes if m.part_id in PLATES},PLATES)
        self.assertFalse(any(m.part_id in PLATES for m in self.scene.meshes))
        retained={'case:psu-top-bracket','case:psu-side-door:left','case:psu-side-door:right'}
        for identity in retained:
            self.assertEqual([m for m in baseline.meshes if m.part_id==identity],
                             [m for m in self.scene.meshes if m.part_id==identity])
        for kind in ('cpu','gpu','memory','board','psu'):
            self.assertEqual([m for m in baseline.meshes if m.component==kind],
                             [m for m in self.scene.meshes if m.component==kind],kind)

    def test_whole_group_hardware_conflict_keeps_gpu_and_all_requested_plates(self):
        anchors=self.scene.metadata['attachment_anchors']
        center=next(f['position'] for f in self.scene.metadata['cooling']['fans'] if f['part_id'] in IDS)
        blocker=Mesh('negative-control-gpu-solid',box(8.,6.,8.),(1.,1.,1.,1.),center,'gpu',part_id='gpu:fixture')
        occupied=(*self.baseline.meshes,blocker)
        spec=copy.deepcopy(self.spec);spec['cooling']['cpu_cooler']='none'
        added,meta=add_cooling(occupied,spec,'balanced',anchors)
        self.assertEqual(len(added),0);self.assertEqual(meta['parts'],[]);self.assertEqual(meta['wire_anchors'],[])
        rejected=next(r for r in meta['rejected'] if r.get('mount')==MOUNT)
        self.assertEqual(rejected['reason'],'case_fan_clearance_conflict')
        self.assertEqual(rejected['omitted_count'],3)
        self.assertIn('gpu:fixture',rejected['conflicting_parts'])
        output,state=finish(occupied,added,meta,self.baseline.metadata['case_shroud'])
        self.assertEqual(output,occupied);self.assertEqual(state['removed_parts'],[])
        self.assertEqual({m.part_id for m in output if m.part_id in PLATES},PLATES)

    def test_missing_authored_frame_other_case_and_legacy_five_are_never_side_fallback(self):
        anchors=copy.deepcopy(self.scene.metadata['attachment_anchors'])
        spec=dict(case=self.spec['case'],cooling=dict(cpu_cooler='none',case_fans=[
            dict(model='arctic-p12-pwm',mount=MOUNT,count=3,direction='intake')]))
        anchors['case_mount_planes'].pop(MOUNT)
        added,meta=add_cooling((),spec,'eco',anchors)
        self.assertEqual(len(added),0);self.assertEqual(meta['rejected'][0]['reason'],'case_fan_mount_reference_unavailable')
        other=copy.deepcopy(spec);other['case']['id']='lian-li-lancool-207'
        added,meta=add_cooling((),other,'eco',self.scene.metadata['attachment_anchors'])
        self.assertEqual(len(added),0);self.assertEqual(meta['rejected'][0]['reason'],'case_fan_mount_reference_unavailable')
        # A real 207 source row supports TWO120s. Missing its own authored
        # placement is a reference gap, not evidence of retail incompatibility.
        # Conversely, THREE120s genuinely exceed that exact catalog count.
        from chassis_catalog import get_case
        other['case']=get_case('lian-li-lancool-207')
        other['cooling']['case_fans'][0]['count']=2
        foreign=copy.deepcopy(anchors);foreign['case']=other['case']
        added,meta=add_cooling((),other,'eco',foreign)
        self.assertEqual(len(added),0)
        self.assertEqual(meta['rejected'][0]['reason'],'case_fan_mount_reference_unavailable')
        # No accepted cooling must remove the original III fixture's plates;
        # this does NOT invent those plates or a III bracket in the real207.
        output,state=finish(self.baseline.meshes,added,meta,self.baseline.metadata['case_shroud'])
        self.assertEqual(output,self.baseline.meshes);self.assertEqual(state['removed_parts'],[])
        self.assertEqual({m.part_id for m in output if m.part_id in PLATES},PLATES)
        other['cooling']['case_fans'][0]['count']=3
        added,meta=add_cooling((),other,'eco',foreign)
        self.assertEqual(len(added),0);self.assertEqual(meta['rejected'][0]['reason'],'unsupported_fan_mount')
        self.assertEqual(tuple(_MOUNT_NORMALS),('front','rear','top','bottom','side'))
        # An unused authored special plane cannot change ANY legacy five
        # construction path, including its exact fan arrays/parts/wire ends.
        full=self.scene.metadata['attachment_anchors']
        for mount in _MOUNT_NORMALS:
            old=dict(case={},cooling=dict(cpu_cooler='none',case_fans=[dict(model='arctic-p12-pwm',mount=mount,count=1)]))
            self.assertEqual(add_cooling((),old,'eco',full),add_cooling((),old,'eco',anchors),mount)

    def test_all_saved_styles_share_actual_fan_arrays_and_exact_safe_style_selection(self):
        base=[m for m in self.scene.meshes if not m.name.startswith('style-')]
        for style in HARDWARE_ICON_STYLES:
            scene=self.cache.build(dict(self.spec,visual_style=style,
                part_styles={'fans:above-psu-shroud:1':'notebook_line'}))
            values=[m for m in scene.meshes if not m.name.startswith('style-')]
            self.assertEqual(len(values),len(base))
            for a,b in zip(base,values):
                self.assertIs(a.vertices,b.vertices)
                self.assertEqual((a.name,a.component,a.part_id,a.position,a.axis,a.rotor,a.direction),
                                 (b.name,b.component,b.part_id,b.position,b.axis,b.rotor,b.direction))
            for mesh,style_id in zip(scene.meshes,scene.metadata['mesh_style_ids']):
                if mesh.part_id=='fans:above-psu-shroud:1':self.assertEqual(style_id,'notebook_line')
            self.assertEqual(part_family('fans:above-psu-shroud:1',scene.metadata),'fans')

    def test_unknown_extraction_stays_unavailable_but_explicit_demo_and_pause_reach_real_fan_geometry(self):
        for identity in IDS:
            descriptor=mount_descriptor(self.scene,identity)
            self.assertFalse(descriptor['available']);self.assertFalse(descriptor['motion_available'])
            for released in ((),(identity,)):
                plan=plan_part_motion(self.scene,identity,released_mounts=released,inspection_cutaway=True)
                self.assertFalse(plan['available']);self.assertEqual(plan['reason'],'case_fan_mount_unverified')
        # Only the selected ACTUAL fan arrays enter this focused fake-VBO
        # renderer proof. It is not a native whole-application GPU test.
        for style in SIX:
            full=self.cache.build(dict(self.spec,visual_style=style,part_styles={}))
            selected=[(index,m) for index,m in enumerate(full.meshes) if m.part_id in IDS]
            indices={old:new for new,(old,_) in enumerate(selected)}
            metadata=copy.deepcopy(full.metadata)
            old_zones=copy.deepcopy(full.metadata['lighting_preview']['zones'])
            self.assertEqual(sum(full.meshes[row['mesh_index']].component=='memory' for row in old_zones),2)
            metadata['lighting_preview']['zones']=[dict(row,mesh_index=indices[row['mesh_index']])
                for row in old_zones if row['mesh_index'] in indices]
            metadata['mesh_style_ids']=tuple(full.metadata['mesh_style_ids'][old] for old,_ in selected)
            value=Scene(tuple(m for _,m in selected),full.dimensions,metadata)
            self.assertEqual(full.metadata['lighting_preview']['zones'],old_zones)
            self.assertEqual(len(metadata['lighting_preview']['zones']),
                             sum(row['mesh_index'] in indices for row in old_zones))
            for row in metadata['lighting_preview']['zones']:
                self.assertEqual(value.meshes[row['mesh_index']].part_id,row['part_id'])
            node,state=clock_host(value);node._focus='fans';node._animate=True
            node._fan_available=True;node._rpm=1600.;node._fan_expiry=float('inf')
            node._cpu_available=True;node._cpu_tach_usable=True;node._cpu_rpm=900.;node._cpu_expiry=float('inf')
            AssemblyViewport._update_animation_state(node)
            self.assertFalse(node._active,'Actual CPU/GPU tach cannot animate these case fans')
            node._demo=True;AssemblyViewport._update_animation_state(node)
            self.assertTrue(node._active);self.assertTrue(AssemblyViewport._step_fans(node,136.))
            self.assertGreater(node._demo_phase,0.)
            render=software_renderer(value)
            try:
                seen={};draw=render._draw_part
                def observe(row,*args,**kwargs):
                    draw(row,*args,**kwargs)
                    if kwargs.get('mode',GL_TRIANGLES)!=GL_TRIANGLES:return
                    mesh=row[0]
                    matrix=next(arguments[1] for name,arguments in reversed(render.program.calls)
                        if name=='setUniformValue' and arguments[0]=='modelMatrix')
                    point=max((mesh.vertices[at:at+3] for at in range(0,len(mesh.vertices),6)),
                              key=lambda p:p[0]*p[0]+p[2]*p[2]) if mesh.rotor else mesh.vertices[:3]
                    p=matrix.map(QVector3D(*point))
                    seen[(mesh.part_id,mesh.name)]=(p.x(),p.y(),p.z())
                render._draw_part=observe
                render.draw(700,500,phase={'fans':0.},focus='fans');before=dict(seen);seen.clear()
                render.draw(700,500,phase={'fans':37.},focus='fans')
                for mesh in value.meshes:
                    key=(mesh.part_id,mesh.name)
                    self.assertIn(key,seen)
                    if mesh.rotor:self.assertNotEqual(seen[key],before[key])
                    else:self.assertEqual(seen[key],before[key])
            finally:render.close()
            for cause in ('hidden','minimized','motion'):
                state['visible']=cause!='hidden';state['minimized']=cause=='minimized';node._motion=cause!='motion'
                AssemblyViewport._update_animation_state(node);self.assertFalse(node._active)


if __name__=='__main__':unittest.main()
