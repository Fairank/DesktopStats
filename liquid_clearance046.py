"""Finite nominal tube clearance; no CAD, sensors, clocks or persistent cache.

Distances use each tube's outer radius. Self clearance excludes a local arc
neighborhood rather than an arbitrary number of tessellation samples. The
remaining segment-parameter domain is checked exactly, including backtracking
segments whose unconstrained closest points happen to be a shared endpoint.
"""
import math

MAX_ROUTE_POINTS = 160
MAX_COORDINATE_MM = 1_000_000


def _point(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 3 or
            any(type(v) not in (int, float) or not math.isfinite(v) or abs(v)>MAX_COORDINATE_MM for v in value)):
        raise ValueError('Invalid finite tube point')
    return tuple(float(v) for v in value)


def _radius(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0<value<=1000:
        raise ValueError('Invalid tube outer radius')
    return float(value)


def _sub(a,b):return tuple(x-y for x,y in zip(a,b))
def _dot(a,b):return sum(x*y for x,y in zip(a,b))
def _cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def _clamp(value):return max(0.,min(1.,value))


def _closest(a0,a1,b0,b1):
    u,v,w=_sub(a1,a0),_sub(b1,b0),_sub(a0,b0)
    a,b,c=_dot(u,u),_dot(u,v),_dot(v,v);d,e=_dot(u,w),_dot(v,w)
    if a<1e-20 and c<1e-20:return math.sqrt(_dot(w,w)),0.,0.
    if a<1e-20:s,t=0.,_clamp(e/c)
    elif c<1e-20:s,t=_clamp(-d/a),0.
    else:
        # Cross products avoid cancellation of a*c-b*b for almost parallel
        # long segments; shallow real crossings must not become disjoint.
        cross=_cross(u,v);denominator=_dot(cross,cross)
        s=_clamp(_dot(_cross(v,w),cross)/denominator) if denominator>0. else 0.
        t=(b*s+e)/c
        if t<0:t=0.;s=_clamp(-d/a)
        elif t>1:t=1.;s=_clamp((b-d)/a)
    delta=tuple(w[i]+s*u[i]-t*v[i] for i in range(3))
    return math.sqrt(_dot(delta,delta)),s,t


def segment_distance(a0,a1,b0,b1):
    """Minimum distance between finite segments; points/parallel cases included."""
    return _closest(*map(_point,(a0,a1,b0,b1)))[0]


def _segments(points):
    if not isinstance(points,(list,tuple)) or not 2<=len(points)<=MAX_ROUTE_POINTS:
        raise ValueError('Tube route requires2..160 finite points')
    points=tuple(map(_point,points));segments=[];arc=0.
    for a,b in zip(points,points[1:]):
        length=math.dist(a,b)
        if length>1e-10:
            bounds=tuple((min(a[i],b[i]),max(a[i],b[i])) for i in range(3))
            segments.append((a,b,length,arc,bounds))
        arc+=length
    if not segments:raise ValueError('Tube route has no nonzero segment')
    return segments


def _near(a,b,reach):
    return all(x[0]-reach<=y[1] and y[0]-reach<=x[1] for x,y in zip(a[4],b[4]))


def route_pair_overlap(points_a,radius_a,points_b,radius_b):
    """True for penetration of two route tubes, including their finite ends."""
    radius_a,radius_b=_radius(radius_a),_radius(radius_b)
    reach=radius_a+radius_b;threshold=reach-min(1e-6,reach*1e-6)
    first,second=_segments(points_a),_segments(points_b)
    for a in first:
        for b in second:
            if _near(a,b,reach) and _closest(a[0],a[1],b[0],b[1])[0]<threshold:return True
    return False


def _nonlocal_distance(a,b,exclude_arc):
    """Minimum distance over the unit parameter square clipped by arc gap."""
    offset=b[3]-a[3]
    allowed=lambda s,t:offset+t*b[2]-s*a[2]-exclude_arc
    polygon=[(0.,0.),(1.,0.),(1.,1.),(0.,1.)];clipped=[]
    for p,q in zip(polygon,polygon[1:]+polygon[:1]):
        first,last=allowed(*p),allowed(*q)
        if first>=0:clipped.append(p)
        if (first<0)!=(last<0):
            amount=first/(first-last)
            clipped.append(tuple(p[i]+amount*(q[i]-p[i]) for i in range(2)))
    if not clipped:return float('inf')
    distance,s,t=_closest(a[0],a[1],b[0],b[1])
    if allowed(s,t)>=0:return distance
    # Convex squared distance has its constrained minimum on a polygon edge
    # when its unconstrained minimum is outside. Each edge is one finite 3-D
    # difference segment; this also detects a long immediate reversal.
    u,v,w=_sub(a[1],a[0]),_sub(b[1],b[0]),_sub(a[0],b[0]);best=float('inf')
    for p,q in zip(clipped,clipped[1:]+clipped[:1]):
        start=tuple(w[i]+p[0]*u[i]-p[1]*v[i] for i in range(3))
        delta=tuple((q[0]-p[0])*u[i]-(q[1]-p[1])*v[i] for i in range(3));denominator=_dot(delta,delta)
        amount=_clamp(-_dot(start,delta)/denominator) if denominator>1e-20 else 0.
        difference=tuple(start[i]+amount*delta[i] for i in range(3))
        best=min(best,math.sqrt(_dot(difference,difference)))
    return best


def self_overlap(points,radius):
    """Check nonlocal tube penetration; local arc gap up to pi*r is excluded.

    Local curvature is a separate requirement of the route generator. The
    pi*r neighborhood avoids flagging the necessary adjacent sweep sections
    of a bend with centerline radius at least r. It is independent of samples.
    """
    radius=_radius(radius);segments=_segments(points);reach=2*radius
    epsilon=min(1e-6,reach*1e-6);exclude_arc=math.pi*radius+epsilon
    for i,a in enumerate(segments):
        for b in segments[i+1:]:
            if b[3]+b[2]-a[3]<=exclude_arc or not _near(a,b,reach):continue
            if _nonlocal_distance(a,b,exclude_arc)<reach-epsilon:return True
    return False
