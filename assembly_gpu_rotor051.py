"""Bounded static axial depth for already reviewed GPU blade planforms.

Only the existing exact model's known curved axial leaves opt in. Their X/Z
outline, count, handedness and tip links are retained. Cup depth is original
illustration reference, not a manufacturer's blade pitch or CFD result. The
unknown, blower and exact Astral049 implementations remain untouched.
No device access, clock, retained cache, new Mesh or render-time work.
"""
import math

CURVED_SHAPES=frozenset(('swept','wide','paired','claw'))


def eligible(profile):
    return (isinstance(profile,dict) and type(profile.get('blades')) is int
            and 2<=profile['blades']<=24 and profile.get('shape') in CURVED_SHAPES
            and profile.get('kind')!='blower')


def cup(x,z,radius,profile,amplitude):
    """Axial shear and derivatives; root and outer tip-link zones stay fixed."""
    r=math.hypot(x,z);hub=profile.get('hub_ratio',.28)
    hub=hub if type(hub) in (int,float) and math.isfinite(hub) else .28
    low=radius*max(.27,min(.70,hub)*1.03);high=radius*.79
    if r<=low or r>=high:return 0.,0.,0.
    t=(r-low)/(high-low);wave=16*t*t*(1-t)*(1-t)
    derivative=32*t*(1-t)*(1-2*t)/(high-low)
    direction=-1 if profile.get('direction')==-1 else 1
    phase=profile['blades']*direction*math.atan2(z,x)
    # Different reviewed leaf plans remain different: this field is only a
    # small axial camber, never a replacement for their actual blade outline.
    factor=.78+.22*math.sin(phase)
    angular=.22*profile['blades']*direction*math.cos(phase)
    return (amplitude*wave*factor,
            amplitude*(derivative*x/r*factor-wave*angular*z/(r*r)),
            amplitude*(derivative*z/r*factor+wave*angular*x/(r*r)))


def curve_rotor(vertices,radius,profile,level='balanced',*,axial_room_mm=0.,axis_sign=1):
    """Return the same planform with conservative one-pass optional splitting.

    Local mesh coordinates already face +/-Y. One uniform axial shear applies
    to front/back/sides, so every shared point remains shared and thickness is
    retained. The inverse-transpose analytically transports the source normals.
    Eco does not split. Higher LOD splits only edges whose midpoint error needs
    it; adjacent triangles use the identical deterministic edge decision.
    """
    if not eligible(profile) or not vertices or not math.isfinite(radius) or radius<=0:
        return vertices,dict(applied=False)
    amplitude=min(2.4,radius*.055,max(0.,axial_room_mm))
    if amplitude<.15:return vertices,dict(applied=False)
    sign=-1 if axis_sign<0 else 1
    tolerance=math.inf if level=='eco' else .22 if level=='balanced' else .11
    result=[];facet_fallbacks=0
    def midpoint(a,b):return tuple((x+y)*.5 for x,y in zip(a,b))
    def h(v):return cup(v[0],v[2],radius,profile,amplitude)[0]
    def split(a,b):return abs(h(midpoint(a,b))-(h(a)+h(b))*.5)>tolerance
    def emit(a,b,c):
        nonlocal facet_fallbacks
        rows=[]
        for v in (a,b,c):
            x,y,z,nx,ny,nz=v;value,dx,dz=cup(x,z,radius,profile,amplitude)
            if value==0. and dx==0. and dz==0.:
                rows.append(v);continue
            normal=(nx-sign*dx*ny,ny,nz-sign*dz*ny)
            size=math.sqrt(sum(n*n for n in normal))
            if not size>1e-12:raise ValueError('GPU rotor requires finite unit normals')
            rows.append((x,y+sign*value,z,*(n/size for n in normal)))
        ab=tuple(rows[1][i]-rows[0][i] for i in range(3));ac=tuple(rows[2][i]-rows[0][i] for i in range(3))
        cross=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
        magnitude=math.sqrt(sum(v*v for v in cross))
        if magnitude<=1e-12:raise ValueError('GPU rotor subdivision produced a degenerate face')
        face=tuple(v/magnitude for v in cross)
        for row in rows:
            # A continuous analytic normal can oppose a very narrow linear
            # ear-clipped facet after adaptive sampling. Its actual geometric
            # face is the conservative static fallback, not a fake highlight.
            if sum(face[i]*row[i+3] for i in range(3))<=0:
                result.extend((*row[:3],*face));facet_fallbacks+=1
            else:result.extend(row)
    for n in range(0,len(vertices),18):
        a,b,c=(tuple(vertices[n+i:n+i+6]) for i in (0,6,12))
        ab,bc,ca=midpoint(a,b),midpoint(b,c),midpoint(c,a)
        mask=(1 if split(a,b) else 0)|(2 if split(b,c) else 0)|(4 if split(c,a) else 0)
        pieces={0:((a,b,c),),1:((a,ab,c),(ab,b,c)),2:((a,b,bc),(a,bc,c)),
                4:((a,b,ca),(ca,b,c)),3:((a,ab,bc),(ab,b,bc),(a,bc,c)),
                5:((a,ab,ca),(ab,b,c),(ab,c,ca)),6:((a,b,bc),(a,bc,ca),(ca,bc,c)),
                7:((a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca))}[mask]
        for triangle in pieces:emit(*triangle)
    return tuple(result),dict(applied=True,amplitude_reference_mm=amplitude,
        triangles_before=len(vertices)//18,triangles_after=len(result)//18,
        facet_normal_fallback_vertices=facet_fallbacks,
        blade_pitch_verified=False,planform_retained=True,root_and_tip_links_retained=True)
