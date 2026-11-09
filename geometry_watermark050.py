"""Lossless-first, offline FLOAT32 geometry issuance markers.

This is not a signature or DRM. Authenticity belongs to an externally signed
release manifest. No key, registry, filesystem, renderer, timer or collector
is retained here. Requantization, transform baking and remeshing may erase it.
"""
import collections
import hashlib
import hmac
import json
import math
import struct

PROFILE='desktopstats-f32-lsb2-v1'
MAX_BYTES=32*1024*1024
MAX_JSON=8*1024*1024
MAX_NODES=4096
MAX_MESHES=1024
MAX_ACCESSORS=8192
MAX_VERTICES=400000
MAX_GROUP_KEYS=150000
MAX_CARRIERS=200000
MAX_VISITS=4000000
BITS=96
MAX_WORLD_DELTA_MM=.001
MAX_NORMAL_ANGLE_DEG=.1

class WatermarkError(ValueError):
    pass

def _need(ok,message):
    if not ok:raise WatermarkError(message)

def _finite(values):
    return isinstance(values,(list,tuple)) and all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in values)

def _integer(v,low,high):
    return isinstance(v,int) and not isinstance(v,bool) and low<=v<=high

def _pairs(items):
    out={}
    for k,v in items:
        _need(k not in out,'duplicate JSON property');out[k]=v
    return out

def _walk(value,depth=0):
    _need(depth<=64,'JSON nesting limit')
    if isinstance(value,dict):
        for k,v in value.items():
            _need(not(k in ('extensions','extensionsUsed','extensionsRequired') and v),'extensions unsupported')
            _need(k!='uri','external or embedded URI unsupported')
            _walk(v,depth+1)
    elif isinstance(value,list):
        for v in value:_walk(v,depth+1)
    elif isinstance(value,float):_need(math.isfinite(value),'nonfinite JSON')

def _mul(a,b):
    return tuple(sum(a[r*4+k]*b[k*4+c] for k in range(4)) for r in range(4) for c in range(4))

IDENTITY=(1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.)

def _trs(n):
    _need('matrix' not in n and 'skin' not in n and 'weights' not in n,'matrix/skin/morph unsupported')
    t=n.get('translation',[0.,0.,0.]);s=n.get('scale',[1.,1.,1.]);q=n.get('rotation',[0.,0.,0.,1.])
    _need(_finite(t) and len(t)==3 and max(map(abs,t))<=1e6,'invalid node translation')
    _need(_finite(s) and len(s)==3 and all(1e-9<=abs(v)<=1e6 for v in s),'invalid node scale')
    _need(_finite(q) and len(q)==4 and abs(sum(v*v for v in q)-1.)<1e-5,'invalid quaternion')
    x,y,z,w=q
    return ((1-2*(y*y+z*z))*s[0],2*(x*y-z*w)*s[1],2*(x*z+y*w)*s[2],t[0],
        2*(x*y+z*w)*s[0],(1-2*(x*x+z*z))*s[1],2*(y*z-x*w)*s[2],t[1],
        2*(x*z-y*w)*s[0],2*(y*z+x*w)*s[1],(1-2*(x*x+y*y))*s[2],t[2],0.,0.,0.,1.)

def _point(m,p):
    return tuple(sum(m[r*4+c]*p[c] for c in range(3))+m[r*4+3] for r in range(3))

def _normal(a,b,c):
    u=tuple(y-x for x,y in zip(a,b));v=tuple(y-x for x,y in zip(a,c))
    n=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
    length=math.sqrt(sum(v*v for v in n))
    return (tuple(v/length for v in n) if length>1e-24 else None,length)

