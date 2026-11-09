"""Five primary-observed rear bays, including the original non-PRO KING95.

Independent thin supports/doors/empty drive frames replace the fictitious
filled chamber. Sheet thickness, perforations and all unlabelled coordinates
are original fixed drawing references, never selected-hardware cutouts or CAD.
"""
import math

NV7='phanteks-nv7'
C8='antec-c8-argb'
PANO='msi-mag-pano-100r-pz'
VISION='lian-li-o11-vision'
KING='montech-king-95'
CASE_IDS=(NV7,C8,PANO,VISION,KING)
PENDING_IDS=()
PSU_BASIS=((0.,1.,0.),(-1.,0.,0.),(0.,0.,1.))
_ROWS={
    NV7:dict(label='NV7',model='PH-NV723TG_DBK01',product='https://phanteks.com/product/nv7-black/',
        manual='https://www.phanteks.com/manuals/NV7_Manual_v1.1.pdf',pages=(13,14,25,26,27),
        max_psu_length_mm=255.,support_fraction=.17,support_offset=0.,support_end=.08),
    C8:dict(label='C8 ARGB',model='C8 ARGB / UPC 0-761345-10022-9',product='https://antec.com/product/case/c8-argb',
        manual='https://antec.com/documents/product/case-Antec_C8_ARGB_Manual_240516_compressed.pdf',pages=(8,14,15),
        max_psu_length_mm=210.,support_fraction=-.12,support_offset=0.,support_end=.02),
    PANO:dict(label='MAG PANO 100R PZ',model='MAG PANO 100R PZ',product='https://us.msi.com/PC-Case/MAG-PANO-100R-PZ/Specification',
        manual='https://download.msi.com/archive/mnu_exe/case/MAGPANO100L100RPZWHITE_English.pdf',pages=(1,3,19,20,21),
        max_psu_length_mm=200.,support_fraction=-.05,support_offset=0.,support_end=-.02),
    VISION:dict(label='O11 Vision',model='O11VX',product='https://lian-li.com/product/o11-vision/',
        manual='https://drive.google.com/file/d/1LVXoan0775264z7y9oL2LNIHVNURXTVy/view?usp=sharing',pages=(5,),
        max_psu_length_mm=232.,support_fraction=-.5,support_offset=21.2,support_end=.06),
    KING:dict(label='KING 95',model='KING 95 original / 475x300x442',
        product='https://www.telon.com.tw/en/products_detail.php?nid=388&s_ok2=',
        manual='https://mega.nz/file/IT9yRQoA#D93zwkDRM1EfWP-XUx5Dzw5e4aNlW8Bfcpxi-natycA',
        pages=(4,8,16,17),max_psu_length_mm=None,support_fraction=-.5,support_offset=21.2,support_end=-.05),
}


def _valid(case,dimensions):
    return (isinstance(case,dict) and isinstance(case.get('id'),str) and case['id'] in _ROWS
        and isinstance(dimensions,(tuple,list)) and len(dimensions)==3
        and all(type(v) in (int,float) and math.isfinite(v) for v in dimensions)
        and 200<=dimensions[0]<=400 and 350<=dimensions[1]<=700 and 350<=dimensions[2]<=650)


