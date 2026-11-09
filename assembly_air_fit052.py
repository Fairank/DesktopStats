"""Construction-only manufacturer air-cooler height conditions, not CAD fit."""
import math


def _positive(value):return type(value) in (int,float) and math.isfinite(value) and value>0


def check(anchors,spec,case,cooler):
    rule=anchors.get('case_air_cooler_constraints')
    if not isinstance(rule,dict):return None
    identity=rule.get('case_id');selected=spec.get('case')
    row=dict(case_id=identity,model_id=cooler.get('id'),source=rule.get('source_url',''),
        reference_only=True,full_fit_verified=False,positions_verified=False,rejected=False)
    if (not isinstance(identity,str) or not isinstance(case,dict) or case.get('id')!=identity
            or not isinstance(selected,dict) or selected.get('id')!=identity):
        return dict(row,state='reference_unavailable',rejected=True,reason='air_cooler_case_reference_unavailable')
    limit=rule.get('max_height_mm');height=(cooler.get('dimensions_mm') or {}).get('height')
    row.update(source_max_height_mm=limit,selected_nominal_height_mm=height)
    if rule.get('source_conflict') is True:
        row.update(source_conflict=True,manufacturer_values_mm=rule.get('manufacturer_values_mm'),
            effective_limit_policy=rule.get('effective_limit_policy'))
    if not _positive(limit) or not _positive(height):return dict(row,state='source_or_selected_height_unknown')
    if height>limit:return dict(row,state='rejected',rejected=True,
        reason='air_cooler_height_source_conflict' if row.get('source_conflict') else 'air_cooler_height_exceeds_case')
    return dict(row,state='nominal_boundary_no_tolerance' if height==limit else 'nominal_height_checked')
