"""Complete RAM envelopes, not PCB heights, constrain source top rails."""
import copy
import unittest
from unittest.mock import patch

from assembly_case_shrouds052 import apply_layout_anchors
from assembly_radiator_fit052 import check,radiator_planes
from assembly_shroud_fractal052 import layout_reference
from chassis_catalog import get_case
from memory_appearance import appearance_for_memory
from memory_dimensions052 import enrich


def memory(part):
    return enrich(dict(count=1,modules=[dict(height_mm=31.,
        appearance=appearance_for_memory(model=part))]))


class RadiatorMemoryLimits052Tests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(target,create=True,side_effect=AssertionError('Pure source limits only')))

    def result(self,identity,ram,size=120,width=120):
        case=get_case(identity);dims=tuple(case['dimensions_mm'][k] for k in ('width','height','depth'))
        spec=dict(case=case,memory=ram)
        anchors=apply_layout_anchors(dict(case_dimensions=dims),spec,layout_reference(case,dims))
        return check(anchors,spec,dict(radiator_mm=dict(width=width)),'top',dict(size_mm=size))

    def test_exact_44mm_trident_is_rejected_by_35_and40_limits_without_changing_pcb(self):
        ram=memory('F4-3200C16D-16GTZR');before=copy.deepcopy(ram)
        for case_id,limit in (('fractal-north-mesh',35.),('fractal-define-7-compact-solid',40.)):
            row=self.result(case_id,ram)
            self.assertTrue(row['rejected']);self.assertEqual(row['reason'],'radiator_memory_height_exceeds_case_limit')
            self.assertEqual(row['model_ram_heights_mm'],(44.,));self.assertEqual(row['ram_height_limit_mm'],limit)
        self.assertEqual(ram,before);self.assertEqual(ram['modules'][0]['height_mm'],31.)
        self.assertIsNone(ram['modules'][0]['pcb_height_mm'])

    def test_primary_bare31_25_passes_nominal_reference_only(self):
        ram=memory('KVR32N22S8/16')
        for case_id in ('fractal-north-mesh','fractal-define-7-compact-solid'):
            row=self.result(case_id,ram)
            self.assertFalse(row['rejected']);self.assertEqual(row['state'],'reference_limits_checked')
            self.assertEqual(row['model_ram_heights_mm'],(31.25,));self.assertEqual(row['unknown_ram_heights'],0)
            self.assertFalse(row['full_fit_verified']);self.assertFalse(row['motherboard_vrm_and_io_height_checked'])

    def test_unknown_or_mixed_complete_envelopes_cannot_borrow_a_known_pcb_height(self):
        unknown=memory('unidentified memory');self.assertEqual(unknown['modules'][0]['height_mm'],31.)
        for ram in (unknown,dict(count=2,modules=memory('KVR32N22S8/16')['modules']+unknown['modules'])):
            row=self.result('fractal-north-mesh',ram)
            self.assertFalse(row['rejected']);self.assertEqual(row['state'],'reference_dimension_unknown')
            self.assertEqual(row['unknown_ram_heights'],1)
        # Direct old synthetic contracts remain clearly marked reference input.
        synthetic=self.result('fractal-north-mesh',dict(count=1,modules=[dict(height_mm=44.)]))
        self.assertTrue(synthetic['rejected'])
        hidden=memory('KVR32N22S8/16');hidden['count']=4
        self.assertEqual(self.result('fractal-north-mesh',hidden)['unknown_ram_heights'],3)

    def test_nominal34_9_plus_tolerance_is_not_a35mm_clearance_guarantee(self):
        row=self.result('fractal-north-mesh',memory('KF560C36BBEK2-32'))
        self.assertFalse(row['rejected']);self.assertEqual(row['model_ram_heights_mm'],(34.9,))
        self.assertEqual(row['state'],'reference_tolerance_overlap')
        self.assertTrue(row['nominal_height_tolerance_overlaps_limit']);self.assertFalse(row['full_fit_verified'])

    def test_derived_axis_mapping_stays_distinct_and_meshify_outer_rail_has_no_ram_restriction(self):
        ram=memory('AX5U6000C3016G-DCLARWH')
        self.assertEqual(ram['modules'][0]['total_height_status'],'derived_nominal')
        self.assertTrue(self.result('fractal-north-mesh',ram)['rejected'])
        outer=self.result('fractal-meshify-2-light-tg',ram)
        self.assertTrue(outer['source_lists_no_ram_height_restriction']);self.assertFalse(outer['rejected'])
        inner=self.result('fractal-meshify-2-light-tg',ram,size=140,width=140)
        self.assertTrue(inner['rejected']);self.assertEqual(inner['ram_height_limit_mm'],36.)

    def test_casefan_plane_is_untouched_and_radiator_rail_is_detached(self):
        case=get_case('fractal-north-mesh');dims=tuple(case['dimensions_mm'][k] for k in ('width','height','depth'))
        anchors=apply_layout_anchors({},dict(case=case),layout_reference(case,dims))
        planes={'top':{'position':(0.,200.,0.)},'front':{'position':(0.,0.,200.)}}
        before=copy.deepcopy((anchors,planes))
        selected=radiator_planes(anchors,planes,'top',dict(size_mm=120))
        self.assertIsNot(selected,planes);self.assertEqual(selected['front'],planes['front'])
        self.assertNotEqual(selected['top']['position'][0],planes['top']['position'][0])
        selected['top']['position']='edited detached copy'
        self.assertEqual((anchors,planes),before)
        self.assertIs(radiator_planes(anchors,planes,'front',dict(size_mm=120)),planes)


if __name__=='__main__':unittest.main()
