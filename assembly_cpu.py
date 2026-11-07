"""Original CPU package reference meshes, shared by SKUs using one package.

Pure construction only. Catalog dimensions are retained separately from reference
thicknesses/contact samples; this is neither a socket map nor manufacturing CAD.
Original code/art: PolyForm Noncommercial 1.0.0; product names retain their owners.
"""
import copy
import math
import re


# The same normalized polygons are exported in HardwareCpuPackages.js. All styles
# use these contours; model text never selects a different physical package.
PACKAGE_SHAPES = {
    'intel_lga115x_1200': dict(vendor='intel',size=(37.5,37.5),lid='square',contacts='lga'),
    'intel_lga1700_1851': dict(vendor='intel',size=(37.5,45.),lid='rect',contacts='lga'),
    'intel_lga2011_2066': dict(vendor='intel',size=(45.,52.5),lid='hedt',contacts='lga'),
    'amd_am4': dict(vendor='amd',size=(40.,40.),lid='square',contacts='pga'),
    'amd_am5': dict(vendor='amd',size=(40.,40.),lid='am5',contacts='lga'),
    'amd_tr4_family': dict(vendor='amd',size=(58.5,75.4),lid='carrier',contacts='lga'),
    'amd_str5': dict(vendor='amd',size=(58.5,75.4),lid='carrier',contacts='lga'),
}


def _chamfer(x0,y0,x1,y1,c):
    return ((x0+c,y0),(x1-c,y0),(x1,y0+c),(x1,y1-c),
            (x1-c,y1),(x0+c,y1),(x0,y1-c),(x0,y0+c))


def package_geometry(identity):
    """Return detached normalized front contours, without SKU or style input."""
    profile=PACKAGE_SHAPES.get(identity)
    if profile is None:return {}
    substrate=_chamfer(0.,0.,1.,1.,.025)
    if profile['lid']=='am5':
        # Two true, concave cutouts on each IHS edge. Their proportions are a
        # source-observed illustration, not measured package machining data.
        lid=((.11,.08),(.24,.08),(.24,.18),(.34,.18),(.34,.08),(.66,.08),(.66,.18),(.76,.18),(.76,.08),(.89,.08),
             (.92,.11),(.92,.24),(.82,.24),(.82,.34),(.92,.34),(.92,.66),(.82,.66),(.82,.76),(.92,.76),(.92,.89),
             (.89,.92),(.76,.92),(.76,.82),(.66,.82),(.66,.92),(.34,.92),(.34,.82),(.24,.82),(.24,.92),(.11,.92),
             (.08,.89),(.08,.76),(.18,.76),(.18,.66),(.08,.66),(.08,.34),(.18,.34),(.18,.24),(.08,.24),(.08,.11))
    else:
        x=.085 if profile['lid'] in ('rect','hedt','carrier') else .10
        y=.075 if profile['lid'] in ('rect','hedt') else .08 if profile['lid']=='carrier' else .10
        lid=_chamfer(x,y,1-x,1-y,.045)
    return dict(id=identity,substrate=substrate,lid=lid,carrier=profile['lid']=='carrier',
                vendor=profile['vendor'],contacts=profile['contacts'],reference_size=profile['size'])


def _valid_vector(value,default):
    if not isinstance(value,(tuple,list)) or len(value)!=3:return default
    return tuple(float(v) for v in value) if all(type(v) in (int,float) and math.isfinite(v) for v in value) else default


def _unit(value,default):
    length=math.sqrt(sum(v*v for v in value))
    return tuple(v/length for v in value) if length>1e-9 else default


def _cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])


def _label(value):
    return value if isinstance(value,str) and re.fullmatch(r'[A-Z0-9][A-Z0-9 -]{0,27}',value) else ''


def package_style(identity):
    return 'am5' if identity=='amd_am5' else 'lga_rect' if identity in ('intel_lga1700_1851','intel_lga2011_2066','amd_tr4_family','amd_str5') else 'chip'


