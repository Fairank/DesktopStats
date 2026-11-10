"""Lazy exact CPU and memory references for the manual 2-D gallery.

Only the three bundled CPUs and actually installed CPU packs are listed.
Memory rows keep their complete kit, capacity and colour identities. This
module does not discover hardware, generate artwork or import authoring data.
"""
from copy import deepcopy
import re


_ID = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z', re.ASCII)
_FIDELITY = 'two_dimensional_reference'


def choices(kind):
    """Copy the light index only; do not resolve any selected appearance."""
    if kind == 'cpu':
        from hardware_appearance import BRANDS, CATALOG
        from cpu_package_runtime import reference_choices
        base = [dict(id=r[0], label=r[4], brand=BRANDS[r[2]][0],
                     fidelity=_FIDELITY) for r in CATALOG if r[1] == 'cpu']
        return base + [dict(id=r['id'], label=r['label'], brand=r['brand'],
                            fidelity=_FIDELITY) for r in reference_choices()]
    if kind == 'memory':
        from memory_appearance import BRANDS, CATALOG
        return [dict(id=r['id'], label=r['label'], brand=BRANDS[r['brand']][0],
                     fidelity=_FIDELITY) for r in CATALOG]
    return []


def _cpu_reference(model_id):
    from hardware_appearance import BRANDS, CATALOG, appearance_for
    row = next((r for r in CATALOG if r[1] == 'cpu' and r[0] == model_id), None)
    if row:
        return appearance_for('cpu', row[-1][0]), row[4], BRANDS[row[2]][0], row[8]
    # A selected installed row is read by exact ID. Do not match a short CPU
    # alias or retain another optional payload in the shared selected cache.
    from cpu_package_runtime import reference_choices
    summary = next((r for r in reference_choices() if r['id'] == model_id), None)
    if summary is None:
        return None
    from hardware_packs import runtime_store
    model = runtime_store().get_model('cpu', model_id, retain=False)
    if (not isinstance(model, dict) or model.get('id') != model_id
            or model.get('label') != summary['label']
            or model.get('vendor') not in ('amd', 'intel')
            or BRANDS[model['vendor']][0] != summary['brand']):
        return None
    package = model.get('cpu_package')
    if (not isinstance(package, dict) or package.get('model_id') != model_id
            or package.get('vendor') != model['vendor']):
        return None
    # These are the same validated package/style fields consumed by the
    # existing CPU renderer, with no inference from the user's processor.
    family = package.get('id')
    style = ('am5' if family == 'amd_am5' else 'chip'
             if family in ('intel_lga115x_1200', 'amd_am4') else 'lga_rect')
    vendor = model['vendor']
    sources = model.get('sources')
    if not isinstance(sources, list) or not sources or not isinstance(sources[0], str):
        return None
    appearance = dict(id=model_id, kind='cpu', vendor=vendor, board_vendor='unknown',
                      label=model['label'], style=style, fan_count=None,
                      visible_fan_count=None, shroud='neutral', source_url=sources[0],
                      confidence='model', accent=BRANDS[vendor][1],
                      series_id=model.get('series', ''), series_label=model.get('series', ''),
                      features=[], legacy=False, extension_pack=True,
                      cpu_package=deepcopy(package))
    return appearance, model['label'], summary['brand'], sources[0]


def reference(kind, model_id):
    """Resolve just one exact existing reference, detached from telemetry."""
    if (kind not in ('cpu', 'memory') or not isinstance(model_id, str)
            or len(model_id) > 64 or not _ID.fullmatch(model_id)):
        return {}
    if kind == 'cpu':
        result = _cpu_reference(model_id)
        if result is None:
            return {}
        appearance, label, brand, source = result
        package = appearance.get('cpu_package')
        if not isinstance(package, dict) or package.get('model_id') != model_id:
            return {}
    else:
        from memory_appearance import BRANDS, CATALOG, appearance_for_memory
        row = next((r for r in CATALOG if r['id'] == model_id), None)
        if row is None:
            return {}
        appearance = appearance_for_memory(model=row['aliases'][0])
        label, brand, source = row['label'], BRANDS[row['brand']][0], row['source_url']
    if (appearance.get('id') != model_id or appearance.get('kind') != kind
            or appearance.get('confidence') != 'model'):
        return {}
    return deepcopy(dict(id=model_id, label=label, brand=brand, appearance=appearance,
                         source_url=source, fidelity=_FIDELITY,
                         reference_only=True, telemetry_bound=False,
                         installed_model_verified=False, mechanical_fit_verified=False))
