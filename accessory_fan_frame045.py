"""Physical frame aspect and source-linked mounting holes, no rotor transforms."""
import math

def _n(value):return format(float(value),'.4f').rstrip('0').rstrip('.') or '0'


def draw_frame(pen,x,y,size,row):
    nominal=row.get('size_mm',120);width=row.get('width_mm',nominal)
    axes=row.get('mount_pitch_axes_mm') if row.get('mount_pitch_axes_verified') else None
    pitch=row.get('mount_pitch_mm') if row.get('mount_pitch_verified') else None
    if not axes and not pitch and width==nominal:return False
    fw=size*width/nominal;left=x+(size-fw)/2;cx=x+size/2;cy=y+size/2
    px,py=axes if axes else (pitch,pitch) if pitch else (width*.83,nominal*.83)
    centers=[(cx+sx*px/nominal*size/2,cy+sy*py/nominal*size/2) for sx in (-1,1) for sy in (-1,1)]
    original=pen.style in ('miniature','classic','solid')
    tone=row.get('frame_color',pen.body) if original else pen.body
    pad=('#725549' if row.get('family','').startswith('noctua') else '#35434c') if original else pen.accent
    rounded=row.get('frame')=='round';radius=size*.437
    if rounded:
        # Ears follow the actual hole rectangle; diameter stays circular.
        half=size*.085
        for hx,hy in centers:
            ex=max(left,min(hx-half,left+fw-half*2));ey=max(y,min(hy-half,y+size-half*2))
            pen.rect(ex,ey,half*2,half*2,tone,size*.018,.55)
        outer='M'+_n(cx+size*.49)+' '+_n(cy)+' A'+_n(size*.49)+' '+_n(size*.49)+' 0 1 0 '+_n(cx-size*.49)+' '+_n(cy)+' A'+_n(size*.49)+' '+_n(size*.49)+' 0 1 0 '+_n(cx+size*.49)+' '+_n(cy)+' Z'
    else:
        cut=size*.065
        points=((left+cut,y),(left+fw-cut,y),(left+fw,y+cut),(left+fw,y+size-cut),(left+fw-cut,y+size),(left+cut,y+size),(left,y+size-cut),(left,y+cut))
        outer='M'+' L'.join(_n(a)+' '+_n(b) for a,b in points)+' Z'
    hole=' M'+_n(cx+radius)+' '+_n(cy)+' A'+_n(radius)+' '+_n(radius)+' 0 1 0 '+_n(cx-radius)+' '+_n(cy)+' A'+_n(radius)+' '+_n(radius)+' 0 1 0 '+_n(cx+radius)+' '+_n(cy)+' Z'
    pen.parts.append('<path data-frame-aspect="'+_n(width/nominal)+'" d="'+outer+hole+'" fill-rule="evenodd"'+pen._attrs(tone,.6)+'/>')
    for hx,hy in centers:
        if row.get('pads'):
            half=size*.045
            if row.get('pad_style')=='round':pen.ellipse(hx,hy,half,half,pad,.45)
            else:pen.rect(hx-half,hy-half,half*2,half*2,pad,size*.012,.45)
        pen.ellipse(hx,hy,size*.018,size*.018,pen.light,.4)
    if row.get('frame_rgb_ring'):pen.ellipse(cx,cy,size*.473,size*.473,'none',size*.025)
    if row.get('frame_rgb_sides'):
        for yy in (y+size*.045,y+size*.955):pen.line_to(left+fw*.17,yy,left+fw*.83,yy,size*.019)
    return True
