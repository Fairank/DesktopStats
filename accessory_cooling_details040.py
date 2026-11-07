"""Original orthographic cooler drawings with connected parts and retained rotors.

All surfaces, tube bends and fan planes share the same world projection.
Dimensions/counts come from the catalog; machining and placement stay schematic.
No vendor assets, graphics dependencies, timers, sensors or I/O.
"""
import math

_SUPPORTED={'noctua-nh-l12s','noctua-nh-c14s','bequiet-dark-rock-tf2','zalman-cnps9900-max'}
_ORIGINAL={'miniature','classic','solid'}
def _n(x):return format(float(x),'.5f').rstrip('0').rstrip('.') or '0'
def _shade(c,k):return '#'+''.join(f'{max(0,min(255,round(int(c[i:i+2],16)*k))):02x}' for i in (1,3,5))
def _svg(s):return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 100">'+s+'</svg>'
def _path(points):return 'M'+' L'.join(' '.join(_n(v) for v in p) for p in points)+' Z '

class _View:
    def __init__(self,w,h,d,yaw=24,pitch=25):
        self.underside=pitch<0
        a,b=math.radians(yaw),math.radians(pitch)
        self.x=(math.cos(a),math.sin(a),0.)
        self.y=(math.sin(a)*math.sin(b),-math.cos(a)*math.sin(b),-math.cos(b))
        points=[self.raw((x,y,z)) for x in (-w/2,w/2) for y in (-d/2,d/2) for z in (0,h)]
        lo=[min(p[i] for p in points) for i in (0,1)];hi=[max(p[i] for p in points) for i in (0,1)]
        self.scale=min(96/(hi[0]-lo[0]),82/(hi[1]-lo[1]))
        self.offset=(60-(hi[0]+lo[0])/2*self.scale,49-(hi[1]+lo[1])/2*self.scale)
    def raw(self,p):return tuple(sum(a*b for a,b in zip(v,p)) for v in (self.x,self.y))
    def at(self,p):
        x,y=self.raw(p);return self.offset[0]+x*self.scale,self.offset[1]+y*self.scale
    def poly(self,p,points,tone,width=.55,**kwargs):p.poly([self.at(q) for q in points],tone,width,**kwargs)
    def line(self,p,a,b,width=.32):p.line_to(*self.at(a),*self.at(b),width)

def _pipe(p,v,points,tone,width=1.4):
    xy=[v.at(q) for q in points]
    data='M'+' '.join(_n(t) for t in xy[0])
    data+=' C'+' '.join(_n(t) for q in xy[1:4] for t in q)
    data+=' C'+' '.join(_n(t) for q in xy[4:7] for t in q)
    p.path(data,width=width)
    if not p.line:
        old=p.ink;p.ink=tone;p.path(data,width=width*.54);p.ink=old

def _box(p,v,w,d,z0,z1,tone):
    v.poly(p,[(-w/2,-d/2,z0),(w/2,-d/2,z0),(w/2,-d/2,z1),(-w/2,-d/2,z1)],_shade(tone,.88))
    v.poly(p,[(w/2,-d/2,z0),(w/2,d/2,z0),(w/2,d/2,z1),(w/2,-d/2,z1)],_shade(tone,.72))
    z=z0 if v.underside else z1
    v.poly(p,[(-w/2,-d/2,z),(w/2,-d/2,z),(w/2,d/2,z),(-w/2,d/2,z)],_shade(tone,1.1))

def _fins(p,v,w,d,z0,z1,tone,count=38):
    # Individual notched vertical sheets leave actual empty air channels. The
    # samples represent a fin bank, not its full documented physical count.
    # No opaque top panel closes the airflow path.
    for i in range(count):
        x=-w/2+(count-1-i)*w/(count-1)
        points=[(x,-d/2+3,z0),(x,-d/2,z0+3),(x,-d/2,z1-2),
                (x,-d/2+2,z1),(x,d/2-2,z1),(x,d/2,z1-2),
                (x,d/2,z0+3),(x,d/2-3,z0)]
        v.poly(p,points,_shade(tone,.94+(i%3)*.035),.22,retrace=False)
    z=z0+1 if v.underside else z1-1
    # Two folded retaining strips span the fin tips; separated channels remain
    # visible between them, including the shallow edge reliefs.
    for y in (-d*.35,d*.35):
        v.poly(p,[(-w/2,y,z),(w/2,y,z),(w/2,y+1.1,z),(-w/2,y+1.1,z)],_shade(tone,1.05),.16)
    v.line(p,(-w/2,-d/2+3,z0),(w/2,-d/2+3,z0),.28)

