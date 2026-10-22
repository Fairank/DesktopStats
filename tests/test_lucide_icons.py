"""Bundled UI icon source integrity; pure files/geometry, no Qt or networking."""

import hashlib
import json
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "c29c276f16590cf017126671535ad8c792be64d8"
EXPECTED = {
    "cpu",
    "gpu",
    "memory",
    "vram",
    "battery",
    "power",
    "network",
    "disk",
    "custom",
    "grid",
    "sliders",
    "sensors",
    "plus",
    "search",
    "copy",
    "trash",
    "up",
    "down",
    "close",
    "check",
    "undo",
    "redo",
    "chevron",
    "fan",
    "temperature",
    "noise",
    "voltage",
    "frequency",
    "time",
    "download",
    "upload",
    "disk_read",
    "disk_write",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LucideSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = ROOT / "assets/lucide"
        cls.manifest = json.loads((cls.directory / "provenance.json").read_text(encoding="utf-8"))
        cls.js = (ROOT / "native/IconData.js").read_text(encoding="utf-8")
        match = re.search(r"var fragments = (.*?);\nfunction fragment", cls.js, re.S)
        cls.fragments = json.loads(match.group(1))

    def test_immutable_official_commit_and_full_license_are_included(self):
        self.assertEqual(self.manifest["repository"], "https://github.com/lucide-icons/lucide")
        self.assertEqual(self.manifest["commit"], COMMIT)
        self.assertEqual(self.manifest["release"], "1.61.0")
        license_path = self.directory / self.manifest["license"]["path"]
        self.assertEqual(digest(license_path), self.manifest["license"]["sha256"])
        text = license_path.read_text(encoding="utf-8")
        for notice in ("ISC License", "Lucide Icons and Contributors", "MIT License", "Cole Bemis"):
            self.assertIn(notice, text)

    def test_existing_and_quantity_names_keep_source_preserving_fragments(self):
        self.assertEqual(set(self.manifest["mapping"]), EXPECTED)
        self.assertEqual(set(self.fragments), EXPECTED)
        self.assertEqual(self.manifest["mapping_count"], len(EXPECTED))
        self.assertEqual(self.manifest["unique_source_count"], 30)

    def test_every_svg_and_fragment_matches_its_provenance(self):
        for alias, entry in self.manifest["mapping"].items():
            with self.subTest(alias=alias):
                source = self.directory / entry["path"]
                self.assertTrue(source.resolve().is_relative_to(self.directory.resolve()))
                self.assertEqual(digest(source), entry["sha256"])
                self.assertTrue(entry["children_unchanged"])
                text = source.read_bytes().decode("utf-8")
                child_text = re.fullmatch(r"\s*<svg\b[^>]*>(.*)</svg>\s*", text, re.S).group(1)
                self.assertEqual(self.fragments[alias], child_text)
                self.assertEqual(
                    hashlib.sha256(child_text.encode("utf-8")).hexdigest(), entry["children_sha256"]
                )

    def test_original_geometry_includes_rectangles_and_circles_not_just_paths(self):
        cpu = ET.fromstring(
            '<svg xmlns="http://www.w3.org/2000/svg">' + self.fragments["cpu"] + "</svg>"
        )
        gpu = ET.fromstring(
            '<svg xmlns="http://www.w3.org/2000/svg">' + self.fragments["gpu"] + "</svg>"
        )
        self.assertEqual(len(cpu.findall("{http://www.w3.org/2000/svg}rect")), 2)
        self.assertEqual(len(gpu.findall("{http://www.w3.org/2000/svg}circle")), 2)

    def test_pinned_urls_and_exact_local_software_source_set(self):
        prefix = "https://raw.githubusercontent.com/lucide-icons/lucide/" + COMMIT + "/icons/"
        expected_files = set()
        for entry in self.manifest["mapping"].values():
            expected_files.add(entry["name"] + ".svg")
            self.assertEqual(entry["url"], prefix + entry["name"] + ".svg")
            self.assertEqual(entry["path"], "icons/" + entry["name"] + ".svg")
        self.assertEqual(
            {path.name for path in (self.directory / "icons").iterdir()}, expected_files
        )
        self.assertFalse(self.manifest["runtime_network_required"])
        self.assertEqual(
            digest(ROOT / self.manifest["derived_file"]), self.manifest["derived_sha256"]
        )

    def test_all_svg_children_are_local_geometry_and_keep_the_original_grid(self):
        allowed = {"path", "line", "rect", "circle", "ellipse", "polyline", "polygon"}
        for source in (self.directory / "icons").glob("*.svg"):
            with self.subTest(source=source.name):
                text = source.read_text(encoding="utf-8")
                self.assertNotIn("<!", text)
                svg = ET.fromstring(text)
                self.assertEqual(svg.attrib["viewBox"], "0 0 24 24")
                self.assertEqual(svg.attrib["stroke-width"], "2")
                for child in svg:
                    self.assertIn(child.tag.removeprefix("{http://www.w3.org/2000/svg}"), allowed)
                    self.assertFalse(list(child))
                    self.assertFalse(
                        any(
                            key.lower().startswith("on") or "href" in key.lower()
                            for key in child.attrib
                        )
                    )
                    self.assertFalse(
                        any("url(" in value.lower() for value in child.attrib.values())
                    )

    def test_shared_aliases_keep_their_meaning(self):
        expected = {
            "cpu": "cpu",
            "gpu": "gpu",
            "memory": "memory-stick",
            "vram": "memory-stick",
            "custom": "layout-grid",
            "grid": "layout-grid",
            "network": "arrow-down-up",
            "power": "zap",
            "up": "chevron-up",
            "down": "chevron-down",
            "chevron": "chevron-right",
            "fan": "fan",
            "temperature": "thermometer",
            "noise": "audio-lines",
            "voltage": "gauge",
            "frequency": "activity",
            "time": "clock",
            "download": "arrow-down-to-line",
            "upload": "arrow-up-from-line",
            "disk_read": "hard-drive-upload",
            "disk_write": "hard-drive-download",
        }
        self.assertEqual(
            {alias: self.manifest["mapping"][alias]["name"] for alias in expected}, expected
        )

    def test_license_notice_is_reachable_in_distribution_assets(self):
        notice = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("assets/lucide/LICENSE", notice)
        self.assertIn(COMMIT, notice)
        self.assertIn("ISC", notice)
        self.assertIn("MIT", notice)
        self.assertEqual(self.manifest["license"]["path"], "LICENSE")


if __name__ == "__main__":
    unittest.main()
