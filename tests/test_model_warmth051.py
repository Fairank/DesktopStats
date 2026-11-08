"""Actual frameless CPU model heat keeps clear corners and real package aspect."""
import unittest

from PySide6.QtTest import QTest
from test_desktop_hardware_models040 import DesktopHardwareModelTests as Fixture

SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')


class ModelWarmthTests(unittest.TestCase):
    setUpClass=classmethod(Fixture.setUpClass.__func__)
    setUp=Fixture.setUp
    tearDown=Fixture.tearDown
    find=Fixture.find
    load=Fixture.load
    evaluate=Fixture.evaluate

    def test_large_heat_retains_actual_package_aspect_and_clear_artwork_corners(self):
        self.load('cpu',360)
        self.controller._data.update(cpu_temp=100.,cpu_usage=95.)
        for name,aspect in (('Intel Core i7-13700KF',37.5/45.),('AMD Ryzen 9 9950X',1.),('Unidentified processor',1.)):
            self.controller._data['cpu_name']=name
            for style in SIX:
                with self.subTest(name=name,style=style):
                    self.controller.changeWidget('cpu','hardware_icon_style',style)
                    self.controller.dataChanged.emit();self.app.processEvents()
                    icon=self.find('desktopHardwareModelIcon')
                    body=self.find('metricIconProcessorBodyWarmth')
                    self.assertTrue(icon.property('modelMode'))
                    self.assertAlmostEqual(body.width()/body.height(),aspect,places=5)
                    halo=self.find('metricIconProcessorHalo_0')
                    self.assertLess(halo.width()-body.width(),2.)
                    # Isolate the heat layer. Electrical arcs are deliberately
                    # allowed outside the chip and must not be mistaken for a
                    # rectangular heat backdrop in the complete widget image.
                    layer=self.find('metricIconProcessorWarmth').property('item')
                    grab=layer.grabToImage()
                    for _ in range(30):
                        if not grab.image().isNull():break
                        QTest.qWait(10)
                    pixels=grab.image();self.assertFalse(pixels.isNull())
                    # Stay outside the physical19.7/24-unit halo envelope.
                    # At10%, Qt software AA can legitimately touch the square
                    # AMD package's rounded halo, so that is not a clear corner.
                    points=((x if left else 1-x,y if top else 1-y)
                            for x in (.02,.035,.05) for y in (.02,.035,.05)
                            for left in (True,False) for top in (True,False))
                    self.assertTrue(all(pixels.pixelColor(int(x*pixels.width()),int(y*pixels.height())).alpha()==0
                                        for x,y in points),
                                    'A frameless CPU must not paint a rectangular heat backdrop at the artwork corners')
                    self.assertGreater(pixels.pixelColor(pixels.width()//2,pixels.height()//2).alpha(),0,
                                       'Keep real heat feedback rather than hiding the entire layer')

    def test_small_bar_heat_geometry_keeps_its_existing_dimensions(self):
        self.load('cpu')
        icon=self.find('desktopHardwareModelIcon');icon.setProperty('modelMode',False)
        self.app.processEvents()
        body=self.find('metricIconProcessorBodyWarmth');halo=self.find('metricIconProcessorHalo_0')
        self.assertEqual((body.width(),body.height()),(12.,12.))
        self.assertAlmostEqual(halo.width()-body.width(),9.6)


del Fixture  # Imported unittest classes must not be discovered a second time.


if __name__=='__main__':unittest.main()
