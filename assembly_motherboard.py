"""Original bounded model-matched motherboard construction from reviewed landmarks.

Official photos/manuals establish the visible layout. Their image proportions
are not CAD coordinates; small IC packages and silkscreen are simplified.
This module never queries the computer, reads assets, or starts work.
"""
import copy
import math
from dataclasses import replace

from motherboard_catalog import resolve


# Generic interface references only: these do not identify a retail board's
# connector supplier, exact mating-pin contour or factory plating.
_POWER_INTERFACE_SOURCE = 'https://www.molex.com/en-us/products/part-detail/39281243'
_M2_INTERFACE_SOURCE = 'https://www.te.com/en/products/connectors/pcb-connectors/card-edge-connectors/m-2-connectors.html?tab=pgp-story'



def _io_clear_cover(model):
    # This original inset belongs only to the three already-authored ASUS
    # profiles. A same-index cover or a new brand must not inherit that shape.
    allowed=('asus-rog-strix-z790-a-wifi-d4','asus-rog-strix-x670e-e-wifi','asus-rog-maximus-z790-hero')
    if model['id'] not in allowed or not model.get('io_clear_inset',True):return None
    return next((cover for cover in model['heatsinks'] if cover['name']=='vrm-io'),None)

def layout_anchors(spec,w,h,d,board_x,board_y,board_rear):
    """Canonical component anchors before the case's rigid orientation change."""
    model=resolve(spec.get('board') or {})
    if not model:return None
    bh=model['dimensions_mm']['height'];bw=model['dimensions_mm']['width']
    def point(uv,out=0.):return (board_x-out,board_y+(.5-uv[1])*bh,board_rear+uv[0]*bw)
    cpu=point(model['cpu_uv'],6.)
    dimms=[point(uv,3.) for uv in model['dimm_uv']]
    first=model['pcie'][0];start=point(first['uv'],6.)
    connectors={key:[] for key in ('atx24','eps8','sata','front_io','usb2','usb3','usb_c','audio','fan','argb','m2','pcie')}
    for row in model['connectors']:
        kind=row['kind'];count=row['count']
        for index in range(count):
            p=point(row['uv'],7.5)
            if count>1:p=(p[0]-index*7.5,p[1],p[2])
            along=row.get('along')
            along=(0.,-along[1],along[0]) if along else (0.,1.,0.) if kind=='atx24' else (0.,0.,1.)
            normal=(0.,0.,1.) if row['orientation']=='edge' else (-1.,0.,0.)
            if kind=='sata' and row['orientation']=='edge':along=(1.,0.,0.)
            connectors.setdefault(kind,[]).append(dict(position=p,normal=normal,
                along=along,kind=kind,position_method='official_manual_proportions',
                **{key:row[key] for key in ('label','role','role_verified','role_source','role_source_page') if key in row}))
    for row in model['pcie']:
        p=point(row['uv'],4.5);p=(p[0],p[1],p[2]+row['length_mm']/2)
        connectors['pcie'].append(dict(position=p,normal=(-1.,0.,0.),along=(0.,0.,1.),kind=row['kind'],
            length_mm=row['length_mm'],rear_position=(p[0],p[1],board_rear),position_method='official_manual_proportions'))
    for row in model['m2']:
        rear=row['side']=='rear';normal=(1.,0.,0.) if rear else (-1.,0.,0.)
        connectors['m2'].append(dict(position=point(row['uv'],-3. if rear else 3.),normal=normal,
            along=(0.,-row['along'][1],row['along'][0]),max_length_mm=row['max_length_mm'],side=row['side'],
            allowed_lengths_mm=row['allowed_lengths_mm'],
            position_method='official_manual_proportions'))
    return dict(model=model,case=copy.deepcopy(spec.get('case') or {}),case_dimensions=(w,h,d),
        board=dict(x=board_x,y=board_y,z=board_rear+bw/2,position=(board_x,board_y,board_rear+bw/2),
            height=bh,width=bw,rear_z=board_rear,normal=(-1.,0.,0.),up=(0.,1.,0.),along=(0.,0.,1.)),
        cpu=dict(x=cpu[0],y=cpu[1],z=cpu[2],position=cpu,normal=(-1.,0.,0.),up=(0.,1.,0.),u=(0.,1.,0.),v=(0.,0.,-1.)),
        dimm_centers=dimms,connectors=connectors,primary_pcie_y=start[1],primary_pcie_start_z=start[2],
        pcie_z=start[2]+first['length_mm']/2)


def memory_slot_indices(count,capacity):
    if capacity==4 and 0<count<4:return {1:(1,),2:(1,3),3:(0,1,3)}[count]
    return tuple(range(count))


def _segment(a,b,radius=.8,segments=8):
    from assembly_detail import _tri,_quad
    direction=tuple(b[k]-a[k] for k in range(3));length=math.sqrt(sum(v*v for v in direction))
    if length<1e-7:return ()
    direction=tuple(v/length for v in direction);up=(1.,0.,0.) if abs(direction[0])<.8 else (0.,1.,0.)
    cross=lambda p,q:(p[1]*q[2]-p[2]*q[1],p[2]*q[0]-p[0]*q[2],p[0]*q[1]-p[1]*q[0])
    u=cross(direction,up);scale=math.sqrt(sum(v*v for v in u));u=tuple(v/scale for v in u);v=cross(direction,u)
    ring=lambda center:[tuple(center[k]+radius*(math.cos(n*math.tau/segments)*u[k]+math.sin(n*math.tau/segments)*v[k]) for k in range(3)) for n in range(segments)]
    aa,bb=ring(a),ring(b);out=[]
    for n in range(segments):
        j=(n+1)%segments;_quad(out,aa[n],aa[j],bb[j],bb[n]);_tri(out,a,aa[j],aa[n]);_tri(out,b,bb[n],bb[j])
    return tuple(out)


def _printed_text(text,pixel):
    """Printed PCB ink needs only its front face, never twelve-sided pixels."""
    from assembly_geometry import model_mark
    vertices=model_mark(text,pixel=pixel)
    return tuple(value for n in range(0,len(vertices),18) if vertices[n+5]>.999 for value in vertices[n:n+18])


def _orient_header(vertices,normal,along,base_along=(0.,0.,1.)):
    """Rigidly orient a connector and its normals; the long axis is explicit."""
    def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
    def dot(a,b):return sum(x*y for x,y in zip(a,b))
    old_n=(-1.,0.,0.);old_b=cross(old_n,base_along)
    # Edge sockets cannot have a long axis parallel to their opening normal.
    # Their source-observed in-plane long axis is retained whenever valid.
    if abs(dot(normal,along))>.9:along=(0.,1.,0.)
    b=cross(normal,along)
    def vector(v):
        depth=-dot(v,old_n);width=dot(v,old_b);length=dot(v,base_along)
        return tuple(-normal[k]*depth+b[k]*width+along[k]*length for k in range(3))
    return tuple(value for n in range(0,len(vertices),6) for v in (vector(vertices[n:n+3]),vector(vertices[n+3:n+6])) for value in v)


