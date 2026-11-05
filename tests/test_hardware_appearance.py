"""Identity matching must never invent a physical cooler or cross devices."""

import copy
import unittest

import hardware_appearance as appearance


class HardwareAppearanceTests(unittest.TestCase):
    def test_reviewed_models_have_official_sources_and_unique_aliases(self):
        aliases = set()
        for row in appearance.CATALOG:
            self.assertTrue(row[8].startswith("https://"))
            for alias in row[9]:
                normalized = appearance._text(alias)
                self.assertNotIn(normalized, aliases)
                aliases.add(normalized)
                match = appearance.appearance_for(row[1], alias)
                self.assertEqual((match["id"], match["confidence"]), (row[0], "model"))
                self.assertEqual(match["fan_count"], row[6])

    def test_each_existing_series_has_a_reviewed_exact_representative(self):
        covered = set()
        for row in appearance.CATALOG:
            match = appearance.appearance_for(row[1], row[-1][0])
            if row[1] == "gpu":
                self.assertEqual(match["confidence"], "model")
                self.assertIn(match["fan_count"], (1, 2, 3))
                covered.add(match["series_id"])
        self.assertEqual(covered, {row["id"] for row in appearance.SERIES_CATALOG})

    def test_actual_intel_registry_name_matches_package(self):
        result = appearance.appearance_for("cpu", "13th Gen Intel(R) Core(TM) i7-13700KF")
        self.assertEqual((result["vendor"], result["style"], result["confidence"]),
                         ("intel", "lga_rect", "model"))
        self.assertIsNone(result["fan_count"])

    def test_amd_top_cover_requires_reviewed_desktop_model(self):
        exact = appearance.appearance_for("cpu", "AMD Ryzen 7 7800X3D 8-Core Processor")
        self.assertEqual(exact["style"], "am5")
        for name in ("AMD Ryzen 9 9950X3D", "AMD Ryzen 9 9950X3D2", "AMD Ryzen 9 7945HX",
                     "AMD Ryzen 7 7800X3D laptop", "AMD Ryzen 7 5800X3D"):
            with self.subTest(name=name):
                self.assertEqual(appearance.appearance_for("cpu", name)["style"], "chip")

    def test_chip_name_does_not_determine_board_cooler(self):
        for name in ("NVIDIA GeForce RTX 4060", "AMD Radeon RX 7600", "Intel Arc A770"):
            result = appearance.appearance_for("gpu", name)
            self.assertEqual(result["confidence"], "brand")
            self.assertEqual(result["style"], "gpu_neutral")
            self.assertIsNone(result["fan_count"])
            self.assertEqual(result["board_vendor"], "unknown")

    def test_board_brand_alone_never_invents_fans(self):
        for brand in appearance.BRANDS.keys() - {"intel", "amd", "nvidia", "unknown"}:
            result = appearance.appearance_for("gpu", "NVIDIA GeForce RTX 4060",
                                               board_vendor=brand)
            self.assertEqual(result["board_vendor"], brand)
            self.assertEqual(result["confidence"], "brand")
            self.assertEqual(result["style"], "gpu_neutral")
            self.assertIsNone(result["fan_count"])

    def test_series_match_has_its_own_identity_but_cannot_invent_a_fan_count(self):
        for row in appearance.SERIES_CATALOG:
            name = f"{row['board_vendor']} {row['aliases'][0]} unidentified GPU"
            with self.subTest(series=row["id"]):
                result = appearance.appearance_for("gpu", name)
                self.assertEqual(result["confidence"], "series")
                self.assertEqual(result["series_id"], row["id"])
                self.assertEqual(result["series_label"], row["label"])
                self.assertEqual(result["source_url"], row["source_url"])
                self.assertIsNone(result["fan_count"])
                self.assertLessEqual(len(result["features"]), 2)
                self.assertTrue(result["features"])

    def test_series_requires_selected_board_brand_and_is_not_another_vendor(self):
        for name in ("NVIDIA TUF RTX 4060", "MSI TUF RTX 4060", "NVIDIA NITRO RX 7600",
                     "ASUS TUF Dual unconfirmed edition", "ASUS TUF Laptop GPU"):
            with self.subTest(name=name):
                result = appearance.appearance_for("gpu", name)
                self.assertNotEqual(result["confidence"], "series")
                self.assertIsNone(result["fan_count"])

    def test_specific_series_can_disambiguate_generic_marketing_words(self):
        for name, expected in (("MSI SUPRIM GAMING GeForce RTX 4090", "msi_suprim"),
                               ("MSI VENTUS GAMING GeForce RTX 4060", "msi_ventus"),
                               ("GIGABYTE AORUS WINDFORCE GeForce RTX 4090", "gigabyte_aorus")):
            result = appearance.appearance_for("gpu", name)
            self.assertEqual(result["series_id"], expected)
            self.assertIsNone(result["fan_count"])
        ambiguous = appearance.appearance_for("gpu", "MSI SUPRIM VENTUS GAMING RTX 4090")
        self.assertEqual(ambiguous["series_id"], "")

    def test_exact_model_retains_series_and_detached_features(self):
        first = appearance.appearance_for("gpu", "TUF-RTX4070TIS-O16G-GAMING")
        self.assertEqual((first["series_id"], first["confidence"], first["fan_count"]),
                         ("asus_tuf", "model", 3))
        self.assertTrue(first["features"])
        first["features"].append("synthetic mutation")
        again = appearance.appearance_for("gpu", "TUF-RTX4070TIS-O16G-GAMING")
        self.assertNotIn("synthetic mutation", again["features"])

    def test_model_match_is_exact_for_gpu_revision_color_capacity_variants(self):
        for name in ("DUAL-RTX4060-O8G-V2", "DUAL-RTX4060-O8G-WHITE",
                     "ASUS Dual GeForce RTX 4060 Ti OC Edition 8GB",
                     "TUF-RTX4070TIS-O16G-GAMING BTF", "ZT-D40600G-10L revised",
                     "SAPPHIRE PULSE RX 7600 XT", "SAPPHIRE PULSE RX 7600 laptop"):
            with self.subTest(name=name):
                result = appearance.appearance_for("gpu", name)
                self.assertNotEqual(result["confidence"], "model")
                self.assertIsNone(result["fan_count"])

    def test_explicit_board_model_resolves_but_conflicts_fall_back(self):
        result = appearance.appearance_for("gpu", "NVIDIA GeForce RTX 4060",
                                           model="DUAL-RTX4060-O8G", board_vendor="ASUSTeK")
        self.assertEqual((result["board_vendor"], result["fan_count"]), ("asus", 2))
        for name, board in (("AMD Radeon RX 7600", "ASUS"),
                            ("NVIDIA GeForce RTX 4060", "MSI")):
            result = appearance.appearance_for("gpu", name, model="DUAL-RTX4060-O8G",
                                               board_vendor=board)
            self.assertNotEqual(result["confidence"], "model")
            self.assertIsNone(result["fan_count"])

    def test_strong_chip_and_board_conflicts_cannot_be_overridden_by_model_metadata(self):
        cases = (
            ("ZOTAC GAMING GeForce RTX 4060 8GB SOLO", "DUAL-RTX4060-O8G", "ASUS"),
            ("NVIDIA GeForce RTX 4090", "DUAL-RTX4060-O8G", "ASUS"),
            ("NVIDIA GeForce RTX 4060 Ti", "DUAL-RTX4060-O8G", "ASUS"),
            ("NVIDIA GeForce RTX 4070 Ti SUPER", "TUF-RTX4070TIS-O16G-GAMING", "ASUS MSI"),
            ("ASUS MSI GeForce RTX 4060", "DUAL-RTX4060-O8G", ""),
            ("AMD NVIDIA GPU", "DUAL-RTX4060-O8G", "ASUS"),
        )
        for name, model, board in cases:
            with self.subTest(name=name, board=board):
                result = appearance.appearance_for("gpu", name, model=model, board_vendor=board)
                self.assertNotIn(result["confidence"], ("model", "series"))
                self.assertIsNone(result["fan_count"])
                self.assertEqual(result["series_id"], "")

    def test_compact_and_spaced_chip_variant_names_match_the_same_exact_model(self):
        for name in ("NVIDIA GeForce RTX 4070 Ti SUPER", "NVIDIA GeForce RTX4070TiSUPER"):
            result = appearance.appearance_for("gpu", name, model="TUF-RTX4070TIS-O16G-GAMING")
            self.assertEqual((result["confidence"], result["fan_count"]), ("model", 3))

    def test_mobile_uses_chip_silhouette_without_card_fans(self):
        for name in ("NVIDIA GeForce RTX 4060 Laptop GPU", "AMD Radeon RX 7600M XT",
                     "Intel Iris Xe Graphics", "Intel UHD Graphics 770"):
            result = appearance.appearance_for("gpu", name)
            self.assertIsNone(result["fan_count"])
            self.assertEqual(result["style"], "gpu_integrated")

    def test_untrusted_and_unknown_names_are_bounded_and_detached(self):
        for name in (None, False, [], {}, 123, "", "unidentified adapter"):
            result = appearance.appearance_for("gpu", name)
            self.assertEqual(result["confidence"], "generic")
            self.assertIsNone(result["fan_count"])
        result = appearance.appearance_for("gpu", "DUAL-RTX4060-O8G")
        result["fan_count"] = 99
        self.assertEqual(appearance.appearance_for("gpu", "DUAL-RTX4060-O8G")["fan_count"], 2)
        self.assertEqual(appearance.appearance_for("disk", "ASUS"), {})
        appearance._resolve.cache_clear()
        for number in range(400):
            appearance.appearance_for("gpu", f"adapter-{number}" + "x" * 400)
        self.assertLessEqual(appearance._resolve.cache_info().currsize, 128)

    def test_selected_gpu_never_borrows_the_default_or_motherboard(self):
        data = dict(gpu_name="DUAL-RTX4060-O8G", motherboard_vendor="ASUS",
                    gpus={"0": dict(gpu_name="DUAL-RTX4060-O8G"),
                          "1": dict(gpu_name="AMD Radeon RX 7600")})
        before = copy.deepcopy(data)
        second = appearance.metric_appearance(data, "gpu_usage", {}, scope="gpus", target="1")
        self.assertEqual(second["vendor"], "amd")
        self.assertEqual(second["board_vendor"], "unknown")
        self.assertIsNone(second["fan_count"])
        missing = appearance.metric_appearance(data, "gpu_usage", {}, scope="gpus", target="2")
        self.assertEqual(missing["confidence"], "generic")
        self.assertEqual(data, before)

    def test_flat_legacy_data_cannot_fill_another_device(self):
        data = dict(gpu_name="DUAL-RTX4060-O8G")
        first = appearance.metric_appearance(data, "gpu_usage", {}, scope="gpus", target="0")
        other = appearance.metric_appearance(data, "gpu_usage", {}, scope="gpus", target="1")
        self.assertEqual(first["fan_count"], 2)
        self.assertIsNone(other["fan_count"])
        data["gpus"] = {}
        missing = appearance.metric_appearance(data, "gpu_usage", {}, scope="gpus", target="0")
        self.assertIsNone(missing["fan_count"])

    def test_external_sensor_and_unrelated_resource_do_not_inherit_cpu_identity(self):
        data = dict(cpu_name="AMD Ryzen 9 9950X", gpu_name="DUAL-RTX4060-O8G")
        self.assertEqual(appearance.metric_appearance(data, "external_1", {}, external=True), {})
        self.assertEqual(appearance.metric_appearance(data, "ram_percent", {}), {})
        self.assertEqual(appearance.metric_appearance(data, "cpu_temp", {})["style"], "am5")


if __name__ == "__main__":
    unittest.main()
