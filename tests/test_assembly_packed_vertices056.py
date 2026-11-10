"""Three small pure candidate controls; no real whole factory or Qt context."""
import ast
import copy
from dataclasses import replace
import gc
import math
from pathlib import Path
import struct
import sys
import unittest
import weakref
from unittest.mock import patch

from assembly_geometry import Mesh,Scene,box,vertex_bytes
from assembly_packed_vertices056 import Float64Vertices,compact_scene
import assembly_scene_cache as cache_module
from assembly_style import apply_model_styles,crease_edges,edge_batches
from assembly_part_motion052 import PartMotionPlanner,plan_part_motion
from assembly_gpu_insertion049 import insertion_plan
from test_assembly_part_motion052 import cpu_scene,ram_scene
from test_gpu_insertion049 import fixture as gpu_scene

SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')


def payload_scene(values,metadata=None):
    return Scene((Mesh('fixture-large',values,(.2,.3,.4,1.),component='gpu',part_id='gpu:0'),),
        (200.,400.,400.),{}if metadata is None else metadata)


def vertex_storage(scene):
    """Exact same-root, id-deduplicated reachable PN owners for small fixtures.

    Sum only sys.getsizeof for the explicitly enumerated known objects; hidden
    C-managed buffer allocations are not estimated. This is not working set/RSS, allocator arenas,
    driver/JIT memory, a whole-process attribution or a predicted RSS reduction.
    The bound prevents use as a large arbitrary heap tracer.
    """
    seen=set();containers=scalars=payload=0;visits=0
    for mesh in scene.meshes:
        value=mesh.vertices
        if id(value)in seen:continue
        seen.add(id(value));containers+=sys.getsizeof(value)
        if isinstance(value,Float64Vertices):
            for owner in(value._payload,value._view):
                if id(owner)not in seen:
                    seen.add(id(owner));containers+=sys.getsizeof(owner)
            payload+=value.nbytes
        elif type(value)is tuple:
            for number in value:
                visits+=1
                if visits>30000:raise ValueError('Small fixture accounting only')
                if id(number)not in seen:seen.add(id(number));scalars+=sys.getsizeof(number)
    return dict(container_bytes=containers,unique_scalar_bytes=scalars,
        accounted_shallow_owner_bytes=containers+scalars,packed_float64_payload_bytes=payload)


