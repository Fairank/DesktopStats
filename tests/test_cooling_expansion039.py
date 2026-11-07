"""0.39 source/fidelity contracts; pure data, no Qt, sensors or app lifecycle."""
import hashlib
import json
import unittest
from urllib.parse import urlparse

import cooling_catalog as catalog


COOLERS=(
    'noctua-nh-p1','scythe-fuma3','scythe-mugen6','scythe-bigshuriken3-revb',
    'arctic-freezer36','thermalright-axp120-x67','thermalright-si100','deepcool-an600',
    'zalman-cnps10x-performa-black','alphacool-core-ocean-t38-360',
    'ek-nucleus-cr360-lux-drgb','tryx-panorama-se360',
)
FANS=(
    'noctua-nf-a12x15-pwm','arctic-p12-max','arctic-p12-slim-pwm-pst',
    'scythe-kaze-flex-ii120','scythe-kaze-flex-ii120-slim','lian-li-uni-tllcd120',
    'phanteks-d30-120-reverse','bequiet-light-wings120-hs','silverstone-ap183',
    'xpg-vento-pro120-pwm','fractal-prisma-al18-pwm','coolermaster-mobius120-oc',
    'thermalright-tlb12-extrem-lcp','thermaltake-ct120','ek-loop-fpt120-drgb',
    'alphacool-rise-aurora120',
)
OFFICIAL_HOSTS={
    'www.noctua.at','www.arctic.de','www.scytheus.com','www.scythe.co.jp',
    'www.thermalright.com','global.deepcool.com','www.zalman.com',
    'www.alphacool.com','shop.alphacool.com','www.ekwb.com','www.tryxzone.com',
    'lian-li.com','phanteks.com','www.bequiet.com','silverstone.en.taiwantrade.com',
    'www.xpg.com','www.fractal-design.com','www.coolermaster.com','thermaltake.com',
}


