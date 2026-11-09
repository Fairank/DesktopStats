"""Exact authored fan bracket, atomic groups, no invented motion or tach."""
import copy
import unittest
from unittest.mock import patch

from assembly_case_shrouds052 import apply_layout_anchors
from assembly_cooling import _authored_fan_plane,_mount_plane,add_cooling
from assembly_geometry import Mesh,box
from assembly_shroud_nzxt_lianli052 import layout_reference
from chassis_catalog import get_case

MOUNT='above_psu_shroud'
IDS={'fans:above-psu-shroud:'+str(i) for i in range(3)}


class AboveShroudConsumer052Tests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(target,create=True,side_effect=AssertionError('Pure bounded construction only')))
        self.case=get_case('lian-li-lancool-iii')
        self.dims=tuple(self.case['dimensions_mm'][k] for k in ('width','height','depth'))
        self.spec=dict(case=self.case,memory=dict(count=0),cooling=dict(case_fans=[
            dict(model='arctic-p12-pwm',mount=MOUNT,count=3,direction='intake')]))
        self.anchors=apply_layout_anchors(dict(case_dimensions=self.dims),self.spec,layout_reference(self.case,self.dims))

    def test_actual_three_reference_fans_have_safe_ids_and_unknown_rpm(self):
        before=copy.deepcopy((self.spec,self.anchors))
        meshes,meta=add_cooling((),self.spec,'eco',self.anchors)
        self.assertEqual(meta['rejected'],[])
        self.assertEqual({p['id'] for p in meta['parts']},IDS)
        self.assertEqual({m.part_id for m in meshes},IDS)
        self.assertEqual(sum(m.rotor for m in meshes),3)
        self.assertTrue(all(row['mount']==MOUNT for row in meta['parts']))
        self.assertTrue(all(row['rpm'] is None and row['rotation_default']=='static' for row in meta['fans']))
        self.assertEqual(meta['new_pollers'],0)
        self.assertEqual((self.spec,self.anchors),before)

    def test_bad_or_missing_authored_frame_is_refused_without_any_side_fallback(self):
        original=self.anchors['case_mount_planes'][MOUNT]
        variants=[None,{},dict(original,position=(0.,float('nan'),0.)),
                  dict(original,normal=(0.,0.,1.)),dict(original,up=(0.,-1.,0.)),
                  dict(original,span_mm=(True,400.)),dict(original,source_capacity_count=2)]
        for plane in variants:
            anchors=copy.deepcopy(self.anchors)
            anchors['case_mount_planes']={} if plane is None else {MOUNT:plane}
            with self.subTest(plane=plane):
                self.assertIsNone(_authored_fan_plane(MOUNT,anchors['case_mount_planes']))
                with self.assertRaises(ValueError):_mount_plane(MOUNT,self.dims,22.5,anchors['case_mount_planes'])
                meshes,meta=add_cooling((),self.spec,'eco',anchors)
                self.assertEqual(meshes,());self.assertEqual(meta['parts'],[])
                self.assertEqual(meta['rejected'][0]['reason'],'case_fan_mount_reference_unavailable')

    def test_gpu_swept_envelope_conflict_rejects_whole_group_and_retains_input_hardware(self):
        plane=self.anchors['case_mount_planes'][MOUNT]
        # A retained actual rigid body occupies the authored fan volume. The
        # group may not move that body, crop a fan, or quietly install two.
        gpu=Mesh('test-retained-gpu',box(160.,40.,400.),(.2,.3,.4,1.),
                 (plane['position'][0],plane['position'][1]+15.,0.),'gpu',part_id='gpu:0')
        original=copy.deepcopy(gpu);meshes,meta=add_cooling((gpu,),self.spec,'eco',self.anchors)
        self.assertEqual(meshes,());self.assertEqual(meta['parts'],[]);self.assertEqual(meta['fans'],[])
        row=meta['rejected'][0];self.assertEqual(row['reason'],'case_fan_clearance_conflict')
        self.assertEqual(row['omitted_count'],3);self.assertEqual(row['conflicting_parts'],['gpu:0'])
        self.assertEqual(gpu,original)

    def test_other_cases_and_140mm_or_four_fans_cannot_inherit_this_exact_reference(self):
        for case_id,model,count,reason in (('lian-li-lancool-207','arctic-p12-pwm',2,'case_fan_mount_reference_unavailable'),
                                   ('lian-li-lancool-207','arctic-p12-pwm',3,'unsupported_fan_mount'),
                                   ('lian-li-lancool-iii','arctic-p14-pwm',3,'unsupported_fan_mount'),
                                   ('lian-li-lancool-iii','arctic-p12-pwm',4,'unsupported_fan_mount')):
            spec=copy.deepcopy(self.spec);spec['case']=get_case(case_id)
            spec['cooling']['case_fans'][0].update(model=model,count=count)
            meshes,meta=add_cooling((),spec,'eco',self.anchors)
            self.assertEqual(meshes,());self.assertEqual(meta['parts'],[])
            self.assertEqual(meta['rejected'][0]['reason'],reason)

    def test_stale_exact_case_anchors_cannot_override_a_new_different_selected_case(self):
        spec=copy.deepcopy(self.spec);spec['case']=get_case('lian-li-lancool-207')
        anchors=dict(self.anchors,case=self.case)
        meshes,meta=add_cooling((),spec,'eco',anchors)
        self.assertEqual(len(meshes),0);self.assertEqual(meta['parts'],[])
        self.assertEqual(meta['rejected'][0]['reason'],'case_fan_mount_reference_unavailable')


if __name__=='__main__':unittest.main()
