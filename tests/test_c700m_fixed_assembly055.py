"""Fixed C700M body datums and real lower/tray material, not CAD fit claims."""
import copy
import math
import unittest

from assembly_geometry import Mesh, box, build_scene, color
from assembly_case_exteriors040 import replace_shell
from assembly_case_shrouds052 import apply_layout_anchors
from assembly_c700m_case055 import (BRACKET_ID, EXACT_ID, FLOOR_ID, SUPPORT_ID, TRAY_ID,
                                    add_tray, build, finish, layout_reference)
from chassis_catalog import get_case


def bounds(mesh):
    return tuple(tuple(fn(mesh.vertices[k::6]) + mesh.position[k] for k in range(3))
                 for fn in (min, max))


def sub(a, b):
    return tuple(a[k] - b[k] for k in range(3))


def dot(a, b):
    return sum(a[k] * b[k] for k in range(3))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def inside(point, mesh):
    """Ray parity through actual triangles, deduplicating shared diagonals."""
    direction = (.713, .377, 1.)
    hits = []
    for at in range(0, len(mesh.vertices), 18):
        a, b, c = (tuple(mesh.vertices[at+j+k] + mesh.position[k] for k in range(3)) for j in (0, 6, 12))
        e1, e2 = sub(b, a), sub(c, a)
        p = cross(direction, e2)
        determinant = dot(e1, p)
        if abs(determinant) < 1e-11:
            continue
        delta = sub(point, a)
        u = dot(delta, p) / determinant
        q = cross(delta, e1)
        v = dot(direction, q) / determinant
        distance = dot(e2, q) / determinant
        if -1e-9 <= u <= 1+1e-9 and v >= -1e-9 and u+v <= 1+1e-9 and distance > 1e-8:
            hits.append(distance)
    unique = []
    for value in sorted(hits):
        if not unique or abs(value-unique[-1]) > 1e-7:
            unique.append(value)
    return len(unique) % 2 == 1


