"""Selected retail loop parts, independent identities and honest tube topology."""
from copy import deepcopy
import math
from liquid_component_runtime046 import get_component
from liquid_geometry046 import build_component,_env,_body,_local
from liquid_selection046 import resolve,choose_service_pair,fitting_ends,port_compatibility,tube_compatibility
from liquid_routes046 import route
from liquid_aux_clearance046 import auxiliary_bounds,component_conflicts

_PARTS={'cpu_block_model':'cooler:cpu','pump_model':'cooler:pump','pump_top_model':'cooler:pump-top',
    'reservoir_model':'cooler:reservoir','pump_reservoir_model':'cooler:pump-reservoir'}

def _bounds(meshes):
    groups={}
    for mesh in meshes:
        if mesh.component not in ('gpu','board','cpu','memory'):continue
        key=mesh.component;lo,hi=groups.setdefault(key,([float('inf')]*3,[float('-inf')]*3))
        for i in range(0,len(mesh.vertices),6):
            for axis in range(3):
                value=mesh.vertices[i+axis]+mesh.position[axis]
                lo[axis]=min(lo[axis],value);hi[axis]=max(hi[axis],value)
    return [(tuple(a),tuple(b)) for a,b in groups.values()]+[row['bounds'] for row in auxiliary_bounds(meshes)]

def _overlap(a,b,padding=2.):return all(a[0][i]-padding<b[1][i] and a[1][i]+padding>b[0][i] for i in range(3))

def _box(center,dims):return tuple(center[i]-dims[i]/2 for i in range(3)),tuple(center[i]+dims[i]/2 for i in range(3))

def _cooling_bounds(meshes):
    groups={}
    for mesh in meshes:
        if mesh.component!='cooler' or mesh.part_id.startswith(('cooler:fitting:','cooler:tubing:')):continue
        low,high=groups.setdefault(mesh.part_id,([float('inf')]*3,[float('-inf')]*3))
        for at in range(0,len(mesh.vertices),6):
            for i in range(3):
                value=mesh.vertices[at+i]+mesh.position[i]
                low[i]=min(low[i],value);high[i]=max(high[i],value)
    return [(tuple(low),tuple(high)) for low,high in groups.values()]

def _place(row,dimensions,occupied,floor):
    w,h,d=dimensions;size=_env(row);extent=(size['width'],size['height'],size['depth'])
    # Reserve room for nominal connector projections as well as the body.
    # These are candidate reference poses, never verified mounting brackets.
    for y in (floor+extent[1]/2+3,0.,h*.13):
        if y-extent[1]/2<floor or y+extent[1]/2>h/2-28:continue
        for z in (d*.34,d*.18,-d*.32,0.):
            for x in (-w*.26,0.,w*.26):
                center=(x,y,z);bounds=_box(center,extent)
                if any(bounds[0][i]<(-w/2,-h/2,-d/2)[i]+28 or bounds[1][i]>(w/2,h/2,d/2)[i]-28 for i in (0,2)):continue
                if any(_overlap(bounds,b) for b in occupied):continue
                occupied.append(bounds);return center
    return None

def _attach_pose(fitting,male,target):
    from assembly_cooling import _basis,_mul,_add
    from liquid_pack_schema046 import FACE_NORMALS
    dims=_env(fitting)
    normal=_local(male.get('normal_reference') or FACE_NORMALS[male['face']])
    source_axes=_basis(normal,(1.,0.,0.));target_axes=_basis(_mul(target['normal'],-1),(0.,1.,0.))
    axes=tuple(tuple(sum(target_axes[k][j]*source_axes[k][i] for k in range(3)) for j in range(3)) for i in range(3))
    local=_local(tuple(male['position_normalized'][i]*dims[k] for i,k in enumerate(('width','height','depth'))))
    offset=tuple(sum(local[k]*axes[k][i] for k in range(3)) for i in range(3))
    return _add(target['position'],_mul(offset,-1)),axes

def _merge(builder,meshes):
    for mesh in meshes:builder.put(mesh.name,mesh.vertices,mesh.color,component=mesh.component,part=mesh.part_id)


def _discard_parts(builder,identities):
    """Drop a rejected radiator assembly, including its retained fan anchors."""
    for key in tuple(builder.static):
        if key[3] in identities:del builder.static[key]
    builder.rotors[:]=[m for m in builder.rotors if m.part_id not in identities]
    builder.parts[:]=[p for p in builder.parts if p.get('id') not in identities]
    builder.fans[:]=[p for p in builder.fans if p.get('part_id') not in identities]
    builder.wire_anchors[:]=[p for p in builder.wire_anchors if p.get('owner') not in identities]

