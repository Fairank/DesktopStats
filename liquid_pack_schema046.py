"""Closed, data-only independent loop references; no catalogs or runtime work."""
from copy import deepcopy
import math
import re
from cooling_pack_schema045 import _keys,_id,_text,_urls,_number,_fail

PART_KINDS=('cpu_block','pump','reservoir','pump_reservoir','fitting','tubing','gpu_block')
FORMS=frozenset(('cpu_block','pump_complete','pump_body','pump_top','pump_reservoir_combo',
    'reservoir_tube','reservoir_flat','gpu_block','soft_compression','hard_compression','barb',
    'rotary_adapter','static_adapter','dual_compression','plug','drain','extension','soft_tube','hard_tube'))
FAMILIES=frozenset(('cpu_clear_square','cpu_armored_square','cpu_round_lcd','cpu_rect_extended',
    'pump_d5_motor','pump_d5_top','pump_d5_complete','pump_ddc_top','pump_ddc_complete','pump_dc_lt_motor','pump_top_compact','reservoir_cylinder','reservoir_flat',
    'pump_reservoir_cylinder','pump_reservoir_flat','pump_reservoir_compact','pump_reservoir_rect_tube',
    'fitting_straight','fitting_angled','fitting_rotary','fitting_extension','fitting_plug','fitting_drain',
    'tube_soft','tube_hard','knurled_soft_compression','knurled_hard_compression','smooth_hard_compression',
    'rotary_compression_elbow','rotary_thread_adapter','hex_thread_adapter','knurled_extension','low_profile_plug',
    'ball_drain','silicone_grip_hard_compression','dual_compression_elbow','static_thread_elbow',
    'clear_soft_tube','opaque_soft_tube','clear_hard_tube','frosted_hard_tube','carbon_hard_tube'))
_FORMS_BY_KIND={
    'cpu_block':{'cpu_block'},'pump':{'pump_complete','pump_body','pump_top'},
    'reservoir':{'reservoir_tube','reservoir_flat'},'pump_reservoir':{'pump_reservoir_combo'},
    'fitting':{'soft_compression','hard_compression','barb','rotary_adapter','static_adapter','dual_compression','plug','drain','extension'},
    'tubing':{'soft_tube','hard_tube'},'gpu_block':{'gpu_block'}}
_FAMILY_PREFIX={'cpu_block':'cpu_','pump':'pump_','reservoir':'reservoir_',
    'pump_reservoir':'pump_reservoir_','fitting':'fitting_','tubing':'tube_'}
_EXTRA_FAMILIES={'fitting':frozenset(('knurled_soft_compression','knurled_hard_compression','smooth_hard_compression',
    'rotary_compression_elbow','rotary_thread_adapter','hex_thread_adapter','knurled_extension','low_profile_plug','ball_drain','silicone_grip_hard_compression','dual_compression_elbow','static_thread_elbow')),
    'tubing':frozenset(('clear_soft_tube','opaque_soft_tube','clear_hard_tube','frosted_hard_tube','carbon_hard_tube'))}
_BASE=('id','label','vendor','series','aliases')
_WRAPPER=(*_BASE,'sources','reference','selector')
_COMMON=('id','label','brand','series','part_kind','form','dimensions_mm','reference_envelope_mm',
    'dimensions_verified','axis_verified','sources','notes','ports_count','ports','ports_geometry_complete',
    'geometry_family','geometry_features')
_OPTIONAL=frozenset(('dimensions_basis','source_authority','photo_reviewed','geometry_accuracy',
    'port_positions_verified','supported_sockets','socket_support_verified','mounting_notes',
    'contains_motor','motor_type','requires_motor','compatible_pump_types','pump_support_verified',
    'diameter_mm','materials','material','observed_lighting','body_color','accent_color',
    'thread_standard','thread_gender','fitting_angle_deg','tube_inner_mm','tube_outer_mm','tube_type',
    'compatible_materials','requires_tube','min_bend_radius_mm','length_mm','length_verified',
    'thread_length_mm','rotation_deg','quantity_per_package','live_temperature_available','factory_bracket',
    'tank_diameter_mm','shape','dimensions_scope','body_dimensions_mm','body_dimensions_verified','port_position_scope',
    'geometry_features_basis','selection_source','reviewed',
    'live_flow_available','live_rpm_available','installed_hardware_inferred','geometry_params'))
