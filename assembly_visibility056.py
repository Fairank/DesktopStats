"""Bounded exact-part view masks tied to one physical assembly selection.

No geometry, hardware, files, clocks or GUI objects live here. A hidden part is
only omitted from inspection; this record never describes mechanical removal.
"""
import hashlib
import json
import re

MAX_HIDDEN_PARTS = 64
_SIGNATURE = re.compile(r'[0-9a-f]{64}')
_PART = re.compile(r'(?:case|gpu|cpu|memory|board|cooler|fans|case-fan|radiator-fan|psu|storage|expansion|cables)(?::[a-z0-9][a-z0-9-]{0,63}){1,3}')
_MODELS = ('case_model', 'cpu_model', 'gpu_model', 'board_model', 'memory_models',
    'cooler_model', 'cooler_mount', 'case_fans', 'psu_model', 'storage',
    'expansion_cards', 'cables_enabled', 'gpu_waterblock', 'radiator_model',
    'radiator_fan_model', 'radiator_fan_layout', 'secondary_radiator_model',
    'secondary_radiator_fan_model', 'secondary_radiator_fan_layout',
    'loop_components_mode', 'cpu_block_model', 'pump_model', 'pump_top_model',
    'reservoir_model', 'pump_reservoir_model', 'fitting_model', 'tubing_model',
    'loop_fittings')


def validate_visibility(value=None):
    """Return a detached canonical record; reject family masks and poses."""
    if value is None:
        value = {}
    if type(value) is not dict or set(value) - {'signature', 'hidden_parts'}:
        raise ValueError('部件显示设置格式不正确')
    signature = value.get('signature', '')
    parts = value.get('hidden_parts', [])
    if (type(signature) is not str or signature and not _SIGNATURE.fullmatch(signature)
            or type(parts) is not list or len(parts) > MAX_HIDDEN_PARTS):
        raise ValueError('部件显示设置格式不正确')
    if any(type(part) is not str or len(part) > 160 or not _PART.fullmatch(part) for part in parts):
        raise ValueError('请使用精确部件标识保存显示状态')
    if len(set(parts)) != len(parts) or parts and not signature:
        raise ValueError('部件显示设置与主机方案不匹配')
    return dict(signature=signature, hidden_parts=sorted(parts))


def _text(value):
    if type(value) is not str or len(value) > 256:
        raise ValueError('Bounded identity text required')
    return value


def _identity(row, *, detected=False):
    if type(row) is not dict:
        raise ValueError('Detached component identity required')
    appearance = row.get('appearance', {})
    if type(appearance) is not dict:
        raise ValueError('Detached appearance identity required')
    # Unknown/generic drawings can share an ID; retain the actual identity text.
    # For explicitly selected references, host detected labels are irrelevant.
    reference = row.get('telemetry_bound') is False
    # ``style`` is the resolved physical shape (e.g. DIMM versus SO-DIMM),
    # including unknown-part form-factor overrides in build_spec. Six artwork
    # palettes use ``icon_set`` / ``appearance_style`` instead and stay excluded.
    return [_text(appearance.get('id', '')), _text(appearance.get('style', '')),
            _text(row.get('label', '')),
            _text(row.get('detected_label', '')) if detected and not reference else '']


def selection_signature(spec):
    """Hash physical identities/mount choices, never artwork or moving values.

    The caller supplies the already built detached spec. Incomplete input has
    no usable signature; this helper never fills it by probing the machine.
    """
    try:
        if type(spec) is not dict:
            return ''
        options = spec['options']
        if type(options) is not dict or any(key not in options for key in _MODELS):
            return ''
        case, board, memory, gpu = (spec[key] for key in ('case', 'board', 'memory', 'gpu'))
        if any(type(row) is not dict for row in (case, board, memory, gpu)):
            return ''
        modules = memory.get('modules', [])
        if type(modules) is not list or len(modules) > 8:
            return ''
        count = memory.get('count', 0)
        generation = spec.get('model_library_generation', 0)
        if type(count) is not int or not 0 <= count <= 128 or type(generation) is not int or generation < 0:
            return ''
        physical = dict(version=1, library_generation=generation,
            choices={key:options[key] for key in _MODELS},
            case=[_text(case.get('id', ''))],
            cpu=_identity(spec['cpu'], detected=True),
            gpu=[*_identity(gpu, detected=True), _text(gpu.get('target', '0')), gpu.get('present') is True],
            memory=dict(count=count, modules=[_identity(row) for row in modules]),
            board=[_text(board.get('model_id', '')), _text(board.get('label', '')),
                   _text(board.get('manufacturer', '')), _text(board.get('form_factor', ''))])
        # Config is normalized before a spec is built. JSON additionally rejects
        # nonfinite/custom values instead of deriving a partial identity.
        raw = json.dumps(physical, sort_keys=True, separators=(',', ':'),
                         ensure_ascii=True, allow_nan=False).encode('ascii')
        if len(raw) > 32768:
            return ''
        return hashlib.sha256(raw).hexdigest()
    except (KeyError, TypeError, ValueError):
        return ''


def selected_hidden(options, spec, exact_known_ids):
    """Apply the complete mask only to its original selection and live IDs.

    An absent LOD part or stale model never broadens to a component family.
    Temporary blockers and manual reference windows must not be passed here.
    """
    try:
        if type(options) is not dict or not isinstance(exact_known_ids, (tuple, list, set, frozenset)):
            return ()
        record = validate_visibility(options.get('part_visibility'))
        signature = selection_signature(spec)
        if not signature or record['signature'] != signature:
            return ()
        known = set(exact_known_ids)
        if any(part not in known for part in record['hidden_parts']):
            return ()
        return tuple(record['hidden_parts'])
    except (TypeError, ValueError):
        return ()
