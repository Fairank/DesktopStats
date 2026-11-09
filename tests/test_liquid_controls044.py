"""Actual liquid component controls update assembly only; no desktop/GL launches."""
import unittest
from tests import test_assembly_page as fixture


class LiquidControlsTests(unittest.TestCase):
    setUpClass=classmethod(fixture.AssemblyPageTests.setUpClass.__func__)
    setUp=fixture.AssemblyPageTests.setUp
    tearDown=fixture.AssemblyPageTests.tearDown
    show_assembly=fixture.AssemblyPageTests.show_assembly
    find=fixture.AssemblyPageTests.find

    def test_actual_primary_and_secondary_controls_have_detached_model_and_layout_choices(self):
        self.show_assembly();self.controller.changeAssembly('cooler_model','custom-loop-360-reference');self.app.processEvents()
        self.find('assemblyRadiatorChoice_').picked.emit('corsair-xr5-360')
        self.find('assemblyRadiatorFanChoice_').picked.emit('noctua-nf-a12x25-pwm')
        self.find('assemblyRadiatorLayoutChoice_').picked.emit('push_pull')
        self.controller.changeAssembly('gpu_waterblock',True);self.app.processEvents()
        self.find('assemblyRadiatorChoice_secondary_').picked.emit('alphacool-xt45-v2-280')
        self.find('assemblyRadiatorFanChoice_secondary_').picked.emit('noctua-nf-a14-pwm')
        self.find('assemblyRadiatorLayoutChoice_secondary_').picked.emit('none');self.app.processEvents()
        state=self.controller._draft['assembly']
        self.assertEqual(state['radiator_model'],'corsair-xr5-360')
        self.assertEqual(state['radiator_fan_model'],'noctua-nf-a12x25-pwm')
        self.assertEqual(state['radiator_fan_layout'],'push_pull')
        self.assertEqual(state['secondary_radiator_model'],'alphacool-xt45-v2-280')
        self.assertEqual(state['secondary_radiator_fan_model'],'noctua-nf-a14-pwm')
        self.assertEqual(state['secondary_radiator_fan_layout'],'none')
        choices=self.find('assemblyRadiatorFanChoice_').property('model')
        self.assertTrue(any(r['id']=='noctua-nf-a12x25-pwm' for r in choices))
        self.assertFalse(any(r['id']=='noctua-nf-a14-pwm' for r in choices))
        self.assertEqual(self.controller.scopeDirty,dict(desktop=False,preferences=True,topbar=False))

    def test_published_mount_spacing_difference_keeps_reference_choice_and_warns(self):
        self.show_assembly();self.controller.changeAssembly('cooler_model','custom-loop-360-reference')
        self.controller.changeAssembly('radiator_model','xspc-ex280');self.app.processEvents()
        choices=self.find('assemblyRadiatorFanChoice_').property('model')
        self.assertTrue(any(r['id']=='noctua-nf-a14-pwm' for r in choices))
        self.controller.changeAssembly('radiator_fan_model','noctua-nf-a14-pwm');self.app.processEvents()
        self.assertFalse(self.find('assemblyRadiatorFanConflict_').property('visible'))
        self.assertTrue(self.find('assemblyRadiatorMountReview_').property('visible'))
        self.assertTrue(any(r['id']=='noctua-nf-a14-pwm' for r in self.find('assemblyRadiatorFanChoice_').property('model')))
        self.controller.changeAssembly('radiator_fan_layout','none');self.app.processEvents()
        self.assertFalse(self.find('assemblyRadiatorMountReview_').property('visible'))
        self.assertEqual(self.controller._draft['assembly']['radiator_fan_model'],'noctua-nf-a14-pwm')


if __name__=='__main__':unittest.main()
