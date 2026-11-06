"""Explicitly implemented structural variants, separate from frequency aliases.

Each recipe needs reviewed exact-product imagery and its own changed structure.
Keeping a version in the inventory alone never enables this registry.
"""
_SUPRIM_BLACKWELL = dict(recipe='suprim_blackwell', shroud_tone='silver', slot_width=None,
    host_interface=dict(bus='pcie',generation=5,lanes=16,connector_shape='pcie_standard'),
    fan_profile=dict(technology='stormforce', label='STORMFORCE 七叶风扇', blades=7,
                     shape='claw', hub_ratio=.29, hub_tone='silver', group_size=1, outer_ring=False, tone='dark'))

ART = {'msi-suprim-5090-32g-soc': dict(_SUPRIM_BLACKWELL),
       'msi-suprim-5090-32g-oc': dict(_SUPRIM_BLACKWELL)}