_PORT_REQUIRED=('id','face','position_normalized','role','thread','thread_gender','position_verified','role_verified','source')
_PORT_OPTIONAL=('normal_reference','normal_verified','tube_type','tube_inner_mm','tube_outer_mm')
FACE_NORMALS={'top':(0.,1.,0.),'bottom':(0.,-1.,0.),'front':(0.,0.,1.),'rear':(0.,0.,-1.),'left':(-1.,0.,0.),'right':(1.,0.,0.)}

def _boolean(value):
    if type(value) is not bool:_fail('Loop flag must be boolean')

def _texts(values,maximum=24,limit=128):
    if type(values) is not list or len(values)>maximum:_fail('Loop text list exceeds limit')
    for value in values:_text(value,limit)

def _dimensions(value,reference=False):
    _keys(value,('width','height','depth'))
    for number in value.values():_number(number,1,800 if reference else 50000,nullable=not reference)

def _diameters(row):
    for key in ('tube_inner_mm','tube_outer_mm'):
        if key in row:_number(row[key],1,50,nullable=True)
    inner,outer=row.get('tube_inner_mm'),row.get('tube_outer_mm')
    if inner is not None and outer is not None and inner>=outer:_fail('Tube inner diameter must be smaller than outer diameter')

def _port(port):
    _keys(port,_PORT_REQUIRED,(*_PORT_REQUIRED,*_PORT_OPTIONAL))
    _id(port['id']);_urls([port['source']])
    if port['face'] not in (*FACE_NORMALS,'angled'):_fail('Unknown loop port face')
    xyz=port['position_normalized']
    if type(xyz) is not list or len(xyz)!=3:_fail('Invalid loop port position')
    for value in xyz:_number(value,-.5,.5)
    if port['position_verified'] is not False:_fail('Exact loop port coordinates are not supported')
    _boolean(port['role_verified'])
    if port['role'] not in ('inlet','outlet','connection','fill','drain','auxiliary','closure'):_fail('Unknown loop port role')
    if port['thread'] not in (None,'G1/4','G3/8','G1/8','M20'):_fail('Unknown loop thread')
    if port['thread']=='M20' and port['role'] not in ('fill','closure','auxiliary'):_fail('Metric fill thread cannot act as an assumed circulation interface')
    if port['thread_gender'] not in ('male','female','none','unknown'):_fail('Unknown loop port gender')
    if port.get('normal_verified',False) is not False:_fail('Exact loop port orientation is not supported')
    normal=port.get('normal_reference')
    if port['face']=='angled' and normal is None:_fail('Angled port requires a reference normal')
    if normal is not None:
        if type(normal) is not list or len(normal)!=3:_fail('Invalid port reference normal')
        for value in normal:_number(value,-1,1)
        if abs(math.sqrt(sum(v*v for v in normal))-1)>.001:_fail('Port reference normal must be unit length')
    if 'tube_type' in port and port['tube_type'] not in ('soft','hard','none','unknown'):_fail('Unknown port tubing type')
    _diameters(port)

