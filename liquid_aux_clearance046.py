"""Finite per-selected-device occupied envelopes for original loop placement.

No cable looms, collectors, I/O, timers, global caches or manufacturer CAD.
Separate storage devices/cards retain separate bounds instead of one large
box spanning their empty intervening space. Envelopes are conservative.
"""


def mesh_bounds(meshes):
    low=[float('inf')]*3;high=[float('-inf')]*3;present=False
    for mesh in meshes:
        for at in range(0,len(mesh.vertices),6):
            present=True
            for axis in range(3):
                value=mesh.vertices[at+axis]+mesh.position[axis]
                low[axis]=min(low[axis],value);high[axis]=max(high[axis],value)
    return (tuple(low),tuple(high)) if present else None


def auxiliary_bounds(meshes):
    """Actual PSU/storage/card envelopes, grouped by independent part ID."""
    groups={}
    for mesh in meshes:
        if mesh.component not in ('psu','storage','expansion'):continue
        key=(mesh.component,mesh.part_id or mesh.name)
        groups.setdefault(key,[]).append(mesh)
    result=[]
    for (component,identity),rows in groups.items():
        bounds=mesh_bounds(rows)
        if bounds:result.append(dict(part_id=identity,component=component,bounds=bounds))
    return tuple(result)


def overlaps(first,second,*,tolerance=.05):
    """Strict occupied-envelope overlap; a touching face alone is not overlap."""
    return all(min(first[1][i],second[1][i])-max(first[0][i],second[0][i])>tolerance for i in range(3))


def component_conflicts(meshes,blockers):
    """Identify selected devices obstructing this new body's actual envelope."""
    bounds=mesh_bounds(meshes)
    return tuple(row['part_id'] for row in blockers if bounds and overlaps(bounds,row['bounds']))
