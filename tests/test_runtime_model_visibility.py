"""Shared WinEvent/factory admission with fake monitors and no native windows."""
import ctypes as c
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
from PySide6.QtCore import QObject,QRect,Qt,Signal
from PySide6.QtWidgets import QApplication
from native_runtime import Runtime,_DesktopAwareTopBarManager,_desktop_session_ready


class Callback:
    def __init__(self):self.callbacks=[]
    def connect(self,value):self.callbacks.append(value)
    def emit(self,*args):
        for value in tuple(self.callbacks):value(*args)


class Screen:
    def __init__(self,name,x):self.identity=name;self.rect=(x,0,x+1920,1080)
    def availableGeometry(self):return QRect(self.rect[0],0,1920,1040)
    def name(self):return self.identity


class Controller(QObject):
    dataChanged=Signal();motionChanged=Signal()
    def __init__(self):
        super().__init__();self._saved={'widgets':{'cpu':{'presentation':'hardware'}},'top_bar':{'monitor_mode':'primary'}}
        self.saved=self._saved;self.motionEnabled=True;self.status=[]
    def set_status(self,text,**kwargs):self.status.append((text,kwargs))
    def set_top_bar_status(self,*args,**kwargs):pass


class Adapter:
    def __init__(self,screens):self.screens=screens;self.queries=0
    def screen_identity(self,screen):
        self.queries+=1
        return SimpleNamespace(native_id=screen.identity,monitor_handle=self.screens.index(screen)+1)
    def _monitor_info(self,handle):
        self.queries+=1;rect=self.screens[handle-1].rect
        return SimpleNamespace(rcMonitor=SimpleNamespace(**dict(zip(('left','top','right','bottom'),rect))))


class Guard:
    def __init__(self,notify):
        self.notify=notify;self.closed=False;self.failure=None;self._known=True
        self.blocked_ids=set();self.queries=[];self.closes=0;self.starts=0;self._monitors={}
    def start(self):self.starts+=1
    def blocked(self,monitors):
        self.queries.append(dict(monitors));self._monitors=dict(monitors)
        return frozenset(set(monitors)&self.blocked_ids)
    def close(self):self.closed=True;self.closes+=1;return True


class Window:
    def __init__(self,screen,mode=None):
        self.target=screen;self.window_mode=mode;self.visible=True;self.exposed=True;self.minimized=False
        self.props={'spec':{'cells':[{'key':'cpu'}]},'modelMotionAllowed':False};self.calls=[]
        self.closed=Callback();self.handle=SimpleNamespace(setScreen=self.set_screen,screenChanged=Callback())
        self.viewport=SimpleNamespace(set_motion_enabled=lambda value:self.calls.append(('motion',value)))
    def property(self,name):return self.props.get(name)
    def setProperty(self,name,value):self.props[name]=value;self.calls.append(('property',name,value));return True
    def screen(self):return self.target
    def isVisible(self):return self.visible
    def isExposed(self):return self.exposed
    def windowState(self):return Qt.WindowMinimized if self.minimized else Qt.WindowNoState
    def isMinimized(self):return self.minimized
    def hide(self):self.visible=False;self.calls.append(('hide',))
    def set_screen(self,target):self.target=target;self.calls.append(('screen',target))
    def setMinimumSize(self,*size):self.calls.append(('minimum',*size))
    def resize(self,*size):self.calls.append(('resize',*size))
    def winId(self):return 123
    def windowHandle(self):return self.handle
    def move(self,*point):self.calls.append(('move',*point))
    def installEventFilter(self,owner):self.calls.append(('watch',))
    def synchronize(self,spec):self.calls.append(('synchronize',spec))
    def setAttribute(self,*args):self.calls.append(('attribute',*args))
    def showNormal(self):self.visible=True;self.calls.append(('show',))
    def show(self):self.visible=True;self.calls.append(('show',))
    def lower(self):self.calls.append(('lower',))
    def raise_(self):self.calls.append(('raise',))
    def activateWindow(self):self.calls.append(('activate',))
    def close(self):self.visible=False;self.calls.append(('close',));self.closed.emit()
    def _clock_active(self,value):self.calls.append(('clock',value))
    def update_readings(self):self.calls.append(('readings',self.property('modelMotionAllowed')))


class ModelRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        assert cls.app.platformName()=='offscreen'
    def setUp(self):
        self.enterContext(patch('ctypes.WinDLL',side_effect=AssertionError('No native query')))
        self.enterContext(patch('subprocess.Popen',side_effect=AssertionError('No processes')))
        self.session=self.enterContext(patch('native_runtime._desktop_session_ready',return_value=True))
        self.screens=[Screen('one',0),Screen('two',1920)];self.guards=[]
        self.runtime=SimpleNamespace(headless=False,shutting_down=False,controller=Controller(),widgets={},
            _widget_appearance_config={},_model_guard_monitors={},_assembly_guard_monitors={},_model_monitor_cache={},
            _assembly_window=None,_assembly_guard_hidden=False,engine=object(),
            app=SimpleNamespace(screens=lambda:self.screens,primaryScreen=lambda:self.screens[0],platformName=lambda:'offscreen'))
        def guard_factory(notify):
            value=Guard(notify);self.guards.append(value);return value
        self.bar=_DesktopAwareTopBarManager(self.runtime,adapter=Adapter(self.screens),fullscreen_guard_factory=guard_factory)
        self.runtime.top_bar=self.bar
    def tearDown(self):
        self.runtime.shutting_down=True;self.bar.close();self.bar.deleteLater()
    def refresh(self):Runtime.refresh_model_motion(self.runtime)
    def add(self,key,screen=0):
        value=Window(self.screens[screen]);self.runtime.widgets[key]=value;return value

    def test_no_topbar_hosts_still_start_one_guard_and_animate_visible_hardware(self):
        window=self.add('cpu');self.refresh()
        self.assertEqual(self.bar.hosts,{})
        self.assertEqual(len(self.guards),1);self.assertTrue(window.property('modelMotionAllowed'))
        self.assertEqual(set(self.guards[0].queries[-1]),{'one'})
        self.refresh();self.assertEqual(len(self.guards),1)
        self.bar._stop_fullscreen_guard();self.assertFalse(self.guards[0].closed)

    def test_two_screens_game_blocks_only_its_models_and_event_refresh_is_shared(self):
        first=self.add('a',0);second=self.add('b',1);self.refresh();guard=self.guards[0]
        guard.blocked_ids={'one'};guard.notify();self.assertTrue(self.bar._foreground_timer.isActive())
        self.bar._foreground_timer.stop();self.bar._foreground_visibility_changed()
        self.assertFalse(first.property('modelMotionAllowed'));self.assertTrue(second.property('modelMotionAllowed'))
        self.assertFalse(first.visible);self.assertTrue(second.visible)
        self.assertEqual(set(guard.queries[-1]),{'one','two'})

    def test_pinned_model_is_hidden_through_game_and_restored_without_activation(self):
        window=self.add('cpu');window.props['spec']['layer']='pinned';self.refresh();guard=self.guards[0]
        guard.blocked_ids={'one'};self.refresh()
        self.assertFalse(window.visible);self.assertIs(self.runtime._model_guard_hidden['cpu'],window)
        self.refresh();self.assertFalse(guard.closed);self.assertFalse(window.visible)
        guard.blocked_ids=set();self.refresh()
        self.assertTrue(window.visible);self.assertTrue(window.property('modelMotionAllowed'))
        self.assertNotIn('cpu',self.runtime._model_guard_hidden)
        self.assertIn(('lower',),window.calls);self.assertNotIn(('activate',),window.calls)

    def test_initial_pinned_model_is_not_shown_before_game_admission(self):
        window=self.add('cpu');window.visible=False;window.props['spec']['layer']='pinned'
        self.runtime._model_guard_monitors={'one':self.screens[0].rect}
        self.bar._ensure_fullscreen_guard();guard=self.guards[-1];guard.blocked_ids={'one'}
        self.assertEqual(Runtime._admit_model_windows(self.runtime),{'cpu'})
        self.assertFalse(window.visible);self.assertNotIn(('show',),window.calls)
        guard.blocked_ids=set();self.refresh()
        self.assertTrue(window.visible);self.assertEqual(window.calls.count(('show',)),1)

    def test_paused_bar_keeps_model_guard_and_last_model_close_unhooks(self):
        window=self.add('cpu');self.refresh();guard=self.guards[0]
        self.bar.paused=True;guard.blocked_ids={'one'};guard.notify()
        self.assertTrue(self.bar._foreground_timer.isActive())
        self.bar._foreground_timer.stop();self.bar._foreground_visibility_changed()
        self.assertFalse(window.property('modelMotionAllowed'));self.assertFalse(guard.closed)
        self.runtime.widgets.clear();self.refresh()
        self.assertTrue(guard.closed);self.assertEqual(guard.closes,1)
        self.assertIsNone(self.bar._fullscreen_guard)

    def test_shutdown_releases_shared_hooks_even_with_visible_models(self):
        self.add('cpu');self.refresh();guard=self.guards[0]
        self.runtime.shutting_down=True;self.bar.close()
        self.assertTrue(guard.closed);self.assertEqual(guard.closes,1)

    def test_unknown_lock_minimize_exposure_and_restore_are_real_flow_gates(self):
        window=self.add('cpu');self.refresh();guard=self.guards[0]
        for known,failure,session in ((False,None,True),(True,'failed',True),(True,None,None),(True,None,False)):
            guard._known=known;guard.failure=failure;self.session.return_value=session;self.refresh()
            self.assertFalse(window.property('modelMotionAllowed'))
        guard._known=True;guard.failure=None;self.session.return_value=True
        window.minimized=True;self.refresh();self.assertFalse(window.property('modelMotionAllowed'))
        window.minimized=False;window.exposed=False;self.refresh();self.assertFalse(window.property('modelMotionAllowed'))
        window.exposed=True;self.refresh();self.assertTrue(window.property('modelMotionAllowed'))

    def test_plain_numeric_cards_add_no_input_desktop_or_foreground_queries(self):
        window=self.add('cpu');self.runtime.controller._saved['widgets']['cpu']['presentation']='metrics'
        self.refresh();self.assertFalse(window.property('modelMotionAllowed'))
        self.assertEqual(self.guards,[]);self.session.assert_not_called()
        self.assertEqual(self.bar.adapter.queries,0)

    def test_unknown_native_mapping_hides_pinned_model_and_recovers_when_known(self):
        window=self.add('cpu');window.props['spec']['layer']='pinned'
        def unavailable(screen):raise ValueError('monitor changed')
        with patch.object(self.bar.adapter,'screen_identity',new=unavailable):
            self.refresh()
        self.assertFalse(window.visible);self.assertFalse(window.property('modelMotionAllowed'))
        self.assertIs(self.runtime._model_guard_hidden['cpu'],window)
        self.refresh();self.assertTrue(window.visible);self.assertTrue(window.property('modelMotionAllowed'))
        self.assertNotIn(('activate',),window.calls)

    def test_guard_initialization_exception_hides_pinned_until_safe_recovery(self):
        window=self.add('cpu');window.props['spec']['layer']='pinned'
        def unavailable():raise RuntimeError('guard unavailable')
        with patch.object(self.bar,'_ensure_fullscreen_guard',new=unavailable):self.refresh()
        self.assertFalse(window.visible);self.assertFalse(window.property('modelMotionAllowed'))
        self.refresh();self.assertTrue(window.visible);self.assertTrue(window.property('modelMotionAllowed'))

    def test_existing_geometry_refresh_invalidates_native_rect_cache_before_next_query(self):
        window=self.add('cpu');self.refresh();guard=self.guards[0]
        self.assertEqual(guard.queries[-1]['one'],(0,0,1920,1080))
        self.screens[0].rect=(0,0,2560,1440);calls=[]
        self.runtime.apply=lambda rearrange:calls.append(rearrange)
        Runtime.fit_windows(self.runtime)
        self.assertEqual(self.runtime._model_monitor_cache,{})
        self.assertEqual(calls,[False]);self.refresh()
        self.assertEqual(guard.queries[-1]['one'],(0,0,2560,1440))

    def test_desktop_factory_uses_compact_size_and_never_activates(self):
        made=[]
        def factory(controller,engine,spec):
            value=Window(self.screens[0],spec['options']['window_mode']);value.visible=False;made.append(value);return value
        with patch('assembly_window.create_assembly_window',new=factory):
            Runtime.open_assembly_view(self.runtime,{'options':{'window_mode':'desktop'}})
        window=made[0];self.assertIs(self.runtime._assembly_window,window)
        self.assertIn(('minimum',280,300),window.calls);self.assertIn(('resize',420,480),window.calls)
        self.assertIn(('show',),window.calls);self.assertIn(('lower',),window.calls)
        self.assertNotIn(('raise',),window.calls);self.assertNotIn(('activate',),window.calls)

    def test_target_game_lock_or_unknown_blocks_factory_before_creation(self):
        with patch('assembly_window.create_assembly_window',new=lambda *args: self.fail('must not construct')):
            self.session.return_value=None
            Runtime.open_assembly_view(self.runtime,{'options':{'window_mode':'desktop'}})
            self.session.return_value=True
            self.runtime._model_guard_monitors={'one':self.screens[0].rect}
            self.bar._ensure_fullscreen_guard();self.guards[-1].blocked_ids={'one'}
            Runtime.open_assembly_view(self.runtime,{'options':{'window_mode':'desktop'}})
        self.assertIsNone(self.runtime._assembly_window)

    def test_mode_replacement_and_stale_closed_signal_cannot_clear_new_window(self):
        made=[]
        def factory(controller,engine,spec):
            value=Window(self.screens[0],spec['options']['window_mode']);made.append(value);return value
        with patch('assembly_window.create_assembly_window',new=factory),patch('native_runtime.foreground_fullscreen',return_value=False):
            Runtime.open_assembly_view(self.runtime,{'options':{'window_mode':'desktop'}})
            old=made[-1]
            Runtime.open_assembly_view(self.runtime,{'options':{'window_mode':'inspect'}})
            new=made[-1];self.assertIn(('close',),old.calls)
            old.closed.emit();self.assertIs(self.runtime._assembly_window,new)
            self.assertIn(('raise',),new.calls);self.assertIn(('activate',),new.calls)

    def test_nonstring_desktop_mode_is_strictly_treated_as_inspection(self):
        made=[]
        def factory(controller,engine,spec):
            value=Window(self.screens[0],'inspect');made.append(value);return value
        with patch('assembly_window.create_assembly_window',new=factory),patch('native_runtime.foreground_fullscreen',return_value=False):
            for value in (True,None,['desktop']):
                Runtime.open_assembly_view(self.runtime,{'options':{'window_mode':value}})
        self.assertEqual(len(made),1)
        self.assertIn(('resize',1080,800),made[0].calls)
        self.assertIn(('activate',),made[0].calls)

    def test_game_arriving_during_factory_baking_is_rechecked_before_show(self):
        made=[]
        def factory(controller,engine,spec):
            value=Window(self.screens[0],'desktop');value.visible=False;made.append(value)
            self.guards[-1].blocked_ids={'one'}
            return value
        with patch('assembly_window.create_assembly_window',new=factory):
            Runtime.open_assembly_view(self.runtime,{'options':{'window_mode':'desktop'}})
        self.assertEqual(len(made),1);self.assertNotIn(('show',),made[0].calls)
        self.assertIn(('close',),made[0].calls);self.assertIsNone(self.runtime._assembly_window)
        self.assertEqual(self.runtime._assembly_guard_monitors,{})

    def test_3d_same_screen_game_hides_and_recovery_never_activates(self):
        window=Window(self.screens[0],'desktop');self.runtime._assembly_window=window
        self.runtime._assembly_guard_monitors={'one':self.screens[0].rect};self.refresh();guard=self.guards[0]
        self.assertTrue(window.property('modelMotionAllowed'))
        guard.blocked_ids={'one'};self.refresh()
        self.assertFalse(window.visible);self.assertFalse(window.property('modelMotionAllowed'))
        self.assertIn(('clock',False),window.calls)
        guard.blocked_ids=set();self.refresh()
        self.assertTrue(window.visible);self.assertTrue(window.property('modelMotionAllowed'))
        self.assertIn(('lower',),window.calls);self.assertNotIn(('activate',),window.calls)

    def test_3d_minimize_restore_and_unknown_do_not_override_user_visibility(self):
        window=Window(self.screens[0],'desktop');self.runtime._assembly_window=window
        self.refresh();window.minimized=True;self.refresh()
        self.assertFalse(window.property('modelMotionAllowed'));self.assertTrue(window.visible)
        window.minimized=False;self.refresh();self.assertTrue(window.property('modelMotionAllowed'))
        self.guards[0].failure='unknown';self.refresh()
        self.assertFalse(window.visible);self.assertFalse(window.property('modelMotionAllowed'))


class InputDesktopReadTests(unittest.TestCase):
    def test_name_and_input_checks_close_every_handle_and_unknown_never_passes(self):
        class Api:
            def __init__(self):self.name='Default';self.input=1;self.closed=[];self.handle=8
            def OpenInputDesktop(self,*args):return self.handle
            def GetUserObjectInformationW(self,handle,kind,buffer,*args):
                if kind==2:buffer.value=self.name
                else:c.cast(buffer,c.POINTER(c.c_int32)).contents.value=self.input
                return 1
            def CloseDesktop(self,handle):self.closed.append(handle);return 1
        api=Api()
        with patch('native_runtime._input_desktop_api',api):
            self.assertTrue(_desktop_session_ready());self.assertEqual(api.closed,[8])
            api.name='Winlogon';self.assertFalse(_desktop_session_ready())
            api.name='Default';api.input=0;self.assertFalse(_desktop_session_ready())
            api.handle=0;self.assertIsNone(_desktop_session_ready());self.assertEqual(len(api.closed),3)


if __name__=='__main__':unittest.main()
