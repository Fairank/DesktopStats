"""Independent radiator bodies, genuine cavities and bounded static geometry."""
import copy
import math
import unittest
from unittest.mock import patch

from assembly_geometry import Mesh, color
from assembly_radiator044 import build_radiator_detail, TRIANGLE_BUDGETS
from assembly_style import apply_model_styles
from liquid_cooling_catalog044 import records, get_radiator
from top_bar_config import HARDWARE_ICON_STYLES


IDENTITY = ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.))
def add(a, b): return tuple(x+y for x, y in zip(a, b))
def sub(a, b): return tuple(x-y for x, y in zip(a, b))
def mul(a, k): return tuple(x*k for x in a)
def dot(a, b): return sum(x*y for x, y in zip(a, b))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def world(p, c=(0., 0., 0.), axes=IDENTITY, direction=False):
    result = tuple(sum(p[k]*axes[k][j] for k in range(3)) for j in range(3))
    return result if direction else add(result, c)


class StaticBuilder:
    """A real value builder, not a QObject/MagicMock or a graphics backend."""
    def __init__(self, level='balanced'):
        self.level = level; self.meshes = []; self.parts = ['caller-part']
        self.fans = ['caller-fan']; self.rotors = ['caller-rotor']; self.wire_anchors = ['caller-wire']

    def put(self, name, vertices, tint, center, basis, component, part):
        out = []
        for n in range(0, len(vertices), 6):
            out.extend(world(vertices[n:n+3], center, basis))
            out.extend(world(vertices[n+3:n+6], axes=basis, direction=True))
        self.meshes.append(Mesh(name, tuple(out), color(tint), component=component, part_id=part))


def build(profile=None, level='balanced', center=(0., 0., 0.), basis=IDENTITY, dimensions=None):
    profile = get_radiator('corsair-xr5-240') if profile is None else profile
    value = copy.deepcopy(profile)
    builder = StaticBuilder(level)
    metadata = build_radiator_detail(builder, dimensions or profile['dimensions_mm'], center, basis,
                                     'cooler:radiator', profile)
    assert value == profile
    return tuple(builder.meshes), metadata, builder


def segment_hit(meshes, start, end):
    """Independent finite Moller-Trumbore test against every actual triangle."""
    direction = sub(end, start)
    for mesh in meshes:
        for offset in range(0, len(mesh.vertices), 18):
            a, b, c = (add(mesh.vertices[offset+k:offset+k+3], mesh.position) for k in (0, 6, 12))
            e, f = sub(b, a), sub(c, a); p = cross(direction, f); det = dot(e, p)
            if abs(det) < 1e-10: continue
            t = sub(start, a); u = dot(t, p)/det
            if u < -1e-8 or u > 1.+1e-8: continue
            q = cross(t, e); v = dot(direction, q)/det
            if v < -1e-8 or u+v > 1.+1e-8: continue
            distance = dot(f, q)/det
            if -1e-8 <= distance <= 1.+1e-8: return True
    return False


