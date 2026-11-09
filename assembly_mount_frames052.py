"""Detached reference mount frames for explicit independent case-fan parts.

``available`` validates this descriptor, NOT a movement or mechanical release.
The caller must explicitly release its listed reference dependencies and run a
bounded continuous clearance planner before enabling motion. Call on explicit
scene/selection changes only; this module owns no scene, cache, clock or I/O.
"""
from collections import Counter
import math

MAX_MESHES = 4096
MAX_ROWS = 256
MAX_CONNECTIONS = 16
MAX_CONNECTION_NAMES = 128


def _text(value):
    return isinstance(value, str) and 0 < len(value) <= 160


def _point(value):
    if (not isinstance(value, (tuple, list)) or len(value) != 3
            or any(type(x) not in (int, float) or not -1.e6 <= x <= 1.e6
                   or not math.isfinite(x) for x in value)):
        return None
    return tuple(float(x) for x in value)


def _unit(value):
    point = _point(value)
    length = math.hypot(*point) if point is not None else 0.
    return tuple(x / length for x in point) if math.isfinite(length) and length > 1.e-9 else None


def _rows(value):
    return (value if isinstance(value, (tuple, list)) and len(value) <= MAX_ROWS
            and all(isinstance(row, dict) for row in value) else None)


def _prefix(name, prefix):
    return name == prefix or name.startswith(prefix + '-')


def _unavailable(reason, target=''):
    return dict(available=False, reason=reason, target=target if _text(target) else '',
                scope='reference_mount_frame_only', motion_available=False,
                direction=(0., 0., 0.), part_ids=(), hide_mesh_names=(),
                connection_mesh_names=(), connection_prefixes=(),
                continuous_clearance_required=True, manual_release_required=True,
                mechanical_installation_complete=False, full_case_extraction=False)


def _mount_frame(metadata, cooling, part):
    mount = part.get('mount')
    # Read the actual producer's convention, not a second guessed lookup and
    # never the rotor axis/intake/exhaust label. Import remains demand-only.
    from assembly_cooling import _MOUNT_NORMALS
    if not _text(mount) or mount not in _MOUNT_NORMALS:
        return None, 'case_fan_mount_unverified'
    anchors = metadata.get('attachment_anchors')
    if not isinstance(anchors, dict):
        return None, 'mount_metadata_unverified'
    planes = anchors.get('case_mount_planes', {})
    sources = cooling.get('mount_plane_sources', {})
    if not isinstance(planes, dict) or not isinstance(sources, dict):
        return None, 'mount_metadata_unverified'
    authored = planes.get(mount)
    if authored is not None:
        if not isinstance(authored, dict):
            return None, 'mount_plane_frame_unverified'
        normal, position = _unit(authored.get('normal')), _point(authored.get('position'))
        if normal is None or position is None:
            return None, 'mount_plane_frame_unverified'
        source = authored.get('source')
        source = source if isinstance(source, str) and len(source) <= 2048 else ''
        return dict(outward_normal=normal, plane_position=position,
                    source_kind='authored_case_mount_plane_reference', source=source,
                    source_path='attachment_anchors.case_mount_planes.' + mount,
                    position_verified=False), ''
    # A summary with a lost/omitted authored frame must not silently fall back
    # to a canonical axis: the real authored mounting plane could be tilted.
    if mount in sources or part.get('placement_method') == 'authored_mount_plane':
        return None, 'mount_plane_frame_missing'
    return dict(outward_normal=tuple(float(x) for x in _MOUNT_NORMALS[mount]),
                plane_position=None, source_kind='canonical_case_mount_reference',
                source='assembly_cooling._MOUNT_NORMALS',
                source_path='assembly_cooling._mount_plane', position_verified=False), ''


def _connections(meshes, cooling, auxiliary, target):
    wires = _rows(cooling.get('wire_anchors'))
    cables = _rows(auxiliary.get('cables'))
    if wires is None or cables is None:
        return None, 'connection_metadata_unverified'
    count = auxiliary.get('cable_count')
    if type(count) is not int or count != len(cables):
        return None, 'connection_metadata_unverified'
    part_ids = {getattr(mesh, 'part_id', '') for mesh in meshes if getattr(mesh, 'part_id', '')}
    components = {getattr(mesh, 'component', '') for mesh in meshes}
    known = part_ids | components | ({'case'} if 'panel' in components else set())
    if any(not _text(row.get('owner')) or row['owner'] not in known for row in wires):
        return None, 'connection_owner_unverified'
    owned = [row for row in wires if row['owner'] == target]
    if (not owned or len(owned) > MAX_CONNECTIONS
            or any(row.get('role') != 'case' or row.get('kind') not in ('fan4', 'argb3') for row in owned)):
        return None, 'fan_connections_unverified'
    prefixes = []
    for row in cables:
        prefix = row.get('mesh_prefix')
        if (not _text(prefix) or not _text(row.get('source_owner')) or not _text(row.get('target_owner'))
                or row['source_owner'] not in known or row['target_owner'] not in known):
            return None, 'connection_owner_unverified'
        if any(_prefix(prefix, previous) or _prefix(previous, prefix) for previous in prefixes):
            return None, 'connection_prefix_ambiguous'
        prefixes.append(prefix)
    matches = {prefix: [] for prefix in prefixes}
    for mesh in meshes:
        names = [prefix for prefix in prefixes if _prefix(mesh.name, prefix)]
        if names and mesh.component != 'cables':
            return None, 'connection_geometry_unverified'
        if mesh.component == 'cables':
            if len(names) != 1:
                return None, 'connection_geometry_unverified'
            matches[names[0]].append(mesh.name)
    if any(not names for names in matches.values()):
        return None, 'connection_geometry_unverified'
    linked = [row for row in cables if target in (row['source_owner'], row['target_owner'])]
    if (not linked or len(linked) > MAX_CONNECTIONS
            or any(row.get('role') != 'case' or row.get('kind') not in ('fan4', 'argb3')
                   or row.get('routing_failed') is not False
                   or row.get('external_route') is not False for row in linked)
            or Counter(row.get('kind') for row in owned) != Counter(row.get('kind') for row in linked)):
        return None, 'fan_connections_unverified'
    names = tuple(sorted({name for row in linked for name in matches[row['mesh_prefix']]}))
    if len(names) > MAX_CONNECTION_NAMES:
        return None, 'connection_budget_exceeded'
    return dict(connection_mesh_names=names, hide_mesh_names=names,
                connection_prefixes=tuple(row['mesh_prefix'] for row in linked),
                connection_kinds=tuple(row['kind'] for row in linked)), ''