def enrich_motherboard(meshes,spec,anchors,level='balanced'):
    """Replace a matched board's reference assembly; retain all other hardware."""
    if not anchors:return tuple(meshes),{}
    from assembly_geometry import Mesh,box,color,rotate_vertices,unit_polygon,ring,model_mark
    from assembly_detail import translated,_boxes,bevel_extrude,perforated_plate,chamfer_rect,circle,_port_shape
    model=anchors['model'];board=anchors['board'];bx,by,bz=board['position'];bh,bw=board['height'],board['width'];rear=board['rear_z']
    out=[mesh for mesh in meshes if mesh.component!='board'];parts=[]
    pcb=color(model['pcb_color']);dark=color('#171c22');metal=color(model['heatsink_color']);copper=color('#b99d66');steel=color('#b6bdc4')
    def point(uv,depth=0.):return (bx-depth,by+(.5-uv[1])*bh,rear+uv[0]*bw)
    def add(name,vertices,tone,position=(bx,by,bz)):
        if vertices:parts.append(Mesh(name,tuple(vertices),tone,position,'board'))
    def cube(name,size,pos,tone):add(name,box(*size),tone,pos)
    def plate(name,polygon,depth,tone,outward=0.,holes=(),clip_walls=False):
        vertices=unit_polygon([list(p) for p in polygon],bw,bh)
        shape=perforated_plate(vertices,holes,depth,clip_walls=clip_walls) if holes else bevel_extrude(vertices,depth,min(.7,depth*.2))
        add(name,rotate_vertices(shape,'left'),tone,(bx-outward-depth/2,by,bz))
    # Through holes and annular solder masks remain open in the physical PCB.
    mounts=model['mount_uv']
    holes=[((u-.5)*bw,(.5-v)*bh,1.6) for u,v in mounts]
    add('motherboard-reference',rotate_vertices(perforated_plate(chamfer_rect(bw,bh,1.),holes,1.6,segments=12),'left'),pcb)
    pads=[]
    for x,y,r in holes:pads.extend(translated(ring(3.2,r,.18,segments=16),(x,y,1.0)))
    add('detail-board-copper-mount-pads',rotate_vertices(tuple(pads),'left'),copper)
    # Model-specific solid heatsink silhouettes, stepped lips and real grooves.
    for cover in model['heatsinks']:
        is_m2=cover['name'].startswith('m2');name='detail-board-m2-heatsink' if is_m2 else 'board-'+cover['name']+'-heatsink'
        clip_cover_walls=model['id']=='asus-rog-strix-z790-a-wifi-d4' and cover['name']=='m2-upper'
        depth=cover['depth_mm'];poly=cover['polygon']
        cover_metal=color(cover.get('finish_color'),model['heatsink_color'])
        from assembly_detail import _point_inside
        mount_holes=[((u-.5)*bw,(.5-v)*bh,3.2) for u,v in mounts if _point_inside((u,v),poly)] if model['mount_method'].startswith('official_') else []
        fan=cover.get('static_fan');vent=cover.get('surface_vent');mechanical_holes=list(mount_holes)
        if fan:
            u,v=fan['uv'];mechanical_holes.append(((u-.5)*bw,(.5-v)*bh,fan['diameter_mm']/2))
        if vent:
            # Only the visible perforated shroud is established in this view.
            # A bounded hole sample is not an inferred internal fan position,
            # factory hole count, blade pattern or tachometer mapping.
            region=vent['polygon'];u0,u1=min(p[0] for p in region),max(p[0] for p in region)
            v0,v1=min(p[1] for p in region),max(p[1] for p in region)
            for line in range(5):
                for col in range(3):
                    u=u0+(u1-u0)*(.20+.30*col);v=v0+(v1-v0)*(.12+.19*line)
                    if _point_inside((u,v),region):mechanical_holes.append(((u-.5)*bw,(.5-v)*bh,1.1))
        # These are open recesses with real depth above a lower plinth, not
        # gray lines painted on an otherwise solid block. The sampling count
        # is illustrative; the outline/region is manually model matched.
        if level!='eco' and cover['grooves'] and not vent:
            u0,u1=min(p[0] for p in poly),max(p[0] for p in poly);v0,v1=min(p[1] for p in poly),max(p[1] for p in poly)
            sample=min(cover['grooves']*(2 if level=='close' else 1),18)
            recess=min(3.,depth*.42);plate(name,poly,depth-recess,cover_metal,1.,mechanical_holes,clip_walls=clip_cover_walls);channels=list(mechanical_holes)
            for n in range(sample):
                along=cover.get('groove_along')
                if along is None:
                    # Preserve the original16 payload when no new observation
                    # supplies a different source-visible groove direction.
                    u=u0+(u1-u0)*(.20+.60*n/max(1,sample-1));v=v0+(v1-v0)*.50
                    cx,cy=(u-.5)*bw,(.5-v)*bh;channel=chamfer_rect(.65,(v1-v0)*bh*.68,.12)
                    if model['id']=='asus-rog-strix-z790-a-wifi-d4' and cover['name']=='m2-upper':
                        # The source-observed right step makes the bounding
                        # rectangle taller than the main strip. Keep each
                        # illustrative groove inside that real outline; an
                        # out-of-bounds hole would create a detached metal wall.
                        physical=unit_polygon([list(p) for p in poly],bw,bh)
                        for attempt in range(12):
                            if all(_point_inside((x+cx,y+cy),physical) for x,y in channel):break
                            channel=tuple((x,y*.8) for x,y in channel)
                        else:raise ValueError('M2 reference groove cannot fit its physical cover')
                    channels.append(tuple((x+cx,y+cy) for x,y in channel))
                else:
                    direction=(along[0]*bw,-along[1]*bh);length=math.hypot(*direction)
                    direction=tuple(v/length for v in direction);across=(-direction[1],direction[0])
                    physical=unit_polygon([list(p) for p in poly],bw,bh)
                    dot=lambda p,q:sum(a*b for a,b in zip(p,q))
                    forward=[dot(p,direction) for p in physical];side=[dot(p,across) for p in physical]
                    center=(min(forward)+max(forward))/2
                    offset=min(side)+(max(side)-min(side))*(.23+.54*n/max(1,sample-1))
                    half=(max(forward)-min(forward))*.33
                    for attempt in range(12):
                        channel=tuple((direction[0]*(center+a*half)+across[0]*(offset+b*.325),
                                       direction[1]*(center+a*half)+across[1]*(offset+b*.325))
                                      for a,b in ((-1,-1),(1,-1),(1,1),(-1,1)))
                        if all(_point_inside(p,physical) for p in channel):channels.append(channel);break
                        half*=.80
            cap=perforated_plate(unit_polygon([list(p) for p in poly],bw,bh),channels,recess,clip_walls=clip_cover_walls)
            add('board-heatsink-recessed-crown',rotate_vertices(cap,'left'),cover_metal,(bx-1.-depth+recess/2,by,bz))
        else:plate(name,poly,depth,cover_metal,1.,mechanical_holes,clip_walls=clip_cover_walls)
        if fan:
            center=point(fan['uv'],depth-1.8);radius=fan['diameter_mm']/2
            add('board-onboard-fan-recess-floor',rotate_vertices(ring(radius*.985,0.,.35,segments=32),'left'),dark,center)
            add('board-onboard-fan-opening-rim',rotate_vertices(ring(radius+.45,radius-.30,.45,segments=32),'left'),steel,point(fan['uv'],depth+1.05))
            add('board-onboard-static-fan-hub',rotate_vertices(ring(radius*fan['hub_ratio'],0.,.9,segments=24),'left'),color('#34383d'),point(fan['uv'],depth+.2))
        # Countersunk retaining screws only on detachable M.2 covers.
        if is_m2:
            u0,u1=min(p[0] for p in poly),max(p[0] for p in poly);v=sum(p[1] for p in poly)/len(poly)
            for u,v in cover.get('fasteners_uv',((u0+.022,v),(u1-.022,v))):
                pos=point((u,v),depth+1.3)
                add('board-cover-screw',rotate_vertices(ring(1.65,.45,.45,segments=12),'left'),steel,pos)
    # Static photo-observed material inlays; no emission, logo or animation.
    for region in model.get('static_finish_regions',()):
        parent_id=region.get('parent_cover')
        parent=next((c for c in model['heatsinks'] if c['name']==parent_id),None) if parent_id else None
        if parent_id and parent is None:continue
        outward=1.1+(parent['depth_mm'] if parent else 0.)
        plate('board-static-finish-'+region['id'],region['polygon'],region['depth_mm'],
            color(region['finish_color']),outward)
    # The I/O cover's clear inset is an original simple translucent panel,
    # not the vendor's copyrighted logo or copied artwork.
    io_cover=_io_clear_cover(model)
    if io_cover:
        plate('board-io-clear-inset',((.018,.079),(.100,.068),(.147,.125),(.143,.355),(.026,.420)),.5,
            color('#a6c9d1',alpha=.54),io_cover['depth_mm']+1.3)
    cp=anchors['cpu']['position'];cy,cz=cp[1],cp[2];am5=model['socket']=='AM5'
    if model['socket']=='AM4':
        # Official AM4 board drawings show a plastic PGA ZIF socket, not an
        # LGA metal load plate/spring bed. The bounded receiving-well sample
        # conveys this topology, never the exact1331-contact electrical map.
        cube('board-am4-zif-carrier',(2.,54.,54.),(bx-1.9,cy,cz),dark)
        sample=9 if level=='eco' else 17 if level=='balanced' else 21
        pitch=34./max(1,sample-1)
        # The shared plate helper deliberately handles at most24 holes. Reuse
        # one truly perforated cell, keeping that safety limit unchanged.
        # Four unique rectangle corners avoid zero-length clipping edges.
        square=lambda size:((-size/2,-size/2),(size/2,-size/2),(size/2,size/2),(-size/2,size/2))
        cell=perforated_plate(square(pitch),(circle(0.,0.,.42,8),),2.)
        socket=list(perforated_plate(chamfer_rect(50.,50.,1.2),
                                    (square(sample*pitch),),2.))
        for line in range(sample):
            for col in range(sample):
                socket.extend(translated(cell,((col-(sample-1)/2)*pitch,(line-(sample-1)/2)*pitch,0.)))
        add('board-am4-pga-receiving-wells',rotate_vertices(socket,'left'),color('#555961'),(bx-4.4,cy,cz))
        cube('board-am4-dark-recess-floor',(.3,39.,39.),(bx-3.05,cy,cz),color('#14191e'))
        lever_points=((bx-5.8,cy+23.,cz+27.),(bx-5.8,cy-21.,cz+27.),
                      (bx-5.8,cy-27.,cz+30.),(bx-5.8,cy-25.,cz+33.))
        add('board-am4-zif-locking-lever',tuple(v for a,b in zip(lever_points,lever_points[1:]) for v in _segment(a,b,.65)),steel,(0,0,0))
        # Two black factory-style clip rails are visible in the reviewed MSI
        # manuals/photos. Their depth/bolt contours remain interface reference.
        for sign in (-1,1):
            cube('board-am4-cooler-retention',(7.,6.,61.),(bx-5.5,cy+sign*44.5,cz),dark)
            cube('board-am4-retention-clip',(9.,4.,9.),(bx-6.5,cy+sign*42.,cz),dark)
            for side in (-1,1):
                add('board-am4-retention-screw',rotate_vertices(ring(2.8,.9,1.,segments=12),'left'),steel,(bx-9.4,cy+sign*44.5,cz+side*27.))
    else:
        # LGA clamp with a genuinely open center, hinge and captive bolts.
        sw,sh=(54.,58.) if am5 else (54.,65.);opening=chamfer_rect(40.5 if am5 else 39.5,42. if am5 else 47.,2.3)
        cube('board-socket-carrier',(2.,sh-4.,sw-4.),(bx-1.9,cy,cz),dark)
        # Dense visible spring heads are sampled, not a claim to reproduce every
        # electrical contact or its exact row map from a proprietary socket CAD.
        from assembly_detail import _quad
        pins=[];columns,rows=(16,18) if level=='eco' else (24,28) if level=='balanced' else (32,36)
        for row in range(rows):
            for col in range(columns):
                yy=cy+(row-(rows-1)/2)*((37. if am5 else 42.)/rows)
                zz=cz+(col-(columns-1)/2)*(34./columns);r=.19
                _quad(pins,(bx-3.05,yy-r,zz-r),(bx-3.15,yy+r,zz-r),(bx-3.28,yy+r,zz+r),(bx-3.18,yy-r,zz+r))
        add('board-socket-spring-heads',tuple(pins),copper,(0,0,0))
        frame=perforated_plate(chamfer_rect(sw,sh,3.),(opening,),2.2)
        add('detail-board-retention-frame',rotate_vertices(frame,'left'),steel,(bx-4.4,cy,cz))
        cube('detail-board-retention-hinge',(4.,3.,sw-5),(bx-4.5,cy+sh/2-1.0,cz),dark)
        bolts=[]
        for uu in (-1,1):
            for vv in (-1,1):
                p=(bx-5.6,cy+vv*(sh/2-3.6),cz+uu*(sw/2-3.4))
                bolts.extend(translated(rotate_vertices(ring(2.1,.7,.6,segments=12),'left'),p))
        add('board-socket-captive-bolts',tuple(bolts),steel,(0,0,0))
        lever_points=((bx-6.,cy+sh*.42,cz+sw*.53),(bx-6.,cy-sh*.35,cz+sw*.53),
            (bx-6.,cy-sh*.51,cz+sw*.68),(bx-6.,cy-sh*.58,cz+sw*.63),(bx-6.,cy-sh*.50,cz+sw*.48))
        add('detail-board-retention-lever',tuple(v for a,b in zip(lever_points,lever_points[1:]) for v in _segment(a,b,.85)),steel,(0,0,0))
        if am5:
            for sign in (-1,1):
                cube('board-am5-cooler-retention',(7.,6.,67.),(bx-5.5,cy+sign*38.,cz),dark)
                for side in (-1,1):add('board-am5-retention-screw',rotate_vertices(ring(2.8,.9,1.,segments=12),'left'),steel,(bx-9.4,cy+sign*38.,cz+side*27.))
    # DIMM sockets have two long walls, independent contact wells, key bridges
    # and end latches; populated modules were positioned at these exact slots.
    dimm_parts=[];dimm_contacts=[];dimm_latches=[]
    key_y=(.5418072740907387-.5)*133.35 if model['memory_type']=='DDR4' else (.5106861642294713-.5)*133.35
    for center in anchors['dimm_centers']:
        x,y,z=center
        dimm_parts.extend((((5.,139.,1.1),(x,y,z-1.7)),((5.,139.,1.1),(x,y,z+1.7)),((2.,1.3,4.5),(bx-2.,y+key_y,z))))
        # Two separated side banks leave the real insertion channel open.
        # The previous solid gold strip crossed that channel and penetrated
        # the populated PCB edge. These are bounded interface references, not
        # a manufacturer spring/contact layout or manufacturing clearances.
        for side in (-1,1):
            dimm_contacts.append(((3.6,132.,.16),(bx-3.,y,z+side*.88)))
        for sign in (-1,1):dimm_latches.append(((7.,6.,5.5),(bx-4.2,y+sign*70.,z)))
    add('detail-board-populated-memory-sockets',_boxes(dimm_parts),dark,(0,0,0))
    add('detail-board-memory-socket-contact-wells',_boxes(dimm_contacts),copper,(0,0,0))
    add('board-dimm-end-latches',_boxes(dimm_latches),color('#727980'),(0,0,0))
    # Native PCIe channels/keys/latches, at each model's documented slot row.
    for row,anchor in zip(model['pcie'],anchors['connectors']['pcie']):
        x,y,z=anchor['position'];length=row['length_mm'];sides=[((6.,1.1,length),(0,-2.1,0)),((6.,1.1,length),(0,2.1,0)),
            ((1.2,5.3,length),(2.8,0,0)),((6.,5.3,1.3),(0,0,-length/2+.65)),((6.,5.3,1.3),(0,0,-length/2+10.5))]
        add('board-expansion-slot' if row['kind']=='x16' else 'detail-board-pcie-'+row['kind'],_boxes(sides),steel if row['reinforced'] else dark,(x,y,z))
        cube('detail-board-pcie-contact-well',(.25,2.8,length*.91),(x+2,y,z),copper)
        if row['kind']=='x16':cube('detail-board-pcie-latch',(7.,6.5,7.),(x-1,y,z+length/2+2),dark)
    # Empty M.2 receiving channels and mounting standoffs. The card approaches
    # along the reviewed slot axis, including rear-facing and rotated sockets.
    # Wall/floor thicknesses are reference proportions, not OEM drawings. No
    # exact key/contact arrangement or already installed SSD is inferred.
    for anchor in anchors['connectors']['m2']:
        p=anchor['position'];along=anchor['along'];rear_side=anchor['side']=='rear'
        normal=(1.,0.,0.) if rear_side else (-1.,0.,0.)
        # Canonical opening is +Z; +X is its insulating floor toward the PCB.
        # This replaces the former solid box within the same 3.2 x 22 x 5 mm
        # reference envelope, leaving an actual open card-receiving mouth.
        housing=_boxes([((3.2,22.,1.),(0.,0.,-2.)),
            ((3.2,1.,4.),(0.,-10.5,.5)),((3.2,1.,4.),(0.,10.5,.5)),
            ((.65,20.,4.),(1.275,0.,.5))])
        add('detail-board-m2-socket',_orient_header(housing,normal,along),dark,p)
        for distance in anchor['allowed_lengths_mm']:
            pos=tuple(p[k]+along[k]*distance for k in range(3))
            add('detail-board-m2-mount-post',rotate_vertices(ring(2.2,.85,1.8,segments=12),'left'),steel,pos)
    # Main and EPS power housings contain the documented count of open cavities.
    # Each cavity receives its own recessed male contact, not a continuous
    # conductive-looking floor. Contact contours/plating remain schematic;
    # the documented 24/8/4/6 positions and original landmarks are unchanged.
    power_contacts=[];power_contact_count=0
    for key,columns in (('atx24',12),('eps8',4),('eps4',2),('aux6',3)):
        for anchor in anchors['connectors'].get(key,()):
            vertical=key=='atx24';pitch=4.2;cw,ch=(10.4,columns*pitch+1.) if vertical else (columns*pitch+1.,10.4)
            holes=[];contacts=[]
            for col in range(columns):
                for row in range(2):
                    x=(row-.5)*pitch if vertical else (col-(columns-1)/2)*pitch
                    y=(col-(columns-1)/2)*pitch if vertical else (row-.5)*pitch
                    holes.append(tuple((x+u,y+v) for u,v in chamfer_rect(3.2,3.2,.42)))
                    # Plane XY becomes local ZY under rotate_vertices('left').
                    # The post ends below the opening and is isolated from its
                    # neighbours. Do not invent an electrical pin-number map.
                    contacts.append(((4.2,.85,.85),(1.0,y,x)))
            shape=perforated_plate(chamfer_rect(cw,ch,.8),holes,7.)
            p=anchor['position'];position=tuple(p[k]-anchor['normal'][k]*3.2 for k in range(3));base_along=(0.,1.,0.) if vertical else (0.,0.,1.)
            normal=anchor['normal'];along=anchor['along']
            orient=lambda verts:_orient_header(verts,normal,along,base_along)
            add('board-'+key+'-housing',orient(rotate_vertices(shape,'left')),dark,position)
            latch=translated(box(2.,ch*.30,2.),(-3.3,0,cw/2+.6))
            add('board-'+key+'-latch',orient(latch),color('#3a424b'),position)
            floor=translated(box(.3,ch-.7,cw-.7),(3.4,0,0))
            add('board-'+key+'-contact-floor',orient(floor),dark,position)
            power_contacts.extend(translated(orient(_boxes(contacts)),position))
            power_contact_count+=len(contacts)
    add('board-power-independent-contacts',tuple(power_contacts),steel,(0.,0.,0.))
    # Peripheral housings and individual pin rows, located at their manual labels.
    for key,rows in anchors['connectors'].items():
        if key in ('atx24','eps8','eps4','aux6','m2','pcie'):continue
        for anchor in rows:
            p=anchor['position'];edge=anchor['normal']==(0.,0.,1.)
            if key=='sata':
                hole=_port_shape('sata',9.,4.6);shape=perforated_plate(chamfer_rect(13.,8.,.7),(hole,),4.)
                face=shape if edge else rotate_vertices(shape,'left')
                # Keep the original default payload verbatim. Reviewed front
                # pairs can instead run longitudinally down the PCB, allowing
                # their neighbouring receiving mouths to remain clear.
                if not edge and anchor['along']!=(0.,0.,1.):
                    face=_orient_header(face,anchor['normal'],anchor['along'])
                add('detail-board-sata-socket',face,dark,p)
            elif key=='usb_c':
                # The front-panel Type-E socket is a compact keyed 20-contact
                # cavity, not a full-size 2.54mm two-row peripheral header.
                orient=lambda verts:_orient_header(verts,anchor['normal'],anchor['along'])
                shape=perforated_plate(chamfer_rect(9.5,6.5,.8),(chamfer_rect(7.8,4.4,.7),),5.0)
                add('board-header-usb_c',orient(rotate_vertices(shape,'left')),dark,p)
                floor=translated(box(.3,4.,7.4),(2.1,0,0));add('board-usb_c-contact-floor',orient(floor),color('#323a41'),p)
                pins=[((.35,.35,.34),(1.85,(r-.5)*2.7,(c-4.5)*.68)) for r in range(2) for c in range(10)]
                add('board-usb_c-twenty-contacts',orient(_boxes(pins)),copper,p)
            else:
                count=4 if key in ('fan','argb','rgb') else 2 if key=='thermal' else 3 if key=='cpu_ov' else 10 if key in ('front_io','audio','usb2','thunderbolt') else 20
                if key=='front_io':count=model.get('front_panel_positions',20 if model['id'].startswith('asus-rog-') else 10)
                cols=count if count<=4 else count//2;ys=1 if count<=4 else 2;pitch=2. if key=='usb3' else 2.54;size=(4.,ys*pitch+1.8,cols*pitch+1.4)
                skips=model.get('front_panel_missing',((0,4),(1,8),(1,9)) if model['id'].startswith('asus-rog-') else ((1,4),))
                orient=lambda verts:_orient_header(verts,anchor['normal'],anchor['along'])
                add('board-header-'+key,orient(box(*size)),dark,p)
                pins=[((2.6,.5,.5),(-3.,(r-(ys-1)/2)*pitch,(c-(cols-1)/2)*pitch)) for r in range(ys) for c in range(cols)
                    if not (key=='argb' and c==2) and not(key=='front_io' and (r,c) in skips) and not(key in ('usb3','usb2','audio') and (r,c)==(1,cols-1))]
                add('board-header-pins',orient(_boxes(pins)),copper,p)
    # Coils/capacitors visibly frame the CPU power stage, not an invented trace.
    coils=[];caps=[];smd=[]
    for index in range(9 if model['form_factor']!='itx' else 6):
        u=model['cpu_uv'][0]-.190;v=model['cpu_uv'][1]-.130+index*.032
        if .05<v<.55:
            coils.append(((5.6,5.4,5.4),point((u,v),3.9)))
            caps.extend(translated(rotate_vertices(ring(2.2,0,4.,segments=10),'left'),point((u+.035,v),3.)))
    for index in range(9 if model['form_factor']!='itx' else 5):
        u=model['cpu_uv'][0]-.15+index*.032;v=model['cpu_uv'][1]-.12
        coils.append(((5.6,5.4,5.4),point((u,v),3.9)))
        caps.extend(translated(rotate_vertices(ring(2.2,0,4.,segments=10),'left'),point((u,v-.024),3.)))
    add('board-vrm-chokes',_boxes(coils),color('#454b52'),(0,0,0));add('board-vrm-capacitors',tuple(caps),steel,(0,0,0))
    # Batched small packages near the lower audio/IO region are approximate.
    if level!='eco':
        from assembly_detail import _point_inside
        tiny=[];terminations=[]
        # Keep major source-observed component regions unobstructed. The fine
        # package sampling conveys populated PCB surface, not an electrical map.
        for row in range(17 if level=='close' else 12):
            for col in range(18 if level=='close' else 13):
                uv=(.075+col*(.84/(17 if level=='close' else 12)),.07+row*(.85/(16 if level=='close' else 11)))
                if any(_point_inside(uv,c['polygon']) for c in model['heatsinks']):continue
                if abs(uv[0]-model['cpu_uv'][0])*bw<33. and abs(uv[1]-model['cpu_uv'][1])*bh<41.:continue
                if any(abs(uv[0]-u)*bw<6. and abs(uv[1]-v)*bh<74. for u,v in model['dimm_uv']):continue
                if any(abs(uv[1]-p['uv'][1])*bh<7. and p['uv'][0]-.03<uv[0]<p['uv'][0]+(p['length_mm']+10)/bw for p in model['pcie']):continue
                seed=(row*23+col*17)%11
                if seed<3:smd.append(((1.35,3.2,4.7),point(uv,1.5)))
                else:
                    p=point(uv,.95);tiny.append(((.7,1.15,2.3),p))
                    terminations.extend((((.78,1.2,.35),(p[0]-.02,p[1],p[2]-1.0)),((.78,1.2,.35),(p[0]-.02,p[1],p[2]+1.0))))
        add('board-small-smd-packages',_boxes(smd),dark,(0,0,0))
        add('board-small-smd-passives',_boxes(tiny),color('#55514b'),(0,0,0))
        add('board-small-smd-terminations',_boxes(terminations),steel,(0,0,0))
    if model.get('battery_uv') is not None:
        battery=point(model['battery_uv'],2.4)
        add('board-cmos-battery-rim',rotate_vertices(ring(10.5,9.0,2.1,segments=24),'left'),dark,battery)
        add('board-cmos-battery',rotate_vertices(ring(9.4,0,1.4,segments=24),'left'),steel,(battery[0]-.8,battery[1],battery[2]))
    audio_caps=[]
    for index in range(6):
        audio_caps.extend(translated(rotate_vertices(ring(2.3,0,4.,segments=12),'left'),point((.064,.805+index*.025),3.)))
    add('board-audio-capacitors',tuple(audio_caps),color('#bea975'),(0,0,0))
    # Textual model identifiers are original simple grid lettering, never logos.
    token={'asus-rog-strix-z790-a-wifi-d4':'STRIX Z790-A D4','asus-rog-strix-x670e-e-wifi':'STRIX X670E-E',
        'msi-mag-b760m-mortar-wifi':'MAG B760M','msi-mag-b650m-mortar-wifi':'MAG B650M',
        'asrock-z790-pg-itx-tb4':'Z790 PG-ITX','asrock-b650i-lightning-wifi':'B650I LIGHTNING'}.get(model['id'],model.get('silkscreen_label',''))
    add('board-model-silkscreen',rotate_vertices(_printed_text(token,.55),'left'),color('#cbd1d6'),point((.47,.642),1.05))
    printed=[]
    def silk(text,uv,vertical=False,pixel=.29):
        verts=_printed_text(text,pixel)
        if vertical:
            verts=tuple(v for n in range(0,len(verts),6) for v in (-verts[n+1],verts[n],verts[n+2],-verts[n+4],verts[n+3],verts[n+5]))
        depth=1.10
        from assembly_detail import _point_inside
        for cover in model['heatsinks']:
            if _point_inside(uv,cover['polygon']):depth=max(depth,cover['depth_mm']+1.12)
        printed.extend(translated(rotate_vertices(verts,'left'),point(uv,depth)))
    for index,(u,v) in enumerate(model['dimm_uv']):
        slot=('A1','A2','B1','B2')[index] if len(model['dimm_uv'])==4 else ('A1','B1')[index]
        silk('DIMM '+slot,(u+.013,v),True,.27)
    for index,row in enumerate(model['pcie']):silk('PCIE '+str(index+1),(row['uv'][0]+.24,row['uv'][1]-.024))
    for index,row in enumerate(model['m2']):
        if row['side']=='front':silk('M2-'+str(index+1),(row['uv'][0]+row['along'][0]*.10,row['uv'][1]-.014),pixel=.27)
    for row in model['connectors']:
        label={'atx24':'ATX24','eps8':'CPU12V','eps4':'CPU12V','aux6':'AUX6','sata':'SATA','front_io':'PANEL','usb2':'USB2','usb3':'USB3',
            'usb_c':'USBC','audio':'AUDIO','fan':'FAN','argb':'ARGB','rgb':'RGB','thermal':'TSENSOR','cpu_ov':'CPU OV','thunderbolt':'TB HEADER'}[row['kind']]
        silk(label,(max(.04,row['uv'][0]-.025),max(.038,min(.958,row['uv'][1]-.017))),pixel=.23)
    silk(model['socket'],(model['cpu_uv'][0]+.09,model['cpu_uv'][1]+.139),True,.24)
    add('board-functional-silkscreen',tuple(printed),color('#bac1c9'),(0,0,0))
    for kind,u,v in model['diagnostics']:
        pos=point((u,v),3.)
        if kind=='start':
            add('board-start-button',rotate_vertices(ring(5.8,0,2.5,segments=24),'left'),steel,pos)
        elif kind=='q-code':
            cube('board-qcode-housing',(3.,9.,15.),pos,dark)
            # Unlit segment wells cannot be mistaken for a measured POST code.
            add('board-qcode-unlit-segments',rotate_vertices(_printed_text('88',.75),'left'),color('#333943'),(pos[0]-1.6,pos[1],pos[2]))
        elif kind=='q-led':
            for index in range(4):cube('board-qled-unlit-lens',(1.,1.7,2.2),point((u,v+index*.009),2.),color('#484d53'))
        elif kind=='q-release':
            cube('board-qrelease-button',(9.,9.,7.),pos,metal)
    # Actual rear connector counts, grouped in a physical 158 x 45mm shield.
    # Exact jack center dimensions are observed layout rather than certified CAD.
    ports=model['rear_ports'];io_pos=(bx-20.5,by+bh/2-80.,rear-.85);port_shapes=[];recesses=[];frames={};inserts=[]
    port_size=dict(usb_a=(12.4,5.6),usb_c=(8.5,3.6),hdmi=(14.,5.8),displayport=(14.5,6.3),lan=(13.,12.),
        audio_3_5=(5.7,5.7),spdif=(8.,8.),antenna=(5.,5.),buttons=(4.,4.),ps2=(12.5,12.5),vga=(18.,9.),dvi=(24.5,8.5))
    for row in model['rear_layout']:
        kind=row['kind'];cx,cy=row['x_mm'],row['y_mm'];pw,ph=port_size[kind]
        shape=circle(0,0,pw/2,16) if kind in ('audio_3_5','antenna','buttons','ps2') else _port_shape(kind,pw,ph)
        if row['rotated']:
            shape=tuple((-y,x) for x,y in shape);pw,ph=ph,pw
        port_shapes.append(tuple((x+cx,y+cy) for x,y in shape))
        frame=perforated_plate(chamfer_rect(pw+1.3,ph+1.3,.7),(shape,),.8)
        frames.setdefault(kind,[]).extend(translated(frame,(cx,cy,0)))
        recesses.append(((pw,ph,2.),(cx,cy,1.8)))
        if kind=='ps2':
            # Six distinct DIN contact wells and its keyed lower opening.
            wells=[circle(x,y,.58,8) for x,y in ((-2.3,2.3),(2.3,2.3),(-3.,0),(3.,0),(-1.4,-2.6),(1.4,-2.6))]
            wells.append(tuple((x,y-4.1) for x,y in chamfer_rect(2.,1.2,.15)))
            inserts.extend(translated(perforated_plate(circle(0,0,5.7,20),wells,.5),(cx,cy,.8)))
        elif kind=='vga':
            wells=[circle((col-2)*2.6+(.6 if row==1 else 0.),(row-1)*2.,.42,8) for row in range(3) for col in range(5)]
            inserts.extend(translated(perforated_plate(_port_shape('vga',16.8,7.8),wells,.5),(cx,cy,.8)))
        elif kind=='dvi':
            # DVI-D's separate24 digital contact wells and flat key: no four
            # analog DVI-I contacts. Pitch/depth are interface reference, not
            # a claim about the exact retail connector supplier's CAD.
            wells=[circle(-7.+col*1.8,(line-1)*1.8,.40,8) for line in range(3) for col in range(8)]
            # Keep the shared24-hole cap: the flat key occupies a separate
            # adjacent region instead of silently becoming an uncut25th hole.
            contact_side=((-11.55*.86,-3.65),(7.2,-3.65),(7.2,3.65),(-11.55,3.65))
            key_side=((7.2,-3.65),(11.55*.86,-3.65),(11.55,3.65),(7.2,3.65))
            key_hole=tuple((x+9.,y) for x,y in chamfer_rect(2.6,.75,.1))
            for inner,holes in ((contact_side,wells),(key_side,(key_hole,))):
                if row['rotated']:
                    # Horizontal manual is observed from outside: local right
                    # runs toward decreasing caseY. Preserve the documented
                    # right-hand flat key, not its mirrored internal view.
                    inner=tuple((-y,-x) for x,y in inner)
                    holes=[tuple((-y,-x) for x,y in hole) for hole in holes]
                inserts.extend(translated(perforated_plate(inner,holes,.5),(cx,cy,.8)))
    add('detail-board-rear-io-shield',perforated_plate(chamfer_rect(45.,158.,1.5),port_shapes,1.),steel,io_pos)
    add('detail-board-rear-io-recesses',_boxes(recesses),dark,io_pos)
    for kind,vertices in frames.items():add('detail-board-rear-'+kind,vertices,steel,io_pos)
    add('detail-board-rear-keyed-pin-inserts',tuple(inserts),color('#454954'),io_pos)
    # Align the previously reference-positioned GPU contact pads to the actual
    # primary-slot landmark; neither card envelope nor rear bracket is moved.
    shift=anchors['primary_pcie_start_z']-(rear+15.)
    out=[replace(mesh,position=(mesh.position[0],mesh.position[1],mesh.position[2]+shift))
         if mesh.name=='detail-gpu-separated-edge-contacts' else mesh for mesh in out]
    counts=dict(dimm=len(model['dimm_uv']),pcie_x16=sum(r['kind']=='x16' for r in model['pcie']),
        pcie_x1=sum(r['kind']=='x1' for r in model['pcie']),m2=len(model['m2']),sata=sum(r['count'] for r in model['connectors'] if r['kind']=='sata'))
    if any(r['kind']=='x4' for r in model['pcie']):counts['pcie_x4']=sum(r['kind']=='x4' for r in model['pcie'])
    requested_memory=(spec.get('memory') or {}).get('count',0)
    requested_memory=max(0,requested_memory) if isinstance(requested_memory,int) and not isinstance(requested_memory,bool) else 0
    meta=dict(model_id=model['id'],model_label=model['label'],exact_profile=model['id'],layout_method=model['layout_method'],
        layout_schematic=True,source_matched_layout=True,layout_source=model['manual'],layout_page=model['layout_page'],
        finish_method=model['finish_method'],sources=model['sources'],cad_verified=False,pcb_routing_verified=False,
        chip_count_schematic=True,mount_positions_schematic=model['mount_method']=='reference_unverified_hole_centers',
        mount_method=model['mount_method'],mount_source=model['manual'],documented_slot_counts=counts,
        documented_rear_ports=copy.deepcopy(ports),rendered_memory_sockets=counts['dimm'],
        populated_memory_sockets=min(requested_memory,counts['dimm']),
        memory_population_exceeds_documented_slots=requested_memory>counts['dimm'],
        m2_heatsinks=sum(c['name'].startswith('m2') for c in model['heatsinks']),installed_ssd_count_inferred=False,
        rear_io_layout_schematic=True,rear_io_source=model['rear_layout_source'],small_package_positions_schematic=True,
        heatsink_recesses_are_open_geometry=True,socket_contact_pattern_is_sampling=True,
        socket_contact_topology='pga_receiving_wells' if model['socket']=='AM4' else 'sampled_lga_springs',
        socket_contact_dimensions_verified=False,
        dimm_contact_topology='split_side_banks_open_channel_reference',dimm_contact_dimensions_verified=False,
        power_contact_count=power_contact_count,power_contacts_independent=True,
        connector_contact_shape_reference=True,connector_oem_identified=False,
        m2_receiving_channel_count=len(anchors['connectors']['m2']),m2_receiving_channel_open=True,
        m2_contact_map_drawn=False,interface_detail_sources=(_POWER_INTERFACE_SOURCE,_M2_INTERFACE_SOURCE),
        finish_status=model['finish_status'],series=model['series'],
        unplaced_source_features=model.get('unplaced_source_features',()),
        bundled_m2_accessory_slots=model.get('bundled_m2_accessory_slots',0),bundled_m2_accessory_installed=False,
        battery_placement_status=model.get('battery_placement_status','manual_observed'))
    if model.get('source_finish_model')==model['id']:
        armor_names={'detail-board-m2-heatsink','board-heatsink-recessed-crown',
                     *('board-'+cover['name']+'-heatsink' for cover in model['heatsinks'])}
        roles={mesh.name:'pcb' if mesh.name=='motherboard-reference' else 'armor' if mesh.name in armor_names else 'inlay'
               for mesh in parts if mesh.name=='motherboard-reference' or mesh.name in armor_names
               or mesh.name.startswith('board-static-finish-')}
        meta['finish_materials']=dict(model_id=model['id'],roles=roles)
    if model.get('onboard_fans'):
        meta['onboard_fans']=copy.deepcopy(model['onboard_fans'])
        meta['onboard_fan_telemetry_bound']=False
        meta['onboard_fan_motion']='static_unverified_tachometer_and_direction'
    cpu=spec.get('cpu') or {};identity=(cpu.get('appearance') or {}).get('id',cpu.get('model_id'))
    known_socket={'intel-13700kf':'LGA1700','amd-9950x':'AM5','amd-7800x3d':'AM5'}.get(identity)
    checks=[dict(kind='cpu_socket',state='unknown' if not known_socket else 'matching' if known_socket==model['socket'] else 'mismatch',
        board_socket=model['socket'],cpu_socket=known_socket)]
    for index,module in enumerate((spec.get('memory') or {}).get('modules') or ()):
        if not isinstance(module,dict):continue
        appearance=module.get('appearance') or {};generation=(appearance.get('board_details') or {}).get('generation')
        if isinstance(generation,str) and generation:
            checks.append(dict(kind='memory_generation',module=index,state='matching' if generation.upper()==model['memory_type'] else 'mismatch',
                board_generation=model['memory_type'],module_generation=generation.upper()))
        if appearance.get('form_factor')=='sodimm' or appearance.get('style')=='sodimm':
            checks.append(dict(kind='memory_form',module=index,state='mismatch',board_form='dimm',module_form='sodimm'))
    meta['compatibility']=checks
    return tuple((*out,*parts)),meta


