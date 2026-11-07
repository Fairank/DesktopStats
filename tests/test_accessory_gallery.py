"""Actual lazy gallery, retained icon motion and preference isolation offscreen."""
import copy
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE','Basic')
from PySide6.QtCore import QCoreApplication,QEvent,QObject,QPointF,Qt,QUrl
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlComponent,QQmlEngine,qmlRegisterType
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import native_controller as controls
from native_card import HardwareCard
from native_surface import MaterialSurface
from stats_config import DEFAULT

ROOT=Path(__file__).resolve().parents[1]

def value(obj,name):
    result=obj.property(name)
    return result.toVariant() if hasattr(result,'toVariant') else result


class AccessoryGalleryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        assert cls.app.platformName()=='offscreen'
        fonts=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
        for name in ('SegUIVar.ttf','segoeui.ttf','msyh.ttc','YuGothM.ttc','malgun.ttf'):
            if (fonts/name).is_file():QFontDatabase.addApplicationFont(str(fonts/name))
        qmlRegisterType(HardwareCard,'DesktopStats',1,0,'HardwareCard')
        qmlRegisterType(MaterialSurface,'DesktopStats',1,0,'MaterialSurface')

    def setUp(self):
        self.enterContext(patch('ctypes.WinDLL',side_effect=AssertionError('No native API')))
        self.enterContext(patch('subprocess.Popen',side_effect=AssertionError('No process')))
        self.enterContext(patch('chassis_identity.snapshot',return_value=dict(state='unavailable',enclosures=[],baseboards=[])))
        self.enterContext(patch('memory_identity.modules',return_value=[]))
        self.enterContext(patch.object(controls,'load',return_value=copy.deepcopy(DEFAULT)))
        self.enterContext(patch.object(controls,'save'))
        self.controller=controls.Controller()
        self.controller._data=dict(cpu_name='Intel Core i7-13700KF')
        self.engine=QQmlEngine();self.warnings=[]
        self.engine.warnings.connect(lambda rows:self.warnings.extend(row.toString() for row in rows))
        self.engine.rootContext().setContextProperty('stats',self.controller)
        self.component=QQmlComponent(self.engine,QUrl.fromLocalFile(str(ROOT/'native/Settings.qml')))
        self.window=self.component.create()
        self.assertIsNotNone(self.window,[row.toString() for row in self.component.errors()])
        self.window.setProperty('nativeHosted',True)

    def tearDown(self):
        self.window.hide();self.window.destroy();self.window.deleteLater()
        self.component.deleteLater();self.engine.deleteLater();self.controller.close();self.controller.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents()
        self.assertEqual(self.warnings,[])

    def find(self,name):
        result=self.window.findChild(QObject,name)
        if result is None:
            pending=[self.window.contentItem()]
            while pending:
                item=pending.pop()
                if item.objectName()==name:result=item;break
                pending.extend(item.childItems())
        self.assertIsNotNone(result,name)
        return result

    def open_gallery(self,width=1280,height=760):
        self.window.resize(width,height);self.window.setProperty('page',5);self.window.show();QTest.qWait(100)
        self.find('browseAssemblyModelsButton').clicked.emit();QTest.qWait(80)
        return self.find('accessoryGallery')

    def test_a_bar_only_start_does_not_load_the_accessory_library(self):
        self.assertNotIn('accessory_art',sys.modules)
        self.assertFalse(self.controller._accessory_gallery_active)
        self.assertIsNone(self.find('accessoryGalleryLoader').property('item'))
        for _ in range(3):self.controller.dataChanged.emit()
        self.assertNotIn('accessory_art',sys.modules)

    def test_b_every_category_style_and_search_preserves_saved_and_draft_settings(self):
        before=copy.deepcopy(self.controller.draft);saved=copy.deepcopy(self.controller.saved)
        gallery=self.open_gallery()
        self.assertTrue(self.controller._accessory_gallery_active)
        self.assertNotIn('assembly_geometry',sys.modules)
        self.assertNotIn('assembly_viewer',sys.modules)
        from top_bar_config import HARDWARE_ICON_STYLES
        for category,count in (('case',64),('cooler',42),('psu',21),('fan',38)):
            gallery.setProperty('category',category);QTest.qWait(25)
            self.assertEqual(len(value(gallery,'entries')),count)
            for style in HARDWARE_ICON_STYLES:
                gallery.setProperty('selectedStyle',style);self.app.processEvents()
                self.assertEqual(len(value(gallery,'filtered')),count)
        gallery.setProperty('category','psu');gallery.setProperty('query','Fanless');QTest.qWait(40)
        self.assertEqual(len(value(gallery,'filtered')),1)
        self.assertEqual(self.controller.draft,before);self.assertEqual(self.controller.saved,saved)
        self.assertFalse(gallery.property('motionActive'))
        self.assertIsNone(self.find('accessoryDemoClock').property('subscription'))

    def test_c_demo_uses_one_retained_clock_and_close_releases_caches(self):
        import accessory_art
        gallery=self.open_gallery();gallery.setProperty('category','fan');QTest.qWait(50)
        with patch('accessory_art.art',wraps=accessory_art.art) as generate:
            gallery.setProperty('selectedStyle','notebook_line');QTest.qWait(30)
            calls=generate.call_count
            gallery.setProperty('demoMotion',True);start=gallery.property('phase');QTest.qWait(160)
            self.assertTrue(gallery.property('motionActive'));self.assertGreater(gallery.property('phase'),start)
            self.assertEqual(generate.call_count,calls,'Animation must transform retained images')
            gallery.setProperty('demoMotion',False);QTest.qWait(40);phase=gallery.property('phase');QTest.qWait(80)
            self.assertEqual(gallery.property('phase'),phase)
        gallery.setProperty('category','psu');gallery.setProperty('query','Fanless');gallery.setProperty('demoMotion',True)
        QTest.qWait(80);self.assertFalse(gallery.property('motionActive'))
        self.find('closeAccessoryGallery').clicked.emit();QTest.qWait(160)
        self.assertFalse(self.controller._accessory_gallery_active)
        self.assertIsNone(self.find('accessoryGalleryLoader').property('item'))
        self.assertEqual(accessory_art.cache_info()['entries'],0)

    def test_d_narrow_languages_escape_and_hiding_retire_the_gallery(self):
        gallery=self.open_gallery(720,600)
        for language in ('zh-CN','en','de','fr','ja','ko','zh-TW','es'):
            self.controller.change('language',language);QTest.qWait(25)
            self.assertLessEqual(gallery.property('width'),720)
            self.assertGreater(self.find('accessoryModelGrid').height(),100)
        QTest.keyClick(self.window,Qt.Key_Escape);QTest.qWait(180)
        self.assertTrue(self.window.isVisible(),'Escape closes the gallery, not the settings window')
        self.assertFalse(self.window.property('accessoryGalleryOpen'))
        self.find('browseAssemblyModelsButton').clicked.emit();QTest.qWait(60)
        self.window.hide();QTest.qWait(80)
        self.assertFalse(self.controller._accessory_gallery_active)
        self.assertIsNone(self.find('accessoryGalleryLoader').property('item'))

    def test_e_download_is_explicit_and_selects_only_the_requested_collection(self):
        from PySide6.QtGui import QDesktopServices
        from product_version import VERSION
        with patch.object(QDesktopServices,'openUrl',return_value=True) as browser:
            gallery=self.open_gallery()
            self.assertFalse(browser.called)
            gallery.setProperty('category','psu');self.find('accessoryDownload').clicked.emit()
            self.assertEqual(browser.call_count,1)
            self.assertEqual(browser.call_args.args[0].toString(),
                'https://github.com/Fairank/DesktopStats/releases/download/v'+VERSION+'/DesktopStats-'+VERSION+'-psus-SVG.zip')
            self.controller.downloadAccessoryArt('../bad')
            self.assertEqual(browser.call_count,1)


if __name__=='__main__':unittest.main()
