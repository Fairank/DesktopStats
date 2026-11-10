"""Fixed GX601 front material and real prepare/finish integration controls."""
from collections import Counter
import inspect
import json
import math
import struct
import types
import unittest
import assembly_helios_front055 as world

def signed_volume(faces):
    total = 0.
    for a,b,c in faces:
        total += (a[0]*(b[1]*c[2]-b[2]*c[1]) + a[1]*(b[2]*c[0]-b[0]*c[2])
                  + a[2]*(b[0]*c[1]-b[1]*c[0]))/6
    return total

def ray_inside(faces, point):
    """Actual triangle ray intersections, independent of UV cell construction."""
    direction = (1.,0.17320508075688773,0.2718281828459045)
    hits = []
    def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
    def dot(a,b):return sum(x*y for x,y in zip(a,b))
    for a,b,c in faces:
        e1=tuple(b[k]-a[k] for k in range(3));e2=tuple(c[k]-a[k] for k in range(3))
        h=cross(direction,e2);det=dot(e1,h)
        if abs(det)<1e-13:continue
        s=tuple(point[k]-a[k] for k in range(3));u=dot(s,h)/det
        if not 0<=u<=1:continue
        q=cross(s,e1);v=dot(direction,q)/det
        if v<0 or u+v>1:continue
        distance=dot(e2,q)/det
        if distance>1e-12:hits.append(distance)
    hits.sort()
    unique=[]
    for hit in hits:
        if not unique or abs(hit-unique[-1])>1e-10:unique.append(hit)
    return bool(len(unique)%2)

def faces(cover):return tuple(tuple(cover.points[i]for i in face)for face in cover.boundary)

def cube(low,high):
    points=tuple((x,y,z)for x in(low[0],high[0])for y in(low[1],high[1])for z in(low[2],high[2]))
    quads=((0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5))
    return tuple(tuple(points[i]for i in tri)for a,b,c,d in quads for tri in((a,b,c),(a,c,d)))

class FakeMesh:
    def __init__(self,name,vertices,tone=(),component='case',part_id=''):
        self.name=name;self.vertices=vertices;self.color=tone;self.component=component;self.part_id=part_id
        self.position=(0.,0.,0.)


def legacy_contains(point):
    # The still-retained 052 plate builder gives the actual old full-roof
    # positive fixture; it is not used to build the new front in prepare().
    from assembly_helios_shroud052 import _cover
    r=world.reference_datum()
    raw=_cover((r['split_bottom'],r['split_top']),(r['front'],r['front']),r['bottom'],r['top'],
               -r['half'],r['half'],1.2,None)
    tris=tuple(tuple(tuple(raw[at+j+k]for k in range(3))for j in(0,6,12))for at in range(0,len(raw),18))
    return all(world._ray_inside(tris,point,d)for d in((1.,.173,.317),(.317,1.,.173),(.173,.317,1.)))

topology=types.SimpleNamespace(legacy_full_roof_contains=legacy_contains)
old_controls=types.SimpleNamespace(signed_volume=signed_volume,ray_inside=ray_inside)


