"""Documented PSU envelopes, honest reference metadata and shared style coverage."""
import hashlib
import json
import math
import unittest
from unittest.mock import patch

from component_catalog import CATALOG,choices,coverage,get_component,validate_catalog


# L x W x H and fan diameter from each linked manufacturer specification. These
# deliberately distinguish similarly named revisions and shorter Core variants.
EXPECTED={
 'asus-rog-loki-1000p-sfx-l':('sfx_l',125,125,63.5,120),
 'asus-rog-thor-1000p2':('atx',190,150,86,135),
 'asus-tuf-gaming-750b':('atx',150,150,86,135),
 'msi-meg-ai1300p-pcie5':('atx',160,150,86,120),
 'msi-mpg-a1000g-pcie5':('atx',150,150,86,135),
 'bequiet-dark-power-13-1000':('atx',175,150,86,135),
 'bequiet-straight-power-12-1000':('atx',160,150,86,135),
 'fsp-hydro-ti-pro-1000-atx31':('atx',150,150,86,135),
 'thermaltake-gf3-snow-1000-2025':('atx',140,150,86,135),
 'coolermaster-v850-sfx-gold-atx31':('sfx',100,125,63.5,92),
 'lian-li-sp-v2-gold-850-white':('sfx',100,125,63.5,92),
 'nzxt-c1000-gold-atx31-white':('atx',160,150,86,135),
 'nzxt-c1000-gold-core':('atx',150,150,86,135),
 'silverstone-sx1000r-platinum':('sfx_l',130,125,63.5,120),
 'corsair-cx650m-cp9020103':('atx',140,150,86,120),
}
ORIGINAL_IDS=('corsair-rm850x-2024','corsair-rm1000x-2024','corsair-sf750-2024',
 'corsair-sf1000l','seasonic-focus-gx850-atx31','seasonic-prime-fanless-tx700')
ORIGINAL_SHA256='5ffc3c6a600b567918e818f293704eeb03f2e25f93a02d8475f0fb511a747b8d'


class PsuCatalogExpansionTests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start','socket.socket'):
            self.enterContext(patch(target,side_effect=AssertionError('PSU references do not access hardware, workers or network')))

    def test_original_six_records_and_non_psu_categories_are_preserved(self):
        original=[get_component(identity) for identity in ORIGINAL_IDS]
        raw=json.dumps(original,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),ORIGINAL_SHA256)
        self.assertTrue(validate_catalog())
        self.assertEqual(coverage(),dict(psu=21,storage=29,expansion=3))
        self.assertEqual({row['id'] for row in choices('psu')},set(ORIGINAL_IDS)|set(EXPECTED))

    def test_new_envelopes_and_unverified_details_are_explicit(self):
        for identity,expected in EXPECTED.items():
            with self.subTest(model=identity):
                row=get_component(identity)
                actual=(row['form_factor'],*(row['dimensions_mm'][key] for key in ('length','width','height')),row['fan_diameter_mm'])
                self.assertEqual(actual,expected)
                self.assertTrue(row['dimensions_verified'] and row['fan_size_verified'])
                self.assertEqual(row['fan_count'],1)
                self.assertTrue(row['series'] and row['brand'] and row['model_number'])
                self.assertTrue(all(url.startswith('https://') for url in row['sources']))
                self.assertEqual(row['selection_source'],'manual')
                self.assertEqual(row['grille_pattern'],'reference')
                self.assertTrue(row['grille_schematic'] and row['connector_layout_schematic'] and row['appearance_unverified'])
                self.assertFalse(row['blade_geometry_reviewed'] or row['rotation_direction_verified'])
                self.assertNotIn('ports',row,'Unverified physical socket counts must not become real counts')
                self.assertNotIn('fixed_cable_groups',row,'An unverified harness is not a known cable map')
                row['dimensions_mm']['length']=1
                self.assertEqual(get_component(identity)['dimensions_mm']['length'],expected[1])
        self.assertTrue(get_component('asus-rog-thor-1000p2')['oled_display'])
        self.assertFalse(get_component('asus-rog-thor-1000p2')['oled_live_telemetry'])
        self.assertTrue(get_component('asus-rog-loki-1000p-sfx-l')['rgb_fan'])
        self.assertTrue(get_component('asus-rog-loki-1000p-sfx-l')['outer_ring'])
        self.assertFalse(get_component('asus-tuf-gaming-750b')['modular'])
        semi=get_component('corsair-cx650m-cp9020103')
        self.assertTrue(semi['modular'] and semi['semi_modular'])
        for identity in ('thermaltake-gf3-snow-1000-2025','lian-li-sp-v2-gold-850-white','nzxt-c1000-gold-atx31-white'):
            self.assertEqual(get_component(identity)['factory_finish'],'white')

    def test_all_styles_keep_identity_rotor_plane_and_expression_free_original(self):
        import accessory_art
        from top_bar_config import HARDWARE_ICON_STYLES
        accessory_art.clear_cache()
        self.addCleanup(accessory_art.clear_cache)
        for identity in EXPECTED:
            baseline=None
            for style in HARDWARE_ICON_STYLES:
                with self.subTest(model=identity,style=style):
                    artwork=accessory_art.art('psu',identity,style)
                    self.assertEqual(artwork['id'],identity)
                    self.assertEqual(artwork['label'],get_component(identity)['label'])
                    self.assertEqual(len(artwork['rotors']),1)
                    layout=[tuple(rotor[key] for key in ('x','y','width','height')) for rotor in artwork['rotors']]
                    if baseline is None:baseline=layout
                    self.assertEqual(layout,baseline)
                    self.assertTrue(artwork['reference_details'])
                    self.assertEqual(artwork['motion_source'],'reference_demo')
                    self.assertEqual(artwork['original_face'],'smile' if style in ('cartoon','notebook_smile') else 'none')
                    self.assertTrue(artwork['svg'].startswith('<svg'))
        self.assertLessEqual(accessory_art.cache_info()['entries'],16)

    def test_new_models_keep_physical_envelopes_without_claiming_installed_telemetry(self):
        from assembly_auxiliary import add_auxiliary
        mounts=dict(case_dimensions=(400.,600.,650.),case=dict(layout='dual_chamber',features=[]))
        for identity,expected in EXPECTED.items():
            with self.subTest(model=identity):
                meshes,meta=add_auxiliary(dict(auxiliary=dict(psu=dict(model_id=identity))),mounts,'eco')
                shell=next(mesh for mesh in meshes if mesh.name=='psu-shell')
                extents=tuple(max(shell.vertices[n::6])-min(shell.vertices[n::6]) for n in range(3))
                self.assertEqual(extents,(expected[3],expected[2],expected[1]))
                self.assertFalse(meta['psu_fan_tachometer_available'])
                self.assertIsNone(meta['devices'][0]['live_power_w'])
                rotors=[mesh for mesh in meshes if mesh.rotor]
                self.assertTrue(any(mesh.name=='psu-fan-blades' for mesh in rotors))
                self.assertTrue(any(mesh.name=='psu-fan-hub' for mesh in rotors))
                self.assertTrue(all(mesh.axis==(1.,0.,0.) for mesh in rotors))
                self.assertFalse(any(mesh.name.startswith('style-') for mesh in meshes))
                self.assertTrue(all(math.isfinite(value) for mesh in meshes for value in mesh.vertices))


if __name__=='__main__':unittest.main()
