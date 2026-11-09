"""Finite, distinct selection effects without another clock, probes or transforms."""
import copy
import math
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch

from assembly_effects import SelectionEffect,effect_for,effect_sample,policies
from assembly_geometry import Mesh,box
from assembly_style import material_for,style_for
from top_bar_config import HARDWARE_ICON_STYLES


class AssemblyEffectTests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,side_effect=AssertionError('Effects perform no I/O or worker work')))

    def node(self,style='miniature'):
        from assembly_viewer import AssemblyViewport
        state={'visible':True,'minimized':False}
        mesh=Mesh('case',box(10,20,30),(.4,.5,.6,1.),component='case')
        node=SimpleNamespace(_closed=False,_error='',_motion=True,_selection_effects=True,
            _effect=SelectionEffect(),_effect_active=False,_clock_active_state=False,
            _animate=False,_fan_available=False,_rpm=0.,_fan_expiry=0.,_active=False,_phase=0.,
            _focus='all',_scene=SimpleNamespace(meshes=(mesh,),metadata={'visual_style':style}),
            _pending=False,animationActiveChanged=Mock(),update=Mock(),
            isVisible=lambda:state['visible'],window=lambda:SimpleNamespace(isMinimized=lambda:state['minimized']))
        node._update_animation_state=lambda:AssemblyViewport._update_animation_state(node)
        return node,state

    def test_each_style_has_a_distinct_finite_mechanism_and_original_adds_no_expressions(self):
        values=policies()
        self.assertEqual([p['style'] for p in values],list(HARDWARE_ICON_STYLES))
        self.assertEqual(len({p['kind'] for p in values}),13)
        self.assertEqual(len({p['mechanism'] for p in values}),13)
        for policy in values:
            self.assertTrue(350<=policy['duration_ms']<=900)
            self.assertFalse(policy['continuous']);self.assertFalse(policy['geometry_transform'])
            if policy['style'] not in ('cartoon','notebook_smile'):
                self.assertFalse(style_for(policy['style'])['expressions'])
        self.assertFalse(style_for('miniature')['expressions'])

    def test_effects_are_deterministic_bounded_and_cannot_restart_after_completion(self):
        for style in HARDWARE_ICON_STYLES:
            with self.subTest(style=style):
                effect=SelectionEffect();self.assertTrue(effect.start(style,'gpu'))
                self.assertEqual(effect.sample(),effect_sample(style,0,'gpu'))
                ticks=0
                while effect.active and ticks<30:
                    self.assertTrue(effect.advance(34));ticks+=1
                    state=effect.sample()
                    self.assertTrue(0<=state['progress']<=1 and 0<=state['amount']<=1)
                self.assertFalse(effect.active);self.assertLess(ticks,30)
                before=effect.sample();self.assertFalse(effect.advance(100));self.assertEqual(effect.sample(),before)
                self.assertEqual(before['amount'],0.)
        for bad in (None,True,float('nan'),float('inf'),'34'):
            effect=SelectionEffect();effect.start('miniature','gpu')
            self.assertFalse(effect.advance(bad));self.assertEqual(effect.elapsed_ms,0.)
        effect.advance(5000);self.assertEqual(effect.elapsed_ms,136.)

    def test_unknown_style_falls_back_and_policies_are_detached(self):
        for style in (None,False,{},[],'not-a-style'):
            self.assertEqual(effect_for(style)['style'],'miniature')
        record=effect_for('miniature');record['duration_ms']=1
        self.assertEqual(effect_for('miniature')['duration_ms'],620)
        self.assertFalse(effect_sample('cartoon',9999)['active'])
        self.assertFalse(effect_sample('cartoon',100,'all')['active'])

    def test_every_effect_eases_brightness_at_both_endpoints_without_extending_its_lifetime(self):
        for policy in policies():
            duration=policy['duration_ms'];style=policy['style']
            first=effect_sample(style,1,'case');last=effect_sample(style,duration-1,'case')
            self.assertLess(first['amount'],.0001)
            self.assertLess(last['amount'],.0001)
            self.assertGreater(effect_sample(style,duration/2,'case')['amount'],.99)
            self.assertFalse(effect_sample(style,duration,'case')['active'])
            self.assertEqual(effect_sample(style,duration,'case')['amount'],0.)

    def test_selection_fx_clock_runs_without_rpm_and_retires_without_geometry_work(self):
        from assembly_viewer import AssemblyViewport
        node,_state=self.node('inkwash')
        self.assertTrue(AssemblyViewport.preview_effect(node,'case'))
        node.animationActiveChanged.emit.assert_called_once_with(True)
        for _ in range(30):AssemblyViewport.advance_animations(node,34)
        self.assertFalse(node._clock_active_state);self.assertFalse(node._effect_active)
        self.assertFalse(node._active);self.assertEqual(node._phase,0.)
        self.assertFalse(node._pending)
        self.assertEqual(node.animationActiveChanged.emit.call_args.args,(False,))
        count=node.update.call_count
        self.assertFalse(AssemblyViewport.advance_animations(node,34));self.assertEqual(node.update.call_count,count)

    def test_motion_visibility_minimization_error_and_close_cancel_not_pause_a_loop(self):
        from assembly_viewer import AssemblyViewport
        for reason in ('motion','disabled','hidden','minimized','error','closed'):
            node,state=self.node();AssemblyViewport.preview_effect(node,'case')
            if reason=='motion':AssemblyViewport.set_motion_enabled(node,False)
            elif reason=='disabled':AssemblyViewport.set_selection_effects_enabled(node,False)
            else:
                if reason=='hidden':state['visible']=False
                elif reason=='minimized':state['minimized']=True
                elif reason=='error':node._error='graphics failure'
                else:node._closed=True
                AssemblyViewport._update_animation_state(node)
            self.assertFalse(node._effect.active,reason);self.assertFalse(node._clock_active_state,reason)
            node._closed=False;node._error='';node._motion=True;node._selection_effects=True
            state.update(visible=True,minimized=False);AssemblyViewport._update_animation_state(node)
            self.assertFalse(node._clock_active_state,reason)

    def test_invisible_focused_part_does_not_start_an_effect(self):
        from assembly_viewer import AssemblyViewport
        node,_state=self.node();node._focus='gpu'
        self.assertFalse(AssemblyViewport.preview_effect(node,'case'))
        self.assertFalse(node._effect.active)

    def test_static_material_classification_separates_glass_metal_pcb_and_paper(self):
        samples=(Mesh('left-glass',box(1,2,3),(.4,.5,.6,.13),component='panel'),
                 Mesh('cpu-lid',box(1,2,3),(.4,.5,.6,1.),component='cpu'),
                 Mesh('ram-pcb',box(1,2,3),(.4,.5,.6,1.),component='memory'))
        values=[material_for(mesh,'miniature') for mesh in samples]
        self.assertEqual(values[0][2],1.)
        self.assertLess(values[1][1],values[2][1]);self.assertGreater(values[1][0],values[2][0])
        self.assertEqual(material_for(samples[1],'notebook_color'),(0.,1.,0.,0.))
        self.assertTrue(style_for('miniature')['contact_shadow']>0)
        self.assertEqual(style_for('notebook_line')['contact_shadow'],0.)

    def test_vertical_case_focus_cameras_face_actual_front_rotors_and_memory_face(self):
        from assembly_geometry import build_scene
        from assembly_viewer import AssemblyViewport
        from chassis_catalog import CASES
        from hardware_appearance import appearance_for
        vertical=[case for case in CASES if case['layout']=='vertical']
        self.assertEqual(len(vertical),8)
        def direction(camera):
            yaw,pitch=math.radians(camera._yaw),math.radians(camera._pitch)
            return math.sin(yaw)*math.cos(pitch),math.sin(pitch),math.cos(yaw)*math.cos(pitch)
        for case in vertical:
            scene=build_scene(dict(case=case,gpu=dict(appearance=appearance_for('gpu','DUAL-RTX4060-O8G'))))
            camera=SimpleNamespace(_scene=scene,_focus='gpu',update=Mock())
            AssemblyViewport.reset_camera(camera)
            rotor=next(mesh for mesh in scene.meshes if mesh.rotor)
            # Front rotors rotate around the inward face normal. The view
            # should be on the open/front side after the rigid chassis pose.
            self.assertGreater(sum(a*-b for a,b in zip(direction(camera),rotor.axis)),.7,case['id'])
            camera._focus='memory';AssemblyViewport.reset_camera(camera)
            self.assertLess(direction(camera)[1],-.7,case['id'])
            for component in ('cpu','board'):
                camera._focus=component;AssemblyViewport.reset_camera(camera)
                self.assertLess(direction(camera)[0],-.9,case['id'])
        for layout,mount,gpu_angles,memory_angles in (
                ('tower','horizontal',(-34.,-62.),(-20.,12.)),
                ('horizontal','horizontal',(-34.,-62.),(-20.,60.)),
                ('dual_chamber','vertical',(-76.,12.),(-20.,12.))):
            camera=SimpleNamespace(_scene=SimpleNamespace(metadata=dict(case_layout=layout,gpu_mount=mount)),
                                   _focus='gpu',update=Mock())
            AssemblyViewport.reset_camera(camera);self.assertEqual((camera._yaw,camera._pitch),gpu_angles)
            camera._focus='memory';AssemblyViewport.reset_camera(camera)
            self.assertEqual((camera._yaw,camera._pitch),memory_angles)


if __name__=='__main__':unittest.main()