def final_anchors(anchors,board_pose,gpu_pose,gpu_position,gpu_size,spec,*,gpu_vector=None,board_vector=None):
    """Return detached final case-space endpoints for cooling/auxiliary modules."""
    result=copy.deepcopy(anchors or {});result.setdefault('case',copy.deepcopy(spec.get('case') or {}))
    board_direction=board_vector or board_pose
    for key in ('cpu','board'):
        row=result.get(key)
        if not row:continue
        for vector in ('normal','up','u','v','along'):
            if vector in row:row[vector]=board_direction(row[vector])
        row['position']=board_pose(row['position']);row.update(zip(('x','y','z'),row['position']))
    for rows in result.get('connectors',{}).values():
        for row in rows:
            for key in ('position','rear_position'): 
                if key in row:row[key]=board_pose(row[key])
            for key in ('normal','along'):
                if key in row:row[key]=board_direction(row[key])
    if 'dimm_centers' in result:result['dimm_centers']=[board_pose(p) for p in result['dimm_centers']]
    if gpu_position is not None:
        vector=gpu_vector or gpu_pose
        center=gpu_pose(gpu_position);result['gpu']=dict(center=center,position=center,size=gpu_size,
            normal=vector((0.,-1.,0.)),up=vector((1.,0.,0.)),along=vector((0.,0.,1.)),
            width_mm=gpu_size[0],thickness_mm=gpu_size[1],length_mm=gpu_size[2],power=[])
        facts=((spec.get('gpu') or {}).get('appearance') or {}).get('board_details') or {}
        power=facts.get('power_connectors') or ()
        gx,gy,gz=gpu_position;gw,gt,gl=gpu_size
        pcb_center=gpu_pose((gx,gy+gt/2-3.3,gz))
        result['gpu']['pcb']=dict(position=pcb_center,center=pcb_center,canonical_size=(gw*.94,1.6,gl*.96),
            width_mm=gw*.94,length_mm=gl*.96,thickness_mm=1.6,normal=vector((0.,-1.,0.)),
            along=vector((0.,0.,1.)),up=vector((1.,0.,0.)),dimensions_verified=False,geometry_is_reference=True,
            source='existing_reference_gpu_pcb_not_verified_retail_outline')
        for group in power:
            if not isinstance(group,dict) or type(group.get('count')) is not int:continue
            for index in range(min(group['count'],4)):
                position=(gx-gw/2-1.,gy,gz+gl*.08+index*16.)
                result['gpu']['power'].append(dict(kind=group.get('type'),type=group.get('type'),
                    position=gpu_pose(position),normal=vector((-1.,0.,0.)),along=vector((0.,0.,1.)),
                    position_schematic=True,count_source='reviewed_gpu_catalog',position_source='reference_not_verified'))
    return result


