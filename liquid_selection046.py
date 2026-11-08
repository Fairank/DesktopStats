"""Explicit loop identities and bounded compatibility; no inferred hardware."""
from copy import deepcopy
import re

MODEL_FIELDS={'cpu_block_model':'cpu_block','pump_model':'pump','pump_top_model':'pump',
    'reservoir_model':'reservoir','pump_reservoir_model':'pump_reservoir','fitting_model':'fitting','tubing_model':'tubing'}
SELECTION_FIELDS=('loop_components_mode',*MODEL_FIELDS,'loop_tubes_visible')

def _canon(value):return re.sub('[^A-Z0-9]','',str(value or '').upper()).removeprefix('SOCKET').removeprefix('FC')

def socket_state(block,spec):
    cpu=((spec.get('cpu') or {}).get('appearance') or {}).get('cpu_package') or {}
    actual=_canon(cpu.get('socket'))
    board=_canon(((spec.get('board') or {}).get('model_profile') or {}).get('socket'))
    if actual and board and actual!=board:return 'unsupported'
    expected=actual or board
    if not expected or not block.get('socket_support_verified'):return 'unknown'
    accepted={_canon(v) for v in block.get('supported_sockets',())}
    if 'LGA115X' in accepted:accepted.update(('LGA1150','LGA1151','LGA1155','LGA1156'))
    return 'nominal_match' if expected in accepted else 'unsupported'

def motor_matches(motor,housing):
    kind=motor.get('motor_type')
    supported=housing.get('compatible_pump_types') or []
    if not kind or not supported or not housing.get('pump_support_verified'):return 'unknown'
    return 'nominal_match' if _canon(kind) in {_canon(v) for v in supported} else 'unsupported'

def _material(value):
    value=_canon(value)
    return {'ACRYLIC':'PMMA','ACRYLICGLASS':'PMMA','PLEXI':'PMMA','POLYVINYLCHLORIDE':'PVC'}.get(value,value)

def tube_compatibility(fitting,tubing):
    """Nominal tube dimensions only. Thread size never stands for tube OD."""
    issues=[]
    if not fitting or not tubing:return ['missing_fitting_or_tubing']
    if not fitting.get('requires_tube') or fitting.get('form') in ('plug','drain','rotary_adapter','extension'):
        return ['fitting_is_not_a_tube_connector']
    if fitting.get('tube_type') not in ('soft','hard') or fitting['tube_type']!=tubing.get('tube_type'):
        issues.append('tube_type_mismatch')
    fields=('tube_inner_mm',) if fitting.get('form')=='barb' else ('tube_outer_mm',) if fitting.get('tube_type')=='hard' else ('tube_inner_mm','tube_outer_mm')
    for key in fields:
        a,b=fitting.get(key),tubing.get(key)
        if a is None or b is None:issues.append('tube_dimensions_unknown')
        elif abs(a-b)>.06:issues.append('tube_diameter_mismatch')
    if not tubing.get('tube_outer_mm'):issues.append('tube_dimensions_unknown')
    materials=fitting.get('compatible_materials') or []
    if materials and _material(tubing.get('material')) not in {_material(v) for v in materials}:
        issues.append('tube_material_requires_review')
    return list(dict.fromkeys(issues))

def service_ports(row):
    # Never attach circulation tubes to fill/drain/auxiliary openings merely
    # because they appear earlier in a product's source list.
    return [p for p in row.get('ports',()) if p['role'] in ('inlet','outlet','connection')]

def choose_service_pair(row):
    ports=service_ports(row)
    ins=[p for p in ports if p['role']=='inlet'];outs=[p for p in ports if p['role']=='outlet']
    if ins and outs:return ins[0],outs[0]
    generic=[p for p in ports if p['role']=='connection']
    return tuple(generic[:2]) if len(generic)>=2 else ()

def fitting_ends(row):
    thread=[p for p in service_ports(row) if p['thread'] and p['thread_gender']=='male']
    tube=[p for p in service_ports(row) if p.get('tube_type') in ('soft','hard') and p['thread'] is None and p['thread_gender']=='none']
    return (thread[0],tube[0]) if len(thread)==1 and len(tube)==1 else ()

def port_compatibility(port,fitting):
    ends=fitting_ends(fitting)
    if not ends:return 'fitting_ends_unknown'
    male=ends[0]
    if port.get('thread_gender')=='unknown' or port.get('thread') is None:return 'port_thread_or_gender_unknown'
    if port['thread_gender']!='female' or port['thread']!=male['thread']:return 'port_thread_or_gender_mismatch'
    return ''

