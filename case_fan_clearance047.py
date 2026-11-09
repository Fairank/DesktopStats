"""One-build occupied-envelope checks for manually selected case fans.

These conservative reference bounds include the full swept rotor volume.
They are not manufacturer mounting coordinates, tolerances or a CAD fit test.
No I/O, hardware sampling, animation work or persistent cache is used.
"""
import math

# Flexible routes are not treated as one huge filled box. Rigid heatpipes,
# hose elbows and fittings remain physical blockers.
_SKIP=('wire','lead','connector','cooler-liquid-tubes','loop-reference-routed-tube')


def _bounds(vertices,position=(0.,0.,0.)):
    return tuple(tuple(fn(vertices[axis::6])+position[axis] for axis in range(3)) for fn in (min,max))


def blockers(meshes,static,rotors,*,gpu_replaced=False):
    """Actual selected solids, independently bounded rather than one big box."""
    result=[]
    retained_gpu={'gpu-pcb','gpu-bracket','gpu-gold-contacts','detail-gpu-separated-edge-contacts',
                  'detail-gpu-pcb-stack-edge','detail-gpu-port-recesses'}
    for mesh in meshes:
        if mesh.component not in ('gpu','cpu','memory','board','psu','storage','expansion'):continue
        if mesh.component=='board' and 'heatsink' not in mesh.name:continue
        if any(token in mesh.name for token in _SKIP):continue
        if gpu_replaced and mesh.component=='gpu' and mesh.name not in retained_gpu and not mesh.name.startswith('gpu-reference-port-'):continue
        if mesh.vertices:result.append((mesh.part_id or mesh.component,mesh.name,_bounds(mesh.vertices,mesh.position)))
    for (name,_tint,component,part),vertices in static.items():
        if any(token in name for token in _SKIP):continue
        if vertices:result.append((part,name,_bounds(vertices)))
    for mesh in rotors:
        if mesh.vertices:result.append((mesh.part_id,mesh.name,_bounds(mesh.vertices,mesh.position)))
    return result


def half_extents(model):
    """Conservative local X(width), Y(size), Z(axis) construction envelope.

    These scalar bounds follow ``assembly_cooling._fan`` without constructing
    or scanning its meshes. Round ears/pads are reference geometry, not CAD.
    The planar rotor bound covers every phase; axial camber is retained.
    """
    size=model['size_mm'];width=model.get('width_mm',size);depth=model['depth_mm']
    radius=size*.465;hub=size*model.get('hub_ratio',.25)*.44
    pitch=model.get('mount_pitch_mm') or {120:105.,140:124.5}.get(size,size*.83)
    axes=model.get('mount_pitch_axes_mm')
    px,py=axes if model.get('mount_pitch_axes_verified') and isinstance(axes,(list,tuple)) and len(axes)==2 else (pitch,pitch)
    hole=(model.get('mount_hole_diameter_mm') or size*.036)/2
    x,y,z=width/2,size/2,depth/2
    if not model.get('frameless'):
        if model.get('frame')=='round':
            ear=max(size*.095,hole)
            x=max(x,size/2,abs(px)/2+ear);y=max(y,size/2,abs(py)/2+ear)
        else:
            # A partial edge hole's old reference wall can reach its circle.
            x=max(x,abs(px)/2+hole);y=max(y,abs(py)/2+hole)
    if model.get('pads'):
        if model.get('pad_style')=='round':
            pad=max(.01,min(size*.08,width/2-px/2-.25,size/2-py/2-.25))
            x=max(x,abs(px)/2+pad);y=max(y,abs(py)/2+pad)
        else:
            x=max(x,abs(min(width*.414,width/2-size*.08))+max(size*.08,hole))
            y=max(y,size*.414+max(size*.08,hole))
        z=max(z,depth/2+.7)
    # Stators are swept tubes around planar endpoints. Parametric blade
    # Bezier control points lie within radius*1.07*2.73/3; outer tip rings
    # remain within radius. Hub/foil acceleration channels are independent.
    radial=max(radius,hub)+size*.012
    leaf_depth=min(depth*.19,4.5)
    camber=radius*(.052 if model.get('family')=='arctic-pressure' else .035)
    rotor_radius=max(radius,hub)
    if model.get('blade_polygons'):
        # The shared polygon contract permits coordinate magnitudes up to4.
        # No catalog currently needs this fallback; bound its full rotation.
        rotor_radius=max(rotor_radius,radius*1.07*math.sqrt(32)/3)
    x=max(x,radial,rotor_radius);y=max(y,radial,rotor_radius)
    z=max(z,depth*.35+size*.012,leaf_depth,leaf_depth/2+camber)
    if model.get('family') in ('noctua-sterrox','noctua-g2') and model.get('blade_geometry_reviewed') and not model.get('foil_profile'):
        x=max(x,radius*.85+.30);y=max(y,radius*.85+.30)
        z=max(z,leaf_depth/2+.54+radius*.035)
    if model.get('rgb'):
        z=max(z,leaf_depth+1.325)
        if model.get('frame_rgb_ring'):
            x=max(x,size*.496);y=max(y,size*.496);z=max(z,depth/2+1.05)
        elif model.get('frame_rgb_outline')=='square':
            x=max(x,width*.477+1.);y=max(y,size*.477+1.)
        elif model.get('frame_rgb_polygon') in (6,12):
            x=max(x,radius+size*.009);y=max(y,radius+size*.009);z=max(z,depth/2+.7+size*.009)
        elif model.get('frame_rgb_sides') or model.get('family') in ('lian-li-sl','lian-li-infinity'):
            x=max(x,width*.49+1.,width*.47+1.)
        if model.get('family')=='lian-li-infinity':z=max(z,leaf_depth+1.8)
    if model.get('family')=='lian-li-p28':x=max(x,width*.485+1.)
    if model.get('fixed_white_hub_window') and model.get('hub_window_face')=='front':z=max(z,leaf_depth+1.2)
    if model.get('hub_display'):
        x=max(x,size*.182);y=max(y,size*.182);z=max(z,depth/2+2.1)
    elif model.get('metal_hub'):z=max(z,leaf_depth+1.3)
    if model.get('directional_grille'):
        x=max(x,radius+size*.008);y=max(y,radius+size*.008);z=max(z,depth/2+1.2+size*.008)
    # Retain the existing reference clearances as floors, rather than adding
    # another3mm beyond already-accounted protrusions on every normal fan.
    return (x+.5,y+.5,max(depth/2+3.,z+.5))


def envelope(model,position,basis):
    half=half_extents(model)
    reach=tuple(sum(abs(basis[k][axis])*half[k] for k in range(3)) for axis in range(3))
    return tuple(tuple(position[axis]+sign*reach[axis] for axis in range(3)) for sign in (-1,1))


def conflicts(bounds,obstacles):
    return sorted({part for part,_name,other in obstacles if all(
        min(bounds[1][axis],other[1][axis])-max(bounds[0][axis],other[0][axis])>.1 for axis in range(3))})
