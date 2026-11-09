"""Source-fixed MOD-5 bottom material, not complete mechanical compatibility.

Manufacturer images are not test assets. Pure construction checks run without
Scene/GUI; actual fan and host checks use the existing public producers.
"""
import copy
import hashlib
import math
import unittest
from unittest.mock import patch

from assembly_geometry import Mesh, box, color
from assembly_mod5_bottom052 import (CASE_ID, PRODUCT, MANUAL, SUPPORT_ID,
    BRACKET_ID, CRADLE_ID, build, describe, layout_reference)
from chassis_catalog import CASES, get_case
import test_shroud_other052 as material


DIMENSIONS = (255., 635., 600.)
STYLES = ('miniature', 'cartoon', 'notebook_color', 'notebook_line', 'sticker', 'papercut')
RAYS = ((1., .173, .317), (.317, 1., .173), (.173, .317, 1.))
OLD_WITNESSES = ((59.988579857486414, -307.4985857864376, -141.00141421356238),
                 (54.61794593823564, -307.4985857864376, 153.00141421356238))


def _inside(point, mesh):
    return all(material._ray_inside(point, material._world(mesh), ray) for ray in RAYS)


def _dim(case):
    return tuple(case['dimensions_mm'][key] for key in ('width', 'height', 'depth'))


def _horizontal_face_covers(mesh, point, outward):
    """Actual facet contact; compound-box XOR is not a union-solid oracle."""
    for triangle in material._world(mesh):
        normal = material._cross(material._sub(triangle[1], triangle[0]),
            material._sub(triangle[2], triangle[0]))
        if normal[1]*outward <= 0. or abs(normal[0])+abs(normal[2]) > 1.e-8:
            continue
        if any(abs(p[1]-point[1]) > 1.e-8 for p in triangle):
            continue
        values = []
        for a, b in zip(triangle, (*triangle[1:], triangle[0])):
            values.append((b[0]-a[0])*(point[2]-a[2])-(b[2]-a[2])*(point[0]-a[0]))
        if min(values) >= -1.e-8 or max(values) <= 1.e-8:
            return True
    return False