class CoolingExpansion039Tests(unittest.TestCase):
    def test_previous_eighty_records_are_byte_equivalent_as_canonical_data(self):
        """The additions must not silently reclassify older product records."""
        old={'coolers':[catalog.get_cooler(c['id']) for c in catalog.choices_coolers()[:42]],
             'fans':[catalog.get_fan(c['id']) for c in catalog.choices_fans()[:38]]}
        serial=json.dumps(old,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
        self.assertEqual(hashlib.sha256(serial).hexdigest(),
                         '5b242023e84617c860121e866040800ed0cdf3125d3605dc3fdc3dd720c87351')

    def test_added_products_are_distinct_and_primary_sourced(self):
        self.assertEqual(tuple(c['id'] for c in catalog.choices_coolers()[42:54]),COOLERS)
        self.assertEqual(tuple(c['id'] for c in catalog.choices_fans()[38:54]),FANS)
        for getter,ids in ((catalog.get_cooler,COOLERS),(catalog.get_fan,FANS)):
            for model_id in ids:
                with self.subTest(model=model_id):
                    row=getter(model_id)
                    self.assertTrue(row['brand']);self.assertTrue(row['series'])
                    self.assertEqual(row['geometry_accuracy'],'original_reference')
                    self.assertEqual(row['reviewed'],'2026-11-07')
                    self.assertTrue(row['sources'])
                    for url in row['sources']:
                        self.assertEqual(urlparse(url).scheme,'https')
                        self.assertIn(urlparse(url).hostname,OFFICIAL_HOSTS)
                    self.assertTrue(row.get('notes'))
                    self.assertNotIn('rpm',row)
                    self.assertNotIn('direction',row)

    def test_passive_nhp1_never_advertises_a_fan(self):
        row=catalog.get_cooler('noctua-nh-p1')
        self.assertEqual(row['kind'],'passive_tower')
        self.assertEqual(row['dimensions_mm'],dict(width=154,height=158,depth=152))
        self.assertTrue(row['dimensions_verified'])
        self.assertEqual(row['fan_count'],0);self.assertIsNone(row['fan_model'])
        self.assertEqual(row['heatpipes'],6)
        self.assertEqual(row['fin_count'],13);self.assertTrue(row['perforated_fins'])

    def test_incomplete_assembled_envelopes_are_not_promoted_to_verified(self):
        for model_id,height in (('thermalright-axp120-x67',67),('thermalright-si100',99.8)):
            with self.subTest(model=model_id):
                row=catalog.get_cooler(model_id)
                self.assertFalse(row['dimensions_verified'])
                self.assertTrue(row['envelope_is_reference'])
                self.assertEqual(row['dimensions_mm']['height'],height)
                self.assertTrue(row['fan_dimensions_verified'])
        tryx=catalog.get_cooler('tryx-panorama-se360')
        self.assertTrue(tryx['radiator_dimensions_verified'])
        self.assertEqual(tryx['radiator_mm'],dict(length=394,width=120,thickness=27))
        self.assertFalse(tryx['pump_dimensions_verified'])
        self.assertFalse(tryx['pump_axis_orientation_verified'])

    def test_fuma_has_independent_front_and_centre_fan_models(self):
        row=catalog.get_cooler('scythe-fuma3')
        self.assertEqual(row['fan_models'],['scythe-kaze-flex-ii120-slim','scythe-kaze-flex-ii120'])
        self.assertEqual(row['fan_depths'],[15,26])
        self.assertEqual([catalog.get_fan(i)['blades'] for i in row['fan_models']],[11,9])
        self.assertTrue(all(catalog.get_fan(i)['blade_count_verified'] for i in row['fan_models']))

    def test_bundled_fans_do_not_inherit_the_wrong_retail_thickness(self):
        ek=catalog.get_cooler('ek-nucleus-cr360-lux-drgb')
        self.assertIsNone(ek['fan_model']);self.assertEqual(ek['fan_reference_depth_mm'],25)
        self.assertEqual(catalog.get_fan('ek-loop-fpt120-drgb')['depth_mm'],27)
        mugen=catalog.get_cooler('scythe-mugen6')
        self.assertIsNone(mugen['fan_model']);self.assertEqual(mugen['fan_reference_depth_mm'],26)
        self.assertEqual(mugen['fan_family'],'scythe-tornado')

    def test_distinct_frames_and_stationary_details_keep_their_semantics(self):
        lcd=catalog.get_fan('lian-li-uni-tllcd120')
        self.assertEqual((lcd['width_mm'],lcd['size_mm'],lcd['depth_mm']),(124,120,28))
        self.assertTrue(lcd['hub_display']);self.assertTrue(lcd['interlock_bridges'])
        self.assertFalse(lcd.get('power_connector_verified',False))
        reverse=catalog.get_fan('phanteks-d30-120-reverse')
        self.assertTrue(reverse['reverse_blade'])
        self.assertFalse(reverse['rotation_direction_verified'])
        self.assertTrue(catalog.get_fan('silverstone-ap183')['directional_grille'])
        self.assertTrue(catalog.get_fan('arctic-p12-max')['outer_ring'])
        for model_id in ('bequiet-light-wings120-hs','fractal-prisma-al18-pwm','alphacool-rise-aurora120'):
            row=catalog.get_fan(model_id)
            self.assertTrue(row['frame_rgb_ring']);self.assertFalse(row['outer_ring'])
        self.assertEqual(catalog.get_fan('thermaltake-ct120')['pad_style'],'round')
        self.assertEqual(catalog.get_fan('alphacool-rise-aurora120')['lighting_connector'],'jst_argb3')

    def test_unverified_blades_and_rotation_remain_explicit(self):
        verified={'scythe-kaze-flex-ii120','scythe-kaze-flex-ii120-slim',
                  'bequiet-light-wings120-hs','fractal-prisma-al18-pwm',
                  'thermaltake-ct120','ek-loop-fpt120-drgb'}
        for model_id in FANS:
            with self.subTest(model=model_id):
                row=catalog.get_fan(model_id)
                self.assertEqual(row['blade_count_verified'],model_id in verified)
                self.assertFalse(row['rotation_direction_verified'])
                self.assertTrue(row['dimensions_verified'])
                self.assertGreater(row['depth_mm'],0)


if __name__=='__main__':
    unittest.main()
