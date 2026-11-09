"""Reference mount descriptors, not geometry rebuilds or removal certification."""
import copy
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from assembly_mount_frames052 import mount_descriptor, MAX_MESHES, MAX_ROWS


class IdentityMesh:
    def __init__(self, name, component, part_id):
        self.name, self.component, self.part_id = name, component, part_id

    @property
    def vertices(self): raise AssertionError('Descriptor must not scan geometry')

    @property
    def axis(self): raise AssertionError('Mount normal must not come from a rotor')


def fixture(target='fans:rear:0', mount='rear', position=(-51.5, 174., -229.), compatibility='documented_fan_mount'):
    # Contract data from the existing051 case-fan producer; this small fixture
    # is independent of private snapshots, real profiles, Qt and mesh arrays.
    return SimpleNamespace(meshes=(IdentityMesh('case-frame', 'case', ''),
        IdentityMesh('fan-frame', 'fans', target), IdentityMesh('fan-rotor', 'fans', target),
        IdentityMesh('board-pcb', 'board', 'board:0'),
        IdentityMesh('cable-1-strands', 'cables', 'cables:all')),
        metadata=dict(attachment_anchors={}, cooling=dict(
            parts=[dict(id=target, kind='case_fan', model_id='arctic-p12-pwm', mount=mount,
                        compatibility=compatibility, placement_method='centered_mount_reference')],
            fans=[dict(part_id=target, model_id='arctic-p12-pwm', role='case', position=position,
                       axis=(0., 0., 1.), direction='exhaust')],
            wire_anchors=[dict(id=target+':power', owner=target, kind='fan4', role='case')],
            mount_plane_sources={}), auxiliary=dict(cable_count=1, cables=[dict(
                source_owner=target, target_owner='board', kind='fan4', role='case',
                mesh_prefix='cable-1', routing_failed=False, external_route=False)])))


