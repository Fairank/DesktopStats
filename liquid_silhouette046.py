"""Retained, view-gated real triangle edges for new loop line artwork.

Only stdlib. Camera clipping is shared by GPU, SVG and offline CPU proofs;
mesh construction/upload owns adjacency work, never a frame timer or sampler.
The existing edge normal3 carries two exact float32 oct12 integers and -2.
"""
import math

CREASE_TAG=(0.,0.,1.)
MARKER=-2.
_MAX_OCT=4095
_BASE=4096
_COS_CREASE=math.cos(math.radians(35.))


def _dot(a,b):return sum(x*y for x,y in zip(a,b))


def _unit(vector):
    length=math.sqrt(_dot(vector,vector))
    return tuple(x/length for x in vector) if length>1e-12 else None


def _point(point):return tuple(round(x,7) for x in point)


def _edge(a,b):return tuple(sorted((_point(a),_point(b))))


def _sign(value):return 1. if value>=0. else -1.


def _encode(normal):
    length=sum(abs(x) for x in normal)
    if length<=1e-12:raise ValueError('A face normal is required')
    x,y,z=(v/length for v in normal)
    if z<0.:x,y=(1.-abs(y))*_sign(x),(1.-abs(x))*_sign(y)
    a,b=(max(0,min(_MAX_OCT,int(math.floor((v*.5+.5)*_MAX_OCT+.5)))) for v in (x,y))
    return float(a+_BASE*b)


def _decode(value):
    integer=int(value);x=(integer%_BASE)/_MAX_OCT*2.-1.;y=(integer//_BASE)/_MAX_OCT*2.-1.
    z=1.-abs(x)-abs(y)
    if z<0.:x,y=(1.-abs(y))*_sign(x),(1.-abs(x))*_sign(y)
    return _unit((x,y,z))


def encode_normals(a,b):
    """Two geometric face normals; both endpoints receive the same tag."""
    return (_encode(a),_encode(b),MARKER)


def decode_normals(tag):
    """Return local face normals, or None for an ordinary crease marker."""
    if len(tag)!=3 or tag[2]!=MARKER:return None
    if any(not math.isfinite(x) or x<0. or x>16777215. or int(x)!=x for x in tag[:2]):return None
    return _decode(tag[0]),_decode(tag[1])


def clip_edge(a,b,tag,*,direction=None,eye=None):
    """Keep exact view-straddling portions in the normals' coordinate space.

    Orthographic direction points toward the eye. Perspective eye is a point;
    both dot products are linear along the edge, hence at most two zero roots.
    Ordinary creases pass through. Depth/opaque visibility remains the caller's.
    """
    normals=decode_normals(tag)
    if normals is None:return ((a,b),)
    if (direction is None)==(eye is None):raise ValueError('Exactly one camera is required')
    if direction is not None:
        signs=tuple(_dot(n,direction) for n in normals)
        return ((a,b),) if min(signs)<=0.<=max(signs) else ()
    delta=tuple(b[k]-a[k] for k in range(3));toward=tuple(eye[k]-a[k] for k in range(3))
    coefficients=tuple((_dot(n,toward),-_dot(n,delta)) for n in normals)
    cuts=[0.,1.]
    for start,slope in coefficients:
        if abs(slope)>1e-15:
            root=-start/slope
            if 0.<root<1.:cuts.append(root)
    cuts=sorted(set(cuts));intervals=[]
    for low,high in zip(cuts,cuts[1:]):
        t=(low+high)*.5;values=tuple(start+slope*t for start,slope in coefficients)
        if min(values)<=0.<=max(values):
            if intervals and abs(intervals[-1][1]-low)<1e-12:intervals[-1]=(intervals[-1][0],high)
            else:intervals.append((low,high))
    point=lambda t:tuple(a[k]+delta[k]*t for k in range(3))
    return tuple((point(low),point(high)) for low,high in intervals)


def _surface_groups(vertices):
    """Union smooth/coplanar faces, not disconnected axial-edge endpoints."""
    faces=[];adjacent={}
    for at in range(0,len(vertices)-17,18):
        p=[tuple(vertices[at+n:at+n+3]) for n in (0,6,12)]
        if not all(math.isfinite(x) for point in p for x in point):continue
        u=tuple(p[1][k]-p[0][k] for k in range(3));v=tuple(p[2][k]-p[0][k] for k in range(3))
        cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]);normal=_unit(cross)
        if normal is None:continue
        index=len(faces);faces.append((normal,.5*math.sqrt(_dot(cross,cross))))
        for a,b in zip(p,p[1:]+p[:1]):
            key=_edge(a,b)
            if key[0]!=key[1]:adjacent.setdefault(key,[(a,b),[]])[1].append(index)
    parents=list(range(len(faces)))
    def find(n):
        while parents[n]!=n:parents[n]=parents[parents[n]];n=parents[n]
        return n
    smooth=[]
    for edge,indices in adjacent.values():
        if len(indices)!=2:continue
        a,b=indices;d=_dot(faces[a][0],faces[b][0])
        if d>_COS_CREASE+1e-8:
            ra,rb=find(a),find(b)
            if ra!=rb:parents[rb]=ra
            if d<1.-1e-8:smooth.append((edge,a,b))
    areas={}
    for index,(_,area) in enumerate(faces):
        root=find(index);areas[root]=areas.get(root,0.)+area
    groups={}
    for edge,a,b in smooth:
        root=find(a);groups.setdefault(root,[]).append((edge,encode_normals(faces[a][0],faces[b][0])))
    return tuple((tuple(rows),areas[root]) for root,rows in groups.items())


def silhouette_edges(vertices,creases,limit=512,*,split_long=False):
    """Return edges, tags and atomic smooth groups within an unchanged budget.

    The budget counts actual emitted segments, including hand-stroke splits.
    Retain complete highest-area physical smooth groups. Reserve half for real
    rims/creases; if a primary group needs more, allow it as one whole group.
    No candidate circle is scattered by longest-edge or angular sampling.
    """
    if type(limit) is not int or limit<=0:return (),(),()
    limit=min(512,limit)
    cost=lambda edge:1+int(split_long and math.dist(*edge)>12.)
    old=[];seen=set()
    for edge in creases:
        key=_edge(*edge)
        if key[0]!=key[1] and key not in seen:old.append(edge);seen.add(key)
    groups=[]
    for members,area in _surface_groups(vertices):
        rows=tuple((edge,tag) for edge,tag in members if _edge(*edge) not in seen)
        if rows:groups.append((rows,area))
    groups.sort(key=lambda row:-row[1])
    chosen=[];spent=0;reserve=limit//2
    for rows,area in groups:
        group_cost=sum(cost(edge) for edge,_ in rows)
        allowance=limit if not chosen else reserve
        if spent+group_cost<=allowance:
            chosen.append((rows,area));spent+=group_cost
    # Preserve all existing creases when possible; otherwise retain the
    # longest real edges in stable source order, never part of a smooth group.
    remaining=limit-spent
    selected=set()
    for n in sorted(range(len(old)),key=lambda n:(-math.dist(*old[n]),n)):
        charge=cost(old[n])
        if charge<=remaining:selected.add(n);remaining-=charge
    edges=[edge for n,edge in enumerate(old) if n in selected];tags=[CREASE_TAG]*len(edges);atomic=[]
    for rows,area in chosen:
        start=len(edges)
        for edge,tag in rows:edges.append(edge);tags.append(tag)
        atomic.append((tuple(range(start,len(edges))),area))
    return tuple(edges),tuple(tags),tuple(atomic)