def mount_descriptor(scene, target):
    """Describe one exact case-fan installation in source world coordinates.

    Inward translation is only a reference candidate. Fastener/manual releases,
    exact listed cable disconnection masks and whole-path clearance are still
    mandatory. A radiator fan's unresolved factory harness is never treated as
    absent, even when no independent electrical route was drawn for that fan.
    No vertices are read and no model lookup or sensor query is performed.
    """
    if not _text(target):
        return _unavailable('choose_individual_case_fan')
    if scene is None:
        return _unavailable('scene_unavailable', target)
    meshes = getattr(scene, 'meshes', None)
    metadata = getattr(scene, 'metadata', None)
    if (not isinstance(meshes, (tuple, list)) or not meshes or len(meshes) > MAX_MESHES
            or not isinstance(metadata, dict)):
        return _unavailable('scene_metadata_unverified', target)
    if any(not _text(getattr(mesh, 'name', None)) or not _text(getattr(mesh, 'component', None))
           or not isinstance(getattr(mesh, 'part_id', None), str) or len(mesh.part_id) > 160
           for mesh in meshes):
        return _unavailable('scene_metadata_unverified', target)
    cooling, auxiliary = metadata.get('cooling'), metadata.get('auxiliary')
    if not isinstance(cooling, dict) or not isinstance(auxiliary, dict):
        return _unavailable('scene_metadata_unverified', target)
    parts, fans = _rows(cooling.get('parts')), _rows(cooling.get('fans'))
    if parts is None or fans is None:
        return _unavailable('case_fan_metadata_unverified', target)
    records = [row for row in parts if row.get('id') == target]
    if len(records) != 1:
        return _unavailable('case_fan_identity_unverified', target)
    part = records[0]
    if part.get('kind') == 'radiator_fan':
        return _unavailable('radiator_fan_internal_harness_unverified', target)
    if part.get('kind') != 'case_fan' or not _text(part.get('model_id')):
        return _unavailable('case_fan_identity_unverified', target)
    if part.get('compatibility') not in ('documented_fan_mount', 'unverified'):
        return _unavailable('case_fan_mount_unverified', target)
    selected = [mesh for mesh in meshes if getattr(mesh, 'part_id', '') == target]
    if not selected or any(getattr(mesh, 'component', '') != 'fans' for mesh in selected):
        return _unavailable('case_fan_geometry_unverified', target)
    rendered = [row for row in fans if row.get('part_id') == target]
    if (len(rendered) != 1 or rendered[0].get('role') != 'case'
            or rendered[0].get('model_id') != part['model_id']):
        return _unavailable('case_fan_identity_unverified', target)
    position = _point(rendered[0].get('position'))
    if position is None:
        return _unavailable('case_fan_position_unverified', target)
    frame, reason = _mount_frame(metadata, cooling, part)
    if frame is None:
        return _unavailable(reason, target)
    connections, reason = _connections(meshes, cooling, auxiliary, target)
    if connections is None:
        return _unavailable(reason, target)
    normal = frame['outward_normal']
    return dict(available=True, reason='reference_case_fan_mount_descriptor',
                target=target, kind='case_fan', model_id=part['model_id'], part_ids=(target,),
                scope='reference_mount_frame_only', motion_available=False,
                direction=tuple(-x for x in normal), mount=part['mount'],
                mount_outward_normal=normal, position=position, mount_frame=frame,
                mount_compatibility=part.get('compatibility', 'unverified'),
                manual_release_required=True, retention_mechanism_simulated=False,
                release_requirements=('manual_case_frame_fastener_reference_release',
                                      'explicit_listed_connection_disconnection_or_inspection_mask'),
                continuous_clearance_required=True, geometry_clearance_verified=False,
                mechanical_installation_complete=False, full_case_extraction=False,
                **connections)
