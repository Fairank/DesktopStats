"""Fixed PSU apertures in eighteen exact, source-observed rear walls.

Only a chassis layout descriptor is accepted. No selected hardware is read:
the cutout always uses the same nominal ATX interface and the fixed source
reference datums. Other rear I/O/PCIe openings and projecting flanges remain
unmodeled; this is an original drawing reference, never manufacturing CAD.
"""
import math
import re

CASE_IDS=(
    'lian-li-o11d-evo-rgb','nzxt-h6-flow-2023','corsair-6500x','hyte-y60','asus-tuf-gt502',
    'phanteks-nv7','antec-c8-argb','msi-mag-pano-100r-pz','lian-li-o11-vision',
    'montech-king-95',
    'nzxt-h9-flow-2023','jonsbo-tk2-black','deepcool-ch780','corsair-2500x',
    'lian-li-o11-vision-compact','be-quiet-light-base-600-lx','havn-hs-420','hyte-y70',
)
ATX_REFERENCE_MM=(150.,86.,160.)
MAX_TRIANGLES=128
_HTTPS=re.compile(r'https://[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?(?::[0-9]{1,5})?(?:[/?#][^\s<>]*)?\Z')


def _finite(value):return type(value) in (int,float) and math.isfinite(value)


def _vector(value,length=3):
    return (isinstance(value,(tuple,list)) and len(value)==length
        and all(_finite(v) and abs(v)<=2000. for v in value))


def _source(value):return isinstance(value,str) and len(value)<=2048 and _HTTPS.fullmatch(value) is not None


def _area(poly):
    return sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(poly,(*poly[1:],poly[0])))/2


def _validated(case,dimensions,layout,tone):
    if not (isinstance(case,dict) and isinstance(case.get('id'),str) and case['id'] in CASE_IDS
            and _vector(dimensions) and 60<=dimensions[0]<=800 and 60<=dimensions[1]<=900
            and 150<=dimensions[2]<=900 and isinstance(layout,dict)
            and layout.get('case_id')==case['id'] and _source(layout.get('source'))
            and _vector(tone,4) and all(0.<=c<=1. for c in tone)):
        return None
    sources=layout.get('source_urls',(layout['source'],))
    if not isinstance(sources,(tuple,list)) or not 1<=len(sources)<=8 or not all(_source(s) for s in sources):return None
    psu=layout.get('psu')
    if not isinstance(psu,dict):return None
    basis=psu.get('basis')
    if not isinstance(basis,(tuple,list)) or len(basis)!=3 or not all(_vector(row) for row in basis):return None
    if any(abs(sum(basis[i][k]*basis[j][k] for k in range(3))-(1. if i==j else 0.))>1.e-8
           for i in range(3) for j in range(3)):return None
    determinant=(basis[0][0]*(basis[1][1]*basis[2][2]-basis[1][2]*basis[2][1])
        -basis[0][1]*(basis[1][0]*basis[2][2]-basis[1][2]*basis[2][0])
        +basis[0][2]*(basis[1][0]*basis[2][1]-basis[1][1]*basis[2][0]))
    if abs(determinant-1.)>1.e-8 or any(abs(basis[2][k]-(1. if k==2 else 0.))>1.e-8 for k in range(3)):return None
    # The host uses the same fixed face-to-real-envelope convention. This
    # helper substitutes only the nominal ATX dimensions, never the selection.
    world=tuple(sum(abs(basis[k][axis])*ATX_REFERENCE_MM[k] for k in range(3)) for axis in range(3))
    floor,ceiling=psu.get('floor_y_mm'),psu.get('ceiling_y_mm')
    bounded=lambda n:_finite(n) and abs(n)<=2000.
    if bounded(floor) and ceiling is None:cy=float(floor)+world[1]/2
    elif bounded(ceiling) and floor is None:cy=float(ceiling)-world[1]/2
    else:return None
    cx=psu.get('center_x_mm')
    if cx is None:
        boundary=psu.get('boundary_x_mm')
        if psu.get('align_x')!='right' or not bounded(boundary):return None
        cx=float(boundary)-world[0]/2
    elif not bounded(cx):return None
    # A fixed rear or front datum must exist even though the wall cutout has
    # no dependence on PSU length. Wrong-facing/front-exhaust frames fail shut.
    rear,front=psu.get('rear_z_mm'),psu.get('front_z_mm')
    if bounded(rear) and front is None:cz=float(rear)+ATX_REFERENCE_MM[2]/2
    elif bounded(front) and rear is None:cz=float(front)-ATX_REFERENCE_MM[2]/2
    else:return None
    if abs(cx)>dimensions[0] or abs(cy)>dimensions[1]:return None
    return tuple(tuple(float(v) for v in row) for row in basis),(float(cx),cy,cz),world,tuple(sources)


