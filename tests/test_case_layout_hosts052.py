"""Fresh public host construction; AIR/reference layout, not native or AIO QA.

No stored scene, private placement patch, hardware inventory or renderer is
used.  AABB separation is only a broad phase: intersecting bounds go through
actual triangle crossings and independent three-direction material witnesses.
This detects the retained host regressions, not factory tolerances or a
complete arbitrary-solid collision certificate below the sampling scale.
"""
import copy
from contextlib import ExitStack
from dataclasses import replace
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QGuiApplication, QOpenGLContext
from PySide6.QtQml import QQmlEngine

from assembly_geometry import Mesh, box, build_scene, ring
from assembly_parts import reference_preset
from assembly_profiles import bake_profiles
from assembly_spec import build_spec
from assembly_visibility048 import mesh_visible
import hardware_packs
from hardware_packs import PackStore
from stats_config import DEFAULT


HAF = 'cooler-master-haf-700-evo'
H7 = 'nzxt-h7-flow-2024'
H5 = 'nzxt-h5-flow-2024'
IDENTITIES = dict(cpu_model='intel-13700kf', gpu_model='asus-astral-5090',
    board_model='asus-rog-strix-z790-a-wifi-d4',
    memory_models=['gskill-f4-3200c16d-16gtzr'] * 2,
    psu_model='corsair-rm1000x-2024')
FANS = {
    HAF: [('front', 'arctic-p14-pwm', 3)],
    H7: [('front', 'arctic-p12-pwm', 3), ('bottom', 'arctic-p12-pwm', 3)],
    H5: [('bottom', 'arctic-p12-pwm', 2)],
}
VERTICAL_PSU = ((0., 1., 0.), (-1., 0., 0.), (0., 0., 1.))
RAYS = ((1., .173, .317), (.317, 1., .173), (.173, .317, 1.))
EPS = 1.e-8


def _sub(a, b):
    return tuple(a[k] - b[k] for k in range(3))


def _dot(a, b):
    return sum(a[k] * b[k] for k in range(3))


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _bounds(points):
    return tuple(tuple(f(p[k] for p in points) for k in range(3)) for f in (min, max))


def _overlap(a, b, *, strict=False):
    if strict:
        return all(min(a[1][k], b[1][k]) - max(a[0][k], b[0][k]) > EPS for k in range(3))
    return all(a[1][k] >= b[0][k]-EPS and b[1][k] >= a[0][k]-EPS for k in range(3))


def _geometry(mesh):
    triangles = tuple(tuple(tuple(mesh.vertices[at+j+k] + mesh.position[k] for k in range(3))
        for j in (0, 6, 12)) for at in range(0, len(mesh.vertices), 18))
    return (triangles, tuple(_bounds(t) for t in triangles),
            _bounds(tuple(p for t in triangles for p in t)))


def _ray_inside(point, triangles, direction):
    """Parity of real faces, deduplicating triangle diagonals on one surface."""
    hits = []
    for a, b, c in triangles:
        e1, e2 = _sub(b, a), _sub(c, a)
        h = _cross(direction, e2)
        determinant = _dot(e1, h)
        if abs(determinant) < 1.e-10:
            continue
        inv = 1. / determinant
        s = _sub(point, a)
        u = inv * _dot(s, h)
        q = _cross(s, e1)
        v = inv * _dot(direction, q)
        if u < -1.e-10 or v < -1.e-10 or u+v > 1.+1.e-10:
            continue
        distance = inv * _dot(e2, q)
        if distance > EPS:
            hits.append(distance)
    unique = []
    for value in sorted(hits):
        if not unique or abs(value-unique[-1]) > 1.e-7:
            unique.append(value)
    return len(unique) % 2 == 1


def _inside(point, geometry):
    triangles, _, bounds = geometry
    if not all(bounds[0][k]+EPS < point[k] < bounds[1][k]-EPS for k in range(3)):
        return False
    return all(_ray_inside(point, triangles, direction) for direction in RAYS)


