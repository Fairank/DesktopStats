"""Lazy exact-case cover factories; no guessing from brand or case size."""
from importlib import import_module
from copy import deepcopy
import math

_GROUPS={
    'assembly_c700m_case055':('cooler-master-cosmos-c700m',),
    'assembly_rear_bay_group_a052':('lian-li-o11d-evo-rgb','nzxt-h6-flow-2023',
        'corsair-6500x','hyte-y60','asus-tuf-gt502'),
    'assembly_rear_bay_group_b052':('phanteks-nv7','antec-c8-argb','msi-mag-pano-100r-pz','lian-li-o11-vision',
        'montech-king-95'),
    'assembly_rear_bay_group_c052':('nzxt-h9-flow-2023','jonsbo-tk2-black','deepcool-ch780','corsair-2500x',
        'lian-li-o11-vision-compact','be-quiet-light-base-600-lx','havn-hs-420'),
    'assembly_y70_case052':('hyte-y70',),
    'assembly_cowboy_case052':('geometric-future-model-8-cowboy',),
    'assembly_phanteks_case052':('phanteks-nv5','phanteks-evolv-x2',),
    'assembly_torrent_shroud052':('fractal-torrent-tg',),
    'assembly_shroud_fractal052':('fractal-north-mesh','fractal-meshify-2-light-tg',
                                 'fractal-define-7-compact-solid'),
    'assembly_shroud_nzxt_lianli052':('nzxt-h5-flow-2024','nzxt-h7-flow-2024','lian-li-lancool-iii'),
    'assembly_shroud_other052':('cooler-master-haf-700-evo','be-quiet-shadow-base-800-fx',
                               'asus-tuf-gt302-argb','phanteks-eclipse-g500a-drgb',
                               'inwin-dubili','corsair-frame-4000d'),
}
_BY_ID={identity:name for name,identities in _GROUPS.items() for identity in identities}


def _factory(case):
    identity=case.get('id') if isinstance(case,dict) else None
    name=_BY_ID.get(identity) if isinstance(identity,str) else None
    return import_module(name) if name else None


def build(case,dimensions,tone):
    factory=_factory(case)
    return factory.build(case,dimensions,tone) if factory else ((),{})


def finish(case,meshes,cooling_meshes,cooling_meta,meta):
    """Resolve whole removable source parts once before final cable/index work."""
    factory=_factory(case)
    complete=getattr(factory,'finish',None) if factory else None
    return complete(meshes,cooling_meshes,cooling_meta,meta) if callable(complete) else (meshes,meta)


def layout_reference(case,dimensions):
    factory=_factory(case)
    describe=getattr(factory,'layout_reference',None) if factory else None
    return describe(case,dimensions) if callable(describe) else {}


def remove_replaced_parts(meshes,metadata):
    """Remove only explicitly replaced generic case bodies, never hardware."""
    names=set()
    for flag,name in (('replaces_case_bottom','case-bottom'),
                      ('replaces_case_feet','case-foot'),
                      ('replaces_rear_chamber_shroud','rear-chamber-shroud')):
        if metadata.get(flag) is True:names.add(name)
    return [mesh for mesh in meshes if not (mesh.component=='case' and mesh.name in names)]


def apply_layout_anchors(anchors,spec,layout):
    """Use source reference planes and the selected PSU's real envelope once."""
    if not layout:return anchors
    result=dict(anchors)
    for source,target in (('radiator_constraints','case_radiator_constraints'),
                          ('air_cooler_constraints','case_air_cooler_constraints'),
                          ('fan_constraints','case_fan_constraints'),
                          ('top_mount_planes_by_fan_size_mm','case_top_radiator_planes_by_size')):
        if isinstance(layout.get(source),dict):result[target]=deepcopy(layout[source])
    planes=layout.get('mount_planes')
    if isinstance(planes,dict):
        result['case_mount_planes']=dict(anchors.get('case_mount_planes',{}))
        result['case_mount_planes'].update(deepcopy(planes))
    placement=layout.get('psu')
    if not isinstance(placement,dict):return result
    from component_catalog import get_component
    selected=(spec.get('auxiliary') or {}).get('psu') or {}
    psu=get_component(selected.get('model_id'))
    if not psu or psu.get('category')!='psu':return result
    dimensions=psu.get('dimensions_mm') or {}
    size=tuple(dimensions.get(k) for k in ('width','height','length'))
    basis=placement.get('basis')
    finite=lambda n:type(n) in (int,float) and math.isfinite(n)
    if (not all(finite(n) and n>0 for n in size) or not isinstance(basis,(tuple,list)) or len(basis)!=3
            or any(not isinstance(row,(tuple,list)) or len(row)!=3 or not all(finite(n) for n in row) for row in basis)):
        return result
    if any(abs(sum(basis[i][k]*basis[j][k] for k in range(3))-(1. if i==j else 0.))>1e-8
           for i in range(3) for j in range(3)):return result
    determinant=(basis[0][0]*(basis[1][1]*basis[2][2]-basis[1][2]*basis[2][1])
                 -basis[0][1]*(basis[1][0]*basis[2][2]-basis[1][2]*basis[2][0])
                 +basis[0][2]*(basis[1][0]*basis[2][1]-basis[1][1]*basis[2][0]))
    if abs(determinant-1.)>1e-8:return result
    world=tuple(sum(abs(basis[k][axis])*size[k] for k in range(3)) for axis in range(3))
    floor=placement.get('floor_y_mm');rear=placement.get('rear_z_mm')
    ceiling=placement.get('ceiling_y_mm');front=placement.get('front_z_mm')
    # A fixed mounting face locates each selected PSU's true envelope. This
    # never rescales a PSU or changes the case skin for the current selection.
    if finite(floor) and ceiling is None:center_y=floor+world[1]/2
    elif finite(ceiling) and floor is None:center_y=ceiling-world[1]/2
    else:return result
    if finite(rear) and front is None:center_z=rear+world[2]/2
    elif finite(front) and rear is None:center_z=front-world[2]/2
    else:return result
    center_x=placement.get('center_x_mm')
    if not finite(center_x):
        boundary=placement.get('boundary_x_mm');align=placement.get('align_x')
        if not finite(boundary) or align not in ('left','right'):return result
        center_x=boundary+(world[0]/2 if align=='left' else -world[0]/2)
    result['psu']=dict(position=(center_x,center_y,center_z),
        basis=tuple(tuple(row) for row in basis),placement_verified=False,
        reference_only=True,model_id=psu['id'],world_dimensions_mm=world)
    return result