def _circle(v,center,u,axis,r,steps=48):
    return [v.at(tuple(center[j]+r*(u[j]*math.cos(i*math.tau/steps)+axis[j]*math.sin(i*math.tau/steps)) for j in range(3))) for i in range(steps)]

def _fan(p,fg,v,fan,style,make_rotor,center,normal='up',frame=True):
    size=fan.get('size_mm',120);depth=fan.get('depth_mm',25)
    u=(1.,0.,0.)
    axis=(0.,-1.,0.) if normal=='up' else (0.,1.,0.) if normal=='down' else (0.,0.,-1.)
    n=(0.,0.,1.) if normal=='up' else (0.,0.,-1.) if normal=='down' else (0.,-1.,0.)
    def point(a,b,z=0):return tuple(center[j]+u[j]*a+axis[j]*b+n[j]*z for j in range(3))
    tone=fan.get('frame_color',p.body) if style in _ORIGINAL else p.body
    if frame:
        for first,second in (((-1,1),(1,1)),((1,1),(1,-1))):
            a,b=first,second
            v.poly(p,[point(a[0]*size/2,a[1]*size/2,-depth),point(b[0]*size/2,b[1]*size/2,-depth),
                      point(b[0]*size/2,b[1]*size/2),point(a[0]*size/2,a[1]*size/2)],_shade(tone,.78),.5)
        cut=size*.065
        square=[(-size/2+cut,-size/2),(size/2-cut,-size/2),(size/2,-size/2+cut),(size/2,size/2-cut),
                (size/2-cut,size/2),(-size/2+cut,size/2),(-size/2,size/2-cut),(-size/2,-size/2+cut)]
        outer=[v.at(point(a,b)) for a,b in square]
        rounded=fan.get('frame')=='round'
        if rounded:outer=_circle(v,center,u,axis,size*.497)
        hole=_circle(v,center,u,axis,size*.463)
        fg.parts.append('<path d="'+_path(outer)+_path(hole)+'" fill-rule="evenodd"'+fg._attrs(tone,.55)+'/>')
        for a,b in ((-.415,-.415),(.415,-.415),(-.415,.415),(.415,.415)):
            pc=point(a*size,b*size)
            if rounded:
                sa=1 if a>0 else -1;sb=1 if b>0 else -1
                v.poly(fg,[point(sa*size*.28,sb*size*.40),point(sa*size*.46,sb*size*.46),
                           point(sa*size*.46,sb*size*.31)],tone,.4)
            if fan.get('pads'):
                corners=[tuple(pc[j]+u[j]*aa+axis[j]*bb for j in range(3)) for aa,bb in ((-5,-5),(5,-5),(5,5),(-5,5))]
                v.poly(fg,corners,'#806a51' if style in _ORIGINAL else p.accent,.28)
            fg.poly(_circle(v,pc,u,axis,size*.014,12),p.light,.27)
    # Rotate in a circular local plane, then project; never rotate a flattened fan.
    diameter=size*1.04;c0=v.at(center)
    pu=v.at(tuple(center[j]+u[j]*diameter for j in range(3)))
    pv=v.at(tuple(center[j]+axis[j]*diameter for j in range(3)))
    a,b=(pu[i]-c0[i] for i in range(2));c,d=(pv[i]-c0[i] for i in range(2))
    a/=100;b/=100;c/=100;d/=100;e=c0[0]-50*(a+c);f=c0[1]-50*(b+d)
    rx,ry=50*math.hypot(a,c),50*math.hypot(b,d)
    result=make_rotor(fan,style,c0[0]-rx,c0[1]-ry,2*rx,2*ry)
    result.update(affine=[a,b,c,d,e,f],projection='one_orthographic_world_reference')
    return result

def _pipes(p,v,row,z,style):
    tone='#a7b3b8' if style in _ORIGINAL else p.accent
    count=row.get('heatpipes',4);w=row['dimensions_mm']['width']
    for i in reversed(range(count)):
        y=(i-(count-1)/2)*7.5;left=-w*.43-i*.5
        _pipe(p,v,[(-11,y,4),(left+4,y,4),(left,y,7),(left,y,16),
                   (left,y,z-3),(left+8,y,z),(w*.20,y,z)],tone)

def _base(p,v,style):
    metal='#a1adb4' if style in _ORIGINAL else p.light
    _box(p,v,40,38,0,5,metal)
    # Original schematic mounting bridge, with grounded ears and spring
    # fasteners. It is not a claim of the vendor's exact mounting-kit shape.
    for sign in (-1,1):
        x=sign*24
        v.poly(p,[(sign*15,-6,5),(x,-6,5),(x,6,5),(sign*15,6,5)],metal,.32)
        p.poly(_circle(v,(x,0,6),(1,0,0),(0,1,0),2.1,12),p.dark,.28)
        v.line(p,(x-1,0,6),(x+1,0,6),.22)

