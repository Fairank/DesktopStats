"""Exact manual radiator facts and safe unknowns; no Qt or live hardware."""
import ast
import json
import math
from pathlib import Path
import unittest

import liquid_cooling_catalog044 as catalog


class RadiatorCatalogTests(unittest.TestCase):
    def test_fresh_import_and_invalid_lookup_do_not_construct_the_directory(self):
        source=Path(catalog.__file__).read_text(encoding='utf-8')
        isolated={}
        exec(compile(source,catalog.__file__,'exec'),isolated)
        self.assertIsNone(isolated['_ROWS'])
        for bad in (None,False,[],{},1,'../radiator','unknown'):
            self.assertIsNone(isolated['get_radiator'](bad))
            self.assertIsNone(isolated['_ROWS'])
        rows=isolated['records']()
        self.assertIs(rows,isolated['records']())
        imports=[n for n in ast.walk(ast.parse(source)) if isinstance(n,(ast.Import,ast.ImportFrom))]
        self.assertEqual([(n.module,tuple(a.name for a in n.names)) for n in imports],[('copy',('deepcopy',))])

    def test_twenty_four_exact_products_eight_brands_not_twenty_four_independent_shells(self):
        rows=catalog.records()
        self.assertEqual(len(rows),24)
        self.assertEqual(len({r['id'] for r in rows}),24)
        self.assertEqual(set(catalog.IDS),{r['id'] for r in rows})
        self.assertEqual(len({r['brand'] for r in rows}),8)
        self.assertEqual(len({r['shell_family'] for r in rows}),11)
        self.assertEqual({r['fan_size_mm']*r['fan_count'] for r in rows},{240,280,360,420})
        self.assertEqual(catalog.coverage()['products'],24)
        self.assertEqual(catalog.coverage()['exact_port_positions'],0)

    def test_all_product_envelopes_are_finite_source_linked_and_manual(self):
        for row in catalog.records():
            with self.subTest(model=row['id']):
                json.dumps(row,allow_nan=False)
                self.assertTrue(row['dimensions_verified'])
                self.assertEqual(set(row['dimensions_mm']),{'length','width','thickness'})
                self.assertTrue(all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in row['dimensions_mm'].values()))
                self.assertTrue(row['model_number']);self.assertTrue(row['dimensions_basis'])
                self.assertTrue(row['sources']);self.assertTrue(all(s.startswith('https://') for s in row['sources']))
                self.assertEqual(row['category'],'radiator');self.assertEqual(row['loop_type'],'custom')
                self.assertEqual(row['selection_source'],'manual')
                self.assertFalse(row['aio_replacement_verified'])
                self.assertFalse(row['installed_hardware_inferred'])
                self.assertFalse(row['live_flow_available']);self.assertFalse(row['live_temperature_available'])

    def test_lookup_is_detached_including_nested_ports_and_dimensions(self):
        row=catalog.get_radiator('corsair-xr5-240')
        row['dimensions_mm']['width']=1
        row['ports'][0]['position_normalized'][0]=42
        row['sources'].append('bad')
        original=catalog.get_radiator('corsair-xr5-240')
        self.assertEqual(original['dimensions_mm']['width'],120)
        self.assertLessEqual(abs(original['ports'][0]['position_normalized'][0]),.5)
        self.assertNotIn('bad',original['sources'])

    def test_name_core_thickness_and_old_reseller_envelopes_do_not_replace_exact_specs(self):
        expected={
            'corsair-xr7-360':(395,120,55),
            'alphacool-st30-v2-360':(394.5,124,30),
            'alphacool-xt45-v2-280':(316.5,143,45.5),
            'alphacool-ut60-360':(397,124,60),
            'xspc-tx240':(278,125,20.5),
            'xspc-ex280':(320.5,143,36),
            'xspc-rx360-v3':(398.5,130,56),
            'hardwarelabs-nemesis-240gts':(278,133,31.3),
            'hardwarelabs-nemesis-360gtx':(398,133,55.7),
            'hardwarelabs-nemesis-420gts':(452,153,31.3),
            'thermaltake-pacific-cld240':(285.4,119,40),
        }
        for identity,dimensions in expected.items():
            row=catalog.get_radiator(identity)
            self.assertEqual(tuple(row['dimensions_mm'][k] for k in ('length','width','thickness')),dimensions,identity)
        self.assertEqual(catalog.get_radiator('alphacool-ut60-360')['model_number'],'14174')
        self.assertNotEqual(catalog.get_radiator('xspc-rx360-v3')['model_number'],'RX360 V2')

    def test_total_ports_active_connections_and_observed_partial_geometry_are_distinct(self):
        for row in catalog.records():
            self.assertEqual(row['active_port_count'],2)
            self.assertGreaterEqual(row['ports_count'],2)
            self.assertTrue(row['port_thread_verified'])
            self.assertIn(row['port_layout'],catalog.PORT_LAYOUTS)
            self.assertFalse(row['default_caps_installed'])
            self.assertLessEqual(len(row['ports']),row['ports_count'])
            if row['ports_geometry_complete']:self.assertEqual(len(row['ports']),row['ports_count'])
            self.assertFalse(row['port_positions_verified'])
            for p in row['ports']:
                self.assertIn(p['face'],('front','rear','left','right','end'))
                self.assertTrue(all(type(n) in (int,float) and math.isfinite(n) and abs(n)<=.5 for n in p['position_normalized']))
                self.assertFalse(p['positions_verified'])
                self.assertTrue(p['source'].startswith('https://'))
        self.assertEqual(catalog.get_radiator('ek-quantum-surface-p360m')['ports_count'],5)
        self.assertEqual(catalog.get_radiator('ek-quantum-surface-p360m')['ports'],[])
        partial=catalog.get_radiator('alphacool-ut60-360')
        self.assertEqual(partial['ports_count'],6);self.assertEqual(len(partial['ports']),4)
        self.assertFalse(partial['ports_geometry_complete'])
        rx=catalog.get_radiator('xspc-rx360-v3')
        self.assertEqual(rx['ports_count'],4)
        self.assertEqual([p['face'] for p in rx['ports']],['front','front','end','end'])

    def test_unknown_hole_positions_and_density_never_become_precise_manufacturing_geometry(self):
        for row in catalog.records():
            self.assertIsNone(row['fin_count'])
            self.assertTrue(row['fin_geometry_is_sampling'])
            self.assertFalse(row['shell_geometry_verified'])
            self.assertFalse(row['mounting_positions_verified'])
            if row['fan_mount_pitch_verified']:
                self.assertGreater(row['fan_mount_pitch_mm'],0)
                self.assertTrue(row['mount_dimensions_source'].startswith('https://'))
            else:self.assertIsNone(row['fan_mount_pitch_mm'])
            if row['fpi_verified']:self.assertGreater(row['fpi'],0)
            else:self.assertIsNone(row['fpi'])
        self.assertEqual(catalog.get_radiator('xspc-ex280')['fan_mount_pitch_mm'],125)
        self.assertIsNone(catalog.get_radiator('corsair-xr5-240')['fan_mount_pitch_mm'])
        for identity in ('hardwarelabs-nemesis-240gts','hardwarelabs-nemesis-360gtx','hardwarelabs-nemesis-420gts'):
            self.assertEqual(catalog.get_radiator(identity)['ports'],[])

    def test_radical_fin_metal_is_separate_from_coolant_contact_materials_and_installed_fans(self):
        for identity in catalog.IDS[-3:]:
            row=catalog.get_radiator(identity)
            self.assertEqual(row['materials']['fins'],'aluminium')
            self.assertEqual(row['materials']['coolant_tubes'],'copper')
            self.assertEqual(row['materials']['terminal'],'Delrin')
            self.assertFalse(row['fan_count_is_installed'])
            self.assertEqual(row['fan_mount_capacity_per_side'],row['fan_count'])
            self.assertNotIn('fan_rpm',row)
            self.assertIn('black_delrin_terminal',row['shell_features'])


if __name__=='__main__':unittest.main()
