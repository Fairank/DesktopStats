"""Render real retained QML artwork, including an oblique PSU rotor plane."""
import os
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QUrl
from PySide6.QtGui import QImage
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]


class AccessoryGlyphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        assert cls.app.platformName() == 'offscreen'

    def test_static_and_retained_rotor_layers_align_and_return_to_zero(self):
        from accessory_art import art, clear_cache
        engine = QQmlEngine()
        warnings = []
        engine.warnings.connect(lambda rows: warnings.extend(row.toString() for row in rows))
        component = QQmlComponent(engine)
        component.setData(b'''import QtQuick
import QtQuick.Window
Window {
    width: 300; height: 210; color: "transparent"
    AccessoryGlyph { objectName: "glyph"; anchors.fill: parent }
}''', QUrl.fromLocalFile(str(ROOT / 'native' / 'glyph-contract.qml')))
        window = component.create()
        self.assertIsNotNone(window, [row.toString() for row in component.errors()])
        glyph = window.findChild(QObject, 'glyph')
        window.show()

        def capture():
            QTest.qWait(45)
            image = window.grabWindow().convertToFormat(QImage.Format_RGBA8888)
            self.assertFalse(image.isNull())
            return image, bytes(image.constBits())

        def changed(left, right):
            return sum(left[index:index+4] != right[index:index+4] for index in range(0, len(left), 4))

        def material_changes(left, right):
            # Separately rasterized SVG layers can differ slightly at antialiased
            # edges. Reject visible displacement rather than one-bit differences.
            return sum(max(abs(left[index+channel]-right[index+channel]) for channel in range(4)) >= 32
                       for index in range(0, len(left), 4))

        try:
            for kind, model in (('psu', 'corsair-rm1000x-2024'),
                                ('cooler', 'noctua-nh-d15-g2'),
                                ('fan', 'phanteks-d30-120-regular')):
                for style in ('miniature', 'cartoon', 'notebook_color', 'notebook_line'):
                    with self.subTest(kind=kind, style=style):
                        result = art(kind, model, style)
                        self.assertTrue(result['rotors'])
                        glyph.setProperty('motion', False)
                        glyph.setProperty('phase', 0)
                        glyph.setProperty('art', result)
                        image, static = capture()
                        occupied = sum(static[index+3] > 0 for index in range(0, len(static), 4))
                        self.assertGreater(occupied, 500)
                        glyph.setProperty('motion', True)
                        _, zero = capture()
                        self.assertLess(material_changes(static, zero), occupied * .04,
                                        'Retained layers must align with the complete SVG')
                        self.assertLess(sum(abs(a-b) for a,b in zip(static, zero))/len(static), 2)
                        glyph.setProperty('phase', 37)
                        _, rotated = capture()
                        self.assertGreater(changed(zero, rotated), 100,
                                           'An explicit phase must visibly turn the fan')
                        glyph.setProperty('phase', 0)
                        _, restored = capture()
                        self.assertEqual(zero, restored)
                        self.assertEqual(image.size(), window.size())
        finally:
            window.hide()
            window.destroy()
            window.deleteLater()
            component.deleteLater()
            engine.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            self.app.processEvents()
            clear_cache()
        self.assertEqual(warnings, [])


if __name__ == '__main__':
    unittest.main()
