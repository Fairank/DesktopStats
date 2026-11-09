"""Primary/derived memory dimensions never replace PCB height with total."""
import copy
import json
import math
import unittest
from unittest.mock import patch
from urllib.parse import urlparse

from memory_dimensions052 import enrich,records
from memory_appearance import CATALOG,appearance_for_memory

EXPECTED_HEIGHTS={
    'corsair-cmk16gx4m2b3200c16':33.53,'corsair-cmh32gx5m2b6000c30':44.,
    'corsair-cmt32gx5m2b5600c36':56.,'gskill-f4-3200c16d-16gvkb':42.,
    'gskill-f4-3200c16d-16gtzr':44.,'gskill-f4-3600c18d-16gtrs':44.,
    'gskill-f5-6000j3038f16gx2-fx5':33.,'kingston-kf560c36bbek2-32':34.9,
    'kingston-kf564c32rsk2-32':39.2,'kingston-kvr32n22s8-16':31.25,
    'kingston-kvr32s22s8-16':30.,'teamgroup-ff3d532g6000hc30dc01':46.1,
    'teamgroup-flbd532g6000hc38jdc01':32.7,'adata-ax5u6000c3016g-dclarwh':43.56,
    'adata-ax4u32008g16a-st60':45.93,'corsair-cmk16gx4m2b3200c16w':33.53,
    'corsair-cmh32gx5m2b6000c30w':44.,'corsair-cmt32gx5m2b5600c36w':56.,
    'gskill-f4-3600c16d-16gtrg':44.,'kingston-kf560c36bbeak2-32':42.23,
    'kingston-kf564c32rsak2-32':44.,'kingston-kvr32n22s8k2-32':31.25,
    'teamgroup-ff4d532g6000hc30dc01':46.1,'teamgroup-flrd532g6000hc38jdc01':32.7,
    'adata-ax5u6000c3016g-dclarbk':43.56,'adata-ax5u6000c3016g-clarwh':43.56,
    'adata-ax4u32008g16a-dt60':45.93,
}
BARE_PCB_HEIGHTS={'kingston-kvr32n22s8-16':31.25,'kingston-kvr32n22s8k2-32':31.25,
                  'kingston-kvr32s22s8-16':30.}
DERIVED_IDS={identity for identity in EXPECTED_HEIGHTS if identity.startswith('adata-')}


def module(part,manufacturer='',height=31.):
    return dict(appearance=appearance_for_memory(model=part,manufacturer=manufacturer),height_mm=height)


