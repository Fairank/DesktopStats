"""Source-backed rotor appearance metadata, separate from live fan telemetry."""
from hardware_fan_profiles_a import PROFILES as GROUP_A
from hardware_fan_profiles_b import PROFILES as GROUP_B

if GROUP_A.keys() & GROUP_B.keys():
    raise ValueError("Duplicate fan-profile identities")
PROFILES = dict(GROUP_A, **GROUP_B)


def profile_for(appearance):
    """Only the reviewed exact board can claim its fan technology."""
    if appearance.get("kind") != "gpu" or appearance.get("confidence") != "model":
        return {}
    value = PROFILES.get(appearance.get("series_id"), {})
    if value.get("model_ids") and appearance.get("id") not in value["model_ids"]:
        return {}
    return dict(label=value.get("label", ""), technology=value.get("technology", "unknown"),
                blades=value.get("blades"), source_url=value.get("source_url", ""),
                blade_counts=[fan.get('blades', value.get('blades'))
                              for fan in value.get('fans', ())],
                verified=value.get("technology", "unknown") != "unknown")
