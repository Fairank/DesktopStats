"""Exact scene packing, camera and pick bounds without a graphics context."""
import math
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from assembly_geometry import Mesh,Scene,box,vertex_bytes
from assembly_viewer import ASSEMBLY_COMPONENTS,AssemblyRenderer,scene_bounds


def reference_bounds(scene,selected,shift):
    """Previous uploaded bounds, including its floating-point operation order."""
    bounds={};pick={}
    targets=(*ASSEMBLY_COMPONENTS,*dict.fromkeys(m.part_id for m in scene.meshes if m.part_id))
    for focus in targets:
        rows=[m for m in scene.meshes if selected(m,focus)]
        if not rows:continue
        for exploded in (False,True):
            low=[float('inf')]*3;high=[float('-inf')]*3
            for mesh in rows:
                offset=shift(mesh,exploded)
                for axis in range(3):
                    values=mesh.vertices[axis::6]
                    low[axis]=min(low[axis],min(values)+mesh.position[axis]+offset[axis])
                    high[axis]=max(high[axis],max(values)+mesh.position[axis]+offset[axis])
            center=tuple((low[i]+high[i])/2 for i in range(3))
            radius=math.sqrt(sum((high[i]-low[i])**2 for i in range(3)))/2
            bounds[(focus,exploded)]=(center,max(1.,radius))
            pick[(focus,exploded)]=(tuple(low),tuple(high))
    return bounds,pick


class AssemblyUploadTests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start','socket.socket'):
            self.enterContext(patch(target,side_effect=AssertionError('No device, window, process or thread')))

    def test_packing_preserves_exact_little_endian_values_and_order(self):
        values=(-0.,0.,1e-30,-3.25,1.,1e30)
        meshes=(SimpleNamespace(vertices=values),SimpleNamespace(vertices=()),
                SimpleNamespace(vertices=tuple(reversed(values))))
        scene=SimpleNamespace(meshes=meshes)
        expected=struct.pack('<12f',*(values+tuple(reversed(values))))
        self.assertEqual(vertex_bytes(scene),expected)
        self.assertEqual(struct.unpack('<12f',vertex_bytes(scene))[0],0.)
        self.assertEqual(vertex_bytes(SimpleNamespace(meshes=())),b'')
        self.assertEqual(scene.meshes[0].vertices,values)

    def test_packing_does_not_silently_accept_bad_or_overflowing_vertex_values(self):
        for bad in ('invalid',None,object(),1e100):
            scene=SimpleNamespace(meshes=(SimpleNamespace(vertices=(0.,1.,bad)),))
            with self.assertRaises((struct.error,TypeError,OverflowError)):
                vertex_bytes(scene)

    def test_camera_and_pick_bounds_are_exact_for_parts_panels_and_exploded_poses(self):
        shared=box(1.2,23.,48.1)
        meshes=(
            Mesh('far-wall',box(1,400,500),(.1,.2,.3,1.),(30.,0.,0.),'case'),
            Mesh('glass',box(1,400,500),(.2,.3,.4,.2),(-100.,0.,0.),'panel'),
            Mesh('gpu',box(30.5,31.75,200.12),(.4,.5,.6,1.),(-45.4,-67.3,20.2),'gpu',part_id='gpu:0'),
            Mesh('ram-a',shared,(.1,.2,.3,1.),(.25,30.,-40.),'memory',part_id='memory:0'),
            Mesh('ram-b',shared,(.1,.2,.3,1.),(2.75,30.,-40.),'memory',part_id='memory:1'),
            Mesh('rotor',box(2,3,4),(.1,.2,.3,1.),(-20.,80.,70.),'fans',True,-1,(1.,0.,0.),'case-fan:0'),
            Mesh('future',box(2,2,2),(.1,.2,.3,1.),(13.,-70.,99.),'future',part_id='future:1'))
        scene=Scene(meshes,(240.,500.,500.),{})
        node=AssemblyRenderer();node.scene=scene
        self.assertEqual(scene_bounds(scene,node._selected,node._shift),
                         reference_bounds(scene,node._selected,node._shift))
        bounds,pick=scene_bounds(scene,node._selected,node._shift)
        self.assertIn(('memory:0',False),bounds);self.assertIn(('memory:1',True),bounds)
        self.assertIn(('future:1',False),bounds)
        self.assertLess(pick[('case',False)][0][0],-99.,'Case focus must also retain the panel extent')
        self.assertEqual(scene_bounds(Scene((),(1,1,1),{}),node._selected,node._shift),({},{}))

    def test_upload_uses_unchanged_vertices_for_draw_and_triangle_picking(self):
        from test_gpu_insertion_renderer049 import renderer,scene
        value=scene('notebook_color');before=vertex_bytes(value)
        node=renderer(value)
        try:
            self.assertEqual(node.upload_count,1)
            self.assertEqual(node.bounds,reference_bounds(value,node._selected,node._shift)[0])
            allocations=[args for name,args in node.buffer.calls if name=='allocate']
            self.assertEqual(len(allocations),1)
            payload,size=allocations[0]
            self.assertEqual(payload[:len(before)],before);self.assertEqual(len(payload),size)
            node.draw(1000,800,yaw=0,pitch=0,gpu_offset=(-40.,0.,0.),hide_gpu_power=True)
            point=node.project_point((-40.,0.,0.))
            self.assertEqual(node.pick(*point[:2]),'gpu:0')
            self.assertEqual(vertex_bytes(value),before)
        finally:node.close()

    def test_closed_viewport_releases_cpu_meshes_while_its_wrapper_is_still_owned(self):
        import weakref
        from assembly_scene_cache import SceneCache
        from assembly_viewer import AssemblyViewport
        mesh=Mesh('retained',box(1,2,3),(.2,.3,.4,1.))
        value=Scene((mesh,),(100.,200.,300.),{})
        scene_ref,mesh_ref=weakref.ref(value),weakref.ref(mesh)
        cache=SceneCache();cache.base=value;cache.key='owned'
        node=AssemblyRenderer();node.scene=value;node.ranges=[(mesh,0,mesh.vertex_count)]
        node.edge_ranges=[(mesh,mesh.vertex_count,2)]
        owner=SimpleNamespace(_scene=value,_scene_cache=cache,_renderer=node,_gpu_plan={'available':True})
        del value,mesh
        self.assertIsNotNone(scene_ref());self.assertIsNotNone(mesh_ref())
        # This is the same CPU retirement used after release_resources(),
        # including its no-current-context early return. No GL object exists.
        AssemblyViewport._retire_cpu_scene(owner)
        self.assertIsNone(scene_ref());self.assertIsNone(mesh_ref())
        self.assertIsNone(cache.base);self.assertIsNone(node.scene)
        self.assertEqual(owner._scene.meshes,());self.assertEqual(node.ranges,[])
        self.assertEqual(owner._scene.dimensions,(100.,200.,300.))
        AssemblyViewport._retire_cpu_scene(owner)  # Idempotent close cleanup.


if __name__=='__main__':unittest.main()