class _GLB:
    def __init__(self,data):
        _need(isinstance(data,bytes) and 28<=len(data)<=MAX_BYTES,'GLB byte limit/type')
        magic,version,length=struct.unpack_from('<III',data)
        _need((magic,version,length)==(0x46546c67,2,len(data)),'invalid GLB header')
        chunks=[];at=12
        while at<len(data):
            _need(at+8<=len(data),'truncated chunk')
            size,kind=struct.unpack_from('<II',data,at);at+=8
            _need(size%4==0 and at+size<=len(data),'invalid chunk range/alignment')
            chunks.append((kind,data[at:at+size]));at+=size
        _need([k for k,_ in chunks]==[0x4e4f534a,0x004e4942],'unsupported GLB chunks')
        _need(len(chunks[0][1])<=MAX_JSON,'JSON byte limit')
        try:self.doc=json.loads(chunks[0][1],object_pairs_hook=_pairs,parse_constant=lambda _:(_ for _ in ()).throw(WatermarkError('nonfinite JSON')))
        except (ValueError,UnicodeError,RecursionError) as e:raise WatermarkError('invalid GLB JSON') from e
        d=self.doc;_walk(d)
        _need(isinstance(d,dict) and d.get('asset',{}).get('version')=='2.0','glTF2 asset required')
        _need(not any(d.get(k) for k in ('images','textures','skins')),'image/texture/skin unsupported')
        self.bin=chunks[1][1]
        buffers=d.get('buffers');_need(isinstance(buffers,list) and len(buffers)==1,'one embedded buffer required')
        count=buffers[0].get('byteLength');_need(_integer(count,0,len(self.bin)) and len(self.bin)-count<=3,'invalid buffer length')
        self.length=count;self.views=d.get('bufferViews',[]);self.acc=d.get('accessors',[])
        _need(isinstance(self.views,list) and len(self.views)<=MAX_ACCESSORS and isinstance(self.acc,list) and len(self.acc)<=MAX_ACCESSORS,'accessor/view limit')
        ranges=[]
        for v in self.views:
            _need(isinstance(v,dict) and v.get('buffer')==0,'invalid bufferView')
            off=v.get('byteOffset',0);size=v.get('byteLength');stride=v.get('byteStride')
            _need(_integer(off,0,count) and _integer(size,1,count) and off+size<=count and off%4==0,'bufferView range/alignment')
            _need(stride is None or _integer(stride,12,252) and stride%4==0,'unsupported byte stride')
            _need(v.get('target') in (None,34962,34963),'invalid bufferView target')
            ranges.append((off,off+size))
        ordered=sorted(ranges)
        _need(all(a[1]<=b[0] for a,b in zip(ordered,ordered[1:])),'overlapping bufferViews unsupported')
        self.layouts=[]
        for a in self.acc:
            _need(isinstance(a,dict) and not a.get('sparse') and not a.get('normalized',False),'sparse/normalized accessor unsupported')
            vi=a.get('bufferView');_need(_integer(vi,0,len(self.views)-1),'invalid accessor view')
            ct=a.get('componentType');kind=a.get('type');num=a.get('count');offset=a.get('byteOffset',0)
            sizes={5121:1,5123:2,5125:4,5126:4};components={'SCALAR':1,'VEC3':3,'VEC4':4}
            _need(ct in sizes and kind in components and _integer(num,1,MAX_VERTICES),'unsupported accessor format/count')
            size=sizes[ct]*components[kind];v=self.views[vi];stride=v.get('byteStride',size)
            _need(_integer(offset,0,v['byteLength']) and offset%sizes[ct]==0 and stride>=size and offset+(num-1)*stride+size<=v['byteLength'],'accessor bounds/alignment')
            self.layouts.append((v.get('byteOffset',0)+offset,stride,num,size,ct,kind,vi))
        self.nodes=d.get('nodes',[]);meshes=d.get('meshes',[])
        _need(isinstance(self.nodes,list) and 0<len(self.nodes)<=MAX_NODES and isinstance(meshes,list) and 0<len(meshes)<=MAX_MESHES,'node/mesh limit')
        scenes=d.get('scenes',[]);_need(len(scenes)==1 and d.get('scene',0)==0,'one scene required')
        roots=scenes[0].get('nodes',[]);_need(isinstance(roots,list) and roots,'scene roots required')
        self.parents={};self.world={};self.order=[];mesh_nodes={}
        for i,n in enumerate(self.nodes):
            _need(isinstance(n,dict),'invalid node');_trs(n)
            for child in n.get('children',[]):
                _need(_integer(child,0,len(self.nodes)-1) and child not in self.parents and child!=i,'invalid node tree')
                self.parents[child]=i
            if 'mesh' in n:
                mi=n['mesh'];_need(_integer(mi,0,len(meshes)-1) and mi not in mesh_nodes,'mesh instancing unsupported');mesh_nodes[mi]=i
        _need(all(_integer(r,0,len(self.nodes)-1) and r not in self.parents for r in roots),'invalid scene root')
        seen=set();pending=[(r,IDENTITY,0) for r in reversed(roots)]
        while pending:
            i,parent,depth=pending.pop();_need(i not in seen and depth<=64,'node cycle/depth');seen.add(i)
            self.world[i]=_mul(parent,_trs(self.nodes[i]));self.order.append(i)
            _need(all(math.isfinite(v) and abs(v)<=1e9 for v in self.world[i]),'world transform limit')
            pending.extend((child,self.world[i],depth+1) for child in reversed(self.nodes[i].get('children',[])))
        _need(len(seen)==len(self.nodes) and len(mesh_nodes)==len(meshes),'unreachable node/mesh unsupported')
        self.prims=[];self.node_prims=collections.defaultdict(list);roles={};total=0
        def role(index,value):
            _need(_integer(index,0,len(self.acc)-1),'invalid accessor index')
            _need(index not in roles or roles[index]==value,'accessor role alias');roles[index]=value
        for mi,m in enumerate(meshes):
            _need(isinstance(m,dict) and not m.get('weights') and isinstance(m.get('primitives'),list),'invalid mesh')
            for p in m['primitives']:
                _need(len(self.prims)<4096 and not p.get('targets') and p.get('mode',4)==4,'primitive mode/morph unsupported')
                attrs=p.get('attributes',{});_need(set(attrs)=={'POSITION','NORMAL'},'unsupported vertex attributes')
                pi,ni=attrs['POSITION'],attrs['NORMAL'];role(pi,'POSITION');role(ni,'NORMAL')
                pl,nl=self.layouts[pi],self.layouts[ni]
                _need(pl[4:6]==(5126,'VEC3') and nl[4:6]==(5126,'VEC3') and pl[2]==nl[2],'POSITION/NORMAL FLOAT VEC3 required')
                _need(self.views[pl[6]].get('target') in (None,34962) and self.views[nl[6]].get('target') in (None,34962),'invalid attribute target')
                points=[struct.unpack_from('<3f',self.bin,pl[0]+j*pl[1]) for j in range(pl[2])]
                _need(all(math.isfinite(v) and abs(v)<=1e9 for point in points for v in point),'POSITION coordinate limit')
                for bound,operation in (('min',min),('max',max)):
                    values=self.acc[pi].get(bound)
                    _need(_finite(values) and len(values)==3 and all(values[a]==operation(p[a] for p in points) for a in range(3)),'invalid POSITION bounds')
                total+=pl[2];_need(total<=MAX_VERTICES,'total vertex limit')
                if 'indices' in p:
                    ii=p['indices'];role(ii,'INDICES');il=self.layouts[ii]
                    _need(il[4] in (5121,5123,5125) and il[5]=='SCALAR' and il[1]==il[3] and il[2]%3==0,'invalid indices')
                    _need(self.views[il[6]].get('target') in (None,34963),'invalid index target')
                    fmt={5121:'B',5123:'H',5125:'I'}[il[4]]
                    inds=tuple(struct.unpack_from('<'+fmt,self.bin,il[0]+j*il[1])[0] for j in range(il[2]))
                    _need(max(inds)<pl[2],'index out of range')
                else:_need(pl[2]%3==0,'nontriangle vertex count');inds=range(pl[2])
                row=dict(mesh=mi,node=mesh_nodes[mi],position=pi,normal=ni,indices=inds)
                self.node_prims[mesh_nodes[mi]].append(len(self.prims));self.prims.append(row)
                for j in range(nl[2]):
                    normal=struct.unpack_from('<3f',self.bin,nl[0]+j*nl[1])
                    _need(all(math.isfinite(v) for v in normal) and abs(sum(v*v for v in normal)-1.)<.002,'invalid NORMAL')
        _need(isinstance(d.get('animations',[]),list) and len(d.get('animations',[]))<=64,'animation count limit')
        for animation in d.get('animations',[]):
            _need(isinstance(animation,dict) and len(animation.get('samplers',[]))<=4096,'animation limit')
            for sampler in animation.get('samplers',[]):
                for k in ('input','output'):role(sampler.get(k),'ANIMATION')
                a=self.layouts[sampler['input']];_need(a[4:6]==(5126,'SCALAR') and 'byteStride' not in self.views[a[6]],'invalid animation input')
                times=[struct.unpack_from('<f',self.bin,a[0]+j*a[1])[0] for j in range(a[2])]
                _need(all(math.isfinite(v) and v>=0 for v in times) and all(a<b for a,b in zip(times,times[1:])),'invalid animation times')
                o=self.layouts[sampler['output']];_need(o[4]==5126 and 'byteStride' not in self.views[o[6]],'invalid animation output')
                _need(sampler.get('interpolation','LINEAR') in ('LINEAR','STEP','CUBICSPLINE'),'unsupported interpolation')
                _need(o[2]==a[2]*(3 if sampler.get('interpolation')=='CUBICSPLINE' else 1),'animation sample count mismatch')
                for j in range(o[2]):
                    values=struct.unpack_from('<'+('4f' if o[5]=='VEC4' else '3f' if o[5]=='VEC3' else 'f'),self.bin,o[0]+j*o[1])
                    _need(all(math.isfinite(v) for v in values),'nonfinite animation output')
            for channel in animation.get('channels',[]):
                target=channel.get('target',{});_need(_integer(target.get('node'),0,len(self.nodes)-1) and target.get('path') in ('translation','rotation','scale'),'unsupported animation channel')
                si=channel.get('sampler');_need(_integer(si,0,len(animation.get('samplers',[]))-1),'invalid animation sampler')
                output=self.layouts[animation['samplers'][si]['output']]
                _need(output[5]==('VEC4' if target['path']=='rotation' else 'VEC3'),'invalid animated transform type')
        _need(len(roles)==len(self.acc),'unused/unknown accessor unsupported')
        used=[]
        for i,l in enumerate(self.layouts):
            start,stride,num,size,_,_,_=l;end=start+(num-1)*stride+size
            for j,s,e,other_stride,other_size in used:
                if end<=s or e<=start:continue
                same_stride=stride==other_stride
                gap=(start-s)%stride if same_stride else 0
                _need(same_stride and gap>=other_size and stride-gap>=size,'overlapping attribute storage unsupported')
            used.append((i,start,end,stride,size))
        self.roots=roots;self.visits=0

    def pos(self,index,buffer=None):
        l=self.layouts[index];buf=self.bin if buffer is None else buffer
        return [struct.unpack_from('<3f',buf,l[0]+i*l[1]) for i in range(l[2])]

    def subtree(self,index):
        todo=[index];out=[]
        while todo:
            i=todo.pop();out.extend(self.node_prims.get(i,()));todo.extend(self.nodes[i].get('children',[]))
        return out

    def entities(self):
        if len(self.roots)>1:return list(self.roots)
        root=self.roots[0]
        while not self.node_prims.get(root) and len(self.nodes[root].get('children',[]))==1:root=self.nodes[root]['children'][0]
        return [root] if self.node_prims.get(root) else list(self.nodes[root].get('children',[]))

    def group(self,index):
        records={};triangles=[];protected=set();scalar_protected=set();positions=set()
        for pr in self.subtree(index):
            p=self.prims[pr];ai=p['position'];l=self.layouts[ai];points=self.pos(ai)
            self.visits+=len(points);_need(self.visits<=MAX_VISITS,'canonical vertex visit limit')
            keys=[];base_points=[]
            for j,xyz in enumerate(points):
                _need(all(math.isfinite(v) for v in xyz),'nonfinite POSITION')
                offset=l[0]+j*l[1];raw=bytes(self.bin[offset:offset+12]);u=struct.unpack('<3I',raw);key=struct.pack('<3I',*(v&~3 for v in u))
                base=struct.unpack('<3f',key);keys.append(key);base_points.append(base)
                r=records.setdefault(key,dict(raw=raw,ambiguous=False,offsets=set()))
                r['ambiguous']|=r['raw']!=raw;r['offsets'].add(offset)
                _need(len(records)<=MAX_GROUP_KEYS,'unique vertex group limit')
            positions.add(ai)
            low=tuple(min(v[a] for v in base_points) for a in range(3));high=tuple(max(v[a] for v in base_points) for a in range(3))
            for key,v in zip(keys,base_points):
                for a in range(3):
                    if v[a]==low[a] or v[a]==high[a]:scalar_protected.add((key,a))
            inds=p['indices']
            for j in range(0,len(inds),3):
                ids=tuple(inds[j+k] for k in range(3));ks=tuple(keys[k] for k in ids);xyz=tuple(base_points[k] for k in ids)
                triangles.append(b''.join(sorted(ks)))
                _,area=_normal(*xyz);edge=max(math.dist(xyz[a],xyz[b]) for a,b in ((0,1),(1,2),(2,0)))
                altitude=area/edge if edge else 0.
                delta=0.
                for key in ks:
                    u=struct.unpack('<3I',key);base=struct.unpack('<3f',key)
                    delta=max(delta,math.sqrt(sum((struct.unpack('<f',struct.pack('<I',v|3))[0]-base[a])**2 for a,v in enumerate(u))))
                if altitude<=8192*delta or area<=1e-24:protected.update(ks)
        _need(records,'empty group')
        fingerprint=hashlib.sha256(b''.join(sorted(records))+b'|'+b''.join(sorted(triangles))).hexdigest()
        candidates=[]
        for key,r in records.items():
            if r['ambiguous'] or key in protected:continue
            for a,u in enumerate(struct.unpack('<3I',key)):
                if (u>>23)&255 not in (0,255) and (key,a) not in scalar_protected:candidates.append((key,a))
        return dict(node=index,id=fingerprint,records=records,candidates=tuple(candidates),positions=positions,
            triangles=len(triangles),label=self.nodes[index].get('name','')[:120])

