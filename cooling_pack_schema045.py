"""Strict data-only fan/cooler/radiator records for optional model packs.

No catalog, renderer, Qt, device, file or network is imported here. Unknown
fields never become a procedural renderer instruction. Source-linked numbers
remain reference facts, not live telemetry or proof of actual installation.
"""
from copy import deepcopy
import math
import re

KINDS = ('fan', 'cooler', 'radiator')
_BASE = ('id','label','vendor','series','aliases')
_WRAPPER = (*_BASE,'sources','reference','selector')
_FAMILIES = frozenset('alphacool-rise antec-fusion apnx-fp1 arctic-flow arctic-max arctic-pressure arctic-slim asus-maglev bequiet-grooved cm-mf200 cm-mobius cm-sickleflow cm-silencio corsair-airguide corsair-lx cryorig-qf deepcool-pressure ek-fpt enermax-squa fractal-aspect fractal-notched gigabyte-aorus idcooling-slim lian-li-216 lian-li-infinity lian-li-p28 lian-li-sl lian-li-tl-lcd montech-ax msi-lcp noctua-a noctua-focused noctua-g2 noctua-redux-p noctua-sterrox nzxt-pressure phanteks-d30 phanteks-t30 scythe-kaze140 scythe-kaze2 scythe-kaze2-slim silverstone-penetrator silverstone-scimitar thermalright-c12 thermalright-lcp thermalright-slim thermalright-ty thermaltake-ct thermaltake-pure thermaltake-swafan thermaltake-toughfan xpg-typhoon stock-reference alphacool-core asus-tuf cryorig-c7 deepcool-fc120 deepcool-fk120 deepcool-slim idcooling-pressure msi-argb scythe-kaze-original scythe-tornado thermalright-e12 tryx-reference xpg-levante zalman-radial zalman-turbine'.split())
_COOLER_KINDS = frozenset('aio custom_loop dual_top_flow dual_tower low_profile passive_tower radial_tower single_tower stock_amd stock_intel stock_prism'.split())
_PUMPS = frozenset('alphacool_square aorus_round_lcd arctic_vrm asus_lcd asus_tuf_hex cm_dual_chamber corsair_octagon corsair_square corsair_lcd deepcool_lcd deepcool_lt_mirror deepcool_square_mirror ek_nucleus enermax_square_mirror fractal_lumen id_white_ring lianli_infinity msi_lcd msi_radiator_pump nzxt_lcd nzxt_infinity phanteks_bridge round thermaltake_mirror tryx_panorama xc7_block xpg_infinity'.split())
_SHELLS = frozenset('alphacool_split_tanks alphacool_v2_flush_plugs aqua_radical_tube_stack corsair_xr_frame ek_surface_aluminium_caps hwlabs_nemesis tt_pacific_stainless_panels watercool_brushed_endplates xspc_ex_low xspc_rx_thick xspc_tx_slim alphacool_monsta_deep alphacool_hpe20_slim alphacool_hpe_frame bitspower_leviathan_ii bitspower_leviathan_xf bykski_rc_v2 bykski_rc_v3 barrow_dabel_twin_header'.split())
_SHELL_FEATURES = frozenset('scalloped_mount_rails split_shoulder_tanks removable_side_plates contrasting_aluminium_endcaps flush_port_collars ultrathin_core rounded_tanks stainless_side_panels double_fin_core triple_row_core brushed_endplates silver_unsoldered_core black_delrin_terminal stainless_side_plates insert_mount_guides angular_tank_shoulders central_header_notch'.split())


def _fail(message):
    from hardware_packs import PackError
    raise PackError(message)


def _keys(value, required, allowed=None):
    allowed = set(required) if allowed is None else set(allowed)
    if type(value) is not dict or not set(required) <= value.keys() or value.keys()-allowed:
        _fail('Unsupported cooling record fields')


def _text(value, limit=256, empty=False):
    if (type(value) is not str or len(value)>limit or not empty and not value
            or any(ord(c)<32 or ord(c)==127 or c in '<>' or 0xD800<=ord(c)<=0xDFFF for c in value)):
        _fail('Invalid cooling text')
    return value


