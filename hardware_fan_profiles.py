"""Source-backed rotor appearance metadata, separate from live fan telemetry."""
from hardware_fan_profiles_a import PROFILES as GROUP_A
from hardware_fan_profiles_b import PROFILES as GROUP_B
from hardware_variants import base_identity,READY
from hardware_variant_art import ART
import hardware_board_details_a as board_a
import hardware_board_details_b as board_b
import hardware_board_details_c as board_c

if GROUP_A.keys() & GROUP_B.keys():
    raise ValueError("Duplicate fan-profile identities")
PROFILES = dict(GROUP_A, **GROUP_B)
for package in (board_a,board_b,board_c):
    for identity,update in getattr(package,'FAN_UPDATES',{}).items():
        original=PROFILES.get(identity)
        guard=update.get('model_ids') or getattr(package,'PROFILES',{}).get(identity,{}).get('model_ids')
        if original is None or tuple(guard or ())!=tuple(original.get('model_ids',())):
            raise ValueError('Fan update must refer to the same exact representative')
        allowed=('blades','shape','hub_ratio','hub_tone','tone','outer_ring','group_size','hub_shape','fans',
                 'technology','label','source_url','notes','evidence','count_status')
        PROFILES[identity]=dict(original,**{key:update[key] for key in allowed if key in update})


def profile_for(appearance):
    """Only the reviewed exact board can claim its fan technology."""
    if appearance.get("kind") != "gpu" or appearance.get("confidence") != "model":
        return {}
    value = PROFILES.get(appearance.get("series_id"), {})
    if value.get("model_ids") and base_identity(appearance.get("id")) not in value["model_ids"]:
        return {}
    if appearance.get('id') in ART:
        value=dict(value,**ART[appearance['id']].get('fan_profile',{}))
    if appearance.get('id') in READY:
        value=dict(value,source_url=READY[appearance['id']]['source_urls'][0])
    counts=[fan.get('blades', value.get('blades')) for fan in value.get('fans', ())] or [value.get('blades')]
    shapes=[fan.get('shape',value.get('shape')) for fan in value.get('fans',())] or [value.get('shape')]
    ready=all(type(count) is int and count>0 for count in counts) and all(shape!='neutral' for shape in shapes)
    return dict(label=value.get("label", ""), technology=value.get("technology", "unknown"),
                blades=value.get("blades"), source_url=value.get("source_url", ""),
                blade_counts=[fan.get('blades', value.get('blades'))
                              for fan in value.get('fans', ())],
                render_ready=ready, artwork_status=('not_applicable' if appearance.get('fan_count')==0
                                                    else 'reviewed' if ready else 'pending'),
                verified=value.get("technology", "unknown") != "unknown")