class PackedVertices056Controls(unittest.TestCase):
    def test_finite_double_bits_and_tuple_contract_are_lossless_and_immutable(self):
        values=(1.+2.**-30,-0.,2.**53,5.e-324,1.,-.25)*3
        packed=Float64Vertices(values)
        self.assertEqual(packed.packed_bytes,struct.pack('='+str(len(values))+'d',*values))
        self.assertEqual(packed.nbytes,8*len(values));self.assertEqual(tuple(packed),values)
        self.assertEqual(packed,values);self.assertEqual(values,packed)
        self.assertEqual(hash(packed),hash(values));self.assertNotEqual(packed,list(values))
        self.assertEqual(packed[-1],values[-1]);self.assertEqual(packed[::-2],values[::-2])
        self.assertEqual(packed[1:17:3],values[1:17:3]);self.assertIs(type(packed[0:3]),tuple)
        self.assertEqual(packed+(3.,),values+(3.,));self.assertEqual((3.,)+packed,(3.,)+values)
        self.assertEqual(2*packed,2*values);self.assertIs(copy.deepcopy(packed),packed)
        self.assertEqual(hash(Mesh('a',packed,(1,1,1,1))),hash(Mesh('a',values,(1,1,1,1))))
        self.assertEqual(vertex_bytes(payload_scene(packed)),vertex_bytes(payload_scene(values)))
        self.assertIs(type(packed._view.obj),bytes);self.assertTrue(packed._view.readonly)
        self.assertNotEqual(packed[0],struct.unpack('<f',struct.pack('<f',values[0]))[0])
        with self.assertRaises(TypeError):packed._view[0]=1.
        with self.assertRaises(AttributeError):packed._payload=b''
        with self.assertRaises(AttributeError):packed.__init__((1.,))
        for number in (float('nan'),float('inf'),2**53+1,True,'1'):
            raw=payload_scene((number,)*4096)
            self.assertIs(compact_scene(raw),raw)
        small=payload_scene(box(1.,2.,3.));self.assertIs(compact_scene(small),small)
        typed=memoryview(struct.pack('<18f',*values)).cast('f');raw=payload_scene(typed)
        self.assertIs(compact_scene(raw,minimum_values=1),raw)

    def test_real_cache_keeps_one_alias_owner_all_six_styles_and_protects_metadata(self):
        large=tuple(float(n)+2.**-30 for n in range(6480));metadata=dict(cooling={},auxiliary={},anchors=(1.,2.,3.))
        source=Scene((Mesh('large-a',large,(.2,.3,.4,1.),component='gpu',part_id='gpu:0'),
                      Mesh('large-b',large,(.3,.2,.4,1.),component='board',part_id='board:0')),(200,400,400),metadata)
        raw_scenes=[]
        def factory(payload):
            self.assertEqual(payload['gpu']['detected_label'],'current host metadata')
            self.assertIs(type(source.meshes[0].vertices),tuple)
            scene=replace(source);raw_scenes.append(weakref.ref(scene));return scene
        cache=cache_module.SceneCache();results=[]
        spec=dict(gpu=dict(label='Reference',telemetry_bound=False,detected_label='current host metadata'),
            case=dict(panels=dict(front='open')))
        with patch.object(cache_module,'build_scene',side_effect=factory)as build:
            for style in SIX:
                result=cache.build(dict(spec,visual_style=style));results.append(result)
                self.assertIs(result.meshes[0].vertices,result.meshes[1].vertices)
                self.assertIs(result.meshes[0].vertices,cache.base.meshes[0].vertices)
                self.assertEqual(vertex_bytes(result),vertex_bytes(source))
            self.assertEqual(build.call_count,1)
            self.assertTrue(all(ref()is None for ref in raw_scenes))
        self.assertIs(cache.base.metadata,metadata);self.assertIs(source.meshes[0].vertices,large)
        original=vertex_storage(source);after=vertex_storage(cache.base)
        self.assertEqual(after['packed_float64_payload_bytes'],len(large)*8)
        self.assertLess(after['accounted_shallow_owner_bytes'],original['accounted_shallow_owner_bytes'])
        self.assertEqual(original['unique_scalar_bytes'],sum(sys.getsizeof(v)for v in large))
        owner=weakref.ref(cache.base.meshes[0].vertices)
        result=None;results.clear();cache.clear();gc.collect();self.assertIsNone(owner())
        for meta in ({'PN_owner':large},{'mesh':source.meshes[0]},
                     {'mesh_id':id(source.meshes[0])},{'vertices_id':id(large)}, {'unknown':object()}):
            protected=replace(source,metadata=meta)
            self.assertIs(compact_scene(protected),protected)
        shared_case=replace(source,meshes=source.meshes+(replace(source.meshes[0],component='case'),))
        self.assertIs(compact_scene(shared_case),shared_case)
        self.assertIs(compact_scene(source,max_metadata_nodes=1),source)

    def test_actual_cpu_geometry_edges_bounds_and_motion_match_before_after(self):
        # Pure renderer functions are extracted from the real current source;
        # no Qt module import, QOpenGLWidget or native context is constructed.
        root=Path(cache_module.__file__).resolve().parent
        if not(root/'assembly_viewer.py').exists():root=Path(__file__).resolve().parents[5]
        tree=ast.parse((root/'assembly_viewer.py').read_text('utf8'))
        nodes=[copy.deepcopy(n)for n in tree.body if isinstance(n,ast.FunctionDef)
            and n.name in('scene_bounds','renderer_vertex_bytes')]
        constants=next(n for n in tree.body if isinstance(n,ast.Assign)
            and any(isinstance(t,ast.Name)and t.id=='ASSEMBLY_COMPONENTS'for t in n.targets))
        space=dict(sys=sys,math=math,vertex_bytes=vertex_bytes)
        exec(compile(ast.Module([copy.deepcopy(constants),*nodes],[]),str(root/'assembly_viewer.py'),'exec'),space)
        for source,target in ((cpu_scene(),'cpu:0'),(ram_scene(),'memory:1')):
            packed=compact_scene(source,minimum_values=18)
            self.assertIsInstance(packed.meshes[0].vertices,Float64Vertices)
            self.assertEqual(plan_part_motion(source,target),plan_part_motion(packed,target))
            self.assertTrue(plan_part_motion(packed,target)['available'])
            left=PartMotionPlanner(source);right=PartMotionPlanner(packed)
            try:self.assertEqual(left.plan(target),right.plan(target))
            finally:left.clear();right.clear()
            self.assertEqual(space['renderer_vertex_bytes'](source),space['renderer_vertex_bytes'](packed))
            chosen=lambda mesh,focus:focus=='all'or mesh.component==focus or mesh.part_id==focus
            shift=lambda mesh,exploded:(0.,0.,0.)
            self.assertEqual(space['scene_bounds'](source,chosen,shift),space['scene_bounds'](packed,chosen,shift))
            for style in SIX:
                before,_=apply_model_styles(source.meshes,style,{},source.dimensions,{'front':'open'})
                after,_=apply_model_styles(packed.meshes,style,{},packed.dimensions,{'front':'open'})
                self.assertEqual(list(edge_batches(before,style)),list(edge_batches(after,style)))
                for index in range(len(before)):
                    self.assertEqual(crease_edges(before[index].vertices),crease_edges(after[index].vertices))
                    self.assertIs(after[index].vertices,packed.meshes[index].vertices)
        source=gpu_scene();packed=compact_scene(source,minimum_values=18)
        self.assertTrue(insertion_plan(source)['available'])
        self.assertEqual(insertion_plan(source),insertion_plan(packed))


if __name__=='__main__':unittest.main()
