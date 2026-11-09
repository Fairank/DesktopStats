"""Helios reference carry strips physically join their rail-supported feet."""
from collections import Counter, defaultdict
import copy
import math
import unittest
from unittest.mock import patch

from assembly_geometry import build_scene, Scene, vertex_bytes
from assembly_style import apply_model_styles
from chassis_catalog import CASES

SIX = ('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')


def specification(level='balanced', straps=True):
    case = copy.deepcopy(next(row for row in CASES if row['id']=='asus-rog-strix-helios-gx601'))
    if not straps: case['features'] = tuple(f for f in case['features'] if f!='fabric_carry_straps')
    return dict(case=case, detail_level=level, visual_style='miniature',
                cooling=dict(cpu_cooler='none', case_fans=[dict(
                    model='arctic-p12-pwm', mount='top', count=2, direction='exhaust')]))


def points(mesh):
    return {tuple(mesh.vertices[n+k]+mesh.position[k] for k in range(3))
            for n in range(0,len(mesh.vertices),6)}


def bounds(mesh):
    p = points(mesh)
    return tuple(tuple((min if side==0 else max)(v[k] for v in p) for k in range(3)) for side in (0,1))


def strips(scene):
    groups = defaultdict(list)
    for mesh in scene.meshes:
        if mesh.name=='fabric-carry-strap': groups[mesh.position[2]].append(mesh)
    return [sorted(values,key=lambda m:bounds(m)[0][0]) for _,values in sorted(groups.items())]


class CarryStrapTests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start','socket.socket'):
            self.enterContext(patch(name,side_effect=AssertionError('Pure geometry only')))

    def test_adjacent_sections_share_a_complete_face_with_no_vertical_or_horizontal_gap(self):
        scene = build_scene(specification())
        groups = strips(scene); self.assertEqual([len(group) for group in groups], [8,8])
        for group in groups:
            for left,right in zip(group,group[1:]):
                shared = points(left) & points(right)
                self.assertEqual(len(shared),4)
                self.assertEqual({v[0] for v in shared},{bounds(left)[1][0]})
                self.assertEqual(bounds(left)[1][0],bounds(right)[0][0])
            for mesh in group:
                self.assertEqual(mesh.vertex_count//3,12)
                edges=Counter();volume=0.
                for n in range(0,len(mesh.vertices),18):
                    tri=[mesh.vertices[n+k:n+k+3] for k in (0,6,12)]
                    a,b,c=tri
                    volume+=(a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0]))/6.
                    for i,j in ((0,1),(1,2),(2,0)):edges[tuple(sorted((tuple(tri[i]),tuple(tri[j]))))]+=1
                self.assertEqual(set(edges.values()),{2})
                self.assertGreater(volume,0.)
                for n in range(0,len(mesh.vertices),6):
                    self.assertAlmostEqual(sum(v*v for v in mesh.vertices[n+3:n+6]),1.)

    def test_each_foot_has_positive_area_on_the_actual_depth_rail_top(self):
        scene = build_scene(specification()); roof=scene.dimensions[1]/2
        rails=[bounds(m) for m in scene.meshes if m.name=='case-depth-rail' and abs(bounds(m)[1][1]-roof)<1.e-8]
        self.assertEqual(len(rails),2)
        for group in strips(scene):
            for foot in (group[0],group[-1]):
                contact=[p for p in points(foot) if p[1]==roof]
                self.assertEqual(len(contact),4)
                self.assertGreater(max(p[0] for p in contact)-min(p[0] for p in contact),0.)
                self.assertGreater(max(p[2] for p in contact)-min(p[2] for p in contact),0.)
                self.assertTrue(any(all(lo[0]<=p[0]<=hi[0] and lo[2]<=p[2]<=hi[2]
                                        and p[1]==hi[1] for p in contact) for lo,hi in rails))
        # Keep the existing reference arch height and overall case width.
        all_points=[p for group in strips(scene) for m in group for p in points(m)]
        self.assertAlmostEqual(max(p[1] for p in all_points),319.7420005039053)
        self.assertLessEqual(max(abs(p[0]) for p in all_points),scene.dimensions[0]/2)

    def test_three_lods_and_six_styles_share_the_same_sixteen_physical_segments(self):
        for level in ('eco','balanced','close'):
            scene=build_scene(specification(level)); original=tuple(m for group in strips(scene) for m in group)
            self.assertEqual(sum(m.vertex_count//3 for m in original),192)
            self.assertLessEqual(scene.triangle_count,scene.metadata['triangle_budget'])
            for style in SIX:
                with self.subTest(level=level,style=style):
                    values,_=apply_model_styles(scene.meshes,style,{},scene.dimensions,{'front':'glass'})
                    current=tuple(m for m in values if m.name=='fabric-carry-strap')
                    self.assertEqual(len(current),16)
                    self.assertEqual([m.vertices for m in current],[m.vertices for m in original])
                    self.assertEqual([m.position for m in current],[m.position for m in original])
                    self.assertTrue(all(not m.rotor for m in current))

    def test_strap_feature_has_no_effect_on_fans_or_any_other_physical_mesh(self):
        with_straps=build_scene(specification());without=build_scene(specification(straps=False))
        kept=tuple(m for m in with_straps.meshes if m.name!='fabric-carry-strap')
        self.assertEqual(vertex_bytes(Scene(kept,with_straps.dimensions,{})),vertex_bytes(without))
        self.assertEqual([(m.name,m.position,m.axis,m.rotor,m.direction) for m in kept],
                         [(m.name,m.position,m.axis,m.rotor,m.direction) for m in without.meshes])
        self.assertEqual(with_straps.metadata['cooling']['fans'],without.metadata['cooling']['fans'])
        self.assertEqual(len(with_straps.metadata['cooling']['fans']),2)


if __name__=='__main__':unittest.main()
