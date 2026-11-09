"""Static GPU source-paint partition; no coplanar colour-face overlays.

The reviewed source polygons already establish painter order. This partitions
those same regions rather than inventing cuts, thickness offsets or new trim.
Concave later paint is subtracted as its real ear-clipped triangles. Physical
fan apertures cut every colour region. No render-time boolean or retained cache.
"""

MAX_CUTTERS=128
MAX_FRAGMENTS=2048
MAX_PANEL_TRIANGLES=8192


def partition(polygons,fan_holes,depth,*,segments=20):
    """Per-source-index meshes and explicit conservative budget omissions.

    Unsupported/over-budget lower paint is omitted, exposing the existing
    structural cover. It is never restored as an overlapping floating layer.
    Only the6 already bounded source-paint polygons are accepted.
    """
    from assembly_geometry import extrude
    from assembly_detail import _area,_subtract,_tri,_quad,_material_wall_segments,circle
    if len(polygons)>6:raise ValueError('GPU paint supports the existing six source layers only')
    cap_triangles=[];source_edges=[]
    for poly in polygons:
        solid=extrude(poly,depth) if poly else ()
        triangles=[tuple(tuple(solid[n+k:n+k+2]) for k in (0,6,12))
                   for n in range(0,len(solid),18) if solid[n+5]>.999]
        cap_triangles.append(triangles)
        source_edges.append(poly if poly and _area(poly)>0 else tuple(reversed(poly or ())))
    fan_polys=[circle(*hole,segments) for hole in fan_holes]
    values=[];omitted=[];partitioned=0
    for index,poly in enumerate(polygons):
        if not cap_triangles[index]:values.append(());continue
        later=[tri for group in cap_triangles[index+1:] for tri in group]
        cuts=(*fan_polys,*later)
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
        out=[];z=depth/2
        for piece in pieces:
            if _area(piece)<0:piece=tuple(reversed(piece))
            for n in range(1,len(piece)-1):
                a,b,c=piece[0],piece[n],piece[n+1]
                _tri(out,(*a,z),(*b,z),(*c,z));_tri(out,(*c,-z),(*b,-z),(*a,-z))
        # Walls use only the real source perimeter, circular fan mouths and
        # later polygon perimeters. Triangulation diagonals aren't hardware.
        boundaries=(*fan_polys,*(p for p in source_edges[index+1:] if p))
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
