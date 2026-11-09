"""Detached, explicit radiator/fan choices; no discovery, geometry or clocks."""
from copy import deepcopy

LAYOUTS=('single','push_pull','none')
CHOICE_FIELDS=('radiator_model','radiator_fan_model','radiator_fan_layout',
               'secondary_radiator_model','secondary_radiator_fan_model','secondary_radiator_fan_layout')


def _one(cooler,selection,secondary=False):
    from cooling_catalog import get_fan
    prefix='secondary_' if secondary else ''
    result=deepcopy(cooler);issues=[]
    identity=selection.get(prefix+'radiator_model','')
    if identity:
        if cooler.get('kind')!='custom_loop':
            issues.append(dict(reason='aio_radiator_is_fixed',selection=prefix+'radiator_model',model_id=identity))
        else:
            from liquid_cooling_catalog044 import get_radiator
            profile=get_radiator(identity)
            if not profile:return None,[dict(reason='unknown_radiator_model',selection=prefix+'radiator_model',model_id=identity)]
            result.update(radiator_mm=deepcopy(profile['dimensions_mm']),fan_count=profile['fan_count'],
                radiator_size=profile['fan_size_mm']*profile['fan_count'],radiator_model=profile['label'],
                radiator_dimensions_verified=profile.get('dimensions_verified') is True,
                _radiator_profile=profile)
            # An independently bought radiator does not include the old cooler's
            # branded fans. An empty fan choice is an explicit neutral reference.
            for key in ('bundled_fan_reference','fan_models','fan_sizes','fan_depths','fan_relative_directions','fan_placements','relative_rotation_verified'):
                result.pop(key,None)
            result.update(fan_family='stock-reference',fan_outer_ring=False,frameless_fan=False,
                fan_dimensions_verified=False,fan_power_connector_verified=False)
            result.update(fan_model='',fan_reference_mm=profile['fan_size_mm'],
                fan_reference_depth_mm=25,fan_reference_rgb=False,fan_reference_blades=7,
                fan_blade_count_verified=False,_neutral_radiator_fan=True)
            result['sources']=list(dict.fromkeys([*result['sources'],*profile['sources']]))
    layout=selection.get(prefix+'radiator_fan_layout','single')
    if type(layout) is not str or layout not in LAYOUTS:
        return None,[dict(reason='invalid_radiator_fan_layout',selection=prefix+'radiator_fan_layout')]
    result['_radiator_fan_layout']=layout
    fan_id=selection.get(prefix+'radiator_fan_model','')
    if fan_id and layout!='none':
        fan=get_fan(fan_id)
        if not fan:return None,[dict(reason='unknown_radiator_fan_model',selection=prefix+'radiator_fan_model',model_id=fan_id)]
        expected=(result.get('_radiator_profile') or {}).get('fan_size_mm',result.get('fan_reference_mm',120))
        if fan['size_mm']!=expected:
            return None,[dict(reason='radiator_fan_size_mismatch',selection=prefix+'radiator_fan_model',
                model_id=fan_id,expected_mm=expected,selected_mm=fan['size_mm'])]
        if fan.get('frame')=='round' or fan.get('frameless'):
            return None,[dict(reason='radiator_fan_mount_requires_review',selection=prefix+'radiator_fan_model',model_id=fan_id)]
        pitch=(result.get('_radiator_profile') or {}).get('fan_mount_pitch_mm')
        if pitch and fan.get('mount_pitch_verified') and abs(pitch-fan['mount_pitch_mm'])>.05:
            issues.append(dict(reason='radiator_fan_mount_spacing_requires_review',severity='review',
                selection=prefix+'radiator_fan_model',model_id=fan_id,radiator_pitch_mm=pitch,fan_pitch_mm=fan['mount_pitch_mm']))
        result['fan_model']=fan_id;result['_neutral_radiator_fan']=False
        result['sources']=list(dict.fromkeys([*result['sources'],*fan['sources']]))
    return result,issues


def resolve_liquid_choices(cooler,selection):
    """Resolve each physical radiator separately; never mutate original facts.

    A primary failure omits the liquid cooler; a secondary failure preserves the
    CPU loop and the original GPU air cooler. Sealed AIO radiators stay original.
    """
    primary,issues=_one(cooler,selection)
    secondary,extra=_one(cooler,selection,True) if cooler.get('kind')=='custom_loop' and selection.get('gpu_waterblock') is True else (deepcopy(primary),[])
    return primary,secondary,[*issues,*extra]
