"""Real optional inventories resolve safely and never inherit another CPU's data."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hardware_packs import PackStore, make_pack
from tools.export_hardware_packs import pack_models


class HardwarePackIntegrationTests(unittest.TestCase):
    def test_every_exported_sku_resolves_and_uses_its_own_package_in_every_style(self):
        import hardware_packs
        from hardware_appearance import appearance_for
        from assembly_cpu import build_cpu_meshes
        from assembly_style import apply_model_styles
        from top_bar_config import HARDWARE_ICON_STYLES
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store=PackStore(root/'installed')
            models=pack_models()
            for vendor,rows in models.items():
                source=root/(vendor+'.dspack');source.write_bytes(make_pack('cpu-'+vendor, vendor, rows));store.install(source)
            with patch.object(hardware_packs,'_store',store):
                for rows in models.values():
                    for row in rows:
                        for alias in row['aliases']:
                            appearance=appearance_for('cpu',alias)
                            self.assertEqual(appearance['id'],row['id'],alias)
                            self.assertEqual(appearance['cpu_package']['model_id'],row['id'])
                        meshes,meta=build_cpu_meshes(dict(appearance=appearance),level='eco')
                        self.assertTrue(meta['available'],row['id'])
                        self.assertFalse(meta['internal_layout_verified'])
                        if row['cpu_package']['width_mm'] is None:self.assertFalse(meta['dimensions_verified'])
                        for style in HARDWARE_ICON_STYLES:
                            styled,_=apply_model_styles(meshes,style,{},(80.,80.,80.),{'front':'open'})
                            self.assertEqual([m.vertices for m in styled[:len(meshes)]],[m.vertices for m in meshes])
                self.assertLessEqual(store.memory_status()['selected_records'],8)

    def test_import_remove_updates_choices_and_reference_cpu_never_binds_installed_readings(self):
        import hardware_packs
        from assembly_parts import choices
        from assembly_spec import build_spec
        from stats_config import DEFAULT
        from hardware_appearance import appearance_for
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store=PackStore(root/'installed');rows=pack_models()['amd']
            source=root/'amd.dspack';source.write_bytes(make_pack('cpu-amd','AMD',rows))
            with patch.object(hardware_packs,'_store',store):
                before=choices();store.install(source);selected=rows[-1]
                self.assertEqual(len(choices()['cpus'])-len(before['cpus']),len(rows))
                config=copy.deepcopy(DEFAULT);config['assembly']['cpu_model']=selected['id']
                spec=build_spec(dict(cpu_name='Intel Core i7-13700KF',cpu_temp=67),config,dict(state='unavailable'),[])
                self.assertEqual(spec['cpu']['appearance']['id'],selected['id'])
                self.assertFalse(spec['cpu']['telemetry_bound'])
                self.assertEqual(spec['cpu']['detected_label'],'Intel Core i7-13700KF')
                store.remove('cpu-amd')
                self.assertEqual(choices()['cpus'],before['cpus'])
                self.assertNotEqual(appearance_for('cpu',selected['aliases'][0])['confidence'],'model')
                recovered=build_spec(dict(cpu_name='Intel Core i7-13700KF'),config,dict(state='unavailable'),[])
                self.assertEqual(recovered['cpu']['appearance']['id'],'intel-13700kf')
                self.assertTrue(recovered['cpu']['telemetry_bound'])


if __name__=='__main__':unittest.main()