def augment_attachment_anchors(anchors,meshes):
    """Actual final-space mesh bounds/known case sockets for safe attachments."""
    result=copy.deepcopy(anchors);gpu=[m for m in meshes if m.component=='gpu']
    if gpu and result.get('gpu'):
        result['gpu']['bounds']={key:tuple(fn(m.position[k]+value for m in gpu for value in m.vertices[k::6]) for k in range(3))
            for key,fn in (('min',min),('max',max))}
    case=result.get('case') or {};details=case.get('exterior_details') or {};io=details.get('io') or {}
    sockets=[];placement=io.get('position');angular=placement=='front_bottom' and 'angular_glass_corner' in case.get('features',())
    normal=(-math.sqrt(.5),0.,math.sqrt(.5)) if angular else (0.,1.,0.) if placement=='top' else (-1.,0.,0.) if placement=='left_front' else (0.,0.,1.)
    for kind in ('usb_a','usb_c','audio','buttons'):
        count=io.get(kind,0)
        if type(count) is not int or not 0<count<=8:continue
        name='case-io-'+kind+('-well' if kind.startswith('usb') else '-inset')
        mesh=next((m for m in meshes if m.name==name),None)
        if mesh is None or len(mesh.vertices)%count:continue
        chunk=len(mesh.vertices)//count
        for index in range(count):
            vertices=mesh.vertices[index*chunk:(index+1)*chunk]
            center=tuple((min(vertices[k::6])+max(vertices[k::6]))/2+mesh.position[k] for k in range(3))
            sockets.append(dict(kind=kind,position=center,normal=normal,position_schematic=True,
                source=details.get('sources',()),position_method='rendered_source_counted_case_io'))
    result['case_front_io']=sockets
    obstacles=[]
    for mesh in meshes:
        solid=(mesh.name=='motherboard-reference' or mesh.component in ('cooler','fans','memory')
               or mesh.component=='board' and 'heatsink' in mesh.name)
        if not solid or any(word in mesh.name for word in ('tube','wire','pipe','hose','fitting','lead')):continue
        low=tuple(min(mesh.vertices[k::6])+mesh.position[k] for k in range(3))
        high=tuple(max(mesh.vertices[k::6])+mesh.position[k] for k in range(3))
        if all(high[k]-low[k]>.1 for k in range(3)):
            obstacles.append(dict(bounds=dict(min=low,max=high),kind=mesh.component,part_id=mesh.part_id,name=mesh.name,
                conservative_mesh_aabb=True))
    result['obstacles']=obstacles
    return result


