"""Same physical fan layers stay distinguishable in the retained pastel styles."""
import unittest
from assembly_geometry import Mesh,box
from assembly_style import apply_colors


class GpuMaterialLayerTests(unittest.TestCase):
    def test_gpu_cover_ink_cancels_partition_diagonals_below_the_mesh_budget(self):
        from assembly_geometry import _quad
        from assembly_style import edge_batches
        vertices=[]
        for left,right,bottom,top in ((0,10,0,20),(10,20,0,10),(10,20,10,20)):
            _quad(vertices,(left,bottom,0),(right,bottom,0),(right,top,0),(left,top,0))
        mesh=Mesh('gpu-cover-panel',tuple(vertices),(.2,.3,.4,1.),component='gpu')
        rows=edge_batches((mesh,),'cartoon');self.assertEqual(len(rows),1)
        values=rows[0][1]
        edges={tuple(sorted((tuple(values[n:n+3]),tuple(values[n+6:n+9])))) for n in range(0,len(values),12)}
        self.assertEqual(edges,{((0,0,0),(0,20,0)),((0,0,0),(20,0,0)),
                                ((0,20,0),(20,20,0)),((20,0,0),(20,20,0))})

    def test_actual_clipped_cover_keeps_only_real_cap_boundaries_and_side_creases(self):
        import math
        from assembly_gpu_panels051 import partition
        from assembly_style import crease_edges
        from test_gpu_panels051 import cap_rows,inside
        lower=((-45,-24),(45,-24),(45,24),(-45,24))
        later=((-12,-20),(35,-20),(35,-4),(5,-4),(5,20),(-12,20))
        parts,_=partition((lower,later),((0.,0.,5.),),.3)
        vertices=parts[0];triangles=cap_rows(vertices)
        edges=crease_edges(vertices,repair_under_cap=True)
        self.assertTrue(any(abs(a[2]-b[2])>.2 for a,b in edges),'Keep real plate thickness creases')
        cap_count=0
        for a,b in edges:
            if abs(a[2]-.15)>1e-6 or abs(b[2]-.15)>1e-6:continue
            dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
            if length<.01:continue
            mid=((a[0]+b[0])/2,(a[1]+b[1])/2);eps=.001
            first=(mid[0]-dy/length*eps,mid[1]+dx/length*eps)
            second=(mid[0]+dy/length*eps,mid[1]-dx/length*eps)
            material=lambda point:any(inside(point,t) for t in triangles)
            self.assertNotEqual(material(first),material(second),'A flat-cap internal triangulation seam is not hardware ink')
            cap_count+=1
        self.assertGreaterEqual(cap_count,8,'Keep real outer and concave boundaries')
        # This hole lies wholly inside the upper paint, not the lower region.
        # Check its actual upper rim rather than expecting it on both layers.
        mouth=[]
        for a,b in crease_edges(parts[1],repair_under_cap=True):
            if (abs(a[2]-.15)<1e-6 and abs(b[2]-.15)<1e-6
                    and abs(math.hypot(*a[:2])-5)<1e-4 and abs(math.hypot(*b[:2])-5)<1e-4):
                mouth.append((a,b))
        self.assertGreaterEqual(len(mouth),18,'Keep the real fan aperture rim')

    def test_real_dark_rotor_recess_and_hub_keep_distinct_palette_layers(self):
        vertices=box(1,2,3)
        meshes=tuple(Mesh(name,vertices,(.12,.13,.14,.8),component='gpu',rotor=rotor)
                     for name,rotor in (('gpu-shroud',False),('gpu-fan-rotor',True),
                                        ('gpu-fan-recess',False),('gpu-fan-hub',False)))
        luminance=lambda color:sum(c*w for c,w in zip(color,(.2126,.7152,.0722)))
        for style in ('cartoon','notebook_color','notebook_smile','sticker'):
            with self.subTest(style=style):
                painted=apply_colors(meshes,style)
                self.assertEqual(len({m.color for m in painted}),4)
                shroud,rotor,recess,hub=map(lambda m:luminance(m.color),painted)
                self.assertGreater(rotor-shroud,.12)
                self.assertGreater(shroud-recess,.08)
                self.assertGreater(rotor-hub,.12)
                for before,after in zip(meshes,painted):
                    self.assertIs(after.vertices,before.vertices)
                    self.assertEqual(after.position,before.position)
                    self.assertEqual(after.rotor,before.rotor)
                    self.assertEqual(after.color[3],.8)

    def test_original_line_other_materials_and_static_unknown_disc_keep_existing_treatment(self):
        vertices=box(1,2,3)
        meshes=(Mesh('gpu-fan-rotor',vertices,(.1,.2,.3,1.),component='gpu',rotor=True),)
        self.assertEqual(apply_colors(meshes,'miniature'),meshes)
        from assembly_style import paint_color
        for style in ('notebook_line','sketch','outline','papercut','solid','soft','inkwash'):
            # Existing explicit cut-paper/solid rotor tints are retained too.
            baseline=apply_colors((Mesh('source',vertices,meshes[0].color,component='gpu',rotor=True),),style)[0]
            self.assertEqual(apply_colors(meshes,style)[0].color,baseline.color)
        for name,component in (('gpu-fan-unreviewed-disc','gpu'),('gpu-fan-recess','case'),('source','gpu')):
            mesh=Mesh(name,vertices,(.1,.2,.3,1.),component=component)
            self.assertEqual(apply_colors((mesh,),'cartoon')[0].color,paint_color(mesh.color,'cartoon',component))


if __name__=='__main__':unittest.main()
