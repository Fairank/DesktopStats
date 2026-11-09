"""Model-only feedback and visible-area rasterization, no native surfaces."""
import json
import unittest
import xml.etree.ElementTree as ET
from tests import test_desktop_hardware_models040 as widgets
from tests import test_gpu_model_art041 as artwork


class ModelFeedback043Tests(unittest.TestCase):
    setUpClass=classmethod(widgets.DesktopHardwareModelTests.setUpClass.__func__)
    setUp=widgets.DesktopHardwareModelTests.setUp
    tearDown=widgets.DesktopHardwareModelTests.tearDown
    load=widgets.DesktopHardwareModelTests.load
    find=widgets.DesktopHardwareModelTests.find

    def test_large_cpu_uses_a_thin_load_meter_without_covering_model_markings(self):
        self.load('cpu',300)
        meter=self.find('metricIconPulseCore')
        self.assertTrue(meter.property('modelMeter'))
        self.assertAlmostEqual(meter.height(),.16)
        self.assertGreater(meter.y(),14.)
        self.assertFalse(self.find('metricIconCapacityActivity').property('active'))
        self.assertTrue(self.find('desktopHardwareModelIcon').property('animationRunning'))
        self.assertIsNone(self.controller.thread)

    def test_actual_wide_gpu_raster_uses_visible_height_and_keeps_rotors(self):
        self.load('gpu',300)
        glyph=self.find('metricHardwareGlyphLoader').property('item')
        self.assertTrue(glyph.property('croppedModelArtwork'))
        size=self.find('hardwareGlyphImage').property('sourceSize')
        self.assertLess(size.height(),size.width()*.65)
        layers=glyph.property('fanLayerData');layers=layers.toVariant() if hasattr(layers,'toVariant') else layers
        self.assertEqual(len(layers['rotors']),2)
        self.assertTrue(self.find('desktopHardwareModelIcon').property('gpuFanMotionActive'))


class ModelViewport043Tests(unittest.TestCase):
    setUpClass=classmethod(artwork.GpuModelArt041Tests.setUpClass.__func__)
    setUp=artwork.GpuModelArt041Tests.setUp
    tearDown=artwork.GpuModelArt041Tests.tearDown
    evaluate=artwork.GpuModelArt041Tests.evaluate

    def test_visible_viewbox_preserves_every_original_body_and_rotor_descriptor(self):
        for identity in ('msi-suprim-5090-32g-soc','biostar-radeon-rx7600-va7606rm81','msi-hd5450-md1gd3h-lp'):
            for style in ('miniature','cartoon','notebook_color','notebook_line','sticker','papercut'):
                value=dict(artwork.exact(identity,style),model_mode=True)
                code='Shapes.key('+json.dumps(value)+',"#303a48")'
                full=self.evaluate('Shapes.layers('+code+')')
                cropped=self.evaluate('Shapes.layers('+code+',{size:240,top:60,height:120})')
                self.assertEqual(full['rotors'],cropped['rotors'])
                a=ET.fromstring(artwork.decode(full['baseSource']))
                b=ET.fromstring(artwork.decode(cropped['baseSource']))
                self.assertEqual(b.get('viewBox'),'0 6 24 12')
                self.assertEqual(b.get('height'),'120')
                self.assertEqual([ET.tostring(n) for n in a],[ET.tostring(n) for n in b])

    def test_bad_viewports_never_inject_markup_or_change_legacy_default(self):
        for expression in ('null','{}','{aspect:0}','{aspect:-1}','{aspect:1}','{aspect:Infinity}','{aspect:NaN}','{aspect:"<svg>"}'):
            self.assertEqual(self.evaluate('Shapes.svgHeader('+expression+')'),
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">')


if __name__=='__main__':unittest.main()
