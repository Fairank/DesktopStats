"""Actual-public gallery checks in one never-shown software Qt host.

The facade executes the real selected-reference slot and inventory getter AST.
Only the optional store is replaced with an explicit empty in-memory index.
"""
import ast
import copy
import json
import os
from pathlib import Path
from types import ModuleType
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')
os.environ.setdefault('QML_DISABLE_DISK_CACHE', '1')

from PySide6.QtCore import QObject, Property, Signal, Slot, QCoreApplication, QEvent, QUrl
from PySide6.QtGui import QGuiApplication, QFontDatabase
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression, qmlContext
from PySide6.QtQuick import QQuickItem, QQuickWindow

ROOT = Path(__file__).resolve().parents[1]
STYLES = ('miniature', 'cartoon', 'notebook_color', 'notebook_line', 'sticker', 'papercut')


def actual_methods():
    parsed = ast.parse((ROOT / 'assembly_tools.py').read_text(encoding='utf8'))
    owner = next(n for n in parsed.body if isinstance(n, ast.ClassDef) and n.name == 'AssemblyTools')
    methods = []
    for name in ('accessoryCatalog', 'accessoryGpuReference'):
        node = copy.deepcopy(next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == name))
        node.decorator_list = []; methods.append(node)
    scope = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=methods, type_ignores=[])),
                 'actual-public-assembly-tools-gallery-methods', 'exec'), scope)
    return scope


class EmptyStore:
    def __init__(self): self.index_calls = []
    def choices(self, category):
        assert category in ('cooler', 'fan', 'loop', 'radiator')
        self.index_calls.append(category)
        return []
    def get_model(self, *args, **kwargs):
        raise AssertionError('No optional payload reads in this gallery check')


class GalleryStats(QObject):
    changed = Signal()
    dataChanged = Signal()
    theme = Property(str, lambda self: 'light', constant=True)
    language = Property(str, lambda self: 'en', constant=True)
    material = Property('QVariantMap', lambda self: {}, constant=True)
    texts = Property('QVariantMap', lambda self: {}, constant=True)
    motionEnabled = Property(bool, lambda self: True, constant=True)
    accessoryArtRevision = Property(int, lambda self: 0, constant=True)
    assemblyStyles = Property('QVariantList', lambda self: [dict(id=s, label=s) for s in STYLES], constant=True)

    def __init__(self):
        super().__init__()
        self.actual = actual_methods()
        self.reads = 0; self.requests = []; self.descriptors = []; self.demands = []; self.activity = []
        self._accessory_gallery_active = False

    @Property('QVariantMap', notify=changed)
    def accessoryCatalog(self):
        self.reads += 1
        return self.actual['accessoryCatalog'](self)

    @Slot(str, result='QVariantMap')
    def accessoryGpuReference(self, identity):
        self.descriptors.append(identity)
        return self.actual['accessoryGpuReference'](self, identity)

    @Slot(str, str, str, result='QVariantMap')
    def accessoryModelArt(self, kind, identity, style):
        self.requests.append((kind, identity, style))
        assert kind != 'gpu', 'GPU must not reach the Python SVG producer'
        return dict(pending=True)

    @Slot('QVariantList')
    def setAccessoryArtDemand(self, rows): self.demands.append(copy.deepcopy(rows))

    @Slot(bool)
    def setAccessoryGalleryActive(self, active):
        self._accessory_gallery_active = active is True
        self.activity.append(active)

    @Slot(str)
    def downloadAccessoryArt(self, kind): raise AssertionError('No downloads in this UI batch')