def _id(value):
    from hardware_packs import _identifier
    return _identifier(value)


def _urls(value):
    from hardware_packs import _urls as validate
    from urllib.parse import urlsplit
    if type(value) is not list or not 1<=len(value)<=8:_fail('Missing source URLs')
    for item in value:
        _text(item,1024)
        try:
            parsed=urlsplit(item)
            legacy=parsed.scheme=='http' and parsed.hostname in ('barrowint.com','www.barrowint.com') and parsed.port in (None,80) and not parsed.username and not parsed.password
        except ValueError:_fail('Invalid source URL')
        if not legacy:validate([item])
    # Citations only: no request, redirects, images or downloads are executed.
    return list(value)


def _number(value, low, high, *, integer=False, nullable=False):
    if value is None and nullable:return
    if (type(value) not in ((int,) if integer else (int,float)) or not low<=value<=high
            or not math.isfinite(value)):
        _fail('Cooling number exceeds renderer limits')


def _rule(value, rule):
    kind=rule[0]
    if kind=='bool':
        if type(value) is not bool:_fail('Cooling flag must be boolean')
    elif kind=='false':
        if value is not False:_fail('Unsupported cooling inference or live binding')
    elif kind=='text':_text(value,rule[1],rule[2] if len(rule)>2 else False)
    elif kind=='id':
        if value is not None or not rule[1]:_id(value)
    elif kind=='urls':_urls(value)
    elif kind=='url':_urls([value])
    elif kind=='enum':
        if type(value) is not str or value not in rule[1]:_fail('Unsupported cooling renderer family')
    elif kind=='color':
        if type(value) is not str or not re.fullmatch(r'#[0-9a-fA-F]{6}',value):_fail('Invalid cooling color')
    elif kind=='number':_number(value,*rule[1:3],integer=rule[3],nullable=rule[4])
    elif kind=='list':
        if type(value) is not list or not rule[1]<=len(value)<=rule[2]:_fail('Cooling list exceeds limit')
        for entry in value:_rule(entry,rule[3])
    elif kind=='map':
        _keys(value,rule[1],rule[2])
        for key,item in value.items():_rule(item,rule[2][key])
    elif kind=='null':
        if value is not None:_fail('Unsupported exact internal cooling geometry')
    else:_fail('Unsupported cooling schema')


def _num(low,high,integer=False,nullable=False):return ('number',low,high,integer,nullable)
def _enum(values):return ('enum',frozenset(values.split()))
def _list(low,high,item):return ('list',low,high,item)
def _map(fields):return ('map',tuple(fields),fields)


_COMMON = dict(id=('id',False),label=('text',256),brand=('text',80),series=('text',80),
    sources=('urls',),reviewed=('text',32),notes=('text',4096,True),specification_observations=('text',4096,True),
    geometry_accuracy=_enum('original_reference explicit_reference_parts_combination'),
    appearance_sources=('urls',),extra_sources=('urls',))
_FAN = dict(_COMMON, family=('text',64),size_mm=_num(40,250),width_mm=_num(35,280),
    depth_mm=_num(5,80),blades=_num(1,64,True),shape=_enum('wide swept'),frame=_enum('round square'),
    frame_color=('color',),blade_color=('color',),hub_ratio=_num(.08,.5),
    mount_pitch_mm=_num(20,250,nullable=True),mount_hole_diameter_mm=_num(1,12,nullable=True),
    mount_pitch_axes_mm=_list(2,2,_num(15,250)),
    mounting_source=('url',),fixed_led_color=('color',),hub_window_face=_enum('front'),switch_face=_enum('rear'),frame_rgb_outline=_enum('square'),
    frame_rgb_polygon=_num(3,12,True),lighting_connector=_enum('argb3 jst_argb3 phanteks_drgb3 rgb12v4'),
    pad_style=_enum('round'),stator_vanes=_num(1,128,True),photo_observations=('text',4096,True),
    leaf_contour_accuracy=_enum('photo_reviewed_parametric original_reference'),
    hub_display_inches=_num(.1,5),hub_display_resolution=_list(2,2,_num(1,4096,True)),
    foil_profile=_map(dict(sweep_deg=_num(-35,55),leading=_num(.05,.5),trailing=_num(.05,.5),root=_num(.15,.5))),
    foil_profile_accuracy=_enum('qualitative_reference'),
    geometry_review_status=_enum('specification_only'),unknown=_list(0,8,_enum('blade_count')))
