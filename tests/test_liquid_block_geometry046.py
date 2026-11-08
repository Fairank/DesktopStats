"""Real retail loop meshes and source distinctions, without a window or GL."""
import copy
import math
import unittest
from unittest.mock import patch

from assembly_cooling import _add, _sub, _mul, _dot, _cross, _basis
from assembly_lighting import apply_lighting, light_kind
from assembly_style import apply_model_styles
from liquid_geometry046 import build_component, _body, LIMITS
from liquid_block_pump_expansion046 import records, get_record

STYLES = ('miniature', 'cartoon', 'notebook_color', 'notebook_line', 'sticker', 'papercut')


def ray_hit(meshes, start, end):
    direction = _sub(end, start)
    for mesh in meshes:
        for offset in range(0, len(mesh.vertices), 18):
            a, b, c = (_add(mesh.vertices[offset+i:offset+i+3], mesh.position) for i in (0, 6, 12))
            edge1, edge2 = _sub(b, a), _sub(c, a)
            perpendicular = _cross(direction, edge2)
            determinant = _dot(edge1, perpendicular)
            if abs(determinant) < 1e-9:
                continue
            inv = 1/determinant
            delta = _sub(start, a)
            u = inv*_dot(delta, perpendicular)
            if not -1e-7 <= u <= 1+1e-7:
                continue
            cross = _cross(delta, edge1)
            v = inv*_dot(direction, cross)
            if v < -1e-7 or u+v > 1+1e-7:
                continue
            if 1e-5 < inv*_dot(edge2, cross) < 1-1e-5:
                return True
    return False


