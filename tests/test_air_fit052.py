"""Actual over-height cooling is omitted whole, not visually scaled to fit."""
import copy
import unittest
from unittest.mock import patch
from assembly_air_fit052 import check
from assembly_case_shrouds052 import apply_layout_anchors
from assembly_cooling import add_cooling
from assembly_rear_bay_group_c052 import layout_reference
from chassis_catalog import get_case
from cooling_catalog import get_cooler


class AirFit052Tests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(target,create=True,side_effect=AssertionError('No device or worker')))
        self.case=get_case('deepcool-ch780')
        self.dims=tuple(self.case['dimensions_mm'][k] for k in ('width','height','depth'))

    def inputs(self,model):
        spec=dict(case=self.case,cooling=dict(cpu_cooler=model,case_fans=[]))
        anchors=apply_layout_anchors(dict(case_dimensions=self.dims),spec,layout_reference(self.case,self.dims))
        return spec,anchors

    def test_actual158mm_tower_exceeds132mm_case_limit_without_any_partial_cooler(self):
        spec,anchors=self.inputs('noctua-nh-u12a');before=copy.deepcopy((spec,anchors))
        meshes,meta=add_cooling((),spec,'eco',anchors)
        self.assertEqual(meshes,());self.assertEqual(meta['parts'],[]);self.assertEqual(meta['fans'],[])
        self.assertEqual(meta['wire_anchors'],[]);self.assertNotIn('cooler',meta)
        self.assertEqual(meta['rejected'][0]['reason'],'air_cooler_height_exceeds_case')
        row=meta['air_cooler_height_check'];self.assertEqual(row['selected_nominal_height_mm'],158.)
        self.assertEqual(row['source_max_height_mm'],132.);self.assertFalse(row['full_fit_verified'])
        self.assertEqual((spec,anchors),before)

    def test_actual37mm_cooler_keeps_its_original_full_scale_geometry(self):
        spec,anchors=self.inputs('noctua-nh-l9i-17xx')
        meshes,meta=add_cooling((),spec,'eco',anchors)
        old=dict(anchors);old.pop('case_air_cooler_constraints')
        original,_=add_cooling((),spec,'eco',old)
        self.assertEqual(meshes,original);self.assertTrue(meshes)
        self.assertEqual(meta['rejected'],[]);self.assertTrue(meta['parts'])
        self.assertEqual(meta['air_cooler_height_check']['selected_nominal_height_mm'],37.)

    def test_nominal_boundary_never_claims_tolerance_or_full_clearance(self):
        spec,anchors=self.inputs('noctua-nh-u12a')
        cooler=get_cooler('noctua-nh-u12a');cooler=copy.deepcopy(cooler)
        cooler['dimensions_mm']['height']=132.
        row=check(anchors,spec,self.case,cooler)
        self.assertFalse(row['rejected']);self.assertEqual(row['state'],'nominal_boundary_no_tolerance')
        self.assertFalse(row['full_fit_verified'])

    def test_unknown_dimension_is_explicit_and_wrong_case_source_is_rejected(self):
        spec,anchors=self.inputs('noctua-nh-u12a');cooler=get_cooler('noctua-nh-u12a')
        unknown=copy.deepcopy(cooler);unknown['dimensions_mm']['height']=None
        self.assertEqual(check(anchors,spec,self.case,unknown)['state'],'source_or_selected_height_unknown')
        other=copy.deepcopy(spec);other['case']=get_case('fractal-torrent-tg')
        self.assertEqual(check(anchors,other,self.case,cooler)['reason'],'air_cooler_case_reference_unavailable')

    def test_cases_without_a_source_rule_preserve_legacy_behavior(self):
        spec,anchors=self.inputs('noctua-nh-u12a');anchors.pop('case_air_cooler_constraints')
        self.assertIsNone(check(anchors,spec,self.case,get_cooler('noctua-nh-u12a')))

    def test_conflicting155_and165mm_manufacturer_claims_remain_explicit(self):
        case=get_case('jonsbo-tk2-black');dims=tuple(case['dimensions_mm'][k] for k in ('width','height','depth'))
        spec=dict(case=case);anchors=apply_layout_anchors({},spec,layout_reference(case,dims))
        row=check(anchors,spec,case,get_cooler('noctua-nh-u12a'))
        self.assertEqual(row['reason'],'air_cooler_height_source_conflict')
        self.assertEqual(row['manufacturer_values_mm'],(155.,165.));self.assertFalse(row['full_fit_verified'])


if __name__=='__main__':unittest.main()
