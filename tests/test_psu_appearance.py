"""Pure PSU family construction, attachment and cross-artwork contracts."""
import copy
import math
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import accessory_art
import assembly_auxiliary
from assembly_style import apply_colors
from component_catalog import choices,get_component
from top_bar_config import HARDWARE_ICON_STYLES


TUF='asus-tuf-gaming-750b'
CXM='corsair-cx650m-cp9020103'
THOR='asus-rog-thor-1000p2'
LOKI='asus-rog-loki-1000p-sfx-l'
SVG='{http://www.w3.org/2000/svg}'


def mounts(wiring=False):
    value=dict(case_dimensions=(600.,800.,800.),psu=dict(position=(0.,0.,0.)))
    if wiring:
        value['connectors']=dict(
            atx24=[dict(position=(120.,140.,210.),normal=(0.,0.,-1.),along=(1.,0.,0.))],
            eps8=[dict(position=(-120.,180.,220.),normal=(0.,0.,-1.),along=(1.,0.,0.))])
    return value


def generate(identity,wiring=False,level='balanced'):
    return assembly_auxiliary.add_auxiliary(
        dict(auxiliary=dict(psu=dict(model_id=identity),cables_enabled=wiring)),mounts(wiring),level)


class PsuAppearanceTests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,side_effect=AssertionError('PSU illustration performs no discovery or workers')))

    def tearDown(self):
        accessory_art.clear_cache()

    def assert_fixed_source(self,meshes,cable):
        grommet=next(mesh for mesh in meshes if mesh.name=='psu-fixed-harness-grommet')
        harness=next(mesh for mesh in meshes if mesh.name=='psu-fixed-harness-reference')
        source=cable['source_socket']
        self.assertLess(abs(source[0]-grommet.position[0]),9.)
        self.assertLess(abs(source[1]-grommet.position[1]),9.)
        self.assertGreater(source[2],grommet.position[2])
        self.assertEqual(cable['start'],source)
        self.assertEqual(cable['source_owner'],'psu')
        self.assertLess(min(math.dist(source,tuple(harness.vertices[start+n]+harness.position[n] for n in range(3)))
                            for start in range(0,len(harness.vertices),6)),1e-7,
                        'A fixed source must touch the modeled factory wire, without an empty attachment gap')

    def test_nonmodular_tuf_has_fixed_exit_and_no_detachable_socket_or_source_plug(self):
        self.assertFalse(get_component(TUF)['modular'])
        meshes,meta=generate(TUF,wiring=True)
        names={mesh.name for mesh in meshes}
        self.assertTrue({'psu-fixed-cable-panel','psu-fixed-harness-grommet','psu-fixed-harness-reference'}<=names)
        self.assertFalse(any(name.startswith('psu-modular-') for name in names))
        self.assertEqual(meta['cable_count'],2)
        self.assertEqual(meta['omitted_route_count'],0)
        self.assertFalse(any('-source-plug-' in name for name in names))
        self.assertTrue(any('-target-plug-shell' in name for name in names))
        for cable in meta['cables']:
            self.assert_fixed_source(meshes,cable)
        device=meta['devices'][0]
        self.assertTrue(device['fixed_harness'])
        self.assertFalse(device['modular'])
        self.assertFalse(device['modular_socket_layout_schematic'])

    def test_semimodular_cxm_keeps_both_attachment_types_without_guessing_fixed_groups(self):
        row=get_component(CXM)
        self.assertTrue(row['modular']);self.assertTrue(row['semi_modular'])
        pristine=copy.deepcopy(row)
        meshes,meta=generate(CXM)
        names={mesh.name for mesh in meshes}
        self.assertTrue({'psu-modular-connector-panel','psu-modular-dark-socket',
                         'psu-fixed-harness-grommet','psu-fixed-harness-reference'}<=names)
        self.assertTrue(meta['devices'][0]['fixed_harness'])
        self.assertTrue(meta['devices'][0]['semi_modular'])
        self.assertEqual(get_component(CXM),pristine)

    def test_declared_fixed_groups_use_the_harness_while_other_groups_keep_modular_plugs(self):
        # The catalog does not establish this old CXM's exact fixed groups.
        # Inject an explicit reference policy only inside the test to verify
        # routing honors known groups without asserting they are factory facts.
        lookup=assembly_auxiliary.get_component
        for fixed in (('atx24',),('atx24','eps8')):
            def fixture(identity):
                value=lookup(identity)
                if identity==CXM:value['fixed_cable_groups']=fixed
                return value
            with self.subTest(fixed=fixed):
                with patch.object(assembly_auxiliary,'get_component',side_effect=fixture):
                    meshes,meta=generate(CXM,wiring=True)
                self.assertEqual(meta['cable_count'],2)
                self.assertEqual(meta['omitted_route_count'],0)
                names={mesh.name for mesh in meshes}
                for index,cable in enumerate(meta['cables']):
                    prefix='cable-'+str(index)+'-'+cable['kind']+'-source-plug-shell'
                    if cable['kind'] in fixed:
                        self.assert_fixed_source(meshes,cable)
                        self.assertNotIn(prefix,names)
                    else:
                        self.assertIn(prefix,names)
                        self.assertNotEqual(cable['start'],cable['source_socket'])

    def test_thor_oled_is_an_unbound_blank_screen_and_never_a_measured_power_value(self):
        meshes,meta=generate(THOR)
        names={mesh.name for mesh in meshes}
        self.assertTrue({'psu-oled-reference-bezel','psu-oled-unread-blank'}<=names)
        device=meta['devices'][0]
        self.assertTrue(device['oled_display_available'])
        self.assertIsNone(device['oled_live_reading'])
        self.assertIsNone(device['live_power_w'])
        for style in HARDWARE_ICON_STYLES:
            drawing=accessory_art.art('psu',THOR,style)
            self.assertTrue(drawing['art_details']['oled_display'])
            self.assertIsNone(drawing['art_details']['oled_live_reading'])
            root=ET.fromstring(drawing['body_svg'])
            screens=[node for node in root.iter() if node.get('data-oled')=='unread-blank-reference']
            self.assertEqual(len(screens),1)
            self.assertTrue(list(screens[0]))
            self.assertFalse(any(node.tag in (SVG+'text',SVG+'image',SVG+'use') for node in screens[0].iter()))

    def test_loki_ring_and_static_rgb_change_the_art_without_creating_live_telemetry(self):
        row=get_component(LOKI)
        self.assertTrue(row['outer_ring']);self.assertTrue(row['rgb_fan'])
        meshes,meta=generate(LOKI)
        blades=next(mesh for mesh in meshes if mesh.name=='psu-fan-blades')
        lookup=assembly_auxiliary.get_component
        def plain(identity):
            value=lookup(identity)
            if identity==LOKI:value.update(outer_ring=False,rgb_fan=False)
            return value
        with patch.object(assembly_auxiliary,'get_component',side_effect=plain):
            ordinary,_=generate(LOKI)
        ordinary_blades=next(mesh for mesh in ordinary if mesh.name=='psu-fan-blades')
        self.assertGreater(blades.vertex_count,ordinary_blades.vertex_count)
        self.assertNotEqual(blades.color,ordinary_blades.color)
        self.assertFalse(meta['psu_fan_tachometer_available'])
        self.assertFalse(meta['devices'][0]['rgb_lighting_live'])
        self.assertFalse(meta['devices'][0]['fan_rpm_available'])
        drawing=accessory_art.art('psu',LOKI)
        self.assertTrue(drawing['art_details']['blade_tip_ring'])
        self.assertTrue(drawing['art_details']['rgb_fan'])
        self.assertFalse(drawing['art_details']['rgb_lighting_live'])
        self.assertFalse(drawing['rotation_direction_verified'])
        self.assertEqual(drawing['motion_source'],'reference_demo')

    def test_documented_white_finishes_are_used_by_original_2d_and_3d_housings(self):
        for identity in ('thermaltake-gf3-snow-1000-2025','lian-li-sp-v2-gold-850-white','nzxt-c1000-gold-atx31-white'):
            with self.subTest(model=identity):
                row=get_component(identity)
                self.assertEqual(row['factory_finish'],'white')
                meshes,_=generate(identity)
                shell=next(mesh for mesh in meshes if mesh.name=='psu-shell')
                expected=tuple(int(row['housing_color'][start:start+2],16)/255. for start in (1,3,5))
                self.assertEqual(shell.color[:3],expected)
                self.assertGreater(min(shell.color[:3]),.75)
                drawing=accessory_art.art('psu',identity,'miniature')
                self.assertIn(row['housing_color'],drawing['body_svg'])

    def test_bequiet_funnel_is_a_static_open_taper_and_appears_in_all_2d_styles(self):
        for identity in ('bequiet-dark-power-13-1000','bequiet-straight-power-12-1000'):
            with self.subTest(model=identity):
                row=get_component(identity)
                self.assertTrue(row['funnel_inlet'])
                meshes,meta=generate(identity)
                funnel=next(mesh for mesh in meshes if mesh.name=='psu-fan-inlet-funnel-reference')
                self.assertFalse(funnel.rotor)
                self.assertGreater(max(funnel.vertices[1::6])-min(funnel.vertices[1::6]),2.)
                for start in range(0,len(funnel.vertices),18):
                    points=[(funnel.vertices[start+n],funnel.vertices[start+n+2]) for n in (0,6,12)]
                    self.assertTrue(all(math.hypot(*point)>row['fan_diameter_mm']*.4 for point in points))
                    cross=[a[0]*b[1]-a[1]*b[0] for a,b in zip(points,(*points[1:],points[0]))]
                    self.assertFalse(all(value>=0 for value in cross) or all(value<=0 for value in cross),
                                     'The funnel must not cap the central fan opening')
                device=meta['devices'][0]
                self.assertEqual(device['fan_inlet_profile'],'funnel_reference')
                self.assertEqual(device['frameless_fan'],bool(row.get('frameless_fan')))
                for style in HARDWARE_ICON_STYLES:
                    drawing=accessory_art.art('psu',identity,style)
                    root=ET.fromstring(drawing['body_svg'])
                    self.assertEqual(sum(node.get('data-fan-inlet')=='funnel-reference' for node in root.iter()),1)
                    self.assertEqual(drawing['art_details']['fan_inlet_profile'],device['fan_inlet_profile'])
                    self.assertEqual(drawing['art_details']['frameless_fan'],device['frameless_fan'])

    def test_frameless_motor_supports_are_actual_static_geometry_and_2d_shapes(self):
        identity='bequiet-dark-power-13-1000'
        self.assertTrue(get_component(identity)['frameless_fan'])
        meshes,_=generate(identity)
        names={mesh.name for mesh in meshes}
        expected={'psu-frameless-motor-supports-reference','psu-frameless-stationary-motor'}
        self.assertTrue(expected<=names)
        self.assertTrue(all(not mesh.rotor for mesh in meshes if mesh.name in expected))
        original=accessory_art.art('psu',identity)
        root=ET.fromstring(original['body_svg'])
        self.assertEqual(sum(node.get('data-fan-support')=='frameless-reference' for node in root.iter()),1)
        lookup=assembly_auxiliary.get_component
        def framed(model):
            row=lookup(model)
            if model==identity:row['frameless_fan']=False
            return row
        accessory_art.clear_cache()
        with patch.object(assembly_auxiliary,'get_component',side_effect=framed),\
             patch.object(accessory_art.component_catalog,'get_component',side_effect=framed):
            ordinary,_=generate(identity)
            drawing=accessory_art.art('psu',identity)
        self.assertFalse(expected&{mesh.name for mesh in ordinary})
        self.assertEqual(next(mesh.vertices for mesh in meshes if mesh.name=='psu-fan-blades'),
                         next(mesh.vertices for mesh in ordinary if mesh.name=='psu-fan-blades'))
        self.assertNotEqual(original['body_svg'],drawing['body_svg'])
        root=ET.fromstring(drawing['body_svg'])
        self.assertFalse(any(node.get('data-fan-support')=='frameless-reference' for node in root.iter()))

    def test_all_psu_structures_and_fan_counts_match_2d_in_every_shared_style(self):
        records=choices('psu')
        self.assertGreaterEqual(len(records),21)
        for selection in records:
            row=get_component(selection['id'])
            meshes,meta=generate(row['id'])
            device=meta['devices'][0]
            self.assertEqual(device['fan_count'],row['fan_count'])
            self.assertEqual(sum(mesh.name=='psu-fan-blades' for mesh in meshes),row['fan_count'])
            self.assertEqual(sum(mesh.name=='psu-fan-hub' for mesh in meshes),row['fan_count'])
            original_planes=None
            for style in HARDWARE_ICON_STYLES:
                with self.subTest(model=row['id'],style=style):
                    colored=apply_colors(meshes,style)
                    self.assertEqual(sum(mesh.rotor for mesh in colored),row['fan_count']*2)
                    self.assertTrue(all(first.vertices is second.vertices for first,second in zip(meshes,colored)))
                    drawing=accessory_art.art('psu',row['id'],style)
                    details=drawing['art_details']
                    self.assertEqual(details['fan_count'],device['fan_count'])
                    self.assertEqual(len(drawing['rotors']),device['fan_count'])
                    self.assertEqual(details['modular'],device['modular'])
                    self.assertEqual(details['semi_modular'],device['semi_modular'])
                    self.assertEqual(details['fixed_harness'],device['fixed_harness'])
                    self.assertEqual(details['oled_display'],device['oled_display_available'])
                    self.assertEqual(details['blade_tip_ring'],bool(row.get('outer_ring')))
                    self.assertEqual(details['grille'],device['grille_pattern'])
                    self.assertEqual(details['form_factor'],row['form_factor'])
                    self.assertEqual(details['fan_inlet_profile'],device['fan_inlet_profile'])
                    self.assertEqual(details['frameless_fan'],device['frameless_fan'])
                    self.assertIsNone(details['oled_live_reading'])
                    self.assertFalse(details['rgb_lighting_live'])
                    planes=tuple((rotor['x'],rotor['y'],rotor['width'],rotor['height']) for rotor in drawing['rotors'])
                    if original_planes is None:original_planes=planes
                    else:self.assertEqual(planes,original_planes)


if __name__=='__main__':unittest.main()