for _name in 'frame_rgb_sides replaceable_reverse_impeller fixed_white_hub_window blade_count_verified blade_geometry_reviewed depth_verified dimensions_verified directional_grille frame_rgb_ring hub_display interlock_bridges lighting_connector_verified marketed_separately_verified metal_hub mount_hole_diameter_verified mount_pitch_verified mount_pitch_axes_verified mount_pitch_axes_orientation_verified outer_ring pads power_connector_verified reverse_blade rgb rotation_direction_verified side_air_inlets vortex_notches frameless'.split():
    _FAN[_name]=('bool',)

_BOX = _map(dict(width=_num(10,450),height=_num(5,450),depth=_num(5,450)))
_RADIATOR_BOX = _map(dict(length=_num(80,800),width=_num(65,250),thickness=_num(12,100)))
_COOLER = dict(_COMMON,kind=('enum',_COOLER_KINDS),fan_count=_num(0,4,True),fan_model=('id',True),
    dimensions_mm=_BOX,heatsink_dimensions_mm=_BOX,pump_reference_mm=_BOX,radiator_mm=_RADIATOR_BOX,
    reservoir_mm=_map(dict(diameter=_num(10,150),height=_num(20,600))),
    fan_reference_mm=_num(40,250,nullable=True),fan_size_mm=_num(40,250,nullable=True),
    fan_reference_depth_mm=_num(5,80),fan_reference_blades=_num(1,64,True),
    fan_sizes=_list(1,4,_num(40,250)),fan_depths=_list(1,4,_num(5,80)),
    fan_models=_list(1,4,('id',False)),fan_relative_directions=_list(1,4,('number',-1,1,True,False)),
    fan_placements=_list(1,4,_enum('above between under')),fan_placement=_enum('above between under'),
    fan_layout=_enum('center_rear center'),fan_family=('enum',_FAMILIES),
    heatpipes=_num(0,20,True),documented_fin_count=_num(1,256,True),fin_count=_num(1,256,True),
    horizontal_fin_banks=_num(1,4,True),radial_fin_banks=_num(1,4,True),
    radial_inner_reference_mm=_num(1,150),radial_outer_reference_mm=_num(1,200),
    heatsink_depth_mm=_num(5,450),ram_clearance_mm=_num(0,150),
    accent=('color',),pipe_color=('color',),fin_color=('color',),
    fin_style=_enum('checker_cut honeycomb parallel passive_perforated radial square'),
    top_style=_enum('assassin_shell asymmetric_caps brushed_caps dark_caps exposed_caps matrix_caps mesh_bridge mesh_bridge_rgb stealth_caps'),
    pump_style=('enum',_PUMPS),pump_location=_enum('radiator'),
    pump_dimensions_scope=_enum('manufacturer_dimension_diagram_shared_LFIII_reference_including_elbows'),
    visible_crown=_enum('photo_observed_radial_vent_crown'),screen_style=_enum('curved_l'),
    screen_diagonal_inches=_num(.1,10),vrm_fan_diameter_mm=_num(10,120),
    radiator_size=_num(80,600,True),tube_length_mm=_num(50,1500),
    radiator_model=('text',160),reservoir_model=('text',160),cpu_block_model=('text',160),
    dimension_axes_verified=_map(dict(width=('bool',),height=('bool',),depth=('bool',))),
    radiator_axes_verified=_map(dict(length=('bool',),width=('bool',),thickness=('bool',))),
    pump_geometry_accuracy=_enum('original_reference'))