def build_cpu_meshes(cpu,position=(0.,0.,0.),normal=(-1.,0.,0.),up=(0.,1.,0.),level='balanced'):
    """Return (replacement CPU meshes, detached metadata), in caller's frame.

    position is the IHS center, matching the existing scene CPU anchor. Unknown
    package IDs return no meshes so the caller can retain its neutral fallback.
    Pins/lands are bounded density samples, never an inferred electrical pin map.
    """
    from assembly_geometry import Mesh,color,extrude,model_mark,ring
    cpu=cpu if isinstance(cpu,dict) else {}
    appearance=cpu.get('appearance') if isinstance(cpu.get('appearance'),dict) else cpu
    descriptor=cpu.get('cpu_package',appearance.get('cpu_package',{}))
    descriptor=descriptor if isinstance(descriptor,dict) else {}
    identity=descriptor.get('id');shape=package_geometry(identity)
    if not shape:return (),dict(available=False,reason='unknown_package',new_pollers=0)
    model_id=descriptor.get('model_id')
    if (not isinstance(model_id,str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}',model_id)
            or appearance.get('id')!=model_id or appearance.get('kind')!='cpu' or appearance.get('confidence')!='model'
            or appearance.get('vendor')!=shape['vendor'] or descriptor.get('vendor')!=shape['vendor']
            or appearance.get('style')!=package_style(identity)):
        return (),dict(available=False,reason='inconsistent_model_identity',new_pollers=0)
    n=_unit(_valid_vector(normal,(-1.,0.,0.)),(-1.,0.,0.))
    v=_unit(_valid_vector(up,(0.,1.,0.)),(0.,1.,0.));u=_cross(v,n)
    if sum(x*x for x in u)<1e-9:
        v=(0.,0.,1.) if abs(n[2])<.9 else (0.,1.,0.);u=_cross(v,n)
    u=_unit(u,(0.,0.,1.));v=_unit(_cross(n,u),(0.,1.,0.));p=_valid_vector(position,(0.,0.,0.))
    def dim(name,fallback):
        value=descriptor.get(name)
        return float(value) if type(value) in (int,float) and math.isfinite(value) and 20<=value<=90 else fallback
    width=dim('width_mm',shape['reference_size'][0]);length=dim('length_mm',shape['reference_size'][1])
    substrate=descriptor.get('substrate_mm')
    thickness_verified=type(substrate) in (int,float) and math.isfinite(substrate) and .3<=substrate<=4
    substrate=float(substrate) if thickness_verified else 1.4
    ihs_depth=2.4 # Reference depth: a catalog package outline is not a stack-up drawing.
    meshes=[]
    def transformed(vertices,offset=0.):
        out=[]
        for i in range(0,len(vertices),6):
            x,y,z,nx,ny,nz=vertices[i:i+6];z+=offset
            out.extend(tuple(u[j]*x+v[j]*y+n[j]*z for j in range(3)))
            out.extend(tuple(u[j]*nx+v[j]*ny+n[j]*nz for j in range(3)))
        return tuple(out)
    def add(name,vertices,tint,offset=0.):
        if vertices:meshes.append(Mesh(name,transformed(vertices,offset),color(tint),position=p,component='cpu',part_id='cpu:0'))
    def polygon(points):return tuple(((x-.5)*width,(.5-y)*length) for x,y in reversed(points))
    add('cpu-substrate',extrude(polygon(shape['substrate']),substrate),'#426b60',-ihs_depth/2-substrate/2)
    from assembly_detail import bevel_extrude
    add('cpu-lid',bevel_extrude(polygon(shape['lid']),ihs_depth,.34) if level!='eco' else extrude(polygon(shape['lid']),ihs_depth),'#cbd6dd')
    if shape['carrier']:
        # Removable carrier family appearance; no unverified retention screws.
        outer=_chamfer(-width/2-2,-length/2-2,width/2+2,length/2+2,2)
        inner=_chamfer(-width/2+.3,-length/2+.3,width/2-.3,length/2-.3,1)
        from assembly_detail import perforated_plate
        add('cpu-carrier-reference',perforated_plate(outer,[inner],1.2),'#d88943',-2.6)
    # Contacts live underneath the substrate, never as side-facing chip legs.
    # An evenly sampled density field intentionally makes no pin-position claim.
    samples={'eco':7,'balanced':11,'close':15}.get(level,11);contact_vertices=[]
    pin=shape['contacts']=='pga';radius=.23 if pin else .35;depth=2. if pin else .10
    contact=ring(radius,0.,depth,6 if level=='eco' else 8)
    for row in range(samples):
        for col in range(samples):
            if samples//2-1<=row<=samples//2+1 and samples//2-1<=col<=samples//2+1:continue
            x=(col/(samples-1)-.5)*width*.84;y=(row/(samples-1)-.5)*length*.84
            for i in range(0,len(contact),6):
                contact_vertices.extend((contact[i]+x,contact[i+1]+y,contact[i+2],*contact[i+3:i+6]))
    add('cpu-pins-reference' if pin else 'cpu-lands-reference',tuple(contact_vertices),'#c4a768',-ihs_depth/2-substrate-depth/2)
    label=_label(descriptor.get('label_ascii',''));mark_lines=[]
    if label:
        words=label.split();brand='INTEL' if shape['vendor']=='intel' else 'AMD';model=words[-1]
        # Original bounded grid type, not a manufacturer's laser/logo artwork.
        for text,offset in ((brand,length*.09),(model,-length*.06)):
            pixel=min(.40,width*.68/max(4,len(text)*4))
            vertices=model_mark(text,pixel)
            if not vertices:continue
            shifted=tuple(value+(offset if i%6==1 else 0) for i,value in enumerate(vertices))
            add('cpu-model-mark',shifted,'#5c6b75',ihs_depth/2+.04);mark_lines.append(text)
    dimensions_verified=all(type(descriptor.get(k)) in (int,float) and math.isfinite(descriptor[k]) and 20<=descriptor[k]<=90 for k in ('width_mm','length_mm')) and descriptor.get('dimensions_status') in ('verified','source_verified','primary_verified')
    pin_count=descriptor.get('pin_count')
    pin_count=pin_count if type(pin_count) is int and 1<=pin_count<=10000 else None
    meta=dict(available=True,package_id=identity,width_mm=width,length_mm=length,dimensions_verified=dimensions_verified,
              substrate_thickness_verified=thickness_verified,ihs_depth_verified=False,geometry_is_reference=True,
              internal_layout_verified=False,physical_pin_count=pin_count,rendered_contact_samples=len(contact_vertices)//len(contact),
              contacts=shape['contacts'],contact_layout='schematic_density_samples_not_pin_map',label_ascii=label,model_mark_lines=mark_lines,
              source_urls=copy.deepcopy(descriptor.get('source_urls',[])),new_pollers=0,cooler_inferred=False)
    return tuple(meshes),meta
