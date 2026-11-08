"""Actual new loop contour candidates and byte-compatible legacy edge ink."""
import hashlib
import math
import struct
import unittest
from unittest.mock import patch

from assembly_geometry import Mesh, box, ring, color
from assembly_style import apply_model_styles, apply_colors, crease_edges, edge_batches
from liquid_ink046 import augment_line_edges
from top_bar_config import HARDWARE_ICON_STYLES


def edge_key(a, b):
    return tuple(sorted((tuple(round(v, 7) for v in a), tuple(round(v, 7) for v in b))))


def real_edges(vertices):
    result = set()
    for start in range(0, len(vertices), 18):
        points = [vertices[start+n:start+n+3] for n in (0, 6, 12)]
        for a, b in zip(points, points[1:]+points[:1]):
            result.add(edge_key(a, b))
    return result


class LiquidInk046Tests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL', 'socket.socket', 'threading.Thread.start', 'subprocess.Popen'):
            self.enterContext(patch(name, side_effect=AssertionError('Ink construction must be static and local')))

    def test_smooth_tube_gains_real_longitudinal_edges_and_keeps_existing_rims(self):
        vertices = ring(10, 6, 30, 24)
        original = crease_edges(vertices)
        before = tuple(vertices)
        ink = augment_line_edges(vertices, original)
        keys = {edge_key(a, b) for a, b in ink}
        old_keys = {edge_key(a, b) for a, b in original}
        self.assertTrue(old_keys <= keys)
        # Legacy crease endpoints are quantized by the established pass;
        # every *new* reference contour must use exact source triangle points.
        self.assertTrue(keys-old_keys <= real_edges(vertices))
        vertical = [(a, b) for a, b in ink if abs(a[2]-b[2]) > 29.9]
        self.assertGreaterEqual(len(vertical), 4)
        self.assertLessEqual(len(vertical), 12)
        self.assertEqual(vertices, before)
        self.assertLessEqual(len(ink), 512)

    def test_flat_adjacent_triangles_do_not_gain_coplanar_diagonals(self):
        vertices = box(24, 18, 12)
        original = crease_edges(vertices)
        self.assertEqual(augment_line_edges(vertices, original), original)
        # One flat plate made from two triangles has four true perimeter edges,
        # while its shared diagonal must remain absent from the reference pass.
        plate = (0.,0.,0.,0.,0.,1., 20.,0.,0.,0.,0.,1., 20.,10.,0.,0.,0.,1.,
                 0.,0.,0.,0.,0.,1., 20.,10.,0.,0.,0.,1., 0.,10.,0.,0.,0.,1.)
        old = crease_edges(plate)
        self.assertEqual(len(old), 4)
        self.assertEqual(augment_line_edges(plate, old), old)
        self.assertNotIn(edge_key((0,0,0), (20,10,0)), {edge_key(a,b) for a,b in augment_line_edges(plate, old)})

    def test_small_loop_port_plate_removes_radial_partition_seams_below_ink_cap(self):
        from assembly_detail import perforated_plate,chamfer_rect
        vertices=perforated_plate(chamfer_rect(40,30,2),[(0,0,5)],2,segments=12)
        legacy=crease_edges(vertices)
        fixed=crease_edges(vertices,repair_under_cap=True)
        self.assertLess(len(legacy),512)
        # Two octagonal exterior rims, two twelve-sided bore rims and the
        # eight actual thickness creases. No hole-to-outside radial ink.
        self.assertEqual(len(fixed),48)
        for a,b in fixed:
            if abs(a[2]-b[2])<1e-8:
                self.assertEqual(math.hypot(a[0],a[1])<6,math.hypot(b[0],b[1])<6)
        for name,expected in (('loop-source-cap',True),('old-reference-cap',False)):
            mesh=Mesh(name,vertices,color('#768e99'),component='cooler')
            with patch('assembly_style.crease_edges',wraps=crease_edges) as helper:
                self.assertTrue(edge_batches((mesh,),'notebook_line'))
            self.assertEqual(helper.call_args.kwargs['repair_under_cap'],expected)

    def test_rotated_mesh_candidates_are_real_edges_and_do_not_mutate_geometry(self):
        vertices = ring(8, 5, 40, 24)
        angle = math.radians(31)
        c, s = math.cos(angle), math.sin(angle)
        rotate = lambda p: (c*p[0]-s*p[2], p[1], s*p[0]+c*p[2])
        moved = tuple(value for start in range(0,len(vertices),6) for point in (rotate(vertices[start:start+3]), rotate(vertices[start+3:start+6])) for value in point)
        original = crease_edges(moved)
        ink = augment_line_edges(moved, original)
        self.assertTrue({edge_key(a,b) for a,b in ink}-{edge_key(a,b) for a,b in original} <= real_edges(moved))
        self.assertGreaterEqual(sum(math.dist(a,b) > 39.9 for a,b in ink), 4)
        self.assertEqual(moved, tuple(moved))

    def test_line_only_new_mesh_gate_and_shared_13_style_physical_geometry(self):
        mesh = Mesh('loop-actual-tube', ring(10,6,40,24), color('#768e99'), component='cooler', part_id='cooler:tubing')
        for style in HARDWARE_ICON_STYLES:
            values, metadata = apply_model_styles((mesh,), style, {}, (40,40,40), {'front':'open'})
            self.assertIs(values[0].vertices, mesh.vertices)
            from liquid_silhouette046 import silhouette_edges
            with patch('liquid_silhouette046.silhouette_edges', wraps=silhouette_edges) as helper:
                batches = edge_batches(values, style, metadata['mesh_style_ids'])
            self.assertEqual(helper.call_count, int(style in ('outline','notebook_line','sketch')))
            if style in ('outline','notebook_line','sketch'):
                points = batches[0][1]
                # Hand ink may split a long real candidate into two decorative
                # strokes. Both still span far beyond the tiny end-rim arcs.
                self.assertGreaterEqual(sum(math.dist(points[n:n+3], points[n+6:n+9]) > 19.0 for n in range(0,len(points),12)), 4)

    def test_mesh_and_whole_scene_ink_budgets_stay_bounded(self):
        # ring() intentionally clamps its segment count. Six separate maximum
        # rings force both the per-mesh union and whole-scene over-budget paths.
        unit = ring(20,12,60,64)
        values = []
        for n in range(6):
            for start in range(0,len(unit),6):
                values.extend((unit[start]+n*60.,*unit[start+1:start+6]))
        vertices = tuple(values)
        original = crease_edges(vertices)
        self.assertEqual(len(original),512)
        self.assertLessEqual(len(augment_line_edges(vertices, original, 5000)), 512)
        self.assertGreaterEqual(sum(math.dist(a,b)>59.9 for a,b in augment_line_edges(vertices,original)),4)
        for invalid in (0,-1,None,True):
            self.assertEqual(augment_line_edges(vertices, original, invalid), ())
        mesh = Mesh('loop-many-rims', vertices, color('#768e99'), component='cooler')
        meshes = tuple(Mesh(mesh.name+str(n),mesh.vertices,mesh.color,position=(n*50.,0.,0.),component='cooler',part_id='cooler:'+str(n)) for n in range(20))
        segments = sum(len(data)//12 for _,data in edge_batches(meshes,'notebook_line'))
        self.assertGreater(segments, 8000)
        self.assertLessEqual(segments, 8192)
        for _,data in edge_batches(meshes,'outline'):
            self.assertLessEqual(len(data)//12,512)

    def test_new_papercut_material_layers_remain_readable_and_legacy_color_stays(self):
        vertices=ring(10,6,30,24)
        names=('loop-open-fitting-middle-sleeve','loop-open-end-collars','loop-factory-silicone-grip-band','loop-reference-carbon-weave-strips','legacy-painted-cylinder')
        meshes=tuple(Mesh(name,vertices,color('#292e31'),component='cooler') for name in names)
        values=apply_colors(meshes,'papercut')
        self.assertTrue(all(a.vertices is b.vertices for a,b in zip(meshes,values)))
        self.assertGreater(math.dist(values[0].color[:3],values[1].color[:3]),.25)
        self.assertGreater(math.dist(values[0].color[:3],values[2].color[:3]),.25)
        self.assertEqual(values[2].color,values[3].color)
        self.assertEqual(values[4].color,color('#29485c'))
        self.assertEqual(apply_colors(meshes,'miniature'),meshes)

    def test_all_legacy_nonloop_style_bytes_equal_prechange_fixture(self):
        meshes = (Mesh('legacy-cylinder',ring(10,6,30,24),color('#677f8a'),component='cooler',part_id='cooler:legacy'),
                  Mesh('legacy-box',box(24,18,12),color('#81949d'),component='case',part_id='case'))
        plain = '4c3325aaf55e785e72a0dc5462fcad62c07325a64b30b48f6b2b9247a3e6fb0a'
        hand = '2183a7caba4e45f75f3c251bde18022e6db3d59a36d7c35d2c1e69c10746dcef'
        ink = 'c359e952397e0d5f93b0f1b8f455855f91f8a11f63573458f8112c0188cbaa1c'
        expected = {style: plain for style in HARDWARE_ICON_STYLES}
        expected.update(miniature=hashlib.sha256(b'').hexdigest(),notebook_color=hand,notebook_line=hand,sketch=hand,notebook_smile=hand,solid=ink,papercut=ink)
        for style in HARDWARE_ICON_STYLES:
            h = hashlib.sha256()
            with patch('liquid_ink046.augment_line_edges',side_effect=AssertionError('Legacy geometry must bypass new ink')):
                for mesh,vertices in edge_batches(meshes,style):
                    h.update(mesh.name.encode())
                    h.update(struct.pack('<I',len(vertices)))
                    h.update(struct.pack('<'+str(len(vertices))+'f',*vertices))
            self.assertEqual(h.hexdigest(),expected[style],style)


if __name__ == '__main__':
    unittest.main()
