"""Independent profile/IPC and explicit existing-cache selection, no Qt/native."""
import argparse
import copy
import json
from pathlib import Path
import tempfile
import unittest

import secondary_mode055 as mode
from profile_paths import resolve_profile_paths


class Screen:
    def __init__(self,name):self.value=name;self.native_id=name
    def name(self):return self.value
class App:
    def __init__(self):self.primary=Screen(r'\\.\DISPLAY36');self.second=Screen(r'\\.\DISPLAY37')
    def screens(self):return[self.primary,self.second]
    def primaryScreen(self):return self.primary


class SecondaryMode055Tests(unittest.TestCase):
    def args(self,**kw):
        value=dict(secondary=True,install=False,uninstall=False,secondary_profile=None,
            secondary_screen=None,share_installed_cpu_cache=None)
        value.update(kw);return argparse.Namespace(**value)

    def test_profile_and_existing_ipc_are_distinct_without_copying_original(self):
        with tempfile.TemporaryDirectory()as tmp:
            base=Path(tmp);primary=base/'DesktopStats';primary.mkdir();original=primary/'preferences.json';original.write_text('original',encoding='utf-8')
            env={'LOCALAPPDATA':str(base),'USERPROFILE':str(base),'DESKTOP_STATS_DATA':str(primary)}
            session=mode.configure(self.args(),environ=env,primary=primary)
            self.assertNotEqual(session.directory,primary);self.assertEqual(original.read_text(),'original')
            selected=resolve_profile_paths(environ=env)
            self.assertEqual(selected.directory,session.directory);self.assertEqual(selected.ipc_key,str(session.directory))
            self.assertNotEqual(selected.ipc_key,str(primary));self.assertFalse((session.directory/'preferences.json').exists())

    def test_primary_or_child_or_unmarked_profile_cannot_be_adopted(self):
        with tempfile.TemporaryDirectory()as tmp:
            base=Path(tmp);primary=base/'primary';primary.mkdir();env={'LOCALAPPDATA':str(base)}
            for target in(primary,primary/'nested',base):
                with self.subTest(target=str(target)),self.assertRaises(ValueError):
                    mode.configure(self.args(secondary_profile=str(target)),environ=dict(env),primary=primary)
            other=base/'other';other.mkdir();(other/'preferences.json').write_text('not ours')
            with self.assertRaises(ValueError):mode.configure(self.args(secondary_profile=str(other)),environ=dict(env),primary=primary)

    def test_install_and_uninstall_reject_before_environment_or_profile_changes(self):
        for option in('install','uninstall'):
            args=self.args();setattr(args,option,True);env={'LOCALAPPDATA':'C:/Local'};before=dict(env)
            with self.assertRaises(ValueError):mode.configure(args,environ=env,primary='C:/Local/DesktopStats')
            self.assertEqual(env,before)

    def test_legacy_primary_ipc_is_reserved_even_with_relocated_original_profile(self):
        with tempfile.TemporaryDirectory()as tmp:
            base=Path(tmp);legacy=base/'AppData/Local/DesktopStats'
            env={'LOCALAPPDATA':str(base/'AppData/Local'),'USERPROFILE':str(base)}
            with self.assertRaises(ValueError):
                mode.configure(self.args(secondary_profile=str(legacy)),environ=env,primary=base/'relocated/DesktopStats')
            self.assertFalse(legacy.exists())

    def test_cache_owner_is_explicit_transient_and_not_saved_as_a_default(self):
        with tempfile.TemporaryDirectory()as tmp:
            env={'LOCALAPPDATA':tmp};primary=Path(tmp)/'original'
            args=self.args(share_installed_cpu_cache='123:100.25')
            first=mode.configure(args,environ=env,primary=primary)
            self.assertTrue(first.cache_requested);self.assertEqual(json.loads(env[mode.OWNER_ENV]),{'pid':123,'created':100.25})
            marker=(first.directory/mode.MARKER).read_text();self.assertNotIn('123',marker);self.assertNotIn('100.25',marker)
            second=mode.configure(self.args(),environ=env,primary=primary)
            self.assertFalse(second.cache_requested);self.assertNotIn(mode.OWNER_ENV,env)

    def test_second_screen_is_strict_and_profile_seed_changes_no_input(self):
        session=mode.SecondarySession(Path('C:/Secondary'),r'\\.\DISPLAY37',False);app=App();env={}
        self.assertIs(session.select_screen(app,environ=env,identity_reader=lambda screen:screen.native_id),app.second)
        source={'visible':True,'autostart':True,'cpu_temperature_prompt_on_start':True,'top_bar':{'enabled':False,'screens':['original']}}
        before=copy.deepcopy(source);value=session.profile_value(source)
        self.assertEqual(source,before);self.assertFalse(value['autostart']);self.assertFalse(value['cpu_temperature_prompt_on_start'])
        self.assertEqual(value['top_bar']['screens'],[r'\\.\DISPLAY37'])
        app.second.native_id='different'
        with self.assertRaises(ValueError):session.select_screen(app,environ=env,identity_reader=lambda screen:screen.native_id)
        primary=mode.SecondarySession(Path('C:/Secondary'),r'\\.\DISPLAY36',False)
        with self.assertRaises(ValueError):primary.select_screen(app,environ=env,identity_reader=lambda screen:screen.native_id)

    def test_disabled_or_unrequested_secondary_never_constructs_owner_lease(self):
        def forbidden(*args,**kw):raise AssertionError('No owner/native query')
        for env in({mode.MODE_ENV:'1'},{mode.MODE_ENV:'1',mode.OWNER_ENV:'{"pid":123,"created":100}', 'DESKTOP_STATS_CPU_BRIDGE_DISABLED':'1'}):
            result=mode.temperature_reader(environ=env,reader_factory=lambda **kw:kw,lease_factory=forbidden)
            self.assertEqual(result,{'enabled':False})

    def test_secondary_process_identity_is_distinct_and_primary_makes_no_call(self):
        called=[]
        self.assertFalse(mode.apply_process_identity(environ={},setter=lambda value:called.append(value)))
        self.assertEqual(called,[])
        self.assertTrue(mode.apply_process_identity(environ={mode.MODE_ENV:'1'},setter=lambda value:called.append(value)or 0))
        self.assertEqual(called,['Fairank.DesktopStats.Secondary'])
        with self.assertRaises(OSError):
            mode.apply_process_identity(environ={mode.MODE_ENV:'1'},setter=lambda value:-1)

    def test_fresh_CPU_GPU_groups_request_temperature_and_later_V2_preferences_survive(self):
        from cpu_temperature import is_requested
        source={'visible':True,'top_bar':{'items':[{'metric':m,'prefs':{}}
            for m in('cpu_usage','gpu_usage','cpu_temp')]}}
        session=mode.SecondarySession(Path('C:/Second'),None,True,target_screen=r'\\.\DISPLAY37')
        value=session.profile_value(source)
        self.assertTrue(is_requested(value))
        self.assertEqual(value['top_bar']['items'][0]['prefs']['metrics'],['cpu_usage','cpu_temp','cpu_power'])
        self.assertEqual(value['top_bar']['items'][1]['prefs']['style'],'icon_value')
        self.assertNotIn('cpu_temp',[item['metric']for item in value['top_bar']['items']])
        session.fresh=False
        later=session.profile_value(source)
        self.assertTrue(later['visible']);self.assertEqual(later['top_bar']['items'],source['top_bar']['items'])

    def test_native_handle_identity_ignores_shuffled_friendly_labels_and_rejects_duplicates(self):
        from types import SimpleNamespace
        app=App();app.primary.value=r'\\.\DISPLAY37';app.second.value='Friendly portrait monitor'
        adapter=SimpleNamespace(screen_identity=lambda screen:SimpleNamespace(native_id=screen.native_id))
        reader=lambda screen:mode.screen_native_id(screen,adapter=adapter)
        session=mode.SecondarySession(Path('C:/Second'),r'\\.\DISPLAY37',False)
        self.assertIs(session.select_screen(app,environ={},identity_reader=reader),app.second)
        self.assertEqual(session.target_screen,r'\\.\DISPLAY37')
        app.primary.native_id=app.second.native_id
        with self.assertRaises(ValueError):session.select_screen(app,environ={},identity_reader=reader)
        app.primary.native_id=r'\\.\DISPLAY36';app.second.native_id=r'\\.\DISPLAY38'
        with self.assertRaises(ValueError):session.select_screen(app,environ={},identity_reader=reader)

if __name__=='__main__':unittest.main()
