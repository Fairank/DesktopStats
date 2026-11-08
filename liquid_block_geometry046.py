"""Original bounded body references for retail blocks, motors and reservoirs.

No author catalog, device I/O, clock, copied photo or manufacturer CAD is used.
Source-observed structure is distinct from unverified port/fastener coordinates.
Canonical component axes are X width, Y height, Z depth; builder axes are X,Z,Y.
"""
import math

from assembly_cooling import _add, _sub, _mul, _dot, _basis
from assembly_geometry import ring
from assembly_detail import chamfer_rect, perforated_plate
from liquid_pack_schema046 import FACE_NORMALS


def _v(canonical, basis):
    local = (canonical[0], canonical[2], canonical[1])
    return tuple(sum(local[k] * basis[k][i] for k in range(3)) for i in range(3))


def _point(center, basis, x=0., y=0., z=0.):
    return _add(center, _v((x, y, z), basis))


def _bore(port):
    if port.get('tube_type') == 'soft' and port.get('tube_inner_mm'):
        return port['tube_inner_mm'] / 2
    return 8.8 if port.get('thread') == 'M20' else 5.1


def _shell(builder, name, size, offset, center, basis, part, ports, color, alpha=1., corner=.09, omit_faces=()):
    """One chamfered footprint with joined walls and genuinely pierced faces."""
    w,d,h=size['width'],size['depth'],size['height']
    extent = (w,d,h)
    body_center = _point(center, basis, *offset)
    sheet = min(1.2, max(.45, min(extent) * .04))
    outline=chamfer_rect(w,d,min(w,d)*corner)
    segments={'eco':8,'balanced':12,'close':16}[builder.level]
    for sign,face in ((1,'top'),(-1,'bottom')):
        if face in omit_faces:continue
        surface=_add(body_center,_mul(basis[2],sign*(h/2-sheet/2)))
        holes=[]
        for port in ports:
            if port['face']!=face:continue
            delta=_sub(port['position'],surface)
            if abs(_dot(delta,basis[2]))>sheet+.5:continue
            x,z=_dot(delta,basis[0]),_dot(delta,basis[1]);radius=_bore(port)
            if abs(x)+radius<w/2-.2 and abs(z)+radius<d/2-.2:holes.append((x,z,radius))
        builder.put(name+'-'+face,perforated_plate(outline,holes,sheet,segments=segments),color,surface,basis,part=part,alpha=alpha)
    for a,b in zip(outline,(*outline[1:],outline[0])):
        dx,dz=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dz)
        if length<.001:continue
        local_axes=((dx/length,dz/length,0.),(0.,0.,1.),(dz/length,-dx/length,0.))
        axes=tuple(tuple(sum(axis[k]*basis[k][i] for k in range(3)) for i in range(3)) for axis in local_axes)
        normal=axes[2]
        if any(_dot(normal,_v(FACE_NORMALS[face],basis))>.99 for face in omit_faces):continue
        surface=_add(_point(body_center,basis,(a[0]+b[0])/2,0,(a[1]+b[1])/2),_mul(normal,-sheet/2))
        holes=[]
        for port in ports:
            if port['face'] in ('top','bottom') or _dot(port['normal'],normal)<.99:continue
            delta=_sub(port['position'],surface)
            if abs(_dot(delta,normal))>sheet+.5:continue
            x,y=_dot(delta,axes[0]),_dot(delta,axes[1]);radius=_bore(port)
            if abs(x)+radius<length/2-.2 and abs(y)+radius<h/2-.2:holes.append((x,y,radius))
        builder.put(name+'-joined-walls',perforated_plate(chamfer_rect(length+.015,h,0.),holes,sheet,segments=segments),
                    color,surface,axes,part=part,alpha=alpha)


def _plate(builder, name, w, d, thickness, xyz, center, basis, part, color, ports=(), corner=.08):
    position = _point(center, basis, *xyz)
    holes = []
    for port in ports:
        if port['face'] not in ('top', 'bottom'):
            continue
        delta = _sub(port['position'], position)
        if abs(_dot(delta, basis[2])) > thickness + 2:
            continue
        x, z = _dot(delta, basis[0]), _dot(delta, basis[1])
        r = _bore(port)
        if abs(x) + r < w/2 - .1 and abs(z) + r < d/2 - .1:
            holes.append((x, z, r))
    builder.put(name, perforated_plate(chamfer_rect(w, d, min(w, d) * corner), holes, thickness,
                                     segments={'eco': 8, 'balanced': 12, 'close': 16}[builder.level]),
                color, position, basis, part=part)


