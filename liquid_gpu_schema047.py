"""Closed retail-GPU-block reference contract; no catalogue, matching inference or I/O.

These records support independent inspection only. A listed retail card does not
provide chip/memory-pad/mounting coordinates or an installed loop pose.
"""
from copy import deepcopy
import re
from cooling_pack_schema045 import _keys,_id,_text,_urls,_number,_fail

GPU_FAMILIES=frozenset(('gpu_core_clear','gpu_carbon_server','gpu_aurora_clear','gpu_heatkiller_window','gpu_xg7_ribbed'))
RECIPES=frozenset(('core_astral5090','es5090_carbon','core4090_fe','aurora7900_reference',
    'core9070_asus','core9070_xfx','core5090_msi','core5090_tuf','heatkiller5090_tuf','heatkiller4090_fe',
    'xg7_4090_strix_tuf','xg7_3080_fe'))
FEATURES=frozenset(('clear_cover','passive_backplate','core_emblem_plate','long_edge_argb','window_argb','opaque_carbon_cover',
    'end_pair_terminal','transparent_terminal','metal_window_fascia','ribbed_side_fascia','separate_terminal',
    'reference_channel_layout','optional_sideport_terminal','replacement_slot_bracket','visible_cover_standoffs',
    'right_blank_metal_land','stepped_coldplate_shoulder','carbon_edge_notch','short_end_port_necks','rounded_terminal_fascia'))
FIELDS=('id','label','brand','series','part_kind','form','dimensions_mm','reference_envelope_mm',
    'dimensions_verified','axis_verified','sources','notes','ports_count','ports','ports_geometry_complete',
    'geometry_family','geometry_features','source_authority','photo_reviewed','geometry_accuracy',
    'port_positions_verified','body_color','accent_color','observed_lighting','dimensions_scope',
    'geometry_features_basis','selection_source','reviewed','live_temperature_available','live_flow_available',
    'live_rpm_available','installed_hardware_inferred','product_id','gpu_vendor','gpu_compatibility',
    'terminal_configurations','default_terminal_configuration','backplate','published_envelopes','lighting',
    'assembly_stage','geometry_recipe','exterior_observations','materials')

def _flag(value):
    if type(value) is not bool:_fail('GPU block flag must be boolean')

def _dims(value,reference=False):
    _keys(value,('width','height','depth'))
    for v in value.values():_number(v,1,800,nullable=not reference)

def _texts(values,maximum=24,limit=160):
    if type(values) is not list or len(values)>maximum:_fail('GPU text inventory exceeds limit')
    for v in values:_text(v,limit)

def _compatibility(value):
    _keys(value,('policy','entries','exclusions','chip_name_sufficient','assembly_pose_verified','global_pcb_revision'))
    if value['policy']!='exact_model_and_required_revision' or value['chip_name_sufficient'] is not False or value['assembly_pose_verified'] is not False:_fail('Unsupported GPU compatibility inference')
    if value['global_pcb_revision'] is not None:_text(value['global_pcb_revision'],120)
    if type(value['entries']) is not list or not 1<=len(value['entries'])<=24:_fail('GPU card whitelist missing or too large')
    for c in value['entries']:
        _keys(c,('card_label','product_code','pcb_revision','state','code_precision'))
        _text(c['card_label'],240)
        for key in ('product_code','pcb_revision'):
            if c[key] is not None:_text(c[key],120)
        if c['state'] not in ('listed','requires_revision_confirmation','held_source_conflict'):_fail('Unknown GPU compatibility state')
        if c['code_precision'] not in ('complete','publisher_abbreviated','not_published'):_fail('Unknown card-code precision')
        if c['code_precision']=='not_published' and c['product_code'] is not None:_fail('Unpublished GPU code is not empty')
    if type(value['exclusions']) is not list or len(value['exclusions'])>16:_fail('GPU exclusion inventory exceeds limit')
    for c in value['exclusions']:
        _keys(c,('pcb_revision','card_label','reason'))
        for key in ('pcb_revision','card_label'):
            if c[key] is not None:_text(c[key],240)
        _text(c['reason'],512)

