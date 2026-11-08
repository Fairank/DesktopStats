"""Finite, static tube-route illustration checks; no fluids or hardware control."""
import math

def _add(a,b):return tuple(x+y for x,y in zip(a,b))
def _sub(a,b):return tuple(x-y for x,y in zip(a,b))
def _mul(v,k):return tuple(x*k for x in v)
def _dot(a,b):return sum(x*y for x,y in zip(a,b))
def _cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])

def _radius(points):
    smallest=float('inf')
    for a,b,c in zip(points,points[1:],points[2:]):
        ab,bc,ac=math.dist(a,b),math.dist(b,c),math.dist(a,c)
        twice_area=math.sqrt(_dot(_cross(_sub(b,a),_sub(c,a)),_cross(_sub(b,a),_sub(c,a))))
        if twice_area>1e-8:smallest=min(smallest,ab*bc*ac/(2*twice_area))
    return smallest

def bounds_intersection(a,b,bounds,padding):
    """Slab test for the whole segment, so sparse samples cannot jump a PCB."""
    low,high=bounds;near,far=0.,1.
    for i in range(3):
        delta=b[i]-a[i];lo,hi=low[i]-padding,high[i]+padding
        if abs(delta)<1e-10:
            if not lo<a[i]<hi:return False
        else:
            x,y=(lo-a[i])/delta,(hi-a[i])/delta
            near=max(near,min(x,y));far=min(far,max(x,y))
            if near>=far:return False
    return far>0 and near<1

def tube_segment_intersection(a,b,bounds,radius):
    """Finite open tube segment, with no fictitious sphere beyond its mouth.

    The remaining radial AABB inflation is conservative. This is a reference
    clearance filter, not an exact curved-mesh collision or mounting guarantee.
    """
    delta=_sub(b,a);lo,hi=bounds
    aligned=(0 if delta[1]==0. and delta[2]==0. else
             1 if delta[0]==0. and delta[2]==0. else
             2 if delta[0]==0. and delta[1]==0. else None)
    if aligned is not None:
        if abs(delta[aligned])<1e-9:return False
        # Almost every lattice edge is axis aligned. Its finite cylinder has
        # no axial radius padding; the other two dimensions retain the same
        # conservative rectangular radial inflation as the general filter.
        if (hi[aligned]<=min(a[aligned],b[aligned])+1e-7 or
                lo[aligned]>=max(a[aligned],b[aligned])-1e-7):return False
        return all(lo[i]-radius<a[i]<hi[i]+radius for i in range(3) if i!=aligned)
    if not bounds_intersection(a,b,bounds,radius):return False
    length=math.dist(a,b)
    if length<1e-9:return False
    axis=_mul(delta,1/length)
    near=sum(((lo[i] if axis[i]>=0 else hi[i])-a[i])*axis[i] for i in range(3))
    far=sum(((hi[i] if axis[i]>=0 else lo[i])-a[i])*axis[i] for i in range(3))
    if far<=1e-7 or near>=length-1e-7:return False
    return True

def route(start,end,tubing,*,steps=12,obstacles=(),case_bounds=None,allow_detour=False):
    """Reference centerline. A route may be omitted; it is never silently forced."""
    a,b=tuple(start['position']),tuple(end['position']);distance=math.dist(a,b)
    if distance<1.:return None,'tube_endpoints_too_close'
    n0,n1=tuple(start['normal']),tuple(end['normal']);direction=_mul(_sub(b,a),1/distance)
    material=str(tubing.get('material','')).casefold()
    straight=_dot(n0,direction)>.995 and _dot(n1,direction)<-.995
    rigid_carbon=('carbon' in material or material=='cfrp'
                  or tubing.get('geometry_family')=='carbon_hard_tube')
    if rigid_carbon and not straight:return None,'rigid_tube_requires_inline_elbows'
    if straight:points=[a,b]
    else:
        from assembly_cooling import _curve
        reach=max(20.,min(100.,distance*.35))
        points=_curve((a,_add(a,_mul(n0,reach)),_add(b,_mul(n1,reach)),b),max(6,min(24,steps)))
    outer=tubing.get('tube_outer_mm')
    if outer is None:return None,'tube_dimensions_unknown'
    radius=outer/2
    reason=''
    if case_bounds:
        low,high=case_bounds
        if any(any(p[i]-radius<low[i] or p[i]+radius>high[i] for i in range(3)) for p in points):reason='tube_route_outside_case'
    minimum=tubing.get('min_bend_radius_mm')
    geometric_minimum=radius*1.2
    if _radius(points)+.05<max(geometric_minimum,minimum or 0.):reason='tube_bend_radius_exceeded'
    for obstacle in obstacles:
        if any(tube_segment_intersection(p,q,obstacle,radius) for p,q in zip(points,points[1:])):reason='tube_route_obstructed';break
    detoured=False
    if reason and allow_detour and tubing.get('tube_type')=='soft' and case_bounds:
        from liquid_path046 import detour
        alternative=detour(a,b,n0,n1,radius,obstacles,case_bounds,minimum)
        if alternative:points=alternative;reason='';detoured=True
    if reason:return None,reason
    return dict(points=points,length_mm=sum(math.dist(p,q) for p,q in zip(points,points[1:])),
        minimum_radius_mm=None if math.isinf(_radius(points)) else _radius(points),
        bend_radius_verified=minimum is not None,positions_verified=False,
        bounded_reference_detour=detoured,
        hard_tube_bends_are_reference=tubing.get('tube_type')=='hard' and not straight),''