def _round_cap(builder, name, radius, height, y, center, basis, part, color, ports):
    """Hollow circular cap with separately pierced top/bottom sheets."""
    segments = builder.segments
    position = _point(center, basis, 0, y, 0)
    builder.put(name + '-rim', ring(radius, max(.1, radius-1.1), height, segments),
                color, position, basis, part=part)
    polygon = tuple((math.cos(i * math.tau / segments) * radius,
                     math.sin(i * math.tau / segments) * radius) for i in range(segments))
    for sign, face in ((1, 'top'), (-1, 'bottom')):
        surface = _point(center, basis, 0, y + sign*(height/2-.4), 0)
        holes = []
        for port in ports:
            if port['face'] != face:
                continue
            delta = _sub(port['position'], surface)
            x, z = _dot(delta, basis[0]), _dot(delta, basis[1])
            r = _bore(port)
            if math.hypot(x, z) + r < radius-.3 and abs(_dot(delta, basis[2])) < 1.5:
                holes.append((x, z, r))
        vertices = perforated_plate(polygon, holes, .8,
                                   segments={'eco': 8, 'balanced': 12, 'close': 16}[builder.level])
        builder.put(name + '-' + face, vertices, color, surface, basis, part=part)


def _port_rims(builder, ports, basis, part, *, name='loop-open-reference-port-collars', metal=False):
    """Open, shallow face collars; never teeth or a fitting compatibility claim."""
    for port in ports:
        # Fixed hose barbs are built by their own pump function, not as G1/4.
        if port.get('tube_type') == 'soft' and port.get('thread') is None:
            continue
        r = _bore(port)
        axes = _basis(port['normal'], basis[0])
        builder.put(name, ring(r+1.15, r, .7, builder.segments), '#aab5b8' if metal else '#233740',
                    _add(port['position'], _mul(port['normal'], -.05)), axes, part=part)


def _display(builder, name, width, height, position, normal, basis, part, *, circular=False):
    axes = _basis(normal, basis[0])
    if circular:
        radius = width/2
        builder.put(name + '-metal-bezel', ring(radius, radius*.90, .9, builder.segments), '#7e9199', position, axes, part=part)
        builder.put(name + '-blank-window', ring(radius*.895, 0, .35, builder.segments), '#101c24',
                    _add(position, _mul(normal, .35)), axes, part=part)
    else:
        builder.box(name + '-blank-window', (width, height, .45), '#101c24', position, axes, part=part, bevel=True)


def _bracket(builder, row, body, center, basis, part):
    if not row.get('factory_bracket'):
        return
    ref = row['reference_envelope_mm']
    w, h, d = body['width'], body['height'], body['depth']
    if row['id']=='xspc-raystorm-edge-am5':
        outer_w,outer_d=ref['width']*.96,ref['depth']*.96
        inner_w,inner_d=w*.91,d*.91
        rail=(outer_w-inner_w)/2
        for sign in (-1,1):
            holes=[(0,z,2.1) for z in (-outer_d*.39,outer_d*.39)]
            plate=perforated_plate(chamfer_rect(rail,outer_d,2.),holes,1.6,segments=12)
            builder.put('loop-edge-four-sided-hold-down-frame',plate,'#2a3c44',
                        _point(center,basis,sign*(inner_w+rail)/2,h/2+.2,0),basis,part=part)
            _plate(builder,'loop-edge-four-sided-hold-down-frame',inner_w,(outer_d-inner_d)/2,1.6,
                   (0,h/2+.2,sign*(inner_d+(outer_d-inner_d)/2)/2),center,basis,part,'#2a3c44')
        return
    extended = row['id'] == 'koolance-cpu-400a-s'
    for xs in (-1, 1):
        for zs in (-1, 1):
            length = max(7., (ref['width']-w)/2 + 7)
            x, z = xs*(w/2+length*.23), zs*d*.37
            holes = [(xs*length*.19, -2.5 if extended else 0, 1.8)]
            if extended:
                holes.append((xs*length*.19, 2.5, 1.8))
            plate = perforated_plate(chamfer_rect(length, 12 if extended else 9, 1.8), holes, 1., segments=8)
            builder.put('loop-reference-socket-bracket-ears', plate, '#879aa0',
                        _point(center, basis, x, -h*.30, z), basis, part=part)
            if row['id'].startswith(('corsair-', 'phanteks-')):
                q = _point(center, basis, x+xs*length*.19, -h*.23, z)
                builder.put('loop-reference-captive-mount-screws', ring(2.3, 1., min(6., h*.25), 12),
                            '#31464e', q, basis, part=part)