for _name in 'sealed_aio pump_lcd pump_rgb_ring pump_rgb_ring_verified pump_fixed_white heatsink_depth_verified asymmetric base_led c_shape dimension_bounds_verified dimensions_verified envelope_is_reference envelope_is_upper_bound fan_blade_count_verified fan_dimensions_verified fan_power_connector_verified fan_reference_rgb fan_outer_ring frameless_fan heatpipe_count_verified perforated_fins pump_dimensions_verified radiator_dimensions_verified relative_rotation_verified tube_length_verified vrm_fan'.split():
    _COOLER[_name]=('bool',)
for _name in 'crown_motion_verified gpu_block internal_vrm_impeller_verified pump_axis_orientation_verified radial_geometry_verified'.split():
    _COOLER[_name]=('false',)

_MATERIAL_KEYS = 'cooling_fins coolant_channels fins tubes end_tanks side_plates end_covers tanks housing side_panels endplates coolant_tubes terminal frame channels'.split()
_MATERIAL_VALUE = _enum('copper copper_or_brass_reference brass stainless_steel aluminium steel H90_copper Delrin copper_brass red_copper iron_not_coolant_contact')
_PORT_FIELDS=dict(id=('id',False),face=_enum('front rear left right end'),position_normalized=_list(3,3,_num(-.5,.5)),
    role=_enum('connection'),positions_verified=('false',),source=('url',),end=_num(-1,1,True))
_PORT = ('map',('id','face','position_normalized','role','positions_verified','source'),_PORT_FIELDS)
_RADIATOR = dict(_COMMON,category=_enum('radiator'),selection_source=_enum('manual'),loop_type=_enum('custom'),
    model_number=('text',160),nominal_size_mm=_num(80,600,True),
    documented_connection_threads=_num(1,16,True,True),source_authority=_enum('exclusive_us_distributor manufacturer'),dimensions_mm=_RADIATOR_BOX,dimensions_basis=('text',1024),
    dimensions_tolerance_mm=_num(0,10),fan_size_mm=_num(40,250),fan_count=_num(1,4,True),
    fan_mount_capacity_per_side=_num(1,4,True),fan_mount_sides=_num(1,2,True),
    fan_mount_pitch_mm=_num(20,250,nullable=True),fan_center_spacing_mm=_num(20,250,nullable=True),
    ports_count=_num(1,16,True,True),active_port_count=_num(1,16,True),port_thread=_enum('G1/4 G1/4_BSPP'),
    port_layout=_enum('same_end_face_pair multiport_end opposite_end unknown'),
    ports=_list(0,16,_PORT),port_center_spacing_mm=_num(1,250),
    fin_count=('null',),fpi=_num(1,64,True,True),
    shell_family=('enum',_SHELLS),shell_features=_list(0,16,('enum',_SHELL_FEATURES)),
    shell_features_basis=_enum('manufacturer_text_reference observed_reference reference'),
    materials=('map',(),{key:_MATERIAL_VALUE for key in _MATERIAL_KEYS}),
    body_color=('color',),frame_color=('color',),tank_color=('color',),
    palette_accuracy=_enum('illustrative_not_measured_factory_paint'),mount_dimensions_source=('url',))
_RADIATOR['port_thread']=('enum',frozenset(('G1/4','G1/4 BSPP')))
for _name in 'dimensions_verified fan_mount_pitch_verified port_thread_verified port_layout_verified ports_geometry_complete fpi_verified fin_geometry_is_sampling port_center_spacing_verified'.split():
    _RADIATOR[_name]=('bool',)
for _name in 'aio_replacement_verified fan_count_is_installed mounting_positions_verified port_positions_verified default_caps_installed shell_geometry_verified internal_channels_verified live_flow_available live_temperature_available installed_hardware_inferred'.split():
    _RADIATOR[_name]=('false',)

_RULES={'fan':_FAN,'cooler':_COOLER,'radiator':_RADIATOR}
_REQUIRED={
    'fan':('id','label','brand','series','sources','family','size_mm','width_mm','depth_mm','blades','shape','frame','frame_color','blade_color','hub_ratio','pads','rgb','outer_ring','dimensions_verified','blade_count_verified'),
    'cooler':('id','label','brand','series','sources','kind','fan_count','fan_model'),
    'radiator':('id','label','brand','series','sources','category','loop_type','selection_source','dimensions_mm','fan_size_mm','fan_count','fan_mount_capacity_per_side','fan_mount_sides','fan_mount_pitch_mm','fan_mount_pitch_verified','ports_count','active_port_count','port_thread','port_layout','ports','ports_geometry_complete','shell_family','shell_features','materials'),
}


