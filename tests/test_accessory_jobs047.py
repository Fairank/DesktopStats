"""Real queued graphics lifecycle; never show/create a platform window or GL."""
import builtins
import copy
import hashlib
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE','Basic')
from PySide6.QtCore import QCoreApplication,QEvent,QObject,QThread,QTimer,QUrl
from PySide6.QtQml import QQmlComponent,QQmlEngine
from PySide6.QtQuick import QQuickItem,QQuickWindow
from PySide6.QtWidgets import QApplication

from accessory_cancel047 import ArtCancelled,checkpoint
from accessory_jobs047 import ArtJobs,_LIVE
import hardware_packs as packs

ROOT=Path(__file__).resolve().parents[1]
# Frozen0.46 reviewed Core1 SVG bytes, independent of the new row-only wrapper.
CORE1_046={
 'miniature':'afaaa0de500164120251561213e8e0e72545b89d8110b25945dee703fa099eac',
 'cartoon':'c64c3338a346e06a248dfb32bfe14c73a232a2776c0b70cbac532af96be78560',
 'notebook_color':'26b87d4760cb8ddfad0735a13f0ce4a34716db57065b5042a99c932a1554db29',
 'notebook_line':'630af8aa3f2641a27d9c75163d35f668d19e87a4233dcb460248da213d788022',
 'sticker':'7577665f6ec4485c3686d963467e5526a5a98a7b2495c20fcb85e2341ffad953',
 'papercut':'7ece378e41c01585186ab223a2efa9c9070d76eb192f7b486a1ed914eb58ca32',
 'inkwash':'08e1ea69caf0802ec427c80294505583f2a7bb04e41a57b2334eeb4b93dc0b8f',
 'classic':'e7dd70ee32fca91fe2b28c38c5de587ede0d4ff459a23afe37e20b36142cd628',
 'outline':'03c0ce5b11cb69baf693f03048ff9d4a831d22ec186e0afe058feba47186f168',
 'solid':'5ca753e1d0f2cd4630b213df68f0170801b7286d0c15279c954aa7e2532faeec',
 'soft':'9c897f21cc2b1a2da44f8c7e2d1dde5f404b1dae848e8a15ae79209781a91e83',
 'sketch':'bf0b92654e2addc4a9d7331baa990a4cf8560d528c80944a896750af8f41080e',
 'notebook_smile':'294a04433f4336e3b7bafe63ed9a493e315c8d72658ebcaebc2da4f872645fa8',
}


