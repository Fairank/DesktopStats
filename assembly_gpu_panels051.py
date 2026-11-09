"""Static GPU source-paint partition; no coplanar colour-face overlays.

The reviewed source polygons already establish painter order. This partitions
those same regions rather than inventing cuts, thickness offsets or new trim.
Concave later paint is subtracted as its real ear-clipped triangles. Physical
fan apertures cut every colour region by default; documented fixed-frame layers
can cross a fan bay. No render-time boolean or retained cache.
"""

MAX_CUTTERS=128
MAX_FRAGMENTS=2048
MAX_PANEL_TRIANGLES=8192


def _convex_cutout(poly):
    """Accept only one finite, simple convex source cutout without a close point.

    The existing half-plane subtractor requires convex cutters. A generous
    arithmetic domain (not a manufactured GPU size) bounds its cross products.
    Every vertex must lie on/left of every CCW edge; local-turn checks alone
    would miss a self-intersecting pentagram. Equal points/zero edges are invalid.
    """
    from math import isfinite
    if (not isinstance(poly,(tuple,list)) or not 3<=len(poly)<=64
            or not all(isinstance(p,(tuple,list)) and len(p)==2
                and all(type(v) in (int,float) and -1e6<=v<=1e6 and isfinite(v) for v in p) for p in poly)):
        raise ValueError('GPU source cutout requires bounded finite polygon points')
    points=tuple(tuple(p) for p in poly)
    if len(set(points))!=len(points):
        raise ValueError('GPU source cutout has repeated point or zero edge')
    from assembly_detail import _area
    area=_area(points)
    if not isfinite(area) or abs(area)<1e-8:
        raise ValueError('Invalid GPU source cutout polygon area')
    if area<0:points=tuple(reversed(points))
    for a,b in zip(points,(*points[1:],points[0])):
        dx,dy=b[0]-a[0],b[1]-a[1]
        if dx==0 and dy==0:
            raise ValueError('GPU source cutout has zero edge')
        for p in points:
            cross=dx*(p[1]-a[1])-dy*(p[0]-a[0])
            if not isfinite(cross) or cross<0:
                raise ValueError('GPU source cutout must be simple and convex')
    return points


def partition(polygons,fan_holes,depth,*,segments=20,front_cutouts=(),layer_fan_indices=None,layer_depths=None):
    """Per-source-index meshes and explicit conservative budget omissions.

    Unsupported/over-budget lower paint is omitted, exposing the existing
    structural cover. It is never restored as an overlapping floating layer.
    Only the6 already bounded source-paint polygons are accepted.
    """
    from assembly_geometry import extrude
    from assembly_detail import _area,_subtract,_tri,_quad,_material_wall_segments,circle
    if len(polygons)>6:raise ValueError('GPU paint supports the existing six source layers only')
    # Optional fixed source-frame regions may cross a fan bay. This is a
    # bounded per-layer construction input, not a renderer/collision bypass.
    # None retains the previous exact default tuple/metadata path.
    from math import isfinite
    if layer_fan_indices is not None:
        if (not isinstance(layer_fan_indices,(tuple,list)) or len(layer_fan_indices)!=len(polygons)
                or any(not isinstance(row,(tuple,list)) or len(row)>len(fan_holes)
                    or any(type(n) is not int or not 0<=n<len(fan_holes) for n in row) or len(set(row))!=len(row)
                    for row in layer_fan_indices)):
            raise ValueError('Invalid bounded GPU source-layer fan apertures')
    if layer_depths is not None:
        if (not isinstance(layer_depths,(tuple,list)) or len(layer_depths)!=len(polygons)
                or any(type(value) not in (int,float) or not isfinite(value) or not 0<value<=depth
                       for value in layer_depths)):
            raise ValueError('Invalid bounded GPU source-layer depth')
    cap_triangles=[];source_edges=[]
    for poly in polygons:
        solid=extrude(poly,depth) if poly else ()
        triangles=[tuple(tuple(solid[n+k:n+k+2]) for k in (0,6,12))
                   for n in range(0,len(solid),18) if solid[n+5]>.999]
        cap_triangles.append(triangles)
        source_edges.append(poly if poly and _area(poly)>0 else tuple(reversed(poly or ())))
    fan_polys=[circle(*hole,segments) for hole in fan_holes]
    # Fixed source-authored openings apply to the face AND every paint layer;
    # default empty preserves the original circle-only construction exactly.
    if len(front_cutouts)>8:raise ValueError('GPU source cutouts exceeded budget')
    cutout_polys=[_convex_cutout(poly) for poly in front_cutouts]
    aperture_polys=(*fan_polys,*cutout_polys)
    values=[];omitted=[];partitioned=0
    for index,poly in enumerate(polygons):
        if not cap_triangles[index]:values.append(());continue
        later=[tri for group in cap_triangles[index+1:] for tri in group]
        layer_apertures=(tuple(fan_polys[n] for n in layer_fan_indices[index])+tuple(cutout_polys)
                         if layer_fan_indices is not None else aperture_polys)
        cuts=(*layer_apertures,*later)
        if len(cuts)>MAX_CUTTERS:
            values.append(());omitted.append(dict(index=index,reason='source_partition_cutters_exceeded'));continue
        if any(p and not ts for p,ts in zip(polygons[index+1:],cap_triangles[index+1:])):
            values.append(());omitted.append(dict(index=index,reason='later_source_polygon_untriangulable'));continue
        pieces=list(cap_triangles[index]);failed=False
        for cutter in cuts:
            pieces=[piece for current in pieces for piece in _subtract(current,cutter)]
            if len(pieces)>MAX_FRAGMENTS:
                failed=True;break
        if failed:
            values.append(());omitted.append(dict(index=index,reason='source_partition_fragments_exceeded'));continue
        out=[];z=(layer_depths[index] if layer_depths is not None else depth)/2
        for piece in pieces:
            if _area(piece)<0:piece=tuple(reversed(piece))
            for n in range(1,len(piece)-1):
                a,b,c=piece[0],piece[n],piece[n+1]
                _tri(out,(*a,z),(*b,z),(*c,z));_tri(out,(*c,-z),(*b,-z),(*a,-z))
        # Walls use only the real source perimeter, circular fan mouths and
        # later polygon perimeters. Triangulation diagonals aren't hardware.
        boundaries=(*layer_apertures,*(p for p in source_edges[index+1:] if p))
        for a,b in zip(source_edges[index],(*source_edges[index][1:],source_edges[index][0])):
            for first,last in _material_wall_segments(a,b,poly,boundaries,True):
                _quad(out,(*first,-z),(*last,-z),(*last,z),(*first,z))
        for hole in boundaries:
            for a,b in zip(hole,(*hole[1:],hole[0])):
                for first,last in _material_wall_segments(a,b,poly,boundaries,False):
                    _quad(out,(*last,-z),(*first,-z),(*first,z),(*last,z))
        if len(out)//18>MAX_PANEL_TRIANGLES:
            values.append(());omitted.append(dict(index=index,reason='source_partition_triangles_exceeded'));continue
        values.append(tuple(out));partitioned+=1
    return tuple(values),dict(source_painter_partition=True,source_layers=len(polygons),
        retained_nonempty_layers=sum(bool(v) for v in values),partitioned_layers=partitioned,
        omitted_source_paint=tuple(omitted),physical_fan_apertures=True,
        z_offset_used=False,manufacturer_panel_seams_inferred=False)
