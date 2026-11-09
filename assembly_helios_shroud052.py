"""GX601's separate cover plates/window, observed reference geometry only.

Official user-manual printed pages6/31 and service-manual page30 distinguish
the front/rear cover and transparent pane. Their unlabelled seam, thickness,
and window proportions below are fixed photograph references, not factory CAD.
No choice, collision, radiator, or cable is used to deform these surfaces.
"""
from copy import deepcopy
import math

CASE_ID='asus-rog-strix-helios-gx601'
SOURCE='https://rog.asus.com/us/cases/rog-strix-helios-model/'
USER='https://dlcdnets.asus.com/pub/ASUS/ODD/DC/ROG_Strix_Helios/ROG_Strix_Helios_User_Manual.pdf'
SERVICE='https://dlcdnets.asus.com/pub/ASUS/ODD/DC/ROG_Strix_Helios/GX601_R2R_Manual.pdf'
PHOTO='https://dlcdnimgs.asus.com/websites/global/products/g2Pl47nZaToiPUKg/img/pic_PSU_Shroud.jpg'
_NAMES={'rear':'helios-psu-rear-cover','front':'helios-psu-front-cover','window':'helios-psu-side-window'}
_IDS={'rear':'case:psu-rear-cover','front':'case:psu-front-cover','window':'case:psu-side-window'}


def _part(key):
    return dict(id=_IDS[key],label={'rear':'Helios 后段电源罩','front':'Helios 前段电源罩',
        'window':'Helios 电源透明观察窗'}[key],kind='case_window' if key=='window' else 'case_cover',
        component='case',model_id=CASE_ID,product_model='GX601',mesh_name=_NAMES[key],
        assembly_state='installed',geometry_status='official_photo_reference',dimensions_verified=False,
        source_url=SOURCE,source_urls=(SOURCE,USER,SERVICE,PHOTO),display_screen=False,power_sensor_bound=False)


def _cover(z0,z1,bottom,top,outer_x,far_x,thickness,window):
    """Watertight L material: side cap, roof, open compartment beneath.

    z0/z1 are (bottom,top) endpoints of the possibly diagonal segment boundary.
    At the bend the inner side ends at the roof underside, so there is no
    duplicated internal plate face, closed-box cavity, or full-height far wall.
    """
    from assembly_geometry import _tri,_quad
    from assembly_detail import perforated_plate
    inner=outer_x+thickness;under=top-thickness;height=top-bottom
    mix=lambda pair,y:pair[0]+(pair[1]-pair[0])*(y-bottom)/height
    polygon=((z0[0],bottom),(z1[0],bottom),(z1[1],top),(z0[1],top))
    inside=((z0[0],bottom),(z1[0],bottom),(mix(z1,under),under),(mix(z0,under),under))
    vertices=[]
    def face(points,normal):
        points=list(points);a,b,c=points[:3]
        ab=tuple(b[k]-a[k] for k in range(3));ac=tuple(c[k]-a[k] for k in range(3))
        cross=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
        if sum(cross[k]*normal[k] for k in range(3))<0:points.reverse()
        if len(points)==4:_quad(vertices,*points)
        else:_tri(vertices,*points)
    def cap(poly,x,normal):
        # Reuse only the app's actual disjoint perforated cap triangles. All
        # side/fold/aperture walls are added once from these same boundaries.
        local=tuple((-z,y) for z,y in poly)
        holes=(tuple((-z,y) for z,y in window),) if window else ()
        values=perforated_plate(local,holes,1.,clip_walls=True)
        for at in range(0,len(values),18):
            if values[at+5]>.999:
                face(tuple((x,values[at+j+1],-values[at+j]) for j in (0,6,12)),normal)
    cap(polygon,outer_x,(-1,0,0));cap(inside,inner,(1,0,0))
    face(((outer_x,top,z0[1]),(far_x,top,z0[1]),(far_x,top,z1[1]),(outer_x,top,z1[1])),(0,1,0))
    a,b=mix(z0,under),mix(z1,under)
    face(((inner,under,a),(far_x,under,a),(far_x,under,b),(inner,under,b)),(0,-1,0))
    face(((far_x,under,a),(far_x,under,b),(far_x,top,z1[1]),(far_x,top,z0[1])),(1,0,0))
    face(((outer_x,bottom,z0[0]),(inner,bottom,z0[0]),(inner,bottom,z1[0]),(outer_x,bottom,z1[0])),(0,-1,0))
    for pair,normal in ((z0,(0,0,-1)),(z1,(0,0,1))):
        z=mix(pair,under)
        face(((outer_x,bottom,pair[0]),(inner,bottom,pair[0]),(inner,under,z),(outer_x,under,z)),normal)
        face(((outer_x,under,z),(far_x,under,z),(far_x,top,pair[1]),(outer_x,top,pair[1])),normal)
    if window:
        cy=sum(y for z,y in window)/len(window);cz=sum(z for z,y in window)/len(window)
        for (za,ya),(zb,yb) in zip(window,(*window[1:],window[0])):
            face(((outer_x,ya,za),(inner,ya,za),(inner,yb,zb),(outer_x,yb,zb)),(0,cy-(ya+yb)/2,cz-(za+zb)/2))
    return tuple(vertices)


