"""Regression coverage for power units, configuration safety and grouping/scaling."""

import copy
import ctypes
import json
import os
import tempfile
import threading
import unittest
from contextlib import ExitStack
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from lupa.lua51 import LuaRuntime

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = PROJECT_ROOT / "qa-private/test-temp"
if not TEST_ROOT.resolve().is_relative_to(PROJECT_ROOT.resolve()):
    raise AssertionError("Product test scratch directory escaped the workspace")
TEST_ROOT.mkdir(parents=True, exist_ok=True)
TEST_DATA = tempfile.TemporaryDirectory(prefix="product-import-", dir=TEST_ROOT)
if not Path(TEST_DATA.name).resolve().is_relative_to(TEST_ROOT.resolve()):
    raise AssertionError("Product import scratch directory escaped the QA root")
# Imports can return cached modules bound to another test's (or the user's)
# profile. This scoped environment is only for fresh imports; every test below
# patches the actual module objects and their write aliases independently.
with patch.dict(os.environ, {"DESKTOP_STATS_DATA": TEST_DATA.name}):
    import build_modular as skins
    import installer
    import sensors as sensor_backend
    import settings_server as controller
    import stats_config as cfg
from battery_sensor import SystemBatteryState, decode, power_state
from localization import (
    LANGUAGES,
    MESSAGES,
    best_language,
    translate,
)
from localization import (
    metadata as localized_metadata,
)
from metrics import required_sources, variable
from presets import catalogue as layout_presets
from sensors import fmt, view


def _qa_path(value):
    path = Path(value)
    if any(part.casefold() == "appdata" for part in path.parts):
        raise AssertionError("Product tests must never access a real AppData target")
    resolved = path.resolve()
    if not resolved.is_relative_to(TEST_ROOT.resolve()) or resolved == TEST_ROOT.resolve():
        raise AssertionError("Product test write target escaped its private QA directory")
    return resolved


def _assert_isolated_paths():
    for owner, fields in (
        (cfg, ("BASE", "CONFIG", "BACKUP")),
        (controller, ("BASE", "ROOT", "SETTINGS", "RAINMETER")),
        (skins, ("BASE", "ROOT")),
        (sensor_backend, ("BASE",)),
        (installer, ("DIRECTORY",)),
    ):
        for field in fields:
            _qa_path(getattr(owner, field))


def _isolate_bindings(stack, root):
    root = _qa_path(root)
    root.mkdir(parents=True, exist_ok=True)
    stack.enter_context(patch.dict(os.environ, {"DESKTOP_STATS_DATA": str(root)}))
    values = (
        (cfg, dict(BASE=root, CONFIG=root / "preferences.json", BACKUP=root / "preferences.backup.json")),
        (controller, dict(BASE=root, ROOT=root / "skin/DesktopStats", SETTINGS=root / "Rainmeter.ini",
                          RAINMETER=root / "Rainmeter.exe", PREFERENCES_CALLBACK=None, EXIT_CALLBACK=None)),
        (skins, dict(BASE=root, ROOT=root / "skin/DesktopStats")),
        (sensor_backend, dict(BASE=root)),
        (installer, dict(DIRECTORY=root / "Programs/DesktopStats")),
    )
    for owner, fields in values:
        for field, value in fields.items():
            stack.enter_context(patch.object(owner, field, value))
    for owner in (skins, controller):
        stack.enter_context(patch.object(owner, "skin_path", lambda: root / "Rainmeter/Skins/DesktopStats"))
        stack.enter_context(patch.object(owner, "display_scale", return_value=1.0))
    stack.enter_context(patch.object(installer, "shell_folder", lambda kind: root / "Shell" / str(kind)))
    original_save, original_load = cfg.save, cfg.load

    def guarded_save(value):
        _assert_isolated_paths()
        return original_save(value)

    def guarded_load():
        _assert_isolated_paths()
        return original_load()

    for owner in (cfg, controller):
        stack.enter_context(patch.object(owner, "save", guarded_save))
        stack.enter_context(patch.object(owner, "load", guarded_load))
    stack.enter_context(patch.object(sensor_backend, "load", guarded_load))
    _assert_isolated_paths()


class IsolatedProductTestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        directory = tempfile.TemporaryDirectory(prefix="product-case-", dir=TEST_ROOT)
        self.addCleanup(directory.cleanup)
        self.profile = _qa_path(directory.name)
        stack = ExitStack()
        self.addCleanup(stack.close)
        _isolate_bindings(stack, self.profile)


class IsolationTests(IsolatedProductTestCase):
    def test_all_write_aliases_are_private_even_for_cached_modules(self):
        _assert_isolated_paths()
        self.assertEqual(cfg.BASE, controller.BASE)
        self.assertEqual(cfg.BASE, sensor_backend.BASE)
        self.assertEqual(controller.ROOT, skins.ROOT)
        self.assertEqual(controller.skin_path(), skins.skin_path())

    def test_real_appdata_target_is_rejected_before_save(self):
        forbidden = Path("C:/Users/fixture/AppData/Local/DesktopStats/preferences.json")
        with patch.object(cfg, "CONFIG", forbidden), self.assertRaises(AssertionError):
            cfg.save(copy.deepcopy(cfg.DEFAULT))

    def test_cached_foreign_bindings_are_overridden_and_restored_without_access(self):
        forbidden = Path("C:/Users/fixture/AppData/Local/DesktopStats")
        with (patch.object(cfg, "BASE", forbidden),
              patch.object(cfg, "CONFIG", forbidden / "preferences.json"),
              patch.object(cfg, "BACKUP", forbidden / "preferences.backup.json"),
              patch.object(controller, "BASE", forbidden)):
            with ExitStack() as stack:
                _isolate_bindings(stack, self.profile / "cached-module-probe")
                cfg.save(copy.deepcopy(cfg.DEFAULT))
                self.assertTrue(cfg.CONFIG.is_file())
                self.assertEqual(cfg.load(), cfg.DEFAULT)
            self.assertEqual(cfg.BASE, forbidden)
            self.assertEqual(controller.BASE, forbidden)
        _assert_isolated_paths()


class BatteryTests(IsolatedProductTestCase):
    def test_ac_zero_rate_does_not_claim_current_is_flowing(self):
        data = {
            "battery_present": True,
            "power_online": True,
            "discharging": True,
            "battery_watts": 0,
        }
        self.assertEqual(power_state(data), 0)
        data["battery_watts"] = 15.5
        self.assertEqual(power_state(data), 2)

    def test_charge_milliwatts_to_watts(self):
        state = SystemBatteryState()
        state.present = 1
        state.charging = 1
        state.rate = 22500
        self.assertEqual(decode(state)["battery_watts"], 22.5)
        self.assertTrue(decode(state)["charging"])

    def test_discharge_signed_long(self):
        state = SystemBatteryState()
        state.present = 1
        state.discharging = 1
        state.rate = ctypes.c_uint32(-17340).value
        self.assertEqual(decode(state)["battery_watts"], 17.34)
        self.assertTrue(decode(state)["discharging"])

    def test_unknown_rate_is_not_zero(self):
        state = SystemBatteryState()
        state.present = 1
        state.rate = 0x80000000
        self.assertIsNone(decode(state)["battery_watts"])

    def test_missing_battery_is_not_empty_battery(self):
        self.assertFalse(decode(SystemBatteryState())["battery_present"])
        self.assertIsNone(decode(SystemBatteryState())["battery_watts"])

    def test_idle_zero_is_valid(self):
        state = SystemBatteryState()
        state.present = 1
        state.online = 1
        state.rate = 0
        self.assertEqual(decode(state)["battery_watts"], 0)


