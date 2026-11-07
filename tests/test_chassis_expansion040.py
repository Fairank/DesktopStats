"""Pure 0.40 catalog and bounded shell tests; no hardware, Qt, windows or GL."""
import hashlib
import json
import math
import unittest
from urllib.parse import urlparse
from xml.etree import ElementTree

import chassis_catalog as catalog
from chassis_catalog_group_e import records
from assembly_case_exteriors040 import (FULL_SHELL_FLAGS, hardware_pose, replace_shell,
                                        torque_pose, TORQUE_TILT_DEGREES)
from assembly_geometry import Mesh, box


def rows():
    return records(catalog._case, catalog._mount, catalog._ATX, catalog._EATX)


def dimensions(row):
    return tuple(row['dimensions_mm'][key] for key in ('width','height','depth'))


class ChassisExpansion040Tests(unittest.TestCase):
    def test_original_eighty_records_are_canonically_unchanged(self):
        raw=json.dumps(list(catalog.CASES[:80]),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         '351f55cb5503fb584c6c9990418e78b309609e93092978b8a399d6deddd55c3b')

    def test_sixteen_distinct_products_increase_case_coverage_without_color_duplicates(self):
        added=rows()
        self.assertEqual(len(added),16)
        self.assertEqual(len({row['id'] for row in added}),16)
        self.assertFalse({row['id'] for row in added}&{row['id'] for row in catalog.CASES[:80]})
        self.assertEqual(len({row['brand'] for row in (*catalog.CASES[:80],*added)}),26)
        self.assertEqual(sum(row['brand']=='SAMA' for row in added),2)

    def test_primary_sources_dimensions_and_optional_cpu_fields_are_explicit(self):
        hosts={'www.sama.cn','www.jonsbo.com','www.antec.com','phanteks.com','phanteks.com.tw',
               'www.corsair.com','lian-li.com','www.coolermaster.com','www.fractal-design.com'}
        for row in rows():
            with self.subTest(case=row['id']):
                json.dumps(row,allow_nan=False)
                self.assertTrue(catalog.valid_case_id(row['id']))
                self.assertTrue(row['fit_note'])
                self.assertEqual(row['geometry_accuracy'],'schematic')
                self.assertTrue(all(50<value<800 for value in dimensions(row)))
                self.assertIn('max_cpu_cooler_height_mm',row)
                limit=row['max_cpu_cooler_height_mm']
                self.assertTrue(limit is None or 50<=limit<=220)
                for source in row['sources']:
                    self.assertEqual(urlparse(source).scheme,'https')
                    self.assertIn(urlparse(source).hostname,hosts)
                self.assertNotIn('installed_fans',row)
                for mount in row['fan_mounts']:
                    self.assertTrue(1<=mount['count']<=8)
                    self.assertTrue(set(mount['size_mm'])<={80,92,120,140,200})

    def test_axis_modes_and_protrusions_are_preserved(self):
        by_id={row['id']:row for row in rows()}
        expected={'sama-im-white':(185,303,391),'sama-new-mirror-white':(220,455,440),
                  'jonsbo-mod-5':(255,635,600),'jonsbo-n5':(355,350,403),'jonsbo-z20':(198,335,382),
                  'antec-torque':(285,644,621),'antec-striker':(230,410,420),
                  'phanteks-evolv-shift-xt':(173,244,371),'phanteks-xt-v3':(235,370,460),
                  'phanteks-evolv-x2':(228,588,454),'corsair-frame-4000d':(239,486,490),
                  'corsair-9000d-airflow':(307,698,698),'lian-li-v3000-plus':(279,674,678.5),
                  'lian-li-q58':(170,250,342),'cooler-master-cosmos-c700m':(306,651,650),
                  'fractal-ridge':(110,395.4,374)}
        for case_id,values in expected.items():
            self.assertEqual(dimensions(by_id[case_id]),values)

    def test_conflicting_or_configuration_dependent_fit_does_not_become_one_limit(self):
        by_id={row['id']:row for row in rows()}
        for case_id in ('sama-im-white','jonsbo-n5','jonsbo-z20','phanteks-xt-v3',
                        'corsair-frame-4000d','cooler-master-cosmos-c700m'):
            self.assertIsNone(by_id[case_id]['max_gpu_length_mm'])
        for case_id in ('sama-im-white','sama-new-mirror-white','jonsbo-z20','antec-striker','lian-li-v3000-plus'):
            self.assertIsNone(by_id[case_id]['max_cpu_cooler_height_mm'])
        self.assertIn('430mm',by_id['phanteks-xt-v3']['fit_note'])
        self.assertIn('400mm',by_id['phanteks-xt-v3']['fit_note'])
        self.assertIn('487',by_id['corsair-frame-4000d']['fit_note'])

    def test_eight_fan_positions_are_two_empty_columns_not_an_installed_stack(self):
        row=next(row for row in rows() if row['id']=='corsair-9000d-airflow')
        self.assertIn('dual_column_fan_rails',row['features'])
        self.assertEqual({m['position'] for m in row['fan_mounts'] if m['count']==8},{'front','top'})
        self.assertIn('双列',row['fit_note'])
        self.assertIn('最多4',row['fit_note'])

    def test_factory_records_are_detached_and_have_no_firmware_guesses(self):
        first,second=rows(),rows()
        first[0]['sources'].clear()
        self.assertTrue(second[0]['sources'])
        self.assertEqual(catalog.match_enclosure({'manufacturer':'SAMA','sku':"趣造 I'M"}),[])


