"""Offline CPU source/catalog contracts; never query a device or installed pack."""
import copy
import importlib
import json
import unittest
from collections import Counter
from unittest.mock import patch
from urllib.parse import urlsplit

import cpu_catalog as catalog
import hardware_appearance as appearance


class CpuCatalogTests(unittest.TestCase):
    def test_named_coverage_sources_and_detached_json_records(self):
        self.assertEqual(len(catalog.MODELS), 75)
        self.assertEqual(Counter(row['brand'] for row in catalog.MODELS), {'intel': 34, 'amd': 41})
        self.assertEqual(len({row['id'] for row in catalog.MODELS}), 75)
        self.assertEqual({row['package_family'] for row in catalog.MODELS}, catalog.PACKAGE_IDS)
        self.assertEqual({row['socket'] for row in catalog.MODELS}, {
            'LGA1156','LGA1155','LGA1150','LGA1151','LGA1200','LGA1700','LGA1851',
            'LGA2011','LGA2066','AM4','AM5','sTR4','sTRX4','sWRX8','sTR5'})
        for row in catalog.MODELS:
            with self.subTest(identity=row['id']):
                self.assertEqual(row['identity_status'], 'primary_verified')
                self.assertEqual(row['socket_status'], 'primary_verified')
                self.assertEqual(row['market_coverage'], 'named_sku_only')
                self.assertEqual(row['license'], 'PolyForm-Noncommercial-1.0.0')
                self.assertIn(row['source_url'], row['sources'])
                self.assertTrue(row['aliases'])
                for url in row['sources']:
                    parsed=urlsplit(url)
                    self.assertEqual(parsed.scheme, 'https')
                    self.assertIn(parsed.hostname, ('www.intel.com','www.amd.com','community.amd.com'))
                self.assertEqual(json.loads(json.dumps(row))['id'], row['id'])

    def test_package_dimensions_have_independent_primary_evidence(self):
        expected={'intel-13700kf':(37.5,45,'LGA1700'), 'intel-g4560':(37.5,37.5,'LGA1151'),
                  'intel-g5905':(37.5,37.5,'LGA1200'), 'intel-ultra-285k':(37.5,45,'LGA1851'),
                  'intel-3930k':(45,52.5,'LGA2011'), 'amd-9950x':(40,40,'AM5')}
        for identity,(width,length,socket) in expected.items():
            row=catalog.get_model(identity); package=row['cpu_package']
            self.assertEqual((package['width_mm'],package['length_mm'],package['socket']), (width,length,socket))
            self.assertEqual(package['dimensions_status'], 'primary_verified')
            self.assertTrue(row['dimensions_source'])
        # Neither socket names nor a secondary-site measurement become CAD facts.
        for row in catalog.MODELS:
            package=row['cpu_package']
            if row['socket'] in ('AM4','sTR4','sTRX4','sWRX8','sTR5') or row['id'] in ('intel-870','intel-10980xe'):
                self.assertIsNone(package['width_mm']); self.assertIsNone(package['length_mm'])
                self.assertEqual(package['dimensions_status'], 'unverified_reference')
                self.assertEqual(package['status'], 'unverified_reference')
            self.assertIsNone(package['substrate_mm'])
            self.assertIsNone(row['dimensions_mm']['height'])
            self.assertFalse(row['exact_ihs_dimensions_verified'])
            self.assertFalse(package['topology_map_verified'])
            self.assertFalse(package['internal_layout_verified'])
            self.assertFalse(row['cooling_verified'])
            self.assertFalse(package['cooler_inferred'])
        self.assertEqual(catalog.get_model('amd-9950x')['mechanical_source_scope'], 'socket_family')
        self.assertEqual(catalog.get_model('intel-13700kf')['mechanical_source_scope'], 'sku')
        self.assertEqual(sum(row['dimensions_status']=='primary_verified' for row in catalog.MODELS), 42)

    def test_interface_facts_are_not_fabricated_pin_maps(self):
        for identity,kind,count in (('intel-13700kf','lga',1700),('amd-5600','pga',1331),('amd-9950x','lga',1718)):
            row=catalog.get_model(identity)
            self.assertEqual((row['topology']['kind'],row['topology']['contact_count']), (kind,count))
            self.assertFalse(row['topology']['map_verified'])
            self.assertEqual(row['topology']['count_status'], 'primary_verified')
        for identity in ('intel-870','intel-10980xe','amd-threadripper-3990x','amd-threadripper-pro-9995wx'):
            row=catalog.get_model(identity)
            self.assertIsNone(row['topology']['contact_count'])
            self.assertEqual(row['topology']['count_status'], 'unverified_reference')
        self.assertEqual(catalog.get_model('amd-threadripper-3990x')['topology']['status'], 'unverified_reference')

    def test_package_identity_guard_and_copy_boundaries(self):
        for row in catalog.MODELS:
            value=dict(id=row['id'],kind='cpu',vendor=row['brand'],style=row['style'],confidence='model')
            original=copy.deepcopy(value)
            package=catalog.by_appearance(value)
            self.assertEqual(package['model_id'],row['id'])
            self.assertEqual(value,original)
            package['width_mm']=-999
            self.assertNotEqual(catalog.by_appearance(value)['width_mm'],-999)
            for mutation in ({'vendor':'unknown'},{'style':'invalid'},{'kind':'gpu'},{'confidence':'brand'},{'id':'not-reviewed'}):
                self.assertEqual(catalog.by_appearance(dict(value,**mutation)),{},(row['id'],mutation))
        record=catalog.get_model('intel-13700kf')
        record['cpu_package']['source_urls']=('invalid',)
        record['dimensions_mm']['width']=-999
        self.assertNotEqual(catalog.get_model('intel-13700kf'),record)
        for invalid in (None,True,[],{},42,'','INTEL-13700KF','intel-13700hx'):
            self.assertIsNone(catalog.get_model(invalid))
        for invalid in (None,True,[],42,{'id':[]},{'id':'intel-13700hx'}):
            self.assertEqual(catalog.by_appearance(invalid),{})

    def test_shared_families_and_bounded_labels_are_explicit(self):
        families={}
        for row in catalog.MODELS:
            package=row['cpu_package']
            self.assertRegex(package['label_ascii'], r'^[A-Z0-9 -]{1,28}$')
            self.assertTrue(package['label_ascii'].endswith(row['label'].rsplit(' ',1)[-1].upper()))
            self.assertEqual(row['surface_method'], 'original_shared_family_reference')
            families.setdefault(package['id'],set()).add((package['ihs_kind'],package['notch_profile'],row['style']))
        self.assertEqual(len(families),7)
        self.assertTrue(all(len(values)==1 for values in families.values()))
        self.assertEqual(catalog.get_model('amd-5800x')['cpu_package']['id'],catalog.get_model('amd-5600')['cpu_package']['id'])
        self.assertNotEqual(catalog.get_model('amd-5800x')['cpu_package']['ihs_kind'],catalog.get_model('amd-9950x')['cpu_package']['ihs_kind'])

    def test_extension_rows_keep_existing_seeds_and_exact_matching(self):
        rows=catalog.extension_rows()
        self.assertEqual(len(rows),72)
        self.assertFalse(catalog.SEED_IDS & {row[0] for row in rows})
        self.assertEqual(Counter(row[2] for row in rows),{'intel':33,'amd':39})
        self.assertTrue(all(len(row)==10 and row[1]=='cpu' and row[6] is None for row in rows))
        aliases={}
        for row in rows:
            for alias in row[-1]:
                normalized=appearance._text(alias)
                self.assertNotIn(normalized,aliases)
                aliases[normalized]=row[0]
        # Exercise the existing resolver in-memory, never read installed packs.
        combined=appearance.CATALOG+rows
        models=tuple((row,tuple(appearance._text(alias) for alias in row[-1])) for row in combined)
        with patch.object(appearance,'_MODELS',models):
            for row in catalog.MODELS:
                for alias in row['aliases']:
                    result=dict(zip(appearance._FIELDS,appearance._resolve.__wrapped__('cpu',alias,'','')))
                    self.assertEqual((result['id'],result['confidence']),(row['id'],'model'),alias)
            for label in ('Intel Core i7-13700HX','Intel Core i7-13700KF2','AMD Ryzen 7 5800X3D2',
                          'AMD Ryzen Threadripper PRO 5995WX2','AMD Ryzen 9 9950HX',
                          'Intel Core Ultra 9 285HX','AMD Ryzen 7 5800X mobile'):
                result=dict(zip(appearance._FIELDS,appearance._resolve.__wrapped__('cpu',label,'','')))
                self.assertNotEqual(result['confidence'],'model',label)
            for label,identity in (('Intel(R) Pentium(R) CPU G4560 @ 3.50GHz','intel-g4560'),
                                   ('Intel(R) Celeron(R) CPU G5905 @ 3.50GHz','intel-g5905'),
                                   ('AMD Ryzen 5 5600 6-Core Processor','amd-5600')):
                result=dict(zip(appearance._FIELDS,appearance._resolve.__wrapped__('cpu',label,'','')))
                self.assertEqual(result['id'],identity)

    def test_import_and_public_functions_do_not_start_devices_or_io(self):
        forbidden=AssertionError('source catalog must remain pure offline data')
        names=('ctypes.WinDLL','subprocess.Popen','threading.Thread.start','socket.create_connection',
               'builtins.open','pathlib.Path.read_text','pathlib.Path.read_bytes')
        with __import__('contextlib').ExitStack() as stack:
            for name in names: stack.enter_context(patch(name,side_effect=forbidden))
            module=importlib.reload(catalog)
            self.assertEqual(len(module.extension_rows()),72)
            self.assertTrue(module.by_appearance({'id':'amd-9950x'}))
            self.assertIsNone(module.get_model('unreviewed'))


if __name__=='__main__':
    unittest.main()
