"""Actual fitting/tube meshes and optional-pack lifecycle, without Qt or I/O probes."""
import builtins
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import hardware_packs as packs
from assembly_cooling import _add, _sub, _mul, _cross, _dot, _basis
from assembly_style import apply_model_styles
from liquid_component_runtime046 import choices, get_component
from liquid_fitting_tube_expansion046 import records, get_record
from liquid_geometry046 import build_component
from liquid_pack_schema046 import selector_for, validate_reference
from liquid_selection046 import fitting_ends, port_compatibility, tube_compatibility, resolve
from top_bar_config import HARDWARE_ICON_STYLES


def segment_hit(meshes, start, end):
    """Finite independent Moller-Trumbore ray against actual mesh triangles."""
    direction = _sub(end, start)
    for mesh in meshes:
        vertices = mesh.vertices
        for offset in range(0, len(vertices), 18):
            a, b, c = (_add(vertices[offset+k:offset+k+3], mesh.position) for k in (0, 6, 12))
            edge1, edge2 = _sub(b, a), _sub(c, a)
            perpendicular = _cross(direction, edge2)
            determinant = _dot(edge1, perpendicular)
            if abs(determinant) < 1e-9:
                continue
            inv = 1/determinant
            delta = _sub(start, a)
            u = inv * _dot(delta, perpendicular)
            if u < -1e-7 or u > 1+1e-7:
                continue
            cross = _cross(delta, edge1)
            v = inv * _dot(direction, cross)
            if v < -1e-7 or u+v > 1+1e-7:
                continue
            t = inv * _dot(edge2, cross)
            if 1e-5 < t < 1-1e-5:
                return True
    return False


def wrapper(row):
    return dict(id=row['id'], label=row['label'], vendor=row['brand'], series=row['series'],
                aliases=[row['id']], sources=list(row['sources']), selector=selector_for(row),
                reference=copy.deepcopy(row))


