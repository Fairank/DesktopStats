"""Fresh Torrent reference hosts; actual solids, never a factory fit claim."""
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
from assembly_visibility048 import mesh_visible
import hardware_packs
from hardware_packs import PackStore
from stats_config import DEFAULT
from test_case_layout_hosts052 import _geometry,_positive_overlap

CASE='fractal-torrent-tg'
TOP='case:psu-top-cover'
BOTTOM='case:bottom-intake-frame'
SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')


class TorrentHost052Tests(unittest.TestCase):
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
        for size in (120,140):
            config=copy.deepcopy(DEFAULT);config['assembly']=reference_preset({},'air')
            config['assembly'].update(case_model=CASE,cpu_model='intel-13700kf',gpu_model='asus-astral-5090',
                board_model='asus-rog-strix-z790-a-wifi-d4',memory_models=['gskill-f4-3200c16d-16gtzr']*2,
                psu_model='corsair-rm1000x-2024',cooler_model='noctua-nh-u12a',cables_enabled=False,
                detail_level='balanced',appearance_style='miniature',part_styles={},
                case_fans=[dict(model='arctic-p'+('12' if size==120 else '14')+'-pwm',
                    mount=mount,count=3,direction='intake') for mount in ('front','bottom')])
            before=copy.deepcopy(config);spec=bake_profiles(build_spec({},config,{},[]),cls.engine)
            scene=build_scene(spec)
            if config!=before:raise AssertionError('Public host construction mutated configuration')
            cls.rows.append((size,spec,scene))

    @classmethod
    def tearDownClass(cls):
        cls.rows.clear();cls.shapes.clear();cls.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        if cls.warnings:raise AssertionError(cls.warnings)
        if cls.app.topLevelWindows() or QOpenGLContext.currentContext() is not None:raise AssertionError('No native window/GL')

    def geometry(self,mesh):
        if id(mesh) not in self.shapes:self.shapes[id(mesh)]=_geometry(mesh)
        return self.shapes[id(mesh)]

    def test_all_actual_identities_and_six_requested_casefans_remain_without_omissions(self):
        for size,spec,scene in self.rows:
            with self.subTest(size=size):
                parts=scene.metadata['hardware']['parts'];cooling=scene.metadata['cooling']
                self.assertEqual(scene.metadata['case_id'],CASE)
                self.assertEqual([r['id'] for r in parts if r['kind']=='cpu'],['cpu:0'])
                self.assertEqual([r['id'] for r in parts if r['kind']=='gpu'],['gpu:0'])
                self.assertEqual(sum(m.name=='ram-pcb' for m in scene.meshes),2)
                self.assertEqual(spec['memory']['modules'][0]['total_height_mm'],44.)
                self.assertEqual(cooling['rejected'],[])
                fans=[r for r in cooling['parts'] if r['kind']=='case_fan']
                self.assertEqual({r['id'] for r in fans},{'fans:'+mount+':'+str(i) for mount in ('front','bottom') for i in range(3)})
                self.assertEqual(scene.metadata['auxiliary']['device_counts']['psu'],1)
                self.assertEqual(sum(m.name=='psu-shell' for m in scene.meshes),1)
                self.assertTrue(any(m.component=='cooler' for m in scene.meshes))

    def test_top_skin_and_open_intake_replace_only_the_two_false_solid_models(self):
        for size,spec,scene in self.rows:
            state=scene.metadata['case_shroud'];rows={r['id']:r for r in state['parts']}
            self.assertEqual(set(rows),{TOP,BOTTOM})
            self.assertEqual(rows[TOP]['kind'],'case_cover');self.assertEqual(rows[BOTTOM]['kind'],'case_structure')
            self.assertFalse(any(m.name=='case-bottom' for m in scene.meshes))
            self.assertEqual(sum(m.part_id==TOP for m in scene.meshes),1)
            self.assertEqual(sum(m.part_id==BOTTOM for m in scene.meshes),1)
            self.assertEqual(sum(m.name=='case-foot' for m in scene.meshes),4)
            self.assertTrue(any(m.name=='case-depth-rail' for m in scene.meshes))
            for mesh in scene.meshes:
                if mesh.part_id==TOP:self.assertFalse(mesh_visible(mesh,True,True))
                if mesh.part_id==BOTTOM:self.assertTrue(mesh_visible(mesh,True,True))

    def test_actual_fan_frames_rotors_plugs_psu_and_board_have_no_positive_material_overlap(self):
        for size,spec,scene in self.rows:
            materials=[m for m in scene.meshes if m.part_id in (TOP,BOTTOM)]
            hardware=[m for m in scene.meshes if m.component in ('psu','cpu','gpu','memory','board','cooler','fans')]
            self.assertTrue(materials);self.assertTrue(hardware)
            for material in materials:
                for mesh in hardware:
                    self.assertIsNone(_positive_overlap(self.geometry(material),self.geometry(mesh)),
                        (size,material.name,mesh.name,mesh.part_id))

    def test_six_styles_keep_physical_arrays_and_source_case_part_visibility(self):
        spec=self.rows[0][1];cache=SceneCache();base=cache.build(spec)
        physical=[m for m in base.meshes if not m.name.startswith('style-')]
        for style in SIX:
            value=cache.build(dict(spec,visual_style=style));rows=[m for m in value.meshes if not m.name.startswith('style-')]
            self.assertEqual(len(rows),len(physical))
            for old,current in zip(physical,rows):
                self.assertIs(current.vertices,old.vertices)
                self.assertEqual((current.position,current.part_id,current.axis,current.rotor),
                                 (old.position,old.part_id,old.axis,old.rotor))
        cache.clear()


if __name__=='__main__':unittest.main()