def prepare(case,dimensions,tone):
    """Keep rear/window physical now; hold the front candidate until cooling.

    No rejected selection can remove it: finish() uses actual built front
    radiator IDs and their world vertices, not only the requested spec.
    """
    if not isinstance(case,dict) or case.get('id')!=CASE_ID:return (),None,{}
    if (not isinstance(dimensions,(tuple,list)) or len(dimensions)!=3
            or any(type(v) not in (int,float) or not math.isfinite(v) for v in dimensions)):
        return (),None,{}
    w,h,d=dimensions
    if not (60<=w<=800 and 60<=h<=900 and 150<=d<=900):return (),None,{}
    from assembly_geometry import Mesh,extrude
    half=(w-12.)/2;bottom=-h*.49;top=-h*.32;rear=-(d-12.)/2;front=-rear
    span=front-rear;thickness=1.2;split=(rear+span*.340,rear+span*.557)
    # The official side photograph has a low, wide slanted window in the
    # rear plate. Its normalized proportions are bounded original geometry.
    window=((rear+span*.04,bottom+(top-bottom)*.16),
            (rear+span*.285,bottom+(top-bottom)*.16),
            (rear+span*.40,bottom+(top-bottom)*.75),
            (rear+span*.04,bottom+(top-bottom)*.75))
    rear_vertices=_cover((rear,rear),split,bottom,top,-half,half,thickness,window)
    front_vertices=_cover(split,(front,front),bottom,top,-half,half,thickness,None)
    glass=[];x=-half+thickness/2
    for at in range(0,len(values:=extrude(tuple((-z,y) for z,y in window),.8)),6):
        u,v,depth,nu,nv,nw=values[at:at+6];glass.extend((x+depth,v,-u,nw,nv,-nu))
    rear_mesh=Mesh(_NAMES['rear'],rear_vertices,tone,component='case',part_id=_IDS['rear'])
    front_mesh=Mesh(_NAMES['front'],front_vertices,tone,component='case',part_id=_IDS['front'])
    pane=Mesh(_NAMES['window'],tuple(glass),(.32,.41,.47,.24),component='case',part_id=_IDS['window'])
    meta=dict(case_id=CASE_ID,method='official_separate_cover_and_window_photo_reference',
        source_urls=(SOURCE,USER,SERVICE,PHOTO),user_manual_printed_pages=(6,31),service_manual_printed_page=30,
        service_part_number='90DC0020-B001JC',dimensions_verified=False,thickness_verified=False,
        positions_verified=False,window_shape_verified=False,cad_verified=False,thickness_mm=thickness,
        glass_thickness_mm=.8,glass_thickness_verified=False,
        normalized_reference=dict(split_bottom_span_fraction=.340,split_top_span_fraction=.557),
        side_window_polygon_world_zy_mm=window,split_world_z_bottom_top_mm=split,
        roof_world_y_mm=top,reference_bounds_world_mm=dict(min=(-half,bottom,rear),max=(half,top,front)),
        front_plate_end_position_verified=False,front_plate_end_reference_requires_review=True,
        official_front_fans=dict(count=3,size_mm=140,preinstalled=True,supported=True,source_url=SOURCE),
        chamber_is_solid=False,far_side_wall_added=False,
        assembly_state='awaiting_actual_cooling',parts=[_part('rear'),_part('window')],removed_parts=[],
        exact_decoration_and_fixings_modeled=False,window_is_display=False,actual_power_sensor_bound=False)
    return (rear_mesh,pane),front_mesh,meta