class MountFrameTests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL', 'subprocess.Popen', 'threading.Thread.start', 'socket.socket'):
            self.enterContext(patch(name, side_effect=AssertionError('No native, process, sampler or network')))

    def test_seven_existing_reference_mounts_use_case_plane_not_airflow_or_rotor(self):
        table = (
            ('north', 'fans:front:0', 'front', (0., -120., 229.), (0., 0., -1.)),
            ('north', 'fans:front:1', 'front', (0., 0., 229.), (0., 0., -1.)),
            ('north', 'fans:front:2', 'front', (0., 120., 229.), (0., 0., -1.)),
            ('north', 'fans:rear:0', 'rear', (-51.5, 174., -229.), (0., 0., 1.)),
            ('helios', 'fans:top:0', 'top', (0., 273., 60.), (0., -1., 0.)),
            ('helios', 'fans:top:1', 'top', (0., 273., -60.), (0., -1., 0.)),
            ('helios', 'fans:rear:0', 'rear', (-56.5, 215., -260.), (0., 0., 1.)))
        for capture, target, mount, position, direction in table:
            with self.subTest(capture=capture, target=target):
                value = fixture(target, mount, position, 'unverified' if capture=='helios' and mount=='rear' else 'documented_fan_mount')
                before = copy.deepcopy(value.metadata)
                for airflow, rotor in (('intake', (0, 1, 0)), ('exhaust', None)):
                    value.metadata['cooling']['fans'][0].update(direction=airflow, axis=rotor)
                    result = mount_descriptor(value, target)
                    self.assertTrue(result['available'], result['reason'])
                    self.assertEqual(result['direction'], direction)
                    self.assertEqual(result['position'], position)
                    self.assertFalse(result['motion_available'])
                    self.assertTrue(result['continuous_clearance_required'])
                    self.assertTrue(result['manual_release_required'])
                    self.assertFalse(result['mechanical_installation_complete'])
                    self.assertFalse(result['full_case_extraction'])
                # Only this test changes its own synthetic airflow/axis fields.
                value.metadata['cooling']['fans'][0].update(direction='exhaust', axis=(0.,0.,1.))
                self.assertEqual(value.metadata, before)

    def test_authored_tilted_plane_overrides_canonical_and_descriptor_is_detached(self):
        value = fixture(); value.metadata['attachment_anchors']['case_mount_planes'] = dict(rear=dict(
            position=(0., 10., -80.), normal=(1., 1., 0.), source='https://example.invalid/reference'))
        before = copy.deepcopy(value.metadata)
        result = mount_descriptor(value, 'fans:rear:0')
        self.assertTrue(result['available'])
        self.assertEqual(result['mount_frame']['source_kind'], 'authored_case_mount_plane_reference')
        self.assertAlmostEqual(result['direction'][0], -math.sqrt(.5))
        self.assertAlmostEqual(result['direction'][1], -math.sqrt(.5))
        self.assertEqual(result['connection_mesh_names'], ('cable-1-strands',))
        result['mount_frame']['plane_position'] = (999.,999.,999.)
        result['hide_mesh_names'] = ('wrong',)
        self.assertEqual(value.metadata, before)
        self.assertNotEqual(mount_descriptor(value, 'fans:rear:0')['hide_mesh_names'], result['hide_mesh_names'])

    def test_malformed_or_lost_authored_plane_cannot_fall_back_to_a_guessed_axis(self):
        for normal in ((0.,0.,0.), (True,0,1), (math.nan,0,1), (10**500,0,1), [0,1], 'rear'):
            with self.subTest(normal=str(normal)[:30]):
                value = fixture(); value.metadata['attachment_anchors']['case_mount_planes'] = dict(rear=dict(position=(0,0,0), normal=normal))
                self.assertFalse(mount_descriptor(value, 'fans:rear:0')['available'])
        value = fixture(); value.metadata['cooling']['mount_plane_sources']['rear'] = dict(source='lost-normal')
        self.assertEqual(mount_descriptor(value, 'fans:rear:0')['reason'], 'mount_plane_frame_missing')
        value = fixture(); value.metadata['cooling']['parts'][0]['mount'] = ['rear']
        self.assertFalse(mount_descriptor(value, 'fans:rear:0')['available'])

    def test_duplicate_missing_or_mixed_part_identity_is_refused_without_prefix_inference(self):
        for change in ('duplicate_part', 'duplicate_fan', 'missing_fan', 'mismatched_model', 'wrong_component'):
            with self.subTest(change=change):
                value = fixture(); cooling = value.metadata['cooling']
                if change=='duplicate_part': cooling['parts'].append(copy.deepcopy(cooling['parts'][0]))
                elif change=='duplicate_fan': cooling['fans'].append(copy.deepcopy(cooling['fans'][0]))
                elif change=='missing_fan': cooling['fans'].clear()
                elif change=='mismatched_model': cooling['fans'][0]['model_id'] = 'other'
                else: value.meshes[1].component = 'gpu'
                self.assertFalse(mount_descriptor(value, 'fans:rear:0')['available'])
        value = fixture('arbitrary-source-id', 'front', (0,0,100))
        self.assertTrue(mount_descriptor(value, 'arbitrary-source-id')['available'])
        self.assertFalse(mount_descriptor(value, 'fans')['available'])

    def test_unknown_duplicate_or_overlapping_connection_ownership_is_refused(self):
        for change in ('unknown_owner', 'missing_prefix', 'duplicate_prefix', 'overlap_prefix', 'unowned_mesh', 'rigid_prefix'):
            with self.subTest(change=change):
                value = fixture(); aux = value.metadata['auxiliary']; wire = aux['cables'][0]
                if change=='unknown_owner': wire['source_owner'] = 'unknown'
                elif change=='missing_prefix': wire.pop('mesh_prefix')
                elif change in ('duplicate_prefix','overlap_prefix'):
                    other = copy.deepcopy(wire)
                    if change=='overlap_prefix': other['mesh_prefix'] += '-branch'
                    aux['cables'].append(other); aux['cable_count'] += 1
                elif change=='unowned_mesh': value.meshes += (IdentityMesh('unmapped-wire', 'cables', 'cables:all'),)
                else: wire['mesh_prefix'] = 'fan'
                self.assertFalse(mount_descriptor(value, 'fans:rear:0')['available'])

    def test_exact_connection_prefix_boundary_keeps_another_fans_wire_out(self):
        value = fixture(); aux = value.metadata['auxiliary']
        value.meshes += (IdentityMesh('other-fan', 'fans', 'other-fan:0'),
                         IdentityMesh('cable-10-strands', 'cables', 'cables:all'))
        value.metadata['cooling']['wire_anchors'].append(dict(owner='other-fan:0', kind='fan4', role='case'))
        aux['cables'].append(dict(aux['cables'][0], source_owner='other-fan:0', mesh_prefix='cable-10'))
        aux['cable_count'] = 2
        result = mount_descriptor(value, 'fans:rear:0')
        self.assertTrue(result['available'])
        self.assertEqual(result['hide_mesh_names'], ('cable-1-strands',))
        self.assertEqual(result['connection_prefixes'], ('cable-1',))

    def test_absent_or_incomplete_factory_wires_never_mean_no_dependency(self):
        for change in ('no_anchor', 'no_cable', 'missing_argb', 'unknown_kind', 'failed_route', 'missing_route_status'):
            with self.subTest(change=change):
                value = fixture(); cooling = value.metadata['cooling']; aux = value.metadata['auxiliary']
                if change=='no_anchor': cooling['wire_anchors'].clear()
                elif change=='no_cable': aux['cables'].clear(); aux['cable_count'] = 0; value.meshes = value.meshes[:-1]
                elif change=='missing_argb': cooling['wire_anchors'].append(dict(owner='fans:rear:0', kind='argb3', role='case'))
                elif change=='unknown_kind': aux['cables'][0]['kind'] = []
                elif change=='failed_route': aux['cables'][0]['routing_failed'] = True
                else: aux['cables'][0].pop('external_route')
                self.assertFalse(mount_descriptor(value, 'fans:rear:0')['available'])
        value = fixture(); value.metadata['cooling']['parts'][0]['kind'] = 'radiator_fan'
        self.assertEqual(mount_descriptor(value, 'fans:rear:0')['reason'], 'radiator_fan_internal_harness_unverified')

    def test_malformed_and_bounded_inputs_remain_unavailable_without_work(self):
        self.assertFalse(mount_descriptor(None, 'fans:rear:0')['available'])
        for target in (None, True, '', 'x'*161):
            self.assertFalse(mount_descriptor(fixture(), target)['available'])
        for change in ('meshes', 'rows', 'bad_mesh', 'no_anchors', 'bad_position'):
            value = fixture()
            if change=='meshes': value.meshes = value.meshes * (MAX_MESHES//len(value.meshes)+1)
            elif change=='rows': value.metadata['cooling']['parts'] *= MAX_ROWS+1
            elif change=='bad_mesh': value.meshes[0].name = None
            elif change=='no_anchors': value.metadata.pop('attachment_anchors')
            else: value.metadata['cooling']['fans'][0]['position'] = (0,False,1)
            self.assertFalse(mount_descriptor(value, 'fans:rear:0')['available'])


if __name__ == '__main__': unittest.main()
