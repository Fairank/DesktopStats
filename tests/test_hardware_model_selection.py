"""Manual artwork choices preserve actual devices, readings and offline costs."""

import copy
import unittest
from contextlib import ExitStack
from unittest.mock import patch

import hardware_appearance as appearance
import hardware_variants as variants
import memory_appearance as memory
import native_controller as controls
from stats_config import DEFAULT, validate
from top_bar_config import default_top_bar, validate_top_bar


GPU_MODEL = "asus-dual-4060-oc"
MEMORY_MODEL = "corsair-cmk16gx4m2b3200c16"


class HardwareModelProjectionTests(unittest.TestCase):
    def test_choices_follow_selected_cached_chip_and_are_detached(self):
        data = dict(gpu_name="NVIDIA GeForce RTX 4090", gpus={
            "0": dict(gpu_name="NVIDIA GeForce RTX 4090"),
            "1": dict(gpu_name="NVIDIA GeForce RTX 4060"),
        })
        prefs = dict(gpu_target="1", hardware_model=GPU_MODEL)
        before = copy.deepcopy((data, prefs))
        choices = appearance.appearance_choices(data, "gpu_usage", prefs)
        ids = {row["id"] for row in choices}
        self.assertIn(GPU_MODEL, ids)
        self.assertIn("zotac-solo-4060", ids)
        self.assertNotIn("asus-rog-strix-4090-oc", ids)
        self.assertTrue(all("4060" in row["label"] and "Ti" not in row["label"]
                            for row in choices))
        choices[0]["label"] = "Changed by caller"
        self.assertNotEqual(appearance.appearance_choices(data, "gpu_usage", prefs)[0]["label"],
                            "Changed by caller")
        self.assertEqual((data, prefs), before)

    def test_manual_gpu_is_marked_without_mutating_the_cached_readings(self):
        data = dict(gpus={"1": dict(gpu_name="NVIDIA GeForce RTX 4060",
                                     gpu_usage=73.5, gpu_temp=61.0)})
        prefs = dict(gpu_target="1", hardware_model=GPU_MODEL)
        before = copy.deepcopy((data, prefs))
        result = appearance.metric_appearance(data, "gpu_temp", prefs,
                                               scope="gpus", target="1")
        self.assertEqual((result["id"], result["confidence"], result["selection_source"]),
                         (GPU_MODEL, "model", "manual"))
        self.assertEqual((data, prefs), before)
        result["features"].append("Caller annotation")
        again = appearance.metric_appearance(data, "gpu_usage", prefs,
                                              scope="gpus", target="1")
        self.assertNotIn("Caller annotation", again["features"])

    def test_wrong_or_ambiguous_actual_chip_ignores_manual_cooler(self):
        names = ("NVIDIA GeForce RTX 4060 Ti", "NVIDIA GeForce RTX 4060 Ti SUPER",
                 "NVIDIA GeForce RTX 4090", "AMD Radeon RX 7600", "Intel Arc A770",
                 "NVIDIA GeForce RTX 4060 / AMD Radeon RX 7600", "unknown adapter")
        for name in names:
            with self.subTest(name=name):
                data = dict(gpus={"1": dict(gpu_name=name)})
                automatic = appearance.metric_appearance(data, "gpu_usage", {"gpu_target": "1"},
                                                           scope="gpus", target="1")
                manual = appearance.metric_appearance(data, "gpu_usage",
                                                       dict(gpu_target="1", hardware_model=GPU_MODEL),
                                                       scope="gpus", target="1")
                self.assertEqual(manual, automatic)
                self.assertNotIn(GPU_MODEL, {row["id"] for row in
                    appearance.appearance_choices(data, "gpu_usage", {"gpu_target": "1"})})

    def test_mobile_gpu_cannot_offer_or_apply_a_desktop_cooler(self):
        cases = (
            (dict(gpu_name="NVIDIA GeForce RTX 4060 Laptop GPU"), GPU_MODEL),
            (dict(gpu_name="NVIDIA GeForce RTX 4090 Laptop GPU"), "asus-rog-strix-4090-oc"),
            (dict(label="NVIDIA GeForce RTX 4060 Mobile GPU"), GPU_MODEL),
            (dict(gpu_name="NVIDIA GeForce RTX 4060", board_model="RTX 4060 Notebook GPU"), GPU_MODEL),
        )
        for device, model in cases:
            with self.subTest(device=device):
                data = dict(gpus={"1": device})
                prefs = dict(gpu_target="1", hardware_model=model)
                before = copy.deepcopy((data, prefs))
                self.assertEqual(appearance.appearance_choices(data, "gpu_usage", prefs), [])
                automatic = appearance.metric_appearance(data, "gpu_usage", {"gpu_target": "1"},
                                                           scope="gpus", target="1")
                selected = appearance.metric_appearance(data, "gpu_usage", prefs,
                                                          scope="gpus", target="1")
                self.assertEqual(selected, automatic)
                self.assertEqual((selected["style"], selected["fan_count"]), ("gpu_integrated", None))
                self.assertNotIn("selection_source", selected)
                self.assertEqual((data, prefs), before)

    def test_integrated_identity_does_not_turn_an_embedded_chip_token_into_a_desktop_choice(self):
        cases = (
            ("Intel UHD Graphics 770 / NVIDIA GeForce RTX 4060", GPU_MODEL),
            ("Intel Iris Xe Graphics (GeForce RTX 4090)", "asus-rog-strix-4090-oc"),
            ("Integrated Radeon RX 7600", "sapphire-pulse-7600"),
        )
        for name, model in cases:
            with self.subTest(name=name):
                data = dict(gpus={"0": dict(gpu_name=name)})
                prefs = {"hardware_model": model}
                self.assertEqual(appearance.appearance_choices(data, "gpu_usage", prefs), [])
                automatic = appearance.metric_appearance(data, "gpu_usage", {},
                                                           scope="gpus", target="0")
                selected = appearance.metric_appearance(data, "gpu_usage", prefs,
                                                          scope="gpus", target="0")
                self.assertEqual(selected, automatic)
                self.assertEqual((selected["style"], selected["fan_count"]), ("gpu_integrated", None))

    def test_desktop_names_with_ordinary_memory_units_still_offer_and_apply_their_cooler(self):
        for name, model in (("NVIDIA GeForce RTX 4060 8GB GDDR6", GPU_MODEL),
                            ("NVIDIA GeForce RTX 4090 24GB GDDR6X", "asus-rog-strix-4090-oc")):
            with self.subTest(name=name):
                data = dict(gpus={"0": dict(gpu_name=name)})
                self.assertIn(model, {row["id"] for row in
                    appearance.appearance_choices(data, "gpu_usage", {})})
                selected = appearance.metric_appearance(data, "gpu_usage", {"hardware_model": model},
                                                          scope="gpus", target="0")
                self.assertEqual((selected["id"], selected["selection_source"]), (model, "manual"))

    def test_chip_suffixes_do_not_share_choices(self):
        pairs = (("NVIDIA GeForce RTX 4070 Ti", "asus-tuf-4070tis-oc"),
                 ("AMD Radeon RX 7900 XT", "amd-reference-rx7900xtx-24g"),
                 ("Intel Arc A750", "intel-limited-arc-a770-16g"))
        for chip, incompatible in pairs:
            with self.subTest(chip=chip):
                data = dict(gpus={"0": dict(gpu_name=chip)})
                self.assertNotIn(incompatible, {row["id"] for row in
                    appearance.appearance_choices(data, "gpu_usage", {})})
                selected = appearance.metric_appearance(data, "gpu_usage",
                    {"hardware_model": incompatible}, scope="gpus", target="0")
                self.assertNotEqual(selected.get("selection_source"), "manual")

    def test_missing_gpu_one_never_borrows_flat_or_gpu_zero_identity(self):
        flat = dict(gpu_name="NVIDIA GeForce RTX 4060", board_model="DUAL-RTX4060-O8G")
        tables = ({"0": dict(gpu_name="NVIDIA GeForce RTX 4060")}, {},
                  {"1": None}, {"1": {}}, None, [])
        for table in tables:
            with self.subTest(table=table):
                data = dict(flat, gpus=table)
                prefs = dict(gpu_target="1", hardware_model=GPU_MODEL)
                self.assertEqual(appearance.appearance_choices(data, "gpu_usage", prefs), [])
                result = appearance.metric_appearance(data, "gpu_usage", prefs,
                                                       scope="gpus", target="1")
                self.assertEqual(result["confidence"], "generic")
                self.assertIsNone(result["fan_count"])
                self.assertNotEqual(result.get("selection_source"), "manual")
        self.assertEqual(appearance.appearance_choices(flat, "gpu_usage", {"gpu_target": "1"}), [])

    def test_explicit_target_overrides_preference_and_empty_gpu_table_is_authoritative(self):
        data = dict(gpu_name="NVIDIA GeForce RTX 4060", gpus={
            "0": dict(gpu_name="NVIDIA GeForce RTX 4060"),
            "1": dict(gpu_name="AMD Radeon RX 7600"),
        })
        result = appearance.metric_appearance(data, "gpu_usage",
            dict(gpu_target="0", hardware_model=GPU_MODEL), scope="gpus", target="1")
        self.assertEqual(result["vendor"], "amd")
        self.assertNotEqual(result.get("selection_source"), "manual")
        data["gpus"] = {}
        result = appearance.metric_appearance(data, "gpu_usage", {"hardware_model": GPU_MODEL},
                                               scope="gpus", target="0")
        self.assertEqual(result["confidence"], "generic")

    def test_empty_and_unknown_manual_ids_keep_automatic_matching(self):
        data = dict(gpus={"0": dict(gpu_name="DUAL-RTX4060-O8G")})
        automatic = appearance.metric_appearance(data, "gpu_usage", {}, scope="gpus", target="0")
        for chosen in ("", "unreviewed-future-card", MEMORY_MODEL):
            with self.subTest(chosen=chosen):
                value = appearance.metric_appearance(data, "gpu_usage", {"hardware_model": chosen},
                                                       scope="gpus", target="0")
                self.assertEqual(value, automatic)
                self.assertNotIn("selection_source", value)

    def test_manual_memory_is_explicit_and_automatic_remains_actual(self):
        data = dict(memory_modules=[dict(manufacturer="Kingston", part_number="unreviewed-part",
                                         form_factor="dimm")], ram_percent=42.0)
        before = copy.deepcopy(data)
        automatic = appearance.memory_appearance(data)
        manual = appearance.metric_appearance(data, "ram_percent", {"hardware_model": MEMORY_MODEL})
        self.assertEqual((manual["id"], manual["selection_source"]), (MEMORY_MODEL, "manual"))
        self.assertNotEqual(automatic["confidence"], "model")
        for selected in ("", "unreviewed-memory", GPU_MODEL):
            self.assertEqual(appearance.metric_appearance(data, "ram_percent",
                             {"hardware_model": selected}), automatic)
        self.assertEqual(data, before)

    def test_external_and_cpu_never_adopt_the_manual_gpu_or_memory_model(self):
        data = dict(cpu_name="AMD Ryzen 9 9950X", memory_modules=[],
                    gpus={"0": dict(gpu_name="NVIDIA GeForce RTX 4060")})
        prefs = {"hardware_model": GPU_MODEL}
        self.assertEqual(appearance.metric_appearance(data, "gpu_usage", prefs,
                         scope="gpus", target="0", external=True), {})
        self.assertEqual(appearance.metric_appearance(data, "cpu_temp", prefs),
                         appearance.metric_appearance(data, "cpu_temp", {}))

    def test_completed_versions_do_not_silently_absorb_unreviewed_revisions(self):
        gpu_ids = {row[0] for row in appearance.CATALOG if row[1] == "gpu"}
        memory_ids = {row["id"] for row in memory.CATALOG}
        self.assertEqual(set(variants.READY),set(variants.RECORDS))
        for identity, row in variants.RECORDS.items():
            with self.subTest(identity=identity):
                self.assertIn(identity,gpu_ids if row['kind']=='gpu' else memory_ids)
                for alias in row["aliases"]:
                    result = (appearance.appearance_for("gpu", alias) if row["kind"] == "gpu"
                              else memory.appearance_for_memory(model=alias))
                    self.assertEqual((result['id'],result['confidence']),(identity,'model'))
                    unknown=alias+'-UNREVIEWED'
                    result=(appearance.appearance_for('gpu',unknown) if row['kind']=='gpu'
                            else memory.appearance_for_memory(model=unknown))
                    self.assertNotEqual(result['confidence'],'model')
                    self.assertNotIn('board_details',result)


