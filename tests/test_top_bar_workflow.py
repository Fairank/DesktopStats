"""Actual settings files survive process boundaries, without an installed app.

Each child owns a new offscreen Qt application and a private test-only profile.
No runtime, collector, native window, IPC client or hardware is started.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def scenario(phase):
    import copy
    from unittest.mock import patch

    from PySide6.QtCore import QCoreApplication

    import native_controller as controls
    import stats_config as config

    app = QCoreApplication([])
    if phase == "initial":
        value = copy.deepcopy(config.DEFAULT)
        value["top_bar"]["items"] = [
            dict(id="b_cpu", metric="cpu_usage", prefs={}),
            dict(id="b_network", metric="net_download", prefs={}),
        ]
        config.save(value)
        ui = controls.Controller()
        ui.set_screen_inventory([dict(id="Synthetic second screen", label="Second screen",
                                     native_id=r"\\.\DISPLAY2", primary=False,
                                     x=-1920, y=0, width=1920, height=1080)])
        ui.change("refresh", .25)  # Must not accidentally submit another page.
        ui.changeTopBar("monitor_mode", "selected")
        assert ui.setTopBarScreenSelected(r"\\.\DISPLAY2", True)
        ui.changeTopBarAppearance("design", "capsule")
        ui.changeTopBarAppearance("glass_transparency", 63.125)
        ui.setTopBarGroupMetrics("b_cpu", ["cpu_usage", "cpu_temp", "cpu_power"])
        ui.changeTopBarItem("b_cpu", "style", "icon_value")
        ui.changeTopBarItem("b_cpu", "icon_effect", "auto")
        ui.changeTopBarEffect("b_cpu", "effect_intensity", .375)
        ui.changeTopBarEffect("b_cpu", "effect_speed", 1.625)
        ui.changeTopBarItem("b_network", "style", "duplex_inline")
        ui.changeTopBarItem("b_network", "network_target", "synthetic-adapter-b")
        ui.changeTopBarItem("b_network", "network_unit", "Mbps")
        assert ui.applyTopBar()
        assert ui._draft["refresh"] == .25 and ui._saved["refresh"] != .25
    else:
        ui = controls.Controller()
    if phase == "reorder":
        ui.change("refresh", .15)
        assert ui.placeLiveTopBarMetric("b_network", "", "left")
        assert ui.placeLiveTopBarMetric("b_cpu", "b_network", "left")
        assert ui._draft["refresh"] == .15 and ui._saved["refresh"] != .15
    if phase == "pending":
        before = config.CONFIG.read_bytes()
        ui.changeTopBarEffect("b_cpu", "effect_speed", .75)
        assert not ui.placeLiveTopBarMetric("b_network", "b_cpu", "left")
        assert config.CONFIG.read_bytes() == before
        assert ui._draft["top_bar"] != ui._saved["top_bar"]
        assert ui.revertTopBarDraft()
        assert config.CONFIG.read_bytes() == before
    if phase == "failed_save":
        before = config.CONFIG.read_bytes()
        saved = copy.deepcopy(ui._saved)
        ui.changeTopBarAppearance("design", "instrument")
        draft = copy.deepcopy(ui._draft)
        real_replace = Path.replace

        def fail_preferences_replace(source, destination):
            if Path(destination) == config.CONFIG:
                raise OSError("Synthetic private preferences commit failure")
            return real_replace(source, destination)

        with patch.object(Path, "replace", fail_preferences_replace):
            assert not ui.applyTopBar()
        assert config.CONFIG.read_bytes() == before
        assert ui._saved == saved and ui._draft == draft and ui.dirty
    result = dict(saved=ui._saved, draft=ui._draft, dirty=ui.dirty,
                  disk=config.load(), platform=app.platformName()
                  if hasattr(app, "platformName") else "core-only")
    ui.close()
    print(json.dumps(result))


class BarRestartWorkflowTests(unittest.TestCase):
    def setUp(self):
        parent = Path(os.environ.get("DESKTOP_STATS_DATA", ROOT / "qa-private/redesign38/workflow"))
        parent.mkdir(parents=True, exist_ok=True)
        self.profile = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="restart-", dir=parent)))

    def phase(self, name):
        env = dict(os.environ, DESKTOP_STATS_DATA=str(self.profile),
                   QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-m", "tests.test_top_bar_workflow", "--scenario", name],
            cwd=ROOT, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=25, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_applied_styles_effects_groups_units_and_display_survive_two_restarts_and_live_reorder(self):
        initial = self.phase("initial")
        resumed = self.phase("read")
        self.assertEqual(resumed["saved"], initial["saved"])
        self.assertEqual(resumed["draft"], initial["saved"])
        self.assertFalse(resumed["dirty"])
        bar = resumed["saved"]["top_bar"]
        self.assertEqual(bar["screens"], [r"\\.\DISPLAY2"])
        self.assertEqual(bar["monitor_mode"], "selected")
        self.assertEqual(bar["appearance"]["design"], "capsule")
        self.assertEqual(bar["appearance"]["glass_transparency"], 63.125)
        self.assertEqual(bar["items"][0]["prefs"]["metrics"], ["cpu_usage", "cpu_temp", "cpu_power"])
        self.assertEqual(bar["items"][0]["prefs"]["effect_speed"], 1.625)
        self.assertEqual(bar["items"][0]["prefs"]["effect_intensity"], .375)
        moved = self.phase("reorder")
        again = self.phase("read")
        expected = json.loads(json.dumps(initial["saved"]))
        for row in expected["top_bar"]["items"]:
            row["prefs"]["placement"] = "left"
        self.assertEqual(moved["saved"], expected)
        self.assertEqual(again["saved"], expected)
        self.assertEqual(again["draft"], expected)
        self.assertEqual(moved["disk"], expected)

    def test_pending_editor_and_actual_failed_atomic_replace_cannot_change_restarted_configuration(self):
        initial = self.phase("initial")["saved"]
        self.assertEqual(self.phase("pending")["disk"], initial)
        failed = self.phase("failed_save")
        self.assertTrue(failed["dirty"])
        self.assertEqual(failed["saved"], initial)
        self.assertEqual(failed["disk"], initial)
        resumed = self.phase("read")
        self.assertEqual(resumed["saved"], initial)
        self.assertEqual(resumed["draft"], initial)
        self.assertFalse(resumed["dirty"])


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--scenario":
        scenario(sys.argv[2])
    else:
        unittest.main()