def _cpu(builder, row, body, center, basis, part, ports):
    w, h, d = body['width'], body['height'], body['depth']
    family, identity = row['geometry_family'], row['id']
    clear = family == 'cpu_clear_square'
    dark = '#2a3439' if identity.startswith('koolance-') else '#28363d'
    _shell(builder, 'loop-cpu-clear-chamber' if clear else 'loop-cpu-source-shell', body,
           (0, 0, 0), center, basis, part, ports, '#8ca7ac' if clear else dark, .24 if clear else 1., .10)
    _plate(builder, 'loop-cpu-nickel-coldplate', w*.94, d*.94, min(1.7, h*.09),
           (0, -h/2+.8, 0), center, basis, part, '#aebabc')
    if clear:
        # Fin repetitions are explicitly bounded visual samples, not source fin counts.
        count = {'eco': 5, 'balanced': 9, 'close': 13}[builder.level]
        for i in range(count):
            builder.box('loop-reference-jetplate-fin-samples', (.6, d*.40, .55), '#9cb0b5',
                        _point(center, basis, (i-(count-1)/2)*w*.043, -h*.26, 0), basis, part=part)
        if identity == 'corsair-xc7-rgb-pro':
            radius = min(w, d)*.39
            frame=perforated_plate(chamfer_rect(w*.97,d*.97,min(w,d)*.11),[(0,0,radius*.96)],1.4,
                                   segments=builder.segments)
            builder.put('loop-xc7-pro-opaque-window-frame',frame,dark,_point(center,basis,0,h/2-.2,0),basis,part=part)
            builder.put('loop-xc7-open-circular-shroud', ring(radius, radius*.86, 2.1, builder.segments),
                        dark, _point(center, basis, 0, h/2-.7, 0), basis, part=part)
            for sign in (-1,1):
                _plate(builder,'loop-xc7-pro-pierced-port-bridge',w*.36,d*.22,1.0,
                       (sign*w*.32,h/2-.1,0),center,basis,part,dark,ports)
        elif identity == 'xspc-raystorm-edge-am5':
            pass  # Complete dry four-sided bracket is drawn by _bracket.
        else:
            for zs in (-1, 1):
                builder.box('loop-w9-silver-window-border', (w*.93, d*.10, 1.7), '#9eafb3',
                            _point(center, basis, 0, h/2-.4, zs*d*.44), basis, part=part, bevel=True)
            for xs in (-1,1):
                builder.box('loop-w9-silver-window-border',(w*.10,d*.93,1.7),'#9eafb3',
                            _point(center,basis,xs*w*.44,h/2-.4,0),basis,part=part,bevel=True)
    if identity == 'watercool-heatkiller-iv-pro-amd-acetal':
        _plate(builder, 'loop-heatkiller-center-metal-strip', w*.24, d*.88, .55,
               (0, h/2+.1, 0), center, basis, part, '#aebabe', ports)
    elif identity == 'alphacool-core1-black':
        _plate(builder, 'loop-core1-lower-silver-perimeter', w*1.01, d*1.01, .65,
               (0, -h*.30, 0), center, basis, part, '#aebabe')
        _port_rims(builder, ports, basis, part, name='loop-core1-nickel-port-collars', metal=True)
    elif identity == 'alphacool-xpx-pro-aurora-brass':
        _plate(builder, 'loop-xpx-recessed-panel-outline', w*.91, d*.91, .4,
               (0, h/2+.05, 0), center, basis, part, '#1e2c32', ports, corner=.15)
        builder.box('loop-source-observed-corner-argb-window', (w*.10, d*.035, .45), '#87c3cb',
                    _point(center, basis, w*.34, h/2+.5, d*.34), basis, part=part, bevel=True)
    elif identity.startswith('koolance-'):
        # Shallow inset cap seam, without turning opaque acetal into glass.
        _plate(builder, 'loop-koolance-inset-cap-panel', w*.94, d*.94, .4,
               (0, h/2+.05, 0), center, basis, part, '#303a3d', ports, corner=.08)
    elif identity=='phanteks-glacier-c370i':
        _plate(builder,'loop-c370-stepped-source-top-cover',w*.91,d*.91,.9,
               (0,h/2+.25,0),center,basis,part,'#3d535d',ports,corner=.15)
    if family == 'cpu_round_lcd':
        q = _point(center, basis, 0, h/2+.6, 0)
        _display(builder, 'loop-xc7-round-lcd', min(w, d)*.68, 0, q, basis[2], basis, part, circular=True)
        builder.put('loop-source-observed-display-rgb-ring', ring(min(w, d)*.365, min(w, d)*.351, .6, builder.segments),
                    '#8abdc9', q, basis, part=part)
    elif clear and row.get('observed_lighting'):
        # Light belongs to the clear chamber rim, not the external socket ears.
        builder.put('loop-source-observed-chamber-rgb-rim', ring(min(w, d)*.35, min(w, d)*.33, .55, builder.segments),
                    '#86bcc8', _point(center, basis, 0, h*.22, 0), basis, part=part)
    _bracket(builder, row, body, center, basis, part)
    if identity != 'alphacool-core1-black':
        _port_rims(builder, ports, basis, part)