class MemoryDimensions052Tests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,create=True,side_effect=AssertionError('Pure dimension data only')))

    def test_real_exact_gskill_total_is_not_a_44mm_pcb(self):
        memory=dict(count=1,modules=[module('F4-3200C16D-16GTZR','G.SKILL')])
        original=copy.deepcopy(memory);value=enrich(memory);item=value['modules'][0]
        self.assertEqual(item['appearance']['id'],'gskill-f4-3200c16d-16gtzr')
        self.assertEqual(item['total_height_mm'],44.)
        self.assertEqual(item['total_height_status'],'primary')
        self.assertEqual(item['height_mm'],31.);self.assertEqual(item['height_mm_describes'],'pcb')
        self.assertIsNone(item['pcb_height_mm']);self.assertEqual(item['pcb_height_status'],'unknown')
        self.assertIn('https://www.gskill.com/specification/165/166/1536654268/F4-3200C16D-16GTZR-Specification',item['dimensions_sources'])
        self.assertIn('F4-3200C16D-16GTZR',item['dimensions_model_binding_url'])
        self.assertIn('/faq/',item['total_height_source_url'])
        self.assertEqual(memory,original)

    def test_real_exact_bare_kingston_binds_pcb_and_complete_module_dimensioned_outline(self):
        value=enrich(dict(modules=[module('KVR32N22S8/16','Kingston',height=30.9)]))['modules'][0]
        self.assertEqual(value['height_mm'],30.9)
        self.assertEqual(value['pcb_height_mm'],31.25);self.assertEqual(value['pcb_height_status'],'primary')
        self.assertEqual(value['total_height_mm'],31.25);self.assertEqual(value['total_height_status'],'primary')
        self.assertTrue(value['total_height_source_url'].endswith('/KVR32N22S8_16.pdf'))
        self.assertEqual(value['pcb_height_source_url'],value['total_height_source_url'])
        self.assertEqual(value['pcb_height_tolerance_mm'],.12)
        self.assertEqual(value['total_height_tolerance_mm'],.12)

    def test_all27_exact_primary_bindings_and_one_unverified_crucial_are_accounted_for(self):
        indexed={r['id']:r for r in records()};self.assertEqual(len(CATALOG),28)
        self.assertEqual(set(indexed),set(EXPECTED_HEIGHTS))
        self.assertEqual({r['id'] for r in CATALOG}-set(indexed),{'crucial-cb16gu4800'})
        for row in CATALOG:
            original=module(row['aliases'][0],row['brand'])
            self.assertEqual(original['appearance']['id'],row['id'])
            original.update(total_height_mm=999.,total_height_status='primary',pcb_height_mm=999.)
            result=enrich(dict(modules=[original]))['modules'][0]
            if row['id']=='crucial-cb16gu4800':
                self.assertIsNone(result['total_height_mm']);self.assertEqual(result['total_height_status'],'unknown')
                self.assertIsNone(result['dimensions_model_id'])
            else:
                self.assertEqual(result['total_height_mm'],EXPECTED_HEIGHTS[row['id']])
                self.assertEqual(result['total_height_status'],'derived_nominal' if row['id'] in DERIVED_IDS else 'primary')
                self.assertEqual(result['dimensions_model_id'],row['id'])
                self.assertTrue(result['total_height_source_url'].startswith('https://'))
            self.assertEqual(result['pcb_height_mm'],BARE_PCB_HEIGHTS.get(row['id']))
            self.assertEqual(result['height_mm'],31.)

    def test_confidence_exact_id_and_kind_are_required_not_brand_alias_or_label(self):
        appearances=[dict(id='gskill-f4-3200c16d-16gtzr',confidence='series'),
            dict(id='gskill-f4-3200c16d-16gtzr'),
            dict(id='gskill-f4-3200c16d-16gtzr',confidence='model',kind='gpu'),
            dict(id='F4-3200C16D-16GTZR',confidence='model',kind='memory'),
            dict(id='gskill-f4-3200c16d-16gtzr-revision-unknown',confidence='model'),
            dict(id='gskill-f4-3200c16d-16gtzr'.upper(),confidence='model'),
            dict(label='G.SKILL Trident Z RGB',brand='gskill',confidence='model')]
        for appearance in appearances:
            item=enrich(dict(modules=[dict(appearance=appearance)]))['modules'][0]
            self.assertIsNone(item['total_height_mm']);self.assertIsNone(item['pcb_height_mm'])
            self.assertIsNone(item['dimensions_model_id'])

    def test_deep_copy_mixed_aggregate_and_identity_change_cannot_retain_old_facts(self):
        value=dict(count=2,height_mm=31.,total_height_mm=44.,modules=[
            module('F4-3200C16D-16GTZR','G.SKILL'),module('not-recorded','unknown')],unrelated=dict(values=[1,2]))
        before=copy.deepcopy(value);first=enrich(value)
        self.assertEqual(value,before);self.assertIsNone(first['total_height_mm'])
        self.assertEqual(first['height_mm'],31.);self.assertEqual(first['height_mm_describes'],'pcb')
        first['modules'][0]['appearance']['id']='not-recorded'
        second=enrich(first)
        self.assertIsNone(second['modules'][0]['total_height_mm'])
        first['unrelated']['values'].append(3);self.assertEqual(value['unrelated']['values'],[1,2])
        second['modules'][0]['appearance']['label']='mutated'
        self.assertNotEqual(second['modules'][0]['appearance']['label'],first['modules'][0]['appearance']['label'])

    def test_publisher_axes_are_not_silently_renamed_to_primary_adata_scene_height(self):
        indexed={r['id']:r for r in records()}
        self.assertEqual(len(DERIVED_IDS),5)
        for identity in DERIVED_IDS:
            row=indexed[identity]
            self.assertEqual(row['declared_dimension_order'],'L x W x H')
            self.assertEqual(row['standing_axis_map'],dict(length='publisher_L',height='publisher_W',thickness='publisher_H'))
            self.assertFalse(row['manufacturer_explicit_scene_axis_labels'])
            raw=row['declared_dimensions_mm']
            self.assertEqual(row['total_length_mm'],raw[0]);self.assertEqual(row['total_height_mm'],raw[1])
            self.assertEqual(row['total_thickness_mm'],raw[2])
            self.assertEqual(row['total_height_status'],'derived_nominal')
            self.assertEqual(row['total_thickness_status'],'derived_nominal')
            self.assertIsNone(row['pcb_height_mm']);self.assertIsNone(row['pcb_length_mm'])
            self.assertTrue(row['axis_basis'])

    def test_tolerances_and_maximum_thickness_do_not_become_nominal_or_fit_guarantees(self):
        indexed={r['id']:r for r in records()}
        beast=indexed['kingston-kf560c36bbek2-32']
        self.assertEqual(beast['total_height_tolerance_mm'],.12)
        self.assertGreater(beast['total_height_mm']+beast['total_height_tolerance_mm'],35.)
        rgb=indexed['kingston-kf560c36bbeak2-32']
        self.assertEqual(rgb['total_thickness_tolerance_mm'],.3)
        sodimm=indexed['kingston-kvr32s22s8-16']
        self.assertEqual(sodimm['max_total_thickness_mm'],3.7)
        self.assertIsNone(sodimm['total_thickness_mm']);self.assertEqual(sodimm['pcb_thickness_mm'],1.2)
        for row in indexed.values():
            self.assertFalse(row['dimensions_manufacturing_fit_verified'])
            self.assertIsNone(row['installed_height_above_motherboard_mm']);self.assertIsNone(row['seat_insertion_depth_mm'])
            self.assertIsNone(row['heatspreader_height_mm']);self.assertIsNone(row['diffuser_height_mm'])
            for field in ('total_height_mm','pcb_height_mm','total_length_mm','pcb_length_mm','total_thickness_mm','pcb_thickness_mm'):
                if row[field] is None:continue
                self.assertTrue(math.isfinite(row[field]) and row[field]>0.)
                self.assertTrue(row[field.removesuffix('_mm')+'_source_url'].startswith('https://'))
            for url in row['dimensions_sources']:
                self.assertTrue(urlparse(url).hostname.endswith(('corsair.com','gskill.com','kingston.com','teamgroupinc.com','adata.com')))

    def test_nested_axis_maps_are_detached_and_enrichment_is_idempotent(self):
        original=dict(modules=[module('AX5U6000C3016G-DCLARWH','ADATA') for _ in range(2)])
        result=enrich(original)
        self.assertEqual(result,enrich(result))
        result['modules'][0]['standing_axis_map']['height']='changed'
        self.assertEqual(result['modules'][1]['standing_axis_map']['height'],'publisher_W')
        self.assertNotIn('standing_axis_map',original['modules'][0])
        audit=records();row=next(r for r in audit if r['id']=='adata-ax5u6000c3016g-dclarwh')
        row['standing_axis_map']['height']='changed'
        self.assertEqual(next(r for r in records() if r['id']==row['id'])['standing_axis_map']['height'],'publisher_W')

    def test_audit_rows_are_detached_json_safe_and_unknown_inputs_stay_unverified(self):
        rows=records();self.assertEqual(json.loads(json.dumps(rows))[0]['id'],rows[0]['id'])
        rows[0]['total_height_mm']=500.
        self.assertNotEqual(records()[0]['total_height_mm'],500.)
        for memory in (None,False,[],dict(count=2),dict(modules=[None,False,{},dict(appearance=False)])):
            value=enrich(memory);self.assertEqual(value['height_mm_describes'],'pcb')
            self.assertIsNone(value['total_height_mm']);self.assertEqual(value['total_height_status'],'unknown')


if __name__=='__main__':unittest.main()