class LiquidBlockGeometry046Tests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL', 'socket.socket', 'threading.Thread.start', 'subprocess.Popen'):
            self.enterContext(patch(target, side_effect=AssertionError('No device I/O, network or worker')))

    def test_all_32_three_lods_are_finite_budgeted_stationary_and_detached(self):
        for row in records():
            original = copy.deepcopy(row)
            previous = 0
            for level, limit in LIMITS.items():
                with self.subTest(identity=row['id'], level=level):
                    meshes, meta = build_component(row, level)
                    count = sum(mesh.vertex_count//3 for mesh in meshes)
                    self.assertTrue(meshes)
                    self.assertEqual(count, meta['triangle_count'])
                    self.assertGreaterEqual(count, previous)
                    self.assertLessEqual(count, limit)
                    previous = count
                    self.assertFalse(meta['telemetry_bound'])
                    self.assertFalse(meta['fit_verified'])
                    for mesh in meshes:
                        self.assertFalse(mesh.rotor)
                        self.assertEqual(mesh.component, 'cooler')
                        self.assertEqual(mesh.part_id, 'cooler:'+row['part_kind'])
                        for offset in range(0, len(mesh.vertices), 6):
                            normal = mesh.vertices[offset+3:offset+6]
                            self.assertTrue(all(math.isfinite(v) for v in mesh.vertices[offset:offset+6]))
                            self.assertAlmostEqual(_dot(normal, normal), 1., places=6)
            self.assertEqual(row, original)

    def test_all_declared_openings_are_open_and_surrounded_by_real_shells(self):
        for row in records():
            for level in LIMITS:
                meshes, meta = build_component(row, level)
                for port in meta['ports']:
                    with self.subTest(identity=row['id'], level=level, port=port['id']):
                        point, normal = port['position'], port['normal']
                        self.assertFalse(ray_hit(meshes, _add(point, _mul(normal, 2)), _sub(point, _mul(normal, 4))))
                        tangent = _basis(normal)
                        radius = ((port.get('tube_inner_mm') or 0)/2+.6 if port.get('tube_type') == 'soft'
                                  else 10.7 if port.get('thread') == 'M20' else 7.1)
                        hits = []
                        for axis in tangent[:2]:
                            for sign in (-1, 1):
                                q = _add(point, _mul(axis, sign*radius))
                                hits.append(ray_hit(meshes, _add(q, _mul(normal, 2)), _sub(q, _mul(normal, 4))))
                        self.assertTrue(any(hits), 'Opening anchor is floating outside the actual body')

    def test_source_lighting_is_limited_and_recoloring_never_adds_geometry(self):
        for row in records():
            meshes, _ = build_component(row)
            rgb = [m for m in meshes if light_kind(m)]
            if not any('rgb' in zone for zone in row['observed_lighting']):
                self.assertEqual(rgb, [])
            for mode in ('off', 'warm', 'mint', 'violet'):
                changed, meta = apply_lighting(meshes, mode)
                self.assertEqual(len(changed), len(meshes))
                self.assertTrue(all(a.vertices is b.vertices for a, b in zip(meshes, changed)))
                self.assertFalse(meta['lighting_preview']['geometry_added'])
                self.assertFalse(meta['lighting_preview']['animated'])
        xpx, _ = build_component(get_record('alphacool-xpx-pro-aurora-brass'))
        lit = [m for m in xpx if light_kind(m)]
        self.assertEqual([m.name for m in lit], ['loop-source-observed-corner-argb-window'])
        self.assertLess(max(lit[0].vertices[0::6])-min(lit[0].vertices[0::6]), 10)
        core, _ = build_component(get_record('alphacool-core1-black'))
        self.assertFalse(any(light_kind(m) for m in core))

    def test_six_styles_share_real_mechanical_arrays_and_no_new_rotors(self):
        for row in records():
            meshes, _ = build_component(row)
            env = row['reference_envelope_mm']
            for style in STYLES:
                colored, meta = apply_model_styles(meshes, style, {}, (env['width'], env['depth'], env['height']), {})
                self.assertGreaterEqual(len(colored), len(meshes))
                self.assertTrue(all(a.vertices is b.vertices for a, b in zip(meshes, colored)))
                self.assertTrue(all(a.part_id == b.part_id and not b.rotor for a, b in zip(meshes, colored)))
                self.assertTrue(all(m.name.startswith('style-') and not m.rotor for m in colored[len(meshes):]))
                if style == 'miniature':
                    self.assertEqual(len(colored), len(meshes))

    def test_naked_motor_top_and_motorless_combos_have_distinct_mechanics(self):
        for row in records('pump'):
            meshes, meta = build_component(row)
            names = {m.name for m in meshes}
            if row['form'] == 'pump_body':
                self.assertEqual(meta['ports'], [])
                self.assertFalse(any('reservoir' in name for name in names))
            if row['form'] == 'pump_top':
                self.assertIn('loop-solotop-removable-aluminum-plate', names)
                self.assertFalse(any('motor-can' in name or 'oled' in name for name in names))
        for identity in ('aquacomputer-ultitube-d5-150-pro-body', 'xspc-d5-argb-mini-tank'):
            meshes, _ = build_component(get_record(identity))
            names = {m.name for m in meshes}
            self.assertFalse(any('sold-included' in name or 'sold-rear' in name or 'oled' in name for name in names))
            self.assertTrue(any('empty' in name and 'seat' in name for name in names))
        row = get_record('koolance-pmp450')
        meshes, _ = build_component(row)
        names = {m.name for m in meshes}
        self.assertIn('loop-pmp450-open-13mm-hose-barbs', names)
        self.assertNotIn('loop-open-reference-port-collars', names)
        self.assertEqual({p['thread'] for p in row['ports']}, {None})

    def test_verified_body_is_not_stretched_to_unverified_external_bracket(self):
        for identity in ('watercool-heatkiller-iv-pro-amd-acetal', 'alphacool-core1-black',
                         'aquacomputer-ultitube-d5-150-pro-next', 'aquacomputer-ultitube-d5-150-pro-body',
                         'aquacomputer-ultitube-d5-50-pro-next'):
            row = get_record(identity)
            self.assertEqual(_body(row), row['body_dimensions_mm'])
            meshes, meta = build_component(row)
            self.assertEqual(meta['body_dimensions_mm'], row['body_dimensions_mm'])
            self.assertFalse(meta['dimensions_verified'])
        row = get_record('watercool-heatkiller-iv-pro-amd-acetal')
        meshes, _ = build_component(row)
        self.assertTrue(any(m.name == 'loop-heatkiller-center-metal-strip' for m in meshes))
        self.assertTrue(any(m.name == 'loop-reference-socket-bracket-ears' for m in meshes))
        lcd, meta = build_component(get_record('corsair-xc7-rgb-elite-lcd'))
        self.assertEqual({p['face'] for p in meta['ports']}, {'right'})
        self.assertTrue(any(m.name == 'loop-xc7-round-lcd-blank-window' for m in lcd))
        self.assertFalse(any(m.rotor for m in lcd))

    def test_xd3_and_xd5_lcd_keep_real_housings_instead_of_generic_cubes_and_motors(self):
        xd3, _ = build_component(get_record('corsair-xd3-rgb'))
        opaque = [m for m in xd3 if m.name.startswith('loop-xd3-opaque-faceted-case')]
        self.assertTrue(opaque)
        self.assertTrue(all(m.color[3] == 1 for m in opaque))
        window = next(m for m in xd3 if m.name == 'loop-xd3-clear-front-chamber-window')
        self.assertLess(window.color[3], 1)
        self.assertTrue(any(m.name == 'loop-xd3-opposing-pierced-front-port-bridges' for m in xd3))
        self.assertTrue(any(m.name == 'loop-xd3-included-rear-ddc-motor' for m in xd3))
        lcd, _ = build_component(get_record('corsair-xd5-rgb-elite-lcd'))
        self.assertTrue(any(m.name.startswith('loop-xd5-lcd-armored-pump-housing') for m in lcd))
        self.assertFalse(any(m.name == 'loop-sold-included-pump-motor' for m in lcd))
        gen2, _ = build_component(get_record('corsair-xd5-rgb-gen2'))
        self.assertTrue(any(m.name == 'loop-sold-included-pump-motor' for m in gen2))

    def test_source_visible_dividers_brackets_and_controller_details_remain_static(self):
        dclt, _ = build_component(get_record('alphacool-dc-lt2-2600'))
        self.assertTrue(any(m.name == 'loop-dclt-source-observed-static-vanes' for m in dclt))
        self.assertFalse(any(m.rotor for m in dclt))
        pump, _ = build_component(get_record('koolance-pmp450'))
        volute = [m for m in pump if m.name.startswith('loop-pmp450-rounded-hydraulic-volute')]
        self.assertTrue(volute)
        self.assertTrue(any(m.name == 'loop-pmp450-source-u-bracket-uprights' for m in pump))
        vertices = tuple(v for mesh in volute for v in mesh.vertices)
        width = max(vertices[0::6])-min(vertices[0::6])
        height = max(vertices[1::6])-min(vertices[1::6])
        self.assertAlmostEqual(width, height, delta=1.)
        edge, _ = build_component(get_record('xspc-raystorm-edge-am5'))
        self.assertTrue(any(m.name == 'loop-edge-four-sided-hold-down-frame' for m in edge))
        self.assertFalse(any(m.name == 'loop-reference-socket-bracket-ears' for m in edge))
        for identity in ('aquacomputer-ultitube-d5-150-pro-next', 'aquacomputer-ultitube-d5-50-pro-next'):
            meshes, _ = build_component(get_record(identity))
            self.assertTrue(any(m.name.startswith('loop-included-d5-next-controller') for m in meshes))
            self.assertTrue(any(m.name == 'loop-included-d5-next-three-control-buttons' for m in meshes))

    def test_distinct_window_frames_round_cap_and_included_mounts_are_present(self):
        models = {
            'corsair-xc7-rgb-pro': ('loop-xc7-pro-opaque-window-frame', 'loop-xc7-pro-pierced-port-bridge'),
            'phanteks-glacier-c370i': ('loop-c370-stepped-source-top-cover',),
            'xspc-photon-v4-black': ('loop-photon-round-bottom-cap-rim',),
            'thermaltake-pacific-pr22-d5-plus': ('loop-pr22-source-motor-locking-hoop',
                                               'loop-pr22-source-mounting-uprights',
                                               'loop-pr22-source-mounting-feet-reference'),
        }
        for identity, expected in models.items():
            meshes, _ = build_component(get_record(identity))
            names = {m.name for m in meshes}
            self.assertTrue(set(expected).issubset(names))
        photon, _ = build_component(get_record('xspc-photon-v4-black'))
        self.assertFalse(any(m.name.startswith('loop-source-hydraulic-reservoir-base') for m in photon))

    def test_verified_overall_axes_include_sold_feet_and_do_not_grow_a_second_base(self):
        # Ports are qualitative face collars; allow their sub-millimeter
        # reference lip, never another 5 mm foot below an already verified H.
        for row in records():
            meshes, _ = build_component(row)
            for axis, key in enumerate(('width', 'height', 'depth')):
                actual = row['dimensions_mm'][key]
                if actual is None:
                    continue
                maximum = max(abs(value) for mesh in meshes for value in mesh.vertices[axis::6])
                with self.subTest(identity=row['id'], axis=key):
                    self.assertLessEqual(maximum, actual/2+1.)


if __name__ == '__main__':
    unittest.main()
