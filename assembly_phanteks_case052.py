"""Original NV5 / standard Evolv X2 lower-bay drawing references.

The manuals show separate covers and bottom fan brackets, not filled PSU
compartments. Unlabelled sheet thickness, coordinates, perforation sampling
and PSU clocking remain references. No selected component carves these skins.
This module only constructs static geometry; it does not discover hardware.
"""
import math

_NV5='phanteks-nv5'
_EVOLV='phanteks-evolv-x2'
CASE_IDS=(_NV5,_EVOLV)
_IDENTITY=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))
_ROWS={
    _NV5:dict(label='NV5',model='PH-NV523TG_DBK01',
        product='https://phanteks.com/product/nv5-black/',
        manual='https://www.phanteks.com/manuals/NV5_Manual_v1.1.pdf',
        photo='https://legacy.phanteks.com/images/product/PH-NV523/Black/NV5_10.png',
        manual_pdf_pages=(1,2,3)),
    _EVOLV:dict(label='Evolv X2',model='PH-ES524XTG_DBK01',
        product='https://phanteks.com/product/evolv-x2-black/',
        manual='https://phanteks.com.tw/assets/manuals/Manual_Evolv%20X2_v1.2_WEB.pdf',
        photo='https://phanteks.com/wp-content/uploads/2024/12/Evolv-X2_White_11.webp',
        manual_pdf_pages=(3,12,14,16)),
}


def _valid(case,dimensions):
    return (isinstance(case,dict) and isinstance(case.get('id'),str) and case['id'] in _ROWS
        and isinstance(dimensions,(tuple,list)) and len(dimensions)==3
        and all(type(v) in (int,float) and math.isfinite(v) for v in dimensions)
        and 180<=dimensions[0]<=350 and 400<=dimensions[1]<=700 and 350<=dimensions[2]<=650)


def layout_reference(case,dimensions):
    """Fixed source-informed host/fan faces, never measured mounting holes.

    NV5's dedicated front-bottom fan is horizontal despite its adjacent
    sloping cover. Evolv's three fans sit above the independently removable
    tray, with the supply below it. The caller positions a selected PSU's true
    envelope against the fixed floor; the skin never follows that envelope.
    """
    if not _valid(case,dimensions):return {}
    w,h,d=map(float,dimensions);identity=case['id'];row=_ROWS[identity]
    result=dict(case_id=identity,source=row['manual'],source_urls=(row['product'],row['manual'],row['photo']),
        reference_only=True,verified=False,positions_verified=False,dimensions_verified=False,
        psu_fan_orientation_verified=False,psu_fan_world_normal_reference=(0.,-1.,0.),
        psu_orientation_basis='Horizontal reference; source does not establish exact rear-opening roll.',
        drawing_floor_gap_mm=1.,drawing_floor_gap_verified=False)
    floor=-h/2+20. if identity==_NV5 else -h*.385
    result['psu']=dict(basis=_IDENTITY,center_x_mm=0.,floor_y_mm=floor,rear_z_mm=-d/2+10.,
        source=row['manual'],reference_only=True,positions_verified=False,verified=False)
    def plane(position,normal,up,span,role):
        return dict(position=position,normal=normal,up=up,span_mm=span,source=row['manual'],
            source_role=role,reference_only=True,verified=False,positions_verified=False,
            dimensions_verified=False,normal_verified=False,up_verified=False,
            drawing_gap_mm=1.,drawing_gap_verified=False)
    if identity==_NV5:
        result['mount_planes']=dict(
            bottom=plane((0.,-h/2+20.,d*.34),(0.,-1.,0.),(0.,0.,1.),(w-24.,d*.29),
                'Manual PDF3 independent single120 bracket; horizontal in exact original NV5 photograph.'),
            side=plane((w/2-10.,0.,d*.32),(1.,0.,0.),(0.,1.,0.),(d*.30,h-40.),
                'Fixed front-biased side bank observed in original NV5_10; unmeasured position.'))
        result['board_pose_changed']=False
    else:
        result['mount_planes']=dict(bottom=plane((0.,-h*.225+1.,0.),(0.,-1.,0.),(0.,0.,1.),
            (w-24.,d-32.),'Manual PDF16 three120 fans above the removable honeycomb tray.'))
        result['board_y_mm']=h*.07
        result['board_positions_verified']=False
        result['board_pose_basis']='Manual PDF12 overall installation drawing; bounded reference, not hole coordinates.'
    return result


def _face(out,points,normal):
    from assembly_geometry import _quad
    points=list(points);a,b,c=points[:3]
    ab=tuple(b[i]-a[i] for i in range(3));ac=tuple(c[i]-a[i] for i in range(3))
    cross=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
    if sum(cross[i]*normal[i] for i in range(3))<0:points.reverse()
    _quad(out,*points)