class Mod5BottomPure052Tests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL', 'socket.socket', 'subprocess.Popen',
                     'threading.Thread.start', 'assembly_geometry.build_scene'):
            self.enterContext(patch(name, create=True,
                side_effect=AssertionError('Pure source material construction only')))
        self.case = get_case(CASE_ID)
        self.meshes, self.meta = build(self.case, DIMENSIONS, color('#24343e'))

    def test_exact_id_fixed_detached_three_part_source_contract(self):
        previous = copy.deepcopy(self.case)
        self.assertEqual(self.meta, describe(self.case, DIMENSIONS))
        self.assertEqual({m.part_id for m in self.meshes}, {SUPPORT_ID, BRACKET_ID, CRADLE_ID})
        self.assertEqual({p['id'] for p in self.meta['parts']}, {SUPPORT_ID, BRACKET_ID, CRADLE_ID})
        self.assertTrue(all(p['kind'] == 'case_structure' and p['source_url'] == MANUAL
                            for p in self.meta['parts']))
        self.assertEqual(self.meta['source_urls'], (PRODUCT, MANUAL))
        self.assertEqual(self.meta['source_bottom_capacity'], {'count': 3, 'size_mm': 120})
        self.assertTrue(self.meta['source_bottom_capacity_verified'])
        self.assertEqual(self.case, previous)
        changed = copy.deepcopy(self.case)
        changed.update(selected_fan={'size_mm': 500, 'count': 20},
            selected_psu={'length_mm': 2000}, selected_gpu={'width_mm': 1000})
        self.assertEqual(build(changed, DIMENSIONS, color('#24343e')), (self.meshes, self.meta))
        self.meta['parts'][0]['id'] = 'mutated'
        self.assertEqual(describe(self.case, DIMENSIONS)['parts'][0]['id'], SUPPORT_ID)
        for key in ('dimensions_verified', 'positions_verified', 'cad_verified',
                    'thickness_verified', 'mounting_hole_positions_verified',
                    'exact_foot_count_verified', 'selected_component_geometry_used',
                    'psu_mount_pose_verified', 'motherboard_mount_pose_verified'):
            self.assertIs(describe(self.case, DIMENSIONS)[key], False)
        for case in CASES:
            if case['id'] != CASE_ID:
                self.assertEqual(build(case, _dim(case), color('#24343e')), ((), {}))
                self.assertEqual(describe(case, _dim(case)), {})
        for invalid in (None, (), (True, 635, 600), (255, float('inf'), 600),
                        (255, 635, 100000), (255, 635)):
            self.assertEqual(build(self.case, invalid, color('#24343e')), ((), {}))

    def test_finite_outward_non_degenerate_bounded_material(self):
        triangles = 0
        for mesh in self.meshes:
            self.assertEqual(mesh.component, 'case')
            self.assertFalse(mesh.rotor)
            self.assertEqual(mesh.position, (0., 0., 0.))
            self.assertEqual(len(mesh.vertices) % 18, 0)
            triangles += len(mesh.vertices)//18
            for at, triangle in zip(range(0, len(mesh.vertices), 18), material._world(mesh)):
                normal = material._cross(material._sub(triangle[1], triangle[0]),
                    material._sub(triangle[2], triangle[0]))
                self.assertGreater(material._dot(normal, normal), 1.e-16)
                for start in (0, 6, 12):
                    shading = mesh.vertices[at+start+3:at+start+6]
                    self.assertAlmostEqual(material._dot(shading, shading), 1., places=8)
                    self.assertGreater(material._dot(normal, shading), 0.)
                self.assertTrue(all(math.isfinite(v) for p in triangle for v in p))
            bounds = material._mesh_bounds(mesh)
            self.assertGreaterEqual(bounds[0][0], -127.5-1.e-8)
            self.assertLessEqual(bounds[1][0], 127.5+1.e-8)
            self.assertGreaterEqual(bounds[0][1], -316.15-1.e-8)
        self.assertLess(triangles, 1000)

    def test_three_real_air_apertures_neighbouring_sheet_and_perimeter_feet(self):
        frame = next(m for m in self.meshes if m.part_id == BRACKET_ID)
        supports = next(m for m in self.meshes if m.part_id == SUPPORT_ID)
        y = self.meta['bracket_center_y_reference_mm']
        for z in (-120., 0., 120.):
            self.assertFalse(_inside((0., y, z), frame))
            self.assertFalse(_inside((0., y, z), supports))
            self.assertTrue(_inside((65., y, z), frame))
        self.assertTrue(_inside((117.3, -313., -132.), supports))
        self.assertTrue(_inside((-117.3, -290., 174.), supports))
        # Both independent old-positive points remain in the old two planks,
        # but are now genuinely outside every replacement material batch.
        legacy = Mesh('old-full-width-feet', tuple(value for z in (-162., 174.)
            for value in tuple(v+(0., -311.15, z)[i % 6] if i % 6 < 3 else v
                for i, v in enumerate(box(209.1, 10., 42.)))), color('#24343e'))
        for point in OLD_WITNESSES:
            self.assertTrue(_inside(point, legacy))
            self.assertTrue(all(not _inside(point, mesh) for mesh in self.meshes))

    def test_six_styles_share_physical_arrays_and_exact_part_ids(self):
        from assembly_style import apply_model_styles
        for style in STYLES:
            styled, _ = apply_model_styles(self.meshes, style, {}, DIMENSIONS, self.case['panels'])
            physical = [m for m in styled if not m.name.startswith('style-')]
            self.assertEqual(len(physical), len(self.meshes))
            for actual, original in zip(physical, self.meshes):
                self.assertIs(actual.vertices, original.vertices)
                self.assertEqual((actual.part_id, actual.position, actual.axis, actual.rotor),
                    (original.part_id, original.position, original.axis, original.rotor))

    def test_supports_and_cassette_ears_really_join_retained_lower_armour(self):
        from assembly_case_exteriors040 import replace_shell
        lower = next(m for m in replace_shell((), DIMENSIONS, self.case)
                     if m.name == 'case-mod5-reference-lower-armour')
        supports = next(m for m in self.meshes if m.part_id == SUPPORT_ID)
        cassette = next(m for m in self.meshes if m.part_id == BRACKET_ID)
        # Independent interior points in both closed materials, not only two
        # overlapping aggregate boxes. All four feet actually join armour.
        for side in (-1., 1.):
            for z, y in ((-132., -310.55), (174., -272.45)):
                point = (side*125.5, y, z)
                self.assertTrue(_inside(point, supports), point)
                self.assertTrue(_inside(point, lower), point)
            for z in (-120., 60.):
                point = (side*125.5, self.meta['bracket_center_y_reference_mm'], z)
                self.assertTrue(_inside(point, cassette), point)
                self.assertTrue(_inside(point, lower), point)
            point = (side*125.5, -635.*.36, -138.)
            self.assertTrue(_inside(point, supports), point)
            self.assertTrue(_inside(point, lower), point)

    def test_exact_shell_hook_retains_hardware_and_unmodified_original_material(self):
        from assembly_case_exteriors040 import replace_shell
        hardware = Mesh('test-hardware', box(1, 2, 3), color('#24343e'), component='gpu')
        meshes = replace_shell((hardware,), DIMENSIONS, self.case)
        self.assertIs(meshes[0], hardware)
        self.assertFalse(any(m.name == 'case-mod5-reference-feet' for m in meshes))
        self.assertEqual({m.part_id for m in meshes if m.part_id}, {SUPPORT_ID, BRACKET_ID, CRADLE_ID})
        expected = {
            'case-mod5-reference-upper-armour': 'ff2827cec4aec6769f3e014e897255d5c2e7faaac5c2a3c44264126dd5778d22',
            'case-mod5-reference-lower-armour': '231e7507b2ab32c81abf92a1aa5d81289448ff133a13e5af5d8917b28e05a5a7',
            'case-mod5-side-glass': 'a8dc73e6284fb0ff4d96e348a8312ed6e224c8cde5189c53d064b6feddb2d7d9',
        }
        for mesh in meshes:
            if mesh.name in expected:
                self.assertEqual(hashlib.sha256(repr(mesh).encode()).hexdigest(), expected.pop(mesh.name))
        self.assertFalse(expected)
        upper = next(m for m in meshes if m.name == 'case-mod5-reference-crossmembers')
        lower = tuple(value + (0., -635.*.36, -600.*.08)[i % 6] if i % 6 < 3 else value
            for i, value in enumerate(box(255.*.84, 9., 600.*.40)))
        from dataclasses import replace
        # Invert only the authorized removal of the former broad lower slab.
        # The retained upper member and all its fields must be exactly old.
        old_combined = replace(upper, vertices=(*lower, *upper.vertices))
        self.assertEqual(hashlib.sha256(repr(old_combined).encode()).hexdigest(),
            '860d0d66d4396576477c289e773ab150669a1a5581507aa2dc446045ee6920eb')
        rails = next(m for m in meshes if m.name == 'case-mod5-reference-tray-rails')
        self.assertEqual(rails.position, ((255.*.36+8.)-255.*.30, 0., 0.))
        self.assertGreater(material._mesh_bounds(rails)[0][0], 255.*.36)
        # Invert exactly the authorized rigid X translation. Original vertex
        # buffers/normals/Y/Z/colour, rather than a new summarizing hash, survive.
        self.assertEqual(hashlib.sha256(repr(replace(rails, position=(0., 0., 0.))).encode()).hexdigest(),
            '272ddf94bcd375addf8eb1f58c8aeaf392012de32f8e7bd3b91b95b79698f07c')
        # A feature token on an unreviewed ID must retain its legacy path;
        # it cannot acquire the exact manufacturer's new component identities.
        foreign = dict(self.case, id='unreviewed-modular-case')
        with patch('assembly_mod5_bottom052.build', side_effect=AssertionError('Exact model only')):
            values = replace_shell((), DIMENSIONS, foreign)
        self.assertTrue(any(m.name == 'case-mod5-reference-feet' for m in values))


