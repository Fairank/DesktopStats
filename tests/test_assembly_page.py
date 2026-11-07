"""Actual assembly settings page, isolated offscreen with synthetic identities."""
import copy
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPointF, Qt, QUrl
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlComponent, QQmlEngine, qmlRegisterType
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

import native_controller as controls
from localization import LANGUAGES, MESSAGES
from native_card import HardwareCard
from native_surface import MaterialSurface
from stats_config import DEFAULT

ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = dict(state="available", system=dict(manufacturer="Example"),
                enclosures=[], baseboards=[])


class AssemblyPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        assert cls.app.platformName() == "offscreen", "Never open a native test window"
        fonts = Path(os.environ.get("WINDIR", "C:/Windows"))/"Fonts"
        for name in ("SegUIVar.ttf", "segoeui.ttf", "seguisb.ttf", "msyh.ttc", "msyhbd.ttc",
                     "YuGothM.ttc", "malgun.ttf"):
            font = fonts/name
            if font.is_file():
                QFontDatabase.addApplicationFont(str(font))
        qmlRegisterType(HardwareCard, "DesktopStats", 1, 0, "HardwareCard")
        qmlRegisterType(MaterialSurface, "DesktopStats", 1, 0, "MaterialSurface")

    def setUp(self):
        if os.environ.get('DESKTOP_STATS_ASSEMBLY_PAGE_PROOF'):
            Path(os.environ['DESKTOP_STATS_ASSEMBLY_PAGE_PROOF']).mkdir(parents=True,exist_ok=True)
        self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native API")))
        self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.enterContext(patch.object(controls, "save"))
        self.snapshot = self.enterContext(patch("chassis_identity.snapshot", return_value=copy.deepcopy(FIRMWARE)))
        self.modules = self.enterContext(patch("memory_identity.modules", return_value=[
            dict(manufacturer="Kingston", part_number="KF560C36BBE-16", form_factor="dimm")]))
        value = copy.deepcopy(DEFAULT)
        value.update(language="zh-CN", theme="light")
        with patch.object(controls, "load", return_value=value):
            self.controller = controls.Controller()
        self.controller._data = dict(cpu_name="Intel Core i7-13700KF", gpus={"0": dict(
            gpu_name="NVIDIA GeForce RTX 5090", gpu_usage=24)})
        self.engine = QQmlEngine()
        self.warnings = []
        self.engine.warnings.connect(lambda rows: self.warnings.extend(row.toString() for row in rows))
        self.engine.rootContext().setContextProperty("stats", self.controller)
        self.component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(ROOT / "native/Settings.qml")))
        self.window = self.component.create()
        self.assertIsNotNone(self.window, [error.toString() for error in self.component.errors()])
        self.window.setProperty("nativeHosted", True)

    def tearDown(self):
        self.window.hide()
        self.window.destroy()
        self.window.deleteLater()
        self.component.deleteLater()
        self.engine.deleteLater()
        self.controller.close()
        self.controller.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        self.assertEqual(self.warnings, [])

    def find(self, name):
        result = self.window.findChild(QObject, name)
        if result is None:
            pending = [self.window.contentItem()]
            while pending:
                item = pending.pop()
                if item.objectName() == name:
                    result = item
                    break
                pending.extend(item.childItems())
        self.assertIsNotNone(result, name)
        return result

    def click(self, item):
        point = item.mapToScene(QPointF(item.width()/2, item.height()/2)).toPoint()
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point)
        QTest.qWait(25)

    def show_assembly(self, width=1280, height=760):
        self.window.resize(width, height)
        self.window.setProperty("page", 5)
        self.window.show()
        QTest.qWait(80)

    def test_page_is_lazy_and_navigation_selection_tracks_assembly_and_preferences(self):
        self.window.setProperty("page", 5)
        self.app.processEvents()
        self.snapshot.assert_not_called()
        self.show_assembly()
        self.snapshot.assert_called_once()
        self.modules.assert_called_once()
        self.assertTrue(self.controller.assemblySummary["initialized"])
        self.assertFalse(self.find("settingsInspectTimer").property("running"))
        selection = self.find("sidebarSelectionSurface")
        for page in (1, 5, 4, 3, 0):
            self.click(self.find("nav_" + str(page)))
            QTest.qWait(230)  # Let the existing sidebar selection transition finish.
            row = self.find("nav_" + str(page))
            self.assertAlmostEqual(selection.y(), row.y(), delta=.01)
        self.snapshot.assert_called_once()
        self.assertNotIn("assembly_viewer", sys.modules)

    def test_case_choice_changes_only_preferences_and_open_is_a_request(self):
        self.show_assembly()
        before = copy.deepcopy(self.controller.saved)
        choice = self.find("assemblyCaseChoice")
        choice.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_End)
        QTest.keyClick(self.window, Qt.Key_Return)
        QTest.qWait(30)
        selected = self.controller.draft["assembly"]["case_model"]
        self.assertTrue(selected)
        self.assertEqual(self.controller.assemblySummary["identity_state"], "manual")
        self.assertEqual(self.controller.saved, before)
        self.assertEqual(self.controller.scopeDirty, dict(desktop=False, preferences=True, topbar=False))
        opened = QSignalSpy(self.controller.assemblyViewRequested)
        button = self.find("openAssemblyViewButton")
        self.assertTrue(button.isEnabled())
        button.clicked.emit()
        self.assertEqual(opened.count(), 1)
        self.assertEqual(opened.at(0)[0]["case"]["id"], selected)
        self.assertNotIn("assembly_viewer", sys.modules)

    def test_widths_and_languages_keep_controls_in_content_and_auto_choice_translated(self):
        self.show_assembly()
        proof = os.environ.get("DESKTOP_STATS_ASSEMBLY_PAGE_PROOF")
        if proof:
            Path(proof).mkdir(parents=True, exist_ok=True)
        sizes = [(1280,760,"zh-CN"),(1280,760,"en")]
        sizes.extend((720,600,language) for language in LANGUAGES)
        for width, height, language in sizes:
            self.controller.change("language", language)
            self.window.resize(width,height)
            for _ in range(60):
                QTest.qWait(10)
                if self.window.property("layoutWidth") == width:
                    break
            QTest.qWait(30)
            self.assertEqual(self.window.property("layoutWidth"),width)
            choice = self.find("assemblyCaseChoice")
            x = choice.mapToScene(QPointF(0,0)).x()
            self.assertGreaterEqual(x, self.window.property("railWidth"))
            self.assertLessEqual(x+choice.width(),width)
            self.assertGreater(choice.width(),300)
            self.assertEqual(choice.property("displayText"), self.controller.tr("自动识别 / 参考机箱"))
            button = self.find("openAssemblyViewButton")
            top = button.mapToScene(QPointF(0,0))
            self.assertGreaterEqual(top.x(),self.window.property("railWidth"))
            self.assertLessEqual(top.x()+button.width(),width)
            self.assertGreaterEqual(top.y(),34)
            self.assertLessEqual(top.y()+button.height(),height-72)
            loader = self.find("assemblyPageLoader")
            pending = [loader.property("item")]
            found_label = None
            while pending:
                item = pending.pop()
                if item.property("text") == self.controller.tr("内存") and item.width()>=100:
                    found_label = item
                    break
                pending.extend(item.childItems())
            self.assertIsNotNone(found_label)
            self.assertGreaterEqual(found_label.width(),100)
            if proof:
                self.assertTrue(self.window.grabWindow().save(str(Path(proof)/f"assembly-{width}-{language}.png")))

    def test_new_assembly_copy_has_all_eight_language_entries(self):
        keys = set()
        for filename in ("native/AssemblyPage.qml", "native/AssemblyParts.qml", "assembly_window.py"):
            source = (ROOT/filename).read_text(encoding="utf-8")
            keys.update(re.findall(r'(?:ui\.t|controller\.tr|self\.controller\.tr)\("([^"]+)"\)', source))
        keys.update(("自动识别 / 参考机箱", "参考机箱（未识别）", "处理器未识别", "显卡未识别",
                     "跟随顶部栏", "整机外观设置不正确",
                     "机箱", "单击部件查看状态", "实时状态", "选中部件", "功率", "主板规格",
                     "宽 × 高 × 深", "参考尺寸", "风扇转速为板卡汇总读数。", "内存读数为整机合计。",
                     "未提供此部件的独立传感器读数。", "桌面 3D 检视", "此屏幕正在运行全屏应用，暂不打开三维检视。",
                     "机箱仅支持半高扩展卡。", "机箱不支持独立显卡安装。",
                     "内存型号未识别", "主板布局示意", "整机视图设置格式不正确", "机箱型号设置不正确",
                     "整机视图开关设置不正确", "模型细节", "简洁", "精细", "近看细节",
                     "模型细节设置不正确", "风格特效", "预览特效",
                     "选择部件时短暂播放，结束后停止。", "精细适合日常查看，近看细节用于局部观察。",
                     "DIMM 插槽", "M.2 插槽", "原厂前置 USB", "原厂音频接口"))
        for language in set(LANGUAGES)-{"zh-CN"}:
            for key in keys:
                self.assertTrue(MESSAGES[language].get(key), (language,key))

    def test_reference_hardware_and_mixed_styles_edit_only_preferences_in_the_actual_page(self):
        self.show_assembly(width=720,height=600)
        before=copy.deepcopy(self.controller.draft)
        cpu=self.find('assemblyReference_cpu_model');gpu=self.find('assemblyReference_gpu_model')
        self.assertGreaterEqual(len(gpu.property('model')),148)
        cpu.picked.emit('amd-9950x');gpu.picked.emit(gpu.property('model')[-1]['id'])
        self.app.processEvents()
        self.assertFalse(self.controller.assembly_specification()['cpu']['telemetry_bound'])
        self.assertFalse(self.controller.assembly_specification()['gpu']['telemetry_bound'])
        self.find('assemblyAddMemory').clicked.emit();self.app.processEvents()
        memory=self.find('assemblyMemory_0');memory.picked.emit(memory.property('model')[-1]['id'])
        self.app.processEvents()
        self.assertEqual(self.controller.draft['assembly']['memory_models'],[memory.property('model')[-1]['id']])
        self.find('assemblyPartStyle_gpu').picked.emit('notebook_line')
        self.app.processEvents()
        self.assertEqual(self.controller.draft['assembly']['part_styles'],{'gpu':'notebook_line'})
        self.find('assemblyResetPartStyles').clicked.emit();self.app.processEvents()
        self.assertEqual(self.controller.draft['assembly']['part_styles'],{})
        for language in LANGUAGES:
            self.controller.change('language',language);QTest.qWait(10)
            for name in ('assemblyReference_cpu_model','assemblyReference_gpu_model','assemblyMemory_0','assemblyBoardChoice','assemblyPartStyle_gpu'):
                item=self.find(name)
                point=item.mapToScene(QPointF(0,0))
                self.assertGreaterEqual(point.x(),self.window.property('railWidth'))
                self.assertLessEqual(point.x()+item.width(),720)
                self.assertGreater(item.width(),200)
        self.assertEqual(self.controller.draft['top_bar'],before['top_bar'])
        self.assertEqual(self.controller.draft['widgets'],before['widgets'])
        self.assertEqual(self.controller.scopeDirty,dict(desktop=False,preferences=True,topbar=False))
        self.snapshot.assert_called_once();self.modules.assert_called_once()

    def test_gpu_brand_and_series_filters_keep_the_reference_choice_and_do_not_edit_preferences(self):
        self.show_assembly()
        self.controller.changeAssembly('gpu_model','asus-astral-5090');self.app.processEvents()
        before=copy.deepcopy(self.controller.draft)
        self.find('assemblyGpuBrandFilter').picked.emit('MSI');self.app.processEvents()
        gpu=self.find('assemblyReference_gpu_model')
        self.assertTrue(all(not row['id'] or row['brand']=='MSI' for row in gpu.property('model')))
        self.assertIn('ASTRAL',gpu.property('displayText').upper())
        series=self.find('assemblyGpuSeriesFilter');rows=series.property('model')
        self.assertGreater(len(rows),1)
        selected=rows[-1]['id'];series.picked.emit(selected);self.app.processEvents()
        gpu=self.find('assemblyReference_gpu_model')
        self.assertTrue(all(not row['id'] or row['series_id']==selected for row in gpu.property('model')))
        self.assertEqual(self.controller.draft,before)

    def test_brand_filter_changes_only_picker_and_keeps_the_current_model_label(self):
        self.show_assembly()
        self.controller.changeAssembly('case_model','hyte-y60')
        before=copy.deepcopy(self.controller.draft)
        brand=self.find('assemblyBrandChoice');choice=self.find('assemblyCaseChoice')
        brand.picked.emit('ASUS');self.app.processEvents()
        rows=choice.property('model')
        self.assertGreater(len(rows),1)
        self.assertTrue(all(not row['id'] or row['brand']=='ASUS' for row in rows))
        self.assertEqual(choice.property('displayText'),'HYTE Y60')
        self.assertEqual(self.controller.draft,before)
        brand.picked.emit('');self.app.processEvents()
        self.assertEqual(len(choice.property('model')),len(self.controller.assemblyCases))

    def test_style_choice_has_follow_and_every_bar_style_without_changing_the_bar_or_case(self):
        from top_bar_config import HARDWARE_ICON_STYLES
        self.show_assembly()
        self.controller.changeAssembly('case_model','hyte-y60')
        before=copy.deepcopy(self.controller.draft)
        choice=self.find('assemblyStyleChoice')
        self.assertEqual([r['id'] for r in choice.property('model')],['follow',*HARDWARE_ICON_STYLES])
        self.assertEqual(choice.property('value'),'follow')
        page=self.find('assemblyPageLoader').property('item');scroll=page.property('contentItem')
        scroll.setProperty('contentY',max(0,scroll.property('contentHeight')-scroll.height()))
        QTest.qWait(30)
        choice.forceActiveFocus();QTest.keyClick(self.window,Qt.Key_End);QTest.keyClick(self.window,Qt.Key_Return)
        QTest.qWait(30)
        self.assertEqual(self.controller.assemblySummary['visual_style'],HARDWARE_ICON_STYLES[-1])
        self.assertEqual(self.controller.draft['assembly']['case_model'],'hyte-y60')
        self.assertEqual(self.controller.draft['top_bar'],before['top_bar'])
        self.assertEqual(self.controller.scopeDirty,dict(desktop=False,preferences=True,topbar=False))
        self.controller.change('language','en');self.app.processEvents()
        self.assertEqual(choice.property('model')[0]['label'],'Follow top bar')
        self.assertEqual(choice.property('value'),HARDWARE_ICON_STYLES[-1])
        proof=os.environ.get('DESKTOP_STATS_ASSEMBLY_PAGE_PROOF')
        if proof:
            self.window.resize(720,600)
            for _ in range(60):
                QTest.qWait(10)
                if self.window.property('layoutWidth')==720:break
            self.assertEqual(self.window.property('layoutWidth'),720)
            for language in ('zh-CN','de','fr','ja'):
                self.controller.change('language',language);QTest.qWait(50)
                scroll.setProperty('contentY',max(0,scroll.property('contentHeight')-scroll.height()))
                QTest.qWait(30)
                top=choice.mapToScene(QPointF(0,0))
                self.assertGreaterEqual(top.x(),self.window.property('railWidth'))
                self.assertLessEqual(top.x()+choice.width(),720)
                self.assertGreaterEqual(top.y(),34)
                self.assertLessEqual(top.y()+choice.height(),self.window.height()-72)
                self.assertTrue(self.window.grabWindow().save(str(Path(proof)/f'assembly-style-choice-{language}.png')))


    def test_optional_pack_import_and_remove_preserves_settings_and_handles_bad_archive(self):
        import hardware_packs
        from hardware_packs import PackStore,make_pack
        from tools.export_hardware_packs import pack_models
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'amd.dspack';store=PackStore(Path(tmp)/'installed')
            rows=pack_models()['amd'];source.write_bytes(make_pack('cpu-amd','AMD CPU',rows))
            with patch.object(hardware_packs,'_store',store):
                self.show_assembly()
                before=copy.deepcopy(self.controller.draft)
                with patch('PySide6.QtWidgets.QFileDialog.getOpenFileName',return_value=(str(source),'')):
                    self.controller.importHardwarePack();self.app.processEvents()
                    self.assertEqual(self.controller.draft,before)
                    self.assertEqual(self.controller.hardwarePacks['installed'][0]['products'],len(rows))
                    self.assertIn(rows[0]['id'],[row['id'] for row in self.controller.assemblyParts['cpus']])
                    source.write_bytes(b'invalid');self.controller.importHardwarePack();self.app.processEvents()
                    self.assertEqual(self.controller.hardwarePacks['installed'][0]['products'],len(rows))
                    self.assertEqual(self.controller.draft,before)
                    self.controller.removeHardwarePack('cpu-amd');self.app.processEvents()
                    self.assertEqual(self.controller.hardwarePacks['installed'],[])
                    self.assertEqual(self.controller.draft,before)


if __name__ == "__main__":
    unittest.main()