class HardwareModelPreferenceTests(unittest.TestCase):
    def config(self, model):
        config = default_top_bar()
        config["items"] = [dict(id="b_selected", metric="gpu_usage",
                                prefs=dict(gpu_target="1", hardware_model=model))]
        return config

    def test_valid_bounded_ids_round_trip_without_catalog_or_device_discovery(self):
        for model in ("", GPU_MODEL, MEMORY_MODEL, "a", "a" * 96, "future-reviewed-2040"):
            with self.subTest(model=model):
                original = self.config(model)
                before = copy.deepcopy(original)
                value = validate_top_bar(original)
                self.assertEqual(value["items"][0]["prefs"]["hardware_model"], model)
                self.assertEqual(value["items"][0]["prefs"]["gpu_target"], "1")
                self.assertEqual(validate_top_bar(value), value)
                self.assertEqual(original, before)

    def test_invalid_or_unbounded_ids_are_rejected(self):
        for model in (None, True, 7, [], {}, "a" * 97, "ASUS", "with space",
                      "a_b", "../card", "a/b", "显卡", "a\n", "a\x00", "-card"):
            with self.subTest(model=repr(model)), self.assertRaises(ValueError):
                validate_top_bar(self.config(model))


class HardwareModelControllerTests(unittest.TestCase):
    def setUp(self):
        config = copy.deepcopy(DEFAULT)
        config["visible"] = False
        config["top_bar"].update(enabled=False, items=[
            dict(id="b_gpu_one", metric="gpu_usage", prefs=dict(
                gpu_target="1", precision="1", style="icon_value", icon_effect="spin")),
            dict(id="b_gpu_zero", metric="gpu_power", prefs=dict(gpu_target="0")),
            dict(id="b_memory", metric="ram_percent", prefs={}),
            dict(id="b_cpu", metric="cpu_temp", prefs={}),
        ])
        with patch.object(controls, "load", return_value=validate(config)):
            self.ui = controls.Controller()
        self.addCleanup(self.ui._reading_notify_timer.stop)
        self.ui._data = dict(time=100.0, gpus={
            "0": dict(gpu_name="AMD Radeon RX 7600", gpu_usage=11.0, gpu_power=14.0),
            "1": dict(gpu_name="NVIDIA GeForce RTX 4060", gpu_usage=73.5),
        }, ram_percent=42.0, external_sensors={})

    def test_hidden_choices_use_cached_identity_without_starting_query_or_worker(self):
        before = copy.deepcopy((self.ui._data, self.ui._saved, self.ui._draft))
        with ExitStack() as stack:
            sampler = stack.enter_context(patch.object(controls.sensors, "Sampler"))
            worker = stack.enter_context(patch("threading.Thread.start"))
            processes = stack.enter_context(patch.object(controls.process_usage, "ProcessUsageMonitor"))
            native = stack.enter_context(patch("ctypes.WinDLL"))
            for _ in range(3):
                choices = self.ui.hardwareAppearanceChoices("b_gpu_one")
                self.assertEqual(choices[0]["id"], "")
                self.assertIn(GPU_MODEL, {row["id"] for row in choices})
                self.assertNotIn("sapphire-pulse-7600", {row["id"] for row in choices})
                self.assertEqual(self.ui.hardwareAppearanceChoices("b_cpu"), [])
                self.assertEqual(self.ui.hardwareAppearanceChoices("missing-id"), [])
            self.ui._data["gpus"].pop("1")
            self.assertEqual([row["id"] for row in self.ui.hardwareAppearanceChoices("b_gpu_one")], [""])
            for call in (sampler, worker, processes, native):
                call.assert_not_called()
        expected_data = copy.deepcopy(before[0])
        expected_data["gpus"].pop("1")
        self.assertEqual((self.ui._data, self.ui._saved, self.ui._draft),
                         (expected_data, before[1], before[2]))
        self.assertIsNone(self.ui.thread)

    def test_slot_changes_only_the_requested_artwork_preference(self):
        saved, draft, readings = copy.deepcopy((self.ui._saved, self.ui._draft, self.ui._data))
        with patch.object(controls, "save") as save, \
             patch.object(controls.sensors, "Sampler") as sampler:
            self.ui.changeTopBarItem("b_gpu_one", "hardware_model", GPU_MODEL)
            save.assert_not_called()
            sampler.assert_not_called()
        expected = copy.deepcopy(draft)
        expected["top_bar"]["items"][0]["prefs"]["hardware_model"] = GPU_MODEL
        self.assertEqual(self.ui._draft, expected)
        self.assertEqual(self.ui._saved, saved)
        self.assertEqual(self.ui._data, readings)
        prefs = self.ui._draft["top_bar"]["items"][0]["prefs"]
        self.assertEqual((prefs["gpu_target"], prefs["precision"], prefs["icon_effect"]),
                         ("1", "1", "spin"))
        self.assertEqual(appearance.metric_appearance(readings, "gpu_usage", prefs,
                         scope="gpus", target="1")["selection_source"], "manual")

    def test_scoped_save_keeps_device_targets_other_metrics_and_unapplied_desktop(self):
        self.ui.changeWidget("cpu", "title", "DeskDraft")
        self.ui.change("refresh", 0.35)
        saved_before = copy.deepcopy(self.ui._saved)
        self.ui.changeTopBarItem("b_gpu_one", "hardware_model", GPU_MODEL)
        self.ui.changeTopBarItem("b_memory", "hardware_model", MEMORY_MODEL)
        expected = copy.deepcopy(saved_before)
        expected["top_bar"] = copy.deepcopy(self.ui._draft["top_bar"])
        draft_before = copy.deepcopy(self.ui._draft)
        with patch.object(controls, "save") as save, \
             patch.object(controls, "set_autostart") as autostart:
            self.assertTrue(self.ui.applyTopBar())
        save.assert_called_once_with(expected)
        autostart.assert_not_called()
        self.assertEqual(self.ui._saved, expected)
        self.assertEqual(self.ui._draft, draft_before)
        self.assertEqual(self.ui._saved["top_bar"]["items"][0]["prefs"]["gpu_target"], "1")
        self.assertEqual(self.ui._saved["top_bar"]["items"][1], saved_before["top_bar"]["items"][1])
        self.assertEqual(self.ui.scopeDirty, dict(desktop=True, preferences=True, topbar=False))
        self.assertEqual(validate(self.ui._saved), self.ui._saved)

    def test_invalid_slot_edit_and_unknown_item_leave_all_state_unchanged(self):
        before = copy.deepcopy((self.ui._saved, self.ui._draft, self.ui._data))
        with patch.object(controls, "save") as save:
            self.ui.changeTopBarItem("b_gpu_one", "hardware_model", "a" * 97)
            self.ui.changeTopBarItem("missing-id", "hardware_model", GPU_MODEL)
            save.assert_not_called()
        self.assertEqual((self.ui._saved, self.ui._draft, self.ui._data), before)

    def test_switching_gpu_device_clears_its_previous_manual_cooler(self):
        self.ui.changeTopBarItem('b_gpu_one','hardware_model',GPU_MODEL)
        self.ui.changeTopBarItem('b_gpu_one','gpu_target','0')
        prefs=self.ui._draft['top_bar']['items'][0]['prefs']
        self.assertEqual(prefs['gpu_target'],'0')
        self.assertNotIn('hardware_model',prefs)
        self.assertEqual(prefs['icon_effect'],'spin')


if __name__ == "__main__":
    unittest.main()
