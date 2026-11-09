"""Pure envelope math preserves physical PCB and source contour identity."""
import copy
import math
import struct
import unittest
from unittest.mock import patch

from memory_geometry052 import layout
from memory_dimensions052 import enrich,records
from memory_appearance import appearance_for_memory

ZIG=[[-.02,.1],[.1,-.25],[.25,-.25],[.35,.02],[.46,-.18],[.7,-.25],[1.02,.1],[1.02,.8],[-.02,.8]]


class MemoryGeometry052Tests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,create=True,side_effect=AssertionError('Pure layout only')))

    def test_known44mm_rgb_keeps31mm_pcb_and_joins_the_reference_cap(self):
        m=dict(height_mm=31.,case_polygon=copy.deepcopy(ZIG),diffuser=True,
            total_height_mm=44.,total_height_status='primary',total_length_mm=135.,total_length_status='primary',
            total_thickness_mm=8.,total_thickness_status='primary',pcb_polygon=[[0,0],[1,0],[1,1],[0,1]])
        before=copy.deepcopy(m);value=layout(m)
        self.assertEqual(m,before);self.assertEqual(value['pcb_height_mm'],31.)
        self.assertEqual(value['pcb_width_mm'],133.35);self.assertEqual(value['pcb_thickness_mm'],1.2)
        self.assertEqual(value['cover_width_mm'],135.);self.assertEqual(value['cover_thickness_mm'],8.)
        self.assertEqual(value['cap_height_mm'],3.);self.assertEqual(value['cap_center_from_pcb_center_mm'],27.)
        top=max((.5-y)*31. for _,y in value['cover_polygon'])
        self.assertAlmostEqual(top,25.5)
        bottom=value['cap_center_from_pcb_center_mm']-1.5
        self.assertTrue(math.isclose(top,bottom,rel_tol=0.,abs_tol=1e-10))
        self.assertEqual(struct.pack('<f',top),struct.pack('<f',bottom))
        self.assertAlmostEqual(value['geometry_total_height_mm'],44.)
        self.assertTrue(value['geometry_matches_total_height']);self.assertTrue(value['total_height_applied'])
        self.assertFalse(value['cover_internal_cavity_modeled']);self.assertFalse(value['cap_height_verified'])
        self.assertFalse(value['cover_thickness_is_metal_sheet_measurement'])

    def test_source_notches_and_zigzags_keep_order_and_relative_shape(self):
        m=dict(case_polygon=copy.deepcopy(ZIG),total_height_mm=56.,total_height_status='primary',
               total_length_mm=135.,total_length_status='primary',diffuser=True)
        value=layout(m);polygon=value['cover_polygon'];self.assertEqual(len(polygon),len(ZIG))
        self.assertEqual(min(x for x,y in polygon),0.);self.assertEqual(max(x for x,y in polygon),1.)
        xs=(max(p[0] for p in ZIG)-min(p[0] for p in ZIG))
        ys=(56.-3.)/(31.*(1.-min(p[1] for p in ZIG)))
        for source,target in zip(ZIG,polygon):
            self.assertAlmostEqual(target[0],(source[0]-min(p[0] for p in ZIG))/xs)
            self.assertAlmostEqual(target[1]-1.,(source[1]-1.)*ys)
        self.assertGreater(polygon[3][1],polygon[2][1])
        self.assertGreater(polygon[3][1],polygon[4][1])
        self.assertEqual(value['required_polygon_margin'],2.)

    def test_primary_pcb_axes_override_legacy_while_total_axes_never_do(self):
        m=dict(height_mm=44.,length_mm=150.,pcb_height_mm=31.25,pcb_height_status='primary',
            pcb_length_mm=133.35,pcb_length_status='primary',pcb_thickness_mm=1.2,pcb_thickness_status='primary',
            total_height_mm=44.,total_height_status='primary',total_length_mm=140.,total_length_status='primary',
            total_thickness_mm=8.4,total_thickness_status='derived_nominal',case_polygon=ZIG,diffuser=True)
        value=layout(m)
        self.assertEqual((value['pcb_width_mm'],value['pcb_height_mm'],value['pcb_thickness_mm']),(133.35,31.25,1.2))
        self.assertEqual((value['cover_width_mm'],value['cover_thickness_mm']),(140.,8.4))
        self.assertTrue(all(value['known'][k] for k in ('pcb_width','pcb_height','pcb_thickness')))
        del m['pcb_height_status'];self.assertEqual(layout(m)['pcb_height_mm'],44.)
        self.assertEqual(m['height_mm'],44.)

    def test_unknown_dimensions_preserve_legacy_contour_cap_and_missing_fallback(self):
        m=dict(height_mm=32.,length_mm=134.,case_polygon=copy.deepcopy(ZIG),diffuser=True,
            total_height_mm=44.,total_height_status='unknown',total_thickness_mm=8.,total_thickness_status='unknown')
        value=layout(m)
        self.assertEqual(value['cover_polygon'],ZIG);self.assertIsNot(value['cover_polygon'],m['case_polygon'])
        self.assertEqual(value['cap_center_from_pcb_center_mm'],32.*.55)
        self.assertEqual(value['cover_thickness_mm'],3.2);self.assertEqual(value['cover_width_mm'],134.)
        self.assertFalse(value['total_height_applied']);self.assertIsNone(value['total_height_mm'])
        self.assertIsNone(value['geometry_matches_total_height'])
        self.assertFalse(value['cover_polygon_is_reference_fallback'])
        missing=layout(dict(diffuser=True))
        self.assertEqual(missing['cover_polygon'],[])
        self.assertEqual(missing['cap_center_from_pcb_center_mm'],31.*.55)

    def test_known_height_without_source_cover_uses_only_old_reference_rectangle(self):
        value=layout(dict(total_height_mm=44.,total_height_status='primary',diffuser=True))
        self.assertEqual(len(value['cover_polygon']),4);self.assertTrue(value['cover_polygon_is_reference_fallback'])
        self.assertTrue(value['total_height_applied']);self.assertTrue(value['geometry_matches_total_height'])
        self.assertAlmostEqual(max((.5-y)*31. for x,y in value['cover_polygon']),25.5)
        self.assertEqual(min(x for x,y in value['cover_polygon']),.02)
        self.assertEqual(max(x for x,y in value['cover_polygon']),.98)

    def test_bare_primary_registry_models_have_no_invented_spreader_or_rgb_strip(self):
        for part,short,pcb_h,pcb_w in (('KVR32N22S8/16',False,31.25,133.35),('KVR32S22S8/16',True,30.,69.6)):
            raw=dict(modules=[dict(appearance=appearance_for_memory(model=part,manufacturer='Kingston'),
                                  height_mm=31.,diffuser=True,case_polygon=copy.deepcopy(ZIG))])
            module=enrich(raw)['modules'][0];value=layout(module,short)
            self.assertEqual((value['pcb_height_mm'],value['pcb_width_mm']),(pcb_h,pcb_w))
            self.assertFalse(value['has_cover']);self.assertFalse(value['has_cap']);self.assertEqual(value['cap_height_mm'],0.)
            self.assertIsNone(value['cap_center_from_pcb_center_mm']);self.assertTrue(value['geometry_matches_total_height'])
            self.assertEqual(value['cover_polygon'],ZIG)
            if short:
                self.assertEqual(module['max_total_thickness_mm'],3.7)
                self.assertEqual(value['pcb_thickness_mm'],1.2);self.assertEqual(value['cover_thickness_mm'],3.2)

    def test_invalid_numbers_and_inconsistent_reference_pcb_do_not_shrink_to_total(self):
        value=layout(dict(height_mm=44.,total_height_mm=44.,total_height_status='primary',
                          diffuser=True,case_polygon=copy.deepcopy(ZIG)))
        self.assertEqual(value['pcb_height_mm'],44.);self.assertEqual(value['cover_polygon'],ZIG)
        self.assertEqual(value['cap_center_from_pcb_center_mm'],44.*.55)
        self.assertFalse(value['total_height_applied']);self.assertFalse(value['geometry_matches_total_height'])
        self.assertIn('total_height_below_pcb_and_reference_cap',value['issues'])
        for module in (None,False,{},dict(height_mm=True,length_mm=float('nan'),total_height_mm=float('inf'),total_height_status='primary'),
                       dict(pcb_height_mm=44.,pcb_height_status='derived_nominal')):
            value=layout(module)
            self.assertEqual(value['pcb_height_mm'],31.);self.assertEqual(value['pcb_width_mm'],133.35)
            self.assertTrue(math.isfinite(value['geometry_total_height_mm']))
        self.assertEqual(layout({},True)['pcb_height_mm'],30.)
        self.assertEqual(layout({},True)['pcb_width_mm'],69.6)

    def test_all27_whole_height_facts_calibrate_same_reference_without_borrowing_pcb(self):
        for record in records():
            module=dict(record,case_polygon=copy.deepcopy(ZIG))
            # Pure source-envelope control, not a replacement native profile.
            # Bare records use the exact bare flag; all other exteriors keep
            # the same non-RGB reference strip count in this mathematical test.
            if record['pcb_height_mm'] is not None:module['heat_spreader']=False
            value=layout(module,record['id']=='kingston-kvr32s22s8-16')
            self.assertEqual(value['pcb_height_mm'],record['pcb_height_mm'] or 31.)
            self.assertEqual(value['total_height_mm'],record['total_height_mm'])
            self.assertTrue(value['geometry_matches_total_height'],record['id'])
            self.assertFalse(value['cad_verified'])


if __name__=='__main__':unittest.main()