class GpuGalleryUi053Tests(unittest.TestCase):
    observations = []

    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        assert cls.app.platformName() == 'offscreen'
        # Reuse existing Windows fonts; no download, install, copy or private
        # font directory is required by this standalone test module.
        cls.loaded_fonts = []
        font_directory = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
        for filename in ('SegUIVar.ttf', 'msyh.ttc'):
            path = font_directory / filename
            if path.is_file():
                font_id = QFontDatabase.addApplicationFont(str(path))
                families = QFontDatabase.applicationFontFamilies(font_id)
                assert font_id >= 0 and families, 'Existing system font did not load'
                cls.loaded_fonts.append((font_id, tuple(families)))

    def setUp(self):
        self.empty = EmptyStore()
        fake = ModuleType('hardware_packs')
        fake.runtime_store = lambda: self.empty
        fake.library_generation = lambda: 0
        self.store_patch = patch.dict(sys.modules, {'hardware_packs': fake}); self.store_patch.start()
        import accessory_art
        accessory_art.clear_cache()
        self.stats = GalleryStats(); self.engine = QQmlEngine(); self.warnings = []
        self.engine.warnings.connect(lambda rows: self.warnings.extend(r.toString() for r in rows))
        self.host = QQuickWindow(); self.host.resize(960, 760)
        self.host.contentItem().setWidth(960); self.host.contentItem().setHeight(760)
        self.engine.rootContext().setContextProperty('stats', self.stats)
        self.engine.rootContext().setContextProperty('testHost', self.host.contentItem())
        self.probe_component = QQmlComponent(self.engine)
        self.probe_component.setData(b'''import QtQml
import "HardwareShapes.js" as Shapes
QtObject {
 id:probe
 property var counts:({keys:0,sources:0,layers:0})
 property var ids:[]
 property var originals:[]
 function install() {
  originals=[Shapes.key,Shapes.source,Shapes.layers]
  Shapes.key=function(a,b) {probe.counts.keys++;probe.ids.push(a && a.id || "");return originals[0](a,b)}
  Shapes.source=function(a) {probe.counts.sources++;return originals[1](a)}
  Shapes.layers=function(a,b) {probe.counts.layers++;return originals[2](a,b)}
 }
 function restore(){Shapes.key=originals[0];Shapes.source=originals[1];Shapes.layers=originals[2]}
 function snapshot(){return JSON.stringify({counts:counts,ids:ids})}
}''', QUrl.fromLocalFile(str(ROOT / 'native/_gpu_gallery_probe053.qml')))
        self.probe = self.probe_component.create()
        self.assertIsNotNone(self.probe, [e.toString() for e in self.probe_component.errors()])
        self.probe.install()
        self.component = QQmlComponent(self.engine)
        self.component.setData(b'import QtQuick\nimport "."\nAccessoryGallery { parent:testHost; category:"gpu" }',
                               QUrl.fromLocalFile(str(ROOT / 'native/_gpu_gallery_fixture053.qml')))
        self.gallery = self.component.create()
        self.assertIsNotNone(self.gallery, [e.toString() for e in self.component.errors()])
        self.polish()

    def tearDown(self):
        try:
            self.gallery.close(); self.polish()
            self.assertFalse(self.host.isVisible())
            self.assertEqual(self.glyphs(), [])
            self.assertEqual(self.value('gpuReference'), {})
            self.probe.restore()
            self.observations.append(dict(test=self.id(), counts=self.counts(),
                                          descriptor_calls=list(self.stats.descriptors),
                                          optional_index_calls=list(self.empty.index_calls),
                                          window_shown=self.host.isVisible(), warnings=list(self.warnings)))
            for obj in (self.gallery, self.component, self.probe, self.probe_component,
                        self.engine, self.host, self.stats): obj.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            self.app.processEvents()
            self.assertEqual(self.warnings, [])
            self.assertEqual(self.app.topLevelWindows(), [])
        finally:
            self.store_patch.stop()

    def walk(self):
        pending = [self.gallery, self.gallery.property('contentItem')]; seen = {}
        while pending:
            obj = pending.pop()
            if obj is None or id(obj) in seen: continue
            seen[id(obj)] = obj; yield obj; pending.extend(obj.children())
            if isinstance(obj, QQuickItem): pending.extend(obj.childItems())

    def polish(self):
        for _ in range(4):
            self.app.processEvents()
            for obj in self.walk():
                if isinstance(obj, QQuickItem): obj.ensurePolished()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def value(self, name):
        value = self.gallery.property(name)
        return value.toVariant() if hasattr(value, 'toVariant') else value

    def find(self, name):
        obj = next((o for o in self.walk() if o.objectName() == name), None)
        self.assertIsNotNone(obj, name); return obj

    def glyphs(self): return [o for o in self.walk() if o.objectName() == 'accessoryGpuPreviewGlyph']

    def evaluate(self, item, code):
        expr = QQmlExpression(qmlContext(item), item, code); value = expr.evaluate()
        self.assertFalse(expr.hasError(), expr.error().toString())
        value = value[0] if isinstance(value, tuple) else value
        return value.toVariant() if hasattr(value, 'toVariant') else value

    def counts(self): return json.loads(self.probe.snapshot())

    def assert_one_static(self, identity):
        self.assertEqual(len(self.glyphs()), 1)
        glyph = self.glyphs()[0]
        actual = glyph.property('appearance').toVariant()
        self.assertEqual(actual['id'], identity)
        self.assertFalse(glyph.property('fanMotionEnabled'))
        self.assertFalse(glyph.property('fanMotionActive'))
        self.assertEqual(glyph.property('fanRotation'), 0)
        self.assertFalse(glyph.property('cacheArtwork'))
        images = [o for o in self.walk() if o.objectName() == 'hardwareGlyphImage'
                  or o.objectName().startswith('hardwareFanRotorImage_')]
        self.assertTrue(images)
        self.assertTrue(all(o.property('cache') is False for o in images))
        self.assertIsNone(self.find('accessoryDemoClock').property('subscription'))
        self.assertFalse(self.gallery.property('motionActive'))
        return glyph

    def test_cold_real_inventory_and_actual_click_filter_paths_only_resolve_selection(self):
        self.assertEqual(self.stats.reads, 0)
        self.assertEqual(self.stats.descriptors, [])
        self.assertEqual(self.counts()['counts'], dict(keys=0, sources=0, layers=0))
        self.gallery.open(); self.polish()
        self.assertEqual(len(self.value('entries')), 148)
        self.assertEqual(len(self.value('library')['gpus']), 148)
        self.assertEqual(self.find('accessoryModelGrid').property('count'), 0)
        self.assertEqual(len(self.stats.descriptors), 1)
        first = self.value('selectedGpuId'); self.assert_one_static(first)
        self.assertLessEqual(self.counts()['counts']['layers'], 8)
        self.assertLessEqual(self.counts()['counts']['sources'], 8)
        second = self.value('entries')[1]['id']
        self.evaluate(self.find('accessoryGpuRow_' + second), 'clicked()'); self.polish()
        self.assertEqual(self.value('selectedGpuId'), second); self.assert_one_static(second)
        self.evaluate(self.find('accessoryBrandChoice'), 'picked("Leadtek")'); self.polish()
        self.assertEqual([r['id'] for r in self.value('filtered')], ['leadtek-hurricane-4090-24g'])
        self.evaluate(self.find('accessorySearch'), 'text="does-not-exist";textEdited()'); self.polish()
        self.assertEqual(self.value('filtered'), []); self.assertEqual(self.glyphs(), [])
        self.assertEqual(self.stats.requests, [])
        self.assertTrue(all(rows == [] for rows in self.stats.demands))

    def test_real_partial_unknown_and_six_styles_keep_one_static_glyph_and_no_clock(self):
        self.gallery.open(); self.polish()
        self.gallery.setProperty('selectedGpuId', 'leadtek-hurricane-4090-24g'); self.polish()
        glyph = self.assert_one_static('leadtek-hurricane-4090-24g')
        self.assertEqual(self.value('gpuReference')['appearance']['fan_profile']['blade_counts'], [9, None, 9])
        self.assertEqual(self.evaluate(glyph, 'fanLayerData.rotors.map(r=>({known:r.known,index:r.source_index}))'),
                         [dict(known=True, index=0), dict(known=False, index=1), dict(known=True, index=2)])
        self.gallery.setProperty('selectedGpuId', 'gigabyte-aorus-4090-master'); self.polish()
        glyph = self.assert_one_static('gigabyte-aorus-4090-master')
        self.assertEqual(self.evaluate(glyph, 'fanLayerData.rotors.map(r=>r.known)'), [False, False, False])
        self.gallery.setProperty('selectedGpuId', 'asus-dual-4060-oc'); self.polish()
        requested = len(self.stats.descriptors)
        for style in STYLES:
            prior_style = self.value('selectedStyle'); retired = []
            previous = self.glyphs()[0]
            if prior_style != style:
                previous.destroyed.connect(lambda *args, retired=retired: retired.append(True))
            self.evaluate(self.find('accessoryStyleChoice'), 'picked(' + json.dumps(style) + ')'); self.polish()
            glyph = self.assert_one_static('asus-dual-4060-oc')
            self.assertEqual(glyph.property('appearance').toVariant()['icon_set'], style)
            if prior_style != style: self.assertEqual(retired, [True], 'The previous preview QObject must be destroyed')
        self.assertEqual(len(self.stats.descriptors), requested, 'Style changes reuse one descriptor')
        self.assertLess(self.counts()['counts']['layers'], 64, 'No whole-catalog artwork pass')
        self.assertTrue(set(self.counts()['ids']) <= {'', self.value('entries')[0]['id'],
                        'leadtek-hurricane-4090-24g', 'gigabyte-aorus-4090-master', 'asus-dual-4060-oc'})

    def test_idle_unload_stale_request_and_existing_category_default_cache_contract(self):
        self.gallery.open(); self.polish()
        before = (self.counts(), list(self.stats.descriptors))
        for _ in range(100): self.stats.dataChanged.emit()
        self.gallery.setProperty('phase', 117.); self.polish()
        self.assertEqual((self.counts(), self.stats.descriptors), before)
        self.gallery.setProperty('selectedGpuId', 'leadtek-hurricane-4090-24g')
        calls = len(self.stats.descriptors)
        self.gallery.close(); self.polish()
        self.assertEqual(len(self.stats.descriptors), calls)
        self.assertEqual(self.glyphs(), []); self.assertEqual(self.value('gpuReference'), {})
        self.gallery.open(); self.polish(); self.assertEqual(len(self.glyphs()), 1)
        self.evaluate(self.find('accessoryCategory_radiator'), 'clicked()'); self.polish()
        self.assertEqual(self.value('category'), 'radiator')
        self.assertEqual(self.glyphs(), []); self.assertEqual(self.value('gpuReference'), {})
        self.assertTrue(self.stats.requests)
        self.assertTrue(all(kind == 'radiator' for kind, identity, style in self.stats.requests))
        self.evaluate(self.find('accessoryCategory_gpu'), 'clicked()'); self.polish()
        self.gallery.setProperty('ownerActive', False); self.polish()
        self.assertEqual(self.glyphs(), []); self.assertEqual(self.value('gpuReference'), {})
        default_component = QQmlComponent(self.engine)
        default_component.setData(b'import QtQuick\nimport "."\nHardwareGlyph {}',
                                  QUrl.fromLocalFile(str(ROOT / 'native/_gpu_gallery_default053.qml')))
        ordinary = default_component.create()
        self.assertIsNotNone(ordinary, [e.toString() for e in default_component.errors()])
        self.assertTrue(ordinary.property('cacheArtwork'))
        ordinary.deleteLater(); default_component.deleteLater(); self.polish()


if __name__ == '__main__': unittest.main()