def _skin(half,bottom,top_rear,top_front,rear,front,thickness,front_wall=False):
    """One conforming closed L/C skin, without coincident internal walls."""
    xs=(-half,-half+thickness,half)
    zs=(rear,front-thickness,front) if front_wall else (rear,front)
    cells={(0,j,k) for j in range(2) for k in range(len(zs)-1)}
    if front_wall:cells|={(1,j,len(zs)-2) for j in range(2)}
    else:cells|={(1,1,0)}
    def p(i,j,k):
        top=top_rear+(top_front-top_rear)*(zs[k]-rear)/(front-rear)
        return (xs[i],bottom if j==0 else top-thickness if j==1 else top,zs[k])
    out=[]
    for i,j,k in sorted(cells):
        for neighbor,indices,normal in (
            ((i-1,j,k),((i,j,k),(i,j,k+1),(i,j+1,k+1),(i,j+1,k)),(-1,0,0)),
            ((i+1,j,k),((i+1,j,k),(i+1,j+1,k),(i+1,j+1,k+1),(i+1,j,k+1)),(1,0,0)),
            ((i,j-1,k),((i,j,k),(i+1,j,k),(i+1,j,k+1),(i,j,k+1)),(0,-1,0)),
            ((i,j+1,k),((i,j+1,k),(i,j+1,k+1),(i+1,j+1,k+1),(i+1,j+1,k)),(0,1,0)),
            ((i,j,k-1),((i,j,k),(i,j+1,k),(i+1,j+1,k),(i+1,j,k)),(0,0,-1)),
            ((i,j,k+1),((i,j,k+1),(i+1,j,k+1),(i+1,j+1,k+1),(i,j+1,k+1)),(0,0,1))):
            if neighbor not in cells:_face(out,[p(*q) for q in indices],normal)
    return tuple(out)


def _vent_floor(width,depth,top,thickness,center_z,columns,rows):
    """Closed sampled hex-aperture plate; sample count is not factory count.

    All cells use matching rectangular boundary partitions. Only the outer
    boundary and hole mouths get vertical walls; no buried cell-box walls.
    """
    cw,ch=width/columns,depth/rows;ax,az=cw/2,ch/2
    corner=math.atan2(az,ax)
    angles=sorted(set((0.,math.pi/3,2*math.pi/3,math.pi,4*math.pi/3,5*math.pi/3,
        corner,math.pi-corner,math.pi+corner,math.tau-corner)))
    hexagon=tuple((math.cos(n*math.tau/6)*ax*.70,math.sin(n*math.tau/6)*az*.70) for n in range(6))
    cross=lambda a,b:a[0]*b[1]-a[1]*b[0]
    def ray(angle):
        direction=(math.cos(angle),math.sin(angle));scale=min(ax/max(abs(direction[0]),1e-15),az/max(abs(direction[1]),1e-15))
        outer=[direction[0]*scale,direction[1]*scale]
        for k,extent in enumerate((ax,az)):
            if abs(abs(outer[k])-extent)<1e-9:outer[k]=math.copysign(extent,outer[k])
        hits=[]
        for a,b in zip(hexagon,(*hexagon[1:],hexagon[0])):
            edge=(b[0]-a[0],b[1]-a[1]);denom=cross(direction,edge)
            if abs(denom)<1e-12:continue
            s=cross(a,edge)/denom;t=cross(a,direction)/denom
            if s>=0 and -1e-9<=t<=1+1e-9:hits.append(s)
        s=min(hits)
        return tuple(outer),(direction[0]*s,direction[1]*s)
    rings=tuple(ray(a) for a in angles);out=[]
    for row in range(rows):
        for col in range(columns):
            cx=-width/2+(col+.5)*cw;cz=center_z-depth/2+(row+.5)*ch
            def point(q,y):return (cx+q[0],y,cz+q[1])
            for (oa,ia),(ob,ib) in zip(rings,(*rings[1:],rings[0])):
                _face(out,(point(oa,top),point(ob,top),point(ib,top),point(ia,top)),(0,1,0))
                _face(out,(point(oa,top-thickness),point(ia,top-thickness),point(ib,top-thickness),point(ob,top-thickness)),(0,-1,0))
                _face(out,(point(ia,top-thickness),point(ia,top),point(ib,top),point(ib,top-thickness)),
                    (-(ia[0]+ib[0]),0,-(ia[1]+ib[1])))
                left=col==0 and abs(oa[0]+ax)<1e-9 and abs(ob[0]+ax)<1e-9
                right=col==columns-1 and abs(oa[0]-ax)<1e-9 and abs(ob[0]-ax)<1e-9
                rear=row==0 and abs(oa[1]+az)<1e-9 and abs(ob[1]+az)<1e-9
                front=row==rows-1 and abs(oa[1]-az)<1e-9 and abs(ob[1]-az)<1e-9
                if left or right or rear or front:
                    _face(out,(point(oa,top-thickness),point(ob,top-thickness),point(ob,top),point(oa,top)),
                        (-1 if left else 1 if right else 0,0,-1 if rear else 1 if front else 0))
    return tuple(out)


