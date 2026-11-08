"""Manual assembly references and choices; no hardware or graphics work."""
import copy
from functools import lru_cache

from assembly_config import CABLE_COLORS,validate_assembly

MOUNT_LABELS={'front':'前部','top':'顶部','rear':'后部','bottom':'底部','side':'侧部'}


@lru_cache(maxsize=1)
def _gpu_rows():
    from hardware_appearance import CATALOG,BRANDS,appearance_for
    rows=[]
    for row in CATALOG:
        if row[1]!='gpu':continue
        appearance=appearance_for('gpu',row[-1][0])
        rows.append((row[0],row[4],BRANDS[row[3] if row[3]!='unknown' else row[2]][0],
                     appearance.get('series_id',''),appearance.get('series_label','')))
    return tuple(rows)


def choices(translate=lambda text:text):
    from motherboard_catalog import choices as boards,get_model as get_board
    from cooling_catalog import choices_coolers,choices_fans
    from liquid_cooling_catalog044 import records as radiator_records
    from cooling_pack_runtime045 import radiator_choices
    from component_catalog import choices as components,get_component
    from hardware_appearance import CATALOG,BRANDS
    from cpu_package_runtime import reference_choices
    from memory_appearance import CATALOG as memory,BRANDS as memory_brands
    from liquid_component_runtime046 import grouped_choices
    loop=grouped_choices()
    empty=lambda label:[dict(id='',label=translate(label))]
    return dict(cpu_blocks=empty('未选择 CPU 冷头')+loop['cpu_block'],
        loop_pumps=empty('未选择水泵／电机')+[r for r in loop['pump'] if r['form']!='pump_top'],
        loop_pump_tops=empty('未选择泵盖')+[r for r in loop['pump'] if r['form']=='pump_top'],
        loop_reservoirs=empty('未选择水箱')+loop['reservoir'],
        loop_combos=empty('使用单独水泵与水箱')+loop['pump_reservoir'],
        loop_fittings=empty('未选择默认接头')+loop['fitting'],loop_tubing=empty('未选择管材')+loop['tubing'],
        cpus=empty('按系统硬件识别')+[dict(id=row[0],label=row[4],brand=BRANDS[row[2]][0]) for row in CATALOG if row[1]=='cpu']+reference_choices(),
        gpus=empty('按系统硬件识别')+[dict(zip(('id','label','brand','series_id','series_label'),row)) for row in _gpu_rows()],
        memory=[dict(id=row['id'],label=row['label'],brand=memory_brands[row['brand']][0]) for row in memory],
        boards=empty('按系统主板识别')+[dict(row,label=row['label']+(' · '+translate('外观待核实') if (get_board(row['id']) or {}).get('finish_status')!='photo_reviewed' else '')) for row in boards()],
        coolers=empty('未选择散热器')+list(choices_coolers()),
        fans=empty('不放置风扇')+list(choices_fans()),
        radiators=empty('沿用参考冷排')+[dict(id=row['id'],label=row['label'],brand=row['brand'],fan_size_mm=row['fan_size_mm'],fan_count=row['fan_count'],fan_mount_pitch_mm=row.get('fan_mount_pitch_mm'),
            fan_mount_pitch_verified=row.get('fan_mount_pitch_verified',False)) for row in radiator_records()]+radiator_choices(),
        radiator_fans=empty('沿用原配／参考风扇')+list(choices_fans()),
        radiator_layouts=[dict(id=key,label=translate(label)) for key,label in
            (('single','单面风扇'),('push_pull','双面夹心'),('none','不装风扇（结构检视）'))],
        psus=empty('未选择电源')+list(components('psu')),
        storage=empty('不放置存储设备')+[dict(row,label=row['label']+(' · '+translate('外观待核实') if (get_component(row['id']) or {}).get('appearance_unverified') else '')) for row in components('storage')],
        expansion=empty('不放置扩展卡')+list(components('expansion')),
        mounts=[dict(id=key,label=translate(label)) for key,label in MOUNT_LABELS.items()],
        colors=[dict(id=key,label=translate(label)) for key,label in
            (('black','黑色'),('white','白色'),('red','红色'),('blue','蓝色'))],
        motion=[dict(id='measured',label=translate('使用实测转速')),
                dict(id='demo',label=translate('参考转动（非实测）'))])


def selected_parts(options):
    """Only explicit chosen IDs; unknown parts are not inferred from a board."""
    return dict(cooling=dict(cpu_cooler=options['cooler_model'] or 'none',gpu_waterblock=options['gpu_waterblock'],
        radiator_mount=options['cooler_mount'],case_fans=copy.deepcopy(options['case_fans']),
        **{key:copy.deepcopy(options[key]) for key in ('loop_components_mode','cpu_block_model','pump_model','pump_top_model',
           'reservoir_model','pump_reservoir_model','fitting_model','tubing_model','loop_tubes_visible','loop_fittings',
           'radiator_model','radiator_fan_model','radiator_fan_layout',
           'secondary_radiator_model','secondary_radiator_fan_model','secondary_radiator_fan_layout')}),
        auxiliary=dict(psu=dict(model_id=options['psu_model']),storage=copy.deepcopy(options['storage']),
            expansion_cards=copy.deepcopy(options['expansion_cards']),
            cables_enabled=options['cables_enabled'],cable_color=CABLE_COLORS[options['cable_color']]))


