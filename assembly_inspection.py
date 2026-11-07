"""Read-only component presentation from the app's existing cached sample.

No sensor access, background worker, file, process list or history query. A
selected GPU keeps its exact device ID; case/mainboard temperatures are never
borrowed from a CPU, GPU or a similarly named external sensor.
"""
import time

from assembly_spec import gpu_preferences
from cpu_temperature import FRESH_SECONDS as CPU_TEMPERATURE_MAX_AGE
from metrics import METRICS,display_value,numeric
from sensor_diagnostics import reading_source,unavailable_reason
from top_bar_feedback import GPU_FAN_MAX_AGE,gpu_fan_feedback
from assembly_effects import component_family

COMPONENT_LABELS = {"all":"整机", "cpu":"处理器", "gpu":"显卡", "memory":"内存",
                    "board":"主板", "case":"机箱", "cooler":"CPU 散热器", "fans":"机箱风扇",
                    "psu":"电源", "storage":"存储设备", "expansion":"扩展卡", "cables":"线缆"}
FRAME_MAX_AGE = 35.0


def mapping(value):
    return value if isinstance(value,dict) else {}


def fresh(timestamp,now,limit=FRAME_MAX_AGE):
    return numeric(timestamp) and numeric(now) and 0 <= now-timestamp < limit


def _prefs(config,component,spec):
    if component=="gpu":
        prefs=dict(gpu_preferences(config))
        prefs['gpu_target']=str(mapping(spec.get('gpu')).get('target') or prefs.get('gpu_target') or '0')
        return prefs
    prefix='ram_' if component=='memory' else 'cpu_'
    for item in mapping(config.get('top_bar')).get('items',()):
        item=mapping(item)
        if str(item.get('metric','')).startswith(prefix):
            prefs=mapping(item.get('prefs'))
            if not prefs.get('sensor_bindings'):
                return {key:prefs[key] for key in ('temperature_unit','precision') if key in prefs}
    return {}


def _static(label,value,available=True,reason=""):
    return dict(label=label,value=str(value) if available else '—',available=bool(available),reason=reason,source='')


def _metric(data,metric,prefs,now,frame_stale):
    meta=METRICS[metric];scope=meta.get('scope');device=data
    if scope=='gpus' and 'gpus' in data:
        device=mapping(mapping(data.get('gpus')).get(prefs.get('gpu_target') or '0'))
    channel=mapping(mapping(device.get('channel_status')).get(metric))
    status=mapping(device.get('device_status')) if scope=='gpus' else {}
    timestamps=mapping(device.get('metric_timestamps'))
    timestamp=channel.get('timestamp',timestamps.get(metric,mapping(data.get('metric_timestamps')).get(metric,data.get('time'))))
    limit=CPU_TEMPERATURE_MAX_AGE if metric=='cpu_temp' else FRAME_MAX_AGE
    stale=frame_stale or (bool(data) and not fresh(timestamp,now,limit))
    rejected=(status.get('state') not in (None,'available')
              or channel.get('state') not in (None,'available'))
    value,unit,digits=display_value({} if stale or rejected else data,metric,prefs)
    available=numeric(value)
    text=(f'{value:.{digits}f}'+(' '+unit if unit else '')) if available else '—'
    reason='' if available else '读数已过期' if stale else unavailable_reason(data,metric,prefs)
    return dict(metric=metric,label=meta['label'],value=text,available=available,reason=reason,
                source=reading_source(data,metric,prefs) if available else '')


def _dimensions(value,fields):
    dims=mapping(value)
    if all(numeric(dims.get(key)) and dims[key]>0 for key in fields):
        return ' × '.join(f'{dims[key]:g}' for key in fields)+' mm'
    return None


