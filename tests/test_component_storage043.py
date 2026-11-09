"""Storage product facts, exact identities and lazy manual-reference contracts."""
import ast
import copy
import json
import math
from pathlib import Path
import unittest
from urllib.parse import urlsplit

import component_storage043 as storage
from assembly_config import validate_assembly

ROOT=Path(__file__).resolve().parents[1]


class StorageCatalog043Tests(unittest.TestCase):
    def test_fresh_module_keeps_record_objects_lazy_and_rejects_unknown_without_building(self):
        namespace={}
        exec(compile((ROOT/'component_storage043.py').read_text(encoding='utf-8'),
                     'component_storage043.py','exec'),namespace)
        self.assertIsNone(namespace['_ROWS'])
        for value in (None,False,{},[],123,'990 PRO','../wd-black-sn770m-1tb'):
            self.assertIsNone(namespace['get_storage'](value))
        self.assertIsNone(namespace['_ROWS'])
        first=namespace['records']()
        self.assertIs(first,namespace['records']())
        self.assertEqual(len(first),24)

    def test_exact_inventory_covers_interfaces_lengths_and_brands_without_counting_styles(self):
        rows=storage.records();coverage=storage.coverage()
        self.assertEqual(len(rows),len(storage.IDS))
        self.assertEqual(len({r['id'] for r in rows}),24)
        self.assertGreaterEqual(coverage['brands'],8)
        self.assertEqual((coverage['nvme'],coverage['sata_ssd'],coverage['hdd']),(17,4,3))
        self.assertEqual({r['m2_size'] for r in rows if r['form_factor']=='m2_nvme'},
                         {'2230','2242','2280','22110'})
        self.assertEqual(coverage['structure_groups'],12)
        self.assertLess(coverage['structure_groups'],coverage['products'])

    def test_immutable_external_lookup_and_no_alias_or_installed_device_inference(self):
        first=storage.get_storage('transcend-mte452t-512gb')
        before=copy.deepcopy(first)
        first['dimensions_mm']['height']=999
        first['sources'].append('https://invalid.example/')
        self.assertEqual(storage.get_storage(before['id']),before)
        self.assertTrue(all(r['selection_source']=='manual' for r in storage.records()))

    def test_dimensions_and_sources_are_finite_json_facts_not_executable_content(self):
        allowed=('sandisk.com','kingston.com','sabrent.com','transcend-info.com','samsung.com',
                 'micron.com','corsair.com','adata.com','kioxia.com','seagate.com',
                 'westerndigital.com','toshiba-storage.com','teamgroupinc.com')
        for row in storage.records():
            with self.subTest(model=row['id']):
                self.assertEqual(row['category'],'storage')
                self.assertTrue(row['brand'] and row['series'] and row['model_number'])
                self.assertGreater(row['capacity_gb'],0)
                self.assertTrue(row['dimensions_verified'])
                self.assertEqual(set(row['dimensions_mm']),{'length','width','height'})
                self.assertTrue(all(type(n) in (int,float) and math.isfinite(n) and 0<n<1000
                                    for n in row['dimensions_mm'].values()))
                self.assertTrue(row['dimensions_basis'])
                self.assertTrue(row['sources'])
                for url in row['sources']+row.get('appearance_sources',[]):
                    parsed=urlsplit(url)
                    self.assertEqual(parsed.scheme,'https')
                    self.assertTrue(any(parsed.hostname==d or parsed.hostname.endswith('.'+d) for d in allowed),url)
                self.assertEqual(json.loads(json.dumps(row)),row)

    def test_short_m2_and_industrial_bm_do_not_inherit_wrong_length_key_or_interface(self):
        short=storage.get_storage('kingston-nv3-2230-1tb')
        self.assertEqual(short['model_number'],'SNV3SM3/1T0')
        self.assertEqual(short['dimensions_mm']['length'],30)
        self.assertEqual(short['m2_size'],'2230')
        single=storage.get_storage('transcend-mte400s-512gb')
        double=storage.get_storage('transcend-mte452t-512gb')
        self.assertEqual(single['m2_key'],'m')
        self.assertEqual(double['m2_key'],'b_m')
        self.assertTrue(single['single_sided']);self.assertFalse(double['single_sided'])
        self.assertNotEqual(single['structure_group'],double['structure_group'])
        self.assertIn('x2',double['interface_detail'])
        self.assertEqual(double['dimensions_mm']['height'],3.58)
        long=storage.get_storage('samsung-983-dct-960gb')
        self.assertEqual(long['m2_size'],'22110')
        self.assertEqual(long['model_number'],'MZ-1LB960NE')
        self.assertEqual(long['dimensions_mm']['length'],110.2)

    def test_capacity_specific_heatsink_envelopes_and_axis_are_preserved(self):
        heatsinks=[r for r in storage.records() if r['factory_heatsink']]
        self.assertEqual(len(heatsinks),5)
        self.assertEqual(len({r['heatsink_style'] for r in heatsinks}),5)
        self.assertTrue(all(r['dimensions_mm']['height']>8 and r['dimensions_mm']['width']>22 for r in heatsinks))
        firecuda=storage.get_storage('seagate-firecuda-530-heatsink-2tb')
        self.assertEqual(firecuda['dimensions_mm']['height'],10.39)
        self.assertEqual(firecuda['heatsink_style'],'smooth_low')
        self.assertEqual(firecuda['fin_axis'],'none')
        sn850=storage.get_storage('wd-black-sn850x-heatsink-2tb')
        self.assertEqual(sn850['fin_axis'],'width')
        self.assertAlmostEqual(sn850['dimensions_mm']['height'],8.90+.40)
        self.assertIn('1/2TB',sn850['dimensions_basis'])
        self.assertEqual(storage.get_storage('corsair-mp600-pro-lpx-2tb')['fin_axis'],'length')

    def test_capacity_sku_and_interface_pairs_do_not_mix_related_bare_or_retail_models(self):
        # These differing capacity units and suffixes are source facts, not
        # interchangeable label variants from a shared product shell.
        expected={
            'kingston-nv3-2230-1tb':('SNV3SM3/1T0',1000,'PCIe 4.0 x4 NVMe'),
            'transcend-mte452t-512gb':('TS512GMTE452T',512,'PCIe 3.0 x2 NVMe 1.3'),
            'samsung-983-dct-960gb':('MZ-1LB960NE',960,'PCIe 3.0 x4 NVMe 1.2b'),
            'kingston-kc600-1024gb':('SKC600/1024G',1024,'SATA III 6 Gb/s'),
            'seagate-firecuda-530-heatsink-2tb':('ZP2000GM30023',2000,'PCIe 4.0 x4 NVMe 1.4'),
            'crucial-t705-heatsink-2tb':('CT2000T705SSD5',2000,'PCIe 5.0 x4 NVMe'),
        }
        for identity,facts in expected.items():
            row=storage.get_storage(identity)
            self.assertEqual((row['model_number'],row['capacity_gb'],row['interface_detail']),facts)
        for row in storage.records():
            if row['form_factor']=='m2_nvme':
                self.assertIn(row['m2_key'],('m','b_m'))
                self.assertTrue(row['m2_key_verified'])
                if row['m2_key']=='b_m':self.assertIn('x2',row['interface_detail'])

    def test_unseen_t705_exterior_and_all_internal_layouts_remain_explicitly_schematic(self):
        t705=storage.get_storage('crucial-t705-heatsink-2tb')
        self.assertTrue(t705['appearance_unverified'])
        self.assertEqual(t705['heatsink_style'],'reference')
        self.assertEqual(t705['fin_axis'],'none')
        self.assertAlmostEqual(t705['dimensions_mm']['height'],.83*25.4)
        for row in storage.records():
            self.assertTrue(row['layout_schematic'] and row['package_layout_schematic'])
            self.assertFalse(row['controller_layout_verified'] or row['nand_layout_verified'])
            self.assertFalse(row['pcb_routing_verified'] or row['screw_positions_verified'])
            self.assertIsNone(row['fin_count'])
            self.assertFalse(row['fin_geometry_verified'])
            self.assertEqual(row['palette_accuracy'],'illustrative_not_measured_factory_paint')

    def test_closed_hdd_enclosures_never_claim_live_rpm_or_visible_platters(self):
        rows=[r for r in storage.records() if r['form_factor']=='sata_35_hdd']
        self.assertEqual({r['model_mark'] for r in rows},{'BARRACUDA','WD BLACK','N300'})
        self.assertEqual({r['capacity_gb'] for r in rows},{6000,8000})
        for row in rows:
            self.assertTrue(row['sealed_cover'])
            self.assertFalse(row['internal_platters_visible'])
            self.assertFalse(row['spindle_rpm_is_live'])
            self.assertNotIn('live_rpm',row)
            self.assertNotIn('fan_count',row)

    def test_existing_manual_selection_contract_accepts_ids_and_preserves_old_defaults(self):
        for begin in (0,8,16):
            chosen=[dict(model_id=i,count=1) for i in storage.IDS[begin:begin+8]]
            self.assertEqual(validate_assembly(dict(storage=chosen))['storage'],chosen)
        self.assertEqual(validate_assembly()['storage'],[])
        module=ast.parse((ROOT/'component_storage043.py').read_text(encoding='utf-8'))
        imports=[n.module for n in ast.walk(module) if isinstance(n,ast.ImportFrom)]
        self.assertEqual(imports,['copy'])
        self.assertFalse(any(isinstance(n,ast.Import) for n in ast.walk(module)))


if __name__=='__main__':unittest.main()