def build(case,dimensions,layout,tone):
    """Return ``(None,{})`` or one pierced replacement for the old case-back.

    There is no fallback for an unknown case, missing source or malformed
    mounting frame. The caller retains the original wall in those situations.
    """
    validated=_validated(case,dimensions,layout,tone)
    if validated is None:return None,{}
    basis,center,world,sources=validated;w,h,d=map(float,dimensions)
    from assembly_detail import perforated_plate,_clip
    from assembly_geometry import Mesh
    # Only Light Base's documented20mm stand changes the body datum. Other
    # sixteen existing walls retain the exact old H-16/Y8 arithmetic.
    light_base=case['id']=='be-quiet-light-base-600-lx'
    body_height=h-20. if light_base else h-16.
    body_y=10. if light_base else 8.
    outer=((-w/2,-body_height/2),(w/2,-body_height/2),(w/2,body_height/2),(-w/2,body_height/2))
    hole=tuple((center[0]+basis[0][0]*x+basis[1][0]*y,
                center[1]-body_y+basis[0][1]*x+basis[1][1]*y)
               for x,y in ((-75.,-43.),(75.,-43.),(75.,43.),(-75.,43.)))
    if _area(hole)<0:hole=tuple(reversed(hole))
    clipped=hole
    for a,b in zip(outer,(*outer[1:],outer[0])):clipped=_clip(clipped,a,b,True)
    if len(clipped)<3 or abs(_area(clipped))<=1.e-8:return None,{}
    # Do not silently replace the complete wall with an empty object.
    if abs(_area(clipped))>=w*body_height-1.e-8:return None,{}
    vertices=perforated_plate(outer,[hole],2.,clip_walls=True)
    if not vertices or len(vertices)%18 or len(vertices)//18>MAX_TRIANGLES:
        raise ValueError('Rear-wall reference exceeded its fixed material budget')
    mesh=Mesh('case-back',tuple(vertices),tuple(tone),(0.,body_y,-d/2+1.),'case',part_id='case:rear-wall')
    original_world=tuple((x,y+body_y) for x,y in hole)
    clipped_world=tuple((x,y+body_y) for x,y in clipped)
    edge_open=any(not (-w/2<x<w/2 and body_y-body_height/2<y<body_y+body_height/2)
        for x,y in original_world)
    part=dict(id='case:rear-wall',label='后部箱壁',kind='case_structure',component='case',model_id=case['id'],
        assembly_state='installed',geometry_status='official_layout_reference',source_url=layout['source'],
        source_urls=sources,dimensions_verified=False,positions_verified=False,
        mounting_hole_positions_verified=False,manufacturing_cad=False)
    meta=dict(case_id=case['id'],source=layout['source'],source_urls=sources,parts=[part],
        replaces_generic_mesh_name='case-back',reference_only=True,dimensions_verified=False,
        positions_verified=False,mounting_hole_positions_verified=False,manufacturing_cad=False,
        thickness_mm=2.,thickness_verified=False,selected_hardware_read=False,
        atx_reference_dimensions_mm=ATX_REFERENCE_MM,reference_psu_center_mm=center,
        reference_psu_basis=basis,reference_psu_world_dimensions_mm=world,
        opening_polygon_xy_mm=original_world,material_cut_polygon_xy_mm=clipped_world,
        opening_scope='fixed_psu_reference_interface_only',edge_open_reference=edge_open,
        clipping_method='actual_perforated_plate_with_clipped_boundary_walls',
        pcie_openings_modeled=False,motherboard_io_openings_modeled=False,
        projecting_rear_flange_modeled=False,source_15mm_bracket_projection_modeled=False,
        maximum_triangles=MAX_TRIANGLES,new_clocks=0,new_pollers=0)
    if light_base:
        meta.update(source_body_height_mm=body_height,source_feet_height_mm=20.,body_center_y_mm=body_y,
            source_body_height_basis='catalog_outer_height_less_documented_20mm_feet')
    return mesh,meta
