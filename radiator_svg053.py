"""On-demand static cards from the existing independent radiator geometry.

No component pipeline, fan, telemetry, image loader or second cache is owned
here. Published dimensions and reference shell/port construction stay distinct.
Original code/art: PolyForm Noncommercial 1.0.0; third-party rights unchanged.
"""
from copy import deepcopy
import re

from accessory_cancel047 import checkpoint

STYLES = ('miniature', 'cartoon', 'notebook_color', 'notebook_line', 'sticker',
          'papercut', 'inkwash', 'classic', 'outline', 'solid', 'soft', 'sketch',
          'notebook_smile')
MAX_TRIANGLES = 2800
_IDENTITY = ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.))
_ID = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z', re.ASCII)


def _valid_id(identity):
    return isinstance(identity, str) and 0 < len(identity) <= 64 and bool(_ID.fullmatch(identity))


def _valid_row(row):
    return (isinstance(row, dict) and row.get('category') == 'radiator'
            and _valid_id(row.get('id')) and isinstance(row.get('label'), str)
            and isinstance(row.get('brand'), str) and isinstance(row.get('sources'), (tuple, list))
            and isinstance(row.get('dimensions_mm'), dict))


def reference(model_id):
    """Resolve one detached validated reference, without constructing geometry.

    Optional resolution deliberately does not retain another selected model.
    The store validates the pack; its row keeps category='radiator'.
    """
    if not _valid_id(model_id):
        return {}
    from liquid_cooling_catalog044 import IDS, get_radiator
    if model_id in IDS:
        row = get_radiator(model_id)
    else:
        from hardware_packs import runtime_store
        model = runtime_store().get_model('radiator', model_id, retain=False)
        row = model.get('reference') if isinstance(model, dict) else None
    return row if _valid_row(row) and row['id'] == model_id else {}


class _MeshSink:
    """The radiator's small value-builder contract, without assembly_cooling.

    Transform order, color conversion, grouping and emitted Mesh fields match
    _Builder.put/finish. Only the caller's existing eco radiator is accepted.
    """
    level = 'eco'

    def __init__(self, cancel=None):
        self.static = {}
        self.cancel = cancel
        self.float_count = 0

    def put(self, name, vertices, tint, center, basis, component, part):
        checkpoint(self.cancel)
        if not vertices:
            return
        if len(vertices) % 18 or self.float_count + len(vertices) > MAX_TRIANGLES * 18:
            raise ValueError('Radiator mesh exceeds its existing eco budget')
        key = (name, tint, component, part)
        out = self.static.setdefault(key, [])
        for start in range(0, len(vertices), 6):
            for offset in (0, 3):
                p = vertices[start+offset:start+offset+3]
                q = tuple(sum(p[k]*basis[k][j] for k in range(3)) for j in range(3))
                out.extend(tuple(q[i]+center[i] for i in range(3)) if offset == 0 else q)
        self.float_count += len(vertices)

    def finish(self):
        from assembly_geometry import Mesh, color
        return tuple(Mesh(name, tuple(vertices),
                          tint if isinstance(tint, tuple) and len(tint) == 4 else color(tint),
                          component=component, part_id=part)
                     for (name, tint, component, part), vertices in self.static.items())


def _geometry(row, cancel=None):
    from assembly_radiator044 import build_radiator_detail
    # This adapter is local to construction. The detached catalog row retains
    # its validated category and is never reinterpreted as a loop component.
    profile = dict(row, part_kind='radiator')
    sink = _MeshSink(cancel)
    physical = build_radiator_detail(sink, profile['dimensions_mm'], (0., 0., 0.),
                                    _IDENTITY, 'radiator:'+profile['id'], profile)
    checkpoint(cancel)
    return sink.finish(), physical


def art_from_reference(row, style='miniature', cancel=None):
    """Build/project one already validated row; no store or model cache here."""
    if not _valid_row(row) or type(style) is not str or style not in STYLES:
        return {}
    checkpoint(cancel)
    try:
        meshes, physical = _geometry(row, cancel)
    except ValueError:
        return {}
    from liquid_svg046 import project_meshes
    projected = project_meshes(meshes, style, cancel, max_triangles=MAX_TRIANGLES,
                               view_direction=(.56, .35, .75))
    if not projected:
        return {}
    body = projected['svg']
    # The geometry builder preserves explicit ports/unknowns and describes
    # sampling. No fan is added merely because a profile has mounting capacity.
    details = dict(geometry_source='assembly_radiator044.build_radiator_detail',
                   detail_level='eco', part_kind='radiator', shell_family=row.get('shell_family'),
                   **projected['art_details'], dimensions_mm=deepcopy(row['dimensions_mm']),
                   dimensions_verified=row.get('dimensions_verified') is True,
                   dimensions_basis=row.get('dimensions_basis'),
                   shell_geometry_verified=row.get('shell_geometry_verified') is True,
                   geometry_accuracy=row.get('geometry_accuracy'),
                   palette_accuracy=row.get('palette_accuracy'),
                   radiator=physical['metadata'], ports=physical['ports'],
                   fan_faces=physical['fan_faces'], mount_holes=physical['mount_holes'],
                   coordinates_verified=False, physical_shape_shared_across_styles=True,
                   telemetry_bound=False, reference_camera=True,
                   reference_camera_side='front_positive_z',
                   reference_view_direction=(.56, .35, .75),
                   installed_hardware_inferred=False, fan_count_is_installed=False,
                   new_fans=0, new_rotors=0)
    return dict(id=row['id'], kind='radiator', label=row['label'], brand=row['brand'], style=style,
                svg=body, body_svg=body, foreground_svg='', rotors=[], reference_details=True,
                sources=deepcopy(row['sources']), fidelity='actual_mesh_projection_reference',
                motion_source='static_reference_mesh', rotation_direction_verified=False,
                original_face='none',
                reference_notes='The existing eco radiator mesh, with sampled fins/tubes and reference wall gauges. '
                                'Mount and port coordinates remain reference where unverified. '
                                'Fan counts are capacity, not installed fans. No live flow, water temperature or RPM.',
                art_details=details)


def art(model_id, style='miniature'):
    if not _valid_id(model_id) or type(style) is not str or style not in STYLES:
        return {}
    row = reference(model_id)
    return art_from_reference(row, style) if row else {}
