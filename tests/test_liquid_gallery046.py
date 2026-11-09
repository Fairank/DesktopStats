"""Real loop gallery popup in a never-shown software Qt host.

No platform window is created, no OpenGL context, native API, collector or
worker is requested. An exported data archive is installed in a private store.
"""
import builtins
import ctypes
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE','Basic')
from PySide6.QtCore import QObject,Property,Signal,Slot,QCoreApplication,QEvent,QPointF,QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent,QQmlEngine
from PySide6.QtQuick import QQuickItem,QQuickWindow

import hardware_packs as packs

ROOT=Path(__file__).resolve().parents[1]
LOOP_KEYS=('cpu_blocks','loop_pumps','loop_reservoirs','loop_combos','loop_fittings','loop_tubing')


class GalleryStats(QObject):
    changed=Signal()
    theme=Property(str,lambda self:'light',constant=True)
    language=Property(str,lambda self:'en',constant=True)
    material=Property('QVariantMap',lambda self:{},constant=True)
    texts=Property('QVariantMap',lambda self:{},constant=True)
    motionEnabled=Property(bool,lambda self:False,constant=True)
    def __init__(self):
        super().__init__();self.catalog_reads=0;self.art_calls=[];self.activity=[]
    @Property('QVariantList',constant=True)
    def assemblyStyles(self):
        from top_bar_config import HARDWARE_ICON_STYLES
        return [dict(id='follow',label='Follow'),*[dict(id=s,label=s) for s in HARDWARE_ICON_STYLES]]
    @Property('QVariantMap',notify=changed)
    def accessoryCatalog(self):
        from accessory_art import choices
        self.catalog_reads+=1;rows=choices()
        return {key:rows[key] for key in LOOP_KEYS}
    @Slot(str,str,str,result='QVariantMap')
    def accessoryModelArt(self,kind,identity,style):
        from accessory_art import art
        self.art_calls.append((kind,identity,style));return art(kind,identity,style)
    @Slot(bool)
    def setAccessoryGalleryActive(self,active):
        self.activity.append(active)
        if not active:
            from accessory_art import clear_cache
            clear_cache()
    @Slot(str)
    def downloadAccessoryArt(self,kind):
        raise AssertionError('No browser/download during gallery tests')


