"""Fixed CowBoy interior and explicit poses; no whole-scene fit claim."""
import copy
import math
import unittest
from unittest.mock import patch

from assembly_geometry import color
from assembly_cowboy_case052 import EXACT_ID, MANUAL, TOP_IO_BASIS, build, layout_reference
from assembly_visibility048 import mesh_visible, psu_cover_mesh_ids
from chassis_catalog import CASES, get_case


def sub(a,b):return tuple(a[k]-b[k]for k in range(3))
def dot(a,b):return sum(a[k]*b[k]for k in range(3))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def transform(v,basis):return tuple(sum(v[k]*basis[k][j]for k in range(3))for j in range(3))
def triangles(mesh):
    return tuple(tuple(tuple(mesh.vertices[i+j+k]+mesh.position[k]for k in range(3))for j in(0,6,12))
                 for i in range(0,len(mesh.vertices),18))


def inside(point,mesh,direction=(.713,.377,1.)):
    distances=[]
    for a,b,c in triangles(mesh):
        e1,e2=sub(b,a),sub(c,a);p=cross(direction,e2);det=dot(e1,p)
        if abs(det)<1e-10:continue
        t=sub(point,a);u=dot(t,p)/det
        if not -1e-9<=u<=1+1e-9:continue
        q=cross(t,e1);v=dot(direction,q)/det
        if v < -1e-9 or u+v>1+1e-9:continue
        distance=dot(e2,q)/det
        if distance>1e-8:distances.append(distance)
    unique=[]
    for distance in sorted(distances):
        if not unique or abs(distance-unique[-1])>1e-7:unique.append(distance)
    return len(unique)%2==1


def open_edge_intervals(mesh):
    """Directed line intervals cancel even across real cap T subdivisions."""
    lines={}
    for triangle in triangles(mesh):
        for a,b in zip(triangle,triangle[1:]+triangle[:1]):
            delta=sub(b,a);length=math.sqrt(dot(delta,delta))
            if length<1e-9:continue
            direction=tuple(v/length for v in delta)
            if next(v for v in direction if abs(v)>1e-9)<0:direction=tuple(-v for v in direction)
            ta,tb=dot(a,direction),dot(b,direction)
            origin=tuple(a[k]-ta*direction[k]for k in range(3))
            key=tuple(round(v,6)for v in direction+origin)
            events=lines.setdefault(key,{})
            sign=1 if tb>ta else -1
            lo,hi=round(min(ta,tb),6),round(max(ta,tb),6)
            events[lo]=events.get(lo,0)+sign;events[hi]=events.get(hi,0)-sign
    invalid=[]
    for line,events in lines.items():
        active=0;previous=None
        for position,change in sorted(events.items()):
            if previous is not None and position-previous>1e-6 and active:invalid.append((line,previous,position,active))
            active+=change;previous=position
        if active:invalid.append((line,'unbalanced',active))
    return invalid


