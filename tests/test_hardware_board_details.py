"""Exact exterior facts and their exported diagrams; synthetic offscreen Qt only."""

import base64
from collections import Counter
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

from PySide6.QtCore import QCoreApplication, QEvent, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression, qmlContext
from PySide6.QtSvg import QSvgRenderer

import hardware_appearance as hardware
import hardware_board_details as boards
from hardware_series import SERIES_CATALOG
from hardware_variant_art import ART
import hardware_variants as variants
import memory_appearance as memory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")

ROOT = Path(__file__).resolve().parents[1]
GPU_ROWS = {row[0]: row for row in hardware.CATALOG if row[1] == "gpu"}
MEMORY_ROWS = {row["id"]: row for row in memory.CATALOG}
BASE_GPU_IDS = {identity for row in boards.PROFILES.values() for identity in row["model_ids"]}
BASE_MEMORY_IDS = {
    identity for row in boards.MEMORY_PROFILES.values() for identity in row["model_ids"]
}
MODERN_STYLES = ("solid", "miniature", "soft")
# These different coolers receive their own explicitly implemented recipe.
# Adding another pending inventory row must never silently enable its art.
INDEPENDENT_GPU_IDS = {"msi-suprim-5090-32g-soc", "msi-suprim-5090-32g-oc"}


def exact_appearance(identity, style="solid"):
    if identity in GPU_ROWS:
        result = hardware.appearance_for("gpu", GPU_ROWS[identity][-1][0])
    else:
        result = memory.appearance_for_memory(model=MEMORY_ROWS[identity]["aliases"][0])
    if result["id"] != identity or result["confidence"] != "model":
        raise AssertionError((identity, result))
    return dict(result, icon_set=style)


def resolve_alias(row, alias):
    if row["kind"] == "memory":
        return memory.appearance_for_memory(model=alias)
    return hardware.appearance_for("gpu", alias)


def decode(source):
    header, body = source.split(",", 1)
    return base64.b64decode(body).decode() if ";base64" in header else unquote(body)


def sockets(svg):
    return Counter(
        node.get("class").split()[1]
        for node in ET.fromstring(svg).iter()
        if node.get("class", "").startswith("hardware-socket ")
    )


def memory_notch(svg):
    """Measure the open lower notch in the actual exported PCB contour."""
    tree = ET.fromstring(svg)
    contours = [node for node in tree.iter() if node.tag.endswith("path")
                and "Q" in node.get("d", "")]
    if len(contours) != 1:
        raise AssertionError("Expected one rounded PCB contour")
    position = start = None
    segments = []
    points = []
    for command, arguments in re.findall(r"([MHVQZ])([^MHVQZ]*)", contours[0].get("d")):
        values = [float(value) for value in re.findall(r"[-+]?(?:\d*\.)?\d+(?:e[-+]?\d+)?", arguments)]
        if command == "M":
            position = start = tuple(values)
        else:
            target = ((values[0], position[1]) if command == "H" else
                      (position[0], values[0]) if command == "V" else
                      tuple(values[-2:]) if command == "Q" else start)
            segments.append((command, position, target))
            position = target
        points.append(position)
    left, right = min(point[0] for point in points), max(point[0] for point in points)
    top, bottom = min(point[1] for point in points), max(point[1] for point in points)
    notches = []
    for index in range(1, len(segments) - 1):
        command, begin, end = segments[index]
        previous, following = segments[index - 1], segments[index + 1]
        if (command == "H" and begin[1] < bottom and previous[0] == following[0] == "V"
                and previous[1][1] == bottom and following[2][1] == bottom):
            notches.append((min(begin[0], end[0]), max(begin[0], end[0]), begin[1]))
    if len(notches) != 1:
        raise AssertionError("Expected one lower PCB notch")
    notch_left, notch_right, notch_top = notches[0]
    return dict(tree=tree, left=left, right=right, top=top, bottom=bottom,
                notch_left=notch_left, notch_right=notch_right, notch_top=notch_top)


