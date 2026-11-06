"""The optional 3D adapter reuses the complete reviewed 2D catalog, with fake I/O."""
import copy
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
os.environ.setdefault("QT_QUICK_BACKEND","software")
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtQml import QQmlEngine
from PySide6.QtWidgets import QApplication

from assembly_profiles import ProfileReader,bake_profiles,bounds,path_polygon
from assembly_spec import build_spec
from hardware_appearance import appearance_for
from stats_config import DEFAULT
from tests.test_hardware_cartoon import all_appearances


class AssemblyProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.native=self.enterContext(patch("ctypes.WinDLL",side_effect=AssertionError("No native calls")))
        self.process=self.enterContext(patch("subprocess.Popen",side_effect=AssertionError("No process")))
        self.engine=QQmlEngine();self.warnings=[]
        self.engine.warnings.connect(lambda rows:self.warnings.extend(row.toString() for row in rows))
        self.reader=ProfileReader(self.engine)

    def tearDown(self):
        self.reader.close();self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents()
        self.assertEqual(self.warnings,[]);self.native.assert_not_called();self.process.assert_not_called()

    def test_all_registered_components_have_reusable_model_profiles(self):
        values=all_appearances();self.assertEqual(len(values),178)
        for value in values:
            with self.subTest(model=value['id']):
                profile=self.reader.read(value)
                if value['kind']=='gpu':
                    if value['style']!='gpu_integrated':
                        self.assertTrue(path_polygon(profile['shell']))
                    self.assertEqual(profile['physical_fan_count'],value['fan_count'])
                    for fan in profile['fans']:
                        self.assertEqual(len(fan['blade_paths']),fan['profile']['blades'] if fan['known'] else 0)
                        for leaf in fan['blade_paths']:
                            self.assertGreaterEqual(len(path_polygon(dict(d=leaf['d'],m=[1,0,0,1,0,0]))),3)
                elif value['kind']=='memory':
                    self.assertTrue(path_polygon(profile['pcb']))
                else:
                    self.assertTrue(path_polygon(profile['package']))
                    self.assertTrue(path_polygon(profile['lid']))

    def test_path_reader_preserves_curves_relative_commands_and_transform(self):
        points=path_polygon(dict(d='M1 2h4v5h-4z',m=[2,0,0,3,10,20]))
        self.assertEqual(bounds(points),(12.0,26.0,8.0,15.0))
        curve=path_polygon(dict(d='M0 0C0 3 4 3 4 0Q2 -2 0 0Z',m=[1,0,0,1,0,0]))
        self.assertGreater(len(curve),8)
        for invalid in ('M0 0A1 1 0 0 1 2 2Z','M0 0Lnan 2Z','M0 0<script>'):
            self.assertEqual(path_polygon(dict(d=invalid,m=[1,0,0,1,0,0])),[])

    def test_actual_illustration_choice_and_physical_dimensions_survive_baking(self):
        config=copy.deepcopy(DEFAULT)
        config['top_bar']['items']=[dict(metric='gpu_usage',prefs=dict(hardware_model='asus-astral-5090'))]
        data=dict(cpu_name='Intel Core i7-13700KF',gpus={'0':dict(gpu_name='NVIDIA GeForce RTX 5090')})
        firmware=dict(state='available',enclosures=[],baseboards=[dict(manufacturer='ASUSTeK COMPUTER INC.',product='ROG STRIX Z790-A GAMING WIFI D4')])
        modules=[dict(manufacturer='G.Skill',part_number='F4-3200C16D-16GTZR',form_factor='dimm')]
        spec=build_spec(data,config,firmware,modules)
        before=copy.deepcopy(spec);baked=bake_profiles(spec,self.engine)
        self.assertEqual(spec,before)
        self.assertEqual(baked['gpu']['appearance']['id'],'asus-astral-5090')
        self.assertEqual(baked['gpu']['length_mm'],357.6)
        self.assertEqual(len(baked['gpu']['fans']),3)
        self.assertEqual(baked['gpu']['physical_fan_count'],4)
        self.assertEqual([f['direction'] for f in baked['gpu']['fans']],[1,-1,1])
        self.assertTrue(all(len(f['blade_polygons'])==7 for f in baked['gpu']['fans']))
        self.assertTrue(baked['cpu']['lid_polygon'])
        self.assertTrue(baked['memory']['pcb_polygon'])
        self.assertFalse(baked['case']['dimensions_verified'])

    def test_vram_item_preserves_the_selected_card_and_manual_cooler(self):
        config=copy.deepcopy(DEFAULT)
        config['top_bar']['items']=[dict(metric='vram_percent',prefs=dict(
            hardware_model='asus-astral-5090',gpu_target='1'))]
        data=dict(gpus={'0':dict(gpu_name='Intel Arc A770'),'1':dict(gpu_name='RTX 5090')})
        spec=build_spec(data,config,dict(state='unavailable'),[])
        self.assertEqual(spec['gpu']['appearance']['id'],'asus-astral-5090')
        self.assertEqual(spec['gpu']['selection_source'],'manual')


if __name__=='__main__':unittest.main()