class HeliosFront055Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.cover=world.build_cover()

    def test_reference_datum_and_real_front_rear_identity(self):
        r=self.cover.datum
        self.assertEqual((r['width'],r['height'],r['depth']),(250.,591.,565.))
        self.assertEqual(r['narrow_end_world_axis'],'+Z')
        self.assertEqual(r['wide_end'],'rear diagonal seam')
        self.assertEqual(r['roof_inward_world_axis'],'+X')
        low,high=world.bounds(self.cover.points)
        for actual,expected in zip(low,(-119.,-591*.49,r['split_bottom'])):
            self.assertAlmostEqual(actual,expected,delta=3e-5)
        self.assertAlmostEqual(high[0],119.,delta=3e-5)
        self.assertAlmostEqual(high[2],276.5,delta=3e-5)
        self.assertAlmostEqual(high[1],-591*.32+2.5,delta=3e-5)
        self.assertFalse(self.cover.dimensions_verified)
        self.assertFalse(self.cover.mounting_fit_verified)
        self.assertFalse(self.cover.fixing_ears_placed)

    def test_actual_uploaded_points_exact_closed_boundary_and_matching_material_volume(self):
        p=self.cover
        self.assertEqual(len(p.vertices),len(p.boundary)*18)
        edges=Counter((a,b)for tri in faces(p)for a,b in zip(tri,(*tri[1:],tri[0])))
        for (a,b),count in edges.items():
            self.assertEqual(count,1);self.assertEqual(edges[(b,a)],1)
        tetra_volume=0.
        for tet in p.tetrahedra:
            volume=world.signed6(*(p.points[i]for i in tet))/6
            self.assertGreater(volume,0);tetra_volume+=volume
        boundary_volume=old_controls.signed_volume(faces(p))
        self.assertGreater(boundary_volume,0)
        self.assertAlmostEqual(tetra_volume,boundary_volume,delta=1e-5)
        packed=struct.unpack('<'+'f'*len(p.vertices),struct.pack('<'+'f'*len(p.vertices),*p.vertices))
        for at,tri in enumerate(faces(p)):
            a,b,c=tri;normal=world.cross(world.sub(b,a),world.sub(c,a))
            self.assertGreater(math.hypot(*normal),0)
            for j,point in zip((0,6,12),tri):
                self.assertEqual(tuple(packed[at*18+j:at*18+j+3]),point)
                self.assertGreater(world.dot(normal,packed[at*18+j+3:at*18+j+6]),0)

    def test_old_p14_positive_retained_but_new_actual_roof_point_is_void(self):
        point=(65.,-189.5,259.)
        self.assertTrue(topology.legacy_full_roof_contains(point))
        self.assertFalse(world.contains_material(self.cover,point))
        for direction in((1.,.173,.317),(.317,1.,.173),(.173,.317,1.)):
            self.assertFalse(world._ray_inside(faces(self.cover),point,direction))
        side=(-118.4,-230.,200.)
        self.assertTrue(world.contains_material(self.cover,side))
        self.assertTrue(old_controls.ray_inside(faces(self.cover),side))

    def test_triangle_inside_real_side_is_positive_and_external_contact_is_not(self):
        tri=((-118.4,-230.2,199.8),(-118.4,-229.8,199.8),(-118.4,-230.,200.2))
        proof=world.triangle_material_witness(self.cover,(tri,))
        self.assertIs(proof['clear'],False)
        self.assertGreater(proof['strict_interior_surface_mm2'],0)
        external=faces(self.cover)[0]
        self.assertIs(world.triangle_material_witness(self.cover,(external,))['clear'],True)
        tiny=((-118.4,-230.,200.),(-118.4,-229.9999,200.),(-118.4,-230.,200.0001))
        proof=world.triangle_material_witness(self.cover,(tiny,))
        self.assertIs(proof['clear'],False)
        self.assertGreater(proof['strict_interior_surface_mm2'],0)
        self.assertLess(proof['strict_interior_surface_mm2'],1e-7)
        a,b,c=tiny;d=(-118.3999,-230.,200.)
        closed=((a,c,b),(a,b,d),(a,d,c),(b,c,d))
        self.assertIs(world.closed_pair_review(self.cover,closed,other_closed_verified=True)['clear'],False)
        self.assertIs(world.triangle_material_witness(self.cover,((a,a,a),))['clear'],False)

    def test_internal_tetra_face_does_not_become_a_false_gap(self):
        counts=Counter(tuple(sorted((tet[a],tet[b],tet[c])))for tet in self.cover.tetrahedra
                       for a,b,c in((0,1,2),(0,1,3),(0,2,3),(1,2,3)))
        selected=None
        for key,count in counts.items():
            if count!=2:continue
            tri=tuple(self.cover.points[i]for i in key)
            centre=tuple(sum(p[k]for p in tri)/3 for k in range(3))
            if world.contains_material(self.cover,centre):selected=tri;break
        self.assertIsNotNone(selected)
        self.assertIs(world.triangle_material_witness(self.cover,(selected,))['clear'],False)

    def test_reverse_containment_unknown_and_disjoint_controls(self):
        low,high=world.bounds(self.cover.points)
        enclosing=cube(tuple(v-5 for v in low),tuple(v+5 for v in high))
        proof=world.closed_pair_review(self.cover,enclosing,other_closed_verified=True)
        self.assertIs(proof['clear'],False)
        self.assertEqual(proof['proof'],'cover_material_inside_closed_other')
        self.assertGreater(proof['other_boundary_distance_mm'],0)
        self.assertEqual(world.closed_pair_review(self.cover,enclosing)['reference_review'],'other_closed_material_unverified')
        far=cube((1000.,1000.,1000.),(1001.,1001.,1001.))
        self.assertIs(world.closed_pair_review(self.cover,far)['clear'],True)

    def test_public_prepare_finish_share_material_release_sidecar_and_keep_all_choices_fixed(self):
        import gc
        import weakref
        from assembly_geometry import Mesh
        from assembly_helios_shroud052 import CASE_ID,prepare,finish,_front_fan_intersection
        vertices=[]
        low,high=(1000.,1000.,1000.),(1001.,1001.,1001.)
        for tri in cube(low,high):
            for p in tri:vertices.extend((*p,0.,1.,0.))
        fan=Mesh('case-fan-frame',tuple(vertices),(0,0,0,1),component='fans',part_id='fans:front:0')
        cooling=dict(parts=[dict(id='fans:front:0',kind='case_fan',mount='front',model_id='arctic-p14-pwm')])
        variants=[]
        for selected in('none','arctic-p12-pwm','arctic-p14-pwm'):
            prepared=prepare(dict(id=CASE_ID,private_choice_marker=selected),(250.,591.,565.),(.2,.3,.4,1.))
            rear,front,meta=prepared
            original=dict(meta)
            material=meta['_front_material055'];ref=weakref.ref(material)
            variants.append(front.vertices)
            result,state,actual_cooling=finish(tuple((*rear,fan)),front,(fan,),cooling,meta)
            self.assertTrue(all(any(m is source for m in result)for source in rear))
            self.assertTrue(any(m is fan for m in result));self.assertTrue(any(m is front for m in result))
            self.assertIs(actual_cooling,cooling)
            self.assertFalse(state['front_fan_reference_clearance_reviews'])
            self.assertNotIn('_front_material055',state);json.dumps(state)
            self.assertEqual(meta,original)
            self.assertIsNotNone(_front_fan_intersection((fan,),dict(case_id=CASE_ID,front_topology055=True)))
            del prepared,meta,original,material
            gc.collect();self.assertIsNone(ref())
        self.assertEqual(variants[0],variants[1]);self.assertEqual(variants[1],variants[2])
        # Pairing is a gate even when every fake fan is far away. An obsolete
        # material with equal bytes is not the owner of this visible PN tuple.
        rear,front,meta=prepare(dict(id=CASE_ID),(250.,591.,565.),(.2,.3,.4,1.))
        stale=world.build_cover()
        self.assertIsNot(stale.vertices,front.vertices);self.assertEqual(stale.vertices,front.vertices)
        wrong_part=Mesh(front.name,front.vertices,front.color,component='case',part_id='gpu:0')
        wrong_pose=Mesh(front.name,front.vertices,front.color,position=(1.,0.,0.),component='case',part_id=front.part_id)
        cases=((front,dict(meta,_front_material055=stale),'front_visible_material_mismatch'),
               (front,dict(meta,_front_material055=object()),'front_material_missing_or_wrong_type'),
               (wrong_part,meta,'front_part_identity_mismatch'),
               (wrong_pose,meta,'front_fixed_pose_unverified'))
        for visible,sidecar,reason in cases:
            with self.subTest(identity_failure=reason):
                result,state,rejected=finish(tuple((*rear,fan)),visible,(fan,),cooling,sidecar)
                self.assertFalse(any(m is fan for m in result))
                self.assertIs(state['front_material_review055']['paired'],False)
                self.assertEqual(state['front_material_review055']['reason'],reason)
                self.assertNotIn('_front_material055',state)
                rows=[r for r in rejected['rejected']if r['reason']=='front_cover_material_unverified']
                self.assertEqual(len(rows),1);self.assertEqual(rows[0]['proof']['reference_review'],reason)
                self.assertIs(rows[0]['real_product_support_rejected'],False)
        self.assertEqual(tuple(inspect.signature(world.build_cover).parameters),('dimensions',))
        for style in('miniature','cartoon','notebook_color','notebook_line','sticker','papercut'):
            mesh=world.replacement_mesh(self.cover,(.2,.3,.4,1.),FakeMesh)
            self.assertIs(mesh.vertices,self.cover.vertices)


if __name__=='__main__':unittest.main()