class HardwareBoardDataTests(unittest.TestCase):
    def test_all_base_gpu_and_memory_models_have_separate_exact_guards(self):
        self.assertEqual(set(boards.PROFILES), {row["id"] for row in SERIES_CATALOG})
        self.assertEqual(set(boards.MEMORY_PROFILES), {row["id"] for row in memory.SERIES_CATALOG})
        self.assertEqual(len(BASE_GPU_IDS), 103)
        self.assertEqual(len(BASE_MEMORY_IDS), 16)
        self.assertFalse(BASE_GPU_IDS & BASE_MEMORY_IDS)
        seen = set()
        for kind, table in (("gpu", boards.PROFILES), ("memory", boards.MEMORY_PROFILES)):
            for series, row in table.items():
                with self.subTest(kind=kind, series=series):
                    self.assertIsInstance(row["model_ids"], tuple)
                    self.assertEqual(len(row["model_ids"]), 1)
                    identity = row["model_ids"][0]
                    self.assertNotIn(identity, seen)
                    seen.add(identity)
                    appearance = exact_appearance(identity)
                    self.assertEqual(appearance["series_id"], series)
                    details = boards.for_appearance(appearance)
                    self.assertEqual(details["model_ids"], (identity,))
                    self.assertEqual(details["kind"], kind)
                    self.assertEqual(details["series_id"], series)
                    self.assertTrue(row["source_urls"])
                    original_sources = list(row["source_urls"])[:8]
                    self.assertEqual(details["source_urls"][:len(original_sources)], original_sources)
                    if kind == "memory":
                        mechanical_source = {
                            ("ddr4", "dimm"): "https://www.kingston.com/datasheets/KVR32N22S8_16.pdf",
                            ("ddr5", "dimm"): "https://www.kingston.com/datasheets/KF564C32RSK2-32.pdf",
                            ("ddr4", "sodimm"): "https://www.kingston.com/datasheets/KVR32S22S8_16.pdf",
                        }[(row["generation"], row["form"])]
                        self.assertIn(mechanical_source, details["source_urls"])
                        self.assertEqual(set(details["source_urls"]) - set(original_sources),
                                         {mechanical_source} - set(original_sources))
                    else:
                        self.assertEqual(details["source_urls"], original_sources)
                    for url in details["source_urls"]:
                        parsed = urlsplit(url)
                        self.assertEqual(parsed.scheme, "https")
                        self.assertTrue(parsed.hostname)
                        self.assertIsNone(parsed.username)
                        self.assertNotIn("qa-private", url)

    def test_series_chip_brand_and_other_model_cannot_borrow_exterior_facts(self):
        for identity in sorted(BASE_GPU_IDS | BASE_MEMORY_IDS):
            value = exact_appearance(identity)
            with self.subTest(model=identity):
                for confidence in ("series", "brand", "generic", ""):
                    self.assertEqual(boards.for_appearance(dict(value, confidence=confidence)), {})
                self.assertEqual(boards.for_appearance(dict(value, id="unreviewed-sku")), {})
                self.assertEqual(boards.for_appearance(dict(value, series_id="wrong-series")), {})
                self.assertEqual(boards.for_appearance(dict(value, kind="cpu")), {})
                other_kind = "memory" if value["kind"] == "gpu" else "gpu"
                self.assertEqual(boards.for_appearance(dict(value, kind=other_kind)), {})

    def test_unknown_no_external_power_and_alternative_positions_remain_distinct(self):
        unknown = boards.for_appearance(exact_appearance("gigabyte-fx5200-n52128d"))
        passive_slot_power = boards.for_appearance(exact_appearance("sapphire-pulse-rx6400-4g-lp"))
        hof = boards.for_appearance(exact_appearance("galax-hof-5080-extreme"))
        self.assertIsNone(unknown["power_connectors"])
        self.assertEqual(unknown["power_text"], "供电接口待核实")
        self.assertEqual(boards.PROFILES["sapphire_pulse_rdna2_lp"]["power_connectors"], ())
        self.assertEqual(passive_slot_power["power_connectors"], [])
        self.assertEqual(passive_slot_power["power_text"], "无需外接供电")
        unconfirmed = boards.normalise("unconfirmed", {"model_ids": ("unconfirmed",)})
        self.assertIsNone(unconfirmed["ports"])
        self.assertIsNone(unconfirmed["power_connectors"])
        self.assertEqual(boards.label_groups(None, unknown="视频接口待核实"), "视频接口待核实")
        self.assertTrue(hof["alternative_power"])
        self.assertEqual(hof["power_connectors"], [
            {"type": "16pin", "count": 1, "standard": "12V-2x6"}
        ])
        self.assertIsNone(hof["dimensions_mm"]["length"])
        self.assertEqual(hof["pcb_length"], "unknown")
        self.assertFalse(passive_slot_power["alternative_power"])

    def test_native_io_and_host_bus_do_not_borrow_chip_reference_specifications(self):
        cases = {
            "asus-proart-5080-oc": {"displayport": 2, "hdmi": 1, "usb_c": 1},
            "asus-tuf-4070tis-oc": {"displayport": 3, "hdmi": 2},
            "gigabyte-windforce-4060-oc": {"displayport": 2, "hdmi": 2},
            "gigabyte-fx5200-n52128d": {"dvi": 1, "tv_out": 1, "vga": 1},
        }
        for identity, expected in cases.items():
            with self.subTest(model=identity):
                details = boards.for_appearance(exact_appearance(identity))
                self.assertEqual({row["type"]: row["count"] for row in details["ports"]}, expected)
        agp = boards.for_appearance(exact_appearance("gigabyte-fx5200-n52128d"))
        self.assertEqual(agp["host_interface"]["bus"], "agp")
        self.assertEqual(agp["host_interface"]["generation"], 8)
        self.assertEqual(agp["host_text"], "AGP8×")
        self.assertIsNone(agp["host_interface"]["lanes"])
        self.assertIsNone(agp["edge_key_count"])
        ambiguous = boards.for_appearance(exact_appearance("msi-n660-tf-2gd5-oc"))
        hdmi = next(row for row in ambiguous["ports"] if row["type"] == "hdmi")
        self.assertEqual(hdmi["form"], "unconfirmed")
        self.assertIn("形态待核实", ambiguous["ports_text"])

    def test_agp_multiplier_does_not_expand_pcie_generation_limit(self):
        raw = {"model_ids": ("synthetic-host",),
               "host_interface": {"bus": "pcie", "generation": 8}}
        self.assertIsNone(boards.normalise("synthetic", raw)["host_interface"]["generation"])
        raw["host_interface"]["generation"] = 6
        self.assertEqual(boards.normalise("synthetic", raw)["host_interface"]["generation"], 6)
        pcie = boards.for_appearance(exact_appearance("asus-dual-4060-oc"))
        self.assertEqual(pcie["host_text"], "PCIe 4")

    def test_exact_dvi_subtypes_keep_native_total_and_distinct_labels(self):
        lightning = boards.for_appearance(exact_appearance("msi-n680gtx-lightning"))
        dvi = [row for row in lightning["ports"] if row["type"] == "dvi"]
        self.assertEqual(dvi, [{"type": "dvi", "count": 1, "subtype": "DVI-I"},
                               {"type": "dvi", "count": 1, "subtype": "DVI-D"}])
        self.assertEqual(sum(row["count"] for row in lightning["ports"]), 4)
        self.assertIn("DVI-I × 1 · DVI-D × 1", lightning["ports_text"])
        duplicate = boards.groups([{"type": "dvi", "count": 2,
                                    "subtypes": ("dvi_d", "DVI-D")}], boards.PORT_TYPES)
        self.assertEqual(duplicate, [{"type": "dvi", "count": 2, "subtype": "DVI-D"}])
        self.assertEqual(boards.label_groups(duplicate), "DVI-D × 2")

    def test_malformed_dvi_subtype_lists_cannot_change_native_socket_counts(self):
        for subtypes in (("dvi_i",), ("dvi_i", "dvi_d", "dvi_d"), (),
                         "dvi_i", None, ("dvi_i", "invented"), ("dvi_i", 2)):
            with self.subTest(subtypes=subtypes):
                with self.assertRaises(ValueError):
                    boards.groups([{"type": "dvi", "count": 2, "subtypes": subtypes}],
                                  boards.PORT_TYPES)
        with self.assertRaises(ValueError):
            boards.groups([{"type": "dvi_i", "count": 1, "subtypes": ("dvi_d",)}],
                          boards.PORT_TYPES)

    def test_memory_module_generation_pins_and_form_survive_exact_lookup(self):
        for series, raw in boards.MEMORY_PROFILES.items():
            with self.subTest(series=series):
                row = boards.for_appearance(exact_appearance(raw["model_ids"][0]))
                self.assertEqual((row["form"], row["generation"], row["pins"]),
                                 (raw["form"], raw["generation"], raw["pins"]))
                self.assertIn(row["generation"], ("ddr4", "ddr5"))
                self.assertEqual(row["pins"], 260 if row["form"] == "sodimm" else 288)
                self.assertNotIn("ports", row)
                self.assertNotIn("power_connectors", row)

    def test_consumers_cannot_mutate_facts_or_provenance_of_later_lookups(self):
        value = exact_appearance("asus-proart-5080-oc")
        before = boards.for_appearance(value)
        changed = boards.for_appearance(value)
        changed["ports"][0]["count"] = 99
        changed["dimensions_mm"]["length"] = 1
        changed["host_interface"]["bus"] = "agp"
        changed["source_urls"].append("https://example.invalid/")
        self.assertEqual(boards.for_appearance(value), before)
        payload = boards.drawing_payload()
        payload[value["id"]]["ports"][0]["count"] = 99
        self.assertEqual(boards.drawing_payload()[value["id"]]["ports"][0]["count"], 2)

    def test_malformed_connector_counts_cannot_become_drawable_hardware(self):
        for count in (True, False, "1", 0, -1, 7, None):
            with self.subTest(count=count):
                with self.assertRaises(ValueError):
                    boards.groups([{"type": "16pin", "count": count}], boards.POWER_TYPES)
        with self.assertRaises(ValueError):
            boards.groups([{"type": "invented-port", "count": 1}], boards.PORT_TYPES)
        with self.assertRaises(ValueError):
            boards.groups([{"type": "hdmi", "count": 5},
                           {"type": "displayport", "count": 4}], boards.PORT_TYPES)