def _terminal(config,row):
    from liquid_pack_schema046 import _port
    _keys(config,('id','label','ports_count','ports','hydraulic_groups','hydraulic_pairing_verified',
        'reference_envelope_mm','published_envelope_mm','dimensions_scope','geometry_reference','sources'))
    _id(config['id']);_text(config['label'],160);_urls(config['sources'])
    _number(config['ports_count'],0,12,integer=True,nullable=True)
    if type(config['ports']) is not list or len(config['ports'])>12:_fail('GPU terminal ports exceed limit')
    for p in config['ports']:_port(p)
    ids={p['id'] for p in config['ports']}
    if len(ids)!=len(config['ports']) or config['ports_count'] is not None and len(ids)>config['ports_count']:_fail('GPU terminal port inventory mismatch')
    _flag(config['hydraulic_pairing_verified'])
    if type(config['hydraulic_groups']) is not list or len(config['hydraulic_groups'])>6:_fail('GPU hydraulic groups exceed limit')
    used=[]
    for group in config['hydraulic_groups']:
        _keys(group,('id','ports'));_id(group['id']);_texts(group['ports'],6,64)
        if not group['ports'] or not set(group['ports'])<=ids:_fail('Hydraulic group refers to an absent terminal socket')
        used.extend(group['ports'])
    if len(set(used))!=len(used):_fail('Terminal socket belongs to multiple hydraulic groups')
    if config['hydraulic_pairing_verified'] and (len(config['hydraulic_groups'])<2 or set(used)!=ids):_fail('Verified GPU hydraulic groups incomplete')
    if not config['hydraulic_pairing_verified'] and config['hydraulic_groups']:_fail('Unverified hydraulic groups cannot guide routing')
    _dims(config['reference_envelope_mm'],True);_dims(config['published_envelope_mm'])
    if config['dimensions_scope'] not in ('published_complete','publisher_unspecified','reference_only'):_fail('Unknown GPU terminal envelope scope')
    g=config['geometry_reference'];_keys(g,('layout','center_uv','span_uv','positions_verified'))
    if g['layout'] not in ('long_edge','short_end','sideport') or g['positions_verified'] is not False:_fail('Invalid GPU terminal reference layout')
    for key,lo,hi in (('center_uv',-.5,.5),('span_uv',.04,1.)):
        if type(g[key]) is not list or len(g[key])!=2:_fail('Invalid terminal reference proportions')
        for v in g[key]:_number(v,lo,hi)

def validate_reference(row):
    from liquid_pack_schema046 import _port
    _keys(row,FIELDS)
    for key in ('id',):_id(row[key])
    for key,limit in (('label',240),('brand',120),('series',120),('product_id',120)):_text(row[key],limit)
    for key in ('geometry_family','geometry_recipe','reviewed'):_text(row[key],120)
    if row['part_kind']!='gpu_block' or row['form']!='gpu_block' or row['geometry_family'] not in GPU_FAMILIES or row['geometry_recipe'] not in RECIPES:_fail('Unsupported GPU block generator')
    if row['gpu_vendor'] not in ('NVIDIA','AMD','Intel'):_fail('Unknown GPU vendor')
    if row['assembly_stage']!='standalone_reference_only':_fail('GPU installation pose is not supported')
    _dims(row['dimensions_mm']);_dims(row['reference_envelope_mm'],True)
    _keys(row['axis_verified'],('width','height','depth'));_flag(row['dimensions_verified'])
    for axis,value in row['axis_verified'].items():
        _flag(value)
        if value and row['dimensions_mm'][axis] is None:_fail('Verified GPU dimension missing')
    if row['dimensions_verified'] and not all(row['axis_verified'].values()):_fail('Partial GPU envelope cannot be fully verified')
    _urls(row['sources']);_texts(row['notes'],8,2048);_texts(row['geometry_features'])
    _texts(row['exterior_observations'],12,512)
    _keys(row['materials'],('cold_plate','top','terminal','connection_threads','fascia','backplate'))
    for value in row['materials'].values():
        if value is not None:_text(value,160)
    if not set(row['geometry_features'])<=FEATURES:_fail('Unknown GPU block geometry feature')
    if row['source_authority']!='manufacturer' or row['photo_reviewed'] is not True:_fail('GPU block requires reviewed primary sources')
    if row['geometry_accuracy']!='original_reference_not_CAD' or row['geometry_features_basis']!='manufacturer_photo_and_manual_observation':_fail('Unsupported GPU geometry precision')
    if row['selection_source']!='manual' or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',row['reviewed']):_fail('GPU blocks require explicit manual selection')
    for flag in ('port_positions_verified','live_temperature_available','live_flow_available','live_rpm_available','installed_hardware_inferred'):
        if row[flag] is not False:_fail('Unsupported GPU block telemetry/position inference')
    for key in ('body_color','accent_color'):
        if type(row[key]) is not str or not re.fullmatch('#[0-9a-fA-F]{6}',row[key]):_fail('Invalid GPU color')
    _texts(row['observed_lighting'])
    if row['dimensions_scope'] not in ('overall','publisher_unspecified','unknown'):_fail('Unknown GPU block dimension scope')
    _compatibility(row['gpu_compatibility'])
    if type(row['terminal_configurations']) is not list or not 1<=len(row['terminal_configurations'])<=4:_fail('GPU terminal configurations missing')
    for t in row['terminal_configurations']:_terminal(t,row)
    configs={t['id']:t for t in row['terminal_configurations']}
    if len(configs)!=len(row['terminal_configurations']) or row['default_terminal_configuration'] not in configs:_fail('GPU terminal identity mismatch')
    default=configs[row['default_terminal_configuration']]
    if row['ports_count']!=default['ports_count'] or row['ports']!=default['ports']:_fail('GPU default ports differ from terminal configuration')
    _flag(row['ports_geometry_complete'])
    if row['ports_geometry_complete'] and (row['ports_count'] is None or len(row['ports'])!=row['ports_count']):_fail('Incomplete GPU socket observation')
    back=row['backplate'];_keys(back,('included','cooling','dimensions_mm','plate_thickness_mm','material','source'))
    if back['included'] is not True or back['cooling']!='passive':_fail('Only observed included passive GPU backplates are supported')
    _dims(back['dimensions_mm']);_number(back['plate_thickness_mm'],.3,20,nullable=True)
    if back['material'] is not None:_text(back['material'],120)
    _urls([back['source']])
    if type(row['published_envelopes']) is not list or not 1<=len(row['published_envelopes'])<=6:_fail('GPU published-envelope inventory invalid')
    for envelope in row['published_envelopes']:
        _keys(envelope,('scope','dimensions_mm','includes_terminal','includes_backplate','source'))
        if envelope['scope'] not in ('cooler_table','backplate','complete_standard','complete_sideport'):_fail('Unknown GPU publisher envelope')
        _dims(envelope['dimensions_mm']);_urls([envelope['source']])
        for key in ('includes_terminal','includes_backplate'):
            if envelope[key] is not None:_flag(envelope[key])
    light=row['lighting'];_keys(light,('present','type','led_count','voltage_v','connector','regions'))
    if light['present'] is not None:_flag(light['present'])
    if light['type'] not in ('digital_argb','rgb_adapter','not_evidenced'):_fail('Unknown GPU light type')
    _number(light['led_count'],0,128,integer=True,nullable=True);_number(light['voltage_v'],0,24,nullable=True)
    if light['connector'] is not None:_text(light['connector'],240)
    _texts(light['regions'])
    if light['present'] is not True and (light['led_count'] is not None or light['regions']):_fail('Unknown GPU lighting cannot gain invented regions')
    return deepcopy(row)

