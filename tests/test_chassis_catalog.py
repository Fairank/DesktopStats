"""Catalog data integrity and conservative matching, without network access."""

import json
import unittest
from unittest.mock import patch
from urllib.parse import urlparse

import chassis_catalog as catalog


class ChassisCatalogTests(unittest.TestCase):
    def test_coverage_is_explicit_and_identical_for_every_style(self):
        result = catalog.coverage()
        self.assertEqual(result["cases"], 96)
        self.assertEqual(result["brands"], 26)
        self.assertFalse(result["complete_market"])
        self.assertEqual(result["verified_firmware_identities"], 0)
        self.assertEqual(result["geometry_accuracy"], "schematic")
        self.assertEqual(len(catalog.choices()), len({row["id"] for row in catalog.choices()}))

    def test_bounded_ids_and_detached_picker_records(self):
        for case_id in (None, 1, [], {}, "", "../hyte-y60", "HYTE-Y60", "hyte-y60\n", "a" * 65):
            self.assertFalse(catalog.valid_case_id(case_id))
            self.assertIsNone(catalog.get_case(case_id))
        choices = catalog.choices()
        first = choices[0]["id"]
        choices[0]["label"] = "changed"
        case = catalog.get_case(first)
        case["dimensions_mm"]["width"] = -1
        case["sources"].clear()
        self.assertNotEqual(catalog.choices()[0]["label"], "changed")
        self.assertGreater(catalog.get_case(first)["dimensions_mm"]["width"], 0)
        self.assertTrue(catalog.get_case(first)["sources"])

    def test_records_are_json_friendly_with_primary_sources_and_sane_dimensions(self):
        hosts = {"lian-li.com", "support.nzxt.com", "nzxt.com", "assets.corsair.com", "www.corsair.com",
                 "www.fractal-design.com", "hyte.com", "www.asus.com", "rog.asus.com",
                 "www.coolermaster.com", "thermaltakeusa.com", "phanteks.com", "phanteks.com.tw", "www.bequiet.com",
                 "www.jonsbo.com", "www.antec.com", "www.montechpc.com", "uk.msi.com",
                 "download.msi.com", "storage-asset.msi.com", "www.msi.com", "legacy.coolermaster.com",
                 "thermaltake.com", "www.deepcool.com", "deepcool.com", "www.silverstonetek.com",
                 "device.report", "resources.mini-box.com", "www.in-win.com", "www.gigabyte.com", "download.gigabyte.com", "havn.global", "streacom.com", "www.dan-cases.com", "ncased.com", "ssupd.co", "www.geometricfuture.com", "geometricfuture.com", "cougargaming.com", "fractaldesign.freshdesk.com", "www.sama.cn"}
        forms = {"atx", "micro_atx", "mini_itx", "e_atx", "mini_dtx", "dtx", "ssi_eeb", "ssi_ceb"}
        for choice in catalog.choices():
            row = catalog.get_case(choice["id"])
            with self.subTest(case=choice["id"]):
                json.dumps(row, ensure_ascii=False, allow_nan=False)
                self.assertTrue(catalog.valid_case_id(row["id"]))
                self.assertEqual(set(row["dimensions_mm"]), {"width", "height", "depth"})
                self.assertTrue(all(50 < x < 800 for x in row["dimensions_mm"].values()))
                self.assertTrue(set(row["form_factors"]) <= forms)
                self.assertEqual(row["geometry_accuracy"], "schematic")
                self.assertEqual(row["sources_reviewed"], "2026-11-07")
                self.assertTrue(row["sources"])
                for source in row["sources"]:
                    self.assertEqual(urlparse(source).scheme, "https")
                    self.assertIn(urlparse(source).hostname, hosts)
                for mount in row["fan_mounts"]:
                    self.assertEqual(set(mount), {"position", "count", "size_mm"})
                    self.assertTrue(0 < mount["count"] <= 8)
                    self.assertTrue(all(80 <= size <= 200 for size in mount["size_mm"]))
                self.assertNotIn("installed_fans", row)

    def test_manufacturer_dimension_order_does_not_swap_height_and_depth(self):
        for case_id, dimensions in {
            "phanteks-nv7": (253, 586, 532),
            "fractal-torrent-tg": (242, 530, 544),
            "asus-proart-pa602": (245, 560, 593),
            "asus-rog-hyperion-gr701": (268, 659, 639),
            "cooler-master-haf-700-evo": (291, 626, 666),
            "be-quiet-shadow-base-800-fx": (247, 522, 550),
            "montech-king-95": (300, 442, 475),
            "jonsbo-d31-mesh": (205, 363, 452),
        }.items():
            with self.subTest(case=case_id):
                row = catalog.get_case(case_id)["dimensions_mm"]
                self.assertEqual(tuple(row[key] for key in ("width", "height", "depth")), dimensions)

    def test_corrected_limits_and_configuration_uncertainty_are_not_lost(self):
        self.assertEqual(catalog.get_case("nzxt-h5-flow-2024")["max_gpu_length_mm"], 410)
        self.assertEqual(catalog.get_case("asus-proart-pa602")["max_gpu_length_mm"], 440)
        for case_id in ("fractal-torrent-tg", "jonsbo-d31-mesh", "msi-mag-pano-100r-pz"):
            row = catalog.get_case(case_id)
            self.assertIsNone(row["max_gpu_length_mm"])
            self.assertTrue(row["fit_note"])
        self.assertEqual(catalog.get_case("fractal-north-mesh")["panels"]["left"], "mesh")
        self.assertEqual(catalog.get_case("hyte-y70")["label"], "HYTE Y70")

    def test_distinct_case_construction_is_available_to_the_renderer(self):
        for case_id, feature in (("hyte-y60", "vertical_gpu_mount"),
                                 ("montech-king-95", "curved_front_glass"),
                                 ("thermaltake-tower-300", "octagonal_front"),
                                 ("fractal-north-mesh", "wooden_front_slats"),
                                 ("fractal-torrent-tg", "top_psu_shroud"),
                                 ("cooler-master-haf-700-evo", "front_round_display")):
            self.assertIn(feature, catalog.get_case(case_id)["features"])
        self.assertEqual({catalog.get_case(row["id"])["layout"] for row in catalog.choices()},
                         {"tower", "dual_chamber", "compact", "vertical", "horizontal", "open_frame"})

    def test_unverified_retail_names_and_generic_brand_strings_never_auto_match(self):
        for enclosure in ({"manufacturer": "ASUS", "version": "TUF Gaming GT502"},
                          {"manufacturer": "HYTE", "version": "Y60"},
                          {"manufacturer": "ASUSTeK COMPUTER INC."}, None):
            self.assertEqual(catalog.match_enclosure(enclosure), [])

    def test_future_verified_mapping_requires_exact_maker_and_model(self):
        registry = (("Verified OEM", "Exact Model 1", "hyte-y60", "https://hyte.com/store/y60/cs-hyte-y60-b"),)
        with patch.object(catalog, "_FIRMWARE_IDENTITIES", registry):
            matches = catalog.match_enclosure({"manufacturer": " VERIFIED OEM ", "sku": "Exact Model 1"})
            self.assertEqual([row["id"] for row in matches], ["hyte-y60"])
            for enclosure in ({"manufacturer": "Other OEM", "sku": "Exact Model 1"},
                              {"manufacturer": "Verified OEM", "sku": "Exact Model 1 Plus"},
                              {"manufacturer": "Verified OEM", "product": "Exact Model 1"}):
                self.assertEqual(catalog.match_enclosure(enclosure), [])


if __name__ == "__main__":
    unittest.main()
