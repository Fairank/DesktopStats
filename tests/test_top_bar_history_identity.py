"""Historical auto selectors must never splice unrelated device readings."""
import copy
import time
import unittest
from unittest.mock import patch

import native_controller as controls
from stats_config import DEFAULT, validate


class HistoryIdentityTests(unittest.TestCase):
    def setUp(self):
        with patch.object(controls, "load", return_value=copy.deepcopy(DEFAULT)):
            self.ui = controls.Controller()
        self.addCleanup(self.ui.close)
        self.now = time.time()

    def project(self, metric, samples, **prefs):
        self.ui._data = samples[-1]
        self.ui._history.clear()
        self.ui._history.extend(samples)
        value = copy.deepcopy(DEFAULT)
        value["top_bar"]["items"] = [dict(id="b_history", metric=metric, prefs=prefs)]
        self.ui._saved = validate(value)
        return self.ui.topBarDetailRow("b_history")

    def networks(self):
        return [dict(time=self.now - 2, network_active="a", net_download=100, net_upload=30,
                     networks={"a": dict(label="Adapter A", net_download=100, net_upload=30)}),
                dict(time=self.now - 1, network_active="a", net_download=110, net_upload=35,
                     networks={"a": dict(label="Adapter A", net_download=110, net_upload=35),
                               "b": dict(label="Adapter B", net_download=0, net_upload=0)}),
                dict(time=self.now, network_active="b", net_download=2, net_upload=1,
                     networks={"b": dict(label="Adapter B", net_download=2, net_upload=1)})]

    def test_auto_network_both_directions_use_current_adapter_and_keep_preexistence_gap_and_idle_zero(self):
        for prefs in ({}, {"network_target": "auto"}, {"network_target": ""}):
            row = self.project("net_download", self.networks(), style="duplex", **prefs)
            self.assertEqual(row["hardware_name"], "Adapter B")
            self.assertEqual(row["history"], [None, 0, 2])
            self.assertEqual(row["history_max"], 2)
            self.assertEqual(row["history_mean"], 1)
            self.assertEqual(row["paired_rows"][0]["history"], [None, 0, 2])
            self.assertEqual(row["paired_rows"][1]["history"], [None, 0, 1])
            self.assertEqual(len(row["history_times"]), 3)
            self.assertIsNone(row["trend_points"][0])
        row = self.project("net_download", self.networks(), network_unit="Mbps")
        self.assertEqual(row["history"], [None, 0, 16])

    def test_explicit_disconnected_device_never_follows_auto(self):
        row = self.project("net_download", self.networks(), network_target="a")
        self.assertEqual(row["history"], [100, 110, None])
        self.assertFalse(row["available"])

    def test_actual_adapter_named_auto_does_not_reresolve_reserved_selector_in_old_frames(self):
        samples = self.networks()
        samples[0]["networks"]["auto"] = dict(label="Adapter named auto", net_download=0)
        samples[-1]["network_active"] = "auto"
        samples[-1]["networks"] = {"auto": dict(label="Adapter named auto", net_download=2)}
        row = self.project("net_download", samples, network_target="auto")
        self.assertEqual(row["hardware_name"], "Adapter named auto")
        self.assertEqual(row["history"], [0, None, 2])

    def test_missing_current_identity_and_removed_devices_have_gaps_not_old_alias_values(self):
        samples = self.networks()
        samples[-1].pop("network_active")
        row = self.project("net_download", samples)
        self.assertEqual(row["history"], [None, None, None])

    def test_legacy_flat_frames_require_same_recorded_identity_when_current_device_is_known(self):
        samples = self.networks()
        for sample in samples:
            sample.pop("networks")
        row = self.project("net_download", samples)
        self.assertEqual(row["history"], [None, None, 2])
        for sample in samples:
            sample.pop("network_active")
        row = self.project("net_download", samples)
        self.assertEqual(row["history"], [100, 110, 2])  # Legacy unscoped aggregate, no named device.

    def test_system_volume_freezes_current_volume_but_all_disks_remains_aggregate(self):
        samples = [dict(time=self.now-1, volume_system="v1", disk_percent=80,
                        volumes={"v1": dict(label="Volume A", disk_percent=80),
                                 "v2": dict(label="Volume B", disk_percent=0)}),
                   dict(time=self.now, volume_system="v2", disk_percent=20,
                        volumes={"v2": dict(label="Volume B", disk_percent=20)})]
        for prefs in ({}, {"volume_target": "system"}, {"volume_target": ""}):
            row = self.project("disk_percent", samples, **prefs)
            self.assertEqual(row["hardware_name"], "Volume B")
            self.assertEqual(row["history"], [0, 20])
        disks = [dict(time=self.now-1, disk_read=100, disks={"a": {"disk_read": 100}}),
                 dict(time=self.now, disk_read=2, disks={"b": {"disk_read": 2}})]
        self.assertEqual(self.project("disk_read", disks, disk_target="all")["history"], [100, 2])
        self.assertEqual(self.project("disk_read", disks, disk_target="b")["history"], [None, 2])


if __name__ == "__main__":
    unittest.main()
