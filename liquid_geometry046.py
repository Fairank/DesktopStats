"""Original selected loop geometry. Ports stay open; missing parts stay absent.

Coordinates/fasteners/channel repetitions are bounded visual references, never
OEM CAD, manufactured thread teeth, installed hardware or measured water flow.
"""
import math
from liquid_component_runtime046 import envelope
from liquid_pack_schema046 import FACE_NORMALS

LIMITS={'eco':2600,'balanced':5200,'close':9000}

def _env(row):
    # The supplier's L/W/H list does not establish an assembly pose. Fitting
    # reference frames are explicit; never combine its port axes with a
    # differently ordered supplier envelope and make an elbow artificially fat.
    if row['part_kind'] in ('tubing','fitting'):return dict(row['reference_envelope_mm'])
    return envelope(row)

def _body(row):
    full=_env(row);known=row.get('body_dimensions_mm') or {}
    if row['part_kind']=='cpu_block':
        return {k:known.get(k) or full[k]*({'width':.76,'height':1.,'depth':.76}[k]) for k in full}
    return {k:known.get(k) or full[k] for k in full}

def _local(canonical):return canonical[0],canonical[2],canonical[1]

def _vector(v,basis):return tuple(sum(v[k]*basis[k][i] for k in range(3)) for i in range(3))

def port_frames(row,center,basis):
    from assembly_cooling import _add
    dims=_body(row) if row.get('port_position_scope')=='body' else _env(row)
    values=[]
    for port in row['ports']:
        point=_local(tuple(port['position_normalized'][i]*dims[k] for i,k in enumerate(('width','height','depth'))))
        normal=_local(port.get('normal_reference') or FACE_NORMALS[port['face']])
        values.append(dict(port,position=_add(center,_vector(point,basis)),normal=_vector(normal,basis),
            geometry_position_reference=True))
    return values

def _swept_tube(points,radius,segments,inside=False,end_tangents=None):
    """Shared rings and transported frames, so a smooth elbow has no cracks."""
    from assembly_cooling import _sub,_unit,_basis,_dot,_mul,_add
    rings=[];prior=None
    for i,point in enumerate(points):
        tangent=_unit(end_tangents[0] if end_tangents and i==0 else end_tangents[1] if end_tangents and i==len(points)-1
                      else _sub(points[min(i+1,len(points)-1)],points[max(0,i-1)]))
        if prior is None:u=_basis(tangent,(1.,0.,0.))[0]
        else:u=_unit(_sub(prior,_mul(tangent,_dot(prior,tangent))),_basis(tangent)[0])
        from assembly_cooling import _cross
        v=_cross(tangent,u);prior=u;circle=[]
        for j in range(segments):
            a=j*math.tau/segments;n=_add(_mul(u,math.cos(a)),_mul(v,math.sin(a)))
            circle.append((_add(point,_mul(n,radius)),_mul(n,-1 if inside else 1)))
        rings.append(circle)
    out=[]
    for first,last in zip(rings,rings[1:]):
        for j in range(segments):
            k=(j+1)%segments;a,b,c,d=first[j],first[k],last[k],last[j]
            order=(a,c,b,a,d,c) if inside else (a,b,c,a,c,d)
            for point,normal in order:out.extend((*point,*normal))
    return tuple(out)


def _hollow_collar(outer,inner_back,inner_mouth,length,segments):
    from assembly_geometry import _quad
    out=[]
    for i in range(segments):
        a=i*math.tau/segments;b=(i+1)*math.tau/segments
        p=lambda r,z,t:(math.cos(t)*r,math.sin(t)*r,z)
        z=length/2
        _quad(out,p(outer,-z,a),p(outer,-z,b),p(outer,z,b),p(outer,z,a))
        _quad(out,p(inner_back,-z,b),p(inner_back,-z,a),p(inner_mouth,z,a),p(inner_mouth,z,b))
        _quad(out,p(inner_mouth,z,a),p(outer,z,a),p(outer,z,b),p(inner_mouth,z,b))
        _quad(out,p(inner_back,-z,b),p(outer,-z,b),p(outer,-z,a),p(inner_back,-z,a))
    return tuple(out)


