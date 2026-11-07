"""Lazy editor failure/reentry/IPC contracts using plain Python owners only."""
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from native_runtime import Runtime,LocalServer


class Signal:
    def __init__(self):self.callbacks=[]
    def connect(self,callback):self.callbacks.append(callback)


class Window:
    def __init__(self,name='settingsWindow'):
        self.name=name;self.visibleChanged=Signal();self.deleted=0;self.shown=0
        self.values={'pendingEdits':False,'page':0,'unsaved_text':''}
        self.on_icon=None;self.visible=False
    def objectName(self):return self.name
    def deleteLater(self):self.deleted+=1
    def setIcon(self,icon):
        if self.on_icon:self.on_icon()
    def setPersistentGraphics(self,value):pass
    def setPersistentSceneGraph(self,value):pass
    def property(self,name):return self.values.get(name)
    def setProperty(self,name,value):self.values[name]=value
    def isVisible(self):return self.visible
    def isActive(self):return False
    def windowState(self):return 0
    def resize(self,*args):pass
    def setPosition(self,*args):pass
    def x(self):return 50
    def y(self):return 50
    def width(self):return 900
    def height(self):return 600
    def showNormal(self):self.shown+=1
    def raise_(self):pass
    def requestActivate(self):pass


class Geometry:
    def x(self):return 0
    def y(self):return 0
    def width(self):return 1920
    def height(self):return 1080
    def right(self):return 1919
    def bottom(self):return 1079
    def contains(self,x,y):return 0<=x<1920 and 0<=y<1080


class Application:
    def __init__(self):self.quit_calls=0
    def platformName(self):return 'windows'
    def windowIcon(self):return None
    def primaryScreen(self):return SimpleNamespace(availableGeometry=Geometry)
    def screens(self):return [self.primaryScreen()]
    def quit(self):self.quit_calls+=1


class Engine:
    def __init__(self):self.roots=[];self.loads=0;self.next=Window;self.on_load=None
    def rootObjects(self):return list(self.roots)
    def load(self,url):
        self.loads+=1
        self.roots.append(self.next())
        if self.on_load:self.on_load()


class Owner:
    def __init__(self,events,name):
        self.events=events;self.name=name;self.paintFailed=Signal();self.disposed=False
        self.start_callback=None;self.fail_start=False
    def paint_background(self,*args):pass
    def start(self):
        self.events.append('start '+self.name)
        if self.start_callback:self.start_callback()
        if self.fail_start:raise RuntimeError('bridge start fixture')
    def close(self):self.events.append('close '+self.name)
    def dispose(self):self.events.append('dispose '+self.name);self.disposed=True
    def status(self):return {'disposed':self.disposed}


class Client:
    def __init__(self,message):self.raw=(json.dumps(message)+'\n').encode();self.response=None
    def property(self,name):return b''
    def readAll(self):return self.raw
    def write(self,raw):self.response=json.loads(raw)
    def flush(self):pass
    def disconnectFromServer(self):pass


def fixture():
    controller=SimpleNamespace(_draft={'theme':'dark'},_saved={'top_bar':{'items':[]}},dirty=False,
        version='fixture',motionEnabled=False,_top_bar_status={},_material={})
    controller.set_status=lambda *args,**kwargs:None
    runtime=SimpleNamespace(shutting_down=False,_settings_loading=False,settings=None,
        settings_host=None,settings_blur=None,settings_material=None,controller=controller,
        headless=False,app=Application(),engine=Engine(),widgets={},composition={},
        cpu_temperature_launcher=None,top_bar=None)
    for name in ('refresh_appearance','_settings_material_request','_publish_settings_material',
                 '_release_settings_surface','_settings_paint_failed','compose'):
        setattr(runtime,name,lambda *args,**kwargs:None)
    return runtime