class C700MFixedAssembly055Tests(unittest.TestCase):
    def setUp(self):
        self.case = get_case(EXACT_ID)
        self.dimensions = tuple(self.case['dimensions_mm'][key] for key in ('width', 'height', 'depth'))
        self.tone = color('#24343e')
        self.meshes, self.metadata = build(self.case, self.dimensions, self.tone)

    def test_fixed_body_datum_is_not_the_external_handle_depth(self):
        pose = layout_reference(self.case, self.dimensions)
        self.assertEqual(self.dimensions, (306, 651, 650))
        for actual, expected in zip(pose['routing_body_dimensions_mm'], (269.28, 572.88, 611.)):
            self.assertAlmostEqual(actual, expected)
        self.assertAlmostEqual(pose['board_rear_z_mm'], -291.5)
        self.assertAlmostEqual(pose['board_rear_z_mm'] - (-650./2.+14.), 19.5)
        self.assertFalse(pose['board_positions_verified'])
        self.assertFalse(pose['manufacturing_fit_verified'])
        self.assertFalse(pose['rear_io_and_pcie_apertures_modelled'])
        self.assertEqual(pose['fan_constraints']['bottom']['max_count_by_size_mm'], {'120': 2, '140': 2})
        self.assertFalse(pose['bottom_radiator_reference']['bottom_360_supported'])

    def test_no_hardware_style_or_sibling_case_changes_fixed_material(self):
        altered = dict(self.case, selected_psu='different', selected_gpu='different', appearance_style='cartoon')
        self.assertEqual(build(altered, self.dimensions, self.tone), (self.meshes, self.metadata))
        sentinel = (Mesh('retained-hardware', box(1., 2., 3.), self.tone, component='gpu'),)
        for case in (dict(self.case, id='cooler-master-cosmos-c700p'), {}, None):
            self.assertEqual(build(case, self.dimensions, self.tone), ((), {}))
            self.assertIs(add_tray(sentinel, case, self.dimensions)[0], sentinel)
        self.assertEqual(build(self.case, (306, float('nan'), 650), self.tone), ((), {}))

    def test_source_lower_frame_and_floor_have_real_voids_and_positive_material(self):
        by_id = {mesh.part_id: mesh for mesh in self.meshes}
        floor, bracket = by_id[FLOOR_ID], by_id[BRACKET_ID]
        pose = layout_reference(self.case, self.dimensions)['body_floor_reference']
        floor_y = pose['floor_top_y_mm'] - pose['floor_thickness_mm']/2.
        self.assertTrue(inside((0., floor_y, 0.), floor))
        self.assertFalse(inside((56.5488, floor_y, 34.8125), floor))
        bracket_y = pose['bracket_top_y_mm'] - .6
        bracket_z = pose['bracket_center_z_mm']
        self.assertFalse(inside((0., bracket_y, bracket_z), bracket))
        self.assertTrue(inside((76., bracket_y, bracket_z), bracket))
        self.assertFalse(inside((53., bracket_y, bracket_z+100.), bracket))
        support = bounds(by_id[SUPPORT_ID])
        self.assertLess(support[1][2], bounds(bracket)[0][2])
        self.assertAlmostEqual(support[1][1], layout_reference(self.case, self.dimensions)['psu']['floor_y_mm'])
        self.assertAlmostEqual(support[0][1], pose['floor_top_y_mm'])

    def test_tray_uses_fixed_openings_matching_material_cells(self):
        result, meta = add_tray((), self.case, self.dimensions)
        tray, = result
        self.assertEqual(tray.part_id, TRAY_ID)
        self.assertFalse(meta['factory_hole_positions_verified'])
        self.assertFalse(meta['selected_component_geometry_used'])
        hole = next(row for row in meta['openings'] if row['role'] == 'cpu_backplate_access')
        point = (meta['plane_x_mm'], (hole['y0']+hole['y1'])/2., (hole['z0']+hole['z1'])/2.)
        self.assertFalse(inside(point, tray))
        self.assertFalse(any(all(row['min'][k] < point[k] < row['max'][k] for k in range(3)) for row in meta['solid_bounds']))
        material = (meta['plane_x_mm'], meta['bounds']['min'][1]+2., meta['bounds']['min'][2]+2.)
        self.assertTrue(inside(material, tray))
        self.assertTrue(any(all(row['min'][k] < material[k] < row['max'][k] for k in range(3)) for row in meta['solid_bounds']))

    def test_rear_and_far_walls_are_retained_not_hidden_to_erase_penetration(self):
        hardware = Mesh('selected-hardware', box(7., 8., 9.), self.tone, component='gpu', part_id='gpu:0')
        shell = replace_shell((*self.meshes, hardware), self.dimensions, self.case)
        self.assertIn(hardware, shell)
        self.assertIs(next(mesh for mesh in shell if mesh is hardware), hardware)
        w, h, d = self.dimensions
        expected = tuple(value - d*.94/2. if at % 6 == 2 else value
                         for at, value in enumerate(box(w*.88, h*.88, 2.)))
        rear = next(mesh for mesh in shell if mesh.name == 'case-cosmos-metal-body' and mesh.color == self.tone)
        self.assertEqual(rear.vertices, expected)
        self.assertEqual(rear.vertex_count//3, 12)
        far = next(mesh for mesh in shell if mesh.name == 'case-cosmos-metal-body' and mesh is not rear)
        self.assertEqual(far.vertex_count//3, 12)
        self.assertEqual(sum(mesh.part_id == FLOOR_ID for mesh in shell), 1)
        self.assertEqual(sum(mesh.part_id == SUPPORT_ID for mesh in shell), 1)
        sibling = replace_shell((hardware,), self.dimensions, dict(self.case, id='cooler-master-cosmos-c700p'))
        old_batch = next(mesh for mesh in sibling if mesh.name == 'case-cosmos-metal-body' and mesh.color == self.tone)
        self.assertEqual(old_batch.vertex_count//3, 24)

    def test_bottom_bracket_requires_actual_generated_bottom_part_identity(self):
        shell = replace_shell(self.meshes, self.dimensions, self.case)
        bracket = next(mesh for mesh in self.meshes if mesh.part_id == BRACKET_ID)
        staged = (*shell, bracket)
        absent, no_meta = finish(staged, (), {'parts': [dict(id='rejected', kind='case_fan', mount='bottom')]}, self.metadata)
        self.assertFalse(any(mesh.part_id == BRACKET_ID for mesh in absent))
        self.assertFalse(no_meta['bracket_installed'])
        fan = Mesh('actual-bottom-fan', box(120., 25., 120.), self.tone, component='fans', part_id='fans:bottom:0')
        cooling = dict(parts=[dict(id=fan.part_id, kind='case_fan', mount='bottom')])
        result, installed = finish(staged, (fan,), cooling, self.metadata)
        self.assertIs(next(mesh for mesh in result if mesh.part_id == BRACKET_ID), bracket)
        self.assertTrue(installed['bracket_installed'])
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            finish(shell, (fan,), cooling, self.metadata)

    def test_actual_psu_envelope_is_located_from_fixed_faces_without_rescaling(self):
        from component_catalog import get_component
        psu = get_component('corsair-rm1000x-2024')
        spec = dict(auxiliary=dict(psu=dict(model_id=psu['id'])))
        anchor = apply_layout_anchors({}, spec, layout_reference(self.case, self.dimensions))['psu']
        dims = psu['dimensions_mm']
        self.assertEqual(anchor['world_dimensions_mm'], tuple(dims[key] for key in ('width', 'height', 'length')))
        pose = layout_reference(self.case, self.dimensions)['psu']
        self.assertAlmostEqual(anchor['position'][1]-dims['height']/2., pose['floor_y_mm'])
        self.assertAlmostEqual(anchor['position'][2]-dims['length']/2., pose['rear_z_mm'])
        self.assertFalse(anchor['placement_verified'])

    def test_every_new_triangle_is_finite_nonzero_and_has_its_real_outward_normal(self):
        tray, _ = add_tray((), self.case, self.dimensions)
        for mesh in (*self.meshes, *tray):
            for at in range(0, len(mesh.vertices), 18):
                row = mesh.vertices[at:at+18]
                self.assertTrue(all(math.isfinite(value) for value in row))
                normal = cross(sub(row[6:9], row[:3]), sub(row[12:15], row[:3]))
                length = math.hypot(*normal)
                self.assertGreater(length, 1e-12)
                self.assertGreater(dot(tuple(value/length for value in normal), row[3:6]), .999999)

    def test_public_core_construction_consumes_the_body_datum_and_preserves_gpu_size(self):
        # Minimal real-sized core isolates the case placement consumer. A
        # separate complete reference check covers rich selected art/cooling.
        spec = dict(case=copy.deepcopy(self.case), visual_style='miniature', detail_level='eco',
                    cpu=dict(style='chip'), board=dict(dimensions_mm=dict(height=305., width=244.)),
                    gpu=dict(present=True, length_mm=357.6, width_mm=149.3, thickness_mm=76.),
                    memory=dict(count=0), cooling={}, auxiliary=dict(cables_enabled=False))
        original = copy.deepcopy(spec)
        scene = build_scene(spec)
        self.assertEqual(spec, original)
        self.assertEqual(scene.metadata['canonical_board_rear_mm'], -291.5)
        self.assertEqual(scene.metadata['canonical_gpu_bracket_mm'], -291.5)
        board = next(mesh for mesh in scene.meshes if mesh.name == 'motherboard-reference')
        gpu = next(mesh for mesh in scene.meshes if mesh.name == 'gpu-shroud')
        self.assertAlmostEqual(bounds(board)[0][2], -291.5)
        self.assertAlmostEqual(bounds(gpu)[1][2]-bounds(gpu)[0][2], 357.6)
        rear_high = -650.*.94/2.+1.
        self.assertGreater(bounds(board)[0][2], rear_high)
        self.assertGreater(bounds(gpu)[0][2], rear_high)
        self.assertEqual(sum(mesh.part_id == TRAY_ID for mesh in scene.meshes), 1)
        self.assertFalse(scene.metadata['case_shroud']['bracket_installed'])


if __name__ == '__main__':
    unittest.main()