def layout_reference(case,dimensions):
    """Fixed host faces; a descriptor is not a mechanical compatibility claim."""
    if not _valid(case,dimensions):return {}
    w,h,d=map(float,dimensions);identity=case['id'];row=_ROWS[identity]
    board_x=w*.23 if identity==NV7 else w*.10
    support_top=h*row['support_fraction']+row['support_offset']
    gap=1. if identity in (VISION,KING) else 2.2
    result=dict(case_id=identity,source=row['manual'],source_urls=(row['product'],row['manual']),
        reference_only=True,positions_verified=False,dimensions_verified=False,verified=False,
        psu_fan_orientation_verified=False,psu_fan_world_normal_reference=(1.,0.,0.),
        psu_basis_observation='Tall rear AC opening / upright installation drawing, not a measured roll angle.',
        source_manual_pdf_pages=row['pages'],psu_support_top_y_mm=support_top,
        drawing_floor_gap_mm=gap,drawing_floor_gap_verified=False,
        psu=dict(basis=PSU_BASIS,align_x='right',boundary_x_mm=w/2-9.,
            floor_y_mm=support_top+gap,rear_z_mm=-d/2+10.,reference_only=True,
            positions_verified=False,source=row['manual']))
    left=-w/2+12.;right=board_x+3.
    def plane(x,span_y,role,normal=(0.,-1.,0.)):
        return dict(position=(x,-h/2+20. if normal[1]<0 else h/2-12.,0.),normal=normal,up=(0.,0.,1.),
            span_mm=(span_y,d-32.),source=row['manual'],source_role=role,reference_only=True,
            positions_verified=False,dimensions_verified=False,normal_verified=False,verified=False,
            drawing_floor_gap_mm=1.,drawing_floor_gap_verified=False)
    planes=dict(bottom=plane((left+right)/2,right-left,'Main-bay bottom mounting architecture; unlabelled fixed reference face.'))
    if identity!=VISION:
        top_right=w*.11-2. if identity==NV7 else right
        planes['top']=plane((left+top_right)/2,top_right-left,
            'Main-bay top reference, beside NV7 upper PSU cover where applicable.',(0.,1.,0.))
    result['mount_planes']=planes
    if identity==NV7:
        result.update(board_x_mm=board_x,board_y_mm=-h*.10,
            board_positions_verified=False,board_pose_source_pdf_page=13,
            rear_divider_top_y_mm=support_top-1.2,rear_divider_position_verified=False,
            rear_divider_reference_reason='Source upper PSU bay lies above the lower motherboard tray; a full-height divider would pass through it.',
            hybrid_upper_psu_bay=True)
    if identity==VISION:
        result.update(source_psu_bracket_protrusion_mm=15.,source_psu_bracket_protrusion_verified=True,
            rear_protrusion_modeled=False,rear_outer_panel_opening_modeled=False,
            preserved_rear_alignment_reason='Existing solid outer back has no source PSU cutout; this stage does not claim a real rear pass-through.')
    if identity==KING:
        result.update(source_variant='original_non_pro_default_glass',default_psu_mount='lower_rear',
            alternate_upper_psu_mount_observed=True,alternate_upper_psu_modeled=False,
            default_upper_drive_bracket_installed=True,
            source_psu_length_conflict_mm=dict(legacy_manual=190.,current_product=185.),
            source_psu_length_conflict_resolved=False,source_max_psu_length_mm=None,
            source_current_product_url='https://zh-tw.montechpc.com/king-95',
            source_legacy_manufacturer_about='https://www.telon.com.tw/en/about.php')
    return result


def _face(out,points,normal):
    from assembly_geometry import _quad
    points=list(points);a,b,c=points[:3]
    ab=tuple(b[k]-a[k] for k in range(3));ac=tuple(c[k]-a[k] for k in range(3))
    n=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
    if sum(n[k]*normal[k] for k in range(3))<0:points.reverse()
    _quad(out,*points)


def _cells(xs,ys,zs,solid):
    """Exterior of a conforming sheet/frame union; void cells stay empty."""
    out=[]
    def p(q):return xs[q[0]],ys[q[1]],zs[q[2]]
    for i,j,k in sorted(solid):
        for neighbor,points,normal in (
            ((i-1,j,k),((i,j,k),(i,j,k+1),(i,j+1,k+1),(i,j+1,k)),(-1,0,0)),
            ((i+1,j,k),((i+1,j,k),(i+1,j+1,k),(i+1,j+1,k+1),(i+1,j,k+1)),(1,0,0)),
            ((i,j-1,k),((i,j,k),(i+1,j,k),(i+1,j,k+1),(i,j,k+1)),(0,-1,0)),
            ((i,j+1,k),((i,j+1,k),(i,j+1,k+1),(i+1,j+1,k+1),(i+1,j+1,k)),(0,1,0)),
            ((i,j,k-1),((i,j,k),(i,j+1,k),(i+1,j+1,k),(i+1,j,k)),(0,0,-1)),
            ((i,j,k+1),((i,j,k+1),(i+1,j,k+1),(i+1,j+1,k+1),(i,j+1,k+1)),(0,0,1))):
            if neighbor not in solid:_face(out,[p(q) for q in points],normal)
    return tuple(out)


