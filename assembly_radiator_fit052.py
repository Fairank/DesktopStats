"""Source-declared radiator limits and fixed rail selection, construction only.

Model heights are reference geometry. These checks do not certify hidden VRM,
I/O covers, hoses or manufacturing tolerances and never reposition memory.
"""
from copy import deepcopy
import math


def _number(value):
    return type(value) in (int,float) and math.isfinite(value) and value>0


def _size(fan):
    value=fan.get('size_mm') if isinstance(fan,dict) else None
    return f'{value:g}' if _number(value) else ''


def _module_height(row):
    """A PCB height cannot establish the complete module's top clearance.

    Unmarked legacy synthetic specifications retain their explicit reference
    height contract. Production identities always carry the PCB marker and
    exact complete-envelope facts, including truthful unknown values.
    """
    if not isinstance(row,dict):return None
    value=row.get('total_height_mm')
    if _number(value):return value
    if row.get('height_mm_describes')=='pcb':return None
    value=row.get('height_mm')
    return value if _number(value) else None


def radiator_planes(anchors,planes,mount,fan):
    """Only radiators select these source rails; ordinary case fans retain theirs."""
    if mount!='top':return planes
    choices=anchors.get('case_top_radiator_planes_by_size')
    selected=choices.get(_size(fan)) if isinstance(choices,dict) else None
    if not isinstance(selected,dict):return planes
    result=dict(planes);result['top']=deepcopy(selected)
    return result


def check(anchors,spec,cooler,mount,fan):
    declared=anchors.get('case_radiator_constraints')
    group=declared.get(mount) if isinstance(declared,dict) else None
    choices=group.get('by_fan_size_mm') if isinstance(group,dict) else None
    rule=choices.get(_size(fan)) if isinstance(choices,dict) else None
    if not isinstance(rule,dict):return None
    result=dict(mount=mount,fan_size_mm=fan.get('size_mm'),source=rule.get('source_url',group.get('source_url','')),
        state='reference_limits_checked',reference_only=True,full_fit_verified=False,
        motherboard_vrm_and_io_height_checked=False,model_height_is_manufacturing_measurement=False,
        source_layout=group.get('layout',''),rejected=False)
    if rule.get('supported') is False:
        return dict(result,state='rejected',rejected=True,reason='unsupported_radiator_size_for_case')
    radiator=cooler.get('radiator_mm') or {};width=radiator.get('width');maximum=rule.get('max_width_mm')
    if _number(maximum):
        result.update(max_width_mm=maximum,radiator_width_mm=width)
        if not _number(width):result['state']='reference_dimension_unknown'
        elif width>maximum+1e-7:
            return dict(result,state='rejected',rejected=True,reason='radiator_width_exceeds_case_limit')
    limit=rule.get('ram_height_limit_mm')
    if _number(limit):
        memory=spec.get('memory') or {};modules=memory.get('modules')
        values=[];unknown=0;tolerance_overlap=False;states=[]
        if isinstance(modules,(tuple,list)) and modules:
            for row in modules[:256]:
                height=_module_height(row)
                if _number(height):
                    values.append(height)
                    states.append(row.get('total_height_status','legacy_reference'))
                    tolerance=row.get('total_height_tolerance_mm')
                    if _number(tolerance) and height<=limit and height+tolerance>limit:tolerance_overlap=True
                else:unknown+=1
            populated=memory.get('count')
            if type(populated) is int and populated>len(modules):unknown+=min(populated,256)-len(modules)
        elif type(memory.get('count')) is int and memory['count']>0:
            height=_module_height(memory)
            if _number(height):values.append(height)
            else:unknown=memory['count']
        result.update(ram_height_limit_mm=limit,model_ram_heights_mm=tuple(values),unknown_ram_heights=unknown,
            model_ram_height_states=tuple(states),nominal_height_tolerance_overlaps_limit=tolerance_overlap)
        if values and max(values)>limit+1e-7:
            return dict(result,state='rejected',rejected=True,reason='radiator_memory_height_exceeds_case_limit')
        if unknown:result['state']='reference_dimension_unknown'
        elif tolerance_overlap:result['state']='reference_tolerance_overlap'
    elif rule.get('ram_height_restriction_applies') is False:
        result['source_lists_no_ram_height_restriction']=True
    return result
