"""Primary fan capacities and selected real PSU lengths remain separate."""
import copy
import unittest
from unittest.mock import patch
from assembly_case_shrouds052 import apply_layout_anchors
from assembly_cooling import add_cooling
from assembly_fan_fit052 import check
from assembly_shroud_other052 import layout_reference
from chassis_catalog import get_case
from cooling_catalog import get_fan


class FanCaseLimits052Tests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(target,create=True,side_effect=AssertionError('Pure source conditions only')))
        self.case=get_case('inwin-dubili')
        self.dims=tuple(self.case['dimensions_mm'][k] for k in ('width','height','depth'))

    def spec(self,psu='corsair-rm1000x-2024',count=2,fan='arctic-p12-pwm'):
        return dict(case=self.case,auxiliary=dict(psu=dict(model_id=psu)),cooling=dict(cpu_cooler='none',
            case_fans=[dict(model=fan,mount='bottom',count=count,direction='intake')]))

    def anchors(self,spec):
        return apply_layout_anchors(dict(case_dimensions=self.dims),spec,layout_reference(self.case,self.dims))

    def test_real160mm_psu_keeps_two120_reference_fans_and_does_not_mutate_input(self):
        spec=self.spec();anchors=self.anchors(spec);before=copy.deepcopy((spec,anchors))
        meshes,meta=add_cooling((),spec,'eco',anchors)
        self.assertEqual(meta['rejected'],[]);self.assertEqual(len(meta['parts']),2)
        self.assertEqual(sum(m.rotor for m in meshes),2)
        row=meta['case_fan_limit_checks'][0]
        self.assertEqual(row['psu_length_mm'],160.);self.assertEqual(row['source_pdf_page'],4)
        self.assertFalse(row['full_fit_verified']);self.assertEqual((spec,anchors),before)

    def test_real190mm_psu_rejects_entire_two_fan_group_before_creating_any_mesh_or_wire(self):
        spec=self.spec('asus-rog-thor-1000p2');anchors=self.anchors(spec)
        meshes,meta=add_cooling((),spec,'eco',anchors)
        self.assertEqual(len(meshes),0);self.assertEqual(meta['parts'],[]);self.assertEqual(meta['fans'],[])
        self.assertEqual(meta['wire_anchors'],[])
        row=meta['rejected'][0];self.assertEqual(row['reason'],'case_fan_psu_length_limit')
        self.assertEqual(row['omitted_count'],2)
        check=meta['case_fan_limit_checks'][0];self.assertEqual(check['psu_length_mm'],190.)
        self.assertEqual(check['max_count_above_psu_length_threshold'],1)

    def test_real190mm_psu_one_fan_reference_is_retained(self):
        spec=self.spec('asus-rog-thor-1000p2',1);meshes,meta=add_cooling((),spec,'eco',self.anchors(spec))
        self.assertEqual(meta['rejected'],[]);self.assertEqual(len(meta['parts']),1)
        self.assertEqual(sum(m.rotor for m in meshes),1)

    def test_unknown_psu_length_is_explicit_and_never_a_complete_fit_certificate(self):
        spec=self.spec('');anchors=self.anchors(spec)
        row=check(anchors,spec,self.case,'bottom',get_fan('arctic-p12-pwm'),2)
        self.assertFalse(row['rejected']);self.assertIsNone(row['psu_length_mm'])
        self.assertEqual(row['state'],'selected_psu_dimension_unknown');self.assertFalse(row['full_fit_verified'])

    def test_source140_capacity_is_one_and_wrong_case_constraints_do_not_leak(self):
        spec=self.spec(fan='arctic-p14-pwm');anchors=self.anchors(spec)
        row=check(anchors,spec,self.case,'bottom',get_fan('arctic-p14-pwm'),2)
        self.assertTrue(row['rejected']);self.assertEqual(row['reason'],'unsupported_fan_mount')
        other=copy.deepcopy(spec);other['case']=get_case('lian-li-lancool-iii')
        row=check(anchors,other,self.case,'bottom',get_fan('arctic-p12-pwm'),2)
        self.assertTrue(row['rejected']);self.assertEqual(row['reason'],'case_fan_mount_reference_unavailable')

    def test_source_depth_limit_is_inclusive_and_never_scales_the_selected_fan(self):
        spec=self.spec();anchors=self.anchors(spec)
        anchors['case_fan_constraints']['bottom']['max_depth_mm']=32.
        for depth,rejected in ((32.,False),(33.,True)):
            model=dict(get_fan('arctic-p12-pwm'),depth_mm=depth)
            before=copy.deepcopy((anchors,spec,model))
            row=check(anchors,spec,self.case,'bottom',model,2)
            self.assertEqual(row['rejected'],rejected)
            self.assertEqual(row['source_max_depth_mm'],32.)
            self.assertFalse(row['full_fit_verified'])
            if rejected:self.assertEqual(row['reason'],'case_fan_depth_limit')
            self.assertEqual((anchors,spec,model),before)

    def test_missing_selected_fan_depth_is_unknown_and_stale_case_still_rejected(self):
        spec=self.spec();anchors=self.anchors(spec)
        anchors['case_fan_constraints']['bottom']['max_depth_mm']=32.
        model=dict(get_fan('arctic-p12-pwm'));model.pop('depth_mm')
        row=check(anchors,spec,self.case,'bottom',model,2)
        self.assertEqual(row['state'],'selected_fan_dimension_unknown');self.assertFalse(row['rejected'])
        anchors['case_fan_constraints']['bottom']['case_id']='hyte-y70'
        row=check(anchors,spec,self.case,'bottom',model,2)
        self.assertEqual(row['reason'],'case_fan_mount_reference_unavailable')


if __name__=='__main__':unittest.main()