def _motor(builder, row, body, center, basis, part):
    w, h, d = body['width'], body['height'], body['depth']
    radius = min(w, d)*.46
    identity = row['id']
    if row['geometry_family'] == 'pump_dc_lt_motor':
        builder.put('loop-dclt-thin-bare-motor', ring(radius, 0, h*.52, builder.segments), '#27363c',
                    _point(center, basis, 0, -h*.2, 0), basis, part=part)
        builder.put('loop-dclt-exposed-impeller-reference', ring(radius*.78, radius*.18, h*.10, builder.segments), '#29363d',
                    _point(center, basis, 0, h*.18, 0), basis, part=part)
        # The inspected official 13332 image shows six exposed swept vanes.
        # Their curves/height are original qualitative references, not CAD or
        # new tachometer bindings; this entire motor remains stationary.
        for i in range(6):
            phi=i*math.tau/6;outline=[]
            for side,steps in ((0,range(6)),(1,range(5,-1,-1))):
                for j in steps:
                    t=j/5;r=radius*(.23+.60*t)
                    angle=phi+math.radians(42*t+(17-8*t if side else 0))
                    outline.append((math.cos(angle)*r,math.sin(angle)*r))
            builder.put('loop-dclt-source-observed-static-vanes',perforated_plate(outline,[],h*.16,segments=8),'#2d414a',
                        _point(center,basis,0,h*.30,0),basis,part=part)
        builder.put('loop-dclt-exposed-ceramic-axle', ring(1.8, 0, h*.18, 12), '#c0c9c9',
                    _point(center, basis, 0, h*.28, 0), basis, part=part)
        for xs in (-1, 1):
            plate = perforated_plate(chamfer_rect(10, 9, 1.7), [(0, 0, 2)], 2., segments=8)
            builder.put('loop-dclt-opposite-fixing-ears', plate, '#293941',
                        _point(center, basis, xs*(w/2-5), -h*.22, 0), basis, part=part)
        return
    next_motor = identity == 'aquacomputer-d5-next'
    can_h = h*(.57 if next_motor else .72)
    can_y = h*(.14 if next_motor else -.08)
    builder.put('loop-d5-exposed-motor-can', ring(radius, 0, can_h, builder.segments),
                '#899ba0' if next_motor else '#26383f', _point(center, basis, 0, can_y, 0), basis, part=part)
    builder.put('loop-d5-stainless-rotor-shoulder', ring(radius*.99, radius*.48, h*.10, builder.segments),
                '#a8b5b8' if identity != 'alphacool-vpp-apex' else '#33474f',
                _point(center, basis, 0, h*.39, 0), basis, part=part)
    builder.put('loop-d5-exposed-unthreaded-rotor-hub', ring(radius*.47, radius*.20, h*.10, builder.segments), '#23343b',
                _point(center, basis, 0, h*.45, 0), basis, part=part)
    if identity == 'alphacool-vpp-apex':
        builder.put('loop-apex-white-ceramic-axle', ring(2.6, 0, 2.2, 12), '#c1cdcf',
                    _point(center, basis, 0, h*.48, 0), basis, part=part)
    if next_motor:
        ctrl = dict(width=w*.95, height=h*.30, depth=d*.94)
        _shell(builder, 'loop-d5-next-controller', ctrl, (0, -h*.32, 0), center, basis, part, (), '#273c45')
        q = _point(center, basis, 0, -h*.28, d*.47+.2)
        _display(builder, 'loop-d5-next-oled', w*.58, h*.12, q, _v((0, 0, 1), basis), basis, part)
        face = _basis(_v((0, 0, 1), basis), basis[0])
        for xs in (-1, 0, 1):
            builder.put('loop-d5-next-three-control-buttons', ring(1.4, 0, .6, 12), '#9baeb3',
                        _point(center, basis, xs*w*.17, -h*.41, d*.47+.4), face, part=part)
        builder.put('loop-source-observed-motor-base-rgb-band', ring(radius*.98, radius*.95, 2.3, builder.segments), '#88c3cb',
                    _point(center, basis, 0, -h*.45, 0), basis, part=part)
        _mount_feet(builder, w, h, d, center, basis, part, inside=True)


def _mount_feet(builder, w, h, d, center, basis, part, inside=False):
    _plate(builder, 'loop-reference-mounting-bottom-plate', w*1.04, d*1.04, 1.3,
           (0, -h/2+4.2 if inside else -h/2-1.1, 0), center, basis, part, '#344a54')
    for xs in (-1, 1):
        for zs in (-1, 1):
            builder.put('loop-reference-rubber-decoupling-feet', ring(2.7, 0, 4., 12), '#31434c',
                        _point(center, basis, xs*w*.40, -h/2+2 if inside else -h/2-3, zs*d*.40), basis, part=part)


