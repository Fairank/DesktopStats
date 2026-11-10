"""The real gallery's manual open-reference menu in one unshown software host."""
from unittest.mock import patch
import unittest

import test_gpu_gallery_ui053 as common


class ReferenceEntryStats(common.GalleryStats):
    def __init__(self):
        super().__init__()
        self.reference_load_calls=0
        self.reference_download_calls=0

    @common.Slot()
    def openReferenceModel(self):
        self.reference_load_calls+=1

    @common.Slot()
    def openReferenceModelsDownload(self):
        self.reference_download_calls+=1


class OpenReferenceEntry054Tests(common.GpuGalleryUi053Tests):
    observations=[]

    def setUp(self):
        with patch.object(common,'GalleryStats',ReferenceEntryStats):
            super().setUp()

    def test_actual_manual_entry_opens_two_actions_and_closes_with_gallery(self):
        self.assertEqual(self.stats.reference_load_calls,0)
        self.assertEqual(self.stats.reference_download_calls,0)
        self.assertEqual(self.stats.reads,0)
        self.assertFalse(self.host.isVisible())
        self.gallery.setProperty('category','case')
        self.gallery.open();self.polish()
        action=self.find('accessoryOpenReference')
        menu=self.find('accessoryOpenReferenceMenu')
        self.assertTrue(action.property('enabled'))
        self.assertFalse(menu.property('visible'))
        self.assertEqual(self.stats.reference_load_calls,0)
        self.assertEqual(self.stats.reference_download_calls,0)
        # The case page also shows the SVG download action, so this is the
        # wider header rather than a favourable category with one less button.
        rects=[]
        for name in ('accessoryPacksDownload','accessoryOpenReference',
                     'accessoryDownload','closeAccessoryGallery'):
            item=self.find(name)
            self.assertTrue(item.property('visible'))
            rect=self.evaluate(item,'({x:mapToItem(testHost,0,0).x,y:mapToItem(testHost,0,0).y,width:width,height:height})')
            self.assertGreater(rect['width'],10);self.assertGreater(rect['height'],10)
            self.assertGreaterEqual(rect['x'],0);self.assertGreaterEqual(rect['y'],0)
            self.assertLessEqual(rect['x']+rect['width'],960.01)
            self.assertLessEqual(rect['y']+rect['height'],760.01)
            rects.append(rect)
        for left,right in zip(rects,rects[1:]):
            self.assertLessEqual(left['x']+left['width'],right['x']+.01)
        self.evaluate(action,'clicked()');self.polish()
        self.assertTrue(menu.property('visible'))
        self.assertEqual(menu.property('count'),2)
        self.assertEqual(self.evaluate(menu,'itemAt(0).objectName'),'referenceLoadZip')
        self.assertEqual(self.evaluate(menu,'itemAt(1).objectName'),'referenceDownloadModels')
        self.evaluate(self.find('referenceLoadZip'),'triggered()');self.polish()
        self.assertEqual((self.stats.reference_load_calls,self.stats.reference_download_calls),(1,0))
        menu.close();self.polish()
        self.evaluate(action,'clicked()');self.polish()
        self.evaluate(self.find('referenceDownloadModels'),'triggered()');self.polish()
        self.assertEqual((self.stats.reference_load_calls,self.stats.reference_download_calls),(1,1))
        # Keep the menu open while dismissing its owner: the real onAboutToHide
        # must remove the nested popup, not leave it as an orphan surface.
        if not menu.property('visible'):
            self.evaluate(action,'clicked()');self.polish()
        self.assertTrue(menu.property('visible'))
        self.gallery.close();self.polish()
        self.assertFalse(menu.property('visible'))
        self.assertFalse(self.host.isVisible())
        self.assertEqual((self.stats.reference_load_calls,self.stats.reference_download_calls),(1,1))
        self.assertEqual(self.counts()['counts'],dict(keys=0,sources=0,layers=0))
        self.observations.append(dict(scope='actual_open_reference_menu',
            load_calls=1,download_calls=1,menu_items=2,menu_closed_with_gallery=True,
            header_rects=rects,host_shown=False))


def load_tests(loader,tests,pattern):
    # Do not repeat the three inherited GPU/cross-style methods here.
    return unittest.TestSuite((OpenReferenceEntry054Tests(
        'test_actual_manual_entry_opens_two_actions_and_closes_with_gallery'),))


if __name__=='__main__':unittest.main()
