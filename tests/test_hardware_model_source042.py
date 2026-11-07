"""Actual retained QML models avoid unused complete-card artwork allocations."""
import json
import unittest

from tests import test_hardware_model_motion041 as fixture
from top_bar_config import HARDWARE_ICON_STYLES
from compact_labels import label_options, model_label_options


class HardwareModelSource042Tests(unittest.TestCase):
    setUpClass=classmethod(fixture.HardwareModelMotion041Tests.setUpClass.__func__)
    setUp=fixture.HardwareModelMotion041Tests.setUp
    tearDown=fixture.HardwareModelMotion041Tests.tearDown
    evaluate=fixture.HardwareModelMotion041Tests.evaluate
    assign=fixture.HardwareModelMotion041Tests.assign
    settle=fixture.HardwareModelMotion041Tests.settle
    glyph=fixture.HardwareModelMotion041Tests.glyph

    def test_all_styles_use_the_retained_base_as_the_only_fixed_model_url(self):
        for identity in ('asus-rog-strix-4090-oc','msi-vega64-8g-reference','intel-limited-arc-a770-16g'):
            for style in HARDWARE_ICON_STYLES:
                self.assign('scene.card',fixture.exact(identity,style))
                layers=json.loads(self.evaluate('retainedLayers()'))
                self.assertTrue(layers['baseSource'])
                self.assertEqual(fixture.decode(self.glyph().property('svgSource')),fixture.decode(layers['baseSource']))
                # The API still supplies a complete static illustration for
                # explicit export; the live widget does not retain this URL.
                full=self.evaluate('direct()')
                self.assertIn('<svg',fixture.decode(full))
                self.assertEqual(self.evaluate('clockCount()'),0)
                if layers['rotors']:
                    self.assertNotEqual(fixture.decode(self.glyph().property('svgSource')),fixture.decode(full))

    def test_stopped_rotating_and_reading_only_changes_never_restore_the_extra_url(self):
        self.assign('scene.card',fixture.exact('asus-rog-strix-4090-oc','notebook_line'))
        original=self.glyph().property('svgSource')
        layers=self.evaluate('retainedLayers()')
        for enabled,angle in ((True,0),(True,37),(False,37),(True,37),(True,0),(False,0)):
            self.assign('scene.retained',enabled);self.assign('scene.angle',angle)
            self.assertEqual(self.glyph().property('svgSource'),original)
            self.assertEqual(self.evaluate('retainedLayers()'),layers)
            self.assertEqual(self.evaluate('clockCount()'),0)


class ModelMetricLabels042Tests(unittest.TestCase):
    def test_contextual_labels_stay_short_without_losing_power_source_semantics(self):
        self.assertEqual(model_label_options('gpu_temp','GPU 温度','zh-CN','gpu'),('温度',))
        self.assertEqual(model_label_options('gpu_power','GPU power','en','gpu'),('Power',))
        for metric in ('cpu_power','gpu_asic_power','gpu_fan_rpm','storage_temp'):
            self.assertEqual(model_label_options(metric,'complete source','en'),label_options(metric,'complete source','en'))
        for kind,metric in (('cpu','gpu_temp'),('gpu','cpu_temp'),('cpu','gpu_usage'),('gpu','cpu_usage')):
            self.assertEqual(model_label_options(metric,'complete source','en',kind),label_options(metric,'complete source','en'))


if __name__=='__main__':unittest.main()
