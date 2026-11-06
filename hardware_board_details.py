"""Bounded offline exterior facts; sockets and PCB interiors are separate facts.

No probing, driver access, network or polling. Unknowns are retained. A family
name, ASIC identity or a different retail revision cannot borrow these sockets.
"""
import copy

import hardware_board_details_a as group_a
import hardware_board_details_b as group_b
import hardware_board_details_c as group_c
from hardware_variants import READY, exterior_row

PACKAGES = (group_a, group_b, group_c)
PROFILES = {}
MEMORY_PROFILES = {}
for package in PACKAGES:
    for target, source in ((PROFILES, getattr(package, 'PROFILES', {})),
                           (MEMORY_PROFILES, getattr(package, 'MEMORY_PROFILES', {}))):
        if target.keys() & source.keys():
            raise ValueError('Duplicate board exterior identity')
        target.update(source)

PORT_TYPES = {
    'dp': 'displayport', 'displayport': 'displayport', 'display_port': 'displayport',
    'mini_dp': 'mini_displayport', 'minidp': 'mini_displayport', 'mini_displayport': 'mini_displayport',
    'hdmi': 'hdmi', 'mini_hdmi': 'mini_hdmi', 'minihdmi': 'mini_hdmi',
    'dvi': 'dvi', 'dvi_i': 'dvi', 'dvi_d': 'dvi', 'dvi-i': 'dvi', 'dvi-d': 'dvi', 'vga': 'vga', 'd_sub': 'vga',
    'usb_c': 'usb_c', 'usb-c': 'usb_c', 'usbc': 'usb_c', 'tv_out': 'tv_out',
    'tv-out': 'tv_out', 's_video': 'tv_out', 'svideo': 'tv_out',
}
POWER_TYPES = {name: name for name in ('4pin', '6pin', '8pin', '12pin', '16pin')}
LABELS = dict(displayport='DP', mini_displayport='Mini DP', hdmi='HDMI', mini_hdmi='Mini HDMI',
              dvi='DVI', vga='VGA', usb_c='USB-C', tv_out='TV-Out',
              **{'4pin': '4 pin', '6pin': '6 pin', '8pin': '8 pin', '12pin': '12 pin', '16pin': '16 pin'})
TONES = ('dark', 'light', 'silver', 'blue', 'pink', 'mixed', 'unknown')
MEMORY_KEYS = {
    # Nominal front-view PCB mechanical drawings, page 2; no SKU-wide
    # tolerance claim. Each dimension is relative to the PCB, not a cover.
    ('ddr4','dimm'):(72.25/133.35,'https://www.kingston.com/datasheets/KVR32N22S8_16.pdf',1.50/133.35,3.85/31.25),
    ('ddr5','dimm'):(68.10/133.35,'https://www.kingston.com/datasheets/KF564C32RSK2-32.pdf',1.50/133.35,3.85/31.25),
    ('ddr4','sodimm'):(38.30/69.60,'https://www.kingston.com/datasheets/KVR32S22S8_16.pdf',1.00/69.60,4.00/30.00),
}


def groups(value, allowed):
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) > 8:
        raise ValueError('Invalid exterior connector group')
    result = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError('Invalid exterior connector')
        name = str(item.get('type', '')).lower().replace(' ', '_')
        kind = allowed.get(name)
        count = item.get('count')
        if kind is None or type(count) is not int or not 1 <= count <= 6:
            raise ValueError('Invalid exterior connector type/count: ' + name)
        row = dict(type=kind, count=count)
        for field in ('standard', 'subtype', 'form'):
            if isinstance(item.get(field), str):
                row[field] = item[field][:40]
        if kind == 'dvi' and name in ('dvi-d', 'dvi_d', 'dvi-i', 'dvi_i'):
            row.setdefault('subtype', name.upper().replace('_', '-'))
        if 'subtypes' in item:
            subtypes = item['subtypes']
            if (kind != 'dvi' or not isinstance(subtypes, (tuple, list))
                    or len(subtypes) != count):
                raise ValueError('Invalid DVI subtype/count correspondence')
            amounts = {}
            for subtype in subtypes:
                if not isinstance(subtype, str):
                    raise ValueError('Invalid DVI subtype')
                subtype = subtype.upper().replace('_', '-')
                if subtype not in ('DVI-I', 'DVI-D'):
                    raise ValueError('Invalid DVI subtype')
                if ('subtype' in row
                        and row['subtype'].upper().replace('_', '-') != subtype):
                    raise ValueError('Conflicting DVI subtypes')
                amounts[subtype] = amounts.get(subtype, 0) + 1
            # A per-socket list is evidence of type/count, not bracket order.
            # Identical types share one group; mixed I/D retain separate counts.
            result.extend(dict(row, subtype=subtype, count=amount)
                          for subtype, amount in amounts.items())
            continue
        result.append(row)
    if sum(row['count'] for row in result) > 8:
        raise ValueError('Too many exterior connectors')
    return result


def label_groups(value, *, empty='', unknown='待核实'):
    if value is None:
        return unknown
    return ' · '.join((row.get('subtype') or LABELS[row['type']] if row['type'] == 'dvi' else LABELS[row['type']])
                      + ('（形态待核实）' if row.get('form') == 'unconfirmed' else '')
                      + ' × ' + str(row['count']) for row in value) or empty


def _number(value, maximum=500):
    return value if type(value) in (int, float) and 0 < value <= maximum else None


