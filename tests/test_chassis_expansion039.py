"""Pure data regression for reviewed 0.39 enclosure references; no hardware I/O."""
import hashlib
import json
import unittest
from urllib.parse import urlparse

import chassis_catalog as catalog
from chassis_catalog_group_d import records


def expansion():
    return records(catalog._case, catalog._mount, catalog._ATX, catalog._EATX)


class ChassisExpansion039Tests(unittest.TestCase):
    def test_original_64_records_are_byte_for_byte_equivalent(self):
        original = list(catalog.CASES[:64])
        self.assertEqual(len(original), 64)
        encoded = json.dumps(original, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest(),
                         "b45133f15330ea71efc1fca8907250ba77783de68ce17e92b9d34424f65f3a56")

    def test_sixteen_structures_do_not_duplicate_the_existing_catalog(self):
        rows = expansion()
        self.assertEqual(len(rows), 16)
        ids = {row["id"] for row in rows}
        self.assertEqual(len(ids), 16)
        self.assertFalse(ids & {row["id"] for row in catalog.CASES[:64]})
        self.assertEqual(len({row["brand"] for row in rows}), 11)
        all_brands = {row["brand"] for row in (*catalog.CASES[:64], *rows)}
        self.assertEqual(len(all_brands), 25)

    def test_reviewed_primary_sources_and_bounded_records(self):
        hosts = {"havn.global", "streacom.com", "lian-li.com", "www.dan-cases.com",
                 "ncased.com", "ssupd.co", "cougargaming.com", "thermaltakeusa.com",
                 "www.geometricfuture.com", "www.fractal-design.com",
                 "fractaldesign.freshdesk.com", "www.in-win.com"}
        for row in expansion():
            with self.subTest(case=row["id"]):
                json.dumps(row, allow_nan=False)
                self.assertTrue(catalog.valid_case_id(row["id"]))
                self.assertEqual(row["geometry_accuracy"], "schematic")
                self.assertEqual(row["sources_reviewed"], "2026-11-07")
                self.assertTrue(row["fit_note"])
                self.assertTrue(row["sources"])
                for source in row["sources"]:
                    self.assertEqual(urlparse(source).scheme, "https")
                    self.assertIn(urlparse(source).hostname, hosts)
                self.assertTrue(all(50 < value < 800 for value in row["dimensions_mm"].values()))
                for fan in row["fan_mounts"]:
                    self.assertTrue(1 <= fan["count"] <= 4)
                    self.assertTrue(set(fan["size_mm"]) <= {120, 140, 180, 200})
                self.assertNotIn("installed_fans", row)

    def test_source_axes_and_mode_are_explicit(self):
        by_id = {row["id"]: row for row in expansion()}
        for case_id, expected in {
            "havn-hs-420": (259.5, 547, 541),
            "streacom-da6": (215, 431, 215),
            "streacom-db4": (260, 270, 260),
            "streacom-bc1-v2": (370, 115, 260),
            "ssupd-meshroom-s-v2": (167, 365, 247),
            "ncase-m2-round": (166, 262, 372),
            "lian-li-sup01": (212, 534, 403.45),
            "inwin-dubili": (244, 543, 523),
        }.items():
            self.assertEqual(tuple(by_id[case_id]["dimensions_mm"][key]
                                   for key in ("width", "height", "depth")), expected)

    def test_uncertain_fit_and_unpositioned_fan_options_stay_unknown(self):
        by_id = {row["id"]: row for row in expansion()}
        for case_id in ("streacom-bc1-v2", "ssupd-meshroom-s-v2",
                        "geometric-future-model-8-cowboy", "lian-li-a3-matx"):
            self.assertIsNone(by_id[case_id]["max_gpu_length_mm"])
        for case_id in ("streacom-da6", "streacom-db4", "streacom-bc1-v2", "ncase-m2-round"):
            self.assertEqual(by_id[case_id]["fan_mounts"], [])

    def test_distinct_exteriors_carry_specific_structure_flags(self):
        by_id = {row["id"]: row for row in expansion()}
        for case_id, flag in {
            "streacom-da6": "tubular_open_frame",
            "streacom-db4": "passive_finned_cube",
            "streacom-bc1-v2": "horizontal_test_bench",
            "fractal-mood": "fabric_column",
            "lian-li-sup01": "front_gpu_chamber",
            "fractal-era-2": "wood_top_panel",
            "inwin-poc": "origami_vent_tabs",
            "inwin-dubili": "reversible_u_frame",
        }.items():
            self.assertIn(flag, by_id[case_id]["features"])

    def test_factory_returns_new_records_without_cross_call_mutation(self):
        first, second = expansion(), expansion()
        first[0]["sources"].clear()
        self.assertTrue(second[0]["sources"])


if __name__ == "__main__":
    unittest.main()