def _merge(groups):
    out={}
    for group in groups:
        if group['id'] not in out:out[group['id']]=group;group['instances']=1;continue
        old=out[group['id']];old['instances']+=1
        old['candidates']=tuple(set(old['candidates'])&set(group['candidates']))
        for key,r in group['records'].items():old['records'][key]['offsets'].update(r['offsets'])
    return out

def _parse(data):
    try:return _GLB(data)
    except WatermarkError:raise
    except (KeyError,TypeError,IndexError,AttributeError,OverflowError,struct.error,RecursionError) as e:
        raise WatermarkError('malformed or unsupported GLB') from e

def _carriers(groups,key,domain):
    values=[]
    for gid,g in groups.items():
        for point,axis in g['candidates']:
            _need(len(values)<MAX_CARRIERS,'carrier budget exceeded')
            identity=bytes.fromhex(gid)+point+bytes([axis])
            code=hmac.new(key,domain+identity,hashlib.sha256).digest()
            values.append((code,identity,gid,point,axis))
    values.sort(key=lambda v:(v[0],v[1]));return values

def _payload(token):return tuple((v>>(7-j))&1 for v in token for j in range(8))

def _decode(glb,carriers,bit,expected):
    votes=[[0,0] for _ in range(BITS)]
    for i,(code,_,gid,point,axis) in enumerate(carriers):
        offset=next(iter(glb[gid]['records'][point]['offsets']))+axis*4
        value=(struct.unpack_from('<I',glb['_buffer'],offset)[0]>>bit)&1
        votes[i%BITS][value^(code[16]&1)]+=1
    decoded=[int(b>a) if a!=b else None for a,b in votes]
    errors=sum(a!=b for a,b in zip(decoded,_payload(expected)))
    token=bytes(sum((decoded[i*8+k] or 0)<<(7-k) for k in range(8)) for i in range(12))
    covered=sum(bool(a+b) for a,b in votes);erasures=sum(a==b for a,b in votes)
    return dict(capacity=len(carriers),repeat_count=len(carriers)//BITS,covered_bits=covered,erasures=erasures,
        bit_errors=errors,bit_error_rate=errors/BITS,decoded_token=token.hex() if not erasures else None,
        exact_match=not erasures and hmac.compare_digest(token,expected))