class LiquidGallery046Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        assert cls.app.platformName()=='offscreen'
        # Authoring is an explicit archive fixture step, never a runtime import.
        from tools.export_loop_packs046 import pack_models
        cls.models=pack_models()
        cls.archive=packs.make_pack('test-loop-gallery046','Loop gallery fixture',cls.models,kind='loop')
    def setUp(self):
        self.enterContext(patch.object(ctypes,'WinDLL',side_effect=AssertionError('No native API'),create=True))
        self.enterContext(patch.object(subprocess,'Popen',side_effect=AssertionError('No process')))
        self.enterContext(patch.object(threading.Thread,'start',side_effect=AssertionError('No worker')))
        self.thread_ids={t.ident for t in threading.enumerate()}
        self.scratch=Path(self.enterContext(tempfile.TemporaryDirectory()))
        source=self.scratch/'loop.dspack';source.write_bytes(self.archive)
        store=packs.PackStore(self.scratch/'installed');store.install(source)
        self.enterContext(patch.object(packs,'_store',store))
        self.author_imports=[];original=builtins.__import__
        def guarded(name,*args,**kwargs):
            if name.startswith(('liquid_block_pump_expansion046','liquid_fitting_tube_expansion046',
                                'tools.export_loop_packs046','cooling_expansion045','liquid_radiator_expansion045')):
                self.author_imports.append(name)
                raise AssertionError('Runtime gallery must not import author catalogs: '+name)
            return original(name,*args,**kwargs)
        self.enterContext(patch('builtins.__import__',new=guarded))
        import accessory_art
        accessory_art.clear_cache()
        self.stats=GalleryStats();self.engine=QQmlEngine();self.warnings=[]
        self.engine.warnings.connect(lambda rows:self.warnings.extend(r.toString() for r in rows))
        self.host=QQuickWindow();self.host.resize(640,760)
        self.host.contentItem().setWidth(640);self.host.contentItem().setHeight(760)
        self.engine.rootContext().setContextProperty('stats',self.stats)
        self.engine.rootContext().setContextProperty('testHost',self.host.contentItem())
        self.component=QQmlComponent(self.engine)
        self.component.setData(b'import QtQuick\nimport "."\nAccessoryGallery { parent:testHost; category:"cpu_block" }',
                               QUrl.fromLocalFile(str(ROOT/'native/_liquid_gallery046_fixture.qml')))
        self.gallery=self.component.create()
        self.assertIsNotNone(self.gallery,[r.toString() for r in self.component.errors()])
        self.polish()
    def tearDown(self):
        self.gallery.close();self.polish()
        self.assertFalse(self.host.isVisible())
        self.gallery.deleteLater();self.component.deleteLater();self.engine.deleteLater()
        self.host.deleteLater();self.stats.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents()
        self.assertEqual(self.warnings,[])
        self.assertEqual(self.author_imports,[])
        self.assertEqual({t.ident for t in threading.enumerate()},self.thread_ids)
        self.assertEqual(self.app.topLevelWindows(),[])
    def walk(self):
        pending=[self.gallery,self.gallery.property('contentItem')];seen={}
        while pending:
            obj=pending.pop()
            if obj is None or id(obj) in seen:continue
            seen[id(obj)]=obj;yield obj
            pending.extend(obj.children())
            if isinstance(obj,QQuickItem):pending.extend(obj.childItems())
    def find(self,name):
        result=next((o for o in self.walk() if o.objectName()==name),None)
        self.assertIsNotNone(result,name);return result
    def value(self,obj,name):
        value=obj.property(name)
        return value.toVariant() if hasattr(value,'toVariant') else value
    def polish(self):
        for _ in range(4):
            self.app.processEvents()
            if hasattr(self,'gallery'):
                for obj in self.walk():
                    if isinstance(obj,QQuickItem):obj.ensurePolished()
    def open(self,width=640):
        self.host.resize(width,760);self.host.contentItem().setWidth(width);self.host.contentItem().setHeight(760)
        self.gallery.open();self.polish()
        self.assertTrue(self.gallery.property('visible'))
        self.assertFalse(self.host.isVisible())
    def test_closed_creation_does_not_read_a_catalog_or_generate_a_card(self):
        self.assertEqual(self.stats.catalog_reads,0);self.assertEqual(self.stats.art_calls,[])
        self.assertFalse(self.gallery.property('motionActive'))
        self.assertIsNone(self.find('accessoryDemoClock').property('subscription'))
    def test_actual_loop_categories_filter_and_close_release_the_existing_bounded_cache(self):
        import accessory_art
        self.open()
        # Qt may probe a QVariant property before retrieving its value; only
        # the explicit opening may read it, never a later close/notify/phase.
        reads=self.stats.catalog_reads;self.assertGreater(reads,0)
        mapping=dict(cpu_block='cpu_blocks',pump='loop_pumps',reservoir='loop_reservoirs',
                     pump_reservoir='loop_combos',fitting='loop_fittings',tubing='loop_tubing')
        for kind,key in mapping.items():
            self.gallery.setProperty('category',kind);self.polish()
            expected=[r for r in self.models if r['reference']['part_kind']==kind]
            self.assertEqual({r['id'] for r in self.value(self.gallery,'entries')},{r['id'] for r in expected})
            self.assertFalse(self.find('accessoryDownload').property('visible'))
        query=next(r['label'] for r in self.models if r['id']=='alphacool-core1-black')
        self.gallery.setProperty('category','cpu_block');self.gallery.setProperty('query',query);self.polish()
        self.assertEqual([r['id'] for r in self.value(self.gallery,'filtered')],['alphacool-core1-black'])
        self.assertGreater(len(self.stats.art_calls),0)
        self.assertLessEqual(accessory_art.cache_info()['entries'],16)
        calls=len(self.stats.art_calls)
        self.gallery.setProperty('phase',117.);self.polish()
        self.assertEqual(len(self.stats.art_calls),calls,'Retained SVG must not regenerate on phase changes')
        self.gallery.close();self.polish()
        self.assertEqual(self.value(self.gallery,'library'),{})
        self.assertEqual(accessory_art.cache_info()['entries'],0)
        self.assertFalse(self.stats.activity[-1])
        self.stats.changed.emit();self.polish()
        self.assertEqual(self.stats.catalog_reads,reads)
        self.assertEqual(len(self.stats.art_calls),calls)
    def test_narrow_and_wide_popup_controls_stay_inside_the_actual_content_layout(self):
        for width in (360,640):
            self.open(width)
            content=self.gallery.property('contentItem')
            for name in ('accessorySearch','accessoryBrandChoice','accessoryStyleChoice',
                         'accessoryDemoToggle','accessoryDemoRpm','accessoryModelGrid'):
                item=self.find(name);position=item.mapToItem(content,QPointF(0.,0.))
                self.assertGreater(item.width(),0.,(width,name))
                self.assertGreaterEqual(position.x(),-.1,(width,name))
                self.assertLessEqual(position.x()+item.width(),content.width()+.1,(width,name,position.x(),item.width(),content.width()))
            self.gallery.close();self.polish()
    def test_loop_cards_never_start_a_clock_and_hidden_delegates_do_not_generate(self):
        self.open()
        grid=self.find('accessoryModelGrid')
        self.assertEqual(grid.property('cacheBuffer'),0)
        requested={identity for kind,identity,style in self.stats.art_calls}
        self.assertTrue(requested)
        self.assertLess(len(requested),len(self.models),'Opening one category must not render the whole optional library')
        self.assertTrue(all(kind=='cpu_block' for kind,identity,style in self.stats.art_calls))
        self.gallery.setProperty('demoMotion',True);self.polish()
        self.assertFalse(self.gallery.property('motionActive'))
        self.assertIsNone(self.find('accessoryDemoClock').property('subscription'))
        self.assertEqual(sum(o.objectName()=='accessoryDemoClock' for o in self.walk()),1)
        for o in self.walk():
            if o.objectName()=='accessoryCardGlyph':
                self.assertFalse(o.property('moving'))
                card=o.parentItem()
                while card is not None and card.property('inViewport') is None:card=card.parentItem()
                self.assertIsNotNone(card)
                if not card.property('inViewport'):self.assertEqual(self.value(o,'art'),{})
        source=(ROOT/'native/AccessoryGallery.qml').read_text(encoding='utf8')
        for forbidden in ('Timer {','FrameAnimation {','WorkerScript'):
            self.assertNotIn(forbidden,source)


if __name__=='__main__':unittest.main()
