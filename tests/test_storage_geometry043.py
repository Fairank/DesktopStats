"""Product storage envelopes, distinct heatsinks and documented mount lengths."""
import unittest
from unittest.mock import patch

from assembly_auxiliary import add_auxiliary
from assembly_geometry import model_mark
from assembly_style import apply_model_styles
from component_catalog import CATALOG,get_component
from tests.test_assembly_auxiliary import anchors
from top_bar_config import HARDWARE_ICON_STYLES


class StorageDetailTests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,side_effect=AssertionError('Static references only')))

    def build(self,identity,mounts=None):
        return add_auxiliary(dict(auxiliary=dict(storage=[dict(model_id=identity,count=1)])),mounts or anchors())

    def test_each_factory_heatsink_is_separate_from_the_schematic_packages_and_style_invariant(self):
        rows=[r for r in CATALOG if r.get('factory_heatsink')]
        self.assertGreaterEqual(len(rows),4)
        for row in rows:
            for level in ('eco','balanced','close'):
                spec=dict(auxiliary=dict(storage=[dict(model_id=row['id'],count=1)]))
                meshes,meta=add_auxiliary(spec,anchors(),level)
                self.assertEqual(meta['device_counts']['storage'],1)
                packages=next(m for m in meshes if m.name.endswith('-m2-reference-packages-controller'))
                self.assertLessEqual(max(packages.vertices[0::6])-min(packages.vertices[0::6]),1.51)
                pcb=next(m for m in meshes if m.name.endswith('-m2-pcb'))
                self.assertAlmostEqual(max(pcb.vertices[1::6])-min(pcb.vertices[1::6]),22.)
                screw=next(m for m in meshes if m.name.endswith('-m2-fixing-screw'))
                self.assertAlmostEqual(pcb.position[0]-screw.position[0],.9)
                self.assertTrue(any(m.name.endswith('-m2-factory-heatsink-base') for m in meshes))
                self.assertEqual(any(m.name.endswith('-m2-smooth-heatsink-shell') for m in meshes),row['heatsink_style']=='smooth_low')
                self.assertFalse(meta['devices'][0]['heatsink_clearance_verified'])
                for style in HARDWARE_ICON_STYLES:
                    result,_=apply_model_styles(meshes,style,{},(400,600,650),{'front':'open'})
                    self.assertEqual(len(meshes),len(result))
                    self.assertTrue(all(a.vertices is b.vertices for a,b in zip(meshes,result)))

    def test_m2_selects_supported_length_and_does_not_consume_incompatible_slots(self):
        short=next(r for r in CATALOG if r.get('m2_size')=='2230')
        mounts=anchors();mounts['model']={'id':'test-board'}
        mounts['connectors']['m2'][0]['allowed_lengths_mm']=(30,42)
        mounts['connectors']['m2'][1]['allowed_lengths_mm']=(80,)
        spec=dict(auxiliary=dict(storage=[dict(model_id='samsung-990-pro-2tb',count=1),dict(model_id=short['id'],count=1)]))
        meshes,meta=add_auxiliary(spec,mounts)
        self.assertEqual(meta['device_counts']['storage'],2)
        pcbs=[m for m in meshes if m.name.endswith('-m2-pcb')]
        self.assertGreater(pcbs[0].position[0],132.)
        self.assertLess(pcbs[1].position[0],130.)
        self.assertTrue(all(r['m2_length_supported'] for r in meta['devices']))
        long=next(r for r in CATALOG if r.get('m2_size')=='22110')
        _,rejected=self.build(long['id'],mounts)
        self.assertEqual(rejected['device_counts']['storage'],0)
        self.assertEqual(rejected['rejected'][0]['reason'],'no_supported_m2_length')
        self.assertFalse(meta['devices'][0]['electrical_compatibility_verified'])

    def test_hdd_markings_use_selected_product_and_capacity(self):
        rows=[r for r in CATALOG if r['form_factor']=='sata_35_hdd']
        self.assertGreaterEqual(len(rows),4)
        for row in rows:
            with patch('assembly_auxiliary.model_mark',wraps=model_mark) as marks:
                meshes,meta=self.build(row['id'])
                text=[call.args[0] for call in marks.call_args_list]
            self.assertIn(row['model_mark'],text)
            capacity=str(row['capacity_gb']//1000)+'TB' if row['capacity_gb']%1000==0 else str(row['capacity_gb'])+'GB'
            self.assertIn(capacity,text)
            self.assertEqual(meta['devices'][0]['model_id'],row['id'])
            self.assertIsNone(meta['devices'][0]['live_activity'])
            if row['id'] in ('seagate-barracuda-st8000dm004','toshiba-n300-hdwg480uzsva'):
                mark=next(m for m in meshes if m.name.endswith('-hdd-label-model'))
                self.assertLess(max(mark.color[:3]),.2)


if __name__=='__main__':unittest.main()
