"""Real software QML: retain identities without retaining sampled sensor state."""
import copy
import math
from pathlib import Path
import time
import unittest

from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlComponent, QQmlExpression, qmlContext
from shiboken6 import getCppPointer

import test_desktop_hardware_models040 as fixture

ROOT = Path(__file__).resolve().parents[1]
SIX = ('miniature', 'cartoon', 'notebook_color', 'notebook_line', 'sticker', 'papercut')


class WidgetEfficiencyTests(unittest.TestCase):
    setUpClass = classmethod(fixture.DesktopHardwareModelTests.setUpClass.__func__)
    find = fixture.DesktopHardwareModelTests.find
    load = fixture.DesktopHardwareModelTests.load

    def setUp(self):
        fixture.DesktopHardwareModelTests.setUp(self)
        self.probe_component = QQmlComponent(self.engine)
        # A plain JS object's counters have no notify signal. QML property
        # counters here would themselves create binding loops and false work.
        self.probe_component.setData(b'''import QtQml
import "../native/HardwareShapes.js" as Shapes
import "../native/MetricEffectClock.js" as Clock
QtObject {
 id:probe
 property var counts:({keys:0,sources:0,layers:0})
 property var original:[]
 property var rememberedAppearance:null
 property var rememberedPackage:null
 function install() {
  original=[Shapes.key,Shapes.source,Shapes.layers]
  Shapes.key=function(a,b) { probe.counts.keys++;return original[0](a,b) }
  Shapes.source=function(a) { probe.counts.sources++;return original[1](a) }
  Shapes.layers=function(a,b) { probe.counts.layers++;return original[2](a,b) }
 }
 function restore() { Shapes.key=original[0];Shapes.source=original[1];Shapes.layers=original[2] }
 function clockCount() { return Clock.activeWindowCount() }
}''', QUrl.fromLocalFile(str(ROOT / 'tests/WidgetEfficiencyProbe.qml')))
        self.probe = self.probe_component.create()
        self.assertIsNotNone(self.probe, [e.toString() for e in self.probe_component.errors()])
        self.probe.install()

    def tearDown(self):
        self.probe.restore()
        self.probe.deleteLater()
        self.probe_component.deleteLater()
        fixture.DesktopHardwareModelTests.tearDown(self)

    def evaluate(self, item, code):
        expression = QQmlExpression(qmlContext(item), item, code)
        result = expression.evaluate()
        self.assertFalse(expression.hasError(), expression.error().toString())
        result = result[0] if isinstance(result, tuple) else result
        return result.toVariant() if hasattr(result, 'toVariant') else result

    def observe(self, kind='gpu'):
        self.load(kind, 360)
        model = self.find('desktopHardwareModel')
        icon = self.find('desktopHardwareModelIcon')
        self.engine.rootContext().setContextProperty('observedModel', model)
        self.engine.rootContext().setContextProperty('observedIcon', icon)
        self.app.processEvents()
        return model, icon

    def emit_sample(self):
        self.controller.dataChanged.emit()
        self.app.processEvents()

    def counts(self):
        return self.probe.property('counts').toVariant().copy()

    def glyph(self):
        return self.find('metricHardwareGlyphLoader').property('item')

    def remember(self):
        self.evaluate(self.probe, 'rememberedAppearance=observedModel.appearance;'
                      'rememberedPackage=observedIcon.processorModelPackage')

    def test_repeated_readings_do_not_recompute_art_identity_or_clone_cpu_package(self):
        model, icon = self.observe('cpu')
        self.remember()
        before = self.counts()
        for value in range(100):
            self.controller._data.update(cpu_usage=float(value), cpu_temp=40.+value/2,
                                         cpu_power=40.+value, time=time.time())
            self.emit_sample()
        self.assertEqual(self.counts(), before)
        self.assertTrue(self.evaluate(self.probe, 'rememberedAppearance===observedModel.appearance'))
        self.assertTrue(self.evaluate(self.probe, 'rememberedPackage===observedIcon.processorModelPackage'))
        state = model.property('snapshot')['hardware_state']
        value = icon.property('hardwareState')
        self.assertEqual(value.toVariant() if hasattr(value, 'toVariant') else value, state)
        self.assertNotEqual(state['thermal'], .5)
        self.assertAlmostEqual(icon.property('loadTarget'), .99)
        self.assertIsNone(self.controller.thread)

    def test_identity_detects_nested_changes_manual_model_confidence_and_style(self):
        model, icon = self.observe()
        self.remember()
        original = copy.deepcopy(model.property('snapshot'))
        changed = copy.deepcopy(original)
        changed['appearance']['fan_profile'].update(render_ready=False, blade_counts=[])
        model.setProperty('snapshot', changed)
        self.app.processEvents()
        self.assertFalse(self.evaluate(self.probe, 'rememberedAppearance===observedModel.appearance'))
        self.assertEqual(self.evaluate(model, 'appearance.fan_profile.render_ready'), False)
        self.assertFalse(icon.property('gpuFanCanAnimate'))
        changed['appearance']['confidence'] = 'unknown'
        model.setProperty('snapshot', copy.deepcopy(changed)); self.app.processEvents()
        self.assertFalse(icon.property('gpuFanCanAnimate'))
        # A manual choice uses the real Controller path and preserves target
        # readings; it cannot be keyed only by the unchanged driver name.
        manual = next(row['id'] for row in self.controller.widgetHardwareChoices('gpu')
                      if row['id'] and row['id'] != original['appearance']['id'])
        self.controller.changeWidget('gpu', 'hardware_model', manual)
        self.emit_sample()
        self.assertEqual(model.property('snapshot')['appearance']['id'], manual)
        self.assertIn(manual, self.glyph().property('geometryKey'))
        self.controller.changeWidget('gpu', 'hardware_icon_style', 'notebook_line')
        self.app.processEvents()
        self.assertIn('|model_notebook_line|', self.glyph().property('geometryKey'))
        self.assertEqual(icon.property('gpuFanRpm'), 1200.)

    def test_cpu_package_known_unknown_and_same_package_new_label_do_not_keep_old_art(self):
        model, icon = self.observe('cpu')
        self.remember()
        self.controller._data['cpu_name'] = 'AMD Ryzen 7 7800X3D'
        self.emit_sample()
        self.assertTrue(self.evaluate(self.probe, 'rememberedPackage===observedIcon.processorModelPackage'))
        self.assertIn('7800X3D', self.glyph().property('geometryKey'))
        for name, package in (('Unidentified processor', ''), ('Intel Core i7-13700KF', 'intel_lga1700_1851'),
                              ('AMD Ryzen 9 9950X', 'amd_am5')):
            with self.subTest(name=name):
                self.controller._data['cpu_name'] = name; self.emit_sample()
                self.assertEqual(icon.property('processorModelPackageId'), package)
                profile = icon.property('processorModelPackage')
                if not package:
                    self.assertIsNone(profile)
                else:
                    self.assertEqual(profile.toVariant()['id'], package)

    def test_six_styles_keep_real_rotors_and_sources_while_rpm_and_heat_change(self):
        model, icon = self.observe()
        for style in SIX:
            with self.subTest(style=style):
                self.controller.changeWidget('gpu', 'hardware_icon_style', style)
                self.app.processEvents(); glyph = self.glyph()
                key = glyph.property('geometryKey')
                self.assertIn('nvidia-founders-rtx5090-32g', key)
                layers = glyph.property('fanLayerData').toVariant()
                self.assertEqual(len(layers['rotors']), 2)
                source = glyph.property('svgSource')
                rotors = [self.find('hardwareFanRotor_'+str(i)) for i in range(2)]
                pointers = [getCppPointer(item)[0] for item in rotors]
                before = self.counts()
                for rpm, temperature in ((0., 30.), (1200., 90.), (1800., 55.)):
                    self.controller._data['gpus']['0'].update(gpu_fan_rpm=rpm, gpu_temp=temperature,
                                                            gpu_fan_rpm_timestamp=time.time())
                    self.emit_sample()
                    self.assertEqual(icon.property('gpuFanRpm'), rpm)
                    self.assertEqual(icon.property('gpuFanMotionActive'), rpm > 0)
                    self.assertEqual(glyph.property('geometryKey'), key)
                    self.assertEqual(glyph.property('svgSource'), source)
                    self.assertEqual(glyph.property('fanLayerData').toVariant(), layers)
                    self.assertEqual([getCppPointer(self.find('hardwareFanRotor_'+str(i)))[0]
                                      for i in range(2)], pointers)
                self.assertEqual(self.counts(), before)
                if style.startswith('notebook_'):
                    from urllib.parse import unquote
                    self.assertIn('hardware-notebook-fe-xbrace', unquote(source.toString()))

    def test_zero_stale_and_wrong_gpu_target_refresh_state_without_an_art_rebuild(self):
        model, icon = self.observe()
        before = self.counts(); source = self.glyph().property('svgSource')
        self.controller._data['gpus']['0'].update(gpu_fan_rpm=0., gpu_fan_rpm_timestamp=time.time())
        self.emit_sample()
        self.assertEqual(icon.property('gpuFanRpm'), 0.)
        self.assertFalse(icon.property('gpuFanMotionActive'))
        self.controller._data['gpus']['0'].update(gpu_fan_rpm=1200., gpu_fan_rpm_timestamp=time.time()-4)
        self.emit_sample()
        self.assertTrue(math.isnan(icon.property('gpuFanRpm')))
        self.assertFalse(icon.property('gpuFanMotionActive'))
        self.assertEqual(self.glyph().property('svgSource'), source)
        self.assertEqual(self.counts(), before)
        self.controller.changeWidget('gpu', 'gpu_target', 'missing')
        self.emit_sample()
        self.assertFalse(model.property('snapshot')['available'])
        self.assertFalse(icon.property('gpuFanMotionActive'))
        self.assertNotEqual(self.glyph().property('svgSource'), source)

    def test_hidden_minimized_and_game_gate_stop_clock_and_restore_fresh_snapshot(self):
        model, icon = self.observe()
        for mode in ('hidden', 'minimized', 'game'):
            with self.subTest(mode=mode):
                if mode == 'hidden': self.window.hide()
                elif mode == 'minimized': self.window.showMinimized()
                else: self.window.setProperty('allowed', False)
                self.app.processEvents()
                self.assertFalse(icon.property('animationRunning'))
                self.assertIsNone(icon.property('clockSubscription'))
                self.assertEqual(self.probe.clockCount(), 0)
                before = self.counts()
                self.controller._data['gpus']['0']['gpu_fan_rpm_timestamp'] = time.time()-4
                self.emit_sample()
                if mode in ('hidden', 'minimized'):
                    self.assertEqual(self.counts(), before)
                if mode == 'hidden': self.window.show()
                elif mode == 'minimized': self.window.showNormal()
                else: self.window.setProperty('allowed', True)
                self.app.processEvents()
                self.assertFalse(icon.property('gpuFanMotionActive'))
                self.controller._data['gpus']['0']['gpu_fan_rpm_timestamp'] = time.time()
                self.emit_sample()
                self.assertTrue(icon.property('gpuFanMotionActive'))
        self.assertIsNone(self.controller.thread)


if __name__ == '__main__':
    unittest.main()
