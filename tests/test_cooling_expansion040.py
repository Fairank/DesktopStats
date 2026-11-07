"""0.40 static data and relative-motion provenance; no GUI or live hardware."""
import hashlib
import json
import unittest
from urllib.parse import urlparse

import cooling_catalog as catalog

COOLERS=(
    'noctua-nh-l12s','noctua-nh-c14s','bequiet-dark-rock-tf2','cryorig-h7-quad-lumi',
    'cryorig-c7','zalman-cnps9900-max','scythe-ninja5','thermalright-macho-revb',
    'thermaltake-toughair510','fractal-lumen-s28-v2','xpg-levante-x360','deepcool-lt720',
)
FANS=(
    'noctua-nfp12-redux1700-pwm','arctic-f8-pwm-pst','arctic-f14-pwm-pst',
    'scythe-kazeflex140-square','cryorig-qf120-led-balance','silverstone-airslimmer120',
    'coolermaster-mf200r-argb','thermaltake-pure20-argb','corsair-lx120r-rgb',
    'antec-fusion120-argb-white','montech-ax120-pwm','apnx-fp1-120','fractal-aspect14-pwm',
    'thermalright-ty147a','bequiet-tf2-upper135','bequiet-tf2-lower135',
)
HOSTS={
    'www.noctua.at','noctua.at','www.arctic.de','www.scytheus.com','www.scythe.co.jp',
    'www.thermalright.com','www.deepcool.com','www.zalman.com','www.cryorig.com','en.cryorig.com',
    'www.fractal-design.com','www.xpg.com','www.silverstonetek.com','www.bequiet.com',
    'thermaltake.com','legacy.coolermaster.com','www.corsair.com','www.antec.com',
    'www.montechpc.com','www.apnx.com',
}


