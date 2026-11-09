"""Bounded static orthogonal detours for reference soft tubing, not CAD fit."""
import heapq
import math

MAX_AXIS_PLANES=12
MAX_VISITED=2048
MAX_EDGE_CACHE=4096

def _rounded(path,radius):
    """Circular tangent fillets with explicit space, never compressed bends."""
    compact=[path[0]]
    for p,q in zip(path[1:],path[2:]):
        before=compact[-1];u=tuple(p[i]-before[i] for i in range(3));v=tuple(q[i]-p[i] for i in range(3))
        cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        if sum(c*c for c in cross)>1e-8 or sum(u[i]*v[i] for i in range(3))<0:compact.append(p)
    compact.append(path[-1]);corners=[]
    for before,p,after in zip(compact,compact[1:],compact[2:]):
        left,right=math.dist(before,p),math.dist(p,after)
        if min(left,right)<1e-8:return None
        u=tuple((p[i]-before[i])/left for i in range(3));v=tuple((after[i]-p[i])/right for i in range(3))
        cosine=max(-1.,min(1.,sum(u[i]*v[i] for i in range(3))));angle=math.acos(cosine)
        if angle>math.pi-.01:return None
        trim=radius*math.tan(angle/2)
        if trim>min(left,right)-1e-5:return None
        corners.append((p,u,v,angle,trim,left,right))
    if any(a[4]+b[4]>a[6]-1e-5 for a,b in zip(corners,corners[1:])):return None
    result=[compact[0]]
    for p,u,v,angle,trim,left,right in corners:
        if angle<1e-6:continue
        entry=tuple(p[i]-u[i]*trim for i in range(3));exit=tuple(p[i]+v[i]*trim for i in range(3))
        inward=tuple((v[i]-u[i]*math.cos(angle))/math.sin(angle) for i in range(3))
        center=tuple(entry[i]+inward[i]*radius for i in range(3));radial=tuple(-inward[i] for i in range(3))
        result.append(entry)
        for n in range(1,max(3,math.ceil(angle/(math.pi/12)))+1):
            fraction=n/max(3,math.ceil(angle/(math.pi/12)));t=angle*fraction
            result.append(tuple(center[i]+radius*(radial[i]*math.cos(t)+u[i]*math.sin(t)) for i in range(3)))
        result[-1]=exit
    result.append(compact[-1])
    # Coincident tangent points are not extra frames for the swept geometry.
    return [p for i,p in enumerate(result) if i==0 or math.dist(p,result[i-1])>1e-6]

def detour(a,b,n0,n1,radius,obstacles,bounds,minimum=None):
    from liquid_routes046 import tube_segment_intersection,_radius
    if not bounds:return None
    low,high=bounds;edge_validity={}
    def safe(p,q):
        key=(p,q) if p<q else (q,p)
        previous=edge_validity.get(key)
        if previous is not None:return previous
        result=(all(low[i]+radius+.2<=v<=high[i]-radius-.2 for p0 in (p,q) for i,v in enumerate(p0))
                and not any(tube_segment_intersection(p,q,box,radius+.3) for box in obstacles))
        # This cache belongs only to one finite construction. It is discarded
        # on return and never grows with frames, selections or installed packs.
        if len(edge_validity)<MAX_EDGE_CACHE:edge_validity[key]=result
        return result
    def plus(p,n,length):return tuple(p[i]+n[i]*length for i in range(3))
    geometric_minimum=max(radius*1.2,minimum or 0.)
    margin=max(12.,geometric_minimum)
    bend=max(10.,geometric_minimum*1.04);visited=0
    for escape in (max(24.,radius*4),max(18.,radius*3),bend+2.):
        start,end=plus(a,n0,escape),plus(b,n1,escape)
        if not safe(a,start) or not safe(end,b):continue
        axes=[]
        for i in range(3):
            required={start[i],end[i]};limits={low[i]+radius+1,high[i]-radius-1};candidate=set(limits)
            for lo,hi in obstacles:candidate.update((lo[i]-radius-margin,hi[i]+radius+margin))
            candidate={v for v in candidate if low[i]+radius+.3<=v<=high[i]-radius-.3}
            # Keep enclosure-side escapes. Earlier curved hoses contribute many
            # almost identical AABB coordinates; those must not consume every
            # plane and erase the only corridor around a graphics card.
            picked=set(required|limits)
            for value in sorted(candidate,key=lambda v:min(abs(v-start[i]),abs(v-end[i]))):
                if len(picked)>=MAX_AXIS_PLANES:break
                if min(abs(value-prior) for prior in picked)<max(10.,geometric_minimum):continue
                picked.add(value)
            axes.append(sorted(picked))
        source=tuple(axes[i].index(start[i]) for i in range(3));target=tuple(axes[i].index(end[i]) for i in range(3))
        point=lambda node:tuple(axes[i][node[i]] for i in range(3))
        def direction(axis,sign):return tuple(sign if i==axis else 0 for i in range(3))
        # Direction is part of the state: a cheaper arrival from the wrong side
        # must not erase a feasible tangent arrival at the same reference point.
        heuristic=lambda p:sum(abs(p[i]-end[i]) for i in range(3))
        first=(source,tuple(n0));scores={first:0.};parents={};queue=[(heuristic(start),0.,first)];found=None
        while queue and visited<MAX_VISITED:
            _,negative_cost,state=heapq.heappop(queue);cost=-negative_cost;node,incoming=state
            if cost!=scores.get(state):continue
            visited+=1
            if node==target and sum(incoming[i]*n1[i] for i in range(3))<.01:found=state;break
            p=point(node)
            for i in range(3):
                for index in range(len(axes[i])):
                    if index==node[i]:continue
                    nxt=list(node);nxt[i]=index;nxt=tuple(nxt);q=point(nxt)
                    length=abs(q[i]-p[i]);outgoing=direction(i,1 if q[i]>p[i] else -1)
                    alignment=sum(incoming[j]*outgoing[j] for j in range(3))
                    if alignment<-.01:continue
                    # Every search edge may join two right-angle fillets. Do
                    # not silently shrink R to accommodate an unusable dogleg.
                    if length<2*bend+.1:continue
                    if nxt==target and sum(outgoing[j]*n1[j] for j in range(3))>.01:continue
                    if not safe(p,q):continue
                    following=(nxt,outgoing);candidate=cost+length+(12. if alignment<.99 else 0.)
                    if candidate>=scores.get(following,float('inf')):continue
                    scores[following]=candidate;parents[following]=state
                    # Manhattan distance is a tight bound for this orthogonal
                    # lattice; progress-first ties avoid a large flat wave of
                    # equivalent subdivisions under the fixed visit ceiling.
                    heapq.heappush(queue,(candidate+heuristic(q),-candidate,following))
        if not found:continue
        states=[found]
        while states[-1]!=first:states.append(parents[states[-1]])
        path=[a]+[point(state[0]) for state in reversed(states)]+[b]
        rounded=_rounded(path,bend)
        if not rounded or len(rounded)>160 or any(not safe(p,q) for p,q in zip(rounded,rounded[1:])):continue
        if _radius(rounded)+.05<geometric_minimum:continue
        return rounded
    return None