class CowBoyCase052Tests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(name,create=True,side_effect=AssertionError('Pure static material only')))
        self.case=get_case(EXACT_ID)
        self.size=tuple(self.case['dimensions_mm'][k]for k in('width','height','depth'))
        self.meshes,self.meta=build(self.case,self.size,color('#35424a'))

    def test_exact_case_only_source_binding_and_no_selected_component_cutout(self):
        before=copy.deepcopy(self.case)
        self.assertEqual(self.size,(230,500,500))
        self.assertEqual(self.case,before);self.assertEqual(len(self.meshes),3)
        self.assertEqual({m.part_id for m in self.meshes},{p['id']for p in self.meta['parts']})
        self.assertTrue(self.meta['replaces_case_bottom']);self.assertTrue(self.meta['replaces_generic_psu_shroud'])
        for key in ('positions_verified','dimensions_verified','thickness_verified','cad_verified','chamber_is_solid','selected_component_geometry_used'):
            self.assertFalse(self.meta[key])
        self.assertTrue(self.meta['reference_only']);self.assertIn(MANUAL,self.meta['source_urls'])
        self.assertLessEqual(self.meta['triangle_count'],1200)
        variant=dict(self.case,gpu_size=1000,psu='different',fan_count=99,detail_level='close')
        self.assertEqual(build(variant,self.size,color('#35424a')),(self.meshes,self.meta))
        self.assertTrue(all(m.component=='case' and not m.rotor for m in self.meshes))

    def test_other_ninety_five_cases_and_bad_dimensions_return_no_override(self):
        others=[c for c in CASES if c['id']!=EXACT_ID]
        self.assertEqual(len(others),95)
        for case in others:
            self.assertEqual(build(case,self.size,(0,0,0,1)),((),{}))
            self.assertEqual(layout_reference(case,self.size),{})
        for dims in ((230,500),('230',500,500),(230,True,500),(230,float('nan'),500),(230,500,float('inf'))):
            self.assertEqual(build(self.case,dims,(0,0,0,1)),((),{}))
            self.assertEqual(layout_reference(self.case,dims),{})

    def test_open_bottom_slots_and_empty_old_tunnel_are_actual_geometry(self):
        frame=next(m for m in self.meshes if m.name=='case-bottom-intake-frame')
        top=self.meta['floor_top_y_mm'];rear=-244.;front=244.
        pitch=(front-rear-32)/5.
        for i in range(5):
            z=rear+16+(i+.5)*pitch
            self.assertFalse(inside((0,top-.6,z),frame,(0,1,0)))
        self.assertTrue(inside((0,top-.6,rear+3),frame,(0,1,0)))
        for point in ((0,-202.5,0),(0,-190,-130),(0,-190,130)):
            self.assertFalse(any(inside(point,m)for m in self.meshes))
        plane=layout_reference(self.case,self.size)['mount_planes']['bottom']
        self.assertEqual(plane['source_capacity_sizes_mm'],(120,140))
        self.assertEqual(plane['source_capacity_count'],3)
        self.assertEqual(plane['position'],(0.,top+1.,0.))
        self.assertFalse(plane['positions_verified'])

    def test_front_psu_frame_has_real_open_ac_face_and_max_length_bay_is_empty(self):
        skin,mount,_=self.meshes;bay=self.meta['front_bay_reference_mm']
        self.assertTrue(inside((-108.4,0,180),skin,(-1,0,0)))
        self.assertFalse(inside((0,200.6,195),mount,(0,1,0)))
        self.assertTrue(inside((-105,200.6,195),mount,(0,1,0)))
        # The fixed front bay is empty, including a max-source-length example.
        # This is not a selected PSU mesh/port/whole-host compatibility test.
        for length in (160.,219.999):
            cy=200-length/2
            for point in ((0,cy,195),(-74,cy,153),(74,cy,237)):
                self.assertFalse(any(inside(point,m)for m in self.meshes))
            self.assertGreaterEqual(200-length,bay['bottom_y'])
        self.assertFalse(self.meta['far_side_wall_added'])

    def test_det_positive_board_and_psu_contracts_preserve_mechanical_axes(self):
        layout=layout_reference(self.case,self.size);board,psu=layout['board_pose'],layout['psu']
        self.assertEqual(board['kind'],'top_io_90');self.assertEqual(board['io_y_mm'],200)
        self.assertEqual(board['rear_z_mm'],-232)
        self.assertEqual(psu['basis'],TOP_IO_BASIS)
        self.assertAlmostEqual(dot(TOP_IO_BASIS[0],cross(TOP_IO_BASIS[1],TOP_IO_BASIS[2])),1)
        self.assertEqual(transform((0,0,-1),TOP_IO_BASIS),(0,1,0))
        self.assertEqual(transform((-1,0,0),TOP_IO_BASIS),(-1,0,0))
        self.assertEqual(transform((0,-1,0),TOP_IO_BASIS),(0,0,-1))
        self.assertFalse(psu['fan_orientation_verified']);self.assertFalse(psu['positions_verified'])
        self.assertEqual((psu['ceiling_y_mm'],psu['front_z_mm'],psu['center_x_mm']),(200.,238.,0.))
        # Independent rigid ATX math for the host, not an identity/world-origin spin.
        source=(82.8,10.,-114.);target=(82.8,200-244/2,-232+305/2)
        def pose(point):return tuple(target[k]+transform(sub(point,source),TOP_IO_BASIS)[k]for k in range(3))
        original=(source[0],source[1],source[2]-244/2)
        self.assertAlmostEqual(pose(original)[1],board['io_y_mm'])
        a=(source[0],source[1]-305/2,source[2]);b=(source[0],source[1]+305/2,source[2])
        self.assertAlmostEqual(math.dist(pose(a),pose(b)),305.)
        self.assertEqual(board['transform_components'],('board','cpu','memory','gpu'))
        self.assertTrue(board['transform_attachment_anchors'])

    def test_thin_parts_are_finite_closed_with_consistent_unit_normals(self):
        for mesh in self.meshes:
            self.assertEqual(open_edge_intervals(mesh),[],mesh.name)
            volume=0.
            for n,(a,b,c)in enumerate(triangles(mesh)):
                normal=mesh.vertices[n*18+3:n*18+6]
                geometric=cross(sub(b,a),sub(c,a));length=math.sqrt(dot(geometric,geometric))
                self.assertGreater(length,1e-10)
                self.assertTrue(all(math.isfinite(v)for v in mesh.vertices[n*18:n*18+18]))
                self.assertAlmostEqual(dot(normal,normal),1.,places=6)
                self.assertAlmostEqual(dot(normal,geometric)/length,1.,places=6)
                volume+=dot(a,cross(b,c))/6
            self.assertGreater(volume,0.,mesh.name)
            self.assertLess(volume,300000.,mesh.name)

    def test_lod_and_six_styles_share_physical_parts_and_show_psu_does_not_hide_support(self):
        from assembly_style import apply_model_styles
        signature=lambda m:(m.name,m.part_id,m.vertices,m.position,m.axis,m.rotor,m.direction)
        expected=[signature(m)for m in self.meshes]
        for level in ('eco','balanced','close'):
            meshes,meta=build(dict(self.case,detail_level=level),self.size,color('#35424a'))
            self.assertEqual([signature(m)for m in meshes],expected)
            for style in ('miniature','cartoon','notebook_color','notebook_line','sticker','papercut'):
                styled,_=apply_model_styles(meshes,style,{},self.size,self.case)
                physical=[m for m in styled if m.part_id in {v.part_id for v in meshes}]
                self.assertEqual([signature(m)for m in physical],expected)
                self.assertTrue(all(a.vertices is b.vertices for a,b in zip(physical,meshes)))
        hidden=psu_cover_mesh_ids(self.meshes)
        self.assertEqual(hidden,frozenset((id(self.meshes[0]),)))
        self.assertTrue(all(mesh_visible(m,True,False)for m in self.meshes))
        self.assertEqual([mesh_visible(m,True,True)for m in self.meshes],[False,True,True])
        self.assertEqual([signature(m)for m in self.meshes],expected)


if __name__=='__main__':unittest.main()