class CoolingExpansion040Tests(unittest.TestCase):
    def test_previous_108_records_have_only_the_two_authorized_fuma_keys_added(self):
        old={'coolers':[catalog.get_cooler(c['id']) for c in catalog.choices_coolers()[:54]],
             'fans':[catalog.get_fan(c['id']) for c in catalog.choices_fans()[:54]]}
        fama=next(row for row in old['coolers'] if row['id']=='scythe-fuma3')
        self.assertEqual(fama.pop('fan_relative_directions'),[1,-1])
        self.assertTrue(fama.pop('relative_rotation_verified'))
        raw=json.dumps(old,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         'c569ca16c4782233df63e33d360c71eaef923c0d26aabf58d9539ab775bed093')

    def test_expansion_has_twelve_coolers_and_sixteen_distinct_fans(self):
        self.assertEqual(tuple(r['id'] for r in catalog.choices_coolers()[54:66]),COOLERS)
        self.assertEqual(tuple(r['id'] for r in catalog.choices_fans()[54:70]),FANS)
        self.assertEqual(len(set(COOLERS)),12);self.assertEqual(len(set(FANS)),16)
        for getter,ids in ((catalog.get_cooler,COOLERS),(catalog.get_fan,FANS)):
            for identity in ids:
                with self.subTest(model=identity):
                    row=getter(identity)
                    self.assertTrue(row['brand']);self.assertTrue(row['series'])
                    self.assertEqual(row['geometry_accuracy'],'original_reference')
                    self.assertTrue(row['notes'])
                    for url in row['sources']:
                        self.assertEqual(urlparse(url).scheme,'https')
                        self.assertIn(urlparse(url).hostname,HOSTS)
                    self.assertNotIn('rpm',row)
                    self.assertFalse(row.get('rotation_direction_verified',False))

    def test_fuma_contra_rotation_uses_common_view_without_swapping_physical_fans(self):
        row=catalog.get_cooler('scythe-fuma3')
        self.assertEqual(row['fan_models'],['scythe-kaze-flex-ii120-slim','scythe-kaze-flex-ii120'])
        self.assertEqual(row['fan_depths'],[15,26])
        self.assertEqual([catalog.get_fan(i)['blades'] for i in row['fan_models']],[11,9])
        self.assertEqual(row['fan_relative_directions'],[1,-1])
        self.assertTrue(row['relative_rotation_verified'])
        self.assertFalse(row.get('rotation_direction_verified',False))
        # Direction is a relationship between the two fans; it must not leak
        # into unrelated retail fan records or make an unknown source rotate.
        for model in row['fan_models']:
            self.assertNotIn('fan_relative_directions',catalog.get_fan(model))
            self.assertFalse(catalog.get_fan(model)['rotation_direction_verified'])

    def test_c_shaped_modes_do_not_substitute_top_and_bottom_installations(self):
        under=catalog.get_cooler('noctua-nh-l12s')
        above=catalog.get_cooler('noctua-nh-c14s')
        self.assertTrue(under['c_shape']);self.assertTrue(above['c_shape'])
        self.assertEqual((under['fan_placement'],under['dimensions_mm']['height']),('under',70))
        self.assertEqual((above['fan_placement'],above['dimensions_mm']['height']),('above',142))
        self.assertEqual(under['fan_model'],'noctua-nf-a12x15-pwm')
        self.assertEqual(above['fan_model'],'noctua-nf-a14-pwm')
        self.assertEqual((under['documented_fin_count'],above['documented_fin_count']),(58,66))

    def test_tf2_has_two_horizontal_banks_with_independent_upper_and_middle_fans(self):
        row=catalog.get_cooler('bequiet-dark-rock-tf2')
        self.assertEqual(row['kind'],'dual_top_flow')
        self.assertEqual(row['horizontal_fin_banks'],2)
        self.assertEqual(row['fan_placements'],['above','between'])
        self.assertEqual(row['fan_models'],['bequiet-tf2-upper135','bequiet-tf2-lower135'])
        self.assertEqual(row['fan_depths'],[25,22])
        self.assertEqual(row['fan_sizes'],[135,135])
        self.assertEqual(row['dimensions_mm'],dict(width=140,height=134,depth=163))
        self.assertTrue(row['dimensions_verified'])
        upper,lower=[catalog.get_fan(i) for i in row['fan_models']]
        self.assertFalse(upper['marketed_separately_verified'])
        self.assertFalse(lower['marketed_separately_verified'])
        self.assertFalse(upper['blade_count_verified'])
        self.assertEqual(lower['blades'],9);self.assertTrue(lower['blade_count_verified'])

    def test_zalman_overall_envelope_does_not_claim_unmeasured_ring_or_rotor_dimensions(self):
        row=catalog.get_cooler('zalman-cnps9900-max')
        self.assertEqual(row['kind'],'radial_tower');self.assertEqual(row['radial_fin_banks'],2)
        self.assertEqual(row['dimensions_mm'],dict(width=131,height=152,depth=94))
        self.assertTrue(row['dimensions_verified']);self.assertTrue(row['frameless_fan'])
        self.assertFalse(row['radial_geometry_verified'])
        self.assertFalse(row['fan_dimensions_verified'])
        self.assertFalse(row['heatpipe_count_verified'])

    def test_ninja_and_macho_keep_their_original_supplied_fan_configuration(self):
        ninja=catalog.get_cooler('scythe-ninja5')
        self.assertEqual(ninja['kind'],'single_tower');self.assertEqual(ninja['fan_count'],2)
        self.assertEqual(ninja['fan_reference_depth_mm'],27)
        self.assertEqual(ninja['fan_family'],'scythe-kaze-original')
        macho=catalog.get_cooler('thermalright-macho-revb')
        self.assertEqual(macho['fan_count'],1)
        self.assertEqual(macho['fan_model'],'thermalright-ty147a')
        self.assertFalse(macho['dimensions_verified'])
        self.assertTrue(macho['envelope_is_reference'])

    def test_aio_pump_location_mirror_and_axis_provenance_are_distinct(self):
        lumen=catalog.get_cooler('fractal-lumen-s28-v2')
        self.assertEqual(lumen['radiator_mm'],dict(length=313,width=140,thickness=27))
        self.assertEqual(lumen['pump_location'],'radiator')
        self.assertEqual(lumen['fan_model'],'fractal-aspect14-pwm')
        self.assertEqual(lumen['pump_style'],'fractal_lumen')
        xpg=catalog.get_cooler('xpg-levante-x360')
        self.assertFalse(xpg['pump_dimensions_verified'])
        self.assertFalse(xpg['pump_axis_orientation_verified'])
        lt=catalog.get_cooler('deepcool-lt720')
        self.assertEqual(lt['pump_reference_mm'],dict(width=80,height=68,depth=94))
        self.assertTrue(lt['pump_dimensions_verified'])
        self.assertFalse(lt['fan_reference_rgb'])

    def test_frame_polygons_are_static_and_reverse_does_not_infer_absolute_motion(self):
        for model,sides in (('antec-fusion120-argb-white',12),('montech-ax120-pwm',6)):
            row=catalog.get_fan(model)
            self.assertEqual(row['frame_rgb_polygon'],sides)
            self.assertFalse(row['outer_ring'])
        lx=catalog.get_fan('corsair-lx120r-rgb')
        self.assertTrue(lx['reverse_blade']);self.assertTrue(lx['frame_rgb_ring'])
        self.assertFalse(lx.get('power_connector_verified',False))
        self.assertFalse(lx['rotation_direction_verified'])
        self.assertTrue(catalog.get_fan('cryorig-qf120-led-balance')['side_air_inlets'])
        self.assertFalse(catalog.get_fan('cryorig-qf120-led-balance')['rgb'])

    def test_only_documented_new_blade_counts_are_marked_verified(self):
        verified={'noctua-nfp12-redux1700-pwm','silverstone-airslimmer120',
                  'thermaltake-pure20-argb','fractal-aspect14-pwm','bequiet-tf2-lower135'}
        for identity in FANS:
            row=catalog.get_fan(identity)
            self.assertEqual(row['blade_count_verified'],identity in verified,identity)
            self.assertFalse(row['rotation_direction_verified'])
        self.assertEqual(catalog.get_fan('silverstone-airslimmer120')['depth_mm'],15.6)
        self.assertEqual(catalog.get_fan('arctic-f14-pwm-pst')['depth_mm'],27)
        self.assertEqual(catalog.get_fan('apnx-fp1-120')['depth_mm'],30)
        self.assertEqual(catalog.get_fan('thermaltake-pure20-argb')['blades'],11)


if __name__=='__main__':
    unittest.main()
