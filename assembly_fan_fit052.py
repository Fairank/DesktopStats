"""Exact case fan capacity conditions, evaluated only during construction.

Manufacturer capacities and unknown selected dimensions stay distinct from
our reference placement. No I/O, telemetry, clocks or geometry are involved.
"""
import math


def _positive(value):
    return type(value) in (int,float) and math.isfinite(value) and value>0


def check(anchors,spec,case,mount,model,count):
    constraints=anchors.get('case_fan_constraints')
    rule=constraints.get(mount) if isinstance(constraints,dict) else None
    if not isinstance(rule,dict):return None
    identity=rule.get('case_id');selected=spec.get('case')
    row=dict(mount=mount,case_id=identity,source=rule.get('source_url',rule.get('source','')),
        source_pdf_page=rule.get('source_manual_pdf_page',rule.get('source_pdf_page')),reference_only=True,
        full_fit_verified=False,positions_verified=False,rejected=False,state='source_capacity_checked')
    if (not isinstance(identity,str) or not identity or not isinstance(case,dict) or case.get('id')!=identity
            or not isinstance(selected,dict) or selected.get('id')!=identity):
        return dict(row,rejected=True,state='reference_unavailable',reason='case_fan_mount_reference_unavailable')
    capacities=rule.get('max_count_by_size_mm');size=model.get('size_mm')
    maximum=capacities.get(f'{size:g}') if isinstance(capacities,dict) and _positive(size) else None
    if type(maximum) is int and 0<=maximum<=4:
        row.update(source_max_count=maximum,fan_size_mm=size)
        if count>maximum:return dict(row,rejected=True,state='rejected',reason='unsupported_fan_mount')
    maximum_depth=rule.get('max_depth_mm')
    if _positive(maximum_depth):
        depth=model.get('depth_mm')
        row.update(source_max_depth_mm=maximum_depth,selected_fan_depth_mm=depth)
        if not _positive(depth):row['state']='selected_fan_dimension_unknown'
        elif depth>maximum_depth:
            return dict(row,rejected=True,state='rejected',reason='case_fan_depth_limit')
    threshold=rule.get('psu_length_threshold_mm');limited=rule.get('max_count_above_psu_length_threshold')
    if not (_positive(threshold) and type(limited) is int and 0<=limited<=4):return row
    from component_catalog import get_component
    auxiliary=spec.get('auxiliary');psu=auxiliary.get('psu') if isinstance(auxiliary,dict) else None
    model_id=psu.get('model_id') if isinstance(psu,dict) else None
    selected_psu=get_component(model_id) if isinstance(model_id,str) else None
    dims=selected_psu.get('dimensions_mm') if isinstance(selected_psu,dict) else None
    length=dims.get('length') if isinstance(dims,dict) and selected_psu.get('category')=='psu' else None
    row.update(psu_model_id=model_id,psu_length_mm=length,psu_length_threshold_mm=threshold,
        max_count_above_psu_length_threshold=limited)
    if not _positive(length):return dict(row,state='selected_psu_dimension_unknown')
    case_maximum=rule.get('source_max_psu_length_mm')
    if _positive(case_maximum):
        row.update(source_max_psu_length_mm=case_maximum,selected_psu_exceeds_case_length=length>case_maximum)
    if length>threshold and count>limited:
        return dict(row,rejected=True,state='rejected',reason='case_fan_psu_length_limit')
    return row