def _pump_complete(builder, row, body, center, basis, part, ports):
    w, h, d = body['width'], body['height'], body['depth']
    if row['id'] == 'koolance-pmp450':
        # Reference full envelope includes its 13 mm hose barbs and steel foot.
        normal = _v((0, 0, 1), basis)
        axes = _basis(normal, basis[0])
        motor_c = _point(center, basis, 0, -h*.055, -d*.05)
        radius = w*.43
        builder.put('loop-pmp450-rear-motor', ring(radius*.80, 0, d*.43, builder.segments), '#9caab0',
                    _point(center, basis, 0, -h*.055, -d*.24), axes, part=part)
        builder.put('loop-pmp450-ribbed-lock-ring', ring(radius, radius*.92, d*.18, builder.segments), '#273b43', motor_c, axes, part=part)
        ribs = {'eco': 10, 'balanced': 14, 'close': 18}[builder.level]
        for i in range(ribs):
            angle = i*math.tau/ribs
            q = _add(motor_c, _add(_mul(axes[0], math.cos(angle)*radius), _mul(axes[1], math.sin(angle)*radius)))
            builder.box('loop-pmp450-reference-lock-grip-ribs', (2., 3., d*.17), '#2c414a', q, axes, part=part)
        # Hollow volute case has a front opening and is not a G1/4 top.
        volute = dict(width=w*.68, height=d*.36, depth=w*.68)
        volute_center=_point(center,basis,0,-h*.055,d*.23)
        projected = []
        for port in ports:
            surface = (-h*.055+volute['depth']/2 if port['face']=='top' else d*.23+volute['height']/2)
            normal = port['normal']
            axis = basis[2] if port['face']=='top' else basis[1]
            delta = _dot(_sub(port['position'], center), axis)-surface
            projected.append(dict(port,face='rear' if port['face']=='top' else 'top',
                                  position=_sub(port['position'],_mul(normal,delta))))
        _shell(builder,'loop-pmp450-rounded-hydraulic-volute',volute,(0,0,0),volute_center,axes,part,projected,'#293d45',corner=.30)
        for port in ports:
            bore = port['tube_inner_mm']/2
            axes2 = _basis(port['normal'], basis[0])
            # Two open molded barbs, with finite source-like retaining lip.
            surface = (-h*.055+volute['depth']/2 if port['face']=='top' else d*.23+volute['height']/2)
            axis = basis[2] if port['face']=='top' else basis[1]
            length = _dot(_sub(port['position'], center), axis)-surface+.4
            q = _add(port['position'], _mul(port['normal'], -length/2))
            builder.put('loop-pmp450-open-13mm-hose-barbs', ring(bore+.9, bore, length, builder.segments), '#293d45', q, axes2, part=part)
            builder.put('loop-pmp450-barb-retaining-lips', ring(bore+1.3, bore, 1.0, builder.segments), '#314a54',
                        _add(port['position'], _mul(port['normal'], -.5)), axes2, part=part)
        builder.box('loop-pmp450-steel-foot', (w*.67, d*.84, 1.4), '#52666f',
                    _point(center, basis, 0, -h/2+.7, 0), basis, part=part)
        for sign in (-1,1):
            builder.box('loop-pmp450-source-u-bracket-uprights',(2.,d*.09,h*.62),'#52666f',
                        _point(center,basis,sign*w*.28,-h*.18,d*.19),basis,part=part)
        return
    clear_top = row['geometry_family'] == 'pump_ddc_complete'
    if clear_top:
        top_h = h*.38
        _shell(builder, 'loop-qx5-clear-pump-top', dict(width=w, height=top_h, depth=d),
               (0, h/2-top_h/2, 0), center, basis, part, ports, '#92acb2', .25)
        builder.box('loop-qx5-black-motor-base', (w, d, h-top_h), '#2c414a',
                    _point(center, basis, 0, -top_h/2, 0), basis, part=part, bevel=True)
        _plate(builder, 'loop-qx5-dark-top-insert', w*.92, d*.92, .4,
               (0, h/2+.1, 0), center, basis, part, '#25383f', ports)
        for xs in (-1, 1):
            for zs in (-1, 1):
                builder.put('loop-qx5-four-corner-tie-bolts', ring(1.2, 0, top_h*.9, 12), '#a5b4b8',
                            _point(center, basis, xs*w*.40, h/2-top_h/2, zs*d*.40), basis, part=part)
        builder.put('loop-source-observed-pump-top-halo', ring(w*.40, w*.38, .65, builder.segments), '#88bdc8',
                    _point(center, basis, 0, h/2-top_h+1, 0), basis, part=part)
    else:
        _shell(builder, 'loop-compact-motorless-pump-top', body, (0, 0, 0), center, basis, part, ports, '#293e48')
        _plate(builder, 'loop-solotop-removable-aluminum-plate', w*.91, d*.91, .5,
               (0, h/2+.15, 0), center, basis, part, '#304954', ports, corner=.13)
    _port_rims(builder, ports, basis, part)