def _plate_x(x,y0,y1,z0,z1,t):return _cells((x,x+t),(y0,y1),(z0,z1),{(0,0,0)})


def _shelf(left,right,top,rear,front,t):
    return _cells((left,left+t,right),(top-t,top,top+16.),(rear,front),
        {(0,0,0),(1,0,0),(0,1,0)})


def _cage(left,right,bottom,top,rear,front,t):
    xs=(left,left+t,right-t,right);ys=(bottom,bottom+t,top-t,top);zs=(rear,rear+t,front-t,front)
    cells={(i,j,k) for i in range(3) for j in range(3) for k in range(3)
        if sum(v in (0,2) for v in (i,j,k))>=2}
    return _cells(xs,ys,zs,cells)


def _frame_z(left,right,bottom,top,rear,t):
    border=4.
    return _cells((left,left+border,right-border,right),(bottom,bottom+border,top-border,top),
        (rear,rear+t),{(i,j,0) for i in range(3) for j in range(3) if i!=1 or j!=1})


def build(case,dimensions,tone):
    if not _valid(case,dimensions):return (),{}
    from assembly_geometry import Mesh
    w,h,d=map(float,dimensions);identity=case['id'];row=_ROWS[identity];t=1.2
    layout=layout_reference(case,dimensions);top=layout['psu_support_top_y_mm']
    left=w*.11+2. if identity==NV7 else w*.10+8.;right=w/2-9.
    rear=-d/2+12.;front=d*row['support_end'];meshes=[];parts=[]
    def add(part,name,label,vertices,kind='case_structure',**extra):
        meshes.append(Mesh(name,vertices,tuple(tone),component='case',part_id=part))
        parts.append(dict(id=part,label=label,kind=kind,component='case',model_id=identity,mesh_name=name,
            assembly_state='installed',geometry_status='official_photo_reference',reference_only=True,
            dimensions_verified=False,positions_verified=False,thickness_verified=False,
            source_url=row['product'],source_urls=(row['product'],row['manual']),source_manual_pdf_pages=row['pages'],
            display_screen=False,power_sensor_bound=False,**extra))
    if identity==KING:
        # The guide shows lower rear mounting edges, not a filled shelf or
        # PSU tunnel. Two narrow fixed rail references leave the bay open.
        rails=_cells((w*.20,w*.20+4.,right-14.,right-10.),(top-t,top),(rear,front),
            {(0,0,0),(2,0,0)})
        add('case:rear-psu-support','case-rear-psu-support','KING 95 下置电源参考承托条',rails)
    else:
        add('case:rear-psu-support','case-rear-psu-support',row['label']+' 独立电源托架',_shelf(left,right,top,rear,front,t))
    if identity==NV7:
        add('case:psu-upper-cover','rear-chamber-shroud','NV7 上部电源仓侧皮',
            _plate_x(w*.11,top,h/2-18.,rear,front,t),'case_cover')
        for i,(y0,y1) in enumerate(((-h*.02,h*.14),(-h*.40,-h*.06))):
            add('case:storage-door:'+str(i),'case-storage-door','NV7 储存安装门 '+str(i+1),
                _plate_x(right-3.,y0,y1,-d*.45,-d*.03,t),factory_removable=True,empty_drive_mount=True)
    elif identity==C8:
        add('case:drive-cage','case-empty-drive-cage','C8 ARGB 独立空硬盘架',
            _cage(left+4.,right-4.,-h*.43,top-3.,rear,rear+d*.29,t),empty_drive_mount=True)
    elif identity==PANO:
        add('case:storage-door:0','case-storage-door','PANO 前部 SSD 安装门',
            _plate_x(right-3.,-h*.03,h*.34,d*.06,d*.30,t),factory_removable=True,empty_drive_mount=True)
        # The source lower hinged carrier has a return lip, not a PSU box.
        add('case:storage-door:1','case-storage-door','PANO 下部储存安装门',
            _cells((right-17.,right-3.,right-3.+t),(-h*.43,-h*.43+t,-h*.15),(-d*.45,d*.27),
                {(0,0,0),(1,0,0),(1,1,0)}),factory_removable=True,empty_drive_mount=True)
    elif identity==KING:
        floor=layout['psu']['floor_y_mm'];center=right-43.
        add('case:rear-psu-mount','case-rear-psu-mount','KING 95 固定后部电源安装边框',
            _frame_z(center-49.,center+49.,floor-2.,floor+156.,-d/2+7.,t),
            factory_removable=False,source_fastener_count=4,source_fastener_positions_modeled=False)
        add('case:drive-cage','case-empty-drive-cage','KING 95 独立空上部硬盘架',
            _cage(left+4.,right-4.,h*.02,h*.38,rear,-d*.10,t),
            factory_removable=True,empty_drive_mount=True,source_manual_pdf_page=16)
    else:
        floor=layout['psu']['floor_y_mm'];center=right-43.
        add('case:psu-rear-frame','case-rear-psu-frame','O11 Vision 可拆电源后框',
            _frame_z(center-49.,center+49.,floor-2.,floor+156.,-d/2+7.,t),
            factory_removable=True,real_rear_protrusion_modeled=False)
        add('case:drive-cage','case-empty-drive-cage','O11 Vision 独立空硬盘笼',
            _cage(left+4.,right-4.,h*.03,h*.37,rear,-d*.08,t),factory_removable=True,empty_drive_mount=True)
    meta=dict(case_id=identity,source_model=row['model'],source_urls=(row['product'],row['manual']),
        source_manual_pdf_pages=row['pages'],parts=parts,removed_parts=[],layout_reference=layout,
        replaces_rear_chamber_shroud=True,dimensions_verified=False,positions_verified=False,
        thickness_verified=False,cad_verified=False,reference_only=True,chamber_is_solid=False,
        selected_component_geometry_used=False,thickness_mm=t,psu_fan_orientation_verified=False,
        exact_vent_pattern_modeled=False,exact_hinge_and_fixings_modeled=False,
        installed_storage_assumed=0,display_screen=False,live_power_w=None,
        source_max_psu_length_mm=row['max_psu_length_mm'],source_max_psu_length_exclusive=identity==VISION,
        source_psu_length_limit_verified=True,layout_is_manufacturer_mount_datum=False,new_clocks=0,new_pollers=0,
        unknown=['Unlabelled thickness, bracket boundaries, clearances and holes remain fixed references.',
                 'No arbitrary selected hardware or wiring compatibility has been certified.'])
    if identity==C8:meta.update(airflow_partition_observed=True,airflow_partition_modeled=False)
    if identity==NV7:meta.update(requires_source_rear_divider_top=True,
        source_rear_divider_top_y_mm=layout['rear_divider_top_y_mm'],board_datum_verified=False)
    if identity==VISION:meta.update(source_psu_bracket_protrusion_mm=15.,source_psu_bracket_protrusion_verified=True,
        rear_protrusion_modeled=False,rear_outer_panel_opening_modeled=False,
        board_high_low_mode_implemented=False)
    if identity==KING:meta.update(source_variant='original_non_pro_default_glass',
        source_manual_sha256='65f292d1d3e498920680f0fd2fcf7f4bea9b577399ac88e44fbf81fc10cfa6bc',
        source_legacy_manufacturer_about='https://www.telon.com.tw/en/about.php',
        source_current_product_url='https://zh-tw.montechpc.com/king-95',
        default_psu_mount='lower_rear',alternate_upper_psu_mount_observed=True,
        alternate_upper_psu_modeled=False,default_upper_drive_bracket_installed=True,
        source_max_psu_length_mm=None,source_psu_length_limit_verified=False,
        source_psu_length_conflict_mm=dict(legacy_manual=190.,current_product=185.),
        source_psu_length_conflict_resolved=False,source_side_radiator_conflict_mm=dict(legacy_manual=280.,current_product=240.),
        source_side_radiator_conflict_resolved=False,source_side_radiator_capacity_changed=False,
        full_psu_shelf_added=False,main_floor_perforations_observed=True,
        main_floor_perforations_modeled=False,main_floor_geometry_changed=False,
        rear_outer_panel_opening_modeled=False)
    return tuple(meshes),meta
