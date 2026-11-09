"""Small detached per-part poses, shared by triangle, ink and click passes.

No geometry, device, clock, cached scene or I/O lives here. The host computes
physical movement plans on explicit actions; these functions only validate
bounded draw inputs and translate already-computed boxes.
"""
import math

MAX_POSED_PARTS=64
MAX_OFFSET_MM=2000.


def valid_offsets(value,known):
    """Reject the entire pose on malformed input; never partly move a group."""
    if not isinstance(value,dict) or len(value)>MAX_POSED_PARTS:return {}
    result={}
    for key,point in value.items():
        if not isinstance(key,str) or not 0<len(key)<=160 or key not in known:return {}
        if not isinstance(point,(tuple,list)) or len(point)!=3:return {}
        if any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>MAX_OFFSET_MM for v in point):return {}
        result[key]=tuple(float(v) for v in point)
    return result


def valid_hidden(value,known,*,maximum=128):
    if not isinstance(value,(tuple,list,set,frozenset)) or len(value)>maximum:return frozenset()
    if any(not isinstance(key,str) or not 0<len(key)<=160 or key not in known or key=='all' for key in value):return frozenset()
    return frozenset(value)


def hidden(mesh,parts=(),names=()):
    component=mesh.component
    return (getattr(mesh,'part_id','') in parts or component in parts
            or component=='panel' and 'case' in parts or mesh.name in names)


def offset_for(mesh,offsets):
    family='case' if mesh.component=='panel' else mesh.component
    return offsets.get(getattr(mesh,'part_id',''),offsets.get(family,(0.,0.,0.)))


def translated(box,offset):
    return tuple(tuple(point[k]+offset[k] for k in range(3)) for point in box)


def union(a,b):
    return (tuple(min(x,y) for x,y in zip(a[0],b[0])),tuple(max(x,y) for x,y in zip(a[1],b[1])))


def posed_bounds(bounds,focus,exploded,offsets,*,include_origin=False,families=None):
    """Conservative broad phase/contact box without scanning a single vertex.

    Exact-part translations have exact boxes. A partially moved family keeps
    a conservative original box plus moved sub-boxes; click narrow phase still
    tests the actual triangles. The optional original union is for a stable
    camera that can show both the socket position and the full end position.
    """
    base=bounds.get((focus,exploded))
    if base is None or not offsets:return base
    def parents(key):
        family=key.split(':',1)[0]
        return families.get(key,frozenset(('case' if family=='panel' else family,))) if families is not None else frozenset(('case' if family=='panel' else family,))
    selected_families=parents(focus)
    family=next(iter(selected_families)) if len(selected_families)==1 else ''
    direct=offsets.get(focus,offsets.get(family) if focus!='all' else None)
    if direct is not None:
        moved=translated(base,direct)
        result=union(base,moved) if include_origin else moved
        # A family translation may contain an exact-part override. Drawing
        # gives that override priority; broad phase/camera must include it too.
        if focus==family:
            for key,point in offsets.items():
                if key==focus or family not in parents(key):continue
                part=bounds.get((key,exploded))
                if part is not None:result=union(result,translated(part,point))
        return result
    result=base
    for key,point in offsets.items():
        if focus!='all' and not selected_families.intersection(parents(key)):continue
        part=bounds.get((key,exploded))
        if part is None:continue
        moved=translated(part,point)
        if not include_origin and focus!='all' and part==base:return moved
        result=union(result,moved)
    return result


def sphere(box):
    low,high=box
    return (tuple((low[k]+high[k])/2 for k in range(3)),
            max(1.,math.sqrt(sum((high[k]-low[k])**2 for k in range(3)))/2))