def _reservoir(builder, row, body, center, basis, part, ports):
    w, h, d = body['width'], body['height'], body['depth']
    identity, family = row['id'], row['geometry_family']
    motor = row.get('contains_motor', False)
    rect = family == 'pump_reservoir_rect_tube'
    aqua = identity.startswith('aquacomputer-ultitube')
    cage = identity.startswith('watercool-heatkiller-tube') or identity.startswith('alphacool-eisbecher')
    motor_h = min(55., h*.34) if motor else 0.
    top_h = min(18., h*.12)
    bottom_h = min(37., h*.23)
    if identity.startswith('xspc-photon'):
        bottom_h=min(28.,h*.16)
    # Keep the lower hydraulic housing around the actual declared side ports.
    side_y = [_dot(_sub(p['position'], center), basis[2]) for p in ports if p['face'] in ('front', 'rear', 'left', 'right')]
    if side_y:
        lower = min(side_y)-7.5
        upper = max(side_y)+7.5
        base_y = (lower+upper)/2
        bottom_h = max(bottom_h, upper-lower)
    else:
        base_y = -h/2+motor_h+bottom_h/2
    # Source-verified dimensions already include the sold end caps. A small
    # reservoir must not grow a taller base below its stated overall height.
    base_y=max(-h/2+bottom_h/2,min(base_y,h/2-top_h-bottom_h/2))
    base_bottom, base_top = base_y-bottom_h/2, base_y+bottom_h/2
    tube_top = h/2-top_h
    tube_bottom = base_top
    tube_h = max(6., tube_top-tube_bottom)
    radius = min(row.get('tank_diameter_mm') or min(w, d)*.88, min(w, d)*.96)/2
    tube_y = (tube_top+tube_bottom)/2
    if rect:
        _shell(builder, 'loop-xd5-rounded-rectangular-clear-tank', dict(width=w*.85, height=tube_h, depth=d*.85),
               (0, tube_y, 0), center, basis, part, (), '#93b0b8', .22, .17)
    else:
        builder.put('loop-dry-source-reservoir-tube', ring(radius, radius-1.2, tube_h, builder.segments), '#91aeb5',
                    _point(center, basis, 0, tube_y, 0), basis, part=part, alpha=.22)
    if identity.startswith('xspc-photon'):
        _round_cap(builder,'loop-photon-round-bottom-cap',min(w,d)*.49,bottom_h,base_y,
                   center,basis,part,'#2c424b',ports)
    else:
        _shell(builder, 'loop-source-hydraulic-reservoir-base', dict(width=w, height=bottom_h, depth=d),
               (0, base_y, 0), center, basis, part, ports, '#2c424b', corner=.13 if aqua else .08)
    top_y = h/2-top_h/2
    if cage or rect:
        _shell(builder, 'loop-square-source-reservoir-lid', dict(width=w, height=top_h, depth=d),
               (0, top_y, 0), center, basis, part, ports, '#2c414b', corner=.13)
    else:
        _round_cap(builder, 'loop-round-source-reservoir-lid', min(w, d)*.49, top_h, top_y,
                   center, basis, part, '#2d424b', ports)
    if motor:
        # The motor remains below the hydraulic base, never a solid blocker
        # directly behind its observed front connection throats.
        actual_motor_h = max(12., base_bottom+h/2)
        if identity == 'corsair-xd5-rgb-elite-lcd':
            _shell(builder,'loop-xd5-lcd-armored-pump-housing',dict(width=w*.96,height=actual_motor_h,depth=d*.96),
                   (0,-h/2+actual_motor_h/2,0),center,basis,part,(),'#344a54',corner=.17)
        else:
            builder.put('loop-sold-included-pump-motor', ring(min(w,d)*.43, 0, actual_motor_h, builder.segments), '#2b4049',
                        _point(center, basis, 0, -h/2+actual_motor_h/2, 0), basis, part=part)
        if aqua:
            face_normal = _v((0,0,1), basis)
            ctrl_h=actual_motor_h*.39
            _shell(builder,'loop-included-d5-next-controller',dict(width=w*.95,height=ctrl_h,depth=d*.94),
                   (0,-h/2+ctrl_h/2,0),center,basis,part,(),'#2b4049')
            q = _point(center, basis, 0, -h/2+ctrl_h*.61, d*.47+.2)
            _display(builder, 'loop-included-d5-next-oled', w*.57, ctrl_h*.32, q, face_normal, basis, part)
            face=_basis(face_normal,basis[0])
            for sign in (-1,0,1):
                builder.put('loop-included-d5-next-three-control-buttons',ring(1.2,0,.5,12),'#a6b5b9',
                            _point(center,basis,sign*w*.17,-h/2+ctrl_h*.20,d*.47+.3),face,part=part)
            builder.put('loop-source-observed-motor-base-rgb-band', ring(min(w,d)*.44, min(w,d)*.42, 2.3, builder.segments), '#89c2c9',
                        _point(center, basis, 0, -h/2+3, 0), basis, part=part)
            builder.box('loop-source-observed-motor-base-rgb-band',(w*.74,1.0,.45),'#89c2c9',
                        _point(center,basis,0,-h/2+1.3,d*.47+.3),face,part=part)
        if identity == 'corsair-xd5-rgb-elite-lcd':
            _display(builder, 'loop-xd5-round-front-lcd', min(w,d)*.48, 0,
                     _point(center, basis, 0, -h/2+actual_motor_h*.48, d*.48+.35), _v((0,0,1), basis), basis, part, circular=True)
    elif row.get('requires_motor'):
        builder.put('loop-empty-unthreaded-d5-motor-seat', ring(min(w,d)*.43,min(w,d)*.34,2.5,builder.segments), '#304a54',
                    _point(center,basis,0,base_bottom-1.25,0),basis,part=part)
    if cage:
        for xs in (-1,1):
            for zs in (-1,1):
                builder.box('loop-source-four-external-support-struts',(3.4,3.4,tube_h+top_h*.4),'#344b56',
                            _point(center,basis,xs*w*.42,tube_y,zs*d*.42),basis,part=part,bevel=True)
    if identity.startswith('xspc-photon'):
        builder.box('loop-photon-rear-backbone',(w*.72,2.,tube_h+top_h*.8),'#324b55',
                    _point(center,basis,0,tube_y,-d*.46),basis,part=part,bevel=True)
        builder.box('loop-source-observed-photon-rear-rgb-strip',(w*.08,.7,tube_h*.88),'#8dc4cb',
                    _point(center,basis,-w*.27,tube_y,-d*.435),basis,part=part,bevel=True)
    if 'top_return_drop_tube' in row['geometry_features'] or rect or identity.startswith('alphacool-eisbecher'):
        builder.put('loop-reference-return-drop-tube',ring(4.8,3.5,tube_h*.58,builder.segments),'#8ca8b0',
                    _point(center,basis,0,tube_top-tube_h*.29,0),basis,part=part,alpha=.40)
    if identity=='thermaltake-pacific-pr22-d5-plus':
        for fraction in (.15,.75):
            builder.put('loop-pr22-source-cap-groove-rims',ring(min(w,d)*.495,min(w,d)*.48,.7,builder.segments),'#49616b',
                        _point(center,basis,0,h/2-top_h*fraction,0),basis,part=part)
        motor_span=max(12.,base_bottom+h/2)
        builder.put('loop-pr22-source-motor-locking-hoop',ring(min(w,d)*.45,min(w,d)*.43,4.,builder.segments),'#4c646e',
                    _point(center,basis,0,-h/2+motor_span*.72,0),basis,part=part)
        for sign in (-1,1):
            builder.box('loop-pr22-source-mounting-uprights',(2.,d*.46,motor_span*.88),'#405a66',
                        _point(center,basis,sign*w*.43,-h/2+motor_span*.44,0),basis,part=part)
        foot=perforated_plate(chamfer_rect(w*.96,d*.85,3.),[(sign*w*.36,d*.28,2.3) for sign in (-1,1)],1.1,segments=12)
        builder.put('loop-pr22-source-mounting-feet-reference',foot,'#405a66',_point(center,basis,0,-h/2+.6,0),basis,part=part)
    if cage or rect or aqua:
        # A few pierced samples suggest the source anti-vortex floor, not its
        # actual perforation count or fluid stream geometry.
        holes=[(x*radius*.35,z*radius*.35,2.2) for x,z in ((-1,-1),(1,-1),(-1,1),(1,1),(0,0))]
        grid=perforated_plate(chamfer_rect(radius*1.4,radius*1.4,3.),holes,.6,segments=8)
        builder.put('loop-reference-anti-vortex-floor-samples',grid,'#91a6ad',_point(center,basis,0,tube_bottom+1.1,0),basis,part=part)
    for zone in row.get('observed_lighting',()):
        if 'rgb' not in zone.lower() or 'motor' in zone or 'rear' in zone:
            continue
        y=tube_bottom+2 if 'base' in zone else tube_top-1
        builder.put('loop-source-observed-reservoir-rgb-ring',ring(radius*1.03,radius*.98,1.2,builder.segments),'#87c1cb',
                    _point(center,basis,0,y,0),basis,part=part)
    if aqua or rect:
        _mount_feet(builder,w,h,d,center,basis,part)
    _port_rims(builder,ports,basis,part)