def _surface_crossing(a, b):
    """Strict transverse face crossing; a shared mounting boundary is allowed."""
    ea = tuple(_sub(a[(k+1) % 3], a[k]) for k in range(3))
    eb = tuple(_sub(b[(k+1) % 3], b[k]) for k in range(3))
    na, nb = _cross(ea[0], ea[1]), _cross(eb[0], eb[1])
    # Both triangles must pass through the other's plane. Coplanar/tangent
    # contacts are instead checked for a common *interior* material witness.
    da = [_dot(_sub(p, b[0]), nb) for p in a]
    db = [_dot(_sub(p, a[0]), na) for p in b]
    ta, tb = EPS*math.hypot(*nb), EPS*math.hypot(*na)
    if not (min(da) < -ta and max(da) > ta and min(db) < -tb and max(db) > tb):
        return False
    line = _cross(na, nb)
    length = math.hypot(*line)
    def cut(triangle, distances, tolerance):
        points = [p for p, value in zip(triangle, distances) if abs(value) <= tolerance]
        for index in range(3):
            following = (index+1) % 3
            first, last = distances[index], distances[following]
            if first*last < 0.:
                t = first/(first-last)
                points.append(tuple(triangle[index][k]+t*(triangle[following][k]-triangle[index][k])
                                    for k in range(3)))
        return points
    pa = [_dot(p, line) for p in cut(a, da, ta)]
    pb = [_dot(p, line) for p in cut(b, db, tb)]
    if not pa or not pb:
        return False
    if min(max(pa), max(pb))-max(min(pa), min(pb)) <= EPS*length:
        return False
    axes = (na, nb, *(_cross(x, y) for x in ea for y in eb))
    for axis in axes:
        length = math.hypot(*axis)
        if length < 1.e-10:
            continue
        pa, pb = [_dot(p, axis) for p in a], [_dot(p, axis) for p in b]
        if min(max(pa), max(pb)) < max(min(pa), min(pb))-EPS*length:
            return False
    return True


def _positive_overlap(first, second):
    """Return an actual crossing/interior witness, never an AABB-only verdict."""
    at, ab, aa = first
    bt, bb, ba = second
    if not _overlap(aa, ba, strict=True):
        return None
    for triangle, bounds in zip(at, ab):
        if not _overlap(bounds, ba):
            continue
        for other, other_bounds in zip(bt, bb):
            if _overlap(bounds, other_bounds) and _surface_crossing(triangle, other):
                return ('transverse_actual_faces', triangle, other)
    # Catch containment and coincident parallel skins as well as crossings.
    # The small offset locates a witness; it never shrinks or moves a surface.
    for geometry, other in ((first, second), (second, first)):
        for triangle, bounds in zip(geometry[0], geometry[1]):
            if not _overlap(bounds, other[2]):
                continue
            normal = _cross(_sub(triangle[1], triangle[0]), _sub(triangle[2], triangle[0]))
            length = math.hypot(*normal)
            if length < 1.e-10:
                continue
            center = tuple(sum(p[k] for p in triangle)/3. for k in range(3))
            for sign in (-1., 1.):
                point = tuple(center[k] + sign*1.e-5*normal[k]/length for k in range(3))
                if _inside(point, other) and _inside(point, geometry):
                    return ('three_ray_common_material', point)
    return None


class HostNarrowPhase052Tests(unittest.TestCase):
    def test_real_void_and_boundary_contact_do_not_mask_positive_material_overlap(self):
        cube = Mesh('test-solid', box(2., 2., 2.), (1., 1., 1., 1.))
        touching = replace(cube, position=(2., 0., 0.))
        penetrating = replace(cube, position=(1.99, 0., 0.))
        self.assertIsNone(_positive_overlap(_geometry(cube), _geometry(touching)))
        self.assertIsNotNone(_positive_overlap(_geometry(cube), _geometry(penetrating)))
        hollow = Mesh('test-real-hole', ring(10., 8., 4., 24), cube.color)
        self.assertTrue(_overlap(_geometry(cube)[2], _geometry(hollow)[2], strict=True))
        self.assertIsNone(_positive_overlap(_geometry(cube), _geometry(hollow)))
        # Full-triangle projections overlap, but the actual plane sections
        # share only (1,0,0). This must never be called material penetration.
        a = ((-2., -1., 0.), (2., -1., 0.), (0., 1., 0.))
        b = ((-1., 0., 1.), (3., 0., 1.), (3., 0., -1.))
        self.assertFalse(_surface_crossing(a, b))
        self.assertTrue(_surface_crossing(a, tuple((x-.01, y, z) for x, y, z in b)))