def reference_preset(options,kind):
    """Explicit user-invoked full reference build, never an installed-PC claim."""
    if kind not in ('air','aio','loop'):raise ValueError('未知参考装机方案')
    result=validate_assembly(options)
    cooler={'air':'noctua-nh-u12a','aio':'arctic-liquid-freezer-iii-360',
            'loop':'custom-loop-360-reference'}[kind]
    result.update(loop_components_mode='reference',loop_fittings={},radiator_model='',radiator_fan_model='',radiator_fan_layout='single',
        secondary_radiator_model='',secondary_radiator_fan_model='',secondary_radiator_fan_layout='single',
        case_model='corsair-5000d-airflow' if kind=='air' else 'hyte-y70',
        cooler_model=cooler,cooler_mount='top',gpu_waterblock=kind=='loop',
        psu_model='corsair-rm1000x-2024',
        storage=[dict(model_id='samsung-990-pro-2tb',count=1)],
        expansion_cards=[],cables_enabled=True,fan_motion='demo',fan_animation=True,
        case_fans=[dict(model='arctic-p12-pwm',mount=mount,count=count,direction=direction)
                   for mount,count,direction in (('side',3,'intake'),('rear',1,'exhaust'))])
    if kind=='air':
        result['case_fans']=[dict(model='arctic-p12-pwm',mount=mount,count=count,direction=direction)
            for mount,count,direction in (('front',3,'intake'),('rear',1,'exhaust'))]
    elif kind=='loop':result['case_fans']=[dict(model='arctic-p12-pwm',mount=mount,count=count,direction=direction)
            for mount,count,direction in (('bottom',3,'intake'),('rear',1,'exhaust'))]
    return validate_assembly(result)


def fit_messages(spec,metadata):
    """Only report actual selected-part conflicts; never promise full CAD fit."""
    reasons={
        'unknown_model':'部分自选型号尚未收录，未放入模型。',
        'unknown_component_model':'部分自选型号尚未收录，未放入模型。',
        'unsupported_radiator_mount':'所选机箱安装位不支持这款冷排。',
        'radiator_exceeds_mount_plane':'冷排超出所选安装面的参考范围。',
        'radiator_occupies_mount':'冷排已占用该安装面，请移除重复的机箱风扇。',
        'unsupported_fan_mount':'所选风扇尺寸或数量超出机箱已核安装位。',
        'fans_exceed_mount_plane':'风扇超出所选安装面的参考范围。',
        'case_fan_clearance_conflict':'机箱风扇与显卡或其它已选部件的参考空间冲突，整组风扇未放入；请调整安装位或配件。',
        'unsupported_psu_form':'所选电源规格尚不适配此机箱。',
        'no_expansion_slot':'所选扩展卡没有可用插槽。',
        'expansion_slot_obstructed':'所选扩展卡没有可用插槽。',
        'low_profile_bracket_required':'机箱仅支持半高扩展卡。',
         'unknown_radiator_model':'所选冷排型号尚未收录，未强行替换。',
        'unknown_radiator_fan_model':'所选冷排风扇尚未收录。',
         'radiator_fan_size_mismatch':'风扇尺寸与冷排安装规格不同。',
        'radiator_fan_mount_requires_review':'圆框或无框风扇的冷排安装方式尚未核实，未强行装入。',
        'radiator_fan_mount_pattern_mismatch':'风扇与冷排的已核孔距不同，未强行装入。',
        'aio_radiator_is_fixed':'一体式水冷保留原厂冷排；独立冷排用于自定义回路。',
        'no_m2_slot':'所选 M.2 数量超出已核插槽。',
        'no_supported_m2_length':'所选 M.2 长度没有已核可用安装位。',
    }
    result=[]
    for group in ('cooling','auxiliary'):
        details=metadata.get(group,{})
        if group=='cooling' and details.get('loop_issues'):
            from liquid_messages046 import messages
            result.extend(messages(details))
        if 'psu_form_factor_not_supported' in details.get('warnings',()):
            result.append('所选电源规格尚不适配此机箱。')
        if details.get('outside_reference'):result.append('部分配件超出机箱参考外形，请检查安装位置。')
        for row in details.get('rejected',()):
            if group=='cooling' and row.get('kind')=='loop_component':
                from liquid_messages046 import REASONS
                result.append(REASONS.get(row.get('reason'),'部分水冷连接尚待核实。'))
            else:result.append(reasons.get(row.get('reason'),'部分自选配件未能放入当前参考装机。'))
    if metadata.get('attachments_outside_reference'):
        result.append('部分配件超出机箱参考外形，请检查安装位置。')
    if metadata.get('cooling',{}).get('mounting_issues'):
        result.append('风扇标称孔距与冷排不同，安装间隙待核。')
    if metadata.get('cooling',{}).get('connection_issues'):
        result.append('部分冷排接口位置尚未核实，对应管路未强行连接。')
    if metadata.get('auxiliary',{}).get('omitted_routes'):
        result.append('部分线缆缺少对应接口或可用路线，未强行连接。')
    for row in spec.get('checks',()):
        if row.get('state') not in ('exceeds_limit','unsupported'):continue
        if row.get('kind')=='board_form':result.append('主板规格超出机箱参考支持范围。')
        elif row.get('kind')=='cpu_socket':result.append('CPU 与所选主板插槽不同，仅作为外观参考。')
        elif row.get('kind')=='memory_type':result.append('内存代际与所选主板不同，仅作为外观参考。')
        elif row.get('kind') in ('gpu_length','gpu_mount'):result.append('显卡超出机箱参考安装限制。')
        elif row.get('kind')=='reference_model':result.append('自选型号尚未收录，继续显示已识别硬件。')
        elif row.get('kind')=='memory_slots':result.append('内存数量超出所选主板的插槽数量。')
    return list(dict.fromkeys(result))
