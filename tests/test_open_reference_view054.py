"""Five source-executed view controls; no Qt import, window or GL operation."""
import argparse
import ast
import copy
import ctypes
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import sys
import time
from types import SimpleNamespace
import unittest

HERE=Path(__file__).resolve().parent
ROOT=Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Scene:
    meshes:tuple
    dimensions:tuple=(120.,120.,25.)
    metadata:dict=None


class Signal:
    def __init__(self):self.values=[]
    def emit(self,*args):self.values.append(args)


class Base:
    NoPartialUpdate=0
    def __init__(self,parent=None):
        self.componentSelected=Signal();self.focusChanged=Signal()
        self.sceneChanged=Signal();self.animationActiveChanged=Signal()
        self.updated=0;self.motion_updates=0;self.base_closed=0
    def setFormat(self,*_):pass
    def setUpdateBehavior(self,*_):pass
    def setMinimumSize(self,*_):pass
    def setFocusPolicy(self,*_):pass
    def setAccessibleName(self,*_):pass
    def update(self):self.updated+=1
    def _update_animation_state(self):self.motion_updates+=1
    def closeEvent(self,event):self.base_closed+=1


class Renderer:
    def __init__(self):self.forgotten=0;self._pick_state=None
    def forget_scene(self):self.forgotten+=1
    @staticmethod
    def _selected(mesh,focus):return focus=='all' or focus==mesh.component or focus==mesh.part_id


class Cache:
    def __init__(self):self.cleared=0
    def clear(self):self.cleared+=1


class Cancel:
    def __init__(self):self.calls=0
    def cancel(self):self.calls+=1;return False
    def reset(self):self.calls+=1;return False


def actual_view():
    source=ast.parse((ROOT/'assembly_viewer.py').read_text('utf-8'))
    cls=next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='AssemblyViewport')
    wanted={'__init__','set_reference_scene','closeEvent'}
    methods=[copy.deepcopy(n) for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in wanted]
    calls=[]
    def factory(spec):calls.append(('factory',spec));return Scene(())
    def plan(scene):calls.append(('mechanical-plan',scene));return {}
    scope=dict(QOpenGLWidget=Base,Qt=SimpleNamespace(StrongFocus=0),surface_format=lambda:None,
               Scene=Scene,AssemblyRenderer=Renderer,build_scene=factory,SceneCache=Cache,
               GpuInsertion=Cancel,PartMotion=Cancel,SelectionEffect=Cancel,insertion_plan=plan)
    shell=ast.ClassDef(name='AssemblyViewport',bases=[ast.Name(id='QOpenGLWidget',ctx=ast.Load())],
                       keywords=[],body=methods,decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[shell],type_ignores=[])),
                 'actual-viewer-methods-no-Qt', 'exec'),scope)
    view=scope['AssemblyViewport']
    view._reset_part_motion=lambda self:False
    return view,calls


def mesh(identity='reference:frame',value=1.):
    owner=struct.pack('<18f',value,0,0,0,0,1,0,value,0,0,0,1,0,0,value,0,0,1)
    return SimpleNamespace(vertices=memoryview(owner).cast('f'),part_id=identity,component='fans')