def _pack(doc,buf):
    j=json.dumps(doc,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode();j+=b' '*((-len(j))%4)
    _need(len(j)<=MAX_JSON,'output JSON limit');b=bytes(buf)+b'\0'*((-len(buf))%4)
    total=28+len(j)+len(b);_need(total<=MAX_BYTES,'output GLB limit')
    return struct.pack('<III',0x46546c67,2,total)+struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',len(b),0x004e4942)+b

def _geometry_check(parsed,marked):
    max_delta=max_angle=bbox_delta=0.;flips=degenerates=0;count=0;shared=0
    for p in parsed.prims:
        a=parsed.pos(p['position']);b=parsed.pos(p['position'],marked);world=parsed.world[p['node']]
        wa=[_point(world,v) for v in a];wb=[_point(world,v) for v in b]
        for u,v in zip(wa,wb):max_delta=max(max_delta,math.dist(u,v)*1000.)
        for axis in range(3):
            bbox_delta=max(bbox_delta,abs(min(v[axis] for v in wa)-min(v[axis] for v in wb))*1000.,abs(max(v[axis] for v in wa)-max(v[axis] for v in wb))*1000.)
        inds=p['indices']
        for i in range(0,len(inds),3):
            ids=[inds[i+j] for j in range(3)];n,_=_normal(*(wa[j] for j in ids));m,_=_normal(*(wb[j] for j in ids));count+=1
            if (n is None)!=(m is None):degenerates+=1
            if n is None or m is None:continue
            dot=sum(x*y for x,y in zip(n,m));flips+=dot<0
            max_angle=max(max_angle,math.degrees(math.acos(max(-1.,min(1.,dot)))))
    _need(max_delta<=MAX_WORLD_DELTA_MM and max_angle<=MAX_NORMAL_ANGLE_DEG and not flips and not degenerates,'unsafe geometry perturbation')
    return dict(max_world_mm_delta=max_delta,max_normal_angle_deg=max_angle,max_world_bbox_mm_delta=bbox_delta,
        triangle_count=count,orientation_flips=flips,new_or_removed_degenerate_triangles=degenerates)

def mark_glb(data,token,key):
    """Return new bytes plus public audit/context. Caller owns all key storage."""
    _need(isinstance(token,bytes) and len(token)==12,'token must be12bytes')
    _need(isinstance(key,bytes) and len(key)==32,'key must be32bytes')
    parsed=_parse(data);original_groups=[parsed.group(n) for n in parsed.entities()]
    source_parts=[dict(geometry_id=g['id'],label=g['label'],source_node=g['node']) for g in original_groups]
    groups=_merge(original_groups);buf=bytearray(parsed.bin);payload=_payload(token)
    local={gid:_carriers({gid:g},key,b'local/') for gid,g in groups.items()}
    global_carriers=_carriers(groups,key,b'global/')
    _need(len(global_carriers)>=BITS,'insufficient geometry capacity')
    assignments={};parts=[]
    for gid,g in groups.items():
        cs=local[gid];supported=len(cs)>=BITS
        parts.append(dict(geometry_id=gid,label=g['label'],instances=g['instances'],capacity=len(cs),repeat_count=len(cs)//BITS,supported=supported))
        if supported:
            for i,(code,_,_,point,axis) in enumerate(cs):assignments[(gid,point,axis)]=payload[i%BITS]^(code[16]&1)
    by_id={p['geometry_id']:p for p in parts}
    part_instances=[dict(p,capacity=by_id[p['geometry_id']]['capacity'],repeat_count=by_id[p['geometry_id']]['repeat_count'],
        supported=by_id[p['geometry_id']]['supported']) for p in source_parts]
    for i,(code,_,gid,point,axis) in enumerate(global_carriers):
        bit1=payload[i%BITS]^(code[16]&1);r=groups[gid]['records'][point]
        for offset in r['offsets']:
            at=offset+axis*4;old=struct.unpack_from('<I',buf,at)[0]
            bit0=assignments.get((gid,point,axis),old&1)
            struct.pack_into('<I',buf,at,(old&~3)|bit0|(bit1<<1))
    safety=_geometry_check(parsed,buf)
    for ai in {p['position'] for p in parsed.prims}:
        points=parsed.pos(ai,buf);parsed.doc['accessors'][ai]['min']=[min(v[a] for v in points) for a in range(3)]
        parsed.doc['accessors'][ai]['max']=[max(v[a] for v in points) for a in range(3)]
    output=_pack(parsed.doc,buf)
    context=dict(profile=PROFILE,version=1,payload_bits=BITS,
        groups=[dict(geometry_id=p['geometry_id'],capacity=p['capacity'],repeat_count=p['repeat_count'],instances=p['instances']) for p in sorted(parts,key=lambda p:p['geometry_id'])])
    extracted=extract_glb(output,key,token,context)
    _need(extracted['global_channel']['exact_match'] and all(p['exact_match'] for p in extracted['parts'] if p['supported']),'internal watermark roundtrip failed')
    decoded={p['geometry_id']:p for p in extracted['parts']}
    for p in part_instances:
        actual=decoded[p['geometry_id']]
        p.update(bit_errors=actual['bit_errors'] if p['supported'] else None,
            covered_bits=actual['covered_bits'],erasures=actual['erasures'])
    return output,dict(profile=PROFILE,public_context=context,source_sha256=hashlib.sha256(data).hexdigest(),marked_sha256=hashlib.sha256(output).hexdigest(),
        token_hex=token.hex(),source_bytes=len(data),marked_bytes=len(output),parts=part_instances,geometry_groups=parts,global_capacity=len(global_carriers),
        position_low_bits_only=True,normal_index_material_animation_node_values_preserved=True,**safety,
        shared_local_vertex_copies_consistent=True,roundtrip=extracted,
        limits=['lossless-first only','transform baking/quantization/remeshing may erase','unit conversion/re-export may erase',
            'local vertex sharing is preserved within each independent geometry group',
            'external signed manifest authenticates issuance; this codec does not'])

def extract_glb(data,key,expected_token,public_context):
    """Blind local-geometry decode; no original mesh/name/extras are needed."""
    _need(isinstance(key,bytes) and len(key)==32,'key must be32bytes')
    _need(isinstance(expected_token,bytes) and len(expected_token)==12,'token must be12bytes')
    _need(isinstance(public_context,dict) and public_context.get('profile')==PROFILE and public_context.get('version')==1 and public_context.get('payload_bits')==BITS,'unsupported public context')
    _need(set(public_context)=={'profile','version','payload_bits','groups'},'unknown public context fields')
    entries=public_context.get('groups');_need(isinstance(entries,list) and 0<len(entries)<=MAX_NODES,'invalid context groups')
    known=set()
    expected_instances={}
    for entry in entries:
        _need(isinstance(entry,dict),'invalid context group')
        _need(set(entry)=={'geometry_id','capacity','repeat_count','instances'},'unknown context group fields')
        gid=entry.get('geometry_id');_need(isinstance(gid,str) and len(gid)==64 and all(c in '0123456789abcdef' for c in gid) and gid not in known,'invalid geometry id');known.add(gid)
        _need(_integer(entry['capacity'],0,MAX_CARRIERS) and entry['repeat_count']==entry['capacity']//BITS,'invalid context capacity')
        instances=entry.get('instances',1);_need(_integer(instances,1,MAX_NODES),'invalid context instance count');expected_instances[gid]=instances
    parsed=_parse(data);candidates=[]
    # Search subtrees so a detached whole part can still use its local channel.
    for node in parsed.order:
        if not parsed.subtree(node):continue
        group=parsed.group(node)
        if group['id'] in known:
            candidates.append(group)
    selected=[]
    for group in candidates:
        parent=parsed.parents.get(group['node']);ancestors=set()
        while parent is not None:ancestors.add(parent);parent=parsed.parents.get(parent)
        if not any(g['id']==group['id'] and g['node'] in ancestors for g in candidates):selected.append(group)
    groups=_merge(selected);results=[]
    for gid,g in groups.items():
        cs=_carriers({gid:g},key,b'local/');rows=dict(groups);rows['_buffer']=parsed.bin
        result=_decode(rows,cs,0,expected_token);result.update(geometry_id=gid,instances=g['instances'],supported=len(cs)>=BITS)
        results.append(result)
    cs=_carriers(groups,key,b'global/');rows=dict(groups);rows['_buffer']=parsed.bin
    whole=_decode(rows,cs,1,expected_token)
    all_present=set(groups)==known
    return dict(profile=PROFILE,detected=(whole['exact_match'] and all_present) or any(r['supported'] and r['exact_match'] for r in results),
        global_channel=whole,all_context_groups_present=all_present,
        all_context_instances_present=all_present and all(g['instances']==expected_instances[gid] for gid,g in groups.items()),
        parts=results,matched_group_count=len(groups),
        expected_group_count=len(known),authentication='Not performed here; verify external signed release manifest',
        geometry_metadata_names_used=False,original_model_required=False)