class CaseExteriors040Tests(unittest.TestCase):
    def test_old_eighty_input_tuples_return_by_identity(self):
        base=(Mesh('old-case',box(2,3,4),(.3,.4,.5,1.)),)
        for case in catalog.CASES[:80]:
            self.assertIs(replace_shell(base,dimensions(case),case),base)
            self.assertIsNone(hardware_pose(case))

    def test_selected_hardware_is_never_replaced_or_scaled(self):
        gpu=Mesh('selected-gpu-pcb',box(110,1.6,200),(.2,.4,.3,1.),component='gpu')
        base=(Mesh('old-case',box(2,3,4),(.3,.4,.5,1.)),gpu)
        for case in rows():
            result=replace_shell(base,dimensions(case),case)
            self.assertIn(gpu,result)
            self.assertIs(next(m for m in result if m.component=='gpu'),gpu)
            if set(case['features'])&FULL_SHELL_FLAGS:
                self.assertFalse(any(m.name=='old-case' for m in result))
            self.assertFalse(any(m.rotor for m in result))
            self.assertFalse(any(m.component not in ('case','panel','gpu') for m in result))

    def test_low_detail_shells_have_bounded_batches_finite_vertices_and_unit_normals(self):
        for case in rows():
            for level,cap in (('eco',6000),('balanced',9000),('close',14000)):
                result=replace_shell((),dimensions(case),case,level)
                with self.subTest(case=case['id'],level=level):
                    self.assertLessEqual(len(result),8)
                    self.assertLess(sum(m.vertex_count//3 for m in result),cap)
                    for mesh in result:
                        self.assertEqual(len(mesh.vertices)%18,0)
                        self.assertTrue(all(math.isfinite(v) for v in mesh.vertices))
                        for start in range(0,len(mesh.vertices),6):
                            self.assertAlmostEqual(sum(v*v for v in mesh.vertices[start+3:start+6]),1.,places=6)

    def test_torque_reference_angle_is_shared_and_rigid(self):
        case=next(row for row in rows() if row['id']=='antec-torque')
        pose=hardware_pose(case)
        self.assertEqual(pose['reference_degrees'],TORQUE_TILT_DEGREES)
        self.assertEqual(pose['rotation_axis'],(1.,0.,0.))
        self.assertEqual(pose['pivot'],(0.,0.,0.))
        self.assertFalse(pose['angle_verified'])
        self.assertFalse(pose['dimensions_scaled'])
        top=torque_pose((0.,1.,0.),vector=True)
        self.assertGreater(top[1],0);self.assertGreater(top[2],0)
        self.assertAlmostEqual(sum(v*v for v in top),1.)
        a,b=(42.,-22.,19.),(-11.,80.,-70.)
        self.assertAlmostEqual(math.dist(a,b),math.dist(torque_pose(a),torque_pose(b)))
        self.assertEqual(torque_pose((0.,0.,0.)),(0.,0.,0.))

    def test_infinity_mirror_and_empty_rails_have_no_fake_readouts_or_fans(self):
        by_id={row['id']:row for row in rows()}
        shift=by_id['phanteks-evolv-shift-xt']
        result=replace_shell((),dimensions(shift),shift)
        self.assertTrue(any('infinity' in m.name for m in result))
        self.assertFalse(any('lcd' in m.name or m.rotor for m in result))
        nas=by_id['jonsbo-n5']
        result=replace_shell((),dimensions(nas),nas)
        self.assertEqual({m.component for m in result},{'case'})
        self.assertTrue(any('empty-tray' in m.name for m in result))


class CaseIllustrations040Tests(unittest.TestCase):
    def test_old_eighty_pens_are_untouched(self):
        from accessory_case_details040 import draw_case
        from accessory_art import _Pen
        for case in catalog.CASES[:80]:
            pen=_Pen('miniature');pen.parts.append('<g/>')
            self.assertFalse(draw_case(pen,case))
            self.assertEqual(pen.parts,['<g/>'])

    def test_new_structures_share_all_thirteen_styles_without_original_smile_or_devices(self):
        from accessory_case_details040 import draw_case
        from accessory_art import _Pen
        from top_bar_config import HARDWARE_ICON_STYLES
        touched=set()
        for case in rows():
            for style in HARDWARE_ICON_STYLES:
                pen=_Pen(style)
                handled=draw_case(pen,case)
                if not handled:
                    continue
                touched.add(case['id']);svg='<svg xmlns="http://www.w3.org/2000/svg">'+pen.finish()+'</svg>'
                root=ElementTree.fromstring(svg)
                self.assertTrue(root.tag.endswith('svg'))
                self.assertIn('original-reference',svg)
                self.assertNotIn('<image',svg)
                self.assertNotIn('<text',svg)
                self.assertNotIn('data-rotor',svg)
                self.assertNotIn('data-installed',svg)
                self.assertNotIn('NaN',svg)
                if style=='miniature':
                    self.assertNotIn('data-art-face',svg)
                if style in ('cartoon','notebook_smile'):
                    self.assertIn('data-art-face="smile"',svg)
        self.assertEqual(len(touched),9)

    def test_torque_drawing_uses_the_same_reference_transform_as_the_shell(self):
        import inspect
        import accessory_case_details040 as drawing
        source=inspect.getsource(drawing.draw_case)
        self.assertIn('from assembly_case_exteriors040 import torque_pose',source)
        self.assertNotIn('math.radians(12',source)


if __name__=='__main__':
    unittest.main()
