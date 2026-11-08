"""Original standalone GPU-block assemblies, with separate body/terminal/backplate.

Only source-observed families drive the exterior. Channels, socket positions,
layer depths and sampled fasteners are bounded illustration references, never
GPU mounting coordinates, OEM CAD, inferred pump telemetry or connected loops.
"""
import math
from dataclasses import replace

LIMITS={'eco':2600,'balanced':5200,'close':9000}
IDENTITY=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))

def _add(a,b):return tuple(x+y for x,y in zip(a,b))
def _mul(a,s):return tuple(x*s for x in a)
def _dot(a,b):return sum(x*y for x,y in zip(a,b))
def _sub(a,b):return tuple(x-y for x,y in zip(a,b))
def _vector(v,basis):return tuple(sum(v[k]*basis[k][i] for k in range(3)) for i in range(3))

def _plate(builder,name,polygon,thickness,z,tone,part,holes=(),alpha=1.):
    from assembly_detail import perforated_plate
    vertices=perforated_plate(polygon,holes,thickness,segments={'eco':12,'balanced':16,'close':24}[builder.level],clip_walls=True)
    builder.put(name,vertices,tone,(0.,0.,z),part=part,alpha=alpha)

def _rect(cx,cy,w,h,corner=0.):
    from assembly_detail import chamfer_rect
    points=[]
    for x,y in chamfer_rect(w,h,corner):
        point=(x+cx,y+cy)
        if not points or math.dist(point,points[-1])>1e-9:points.append(point)
    if len(points)>1 and math.dist(points[0],points[-1])<1e-9:points.pop()
    return tuple(points)

def _rounded_rect(w,h,r,steps=4):
    out=[];r=min(r,w/3,h/3)
    for cx,cy,start in ((w/2-r,h/2-r,0),(-w/2+r,h/2-r,90),(-w/2+r,-h/2+r,180),(w/2-r,-h/2+r,270)):
        for i in range(steps+1):
            angle=math.radians(start+i*90/steps);out.append((cx+r*math.cos(angle),cy+r*math.sin(angle)))
    return tuple(out)

