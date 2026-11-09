"""Actual optional-pack/getter/art/geometry integration without device access.

All stores are temporary. These tests inspect actual SVG source and CPU mesh
data; the associated private visual proof uses Qt's software rasterizer.
"""
import copy
import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
import accessory_art
import cooling_catalog
import hardware_packs
from hardware_packs import PackStore,make_pack
from tools.export_cooling_packs045 import pack_models
from assembly_cooling import add_cooling
from assembly_style import apply_model_styles
from assembly_detail import TRIANGLE_BUDGETS

ANCHORS=dict(cpu=dict(position=(0.,0.,0.),normal=(0.,0.,1.),up=(0.,1.,0.)),
             case_dimensions=(800.,900.,900.))
CENTRE=('noctua-nh-d12l','thermalright-pa120-mini-black',
        'thermalright-silver-soul135','deepcool-assassin4s')
LOW=('noctua-nh-l9x65','bequiet-pure-rock-lp','deepcool-an400')


class CoolingRenderIntegration045Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=TemporaryDirectory(prefix='desktopstats-cooling045-')
        cls.root=Path(cls.folder.name);cls.library=pack_models()
        cls.store=PackStore(cls.root/'profile'/'hardware-packs')
        cls.sources={}
        for kind,rows in cls.library.items():
            source=cls.root/(kind+'.dspack')
            source.write_bytes(make_pack('test-'+kind+'-045','Private integration '+kind,rows,kind=kind))
            cls.store.install(source);cls.sources[kind]=source
        cls.patcher=patch.object(hardware_packs,'_store',cls.store);cls.patcher.start()

    @classmethod
    def tearDownClass(cls):
        accessory_art.clear_cache();cls.patcher.stop();cls.folder.cleanup()

    def scene(self,identity,level='balanced',kind='cooler'):
        cooling=dict(cpu_cooler=identity) if kind=='cooler' else dict(case_fans=[dict(model=identity,mount='front',count=1,direction='intake')])
        return add_cooling((),dict(cooling=cooling),level,copy.deepcopy(ANCHORS))

    def test_real_three_kind_archives_and_runtime_getters(self):
        from liquid_cooling_catalog044 import get_radiator
        self.assertEqual(len(self.library['fan']),40)
        self.assertEqual(len(self.library['cooler']),23)
        self.assertTrue(self.library['radiator'])
        for kind,rows in self.library.items():
            getter=dict(fan=cooling_catalog.get_fan,cooler=cooling_catalog.get_cooler,radiator=get_radiator)[kind]
            for row in rows:
                self.assertEqual(getter(row['id']),row['reference'])
        self.assertEqual(self.store.memory_status()['persistent_meshes'],0)
        self.assertEqual(self.store.memory_status()['background_workers'],0)

    def test_all_819_svg_variants_keep_model_identity_rotor_and_leaf_counts(self):
        count=0
        for kind in ('fan','cooler'):
            for model in self.library[kind]:
                row=model['reference']
                for style in accessory_art.STYLES:
                    with self.subTest(kind=kind,id=row['id'],style=style):
                        art=accessory_art.art(kind,row['id'],style)
                        self.assertEqual(art['id'],row['id'])
                        self.assertEqual(art['style'],style)
                        self.assertEqual(len(art['rotors']),1 if kind=='fan' else row['fan_count'])
                        ET.fromstring(art['svg'])
                        self.assertEqual(art['original_face'],'smile' if style in ('cartoon','notebook_smile') else 'none')
                        for rotor in art['rotors']:
                            root=ET.fromstring(rotor['svg'])
                            leaves=[x for x in root.iter() if 'data-leaf' in x.attrib]
                            numbers=[int(x.attrib['data-blade-count']) for x in root.iter() if 'data-blade-count' in x.attrib]
                            self.assertEqual(len(numbers),1)
                            self.assertEqual(len(leaves),numbers[0])
                            if kind=='fan':self.assertEqual(len(leaves),row['blades'])
                            self.assertTrue(all(math.isfinite(rotor[k]) for k in ('x','y','width','height','direction')))
                            if rotor.get('affine'):self.assertTrue(all(math.isfinite(v) for v in rotor['affine']))
                        count+=1
        self.assertEqual(count,819)

    def test_bundled_factory_fan_survives_without_separate_fan_pack(self):
        store=PackStore(self.root/'cooler-only'/'hardware-packs');store.install(self.sources['cooler'])
        ids=('noctua-nh-d12l','corsair-h170i-elite-lcd-xt','nzxt-kraken-elite240-rgb-2023')
        before={id:accessory_art.art('cooler',id,'miniature')['svg'] for id in ids}
        with patch.object(hardware_packs,'_store',store):
            for id in ids:
                self.assertEqual(accessory_art.art('cooler',id,'miniature')['svg'],before[id])
                meshes,meta=self.scene(id)
                self.assertFalse(meta['rejected'])
                expected=cooling_catalog.get_cooler(id)
                self.assertEqual([f['model_id'] for f in meta['fans']],[expected['fan_model']]*expected['fan_count'])

    def test_central_fans_really_fit_between_both_fin_banks_at_three_lods(self):
        for id in CENTRE:
            for level in ('eco','balanced','close'):
                with self.subTest(id=id,level=level):
                    meshes,meta=self.scene(id,level)
                    self.assertFalse(meta['rejected'])
                    self.assertEqual(len(meta['fans']),1)
                    fan=meta['fans'][0];self.assertAlmostEqual(fan['position'][0],0.)
                    # With the common fixture local depth is world -X. A clear
                    # central gap is tested in the actual mesh, not a row flag.
                    fins=next(m for m in meshes if m.name=='cooler-tower-fins')
                    depth=cooling_catalog.get_cooler(id).get('fan_reference_depth_mm',25)
                    xs=[fins.vertices[i]+fins.position[0] for i in range(0,len(fins.vertices),6)]
                    self.assertTrue(any(x<0 for x in xs) and any(x>0 for x in xs))
                    self.assertGreater(min(abs(x) for x in xs),depth/2)
                    self.assertLess(meta['triangle_count'],TRIANGLE_BUDGETS[level])

    def test_new_low_profiles_have_horizontal_fan_and_sku_specific_height(self):
        for id in LOW:
            art=accessory_art.art('cooler',id,'miniature')
            self.assertIn('horizontal-low-profile-reference',art['body_svg'])
            self.assertEqual(len(art['rotors'][0]['affine']),6)
            self.assertNotIn('data-art-face',art['svg'])
            row=cooling_catalog.get_cooler(id);meshes,meta=self.scene(id)
            fan=meta['fans'][0]
            self.assertEqual(fan['axis'],(0.,0.,1.))
            depth=row.get('fan_reference_depth_mm') or cooling_catalog.get_fan(row['fan_model'])['depth_mm']
            self.assertAlmostEqual(fan['position'][2]+depth/2,row['dimensions_mm']['height'])
        _,meta=self.scene('noctua-nh-l12sx77')
        self.assertEqual(meta['fans'][0]['diameter_mm'],120)
        self.assertEqual(meta['fans'][0]['axis'],(0.,0.,1.))
        self.assertLess(meta['fans'][0]['position'][2]+7.5,55)

    def test_assassin_shell_and_corsair_screen_are_static_actual_parts(self):
        art=accessory_art.art('cooler','deepcool-assassin4s','miniature')
        root=ET.fromstring(art['foreground_svg'])
        vents=[x for x in root.iter() if x.attrib.get('data-reference-vent-samples')=='12']
        self.assertEqual(len(vents),1)
        self.assertEqual(vents[0].attrib.get('fill-rule'),'evenodd')
        self.assertEqual(vents[0].attrib['d'].count('M'),13)
        meshes,meta=self.scene('deepcool-assassin4s')
        self.assertEqual(meta['fans'][0]['diameter_mm'],140)
        for id in ('corsair-h100i-elite-lcd-xt','corsair-h170i-elite-lcd-xt'):
            meshes,meta=self.scene(id)
            names={m.name for m in meshes}
            self.assertIn('cooler-corsair-lcd-rounded-pedestal',names)
            self.assertIn('cooler-corsair-blank-circular-screen',names)
            self.assertFalse(any(m.rotor for m in meshes if 'corsair' in m.name))

    def test_ft14_white_window_is_static_and_only_in_front_plane(self):
        meshes,meta=self.scene('deepcool-ft14',kind='fan')
        window=next(m for m in meshes if m.name.endswith('-fixed-white-bearing-window'))
        self.assertFalse(window.rotor)
        fan=meta['fans'][0]
        points=[tuple(window.vertices[i+k]+window.position[k]-fan['position'][k] for k in range(3)) for i in range(0,len(window.vertices),6)]
        self.assertTrue(all(sum(point[k]*fan['axis'][k] for k in range(3))>0 for point in points))
        self.assertFalse(any('rgb' in m.name for m in meshes))
        art=accessory_art.art('fan','deepcool-ft14','miniature')
        self.assertIn('data-light="fixed-white"',art['foreground_svg'])
        self.assertNotIn('stationary-front-bearing-reference',art['rotors'][0]['svg'])

    def test_verified_pack_hole_pitch_reaches_the_actual_svg_frame(self):
        for id,axes in (('arctic-p9-pwm-pst',(82.5,82.5)),
                        ('fractal-prisma-al14-pwm',(125,125)),
                        ('noctua-nf-a12x25r-pwm',(93,83))):
            row=cooling_catalog.get_fan(id);holes=accessory_art._fan_holes(row)
            self.assertEqual(len(holes),4)
            width=row['width_mm'];height=row['size_mm']
            self.assertAlmostEqual((max(p[0] for p in holes)-min(p[0] for p in holes))*width,axes[0])
            self.assertAlmostEqual((max(p[1] for p in holes)-min(p[1] for p in holes))*height,axes[1])

    def test_geometry_styles_share_physical_arrays_and_do_not_create_readings(self):
        for id in ('noctua-nh-l12sx77','deepcool-assassin4s'):
            meshes,meta=self.scene(id)
            for style in accessory_art.STYLES:
                styled,policy=apply_model_styles(meshes,style,{},ANCHORS['case_dimensions'],{'front':'open'})
                self.assertEqual(len(styled),len(meshes))
                for a,b in zip(meshes,styled):
                    self.assertIs(a.vertices,b.vertices)
                    self.assertEqual((a.position,a.axis,a.part_id,a.rotor),(b.position,b.axis,b.part_id,b.rotor))
            self.assertEqual(meta['new_pollers'],0)
            self.assertFalse(meta['automatic_detection'])
            self.assertTrue(all(f['rpm'] is None and f['rotation_default']=='static' for f in meta['fans']))


if __name__=='__main__':unittest.main()