class PreferencesTests(IsolatedProductTestCase):
    def setUp(self):
        super().setUp()
        _assert_isolated_paths()
        cfg.CONFIG.unlink(missing_ok=True)
        cfg.BACKUP.unlink(missing_ok=True)

    def test_invalid_types_and_out_of_range_are_rejected(self):
        for payload in [
            None,
            [],
            {"size": True},
            {"size": 12},
            {"size": 500},
            {"theme": "fake"},
            {"widgets": {"cpu": {"enabled": "yes"}}},
            {"widgets": {"gpu": {"primary": "run-command"}}},
        ]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                cfg.validate(payload)

    def test_incomplete_import_receives_safe_defaults(self):
        out = cfg.validate({"widgets": {"cpu": {"primary": "usage"}}})
        self.assertEqual(out["widgets"]["cpu"]["primary"], "usage")
        self.assertEqual(len(out["widgets"]), 6)
        self.assertTrue(out["widgets"]["battery"]["enabled"])

    def test_round_trip_and_malformed_file_fallback(self):
        config = copy.deepcopy(cfg.DEFAULT)
        config["mode"] = "mixed"
        config["widgets"]["cpu"]["size"] = 76
        cfg.save(config)
        self.assertEqual(cfg.load(), config)
        newer = copy.deepcopy(config)
        newer["theme"] = "dark"
        cfg.save(newer)
        cfg.CONFIG.write_text("{bad", encoding="utf-8")
        self.assertEqual(cfg.load(), config)
        cfg.BACKUP.write_text("{bad", encoding="utf-8")
        self.assertEqual(cfg.load(), cfg.DEFAULT)

    def test_free_content_validation_and_order(self):
        content = ["gpu_power", "cpu_temp", "battery_percent", "ram_used_gb"]
        out = cfg.validate(
            {"widgets": {"cpu": {"content": content, "title": "我的桌面", "skin": "glass"}}}
        )
        self.assertEqual(out["widgets"]["cpu"]["content"], content)
        self.assertEqual(out["widgets"]["cpu"]["title"], "我的桌面")
        for bad in [[], ["cpu_temp"] * 2, ["unknown"], list(cfg.METRICS)[:5], [{}]]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                cfg.validate({"widgets": {"cpu": {"content": bad}}})

    def test_custom_title_cannot_create_native_ini_sections_or_variables(self):
        for title in ["bad\n[Injected]", "#CpuTemp#", "a=b", "a\x00b", "标题太长" * 4]:
            with self.subTest(title=title), self.assertRaises(ValueError):
                cfg.validate({"widgets": {"cpu": {"title": title}}})

    def test_legacy_translucency_migrates_and_skin_inherits(self):
        out = cfg.validate({"theme": "glass"})
        self.assertEqual((out["theme"], out["skin"]), ("light", "glass"))
        self.assertIsNone(out["widgets"]["cpu"]["skin"])

    def test_gpu_sensor_follows_custom_content_in_another_widget(self):
        config = copy.deepcopy(cfg.DEFAULT)
        config["widgets"]["gpu"]["enabled"] = False
        self.assertIn("gpu", required_sources(config))  # New power card still displays GPU watts.
        config["widgets"]["power"]["enabled"] = False
        self.assertNotIn("gpu", required_sources(config))
        config["widgets"]["battery"]["content"] = ["battery_percent", "gpu_power"]
        self.assertIn("gpu", required_sources(config))


class LanguageTests(IsolatedProductTestCase):
    def test_eight_languages_have_complete_common_message_catalogues(self):
        self.assertEqual(len(LANGUAGES), 8)
        for code in LANGUAGES:
            if code != "zh-CN":
                self.assertEqual(set(MESSAGES[code]), set(MESSAGES["en"]))
                self.assertTrue(all(MESSAGES[code].values()))
        self.assertEqual(translate("内存", "en"), "Memory")
        self.assertEqual(translate("内存", "zh-TW"), "記憶體")

    def test_windows_locale_matching_and_fallback(self):
        for name, expected in [
            ("en-US", "en"),
            ("zh_HK", "zh-TW"),
            ("zh-Hans-CN", "zh-CN"),
            ("ja-JP", "ja"),
            ("fr-CA", "fr"),
            ("it-IT", "en"),
        ]:
            self.assertEqual(best_language(name), expected)

    def test_every_localized_preset_is_valid_and_source_catalogues_stay_unchanged(self):
        for language in LANGUAGES:
            pack = localized_metadata(
                language, cfg.MODULES, cfg.METRICS, cfg.SKINS, layout_presets()
            )
            for preset in pack["presets"].values():
                self.assertEqual(cfg.validate(preset["config"]), preset["config"])
        self.assertEqual(cfg.MODULES["memory"]["label"], "内存")

    def test_language_and_user_title_round_trip(self):
        config = copy.deepcopy(cfg.DEFAULT)
        config["language"] = "de"
        config["widgets"]["cpu"]["title"] = "我的内存"
        cfg.save(config)
        self.assertEqual(cfg.load(), config)