class ExtendedLazySettingsTests(unittest.TestCase):
    def setUp(self):
        self.runtime=fixture();self.events=[];self.owners=[];self.bridge_kwargs=[]
        def host(window):
            owner=Owner(self.events,'host');self.owners.append(owner);return owner
        def blur(**kwargs):
            owner=Owner(self.events,'blur');self.owners.append(owner);return owner
        def bridge(*args,**kwargs):
            owner=Owner(self.events,'bridge');self.owners.append(owner);self.bridge_kwargs.append(kwargs);return owner
        for target,replacement in (('native_runtime.SettingsBackdropHost',host),
                                   ('native_runtime.ThinRasterAcrylicMaterial',blur),
                                   ('native_runtime.SettingsMaterialBridge',bridge)):
            guard=patch(target,new=replacement);guard.start();self.addCleanup(guard.stop)

    def test_prior_engine_root_is_not_mistaken_for_the_editor(self):
        old=Window('topBarWindow');self.runtime.engine.roots.append(old)
        editor=Runtime.ensure_settings(self.runtime)
        self.assertIs(editor,self.runtime.engine.roots[1])
        self.assertEqual(old.deleted,0)
        self.assertEqual(self.runtime.engine.loads,1)
        self.assertEqual(self.events,['start bridge'])
        kwargs=self.bridge_kwargs[0]
        self.assertIs(kwargs['frame_source'],editor)
        self.assertTrue(kwargs['allow_hidden_prepare']);self.assertTrue(kwargs['wait_for_first_frame'])
        self.assertTrue(kwargs['activation_requests'])

    def test_retry_releases_only_failed_roots_and_preserves_prior_roots(self):
        old=Window('topBarWindow');self.runtime.engine.roots.append(old)
        self.runtime.engine.next=lambda:Window('unrelatedWindow')
        with self.assertRaisesRegex(RuntimeError,'Native settings could not load'):
            Runtime.ensure_settings(self.runtime)
        failed=self.runtime.engine.roots[1]
        self.assertEqual((old.deleted,failed.deleted),(0,1))
        self.assertIsNone(self.runtime.settings);self.assertFalse(self.runtime._settings_loading)
        self.runtime.engine.next=Window
        retry=Runtime.ensure_settings(self.runtime)
        self.assertIs(retry,self.runtime.engine.roots[2]);self.assertEqual(old.deleted,0)

    def test_partial_bridge_failure_releases_in_original_dependency_order_then_retries(self):
        def failing_bridge(*args,**kwargs):
            owner=Owner(self.events,'bridge');owner.fail_start=True;return owner
        with patch('native_runtime.SettingsMaterialBridge',new=failing_bridge):
            with self.assertRaisesRegex(RuntimeError,'bridge start fixture'):
                Runtime.ensure_settings(self.runtime)
        failed=self.runtime.engine.roots[-1]
        self.assertEqual(self.events,['start bridge','close bridge','close blur','dispose host'])
        self.assertEqual(failed.deleted,1)
        for name in ('settings','settings_host','settings_blur','settings_material'):
            self.assertIsNone(getattr(self.runtime,name))
        self.assertFalse(self.runtime._settings_loading)
        self.assertIsNotNone(Runtime.ensure_settings(self.runtime))

    def test_reentrant_load_request_is_ignored_and_does_not_duplicate_the_tree(self):
        seen=[]
        self.runtime.engine.on_load=lambda:seen.append(Runtime.ensure_settings(self.runtime))
        self.assertIsNotNone(Runtime.ensure_settings(self.runtime))
        self.assertEqual(seen,[None]);self.assertEqual(self.runtime.engine.loads,1)

    def test_shutdown_during_qml_load_does_not_create_native_owners_or_cache_a_root(self):
        self.runtime.engine.on_load=lambda:setattr(self.runtime,'shutting_down',True)
        self.assertIsNone(Runtime.ensure_settings(self.runtime))
        self.assertIsNone(self.runtime.settings)
        self.assertEqual(self.runtime.engine.roots[-1].deleted,1)
        self.assertEqual(self.owners,[]);self.assertFalse(self.runtime._settings_loading)

    def test_show_request_during_initialization_cannot_display_an_incomplete_editor(self):
        self.runtime.settings=Window();self.runtime._settings_loading=True
        Runtime.show_settings(self.runtime)
        self.assertEqual(self.runtime.settings.shown,0)
        self.assertEqual(self.runtime.engine.loads,0)

    def test_shutdown_from_icon_change_aborts_native_setup_and_releases_candidate(self):
        window=Window();window.on_icon=lambda:setattr(self.runtime,'shutting_down',True)
        self.runtime.engine.next=lambda:window
        self.assertIsNone(Runtime.ensure_settings(self.runtime))
        self.assertIsNone(self.runtime.settings)
        self.assertEqual(window.deleted,1)
        self.assertEqual(self.owners,[])
        self.assertFalse(self.runtime._settings_loading)

    def test_cached_hidden_editor_keeps_pending_input_and_draft_without_reload(self):
        editor=Window();editor.values.update(pendingEdits=True,page=3,unsaved_text='uncommitted')
        self.runtime.settings=editor
        self.assertIs(Runtime.ensure_settings(self.runtime),editor)
        self.assertEqual(self.runtime.engine.loads,0)
        self.assertEqual(editor.values['unsaved_text'],'uncommitted')
        self.assertTrue(Runtime._settings_pending(self.runtime))

    def test_disposed_host_rejects_queued_show_without_recreating_editor(self):
        self.runtime.settings=Window()
        host=Owner(self.events,'host');host.disposed=True;self.runtime.settings_host=host
        Runtime.show_settings(self.runtime,'__history__')
        self.assertEqual(self.runtime.settings.shown,0)
        self.assertEqual(self.runtime.settings.values['page'],0)
        self.assertEqual(self.runtime.engine.loads,0)

    def test_shutdown_rejects_both_load_and_show_without_owners_or_roots(self):
        self.runtime.shutting_down=True
        self.assertIsNone(Runtime.ensure_settings(self.runtime))
        Runtime.show_settings(self.runtime)
        self.assertEqual(self.runtime.engine.loads,0)
        self.assertEqual(self.runtime.engine.roots,[])
        self.assertEqual(self.owners,[])

    def test_quit_rechecks_new_pending_input_after_a_clean_response(self):
        server=SimpleNamespace(runtime=self.runtime,application=self.runtime.app)
        callbacks=[]
        def queue(delay,callback):callbacks.append(callback)
        client=Client({'command':'quit_if_clean'})
        with patch('native_runtime.QTimer.singleShot',new=queue):LocalServer.read(server,client)
        self.assertTrue(client.response['quitting']);self.assertEqual(len(callbacks),1)
        editor=Window();editor.values['pendingEdits']=True;self.runtime.settings=editor
        callbacks[0]()
        self.assertEqual(self.runtime.app.quit_calls,0)
        self.assertEqual(self.runtime.engine.loads,0)

    def test_dirty_controller_and_pending_hidden_input_both_block_quit(self):
        server=SimpleNamespace(runtime=self.runtime,application=self.runtime.app)
        for dirty,pending in ((True,False),(False,True)):
            self.runtime.controller.dirty=dirty
            self.runtime.settings=Window() if pending else None
            if pending:self.runtime.settings.values['pendingEdits']=True
            client=Client({'command':'quit_if_clean'})
            LocalServer.read(server,client)
            self.assertEqual(client.response,dict(ok=False,dirty=True,reason='unsaved_changes'))
        self.assertEqual(self.runtime.engine.loads,0)

    def test_status_query_never_loads_a_dormant_editor(self):
        server=SimpleNamespace(runtime=self.runtime,application=self.runtime.app)
        client=Client({'command':'status'});LocalServer.read(server,client)
        self.assertTrue(client.response['ok']);self.assertFalse(client.response['settings_loaded'])
        self.assertFalse(client.response['settings_active']);self.assertFalse(client.response['settings_minimized'])
        self.assertFalse(client.response['dirty']);self.assertEqual(self.runtime.engine.loads,0)


if __name__=='__main__':unittest.main()
