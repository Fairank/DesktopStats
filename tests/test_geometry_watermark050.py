"""Real GLB transformations/negative controls, no Qt/GL/filesystem keys."""
import copy
import json
import math
import struct
import unittest

from geometry_watermark050 import mark_glb,extract_glb,WatermarkError

KEY=bytes(range(32))  # Synthetic public test vector, never an owner's key.
TOKEN=bytes(range(12))

def unpack(data):
    size,kind=struct.unpack_from('<II',data,12);assert kind==0x4e4f534a
    d=json.loads(data[20:20+size]);at=20+size;length,kind=struct.unpack_from('<II',data,at);assert kind==0x004e4942
    return d,bytearray(data[at+8:at+8+length])

def pack(d,b):
    j=json.dumps(d,separators=(',',':'),allow_nan=False).encode();j+=b' '*((-len(j))%4)
    b=bytes(b)+b'\0'*((-len(b))%4)
    return struct.pack('<III',0x46546c67,2,28+len(j)+len(b))+struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',len(b),0x004e4942)+b

def geometry(d,b):
    out=[]
    for mesh in d['meshes']:
        p=mesh['primitives'][0];a=d['accessors'][p['attributes']['POSITION']];v=d['bufferViews'][a['bufferView']]
        off=v.get('byteOffset',0)+a.get('byteOffset',0);stride=v.get('byteStride',12)
        points=[struct.unpack_from('<3f',b,off+i*stride) for i in range(a['count'])]
        n=d['accessors'][p['attributes']['NORMAL']];nv=d['bufferViews'][n['bufferView']]
        normals=[struct.unpack_from('<3f',b,nv.get('byteOffset',0)+n.get('byteOffset',0)+i*nv.get('byteStride',12)) for i in range(n['count'])]
        if 'indices' in p:
            a=d['accessors'][p['indices']];v=d['bufferViews'][a['bufferView']];off=v.get('byteOffset',0)+a.get('byteOffset',0)
            ids=list(struct.unpack_from('<%dI'%a['count'],b,off))
        else:ids=list(range(len(points)))
        out.append((points,normals,ids))
    return out

def assemble(d,values,indexed):
    d=copy.deepcopy(d);d['accessors']=[];d['bufferViews']=[];b=bytearray()
    for mi,(points,normals,ids) in enumerate(values):
        if indexed:
            unique={};newpoints=[];newnormals=[];newids=[]
            for old in ids:
                key=struct.pack('<6f',*points[old],*normals[old])
                if key not in unique:unique[key]=len(newpoints);newpoints.append(points[old]);newnormals.append(normals[old])
                newids.append(unique[key])
            points,normals,ids=newpoints,newnormals,newids
        else:points,normals=[points[i] for i in ids],[normals[i] for i in ids]
        view=len(d['bufferViews']);start=len(b)
        for p,n in zip(points,normals):b.extend(struct.pack('<6f',*p,*n))
        d['bufferViews'].append(dict(buffer=0,byteOffset=start,byteLength=len(b)-start,byteStride=24,target=34962))
        ai=len(d['accessors']);bounds=dict(min=[min(p[a] for p in points) for a in range(3)],max=[max(p[a] for p in points) for a in range(3)])
        # Python fixture coordinates round once to exact stored float bounds.
        bounds={k:[struct.unpack('<f',struct.pack('<f',v))[0] for v in values] for k,values in bounds.items()}
        d['accessors'].append(dict(bufferView=view,byteOffset=0,componentType=5126,type='VEC3',count=len(points),**bounds))
        d['accessors'].append(dict(bufferView=view,byteOffset=12,componentType=5126,type='VEC3',count=len(normals)))
        primitive=dict(attributes=dict(POSITION=ai,NORMAL=ai+1),mode=4,material=0)
        if indexed:
            view=len(d['bufferViews']);start=len(b);b.extend(struct.pack('<%dI'%len(ids),*ids))
            d['bufferViews'].append(dict(buffer=0,byteOffset=start,byteLength=len(b)-start,target=34963))
            primitive['indices']=len(d['accessors']);d['accessors'].append(dict(bufferView=view,componentType=5125,type='SCALAR',count=len(ids)))
        d['meshes'][mi]['primitives']=[primitive]
    # Keep a real finite GPU-like transform clip and never alter its BIN data.
    view=len(d['bufferViews']);start=len(b);b.extend(struct.pack('<2f',0.,1.))
    d['bufferViews'].append(dict(buffer=0,byteOffset=start,byteLength=8))
    ti=len(d['accessors']);d['accessors'].append(dict(bufferView=view,componentType=5126,type='SCALAR',count=2))
    view=len(d['bufferViews']);start=len(b);b.extend(struct.pack('<6f',0.,0.,0.,-1.,0.,0.))
    d['bufferViews'].append(dict(buffer=0,byteOffset=start,byteLength=24))
    oi=len(d['accessors']);d['accessors'].append(dict(bufferView=view,componentType=5126,type='VEC3',count=2))
    d['animations']=[dict(name='finite reference',samplers=[dict(input=ti,output=oi,interpolation='LINEAR')],channels=[dict(sampler=0,target=dict(node=1,path='translation'))])]
    d['buffers']=[dict(byteLength=len(b))]
    return pack(d,b)

