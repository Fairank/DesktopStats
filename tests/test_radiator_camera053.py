"""Radiator camera controls: actual rays and old-loop output, not a face-normal proxy."""
from copy import deepcopy
import hashlib
import importlib.machinery
import importlib.util
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

from assembly_geometry import Mesh, box
import liquid_svg046 as projector
import radiator_svg053 as radiator
from liquid_cooling_catalog044 import get_radiator

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CAMERA_WITNESSES = []


def add(a, b): return tuple(x+y for x, y in zip(a, b))
def sub(a, b): return tuple(x-y for x, y in zip(a, b))
def mul(a, k): return tuple(x*k for x in a)
def dot(a, b): return sum(x*y for x, y in zip(a, b))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def unit(a):
    size = math.hypot(*a)
    return tuple(v/size for v in a)


def ray_box(origin, direction, low, high):
    near, far = 0., 4000.
    for k in range(3):
        if direction[k] == 0.:
            if origin[k] < low[k] or origin[k] > high[k]: return False
        else:
            a, b = (low[k]-origin[k])/direction[k], (high[k]-origin[k])/direction[k]
            near, far = max(near, min(a, b)), min(far, max(a, b))
            if far < near: return False
    return True


def actual_facets(meshes):
    result = []
    for mesh in meshes:
        triangles = [tuple(add(mesh.vertices[at+k:at+k+3], mesh.position) for k in (0, 6, 12))
                     for at in range(0, len(mesh.vertices), 18)]
        points = [p for triangle in triangles for p in triangle]
        result.append((mesh.name, tuple(min(p[k] for p in points) for k in range(3)),
                       tuple(max(p[k] for p in points) for k in range(3)), triangles))
    return result


def first_hit(facets, target, eye):
    """Independent unculled Moller ray; preserve all same-depth material ties."""
    origin = add(target, mul(eye, 2000.)); direction = mul(eye, -1.)
    nearest = math.inf; names = set()
    for name, low, high, triangles in facets:
        if not ray_box(origin, direction, low, high): continue
        for a, b, c in triangles:
            edge1, edge2 = sub(b, a), sub(c, a)
            h = cross(direction, edge2); determinant = dot(edge1, h)
            if abs(determinant) < 1e-10: continue
            delta = sub(origin, a); u = dot(delta, h)/determinant
            if u < -1e-8 or u > 1.+1e-8: continue
            q = cross(delta, edge1); v = dot(direction, q)/determinant
            if v < -1e-8 or u+v > 1.+1e-8: continue
            distance = dot(edge2, q)/determinant
            if distance < 1e-7 or distance > 4000.: continue
            if distance < nearest-1e-6:
                nearest, names = distance, {name}
            elif abs(distance-nearest) <= 1e-6:
                nearest = min(nearest, distance); names.add(name)
    return nearest, sorted(names)