def _front_fan_intersection(meshes,meta):
    """Strict actual-triangle/material overlap, bounded and construction-only.

    The front L has two convex material regions: its thin side below the fold
    and its thin roof. The empty lower compartment is NOT an obstacle. This
    refuses an unresolved reference pose without asserting factory inability.
    """
    low,high=(meta['reference_bounds_world_mm'][k] for k in ('min','max'))
    thick=meta['thickness_mm'];under=high[1]-thick
    a,b=meta['split_world_z_bottom_top_mm'];slope=(b-a)/(high[1]-low[1]);intercept=a-slope*low[1]
    regions=(((1.,0.,0.,-low[0]),(-1.,0.,0.,low[0]+thick),(0.,1.,0.,-low[1]),(0.,-1.,0.,under)),
             ((1.,0.,0.,-low[0]),(-1.,0.,0.,high[0]),(0.,1.,0.,-under),(0.,-1.,0.,high[1])))
    common=((0.,-slope,1.,-intercept),(0.,0.,-1.,high[2]))
    seen=0
    for mesh in meshes:
        if any(word in mesh.name for word in ('wire','lead','connector')):continue
        v=mesh.vertices;p=mesh.position
        for at in range(0,len(v),18):
            seen+=1
            if seen>60000:return dict(mesh_name=mesh.name,reference_review='bounded_check_exhausted')
            triangle=[tuple(v[at+j+k]+p[k] for k in range(3)) for j in (0,6,12)]
            for region in regions:
                poly=triangle
                for nx,ny,nz,c in (*region,*common):
                    result=[]
                    for x,y in zip(poly,poly[1:]+poly[:1]):
                        dx=nx*x[0]+ny*x[1]+nz*x[2]+c-1e-5;dy=nx*y[0]+ny*y[1]+nz*y[2]+c-1e-5
                        if dx>=0:result.append(x)
                        if (dx<0)!=(dy<0):
                            t=dx/(dx-dy);result.append(tuple(x[k]+t*(y[k]-x[k]) for k in range(3)))
                    poly=result
                    if not poly:break
                area=0.
                for i in range(1,len(poly)-1):
                    ab=tuple(poly[i][k]-poly[0][k] for k in range(3));ac=tuple(poly[i+1][k]-poly[0][k] for k in range(3))
                    area+=math.hypot(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])*.5
                if area>1e-7:return dict(mesh_name=mesh.name,triangle_index=at//18,strict_interior_surface_mm2=area)
    return None


def finish(meshes,front_candidate,cooling_meshes,cooling_meta,meta):
    """Resolve physical cover state before final anchors/aux/lighting indices."""
    if front_candidate is None or not meta:return meshes,meta,cooling_meta
    result=deepcopy(meta);parts=cooling_meta.get('parts',()) if isinstance(cooling_meta,dict) else ()
    sources=[]
    for row in parts:
        if not isinstance(row,dict) or row.get('kind')!='radiator' or row.get('mount')!='front':continue
        actual=[m for m in cooling_meshes if m.part_id==row.get('id') and m.vertices]
        if not actual:continue
        low=tuple(min(min(m.vertices[k::6])+m.position[k] for m in actual) for k in range(3))
        high=tuple(max(max(m.vertices[k::6])+m.position[k] for m in actual) for k in range(3))
        # The positive-front mounting metadata and actual lower endpoint both
        # have to exist. A requested/rejected model or a top radiator is not
        # evidence that the removable front plate was taken off.
        if low[1]<meta['roof_world_y_mm']-1e-7 and high[2]>meta['split_world_z_bottom_top_mm'][1]:
            sources.append(dict(part_id=row['id'],model_id=row.get('model_id'),bounds_world_mm=dict(min=low,max=high)))
    if sources:
        removed=_part('front');removed.update(assembly_state='removed_reference',
            reason='front_cover_removed_for_radiator_lower_bay',physical_mesh_present=False)
        result.update(assembly_state='front_cover_removed_for_radiator_lower_bay',removed_parts=[removed],
                      removal_basis='actual_built_front_radiator_enters_lower_bay',front_radiators=sources)
        return meshes,result,cooling_meta
    result['parts'].insert(1,_part('front'))
    result.update(assembly_state='both_covers_installed',front_radiators=[])
    reviews=[];withdrawn=set()
    for model in dict.fromkeys(row.get('model_id') for row in parts if isinstance(row,dict) and row.get('kind')=='case_fan' and row.get('mount')=='front'):
        group=[row for row in parts if row.get('kind')=='case_fan' and row.get('mount')=='front' and row.get('model_id')==model]
        ids={row['id'] for row in group};actual=[m for m in cooling_meshes if m.part_id in ids]
        proof=_front_fan_intersection(actual,meta)
        if proof:
            withdrawn.update(ids);reviews.append(dict(model_id=model,mount='front',part_ids=sorted(ids),omitted_count=len(ids),
                reason='case_cover_reference_clearance_unverified',conflicting_parts=[_IDS['front']],
                reference_only_conflict=True,real_product_support_rejected=False,source_url=SOURCE,proof=proof))
    if withdrawn:
        # The caller uses this detached metadata before final auxiliary routes
        # or lighting indices. Withdraw the entire exact source group, not a
        # single leaf/rotor, and do not retain sockets for omitted fan cables.
        cooling_meta=deepcopy(cooling_meta)
        cooling_meta['parts']=[row for row in cooling_meta['parts'] if row.get('id') not in withdrawn]
        cooling_meta['fans']=[row for row in cooling_meta.get('fans',()) if row.get('part_id') not in withdrawn]
        cooling_meta['wire_anchors']=[row for row in cooling_meta.get('wire_anchors',()) if row.get('owner') not in withdrawn]
        cooling_meta.setdefault('rejected',[]).extend(dict(row,kind='case_fan') for row in reviews)
        kept=[m for m in cooling_meshes if m.part_id not in withdrawn]
        cooling_meta.update(mesh_count=len(kept),triangle_count=sum(m.vertex_count//3 for m in kept))
        if not any(row.get('mount')=='front' for row in cooling_meta['parts']):cooling_meta.get('mount_plane_sources',{}).pop('front',None)
        meshes=tuple(m for m in meshes if m.part_id not in withdrawn)
    result['front_fan_reference_clearance_reviews']=reviews
    return tuple((*meshes,front_candidate)),result,cooling_meta
