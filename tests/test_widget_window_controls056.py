"""Real inspector actions keep draft boundaries and reach desktop placement."""
import copy
from pathlib import Path
import unittest

from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlComponent
from PySide6.QtTest import QTest

from desktop_placement import desktop_plan
from tests import test_desktop_hardware_models040 as fixture

ROOT = Path(__file__).resolve().parents[1]


class WidgetWindowControls056Tests(unittest.TestCase):
    setUpClass = classmethod(fixture.DesktopHardwareModelTests.setUpClass.__func__)
    setUp = fixture.DesktopHardwareModelTests.setUp
    tearDown = fixture.DesktopHardwareModelTests.tearDown
    find = fixture.DesktopHardwareModelTests.find
    evaluate = fixture.DesktopHardwareModelTests.evaluate

    def load_inspector(self):
        self.component = QQmlComponent(self.engine)
        self.component.setData(b'''import QtQuick
import "../native" as Product
Window {
    width:780; height:640; visible:false
    QtObject {
        id:layoutState
        property var dimensions:{const draft=stats.draft;return stats.widgetDimensions(inspector.widgetKey)}
        property var contents:stats.draft.widgets[inspector.widgetKey].content
        property bool enabled:false
        property bool manual:false
        property string notice:""
        property string selectedMetric:""
        property var positions:[]
        property var selectedMeta:({label:""})
        property var selectedRect:({x:0,y:0,width:0,height:0})
    }
    Product.WidgetInspector {
        id:inspector;objectName:"modelInspector";anchors.fill:parent
        widgetKey:"gpu";canvas:layoutState;inlineMode:true
    }
}''', QUrl.fromLocalFile(str(ROOT / 'tests/WidgetWindowControls056Fixture.qml')))
        self.window = self.component.create()
        self.assertIsNotNone(self.window, [error.toString() for error in self.component.errors()])
        self.window.show()
        QTest.qWait(10)

    def test_size_actions_preserve_identity_metrics_style_and_saved_state(self):
        self.load_inspector()
        saved = copy.deepcopy(self.controller._saved)
        for kind in ('cpu', 'gpu'):
            self.find('modelInspector').setProperty('widgetKey', kind)
            before = copy.deepcopy(self.controller._draft['widgets'][kind])
            for choice in ('compact', 'standard', 'large'):
                self.evaluate("inspector.chooseModelSize('" + choice + "')")
                self.app.processEvents()
                after = self.controller._draft['widgets'][kind]
                self.assertEqual({k:v for k,v in before.items() if k not in ('width','height','form')},
                                 {k:v for k,v in after.items() if k not in ('width','height','form')})
                geometry = fixture.hardware_model_geometry(after['width'], after['height'], after['content'], after)
                self.assertLessEqual(geometry['image'].bottom, geometry['caption'].y)
                self.assertLessEqual(geometry['caption'].bottom, geometry['readings'][0].y)
                self.assertEqual(self.controller._saved, saved)
            self.assertEqual(self.find('widgetModelSizePreset').property('currentValue'), 'large')
        self.assertIsNone(self.controller.thread)

    def test_custom_mode_and_rejected_size_do_not_silently_replace_preferences(self):
        self.load_inspector()
        before = copy.deepcopy(self.controller._draft)
        self.evaluate("inspector.chooseModelSize('custom')")
        self.app.processEvents()
        self.assertTrue(self.find('widgetWidthInput').isVisible())
        self.assertTrue(self.find('widgetHeightInput').isVisible())
        self.assertFalse(self.find('widgetModelSizePreset').isVisible())
        self.assertEqual(self.controller._draft, before)
        self.evaluate("inspector.chooseModelSize('not-a-preset')")
        self.assertEqual(self.controller._draft, before)
        self.assertFalse(self.controller.setWidgetDimensions('gpu', float('nan'), 240))
        self.assertEqual(self.controller._draft, before)
        self.find('modelInspector').setProperty('widgetKey', 'cpu')
        self.app.processEvents()
        self.assertFalse(self.find('modelInspector').property('preciseModelSize'))
        self.assertTrue(self.find('widgetModelSizePreset').isVisible())

    def test_free_widget_monitor_action_reaches_the_selected_negative_coordinate_screen(self):
        screens = [dict(id='one', native_id='DISPLAY1', label='Screen 1', primary=True,
                        x=0,y=0,width=1920,height=1080),
                   dict(id='two', native_id='DISPLAY2', label='Screen 2', primary=False,
                        x=1920,y=-500,width=1920,height=1440)]
        self.controller.set_screen_inventory(screens)
        self.load_inspector()
        self.find('modelInspector').setProperty('positionOpen', True)
        self.app.processEvents()
        self.assertEqual(self.controller._draft['widgets']['gpu']['dock'], 'free')
        self.assertTrue(self.find('widgetScreen').isVisible())
        saved = copy.deepcopy(self.controller._saved)
        self.find('widgetScreen').picked.emit('two')
        self.app.processEvents()
        self.assertEqual(self.controller._draft['widgets']['gpu']['screen_target'], 'two')
        specs, positions = desktop_plan(self.controller._draft, screens)
        spec = next(row for row in specs if row['id'] == 'gpu')
        x,y = positions['gpu']
        self.assertEqual(spec['screen_id'], 'two')
        self.assertGreaterEqual(x, 1920)
        self.assertGreaterEqual(y, -500)
        self.assertLessEqual(x + spec['width'], 3840)
        self.assertLessEqual(y + spec['height'], 940)
        self.assertEqual(self.controller._saved, saved)
        self.assertIsNone(self.controller.thread)


if __name__ == '__main__':
    unittest.main()
