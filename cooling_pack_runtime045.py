"""Small optional picker indexes; never imports the authoring catalogs."""
def bundled_fan(cooler):
    from cooling_catalog import _FAN_BY_ID
    from copy import deepcopy
    row=cooler.get('bundled_fan_reference')
    if row and row['id']==cooler.get('fan_model') and row['id'] not in _FAN_BY_ID:
        # Factory descriptor is already validated with the selected cooler;
        # avoid reading a second optional pack or borrowing a different revision.
        return deepcopy(row)
    return None


def radiator_choices():
    from hardware_packs import runtime_store
    from liquid_cooling_catalog044 import IDS
    return [dict(id=row['id'],label=row['label'],brand=row['vendor'],series=row['series'],pack_id=row['pack_id'],
                 **row['selector']) for row in runtime_store().choices('radiator') if row['id'] not in IDS]