class HardwareVersionGuardTests(unittest.TestCase):
    def test_only_shared_or_explicit_independent_art_can_enter_ready_catalogs(self):
        shared = {key for key, row in variants.RECORDS.items()
                  if row["visual_relation"] == "shared"}
        self.assertTrue(INDEPENDENT_GPU_IDS <= set(ART))
        self.assertEqual(set(variants.READY), shared | set(ART))
        for identity in ART:
            self.assertIn(variants.RECORDS[identity]["visual_relation"], ("shared","different","unknown"))
            self.assertIn(variants.RECORDS[identity]["kind"], ("gpu","memory"))
            self.assertRegex(ART[identity]['recipe'],r'^(suprim_blackwell|[abc]_[a-z0-9_]+)$')
        for identity, version in variants.RECORDS.items():
            with self.subTest(model=identity):
                table = boards.MEMORY_PROFILES if version["kind"] == "memory" else boards.PROFILES
                self.assertIn(version["base_model_id"], table[version["series_id"]]["model_ids"])
                for alias in version["aliases"]:
                    answer = resolve_alias(version, alias)
                    if identity in variants.READY:
                        self.assertEqual(answer["id"], identity)
                        self.assertEqual(answer["confidence"], "model")
                        self.assertEqual(answer["board_details"]["model_ids"], (identity,))
                    else:
                        # A known white/revision/alternate cooler must not be
                        # mistaken for the shorter base alias embedded in it.
                        self.assertNotEqual(answer["confidence"], "model", (identity, alias, answer))
                        self.assertNotIn("board_details", answer)

    def test_shared_versions_inherit_only_their_reviewed_base_and_keep_own_sources(self):
        for identity, version in variants.READY.items():
            if version["visual_relation"] != "shared":
                continue
            with self.subTest(model=identity):
                source_table = (boards.MEMORY_PROFILES if version["kind"] == "memory"
                                else boards.PROFILES)
                source = source_table[version["series_id"]]
                saved = copy.deepcopy(source)
                result = variants.exterior_row(identity, source)
                self.assertEqual(result["model_ids"], (identity,))
                self.assertEqual(result["source_urls"], version["source_urls"])
                self.assertEqual(variants.base_identity(identity), version["base_model_id"])
                self.assertEqual(variants.exterior_row(identity, {"model_ids": ("another-sku",)}), {})
                self.assertEqual(source, saved)
                result["source_urls"] = ()
                self.assertEqual(source, saved)
        astral = exact_appearance("asus-astral-5090-oc")
        self.assertEqual(astral["board_details"]["dimensions_mm"],
                         {"length": 357.6, "height": 149.3, "thickness": 76})
        self.assertEqual(astral["id"], "asus-astral-5090-oc")

    def test_exact_version_aliases_do_not_swallow_unknown_suffixes_or_chip_only_names(self):
        for alias in ("ROG-ASTRAL-RTX5090-O32G-GAMING-UNREVIEWED",
                      "GeForce RTX 5090 32G SUPRIM SOC UNREVIEWED",
                      "CMK16GX4M2B3200C16-UNREVIEWED"):
            with self.subTest(alias=alias):
                answer = (memory.appearance_for_memory(model=alias) if alias.startswith("CMK")
                          else hardware.appearance_for("gpu", alias))
                self.assertNotEqual(answer["confidence"], "model")
                self.assertNotIn("board_details", answer)
        for name in ("NVIDIA GeForce RTX 5090", "ASUS RTX 5090", "MSI SUPRIM RTX 5090"):
            answer = hardware.appearance_for("gpu", name)
            self.assertNotEqual(answer["confidence"], "model")
            self.assertNotIn("board_details", answer)


class HardwareBoardSvgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native = cls.enterClassContext(patch(
            "ctypes.WinDLL", side_effect=AssertionError("No native I/O"), create=True))
        cls.process = cls.enterClassContext(patch(
            "subprocess.Popen", side_effect=AssertionError("No subprocess")))
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.engine = QQmlEngine()
        cls.warnings = []
        cls.engine.warnings.connect(
            lambda errors: cls.warnings.extend(error.toString() for error in errors))
        cls.component = QQmlComponent(cls.engine)
        cls.component.setData(b'''import QtQml
import "../native/HardwareShapes.js" as Shapes
import "../native/HardwareBoardDesigns.js" as Board
import "../native/HardwareBoardProfileData.js" as Data
QtObject {
 function table() { return JSON.stringify(Data.models) }
 function drawing(value) {
  const key=Shapes.key(value,"#303a48")
  return JSON.stringify({key:key,source:Shapes.source(key)})
 }
 function fromKey(key) { return JSON.stringify({source:Shapes.source(key),layers:Shapes.layers(key)}) }
 function technical(model,view) { return JSON.stringify(Board.technicalSource(model,view)) }
 function base(model) {
  const row=Data.models[model]
  const state={model_id:model,kind:row.kind,series_id:row.series_id}
  const g={x:3,y:6,w:18,h:10}
  const c={rim:"#777777",metal:"#aaaaaa",caseShade:"#333333",pcb:"#456456",gold:"#dddd00",edge:"#eeeeee"}
  return JSON.stringify(Board.base(state,g,c))
 }
 function baseWithHostField(model,field,value) {
  const host=Data.models[model].host_interface
  const previous=host[field]
  try {host[field]=value;return base(model)}
  finally {host[field]=previous}
 }
}''', QUrl.fromLocalFile(str(ROOT / "tests/HardwareBoardDetailsFixture.qml")))
        cls.item = cls.component.create()
        if cls.item is None:
            raise AssertionError([error.toString() for error in cls.component.errors()])

    @classmethod
    def tearDownClass(cls):
        cls.item.deleteLater()
        cls.component.deleteLater()
        cls.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        cls.app.processEvents()
        cls.native.assert_not_called()
        cls.process.assert_not_called()
        if cls.warnings:
            raise AssertionError(cls.warnings)

    def evaluate(self, expression):
        code = QQmlExpression(qmlContext(self.item), self.item, expression)
        result = code.evaluate()
        self.assertFalse(code.hasError(), code.error().toString())
        return json.loads(result[0] if isinstance(result, tuple) else result)

    def drawing(self, value):
        return self.evaluate("drawing(" + json.dumps(value) + ")")

    def technical(self, identity, view):
        return decode(self.evaluate("technical(" + json.dumps(identity) + "," + json.dumps(view) + ")"))

    def test_baked_table_is_current_bounded_and_contains_no_sources_or_notes(self):
        data = self.evaluate("table()")
        self.assertEqual(data, json.loads(json.dumps(boards.drawing_payload())))
        self.assertEqual(set(data), BASE_GPU_IDS | BASE_MEMORY_IDS | set(variants.READY))
        encoded = json.dumps(data)
        for field in ("source_url", "source_urls", "source_image_url", "notes", "representative"):
            self.assertNotIn('"' + field + '"', encoded)

    def test_every_typed_native_socket_is_drawn_once_and_unknowns_are_not_invented(self):
        data = boards.drawing_payload()
        for identity in sorted(BASE_GPU_IDS):
            for view, field in (("ports", "ports"), ("power", "power_connectors")):
                with self.subTest(model=identity, view=view):
                    expected = Counter()
                    for group in data[identity][field] or ():
                        kind = "unknown" if group.get("form") == "unconfirmed" else group["type"]
                        expected[kind] += group["count"]
                    svg = self.technical(identity, view)
                    self.assertEqual(sockets(svg), expected)
                    self.assertTrue(QSvgRenderer(svg.encode()).isValid())
                    self.assertFalse(any(node.tag.endswith(("image", "text", "script"))
                                         for node in ET.fromstring(svg).iter()))
        self.assertEqual(sockets(self.technical("asus-proart-5080-oc", "ports")),
                         Counter(displayport=2, hdmi=1, usb_c=1))
        self.assertEqual(sockets(self.technical("galax-hof-5080-extreme", "ports")),
                         Counter(displayport=3, hdmi=1))
        self.assertEqual(sockets(self.technical("galax-hof-5080-extreme", "power")),
                         Counter({"16pin": 1}))
        self.assertEqual(sockets(self.technical("msi-n660-tf-2gd5-oc", "ports")),
                         Counter(dvi=2, displayport=1, unknown=1))
        self.assertEqual(sockets(self.technical("unreviewed-sku", "power")), Counter())

    def test_agp_is_distinct_and_electrical_lanes_do_not_shorten_pcie_edge(self):
        base = lambda identity: self.evaluate("base(" + json.dumps(identity) + ")")
        table = self.evaluate("table()")
        identity = "sapphire-pulse-rx6400-4g-lp"
        original = base(identity)
        # Hold this exact card's full envelope fixed. Only electrical lanes
        # vary, so a changed connector would be an unjustified inference.
        for lanes in (1, 2, 4, 8, 16, None):
            with self.subTest(lanes=lanes):
                changed = self.evaluate("baseWithHostField(" + json.dumps(identity)
                                        + ',"lanes",' + json.dumps(lanes) + ")")
                self.assertEqual(changed, original)
        agp_id = "gigabyte-fx5200-n52128d"
        pcie_on_same_card = self.evaluate("baseWithHostField(" + json.dumps(agp_id)
                                          + ',"bus","pcie")')
        self.assertNotEqual(base(agp_id), pcie_on_same_card)
        self.assertEqual(self.evaluate("table()"), table, "Fixture mutations must be restored")
        self.assertEqual(table["gigabyte-fx5200-n52128d"]["host_interface"]["bus"], "agp")
        self.assertIsNone(table["gigabyte-fx5200-n52128d"]["edge_key_count"])

    def test_modern_memory_notches_follow_reviewed_module_dimensions(self):
        cases = (
            ("kingston-kvr32n22s8-16", 72.25 / 133.35, 1.5 / 133.35, 3.85 / 31.25),
            ("kingston-kf564c32rsk2-32", 68.10 / 133.35, 1.5 / 133.35, 3.85 / 31.25),
            ("kingston-kvr32s22s8-16", 38.3 / 69.6, 1 / 69.6, 4 / 30),
        )
        for identity, expected_position, expected_width, expected_depth in cases:
            for style in MODERN_STYLES:
                with self.subTest(model=identity, style=style):
                    measured = memory_notch(decode(self.drawing(exact_appearance(identity, style))["source"]))
                    width = measured["right"] - measured["left"]
                    height = measured["bottom"] - measured["top"]
                    center = (measured["notch_left"] + measured["notch_right"]) / 2
                    self.assertAlmostEqual((center - measured["left"]) / width, expected_position)
                    self.assertAlmostEqual((measured["notch_right"] - measured["notch_left"]) / width,
                                           expected_width)
                    self.assertAlmostEqual((measured["bottom"] - measured["notch_top"]) / height,
                                           expected_depth)
                    # The contact strip must leave the same opening; a PCB
                    # notch painted over by an unbroken gold bar is unusable.
                    contacts = [node for node in measured["tree"].iter()
                                if node.tag.endswith("rect")
                                and abs(float(node.get("y")) + float(node.get("height"))
                                        - measured["bottom"]) < 1e-8]
                    self.assertEqual(len(contacts), 2)
                    contacts.sort(key=lambda node: float(node.get("x")))
                    self.assertAlmostEqual(float(contacts[0].get("x")) + float(contacts[0].get("width")),
                                           measured["notch_left"])
                    self.assertAlmostEqual(float(contacts[1].get("x")), measured["notch_right"])
            # Outline keeps its old stylised opening instead of adopting the
            # new mechanical ratios, and still omits the exact model key.
            outlined = self.drawing(exact_appearance(identity, "outline"))
            self.assertEqual(len(outlined["key"].split("|")), 11)
            old = memory_notch(decode(outlined["source"]))
            old_center = (old["notch_left"] + old["notch_right"]) / 2
            self.assertAlmostEqual((old_center - old["left"]) / (old["right"] - old["left"]), .49)
            self.assertAlmostEqual(old["notch_right"] - old["notch_left"], 1.3)
            self.assertAlmostEqual(old["bottom"] - old["notch_top"], 1.05)

    def test_modern_exact_keys_add_identity_while_legacy_eleven_fields_still_render(self):
        for identity in sorted(BASE_GPU_IDS | BASE_MEMORY_IDS):
            for style in MODERN_STYLES:
                with self.subTest(model=identity, style=style):
                    value = exact_appearance(identity, style)
                    actual = self.drawing(value)
                    parts = actual["key"].split("|")
                    self.assertEqual(len(parts), 12)
                    self.assertEqual(parts[-1], identity)
                    legacy = self.evaluate("fromKey(" + json.dumps("|".join(parts[:11])) + ")")
                    svg = decode(legacy["source"])
                    self.assertTrue(QSvgRenderer(svg.encode()).isValid())
                    self.assertGreater(len(list(ET.fromstring(svg).iter())), 2)

    def test_forged_model_fields_and_telemetry_cannot_replace_reviewed_art(self):
        value = exact_appearance("asus-dual-4060-oc")
        original = self.drawing(value)
        changed = dict(value, source_url="https://example.invalid/injected", gpu_temp=100,
                       gpu_usage=99, gpu_power=900, fan_rpm=5000,
                       board_details={"ports": [{"type": "vga", "count": 6}]})
        self.assertEqual(self.drawing(changed), original)
        parts = original["key"].split("|")
        forged = parts[:-1] + ["msi-ventus-4060-2x-oc"]
        invalid = self.evaluate("fromKey(" + json.dumps("|".join(forged)) + ")")
        legacy = self.evaluate("fromKey(" + json.dumps("|".join(parts[:-1])) + ")")
        self.assertEqual(invalid, legacy)
        self.assertEqual(len(self.drawing(dict(value, confidence="series"))["key"].split("|")), 11)

    def test_independent_5090_recipe_draws_its_own_casing_and_seven_blade_fans(self):
        for identity in sorted(INDEPENDENT_GPU_IDS):
            value = exact_appearance(identity)
            self.assertEqual(value["board_details"]["recipe"], "suprim_blackwell")
            self.assertEqual(value["board_details"]["dimensions_mm"],
                             {"length": 359, "height": 150, "thickness": 76})
            self.assertEqual(value["fan_profile"]["technology"], "stormforce")
            self.assertEqual(value["fan_profile"]["blades"], 7)
            self.assertEqual(ART[identity]["fan_profile"]["group_size"], 1)
            self.assertEqual(sockets(self.technical(identity, "ports")),
                             Counter(displayport=3, hdmi=1))
            self.assertEqual(sockets(self.technical(identity, "power")), Counter({"16pin": 1}))
            for style in MODERN_STYLES:
                with self.subTest(model=identity, style=style):
                    result = self.drawing(dict(value, icon_set=style))
                    base = self.drawing(exact_appearance("msi-suprim-x-4090-24g", style))
                    self.assertNotEqual(result["source"], base["source"])
                    rendered = self.evaluate("fromKey(" + json.dumps(result["key"]) + ")")
                    casing = ET.fromstring(decode(rendered["layers"]["baseSource"]))
                    self.assertEqual(sum(node.get("class") == "hardware-variant-face suprim_blackwell"
                                         for node in casing.iter()), 1)
                    self.assertEqual(len(rendered["layers"]["rotors"]), 3)
                    for rotor in rendered["layers"]["rotors"]:
                        tree = ET.fromstring(decode(rotor["source"]))
                        blades = [node for node in tree.iter() if node.tag.endswith("path")
                                  and node.get("transform", "").startswith("rotate(")]
                        self.assertEqual(len(blades), 7)

    def test_outline_gpu_hashes_stay_exact_and_cpu_packages_bind_the_model(self):
        from tests.test_hardware_cartoon import assert_cpu_artwork
        cases = (
            ("cpu", "Intel Core i7-13700KF", "a82bae4cf9e8b4a7c5ef6ec66a3414d48c1d577e3d246730e8da994c4014bf41"),
            ("cpu", "AMD Ryzen 9 9950X", "63190769e5b03ec7cb5a970553c3726e309da3656a9033b45cae66cf204fa183"),
            ("gpu", "DUAL-RTX4060-O8G", "b08a961cb281d10a62d105d9a2e8a306afdeb1195b3805767145549d30f9cfbe"),
            ("gpu", "TUF-RTX4070TIS-O16G-GAMING", "19827c993b8a33978631ac6d2919a07de67e1324b73a05f2ad2631b04cc199d0"),
            ("gpu", "NVIDIA GeForce RTX 4070", "8c9cc5541d145f68bb67bae0d7b1d80cc559dac6c989e95e0dac0df394df6a68"),
        )
        for kind, alias, expected in cases:
            with self.subTest(alias=alias):
                value=dict(hardware.appearance_for(kind,alias),icon_set='outline');result=self.drawing(value)
                if kind=='cpu':assert_cpu_artwork(self,value,result)
                else:self.assertEqual(len(result["key"].split("|")), 11)
                self.assertEqual(hashlib.sha256(decode(result["source"]).encode()).hexdigest(), expected)

    def test_completed_version_inventory_contains_all_fifty_six_exact_versions(self):
        self.assertEqual(len(variants.RECORDS),56)
        self.assertEqual(set(variants.READY),set(variants.RECORDS))
        for identity,version in variants.READY.items():
            with self.subTest(model=identity):
                value=exact_appearance(identity)
                self.assertEqual(value['confidence'],'model')
                self.assertEqual(value['id'],identity)
                self.assertEqual(value['board_details']['model_ids'],(identity,))
                for style in MODERN_STYLES:
                    rendered=self.drawing(dict(value,icon_set=style))
                    self.assertEqual(rendered['key'].split('|')[-1],identity)
                    self.assertTrue(QSvgRenderer(decode(rendered['source']).encode()).isValid())

    def test_compact_dual_variants_replace_three_fan_parent_geometry(self):
        for identity in ('powercolor-fighter-7800xt-mini','sparkle-b580-roc-luna-12g-oc-ultra'):
            for style in MODERN_STYLES:
                with self.subTest(model=identity,style=style):
                    value=exact_appearance(identity,style)
                    self.assertEqual(value['fan_count'],2)
                    self.assertEqual(value['visible_fan_count'],2)
                    rendered=self.drawing(value)
                    layers=self.evaluate('fromKey('+json.dumps(rendered['key'])+')')['layers']
                    self.assertEqual(len(layers['rotors']),2)
                    self.assertLess(layers['rotors'][0]['cx'],layers['rotors'][1]['cx'])

    def test_rear_accessories_and_gc_hpwr_are_separate_lazy_sources(self):
        checked=0
        for identity in variants.READY:
            facts=boards.for_appearance(exact_appearance(identity))
            if facts.get('extra_power_interface')=='gc_hpwr':
                self.assertEqual(sockets(self.technical(identity,'power'))['gc_hpwr'],1)
            for view,field in (('backplate','backplate_recipe'),('accessory','accessory_backplate_recipe')):
                if not facts.get(field):continue
                source=self.technical(identity,view)
                self.assertTrue(QSvgRenderer(source.encode()).isValid())
                self.assertGreater(len(list(ET.fromstring(source).iter())),3)
                checked+=1
        self.assertGreaterEqual(checked,8)


if __name__ == "__main__":
    unittest.main()
