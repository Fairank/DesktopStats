"""Fan channels stay separate; a pump tachometer never animates radiator fans."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch

from assembly_feedback import cpu_fan_state
from assembly_effects import SelectionEffect
from assembly_geometry import Mesh,Scene,box
from assembly_viewer import AssemblyViewport,mesh_phase,posed_point


class AssemblyFeedbackTests(unittest.TestCase):
    def node(self):
        meshes=tuple(Mesh('rotor',box(2,2,1),(.4,.5,.6,1),component=group,rotor=True,axis=(0,0,1),part_id=part)
                     for group,part in (('gpu',''),('cooler','cooler:cpu'),('cooler','cooler:vrm'),
                                        ('fans','fans:side:0'),('psu','psu:0')))
        node=SimpleNamespace(_closed=False,_error='',_motion=True,_selection_effects=True,
            _effect=SelectionEffect(),_effect_active=False,_clock_active_state=False,
            _animate=True,_active=False,_fan_available=False,_fan_expiry=103.,_rpm=0.,_phase=0.,
            _cpu_available=True,_cpu_expiry=103.,_cpu_rpm=1200.,_cpu_phase=0.,_cpu_tach_usable=True,
            _real_cpu_rotor_parts=('cooler:cpu',),_demo=False,_demo_phase=0.,_focus='all',
            _scene=Scene(meshes,(300,500,500),{}),_visible=True,
            animationActiveChanged=Mock(),update=Mock())
        node.isVisible=lambda:node._visible;node.window=lambda:SimpleNamespace(isMinimized=lambda:False)
        node._update_animation_state=lambda:AssemblyViewport._update_animation_state(node)
        return node

    def test_fresh_header_zero_and_exact_channel_failure_or_expiry(self):
        data=dict(time=100.,cpu_fan_rpm=1200.,metric_timestamps=dict(cpu_fan_rpm=100.))
        self.assertTrue(cpu_fan_state(data,now=100.)['available'])
        data['cpu_fan_rpm']=0;self.assertTrue(cpu_fan_state(data,now=100.)['available'])
        for value in (True,-1,12001,float('nan'),'1200'):
            data['cpu_fan_rpm']=value;self.assertFalse(cpu_fan_state(data,now=100.)['available'])
        data['cpu_fan_rpm']=1200
        for stamp in (True,96.,101.,None,float('inf')):
            data['channel_status']=dict(cpu_fan_rpm=dict(state='available',timestamp=stamp))
            self.assertFalse(cpu_fan_state(data,now=100.)['available'])
        data['channel_status']=dict(cpu_fan_rpm=dict(state='unavailable',timestamp=100.))
        self.assertFalse(cpu_fan_state(data,now=100.)['available'])

    def test_cpu_channel_advances_only_verified_air_rotor_and_never_gpu_case_or_psu(self):
        node=self.node()
        with patch('assembly_viewer.time.monotonic',return_value=100.):
            node._update_animation_state();self.assertTrue(node._active)
            self.assertTrue(AssemblyViewport._step_fans(node,100.))
        self.assertEqual(node._phase,0.);self.assertAlmostEqual(node._cpu_phase,6.)
        phases={'gpu':node._phase,'cooler:cpu':node._cpu_phase}
        values=[mesh_phase(mesh,phases) for mesh in node._scene.meshes]
        self.assertEqual(values,[0.,6.,0.,0.,0.])
        cpu=node._scene.meshes[1]
        self.assertNotEqual(posed_point(cpu,(1,0,0),phase=phases),posed_point(cpu,(1,0,0),phase=0))

    def test_unmatched_aio_header_and_expired_air_channel_stop_without_new_clock(self):
        node=self.node();node._cpu_tach_usable=False
        with patch('assembly_viewer.time.monotonic',return_value=100.):
            node._update_animation_state();self.assertFalse(node._active)
            self.assertFalse(AssemblyViewport._step_fans(node,100.))
        node._cpu_tach_usable=True
        with patch('assembly_viewer.time.monotonic',return_value=100.):node._update_animation_state()
        with patch('assembly_viewer.time.monotonic',return_value=104.):
            self.assertFalse(AssemblyViewport._step_fans(node,100.))
        self.assertFalse(node._cpu_available);self.assertFalse(node._clock_active_state)

    def test_explicit_demo_is_independent_and_visibility_still_retires_clock(self):
        node=self.node();node._cpu_available=False;node._demo=True
        with patch('assembly_viewer.time.monotonic',return_value=100.):
            node._update_animation_state();self.assertTrue(node._active)
            self.assertTrue(AssemblyViewport._step_fans(node,100.))
        self.assertAlmostEqual(node._demo_phase,6.)
        self.assertEqual(node._cpu_phase,0.);self.assertEqual(node._phase,0.)
        node._visible=False;node._update_animation_state()
        self.assertFalse(node._active);self.assertFalse(node._clock_active_state)


if __name__=='__main__':unittest.main()