class LiquidFittingGeometry046Tests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL', 'socket.socket', 'threading.Thread.start', 'subprocess.Popen'):
            self.enterContext(patch(target, side_effect=AssertionError('No device, network, window or worker')))

    def test_all_31_three_lods_have_real_finite_geometry_and_detached_metadata(self):
        for row in records():
            validate_reference(row)
            original = copy.deepcopy(row)
            previous = 0
            for level, budget in (('eco', 2600), ('balanced', 5200), ('close', 9000)):
                with self.subTest(model=row['id'], level=level):
                    meshes, meta = build_component(row, level)
                    self.assertTrue(meshes)
                    count = sum(mesh.vertex_count//3 for mesh in meshes)
                    self.assertEqual(meta['triangle_count'], count)
                    self.assertGreater(count, previous)
                    previous = count
                    self.assertLessEqual(count, budget)
                    self.assertLessEqual(len(meshes), 8)
                    self.assertEqual(meta['dimensions_mm'], row['dimensions_mm'])
                    self.assertEqual(meta['reference_envelope_mm'], row['reference_envelope_mm'])
                    self.assertFalse(meta['telemetry_bound'])
                    self.assertFalse(meta['fit_verified'])
                    self.assertFalse(meta['coordinates_verified'])
                    for mesh in meshes:
                        self.assertEqual(mesh.component, 'cooler')
                        self.assertEqual(mesh.part_id, 'cooler:'+row['part_kind'])
                        self.assertFalse(mesh.rotor)
                        for offset in range(0, len(mesh.vertices), 6):
                            point, normal = mesh.vertices[offset:offset+3], mesh.vertices[offset+3:offset+6]
                            self.assertTrue(all(math.isfinite(value) for value in point+normal))
                            self.assertAlmostEqual(_dot(normal, normal), 1, places=6)
                        for offset in range(0, len(mesh.vertices), 18):
                            a, b, c = (mesh.vertices[offset+k:offset+k+3] for k in (0, 6, 12))
                            normal = mesh.vertices[offset+3:offset+6]
                            self.assertGreater(_dot(_cross(_sub(b, a), _sub(c, a)), normal), 1e-10)
            self.assertEqual(row, original)

    def test_every_flow_mouth_is_open_all_lods_and_closure_remains_solid(self):
        for row in records():
            for level in ('eco', 'balanced', 'close'):
                meshes, meta = build_component(row, level)
                ports = meta['ports']
                if row['part_kind'] == 'tubing':
                    # The supplied length is not rendered as an 0.5–3.3m stock
                    # rod. Check the actual declared short reference segment.
                    half = row['reference_envelope_mm']['height']/2
                    ports = [dict(id='tube-lower', position=(0., -half, 0.), normal=(0., -1., 0.), role='connection'),
                             dict(id='tube-upper', position=(0., half, 0.), normal=(0., 1., 0.), role='connection')]
                for port in ports:
                    p, normal = port['position'], port['normal']
                    with self.subTest(model=row['id'], level=level, port=port['id']):
                        offsets = [(0., 0., 0.)]
                        if level == 'balanced' and port['role'] != 'closure':
                            first, second, _ = _basis(normal)
                            offsets += [_mul(first, 1.0), _mul(first, -1.0), _mul(second, 1.0), _mul(second, -1.0)]
                        for offset in offsets:
                            sample = _add(p, offset)
                            hit = segment_hit(meshes, _add(sample, _mul(normal, 3)), _sub(sample, _mul(normal, 5)))
                            self.assertEqual(hit, port['role'] == 'closure')

    def test_open_mouth_is_surrounded_by_real_wall_not_only_empty_anchors(self):
        for row in records('fitting'):
            if row['form'] == 'plug':
                continue
            meshes, meta = build_component(row)
            diameter = min(row['reference_envelope_mm'][key] for key in ('width', 'depth'))
            for port in meta['ports']:
                normal = port['normal']
                tangent = _basis(normal)[0]
                probes = []
                for ratio in (.28, .34, .40, .46):
                    p = _add(port['position'], _mul(tangent, diameter*ratio))
                    probes.append(segment_hit(meshes, _add(p, _mul(normal, 2)), _sub(p, _mul(normal, 3))))
                self.assertTrue(any(probes), (row['id'], port['id']))

    def test_ball_valve_has_two_female_shoulders_and_a_broad_side_lever(self):
        row = get_record('corsair-xf-ball-valve')
        meshes, metadata = build_component(row)
        self.assertEqual([p['thread_gender'] for p in metadata['ports']], ['female', 'female'])
        barrel = next(m for m in meshes if m.name == 'loop-valve-barrel')
        shoulders = next(m for m in meshes if m.name == 'loop-valve-female-shoulders')
        lever = next(m for m in meshes if m.name == 'loop-valve-lever-paddle')
        span = lambda mesh, axis: max(mesh.vertices[axis::6])-min(mesh.vertices[axis::6])
        self.assertGreater(span(shoulders, 0), span(barrel, 0)*.75)
        self.assertGreater(span(lever, 1), span(barrel, 1)*.7)
        self.assertGreater(min(abs(x) for x in lever.vertices[0::6]), span(barrel, 0)/2)
        self.assertFalse(metadata['fit_verified'])

    def test_reference_pose_preserves_thin_elbows_and_all_13_styles_share_geometry(self):
        self.assertEqual(len(HARDWARE_ICON_STYLES), 13)
        for row in records():
            meshes, meta = build_component(row)
            physical = [mesh.vertices for mesh in meshes]
            for style in HARDWARE_ICON_STYLES:
                styled, appearance = apply_model_styles(meshes, style, {}, (200, 200, 200), {'front': 'open'})
                self.assertEqual([mesh.vertices for mesh in styled], physical, (row['id'], style))
                self.assertEqual(appearance['visual_style'], style)
                self.assertFalse(appearance['decorative_expression'])
                self.assertEqual(len(styled), len(meshes))
            if row['id'] in ('alphacool-eiszapfen-rotary-90', 'thermaltake-pacific-dual-hard-90-16'):
                first = meta['ports'][0]['position']
                self.assertAlmostEqual(first[1], -row['reference_envelope_mm']['height']/2)
                self.assertNotAlmostEqual(first[1], -row['dimensions_mm']['height']/2)

    def test_rigid_placement_transforms_geometry_and_port_normals_together(self):
        center = (12., -8., 19.)
        rotate = lambda v: (-v[1], v[0], v[2])
        original_axes = ((1., 0., 0.), (0., 0., -1.), (0., 1., 0.))
        axes = tuple(rotate(axis) for axis in original_axes)
        for identity in ('alphacool-eiszapfen-soft-90-13-10', 'alphacool-eiszapfen-static-45', 'thermaltake-pacific-dual-hard-90-16', 'corsair-xt-hardline-14-10'):
            row = get_record(identity)
            plain, before = build_component(row)
            moved, after = build_component(row, center=center, basis=axes)
            self.assertEqual([m.name for m in moved], [m.name for m in plain])
            self.assertEqual(before['triangle_count'], after['triangle_count'])
            for a, b in zip(plain, moved):
                for offset in range(0, len(a.vertices), 6):
                    expected_point = _add(rotate(a.vertices[offset:offset+3]), center)
                    expected_normal = rotate(a.vertices[offset+3:offset+6])
                    for left, right in zip(b.vertices[offset:offset+6], expected_point+expected_normal):
                        self.assertAlmostEqual(left, right, places=6)
            for a, b in zip(before['ports'], after['ports']):
                for left, right in zip(b['position'], _add(rotate(a['position']), center)):
                    self.assertAlmostEqual(left, right)
                for left, right in zip(b['normal'], rotate(a['normal'])):
                    self.assertAlmostEqual(left, right)

    def test_elbow_body_is_one_continuous_loft_with_only_two_open_end_loops(self):
        for row in records('fitting'):
            if not row['fitting_angle_deg']:
                continue
            for level in ('eco', 'balanced', 'close'):
                meshes, _ = build_component(row, level)
                bodies = [m for m in meshes if 'elbow-body' in m.name]
                self.assertEqual(len(bodies), 1)
                counts = {}
                for offset in range(0, len(bodies[0].vertices), 18):
                    points = [tuple(round(v, 6) for v in bodies[0].vertices[offset+k:offset+k+3]) for k in (0, 6, 12)]
                    for a, b in zip(points, points[1:]+points[:1]):
                        edge = tuple(sorted((a, b)))
                        counts[edge] = counts.get(edge, 0)+1
                self.assertTrue(all(n in (1, 2) for n in counts.values()), (row['id'], level))
                graph = {}
                for (a, b), count in counts.items():
                    if count != 1:
                        continue
                    graph.setdefault(a, set()).add(b)
                    graph.setdefault(b, set()).add(a)
                self.assertTrue(graph)
                self.assertTrue(all(len(neighbors) == 2 for neighbors in graph.values()), (row['id'], level))
                unseen = set(graph)
                loops = 0
                while unseen:
                    loops += 1
                    pending = [unseen.pop()]
                    while pending:
                        for neighbor in graph[pending.pop()]:
                            if neighbor in unseen:
                                unseen.remove(neighbor)
                                pending.append(neighbor)
                self.assertEqual(loops, 2, (row['id'], level))

    def test_dual_unknown_and_closure_cannot_become_default_thread_to_tube(self):
        tube = get_record('thermaltake-v-tubler-petg-16-12')
        dual = get_record('thermaltake-pacific-dual-hard-90-16')
        self.assertEqual(tube_compatibility(dual, tube), [])
        self.assertFalse(fitting_ends(dual))
        self.assertEqual(port_compatibility(dict(thread='G1/4', thread_gender='female'), dual), 'fitting_ends_unknown')
        for identity in ('alphacool-eiszapfen-static-45', 'alphacool-eiszapfen-plug'):
            self.assertFalse(fitting_ends(get_record(identity)))
        fitting = get_record('thermaltake-f-pro-hard-16')
        self.assertTrue(fitting_ends(fitting))
        self.assertEqual(port_compatibility(dict(thread='G1/4', thread_gender='female'), fitting), '')
        self.assertEqual(port_compatibility(dict(thread='G1/4', thread_gender='unknown'), fitting), 'port_thread_or_gender_unknown')
        self.assertEqual(port_compatibility(dict(thread=None, thread_gender='none'), fitting), 'port_thread_or_gender_unknown')
        self.assertEqual(port_compatibility(dict(thread='G1/4', thread_gender='male'), fitting), 'port_thread_or_gender_mismatch')
        selected = {'loop_components_mode': 'selected', 'fitting_model': dual['id'], 'tubing_model': tube['id']}
        models = {dual['id']: dual, tube['id']: tube}
        result = resolve(selected, {}, getter=lambda kind, identity: models.get(identity))
        self.assertIn('fitting_ends_unknown', {r['reason'] for r in result['issues']})
        self.assertFalse(result['can_draw_connections'])

    def test_real_pack_31_products_eight_lru_upgrade_removal_without_author_imports(self):
        source = list(records())
        raw = packs.make_pack('test-loop-components', 'Test loop components', [wrapper(r) for r in source], kind='loop')
        real_import = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name in ('liquid_fitting_tube_expansion046', 'liquid_block_pump_expansion046') or name.startswith('PySide6'):
                raise AssertionError('Selected runtime must not import author catalogs or graphics')
            return real_import(name, *args, **kwargs)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root/'test.dspack'
            path.write_bytes(raw)
            store = packs.PackStore(root/'installed')
            with patch.object(packs, '_store', store), patch('builtins.__import__', side_effect=guarded):
                store.install(path)
                self.assertEqual((len(choices('fitting')), len(choices('tubing'))), (20, 11))
                for row in source[:9]:
                    self.assertEqual(get_component(row['part_kind'], row['id']), row)
                self.assertEqual(len(store._selected), 8)
                self.assertNotIn(('loop', source[0]['id']), store._selected)
                detached = get_component(source[1]['part_kind'], source[1]['id'])
                detached['ports'].clear()
                self.assertEqual(get_component(source[1]['part_kind'], source[1]['id']), source[1])
                self.assertIsNone(store.get_cpu(source[1]['id']))
                generation = store.generation
                revised = copy.deepcopy(source)
                revised[1]['label'] += ' revised'
                path.write_bytes(packs.make_pack('test-loop-components', 'Test loop components', [wrapper(r) for r in revised], version='1.0.1', kind='loop'))
                store.install(path)
                self.assertGreater(store.generation, generation)
                self.assertFalse(store._selected)
                self.assertEqual(get_component(revised[1]['part_kind'], revised[1]['id'])['label'], revised[1]['label'])
                generation = store.generation
                self.assertTrue(store.remove('test-loop-components'))
                self.assertGreater(store.generation, generation)
                self.assertFalse(store._selected)
                self.assertEqual(get_component(source[1]['part_kind'], source[1]['id']), {})
                self.assertEqual(choices('fitting'), [])


if __name__ == '__main__':
    unittest.main()
