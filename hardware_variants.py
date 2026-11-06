"""Exact versions match only with reviewed shared art or an explicit recipe.

Other coolers, rear-power revisions and unknown versions stay listed as pending,
never a silent colour/frequency suffix guess. No I/O or discovery.
"""
import copy
import re
import hardware_board_details_a as group_a
import hardware_board_details_b as group_b
import hardware_board_details_c as group_c
from hardware_variant_art import ART

PACKAGES=(group_a,group_b,group_c)
FAMILIES=tuple(row for package in PACKAGES for row in getattr(package,'VERSION_FAMILIES',()))
RECORDS={}
for family in FAMILIES:
    for item in family.get('variants',()):
        identity=item.get('model_id')
        if not isinstance(identity,str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,95}',identity) or identity in RECORDS:
            raise ValueError('Invalid or duplicate exterior version identity')
        aliases=item.get('aliases',())
        if not aliases or any(not isinstance(alias,str) or not alias.strip() or len(alias)>256 for alias in aliases):
            raise ValueError('Version requires bounded complete SKU aliases')
        RECORDS[identity]=dict(item,series_id=family['series_id'],base_model_id=family['base_model_id'],
                               kind=family.get('kind','gpu'))
if set(ART)-set(RECORDS):raise ValueError('A structural recipe needs an exact reviewed version record')
READY={key:row for key,row in RECORDS.items() if row.get('visual_relation')=='shared' or key in ART}


def base_identity(identity):
    return READY[identity]['base_model_id'] if identity in READY else identity


def extend_gpu_catalog(rows):
    by_id={row[0]:row for row in rows}
    extra=[]
    for key,version in READY.items():
        if version['kind']!='gpu':continue
        base=by_id.get(version['base_model_id'])
        if base is None or key in by_id:
            raise ValueError('Version base is absent or version duplicates a catalog entry')
        source=next((url for url in version.get('source_urls',()) if url.startswith('https://')),None)
        if not source:raise ValueError('Shared exterior version needs a source')
        extra.append((key,base[1],base[2],base[3],version['label'],*base[5:8],source,tuple(version['aliases'])))
    return tuple(rows)+tuple(extra)


def extend_memory_catalog(rows):
    by_id={row['id']:row for row in rows}
    extra=[]
    for key,version in READY.items():
        if version['kind']!='memory':continue
        base=by_id.get(version['base_model_id'])
        if base is None or key in by_id:raise ValueError('Invalid memory version base')
        row=dict(base,id=key,label=version['label'],aliases=tuple(version['aliases']))
        if version.get('source_urls'):row['source_url']=version['source_urls'][0]
        extra.append(row)
    return tuple(rows)+tuple(extra)


def exterior_row(identity,source):
    """Return only an explicitly supported version's own documented overrides."""
    version=READY.get(identity)
    if not version:return source
    if version['base_model_id'] not in source.get('model_ids',()):return {}
    result=copy.deepcopy(source)
    result.update(version.get('overrides',{}))
    art=ART.get(identity,{})
    if art:
        result.update({key:value for key,value in art.items() if key!='fan_profile'})
        result['fan_profile']=dict(result.get('fan_profile',{}),**art.get('fan_profile',{}))
    result['model_ids']=(identity,)
    result['source_urls']=tuple(version.get('source_urls',()))
    return result
