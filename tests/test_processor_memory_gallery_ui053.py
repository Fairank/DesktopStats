"""Prepared current-public CPU/memory UI checks; three new methods only.

Reuse the already reviewed never-shown gallery fixture, not another window or
controller. Its optional store is explicitly empty. No installed-profile or
hardware read is needed to browse the three bundled CPUs and 28 memory SKUs.
"""
import ast
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_gpu_gallery_ui053 as common

ROOT = common.ROOT


def _literal(relative, name):
    parsed = ast.parse((ROOT / relative).read_text(encoding='utf8'))
    node = next(n for n in parsed.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))
    return ast.literal_eval(node.value)


STYLE_IDS = _literal('top_bar_config.py', 'HARDWARE_ICON_STYLES')
STYLE_LABELS = _literal('assembly_config.py', 'STYLE_LABELS')


class ComponentStats(common.GalleryStats):
    assemblyStyles = common.Property('QVariantList', lambda self: [
        dict(id=style, label=STYLE_LABELS[style]) for style in STYLE_IDS], constant=True)

    def __init__(self):
        super().__init__()
        parsed = ast.parse((ROOT / 'assembly_tools.py').read_text(encoding='utf8'))
        owner = next(n for n in parsed.body if isinstance(n, ast.ClassDef) and n.name == 'AssemblyTools')
        node = deepcopy(next(n for n in owner.body if isinstance(n, ast.FunctionDef)
                             and n.name == 'accessoryComponentReference'))
        node.decorator_list = []
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                     'actual-public-component-selected-slot', 'exec'), self.actual)
        self.component_descriptors = []

    @common.Slot(str, str, result='QVariantMap')
    def accessoryComponentReference(self, kind, identity):
        self.component_descriptors.append((kind, identity))
        return self.actual['accessoryComponentReference'](self, kind, identity)


