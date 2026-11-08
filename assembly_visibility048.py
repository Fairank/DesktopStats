"""Static inspection-only visibility of exterior skins; no physical changes.

Names are the existing renderer's declared case/panel batches. Unknown case
batches remain visible. A cutaway is an illustration aid, not a claim that a
retail panel, passive cooling wall or PSU cover can be removed during operation.
Structural rails, motherboard trays, floors, feet and all selected hardware stay.
"""

_CASE_SKINS = frozenset((
    'case-right', 'case-back', 'front-panel', 'top-panel', 'top-glass',
    'psu-shroud', 'top-psu-shroud', 'rear-chamber-shroud',
    'case-origami-reference-folded-tabs',
))
# This pre-existing stand uses the panel category for transparency, but is a
# support rather than a removable cover. Keep it and any future unknown casing.
_PANEL_SUPPORTS = frozenset(('translucent-stand',))


def mesh_visible(mesh, inspection_cutaway=False):
    """One shared rule for triangle, ink and click passes across all styles."""
    if inspection_cutaway is not True:
        return True
    component = getattr(mesh, 'component', '')
    name = getattr(mesh, 'name', '')
    if component == 'panel':
        return name in _PANEL_SUPPORTS
    return component != 'case' or name not in _CASE_SKINS


def hidden_mesh_ids(meshes):
    """Compute once with the existing scene upload; release with that renderer."""
    return frozenset(id(mesh) for mesh in meshes if not mesh_visible(mesh, True))