def validate_reference(row):
    if type(row) is dict and row.get('part_kind')=='gpu_block':
        from liquid_gpu_schema047 import validate_reference as validate_gpu
        return validate_gpu(row)
    _keys(row,_COMMON,(*_COMMON,*_OPTIONAL))
    _id(row['id']);_text(row['label']);_text(row['brand'],120);_text(row['series'],120)
    if (type(row['part_kind']) is not str or row['part_kind'] not in PART_KINDS
            or type(row['form']) is not str or row['form'] not in FORMS
            or type(row['geometry_family']) is not str or row['geometry_family'] not in FAMILIES):_fail('Unsupported loop model generator')
    family_matches=row['geometry_family'].startswith(_FAMILY_PREFIX[row['part_kind']]) or row['geometry_family'] in _EXTRA_FAMILIES.get(row['part_kind'],())
    if row['form'] not in _FORMS_BY_KIND[row['part_kind']] or not family_matches:_fail('Loop form or geometry does not match component kind')
    if row['part_kind']=='pump' and row['geometry_family'].startswith('pump_reservoir_'):_fail('Pump-reservoir geometry cannot stand in for a separate pump')
    _dimensions(row['dimensions_mm']);_dimensions(row['reference_envelope_mm'],True)
    _keys(row['axis_verified'],('width','height','depth'))
    for axis,verified in row['axis_verified'].items():
        _boolean(verified)
        if verified and row['dimensions_mm'][axis] is None:_fail('Verified loop dimension is missing')
    _boolean(row['dimensions_verified'])
    if row['dimensions_verified'] and not all(row['axis_verified'].values()):_fail('Partial loop dimensions cannot be fully verified')
    _urls(row['sources'])
    if type(row['notes']) is list:_texts(row['notes'],8,2048)
    else:_text(row['notes'],4096,True)
    _texts(row['geometry_features'])
    _number(row['ports_count'],0,24,integer=True,nullable=True)
    if type(row['ports']) is not list or len(row['ports'])>24:_fail('Too many loop ports')
    for port in row['ports']:_port(port)
    if len({p['id'] for p in row['ports']})!=len(row['ports']):_fail('Duplicate loop port identity')
    if row['ports_count'] is not None and len(row['ports'])>row['ports_count']:_fail('Loop port inventory exceeds documented count')
    _boolean(row['ports_geometry_complete'])
    if row['ports_geometry_complete'] and (row['ports_count'] is None or len(row['ports'])!=row['ports_count']):_fail('Incomplete loop port geometry')
    for key in ('photo_reviewed','socket_support_verified','pump_support_verified','contains_motor','requires_motor','requires_tube','length_verified','body_dimensions_verified'):
        if key in row:_boolean(row[key])
    for key in ('port_positions_verified','live_temperature_available','live_flow_available','live_rpm_available','installed_hardware_inferred'):
        if key in row and row[key] is not False:_fail('Unsupported loop inference or live binding')
    for key in ('dimensions_basis','geometry_accuracy','mounting_notes'):
        if key in row:_text(row[key],2048,True)
    if 'geometry_features_basis' in row:_text(row['geometry_features_basis'],2048)
    if row.get('selection_source','manual')!='manual':_fail('Loop parts require explicit manual selection')
    if 'reviewed' in row and (type(row['reviewed']) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',row['reviewed'])):_fail('Invalid loop review date')
    if 'shape' in row:_text(row['shape'],80)
    if row.get('dimensions_scope','overall') not in ('overall','complete','partial','body_only','unknown','publisher_unspecified','supplied_tube'):_fail('Unknown loop dimension scope')
    if row.get('port_position_scope','overall') not in ('overall','body'):_fail('Unknown loop port scope')
    if row.get('port_position_scope')=='body' and not row.get('body_dimensions_mm'):_fail('Body port positions need a body envelope')
    if 'body_dimensions_mm' in row:_dimensions(row['body_dimensions_mm'])
    if row.get('body_dimensions_verified') and (not row.get('body_dimensions_mm') or any(v is None for v in row['body_dimensions_mm'].values())):_fail('Verified loop body dimensions are missing')
    bracket=row.get('factory_bracket')
    if bracket is not None:
        _keys(bracket,('included','description','source'));_boolean(bracket['included'])
        _text(bracket['description'],2048);_urls([bracket['source']])
    if 'source_authority' in row and row['source_authority'] not in ('manufacturer','authorized_distributor'):_fail('Unknown loop source authority')
    for key in ('supported_sockets','compatible_pump_types','materials','observed_lighting','compatible_materials'):
        if key in row:_texts(row[key])
    for key in ('material','motor_type'):
        if key in row and row[key] is not None:_text(row[key],80)
    if 'thread_standard' in row and row['thread_standard'] not in (None,'G1/4','G3/8','G1/8'):_fail('Unknown loop thread')
    if 'thread_gender' in row and row['thread_gender'] not in ('male','female','none','unknown'):_fail('Unknown loop gender')
    if 'tube_type' in row and row['tube_type'] not in ('soft','hard','none','unknown'):_fail('Unknown loop tubing type')
    _diameters(row)
    for key,maximum in (('diameter_mm',200),('tank_diameter_mm',200),('min_bend_radius_mm',1000),('length_mm',50000),('thread_length_mm',40),('rotation_deg',360)):
        if key in row:_number(row[key],0,maximum,nullable=True)
    if 'fitting_angle_deg' in row and row['fitting_angle_deg'] not in (0,45,90):_fail('Unsupported fitting angle')
    if 'quantity_per_package' in row:_number(row['quantity_per_package'],1,64,integer=True)
    for key in ('body_color','accent_color'):
        if key in row and (type(row[key]) is not str or not re.fullmatch('#[0-9a-fA-F]{6}',row[key])):_fail('Invalid loop color')
    if 'geometry_params' in row:
        allowed=('body_width_ratio','body_depth_ratio','body_height_ratio','window_width_ratio','window_depth_ratio',
                 'base_height_ratio','top_height_ratio','mount_ear_span_ratio','port_bore_radius_mm','cap_height_ratio')
        _keys(row['geometry_params'],(),allowed)
        for key,value in row['geometry_params'].items():_number(value,.01,12 if key.endswith('_mm') else 1.5)
    if row['part_kind']=='cpu_block' and not {'supported_sockets','socket_support_verified'}<=row.keys():_fail('CPU block requires explicit socket support facts')
    if row.get('socket_support_verified') and not row.get('supported_sockets'):_fail('Verified socket list is empty')
    if row['part_kind'] in ('pump','reservoir','pump_reservoir') and not {'contains_motor','requires_motor'}<=row.keys():_fail('Missing pump motor identity')
    if row.get('contains_motor') and row.get('requires_motor'):_fail('Installed motor cannot also be required')
    if row['part_kind']=='reservoir' and row['contains_motor']:_fail('Motor belongs to a pump or pump-reservoir combo')
    if row['part_kind']=='reservoir' and row['requires_motor']:_fail('Body-only motor housing belongs to a pump-reservoir combo')
    if row['part_kind']=='pump':
        if row['form']=='pump_top' and (row['contains_motor'] or not row['requires_motor']):_fail('Pump top needs a separate motor')
        if row['form'] in ('pump_body','pump_complete') and (not row['contains_motor'] or row['requires_motor']):_fail('A named pump or motor must retain its included motor')
    if row['part_kind'] in ('fitting','tubing') and not {'tube_type','tube_inner_mm','tube_outer_mm','requires_tube'}<=row.keys():_fail('Missing tube compatibility facts')
    if row['part_kind']=='tubing' and row['tube_type'] not in ('soft','hard'):_fail('Tubing requires a real material type')
    return deepcopy(row)

def selector_for(row):return dict(part_kind=row['part_kind'],form=row['form'])

def validate_summary(row):
    _keys(row,(*_BASE,'selector'))
    _id(row['id']);_text(row['label']);_text(row['vendor'],120);_text(row['series'],120)
    _texts(row['aliases'],8,160)
    if len(set(row['aliases']))!=len(row['aliases']):_fail('Duplicate loop aliases')
    _keys(row['selector'],('part_kind','form'))
    kind,form=row['selector']['part_kind'],row['selector']['form']
    if (type(kind) is not str or kind not in PART_KINDS or type(form) is not str
            or form not in _FORMS_BY_KIND[kind]):_fail('Invalid loop selector')
    return deepcopy(row)

def summary_for(row):return {**{key:deepcopy(row[key]) for key in _BASE},'selector':deepcopy(row['selector'])}

def validate_model(row):
    _keys(row,_WRAPPER);summary=validate_summary(summary_for(row));reference=validate_reference(row['reference'])
    if (summary['id'],summary['label'],summary['vendor'],summary['series'])!=(reference['id'],reference['label'],reference['brand'],reference['series']):_fail('Loop identity does not match model')
    if _urls(row['sources'])!=reference['sources'] or summary['selector']!=selector_for(reference):_fail('Loop sources or selector do not match model')
    return deepcopy(row)
