"""Seventeen fresh public AIR hosts, one physical host resident at a time.

These are fixed source-reference layouts, not manufacturer CAD or native
acceptance. Bounds only reject disjoint pairs. Possible intersections use
actual facets and three-direction common-material witnesses, including every
PSU child mesh and every selected fan's connector/lead. No stored scene or
private pose patch is substituted for build_spec/profile/SceneCache.
"""
import copy
from contextlib import ExitStack
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QGuiApplication, QOpenGLContext
from PySide6.QtQml import QQmlEngine

from assembly_feedback import cpu_fan_state
from assembly_geometry import Mesh, box, color, extrude, rotate_vertices
from assembly_inspection import snapshot as inspection_snapshot
from assembly_parts import reference_preset
from assembly_profiles import bake_profiles
from assembly_scene_cache import SceneCache
from assembly_spec import build_spec
from assembly_viewer import AssemblyViewport, mesh_phase
from assembly_visibility048 import mesh_visible
from chassis_catalog import get_case
from cooling_catalog import get_cooler
from motherboard_catalog import get_model
import hardware_packs
from hardware_packs import PackStore
from stats_config import DEFAULT
from test_case_layout_hosts052 import _geometry, _inside, _overlap, _positive_overlap

SIX = ('miniature', 'cartoon', 'notebook_color', 'notebook_line', 'sticker', 'papercut')
ATX = 'asus-rog-strix-z790-a-wifi-d4'
MATX = 'asus-prime-b760m-a-wifi-d4'
LOW = 'noctua-nh-l9i-17xx'
TOWER = 'noctua-nh-u12a'
ASTRAL = 'asus-astral-5090'
DUAL = 'asus-dual-4060'
# Exact requested bank, not a capacity inferred from a generic mount plane.
# GT502 exercises its documented top bank in this one-host matrix; its exact
# bottom3x120 source capacity is independently covered by the fan matrix.
# Empty catalog fan lists for Vision/TK2/2500X/Compact do not imply no fans:
# their explicit source-reviewed reference architecture supplies the plane.
JOBS = (
    ('lian-li-o11d-evo-rgb', ATX, TOWER, ASTRAL, 'bottom', 140, 3),
    ('nzxt-h6-flow-2023', ATX, TOWER, ASTRAL, 'bottom', 140, 2),
    ('corsair-6500x', ATX, TOWER, ASTRAL, 'bottom', 140, 3),
    ('hyte-y60', ATX, TOWER, DUAL, 'bottom', 140, 2),
    ('asus-tuf-gt502', ATX, TOWER, ASTRAL, 'top', 120, 3),
    ('phanteks-nv7', ATX, TOWER, ASTRAL, 'bottom', 140, 3),
    ('antec-c8-argb', ATX, TOWER, ASTRAL, 'bottom', 140, 3),
    ('montech-king-95', ATX, TOWER, ASTRAL, 'bottom', 140, 2),
    ('msi-mag-pano-100r-pz', ATX, TOWER, ASTRAL, 'bottom', 140, 2),
    ('lian-li-o11-vision', ATX, TOWER, ASTRAL, 'bottom', 120, 3),
    ('nzxt-h9-flow-2023', ATX, TOWER, ASTRAL, 'bottom', 140, 2),
    # Keep TK2's conflicting 155/165 source limits; do not adjudicate them by
    # silently installing a 158mm tower. This real cooler is 37mm high.
    ('jonsbo-tk2-black', ATX, LOW, ASTRAL, 'bottom', 120, 3),
    ('deepcool-ch780', ATX, LOW, ASTRAL, 'bottom', 140, 3),
    ('corsair-2500x', MATX, TOWER, ASTRAL, 'bottom', 120, 3),
    ('lian-li-o11-vision-compact', ATX, TOWER, ASTRAL, 'bottom', 120, 3),
    ('be-quiet-light-base-600-lx', ATX, TOWER, ASTRAL, 'bottom', 140, 2),
    ('havn-hs-420', ATX, TOWER, ASTRAL, 'bottom', 140, 3),
)
FORM = {'atx': 'atx', 'matx': 'micro_atx', 'itx': 'mini_itx', 'eatx': 'e_atx'}
HARDWARE = frozenset(('psu', 'cpu', 'gpu', 'memory', 'board', 'cooler', 'fans'))