def _terminal(builder,row,config,extent,root):
    """Pierced face sheets and true open collars; no assumed unseen sockets."""
    from assembly_cooling import _basis
    from assembly_geometry import ring,_quad
    from assembly_detail import perforated_plate,chamfer_rect
    from liquid_pack_schema046 import FACE_NORMALS
    w,h,d=extent;g=config['geometry_reference'];cx,cy=g['center_uv'][0]*w,g['center_uv'][1]*h
    tw,th=g['span_uv'][0]*w,g['span_uv'][1]*h
    center=(cx,cy,0.);size=(tw,th,d);part=root+':terminal';ports=[]
    for p in config['ports']:
        position=tuple(p['position_normalized'][i]*extent[i] for i in range(3))
        ports.append(dict(p,position=position,normal=FACE_NORMALS[p['face']],part_id=part,geometry_position_reference=True))
    clear=row['geometry_family']=='gpu_aurora_clear'
    tone='#91a9af' if clear else '#657078' if row['geometry_family']=='gpu_carbon_server' else '#25313a'
    sheet=.8
    faces=((0,-1,'left'),(0,1,'right'),(1,-1,'bottom'),(1,1,'top'),(2,-1,'rear'),(2,1,'front'))
    rounded='rounded_terminal_fascia' in row['geometry_features']
    if rounded:
        outline=_rounded_rect(tw,th,min(3.3,th*.16),2 if builder.level=='eco' else 4);walls=[]
        for a,b in zip(outline,(*outline[1:],outline[0])):
            _quad(walls,(a[0]+cx,a[1]+cy,-d/2),(b[0]+cx,b[1]+cy,-d/2),(b[0]+cx,b[1]+cy,d/2),(a[0]+cx,a[1]+cy,d/2))
        builder.put('loop-gpu-rounded-terminal-perimeter',tuple(walls),tone,part=part,alpha=.5 if clear else 1.)
    for axis,sign,face in faces:
        if rounded and axis!=2:continue
        normal=tuple(float(sign) if i==axis else 0. for i in range(3));up=(1.,0.,0.) if axis!=0 else (0.,1.,0.)
        basis=_basis(normal,up);surface=_add(center,_mul(normal,size[axis]/2-sheet/2))
        # Basis may swap the local face axes; project the box spans exactly.
        width=sum(abs(basis[0][i])*size[i] for i in range(3));height=sum(abs(basis[1][i])*size[i] for i in range(3))
        holes=[]
        for p in ports:
            if p['face']!=face:continue
            delta=_sub(p['position'],surface);x,y=_dot(delta,basis[0]),_dot(delta,basis[1]);r=5.1
            if abs(x)+r>=width/2-.1 or abs(y)+r>=height/2-.1:raise ValueError('GPU reference socket lies outside its terminal face')
            holes.append((x,y,r))
        face_outline=_rounded_rect(width,height,min(3.3,height*.16),2 if builder.level=='eco' else 4) if rounded else chamfer_rect(width,height,.45)
        vertices=perforated_plate(face_outline,holes,sheet,segments={'eco':12,'balanced':16,'close':24}[builder.level],clip_walls=True)
        builder.put('loop-gpu-terminal-pierced-face-sheets',vertices,tone,surface,basis,part=part,alpha=.5 if clear else 1.)
    for p in ports:
        neck=6. if 'short_end_port_necks' in row['geometry_features'] else 1.
        axes=_basis(p['normal'],(0.,1.,0.));center=_add(p['position'],_mul(p['normal'],-neck/2))
        segments={'eco':12,'balanced':20,'close':28}[builder.level]
        port_part=root+':port:'+p['id'];p['part_id']=port_part
        builder.put('loop-gpu-open-female-thread-mouth-reference',ring(7.35,5.1,neck,segments),
            '#b5c2c6' if row['brand']=='Alphacool' else '#4b5d65',center,axes,part=port_part)
        # One thin ring shows an insert edge, not a manufactured thread pitch.
        if builder.level!='eco':
            builder.put('loop-gpu-terminal-insert-edge',ring(7.65,7.05,.25,segments),'#3b4e55',
                _add(p['position'],_mul(p['normal'],-.14)),axes,part=port_part)
    return ports