def normalise(series, row, *, kind='gpu'):
    result = dict(kind=kind, series_id=series, model_ids=tuple(row.get('model_ids', ())))
    if not result['model_ids']:
        raise ValueError('Exterior facts require exact model guards: ' + series)
    result['shroud_tone'] = row.get('shroud_tone', row.get('tone', 'unknown'))
    result['pcb_tone'] = row.get('pcb_tone') if row.get('pcb_tone') in ('blue','green','dark') else 'unknown'
    if result['shroud_tone'] not in TONES:
        result['shroud_tone'] = 'unknown'
    if kind == 'memory':
        for field in ('form', 'generation', 'pins', 'heat_spreader', 'diffuser'):
            result[field] = row.get(field)
        standard=MEMORY_KEYS.get((result['generation'],result['form']))
        result['notch_ratio']=standard[0] if standard else None
        result['notch_width_ratio']=standard[2] if standard else None
        result['notch_depth_ratio']=standard[3] if standard else None
        return result
    result.update(ports=groups(row.get('ports'), PORT_TYPES),
                  power_connectors=groups(row.get('power_connectors'), POWER_TYPES),
                  slot_width=_number(row.get('slot_width'), 5),
                  backplate=row.get('backplate') if type(row.get('backplate')) is bool else None,
                  pcb_length=row.get('pcb_length') if row.get('pcb_length') in ('short', 'full') else 'unknown')
    dimensions = row.get('dimensions_mm') or {}
    if isinstance(dimensions, (tuple, list)):
        dimensions = dict(zip(('length', 'height', 'thickness'), dimensions))
    result['dimensions_mm'] = {key: _number(dimensions.get(key)) for key in ('length', 'height', 'thickness')}
    host = row.get('host_interface') or {}
    bus = host.get('bus') if host.get('bus') in ('pcie', 'agp') else 'unknown'
    result['host_interface'] = dict(bus=bus,
                                    generation=_number(host.get('generation'), 8 if bus == 'agp' else 6),
                                    lanes=host.get('lanes') if type(host.get('lanes')) is int and host['lanes'] in (1, 2, 4, 8, 16) else None)
    result['edge_key_count'] = row.get('edge_key_count') if type(row.get('edge_key_count')) is int and 0 <= row['edge_key_count'] <= 2 else None
    result['power_position'] = row.get('power_position') if row.get('power_position') in ('top', 'end', 'rear', 'hidden', 'alternative') else 'unknown'
    result['recipe'] = row.get('recipe') if row.get('recipe') in ('suprim_blackwell',) else ''
    if isinstance(row.get('fan_profile'),dict):
        allowed=('blades','shape','hub_ratio','hub_tone','group_size','outer_ring','tone')
        result['fan_profile']={key:row['fan_profile'][key] for key in allowed if key in row['fan_profile']}
    layout = row.get('power_layout') or {}
    result['alternative_power'] = layout.get('mode') == 'alternative'
    if row.get('auxiliary_button')=='hyper_boost':
        result['auxiliary_button']='hyper_boost'
    return result


def for_appearance(appearance):
    if appearance.get('confidence') != 'model':
        return {}
    kind = appearance.get('kind')
    if kind not in ('gpu', 'memory'):
        return {}
    source = (PROFILES if kind == 'gpu' else MEMORY_PROFILES).get(appearance.get('series_id'), {})
    source = exterior_row(appearance.get('id'), source)
    if appearance.get('id') not in source.get('model_ids', ()):
        return {}
    result = normalise(appearance['series_id'], source, kind=kind)
    result['source_urls'] = [url for url in source.get('source_urls', ())
                             if isinstance(url, str) and url.startswith('https://')][:8]
    if kind=='memory':
        standard=MEMORY_KEYS.get((result.get('generation'),result.get('form')))
        if standard and standard[1] not in result['source_urls']:
            result['source_urls'].append(standard[1])
    if kind == 'gpu':
        result['ports_text'] = label_groups(result['ports'], unknown='视频接口待核实')
        result['power_text'] = label_groups(result['power_connectors'], empty='无需外接供电', unknown='供电接口待核实')
        result['pcb_text'] = ('短 PCB · ' if result['pcb_length']=='short' else '')+'PCB 内部布局未核实'
        host = result['host_interface']
        result['host_text'] = ('PCIe' if host['bus'] == 'pcie' else 'AGP' if host['bus'] == 'agp' else '主机接口待核实')
        if host['generation'] is not None:
            result['host_text'] += (str(host['generation']) + '×' if host['bus'] == 'agp'
                                    else ' ' + str(host['generation']))
        if host['lanes'] is not None:
            result['host_text'] += ' ×' + str(host['lanes'])
    return copy.deepcopy(result)


def version_families():
    return tuple(copy.deepcopy(row) for package in PACKAGES for row in getattr(package, 'VERSION_FAMILIES', ()))


def drawing_payload():
    result = {}
    for kind, source in (('gpu', PROFILES), ('memory', MEMORY_PROFILES)):
        for series, row in source.items():
            facts = normalise(series, row, kind=kind)
            for model in facts['model_ids']:
                if model in result:
                    raise ValueError('Duplicate exact exterior model')
                result[model] = {key: value for key, value in facts.items() if key != 'model_ids'}
    for model,version in READY.items():
        source=(PROFILES if version['kind']=='gpu' else MEMORY_PROFILES).get(version['series_id'],{})
        facts=normalise(version['series_id'],exterior_row(model,source),kind=version['kind'])
        result[model]={key:value for key,value in facts.items() if key!='model_ids'}
    return result