def _normalize(value):return re.sub(r'\s+',' ',str(value or '').replace('™','').replace('®','')).strip().casefold()

def compatibility(row,*,card_label=None,product_code=None,pcb_revision=None):
    """Strict evidence lookup only. Never a mounting/loop-compatibility verdict."""
    if row.get('part_kind')!='gpu_block':return dict(state='unknown',assembly_supported=False)
    facts=row['gpu_compatibility'];label,code,revision=map(_normalize,(card_label,product_code,pcb_revision))
    def answer(state,entry=None):return dict(state=state,entry=deepcopy(entry),assembly_supported=False,
        installed_hardware_inferred=False,reason='standalone_reference_only_missing_verified_gpu_mounting_pose')
    for excluded in facts['exclusions']:
        if excluded['pcb_revision'] and revision==_normalize(excluded['pcb_revision']):return answer('excluded')
        if excluded['card_label'] and label==_normalize(excluded['card_label']):return answer('excluded')
    candidates=[]
    for c in facts['entries']:
        label_matches=bool(label and label==_normalize(c['card_label']))
        code_matches=bool(code and c['code_precision']=='complete' and code==_normalize(c['product_code']))
        if label and code:
            # Contradictory precise identifiers must not win via a loose OR.
            if label_matches and code_matches:candidates.append(c)
        elif label_matches or code_matches:candidates.append(c)
    if not candidates:return answer('unlisted' if label or code else 'unknown')
    if revision:
        exact=[c for c in candidates if c['pcb_revision'] and revision==_normalize(c['pcb_revision'])]
        if exact:candidates=exact
        elif any(c['pcb_revision'] for c in candidates):return answer('unlisted_revision')
    selected=candidates[0]
    if selected['state']=='held_source_conflict':return answer('source_conflict',selected)
    required=selected['pcb_revision'] or facts['global_pcb_revision']
    if required and not revision:return answer('revision_confirmation_required',selected)
    if required and revision!=_normalize(required):return answer('unlisted_revision',selected)
    if selected['state']=='requires_revision_confirmation' and not facts['global_pcb_revision']:return answer('revision_confirmation_required',selected)
    return answer('manufacturer_listed',selected)

def port_pair_status(row,first,second,terminal='standard'):
    """A same hydraulic column must never become a false inlet/outlet pair."""
    if not all(type(v) is str for v in (first,second,terminal)):return 'invalid_pair'
    config=next((t for t in row['terminal_configurations'] if t['id']==terminal),None)
    if not config or first==second:return 'invalid_pair'
    ids={p['id'] for p in config['ports']}
    if first not in ids or second not in ids:return 'unknown_port'
    if not config['hydraulic_pairing_verified']:return 'hydraulic_groups_unverified'
    a=next((g['id'] for g in config['hydraulic_groups'] if first in g['ports']),None)
    b=next((g['id'] for g in config['hydraulic_groups'] if second in g['ports']),None)
    return 'same_hydraulic_column_forbidden' if a==b else 'different_verified_columns_reference_only'