def _bounds(vertices):
    return dict(min=tuple(min(vertices[k::6]) for k in range(3)),max=tuple(max(vertices[k::6]) for k in range(3)))


def build(case,dimensions,tone):
    """Return only exact model skins/brackets and detached static metadata."""
    if not _valid(case,dimensions):return (),{}
    from assembly_geometry import Mesh
    w,h,d=map(float,dimensions);identity=case['id'];row=_ROWS[identity];t=1.2
    half=(w-12.)/2;rear=-d/2+12.;layout=layout_reference(case,dimensions)
    floor=layout['psu']['floor_y_mm']-1.;meshes=[];parts=[]
    def add(name,vertices,part_id,label,kind,**extra):
        meshes.append(Mesh(name,vertices,tone,component='case',part_id=part_id))
        parts.append(dict(id=part_id,label=label,kind=kind,component='case',model_id=identity,
            mesh_name=name,assembly_state='installed',geometry_status='official_photo_reference',
            dimensions_verified=False,positions_verified=False,thickness_verified=False,
            source_url=row['product'],source_urls=(row['product'],row['manual'],row['photo']),
            reference_bounds_world_mm=_bounds(vertices),display_screen=False,power_sensor_bound=False,**extra))
    if identity==_NV5:
        roof=-h*.275;seam=d*.05;end=d*.18
        add('psu-shroud',_skin(half,floor,roof,roof,rear,seam,t),'case:psu-cover','NV5 后部电源罩','case_cover')
        add('psu-shroud',_skin(half,floor,roof,floor+24.,seam,end,t),'case:psu-front-cover',
            'NV5 独立前斜罩','case_cover',factory_removable=True,removal_source_pdf_page=2)
        add('phanteks-lower-support-floor',_vent_floor(w-12.,end-rear,floor,t,(rear+end)/2,3,5),
            'case:lower-support-floor','NV5 下部通风承托板','case_structure')
        depth=d*.29;center=d*.34
        add('phanteks-bottom-fan-bracket',_vent_floor(w-24.,depth,floor,t,center,3,2),
            'case:bottom-fan-bracket','NV5 独立底部风扇架','case_structure',factory_removable=True,removal_source_pdf_page=3)
        refs=dict(roof_height_fraction=-.275,rear_depth_fraction=rear/d,cover_seam_fraction=.05,
            cover_front_end_fraction=.18,side_bank_depth_fraction=.32,bottom_fan_depth_fraction=.34)
    else:
        tray=-h*.225;front=d/2-12.;support_end=d*.12
        # The C-like near side/front skin bounds an empty bay; the fan tray
        # and lower support remain separately inspectable structural parts.
        add('psu-shroud',_skin(half,floor,tray-t,tray-t,rear,front,t,True),
            'case:psu-cover','Evolv X2 下舱侧围','case_cover',factory_removable=None)
        add('phanteks-lower-support-floor',_vent_floor(w-12.,support_end-rear,floor,t,(rear+support_end)/2,3,4),
            'case:lower-support-floor','Evolv X2 下部电源承托板','case_structure')
        add('phanteks-bottom-fan-bracket',_vent_floor(w-12.,d-32.,tray,t,0.,3,6),
            'case:bottom-fan-bracket','Evolv X2 独立底部风扇托盘','case_structure',factory_removable=True,removal_source_pdf_page=16)
        refs=dict(psu_floor_height_fraction=-.385,tray_height_fraction=-.225,board_center_height_fraction=.07,
            lower_support_front_depth_fraction=.12)
    meta=dict(case_id=identity,source_model=row['model'],source_urls=(row['product'],row['manual'],row['photo']),
        source_manual_pdf_pages=row['manual_pdf_pages'],method='exact_manual_independent_lower_skin_and_open_fan_bracket_reference',
        parts=parts,replaces_case_bottom=True,chamber_is_solid=False,far_side_wall_added=False,
        dimensions_verified=False,positions_verified=False,thickness_verified=False,cad_verified=False,
        selected_component_geometry_used=False,reference_only=True,sheet_thickness_mm=t,
        sheet_thickness_verified=False,normalized_reference=refs,layout_reference=layout,
        ventilation_observed=True,exact_vent_pattern_modeled=False,vent_pattern_reference='coarse_hex_aperture_sampling',
        vent_sample_count_is_manufacturer_count=False,exact_mount_holes_modeled=False,
        psu_fan_orientation_verified=False,source_cover_lighting_observed=True,cover_lighting_modeled=False,
        white_photo_used_for_shape_only=identity==_EVOLV,finish_from_selected_case_tone=True,
        source_case_is_matrix=False,source_case_is_nv5_mkii=False,new_pollers=0,new_clocks=0)
    return tuple(meshes),meta
