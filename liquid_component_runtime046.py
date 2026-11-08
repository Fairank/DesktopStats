"""Selected independent loop data only; no author catalogs, probing or clock."""

PART_KINDS=('cpu_block','pump','reservoir','pump_reservoir','fitting','tubing')

def choices(part_kind):
    if part_kind not in PART_KINDS:return []
    from hardware_packs import runtime_store
    return [dict(id=r['id'],label=r['label'],brand=r['vendor'],series=r['series'],pack_id=r['pack_id'],**r['selector'])
            for r in runtime_store().choices('loop') if r['selector']['part_kind']==part_kind]

def grouped_choices():
    """One detached index pass for all pickers; never read product payloads."""
    from hardware_packs import runtime_store
    result={kind:[] for kind in PART_KINDS}
    for row in runtime_store().choices('loop'):
        result[row['selector']['part_kind']].append(dict(id=row['id'],label=row['label'],brand=row['vendor'],
            series=row['series'],pack_id=row['pack_id'],**row['selector']))
    return result

def get_component(part_kind,identity):
    if part_kind not in PART_KINDS or not identity:return {}
    from hardware_packs import runtime_store
    row=runtime_store().get_model('loop',identity)
    reference=row.get('reference') if row else None
    # PackStore already returns a detached model. Copying its reference again
    # doubles the same selected-record traversal without adding isolation.
    return reference if reference and reference['part_kind']==part_kind else {}

def envelope(row):
    actual=row['dimensions_mm'];reference=row['reference_envelope_mm']
    return {key:actual[key] if actual[key] is not None else reference[key] for key in ('width','height','depth')}