class CameraFront053Tests(unittest.TestCase):
    def test_old_core1_default_complete_ordered_svg_json_byte_bridge(self):
        from liquid_block_pump_expansion046 import get_record
        from liquid_pack_schema046 import validate_reference
        path = ROOT/'tests/fixtures/liquid_svg046_pre053.py.txt'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         '3e47b0996def90591880942c2c18ec332043252257739cba69b8b8eec6516a6e')
        loader = importlib.machinery.SourceFileLoader('liquid_svg046_original_camera_control', str(path))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        old = importlib.util.module_from_spec(spec); loader.exec_module(old)
        row = validate_reference(get_record('alphacool-core1-black'))
        previous = old.art_from_reference(row, 'miniature')
        current = projector.art_from_reference(row, 'miniature')
        self.assertTrue(previous); self.assertTrue(current)
        self.assertEqual(current, previous)
        self.assertEqual(json.dumps(current, ensure_ascii=False), json.dumps(previous, ensure_ascii=False))
        self.assertEqual(projector.MAX_TRIANGLES, 2600); self.assertEqual(projector.MAX_CLIP_WORK, 600000)

    def test_bad_direction_early_rejection_mesh_globals_and_clip_direction(self):
        class ForbiddenMeshRead:
            def __iter__(self): raise AssertionError('Invalid view must reject before mesh traversal')
        for direction in ((), (0., 0., 0.), (0., 1., 0.), (0., -1., 0.), (True, 0., 1.),
                          (math.nan, 0., 1.), (0., math.inf, 1.), [1., 0.], 'front',
                          (10**400, 0., 1.)):
            with self.subTest(direction=repr(direction)):
                self.assertEqual(projector.project_meshes(ForbiddenMeshRead(), view_direction=direction), {})
        mesh = Mesh('small-static-control', box(12., 10., 8.), (.2, .3, .4, 1.))
        before = deepcopy(mesh); globals_before = (projector._EYE, projector._RIGHT, projector._UP)
        default = projector.project_meshes((mesh,))
        explicit_none = projector.project_meshes((mesh,), view_direction=None)
        self.assertTrue(default); self.assertEqual(default, explicit_none)
        front = projector.project_meshes((mesh,), view_direction=(.56, .35, .75))
        scaled = projector.project_meshes((mesh,), view_direction=(1.12, .70, 1.50))
        self.assertEqual(front, scaled); self.assertEqual(mesh, before)
        self.assertEqual((projector._EYE, projector._RIGHT, projector._UP), globals_before)
        seen = []
        edge = (-4., 0., 4., .2, .3, -2., 4., 0., 4., .2, .3, -2.)
        with patch('assembly_style.edge_batches', side_effect=lambda meshes, style: [(meshes[0], edge)]), \
             patch('liquid_silhouette046.clip_edge', side_effect=lambda a, b, tag, direction: seen.append(direction) or True):
            self.assertTrue(projector.project_meshes((mesh,), 'notebook_line', view_direction=(.56, .35, .75)))
            self.assertTrue(seen); self.assertGreater(seen[-1][2], 0.)
            seen.clear()
            self.assertTrue(projector.project_meshes((mesh,), 'notebook_line'))
            self.assertTrue(seen); self.assertIs(seen[-1], projector._EYE)

    def test_actual_front_port_caps_reach_collar_back_view_hits_tank_geometry(self):
        row = get_radiator('corsair-xr5-240'); before = deepcopy(row)
        meshes, physical = radiator._geometry(row); facets = actual_facets(meshes)
        positive, negative = unit((.56, .35, .75)), projector._EYE
        collar = next(mesh for mesh in meshes if mesh.name == 'cooler-radiator044-port-collars')
        self.assertEqual(len(physical['ports']), 2)
        expected_back = {'connection-1': 'cooler-radiator044-end-tanks',
                         'connection-2': 'cooler-radiator044-folded-rails'}
        actual_materials = {name: dict(low=low, high=high,
                                      alpha=next(m.color[3] for m in meshes if m.name == name))
                            for name, low, high, triangles in facets}
        for port in physical['ports']:
            self.assertEqual(port['face'], 'front'); self.assertEqual(port['normal'], (0., 0., 1.))
            position = port['position']; candidates = []
            for at in range(0, len(collar.vertices), 18):
                normal = collar.vertices[at+3:at+6]
                if normal[2] < .9 or dot(normal, positive) <= 0.: continue
                triangle = [add(collar.vertices[at+k:at+k+3], collar.position) for k in (0, 6, 12)]
                center = tuple(sum(p[k] for p in triangle)/3 for k in range(3))
                # A real lower-left cap triangle, away from the end/outer-rail
                # silhouette. No target point, port or source mesh is moved.
                if (math.dist(center, position) < 9. and center[0] < position[0]-1.
                        and center[1] < position[1]-1.):
                    candidates.append((at//18, center))
            self.assertTrue(candidates)
            witnesses = []
            for triangle_index, center in candidates:
                front_distance, front_names = first_hit(facets, center, positive)
                back_distance, back_names = first_hit(facets, center, negative)
                if (collar.name in front_names and abs(front_distance-2000.) < 1e-4
                        and back_names == [expected_back[port['id']]] and back_distance < 1999.9):
                    material = actual_materials[expected_back[port['id']]]
                    self.assertEqual(material['alpha'], 1.)
                    # The observed rear-skin plane is one source thickness
                    # before this same cap point along the original ray.
                    self.assertAlmostEqual(2000.-back_distance,
                                           row['dimensions_mm']['thickness']/abs(negative[2]), places=5)
                    hit = add(center, mul(negative, 2000.-back_distance))
                    self.assertTrue(all(material['low'][k]-1e-6 <= hit[k] <= material['high'][k]+1e-6
                                        for k in range(3)))
                    witnesses.append(dict(port_id=port['id'], source_triangle=triangle_index,
                                          actual_triangle_centroid=center, front_names=front_names,
                                          front_distance=front_distance, back_names=back_names,
                                          back_distance=back_distance, back_source_material=material,
                                          actual_back_hit_position=hit,
                                          front_same_plane_tie=len(front_names) > 1))
            self.assertTrue(witnesses, 'Need actual collar-first versus tank-first witness for each real mouth')
            CAMERA_WITNESSES.append(witnesses[0])
        front = radiator.art_from_reference(row, 'miniature')
        back = projector.project_meshes(meshes, 'miniature', max_triangles=2800)
        self.assertTrue(front); self.assertTrue(back)
        self.assertEqual(front['art_details']['geometry_digest'], back['art_details']['geometry_digest'])
        self.assertNotEqual(front['svg'], back['svg'])
        self.assertEqual(front['art_details']['reference_camera_side'], 'front_positive_z')
        self.assertEqual(front['art_details']['reference_view_direction'], (.56, .35, .75))
        self.assertEqual(front['rotors'], []); self.assertEqual(row, before)
        self.assertFalse(any(m.rotor for m in meshes))


if __name__ == '__main__': unittest.main()
