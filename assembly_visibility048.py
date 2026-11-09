"""Static inspection-only visibility of exterior skins; no physical changes.

Names are the existing renderer's declared case/panel batches. Unknown case
batches remain visible. A cutaway is an illustration aid, not a claim that a
retail panel, passive cooling wall or PSU cover can be removed during operation.
Structural rails, motherboard trays, floors, feet and all selected hardware stay.
The far-side casing and rear I/O wall retain the case's depth and enclosure.
"""

_CASE_SKINS = frozenset((
    'front-panel', 'top-panel', 'top-glass',
    'case-origami-reference-folded-tabs',
))
# This pre-existing stand uses the panel category for transparency, but is a
# support rather than a removable cover. Keep it and any future unknown casing.
_PANEL_SUPPORTS = frozenset(('translucent-stand',))
_PSU_COVERS = frozenset(('psu-shroud','top-psu-shroud','rear-chamber-shroud',
    'helios-psu-front-cover','helios-psu-rear-cover','helios-psu-side-window'))


def mesh_visible(mesh, inspection_cutaway=False, show_psu=False):
    """One shared rule for triangle, ink and click passes across all styles."""
    component = getattr(mesh, 'component', '')
    name = getattr(mesh, 'name', '')
    # Keep the real PSU and cables present. Its real enclosure controls
    # occlusion; open frames never acquire an invented cover or hidden PSU.
    if component=='case' and name in _PSU_COVERS:return show_psu is not True
    if inspection_cutaway is not True:
        return True
    if component == 'panel':
        return name in _PANEL_SUPPORTS
    return component != 'case' or name not in _CASE_SKINS


def hidden_mesh_ids(meshes):
    """Compute once with the existing scene upload; release with that renderer."""
    return frozenset(id(mesh) for mesh in meshes if not mesh_visible(mesh, True))


def psu_cover_mesh_ids(meshes):
    """Once-upload integer IDs only; no retained Mesh references or clock."""
    return frozenset(id(mesh) for mesh in meshes if getattr(mesh,'component','')=='case' and getattr(mesh,'name','') in _PSU_COVERS)