class ProcessorMemoryGalleryUi053Tests(common.GpuGalleryUi053Tests):
    observations = []

    live_interfaces = []

    def setUp(self):
        with patch.object(common, 'GalleryStats', ComponentStats):
            super().setUp()
        try:
            from PySide6.QtGui import QOpenGLContext
            from PySide6.QtQuick import QSGRendererInterface
            api = self.host.rendererInterface().graphicsApi()
            self.assertEqual(api, QSGRendererInterface.GraphicsApi.Software)
            self.assertIsNone(self.host.rhi())
            self.assertIsNone(QOpenGLContext.currentContext())
            self.assertFalse(self.host.isVisible())
            self.live_interfaces.append(dict(test=self.id(), api=str(api),
                                             rhi=None, current_GL=None, shown=False))
        except BaseException:
            super().tearDown()
            raise

    def _category(self, kind):
        self.evaluate(self.find('accessoryCategory_' + kind), 'clicked()')
        self.polish()
        self.assertEqual(self.value('category'), kind)

    def _layout(self):
        glyph = self.glyphs()[0]
        box = self.evaluate(glyph, '''({x:mapToItem(testHost,0,0).x,
            y:mapToItem(testHost,0,0).y,width:width,height:height})''')
        self.assertGreater(box['width'], 120)
        self.assertGreater(box['height'], 70)
        self.assertGreaterEqual(box['x'], 0)
        self.assertGreaterEqual(box['y'], 0)
        self.assertLessEqual(box['x'] + box['width'], self.host.width() + .01)
        self.assertLessEqual(box['y'] + box['height'], self.host.height() + .01)
        label = self.find('accessoryGpuSelectedLabel')
        self.assertEqual(label.property('text'), self.value('gpuReference')['label'])
        self.assertTrue(label.property('visible'))
        self.assertFalse(label.property('truncated'))
        self.assertGreater(label.property('width'), 120)
        self.assertGreater(label.property('height'), 0)
        self.assertGreaterEqual(len(self.evaluate(self.find('accessoryStyleChoice'), 'model')), 13)
        return box

    def test_cold_cpu_and_memory_tabs_resolve_only_one_selected_real_reference(self):
        self.assertEqual(self.stats.reads, 0)
        self.assertEqual(self.counts()['counts'], dict(keys=0, sources=0, layers=0))
        self.gallery.setProperty('category', 'cpu')
        self.gallery.open(); self.polish()
        self.assertEqual(len(self.value('entries')), 3)
        self.assertEqual(len(self.value('library')['memory']), 28)
        self.assertEqual(len(self.stats.component_descriptors), 1)
        self.assertEqual(self.stats.descriptors, [])
        first = self.value('selectedGpuId')
        self.assert_one_static(first)
        self.assertEqual(self.value('gpuReference')['appearance']['kind'], 'cpu')
        self.assertEqual(self.find('accessoryModelGrid').property('count'), 0)
        self.assertEqual(self.find('accessoryCategory_cpu').property('text'), '处理器 · 3')
        self._layout()
        self._category('memory')
        self.assertEqual(len(self.value('entries')), 28)
        self.assertEqual(len(self.stats.component_descriptors), 2)
        self.assert_one_static(self.value('selectedGpuId'))
        self.assertEqual(self.value('gpuReference')['appearance']['kind'], 'memory')
        self.assertEqual(self.value('gpuReference')['appearance']['confidence'], 'model')
        self._layout()
        self.assertEqual(self.stats.requests, [])
        self.assertTrue(all(rows == [] for rows in self.stats.demands))

    def test_two_selected_models_keep_one_uncached_static_glyph_across_six_styles(self):
        self.gallery.setProperty('category', 'cpu')
        self.gallery.open(); self.polish()
        self.gallery.setProperty('selectedGpuId', 'amd-9950x'); self.polish()
        style_model = self.evaluate(self.find('accessoryStyleChoice'), 'model')
        self.assertEqual([(r['id'], r['label']) for r in style_model],
                         [(s, STYLE_LABELS[s]) for s in STYLE_IDS])
        for kind, identity in (('cpu', 'amd-9950x'), ('memory', 'gskill-f4-3200c16d-16gtzr')):
            if self.value('category') != kind:
                self._category(kind)
            self.gallery.setProperty('selectedGpuId', identity); self.polish()
            calls = len(self.stats.component_descriptors)
            for style in common.STYLES:
                previous = self.glyphs()[0]; retired = []
                changed = self.value('selectedStyle') != style
                if changed:
                    previous.destroyed.connect(lambda *args, retired=retired: retired.append(True))
                self.evaluate(self.find('accessoryStyleChoice'), 'picked(' + json.dumps(style) + ')')
                self.polish()
                glyph = self.assert_one_static(identity)
                self.assertEqual(glyph.property('appearance').toVariant()['icon_set'], style)
                if changed:
                    self.assertEqual(retired, [True])
            self.assertEqual(len(self.stats.component_descriptors), calls)
        self.assertEqual(self.stats.requests, [])
        self.assertEqual(self.stats.descriptors, [])
        self.assertLess(self.counts()['counts']['sources'], 100)
        self.assertTrue(set(self.counts()['ids']) <= {
            '', 'intel-13700kf', 'amd-9950x', 'corsair-cmk16gx4m2b3200c16',
            'gskill-f4-3200c16d-16gtzr'})

    def test_cross_kind_stale_close_hidden_release_and_idle_do_not_keep_old_preview(self):
        self.gallery.setProperty('category', 'cpu')
        self.gallery.open(); self.polish()
        before = (self.counts(), list(self.stats.component_descriptors))
        for _ in range(100): self.stats.dataChanged.emit()
        self.polish()
        self.assertEqual((self.counts(), self.stats.component_descriptors), before)
        self.gallery.setProperty('selectedGpuId', 'amd-9950x')
        self.gallery.setProperty('category', 'memory')
        self.polish()
        self.assertEqual(self.value('gpuReference')['appearance']['kind'], 'memory')
        self.assertFalse(any(kind == 'cpu' and identity == 'amd-9950x'
                             for kind, identity in self.stats.component_descriptors))
        self.assert_one_static(self.value('selectedGpuId'))
        self.gallery.setProperty('selectedGpuId', 'gskill-f4-3200c16d-16gtzr')
        calls = len(self.stats.component_descriptors)
        self.gallery.close(); self.polish()
        self.assertEqual(len(self.stats.component_descriptors), calls)
        self.assertEqual(self.glyphs(), [])
        self.assertEqual(self.value('gpuReference'), {})
        self.gallery.open(); self.polish()
        self.assert_one_static(self.value('selectedGpuId'))
        self._category('gpu')
        self.assertEqual(self.value('gpuReference')['appearance']['kind'], 'gpu')
        self.assertEqual(len(self.glyphs()), 1)
        self.gallery.setProperty('ownerActive', False); self.polish()
        self.assertEqual(self.glyphs(), [])
        self.assertEqual(self.value('gpuReference'), {})
        self.assertFalse(self.host.isVisible())


METHODS = (
    'test_cold_cpu_and_memory_tabs_resolve_only_one_selected_real_reference',
    'test_two_selected_models_keep_one_uncached_static_glyph_across_six_styles',
    'test_cross_kind_stale_close_hidden_release_and_idle_do_not_keep_old_preview',
)


def load_tests(loader, tests, pattern):
    # The common fixture's three already tested GPU methods are deliberately
    # outside this new class's batch. The runner adds one old cold path only.
    return unittest.TestSuite(ProcessorMemoryGalleryUi053Tests(name) for name in METHODS)