def fixture(indexed=False):
    d=dict(asset=dict(version='2.0'),scene=0,scenes=[dict(nodes=[0])],
        nodes=[dict(name='root',scale=[.001]*3,children=[1,3]),dict(name='CPU',children=[2],extras=dict(part_id='cpu:0')),
            dict(name='CPU surface',mesh=0,translation=[0.,0.,0.]),dict(name='RAM',children=[4],extras=dict(part_id='memory:0')),
            dict(name='RAM surface',mesh=1,translation=[25.,10.,0.])],
        meshes=[dict(name='CPU',primitives=[]),dict(name='RAM',primitives=[])],
        materials=[dict(pbrMetallicRoughness=dict(baseColorFactor=[.8,.7,.5,1.],metallicFactor=.4,roughnessFactor=.6),doubleSided=True)],
        extras=dict(not_a_watermark='metadata must not be used for extraction'))
    values=[]
    for size in (5.,3.25):
        points=[(100.125+x*size,200.375+y*size,12.5) for y in range(13) for x in range(13)]
        ids=[]
        for y in range(12):
            for x in range(12):a=y*13+x;ids.extend((a,a+1,a+13,a+1,a+14,a+13))
        values.append((points,[(0.,0.,1.)]*len(points),ids))
    return assemble(d,values,indexed)

