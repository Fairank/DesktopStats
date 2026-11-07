"""Pure SVG/caching contracts for the lazy, manual accessory artwork library."""
import ast
import copy
import math
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import accessory_art as artwork
import chassis_catalog
import component_catalog
import cooling_catalog


ROOT=Path(__file__).resolve().parents[1]
KINDS={'cases':'case','coolers':'cooler','psus':'psu','fans':'fan'}
SVG='{http://www.w3.org/2000/svg}'


class AccessoryArtTests(unittest.TestCase):
    def tearDown(self):
        artwork.clear_cache()

    def test_picker_covers_every_current_catalog_without_rendering(self):
        artwork.clear_cache()
        rows=artwork.choices()
        self.assertEqual({key:len(value) for key,value in rows.items()},
                         dict(cases=96,coolers=66,psus=21,fans=70))
        catalog_rows=(chassis_catalog.choices(),cooling_catalog.choices_coolers(),
                      component_catalog.choices('psu'),cooling_catalog.choices_fans())
        for key,source in zip(KINDS,catalog_rows):
            self.assertEqual([r['id'] for r in rows[key]],[r['id'] for r in source])
            self.assertTrue(all(set(r)=={'id','label','brand','fidelity'} for r in rows[key]))
        self.assertEqual(artwork.cache_info(),dict(entries=0,max_entries=16))
        rows['cases'][0]['label']='changed'
        rows['coolers'].clear()
        self.assertNotEqual(artwork.choices(),rows)

    def test_styles_match_shared_preferences_without_importing_sensors(self):
        tree=ast.parse((ROOT/'top_bar_config.py').read_text(encoding='utf-8'))
        for node in tree.body:
            if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='HARDWARE_ICON_STYLES' for t in node.targets):
                self.assertEqual(artwork.STYLES,ast.literal_eval(node.value))
                break
        else:
            self.fail('Shared hardware style IDs were not found')

    def test_all_current_artworks_are_safe_detached_svg_and_keep_the_model(self):
        required={'id','kind','label','brand','style','svg','body_svg','foreground_svg',
                  'rotors','reference_details','sources'}
        for key,rows in artwork.choices().items():
            kind=KINDS[key]
            for row in rows:
                counts=set()
                planes=set()
                for style in artwork.STYLES:
                    with self.subTest(kind=kind,model=row['id'],style=style):
                        art=artwork.art(kind,row['id'],style)
                        self.assertTrue(required<=set(art))
                        self.assertEqual((art['id'],art['kind'],art['label'],art['brand'],art['style']),
                                         (row['id'],kind,row['label'],row['brand'],style))
                        self.assertTrue(art['reference_details'])
                        self.assertTrue(art['sources'])
                        self.assertTrue(all(source.startswith('https://') for source in art['sources']))
                        self.assertFalse(art['rotation_direction_verified'])
                        self.assertEqual(art['motion_source'],'reference_demo')
                        for field in ('svg','body_svg','foreground_svg'):
                            source=art[field]
                            if not source:
                                self.assertEqual(field,'foreground_svg')
                                continue
                            xml=ET.fromstring(source)
                            self.assertEqual(xml.tag,SVG+'svg')
                            self.assertEqual(xml.get('viewBox'),'0 0 120 100')
                            for element in xml.iter():
                                self.assertNotIn(element.tag.removeprefix(SVG),('script','foreignObject','image','text','use'))
                                self.assertFalse(any(name.lower().startswith('on') or name.endswith('href') for name in element.attrib))
                            self.assertLess(len(source),100_000)
                        self.assertNotIn('data-blade-count',art['body_svg'])
                        self.assertNotIn('data-blade-count',art['foreground_svg'])
                        counts.add(len(art['rotors']))
                        planes.add(tuple((r['x'],r['y'],r['width'],r['height']) for r in art['rotors']))
                        for rotor in art['rotors']:
                            self.assertEqual(rotor['direction'],-1 if row['id']=='scythe-fuma3' and rotor is art['rotors'][0] else 1)
                            self.assertTrue(all(math.isfinite(rotor[k]) for k in ('x','y','width','height')))
                            self.assertTrue(0<=rotor['x']<120 and 0<=rotor['y']<100)
                            self.assertTrue(0<rotor['width']<=120-rotor['x'])
                            self.assertTrue(0<rotor['height']<=100-rotor['y'])
                            xml=ET.fromstring(rotor['svg'])
                            self.assertEqual(xml.get('viewBox'),'0 0 100 100')
                        if style in ('cartoon','notebook_smile'):
                            self.assertEqual(art['original_face'],'smile')
                            self.assertIn('data-art-face="smile"',art['svg'])
                        else:
                            self.assertEqual(art['original_face'],'none')
                            self.assertNotIn('data-art-face',art['svg'])
                self.assertEqual(len(counts),1,'Changing style must not add or lose a fan')
                self.assertEqual(len(planes),1,'Changing style must preserve the model and fan planes')
                count=counts.pop()
                if kind=='case':
                    self.assertEqual(count,0,'Case fan mounts must not invent installed fans')
                elif kind=='cooler':
                    self.assertEqual(count,cooling_catalog.get_cooler(row['id'])['fan_count'])
                elif kind=='psu':
                    self.assertEqual(count,component_catalog.get_component(row['id'])['fan_count'])
                else:
                    self.assertEqual(count,1)

    def test_invalid_inputs_do_not_raise_or_consume_cache(self):
        artwork.clear_cache()
        for kind in ('',None,[],{},True,'storage','case<script>'):
            self.assertEqual(artwork.art(kind,'hyte-y70'),{})
        for identity in ('',None,[],{},True,'x'*65,'../hyte-y70','HYTE-Y70','hyte-y70\x00'):
            self.assertEqual(artwork.art('case',identity),{})
        for style in ('',None,[],{},True,'not-a-style','miniature" onload="bad'):
            self.assertEqual(artwork.art('case','hyte-y70',style),{})
        self.assertEqual(artwork.art('psu','samsung-990-pro-2tb'),{})
        self.assertEqual(artwork.art('fan','hyte-y70'),{})
        self.assertEqual(artwork.cache_info()['entries'],0)

    def test_only_sixteen_artworks_are_retained_and_results_are_detached(self):
        first=artwork.art('fan','arctic-p12-pwm')
        pristine=copy.deepcopy(first)
        first['rotors'][0]['svg']='bad'
        first['sources'].clear()
        first['art_details']['blade_count']=99
        self.assertEqual(artwork.art('fan','arctic-p12-pwm'),pristine)
        for row in artwork.choices()['cases']:
            artwork.art('case',row['id'],'notebook_line')
        self.assertEqual(artwork.cache_info(),dict(entries=16,max_entries=16))
        with patch.object(chassis_catalog,'choices',wraps=chassis_catalog.choices) as picker:
            artwork.choices()
            artwork.clear_cache()
            artwork.choices()
            self.assertEqual(picker.call_count,1)
        artwork.clear_cache()
        self.assertEqual(artwork.cache_info()['entries'],0)

    def test_known_family_shapes_and_hand_drawn_linework_are_distinct(self):
        for kind,models in (
            ('case',('fractal-north-mesh','cooler-master-masterframe-700','hyte-y70','fractal-terra-graphite')),
            ('cooler',('intel-laminar-rm1','noctua-nh-d15-g2','arctic-liquid-freezer-iii-360','nzxt-kraken-360-2023','custom-loop-360-reference')),
            ('psu',('corsair-rm1000x-2024','corsair-sf750-2024','seasonic-prime-fanless-tx700')),
            ('fan',('noctua-nf-a12x25-pwm','arctic-p12-pwm','coolermaster-mobius120','bequiet-silent-wings-pro4-120'))):
            images=[artwork.art(kind,model)['svg'] for model in models]
            self.assertEqual(len(set(images)),len(models))
            for model in models:
                original=artwork.art(kind,model)
                for style in ('notebook_color','notebook_line'):
                    drawing=artwork.art(kind,model,style)
                    self.assertIn(' C',drawing['svg'])
                    self.assertNotEqual(original['svg'],drawing['svg'])
                    self.assertEqual(original['art_details'],drawing['art_details'])
        dual=artwork.art('cooler','noctua-nh-d15-g2')['rotors']
        self.assertLess(dual[1]['x'],dual[0]['x'])
        self.assertGreater(dual[1]['y'],dual[0]['y'])
        self.assertLess(dual[0]['x'],dual[1]['x']+dual[1]['width'],'Dual-tower fans must overlap in depth')
        self.assertIn('data-grille="rounded_y"',artwork.art('psu','corsair-rm1000x-2024')['foreground_svg'])
        self.assertIn('data-fanless="true"',artwork.art('psu','seasonic-prime-fanless-tx700')['body_svg'])
        facet=artwork.art('case','hyte-y70')
        self.assertIn('data-case-facet="angular-glass-corner"',facet['body_svg'])
        line=artwork.art('cooler','noctua-nh-d15-g2','notebook_line')
        for rotor in line['rotors']:
            xml=ET.fromstring(rotor['svg'])
            leaf=[e for e in xml.iter() if 'data-leaf' in e.attrib]
            self.assertTrue(leaf)
            for group in leaf:
                self.assertEqual(next(iter(group)).get('fill'),'#fbf8ed',
                                 'Opaque line-art leaves must hide rear leaves and fins')
        self.assertIn('fill-rule="evenodd"',line['foreground_svg'],
                      'Stationary frames need a transparent opening above moving leaves')
        for model in ('arctic-liquid-freezer-iii-240','arctic-liquid-freezer-iii-360'):
            result=artwork.art('cooler',model)
            self.assertEqual(len(result['rotors']),cooling_catalog.get_cooler(model)['fan_count'],
                             'Exterior pump crown must not be invented as a moving impeller')

    def test_import_and_render_do_not_load_qt_meshes_or_native_device_code(self):
        script='''import importlib.abc,sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in {'PySide6','PyQt6','assembly_geometry','assembly_cooling','assembly_viewer','ctypes','wmi','win32api','hardware_monitor','chassis_identity','memory_identity'}:
            raise AssertionError('Forbidden dependency: '+fullname)
sys.meta_path.insert(0,Guard())
import accessory_art
assert accessory_art.cache_info()['entries']==0
assert len(accessory_art.choices()['cases'])==96
for kind,identity in [('case','hyte-y70'),('cooler','noctua-nh-d15-g2'),('psu','corsair-rm1000x-2024'),('fan','arctic-p12-pwm')]:
    assert accessory_art.art(kind,identity)['svg']
'''
        result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,capture_output=True,text=True,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__=='__main__':
    unittest.main()
