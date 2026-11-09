"""Fixed source mounting faces preserve selected dimensions and handedness."""
import copy
import unittest
from unittest.mock import patch

from assembly_case_shrouds052 import apply_layout_anchors,remove_replaced_parts
from assembly_geometry import Mesh,box


ROTATED=((1.,0.,0.),(0.,0.,1.),(0.,-1.,0.))


class CasePoseContract052Tests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(target,create=True,side_effect=AssertionError('Pure mounting contract only')))
        self.spec=dict(auxiliary=dict(psu=dict(model_id='corsair-rm1000x-2024')))

    def test_fixed_upper_front_faces_locate_actual_rotated_psu_without_rescaling(self):
        anchors=dict(case_mount_planes=dict(top=dict(existing=True)))
        layout=dict(psu=dict(basis=ROTATED,ceiling_y_mm=200.,front_z_mm=238.,center_x_mm=0.))
        before=copy.deepcopy((anchors,self.spec,layout))
        out=apply_layout_anchors(anchors,self.spec,layout)
        self.assertEqual(out['psu']['world_dimensions_mm'],(150.,160.,86.))
        self.assertEqual(out['psu']['position'],(0.,120.,195.))
        self.assertEqual(out['psu']['basis'],ROTATED)
        self.assertTrue(out['psu']['reference_only']);self.assertFalse(out['psu']['placement_verified'])
        self.assertEqual((anchors,self.spec,layout),before)

    def test_existing_floor_and_rear_contract_preserves_lower_psu_placement(self):
        out=apply_layout_anchors({},self.spec,dict(psu=dict(basis=ROTATED,
            floor_y_mm=-200.,rear_z_mm=-230.,boundary_x_mm=100.,align_x='left')))
        self.assertEqual(out['psu']['position'],(175.,-120.,-187.))

    def test_competing_or_nonfinite_mounting_faces_never_partly_apply_psu_pose(self):
        base=dict(basis=ROTATED,ceiling_y_mm=200.,front_z_mm=238.,center_x_mm=0.)
        for changed in (dict(floor_y_mm=-200.),dict(rear_z_mm=-230.),
                        dict(ceiling_y_mm=float('nan')),dict(front_z_mm=True)):
            layout=dict(psu=dict(base,**changed))
            out=apply_layout_anchors({},self.spec,layout)
            self.assertNotIn('psu',out)

    def test_reflection_scaling_shear_and_nonfinite_basis_are_refused(self):
        bases=(((1,0,0),(0,1,0),(0,0,-1)),((2,0,0),(0,1,0),(0,0,1)),
               ((1,.1,0),(0,1,0),(0,0,1)),((1,0,0),(0,float('inf'),0),(0,0,1)))
        for basis in bases:
            out=apply_layout_anchors({},self.spec,dict(psu=dict(basis=basis,
                ceiling_y_mm=200.,front_z_mm=238.,center_x_mm=0.)))
            self.assertNotIn('psu',out)

    def test_unknown_psu_keeps_detached_source_planes_but_invents_no_body(self):
        layout=dict(mount_planes=dict(bottom=dict(position=(0,-225,0))),
            psu=dict(basis=ROTATED,ceiling_y_mm=200.,front_z_mm=238.,center_x_mm=0.))
        spec=dict(auxiliary=dict(psu=dict(model_id='unknown-psu')))
        out=apply_layout_anchors({},spec,layout)
        self.assertNotIn('psu',out)
        out['case_mount_planes']['bottom']['position']=(9,9,9)
        self.assertEqual(layout['mount_planes']['bottom']['position'],(0,-225,0))

    def test_explicit_replacement_flags_remove_only_the_named_generic_case_bodies(self):
        def mesh(name,component='case'):
            return Mesh(name,box(1,1,1),(1,1,1,1),component=component)
        rows=[mesh('case-bottom'),mesh('case-foot'),mesh('rear-chamber-shroud'),
              mesh('case-foot','psu'),mesh('case-depth-rail'),mesh('case-bottom','panel')]
        out=remove_replaced_parts(rows,dict(replaces_case_bottom=True,replaces_case_feet=True,
            replaces_rear_chamber_shroud=True))
        self.assertEqual(out,rows[3:]);self.assertEqual(len(rows),6)
        self.assertEqual(remove_replaced_parts(rows,dict(replaces_case_bottom=1,replaces_case_feet='yes')),rows)


if __name__=='__main__':unittest.main()