class ArtJobs047Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.jobs=[];self.gates=[]
        for target in ('ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(target,side_effect=AssertionError('No native/device/network/Python-worker work')))

    def pump(self,condition,seconds=4):
        until=time.monotonic()+seconds
        while not condition() and time.monotonic()<until:
            self.app.processEvents();threading.Event().wait(.001)
        self.app.processEvents();self.assertTrue(condition())

    def tearDown(self):
        for gate in self.gates:gate.set()
        for job in self.jobs:job.close()
        self.pump(lambda:not _LIVE)
        for job in self.jobs:job.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

    def make(self,producer,prepare=None,generation=None):
        cache={};commits=[];gen=[1] if generation is None else generation
        def gui():self.assertEqual(QThread.currentThread(),self.app.thread())
        def prep(key):
            gui();return prepare(key) if prepare else dict(id=key[1])
        def commit(key,value):gui();cache[key]=value;commits.append((key,value))
        job=ArtJobs(prep,producer,lambda key:key in cache,commit,lambda:gen[0])
        job.activate(True);self.jobs.append(job)
        return job,cache,commits,gen

    def test_cold_idle_creates_no_worker_and_caps_pending_without_materializing_generator(self):
        def forbidden(*args):raise AssertionError('No rendering without demand')
        job,cache,commits,_=self.make(forbidden)
        self.assertIsNone(job.worker);job.demand([]);self.assertFalse(_LIVE)
        job.activate(False);job.demand([('pump','a','miniature',1)])
        self.assertFalse(_LIVE);self.assertEqual(commits,[])

    def test_one_active_task_queue_replacement_and_gui_event_delivery(self):
        started=threading.Event();gate=threading.Event();self.gates.append(gate)
        active=[0,0];lock=threading.Lock()
        def producer(row,style,cancel):
            self.assertNotEqual(QThread.currentThread(),self.app.thread())
            with lock:active[0]+=1;active[1]=max(active)
            try:
                if row['id']=='old':
                    started.set()
                    while not gate.wait(.002):checkpoint(cancel)
                return dict(id=row['id'])
            finally:
                with lock:active[0]-=1
        job,cache,commits,_=self.make(producer)
        job.demand([('pump','old','miniature',1)]);self.pump(started.is_set)
        delivered=[];QTimer.singleShot(0,lambda:delivered.append(True))
        self.pump(lambda:bool(delivered));self.assertFalse(gate.is_set())
        consumed=[]
        def keys():
            for i in range(1000):consumed.append(i);yield ('pump','new-'+str(i),'miniature',1)
        job.demand(keys());self.assertEqual(len(consumed),16);self.assertEqual(len(job.wanted),16)
        self.pump(lambda:len(commits)==16)
        self.assertEqual(active[1],1);self.assertNotIn(('pump','old','miniature',1),cache)

    def test_close_reopen_retires_old_task_before_starting_new_epoch(self):
        gate=threading.Event();started=threading.Event();self.gates.append(gate)
        calls=[]
        def producer(row,style,cancel):
            calls.append(row['id'])
            if row['id']=='old':started.set();gate.wait(3)
            return dict(id=row['id'])
        job,cache,commits,_=self.make(producer)
        job.demand([('pump','old','miniature',1)]);self.pump(started.is_set)
        old=job.worker;job.activate(False);job.activate(True)
        job.demand([('pump','new','notebook_line',1)])
        self.app.processEvents();self.assertIs(job.worker,old);self.assertEqual(calls,['old'])
        gate.set();self.pump(lambda:len(commits)==1)
        self.assertEqual(commits[0][0],('pump','new','notebook_line',1))

    def test_generation_changed_inside_prepare_discards_old_row_and_fetches_fresh(self):
        gen=[1];prepares=[]
        def prepare(key):
            prepares.append(key)
            if len(prepares)==1:gen[0]=2;return dict(id='old-record')
            return dict(id='new-record')
        seen=[]
        def producer(row,style,cancel):seen.append(row['id']);return dict(id=row['id'])
        job,_,commits,_=self.make(producer,prepare,gen)
        job.demand([('pump','chosen','miniature',1)])
        self.pump(lambda:bool(commits));self.assertEqual(seen,['new-record'])
        self.assertEqual(len(prepares),2);self.assertEqual(commits[0][0][3],2)

    def test_pack_update_and_style_scroll_changes_drop_stale_results(self):
        gate=threading.Event();started=threading.Event();self.gates.append(gate)
        def producer(row,style,cancel):
            if row['id']=='old':started.set();gate.wait(3)
            return dict(id=row['id'],style=style)
        job,cache,commits,gen=self.make(producer)
        job.demand([('pump','old','miniature',1)]);self.pump(started.is_set)
        gen[0]=2;job.invalidate();job.demand([('pump','new','notebook_line',2)])
        gate.set();self.pump(lambda:len(commits)==1)
        self.assertEqual(list(cache),[('pump','new','notebook_line',2)])

    def test_controller_lifetime_and_short_wait_timeout_never_destroy_running_qthread(self):
        gate=threading.Event();started=threading.Event();self.gates.append(gate)
        def producer(row,style,cancel):started.set();gate.wait(3);return dict(id='late')
        job,cache,commits,_=self.make(producer)
        job.demand([('pump','slow','miniature',1)]);self.pump(started.is_set)
        worker=job.worker;self.assertIsNone(worker.parent())
        before=time.monotonic();self.assertFalse(job.close(wait=True,timeout_ms=1))
        self.assertLess(time.monotonic()-before,.2)
        self.assertIn(worker,_LIVE);self.assertTrue(worker.isRunning())
        self.jobs.remove(job);job.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        gate.set();self.pump(lambda:worker not in _LIVE)
        self.assertEqual(cache,{});self.assertEqual(commits,[])

    def test_direct_qobject_destruction_cancels_and_never_commits_to_a_dead_owner(self):
        started=threading.Event()
        def producer(row,style,cancel):
            started.set()
            while not cancel.wait(.002):pass
            return dict(id='late')
        job,cache,commits,_=self.make(producer)
        job.demand([('pump','old','miniature',1)]);self.pump(started.is_set)
        worker=job.worker;self.jobs.remove(job)
        job.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.assertTrue(worker.cancel.is_set());self.pump(lambda:worker not in _LIVE)
        self.assertEqual(cache,{});self.assertEqual(commits,[])

    def test_failed_or_cancelled_producer_is_not_retried_every_binding_read(self):
        calls=[]
        def producer(*args):calls.append(True);raise ValueError('bounded geometry rejected')
        job,cache,commits,_=self.make(producer);key=('pump','bad','miniature',1)
        job.demand([key]);self.pump(lambda:job.worker is None)
        for _ in range(20):job.demand([key])
        self.assertEqual(len(calls),1);self.assertEqual(cache,{})

    def test_repeated_generation_churn_cannot_recurse_or_publish_old_rows(self):
        gen=[1];calls=[]
        def prepare(key):gen[0]+=1;calls.append(key);return dict(id='stale')
        def producer(*args):raise AssertionError('No stable generation was prepared')
        job,cache,commits,_=self.make(producer,prepare,gen)
        job.demand([('pump','chosen','miniature',1)])
        self.assertEqual(len(calls),2);self.assertIsNone(job.worker);self.assertEqual(commits,[])

    def test_missing_or_failed_prepare_notifies_unavailable_without_starting_a_worker(self):
        def producer(*args):raise AssertionError('No reference exists')
        job,cache,commits,_=self.make(producer,lambda key:None)
        notices=[];job.changed.connect(lambda:notices.append(True));key=('pump','removed','miniature',1)
        job.demand([key])
        self.assertIn(key,job.done);self.assertEqual(notices,[True]);self.assertIsNone(job.worker)
        self.assertEqual(cache,{})


class ActualGalleryJobs047Tests(unittest.TestCase):
    pump=ArtJobs047Tests.pump
    make=ArtJobs047Tests.make
    tearDown=ArtJobs047Tests.tearDown
    @classmethod
    def setUpClass(cls):
        ArtJobs047Tests.setUpClass()
        cls.app=ArtJobs047Tests.app
        # Authoring is explicitly outside all runtime/worker guards.
        from tools.export_loop_packs046 import pack_models
        cls.wrapped=[r for r in pack_models() if r['id'] in ('alphacool-core1-black','phanteks-glacier-r260c-d5')]
        cls.archive=packs.make_pack('test-art-jobs047','Art jobs fixture',cls.wrapped,kind='loop')

    def setUp(self):
        ArtJobs047Tests.setUp(self)
        self.tmp=Path(self.enterContext(tempfile.TemporaryDirectory()))
        archive=self.tmp/'input.dspack';archive.write_bytes(self.archive)
        self.store=packs.PackStore(self.tmp/'packs');self.store.install(archive)
        self.enterContext(patch.object(packs,'_store',self.store))
        import accessory_art
        accessory_art.clear_cache()
        original=builtins.__import__;main=threading.get_ident()
        def guarded(name,*args,**kwargs):
            if name.startswith(('liquid_block_pump_expansion046','liquid_fitting_tube_expansion046','tools.export_loop_packs046')):
                raise AssertionError('No runtime author import')
            if threading.get_ident()!=main and name.startswith('PySide6'):
                raise AssertionError('Pure SVG producer must not import Qt')
            return original(name,*args,**kwargs)
        self.enterContext(patch('builtins.__import__',new=guarded))

    def test_detached_nonretaining_lookup_and_actual_worker_match_sync_art(self):
        from liquid_component_runtime046 import get_component
        from liquid_svg046 import art_from_reference,art
        from top_bar_config import HARDWARE_ICON_STYLES
        row=get_component('cpu_block','alphacool-core1-black',retain=False)
        self.assertEqual(len(self.store._selected),0)
        for style in HARDWARE_ICON_STYLES:
            value=art_from_reference(row,style)
            self.assertEqual(value,art('cpu_block',row['id'],style))
            self.assertEqual(hashlib.sha256(value['svg'].encode()).hexdigest(),CORE1_046[style])
        self.store._selected.clear();main=threading.get_ident()
        real=self.store.get_model
        def lookup(*args,**kwargs):
            self.assertEqual(threading.get_ident(),main);self.assertFalse(kwargs['retain'])
            return real(*args,**kwargs)
        with patch.object(self.store,'get_model',side_effect=lookup):
            gen=self.store.generation
            job,cache,commits,_=self.make(art_from_reference,
                lambda key:get_component(key[0],key[1],retain=False),[gen])
            job.demand([('cpu_block',row['id'],'notebook_line',gen)])
            self.pump(lambda:bool(commits))
        self.assertEqual(commits[0][1],art_from_reference(row,'notebook_line'))
        self.assertEqual(len(self.store._selected),0)

    def test_real_cancellation_at_geometry_merge_face_and_edge_stages(self):
        import liquid_svg046 as svg
        import liquid_geometry046 as geometry
        import assembly_style
        row=copy.deepcopy(next(r['reference'] for r in self.wrapped if r['id']=='phanteks-glacier-r260c-d5'))
        for stage in ('build','merge','face','edge'):
            event=threading.Event()
            if stage=='build':target=geometry;name='build_component'
            elif stage=='merge':target=svg;name='_merge_faces'
            elif stage=='face':target=svg._Visibility;name='visible_face'
            else:target=assembly_style;name='edge_batches'
            original=getattr(target,name)
            def cancel_then_call(*args,**kwargs):event.set();return original(*args,**kwargs)
            with self.subTest(stage=stage),patch.object(target,name,new=cancel_then_call):
                with self.assertRaises(ArtCancelled):svg.art_from_reference(row,'notebook_line',event)

    def test_nonretaining_gallery_read_preserves_shared_selected_record_order_and_isolation(self):
        from liquid_component_runtime046 import get_component
        first=get_component('cpu_block','alphacool-core1-black')
        get_component('pump_reservoir','phanteks-glacier-r260c-d5')
        before=list(self.store._selected)
        detached=get_component('cpu_block','alphacool-core1-black',retain=False)
        detached['label']='Changed only in the detached GUI task'
        self.assertEqual(list(self.store._selected),before)
        self.assertEqual(self.store._selected[before[0]]['reference']['label'],first['label'])

    def test_unused_controller_cleanup_never_imports_the_art_or_worker_modules(self):
        import native_controller as controls
        from stats_config import DEFAULT
        with patch.object(controls,'load',return_value=copy.deepcopy(DEFAULT)):
            controller=controls.Controller()
        original=builtins.__import__
        def deny(name,*args,**kwargs):
            if name in ('accessory_art','accessory_jobs047','liquid_svg046'):
                raise AssertionError('Cleanup must not import optional graphics')
            return original(name,*args,**kwargs)
        with patch('builtins.__import__',new=deny):
            controller.setAccessoryGalleryActive(False);controller.close()
        self.assertIsNone(controller._accessory_jobs);controller.deleteLater()

    def test_actual_controller_queued_software_popup_close_phase_and_pack_invalidation(self):
        import accessory_art
        import native_controller as controls
        from stats_config import DEFAULT
        with patch.object(controls,'load',return_value=copy.deepcopy(DEFAULT)):
            controller=controls.Controller()
        self.addCleanup(controller.deleteLater);self.addCleanup(controller.close)
        engine=QQmlEngine();warnings=[];engine.warnings.connect(lambda values:warnings.extend(v.toString() for v in values))
        host=QQuickWindow();host.contentItem().setWidth(640);host.contentItem().setHeight(760)
        engine.rootContext().setContextProperty('stats',controller)
        engine.rootContext().setContextProperty('testHost',host.contentItem())
        component=QQmlComponent(engine);component.setData(b'import QtQuick\nimport "."\nAccessoryGallery { parent:testHost; category:"cpu_block" }',
            QUrl.fromLocalFile(str(ROOT/'native/_jobs047_fixture.qml')))
        popup=component.create();self.assertIsNotNone(popup,[r.toString() for r in component.errors()])
        self.assertIsNone(controller._accessory_jobs)
        self.assertEqual(controller.accessoryModelArt('cpu_block','alphacool-core1-black','miniature'),{})
        popup.open()
        def polish():
            pending=[popup,popup.property('contentItem')]
            while pending:
                item=pending.pop()
                if isinstance(item,QQuickItem):item.ensurePolished();pending.extend(item.childItems())
        for _ in range(5):polish();self.app.processEvents()
        self.pump(lambda:accessory_art.cache_info()['entries']>0)
        self.assertFalse(host.isVisible());self.assertTrue(popup.property('asyncArt'))
        jobs=controller._accessory_jobs;self.assertIsNotNone(jobs)
        self.pump(lambda:jobs.worker is None)
        # Actual async backend at the narrow layout, with a new style demand.
        host.contentItem().setWidth(360);popup.setProperty('selectedStyle','notebook_line')
        for _ in range(5):polish();self.app.processEvents()
        self.pump(lambda:bool(controller.accessoryModelArt('cpu_block','alphacool-core1-black','notebook_line').get('svg')))
        self.pump(lambda:jobs.worker is None)
        self.assertLessEqual(popup.property('width'),360)
        revision=controller.accessoryArtRevision;entries=accessory_art.cache_info()['entries']
        popup.setProperty('phase',37.);polish();self.app.processEvents()
        self.assertEqual(controller.accessoryArtRevision,revision)
        self.assertEqual(accessory_art.cache_info()['entries'],entries)
        self.assertEqual(len(self.store._selected),0)
        popup.setProperty('category','gpu_block');polish();self.app.processEvents()
        note=popup.findChild(QObject,'accessoryStandaloneNote')
        self.assertIsNotNone(note);self.assertTrue(note.property('visible'))
        self.assertEqual(note.property('text'),'独立外观检视；显卡安装与连管尚未验证。')
        pending=[popup.property('contentItem')];names=[]
        while pending:
            item=pending.pop();names.append(item.objectName())
            if isinstance(item,QQuickItem):pending.extend(item.childItems())
        self.assertIn('accessoryCategory_gpu_block',names)
        self.store.remove('test-art-jobs047');controller._hardware_packs_updated()
        self.app.processEvents();self.assertEqual(accessory_art.cache_info()['entries'],0)
        popup.close();self.app.processEvents();self.assertFalse(controller._accessory_gallery_active)
        self.pump(lambda:not _LIVE);self.assertEqual(accessory_art.cache_info()['entries'],0)
        self.assertFalse(host.isVisible())
        popup.deleteLater();component.deleteLater();engine.deleteLater();host.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.assertEqual(warnings,[])


if __name__=='__main__':unittest.main()