class RearCaseHosts052Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        if cls.app.platformName() != 'offscreen':
            raise unittest.SkipTest('Only offscreen construction; no native acceptance')
        cls.stack = ExitStack()
        cls.addClassCleanup(cls.stack.close)
        cls.cache = SceneCache()
        cls.scene = None
        cls.shapes = {}
        cls.bounds = {}
        cls.addClassCleanup(cls.release_host)
        folder = Path(cls.stack.enter_context(tempfile.TemporaryDirectory()))
        cls.stack.enter_context(patch.object(hardware_packs, '_store', PackStore(folder/'packs')))
        for target in ('ctypes.WinDLL', 'socket.socket', 'threading.Thread.start', 'subprocess.Popen'):
            cls.stack.enter_context(patch(target, create=True,
                side_effect=AssertionError('No hardware/network/native process/worker in host QA')))
        cls.engine = QQmlEngine()
        cls.warnings = []
        cls.engine.warnings.connect(lambda rows: cls.warnings.extend(row.toString() for row in rows))
        cls.addClassCleanup(cls.release_engine)
        case, board, cooler, gpu, mount, size, count = cls.job
        cls.config = copy.deepcopy(DEFAULT)
        cls.config['assembly'] = reference_preset({}, 'air')
        cls.config['assembly'].update(case_model=case, cpu_model='intel-13700kf', gpu_model=gpu,
            board_model=board, memory_models=['gskill-f4-3200c16d-16gtzr']*2,
            psu_model='corsair-rm1000x-2024', cooler_model=cooler, cables_enabled=False,
            detail_level='balanced', appearance_style='miniature', part_styles={},
            fan_animation=True, fan_motion='measured',
            case_fans=[dict(model='arctic-p'+('12' if size == 120 else '14')+'-pwm',
                mount=mount, count=count, direction='intake' if mount == 'bottom' else 'exhaust')])
        before = copy.deepcopy(cls.config)
        cls.spec = bake_profiles(build_spec({}, cls.config, {}, []), cls.engine)
        # Exactly one public construction; the same cache is used by style QA.
        cls.scene = cls.cache.build(cls.spec)
        if cls.config != before:
            raise AssertionError('Public host construction mutated its input configuration')

    @classmethod
    def release_host(cls):
        cls.shapes.clear()
        cls.bounds.clear()
        cls.scene = None
        cls.spec = None
        cls.cache.clear()

    @classmethod
    def release_engine(cls):
        cls.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        if cls.warnings:
            raise AssertionError(cls.warnings)
        if cls.app.topLevelWindows() or QOpenGLContext.currentContext() is not None:
            raise AssertionError('Host QA must create no window or native GL context')

    def shape(self, mesh):
        if id(mesh) not in self.shapes:
            self.shapes[id(mesh)] = _geometry(mesh)
        return self.shapes[id(mesh)]

    def bound(self, mesh):
        if id(mesh) not in self.bounds:
            self.bounds[id(mesh)] = tuple(tuple(f(mesh.vertices[k::6])+mesh.position[k]
                for k in range(3)) for f in (min, max))
        return self.bounds[id(mesh)]

    def assert_material_clear(self, first, second):
        # No geometry copies/ray queries for strictly disjoint mesh bounds.
        if not _overlap(self.bound(first), self.bound(second), strict=True):
            return
        witness = _positive_overlap(self.shape(first), self.shape(second))
        self.assertIsNone(witness, dict(case=self.job[0],
            first=(first.name, first.component, first.part_id),
            second=(second.name, second.component, second.part_id), witness=witness))

    def materials(self):
        # Source parts are identified by their declared independent identity,
        # including the NV7 thin skin that deliberately keeps the old name.
        # Retained legacy floor/feet are tested too; source identity is not an
        # excuse to omit any remaining ordinary material from collision QA.
        ids = {row['id'] for row in self.scene.metadata['case_shroud']['parts']}
        return tuple(mesh for mesh in self.scene.meshes if mesh.component == 'case' and
            (mesh.part_id in ids or mesh.name in ('case-back', 'rear-chamber-divider',
                'case-bottom', 'case-foot', 'case-cold-floor-deck')))

    def assert_same_physical(self, actual, expected):
        self.assertEqual((actual.name, actual.component, actual.part_id, actual.position,
            actual.axis, actual.rotor, actual.direction),
            (expected.name, expected.component, expected.part_id, expected.position,
             expected.axis, expected.rotor, expected.direction))
        self.assertTrue(actual.vertices == expected.vertices,
            (self.job[0], actual.name, actual.part_id, 'F64 POSITION/NORMAL arrays differ'))

    def test_real_compatible_selected_identities_and_entire_requested_fan_bank_survive(self):
        case, board, cooler, gpu, mount, size, count = self.job
        meta = self.scene.metadata
        parts = meta['hardware']['parts']
        source = get_case(case)
        profile = get_model(board)
        self.assertIn(FORM[profile['form_factor']], source['form_factors'])
        self.assertEqual(profile['socket'], 'LGA1700')
        self.assertEqual(profile['memory_type'], 'DDR4')
        self.assertEqual(meta['case_id'], case)
        self.assertEqual(self.spec['board']['model_profile']['id'], board)
        self.assertEqual(self.spec['gpu']['appearance']['id'], gpu)
        for family in ('cpu', 'gpu', 'board'):
            self.assertEqual([row['id'] for row in parts if row['kind'] == family], [family+':0'])
        self.assertEqual(sum(mesh.name == 'ram-pcb' for mesh in self.scene.meshes), 2)
        self.assertEqual({mesh.part_id for mesh in self.scene.meshes if mesh.component == 'memory'},
                         {'memory:0', 'memory:1'})
        self.assertEqual([row['total_height_mm'] for row in self.spec['memory']['modules']], [44., 44.])
        self.assertEqual(meta['auxiliary']['device_counts']['psu'], 1)
        self.assertEqual(sum(mesh.name == 'psu-shell' for mesh in self.scene.meshes), 1)
        psu = [mesh for mesh in self.scene.meshes if mesh.component == 'psu']
        self.assertGreater(len(psu), 10)
        self.assertEqual({mesh.part_id for mesh in psu}, {'psu:0'})
        self.assertTrue(any(mesh.name == 'psu-fan-panel' for mesh in psu))
        self.assertTrue(any(mesh.name == 'psu-modular-connector-panel' for mesh in psu))
        cooling = meta['cooling']
        self.assertEqual(cooling['rejected'], [])
        self.assertEqual(cooling['cooler']['id'], cooler)
        fan_ids = {'fans:'+mount+':'+str(i) for i in range(count)}
        self.assertEqual({row['id'] for row in cooling['parts'] if row['kind'] == 'case_fan'}, fan_ids)
        for identity in fan_ids:
            actual = [mesh for mesh in self.scene.meshes if mesh.part_id == identity]
            self.assertTrue(any(mesh.rotor for mesh in actual), identity)
            self.assertTrue(any(mesh.name == 'case-fan-power-connector' for mesh in actual), identity)
            self.assertTrue(any('frame' in mesh.name for mesh in actual), identity)
        if case == 'deepcool-ch780':
            self.assertEqual(get_cooler(cooler)['dimensions_mm']['height'], 37.)
        if case == 'hyte-y60':
            self.assertLessEqual(self.spec['gpu']['thickness_mm'], 60.)

    def test_source_material_parts_rear_psu_void_and_special_divider_edges_are_real(self):
        meta = self.scene.metadata
        shroud = meta['case_shroud']
        self.assertFalse(shroud.get('positions_verified', False))
        self.assertFalse(shroud.get('chamber_is_solid', False))
        from assembly_case_shrouds052 import build as build_source_material
        from assembly_rear_panel052 import build as build_source_rear_wall
        tone = color('#25313e')
        covers, factory_meta = build_source_material(self.spec['case'], self.scene.dimensions, tone)
        rear_wall, _ = build_source_rear_wall(self.spec['case'], self.scene.dimensions,
            meta['case_pose_reference'], tone)
        self.assertIsNotNone(rear_wall)
        expected_source = (*covers, rear_wall)
        ids = {row['id'] for row in shroud['parts']}
        self.assertTrue(ids)
        self.assertEqual(ids, {mesh.part_id for mesh in expected_source})
        physical_ids = {mesh.part_id for mesh in self.scene.meshes}
        hardware_ids = {row['id'] for row in meta['hardware']['parts']}
        self.assertTrue(ids <= physical_ids & hardware_ids)
        for identity in ids:
            actual = [mesh for mesh in self.scene.meshes if mesh.part_id == identity]
            expected = [mesh for mesh in expected_source if mesh.part_id == identity]
            self.assertEqual(len(actual), len(expected), identity)
            for mesh, source in zip(actual, expected):
                self.assert_same_physical(mesh, source)
        materials = {id(mesh) for mesh in self.materials()}
        self.assertTrue({id(mesh) for mesh in self.scene.meshes if mesh.part_id in ids} <= materials)
        # A reused display name cannot allow the old filled rear-chamber box.
        # Every same-name mesh must instead be the exact source thin part.
        for mesh in self.scene.meshes:
            if mesh.name == 'rear-chamber-shroud':
                self.assertIn(mesh.part_id, ids)
                source = [row for row in expected_source if row.part_id == mesh.part_id and row.name == mesh.name]
                self.assertEqual(len(source), 1)
                self.assert_same_physical(mesh, source[0])
                w, h, d = self.scene.dimensions
                self.assertNotEqual(mesh.vertices, box(w*.28, h*.23, d*.44))
        floors = [mesh for mesh in self.scene.meshes if mesh.name == 'case-bottom']
        if factory_meta.get('replaces_case_bottom') is True:
            self.assertFalse(floors)
        else:
            # Group B intentionally retains the original 3mm drawing floor;
            # it is not a newly sourced perforated intake or a filled PSU bay.
            self.assertIn(self.job[0], ('phanteks-nv7', 'antec-c8-argb', 'montech-king-95',
                'msi-mag-pano-100r-pz', 'lian-li-o11-vision'))
            self.assertEqual(len(floors), 1)
            w, h, d = self.scene.dimensions
            corner = any(key in self.spec['case'].get('features', ())
                for key in ('curved_front_glass', 'angular_glass_corner'))
            if corner:
                cut = min(w*.23, d*.18)
                footprint = ((-w/2, -d/2), (w/2, -d/2), (w/2, d/2),
                             (-w/2+cut, d/2), (-w/2, d/2-cut))
                vertices = rotate_vertices(extrude(footprint, 3.), 'down')
            else:
                vertices = box(w, 3., d)
            self.assert_same_physical(floors[0], Mesh('case-bottom', vertices, tone,
                (0., -h/2+17.5, 0.)))
            self.assertIn(id(floors[0]), materials)
        for row in shroud['parts']:
            self.assertFalse(row.get('dimensions_verified', False))
        backs = [mesh for mesh in self.scene.meshes if mesh.name == 'case-back']
        self.assertEqual(len(backs), 1)
        self.assertEqual(backs[0].part_id, 'case:rear-wall')
        aperture = shroud['rear_panel_reference']
        center = aperture['reference_psu_center_mm']
        hole_point = (center[0], center[1], backs[0].position[2])
        self.assertFalse(_inside(hole_point, self.shape(backs[0])))
        # The real aperture must not be implemented by deleting the wall.
        self.assertTrue(_inside((-self.scene.dimensions[0]/2+5., backs[0].position[1],
            backs[0].position[2]), self.shape(backs[0])))
        case = self.job[0]
        if case in ('phanteks-nv7', 'deepcool-ch780', 'havn-hs-420'):
            reference = meta['rear_divider_reference']
            layout = meta['case_pose_reference']
            divider = next(mesh for mesh in self.scene.meshes if mesh.name == 'rear-chamber-divider')
            low, high = self.bound(divider)
            self.assertEqual(reference['case_id'], case)
            self.assertFalse(reference['positions_verified'])
            self.assertAlmostEqual(low[1], reference['bottom_y_mm'])
            self.assertAlmostEqual(high[1], reference['top_y_mm'])
            key = 'rear_divider_top_y_mm' if case == 'phanteks-nv7' else 'rear_divider_bottom_y_mm'
            self.assertAlmostEqual(reference['top_y_mm' if case == 'phanteks-nv7' else 'bottom_y_mm'], layout[key])
        if case == 'jonsbo-tk2-black':
            conflict = next(row for row in shroud['source_conflicts'] if row['field'] == 'air_cooler_height_mm')
            self.assertEqual((conflict['manual'], conflict['product'], conflict['resolved']), (155., 165., False))

    def test_every_actual_psu_child_clears_reference_skins_holes_divider_floor_and_feet(self):
        materials = self.materials()
        self.assertTrue(materials)
        for psu in (mesh for mesh in self.scene.meshes if mesh.component == 'psu'):
            for material in materials:
                with self.subTest(psu=psu.name, material=material.name):
                    self.assert_material_clear(psu, material)

    def test_other_selected_hardware_clears_new_case_material_and_tray(self):
        for mesh in self.scene.meshes:
            if mesh.component not in HARDWARE - {'psu'}:
                continue
            for material in self.materials():
                with self.subTest(part=mesh.part_id, mesh=mesh.name, material=material.name):
                    self.assert_material_clear(mesh, material)

    def test_selected_fan_entire_material_bank_and_psu_clear_gpu_board_ram_and_cooler(self):
        bank = [mesh for mesh in self.scene.meshes if mesh.component == 'fans']
        self.assertTrue(bank)
        others = [mesh for mesh in self.scene.meshes if mesh.component in HARDWARE - {'fans'}]
        for fan in bank:
            for mesh in others:
                with self.subTest(fan=fan.name, target=mesh.name, part=mesh.part_id):
                    self.assert_material_clear(fan, mesh)
        # An empty rear bay must not merely clear its own supports while the
        # upright PSU intersects the actual board or the installed GPU.
        for psu in (mesh for mesh in self.scene.meshes if mesh.component == 'psu'):
            for mesh in (mesh for mesh in others if mesh.component != 'psu'):
                with self.subTest(psu=psu.name, target=mesh.name, part=mesh.part_id):
                    self.assert_material_clear(psu, mesh)

    def test_six_styles_share_all_physical_arrays_and_empty_telemetry_remains_static(self):
        physical = [mesh for mesh in self.scene.meshes if not mesh.name.startswith('style-')]
        cache_key = self.cache.key
        for style in SIX:
            value = self.cache.build(dict(self.spec, visual_style=style))
            self.assertEqual(self.cache.key, cache_key)
            rows = [mesh for mesh in value.meshes if not mesh.name.startswith('style-')]
            self.assertEqual(len(rows), len(physical))
            for old, current in zip(physical, rows):
                self.assertIs(current.vertices, old.vertices)
                self.assertEqual((current.name, current.component, current.part_id, current.position,
                    current.axis, current.rotor, current.direction),
                    (old.name, old.component, old.part_id, old.position, old.axis, old.rotor, old.direction))
                if current.component in HARDWARE:
                    self.assertTrue(mesh_visible(current, False, False))
                    self.assertTrue(mesh_visible(current, True, True))
        for family, metric in (('cpu', 'cpu_temp'), ('gpu', 'gpu_temp')):
            view = inspection_snapshot({}, self.spec, self.config, family, now=100.,
                                       scene_metadata=self.scene.metadata)
            row = next(row for row in view['rows'] if row.get('metric') == metric)
            self.assertFalse(row['available'])
            self.assertEqual(row['value'], '—')
        self.assertFalse(cpu_fan_state({}, now=100.)['available'])
        node = SimpleNamespace(_scene=self.scene, _closed=False, _error='', _motion=True,
            _animate=True, _demo=False, _fan_available=False, _rpm=0., _phase=0., _fan_expiry=0.,
            _cpu_available=False, _cpu_rpm=0., _cpu_phase=0., _cpu_expiry=0.,
            _cpu_tach_usable=self.scene.metadata['cooling']['cpu_fan_tach_usable'],
            _real_cpu_rotor_parts=self.scene.metadata['cooling'].get('real_cpu_rotor_parts', ()),
            _active=False, _clock_active_state=False, _effect=None, _focus='all',
            animationActiveChanged=Mock(), update=Mock())
        node.isVisible = lambda: True
        node.window = lambda: SimpleNamespace(isMinimized=lambda: False)
        node._update_animation_state = lambda: AssemblyViewport._update_animation_state(node)
        node._update_animation_state()
        for _ in range(10):
            self.assertFalse(AssemblyViewport._step_fans(node, 100.))
        self.assertFalse(node._active)
        self.assertFalse(node._clock_active_state)
        node.animationActiveChanged.assert_not_called()
        phases = {'gpu': node._phase, **{key: node._cpu_phase for key in node._real_cpu_rotor_parts}}
        self.assertTrue(all(mesh_phase(mesh, phases) == 0. for mesh in physical if mesh.rotor))


def load_tests(loader, tests, pattern):
    # Unittest disposes each class before starting the next. No 17-scene list,
    # no second build for style QA, no test filter that quietly omits a case.
    suite = unittest.TestSuite()
    for job in JOBS:
        selected = type(job[0].replace('-', '_')+'RearHost052Tests',
                        (RearCaseHosts052Tests,), dict(job=job))
        suite.addTests(loader.loadTestsFromTestCase(selected))
    return suite


if __name__ == '__main__':
    unittest.main()