def _compact_or_flat(builder,row,body,center,basis,part,ports):
    w,h,d=body['width'],body['height'],body['depth']
    flat=row['geometry_family']=='pump_reservoir_flat'
    xd3=row['id']=='corsair-xd3-rgb'
    if xd3:
        _xd3(builder,row,body,center,basis,part,ports)
        return
    # Separate transparent reservoir chamber from the rear motor attachment.
    depth=d*.34 if flat else d*.65
    offset=d/2-depth/2
    _shell(builder,'loop-flat-clear-reservoir-body' if flat else 'loop-compact-clear-reservoir-body',
           dict(width=w,height=h,depth=depth),(0,0,offset),center,basis,part,ports,'#91adb4',.24,.06)
    if flat:
        for xs in (1,):
            builder.box('loop-r260-narrow-side-armor',(w*.10,depth*.9,h*.98),'#344b54',
                        _point(center,basis,xs*w*.45,0,offset),basis,part=part,bevel=True)
        for side in (-1,1):
            count={'eco':5,'balanced':7,'close':9}[builder.level]
            for i in range(count):
                y=(i/(count-1)-.5)*h*.88
                face=_basis(_v((0,0,1),basis),basis[0])
                builder.put('loop-r260-reference-perimeter-fasteners',ring(1.3,.5,.7,12),'#69808a',
                            _point(center,basis,side*w*.39,y,d/2+.3),face,part=part)
        builder.box('loop-source-observed-r260-side-rgb-strip',(w*.025,h*.88,.7),'#87c3cc',
                    _point(center,basis,w*.36,0,d/2+.4),_basis(_v((0,0,1),basis),basis[0]),part=part)
    if row.get('contains_motor'):
        normal=_v((0,0,-1),basis);axes=_basis(normal,basis[0])
        motor_y=-h*.30 if flat else 0
        builder.put('loop-sold-rear-pump-motor',ring(min(w,h)*(.30 if flat else .34),0,d-depth,builder.segments),'#2b424c',
                    _point(center,basis,0,motor_y,-depth/2),axes,part=part)
    elif row.get('requires_motor'):
        axes=_basis(_v((0,0,-1),basis),basis[0])
        builder.put('loop-empty-rear-d5-seat',ring(min(w,h)*.36,min(w,h)*.30,2.,builder.segments),'#2d424a',
                    _point(center,basis,0,0,-d/2),axes,part=part)
    if row['id']=='xspc-d5-argb-mini-tank':
        builder.put('loop-source-observed-mini-tank-base-halo',ring(min(w,d)*.39,min(w,d)*.37,.7,builder.segments),'#8dc4cc',
                    _point(center,basis,0,-h*.43,d*.10),basis,part=part)
    _port_rims(builder,ports,basis,part)


