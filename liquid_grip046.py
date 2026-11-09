"""Shallow reference grip marks on the actual faceted compression sleeve."""
import math
from assembly_geometry import _quad

def grip_strips(radius,length,segments,count,diamond=True):
    """No ideal-circle rods outside a low-detail polygonal fitting body."""
    out=[];period=math.tau/segments;half_width=.08/radius
    def point(phi,z):
        middle=(math.floor(phi/period)+.5)*period
        # The sleeve is an inscribed polygon. Follow its real face, with only
        # a tiny normal offset to prevent coplanar drawing flicker.
        r=(radius*math.cos(period/2)+.012)/math.cos(phi-middle)
        return r*math.cos(phi),r*math.sin(phi),z
    for i in range(count):
        angle=i*math.tau/count
        for sign in ((-1,1) if diamond else (0,)):
            first,last=angle-sign*.21,angle+sign*.21
            values={0.,1.}
            if sign:
                lo,hi=sorted((first,last))
                for j in range(math.floor(lo/period),math.ceil(hi/period)+1):
                    t=(j*period-first)/(last-first)
                    if 0<t<1:values.add(t)
            values=sorted(values)
            for a,b in zip(values,values[1:]):
                pa,pb=first+(last-first)*a,first+(last-first)*b
                za,zb=(a-.5)*length*.64,(b-.5)*length*.64
                _quad(out,point(pa-half_width,za),point(pa+half_width,za),
                      point(pb+half_width,zb),point(pb-half_width,zb))
    return tuple(out)