def resolve(selection,spec,getter=None):
    """A detached partial assembly is useful; a missing part is never invented."""
    if selection.get('loop_components_mode','reference')!='selected':return None
    if getter is None:
        from liquid_component_runtime046 import get_component
        getter=get_component
    components={};issues=[]
    def issue(reason,field='',severity='review'):issues.append(dict(reason=reason,field=field,severity=severity))
    for field,kind in MODEL_FIELDS.items():
        identity=selection.get(field,'')
        if not identity:continue
        row=getter(kind,identity)
        if not row:issue('unknown_loop_component',field,'error')
        else:components[field]=row
    cpu=components.get('cpu_block_model')
    if cpu:
        state=socket_state(cpu,spec)
        if state!='nominal_match':issue('cpu_block_socket_unsupported' if state=='unsupported' else 'cpu_block_socket_unknown','cpu_block_model','error' if state=='unsupported' else 'review')
    else:issue('missing_cpu_block','cpu_block_model')
    pump=components.get('pump_model');top=components.get('pump_top_model')
    reservoir=components.get('reservoir_model');combo=components.get('pump_reservoir_model')
    if top and top['form']!='pump_top':issue('wrong_pump_top_form','pump_top_model','error')
    if pump and pump['form']=='pump_top':issue('wrong_pump_form','pump_model','error')
    if combo:
        if reservoir or top:issue('duplicate_loop_pump_or_reservoir','pump_reservoir_model','error')
        if combo['contains_motor']:
            if pump:issue('duplicate_loop_motor','pump_model','error')
        elif combo['requires_motor']:
            if not pump:issue('missing_loop_motor','pump_model')
            elif pump['form']!='pump_body' or not pump['contains_motor']:issue('motor_body_required','pump_model','error')
            else:
                state=motor_matches(pump,combo)
                if state!='nominal_match':issue('pump_motor_type_mismatch' if state=='unsupported' else 'pump_motor_fit_unknown','pump_model','error' if state=='unsupported' else 'review')
        else:issue('pump_reservoir_has_no_confirmed_motor','pump_reservoir_model')
    else:
        if not reservoir:issue('missing_loop_reservoir','reservoir_model')
        if not pump:issue('missing_loop_pump','pump_model')
        elif pump['form']=='pump_body':
            if not top:issue('missing_loop_pump_top','pump_top_model')
            else:
                state=motor_matches(pump,top)
                if state!='nominal_match':issue('pump_motor_type_mismatch' if state=='unsupported' else 'pump_motor_fit_unknown','pump_top_model','error' if state=='unsupported' else 'review')
        elif pump['form']=='pump_complete':
            if not pump['contains_motor'] or pump['requires_motor']:issue('missing_loop_motor','pump_model')
            if top:issue('duplicate_loop_pump_top','pump_top_model','error')
    fitting=components.get('fitting_model');tubing=components.get('tubing_model')
    if not selection.get('loop_fittings'):
        for reason in tube_compatibility(fitting,tubing):issue(reason,'fitting_model')
        if fitting and not fitting_ends(fitting):issue('fitting_ends_unknown','fitting_model')
    elif not tubing:issue('missing_fitting_or_tubing','tubing_model')
    if selection.get('gpu_waterblock'):issue('retail_gpu_block_not_selected','gpu_waterblock')
    return dict(components=components,issues=issues,
        can_draw_connections=not issues,reference_only=True,manufacturer_fit_verified=False,
        automatic_detection=False,installed_hardware_inferred=False,new_pollers=0)

def updated_choice(options,field,identity,getter=None):
    """Keep deliberate alternatives; remove only mutually exclusive duplicates."""
    result=deepcopy(options);result[field]=identity
    if field not in MODEL_FIELDS or not identity:return result
    if getter is None:
        from liquid_component_runtime046 import get_component
        getter=get_component
    selected=getter(MODEL_FIELDS[field],identity)
    if not selected:return result
    if field=='pump_reservoir_model':
        result['reservoir_model']='';result['pump_top_model']=''
        pump=getter('pump',result.get('pump_model',''))
        if selected.get('contains_motor') or not pump or pump['form']!='pump_body':result['pump_model']=''
    elif field=='pump_model':
        combo=getter('pump_reservoir',result.get('pump_reservoir_model',''))
        if combo and not (combo['requires_motor'] and selected['form']=='pump_body'):result['pump_reservoir_model']=''
        if selected['form']=='pump_complete':result['pump_top_model']=''
    elif field=='pump_top_model':
        result['pump_reservoir_model']=''
        pump=getter('pump',result.get('pump_model',''))
        if pump and pump['form']=='pump_complete':result['pump_model']=''
    elif field=='reservoir_model':result['pump_reservoir_model']=''
    return result