def _fitting(builder,row,center,basis,part):
    from assembly_cooling import _basis,_add,_mul,_dot,_sub,_tube,_curve
    from assembly_geometry import ring
    from assembly_detail import perforated_plate
    body=_env(row);w,h,d=body['width'],body['height'],body['depth'];radius=min(w,d)*.48
    ports=port_frames(row,center,basis);features=set(row['geometry_features']);family=row['geometry_family']
    axis=basis[2];color=row.get('body_color','#89979b')
    flow=min(radius*.62,(row.get('tube_inner_mm') or min(10.,radius*1.1))/2)
    if row['form']=='plug':
        builder.put('loop-closed-port-plug',ring(radius,0,h*.65,builder.segments),color,center,basis,part=part)
        if 'slotted_cap' in features:
            builder.box('loop-plug-driver-slot',(w*.55,max(.7,d*.04),.4),'#25353c',_add(center,_mul(axis,h*.325+.1)),basis,part=part)
        return ports
    if row['form']=='drain':
        # Source-observed barrel, two female necks and broad side lever. Only
        # the exterior is represented; the ball/valve state is not simulated.
        barrel=min(d*.47,w*.35);neck=barrel*.88;length=h*.18
        builder.put('loop-valve-barrel',ring(barrel,flow,h*.72,builder.segments),color,center,basis,part=part)
        for port in ports:
            axes=_basis(port['normal'],basis[0])
            cuff=_add(port['position'],_mul(port['normal'],-length/2))
            builder.put('loop-valve-female-shoulders',_hollow_collar(neck,flow,flow+.10,length,builder.segments),
                color,cuff,axes,part=part)
            builder.put('loop-valve-neck-ring-seams',ring(neck+.08,neck-.35,.42,builder.segments),'#52616a',
                _add(cuff,_mul(port['normal'],-length*.24)),axes,part=part)
        normal=_mul(basis[0],-1);stem=max(2.5,(w/2-barrel)*.42)
        stem_center=_add(center,_mul(normal,barrel+stem/2-.25))
        builder.put('loop-valve-side-control-stem',ring(min(3.,d*.13),0,stem,builder.segments),'#52616a',
            stem_center,_basis(normal,axis),part=part)
        # Lever lies beside the through-flow axis; it cannot become a false
        # cap over a female throat. Dimensions/pose remain original references.
        paddle=max(2.,w*.065);lever_center=_add(center,_mul(normal,barrel+stem+paddle/2-.25))
        builder.box('loop-valve-lever-paddle',(paddle,d*.37,h*.77),color,lever_center,basis,part=part,bevel=True)
        return ports
    angled=row.get('fitting_angle_deg',0)>0 and len(ports)==2
    def collar_length(port):
        tube_end=port.get('tube_type') in ('soft','hard')
        value=h*(.27 if angled and tube_end else .30 if tube_end else .20)
        if angled and not tube_end:
            value=min(value,abs(_dot(_sub(port['position'],center),port['normal']))*.28)
        return max(2.,value)
    if angled:
        a,b=ports
        first=_add(a['position'],_mul(a['normal'],-collar_length(a)))
        last=_add(b['position'],_mul(b['normal'],-collar_length(b)))
        # The port centers are already half-extents from the elbow corner.
        # A handle based on the full envelope doubles the reach, folds the
        # centerline and inverts the inner sweep. Use the endpoint span.
        reach=math.dist(first,last)*.36
        points=_curve((first,_add(first,_mul(a['normal'],-reach)),
            _add(last,_mul(b['normal'],-reach)),last),{'eco':5,'balanced':8,'close':12}[builder.level])
        segments={'eco':8,'balanced':12,'close':16}[builder.level]
        tangents=(_mul(a['normal'],-1),b['normal'])
        vertices=_swept_tube(points,min(radius*.76,flow+.85),segments,end_tangents=tangents)
        builder.put('loop-source-shaped-elbow-body',vertices,color,part=part)
        builder.put('loop-elbow-continuous-inner-channel',_swept_tube(points,min(flow,radius*.65),segments,True,end_tangents=tangents),
            '#344950',part=part)
    else:
        smooth='smooth' in family or row['form']=='drain'
        builder.put('loop-open-fitting-middle-sleeve',ring(radius*(.98 if smooth else .94),flow,h*.72,builder.segments),
            color,_add(center,_mul(axis,h*.08)),basis,part=part)
        if 'hex' in family:
            poly=tuple((math.cos(i*math.tau/6)*radius,math.sin(i*math.tau/6)*radius) for i in range(6))
            builder.put('loop-factory-hex-wrench-body',perforated_plate(poly,[(0,0,flow)],h*.38,segments=12),color,center,basis,part=part)
    for port in ports:
        normal=port['normal'];axes=_basis(normal,basis[0]);tube_end=port.get('tube_type') in ('soft','hard')
        length=collar_length(port)
        # One broad compression sleeve and a short narrow male tail, rather
        # than two equal flanges joined by an artificial spool-like waist.
        outer=radius if tube_end else max(flow+.6,radius*.64)
        od=port.get('tube_outer_mm') or row.get('tube_outer_mm')
        mouth=min(outer-.6,od/2+.10) if tube_end and od else min(outer-.6,flow)
        cuff=_add(port['position'],_mul(normal,-length/2))
        builder.put('loop-open-end-collars',_hollow_collar(outer,flow,mouth,length,builder.segments),color,cuff,axes,part=part)
        gripped=tube_end and ('knurl' in family or 'diamond_knurl' in features or 'axial_grip_flutes' in features)
        if gripped:
            from liquid_grip046 import grip_strips
            count={'eco':8,'balanced':12,'close':16}[builder.level]
            name='loop-reference-crossed-grip-samples' if 'diamond_knurl' in features else 'loop-reference-grip-samples'
            builder.put(name,grip_strips(outer,length,builder.segments,count,'diamond_knurl' in features),'#506168',cuff,axes,part=part)
        if tube_end and 'silicone' in family:
            builder.put('loop-factory-silicone-grip-band',ring(outer,outer-.6,length*.50,builder.segments),'#33474f',cuff,axes,part=part)
        if tube_end and ('compression_ring' in features or 'dual_compression_rings' in features):
            builder.put('loop-separate-compression-ring-seam',ring(outer+.10,outer-.35,.45,builder.segments),'#455b64',
                _add(cuff,_mul(normal,-length*.25)),axes,part=part)
    return ports