def _channel_holes(recipe,cx,cy,w,h):
    """Finite source-family channel study; no exact fluid circuit/CAD claim."""
    arrangements={
        'core_astral5090':(-.10,.02,.16,.25),'core4090_fe':(-.04,-.03,.18,.27),
        'aurora7900_reference':(-.04,-.02,.16,.26),'core9070_asus':(-.04,.02,.17,.26),
        'core9070_xfx':(.02,.02,.18,.28),'core5090_msi':(.03,-.01,.17,.25),
        'core5090_tuf':(-.02,-.01,.17,.26),'heatkiller5090_tuf':(-.07,0.,.18,.27),
        'heatkiller4090_fe':(-.01,-.02,.19,.28),'xg7_4090_strix_tuf':(0.,-.01,.20,.33),
        'xg7_3080_fe':(-.05,-.02,.20,.32)}
    ox,oy,sx,sy=arrangements[recipe];gx=cx+ox*w;gy=cy+oy*h
    cw,ch=w*sx,h*sy;stroke=max(1.7,min(w,h)*.025)
    holes=[_rect(gx,gy,cw,ch,min(cw,ch)*.10)]
    # Distinct low-frequency passage studies from reviewed clear-face layouts.
    # These are not invented pad arrays, electrical circuits or exact flow CAD.
    patterns={
        'core_astral5090':[[(-.42,-.04),(-.42,.32),(-.18,.32),(-.18,.20),(.18,.20),(.18,.34),(.41,.34),(.41,-.30),(.08,-.30),(.08,-.13)],
                           [(-.38,-.31),(-.20,-.31),(-.20,-.10)]],
        'core4090_fe':[[(-.42,.27),(-.17,.27),(-.17,.10)],[(-.40,-.28),(-.22,-.28),(-.22,-.06)],[(.13,.12),(.40,.12),(.40,-.28),(.09,-.28),(.09,-.16)]],
        'aurora7900_reference':[[(-.43,.29),(-.16,.29),(-.16,.14)],[(.09,.14),(.38,.14),(.38,-.28),(.10,-.28),(.10,-.15)],[(-.40,-.30),(-.23,-.30),(-.23,-.02)]],
        'core9070_asus':[[(-.41,.30),(-.17,.30),(-.17,.13)],[(.10,.15),(.37,.15),(.37,-.27),(.08,-.27),(.08,-.13)],[(-.39,-.29),(-.19,-.29),(-.19,-.10)]],
        'core9070_xfx':[[(-.42,.27),(-.10,.27),(-.10,.13)],[(.13,.14),(.39,.14),(.39,-.30),(.12,-.30),(.12,-.13)],[(-.38,-.26),(-.20,-.26),(-.20,-.02)]],
        'core5090_msi':[[(-.42,.30),(-.10,.30),(-.10,.13)],[(.15,.14),(.40,.14),(.40,-.29),(.10,-.29),(.10,-.13)],[(-.40,-.30),(-.22,-.30),(-.22,-.01)]],
        'core5090_tuf':[[(-.43,.28),(-.17,.28),(-.17,.13)],[(.12,.13),(.40,.13),(.40,-.28),(.08,-.28),(.08,-.13)],[(-.40,-.28),(-.19,-.28),(-.19,-.02)]],
        'heatkiller5090_tuf':[[(-.32,.28),(.25,.28),(.25,-.26),(.03,-.26),(.03,-.14)],[(-.32,.28),(-.32,-.26),(-.18,-.26),(-.18,-.05)]],
        'heatkiller4090_fe':[[(-.30,.28),(.28,.28),(.28,-.26),(.10,-.26),(.10,-.13)],[(-.30,.28),(-.30,-.26),(-.15,-.26),(-.15,-.10)]],
        'xg7_4090_strix_tuf':[[(-.25,.31),(.23,.31),(.23,-.29),(.10,-.29),(.10,-.16)],[(-.25,.31),(-.25,-.30),(-.12,-.30),(-.12,-.16)]],
        'xg7_3080_fe':[[(-.24,.29),(.20,.29),(.20,-.28),(.05,-.28),(.05,-.16)],[(-.24,.29),(-.24,-.29),(-.15,-.29),(-.15,-.07)]]}
    for path in patterns[recipe]:
        for (ax,ay),(bx,by) in zip(path,path[1:]):
            a=(cx+ax*w,cy+ay*h);b=(cx+bx*w,cy+by*h)
            holes.append(_rect((a[0]+b[0])/2,(a[1]+b[1])/2,max(stroke,abs(b[0]-a[0])+stroke*.8),
                max(stroke,abs(b[1]-a[1])+stroke*.8),stroke*.18))
    return holes,(gx,gy,cw,ch)

def _fasteners(builder,footprint,cx,cy,w,h,z,part,recipe,standoff_start=None):
    from assembly_geometry import ring
    # Bounded sampling, deliberately not the product's asserted screw count.
    points=[(-.45,.35),(-.21,.38),(.02,.38),(.24,.34),(.27,.05),(.27,-.30),(.03,-.39),(-.18,-.39),(-.42,-.38),(-.45,-.03),(.46,-.37),(.46,.37)]
    if recipe in ('core9070_asus','core9070_xfx'):
        points[3]=(.27,.29);points[4]=(.31,-.02);points[5]=(.31,-.33)
    elif recipe=='core5090_msi':
        points[2]=(.08,.38);points[3]=(.31,.33);points[4]=(.34,0.);points[5]=(.34,-.34)
    elif recipe in ('core4090_fe','aurora7900_reference'):
        points[2]=(-.02,.38);points[3]=(.20,.33);points[4]=(.24,.01);points[5]=(.24,-.32)
    indices=(0,3,6,9) if builder.level=='eco' else (0,1,3,4,5,6,8,10) if builder.level=='balanced' else tuple(range(len(points)))
    for index in indices:
        x=cx+points[index][0]*w;y=cy+points[index][1]*h
        builder.put('loop-gpu-reference-fastener-samples',ring(1.9,.52,.55,12),'#b9c7cc',(x,y,z),part=part)
        if standoff_start is not None:
            length=max(.5,z-standoff_start-.3)
            builder.put('loop-gpu-source-observed-cover-standoff-samples',ring(1.2,.52,length,12),'#a4b7bf',
                (x,y,standoff_start+length/2),part=part)