def attachment_bounds(meshes,dimensions,case):
    """Warn about actual selected geometry outside the reference case envelope.

    A bounded illustration is not a clearance certificate. Open frames can
    naturally expose parts; their protrusion is reported without asserting
    incompatibility. Nothing is reduced or omitted to make it fit.
    """
    groups={}
    for mesh in meshes:
        if mesh.component not in ('cooler','fans','psu','storage','expansion') and mesh.part_id!='gpu:waterblock':continue
        groups.setdefault((mesh.component,mesh.part_id or mesh.component),[]).append(mesh)
    bounds=[];notices=[];tolerance=7.5
    for (component,identity),parts in groups.items():
        low=tuple(min(m.position[k]+value for m in parts for value in m.vertices[k::6]) for k in range(3))
        high=tuple(max(m.position[k]+value for m in parts for value in m.vertices[k::6]) for k in range(3))
        excess=tuple(max(0.,-dimensions[k]/2-low[k],high[k]-dimensions[k]/2) for k in range(3))
        record=dict(component=component,part_id=identity,min=low,max=high,excess_mm=excess,tolerance_mm=tolerance)
        bounds.append(record)
        if any(value>tolerance for value in excess):
            notices.append(dict(**record,reason='outside_reference_case',severity='warning',
                case_open_frame=case.get('layout')=='open_frame',actual_fit_verified=False))
    return bounds,notices