def snapshot(data,spec,config,component='all',*,now=None,scene_metadata=None):
    """Return at most six fixed rows without changing any supplied snapshot."""
    data=mapping(data);spec=mapping(spec);config=mapping(config)
    target=component
    component=component_family(component)
    component=component if component in COMPONENT_LABELS else 'all'
    target=target if component!='all' else 'all'
    details=mapping(scene_metadata);part={}
    for group in ('hardware','cooling','auxiliary'):
        part=next((row for row in mapping(details.get(group)).get('parts',())
                   if isinstance(row,dict) and row.get('id')==target),part)
    now=time.time() if now is None else now
    stale=((bool(data) and not fresh(data.get('time'),now))
           or mapping(data.get('sample_status')).get('state')=='stale')
    cpu=mapping(spec.get('cpu'));gpu=mapping(spec.get('gpu'))
    memory=mapping(spec.get('memory'));board=mapping(spec.get('board'));case=mapping(spec.get('case'))
    cpu_prefs=_prefs(config,'cpu',spec);gpu_prefs=_prefs(config,'gpu',spec)
    memory_prefs=_prefs(config,'memory',spec)
    rows=[];notes=[]
    if component=='all':
        identity=' · '.join(str(value) for value in (cpu.get('label'),gpu.get('label')) if value)
        readings=(('cpu_usage',cpu_prefs),('cpu_temp',cpu_prefs),('gpu_usage',gpu_prefs),
                  ('gpu_temp',gpu_prefs),('ram_percent',memory_prefs),('vram_percent',gpu_prefs))
        rows=[_metric(data,metric,prefs,now,stale) for metric,prefs in readings]
    elif component=='cpu':
        identity=cpu.get('label') or '处理器未识别'
        rows=[_metric(data,metric,cpu_prefs,now,stale)
              for metric in ('cpu_usage','cpu_temp','cpu_power','cpu_frequency')]
        package=mapping(mapping(cpu.get('appearance')).get('cpu_package'))
        if package:
            rows.append(_static('CPU 插槽',package.get('socket'),bool(package.get('socket'))))
            known=package.get('dimensions_status')=='primary_verified'
            size=_dimensions(package,('width_mm','length_mm')) if known else None
            rows.append(_static('封装尺寸',size,size is not None,'尺寸尚未核实，模型采用封装系列参考轮廓。'))
            notes.append('触点排列与盖板厚度为示意，不代表电气针脚图。')
    elif component=='gpu':
        identity=gpu.get('label') or '显卡未识别'
        rows=[_metric(data,metric,gpu_prefs,now,stale)
              for metric in ('gpu_usage','gpu_temp','gpu_power','gpu_clock','vram_percent')]
        fan=gpu_fan_feedback(data,gpu_prefs,stale=stale)
        card=mapping(mapping(data.get('gpus')).get(gpu_prefs['gpu_target']))
        fan_channel=mapping(mapping(card.get('channel_status')).get('gpu_fan_rpm'))
        if 'timestamp' in fan_channel and not fresh(fan_channel['timestamp'],now,GPU_FAN_MAX_AGE):
            fan=dict(fan,available=False,rpm=None)
        rows.append(dict(metric='gpu_fan_rpm',label=METRICS['gpu_fan_rpm']['label'],
            value=f"{fan['rpm']:.0f} RPM" if fan['available'] else '—',available=fan['available'],
            reason='' if fan['available'] else '风扇转速不可用，保持静止',source=fan.get('source','')))
        if fan.get('aggregate'):notes.append('风扇转速为板卡汇总读数。')
    elif component=='memory':
        identity=part.get('label') or memory.get('label') or '内存型号未识别'
        rows=[_metric(data,metric,memory_prefs,now,stale)
              for metric in ('ram_percent','ram_used_gb','ram_available_gb','ram_total_gb')]
        rows.append(_static('温度',None,False,'未提供此部件的独立传感器读数。'))
        notes.append('内存读数为整机合计。')
    elif component=='board':
        identity=board.get('label') or '主板布局示意'
        form={'atx':'ATX','micro_atx':'Micro-ATX','mini_itx':'Mini-ITX','e_atx':'E-ATX'}.get(board.get('form_factor'))
        size=_dimensions(board.get('dimensions_mm'),('width','height'))
        rows=[_static('主板规格',form,form is not None),_static('尺寸',size,size is not None)]
        rows.extend(_static(label,None,False,'未提供此部件的独立传感器读数。') for label in ('温度','功率'))
        slots=mapping(board.get('slot_counts'))
        for key,label in (('dimm','DIMM 插槽'),('m2','M.2 插槽')):
            if type(slots.get(key)) is int and slots[key]>0:rows.append(_static(label,slots[key]))
        notes.append('未提供此部件的独立传感器读数。')
        profile=mapping(board.get('model_profile'))
        if profile and profile.get('finish_status')!='photo_reviewed':
            notes.append('外观细节尚未核实，当前显示参考布局。')
    elif component=='case':
        identity=case.get('label') or '参考机箱（未识别）'
        size=_dimensions(case.get('dimensions_mm'),('width','height','depth'))
        limit=case.get('max_gpu_length_mm')
        rows=[_static('宽 × 高 × 深' if case.get('dimensions_verified') else '参考尺寸',size,size is not None),
              _static('机箱参考限值',f'{limit:g} mm' if numeric(limit) else None,numeric(limit))]
        rows.extend(_static(label,None,False,'未提供此部件的独立传感器读数。') for label in ('温度','功率'))
        io=mapping(mapping(case.get('exterior_details')).get('io'))
        usb=[]
        for key,label in (('usb_a','A'),('usb_c','C')):
            if type(io.get(key)) is int and io[key]>=0:usb.append(f'{label} × {io[key]}')
        if usb:rows.append(_static('原厂前置 USB',' · '.join(usb)))
        if type(io.get('audio')) is int and io['audio']>=0:rows.append(_static('原厂音频接口',io['audio']))
        source=case.get('selection_source')
        notes.append('手动外观' if source=='manual' else '已按机箱固件标识匹配。'
                     if source=='automatic' else '参考机箱（未识别）')
        for check in spec.get('checks',()):
            if check.get('kind')=='gpu_mount' and check.get('state')=='unsupported':
                notes.append('机箱仅支持半高扩展卡。' if check.get('reason')=='low_profile' else '机箱不支持独立显卡安装。')
            elif check.get('kind')=='gpu_length' and check.get('state')=='exceeds_limit':
                notes.append('已超出参考限值')
    else:
        from cooling_catalog import get_cooler,get_fan
        from component_catalog import get_component
        cooling=mapping(spec.get('cooling'));auxiliary=mapping(spec.get('auxiliary'))
        model_id=part.get('model_id','')
        if component=='cooler':
            model=get_cooler(model_id or cooling.get('cpu_cooler'))
            identity=part.get('label') or model.get('label') or '未选择散热器'
            size=_dimensions(model.get('dimensions_mm'),('width','height','depth'))
            rows=[_static('尺寸',size,size is not None),_metric(data,'cpu_temp',cpu_prefs,now,stale)]
            from assembly_feedback import cpu_fan_state
            feedback=cpu_fan_state(data,now=now)
            if cpu.get('telemetry_bound') is False:feedback=dict(available=False,rpm=None)
            rows.append(_static('CPU_FAN 通道',f"{feedback['rpm']:.0f} RPM" if feedback['available'] else None,feedback['available']))
            usable=mapping(details.get('cooling')).get('cpu_fan_tach_usable')
            if model:
                notes.append('CPU_FAN 是代表通道，不是每把风扇的独立测速。' if usable
                             else '水泵与风扇测速尚未匹配，实测模式保持静止。' if model.get('kind') in ('aio','custom_loop')
                             else '风扇结构或测速尚未匹配，实测模式保持静止。')
        elif component=='fans':
            groups=cooling.get('case_fans') or []
            if model_id:
                model=get_fan(model_id);identity=part.get('label') or model.get('label')
                count=1;size=f"{model['size_mm']:g} mm" if model.get('size_mm') else None
            else:
                identity='机箱风扇';count=sum(row.get('count',0) for row in groups);size=None
            rows=[_static('数量',count),_static('风扇尺寸',size,size is not None),
                  _static('实测转速',None,False,'未提供此部件的独立传感器读数。')]
            notes.append('机箱风扇尚未绑定独立测速，实测模式保持静止。')
        elif component=='psu':
            model=get_component(model_id or mapping(auxiliary.get('psu')).get('model_id')) or {}
            identity=part.get('label') or model.get('label') or '未选择电源'
            watts=model.get('capacity_w');size=_dimensions(model.get('dimensions_mm'),('length','width','height'))
            rows=[_static('额定功率',f'{watts:g} W' if numeric(watts) else None,numeric(watts)),
                  _static('尺寸',size,size is not None),_static('实际功率',None,False,'未提供此部件的独立传感器读数。')]
        elif component in ('storage','expansion'):
            selected=auxiliary.get('storage' if component=='storage' else 'expansion_cards') or []
            if model_id:
                model=get_component(model_id) or {};identity=part.get('label') or model.get('label')
                if model.get('appearance_unverified'):notes.append('外观细节尚未核实，当前显示参考布局。')
                size=_dimensions(model.get('dimensions_mm'),('length','width','height'))
                rows=[_static('尺寸',size,size is not None)]
                if numeric(model.get('capacity_gb')):rows.append(_static('容量',f"{model['capacity_gb']:g} GB"))
                rows.append(_static('接口',model.get('interface') or model.get('form_factor'),bool(model)))
            else:
                identity=COMPONENT_LABELS[component]
                rows=[_static('数量',sum(row.get('count',1) for row in selected))]
            rows.append(_static('温度',None,False,'未提供此部件的独立传感器读数。'))
            notes.append('自选设备尚未绑定对应的传感器。')
        else:
            identity=part.get('label') or '线缆'
            rows=[_static('连接状态','参考连接' if auxiliary.get('cables_enabled') else '未启用')]
            notes.append('线缆路线为参考排布，不代表检测到实际接线。')
        notes.insert(0,'自选配件模型不代表已识别的本机硬件。')
    if component=='board' and board.get('selection_source')=='manual':notes.append('自选配件模型不代表已识别的本机硬件。')
    unbound=set()
    for family,model in (('cpu',cpu),('gpu',gpu),('ram',memory)):
        if model.get('telemetry_bound') is False:
            unbound.add(family)
    for row in rows:
        metric=row.get('metric','')
        if any(metric.startswith(family+'_') for family in unbound) or 'gpu' in unbound and metric=='vram_percent':
            row.update(value='—',available=False,reason='参考型号未绑定本机传感器。',source='')
    if (component=='all' and unbound or component in ('cpu','gpu') and component in unbound
            or component=='memory' and 'ram' in unbound or component=='cooler' and 'cpu' in unbound):
        notes.append('参考型号未绑定本机传感器。')
    if part.get('kind')=='gpu_waterblock':notes.append('自选配件模型不代表已识别的本机硬件。')
    if mapping(spec.get('options')).get('fan_motion')=='demo' and mapping(spec.get('options')).get('fan_animation'):
        notes.append('参考转动（非实测）')
    if stale and component in ('all','cpu','gpu','memory','cooler'):notes.insert(0,'读数已过期')
    return dict(component=target,label=part.get('label') or COMPONENT_LABELS[component],identity=str(identity or ''),
                identity_parts=[str(value) for value in (cpu.get('label'),gpu.get('label')) if value]
                    if component=='all' else [str(identity or '')],
                rows=rows[:6],notes=notes,state='available' if any(row['available'] for row in rows) else 'unavailable')
