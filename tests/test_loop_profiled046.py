"""Selected loops use the same flattened hardware profiles as the real window."""
import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtGui import QGuiApplication,QOpenGLContext
from PySide6.QtQml import QQmlEngine

import hardware_packs
from hardware_packs import PackStore
from assembly_profiles import bake_profiles
from assembly_scene_cache import SceneCache
from assembly_spec import build_spec
from assembly_style import edge_batches,MAX_MESH_EDGES,MAX_STYLE_EDGES
from test_loop_auxiliary_clearance046 import configuration

SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')


class ProfiledLoop046Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        if cls.app.platformName()!='offscreen':raise unittest.SkipTest('Software offscreen regression only')

    def setUp(self):
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(target,side_effect=AssertionError('No device, network or worker')))
        private=Path(self.enterContext(tempfile.TemporaryDirectory()))
        store=PackStore(private/'installed')
        store.install(Path(__file__).resolve().parents[1]/'model-packs/v046/DesktopStats-loop-collection-046-1.0.0.dspack')
        self.enterContext(patch.object(hardware_packs,'_store',store))
        self.engine=QQmlEngine();self.warnings=[]
        self.engine.warnings.connect(lambda rows:self.warnings.extend(row.toString() for row in rows))

    def tearDown(self):
        self.engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.assertEqual(self.warnings,[])
        self.assertEqual(self.app.topLevelWindows(),[])
        self.assertIsNone(QOpenGLContext.currentContext())

    def baked(self,case):
        raw=build_spec({},configuration(case),{},[])
        self.assertNotIn('shell_polygon',raw['gpu'])
        baked=bake_profiles(raw,self.engine)
        self.assertTrue(baked['gpu']['shell_polygon'])
        self.assertTrue(baked['gpu']['detail_polygons'])
        self.assertEqual(len(baked['gpu']['fans']),3)
        self.assertTrue(all(fan['blade_polygons'] for fan in baked['gpu']['fans']))
        self.assertTrue(baked['memory']['modules'][0]['case_polygon'])
        return baked

    def test_actual_profiled_haf_retains_all_six_styles_and_bounded_ink(self):
        spec=self.baked('cooler-master-haf-700-evo');cache=SceneCache();base=cache.build(spec)
        self.assertEqual(base.metadata['physical_total_fans'],4)
        for style in SIX:
            with self.subTest(style=style):
                scene=cache.build(dict(spec,visual_style=style))
                self.assertTrue(all(a.vertices is b.vertices for a,b in zip(base.meshes,scene.meshes)))
                loop=scene.metadata['cooling']['selected_loop']
                self.assertTrue(loop['connected_reference_loop'],loop['issues'])
                self.assertEqual(len(loop['routes']),3)
                batches=edge_batches(scene.meshes,style,scene.metadata['mesh_style_ids'])
                self.assertTrue(all(len(vertices)//12<=MAX_MESH_EDGES for _,vertices in batches))
                self.assertLessEqual(sum(len(vertices)//12 for _,vertices in batches),MAX_STYLE_EDGES)
        cache.clear()

    def test_actual_profiled_regular_5000d_has_three_complete_routes(self):
        cache=SceneCache();scene=cache.build(self.baked('corsair-5000d-airflow'))
        loop=scene.metadata['cooling']['selected_loop']
        self.assertTrue(loop['connected_reference_loop'],loop['issues'])
        self.assertEqual(len(loop['routes']),3)
        self.assertEqual(sum(m.name=='loop-reference-routed-tube' for m in scene.meshes),3)
        cache.clear()


if __name__=='__main__':unittest.main()
