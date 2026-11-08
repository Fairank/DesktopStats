"""Selected loop reference facts. No telemetry, clock, hardware or Qt imports."""
KINDS=frozenset(('cpu_block','pump','reservoir','pump_reservoir','fitting','tubing'))

def _row(label,value=None,reason=''):
    return dict(label=label,value=str(value) if value is not None else '—',
                available=value is not None,reason=reason if value is None else '',source='')

def _size(value):
    if not isinstance(value,dict):return None
    numbers=[value.get(k) for k in ('width','height','depth')]
    if any(type(n) not in (int,float) or n<=0 for n in numbers):return None
    return ' × '.join(f'{n:g}' for n in numbers)+' mm'

def _ports(model):
    ports=model.get('ports') or []
    threads=list(dict.fromkeys(p['thread'] for p in ports if p.get('thread')))
    number=model.get('ports_count')
    if number is None:return None
    return str(number)+(' · '+' / '.join(threads) if threads else '')

def describe(part,model):
    """At most six facts; never substitute CPU heat for coolant or pump RPM."""
    kind=part['kind'];notes=['自选配件模型不代表已识别的本机硬件。']
    if not model:
        return dict(identity=part.get('label') or '部件型号不可用',
            rows=[_row('型号',reason='对应扩展包未安装或型号已移除。')],notes=notes)
    rows=[]
    size=_size(model.get('dimensions_mm')) if model.get('dimensions_verified') else None
    if size:rows.append(_row('宽 × 高 × 深',size))
    elif model.get('body_dimensions_verified'):
        rows.append(_row('已核本体尺寸',_size(model.get('body_dimensions_mm'))))
        notes.append('本体尺寸不含安装支架；整体包络尚未核实。')
    else:rows.append(_row('已核整体尺寸',reason='整体尺寸尚未核实，模型包络为参考。'))
    if kind=='cpu_block':
        sockets=model.get('supported_sockets') if model.get('socket_support_verified') else None
        rows.append(_row('支持插槽',' / '.join(sockets) if sockets else None,'原厂插槽支持尚未核实。'))
    if kind in ('pump','reservoir','pump_reservoir'):
        motor=('含电机' if model.get('contains_motor') else '另需电机' if model.get('requires_motor') else '不含电机')
        rows.append(_row('电机',motor+(' · '+model['motor_type'] if model.get('motor_type') else '')))
    if kind=='tubing':
        inner,outer=model.get('tube_inner_mm'),model.get('tube_outer_mm')
        rows.append(_row('内径 / 外径',f'{inner:g} / {outer:g} mm' if inner is not None and outer is not None else None,
                         '管材内外径尚未完整核实。'))
        length=model.get('length_mm') if model.get('length_verified') else None
        rows.append(_row('原厂管材长度',f'{length:g} mm' if length is not None else None,'供货长度尚未核实。'))
        if part.get('length_mm') is not None:rows.append(_row('参考走管长度',f"{part['length_mm']:g} mm"))
        rows.append(_row('管材',model.get('material')))
    else:
        rows.append(_row('接口',_ports(model),'接口总数或螺纹尚未完整核实。'))
        if kind=='fitting':
            inner,outer=model.get('tube_inner_mm'),model.get('tube_outer_mm')
            if outer is not None:
                rows.append(_row('适用管径',(f'{inner:g} / ' if inner is not None else '')+f'{outer:g} mm'))
            rows.append(_row('连接验证','参考连接',''))
        if kind in ('pump','pump_reservoir'):
            rows.append(_row('水泵转速',reason='未提供此部件的独立传感器读数。'))
        if kind in ('cpu_block','reservoir','pump_reservoir'):
            rows.append(_row('水温',reason='未提供此部件的独立传感器读数。'))
        if kind in ('cpu_block','pump','pump_reservoir'):
            rows.append(_row('流量',reason='未提供此部件的独立传感器读数。'))
    notes.append('接口位置、走管和安装支架为参考，未验证为可制造装配。')
    if kind in ('cpu_block','pump','reservoir','pump_reservoir'):
        notes.append('水冷部件未绑定独立传感器，不借用 CPU 温度或 CPU_FAN 转速。')
    return dict(identity=model['label'],rows=rows[:6],notes=notes)
