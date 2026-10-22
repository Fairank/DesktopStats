"""Pure editor interaction checks; no Qt, collector, IPC or displayed window."""

import copy
import math
import unittest

from layout_assist import (
    LayoutAssistError,
    align_layout,
    append_layout,
    assist_rect,
    distribute_layout,
    preset_layout,
    resize_layout,
    swap_layout,
)


def rect(x, y, width, height):
    return dict(x=x, y=y, width=width, height=height)


class LayoutAssistTests(unittest.TestCase):
    def setUp(self):
        self.body = dict(width=1000, height=300)
        self.positions = {
            "cpu_power": rect(0.1, 0.1, 0.128, 0.1),
            "external:gpu": rect(0.5, 0.5, 0.128, 0.1),
        }

    def assert_legal(self, positions, body):
        for key, a in positions.items():
            self.assertGreaterEqual(a["x"], -1e-8, key)
            self.assertGreaterEqual(a["y"], -1e-8, key)
            self.assertLessEqual(a["x"] + a["width"], 1 + 1e-8, key)
            self.assertLessEqual(a["y"] + a["height"], 1 + 1e-8, key)
            self.assertGreaterEqual(a["width"] * body["width"], 128 - 1e-8, key)
            self.assertGreaterEqual(a["height"] * body["height"], 30 - 1e-8, key)
            for other, b in positions.items():
                if key == other:
                    continue
                overlap = (
                    min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"]) > 1e-8
                    and min(a["y"] + a["height"], b["y"] + b["height"]) - max(a["y"], b["y"]) > 1e-8
                )
                self.assertFalse(overlap, (key, other))

    def test_content_boundary_and_center_guides_use_actual_dip(self):
        proposal = rect(0.004, 0.1, 0.128, 0.1)
        result = assist_rect(self.positions, "cpu_power", proposal, self.body)
        self.assertTrue(result["valid"])
        self.assertEqual(result["rect"]["x"], 0)
        self.assertIn(
            dict(axis="x", position=0.0, kind="boundary", target_id=None, anchor="start"),
            result["guides"],
        )
        proposal["x"] = 0.434
        result = assist_rect(self.positions, "cpu_power", proposal, self.body)
        self.assertAlmostEqual(result["rect"]["x"], 0.436)
        self.assertTrue(
            any(
                g["axis"] == "x" and g["kind"] == "center" and g["position"] == 500
                for g in result["guides"]
            )
        )

    def test_peer_semantics_precede_nearer_grid_and_include_stable_id(self):
        self.positions["external:gpu"]["x"] = 0.53
        result = assist_rect(self.positions, "cpu_power", rect(0.396, 0.1, 0.128, 0.1), self.body)
        # Right edge 524 -> peer left 530 is within six DIP; grid 400 must not win.
        self.assertAlmostEqual(result["rect"]["x"], 0.402)
        self.assertTrue(
            any(g["position"] == 530 and g["target_id"] == "external:gpu" for g in result["guides"])
        )

    def test_grid_is_eight_dip_and_threshold_can_disable_a_distant_target(self):
        result = assist_rect(self.positions, "cpu_power", rect(0.021, 0.1, 0.128, 0.1), self.body)
        self.assertAlmostEqual(result["rect"]["x"], 0.024)
        self.assertTrue(
            any(
                g["axis"] == "x" and g["kind"] == "grid" and g["position"] == 24
                for g in result["guides"]
            )
        )
        result = assist_rect(
            self.positions, "cpu_power", rect(0.021, 0.1, 0.128, 0.1), self.body, threshold=1
        )
        self.assertAlmostEqual(result["rect"]["x"], 0.021)
        self.assertFalse(any(g["axis"] == "x" for g in result["guides"]))

    def test_alt_and_snap_off_bypass_only_snap_not_bounds_or_minimum(self):
        for settings in (dict(enabled=False), dict(bypass=True)):
            result = assist_rect(
                self.positions, "cpu_power", rect(0.021, 0.1, 0.9, 0.9), self.body, **settings
            )
            self.assertEqual(result["rect"], rect(0.021, 0.1, 0.128, 0.1))
            self.assertFalse(result["guides"])
            result = assist_rect(
                self.positions, "cpu_power", rect(-1, 2, 0.9, 0.9), self.body, **settings
            )
            self.assertEqual(result["rect"], rect(0, 0.9, 0.128, 0.1))
            result = assist_rect(
                self.positions,
                "cpu_power",
                rect(0.9, 0.9, 0.001, 0.001),
                self.body,
                operation="resize",
                **settings,
            )
            self.assertEqual(result["rect"], self.positions["cpu_power"])

    def test_resize_keeps_anchor_and_snaps_only_moving_edges(self):
        result = assist_rect(
            self.positions, "cpu_power", rect(0.2, 0.2, 0.396, 0.1), self.body, operation="resize"
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["rect"]["x"], 0.1)
        self.assertEqual(result["rect"]["y"], 0.1)
        self.assertAlmostEqual(result["rect"]["width"], 0.4)
        self.assertTrue(all(g["anchor"] == "end" for g in result["guides"]))

    def test_resize_cannot_overflow_and_does_not_inflate_the_content_body(self):
        body = dict(width=300, height=100)
        positions = {"a": rect(0.2, 0.2, 0.5, 0.5)}
        result = assist_rect(
            positions, "a", rect(0, 0, 20, 20), body, operation="resize", bypass=True
        )
        self.assertEqual(result["rect"], rect(0.2, 0.2, 0.8, 0.8))
        self.assertTrue(result["valid"])
        self.assertEqual(body, dict(width=300, height=100))

    def test_occupied_slot_returns_collision_instead_of_silent_swap(self):
        result = assist_rect(
            self.positions, "cpu_power", self.positions["external:gpu"], self.body, bypass=True
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "overlap")
        self.assertEqual(result["collisions"], ["external:gpu"])

    def test_snap_never_introduces_an_overlap_in_an_accepted_candidate(self):
        for x in range(0, 873, 19):
            for y in (0, 120, 145, 180, 270):
                result = assist_rect(
                    self.positions, "cpu_power", rect(x / 1000, y / 300, 0.128, 0.1), self.body
                )
                if result["valid"]:
                    updated = dict(self.positions, cpu_power=result["rect"])
                    self.assert_legal(updated, self.body)

    def test_all_presets_keep_all_ids_and_enforce_real_readable_floor(self):
        for count in range(1, 7):
            ids = [f"external:{index}" for index in range(count)]
            for preset in ("auto", "horizontal", "vertical", "grid"):
                for width in (80, 300, 760, 880, 1400):
                    for height in (24, 32, 132, 300):
                        body = dict(width=width, height=height)
                        result = preset_layout(ids, body, preset)
                        self.assertTrue(result["valid"])
                        self.assertEqual(list(result["positions"]), ids)
                        self.assert_legal(result["positions"], result["body"])
                        self.assertGreaterEqual(result["body"]["width"], width)
                        self.assertGreaterEqual(result["body"]["height"], height)
                        self.assertEqual(body, dict(width=width, height=height))

    def test_auto_balances_six_as_three_by_two_and_slim_strip_keeps_one_row(self):
        ids = list("abcdef")
        balanced = preset_layout(ids, dict(width=760, height=152))
        self.assertEqual((balanced["columns"], balanced["rows"]), (3, 2))
        strip = preset_layout(ids, dict(width=880, height=32))
        self.assertEqual((strip["columns"], strip["rows"]), (6, 1))
        self.assertEqual(strip["body"], dict(width=880, height=32))
        narrow = preset_layout(ids, dict(width=300, height=32))
        self.assertEqual((narrow["columns"], narrow["rows"]), (2, 3))
        self.assertEqual(narrow["body"], dict(width=300, height=106))

    def test_grid_preset_has_balanced_default_or_requested_column_count(self):
        result = preset_layout(list("abcde"), self.body, "grid")
        self.assertEqual((result["columns"], result["rows"]), (3, 2))
        result = preset_layout(list("abcde"), self.body, "grid", columns=2)
        self.assertEqual((result["columns"], result["rows"]), (2, 3))

    def test_horizontal_and_vertical_expand_instead_of_discarding_metrics(self):
        body = dict(width=300, height=32)
        horizontal = preset_layout(list("abcdef"), body, "horizontal")
        self.assertEqual(horizontal["body"], dict(width=808, height=32))
        vertical = preset_layout(list("abcdef"), body, "vertical")
        self.assertEqual(vertical["body"], dict(width=300, height=220))

    def test_single_alignment_uses_content_while_multi_uses_selected_envelope(self):
        for command, axis, expected in (
            ("left", "x", 0),
            ("center", "x", 0.436),
            ("right", "x", 0.872),
            ("top", "y", 0),
            ("middle", "y", 0.45),
            ("bottom", "y", 0.9),
        ):
            result = align_layout(self.positions, self.body, ["cpu_power"], command)
            self.assertTrue(result["valid"])
            self.assertAlmostEqual(result["positions"]["cpu_power"][axis], expected)
        result = align_layout(self.positions, self.body, list(self.positions), "left")
        self.assertTrue(result["valid"])
        self.assertEqual(result["positions"]["external:gpu"]["x"], 0.1)
        self.assertEqual(result["positions"]["cpu_power"], self.positions["cpu_power"])

    def test_alignment_collision_rejects_whole_batch_and_keeps_other_metrics(self):
        positions = dict(self.positions, third=rect(0.1, 0.5, 0.128, 0.1))
        original = copy.deepcopy(positions)
        result = align_layout(positions, self.body, ["cpu_power", "external:gpu"], "left")
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "overlap")
        self.assertEqual(result["positions"], original)
        self.assertEqual(result["collisions"], ["external:gpu", "third"])

    def test_distribution_equalizes_gaps_keeps_endpoints_and_unselected_rects(self):
        body = dict(width=1000, height=300)
        positions = {
            "a": rect(0, 0, 0.128, 0.1),
            "b": rect(0.2, 0, 0.2, 0.1),
            "c": rect(0.8, 0, 0.128, 0.1),
            "other": rect(0, 0.5, 0.128, 0.1),
        }
        result = distribute_layout(positions, body, ["c", "a", "b"], "horizontal")
        self.assertTrue(result["valid"])
        updated = result["positions"]
        left_gap = updated["b"]["x"] - (updated["a"]["x"] + updated["a"]["width"])
        right_gap = updated["c"]["x"] - (updated["b"]["x"] + updated["b"]["width"])
        self.assertAlmostEqual(left_gap, right_gap)
        self.assertEqual(updated["a"], positions["a"])
        self.assertEqual(updated["c"], positions["c"])
        self.assertEqual(updated["other"], positions["other"])

    def test_vertical_distribution_and_insufficient_axis_space(self):
        body = dict(width=400, height=300)
        positions = {
            "a": rect(0, 0, 0.4, 0.1),
            "b": rect(0, 0.2, 0.4, 0.1),
            "c": rect(0, 0.9, 0.4, 0.1),
        }
        result = distribute_layout(positions, body, list(positions), "y")
        self.assertTrue(result["valid"])
        self.assertAlmostEqual(result["positions"]["b"]["y"], 0.45)
        # All items sit in separate vertical rows, so horizontally fitting them
        # inside their identical 160-DIP envelope is impossible.
        result = distribute_layout(positions, body, list(positions), "x")
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "insufficient_space")
        self.assertEqual(result["positions"], positions)

    def test_distribution_preserves_full_envelope_for_staggered_unequal_rectangles(self):
        body = dict(width=2000, height=300)
        for positions in (
            {
                "wide": rect(0, 0, 0.45, 0.1),
                "small": rect(0.05, 0.3, 0.064, 0.1),
                "right": rect(0.8, 0.6, 0.064, 0.1),
            },
            {
                "left": rect(0, 0, 0.064, 0.1),
                "wide": rect(0.3, 0.3, 0.45, 0.1),
                "small": rect(0.4, 0.6, 0.064, 0.1),
            },
        ):
            result = distribute_layout(positions, body, list(positions), "x")
            self.assertTrue(result["valid"])
            updated = result["positions"]
            self.assertEqual(
                min(r["x"] for r in updated.values()), min(r["x"] for r in positions.values())
            )
            self.assertEqual(
                max(r["x"] + r["width"] for r in updated.values()),
                max(r["x"] + r["width"] for r in positions.values()),
            )
            ordered = sorted(updated.values(), key=lambda r: r["x"])
            gaps = [b["x"] - a["x"] - a["width"] for a, b in zip(ordered, ordered[1:])]
            self.assertAlmostEqual(gaps[0], gaps[1])
            self.assert_legal(updated, body)

    def test_distribution_clashing_with_unselected_item_rolls_back_atomically(self):
        positions = {
            "a": rect(0, 0, 0.128, 0.1),
            "b": rect(0.2, 0, 0.128, 0.1),
            "c": rect(0.8, 0, 0.128, 0.1),
            "other": rect(0.4, 0, 0.128, 0.1),
        }
        result = distribute_layout(positions, self.body, list("abc"), "x")
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "overlap")
        self.assertEqual(result["positions"], positions)

    def test_disabled_commands_have_stable_reasons(self):
        result = align_layout(self.positions, self.body, [], "left")
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "need_selection")
        result = distribute_layout(self.positions, self.body, list(self.positions), "x")
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "need_three")

    def test_resize_keeps_every_slot_and_clamps_body_to_readable_floor(self):
        body = dict(width=880, height=152)
        positions = preset_layout(list("abcdef"), body, "grid")["positions"]
        result = resize_layout(positions, body, dict(width=80, height=20))
        self.assertTrue(result["valid"])
        self.assertTrue(result["expanded"])
        self.assertEqual(result["positions"], positions)
        self.assertEqual(list(result["positions"]), list("abcdef"))
        self.assert_legal(result["positions"], result["body"])
        larger = resize_layout(positions, body, dict(width=1400, height=500))
        self.assertEqual(larger["body"], dict(width=1400, height=500))
        self.assertFalse(larger["expanded"])

    def test_resize_rejects_existing_invalid_layout_instead_of_hiding_missing_values(self):
        positions = dict(self.positions, bad=rect(0, 0.8, 0.01, 0.1))
        result = resize_layout(positions, self.body, dict(width=1400, height=500))
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "minimum_size")
        self.assertEqual(result["positions"], positions)

    def test_explicit_swap_preserves_complete_slot_set_and_untouched_items(self):
        positions = preset_layout(list("abcdef"), dict(width=880, height=152), "grid")["positions"]
        result = swap_layout(positions, dict(width=880, height=152), "a", "f")
        self.assertTrue(result["valid"])
        self.assertTrue(result["changed"])
        self.assertEqual(result["positions"]["a"], positions["f"])
        self.assertEqual(result["positions"]["f"], positions["a"])
        self.assertEqual(list(result["positions"]), list(positions))
        for key in "bcde":
            self.assertEqual(result["positions"][key], positions[key])

    def test_append_fills_available_slot_with_gap_and_preserves_old_dip(self):
        body = dict(width=300, height=100)
        positions = {"cpu": rect(0, 0, 128 / 300, 0.3)}
        original = copy.deepcopy(positions)
        result = append_layout(positions, body, ["gpu"])
        self.assertTrue(result["valid"])
        self.assertFalse(result["expanded"])
        self.assertEqual(result["positions"]["cpu"], positions["cpu"])
        self.assertEqual(result["positions"]["gpu"], rect(136 / 300, 0, 128 / 300, 0.3))
        self.assertEqual(result["added"], ["gpu"])
        self.assertEqual(positions, original)
        self.assert_legal(result["positions"], result["body"])

    def test_append_full_body_grows_below_and_preserves_all_visible_old_rectangles(self):
        body = dict(width=400, height=100)
        positions = {"old:a": rect(0, 0, 0.5, 1), "old:b": rect(0.5, 0, 0.5, 1)}
        result = append_layout(positions, body, ["external:new:1", "new:2", "new:3", "new:4"])
        self.assertTrue(result["valid"])
        self.assertTrue(result["expanded"])
        self.assertEqual(result["body"], dict(width=400, height=176))
        self.assertEqual(
            list(result["positions"]), [*positions, "external:new:1", "new:2", "new:3", "new:4"]
        )
        for key, old in positions.items():
            new = result["positions"][key]
            for field, edge in (
                ("x", "width"),
                ("y", "height"),
                ("width", "width"),
                ("height", "height"),
            ):
                self.assertAlmostEqual(old[field] * body[edge], new[field] * result["body"][edge])
        self.assertAlmostEqual(result["positions"]["external:new:1"]["y"] * 176, 108)
        self.assertAlmostEqual(result["positions"]["new:3"]["y"] * 176, 146)
        self.assert_legal(result["positions"], result["body"])

    def test_append_preserves_every_old_dip_for_real_small_bar_and_large_bodies(self):
        for count in range(1, 6):
            ids = [f"old:{index}" for index in range(count)]
            for body in (
                dict(width=264, height=84),
                dict(width=880, height=32),
                dict(width=1380, height=292),
            ):
                initial = preset_layout(ids, body)
                result = append_layout(initial["positions"], initial["body"], ["new"])
                self.assertTrue(result["valid"])
                self.assert_legal(result["positions"], result["body"])
                self.assertEqual(list(result["positions"]), [*ids, "new"])
                for key in ids:
                    for field, edge in (
                        ("x", "width"),
                        ("y", "height"),
                        ("width", "width"),
                        ("height", "height"),
                    ):
                        before = initial["positions"][key][field] * initial["body"][edge]
                        after = result["positions"][key][field] * result["body"][edge]
                        self.assertAlmostEqual(before, after)

    def test_append_empty_sequence_is_noop_and_unreadable_old_state_is_explicit(self):
        result = append_layout(self.positions, self.body, [])
        self.assertTrue(result["valid"])
        self.assertFalse(result["changed"])
        self.assertFalse(result["expanded"])
        self.assertEqual(result["positions"], self.positions)
        invalid = {"a": rect(0, 0, 0.01, 1)}
        result = append_layout(invalid, self.body, ["b"])
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "minimum_size")
        self.assertEqual(result["positions"], invalid)

    def test_append_rejects_overwrite_duplicate_and_excess_channels(self):
        for ids in (["cpu_power"], ["x", "x"], list("abcde"), [None], "a"):
            with self.subTest(ids=ids), self.assertRaises(LayoutAssistError):
                append_layout(self.positions, self.body, ids)

    def test_all_operations_leave_input_objects_unchanged_and_return_detached_rects(self):
        positions, body = copy.deepcopy(self.positions), dict(self.body)
        original = copy.deepcopy(positions), dict(body)
        results = [
            align_layout(positions, body, list(positions), "left"),
            distribute_layout(positions, body, list(positions), "x"),
            swap_layout(positions, body, *positions),
            resize_layout(positions, body, dict(width=1500, height=600)),
        ]
        assist_rect(positions, "cpu_power", rect(0.004, 0.1, 0.128, 0.1), body)
        self.assertEqual((positions, body), original)
        for result in results:
            result["positions"]["cpu_power"]["x"] = 0.99
        self.assertEqual((positions, body), original)

    def test_invalid_finite_geometry_and_unsupported_operations_are_rejected(self):
        calls = [
            lambda: assist_rect(self.positions, "absent", rect(0, 0, 1, 1), self.body),
            lambda: assist_rect(self.positions, "cpu_power", rect(math.nan, 0, 1, 1), self.body),
            lambda: assist_rect(self.positions, "cpu_power", rect(0, 0, 1, 1), self.body, grid=-1),
            lambda: assist_rect(
                self.positions, "cpu_power", rect(0, 0, 1, 1), self.body, threshold=True
            ),
            lambda: preset_layout([], self.body),
            lambda: preset_layout(["a", "a"], self.body),
            lambda: preset_layout(list("abcdefg"), self.body),
            lambda: preset_layout(["a"], self.body, columns=1.5),
            lambda: align_layout(self.positions, self.body, ["cpu_power"], "nonsense"),
            lambda: align_layout(self.positions, self.body, ["cpu_power"] * 2, "left"),
            lambda: distribute_layout(self.positions, self.body, list(self.positions), "z"),
            lambda: resize_layout(self.positions, self.body, dict(width=0, height=100)),
            lambda: swap_layout(self.positions, self.body, "cpu_power", "missing"),
        ]
        for call in calls:
            with self.subTest(call=call), self.assertRaises(LayoutAssistError):
                call()


if __name__ == "__main__":
    unittest.main()