class ActualCaseLayoutHosts052Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        if cls.app.platformName() != 'offscreen':
            raise unittest.SkipTest('Only software/offscreen reference construction')
        cls.stack = ExitStack()
        cls.addClassCleanup(cls.stack.close)
        folder = Path(cls.stack.enter_context(tempfile.TemporaryDirectory()))
        cls.stack.enter_context(patch.object(hardware_packs, '_store', PackStore(folder/'packs')))
        for target in ('ctypes.WinDLL', 'socket.socket', 'threading.Thread.start', 'subprocess.Popen'):
            cls.stack.enter_context(patch(target, create=True,
                side_effect=AssertionError('No hardware, network, process or worker in host fixture')))
        cls.engine = QQmlEngine()
        cls.warnings = []
        cls.engine.warnings.connect(lambda rows: cls.warnings.extend(row.toString() for row in rows))
        cls.rows = {}
        cls.geometry = {}
        for case_id in (HAF, H7, H5):
            config = copy.deepcopy(DEFAULT)
            # Begin with a genuinely different case, then regenerate all
            # checks from the requested manual selections, not a stale spec.
            config['assembly'] = reference_preset({}, 'air')
            config['assembly'].update(IDENTITIES, case_model=case_id,
                appearance_style='miniature', part_styles={}, detail_level='balanced',
                cooler_model='noctua-nh-u12a', gpu_waterblock=False, cables_enabled=False,
                case_fans=[dict(model=model, mount=mount, count=count, direction='intake')
                           for mount, model, count in FANS[case_id]])
            before = copy.deepcopy(config)
            spec = bake_profiles(build_spec({}, config, {}, []), cls.engine)
            scene = build_scene(spec)
            if config != before:
                raise AssertionError('Public construction mutated the fresh configuration')
            cls.rows[case_id] = (config, spec, scene)

    @classmethod
    def tearDownClass(cls):
        cls.rows.clear()
        cls.geometry.clear()
        cls.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        if cls.warnings:
            raise AssertionError(cls.warnings)
        if cls.app.topLevelWindows() or QOpenGLContext.currentContext() is not None:
            raise AssertionError('No native window or GL context allowed')

    def shape(self, mesh):
        key = id(mesh)
        if key not in self.geometry:
            self.geometry[key] = _geometry(mesh)
        return self.geometry[key]

    def assert_material_separate(self, first, second, context):
        self.assertIsNone(_positive_overlap(self.shape(first), self.shape(second)),
            (context, first.part_id, first.name, second.part_id, second.name))

    def structures(self, scene):
        ids = {row['id'] for row in scene.metadata['case_shroud']['parts']}
        return [m for m in scene.meshes if m.part_id in ids or m.name == 'case-bottom']

    def test_fresh_public_chain_keeps_all_reference_identities_and_current_case_checks(self):
        for case_id, (config, spec, scene) in self.rows.items():
            with self.subTest(case=case_id):
                self.assertEqual(spec['case']['id'], case_id)
                self.assertEqual(scene.metadata['case_id'], case_id)
                self.assertEqual(spec['options']['case_model'], case_id)
                self.assertNotEqual(case_id, 'corsair-5000d-airflow')
                self.assertEqual(spec['cpu']['appearance']['id'], IDENTITIES['cpu_model'])
                self.assertEqual(spec['gpu']['appearance']['id'], IDENTITIES['gpu_model'])
                self.assertEqual(spec['board']['model_id'], IDENTITIES['board_model'])
                self.assertEqual([m['appearance']['id'] for m in spec['memory']['modules']],
                                 IDENTITIES['memory_models'])
                self.assertTrue(spec['gpu']['shell_polygon'])
                self.assertTrue(all(m['case_polygon'] for m in spec['memory']['modules']))
                for family in ('cpu', 'gpu', 'memory'):
                    self.assertFalse(spec[family]['telemetry_bound'])
                checks = {row['kind']: row for row in spec['checks']}
                self.assertEqual(checks['gpu_length']['limit_mm'], spec['case']['max_gpu_length_mm'])
                self.assertTrue(all(row['state'] == 'within_limit' for row in spec['checks']), spec['checks'])
                core = scene.metadata['hardware']['parts']
                for family, count in (('cpu', 1), ('gpu', 1), ('memory', 2)):
                    self.assertEqual(sum(p['kind'] == family for p in core), count)
                self.assertEqual(scene.metadata['memory_rendered_count'], 2)
                self.assertEqual(sum(m.name == 'ram-pcb' for m in scene.meshes), 2)
                self.assertEqual(scene.metadata['auxiliary']['device_counts']['psu'], 1)
                self.assertEqual(scene.metadata['cooling']['rejected'], [])
                self.assertEqual(scene.metadata['auxiliary']['rejected'], [])
                self.assertEqual(scene.metadata['auxiliary']['cable_count'], 0)
                self.assertFalse(config['assembly']['cables_enabled'])

    def test_actual_psu_world_basis_bounds_and_board_group_follow_exact_host_anchors(self):
        for case_id, (_, spec, scene) in self.rows.items():
            with self.subTest(case=case_id):
                w, h, d = scene.dimensions
                anchors = scene.metadata['attachment_anchors']
                pose = scene.metadata['case_pose_reference']
                psu = anchors['psu']
                basis = VERTICAL_PSU if case_id in (HAF, H7) else ((-1., 0., 0.), (0., -1., 0.), (0., 0., 1.))
                size = (86., 150., 160.) if case_id in (HAF, H7) else (150., 86., 160.)
                self.assertEqual(psu['basis'], basis)
                self.assertEqual(psu['world_dimensions_mm'], size)
                self.assertEqual(psu['model_id'], IDENTITIES['psu_model'])
                self.assertFalse(psu['placement_verified'])
                self.assertTrue(psu['reference_only'])
                self.assertFalse(pose['positions_verified'])
                self.assertFalse(pose['dimensions_verified'])
                self.assertTrue(all(url.startswith('https://') for url in pose['source_urls']))
                floor = -h/2 + (46. if case_id == HAF else 12. if case_id == H7 else 20.)
                rear = -d/2 + 10.
                center = psu['position']
                self.assertAlmostEqual(center[1]-size[1]/2, floor)
                self.assertAlmostEqual(center[2]-size[2]/2, rear)
                if case_id == HAF:
                    self.assertEqual(anchors['board']['x'], 35.5)
                    self.assertAlmostEqual(center[0]-size[0]/2, pose['tray_x_mm']+5.)
                elif case_id == H7:
                    self.assertAlmostEqual(center[0]+size[0]/2, w/2-9.)
                else:
                    self.assertEqual(center[0], 0.)
                board = anchors['board']
                if case_id in (H5, H7):
                    self.assertAlmostEqual(board['y'], h*.10)
                pcb = next(m for m in scene.meshes if m.name == 'motherboard-reference')
                self.assertEqual(pcb.position, board['position'])
                self.assertAlmostEqual(anchors['cpu']['position'][1],
                    board['y']+(.5-spec['board']['model_profile']['cpu_uv'][1])*board['height'])
                self.assertEqual(sorted(m.position[1:] for m in scene.meshes if m.name == 'ram-pcb'),
                    sorted(tuple(anchors['dimm_centers'][i][1:]) for i in (1, 3)))
                shell = next(m for m in scene.meshes if m.name == 'psu-shell')
                bounds = self.shape(shell)[2]
                for k in range(3):
                    self.assertAlmostEqual(bounds[1][k]-bounds[0][k], size[k])
                    self.assertAlmostEqual((bounds[1][k]+bounds[0][k])/2, center[k])
                for hardware in [m for m in scene.meshes if m.component in ('psu', 'cpu', 'gpu', 'memory')
                                 or m.name == 'motherboard-reference']:
                    for material in self.structures(scene):
                        self.assert_material_separate(hardware, material, case_id)

    def test_selected_case_fans_keep_real_frames_rotors_and_connectors_clear_of_new_material(self):
        for case_id, (_, _, scene) in self.rows.items():
            with self.subTest(case=case_id):
                cooling = scene.metadata['cooling']
                parts = [p for p in cooling['parts'] if p['kind'] == 'case_fan']
                self.assertEqual(len(parts), sum(n for _, _, n in FANS[case_id]))
                for mount, model, count in FANS[case_id]:
                    expected = {'fans:'+mount+':'+str(i) for i in range(count)}
                    self.assertEqual({p['id'] for p in parts if p['mount'] == mount}, expected)
                    for identity in expected:
                        selected = [m for m in scene.meshes if m.part_id == identity]
                        self.assertEqual(sum(m.name == 'case-fan-frame' for m in selected), 1)
                        self.assertEqual(sum(m.rotor for m in selected), 1)
                        self.assertEqual(sum(m.name == 'case-fan-power-connector' for m in selected), 1)
                        self.assertEqual(next(f['model_id'] for f in cooling['fans'] if f['part_id'] == identity), model)
                        # Flexible reference leads stay in the scene too. Their
                        # entire surfaces, not only rigid frame AABBs, are tested.
                        for fan_mesh in selected:
                            for material in self.structures(scene):
                                self.assert_material_separate(fan_mesh, material, (case_id, identity))
                for fan in (f for f in cooling['fans'] if f['role'] == 'case'):
                    self.assertIsNone(fan['rpm'])
                    self.assertEqual(fan['rotation_default'], 'static')

    def test_only_open_floor_hosts_replace_bottom_and_show_psu_keeps_load_bearing_parts(self):
        for case_id, (_, _, scene) in self.rows.items():
            with self.subTest(case=case_id):
                meta = scene.metadata['case_shroud']
                replaced = case_id in (HAF, H7)
                self.assertEqual(meta['replaces_case_bottom'], replaced)
                self.assertEqual(sum(m.name == 'case-bottom' for m in scene.meshes), 0 if replaced else 1)
                self.assertTrue(any(m.name == 'case-depth-rail' for m in scene.meshes))
                self.assertTrue(any('foot' in m.name for m in scene.meshes))
                supports = {p['id'] for p in meta['parts'] if p['kind'] == 'case_structure'}
                if replaced:
                    self.assertTrue(supports)
                for mesh in (m for m in scene.meshes if m.part_id in supports or m.name == 'case-bottom'):
                    for cutaway in (False, True):
                        self.assertTrue(mesh_visible(mesh, cutaway, show_psu=True), (case_id, mesh.name))
                        self.assertTrue(mesh_visible(mesh, cutaway, show_psu=False), (case_id, mesh.name))
                if case_id == H5:
                    roof = meta['roof_world_y_mm']
                    bottom = [m for m in scene.meshes if m.part_id.startswith('fans:bottom:') and m.name == 'case-fan-frame']
                    self.assertEqual(len(bottom), 2)
                    self.assertGreater(min(self.shape(m)[2][0][1] for m in bottom), roof)
                    self.assertEqual(scene.metadata['case_pose_reference']['psu_fan_world_normal_reference'], (0., 1., 0.))

    def test_h7_current_reference_tail_halfturn_clears_partition_and_old_tail_really_penetrated(self):
        scene = self.rows[H7][2]
        plane = scene.metadata['attachment_anchors']['case_mount_planes']['bottom']
        self.assertEqual(plane['normal'], (0., -1., 0.))
        self.assertEqual(plane['up'], (0., 0., -1.))
        self.assertFalse(plane['positions_verified'])
        self.assertTrue(plane['halfturn_for_main_chamber_lead'])
        partition = [m for m in self.structures(scene) if m.part_id == 'case:psu-cover']
        self.assertTrue(partition)
        fan_rows = {f['part_id']: f for f in scene.metadata['cooling']['fans'] if f['role'] == 'case'}
        anchors = scene.metadata['cooling']['wire_anchors']
        for index in range(3):
            identity = 'fans:bottom:'+str(index)
            connector = next(m for m in scene.meshes if m.part_id == identity and m.name == 'case-fan-power-connector')
            source = next(a for a in anchors if a['owner'] == identity and a['kind'] == 'fan4')
            self.assertFalse(source['position_verified'])
            self.assertTrue(source['connector_rendered'])
            for material in partition:
                self.assert_material_separate(connector, material, identity)
            center = fan_rows[identity]['position']
            # A source-recorded old up+Z pose differs by a rigid 180deg turn
            # around the unchanged mount normal. Recreate ONLY that old rigid
            # connector for a negative control, never relocate the real scene.
            vertices = []
            for at in range(0, len(connector.vertices), 6):
                p = tuple(connector.vertices[at+k]+connector.position[k] for k in range(3))
                n = connector.vertices[at+3:at+6]
                vertices.extend((2*center[0]-p[0], p[1], 2*center[2]-p[2], -n[0], n[1], -n[2]))
            old = replace(connector, vertices=tuple(vertices), position=(0., 0., 0.))
            old_geometry = _geometry(old)
            witness = None
            for material in partition:
                witness = _positive_overlap(old_geometry, self.shape(material))
                if witness is not None:
                    break
            self.assertIsNotNone(witness, ('legacy H7 bottom connector must remain a real regression', identity))


if __name__ == '__main__':
    unittest.main()
