"""Original world-projected centre-fan and low-profile cooler structures.

Factory envelopes and fan placements are preserved. Fin repetition, shell
vents, spring clips and hidden heatpipe routing are illustrative samples,
never manufacturer CAD or a claim about the actual internal fin/vent count.
"""
from accessory_cooling_details040 import (
    _View,_base,_pipe,_box,_ORIGINAL,_shade,_path,_fins,_wire_clips,
)


def _factory_fan(row,fan_for):
    """Supply documented bundled size when its retail identity is unknown."""
    fan=dict(fan_for(row))
    fan.setdefault('size_mm',row.get('fan_reference_mm',120))
    fan.setdefault('width_mm',fan['size_mm'])
    fan.setdefault('depth_mm',row.get('fan_reference_depth_mm',25))
    return fan


def _assassin_shell(p,v,w,h,d,bottom,style):
    tone='#29343b' if style in _ORIGINAL else p.dark
    # One enclosure surrounds both banks and the centre fan. The right side is
    # visible from this projection; it is not another thick fin bank.
    p.parts.append('<g data-cooler-structure="assassin-shell-reference">')
    v.poly(p,[(w*.49,-d/2,bottom),(w*.49,d/2,bottom),
              (w*.49,d/2,h-1),(w*.49,-d/2,h-1)],_shade(tone,.78),.45)
    outer=[(-w*.49,-d/2,h),(w*.49,-d/2,h),
           (w*.49,d/2,h),(-w*.49,d/2,h)]
    # Actual missing areas in the static top plate; twelve elongated reference
    # samples echo the 3-D enclosure's open vent strip without claiming OEM CAD.
    holes=[]
    for i in range(12):
        x=(i-5.5)*w*.065;half=w*.014
        holes.append([(x-half,-d*.34,h),(x+half,-d*.34,h),
                      (x+half,d*.34,h),(x-half,d*.34,h)])
    path=_path([v.at(q) for q in outer])+''.join(_path([v.at(q) for q in hole]) for hole in holes)
    p.parts.append('<path data-reference-vent-samples="12" d="'+path+
                   '" fill-rule="evenodd"'+p._attrs(tone,.42)+'/>')
    # A narrow folded leading edge grounds the thin cover above the fin face.
    v.poly(p,[(-w*.49,-d/2,h-2),(w*.49,-d/2,h-2),
              (w*.49,-d/2,h),(-w*.49,-d/2,h)],_shade(tone,.92),.32)
    p.parts.append('</g>')


def draw_center(p,fg,row,style,fan_for,make_rotor):
    if row.get('kind')!='dual_tower' or row.get('fan_layout')!='center':return None
    from accessory_cooling_details040 import _fan
    dims=row['dimensions_mm'];w,h,d=(dims[key] for key in ('width','height','depth'))
    fan=_factory_fan(row,fan_for);fd=fan['depth_mm'];size=fan['size_mm']
    depth=row.get('heatsink_depth_mm',row.get('heatsink_dimensions_mm',{}).get('depth',d))
    gap=fd+4;thickness=max(5,(depth-gap)/2);offset=gap/2+thickness/2
    bottom=max(25,h-size+3);top=h-5;v=_View(w,h,d,yaw=29,pitch=19)
    metal=row.get('fin_color','#abb5bd') if style in _ORIGINAL else p.body
    _base(p,v,style)
    pipe_tone=row.get('pipe_color','#aab4b8') if style in _ORIGINAL else p.accent
    pipes=row.get('heatpipes',0)
    for i in range(pipes):
        x=(i-(pipes-1)/2)*min(10,w/(pipes+2))
        _pipe(p,v,[(x,offset,top),(x,offset,12),(x,0,5),(x,0,5),(x,0,5),(x,-offset,12),(x,-offset,top)],pipe_tone,.95)
    def bank(pen,center):
        for i in range(27):
            z=bottom+(top-bottom)*i/26
            # Horizontal open fin sheets, not a solid block or vertical louvers.
            poly=[(-w*.475,center-thickness/2,z),(w*.475,center-thickness/2,z),
                  (w*.475,center+thickness/2,z),(-w*.475,center+thickness/2,z)]
            v.poly(pen,poly,_shade(metal,.96+(i%2)*.04),.22)
        if row.get('top_style') in ('dark_caps','stealth_caps','assassin_shell'):
            tone='#253239' if style in _ORIGINAL else p.dark
            # Offset box uses the same world transform as the fin bank.
            poly=[(-w*.48,center-thickness/2,top+1),(w*.48,center-thickness/2,top+1),
                  (w*.48,center+thickness/2,top+1),(-w*.48,center+thickness/2,top+1)]
            v.poly(pen,poly,tone,.5)
    bank(p,offset)
    rotor=_fan(p,fg,v,fan,style,make_rotor,(0,-fd/2,(bottom+top)/2),normal='front')
    bank(fg,-offset)
    if row.get('top_style')=='assassin_shell':
        _assassin_shell(fg,v,w,h,depth,bottom,style)
    return [rotor]


def draw_low_profile(p,fg,row,style,fan_for,make_rotor):
    """A horizontal fan over a genuinely short, open vertical-fin bank."""
    if row.get('kind')!='low_profile' or row.get('c_shape'):return None
    from accessory_cooling_details040 import _fan
    w,h,d=(row['dimensions_mm'][key] for key in ('width','height','depth'))
    fan=_factory_fan(row,fan_for);fd=fan['depth_mm']
    v=_View(w,h,d,yaw=27,pitch=32)
    bottom=8.;top=max(bottom+3,h-fd-.6)
    metal=row.get('fin_color','#abb7bd') if style in _ORIGINAL else p.body
    tone=row.get('pipe_color','#a6b1b7') if style in _ORIGINAL else p.accent
    p.parts.append('<g data-cooler-structure="horizontal-low-profile-reference">')
    _base(p,v,style)
    pipes=row.get('heatpipes',0)
    for i in range(pipes):
        x=(i-(pipes-1)/2)*min(9.,w/(pipes+2))
        z=min(top-2,bottom+8)
        # Continuous U pipes return through the underside of the small bank;
        # exact coldplate channels and tube bend radii remain reference.
        _pipe(p,v,[(x,d*.36,z),(x,d*.36,7),(x,d*.24,5),(x,0,5),
                   (x,-d*.24,5),(x,-d*.36,7),(x,-d*.36,z)],tone,.85)
    _fins(p,v,w*.95,d*.94,bottom,top,metal,32)
    p.parts.append('</g>')
    rotor=_fan(p,fg,v,fan,style,make_rotor,(0,0,h),normal='up')
    _wire_clips(fg,v,w*.95,d*.86,top-4,h-fd+2)
    return [rotor]
