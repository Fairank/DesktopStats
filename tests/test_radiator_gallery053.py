"""Radiator discovery and cold requests, in an unshown software Qt host.

No renderer, model build, sensor, real user store or worker is needed here.
The mesh projection has separate geometry checks.
"""
import ast
import copy
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE','Basic')
from PySide6.QtCore import QObject,Property,Signal,Slot,QCoreApplication,QEvent,QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent,QQmlEngine
from PySide6.QtQuick import QQuickItem,QQuickWindow

ROOT=Path(__file__).resolve().parents[1]
STYLES=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')


class GalleryStats(QObject):
    changed=Signal()
    theme=Property(str,lambda self:'light',constant=True)
    language=Property(str,lambda self:'en',constant=True)
    material=Property('QVariantMap',lambda self:{},constant=True)
    texts=Property('QVariantMap',lambda self:{},constant=True)
    motionEnabled=Property(bool,lambda self:False,constant=True)
    accessoryArtRevision=Property(int,lambda self:0,constant=True)
    assemblyStyles=Property('QVariantList',lambda self:[dict(id=s,label=s) for s in STYLES],constant=True)

    def __init__(self):
        super().__init__();self.requests=[];self.demands=[];self.activity=[];self.reads=0

    @Property('QVariantMap',notify=changed)
    def accessoryCatalog(self):
        from liquid_cooling_catalog044 import records
        self.reads+=1
        return dict(radiators=[dict(id=r['id'],label=r['label'],brand=r['brand']) for r in records()])

    @Slot(str,str,str,result='QVariantMap')
    def accessoryModelArt(self,kind,identity,style):
        self.requests.append((kind,identity,style));return dict(pending=True)

    @Slot('QVariantList')
    def setAccessoryArtDemand(self,rows):
        self.demands.append(copy.deepcopy(rows))

    @Slot(bool)
    def setAccessoryGalleryActive(self,active):self.activity.append(active)

    @Slot(str)
    def downloadAccessoryArt(self,kind):raise AssertionError('No download in gallery checks')


class RadiatorGallery053Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        assert cls.app.platformName()=='offscreen'

    def setUp(self):
        self.stats=GalleryStats();self.engine=QQmlEngine();self.warnings=[]
        self.engine.warnings.connect(lambda rows:self.warnings.extend(r.toString() for r in rows))
        self.host=QQuickWindow();self.host.resize(760,760)
        self.host.contentItem().setWidth(760);self.host.contentItem().setHeight(760)
        self.engine.rootContext().setContextProperty('stats',self.stats)
        self.engine.rootContext().setContextProperty('testHost',self.host.contentItem())
        self.component=QQmlComponent(self.engine)
        self.component.setData(b'import QtQuick\nimport "."\nAccessoryGallery { parent:testHost; category:"radiator" }',
                               QUrl.fromLocalFile(str(ROOT/'native/_radiator_gallery053_fixture.qml')))
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
        self.assertEqual(self.app.topLevelWindows(),[])

    def walk(self):
        pending=[self.gallery,self.gallery.property('contentItem')];seen={}
        while pending:
            obj=pending.pop()
            if obj is None or id(obj) in seen:continue
            seen[id(obj)]=obj;yield obj;pending.extend(obj.children())
            if isinstance(obj,QQuickItem):pending.extend(obj.childItems())

    def polish(self):
        for _ in range(4):
            self.app.processEvents()
            for obj in self.walk():
                if isinstance(obj,QQuickItem):obj.ensurePolished()

    def value(self,name):
        value=self.gallery.property(name)
        return value.toVariant() if hasattr(value,'toVariant') else value

    def find(self,name):
        value=next((o for o in self.walk() if o.objectName()==name),None)
        self.assertIsNotNone(value,name);return value

    def test_unopened_does_not_request_any_model(self):
        self.assertEqual(self.stats.reads,0);self.assertEqual(self.stats.requests,[])
        self.assertEqual(self.stats.demands,[])

    def test_real_radiator_category_filters_six_styles_without_installed_fans(self):
        self.gallery.open();self.polish()
        self.assertEqual(len(self.value('entries')),24)
        self.assertEqual(self.value('catalogKey'),'radiators')
        self.assertTrue(self.find('accessoryRadiatorNote').property('visible'))
        self.assertFalse(self.find('accessoryDownload').property('visible'))
        for style in STYLES:
            self.gallery.setProperty('selectedStyle',style);self.polish()
            self.assertEqual(len(self.value('entries')),24)
        self.gallery.setProperty('brand','Watercool');self.polish()
        self.assertEqual(len(self.value('filtered')),3)
        self.gallery.setProperty('query','360');self.polish()
        self.assertEqual([r['id'] for r in self.value('filtered')],['watercool-heatkiller-rad-360-l'])
        self.gallery.setProperty('demoMotion',True);self.polish()
        self.assertFalse(self.gallery.property('motionActive'))
        self.assertIsNone(self.find('accessoryDemoClock').property('subscription'))
        self.assertTrue(self.stats.requests)
        self.assertTrue(all(r[0]=='radiator' for r in self.stats.requests))
        self.assertTrue(all(len(rows)<=16 for rows in self.stats.demands))
        calls=len(self.stats.requests)
        self.gallery.setProperty('phase',117.);self.polish()
        self.assertEqual(len(self.stats.requests),calls)
        self.gallery.close();self.polish()
        self.assertEqual(self.value('library'),{})
        self.assertFalse(self.stats.activity[-1])


class RadiatorColdDispatch053Tests(unittest.TestCase):
    def test_controller_cold_miss_defers_mesh_work_and_retains_existing_cache_limit(self):
        # Execute the actual short controller method without its app/config
        # imports. A cold radiator must follow the asynchronous loop path.
        tree=ast.parse((ROOT/'assembly_tools.py').read_text(encoding='utf8'))
        owner=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='AssemblyTools')
        method=copy.deepcopy(next(n for n in owner.body if isinstance(n,ast.FunctionDef) and n.name=='accessoryModelArt'))
        method.decorator_list=[];scope={}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),'assembly_tools.py','exec'),scope)
        import accessory_art
        dummy=SimpleNamespace(_accessory_gallery_active=True,_accessory_jobs=SimpleNamespace(done=set()))
        with patch.object(accessory_art,'art',side_effect=AssertionError('No GUI mesh build')):
            result=scope['accessoryModelArt'](dummy,'radiator','corsair-xr5-240','miniature')
        self.assertEqual(result,dict(pending=True))
        self.assertEqual(accessory_art.cache_info()['max_entries'],16)
        dummy._accessory_gallery_active=False
        self.assertEqual(scope['accessoryModelArt'](dummy,'radiator','corsair-xr5-240','miniature'),{})


if __name__=='__main__':unittest.main()
