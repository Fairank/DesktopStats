"""Real process ranking with explicit snapshots; never enumerate user processes."""

import importlib
import importlib.util
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class ProcessRankingTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("process_usage"), "Process ranking is missing"
        )
        self.module = importlib.import_module("process_usage")
        self.now = 10.0
        self.rows = []
        self.denied = {}
        self.gpu_data = dict(
            adapters=[dict(name="GPU A", luid="00000000_00000001", memory=8 * 2**30)],
            gpu=[],
            vram=[],
            errors={},
            warming=False,
        )
        fixture = self

        class Source:
            def snapshot(self, kinds):
                return dict(
                    rows=[dict(r) for r in fixture.rows],
                    logical_cpus=4,
                    total_memory=8 * 2**30,
                    denied=dict(fixture.denied),
                )

        class Gpu:
            def read(self, kinds):
                return fixture.gpu_data

            def close(self):
                pass

        self.sampler = self.module.ProcessUsageSampler(
            source=Source(),
            gpu=Gpu(),
            clock=lambda: self.now,
            wall_clock=lambda: 1_700_000_000 + self.now,
        )
        self.addCleanup(self.sampler.close)
        self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native API")))
        self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))

    @staticmethod
    def target(kind, name=""):
        return dict(kind=kind, hardware_name=name)

    def sample(self, kind="cpu", name=""):
        return self.sampler.read({"test": self.target(kind, name)})["test"]

    def test_cpu_merges_then_sorts_five_names_and_normalizes_all_processors(self):
        self.rows = [
            dict(pid=i, started=1.0, name=name, cpu_seconds=0.0)
            for i, name in enumerate(
                [
                    "Chrome.exe",
                    "chrome.EXE",
                    "Editor.exe",
                    "A.exe",
                    "B.exe",
                    "C.exe",
                    "D.exe",
                    "E.exe",
                ],
                1,
            )
        ]
        self.assertEqual(self.sample()["state"], "warming_up")
        self.now = 12.0
        for row, seconds in zip(self.rows, [1, 1.4, 1.6, 0.8, 0.4, 0.24, 0.16, 0.08]):
            row["cpu_seconds"] = seconds
        result = self.sample()
        self.assertEqual(
            [r["name"].casefold() for r in result["rows"]],
            ["chrome.exe", "editor.exe", "a.exe", "b.exe", "c.exe"],
        )
        self.assertEqual([r["value"] for r in result["rows"]], [30.0, 20.0, 10.0, 5.0, 3.0])
        self.assertEqual(result["rows"][0]["process_count"], 2)
        self.assertEqual(result["rows"][0]["fraction"], 0.3)
        self.assertEqual(result["kind"], "cpu")

    def test_pid_reuse_counter_reset_zero_and_invalid_values_never_invent_activity(self):
        self.rows = [
            dict(pid=1, started=1.0, name="Reused.exe", cpu_seconds=9.0),
            dict(pid=2, started=1.0, name="Reset.exe", cpu_seconds=9.0),
        ]
        self.sample()
        self.now = 12.0
        self.rows = [
            dict(pid=1, started=2.0, name="New.exe", cpu_seconds=100.0),
            dict(pid=2, started=1.0, name="Reset.exe", cpu_seconds=2.0),
            dict(pid=3, started=1.0, name="Invalid.exe", cpu_seconds=float("nan")),
        ]
        result = self.sample()
        self.assertEqual(result["rows"], [])
        self.assertNotEqual(result["state"], "ready")

    def test_memory_is_current_working_set_sorted_before_limiting(self):
        self.rows = [
            dict(pid=i, started=1.0, name=f"App{i}.exe", memory_bytes=i * 2**20)
            for i in range(1, 8)
        ]
        result = self.sample("memory")
        self.assertEqual(
            [r["name"] for r in result["rows"]],
            ["App7.exe", "App6.exe", "App5.exe", "App4.exe", "App3.exe"],
        )
        self.assertEqual(result["rows"][0]["value"], 7 * 2**20)
        self.assertEqual(result["rows"][0]["fraction"], 7 / 8192)
        self.assertEqual(result["unit"], "bytes")
        self.assertEqual(result["state"], "ready")

    def test_access_denial_marks_partial_instead_of_claiming_complete_top_five(self):
        self.rows = [dict(pid=1, started=1.0, name="Readable.exe", memory_bytes=2**20)]
        self.denied = {"memory": 2}
        result = self.sample("memory")
        self.assertEqual(result["state"], "partial")
        self.assertEqual(result["denied_count"], 2)
        self.assertEqual(len(result["rows"]), 1)

    def test_sleep_or_clock_reset_clears_cpu_rate_baseline(self):
        self.rows = [dict(pid=1, started=1.0, name="A.exe", cpu_seconds=1.0)]
        self.sample()
        for stamp in (50.0, 49.0):
            self.now = stamp
            self.rows[0]["cpu_seconds"] += 1
            result = self.sample()
            self.assertEqual(result["state"], "warming_up")
            self.assertEqual(result["rows"], [])

    def test_gpu_filters_adapter_and_aggregates_each_engine_before_taking_maximum(self):
        self.rows = [
            dict(pid=1, started=1.0, name="Browser.exe"),
            dict(pid=2, started=1.0, name="browser.EXE"),
            dict(pid=3, started=1.0, name="Editor.exe"),
        ]
        self.sample("gpu", "GPU A")
        self.now = 12.0
        self.gpu_data["gpu"] = [
            dict(pid=1, luid="00000000_00000001", engine="0_3D", value=30.0),
            dict(pid=2, luid="00000000_00000001", engine="0_3D", value=20.0),
            dict(pid=2, luid="00000000_00000001", engine="1_Copy", value=80.0),
            dict(pid=3, luid="00000000_00000001", engine="0_3D", value=60.0),
            dict(pid=3, luid="00000000_00000002", engine="0_3D", value=99.0),
        ]
        result = self.sample("gpu", "GPU A")
        self.assertEqual(
            [r["name"].casefold() for r in result["rows"]], ["browser.exe", "editor.exe"]
        )
        self.assertEqual([r["value"] for r in result["rows"]], [80.0, 60.0])
        self.assertEqual(result["rows"][0]["process_count"], 2)

    def test_gpu_never_uses_first_adapter_when_selected_name_is_missing_or_ambiguous(self):
        self.gpu_data["adapters"].append(dict(name="GPU A", luid="00000000_00000002", memory=2**30))
        for name in ("GPU A", "Missing GPU", "0", ""):
            result = self.sample("gpu", name)
            self.assertEqual(result["state"], "unavailable")
            self.assertEqual(result["rows"], [])
            self.assertEqual(result["reason_code"], "adapter_identity")

    def test_same_physical_gpu_aliases_require_the_same_verified_pci_address(self):
        self.gpu_data["adapters"][0]["pci_address"] = [1, 0, 0]
        self.gpu_data["adapters"].append(
            dict(name="GPU A", luid="00000000_00000002", memory=8 * 2**30, pci_address=[1, 0, 0])
        )
        self.rows = [dict(pid=1, started=1.0, name="A.exe")]
        self.sample("gpu", "GPU A")
        self.now = 12.0
        self.gpu_data["gpu"] = [dict(pid=1, luid="00000000_00000002", engine="0_3D", value=72.0)]
        result = self.sample("gpu", "GPU A")
        self.assertEqual(result["state"], "ready")
        self.assertEqual(result["rows"][0]["value"], 72.0)
        self.gpu_data["adapters"][1]["pci_address"] = [2, 0, 0]
        self.assertEqual(self.sample("gpu", "GPU A")["reason_code"], "adapter_identity")

    def test_unique_physical_gpu_is_not_hidden_by_an_explicit_non_pci_name_alias(self):
        self.gpu_data["adapters"][0]["pci_address"] = [1, 0, 0]
        self.gpu_data["adapters"].append(
            dict(name="GPU A", luid="00000000_00000002", memory=8 * 2**30, pci_address=None)
        )
        self.rows = [dict(pid=1, started=1.0, name="A.exe")]
        self.sample("gpu", "GPU A")
        self.now = 12.0
        self.gpu_data["gpu"] = [dict(pid=1, luid="00000000_00000001", engine="0_3D", value=38.0)]
        result = self.sample("gpu", "GPU A")
        self.assertEqual(result["state"], "ready")
        self.assertEqual(result["rows"][0]["value"], 38.0)

    def test_vram_keeps_the_selected_adapter_and_dedicated_bytes(self):
        self.rows = [dict(pid=1, started=1.0, name="A.exe"), dict(pid=2, started=1.0, name="B.exe")]
        self.sample("vram", "GPU A")
        self.now = 12.0
        self.gpu_data["vram"] = [
            dict(pid=1, luid="00000000_00000001", value=2**30),
            dict(pid=2, luid="00000000_00000001", value=2 * 2**30),
            dict(pid=1, luid="00000000_00000002", value=7 * 2**30),
        ]
        result = self.sample("vram", "GPU A")
        self.assertEqual([r["value"] for r in result["rows"]], [2 * 2**30, 2**30])
        self.assertEqual(result["rows"][0]["fraction"], 0.25)

    def test_gpu_failure_preserves_safe_error_code_without_private_exception_text(self):
        self.gpu_data["errors"] = {"gpu": dict(api="PdhCollectQueryData", code="0xc0000bb8")}
        result = self.sample("gpu", "GPU A")
        self.assertEqual(result["state"], "unavailable")
        self.assertEqual(result["error"]["code"], "0xc0000bb8")
        self.assertEqual(result["rows"], [])

    def test_closed_sampler_does_not_reuse_or_return_previous_rows(self):
        self.rows = [dict(pid=1, started=1.0, name="A.exe", memory_bytes=2**20)]
        self.assertTrue(self.sample("memory")["rows"])
        self.sampler.close()
        result = self.sample("memory")
        self.assertEqual(result["state"], "closed")
        self.assertEqual(result["rows"], [])


class MonitorAndSourceTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module("process_usage")
        self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native API")))
        self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))

    def test_no_demand_or_unsupported_demand_never_creates_worker(self):
        monitor = self.module.ProcessUsageMonitor(lambda *_: self.fail("Idle callback"))
        self.addCleanup(monitor.close)
        with patch("threading.Thread.start", side_effect=AssertionError("No idle worker")):
            monitor.set_targets({})
            monitor.set_targets({"network": dict(kind="network", hardware_name="")})
            self.assertIsNone(monitor.thread)

    def test_new_card_request_is_not_blocked_by_native_cleanup_on_the_worker(self):
        sampled, closing, released, requested = (threading.Event() for _ in range(4))

        class Sampler:
            def read(self, targets):
                sampled.set()
                return {}

            def close(self):
                closing.set()
                released.wait(2)

        monitor = self.module.ProcessUsageMonitor(lambda *_: None, factory=Sampler)
        self.addCleanup(monitor.close)
        target = {"cpu": dict(kind="cpu", hardware_name="")}
        monitor.set_targets(target)
        self.assertTrue(sampled.wait(1))
        monitor.set_targets({})
        self.assertTrue(closing.wait(1))

        def request():
            monitor.set_targets(target)
            requested.set()

        setter = threading.Thread(target=request, daemon=True)
        setter.start()
        try:
            self.assertTrue(requested.wait(0.3), "A new GUI request waited for native cleanup")
        finally:
            released.set()
            setter.join(timeout=1)

    def test_last_card_release_closes_sampler_and_drops_late_result(self):
        entered, released, closed = threading.Event(), threading.Event(), threading.Event()
        callbacks = []

        class Sampler:
            def read(self, targets):
                entered.set()
                if not released.wait(2):
                    raise RuntimeError("Fake fixture timed out")
                return {"old": dict(rows=[])}

            def close(self):
                closed.set()

        monitor = self.module.ProcessUsageMonitor(lambda *r: callbacks.append(r), factory=Sampler)
        self.addCleanup(monitor.close)
        monitor.set_targets({"old": dict(kind="cpu", hardware_name="")})
        self.assertTrue(entered.wait(1))
        monitor.set_targets({})
        released.set()
        self.assertTrue(closed.wait(1))
        self.assertEqual(callbacks, [])

    def test_duplicate_requests_do_not_sample_faster_than_the_one_second_interval(self):
        done = threading.Event()
        stamps = []

        class Sampler:
            def read(self, targets):
                stamps.append(time.monotonic())
                return {}

            def close(self):
                pass

        def callback(*_):
            if len(stamps) >= 2:
                done.set()

        monitor = self.module.ProcessUsageMonitor(callback, factory=Sampler)
        self.addCleanup(monitor.close)
        target = {"cpu": dict(kind="cpu", hardware_name="")}
        monitor.set_targets(target)
        for _ in range(100):
            monitor.set_targets(target)
        self.assertTrue(done.wait(3))
        self.assertGreaterEqual(stamps[1] - stamps[0], 0.9)
        self.assertLess(stamps[1] - stamps[0], 1.6)

    def test_first_cpu_baseline_is_followed_by_a_prompt_measurement(self):
        done = threading.Event()
        stamps = []

        class Sampler:
            def read(self, targets):
                stamps.append(time.monotonic())
                return {"cpu": dict(state="warming_up" if len(stamps) == 1 else "ready")}

            def close(self):
                pass

        monitor = self.module.ProcessUsageMonitor(
            lambda *_: done.set() if len(stamps) >= 2 else None, factory=Sampler
        )
        self.addCleanup(monitor.close)
        monitor.set_targets({"cpu": dict(kind="cpu", hardware_name="")})
        self.assertTrue(done.wait(1), "The first CPU reading still waits a full refresh interval")
        self.assertGreaterEqual(stamps[1] - stamps[0], 0.2)

    def test_refresh_period_does_not_add_collection_time(self):
        done = threading.Event()
        stamps = []

        class Sampler:
            def read(self, targets):
                stamps.append(time.monotonic())
                time.sleep(0.2)  # A slow native provider must not extend every period.
                return {}

            def close(self):
                pass

        monitor = self.module.ProcessUsageMonitor(
            lambda *_: done.set() if len(stamps) >= 2 else None, factory=Sampler
        )
        self.addCleanup(monitor.close)
        with patch.object(self.module, "INTERVAL", 0.4):
            monitor.set_targets({"cpu": dict(kind="cpu", hardware_name="")})
            self.assertTrue(done.wait(1.3))
            self.assertGreaterEqual(stamps[1] - stamps[0], 0.36)
            self.assertLess(stamps[1] - stamps[0], 0.53)

    def test_native_snapshot_failure_keeps_the_real_api_and_status(self):
        from process_snapshot import SnapshotError

        report = self.module.safe_error(SnapshotError(0xc0000022), "psutil process snapshot")
        self.assertEqual(report["api"], "NtQuerySystemInformation")
        self.assertEqual(report["code"], "0xc0000022")

    def test_rapid_target_replacements_keep_a_query_cooldown(self):
        done, stamps = threading.Event(), []

        class Sampler:
            def read(self, targets):
                stamps.append(time.monotonic())
                return {}

            def close(self):
                pass

        def callback(*_):
            if len(stamps) == 3:
                done.set()
            else:
                monitor.set_targets({str(len(stamps)): dict(kind="cpu", hardware_name="")})

        monitor = self.module.ProcessUsageMonitor(callback, factory=Sampler)
        self.addCleanup(monitor.close)
        monitor.set_targets({"initial": dict(kind="cpu", hardware_name="")})
        self.assertTrue(done.wait(1))
        self.assertTrue(all(b - a >= 0.045 for a, b in zip(stamps, stamps[1:])))

    def test_initial_gpu_collection_keeps_a_full_rate_window_after_initialization(self):
        done, stamps = threading.Event(), []

        class Sampler:
            def read(self, targets):
                if not stamps:
                    time.sleep(0.2)  # Lazy PDH/DXGI initialization before its first collection.
                stamps.append(time.monotonic())
                return {"gpu": dict(state="warming_up" if len(stamps) == 1 else "ready")}

            def close(self):
                pass

        monitor = self.module.ProcessUsageMonitor(
            lambda *_: done.set() if len(stamps) >= 2 else None, factory=Sampler
        )
        self.addCleanup(monitor.close)
        monitor.set_targets({"gpu": dict(kind="gpu", hardware_name="Test GPU")})
        self.assertTrue(done.wait(2))
        self.assertGreaterEqual(stamps[1] - stamps[0], 1.0)

    def test_factory_failure_is_a_report_and_does_not_silently_kill_detail_updates(self):
        done = threading.Event()
        results = []

        def factory():
            raise RuntimeError("PRIVATE CONTENT MUST NOT BE EXPORTED")

        def callback(generation, value):
            results.append(value)
            done.set()

        monitor = self.module.ProcessUsageMonitor(callback, factory=factory)
        self.addCleanup(monitor.close)
        monitor.set_targets({"cpu": dict(kind="cpu", hardware_name="")})
        self.assertTrue(done.wait(0.5))
        self.assertEqual(results[0]["cpu"]["state"], "unavailable")
        self.assertNotIn("PRIVATE CONTENT", str(results))

    def test_snapshot_uses_fresh_process_identity_and_only_requested_fields(self):
        created = []
        rows = {
            1: dict(name="A.exe", create_time=1.0, cpu_times=SimpleNamespace(user=2.0, system=1.0)),
            2: dict(name="B.exe", create_time=2.0, cpu_times=SimpleNamespace(user=3.0, system=2.0)),
        }

        class Process:
            def __init__(self, pid):
                created.append(pid)
                self.pid = pid

            def as_dict(self, attrs, ad_value):
                if set(attrs) != {"name", "create_time", "cpu_times"}:
                    raise AssertionError("Unneeded/private fields requested")
                return dict(rows[self.pid])

        with (
            patch.object(self.module.sys, "platform", "linux"),
            patch.object(self.module.psutil, "pids", return_value=[0, 1, 2]),
            patch.object(self.module.psutil, "Process", Process),
            patch.object(self.module.psutil, "cpu_count", return_value=4),
            patch.object(
                self.module.psutil, "virtual_memory", side_effect=AssertionError("No memory query")
            ),
        ):
            source = self.module.ProcessSource()
            first = source.snapshot({"cpu"})
            rows[1]["create_time"] = 5.0
            second = source.snapshot({"cpu"})
        self.assertEqual(created, [1, 2, 1, 2])
        self.assertEqual(first["rows"][0]["cpu_seconds"], 3.0)
        self.assertEqual(second["rows"][0]["started"], 5.0)


if __name__ == "__main__":
    unittest.main()
