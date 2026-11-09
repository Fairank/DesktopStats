"""Deferred editor lifecycle on offscreen Qt, with all collectors disabled."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication

from native_controller import Controller
from native_runtime import Runtime,LocalServer
from stats_config import DEFAULT


def no_collect(self,**kwargs):
    """Use a real function: replacing a QObject method with MagicMock is unsafe."""


class LazySettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        assert cls.app.platformName()=='offscreen'

    def setUp(self):
        self.guards=[patch.object(Controller,'start',new=no_collect),
                     patch('native_runtime.transparency_enabled',return_value=False),
                     patch('native_controller.load',return_value=copy.deepcopy(DEFAULT)),
                     patch('ctypes.WinDLL',side_effect=AssertionError('No native material API')),
                     patch('subprocess.Popen',side_effect=AssertionError('No process')),
                     patch('threading.Thread.start',side_effect=AssertionError('No collector'))]
        for guard in self.guards:
            guard.start();self.addCleanup(guard.stop)
        self.runtime=Runtime(self.app,background=True,headless=True)

    def tearDown(self):
        self.runtime.shutdown()
        self.runtime.engine.deleteLater();self.runtime.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

    def test_background_start_does_not_construct_settings_or_material(self):
        self.assertIsNone(self.runtime.settings)
        self.assertEqual(self.runtime.engine.rootObjects(),[])
        self.assertIsNone(self.runtime.settings_host)
        self.assertIsNone(self.runtime.settings_material)
        self.assertIsNone(self.runtime.component)
        self.assertFalse(Runtime._settings_pending(self.runtime))
        self.assertEqual(Runtime._settings_window_state(self.runtime),dict(settings_loaded=False,
            settings_visible=False,settings_active=False,settings_minimized=False))

    def test_first_load_uses_current_draft_and_reuses_window_with_pending_edits(self):
        self.runtime.controller._draft['theme']='dark'
        settings=self.runtime.ensure_settings()
        self.assertIsNotNone(settings)
        self.assertFalse(settings.isVisible())
        self.assertEqual(settings.property('draftConfig')['theme'],'dark')
        settings.setProperty('page',3)
        self.assertIs(self.runtime.ensure_settings(),settings)
        self.assertEqual(settings.property('page'),3)
        self.assertEqual(len(self.runtime.engine.rootObjects()),1)

    def test_status_and_clean_exit_queries_do_not_create_the_editor(self):
        server=LocalServer(self.app);server.runtime=self.runtime
        for command in ('status','quit_if_clean'):
            client=Mock();client.property.return_value=b''
            client.readAll.return_value=(json.dumps(dict(command=command))+'\n').encode()
            with patch('native_runtime.QTimer.singleShot'):
                server.read(client)
            result=json.loads(client.write.call_args.args[0]);self.assertTrue(result['ok'])
            if command=='status':
                self.assertFalse(result['settings_loaded'])
                self.assertFalse(result['dirty'])
            self.assertIsNone(self.runtime.settings)
        server.deleteLater()

    def test_appearance_and_shutdown_do_not_load_a_dormant_editor(self):
        self.runtime.controller._draft['theme']='dark'
        self.runtime.settings_draft_changed()
        self.runtime.shutdown()
        self.assertIsNone(self.runtime.ensure_settings())
        self.assertEqual(self.runtime.engine.rootObjects(),[])

    def test_failed_qml_load_can_retry_without_reusing_an_incomplete_window(self):
        with patch.object(self.runtime.engine,'load',new=lambda *_:None):
            with self.assertRaisesRegex(RuntimeError,'Native settings could not load'):
                self.runtime.ensure_settings()
        self.assertIsNone(self.runtime.settings)
        self.assertFalse(self.runtime._settings_loading)
        self.assertIsNotNone(self.runtime.ensure_settings())


if __name__=='__main__':unittest.main()