class LocalPanelTests(IsolatedProductTestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), controller.Handler)
        cls.port = cls.server.server_port
        cls.port_patch = patch.object(controller, "PORT", cls.port)
        cls.port_patch.start()
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.port_patch.stop()

    def request(self, path, payload=None, authorized=True, origin=None):
        _assert_isolated_paths()
        headers = {}
        if authorized:
            headers["X-Stats-Token"] = controller.TOKEN
        if origin:
            headers["Origin"] = origin
        data = json.dumps(payload).encode() if payload is not None else None
        if data:
            headers["Content-Type"] = "application/json"
        request = Request(f"http://127.0.0.1:{self.port}" + path, data=data, headers=headers)
        try:
            response = urlopen(request, timeout=3)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def test_panel_exposes_catalogue_and_import_round_trip(self):
        status, result = self.request("/api/config")
        self.assertEqual(status, 200)
        self.assertEqual(
            set(result["skins"]), {"card", "glass", "minimal", "frost", "tint", "graphite"}
        )
        self.assertIn("gpu_power", result["metrics"])
        status, result = self.request(
            "/api/validate",
            {
                "config": {
                    "widgets": {
                        "cpu": {
                            "title": "工作台",
                            "content": ["cpu_temp", "gpu_power"],
                            "skin": "minimal",
                        }
                    }
                }
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(result["config"]["widgets"]["cpu"]["content"], ["cpu_temp", "gpu_power"])

    def test_invalid_import_and_untrusted_writes_do_not_change_desktop(self):
        with patch.object(controller, "apply") as apply:
            self.assertEqual(self.request("/api/config", {"config": {}}, authorized=False)[0], 403)
            self.assertEqual(
                self.request("/api/config", {"config": {}}, origin="https://example.com")[0], 403
            )
            self.assertEqual(
                self.request("/api/validate", {"config": {"widgets": {"cpu": {"content": []}}}})[0],
                400,
            )
            self.assertEqual(self.request("/api/config", [])[0], 400)
            apply.assert_not_called()

    def test_apply_persists_only_after_controller_success(self):
        with patch.object(controller, "apply", return_value=[]):
            status, result = self.request(
                "/api/config", {"config": {"skin": "minimal", "mode": "combined"}}
            )
        self.assertEqual(status, 200)
        self.assertEqual(cfg.load()["skin"], "minimal")
        with patch.object(controller, "apply", side_effect=RuntimeError("test")):
            status, _ = self.request("/api/config", {"config": {"skin": "glass"}})
        self.assertEqual(status, 500)
        self.assertEqual(cfg.load()["skin"], "minimal")


class NativeWidgetTests(IsolatedProductTestCase):
    def test_native_language_changes_status_but_keeps_user_title_and_file_path(self):
        self.config["language"] = "en"
        self.config["widgets"]["cpu"]["title"] = "我的内存"
        with patch.object(skins, "BASE", self.root / "内存" / "设置"):
            skins.build(self.config)
        text = (self.root / "cpu/Widget.ini").read_text(encoding="utf-16")
        self.assertIn("Text=我的内存", text)
        self.assertIn("ContextTitle=Widget settings", text)
        self.assertIn("Plugged in", text)
        self.assertIn(str(self.root / "内存" / "设置" / "state.txt"), text)

    def lua_reader(self):
        skins.build(self.config)
        lua = LuaRuntime()
        lua.execute("""
            values={}
            SKIN={}
            function SKIN:GetVariable(key) return 'test' end
            function SKIN:Bang(command,key,value) values[key]=value end
            function os.time() return 100000 end
            function SKIN:GetMeasure(name)
                return {GetStringValue=function() return TEST_DATA or '' end}
            end
        """)
        lua.execute((self.root / "@Resources/ReadSensors.lua").read_text(encoding="ascii"))
        return lua

    def test_lua_reads_fresh_ascii_values(self):
        lua = self.lua_reader()
        lua.globals().TEST_DATA = (
            "SampleEpoch=100000\nCpuTemp=83\nMetricGpuPower=8.4\nPowerState=1\n"
        )
        self.assertEqual(lua.globals().Update(), 1)
        self.assertEqual(lua.globals()["values"]["CpuTemp"], "83")
        self.assertEqual(lua.globals()["values"]["MetricGpuPower"], "8.4")

    def test_empty_reader_clears_previously_displayed_values(self):
        lua = self.lua_reader()
        lua.globals().TEST_DATA = "SampleEpoch=100000\nCpuTemp=83\nMetricGpuPower=8.4\n"
        lua.globals().Update()
        lua.globals().TEST_DATA = None
        self.assertEqual(lua.globals().Update(), 0)
        self.assertEqual(lua.globals()["values"]["CpuTemp"], "--")
        self.assertEqual(lua.globals()["values"]["MetricGpuPower"], "--")
        self.assertEqual(lua.globals()["values"]["MetricGpuPowerBar"], "0")
        self.assertEqual(lua.globals()["values"]["PowerState"], "3")

    def test_stale_or_future_data_is_not_shown_as_live(self):
        lua = self.lua_reader()
        for epoch in (1, 100006):
            lua.globals().TEST_DATA = f"SampleEpoch={epoch}\nCpuTemp=83\n"
            self.assertEqual(lua.globals().Update(), 0)
            self.assertEqual(lua.globals()["values"]["CpuTemp"], "--")

    def setUp(self):
        super().setUp()
        self.output = tempfile.TemporaryDirectory(dir=TEST_ROOT)
        self.addCleanup(self.output.cleanup)
        _qa_path(self.output.name)
        self.root = Path(self.output.name) / "DesktopStats"
        self.root_patch = patch.object(skins, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.dpi_patch = patch.object(skins, "display_scale", return_value=1.75)
        self.dpi_patch.start()
        self.addCleanup(self.dpi_patch.stop)
        self.config = copy.deepcopy(cfg.DEFAULT)

    def test_independent_widgets_do_not_duplicate_content(self):
        output = skins.build(self.config)
        self.assertEqual([i["id"] for i in output], ["cpu", "gpu", "memory", "battery", "power"])
        self.assertNotIn("Group", [i["id"] for i in output])

    def test_combined_has_one_window_and_all_selected_metrics(self):
        self.config["mode"] = "combined"
        output = skins.build(self.config)
        self.assertEqual([i["id"] for i in output], ["Group"])
        text = (self.root / "Group/Widget.ini").read_text(encoding="utf-16")
        for name in ("cpuValue", "gpuValue", "memoryValue", "batteryValue"):
            self.assertIn("[" + name + "]", text)
        for index in range(len(self.config["widgets"]["power"]["content"])):
            self.assertIn(f"[powerMetricValue{index}]", text)
        self.assertIn("OnRefreshAction=[!ZPos -2]", text)

    def test_mixed_avoids_duplicate_singles(self):
        self.config["mode"] = "mixed"
        output = skins.build(self.config)
        self.assertEqual([i["id"] for i in output], ["Group", "battery", "power"])

    def test_all_hidden_is_a_valid_layout(self):
        for w in self.config["widgets"].values():
            w["enabled"] = False
        self.assertEqual(skins.build(self.config), [])

    def test_global_hide_preserves_selected_widgets_and_sensor_dependencies(self):
        before = copy.deepcopy(self.config["widgets"])
        self.config["visible"] = False
        self.assertEqual(skins.build(self.config), [])
        self.assertEqual(self.config["widgets"], before)
        self.assertEqual(required_sources(self.config), set())
        self.config["visible"] = True
        self.assertEqual(len(skins.build(self.config)), 5)

    def test_per_widget_size_is_independent_and_uses_native_dpi(self):
        output = skins.build(self.config)
        small = {i["id"]: i["width"] for i in output}
        self.config["widgets"]["cpu"]["size"] = 176
        output = skins.build(self.config)
        large = {i["id"]: i["width"] for i in output}
        self.assertGreater(large["cpu"], small["cpu"] * 1.95)
        self.assertEqual(large["gpu"], small["gpu"])
        text = (self.root / "cpu/Widget.ini").read_text(encoding="utf-16")
        self.assertIn("°C", text)

    def test_four_mixed_metrics_are_rendered_in_order_with_numeric_graph(self):
        content = ["gpu_power", "cpu_temp", "battery_percent", "ram_used_gb"]
        self.config["widgets"]["cpu"].update(content=content, title="我的桌面", skin="glass")
        skins.build(self.config)
        text = (self.root / "cpu/Widget.ini").read_text(encoding="utf-16")
        positions = [text.index("#" + variable(key) + "#") for key in content]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("Text=我的桌面", text)
        self.assertIn("Formula=#MetricGpuPowerBar#", text)
        self.assertNotIn("[cpuValue]", text)

    def test_group_respects_per_widget_surface_override(self):
        self.config["mode"] = "combined"
        self.config["skin"] = "card"
        self.config["widgets"]["cpu"]["skin"] = "glass"
        skins.build(self.config)
        text = (self.root / "Group/Widget.ini").read_text(encoding="utf-16")
        self.assertIn("[cpuSurface]", text)
        self.assertNotIn("[gpuSurface]", text)


class DailyUseTests(IsolatedProductTestCase):
    def test_all_presets_validate_and_light_layout_skips_gpu(self):
        presets = layout_presets()
        self.assertEqual(len(presets), 4)
        for preset in presets.values():
            self.assertEqual(cfg.validate(preset["config"]), preset["config"])
            self.assertFalse(preset["config"]["autostart"])
        self.assertNotIn("gpu", required_sources(presets["light"]["config"]))
        self.assertEqual(len(presets["overview"]["config"]["widgets"]["cpu"]["content"]), 4)

    def test_startup_is_quoted_and_runs_without_opening_settings(self):
        command = installer.startup_command(Path(r"C:\Applications with spaces\DesktopStats.exe"))
        self.assertEqual(command, '"C:\\Applications with spaces\\DesktopStats.exe" --background')
        with (
            patch.object(installer.winreg, "CreateKey"),
            patch.object(installer.winreg, "SetValueEx") as write,
            patch.object(installer.winreg, "DeleteValue") as delete,
        ):
            installer.set_autostart(True, Path(r"C:\Apps\DesktopStats.exe"))
            self.assertEqual(write.call_args.args[-1], r"C:\Apps\DesktopStats.exe --background")
            installer.set_autostart(False)
            delete.assert_called_once()

    def test_tray_hiding_and_locking_keep_custom_contents(self):
        config = copy.deepcopy(cfg.DEFAULT)
        config["widgets"]["cpu"].update(title="工作台", content=["cpu_temp", "gpu_power"])
        cfg.save(config)
        with patch.object(controller, "apply", return_value=[]):
            hidden, _ = controller.quick_change("visible")
            locked, _ = controller.quick_change("locked")
            restored, _ = controller.quick_change("visible")
        self.assertFalse(hidden["visible"])
        self.assertTrue(locked["locked"])
        self.assertTrue(restored["visible"])
        self.assertEqual(restored["widgets"], config["widgets"])


class DataTests(IsolatedProductTestCase):
    def test_rainmeter_cli_uses_one_bang_per_invocation(self):
        # Regression for the real startup failure: a bracketed batch was parsed
        # as an INI path by Rainmeter's executable.
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(controller.subprocess, "run") as run,
        ):
            run.return_value.returncode = 0
            controller.bang(
                [["!RefreshApp"], ["!ActivateConfig", "DesktopStats\\cpu", "Widget.ini"]]
            )
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[0].args[0][1], "!RefreshApp")
        self.assertEqual(
            run.call_args_list[1].args[0][1:],
            ["!ActivateConfig", "DesktopStats\\cpu", "Widget.ini"],
        )

    def test_zero_and_unavailable_are_distinct(self):
        self.assertEqual(fmt(0, " W", 1), "0.0 W")
        self.assertEqual(fmt(None, " W", 1), "--")

    def test_dynamic_data_is_ascii_to_prevent_legacy_lua_mojibake(self):
        data = dict(
            time=1,
            cpu_usage=35,
            cpu_cores=8,
            cpu_threads=16,
            ram_percent=50,
            ram_used_gb=8,
            ram_total_gb=16,
            ram_available_gb=8,
            battery_watts=0,
            battery_present=True,
            power_online=True,
        )
        result = view(data)
        result.encode("ascii")
        self.assertIn("PowerState=0\n", result)
        self.assertIn("PowerNumber=0.0\n", result)
        self.assertIn("CpuTemp=--\n", result)
        self.assertIn("MetricCpuTemp=--\n", result)
        self.assertIn("MetricCpuTempBar=0.00\n", result)
        self.assertIn("MetricBatteryWatts=0.0\n", result)


if __name__ == "__main__":
    unittest.main()