def _reference(kind, reference):
    allowed=set(_RULES[kind]) | ({'bundled_fan_reference'} if kind=='cooler' else set())
    _keys(reference,_REQUIRED[kind],allowed)
    for key,value in reference.items():
        if key!='bundled_fan_reference':_rule(value,_RULES[kind][key])
    if kind=='fan':
        if reference.get('fixed_white_hub_window') and reference.get('hub_window_face')!='front':_fail('Missing observed hub-window face')
        family=reference['family']
        if family not in _FAMILIES:
            _id(family)
            if 'foil_profile' not in reference:_fail('Unknown fan family requires bounded reference foil')
        if ('foil_profile' in reference)!=('foil_profile_accuracy' in reference):_fail('Missing foil reference status')
        if reference.get('mount_pitch_verified') and reference.get('mount_pitch_mm') is None:_fail('Verified fan pitch is missing')
        if reference.get('mount_hole_diameter_verified') and reference.get('mount_hole_diameter_mm') is None:_fail('Verified mounting diameter is missing')
        if reference.get('mount_pitch_verified') or reference.get('mount_hole_diameter_verified'):
            if not reference.get('mounting_source'):_fail('Verified fan mounting needs source')
        if reference.get('mount_pitch_axes_verified'):
            if not reference.get('mount_pitch_axes_mm') or not reference.get('mounting_source'):_fail('Verified mounting axes need source and dimensions')
        if reference.get('mount_pitch_axes_orientation_verified') and not reference.get('mount_pitch_axes_verified'):
            _fail('Unverified fan axes cannot have verified orientation')
    elif kind=='cooler':
        if reference.get('dimensions_verified') and not all(reference.get('dimension_axes_verified',{}).values()):_fail('Partial dimensions cannot be fully verified')
        if reference.get('radiator_dimensions_verified') and not all(reference.get('radiator_axes_verified',{}).values()):_fail('Partial radiator dimensions cannot be fully verified')
        liquid=reference['kind'] in ('aio','custom_loop')
        needed=('radiator_mm','radiator_size','pump_reference_mm','pump_style') if liquid else ('dimensions_mm','heatpipes')
        if not set(needed)<=reference.keys():_fail('Missing cooler geometry')
        if reference['kind']=='custom_loop' and not {'reservoir_mm','reservoir_model'}<=reference.keys():
            _fail('Missing custom-loop reservoir geometry or identity')
        count=reference['fan_count']
        for key in ('fan_sizes','fan_depths','fan_models','fan_relative_directions','fan_placements'):
            if key in reference and len(reference[key])!=count:_fail('Cooler fan list/count mismatch')
        if any(value not in (-1,1) for value in reference.get('fan_relative_directions',())):_fail('Invalid relative fan direction')
        if any(value==-1 for value in reference.get('fan_relative_directions',())) and not reference.get('relative_rotation_verified'):_fail('Unverified relative fan direction')
        if count and reference.get('fan_reference_mm',reference.get('fan_size_mm')) is None:_fail('Cooler needs explicit fan dimensions')
        if not count and reference['kind']!='passive_tower':_fail('Unexpected fanless cooler kind')
        if 'bundled_fan_reference' in reference:
            child=reference['bundled_fan_reference'];_reference('fan',child)
            if reference.get('fan_model')!=child['id'] or reference.get('fan_reference_mm',reference.get('fan_size_mm'))!=child['size_mm']:
                _fail('Bundled fan identity or size mismatch')
    else:
        count=reference['ports_count'];ports=reference['ports']
        if count is not None and (len(ports)>count or reference['active_port_count']>count):_fail('Radiator port inventory mismatch')
        if len({row['id'] for row in ports})!=len(ports):_fail('Duplicate radiator port identity')
        for port in ports:
            if port['face']=='end' and port.get('end') not in (-1,1):_fail('Invalid radiator end face')
            if port['face']!='end' and 'end' in port:_fail('Unexpected radiator end face')
        if reference['ports_geometry_complete'] and (count is None or len(ports)!=count):_fail('Incomplete radiator ports marked complete')
        if reference['fan_mount_capacity_per_side']!=reference['fan_count']:_fail('Radiator fan capacity mismatch')
        if reference.get('fan_mount_pitch_verified') and reference['fan_mount_pitch_mm'] is None:_fail('Verified radiator pitch is missing')
        if reference.get('fpi_verified') and reference.get('fpi') is None:_fail('Verified FPI is missing')
        if reference.get('port_layout_verified') and reference['port_layout']=='unknown':_fail('Unknown port layout marked verified')


