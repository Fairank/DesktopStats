"""Six fresh selected AIR builds; source reference structures, not factory CAD."""
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
from PySide6.QtGui import QGuiApplication,QOpenGLContext
from PySide6.QtQml import QQmlEngine
from assembly_geometry import build_scene
from assembly_parts import reference_preset
from assembly_profiles import bake_profiles
from assembly_scene_cache import SceneCache
from assembly_spec import build_spec
import hardware_packs
from hardware_packs import PackStore
from stats_config import DEFAULT
from test_case_layout_hosts052 import _geometry,_positive_overlap

SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')
COWBOY='geometric-future-model-8-cowboy'
JOBS=(('hyte-y70',120,3),('hyte-y70',140,2),(COWBOY,120,3),(COWBOY,140,3),
      ('phanteks-nv5',120,1),('phanteks-evolv-x2',120,3))


class SpecialCaseHosts052Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        if cls.app.platformName()!='offscreen':raise unittest.SkipTest('Offscreen reference only')
        cls.stack=ExitStack();cls.addClassCleanup(cls.stack.close)
        folder=Path(cls.stack.enter_context(tempfile.TemporaryDirectory()))
        cls.stack.enter_context(patch.object(hardware_packs,'_store',PackStore(folder/'packs')))
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            cls.stack.enter_context(patch(target,create=True,side_effect=AssertionError('No device/window/worker')))
        cls.engine=QQmlEngine();cls.warnings=[]
        cls.engine.warnings.connect(lambda rows:cls.warnings.extend(row.toString() for row in rows))
        cls.rows=[];cls.shapes={}
        for case,size,count in cls.jobs:
            config=copy.deepcopy(DEFAULT);config['assembly']=reference_preset({},'air')
            config['assembly'].update(case_model=case,cpu_model='intel-13700kf',gpu_model='asus-astral-5090',
                board_model='asus-rog-strix-z790-a-wifi-d4',memory_models=['gskill-f4-3200c16d-16gtzr']*2,
                psu_model='corsair-rm1000x-2024',cooler_model='noctua-nh-u12a',cables_enabled=False,
                detail_level='balanced',appearance_style='miniature',part_styles={},
                case_fans=[dict(model='arctic-p'+('12' if size==120 else '14')+'-pwm',
                    mount='bottom',count=count,direction='intake')])
            before=copy.deepcopy(config);spec=bake_profiles(build_spec({},config,{},[]),cls.engine)
            scene=build_scene(spec)
            if config!=before:raise AssertionError('Host construction mutated configuration')
            cls.rows.append((case,size,count,spec,scene))

    @classmethod
    def tearDownClass(cls):
        cls.rows.clear();cls.shapes.clear();cls.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        if cls.warnings:raise AssertionError(cls.warnings)
        if cls.app.topLevelWindows() or QOpenGLContext.currentContext() is not None:raise AssertionError('No native window/GL')

    def geometry(self,mesh):
        if id(mesh) not in self.shapes:self.shapes[id(mesh)]=_geometry(mesh)
        return self.shapes[id(mesh)]

    def test_actual_requested_hardware_and_bottom_fans_are_present_without_rejection(self):
        for case,size,count,spec,scene in self.rows:
            with self.subTest(case=case,size=size):
                cooling=scene.metadata['cooling'];parts=scene.metadata['hardware']['parts']
                self.assertEqual(cooling['rejected'],[])
                self.assertEqual(scene.metadata['case_id'],case)
                self.assertEqual([r['id'] for r in parts if r['kind']=='cpu'],['cpu:0'])
                self.assertEqual([r['id'] for r in parts if r['kind']=='gpu'],['gpu:0'])
                self.assertEqual(sum(m.name=='ram-pcb' for m in scene.meshes),2)
                self.assertEqual(spec['memory']['modules'][0]['total_height_mm'],44.)
                self.assertEqual(scene.metadata['auxiliary']['device_counts']['psu'],1)
                self.assertEqual(sum(m.name=='psu-shell' for m in scene.meshes),1)
                self.assertTrue(any(m.component=='cooler' for m in scene.meshes))
                self.assertEqual({r['id'] for r in cooling['parts'] if r['kind']=='case_fan'},
                    {'fans:bottom:'+str(i) for i in range(count)})

    def test_source_structures_replace_false_generic_material_and_remain_independent(self):
        for case,size,count,spec,scene in self.rows:
            with self.subTest(case=case,size=size):
                meta=scene.metadata['case_shroud'];ids={r['id'] for r in meta['parts']}
                self.assertFalse(meta.get('positions_verified',False))
                self.assertTrue(ids)
                self.assertFalse(any(m.name=='case-bottom' for m in scene.meshes))
                self.assertFalse(any(m.name in ('psu-shroud','rear-chamber-shroud') and not m.part_id
                    for m in scene.meshes))
                self.assertFalse(meta.get('chamber_is_solid',False))
                if case=='phanteks-evolv-x2':
                    self.assertTrue(any(m.part_id=='case:lower-support-floor' for m in scene.meshes))
                    self.assertFalse(any(m.name=='case-elevated-reference-floor' for m in scene.meshes))
                    self.assertTrue(any(m.name=='case-elevated-reference-plinth' for m in scene.meshes))
                for identity in ids:
                    self.assertGreaterEqual(sum(m.part_id==identity for m in scene.meshes),1)
                    self.assertTrue(any(r['id']==identity for r in scene.metadata['hardware']['parts']))

    def test_actual_selected_hardware_has_no_positive_overlap_with_new_reference_material(self):
        for case,size,count,spec,scene in self.rows:
            ids={r['id'] for r in scene.metadata['case_shroud']['parts']}
            materials=[m for m in scene.meshes if m.part_id in ids or m.name in (
                'rear-chamber-divider','case-cold-floor-deck')]
            hardware=[m for m in scene.meshes if m.component in ('psu','cpu','gpu','memory','board','cooler','fans')]
            self.assertTrue(materials);self.assertTrue(hardware)
            for material in materials:
                for mesh in hardware:
                    self.assertIsNone(_positive_overlap(self.geometry(material),self.geometry(mesh)),
                        (case,size,material.name,mesh.name,mesh.part_id))

    def test_all_six_styles_reuse_physical_vertices_pose_axes_and_identity(self):
        seen=set()
        for case,size,count,spec,scene in self.rows:
            if case in seen:continue
            seen.add(case);cache=SceneCache();base=cache.build(spec)
            physical=[m for m in base.meshes if not m.name.startswith('style-')]
            for style in SIX:
                value=cache.build(dict(spec,visual_style=style))
                rows=[m for m in value.meshes if not m.name.startswith('style-')]
                self.assertEqual(len(rows),len(physical))
                for old,current in zip(physical,rows):
                    self.assertIs(current.vertices,old.vertices)
                    self.assertEqual((current.position,current.part_id,current.axis,current.rotor),
                        (old.position,old.part_id,old.axis,old.rotor))
            cache.clear()

    def test_cowboy_board_group_rotates_rigidly_with_top_io_and_selected_psu_actual_size(self):
        case,size,count,spec,scene=next(row for row in self.rows if row[0]==COWBOY)
        canonical=copy.deepcopy(spec);canonical['case']['id']='unbound-cowboy-reference'
        canonical['cooling']=dict(cpu_cooler='none',case_fans=[]);canonical['auxiliary']={}
        original=build_scene(canonical)
        old_board=original.metadata['attachment_anchors']['board']
        center=old_board['position'];reference=scene.metadata['case_pose_reference']['board_pose']
        target=(center[0],reference['io_y_mm']-old_board['width']/2,
                reference['rear_z_mm']+old_board['height']/2)
        def rotate(p):return (p[0],-p[2],p[1])
        def pose(p):
            rotated=rotate(tuple(p[k]-center[k] for k in range(3)))
            return tuple(target[k]+rotated[k] for k in range(3))
        family={'board','cpu','gpu','memory'}
        left=[m for m in original.meshes if m.component in family]
        right=[m for m in scene.meshes if m.component in family]
        self.assertEqual(len(left),len(right))
        for old,current in zip(left,right):
            self.assertEqual((old.name,old.part_id,old.rotor),(current.name,current.part_id,current.rotor))
            for a,b in zip(pose(old.position),current.position):self.assertAlmostEqual(a,b,places=7)
            for start in range(0,len(old.vertices),3):
                for a,b in zip(rotate(old.vertices[start:start+3]),current.vertices[start:start+3]):
                    self.assertAlmostEqual(a,b,places=7)
            # Post-pose socket meshes are rebuilt from transformed anchors.
            # Their unused default axis is not a physical rotation vector;
            # every actual rotor axis must still follow the rigid pose.
            if old.rotor:self.assertEqual(rotate(old.axis),current.axis,(old.name,old.component))
        self.assertEqual(scene.metadata['gpu_mount'],'case_top_io')
        self.assertEqual(scene.metadata['attachment_anchors']['psu']['world_dimensions_mm'],(150.,160.,86.))


def load_tests(loader,tests,pattern):
    # Keep at most one case's two selected sizes in memory at once. Each
    # class finishes and releases its scenes before the next case is built.
    # Every fixed JOB remains present; no environment filter or hidden skip.
    suite=unittest.TestSuite()
    for case in dict.fromkeys(row[0] for row in JOBS):
        attributes=dict(jobs=tuple(row for row in JOBS if row[0]==case))
        if case!=COWBOY:
            attributes['test_cowboy_board_group_rotates_rigidly_with_top_io_and_selected_psu_actual_size']=None
        selected=type(case.replace('-','_')+'Host052Tests',(SpecialCaseHosts052Tests,),attributes)
        suite.addTests(loader.loadTestsFromTestCase(selected))
    return suite


if __name__=='__main__':unittest.main()
