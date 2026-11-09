"""Three actual-public QML entry contracts, with explicit external-action stubs."""
import sys
import unittest
from unittest.mock import patch

from PySide6.QtCore import Signal, Slot, QPointF
import test_gpu_gallery_ui053 as base


class IndexStore(base.EmptyStore):
    def __init__(self):
        super().__init__(); self.generation = 0; self.available = False

    def choices(self, category):
        super().choices(category)
        if category == 'loop' and self.available:
            return [dict(id='fixture-cpu-block', label='Metadata fixture CPU block',
                         vendor='Fixture', series='Fixture', pack_id='fixture-pack',
                         selector=dict(part_kind='cpu_block'))]
        return []


class EntryStats(base.GalleryStats):
    hardwarePacksChanged = Signal()

    def __init__(self):
        super().__init__(); self.downloads = 0; self.imports = 0

    @Slot()
    def openHardwarePacksDownload(self): self.downloads += 1

    @Slot()
    def importHardwarePack(self): self.imports += 1


class PackEntry053Tests(unittest.TestCase):
    observations = []
    setUpClass = classmethod(base.GpuGalleryUi053Tests.setUpClass.__func__)
    walk = base.GpuGalleryUi053Tests.walk
    polish = base.GpuGalleryUi053Tests.polish
    value = base.GpuGalleryUi053Tests.value
    find = base.GpuGalleryUi053Tests.find
    evaluate = base.GpuGalleryUi053Tests.evaluate
    glyphs = base.GpuGalleryUi053Tests.glyphs
    counts = base.GpuGalleryUi053Tests.counts

    def setUp(self):
        with patch.object(base, 'EmptyStore', IndexStore), patch.object(base, 'GalleryStats', EntryStats):
            base.GpuGalleryUi053Tests.setUp(self)
        sys.modules['hardware_packs'].library_generation = lambda: self.empty.generation
        self.bounds_observed = []
        self.gallery.setProperty('category', 'cpu_block'); self.polish()

    def tearDown(self):
        self.observations.append(dict(test=self.id(), downloads=self.stats.downloads,
                                      imports=self.stats.imports, reads=self.stats.reads,
                                      index_generation=self.empty.generation,
                                      new_artwork_calls=len(self.stats.requests), bounds=self.bounds_observed))
        base.GpuGalleryUi053Tests.tearDown(self)

    def assert_empty_buttons_inside_viewport(self):
        grid = self.find('accessoryModelGrid')
        self.assertIs(self.find('accessoryEmptyState').parentItem(), grid)
        origin = grid.mapToScene(QPointF(0, 0))
        left, top = origin.x(), origin.y()
        right, bottom = left + grid.width(), top + grid.height()
        self.assertGreater(right - left, 0)
        self.assertGreater(bottom - top, 0)
        for name in ('accessoryEmptyDownload', 'accessoryEmptyImport'):
            button = self.find(name)
            p = button.mapToScene(QPointF(0, 0))
            self.bounds_observed.append(dict(button=name, viewport=[left, top, right, bottom], rect=[p.x(), p.y(), p.x()+button.width(), p.y()+button.height()]))
            self.assertTrue(button.property('visible'))
            self.assertGreater(button.width(), 0); self.assertGreater(button.height(), 0)
            self.assertGreaterEqual(p.x(), left - .01)
            self.assertGreaterEqual(p.y(), top - .01)
            self.assertLessEqual(p.x() + button.width(), right + .01)
            self.assertLessEqual(p.y() + button.height(), bottom + .01)

    def test_cold_and_open_empty_category_have_no_automatic_external_action(self):
        self.assertEqual(self.stats.reads, 0)
        self.assertEqual((self.stats.downloads, self.stats.imports), (0, 0))
        self.gallery.open(); self.polish()
        self.assertEqual(self.value('entries'), [])
        self.assertTrue(self.find('accessoryEmptyState').property('needsPack'))
        self.assertTrue(self.find('accessoryEmptyDownload').property('visible'))
        self.assertTrue(self.find('accessoryEmptyImport').property('visible'))
        self.assert_empty_buttons_inside_viewport()
        self.assertEqual((self.stats.downloads, self.stats.imports), (0, 0))
        self.assertEqual(self.stats.requests, [])

    def test_actual_download_and_import_click_handlers_only_invoke_stub_counters(self):
        self.gallery.open(); self.polish()
        self.assert_empty_buttons_inside_viewport()
        for name in ('accessoryPacksDownload', 'accessoryEmptyDownload', 'accessoryEmptyImport'):
            button = self.find(name)
            self.assertTrue(button.property('enabled'))
            self.evaluate(button, 'clicked()')
        self.polish()
        self.assertEqual((self.stats.downloads, self.stats.imports), (2, 1))
        self.assertEqual(self.value('entries'), [])
        self.assertEqual(self.stats.requests, [])
        self.assertEqual(self.glyphs(), [])

    def test_import_signal_refreshes_metadata_and_filter_empty_does_not_offer_missing_pack(self):
        self.gallery.open(); self.polish()
        before = self.stats.reads
        # Synthetic completed import metadata event, not a file-dialog/archive test.
        self.empty.available = True; self.empty.generation += 1
        self.stats.hardwarePacksChanged.emit(); self.polish()
        self.assertGreater(self.stats.reads, before)
        self.assertEqual([r['id'] for r in self.value('entries')], ['fixture-cpu-block'])
        self.assertFalse(self.find('accessoryEmptyState').property('visible'))
        self.gallery.setProperty('query', 'not-a-match'); self.polish()
        self.assertEqual(self.value('filtered'), [])
        self.assertTrue(self.find('accessoryEmptyState').property('visible'))
        self.assertFalse(self.find('accessoryEmptyState').property('needsPack'))
        self.assertFalse(self.find('accessoryEmptyDownload').property('visible'))
        self.assertFalse(self.find('accessoryEmptyImport').property('visible'))
        self.assertEqual((self.stats.downloads, self.stats.imports), (0, 0))
        self.assertTrue(all(kind == 'cpu_block' for kind, identity, style in self.stats.requests))
        self.assertEqual(self.glyphs(), [])


if __name__ == '__main__': unittest.main()
