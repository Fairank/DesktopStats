"""Real crease recovery for four imported fans, without changing source PN."""
import unittest

from assembly_geometry import Mesh
from assembly_style import crease_edges, edge_batches


def pn(points, normal=(0.,0.,1.)):
    return tuple(value for point in points for value in (*point,*normal))


FOLD = pn(((0.,0.,0.),(1.,0.,0.),(0.,1.,0.),
           (1.,0.,0.),(0.,0.,0.),(0.,0.,1.)))
SHARED_FOLD = ((0.,0.,0.),(1.,0.,0.))


def ink_edges(batches):
    return {tuple(sorted((tuple(data[at:at+3]),tuple(data[at+6:at+9]))))
            for _,data in batches for at in range(0,len(data),12)}


class ReferenceFaceCreases054Tests(unittest.TestCase):
    def test_true_fold_survives_identical_corner_shading_normals(self):
        before = tuple(FOLD)
        self.assertNotIn(SHARED_FOLD,crease_edges(FOLD))
        self.assertIn(SHARED_FOLD,crease_edges(FOLD,geometric_normals=True))
        self.assertEqual(FOLD,before)

    def test_coplanar_weld_does_not_become_a_fake_diagonal(self):
        square = pn(((0.,0.,0.),(1.,0.,0.),(1.,1.,0.))) + pn(
            ((0.,0.,0.),(1.,1.,0.),(0.,1.,0.)),normal=(1.,0.,0.))
        diagonal = ((0.,0.,0.),(1.,1.,0.))
        self.assertIn(diagonal,crease_edges(square))
        real = crease_edges(square,geometric_normals=True)
        self.assertNotIn(diagonal,real)
        self.assertEqual(len(real),4)

    def test_zero_area_has_no_invented_edges_and_small_real_face_remains(self):
        collinear = pn(((0.,0.,0.),(1.,1.,1.),(2.,2.,2.)))
        self.assertEqual(crease_edges(collinear,geometric_normals=True),())
        tiny = pn(((0.,0.,0.),(.0001,0.,0.),(0.,.0001,0.)))
        self.assertEqual(len(crease_edges(tiny,geometric_normals=True)),3)

    def test_four_attested_draws_recover_real_fold_only_in_line_styles(self):
        expected = (
            ('whole-pc:CPU_COOLER:1','reference:CPU_COOLER','cooler'),
            ('whole-pc:CASE_FAN_01:0','reference:CASE_FAN_01','fans'),
            ('whole-pc:CASE_FAN_02:0','reference:CASE_FAN_02','fans'),
            ('whole-pc:CASE_FAN_03:0','reference:CASE_FAN_03','fans'),
        )
        styles = ('miniature','cartoon','notebook_color','notebook_line','sticker','papercut','outline','sketch')
        for name,part,component in expected:
            mesh = Mesh(name,FOLD,(.3,.4,.5,1.),component=component,part_id=part)
            for style in styles:
                with self.subTest(name=name,style=style):
                    self.assertEqual(SHARED_FOLD in ink_edges(edge_batches((mesh,),style)),
                                     style in ('notebook_line','outline','sketch'))
                    self.assertIs(mesh.vertices,FOLD)
                    self.assertFalse(mesh.rotor)

    def test_other_source_parts_and_factory_draws_keep_the_original_crease_path(self):
        excluded = (
            ('ordinary-fan','fans:case','fans'),
            ('whole-pc:CASE_FAN_01:0','fans:case','fans'),
            ('ordinary-fan','reference:CASE_FAN_01','fans'),
            ('whole-pc:CASE_FAN_01:0','reference:CASE_FAN_01','gpu'),
            ('whole-pc:CPU_COOLER:0','reference:CPU_COOLER','cooler'),
        )
        for name,part,component in excluded:
            with self.subTest(name=name,part=part,component=component):
                mesh = Mesh(name,FOLD,(.3,.4,.5,1.),component=component,part_id=part)
                self.assertNotIn(SHARED_FOLD,ink_edges(edge_batches((mesh,),'notebook_line')))


if __name__ == '__main__':
    unittest.main()