class ReferenceViewControls(unittest.TestCase):
    def test_reference_constructor_bypasses_default_factory_and_preserves_normal_default(self):
        view,calls=actual_view();reference=Scene((mesh(),))
        actual=view(reference_scene=reference)
        self.assertIs(actual._scene,reference);self.assertEqual(calls,[])
        self.assertTrue(actual._reference_scene_mode)
        self.assertFalse(actual._motion);self.assertFalse(actual._selection_effects)
        ordinary=view()
        self.assertFalse(ordinary._reference_scene_mode)
        self.assertTrue(ordinary._motion);self.assertTrue(ordinary._selection_effects)
        self.assertEqual([kind for kind,_ in calls],['factory','mechanical-plan'])

    def test_palette_scene_replacement_keeps_geometry_and_valid_part_visibility_without_factory(self):
        view,calls=actual_view();physical=mesh();first=Scene((physical,))
        actual=view(reference_scene=first)
        actual._hidden_parts=frozenset(('reference:frame','reference:missing'))
        actual._selected='reference:missing';actual._focus='reference:missing'
        following=Scene((physical,),metadata={'visual_style':'notebook_line'})
        actual.set_reference_scene(following)
        self.assertIs(actual._scene,following)
        self.assertIs(actual._scene.meshes[0].vertices,physical.vertices)
        self.assertEqual(actual._hidden_parts,frozenset(('reference:frame',)))
        self.assertEqual((actual._selected,actual._focus),('','all'))
        self.assertEqual(actual._renderer.forgotten,1)
        self.assertEqual(actual._scene_cache.cleared,1)
        self.assertEqual(calls,[])
        self.assertFalse(actual._motion);self.assertFalse(actual._animate)
        self.assertEqual(actual.sceneChanged.values,[()])
        self.assertEqual(actual.updated,1)

    def test_reference_setter_rejects_wrong_mode_and_empty_input_before_mutation(self):
        view,calls=actual_view();ordinary=view();calls.clear()
        with self.assertRaises(RuntimeError):ordinary.set_reference_scene(Scene((mesh(),)))
        actual=view(reference_scene=Scene((mesh(),)))
        for invalid in (None,{},Scene(())):
            with self.assertRaises(ValueError):actual.set_reference_scene(invalid)
        self.assertEqual(actual._renderer.forgotten,0);self.assertEqual(calls,[])
        # Queued UI actions must stop after hiding or a guard change, even if
        # the object and loaded data still exist until deferred deletion.
        tree=ast.parse((ROOT/'open_reference_window054.py').read_text('utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='OpenReferenceWindow')
        node=copy.deepcopy(next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_can_interact'))
        scope={}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'actual-reference-ui-guard','exec'),scope)
        state=dict(closing=False,guard=False,error=False,visible=True,minimized=False,allowed=True)
        owner=SimpleNamespace(isVisible=lambda:state['visible'],isMinimized=lambda:state['minimized'],
                              property=lambda _name:state['allowed'])
        for blocked in (None,'closing','guard','error','visible','minimized','allowed'):
            following=dict(state)
            if blocked is not None:following[blocked]=blocked not in ('visible','allowed')
            owner._closing=following['closing'];owner._guard_hidden=following['guard'];owner._renderer_failed=following['error']
            owner.isVisible=lambda value=following['visible']:value
            owner.isMinimized=lambda value=following['minimized']:value
            owner.property=lambda _name,value=following['allowed']:value
            self.assertEqual(scope[node.name](owner),blocked is None)

    def test_typed_packing_preserves_f32_bytes_and_uses_old_path_for_mutable_or_non_native_owners(self):
        tree=ast.parse((ROOT/'assembly_viewer.py').read_text('utf-8'))
        node=copy.deepcopy(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='renderer_vertex_bytes'))
        calls=[]
        scope=dict(sys=SimpleNamespace(byteorder='little'),vertex_bytes=lambda scene:calls.append(scene) or b'legacy')
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'actual-typed-pack','exec'),scope)
        function=scope[node.name];a,b=mesh(value=-0.),mesh(value=.125)
        scene=Scene((a,b))
        self.assertEqual(function(scene),bytes(a.vertices.cast('B'))+bytes(b.vertices.cast('B')))
        self.assertEqual(calls,[])
        mutable=SimpleNamespace(vertices=memoryview(bytearray(bytes(a.vertices.cast('B')))).cast('f'))
        self.assertEqual(function(Scene((mutable,))),b'legacy')
        readonly_mutable=SimpleNamespace(vertices=mutable.vertices.toreadonly())
        self.assertEqual(function(Scene((readonly_mutable,))),b'legacy')
        scope['sys'].byteorder='big'
        self.assertEqual(function(scene),b'legacy');self.assertEqual(len(calls),3)

    def test_reference_close_retires_cpu_even_when_native_release_fails_and_window_drops_owner(self):
        view,_=actual_view();actual=view(reference_scene=Scene((mesh(),)))
        def failure():raise RuntimeError('Synthetic lost context')
        actual.release_resources=failure
        retired=[]
        actual._retire_cpu_scene=lambda:retired.append(True)
        with self.assertRaises(RuntimeError):actual.closeEvent(None)
        self.assertEqual(retired,[True]);self.assertEqual(actual.base_closed,1)
        tree=ast.parse((ROOT/'open_reference_window054.py').read_text('utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='OpenReferenceWindow')
        node=copy.deepcopy(next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_dispose'))
        scope={}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'actual-window-dispose','exec'),scope)
        owner=SimpleNamespace(_closing=False,_model=object(),_styled_scene=object(),
                              _close_owned_popups=lambda:None,viewport=SimpleNamespace(close=failure))
        scope[node.name](owner)
        self.assertTrue(owner._closing);self.assertIsNone(owner._model);self.assertIsNone(owner._styled_scene)
        self.assertEqual(owner._close_error,'Synthetic lost context')


if __name__=='__main__':
    unittest.main()
