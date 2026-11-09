"""Exact N260GTX Lightning exterior observations, not inferred fan blades.

MSI's original technical briefing p15 shows the brushed thin metal cover,
open cooler edge and two exposed heat-pipe bends; p15 documents five pipes
in total. The short visible segments below are original reference placement,
not an invented complete internal route, measured diameter or factory CAD.
No I/O, clock, sensor, GPU pose/connector change or generic SKU substitution.
"""
from dataclasses import replace
import math

EXACT_ID='msi-n260gtx-lightning'
EXPOSED_ID='gigabyte-fx5200-n52128d'
MANUAL_ID='gigabyte-fx5200-n52128d-rev10-reference'
METAL_COVER='gpu-cover-panel-tesla-brushed-metal'
SOURCE='https://event.msi.com/vga/lightning/download/MSI%20N260GTX%20Lightning%20Technical%20Briefing.pdf'


def side_windows(identity,outer,width,thickness):
    if identity!=EXACT_ID:return {}
    # The visible long edge below the face sheet exposes the fin bank and
    # two pipe returns. The photo shows a shallow folded front lip, not a
    # full-depth plastic wall. Ratios below are original reference placement;
    # keep the quoted envelope and end shoulders, do not invent CAD dimensions.
    return {i:(((.06,-thickness*.46),(.94,-thickness*.46),
                 (.94,thickness*.32),(.06,thickness*.32)),)
            for i,a in enumerate(outer)
            if abs(a[1]+width/2)<1e-5 and abs(outer[(i+1)%len(outer)][1]+width/2)<1e-5}


def _unit(v):
    size=math.hypot(*v)
    return tuple(x/size for x in v)


def _cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])


def _pipe(points,radius,segments):
    """Shared ring coordinates/normals; bounded static reference, solid ends."""
    rings=[];normals=[];tangents=[];previous=None
    for i,point in enumerate(points):
        delta=tuple(points[min(i+1,len(points)-1)][k]-points[max(0,i-1)][k] for k in range(3))
        t=_unit(delta);tangents.append(t)
        if previous is None:
            reference=(0.,0.,1.) if abs(t[2])<.85 else (0.,1.,0.)
            u=_unit(_cross(t,reference))
        else:
            dot=sum(a*b for a,b in zip(previous,t));u=_unit(tuple(previous[k]-dot*t[k] for k in range(3)))
        v=_cross(t,u);previous=u;ring=[];ns=[]
        for j in range(segments):
            a=math.tau*j/segments;n=tuple(u[k]*math.cos(a)+v[k]*math.sin(a) for k in range(3))
            ns.append(n);ring.append(tuple(point[k]+radius*n[k] for k in range(3)))
        rings.append(ring);normals.append(ns)
    result=[]
    def tri(a,b,c,na,nb,nc):
        ab=tuple(b[k]-a[k] for k in range(3));ac=tuple(c[k]-a[k] for k in range(3));face=_cross(ab,ac)
        if sum(face[k]*(na[k]+nb[k]+nc[k]) for k in range(3))<0:b,c,nb,nc=c,b,nc,nb
        for p,n in ((a,na),(b,nb),(c,nc)):result.extend((*p,*n))
    for i in range(len(points)-1):
        for j in range(segments):
            k=(j+1)%segments
            tri(rings[i][j],rings[i][k],rings[i+1][k],normals[i][j],normals[i][k],normals[i+1][k])
            tri(rings[i][j],rings[i+1][k],rings[i+1][j],normals[i][j],normals[i+1][k],normals[i+1][j])
    for i,sign in ((0,-1),(len(points)-1,1)):
        n=tuple(sign*x for x in tangents[i])
        for j in range(segments):tri(points[i],rings[i][j],rings[i][(j+1)%segments],n,n,n)
    return tuple(result)