def add_selected_loop(builder,cooler,selection,spec,anchors,dimensions,planes,p,basis,mount,base_meshes):
    from assembly_cooling import _radiator,_add,_mul,_unit
    from liquid_geometry046 import _swept_tube
    from liquid_pack_schema046 import FACE_NORMALS
    plan=resolve(selection,spec);issues=deepcopy(plan['issues']);parts={};rows=plan['components'];rad_profile=cooler.get('_radiator_profile')
    def issue(reason,field='',severity='review',**details):issues.append(dict(reason=reason,field=field,severity=severity,**details))
    auxiliary_obstacles=auxiliary_bounds(base_meshes)
    occupied=_bounds(base_meshes);base_obstacles=list(occupied);floor=-dimensions[1]/2+20
    deck=anchors.get('case_floor_deck') or {}
    if deck.get('position'):floor=max(floor,deck['position'][1]+deck.get('thickness_mm',2)/2)
    if rad_profile:
        selected=dict(cooler,_retail_loop_parts=True)
        previous_parts={row['id'] for row in builder.parts}
        if _radiator(builder,selected,mount,dimensions,planes=planes) is None:issue('radiator_exceeds_mount_plane','radiator_model','error')
        else:
            item=builder.parts[-1];ports=item.get('connection_ports',[])
            added={row['id'] for row in builder.parts}-previous_parts
            obstructed=component_conflicts((m for m in builder.finish() if m.part_id in added),auxiliary_obstacles)
            if obstructed:
                _discard_parts(builder,added)
                issue('loop_component_no_reference_clearance','radiator_model',obstructed_by=list(obstructed))
            else:parts['radiator_model']=dict(item,ports=ports)
    else:issue('missing_selected_loop_radiator','radiator_model')
    error_fields={i['field'] for i in issues if i['severity']=='error'}
    order=('cpu_block_model','pump_reservoir_model','reservoir_model','pump_model','pump_top_model')
    for field in order:
        row=rows.get(field)
        if not row or field in error_fields:continue
        if field=='cpu_block_model':center=_add(p,_mul(basis[2],4+_body(row)['height']/2));axes=basis
        else:
            axes=((1.,0.,0.),(0.,0.,-1.),(0.,1.,0.))
            paired=parts.get('pump_model') if field=='pump_top_model' else None
            if paired and rows['pump_model']['form']=='pump_body':
                prior=paired['pose_center'];size=_env(rows['pump_model'])
                center=(prior[0],prior[1]+(size['height']+_env(row)['height'])/2,prior[2])
            elif field=='pump_model' and rows.get('pump_reservoir_model') and row['form']=='pump_body' and parts.get('pump_reservoir_model'):
                parent=parts['pump_reservoir_model'];size=_env(rows['pump_reservoir_model'])
                center=tuple(parent['pose_center'][i]-(size['height']-_env(row)['height'])/2 if i==1 else parent['pose_center'][i] for i in range(3))
            else:center=_place(row,dimensions,occupied,floor)
            if center is None:issue('loop_component_no_reference_clearance',field);continue
        try:meshes,item=build_component(row,builder.level,center,axes,_PARTS[field])
        except ValueError:issue('loop_component_detail_budget',field,'error');continue
        obstructed=component_conflicts(meshes,auxiliary_obstacles)
        if obstructed:
            issue('loop_component_no_reference_clearance',field,obstructed_by=list(obstructed));continue
        _merge(builder,meshes);item['pose_center']=center;item['selection_field']=field
        builder.parts.append(item);parts[field]=item
    # A default connector is a convenience. Per-port overrides retain exact
    # selected identities instead of recoloring one fictional universal part.
    nodes=['cpu_block_model','radiator_model']
    nodes+=['pump_reservoir_model'] if rows.get('pump_reservoir_model') else ['reservoir_model','pump_top_model' if rows.get('pump_top_model') else 'pump_model']
    pairs={};flow_keys=set()
    for field in nodes:
        item=parts.get(field);pair=choose_service_pair(item) if item else ()
        if len(pair)!=2:issue('loop_circulation_ports_missing',field)
        else:
            pairs[field]=pair
            flow_keys.update(field+':'+p['id'] for p in pair)
    fitting=rows.get('fitting_model');tubing=rows.get('tubing_model');endpoints={};attachments=[]
    for field,item in parts.items():
        for port in item.get('ports',[]):
            key=field+':'+port['id'];identity=(selection.get('loop_fittings') or {}).get(key)
            active=key in flow_keys
            # A factory hose barb is already a tube connector, not an unknown
            # G1/4 socket. Keep its documented hose ID; never add a fake thread.
            if active and not identity and port.get('thread') is None and port.get('thread_gender')=='none' and port.get('tube_type')=='soft':
                inner=port.get('tube_inner_mm');actual=tubing.get('tube_inner_mm') if tubing else None
                if not tubing or tubing.get('tube_type')!='soft':issue('tube_type_mismatch',key)
                elif inner is None or actual is None:issue('tube_dimensions_unknown',key)
                elif abs(inner-actual)>.06:issue('tube_diameter_mismatch',key)
                else:endpoints[key]=port
                continue
            chosen=get_component('fitting',identity) if identity else fitting if active else None
            if identity and not chosen:issue('unknown_loop_component',key,'error');continue
            if not chosen:continue
            if active:
                conflicts=tube_compatibility(chosen,tubing)
                if conflicts:
                    for reason in conflicts:issue(reason,key)
                    continue
            # Closure/drain devices may be inspected on a chosen spare port,
            # but are never substituted for a circulation-tube connector.
            males=[p for p in chosen['ports'] if p['thread'] and p['thread_gender']=='male']
            if len(males)!=1 or port.get('thread_gender')!='female' or port.get('thread')!=males[0]['thread']:
                unknown=(port.get('thread') is None or port.get('thread_gender') in (None,'unknown')
                         or not males and any(p.get('thread_gender')=='unknown' for p in chosen['ports']))
                issue('port_thread_or_gender_unknown' if unknown else 'port_thread_or_gender_mismatch',key);continue
            center,axes=_attach_pose(chosen,males[0],port)
            part='cooler:fitting:'+str(len(attachments))
            try:meshes,attached=build_component(chosen,builder.level,center,axes,part)
            except ValueError:issue('loop_component_detail_budget',key,'error');continue
            obstructed=component_conflicts(meshes,auxiliary_obstacles)
            if obstructed:
                issue('loop_component_no_reference_clearance',key,obstructed_by=list(obstructed));continue
            attached.update(attached_port_key=key,selection_field='fitting_model')
            _merge(builder,meshes);builder.parts.append(attached);attachments.append(attached)
            ends=fitting_ends(chosen)
            if ends:
                tube_port=next(pp for pp in attached['ports'] if pp['id']==ends[1]['id'])
                endpoints[key]=tube_port
    routes=[]
    if plan['can_draw_connections'] and not issues and selection.get('loop_tubes_visible',True):
        component_obstacles=_cooling_bounds(builder.finish())
        tube_obstacles=[]
        for i,field in enumerate(nodes):
            following=nodes[(i+1)%len(nodes)]
            a=field+':'+pairs[field][1]['id'];b=following+':'+pairs[following][0]['id']
            if a not in endpoints or b not in endpoints:issue('loop_fitting_endpoint_missing',field);break
            line,reason=route(endpoints[a],endpoints[b],tubing,steps={'eco':8,'balanced':12,'close':18}[builder.level],
                obstacles=(*base_obstacles,*component_obstacles,*tube_obstacles),case_bounds=(tuple(-v/2 for v in dimensions),tuple(v/2 for v in dimensions)),allow_detour=True)
            if reason:issue(reason,field);break
            routes.append(dict(line,from_port=a,to_port=b))
            # At most 24 conservative boxes per earlier route. Treat earlier
            # tubes as occupied volume; never draw two reference hoses through
            # each other merely because they clear the graphics card.
            points=line['points'];step=max(1,math.ceil((len(points)-1)/24));radius=tubing['tube_outer_mm']/2
            for at in range(0,len(points)-1,step):
                chunk=points[at:min(len(points),at+step+1)]
                tube_obstacles.append((tuple(min(p[j] for p in chunk)-radius for j in range(3)),
                                       tuple(max(p[j] for p in chunk)+radius for j in range(3))))
        total=sum(r['length_mm'] for r in routes)
        if tubing.get('length_mm') is not None and total>tubing['length_mm']+.05:issue('tube_stock_length_exceeded','tubing_model')
        if not issues:
            from liquid_clearance046 import self_overlap,route_pair_overlap
            radius=tubing['tube_outer_mm']/2
            if any(self_overlap(line['points'],radius) for line in routes):issue('tube_route_self_overlap','tubing_model')
            if any(route_pair_overlap(a['points'],radius,b['points'],radius)
                   for i,a in enumerate(routes) for b in routes[i+1:]):issue('tube_routes_overlap','tubing_model')
        if not issues:
            from assembly_geometry import ring
            radius=tubing['tube_outer_mm']/2;inner=(tubing.get('tube_inner_mm') or tubing['tube_outer_mm']*.68)/2
            for i,line in enumerate(routes):
                part='cooler:tubing:'+str(i)
                alpha=.30 if tubing['geometry_family'].startswith(('clear_','frosted_')) else 1.
                builder.put('loop-reference-routed-tube',_swept_tube(line['points'],radius,{'eco':6,'balanced':8,'close':10}[builder.level]),
                    '#7e9ba3' if alpha<1 else '#354c56',part=part,alpha=alpha)
                builder.parts.append(dict(id=part,kind='tubing',model_id=tubing['id'],label=tubing['label'],
                    length_mm=line['length_mm'],telemetry_bound=False,fit_verified=False,source_stock_length_mm=tubing.get('length_mm')))
    if issues:routes=[]
    return dict(parts=parts,issues=issues,routes=routes,connected_reference_loop=bool(routes),
        complete_installation_verified=False,new_pollers=0,flow_direction_verified=False,
        tubing_is_static_reference=True,stock_model_id=tubing['id'] if tubing else '',
        hidden_runtime_work=False)