def _selector(kind, reference):
    if kind=='fan':return dict(size_mm=reference['size_mm'],depth_mm=reference['depth_mm'],frame=reference['frame'],
        frameless=reference.get('frameless',False),mount_pitch_mm=reference.get('mount_pitch_mm'),mount_pitch_verified=reference.get('mount_pitch_verified',False))
    if kind=='cooler':return dict(kind=reference['kind'],fan_size_mm=reference.get('fan_reference_mm',reference.get('fan_size_mm')))
    return {key:reference[key] for key in ('fan_size_mm','fan_count','fan_mount_pitch_mm','fan_mount_pitch_verified')}


def validate_summary(kind, row):
    """Validate lightweight picker data without importing authoring catalogs."""
    if type(kind) is not str or kind not in KINDS:_fail('Unsupported cooling pack kind')
    _keys(row,(*_BASE,'selector'))
    _id(row['id']);_text(row['label']);_text(row['vendor'],80);_text(row['series'],80)
    aliases=row['aliases']
    if type(aliases) is not list or not 1<=len(aliases)<=8:_fail('Invalid cooling aliases')
    for alias in aliases:_text(alias)
    if len(set(aliases))!=len(aliases):_fail('Duplicate cooling aliases')
    rules=(dict(size_mm=_num(40,250),depth_mm=_num(5,80),frame=_enum('round square'),frameless=('bool',),mount_pitch_mm=_num(20,250,nullable=True),mount_pitch_verified=('bool',)) if kind=='fan' else
        dict(kind=('enum',_COOLER_KINDS),fan_size_mm=_num(40,250,nullable=True)) if kind=='cooler' else
        dict(fan_size_mm=_num(40,250),fan_count=_num(1,4,True),fan_mount_pitch_mm=_num(20,250,nullable=True),fan_mount_pitch_verified=('bool',)))
    _rule(row['selector'],_map(rules))
    pitch='mount_pitch_mm' if kind=='fan' else 'fan_mount_pitch_mm' if kind=='radiator' else None
    verified='mount_pitch_verified' if kind=='fan' else 'fan_mount_pitch_verified'
    if pitch and row['selector'][verified] and row['selector'][pitch] is None:
        _fail('Verified selector pitch is missing')
    return deepcopy(row)


def validate_model(kind, row):
    """Return a detached fully validated data record; reject unknown instructions."""
    if type(kind) is not str or kind not in KINDS:_fail('Unsupported cooling pack kind')
    _keys(row,_WRAPPER)
    result=validate_summary(kind,{key:row[key] for key in (*_BASE,'selector')})
    sources=_urls(row['sources']);reference=row['reference'];_reference(kind,reference)
    for field,target in (('id','id'),('label','label'),('vendor','brand'),('series','series')):
        if row[field]!=reference[target]:_fail('Cooling wrapper identity conflicts with reference')
    if sources!=reference['sources']:_fail('Cooling source declarations conflict')
    expected=_selector(kind,reference)
    if result['selector']!=expected:_fail('Cooling selector conflicts with reference')
    result.update(sources=sources,reference=deepcopy(reference))
    return result


def summary_for(kind, row):
    """Derive only the picker fields from a validated full record."""
    result=validate_model(kind,row)
    return {key:deepcopy(result[key]) for key in (*_BASE,'selector')}
