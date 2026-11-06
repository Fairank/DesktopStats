"""Desktop entry and secondary-screen game protection, with no native surfaces."""
import copy
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QRect,Qt
from PySide6.QtWidgets import QApplication
from native_runtime import Runtime
from stats_config import DEFAULT


class AssemblyDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.enterContext(patch('ctypes.WinDLL',side_effect=AssertionError('No Windows access')))
        self.enterContext(patch('subprocess.Popen',side_effect=AssertionError('No processes')))

    def runtime(self,blocked=()):
        first,second=Mock(),Mock();second.availableGeometry.return_value=QRect(2560,-541,1440,2560)
        config=copy.deepcopy(DEFAULT);config['top_bar'].update(monitor_mode='selected',screens=['second'])
        controller=SimpleNamespace(saved=config,_saved=config,set_status=Mock(),openAssemblyView=Mock(),quick=Mock())
        return SimpleNamespace(headless=False,shutting_down=False,controller=controller,_assembly_window=Mock(),
            app=SimpleNamespace(screens=lambda:[first,second],primaryScreen=lambda:first,quit=Mock()),
            top_bar=SimpleNamespace(focus_details=Mock(),_foreground_hidden_screens=set(blocked),
                adapter=SimpleNamespace(screen_identity=lambda s:SimpleNamespace(native_id='second' if s is second else 'first'))),
            tray=Mock(),show_settings=Mock(),create_status_bar=Mock())

    def test_tray_entry_requests_the_existing_lazy_desktop_inspector(self):
        runtime=self.runtime();runtime.tray.contextMenu.return_value=None
        Runtime.update_menu(runtime)
        menu=runtime.tray_menu
        self.addCleanup(menu.deleteLater)
        action=next(a for a in menu.actions() if a.objectName()=='openAssemblyDesktop')
        runtime.controller.openAssemblyView.assert_not_called()
        action.trigger();runtime.controller.openAssemblyView.assert_called_once_with()
        runtime.show_settings.assert_not_called()

    def test_a_game_on_the_selected_screen_prevents_opening_or_raising_the_viewer(self):
        runtime=self.runtime(blocked={'second'})
        with patch('native_runtime.foreground_fullscreen',return_value=True):
            Runtime.open_assembly_view(runtime,{})
        runtime._assembly_window.showNormal.assert_not_called()
        runtime._assembly_window.synchronize.assert_not_called()
        runtime.controller.set_status.assert_called_once()

    def test_game_on_another_screen_shows_the_requested_view_without_activation(self):
        for fullscreen in (True,None):
            runtime=self.runtime()
            with patch('native_runtime.foreground_fullscreen',return_value=fullscreen):
                Runtime.open_assembly_view(runtime,{})
            window=runtime._assembly_window
            window.showNormal.assert_called_once()
            window.setAttribute.assert_called_once_with(Qt.WA_ShowWithoutActivating,True)
            window.activateWindow.assert_not_called();window.raise_.assert_not_called()
            runtime.controller.set_status.assert_not_called()

    def test_desktop_request_activates_only_the_requested_secondary_window(self):
        runtime=self.runtime()
        with patch('native_runtime.foreground_fullscreen',return_value=False):
            Runtime.open_assembly_view(runtime,{})
        runtime._assembly_window.setAttribute.assert_called_once_with(Qt.WA_ShowWithoutActivating,False)
        runtime._assembly_window.activateWindow.assert_called_once()

    def test_existing_stale_check_also_expires_visible_inspector_values_when_sampling_stops(self):
        runtime=SimpleNamespace(controller=SimpleNamespace(expire_readings=Mock()),_assembly_window=Mock())
        Runtime.clear_stale(runtime)
        runtime.controller.expire_readings.assert_called_once()
        runtime._assembly_window.update_readings.assert_called_once()


if __name__=='__main__':unittest.main()
