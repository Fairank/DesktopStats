"""Actual small model widgets keep full identities and fixed sampled geometry."""
import copy
from pathlib import Path
import unittest

from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlComponent,QQmlExpression,qmlContext
from PySide6.QtTest import QTest,QSignalSpy
from tests import test_desktop_hardware_models040 as fixture
from responsive_layout import hardware_model_geometry

ROOT=Path(__file__).resolve().parents[1]


class HardwareModelLayout041Tests(unittest.TestCase):
    setUpClass=classmethod(fixture.DesktopHardwareModelTests.setUpClass.__func__)
    setUp=fixture.DesktopHardwareModelTests.setUp
    tearDown=fixture.DesktopHardwareModelTests.tearDown
    load=fixture.DesktopHardwareModelTests.load
    find=fixture.DesktopHardwareModelTests.find
    evaluate=fixture.DesktopHardwareModelTests.evaluate

    def test_long_gpu_caption_fits_two_lines_in_actual_240_widget(self):
        self.load('gpu',240)
        caption=self.find('desktopHardwareModelName')
        self.assertEqual(caption.property('text'),'NVIDIA GeForce RTX 5090 Founders Edition')
        self.assertGreaterEqual(caption.property('font').pixelSize(),11)
        self.assertEqual(caption.property('maximumLineCount'),2)
        self.assertGreater(caption.property('lineCount'),1)
        self.assertFalse(caption.property('truncated'))
        self.assertLessEqual(caption.property('contentHeight'),caption.height())
        geometry=hardware_model_geometry(240,240,self.controller.draft['widgets']['gpu']['content'],self.controller.draft['widgets']['gpu'])
        self.assertLessEqual(geometry['image'].bottom,caption.y())
        self.assertLessEqual(caption.y()+caption.height(),geometry['readings'][0].y)

    def test_source_and_geometry_do_not_change_with_sampled_values_or_rpm_phase(self):
        self.load('gpu',360)
        glyph=self.find('metricHardwareGlyphLoader').property('item')
        source=glyph.property('svgSource').toString();key=glyph.property('geometryKey')
        spy=QSignalSpy(glyph.svgSourceChanged)
        image=self.find('desktopHardwareArtwork');bounds=(image.x(),image.y(),image.width(),image.height())
        self.assertIn('|model_miniature|',key)
        for index in range(12):
            data=fixture.sample();data['gpus']['0'].update(gpu_usage=20+index,gpu_temp=40+index,gpu_power=150+index,gpu_fan_rpm=900+index*10)
            self.controller._data=data;self.controller.dataChanged.emit();self.app.processEvents()
            self.assertEqual(glyph.property('svgSource').toString(),source)
            self.assertEqual(glyph.property('geometryKey'),key)
            self.assertEqual((image.x(),image.y(),image.width(),image.height()),bounds)
        QTest.qWait(70)
        self.assertEqual(spy.count(),0)
        self.assertIsNone(self.controller.thread)

    def test_oversized_model_caps_texture_edges_without_an_oversized_window(self):
        self.load('gpu',240)
        glyph=self.find('metricHardwareGlyphLoader').property('item')
        normal=self.find('hardwareGlyphImage').property('sourceSize')
        self.assertLess(normal.width(),2048)
        self.window.hide()
        expression=QQmlExpression(qmlContext(glyph),glyph,'anchors.fill=undefined;width=8192;height=4320')
        expression.evaluate();self.assertFalse(expression.hasError(),expression.error().toString())
        self.app.processEvents()
        image=self.find('hardwareGlyphImage')
        self.assertEqual(image.property('sourceSize').width(),2048)
        self.assertEqual(image.property('sourceSize').height(),2048)
        pending=[glyph];rotors=[]
        while pending:
            item=pending.pop();pending.extend(item.childItems())
            if item.objectName().startswith('hardwareFanRotorImage_'):rotors.append(item)
        self.assertEqual(len(rotors),2)
        for rotor in rotors:self.assertLessEqual(rotor.property('sourceSize').width(),1024)
        self.assertEqual((self.window.width(),self.window.height()),(240,240))
        self.assertFalse(self.find('desktopHardwareModelIcon').property('animationRunning'))


class ModelGeometry041Tests(unittest.TestCase):
    def test_two_line_identity_and_readings_are_disjoint_for_titles_sizes_and_metrics(self):
        prefs=fixture.configuration()['widgets']
        for kind in ('cpu','gpu'):
            for title in (True,False):
                for size in ((220,220),(240,240),(360,360),(520,260)):
                    for count in (2,3):
                        value=copy.deepcopy(prefs[kind]);value['show_title']=title
                        g=hardware_model_geometry(*size,value['content'][:count],value)
                        self.assertGreaterEqual(g['caption'].height,32)
                        self.assertLessEqual(g['image'].bottom,g['caption'].y)
                        self.assertLessEqual(g['caption'].bottom,g['readings'][0].y)
                        self.assertLessEqual(g['readings'][0].bottom,size[1])


if __name__=='__main__':unittest.main()