def refine(meshes,spec,level):
    appearance=(spec.get('gpu')or{}).get('appearance')or{}
    if appearance.get('id') in (EXPOSED_ID,MANUAL_ID):return _exposed_fx5200(meshes,spec,level)
    if appearance.get('id')!=EXACT_ID:return meshes,{}
    shell=next((m for m in meshes if m.name=='gpu-shroud'),None)
    if shell is None:return meshes,{}
    from assembly_geometry import Mesh,gpu_plane,color,box
    width,thickness,length=tuple(max(shell.vertices[k::6])-min(shell.vertices[k::6]) for k in range(3))
    # Existing disjoint source-paint regions, real circular holes and thin
    # plate triangles stay byte-identical. Only their exact material identity
    # changes to the existing metallic/brushed policy.
    values=[replace(m,name=METAL_COVER) if m.name=='gpu-cover-panel' else m for m in meshes]
    steps=6 if level=='eco' else 10 if level=='balanced' else 14
    segments=6 if level=='eco' else 8 if level=='balanced' else 10
    radius=min(2.,thickness*.07,width*.025);pipe=[]
    for center in (.035*length,.345*length):
        points=[(center+length*.055*math.cos(math.pi*i/steps),
                 -width*(.33+.12*math.sin(math.pi*i/steps)),
                 thickness*(.10+.015*math.sin(math.pi*i/steps))) for i in range(steps+1)]
        pipe.extend(_pipe(points,radius,segments))
    values.append(Mesh('detail-gpu-lightning-visible-metal-pipe-bends',gpu_plane(pipe),color('#bbc0bd'),
                       shell.position,'gpu',part_id=getattr(shell,'part_id','')))
    # The manufacturer's side close-up establishes exposed fin stacks. Their
    # tiny individual count/pitch is not documented. Bounded samples make the
    # layer readable without fabricating additional heat pipes or PCB circuits.
    fin_count=24 if level=='eco' else 48 if level=='balanced' else 64
    fins=[]
    for i in range(fin_count):
        center=-length*.39+length*.78*i/(fin_count-1)
        vertices=box(width*.77,thickness*.48,.34)
        for n in range(0,len(vertices),6):
            fins.extend((vertices[n],vertices[n+1]+thickness*.02,vertices[n+2]+center,
                         *vertices[n+3:n+6]))
    values.append(Mesh('detail-gpu-lightning-observed-sampled-fin-stack',tuple(fins),color('#697477'),
                       shell.position,'gpu',part_id=getattr(shell,'part_id','')))
    return tuple(values),dict(legacy_exterior_exact_id=EXACT_ID,legacy_exterior_source=SOURCE,
        source_page=15,documented_total_heatpipes=5,observed_reference_visible_pipe_bends=2,
        remaining_internal_heatpipe_routes='unknown/not reconstructed',heatpipe_diameter_verified=False,
        pipe_radius_original_reference_mm=radius,face_sheet_geometry_preserved=True,
        exposed_fin_stack_observed=True,fin_sampling_count=fin_count,
        front_sheet_material='observed brushed metal; no factory finish measurement',
        fan_blade_count_still_unverified=True,ports_and_original_envelope_preserved=True)


