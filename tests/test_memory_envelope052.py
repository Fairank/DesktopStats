"""Fresh public profiles keep separate PCB, spreader and RGB total heights.

Software/offscreen construction only: these are physical model contracts,
not native pixels, hardware inventory or manufacturer installation tests.
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

SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')
CASES=('fractal-north-mesh','fractal-define-7-compact-solid','fractal-meshify-2-light-tg')
MODELS=(('gskill-f4-3200c16d-16gtzr',44.,31.),
        ('corsair-cmt32gx5m2b5600c36',56.,31.),
        ('kingston-kvr32n22s8-16',31.25,31.25))


def bounds(mesh):
    return tuple(tuple(f(mesh.vertices[k::6])+mesh.position[k] for k in range(3)) for f in (min,max))


class MemoryEnvelope052Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        if cls.app.platformName()!='offscreen':raise unittest.SkipTest('Software/offscreen only')
        cls.stack=ExitStack();cls.addClassCleanup(cls.stack.close)
        folder=Path(cls.stack.enter_context(tempfile.TemporaryDirectory()))
        cls.stack.enter_context(patch.object(hardware_packs,'_store',PackStore(folder/'packs')))
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            cls.stack.enter_context(patch(target,create=True,side_effect=AssertionError('No device or worker in reference fixture')))
        cls.engine=QQmlEngine();cls.warnings=[]
        cls.engine.warnings.connect(lambda rows:cls.warnings.extend(row.toString() for row in rows))
        cls.rows={}
        for identity,total,pcb in MODELS:
            config=copy.deepcopy(DEFAULT);config['assembly']=reference_preset({},'air')
            config['assembly'].update(case_model=CASES[0],cpu_model='intel-13700kf',
                gpu_model='asus-astral-5090',board_model='asus-rog-strix-z790-a-wifi-d4',
                memory_models=[identity],cooler_model='none',case_fans=[],cables_enabled=False,
                detail_level='eco',appearance_style='miniature',part_styles={})
            before=copy.deepcopy(config);spec=bake_profiles(build_spec({},config,{},[]),cls.engine)
            if config!=before:raise AssertionError('Public profile construction mutated configuration')
            cls.rows[identity]=(spec,build_scene(spec),total,pcb)

    @classmethod
    def tearDownClass(cls):
        cls.rows.clear();cls.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        if cls.warnings:raise AssertionError(cls.warnings)
        if cls.app.topLevelWindows() or QOpenGLContext.currentContext() is not None:raise AssertionError('No native window/GL')

    def test_public_model_keeps_pcb_and_complete_envelope_separate_and_input_detached(self):
        for identity,(spec,scene,total,pcb_h) in self.rows.items():
            with self.subTest(model=identity):
                before=copy.deepcopy(spec);second=build_scene(spec);self.assertEqual(spec,before)
                pcb=next(m for m in scene.meshes if m.name=='ram-pcb');low,high=bounds(pcb)
                self.assertAlmostEqual(high[0]-low[0],pcb_h)
                modules=[m for m in scene.meshes if m.part_id=='memory:0']
                self.assertTrue(modules)
                outer_top=min(bounds(m)[0][0] for m in modules)
                self.assertAlmostEqual(high[0]-outer_top,total,places=6)
                self.assertEqual(scene.meshes,second.meshes)
                self.assertEqual(spec['memory']['modules'][0]['total_height_mm'],total)
                self.assertIsNone(spec['memory']['total_height_mm'])

    def test_rgb_cap_meets_spreader_instead_of_floating_at_pcb_top(self):
        for identity,(spec,scene,total,pcb_h) in self.rows.items():
            caps=[m for m in scene.meshes if m.name=='ram-diffuser']
            spreaders=[m for m in scene.meshes if m.name=='ram-spreader']
            if identity.startswith('kingston-kvr'):
                self.assertEqual((caps,spreaders),([],[]));continue
            self.assertEqual(len(caps),1);self.assertEqual(len(spreaders),1)
            cap=bounds(caps[0]);metal=bounds(spreaders[0])
            self.assertAlmostEqual(cap[1][0],metal[0][0],places=6)
            self.assertAlmostEqual(cap[1][0]-cap[0][0],3.)

    def test_six_styles_reuse_exact_memory_vertices_and_keep_all_part_identities(self):
        spec=self.rows[MODELS[0][0]][0];cache=SceneCache();base=cache.build(spec)
        original=[m for m in base.meshes if m.component=='memory']
        self.assertTrue(original)
        for style in SIX:
            scene=cache.build(dict(spec,visual_style=style))
            memory=[m for m in scene.meshes if m.component=='memory']
            self.assertEqual(len(memory),len(original))
            for first,current in zip(original,memory):
                self.assertIs(first.vertices,current.vertices)
                self.assertEqual((first.name,first.position,first.part_id,first.rotor,first.axis),
                                 (current.name,current.position,current.part_id,current.rotor,current.axis))
        cache.clear()

    def test_fresh_production44mm_identity_rejects_whole_limited_top_cooling_group(self):
        from chassis_catalog import get_case
        spec=self.rows[MODELS[0][0]][0]
        for case_id in CASES[:2]:
            fresh=copy.deepcopy(spec);fresh['case']=get_case(case_id)
            fresh['cooling']=dict(cpu_cooler='arctic-liquid-freezer-iii-240',radiator_mount='top')
            scene=build_scene(fresh);cooling=scene.metadata['cooling']
            self.assertEqual(cooling['parts'],[])
            self.assertEqual(cooling['rejected'][0]['reason'],'radiator_memory_height_exceeds_case_limit')
            self.assertEqual(sum(m.name=='ram-pcb' for m in scene.meshes),1)
            self.assertFalse(any(m.component=='cooler' for m in scene.meshes))


if __name__=='__main__':unittest.main()