def _wire_clips(p,v,w,d,z0,z1):
    # Bent spring-wire clips sit at the edge of the frame and fin bank.
    for sign in (-1,1):
        x=sign*w*.49
        points=[(x,-d*.23,z1),(x+sign*2,-d*.23,z1-4),
                (x+sign*2,d*.25,z0+3),(x,d*.25,z0)]
        p.poly([v.at(q) for q in points],'none',.38,close=False)

def _annulus(p,cx,cy,rx,ry,inner_x,inner_y,tone,segments=32):
    for i in range(segments):
        a,b=i*math.tau/segments,(i+1)*math.tau/segments
        p.poly([(cx+rx*math.cos(a),cy+ry*math.sin(a)),(cx+rx*math.cos(b),cy+ry*math.sin(b)),
                (cx+inner_x*math.cos(b),cy+inner_y*math.sin(b)),(cx+inner_x*math.cos(a),cy+inner_y*math.sin(a))],tone,.2)

def _radial(p,fg,v,row,style,fan_for,make_rotor):
    outer=row.get('radial_outer_reference_mm',126)/2;cz=83.
    tone='#8f9da4' if style in _ORIGINAL else p.body
    _box(p,v,39,36,0,5,'#a1aeb4' if style in _ORIGINAL else p.light)
    for x in (-13.,0.,13.):
        _pipe(p,v,[(x,0,4),(x,-26,5),(x,-29,10),(x,-29,24),(x,-26,43),(x,-17,47),(x,-15,48)],
              '#aebbc1' if style in _ORIGINAL else p.accent)
    def bank(pen,y,r,inner):
        for i in range(36):
            a,b=i*math.tau/36,(i+1)*math.tau/36
            points=[(rr*math.cos(t),y,cz+rr*math.sin(t)) for rr,t in ((r,a),(r,b),(inner,b),(inner,a))]
            v.poly(pen,points,_shade(tone,.88+.18*max(0,math.sin(a))),.22)
        for rr in (r,inner):pen.poly(_circle(v,(0.,y,cz),(1,0,0),(0,0,1),rr),'none',.5)
    bank(p,24.,outer,36.)
    rotor=_fan(p,fg,v,fan_for(row),style,make_rotor,(0.,0.,cz),normal='front',frame=False)
    bank(fg,-26.,outer*.84,31.)
    return [rotor]

def draw_air(p,fg,row,style,fan_for,make_rotor):
    if row.get('id') not in _SUPPORTED:return None
    dims=row['dimensions_mm'];w,h,d=(dims[k] for k in ('width','height','depth'))
    under=row.get('fan_placement')=='under'
    # The low-profile factory installation is deliberately viewed from below:
    # showing a fan on top would describe a different, taller installation.
    v=_View(w,h,d,pitch=-28 if under else 25)
    if row['kind']=='radial_tower':return _radial(p,fg,v,row,style,fan_for,make_rotor)
    fan=fan_for(row);metal='#bfc9ce' if style in _ORIGINAL else p.body
    _base(p,v,style)
    if row['kind']=='dual_top_flow':
        _pipes(p,v,row,91.,style)
        _fins(p,v,93,112,24,47,'#39464e' if style in _ORIGINAL else metal,13)
        mid=type(p)(style);mid_frame=type(p)(style)
        lower=fan_for(dict(row,fan_model=row['fan_models'][1]))
        low_rotor=_fan(p,mid_frame,v,lower,style,make_rotor,(0,-5,73))
        mid.parts.extend(mid_frame.parts)
        _fins(mid,v,w*.96,d*.90,78,107,'#39464e' if style in _ORIGINAL else metal)
        upper=_fan(mid,fg,v,fan,style,make_rotor,(0,0,h))
        low_rotor['after_svg']=_svg(mid.finish())
        return [low_rotor,upper]
    bottom,top=(48.,70.) if under else (h-60.,h-26.)
    _pipes(p,v,row,(bottom+top)/2,style)
    # With an underside view the fin bank lies behind the installed fan.
    _fins(p,v,w*.96,d*.94,bottom,top,metal)
    rotor=_fan(p,fg,v,fan,style,make_rotor,(0,-12 if under else 0,31. if under else h),
               normal='down' if under else 'up')
    _wire_clips(fg,v,w*.96,d*.83,31 if under else top,h if not under else top)
    return [rotor]