def build_component(row,level='balanced',center=(0.,0.,0.),basis=((1.,0.,0.),(0.,0.,-1.),(0.,1.,0.)),part=None,terminal=None):
    """Independent original assembly, with no GPU/case replacement or routing."""
    from liquid_gpu_schema047 import validate_reference
    from assembly_cooling import _Builder,_transform
    from assembly_detail import bevel_extrude
    validate_reference(row)
    config=next((t for t in row['terminal_configurations'] if t['id']==(terminal or row['default_terminal_configuration'])),None)
    if config is None:raise ValueError('Unknown GPU block terminal configuration')
    builder=_Builder(level);root=part or 'cooler:gpu-block';body_part=root+':body';back_part=root+':backplate'
    envelope=config['reference_envelope_mm'];w,h,d=(envelope[k] for k in ('width','height','depth'));extent=(w,h,d)
    family=row['geometry_family'];recipe=row['geometry_recipe'];short=config['geometry_reference']['layout']!='long_edge'
    if short:
        left=-w*.49;right=w*(config['geometry_reference']['center_uv'][0]-config['geometry_reference']['span_uv'][0]/2-.001)
        bw=right-left;cx=(left+right)/2
    else:bw=w*.98;cx=0.
    bh=h*(.95 if short else .79);cy=0. if short else -h*.085
    outline=_rect(cx,cy,bw,bh,min(bw,bh)*(.035 if family=='gpu_carbon_server' else .055))
    if family=='gpu_carbon_server':
        # Open perimeter notch seen on the carbon plate; dimensions reference.
        x,y=bw/2,bh/2
        outline=tuple((cx+a,cy+b) for a,b in ((-x,-y),(x,-y),(x,y),(bw*.35,y),(bw*.35,y-bh*.11),(bw*.24,y-bh*.11),(bw*.24,y),(-x,y)))
    back=row['backplate'];known=back['dimensions_mm'];bpw=known['width'] or bw;bph=known['height'] or bh
    # A separate plate, with no GPU PCB/VRAM/IO geometry duplicated beneath it.
    bp_depth=min(d*.20,back['plate_thickness_mm'] or 1.6);bpz=-d/2+bp_depth/2
    back_y=max(-(h-bph)/2,min((h-bph)/2,cy))
    back_outline=_rect(0.,back_y,bpw,bph,min(bpw,bph)*.035)
    _plate(builder,'loop-gpu-passive-backplate',back_outline,bp_depth,bpz,'#28343c' if family!='gpu_carbon_server' else '#3b4448',back_part)
    if family=='gpu_carbon_server':
        builder.put('loop-gpu-carbon-cover',bevel_extrude(outline,max(1.,d*.10),.35),'#343d43',(0.,0.,d*.16),part=body_part)
        # Bounded interlaced albedo patches, not long false sewing stitches or
        # a measured fibre count. No copied bitmap texture is shipped.
        from assembly_geometry import _quad
        patches=[];columns={'eco':10,'balanced':14,'close':18}[builder.level]
        for j in range(6):
            for i in range(columns):
                x=cx-bw*.41+i/(columns-1)*bw*.82;y=cy-bh*.36+j*bh*.144
                dx=min(4.,bw*.025);dy=min(1.2,bh*.012);s=1 if (i+j)%2 else -1
                _quad(patches,(x-dx,y-dy,d*.213),(x+dx,y+s*dy,d*.213),
                    (x+dx,y+s*dy+dy,d*.213),(x-dx,y,d*.213))
        builder.put('loop-gpu-carbon-reference-weave',tuple(patches),'#48585e',part=body_part)
        builder.box('loop-gpu-server-coldplate-reference',(bw*.96,bh*.96,d*.18),'#aebbc0',(cx,cy,-d*.05),IDENTITY,part=body_part)
        _fasteners(builder,outline,cx,cy,bw,bh,d*.23,body_part,recipe)
    else:
        base_z=-d*.16;base_depth=max(1.2,d*.13)
        metal_outline=outline
        if 'stepped_coldplate_shoulder' in row['geometry_features']:
            x,y=bw/2,bh/2;c=min(bw,bh)*.04
            metal_outline=tuple((cx+a,cy+b) for a,b in ((-x+c,-y),(x-c,-y),(x,-y+c),(x,y-bh*.14),(x-bw*.16,y),(-x+c,y),(-x,y-c),(-x,-y+c)))
        _plate(builder,'loop-gpu-chrome-or-nickel-coldplate-base',metal_outline,base_depth,base_z,'#9faeb4',body_part)
        # The broad blank land on the right is visible in the primary photos.
        # Groove coordinates remain an explicitly illustrative low-frequency
        # study, rather than an asserted internal coolant circuit.
        active={'core_astral5090':(.74,-.10),'core5090_msi':(.83,-.055),'core5090_tuf':(.77,-.10),
            'core9070_asus':(.74,-.10),'core9070_xfx':(.80,-.075),'core4090_fe':(.78,-.08),
            'aurora7900_reference':(.78,-.08)}.get(recipe,(1.,0.))
        holes,chamber=_channel_holes(recipe,cx+active[1]*bw,cy,bw*active[0],bh)
        floor_z=base_z+base_depth/2+.25
        _plate(builder,'loop-gpu-reference-coolant-channel-floor',metal_outline,.45,floor_z,'#526f77',body_part)
        _plate(builder,'loop-gpu-recessed-metal-channel-study',metal_outline,max(1.1,d*.05),floor_z+1.0,'#bbc7cb',body_part,holes)
        cover_z=d*.12;cover_depth=max(1.5,d*.105)
        _plate(builder,'loop-gpu-source-observed-acrylic-window',outline,cover_depth,cover_z,'#9cb8c2',body_part,alpha=.26)
        # No source logos, serials or imagined PCB circuit arrangements.
        if 'core_emblem_plate' in row['geometry_features']:
            gx,gy,cw,ch=chamber;pad=_rect(gx,gy,min(24.,cw*.65),min(23.,ch*.70),2.)
            _plate(builder,'loop-gpu-source-jetplate-cover-reference',pad,.9,cover_z+cover_depth/2+.5,'#c4cfd0',body_part)
            _plate(builder,'loop-gpu-original-centre-plate-inset',_rect(gx,gy,min(15.,cw*.40),min(15.,ch*.45),1.5),.25,cover_z+cover_depth/2+1.1,'#789098',body_part)
        if family=='gpu_heatkiller_window':
            window=_rect(cx-bw*.02,cy,bw*.68,bh*.69,min(bw,bh)*.17)
            _plate(builder,'loop-gpu-metal-window-fascia',outline,1.35,cover_z+cover_depth/2+1.,'#bbc5c8',body_part,[window])
        if family=='gpu_xg7_ribbed':
            panel_w=bw*.18;panel_h=bh*.92;panel_z=cover_z+cover_depth/2+.6
            for sign in (-1,1):
                this_w=panel_w*(1.24 if recipe=='xg7_3080_fe' and sign>0 else .86 if recipe=='xg7_3080_fe' else 1.)
                px=cx+sign*(bw/2-this_w/2-.7)
                _plate(builder,'loop-gpu-xg7-side-fascia',_rect(px,cy,this_w,panel_h,1.5),1.6,panel_z,'#27343c',body_part)
                count={'eco':5,'balanced':8,'close':12}[builder.level]
                for i in range(count):
                    py=cy-panel_h*.40+i/(count-1)*panel_h*.80
                    builder.box('loop-gpu-reference-ribbed-fascia-samples',(this_w*.94,.65,1.0),'#4d6069',(px,py,panel_z+1.1),IDENTITY,part=body_part)
        if family!='gpu_heatkiller_window':
            _fasteners(builder,outline,cx,cy,bw,bh,cover_z+cover_depth/2+.35,body_part,recipe,
                floor_z+1.2 if 'visible_cover_standoffs' in row['geometry_features'] else None)
        if row['lighting']['present'] is True:
            if recipe in ('core_astral5090','core9070_asus','core9070_xfx','core5090_msi','core5090_tuf','heatkiller5090_tuf','heatkiller4090_fe'):
                builder.box('loop-gpu-diffuser-black-rail',(bw*.90,3.2,2.4),'#263741',(cx,cy-bh*.48,cover_z),IDENTITY,part=body_part)
                builder.box('loop-gpu-source-observed-side-rgb',(bw*.85,1.0,.8),row['accent_color'],(cx,cy-bh*.485,cover_z+1.25),IDENTITY,part=body_part)
            else:
                # An illuminated window rim only; no unseen LED strip/circuit.
                rim_outer=_rect(cx,cy,bw*.95,bh*.95,2.);rim_inner=_rect(cx,cy,bw*.95-2.,bh*.95-2.,1.)
                _plate(builder,'loop-gpu-source-observed-side-rgb',rim_outer,.35,cover_z+cover_depth/2+.25,row['accent_color'],body_part,[rim_inner],alpha=.4)
    ports=_terminal(builder,row,config,extent,root)
    meshes=builder.finish();triangles=sum(m.vertex_count for m in meshes)//3
    if triangles>LIMITS[builder.level]:raise ValueError('GPU block reference exceeds bounded detail budget')
    # Proper inspection rotation: default front faces -Z with canonical Y up.
    # Rotating the full body and every normal/socket once preserves handedness.
    rotation=((-1.,0.,0.),(0.,0.,1.),(0.,1.,0.))
    if family=='gpu_carbon_server':
        # Rotate this symmetric opaque reference180deg in its face plane so
        # the documented short-end necks face the shared fixed-camera view.
        # The whole assembly/ports rotate together; no sockets are invented.
        rotation=((1.,0.,0.),(0.,0.,-1.),(0.,1.,0.))
    combined=tuple(_vector(v,basis) for v in rotation)
    meshes=tuple(replace(m,vertices=_transform(m.vertices,center,combined)) for m in meshes)
    ports=[dict(p,position=_add(center,_vector(p['position'],combined)),normal=_vector(p['normal'],combined)) for p in ports]
    selected_dimensions=config['published_envelope_mm'] if config['dimensions_scope']=='published_complete' else row['dimensions_mm']
    selected_dimensions_verified=config['dimensions_scope']=='published_complete' and all(v is not None for v in selected_dimensions.values())
    meta=dict(id=root,model_id=row['id'],label=row['label'],kind='gpu_block',dimensions_mm=selected_dimensions,
        reference_envelope_mm=envelope,dimensions_verified=selected_dimensions_verified,geometry_family=family,
        terminal_configuration=config['id'],ports=ports,ports_count=config['ports_count'],
        observed_ports_count=len(ports),port_positions_verified=False,
        ports_geometry_complete=row['ports_geometry_complete'] if config['id']==row['default_terminal_configuration'] else False,
        unplaced_documented_ports=config['ports_count']-len(ports) if config['ports_count'] is not None else None,
        hydraulic_groups=config['hydraulic_groups'],hydraulic_pairing_verified=config['hydraulic_pairing_verified'],
        triangle_count=triangles,telemetry_bound=False,fit_verified=False,coordinates_verified=False,
        sources=row['sources'],assembly_stage='standalone_reference_only',gpu_mount_pose_verified=False,
        attached_to_gpu=False,routes_supported=False,pump_present=False,rotors_present=False,
        materials=row['materials'],unplaced_documented_accessories=['replacement_slot_bracket'] if 'replacement_slot_bracket' in row['geometry_features'] else [],
        reference_details=['illustrative channel study, not verified fluid circuit','sampled fastener/fascia rib count and coordinates','layer depths','terminal socket positions'],
        source_observed_exterior=row['exterior_observations'],
        subparts=[dict(id=body_part,label='冷头本体',kind='gpu_block_body'),dict(id=root+':terminal',label='独立端子',kind='gpu_block_terminal'),dict(id=back_part,label='被动背板',kind='gpu_block_passive_backplate'),
            *[dict(id=p['part_id'],label='接口观察 · '+p['id'],kind='gpu_block_port',port_id=p['id'],physical_detachability_verified=False) for p in ports]])
    return meshes,meta
