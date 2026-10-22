"""Status reads a real QWindow API without capture, listening or visible UI."""
import copy
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtQuick import QQuickWindow
from PySide6.QtWidgets import QApplication

from native_controller import Controller
from native_runtime import LocalServer
from stats_config import DEFAULT


class RuntimeStatusTests(unittest.TestCase):
    def test_actual_window_metadata_is_serializable_with_no_capture_or_commands(self):
        app = QApplication.instance() or QApplication([])
        self.assertEqual(app.platformName(), "offscreen")
        with patch("native_controller.load", return_value=copy.deepcopy(DEFAULT)):
            controller = Controller()
        window = QQuickWindow()
        server = LocalServer(app)  # Not started: no socket or IPC listener.
        context = {'surface_serial': 2, 'window_visible_now': False}
        server.runtime = SimpleNamespace(controller=controller, settings=window, widgets={},
                                          settings_material=SimpleNamespace(status=lambda: context))
        try:
            for state, minimized in ((Qt.WindowNoState, False), (Qt.WindowMinimized, True)):
                window.setWindowState(state)
                client = Mock()
                client.property.return_value = b""
                client.readAll.return_value = b'{"command":"status"}\n'
                with patch.object(window, "grabWindow", side_effect=AssertionError("No capture")):
                    server.read(client)
                reply = json.loads(client.write.call_args.args[0])
                self.assertTrue(reply["ok"])
                self.assertIs(reply["settings_minimized"], minimized)
                self.assertIs(reply["settings_active"], False)
                self.assertIs(reply["settings_visible"], False)
                self.assertEqual(reply["settings_material"], {"material": "solid"})
                self.assertEqual(reply["settings_material_context"], context)
                self.assertEqual(reply["widget_materials"], {})
                self.assertEqual(reply["top_bar"]["state"], "disabled")
        finally:
            server.deleteLater()
            window.deleteLater()


if __name__ == "__main__":
    unittest.main()