def _xd3(builder,row,body,center,basis,part,ports):
    """Opaque compact case, open circular front window and pierced bridges."""
    w,h,d=body['width'],body['height'],body['depth']
    depth=d*.72;offset=d/2-depth/2;dark='#293d46'
    _shell(builder,'loop-xd3-opaque-faceted-case',dict(width=w,height=h,depth=depth),
           (0,0,offset),center,basis,part,ports,dark,corner=.15,omit_faces=('front',))
    face=_basis(_v((0,0,1),basis),basis[0]);radius=min(w,h)*.37
    # Square faceted outer panel, with a genuinely open circular chamber area.
    panel=perforated_plate(chamfer_rect(w,h,min(w,h)*.15),[(0,0,radius)],1.1,segments=builder.segments)
    builder.put('loop-xd3-open-window-shroud',panel,dark,_point(center,basis,0,0,d/2-.55),face,part=part)
    window_outline=tuple((math.cos(i*math.tau/builder.segments)*radius*.985,math.sin(i*math.tau/builder.segments)*radius*.985)
                         for i in range(builder.segments))
    window_holes=[]
    for port in ports:
        if port['face']=='front':
            delta=_sub(port['position'],center)
            window_holes.append((_dot(delta,basis[0]),-_dot(delta,basis[2]),_bore(port)))
    builder.put('loop-xd3-clear-front-chamber-window',perforated_plate(window_outline,window_holes,.55,segments=builder.segments),'#92aeb8',
                _point(center,basis,0,0,d/2-1.4),face,part=part,alpha=.24)
    for port in ports:
        if port['face']!='front':continue
        delta=_sub(port['position'],center);px=_dot(delta,basis[0]);py=_dot(delta,basis[2])
        sign=1 if px>=0 else -1;cx=sign*w*.32
        bridge=perforated_plate(chamfer_rect(w*.36,h*.25,min(w,h)*.05),[(px-cx,0,_bore(port))],1.5,
                                segments={'eco':8,'balanced':12,'close':16}[builder.level])
        builder.put('loop-xd3-opposing-pierced-front-port-bridges',bridge,dark,
                    _point(center,basis,cx,py,d/2-.6),face,part=part)
    builder.put('loop-source-observed-xd3-front-chamber-rgb-rim',ring(radius*.99,radius*.96,.7,builder.segments),'#8abcc9',
                _point(center,basis,0,0,d/2-1.0),face,part=part)
    builder.box('loop-xd3-included-rear-ddc-motor',(w*.62,d*.28,h*.62),'#2d424c',
                _point(center,basis,0,0,-d*.36),basis,part=part,bevel=True)
    count={'eco':3,'balanced':5,'close':7}[builder.level]
    for i in range(count):
        builder.box('loop-xd3-reference-internal-divider-samples',(.65,d*.13,h*.45),'#657e88',
                    _point(center,basis,(i-(count-1)/2)*w*.08,-h*.05,d*.17),basis,part=part)
    _port_rims(builder,ports,basis,part,metal=True)


def build_body(builder,row,center,basis,part,body,ports):
    """Draw four non-fitting/tube categories; return the unchanged port frames."""
    if row['part_kind']=='cpu_block':
        _cpu(builder,row,body,center,basis,part,ports)
    elif row['form']=='pump_body':
        _motor(builder,row,body,center,basis,part)
    elif row['part_kind']=='pump':
        _pump_complete(builder,row,body,center,basis,part,ports)
    elif row['geometry_family'] in ('pump_reservoir_compact','pump_reservoir_flat','reservoir_flat'):
        _compact_or_flat(builder,row,body,center,basis,part,ports)
    else:
        _reservoir(builder,row,body,center,basis,part,ports)
    return ports
