"""Pure source-layer controls for the fixed Leadtek front frame.

Synthetic bounded fixtures exercise clipping, normal/depth constraints and
shared style arrays; actual retail profiles and installed fit are separate QA.
"""
import copy
import math
import struct
import unittest

STYLES=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')

def _encoded(values):return struct.pack('<'+str(len(values))+'f',*values)
def _dot(a,b):return sum(x*y for x,y in zip(a,b))
def _sub(a,b):return tuple(x-y for x,y in zip(a,b))
def _cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def _cap_contains(vertices,point):
    # Independent triangle test; no producer polygon/clipping helper.
    for n in range(0,len(vertices),18):
        if vertices[n+5]<.999:continue
        a,b,c=(vertices[n+k:n+k+2] for k in (0,6,12));x,y=point
        signs=[(q[0]-p[0])*(y-p[1])-(q[1]-p[1])*(x-p[0]) for p,q in ((a,b),(b,c),(c,a))]
        if min(signs)>=-1e-10 or max(signs)<=1e-10:return True
    return False
def _inside(vertices,position,point):
    votes=[]
    for direction in ((1.,.271,.193),(.137,1.,.313),(.263,.419,1.)):
        hits=[]
        for n in range(0,len(vertices),18):
            a,b,c=(tuple(vertices[n+k+j]+position[j] for j in range(3)) for k in (0,6,12))
            e1,e2=_sub(b,a),_sub(c,a);p=_cross(direction,e2);det=_dot(e1,p)
            if abs(det)<1e-12:continue
            s=_sub(point,a);u=_dot(s,p)/det
            if u<0 or u>1:continue
            q=_cross(s,e1);v=_dot(direction,q)/det
            if v<0 or u+v>1:continue
            t=_dot(e2,q)/det
            if t>1e-9 and not any(abs(t-old)<1e-8 for old in hits):hits.append(t)
        votes.append(len(hits)%2==1)
    return all(votes)