def build_component(row,level='balanced',center=(0.,0.,0.),basis=((1.,0.,0.),(0.,0.,-1.),(0.,1.,0.)),part=None):
    """No selected/reference renderer ever imports the full author catalogs."""
    from assembly_cooling import _Builder,_transform,_add
    from assembly_geometry import ring
    from dataclasses import replace
    requested_center,requested_basis=center,basis
    # Build in one canonical frame, then pose exactly once. In particular the
    # reference tube sampler must not choose a new world-up radial phase after
    # a 90-degree elbow has been rotated in the case.
    center=(0.,0.,0.);basis=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))
    part=part or 'cooler:'+row['part_kind'];builder=_Builder(level);body=_body(row);kind=row['part_kind']
    if kind=='fitting':ports=_fitting(builder,row,center,basis,part)
    elif kind=='tubing':
        od=row.get('tube_outer_mm') or body['width'];inner=row.get('tube_inner_mm') or od*.68
        length=min(220.,body['height']);alpha=.32 if row['geometry_family'].startswith(('clear_','frosted_')) else 1.
        builder.put('loop-selected-tube-stock-sample',ring(od/2,inner/2,length,builder.segments),row.get('body_color','#7e9ba3'),center,basis,part=part,alpha=alpha)
        if row['geometry_family']=='carbon_hard_tube':
            from assembly_geometry import _quad
            # Finite crossed albedo strips suggest the observed weave. They
            # are not a measured strand count or a copied bitmap texture.
            for sign in (-1,1):
                weave=[]
                for band in range(6):
                    for step in range(10):
                        a0=band*math.tau/6+sign*step*.20;a1=band*math.tau/6+sign*(step+1)*.20
                        z0=-length/2+length*step/10;z1=-length/2+length*(step+1)/10
                        point=lambda a,z:((od/2+.015)*math.cos(a),(od/2+.015)*math.sin(a),z)
                        _quad(weave,point(a0-.035,z0),point(a0+.035,z0),point(a1+.035,z1),point(a1-.035,z1))
                builder.put('loop-reference-carbon-weave-strips',tuple(weave),'#39454a' if sign==1 else '#566064',center,basis,part=part)
        ports=[]
    else:
        from liquid_block_geometry046 import build_body
        ports=build_body(builder,row,center,basis,part,body,port_frames(row,center,basis))
    meshes=builder.finish();triangles=sum(m.vertex_count for m in meshes)//3
    if triangles>LIMITS[builder.level]:raise ValueError('Independent loop component exceeds its detail budget')
    meshes=tuple(replace(m,vertices=_transform(m.vertices,requested_center,requested_basis)) for m in meshes)
    ports=[dict(p,position=_add(requested_center,_vector(p['position'],requested_basis)),normal=_vector(p['normal'],requested_basis)) for p in ports]
    return meshes,dict(id=part,model_id=row['id'],label=row['label'],kind=row['part_kind'],
        dimensions_mm=row['dimensions_mm'],reference_envelope_mm=row['reference_envelope_mm'],
        body_dimensions_mm=row.get('body_dimensions_mm'),dimensions_verified=row['dimensions_verified'],
        geometry_family=row['geometry_family'],ports=ports,triangle_count=triangles,
        telemetry_bound=False,fit_verified=False,coordinates_verified=False,sources=row['sources'])
