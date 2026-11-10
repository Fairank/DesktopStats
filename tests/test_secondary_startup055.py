"""Execute real startup/mode guard bodies with fake effects, never Qt/native."""
import ast
import copy
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]


def function(path,name,cls=None):
    tree=ast.parse((ROOT/path).read_text('utf-8'),filename=path)
    body=next(n.body for n in tree.body if isinstance(n,ast.ClassDef)and n.name==cls)if cls else tree.body
    node=next(n for n in body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))and n.name==name)
    node.decorator_list=[]
    return node


def actual_function(path,name,scope,cls=None):
    module=ast.fix_missing_locations(ast.Module(body=[function(path,name,cls)],type_ignores=[]))
    exec(compile(module,path,'exec'),scope)
    return scope[name]


class Signal:
    def __init__(self):self.events=[]
    def emit(self,*args):self.events.append(args)


class SecondaryStartup055Tests(unittest.TestCase):
    def test_real_app_configures_profile_before_profile_and_ipc_imports(self):
        node=function('app.py','main')
        configured=next(n.lineno for n in ast.walk(node)if isinstance(n,ast.Call)
            and isinstance(n.func,ast.Name)and n.func.id=='configure')
        imports=[n.lineno for n in ast.walk(node)if isinstance(n,ast.ImportFrom)
                 and n.module in('stats_config','native_ipc')]
        self.assertTrue(imports);self.assertTrue(all(configured<line for line in imports))
        branch=next(n for n in ast.walk(node)if isinstance(n,ast.If)
            and any(isinstance(v,ast.Attribute)and v.attr=='self_check'for v in ast.walk(n.test)))
        text=ast.unparse(branch)
        self.assertIn("DESKTOP_STATS_CPU_BRIDGE_DISABLED",text)
        self.assertIn("DESKTOP_STATS_SECONDARY_CPU_OWNER055",text)
        migrate=next(n for n in ast.walk(node)if isinstance(n,ast.If)
            and isinstance(n.test,ast.Compare)and ast.unparse(n.test)=='secondary is None')
        self.assertIn('legacy_migration','\n'.join(map(ast.unparse,migrate.body)))
        self.assertNotIn('legacy_migration','\n'.join(map(ast.unparse,migrate.orelse)))

    def test_installer_actions_refuse_secondary_before_any_effect_or_import(self):
        def forbidden(*args,**kwargs):raise AssertionError('Forbidden original side effect')
        scope=dict(secondary_active=lambda:True,winreg=SimpleNamespace(CreateKey=forbidden),
                   set_autostart=forbidden)
        for name,args in(('set_autostart',(False,)),('set_autostart',(True,)),
                          ('close_existing',()),('install',()),('remove_registration',())):
            with self.subTest(name=name,args=args):
                fn=actual_function('installer.py',name,dict(scope))
                with self.assertRaisesRegex(RuntimeError,'第二版'):fn(*args)

    def test_secondary_CLI_quit_and_diagnose_are_not_replaced_by_forced_background(self):
        body=function('app.py','main').body
        forced=next(n for n in body if isinstance(n,ast.If)
            and any(isinstance(v,ast.Assign)and any(isinstance(t,ast.Attribute)and t.attr=='background'
                for t in v.targets)for v in n.body))
        command=next(n for n in body if isinstance(n,ast.Assign)
            and any(isinstance(t,ast.Name)and t.id=='command'for t in n.targets))
        module=ast.fix_missing_locations(ast.Module(body=[forced,command],type_ignores=[]))
        code=compile(module,'<actual secondary CLI command>','exec')
        for background in(False,True):
            for action,expected in(('quit','quit'),('diagnose','diagnose'),('status','status'),('startup','status')):
                args=SimpleNamespace(status=action=='status',quit=action=='quit',diagnose='private.json'if action=='diagnose'else None,
                    background=background,headless=False)
                scope=dict(args=args,secondary=object());exec(code,scope)
                self.assertEqual(scope['command']['command'],expected)
                self.assertEqual(args.background,background or action=='startup')

    def test_secondary_sampler_reconnect_never_queries_Asus_device(self):
        def forbidden(*args,**kwargs):raise AssertionError('No ASUS query or clock needed')
        fn=actual_function('sensors.py','_ensure_asus',dict(secondary_active=lambda:True,
            AsusTemperature=forbidden,time=SimpleNamespace(monotonic=forbidden)),'Sampler')
        self.assertIsNone(fn(SimpleNamespace(asus=None)))
        constructor=function('sensors.py','__init__','Sampler')
        factory=next(n for n in ast.walk(constructor)if isinstance(n,ast.If)
            and ast.unparse(n.test)=='not secondary_active()')
        self.assertIn('AsusTemperature()','\n'.join(map(ast.unparse,factory.body)))
        self.assertNotIn('AsusTemperature()','\n'.join(map(ast.unparse,factory.orelse)))

    def _commit(self,secondary,fail=False):
        previous=dict(autostart=False,cpu_temperature_prompt_on_start=False,language='en',mode='single',
            layout='row',size='medium',group_columns=2,widget_order=[],widgets={})
        draft=copy.deepcopy(previous);draft.update(autostart=True,cpu_temperature_prompt_on_start=True,language='zh')
        controller=SimpleNamespace(_saved=previous,_draft=draft,_replacement_backup=None,
            layout_error=lambda *a:'',_clear_draft_history=lambda:None,_applied_status=lambda *a:None,
            set_status=lambda *a,**k:None,savedChanged=Signal(),draftChanged=Signal(),applyRequested=Signal())
        registrations=[];saved=[]
        def save(value):
            saved.append(copy.deepcopy(value))
            if fail:raise OSError('Fake write failure')
        scope=dict(secondary_active=lambda:secondary,validate=copy.deepcopy,copy=copy,save=save,
            set_autostart=registrations.append,logging=SimpleNamespace(exception=lambda *a:None))
        fn=actual_function('native_controller.py','_commit',scope,'Controller')
        return fn(controller),controller,registrations,saved

    def test_secondary_commit_and_failed_save_never_touch_original_autostart(self):
        for fail in(False,True):
            with self.subTest(fail=fail):
                result,controller,registrations,saved=self._commit(True,fail)
                self.assertEqual(result,not fail)
                self.assertEqual(registrations,[]);self.assertEqual(len(saved),1)
                self.assertFalse(saved[0]['autostart']);self.assertFalse(saved[0]['cpu_temperature_prompt_on_start'])
                self.assertFalse(controller._saved['autostart'])

    def test_primary_commit_and_rollback_keep_existing_autostart_semantics(self):
        result,controller,registrations,saved=self._commit(False)
        self.assertTrue(result);self.assertEqual(registrations,[True]);self.assertTrue(saved[0]['autostart'])
        result,controller,registrations,saved=self._commit(False,True)
        self.assertFalse(result);self.assertEqual(registrations,[True,False])
        self.assertFalse(controller._saved['autostart'])

    def test_runtime_target_and_game_desktop_admission_fail_closed(self):
        primary=SimpleNamespace(name=lambda:r'\\.\DISPLAY36')
        second=SimpleNamespace(name=lambda:r'\\.\DISPLAY37')
        screens=[primary,second]
        scope=dict(secondary_active=lambda:True,secondary_target=lambda:r'\\.\DISPLAY37',
                   _desktop_session_ready=lambda:True,
                   secondary_screen_id=lambda screen:r'\\.\DISPLAY37'if screen is second else r'\\.\DISPLAY36')
        methods=['_secondary_screen','_allowed_screens','_placement_screen','_secondary_admitted']
        runtime_type=type('Runtime',(),{})
        scope['Runtime']=runtime_type
        for name in methods:setattr(runtime_type,name,actual_function('native_runtime.py',name,scope,'Runtime'))
        guard=SimpleNamespace(_known=True,closed=False,failure=None)
        bar=SimpleNamespace(_ensure_fullscreen_guard=lambda:None,_read_foreground_visibility=lambda:None,
                            _fullscreen_guard=guard,_fullscreen_guard_error=None,_foreground_hidden_screens=())
        runtime=runtime_type();runtime.app=SimpleNamespace(screens=lambda:screens,primaryScreen=lambda:primary)
        runtime.top_bar=bar
        runtime_type._model_screen_fact=lambda self,target:(r'\\.\DISPLAY37',(2560,-541,4000,899))
        self.assertIs(runtime._secondary_screen(),second)
        self.assertEqual(runtime._allowed_screens(),[second]);self.assertIs(runtime._placement_screen(),second)
        # Friendly labels are deliberately shuffled; only native identity wins.
        primary.name=lambda:r'\\.\DISPLAY37';second.name=lambda:'Portrait friendly name'
        self.assertIs(runtime._secondary_screen(),second)
        self.assertTrue(runtime._secondary_admitted())
        bar._foreground_hidden_screens=(r'\\.\DISPLAY37',)
        self.assertFalse(runtime._secondary_admitted())
        bar._foreground_hidden_screens=()
        scope['_desktop_session_ready']=lambda:None
        self.assertFalse(runtime._secondary_admitted())
        scope['_desktop_session_ready']=lambda:True
        guard._known=False;self.assertFalse(runtime._secondary_admitted())
        screens[:]=[primary];self.assertFalse(runtime._secondary_admitted())
        self.assertEqual(runtime._allowed_screens(),[]);self.assertIsNone(runtime._placement_screen())

    def test_secondary_inspect_view_hides_for_game_and_restores_without_activation(self):
        state={'visible':True,'motion':True};events=[]
        window=SimpleNamespace(window_mode='inspect',isMinimized=lambda:False,isVisible=lambda:state['visible'],
            hide=lambda:(state.update(visible=False),events.append('hide')),
            showNormal=lambda:(state.update(visible=True),events.append('show')),
            lower=lambda:events.append('lower'),setAttribute=lambda *a:events.append(('attribute',)+a),
            property=lambda key:state['motion'],setProperty=lambda key,value:state.update(motion=value),
            _clock_active=lambda value:None,viewport=SimpleNamespace(set_motion_enabled=lambda value:None),
            update_readings=lambda:None)
        runtime=SimpleNamespace(_assembly_window=window,_assembly_guard_monitors={'second':(0,0,100,100)},
            shutting_down=False)
        scope=dict(secondary_active=lambda:True,Qt=SimpleNamespace(WA_ShowWithoutActivating='noactivate'),
            Runtime=SimpleNamespace(_secondary_window_admitted=lambda runtime,window:True))
        fn=actual_function('native_runtime.py','_update_assembly_motion',scope,'Runtime')
        fn(runtime,True,True,SimpleNamespace(_foreground_hidden_screens=('second',)))
        self.assertFalse(state['visible']);self.assertTrue(runtime._assembly_guard_hidden)
        fn(runtime,True,True,SimpleNamespace(_foreground_hidden_screens=()))
        self.assertTrue(state['visible']);self.assertIn(('attribute','noactivate',True),events)
        self.assertEqual(events[-2:],['show','lower'])
        fn(runtime,True,False,SimpleNamespace(_foreground_hidden_screens=()))
        self.assertFalse(state['visible'])
        scope['secondary_active']=lambda:False;state['visible']=True
        fn(runtime,True,False,SimpleNamespace(_foreground_hidden_screens=()))
        self.assertTrue(state['visible'])  # Existing legacy inspect behavior.


if __name__=='__main__':unittest.main()