class TestLeadtekFixedX053(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import assembly_gpu_panels051 as panels
        import assembly_gpu_exterior053 as exterior
        cls.panels=panels;cls.exterior=exterior
        cls.gpu=dict(appearance=dict(id='leadtek-hurricane-4090-24g'),fans=[{'blades':9},{'blades':None},{'blades':9}])
        # Explicit synthetic layering controls; these are not claimed to be
        # the curved, QQml-baked retail contours.
        cls.polys=(((-4.,-1.),(4.,-1.),(4.,1.),(-4.,1.)),
                   ((-.3,-2.),(.3,-2.),(.3,2.),(-.3,2.)),(),())
        cls.holes=((-3.,0.,.8),(0.,0.,.8),(3.,0.,.8))

    def reference(self,holes=None):
        return self.exterior.fixed_front_layers(self.gpu,4,self.holes if holes is None else holes)

    def fixed(self,depths=None):
        info=self.reference()
        return self.panels.partition(self.polys,self.holes,.3,segments=20,
            layer_fan_indices=info['fan_indices'],layer_depths=depths or info['depths'])[0]

    def test_exact_source_only_and_unknown_bad_geometry_failclosed(self):
        self.assertEqual(self.exterior.fixed_front_layers({'appearance':{'id':'other'}},4,self.holes),{})
        self.assertEqual(self.exterior.fixed_front_layers(self.gpu,3,self.holes),{})
        self.assertEqual(self.reference((self.holes[0],self.holes[0],self.holes[2])),{})
        self.assertEqual(self.reference((self.holes[0],(0.,0.,float('nan')),self.holes[2])),{})
        self.assertEqual(self.reference((self.holes[0],self.holes[2])),{})

    def test_source_two_layers_and_sorted_middle_preserve_other_two_holes(self):
        r=self.reference((self.holes[2],self.holes[0],self.holes[1]))
        self.assertEqual(r['fan_indices'],((0,1),(0,1),(0,1,2),(0,1,2)))
        self.assertEqual(r['metadata']['fixed_x_center_fan_index'],2)
        self.assertEqual(r['metadata']['fixed_x_source_layer_indices'],(0,1))
        self.assertEqual(r['depths'],(.2,.2,.3,.3));self.assertEqual(r['center_offsets'],(.1,.1,.2,.2))
        self.assertFalse(r['metadata']['fixed_x_manufacturer_clearance_verified'])

    def test_default_and_explicit_full_apertures_are_byte_exact(self):
        for segments in (12,20,32):
            baseline=self.panels.partition(self.polys,self.holes,.3,segments=segments)
            full=tuple(tuple(range(len(self.holes))) for _ in self.polys)
            for result in (self.panels.partition(self.polys,self.holes,.3,segments=segments,layer_fan_indices=None,layer_depths=None),
                           self.panels.partition(self.polys,self.holes,.3,segments=segments,layer_fan_indices=full,layer_depths=(.3,)*len(self.polys))):
                self.assertEqual(result,baseline)
                self.assertEqual(tuple(map(_encoded,result[0])),tuple(map(_encoded,baseline[0])))

    def test_center_frame_is_real_material_and_outer_bays_stay_open(self):
        fixed=self.fixed();baseline=self.panels.partition(self.polys,self.holes,.3,segments=20)[0]
        self.assertTrue(any(_cap_contains(v,(.04,.03)) for v in fixed))
        self.assertFalse(any(_cap_contains(v,(.04,.03)) for v in baseline))
        for u in (-3.,3.):
            for angle in range(0,360,30):
                point=(u+.55*math.cos(math.radians(angle)),.55*math.sin(math.radians(angle)))
                self.assertFalse(any(_cap_contains(v,point) for v in fixed),point)

    def test_thin_frame_hub_separation_and_naive_depth_positive_control(self):
        from assembly_geometry import gpu_plane,ring
        fixed=self.fixed();old_depth=self.fixed((.3,.3,.3,.3))
        hub=gpu_plane(ring(.4,0.,2.7,segments=20));hub_position=(0.,1.6,0.)
        minimum=min(hub[n+1]+hub_position[1] for n in range(0,len(hub),6))
        for n in (0,1):
            plate=gpu_plane(fixed[n]);ys=[plate[k+1]+.1 for k in range(0,len(plate),6)]
            self.assertGreaterEqual(min(ys),0.);self.assertLessEqual(max(ys),.2)
            self.assertGreater(minimum,max(ys))
        # The naive mask-only repair really would share a 3D interior point
        # with the original unchanged hub; no collision exemption is used.
        witness=(.03,.30,.04)
        self.assertTrue(_inside(hub,hub_position,witness))
        self.assertTrue(any(_inside(gpu_plane(v),(0.,.2,0.),witness) for v in old_depth[:2]))
        self.assertFalse(any(_inside(gpu_plane(v),(0.,.1,0.),witness) for v in fixed[:2]))

    def test_actual_triangle_normals_and_shared_arrays_six_styles(self):
        from assembly_geometry import Mesh,gpu_plane
        from assembly_style import apply_colors
        meshes=tuple(Mesh('gpu-cover-panel',gpu_plane(v),(.5,.6,.7,1.),(0.,.1 if n<2 else .2,0.),'gpu',part_id='gpu:0')
                     for n,v in enumerate(self.fixed()) if v)
        for m in meshes:
            for i in range(0,len(m.vertices),18):
                a,b,c=(m.vertices[i+k:i+k+3] for k in (0,6,12));normal=_cross(_sub(b,a),_sub(c,a))
                self.assertGreater(_dot(normal,normal),1e-20)
                for k in (0,6,12):
                    authored=m.vertices[i+k+3:i+k+6]
                    self.assertAlmostEqual(_dot(authored,authored),1.,places=8)
                    self.assertGreater(_dot(authored,normal),0.)
        for style in STYLES:
            values=apply_colors(meshes,style)
            for left,right in zip(meshes,values):
                self.assertIs(left.vertices,right.vertices)
                self.assertEqual((left.position,left.axis,left.rotor,left.part_id),(right.position,right.axis,right.rotor,right.part_id))

    def test_layer_gate_invalid_controls_and_original_unknown_middle_preserved(self):
        before=copy.deepcopy(self.gpu);self.reference();self.assertEqual(self.gpu,before)
        self.assertEqual([row['blades'] for row in self.gpu['fans']],[9,None,9])
        self.assertFalse(self.reference()['metadata']['fixed_x_blade_counts_changed'])
        bad_indices=(((0,0),)*4,((False,),)*4,((3,),)*4,((0,),),(([[]],),)*4)
        for value in bad_indices:
            with self.assertRaises((ValueError,TypeError)):
                self.panels.partition(self.polys,self.holes,.3,layer_fan_indices=value)
        for depths in ((.4,)*4,(0.,)*4,(float('nan'),)*4,(.2,),('x',)*4):
            with self.assertRaises(ValueError):self.panels.partition(self.polys,self.holes,.3,layer_depths=depths)

if __name__=='__main__':unittest.main()
