"""Production local GPU exterior contracts; no Scene or Qt construction.

Synthetic known-size fixtures exercise the actual producer, boolean surfaces,
shared physical arrays and metadata merge. Actual baked-profile/full-card and
image evidence remains separate; no private candidate or old-version loader.
"""
import math
import unittest
from dataclasses import replace

from assembly_geometry import Mesh, box, gpu_plane, color
from assembly_detail import hollow_cover, chamfer_rect
from assembly_gpu_panels051 import partition
from assembly_gpu_exterior053 import front_cutouts, refine, N480, KEPLER


def appearance(identity=N480):
    return dict(id=identity, board_details=dict(dimensions_mm=dict(length=265., height=120., thickness=33.)))


def projected_front_covers(vertices, x, z):
    """Independent strict barycentric front-cap witness; no producer predicate."""
    for n in range(0, len(vertices), 18):
        tri=[vertices[n+k:n+k+3] for k in (0,6,12)]
        if not all(vertices[n+k+4]<-.99 for k in (0,6,12)):continue
        a,b,c=[(p[0],p[2]) for p in tri]
        cross=lambda p,q,r:(q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
        area=cross(a,b,c)
        if abs(area)<1e-12:continue
        sides=[cross(a,b,(x,z)),cross(b,c,(x,z)),cross(c,a,(x,z))]
        if all(t>1e-9 for t in sides) or all(t<-1e-9 for t in sides):return True
    return False


def contains_xz(triangle,point):
    def side(a,b,p):return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
    values=[side(triangle[n],triangle[(n+1)%3],point) for n in range(3)]
    return all(x>=-1e-12 for x in values) or all(x<=1e-12 for x in values)

def faces(shape,sign):
    result=[]
    for n in range(0,len(shape),18):
        if all(shape[n+k+4]*sign>.999 for k in (0,6,12)):
            result.append(tuple((shape[n+k],shape[n+k+2]) for k in (0,6,12)))
    return result


class GpuExterior053Tests(unittest.TestCase):
    def test_exact_cutout_is_fixed_not_selected_fan_or_cable_dependent(self):
        expected=front_cutouts(appearance(),265.,120.)
        self.assertEqual(len(expected),1)
        self.assertEqual(expected,front_cutouts(dict(appearance(),selected_fan='unrelated',cables=[1]),265.,120.))
        for identity in (KEPLER,'msi-n480gtx-lightning','msi-n470gtx','unknown'):
            self.assertEqual(front_cutouts(appearance(identity),265.,120.),())
        self.assertEqual(front_cutouts(dict(id=N480),265.,120.),())

    def test_kepler_reuses_fixed_ring_and_does_not_invent_or_rotate_it(self):
        ring=Mesh('gpu-fan-opening',box(2,2,2),color('#48535b'),component='gpu')
        rotor=Mesh('gpu-fan-rotor',(),color('#45515a'),component='gpu',rotor=True)
        bracket=Mesh('gpu-bracket',box(4,4,1),color('#999999'),component='gpu')
        out,meta=refine((ring,rotor,bracket),dict(gpu=dict(appearance=appearance(KEPLER))),'balanced')
        self.assertEqual(len(out),3)
        self.assertIs(out[0].vertices,ring.vertices)
        self.assertFalse(out[0].rotor)
        self.assertIs(out[1],rotor);self.assertIs(out[2],bracket)
        self.assertNotEqual(out[0].color,ring.color)
        self.assertTrue(meta['fixed_rim_geometry_preserved'])
        self.assertFalse(meta['blade_counts_changed'])

    def test_n480_opens_both_shell_and_paint_over_existing_source_window(self):
        cutouts=front_cutouts(appearance(),265.,120.)
        outer=chamfer_rect(265.,120.,2.)
        old=gpu_plane(hollow_cover(outer,(),33.))
        new=gpu_plane(hollow_cover(outer,(),33.,front_cutouts=cutouts))
        self.assertTrue(projected_front_covers(old,0.,-265.*.19))
        self.assertFalse(projected_front_covers(new,0.,-265.*.19))
        old_paint,_=partition((outer,),(),.3)
        new_paint,_=partition((outer,),(),.3,front_cutouts=cutouts)
        self.assertTrue(projected_front_covers(gpu_plane(old_paint[0]),0.,-265.*.19))
        self.assertFalse(projected_front_covers(gpu_plane(new_paint[0]),0.,-265.*.19))
        # A retained opaque corner supplies a positive material control.
        self.assertTrue(projected_front_covers(new,50.,100.))

    def test_n480_three_lods_retain_rotor_ports_and_bound_the_reference_stack(self):
        shell=Mesh('gpu-shroud',box(120.,33.,265.),color('#333333'),component='gpu')
        fins=Mesh('detail-gpu-heatsink-fins',box(80.,20.,.3),color('#aaaaaa'),component='gpu')
        rotor=Mesh('gpu-fan-rotor',(),color('#45515a'),component='gpu',rotor=True)
        port=Mesh('gpu-reference-port-dvi',box(25.,9.,3.),color('#888888'),(0.,0.,-130.),'gpu')
        source=(shell,fins,rotor,port)
        for level,count in (('eco',8),('balanced',16),('close',24)):
            out,meta=refine(source,dict(gpu=dict(appearance=appearance())),level)
            self.assertEqual(len(out),4)
            self.assertIs(out[0],shell);self.assertIs(out[2],rotor);self.assertIs(out[3],port)
            self.assertEqual(meta['fin_sampling_count'],count)
            self.assertTrue(meta['fin_count_is_sampling'])
            self.assertFalse(meta['manufacturer_dimensions_verified'])
            self.assertFalse(meta['blade_counts_changed'])
            self.assertEqual(len(out[1].vertices)//18,(count+4)*12)
            for n in range(0,len(out[1].vertices),6):
                x,y,z=out[1].vertices[n:n+3]
                self.assertTrue(abs(x)<=60. and abs(y)<=16.5 and abs(z)<=132.5)
                self.assertAlmostEqual(sum(t*t for t in out[1].vertices[n+3:n+6]),1.)

    def test_other_exact_skus_remain_the_same_objects(self):
        source=(Mesh('gpu-shroud',box(20.,20.,20.),color('#333333'),component='gpu'),)
        for identity in ('gigabyte-aorus-4090-master','leadtek-hurricane-4090-24g','asus-astral-5090','msi-rx480-8g-reference'):
            out,meta=refine(source,dict(gpu=dict(appearance=appearance(identity))),'balanced')
            self.assertIs(out,source);self.assertEqual(meta,{})

    def test_empty_cutouts_preserve_default_partition_and_bad_cutouts_fail(self):
        outer=chamfer_rect(265.,120.,2.)
        self.assertEqual(partition((outer,),(),.3),partition((outer,),(),.3,front_cutouts=()))
        for bad in ((((0.,0.),(math.inf,0.),(0.,1.)),), (((0.,0.),(0.,0.),(0.,0.)),)):
            with self.assertRaises(ValueError):partition((outer,),(),.3,front_cutouts=bad)


    def test_four_cross_supports_have_positive_area_facet_contact_not_floating(self):
        shell=Mesh('gpu-shroud',box(120.,33.,265.),color('#333333'),component='gpu')
        old=Mesh('detail-gpu-heatsink-fins',box(80.,20.,.3),color('#aaaaaa'),component='gpu')
        for level,count in (('eco',8),('balanced',16),('close',24)):
            out,meta=refine((shell,old),dict(gpu=dict(appearance=appearance())),level)
            bank=out[1].vertices
            stride=36*6  # each actual closed box has twelve triangles
            pieces=[bank[n:n+stride] for n in range(0,len(bank),stride)]
            self.assertEqual(len(pieces),count+4)
            for support in pieces[count:]:
                back=max(support[1::6]);back_faces=faces(support,1)
                for fin in pieces[:count]:
                    front=min(fin[1::6]);front_faces=faces(fin,-1)
                    self.assertAlmostEqual(back,front,places=12)
                    # No positive-volume Y overlap: adjacent exposed surfaces.
                    self.assertLessEqual(back-front,1e-12)
                    x0,x1=max(min(fin[0::6]),min(support[0::6])),min(max(fin[0::6]),max(support[0::6]))
                    z0,z1=max(min(fin[2::6]),min(support[2::6])),min(max(fin[2::6]),max(support[2::6]))
                    self.assertGreater((x1-x0)*(z1-z0),0.)
                    # Three non-collinear interior points lie on BOTH real
                    # opposing-normal cap triangulations, not just their AABBs.
                    witnesses=((x0+(x1-x0)*.25,z0+(z1-z0)*.25),
                               (x0+(x1-x0)*.75,z0+(z1-z0)*.25),
                               (x0+(x1-x0)*.25,z0+(z1-z0)*.75))
                    for point in witnesses:
                        self.assertTrue(any(contains_xz(tri,point) for tri in front_faces))
                        self.assertTrue(any(contains_xz(tri,point) for tri in back_faces))

    def test_each_lod_one_physical_array_set_is_shared_by_all_six_real_color_policies(self):
        from assembly_style import apply_colors
        shell=Mesh('gpu-shroud',box(120.,33.,265.),color('#333333'),component='gpu')
        fins=Mesh('detail-gpu-heatsink-fins',box(80.,20.,.3),color('#aaaaaa'),component='gpu')
        rim=Mesh('gpu-fan-opening',box(10.,1.,10.),color('#48535b'),(0.,-14.,80.),'gpu')
        rotor=Mesh('gpu-fan-rotor',(),color('#45515a'),(0.,-12.,80.),'gpu',rotor=True)
        port=Mesh('gpu-reference-port-dvi',box(25.,9.,3.),color('#888888'),(0.,0.,-130.),'gpu')
        source=(shell,fins,rim,rotor,port)
        for identity in (N480,KEPLER):
            for level in ('eco','balanced','close'):
                physical,_=refine(source,dict(gpu=dict(appearance=appearance(identity))),level)
                for style in ('miniature','cartoon','notebook_color','notebook_line','sticker','papercut'):
                    styled=apply_colors(physical,style)
                    self.assertEqual(len(styled),len(physical))
                    for a,b in zip(physical,styled):
                        self.assertIs(a.vertices,b.vertices)
                        self.assertEqual((a.name,a.component,a.position,a.rotor,a.direction,a.axis,a.part_id),
                                         (b.name,b.component,b.position,b.rotor,b.direction,b.axis,b.part_id))
                    self.assertFalse(any('face' in mesh.name or 'expression' in mesh.name for mesh in styled))


    def test_real_gpu_detail_metadata_merge_keeps_outer_sampling_flag(self):
        from assembly_detail import _gpu_detail
        facts=appearance()
        facts.update(style='gpu_blower',confidence='model',fan_count=1)
        spec=dict(gpu=dict(appearance=facts,fans=[],detail_polygons=[]))
        shell=Mesh('gpu-shroud',box(120.,33.,265.),color('#333333'),component='gpu')
        for level,count in (('eco',8),('balanced',16),('close',24)):
            # This calls the actual production consumer, not refine alone.
            # Duplicate fin_count_is_sampling via **exterior used to raise
            # TypeError here, so a helper-only success cannot satisfy it.
            completed,meta=_gpu_detail((shell,),spec,level)
            self.assertIs(meta['fin_count_is_sampling'],True)
            self.assertEqual(meta['heatsink_fins'],count)
            self.assertTrue(meta['exposed_front_fin_window'])
            self.assertEqual(meta['source_observed_fixed_cross_supports'],4)
            self.assertEqual(sum(m.name=='detail-gpu-heatsink-fins' for m in completed),1)


if __name__=='__main__':unittest.main()