class GeometryWatermark050Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=fixture();cls.marked,cls.report=mark_glb(cls.original,TOKEN,KEY);cls.context=cls.report['public_context']

    def test_real_payload_geometry_and_finite_animation_preserved(self):
        d,b=unpack(self.original);e,c=unpack(self.marked)
        self.assertEqual(d['nodes'],e['nodes']);self.assertEqual(d['meshes'],e['meshes'])
        self.assertEqual(d['animations'],e['animations']);self.assertEqual(d['materials'],e['materials'])
        old,new=geometry(d,b),geometry(e,c)
        changed=0
        for a,z in zip(old,new):
            self.assertEqual(a[1:],z[1:])
            for p,q in zip(a[0],z[0]):
                for x,y in zip(p,q):
                    u,v=struct.unpack('<II',struct.pack('<ff',x,y));self.assertEqual(u&~3,v&~3);changed+=u!=v
        self.assertGreater(changed,100)
        self.assertEqual(self.report['triangle_count'],576)
        self.assertEqual(self.report['orientation_flips'],0)
        self.assertEqual(self.report['new_or_removed_degenerate_triangles'],0)
        self.assertLess(self.report['max_world_mm_delta'],.001)
        self.assertLess(self.report['max_normal_angle_deg'],.1)
        self.assertTrue(all(p['supported'] and p['bit_errors']==0 for p in self.report['parts']))
        # Retain exact same coordinate sharing relation, not only same counts.
        for a,z in zip(old,new):
            mapping={}
            for p,q in zip(a[0],z[0]):self.assertEqual(mapping.setdefault(p,q),q)
        position_bytes=set()
        for m in d['meshes']:
            a=d['accessors'][m['primitives'][0]['attributes']['POSITION']];v=d['bufferViews'][a['bufferView']]
            for i in range(a['count']):position_bytes.update(range(v['byteOffset']+i*24,v['byteOffset']+i*24+12))
        self.assertEqual(len(b),len(c))
        self.assertTrue(all(x==y for i,(x,y) in enumerate(zip(b,c)) if i not in position_bytes))

    def test_deterministic_byte_output_and_no_secret_carrier_context(self):
        again,r=mark_glb(self.original,TOKEN,KEY);self.assertEqual(again,self.marked)
        self.assertEqual(r['public_context'],self.context)
        public=json.dumps(self.context)
        self.assertNotIn(KEY.hex(),public);self.assertNotIn('carrier_order',public);self.assertNotIn('positions',public)
        self.assertEqual(set(self.context),{'profile','version','payload_bits','groups'})

    def test_rename_delete_metadata_reorder_nodes_and_meshes(self):
        d,b=unpack(self.marked)
        def strip(v):
            if isinstance(v,dict):
                return {k:strip(x) for k,x in v.items() if k not in ('name','extras')}
            if isinstance(v,list):return [strip(x) for x in v]
            return v
        d=strip(d);order=list(reversed(range(len(d['nodes']))));remap={old:new for new,old in enumerate(order)}
        nodes=[d['nodes'][i] for i in order]
        for n in nodes:
            if 'children' in n:n['children']=[remap[i] for i in reversed(n['children'])]
            if 'mesh' in n:n['mesh']=len(d['meshes'])-1-n['mesh']
        d['nodes']=nodes;d['meshes'].reverse();d['scenes'][0]['nodes']=[remap[i] for i in d['scenes'][0]['nodes']]
        for a in d['animations']:
            for c in a['channels']:c['target']['node']=remap[c['target']['node']]
        r=extract_glb(pack(d,b),KEY,TOKEN,self.context)
        self.assertTrue(r['detected']);self.assertTrue(r['global_channel']['exact_match']);self.assertTrue(r['all_context_instances_present'])
        self.assertTrue(all(p['bit_errors']==0 for p in r['parts']))

    def test_index_rebuild_vertex_and_triangle_index_reorder(self):
        d,b=unpack(self.marked);indexed=assemble(d,geometry(d,b),True)
        d,b=unpack(indexed)
        for m in d['meshes']:
            p=m['primitives'][0];a=d['accessors'][p['attributes']['POSITION']];v=d['bufferViews'][a['bufferView']]
            start=v['byteOffset'];count=a['count'];rows=[bytes(b[start+i*24:start+(i+1)*24]) for i in range(count)]
            b[start:start+count*24]=b''.join(reversed(rows))
            ia=d['accessors'][p['indices']];iv=d['bufferViews'][ia['bufferView']];at=iv['byteOffset']
            ids=list(struct.unpack_from('<%dI'%ia['count'],b,at));triangles=[ids[i:i+3] for i in range(0,len(ids),3)]
            values=[count-1-i for tri in reversed(triangles) for i in tri]
            struct.pack_into('<%dI'%len(values),b,at,*values)
        r=extract_glb(pack(d,b),KEY,TOKEN,self.context)
        self.assertTrue(r['detected']);self.assertEqual(r['global_channel']['bit_errors'],0)
        self.assertTrue(all(p['bit_errors']==0 for p in r['parts']))
        # Writer also supports an original indexed model without touching indices.
        source=fixture(True);marked,report=mark_glb(source,TOKEN,KEY)
        s,sb=unpack(source);t,tb=unpack(marked)
        self.assertEqual([x[2] for x in geometry(s,sb)],[x[2] for x in geometry(t,tb)])
        self.assertTrue(report['roundtrip']['detected'])

    def test_nodes_can_transform_without_baking_positions(self):
        d,b=unpack(self.marked);angle=.37
        d['nodes'][1]['translation']=[12.,-5.,2.];d['nodes'][1]['rotation']=[0.,math.sin(angle/2),0.,math.cos(angle/2)]
        d['nodes'][3]['scale']=[1.2,.8,1.4]
        r=extract_glb(pack(d,b),KEY,TOKEN,self.context)
        self.assertTrue(r['detected']);self.assertTrue(r['global_channel']['exact_match'])

    def test_isolated_complete_part_uses_local_channel(self):
        d,b=unpack(self.marked);values=geometry(d,b)[:1]
        d['nodes']=[dict(children=[1],scale=[.001]*3),dict(mesh=0)];d['scenes']=[dict(nodes=[0])];d['meshes']=d['meshes'][:1]
        # assemble generates a harmless finite clip targeting node1.
        alone=assemble(d,values,True)
        r=extract_glb(alone,KEY,TOKEN,self.context)
        self.assertTrue(r['detected']);self.assertFalse(r['all_context_groups_present'])
        self.assertEqual(r['matched_group_count'],1);self.assertEqual(r['parts'][0]['bit_errors'],0)

    def test_unmarked_wrong_key_wrong_token_and_zero_token_controls(self):
        self.assertFalse(extract_glb(self.original,KEY,TOKEN,self.context)['detected'])
        for key in (b'X'*32,bytes(reversed(KEY))):self.assertFalse(extract_glb(self.marked,key,TOKEN,self.context)['detected'])
        self.assertFalse(extract_glb(self.marked,KEY,b'Y'*12,self.context)['detected'])
        marked,r=mark_glb(self.original,b'\0'*12,KEY)
        self.assertTrue(extract_glb(marked,KEY,b'\0'*12,r['public_context'])['detected'])
        self.assertFalse(extract_glb(self.original,KEY,b'\0'*12,r['public_context'])['detected'])

    def test_requantization_and_baked_rotation_are_explicit_boundaries(self):
        d,b=unpack(self.marked)
        for m in d['meshes']:
            a=d['accessors'][m['primitives'][0]['attributes']['POSITION']];v=d['bufferViews'][a['bufferView']]
            for i in range(a['count']):
                at=v['byteOffset']+i*24;x,y,z=struct.unpack_from('<3f',b,at)
                struct.pack_into('<3f',b,at,round(x,2),round(y,2),round(z,2))
            p=[struct.unpack_from('<3f',b,v['byteOffset']+i*24) for i in range(a['count'])]
            a['min']=[min(q[k] for q in p) for k in range(3)];a['max']=[max(q[k] for q in p) for k in range(3)]
        self.assertFalse(extract_glb(pack(d,b),KEY,TOKEN,self.context)['detected'])
        d,b=unpack(self.marked);angle=math.radians(37);co,si=math.cos(angle),math.sin(angle)
        values=[]
        for points,normals,ids in geometry(d,b):
            points=[(co*x+si*z,y,-si*x+co*z) for x,y,z in points]
            normals=[(co*x+si*z,y,-si*x+co*z) for x,y,z in normals]
            values.append((points,normals,ids))
        rotated=assemble(d,values,True)
        self.assertFalse(extract_glb(rotated,KEY,TOKEN,self.context)['detected'])
        d,b=unpack(self.marked);values=geometry(d,b)
        values=[([tuple(v*.001 for v in p) for p in points],normals,ids) for points,normals,ids in values]
        d['nodes'][0]['scale']=[1.]*3
        for node in d['nodes']:
            if 'translation' in node:node['translation']=[v*.001 for v in node['translation']]
        rewritten_units=assemble(d,values,True)
        self.assertFalse(extract_glb(rewritten_units,KEY,TOKEN,self.context)['detected'])
        self.assertIn('unit conversion/re-export may erase',self.report['limits'])
        self.assertIn('transform baking/quantization/remeshing may erase',self.report['limits'])

    def test_unknown_formats_and_allocation_bombs_fail_closed(self):
        d,b=unpack(self.original)
        variants=[]
        q=copy.deepcopy(d);q['extensionsUsed']=['KHR_mesh_quantization'];variants.append(q)
        q=copy.deepcopy(d);q['buffers'][0]['uri']='https://invalid.example/x.bin';variants.append(q)
        q=copy.deepcopy(d);q['meshes'][0]['primitives'][0]['attributes']['COLOR_0']=1;variants.append(q)
        q=copy.deepcopy(d);q['accessors'][0]['count']=10**12;variants.append(q)
        q=copy.deepcopy(d);q['accessors'][0]['sparse']={'count':1};variants.append(q)
        q=copy.deepcopy(d);q['bufferViews'][1]['byteOffset']=0;variants.append(q)
        q=copy.deepcopy(d);q['nodes'][1]['children']=[0];variants.append(q)
        q=copy.deepcopy(d);q['meshes'][0]['primitives'][0]['attributes']['NORMAL']=0;variants.append(q)
        q=copy.deepcopy(d);q['animations'][0]['channels'][0]['sampler']=10**10;variants.append(q)
        for q in variants:
            with self.subTest(q=q):
                with self.assertRaises(WatermarkError):mark_glb(pack(q,b),TOKEN,KEY)
        with self.assertRaises(WatermarkError):mark_glb(self.original[:-1],TOKEN,KEY)
        with self.assertRaises(WatermarkError):mark_glb(self.original,b'bad',KEY)
        with self.assertRaises(WatermarkError):extract_glb(self.marked,b'bad',TOKEN,self.context)
        ctx=copy.deepcopy(self.context);ctx['key']='must not be placed in public context'
        with self.assertRaises(WatermarkError):extract_glb(self.marked,KEY,TOKEN,ctx)

    def test_unsafe_world_displacement_is_rejected(self):
        d,b=unpack(self.original);d['nodes'][0]['scale']=[1e6]*3
        with self.assertRaisesRegex(WatermarkError,'unsafe geometry'):mark_glb(pack(d,b),TOKEN,KEY)

if __name__=='__main__':unittest.main()
