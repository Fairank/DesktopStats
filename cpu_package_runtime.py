"""Three preserved base CPUs plus explicitly installed data packs.

The broad authoring catalog is deliberately not imported by the app. Small
package descriptors use shared code-native shapes; no SKU retains a mesh.
"""
from copy import deepcopy
from functools import lru_cache
import re

_BASE = {
    'intel-13700kf': ('intel_lga1700_1851', 'LGA1700', 37.5, 45., 'intel_rectangle', 'lga', 1700, 'INTEL 13700KF',
        'https://www.intel.com/content/www/us/en/products/sku/230489/intel-core-i713700kf-processor-30m-cache-up-to-5-40-ghz/specifications.html'),
    'amd-9950x': ('amd_am5', 'AM5', 40., 40., 'amd_am5_notched', 'lga', 1718, 'AMD 9950X',
        'https://www.amd.com/en/products/processors/desktops/ryzen/9000-series/amd-ryzen-9-9950x.html'),
    'amd-7800x3d': ('amd_am5', 'AM5', 40., 40., 'amd_am5_notched', 'lga', 1718, 'AMD 7800X3D',
        'https://www.amd.com/en/products/processors/desktops/ryzen/7000-series/amd-ryzen-7-7800X3d.html'),
}


def get_package(model_id):
    row = _BASE.get(model_id) if isinstance(model_id, str) else None
    if row:
        family, socket, width, length, ihs, contacts, pins, label, url = row
        return dict(id=family, model_id=model_id, vendor='intel' if family.startswith('intel_') else 'amd', socket=socket, width_mm=width, length_mm=length,
                    substrate_mm=None, ihs_kind=ihs, contacts=contacts, pin_count=pins,
                    notch_profile=ihs, label_ascii=label, status='reviewed', dimensions_status='primary_verified',
                    topology_status='interface_verified',source_urls=[url]+(['https://www.intel.com/content/www/us/en/support/articles/000005670/processors.html'] if family.startswith('intel_') else
                        ['https://www.amd.com/en/newsroom/press-releases/2023-11-14-amd-expands-ryzen-embedded-processor-family-for-h.html',
                         'https://www.amd.com/content/dam/amd/en/documents/partner-hub/ryzen/amd-socket-am5-quick-reference-guide.pdf']),
                    topology_map_verified=False, internal_layout_verified=False, cooler_inferred=False,
                    )
    from hardware_packs import runtime_store
    model = runtime_store().get_cpu(model_id)
    return deepcopy(model['cpu_package']) if model else None


def _normal(value):
    value = re.sub(r'\((?:r|tm)\)|[®™]', ' ', value.casefold())
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', value).split())


@lru_cache(maxsize=128)
def _match_identity(name, model, board, store, generation):
    """Resolve reviewed complete aliases; do not derive packages from a socket name."""
    text = _normal(model or name)
    supplied = _normal(name + ' ' + model)
    if re.search(r'\b(?:mobile|laptop|notebook|engineering sample|es sample)\b', supplied):
        return None
    vendors = {vendor for vendor, tokens in (('intel', ('intel', 'genuineintel')), ('amd', ('amd', 'ryzen', 'threadripper')))
               if any(' ' + token + ' ' in ' ' + supplied + ' ' for token in tokens)}
    if len(vendors) > 1:
        return None
    matches = [row for row in store.choices() if (not vendors or row['vendor'] in vendors)
               and any(' ' + _normal(alias) + ' ' in ' ' + text + ' ' for alias in row['aliases'])]
    # Never choose a short alias arbitrarily if a provider string contains
    # several products. The imported record controls drawing only, not sensors.
    return matches[0]['id'] if len(matches) == 1 else None


def match_model(name, model='', board=''):
    from hardware_packs import runtime_store
    store=runtime_store(); store._ensure()
    identity=_match_identity(name, model, board, store, store.generation)
    return store.get_cpu(identity) if identity else None


def reference_rows():
    from hardware_packs import runtime_store
    return tuple((row['id'], 'cpu', row['vendor'], 'unknown', row['label'],
                  'chip', None, 'neutral', '', tuple(row['aliases']))
                 for row in runtime_store().choices())


def reference_choices():
    from hardware_packs import runtime_store
    return [dict(id=row['id'], label=row['label'], brand={'intel': 'Intel', 'amd': 'AMD'}[row['vendor']],
                 series_id=row['series'], series_label=row['series'], pack_id=row['pack_id'])
            for row in runtime_store().choices()]