class AssemblyRadiator044Tests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL', 'subprocess.Popen', 'threading.Thread.start', 'socket.socket'):
            self.enterContext(patch(target, side_effect=AssertionError('Radiators are pure static geometry')))

    def test_all_twenty_four_three_lods_envelopes_unit_normals_winding_and_hard_budgets(self):
        self.assertEqual(len(records()), 24)
        for profile in records():
            last = 0
            for level in ('eco', 'balanced', 'close'):
                with self.subTest(model=profile['id'], level=level):
                    meshes, result, builder = build(profile, level)
                    meta = result['metadata']; bounds = profile['dimensions_mm']
                    self.assertLessEqual(meta['triangle_count'], TRIANGLE_BUDGETS[level])
                    self.assertGreater(meta['triangle_count'], last); last = meta['triangle_count']
                    self.assertEqual(meta['triangle_count'], sum(m.vertex_count//3 for m in meshes))
                    self.assertGreaterEqual(len(meshes), 6); self.assertLessEqual(len(meshes), 9)
                    self.assertEqual(result['metadata']['modelled_ports'], len(profile['ports']))
                    self.assertFalse(any(m.rotor for m in meshes))
                    self.assertEqual(builder.parts, ['caller-part']); self.assertEqual(builder.fans, ['caller-fan'])
                    self.assertEqual(builder.rotors, ['caller-rotor']); self.assertEqual(builder.wire_anchors, ['caller-wire'])
                    for m in meshes:
                        self.assertEqual(m.component, 'cooler'); self.assertEqual(m.part_id, 'cooler:radiator')
                        for n in range(0, len(m.vertices), 6):
                            point, normal = m.vertices[n:n+3], m.vertices[n+3:n+6]
                            self.assertTrue(all(math.isfinite(x) for x in point+normal))
                            self.assertAlmostEqual(dot(normal, normal), 1., places=6)
                            for x, bound in zip(point, (bounds['width'], bounds['length'], bounds['thickness'])):
                                self.assertLessEqual(abs(x), bound/2+1e-5)
                        for n in range(0, len(m.vertices), 18):
                            a, b, c = (m.vertices[n+k:n+k+3] for k in (0, 6, 12))
                            actual = cross(sub(b, a), sub(c, a)); self.assertGreater(dot(actual, m.vertices[n+3:n+6]), 1e-10)

    def test_all_observed_mouths_are_genuinely_open_not_disks_or_hidden_shells(self):
        for profile in records():
            meshes, result, _ = build(profile)
            for port in result['ports']:
                with self.subTest(model=profile['id'], port=port['id']):
                    p, normal = port['position'], port['normal']
                    up = (0.,1.,0.) if abs(normal[1]) < .9 else (1.,0.,0.)
                    tangent = cross(up, normal)
                    offsets = ((0.,0.,0.), mul(tangent,3.8), mul(tangent,-3.8), mul(up,3.8), mul(up,-3.8))
                    for offset in offsets:
                        sample = add(p,offset)
                        self.assertFalse(segment_hit(meshes, add(sample, mul(normal, 2)), sub(sample, mul(normal, 7))), (profile['id'],port['id'],offset))
                    self.assertTrue(port['open']); self.assertFalse(port['positions_verified'])
                    self.assertIn('G1/4', port['thread'])

    def test_mounting_holes_pass_through_both_folded_flange_faces(self):
        for identity in ('corsair-xr5-240', 'xspc-ex280', 'xspc-rx360-v3'):
            meshes, result, _ = build(get_radiator(identity))
            thickness = result['metadata']['envelope_mm']['thickness']
            for hole in result['mount_holes']:
                p = hole['position']
                self.assertFalse(segment_hit(meshes, (p[0], p[1], thickness), (p[0], p[1], -thickness)), identity)
            # A real metal region next to a hole remains present, rather than
            # deleting the entire mounting strip to make an openness test pass.
            point = result['mount_holes'][0]['position']
            self.assertTrue(segment_hit(meshes, (point[0]+3., point[1], thickness), (point[0]+3., point[1], -thickness)))

    def test_rear_and_side_observed_ports_open_through_every_intersecting_wall(self):
        profile = copy.deepcopy(get_radiator('corsair-xr5-240'))
        profile.update(ports_count=4, ports=[
            dict(id='back', face='rear', position_normalized=[0., .455, -.5]),
            dict(id='left', face='left', position_normalized=[-.5, .455, 0.]),
            dict(id='right', face='right', position_normalized=[.5, .455, 0.]),
            dict(id='end', face='end', end=-1, position_normalized=[0., -.5, 0.])])
        meshes, result, _ = build(profile)
        for port in result['ports']:
            p, normal = port['position'], port['normal']
            self.assertFalse(segment_hit(meshes, add(p, mul(normal, 2)), sub(p, mul(normal, 7))), port['id'])

    def test_caps_are_only_explicit_and_do_not_turn_alternative_connections_into_installed_hoses(self):
        profile = copy.deepcopy(get_radiator('xspc-rx360-v3'))
        meshes, open_result, _ = build(profile)
        self.assertEqual(len(open_result['ports']), 4)
        self.assertFalse(any('plug' in m.name for m in meshes))
        profile['ports'][-1]['capped'] = True
        capped_meshes, capped, _ = build(profile)
        self.assertEqual(sum('plug' in m.name for m in capped_meshes), 1)
        self.assertEqual(sum(not p['open'] for p in capped['ports']), 1)
        port = capped['ports'][-1]; p, normal = port['position'], port['normal']
        self.assertTrue(segment_hit(capped_meshes, add(p, mul(normal, 2)), sub(p, mul(normal, 7))))

    def test_unknown_positions_and_unverified_thread_never_gain_invented_mouths(self):
        for identity in ('ek-quantum-surface-p360m', 'hardwarelabs-nemesis-420gts'):
            profile = get_radiator(identity); _, result, _ = build(profile)
            self.assertEqual(result['ports'], []); self.assertGreater(profile['ports_count'], 0)
            self.assertTrue(result['metadata']['unknown'])
        profile = copy.deepcopy(get_radiator('corsair-xr5-240')); profile['port_thread_verified'] = False
        meshes, result, _ = build(profile)
        self.assertEqual(result['ports'], []); self.assertFalse(any('port-' in m.name for m in meshes))

    def test_aio_keeps_envelope_but_owns_no_ports_pump_fans_or_part_entries(self):
        from assembly_cooling import _Builder
        dimensions = dict(length=398, width=120, thickness=38, fan_size_mm=120, fan_count=3)
        builder = _Builder('balanced'); parts = list(builder.parts)
        result = build_radiator_detail(builder, dimensions, (13., -5., 8.), IDENTITY, 'cooler:radiator')
        self.assertEqual(result['ports'], []); self.assertEqual(result['metadata']['port_owner'], 'caller_aio')
        self.assertEqual(builder.parts, parts); self.assertFalse(builder.rotors); self.assertFalse(builder.fans)
        self.assertEqual(len(result['fan_faces']), 6)
        self.assertTrue(all(not row['installed'] for row in result['fan_faces']))
        self.assertFalse(any('pump' in m.name or 'port-' in m.name for m in builder.finish()))

    def test_no_fan_capacity_is_inferred_from_a_bare_envelope(self):
        builder = StaticBuilder()
        result = build_radiator_detail(builder, dict(length=280, width=120, thickness=30), (0.,0.,0.), IDENTITY, 'cooler:radiator')
        self.assertEqual(result['fan_faces'], []); self.assertEqual(result['mount_holes'], [])

    def test_aio_caller_pitch_is_used_without_promoting_reference_to_verified(self):
        builder = StaticBuilder()
        dimensions = dict(length=320.5, width=143, thickness=36, fan_size_mm=140,
                          fan_count=2, fan_mount_pitch_mm=125., fan_mount_pitch_verified=False)
        result = build_radiator_detail(builder, dimensions, (0.,0.,0.), IDENTITY, 'cooler:radiator')
        self.assertEqual(result['metadata']['mount_pitch_mm'],125.)
        self.assertFalse(result['metadata']['mount_pitch_verified'])
        self.assertEqual({abs(row['position'][0]) for row in result['mount_holes']},{62.5})
        self.assertEqual(result['ports'],[])

    def test_edge_terminal_ports_do_not_delete_or_block_independent_outer_fan_holes(self):
        # A center-of-tank mouth at y=.455 must not globally shorten both
        # outer flanges before the final y=172.5 mounting hole of a 360mm row.
        for identity in ('corsair-xr5-360','aquacomputer-airplex-radical2-360','xspc-tx240'):
            meshes,result,_=build(get_radiator(identity))
            self.assertEqual(len(result['mount_holes']),get_radiator(identity)['fan_count']*8)
            for row in result['mount_holes']:
                p=row['position'];self.assertFalse(segment_hit(meshes,(p[0],p[1],100.),(p[0],p[1],-100.)))

    def test_rigid_frames_preserve_lengths_and_transform_every_anchor_consistently(self):
        original, data, _ = build()
        theta = math.radians(19); co, si = math.cos(theta), math.sin(theta)
        frames = (IDENTITY, ((1.,0.,0.),(0.,co,si),(0.,-si,co)),
                  ((0.,1.,0.),(-1.,0.,0.),(0.,0.,1.)), ((0.,0.,-1.),(0.,1.,0.),(1.,0.,0.)))
        center = (23., -41., 7.)
        for axes in frames:
            meshes, moved, _ = build(center=center, basis=axes)
            for a, b in zip(original, meshes):
                self.assertEqual(len(a.vertices), len(b.vertices))
                for n in range(0, len(a.vertices), 6):
                    for actual, expected in zip(b.vertices[n:n+3], world(a.vertices[n:n+3], center, axes)):
                        self.assertAlmostEqual(actual, expected, places=7)
            for key, poskey in (('ports','position'), ('fan_faces','center'), ('mount_holes','position')):
                for a, b in zip(data[key], moved[key]):
                    for actual, expected in zip(b[poskey], world(a[poskey], center, axes)):
                        self.assertAlmostEqual(actual, expected, places=7)
                    for actual, expected in zip(b['normal'], world(a['normal'], axes=axes, direction=True)):
                        self.assertAlmostEqual(actual, expected, places=7)

    def test_all_thirteen_styles_share_physical_arrays_and_have_no_radiator_expression_or_clock(self):
        meshes, _, _ = build()
        self.assertEqual(len(HARDWARE_ICON_STYLES), 13)
        for style in HARDWARE_ICON_STYLES:
            styled, metadata = apply_model_styles(meshes, style, {}, (120.,280.,30.), {'front':'open'})
            self.assertEqual(len(styled), len(meshes)); self.assertFalse(metadata['decorative_expression'])
            self.assertTrue(all(a.vertices is b.vertices for a, b in zip(meshes, styled)))
            self.assertTrue(all(not m.rotor for m in styled))

    def test_airplex_silver_aluminium_stack_is_not_copper_folded_fins_or_silver_coolant_tubes(self):
        meshes, result, _ = build(get_radiator('aquacomputer-airplex-radical2-240'))
        tubes = next(m for m in meshes if 'flat-tube-samples' in m.name)
        fins = next(m for m in meshes if 'folded-fin-samples' in m.name)
        self.assertIn('copper round tubes / aluminium plate stack', result['metadata']['core_construction'])
        self.assertGreater(tubes.color[0], tubes.color[2]); self.assertLess(max(fins.color)-min(fins.color), .3)
        self.assertEqual(result['metadata']['louver_sample_cells'], 0)
        self.assertIsNone(result['metadata']['actual_fin_count'])
        # A sampled tube runs through a genuine clearance aperture in every
        # aluminium fin, with no plate triangles crossing its bore path.
        xs = [tubes.vertices[n] for n in range(0, len(tubes.vertices), 6)]
        axis = min(xs)+2.
        self.assertFalse(segment_hit((fins,), (axis,-150.,0.), (axis,150.,0.)))

    def test_balanced_fold_foil_has_a_fine_grid_without_thick_front_shutter_caps(self):
        meshes,result,_=build(get_radiator('corsair-xr5-360'))
        fins=next(m for m in meshes if 'folded-fin-samples' in m.name)
        self.assertTrue(result['metadata']['foil_is_zero_thickness_reference'])
        # Default detail must not regress into the former ~25mm-wide solid
        # triangular shutters. This checks the actual projected geometry and
        # missing front/back slab caps, rather than a particular row constant.
        for n in range(0,len(fins.vertices),18):
            points=[fins.vertices[n+k:n+k+3] for k in (0,6,12)]
            self.assertLess(abs(fins.vertices[n+5]),.9)
            for a,b in zip(points,points[1:]+points[:1]):self.assertLess(math.hypot(a[0]-b[0],a[1]-b[1]),15.)

    def test_invalid_inputs_and_disagreeing_envelopes_are_transactional(self):
        profile = copy.deepcopy(get_radiator('corsair-xr5-240'))
        variants = [dict(dimensions=dict(length=float('nan'),width=120,thickness=30)),
                    dict(dimensions=dict(length=280,width=True,thickness=30)),
                    dict(dimensions=dict(length=281,width=120,thickness=30)),
                    dict(basis=((1.,0.,0.),(0.,1.,0.),(0.,0.,-1.))),
                    dict(basis=((2.,0.,0.),(0.,1.,0.),(0.,0.,1.)))]
        for variant in variants:
            builder = StaticBuilder()
            with self.assertRaises(ValueError):
                build_radiator_detail(builder, variant.get('dimensions',profile['dimensions_mm']), (0.,0.,0.), variant.get('basis',IDENTITY), 'cooler:radiator', profile)
            self.assertEqual(builder.meshes, [])
        bad = copy.deepcopy(profile); bad['ports'][0]['position_normalized'] = [0.,0.,0.]
        builder = StaticBuilder()
        with self.assertRaises(ValueError): build_radiator_detail(builder, bad['dimensions_mm'], (0.,0.,0.), IDENTITY, 'cooler:radiator', bad)
        self.assertEqual(builder.meshes, [])


if __name__ == '__main__': unittest.main()