def _exposed_fx5200(meshes,spec,level):
    """An exposed blue AGP board, not a modern full-depth plastic enclosure.

    The exact manufacturer's board photo and existing 2D study establish the
    small black radial heatsink, single active fan and blue PCB. Card dimensions,
    fin count/pitch and cooling height remain reference proportions. Leave the
    existing reference I/O/AGP contact layout alone; do not add guessed chips,
    capacitors, keyed pins or a confirmed absence of auxiliary power.
    """
    from assembly_geometry import Mesh,color,extrude,gpu_plane,ring,box
    from assembly_detail import perforated_plate,chamfer_rect,_port_shape
    gpu=spec.get('gpu')or{};facts=(gpu.get('appearance')or{}).get('board_details')or{}
    # The runtime deliberately projects only reviewed public fields. Gate this
    # exact source ID again by its existing blue AGP identity, rather than
    # widening every generic GPU with an author-only cover_style field.
    if facts.get('pcb_tone')!='blue' or (facts.get('host_interface')or{}).get('bus')!='agp':return meshes,{}
    pcb=next((m for m in meshes if m.name=='gpu-pcb'),None)
    shell=next((m for m in meshes if m.name=='gpu-shroud'),None)
    fan=next((m for m in meshes if m.name=='gpu-fan-opening'),None)
    if pcb is None or shell is None or fan is None:return meshes,{}
    width,thickness,length=tuple(max(shell.vertices[k::6])-min(shell.vertices[k::6]) for k in range(3))
    radius=max(math.hypot(fan.vertices[n],fan.vertices[n+2]) for n in range(0,len(fan.vertices),6))
    outer=min(radius*1.13,width*.31,length*.17);inner=outer*.77
    height=max(1.,thickness*.18);base_depth=min(1.,height*.12)
    pcb_front=pcb.position[1]+min(pcb.vertices[1::6])
    front=pcb_front-height-2.5;shift=front-fan.position[1]
    gx,gy,gz=shell.position;board_w=width*.90;board_l=length*.96;board_x=gx-width*.05
    def point(u,v,y=0.):return (board_x+(v-.5)*board_w,pcb_front-y,gz+(u-.5)*board_l)
    # The official manual photo labels this specimen REV:1.0. Use only its
    # clearly visible, fixed front parts, not a plausible random SMD scatter.
    memories=((.359,.167,.068,.233),(.469,.167,.068,.233),(.621,.167,.068,.233),(.723,.167,.068,.233),
              (.914,.208,.135,.126),(.914,.399,.135,.126),(.914,.681,.135,.126),(.914,.874,.135,.126))
    capacitors=((.090,.068,.018),(.113,.185,.027),(.271,.077,.028),
                (.272,.336,.022),(.311,.449,.027),(.312,.571,.027))
    values=[]
    for mesh in meshes:
        if mesh.name in ('gpu-shroud','gpu-cover-panel','gpu-bracket','detail-gpu-port-recesses',
                         'detail-gpu-pcb-stack-edge','detail-gpu-separated-edge-contacts') or mesh.name.startswith('gpu-reference-port-'):continue
        if mesh.name=='gpu-pcb':mesh=replace(mesh,vertices=box(board_w,1.6,board_l),position=(board_x,pcb.position[1],gz),
                                           color=color((gpu.get('colors')or{}).get('pcb'),'#386e98'))
        elif mesh.name.startswith('gpu-fan-'):mesh=replace(mesh,position=(mesh.position[0],mesh.position[1]+shift,mesh.position[2]))
        values.append(mesh)
    def add(name,vertices,tone,position):
        values.append(Mesh(name,vertices,color(tone),position,'gpu',part_id=getattr(pcb,'part_id','')))
    for i,(u,v,du,dv) in enumerate(memories):
        add('detail-gpu-fx5200-observed-memory-package-'+str(i+1),box(board_w*dv,1.4,board_l*du),
            '#233439',point(u,v,.7))
    sides=12 if level=='eco' else 16 if level=='balanced' else 24
    for i,(u,v,r) in enumerate(capacitors):
        r*=board_l;cap_h=r*1.8
        add('detail-gpu-fx5200-observed-capacitor-body-'+str(i+1),gpu_plane(ring(r,0,cap_h,segments=sides)),
            '#437d5c',point(u,v,cap_h/2))
        add('detail-gpu-fx5200-observed-capacitor-cap-'+str(i+1),gpu_plane(ring(r*.91,0,.35,segments=sides)),
            '#b7c1b7',point(u,v,cap_h+.18))
    add('detail-gpu-fx5200-observed-copper-toroid',gpu_plane(ring(board_l*.025,board_l*.012,5.,segments=sides)),
        '#bd8c46',point(.200,.560,3.))
    add('detail-gpu-fx5200-observed-grey-inductor',box(board_w*.059,3.8,board_l*.058),
        '#63776f',point(.200,.336,1.9))
    add('detail-gpu-fx5200-observed-white-two-wire-header',box(board_w*.044,3.0,board_l*.061),
        '#d7d9bd',point(.340,.954,1.5))
    # Bounded radial fin samples are heatsink metal, never rotor vanes.
    count=20 if level=='eco' else 32 if level=='balanced' else 48
    vertices=list(gpu_plane(ring(outer,0,base_depth,segments=24)))
    center_y=pcb_front-height/2
    # Base underside lies on the PCB surface, not in the middle of the fins.
    for n in range(0,len(vertices),6):vertices[n+1]+=height/2-base_depth/2
    for i in range(count):
        a=math.tau*i/count;half=math.tau/count*.11
        polygon=tuple((r*math.cos(t),r*math.sin(t)) for r,t in ((inner,a-half),(outer,a-half),(outer,a+half),(inner,a+half)))
        vertices.extend(gpu_plane(extrude(polygon,height)))
    values.append(Mesh('detail-gpu-fx5200-black-radial-heatsink',tuple(vertices),color('#273137'),
                       (fan.position[0],center_y,fan.position[2]),'gpu',part_id=getattr(pcb,'part_id','')))
    # Three observed edge-contact sections. Pad repetition is a bounded visual
    # sample, not the physical AGP contact count or an electrical key standard.
    for i,(u0,u1) in enumerate(((.385,.525),(.535,.647),(.658,.800))):
        add('detail-gpu-fx5200-observed-agp-tongue-'+str(i+1),box(width*.10,1.6,board_l*(u1-u0)),
            '#366a8a',point((u0+u1)/2,1+width*.05/board_w,-.8))
        pads=4 if level=='eco' else 8 if level=='balanced' else 12
        pad=[]
        for j in range(pads):
            at=u0+(u1-u0)*(j+.5)/pads;q=point(at,1+width*.05/board_w,.04)
            for n in range(0,len(b:=box(width*.083,.08,board_l*(u1-u0)/pads*.70)),6):
                pad.extend((b[n]+q[0],b[n+1]+q[1],b[n+2]+q[2],*b[n+3:n+6]))
        add('detail-gpu-fx5200-reference-agp-pad-samples-'+str(i+1),tuple(pad),'#c7a65d',(0,0,0))
    wire_points=((.525,.93),(.50,1.05),(.43,1.12),(.30,1.12),(.25,1.05),(.26,.99),(.34,.954))
    for i,tone in enumerate(('#973c38','#293135')):
        points=tuple(point(u,v,1.5+i*.8) for u,v in wire_points)
        add('detail-gpu-fx5200-reference-fan-wire-'+str(i+1),_pipe(points,.52,6),tone,(0,0,0))
    # Source-labelled I/O order (manual p5), with different real socket forms.
    # Their centers/heights are reference observations, not a measured bracket.
    holes=[];connector_y=pcb_front-5.;port_z=gz-length/2+1.
    for kind,v,pw,ph,tone in (('dvi',.30,25.,9.,'#d4d8c4'),('tv_out',.58,8.,8.,'#687b79'),('vga',.85,18.,9.,'#497fa7')):
        cx=point(.0,v)[0]-gx;shape=_port_shape(kind,pw,ph);hole=tuple((x+cx,y) for x,y in shape);holes.append(hole)
        frame=perforated_plate(chamfer_rect(pw+2.,ph+2.,.8),(shape,),4.,segments=16)
        add('gpu-reference-port-'+kind,frame,tone,(gx+cx,connector_y,port_z+1.4))
        # VGA's explicitly documented fifteen contacts remain fifteen; no
        # invented DVI/TV pin diagram is substituted behind the other sockets.
        if kind=='vga':
            pins=[]
            for row in range(3):
                for col in range(5):
                    p=(gx+cx+(col-2)*2.3,connector_y+(row-1)*1.9,port_z+2.2)
                    q=ring(.38,0,.4,segments=12)
                    for n in range(0,len(q),6):pins.extend((q[n]+p[0],q[n+1]+p[1],q[n+2]+p[2],*q[n+3:n+6]))
            add('detail-gpu-fx5200-vga-fifteen-reference-contacts',tuple(pins),'#9aabb1',(0,0,0))
    add('gpu-bracket',perforated_plate(chamfer_rect(width*.99,min(20.,thickness*.44),.8),tuple(holes),1.0,segments=16),
        '#a6b5bb',(gx,connector_y,port_z-.8))
    return tuple(values),dict(legacy_exterior_exact_id=(gpu.get('appearance')or{}).get('id'),
        legacy_exterior_source='https://download1.gigabyte.com/Files/Manual/vga_manual_n52128_e.pdf?v=26f5e035240719cc61a6b774d7ded4cd',
        source_image='manufacturer manual p5 embedded 1313x725 REV:1.0 board photograph',
        exposed_board_without_modern_shroud=True,pcb_tone_observed='blue',
        heatsink_geometry='small black radial active cooler; original reference dimensions',
        heatsink_fin_count_is_sampling=True,heatsink_fin_samples=count,
        actual_card_dimensions_verified=False,reference_envelope_is_not_measured=True,
        board_layout_reference='manufacturer manual p5 exact GV-N52128D REV:1.0 specimen; not a detected revision',
        observed_memory_packages=8,observed_large_capacitors=6,observed_copper_toroids=1,
        observed_fan_wire_header=1,observed_fan_wires=2,observed_agp_sections=3,
        positions_and_heights_verified=False,unreadable_small_components_not_reconstructed=True,
        fan_blade_count_still_unverified=(gpu.get('appearance')or{}).get('id')!=MANUAL_ID,
        known_io_types_and_agp_electrical_identity_preserved=True)
