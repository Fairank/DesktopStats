"""Bounded static reference-view ink for new loop component triangle meshes.

Only existing triangle edges are selected. Six axis-aligned reference views
keep a few real longitudinal edges on smooth tubes/sleeves; these are static
illustration candidates, not per-frame camera silhouettes or extra geometry.
Existing crease/boundary ink remains the primary input. No retained cache,
graphics, sensors, timers, catalog imports or manufacturer texture data.
"""
import math

MAX_REFERENCE_EDGES = 512


def _point_key(point):
    return tuple(round(value, 7) for value in point)


def _edge_key(edge):
    return tuple(sorted((_point_key(edge[0]), _point_key(edge[1]))))


def _normal(a, b, c):
    u = tuple(b[i]-a[i] for i in range(3))
    v = tuple(c[i]-a[i] for i in range(3))
    n = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
    length = math.sqrt(sum(value*value for value in n))
    return tuple(value/length for value in n) if length > 1e-12 else None


def _reference_candidates(vertices):
    adjacent = {}
    for start in range(0, len(vertices)-17, 18):
        points = [tuple(vertices[start+offset:start+offset+3]) for offset in (0, 6, 12)]
        if not all(math.isfinite(value) for point in points for value in point):
            continue
        normal = _normal(*points)
        if normal is None:
            continue
        for a, b in zip(points, points[1:]+points[:1]):
            key = _edge_key((a, b))
            if key[0] == key[1]:
                continue
            row = adjacent.get(key)
            if row is None:
                row = [(a, b), []]
                adjacent[key] = row
            # Geometric face normals, rather than the mesh's interpolated
            # shading normals, ensure flat triangulation diagonals stay absent.
            row[1].append(normal)
    values = []
    for edge, normals in adjacent.values():
        if len(normals) < 2:
            # Boundary ink is already supplied by the existing crease pass.
            continue
        first = normals[0]
        if all(abs(sum(a*b for a, b in zip(first, other))) >= 1-1e-8 for other in normals[1:]):
            continue
        # +/- axis views have the same sign-crossing condition. A smooth
        # cylinder usually contributes four outer and four inner meridians.
        if any(min(n[axis] for n in normals) < -1e-9 and max(n[axis] for n in normals) > 1e-9 for axis in range(3)):
            values.append(edge)
    return values


def augment_line_edges(vertices, crease_edges, limit=MAX_REFERENCE_EDGES):
    """Union real reference-view edges with existing ink under the mesh cap.

    Normal-sized models retain every supplied crease/boundary. If the union
    exceeds the established cap, keep at most 64 longest new contours and fill
    remaining slots with the longest existing ink. Output order stays stable.
    """
    if type(limit) is not int or limit <= 0:
        return ()
    limit = min(limit, MAX_REFERENCE_EDGES)
    existing = []
    seen = set()
    for edge in crease_edges:
        key = _edge_key(edge)
        if key[0] != key[1] and key not in seen:
            seen.add(key)
            existing.append(edge)
    additional = []
    for edge in _reference_candidates(vertices):
        key = _edge_key(edge)
        if key not in seen:
            seen.add(key)
            additional.append(edge)
    if len(existing)+len(additional) <= limit:
        return tuple(existing+additional)
    length = lambda edge: sum((a-b)**2 for a, b in zip(*edge))
    fresh = sorted(range(len(additional)), key=lambda i: (-length(additional[i]), i))[:min(64, limit//4)]
    old = sorted(range(len(existing)), key=lambda i: (-length(existing[i]), i))[:limit-len(fresh)]
    old, fresh = set(old), set(fresh)
    return tuple(edge for i, edge in enumerate(existing) if i in old)+tuple(edge for i, edge in enumerate(additional) if i in fresh)
