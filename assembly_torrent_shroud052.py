"""Exact Torrent upper PSU skin and open bottom fan bracket references.

The official manual shows a short rear PSU compartment, a rising front end,
ventilation beneath the supply, and a separate open bottom fan bracket. These
are original low-poly surfaces, not a filled bay or manufacturer CAD. Unmarked
sheet thickness, aperture shape and all coordinates remain drawing references;
they never depend on a selected fan, power supply or collision result.
"""
import math

CASE_ID='fractal-torrent-tg'
CASE_IDS=(CASE_ID,)
PRODUCT='https://www.fractal-design.com/products/cases/torrent-series/torrent/torrent-rgb-black-tg-light-tint/'
MANUAL='https://www.fractal-design.com/app/uploads/2024/10/Torrent-manual-v.1.1_2024-10-28.pdf'
INTERIOR='https://assets.fractal-design.com/images/uxzbxy2o/production/1d3a02ac929e33757d0d9308cf14615f4eb5a2cd-2560x1810.jpg'
REAR_INTERIOR='https://assets.fractal-design.com/images/uxzbxy2o/production/62628eadf233aa73bd5aada76eefd44474841a04-2560x1810.jpg'
SOURCES=(PRODUCT,MANUAL,INTERIOR,REAR_INTERIOR)


def _valid(case,dimensions):
    if not isinstance(case,dict) or case.get('id')!=CASE_ID:return False
    if (not isinstance(dimensions,(tuple,list)) or len(dimensions)!=3
            or any(type(v) not in (int,float) or not math.isfinite(v) for v in dimensions)):
        return False
    w,h,d=dimensions
    return 60<=w<=800 and 120<=h<=900 and 150<=d<=900


def layout_reference(case,dimensions):
    """Fixed bottom installation face and a bounded rear-top PSU reference.

    Manual printed29/30 depicts fans above the open bracket. The 1-mm drawing
    gap and numeric plane are references, not measured fastener coordinates or
    an inferred airflow direction. The existing canonical bottom frame supplies
    its normal. The fixed PSU floor clears the skin; no board/CPU/GPU/RAM
    position or selected component geometry defines that skin.
    """
    if not _valid(case,dimensions):return {}
    w,h,d=map(float,dimensions);top=-h/2+18.
    return dict(case_id=CASE_ID,source=MANUAL,source_urls=SOURCES,
        reference_only=True,verified=False,dimensions_verified=False,positions_verified=False,
        board_pose_changed=False,psu_original_axis_and_rear_alignment_preserved=True,
        psu_fan_orientation_verified=False,psu_fan_world_normal_reference=(0.,-1.,0.),
        psu=dict(basis=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.)),center_x_mm=0.,
            floor_y_mm=h*.315+1.2+1.,rear_z_mm=-d/2+10.,
            source=MANUAL,reference_only=True,positions_verified=False,
            drawing_floor_gap_mm=1.,drawing_floor_gap_verified=False),
        mount_planes=dict(bottom=dict(position=(0.,top+1.,0.),normal=(0.,-1.,0.),up=(0.,0.,1.),
            span_mm=(w-24.,d-32.),source=MANUAL,reference_only=True,
            positions_verified=False,dimensions_verified=False,normal_verified=False,
            up_verified=False,verified=False,drawing_gap_mm=1.,drawing_gap_verified=False,
            source_manual_printed_pages=(29,30),source_role='Fans above the independent open bottom bracket.')))


def _surface(xs,ys,zs,cells,variable_y=None):
    """Exterior only of a small conforming material-cell union.

    Coordinates share exact nodes across folds; absent cells are real voids.
    There are no buried duplicate walls between neighbouring material cells.
    """
    from assembly_geometry import _quad
    out=[]
    def point(i,j,k):
        return (xs[i],variable_y(j,zs[k]) if variable_y else ys[j],zs[k])
    for i,j,k in sorted(cells):
        faces=(
            ((i-1,j,k),((i,j,k),(i,j,k+1),(i,j+1,k+1),(i,j+1,k)),(-1,0,0)),
            ((i+1,j,k),((i+1,j,k),(i+1,j+1,k),(i+1,j+1,k+1),(i+1,j,k+1)),(1,0,0)),
            ((i,j-1,k),((i,j,k),(i+1,j,k),(i+1,j,k+1),(i,j,k+1)),(0,-1,0)),
            ((i,j+1,k),((i,j+1,k),(i,j+1,k+1),(i+1,j+1,k+1),(i+1,j+1,k)),(0,1,0)),
            ((i,j,k-1),((i,j,k),(i,j+1,k),(i+1,j+1,k),(i+1,j,k)),(0,0,-1)),
            ((i,j,k+1),((i,j,k+1),(i+1,j,k+1),(i+1,j+1,k+1),(i,j+1,k+1)),(0,0,1)),
        )
        for neighbour,indices,normal in faces:
            if neighbour in cells:continue
            points=[point(*p) for p in indices]
            a,b,c=points[:3];ab=tuple(b[n]-a[n] for n in range(3));ac=tuple(c[n]-a[n] for n in range(3))
            cross=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
            if sum(cross[n]*normal[n] for n in range(3))<0:points.reverse()
            _quad(out,*points)
    return tuple(out)


