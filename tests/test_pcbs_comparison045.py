"""Bounded publisher-list extraction and conservative identity comparison.

Synthetic HTML only: no publisher assets, network, hardware or Qt.
"""
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.compare_pcbs045 import canonical, compare, parse_article


class PCBSComparison045Tests(unittest.TestCase):
    def compare_fixture(self, html, products, optional=()):
        with TemporaryDirectory(prefix="desktopstats-pcbs045-") as folder:
            root = Path(folder)
            raw = html.encode("utf8")
            (root / "fixture.html").write_bytes(raw)
            sources = [dict(id="fixture", url="https://publisher.example/update",
                            sha256=hashlib.sha256(raw).hexdigest())]
            return compare(dict(products=products, optional_products=list(optional)),
                           sources, root)

    def test_source_headers_are_not_parts_and_change_the_category(self):
        html = """<h2>Full Parts List</h2>
        <h3>Peripherals</h3><ul><li>Example Mouse</li></ul>
        <h3>SSD</h3><ul><li>Example NVMe 1TB</li></ul>
        <h3>CPU Blocks</h3><ul><li>Example CPU Water Block</li></ul>
        <h3>Other</h3><ul><li>Example NVLink Bridge</li></ul>
        <h2>Bug Fixes</h2><p>Example fixed accessory</p>"""
        rows = parse_article(html)
        self.assertEqual([(r["kind"], r["name"]) for r in rows], [
            ("peripheral", "Example Mouse"), ("storage", "Example NVMe 1TB"),
            ("cpu_block", "Example CPU Water Block"),
            ("expansion", "Example NVLink Bridge")])

    def test_duplicate_aliases_for_one_id_are_one_candidate(self):
        title = "NVIDIA GeForce Example GPU"
        product = dict(kind="gpu", label=title, model_id="same-id")
        alias = dict(kind="gpu", label="Example GPU", model_id="same-id")
        report, rows = self.compare_fixture(
            "<h2>Parts List</h2><h3>GPUs</h3><li>Example GPU</li>",
            [product], [alias])
        self.assertEqual(canonical(title), canonical(alias["label"]))
        self.assertEqual(rows[0]["candidate_ids"], ["same-id"])
        self.assertTrue(rows[0]["name_exact_match"])
        self.assertEqual(report["name_exact_matches"], 1)

    def test_ambiguous_catalog_names_are_not_promoted_to_verified_matches(self):
        report, rows = self.compare_fixture(
            "<h2>Parts List</h2><h3>GPUs</h3><li>Example GPU</li>",
            [dict(kind="gpu", label="Example GPU", model_id="sku-a"),
             dict(kind="gpu", label="Example GPU", model_id="sku-b")])
        self.assertEqual(rows[0]["candidate_ids"], ["sku-a", "sku-b"])
        self.assertFalse(rows[0]["name_exact_match"])
        self.assertEqual(report["unmatched_or_review"], 1)

    def test_grouped_variants_remain_one_review_entry_without_expansion(self):
        html = """<h2>Parts List</h2><h3>GPUs</h3>
        <li>Example GPU | OC | White</li>
        <h3>Cases</h3><li>Example Case (Includes Black and White)</li>"""
        report, rows = self.compare_fixture(html, [
            dict(kind="gpu", label="Example GPU | OC | White", model_id="gpu-a"),
            dict(kind="case", label="Example Case (Includes Black and White)", model_id="case-a")])
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["variant_group"] for r in rows))
        self.assertTrue(all(not r["name_exact_match"] for r in rows))
        self.assertEqual(report["grouped_variants"], 2)
        self.assertFalse(report["whole_game_inventory"])

    def test_bugfix_and_quality_sections_do_not_become_hardware(self):
        for stop in ("Bug List", "Bug Fixes", "Quality of Life Improvements", "General Fixes"):
            with self.subTest(stop=stop):
                html = ("<script>Parts List Cases Fake case</script>"
                        "<h2>Parts List</h2><h3>Cases</h3><li>Example Case</li>"
                        f"<h2>{stop}</h2><h3>GPUs</h3><li>Fixed GPU clipping</li>")
                self.assertEqual([r["name"] for r in parse_article(html)], ["Example Case"])

    def test_snapshot_hash_is_checked_before_comparison(self):
        with TemporaryDirectory(prefix="desktopstats-pcbs045-") as folder:
            root = Path(folder)
            (root / "fixture.html").write_text("<h2>Parts List</h2>", encoding="utf8")
            with self.assertRaises(AssertionError):
                compare(dict(products=[]), [dict(id="fixture", url="https://publisher.example/update",
                                                sha256="0" * 64)], root)


if __name__ == "__main__":
    unittest.main()
