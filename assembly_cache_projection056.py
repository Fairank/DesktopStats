"""Pure cache keys: manual reference shape is independent of host name text.

Only CPU/GPU rows explicitly unbound from telemetry omit detected_label in a
cache comparison. All actual input/UI data and every other field are retained.
No geometry, Qt, hardware, file, timer or process work occurs in this module.
"""


def cache_key_input(value, fields=None):
    """Return a shallow key projection without changing any supplied row."""
    result=dict(value) if fields is None else {key:value[key]for key in fields if key in value}
    for family in ('cpu','gpu'):
        row=result.get(family)
        if isinstance(row,dict) and row.get('telemetry_bound')is False and 'detected_label'in row:
            result[family]={key:item for key,item in row.items()if key!='detected_label'}
    return result


def current_reference_metadata(profiles, specification):
    """Refresh the one ignored field in an already copied profile payload.

    Profile comparison preserves every other field. A reused shape therefore
    needs only this host metadata copied from the current original spec. An
    absent current field stays absent rather than inheriting an older value.
    Neither the profile snapshot nor any of its shape arrays is mutated.
    """
    result=dict(profiles)
    for family in ('cpu','gpu'):
        current=specification.get(family);cached=result.get(family)
        if isinstance(current,dict) and current.get('telemetry_bound')is False and isinstance(cached,dict):
            row=dict(cached)
            if 'detected_label'in current:row['detected_label']=current['detected_label']
            else:row.pop('detected_label',None)
            result[family]=row
    return result