class Mod5BottomActual052Tests(unittest.TestCase):
    def test_actual_three_p12_all_lods_all_children_and_historical_positive_control(self):
        from assembly_cooling import add_cooling
        from test_case_layout_hosts052 import _geometry, _positive_overlap
        case = get_case(CASE_ID)
        solids, _ = build(case, DIMENSIONS, color('#24343e'))
        spec = dict(case=case, cooling=dict(cpu_cooler='none', case_fans=[dict(
            model='arctic-p12-pwm', mount='bottom', count=3, direction='intake')]))
        anchors = dict(case=case, case_dimensions=DIMENSIONS)
        obstacles = tuple((m, _geometry(m)) for m in solids)
        for level in ('eco', 'balanced', 'close'):
            before, old_meta = add_cooling((), spec, level, anchors)
            after, meta = add_cooling(solids, spec, level, anchors)
            self.assertEqual(before, after)
            self.assertEqual(meta, old_meta)
            self.assertEqual(meta['rejected'], [])
            self.assertEqual(len(meta['fans']), 3)
            self.assertEqual(sum(m.rotor for m in after), 3)
            self.assertEqual(sum(m.name == 'case-fan-power-connector' for m in after), 3)
            self.assertTrue(all(f['axis'] == (0., -1., 0.) and f['rpm'] is None
                and f['rotation_default'] == 'static' for f in meta['fans']))
            for mesh in after:
                shape = _geometry(mesh)
                for other, obstacle in obstacles:
                    self.assertIsNone(_positive_overlap(shape, obstacle),
                        (level, mesh.name, other.name))
            if level == 'balanced':
                frames = [m for m in after if m.name == 'case-fan-frame']
                for point, frame in zip(OLD_WITNESSES, (frames[0], frames[2])):
                    self.assertTrue(_inside(point, frame))

    def test_actual_psu_all_children_three_lods_raised_reference_and_old_floor_negative(self):
        from assembly_auxiliary import add_auxiliary
        from assembly_case_shrouds052 import apply_layout_anchors
        from assembly_cooling import add_cooling
        from test_case_layout_hosts052 import _geometry, _positive_overlap
        case = get_case(CASE_ID)
        spec = dict(case=case, auxiliary=dict(psu=dict(model_id='corsair-rm1000x-2024'),
            cables_enabled=False), cooling=dict(cpu_cooler='none', case_fans=[dict(
            model='arctic-p12-pwm', mount='bottom', count=3, direction='intake')]))
        original = dict(case=case, case_dimensions=DIMENSIONS, connectors={})
        layout = layout_reference(case, DIMENSIONS)
        anchors = apply_layout_anchors(original, spec, layout)
        self.assertEqual(anchors['psu']['basis'], ((-1., 0., 0.), (0., -1., 0.), (0., 0., 1.)))
        self.assertAlmostEqual(anchors['psu']['position'][1], -635.*.38+43.)
        solids, meta = build(case, DIMENSIONS, color('#24343e'))
        obstacles = tuple((m, _geometry(m)) for m in solids)
        self.assertFalse(layout['positions_verified'])
        self.assertEqual(layout['source_psu_option'], '02_reference')
        for level in ('eco', 'balanced', 'close'):
            psus, info = add_auxiliary(spec, anchors, level)
            fans, fan_info = add_cooling((), spec, level, original)
            fan_shapes = tuple((fan, _geometry(fan)) for fan in fans)
            self.assertEqual(info['device_counts']['psu'], 1)
            self.assertEqual(info['rejected'], [])
            self.assertEqual(len(fan_info['fans']), 3)
            self.assertTrue(all(m.component == 'psu' for m in psus))
            # Genuine bearing: the fixed lands meet the actual flipped PSU
            # lower shell at the same plane; neither a floating gap nor a
            # positive-volume interpenetration is accepted as support.
            shell = next(m for m in psus if m.name == 'psu-shell')
            cradle = next(m for m in solids if m.part_id == CRADLE_ID)
            floor = layout['psu']['floor_y_mm']
            rear = layout['psu']['rear_z_mm']
            for x in (-67.5, 67.5):
                contact = ((x-1., floor, rear+28.), (x+1., floor, rear+28.),
                           (x, floor, rear+44.))
                area = math.hypot(*material._cross(material._sub(contact[1], contact[0]),
                    material._sub(contact[2], contact[0])))/2
                self.assertAlmostEqual(area, 16.)
                for point in contact:
                    px, _, pz = point
                    self.assertTrue(_inside((px, floor-1.e-5, pz), cradle))
                    self.assertTrue(_horizontal_face_covers(cradle, point, 1.))
                    self.assertTrue(_horizontal_face_covers(shell, point, -1.))
                    self.assertTrue(_inside((px, floor+.4, pz), shell))
                    self.assertFalse(_inside((px, floor+1.e-5, pz), cradle))
                    self.assertFalse(_inside((px, floor-1.e-5, pz), shell))
            for psu in psus:
                shape = _geometry(psu)
                for other, obstacle in obstacles:
                    self.assertIsNone(_positive_overlap(shape, obstacle), (level, psu.name, other.name))
                for fan, fan_shape in fan_shapes:
                    self.assertIsNone(_positive_overlap(shape, fan_shape), (level, psu.name, fan.name))
            if level == 'eco':
                # The former generic pose is a real negative control; retain
                # all source PSU details and all source fan-frame apertures.
                old_psus, _ = add_auxiliary(spec, original, level)
                old_shapes = tuple((p, _geometry(p)) for p in old_psus)
                hit = next(((p.name, f.name) for p, p_shape in old_shapes for f, f_shape in fan_shapes
                    if _positive_overlap(p_shape, f_shape)), None)
                self.assertIsNotNone(hit, 'Old floor12 must still demonstrate the retained regression')
                from assembly_case_exteriors040 import replace_shell
                from dataclasses import replace
                rail = next(m for m in replace_shell((), DIMENSIONS, case)
                            if m.name == 'case-mod5-reference-tray-rails')
                old_rail = replace(rail, position=(0., 0., 0.))
                shell = next(m for m in psus if m.name == 'psu-shell')
                point = (74.4, -171.45, -160.)
                self.assertTrue(_inside(point, old_rail))
                self.assertTrue(_inside(point, shell))
                self.assertIsNotNone(_positive_overlap(_geometry(shell), _geometry(old_rail)))
                self.assertIsNone(_positive_overlap(_geometry(shell), _geometry(rail)))

    def test_fresh_public_whole_host_and_six_palettes_keep_actual_bottom_and_psu(self):
        import os
        import tempfile
        from contextlib import ExitStack
        from pathlib import Path
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        os.environ.setdefault('QT_QUICK_BACKEND', 'software')
        from PySide6.QtCore import QCoreApplication, QEvent
        from PySide6.QtGui import QGuiApplication, QOpenGLContext
        from PySide6.QtQml import QQmlEngine
        import hardware_packs
        from hardware_packs import PackStore
        from assembly_parts import reference_preset
        from assembly_profiles import bake_profiles
        from assembly_spec import build_spec
        from assembly_scene_cache import SceneCache
        from stats_config import DEFAULT
        from test_case_layout_hosts052 import _geometry, _positive_overlap
        app = QGuiApplication.instance() or QGuiApplication([])
        if app.platformName() != 'offscreen':
            self.skipTest('Only offscreen software construction')
        cache = SceneCache()
        with ExitStack() as stack:
            temporary = Path(stack.enter_context(tempfile.TemporaryDirectory()))
            stack.enter_context(patch.object(hardware_packs, '_store', PackStore(temporary/'packs')))
            for name in ('ctypes.WinDLL', 'socket.socket', 'subprocess.Popen', 'threading.Thread.start'):
                stack.enter_context(patch(name, create=True,
                    side_effect=AssertionError('No network/hardware/worker in reference host')))
            engine = QQmlEngine()
            warnings = []
            engine.warnings.connect(lambda rows: warnings.extend(row.toString() for row in rows))
            try:
                config = copy.deepcopy(DEFAULT)
                config['assembly'] = reference_preset({}, 'air')
                config['assembly'].update(case_model=CASE_ID, cpu_model='intel-13700kf',
                    gpu_model='asus-astral-5090', board_model='asus-rog-strix-z790-a-wifi-d4',
                    memory_models=['gskill-f4-3200c16d-16gtzr']*2,
                    psu_model='corsair-rm1000x-2024', cooler_model='noctua-nh-u12a',
                    cables_enabled=False, detail_level='balanced', appearance_style='miniature',
                    part_styles={}, case_fans=[dict(model='arctic-p12-pwm', mount='bottom',
                        count=3, direction='intake')])
                before = copy.deepcopy(config)
                spec = bake_profiles(build_spec({}, config, {}, []), engine)
                scene = cache.build(spec)
                self.assertEqual(config, before)
                self.assertEqual(scene.metadata['case_id'], CASE_ID)
                self.assertEqual(scene.metadata['case_pose_reference']['source_psu_option'], '02_reference')
                self.assertEqual(scene.metadata['memory_rendered_count'], 2)
                self.assertEqual(scene.metadata['auxiliary']['device_counts']['psu'], 1)
                self.assertEqual(scene.metadata['cooling']['rejected'], [])
                self.assertEqual(scene.metadata['auxiliary']['rejected'], [])
                self.assertEqual(len([p for p in scene.metadata['cooling']['parts']
                    if p['kind'] == 'case_fan' and p['mount'] == 'bottom']), 3)
                ids = {SUPPORT_ID, BRACKET_ID, CRADLE_ID}
                self.assertEqual({p['id'] for p in scene.metadata['hardware']['parts']
                    if p['id'] in ids}, ids)
                self.assertEqual(sum(m.part_id == 'cpu:0' for m in scene.meshes) > 0, True)
                self.assertEqual(sum(m.name == 'ram-pcb' for m in scene.meshes), 2)
                self.assertTrue(any(m.part_id == 'gpu:0' for m in scene.meshes))
                self.assertTrue(all(row['state'] == 'within_limit' for row in spec['checks']), spec['checks'])
                self.assertEqual(scene.metadata['auxiliary']['cable_count'], 0)
                # The full host retains every source body. Only genuinely
                # separate new material, not its pierced aggregate AABB, can
                # clear a fan/PSU or other installed reference component.
                obstacles = [(m, _geometry(m)) for m in scene.meshes if m.component in ('case', 'panel')]
                for mesh in scene.meshes:
                    if mesh.component not in ('cpu', 'gpu', 'memory', 'psu', 'fans', 'cooler', 'board'):
                        continue
                    shape = _geometry(mesh)
                    for other, obstacle in obstacles:
                        self.assertIsNone(_positive_overlap(shape, obstacle), (mesh.name, other.name))
                baseline = tuple(m for m in scene.meshes if not m.name.startswith('style-'))
                for style in STYLES:
                    styled = cache.build(dict(spec, visual_style=style, part_styles={}))
                    physical = tuple(m for m in styled.meshes if not m.name.startswith('style-'))
                    self.assertEqual(len(physical), len(baseline))
                    for current, original in zip(physical, baseline):
                        self.assertIs(current.vertices, original.vertices)
                        self.assertEqual((current.position, current.part_id, current.axis, current.rotor),
                            (original.position, original.part_id, original.axis, original.rotor))
            finally:
                cache.clear()
                engine.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.assertEqual(warnings, [])
        self.assertFalse(app.topLevelWindows())
        self.assertIsNone(QOpenGLContext.currentContext())


if __name__ == '__main__':
    unittest.main()