def _part(identity,label,name,kind,bounds):
    return dict(id=identity,label=label,kind=kind,component='case',model_id=CASE_ID,
        mesh_name=name,assembly_state='installed',geometry_status='official_photo_reference',
        dimensions_verified=False,positions_verified=False,thickness_verified=False,
        source_url=PRODUCT,source_urls=SOURCES,reference_bounds_world_mm=bounds,
        display_screen=False,power_sensor_bound=False)


def _bounds(vertices):
    return dict(min=tuple(min(vertices[k::6]) for k in range(3)),
                max=tuple(max(vertices[k::6]) for k in range(3)))


def build(case,dimensions,tone):
    """Return two fixed physical parts and detached construction-only metadata.

    The caller replaces the old full-depth top cuboid AND old solid bottom
    plate. Existing case rails/feet remain. No whole compartment AABB is added
    as material; collision and picking use these actual open surfaces.
    """
    if not _valid(case,dimensions):return (),{}
    from assembly_geometry import Mesh
    w,h,d=map(float,dimensions);rail=max(5.,min(9.,w*.028))
    t=1.2;half=(w-12.)/2.;rear=-d*.48;end=-d*.02;front=d*.07
    low=h*.315;raised=h*.39;top=h/2-rail
    # Printed7/39 side views: rear low floor, then a short rising front end.
    # The back and far side remain open as the official top-access/cable views
    # show; the existing chassis boundary/tray is not duplicated with a wall.
    xs=(-half,-half+t,-w*.31,w*.31,half)
    zs=(rear,-d*.47,-d*.07,end,front)
    cells={(0,j,k) for j in (0,1) for k in range(4)}
    cells|={(i,0,k) for i in range(1,4) for k in range(4)}
    cells.remove((2,0,1))
    def y(j,z):
        floor=low if z<=end else low+(raised-low)*(z-end)/(front-end)
        return floor if j==0 else floor+t if j==1 else top
    cover=_surface(xs,(0.,1.,2.),zs,cells,y)
    cover_bounds=_bounds(cover)
    # Printed30 shows three broad open bracket windows. Long mounting slots
    # and small perforations are not guessed. These fixed reference windows
    # are not shaped around a currently selected fan.
    hx=w/2-rail;hz=d/2-rail;side=w*.34;border=12.;bar=6.
    opening=(2*hz-2*border-2*bar)/3
    cuts=[-hz,-hz+border]
    for i in range(3):
        cuts.append(cuts[-1]+opening)
        if i<2:cuts.append(cuts[-1]+bar)
    cuts.append(hz)
    bx=(-hx,-side,side,hx);by=(-h/2+16.,-h/2+18.)
    solids={(i,0,k) for i in range(3) for k in range(7)
            if not(i==1 and k in (1,3,5))}
    bracket=_surface(bx,by,tuple(cuts),solids)
    bracket_bounds=_bounds(bracket)
    meshes=(Mesh('top-psu-shroud',cover,tone,component='case',part_id='case:psu-top-cover'),
            Mesh('torrent-bottom-intake-frame',bracket,tone,component='case',part_id='case:bottom-intake-frame'))
    parts=[_part('case:psu-top-cover','Torrent 顶部电源罩','top-psu-shroud','case_cover',cover_bounds),
           _part('case:bottom-intake-frame','Torrent 底部进气支架','torrent-bottom-intake-frame','case_structure',bracket_bounds)]
    meta=dict(case_id=CASE_ID,method='official_manual_short_rear_top_psu_skin_and_open_bottom_bracket_reference',
        source_urls=SOURCES,manual_printed_pages=(5,7,12,13,29,30,39),parts=parts,
        replaces_case_bottom=True,replaces_top_psu_shroud=True,
        dimensions_verified=False,positions_verified=False,thickness_verified=False,cad_verified=False,
        chamber_is_solid=False,far_side_wall_added=False,selected_component_geometry_used=False,
        top_cover_thickness_mm=t,bottom_bracket_thickness_mm=2.,
        top_cover_thickness_verified=False,bottom_bracket_thickness_verified=False,
        front_upper_bay_open=True,psu_max_length_mm=230.,psu_max_length_source=PRODUCT,
        psu_max_length_verified=True,psu_original_axis_and_rear_alignment_preserved=True,psu_fan_orientation_verified=False,
        rear_floor_y_mm=low,rising_floor_end_y_mm=raised,side_upper_y_mm=top,
        rear_depth_mm=rear,rear_floor_end_depth_mm=end,rising_front_end_depth_mm=front,
        normalized_reference=dict(rear_depth_fraction=-.48,rear_floor_end_depth_fraction=-.02,
            front_end_depth_fraction=.07,floor_height_fraction=.315,raised_floor_height_fraction=.39),
        psu_intake_ventilation_observed=True,psu_intake_exact_pattern_modeled=False,
        psu_intake_reference_aperture=dict(x=(-w*.31,w*.31),z=(-d*.47,-d*.07),
            source_manual_printed_page=7,shape_verified=False,positions_verified=False,
            representation='One simplified open ventilation region; not the manufactured honeycomb hole pattern/count.'),
        bottom_bracket_three_large_openings_observed=True,bottom_bracket_exact_opening_dimensions_verified=False,
        bottom_mount_slots_modeled=False,bottom_mount_hole_positions_verified=False,
        source_top_shroud_argb_strip_observed=True,top_shroud_lighting_modeled=False,
        exact_fasteners_modeled=False,reference_only=True,new_pollers=0,new_clocks=0,
        reference_bounds_world_mm=cover_bounds,layout_reference=layout_reference(case,dimensions))
    return meshes,meta
