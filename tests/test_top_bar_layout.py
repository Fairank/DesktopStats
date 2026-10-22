"""Pure top-bar layout contracts; no native APIs, sensors, or shown windows."""

import copy
import unittest
from dataclasses import FrozenInstanceError
from math import ceil

from top_bar_layout import LayoutError, MetricItem, PixelRect, plan_top_bar


def metrics(count, width=40):
    return [MetricItem(f"metric_{index}", width) for index in range(count)]


class TopBarLayoutTests(unittest.TestCase):
    def assert_valid_regions(self, plan, original):
        self.assertEqual(plan.bounds.left, original.left)
        self.assertEqual(plan.bounds.right, original.right)
        self.assertEqual(plan.bounds.top, original.top)
        self.assertLessEqual(plan.bounds.bottom, original.bottom)
        regions = [plan.menu_hit, *(item.rect for item in plan.items)]
        if plan.overflow_hit is not None:
            regions.append(plan.overflow_hit)
        for region in regions:
            self.assertGreaterEqual(region.left, plan.bounds.left)
            self.assertLessEqual(region.right, plan.bounds.right)
            self.assertEqual((region.top, region.bottom), (plan.bounds.top, plan.bounds.bottom))
            self.assertGreaterEqual(region.width, plan.bounds.height)
        for left, right in zip(regions, regions[1:]):
            self.assertLessEqual(left.right, right.left)

    def test_zero_items_and_menu_minimum_width(self):
        plan = plan_top_bar(PixelRect(0, 0, 48, 32))
        self.assertEqual(plan.bounds, PixelRect(0, 0, 48, 32))
        self.assertEqual(plan.menu_hit, PixelRect(8, 0, 40, 32))
        self.assertEqual(plan.items, ())
        self.assertIsNone(plan.overflow_hit)
        self.assertEqual(plan.overflow_ids, ())
        self.assertIs(plan.bounds, plan.desired_bounds)

    def test_six_twenty_four_and_sixty_four_items_fit_without_overflow(self):
        for count in (6, 24, 64):
            with self.subTest(count=count):
                monitor = PixelRect(0, 0, 6000, 1000)
                requested = metrics(count)
                plan = plan_top_bar(monitor, items=requested)
                self.assertEqual(
                    tuple(item.id for item in plan.items), tuple(i.id for i in requested)
                )
                self.assertIsNone(plan.overflow_hit)
                self.assertEqual(plan.overflow_ids, ())
                self.assertEqual(plan.items[-1].rect.right, 5992)
                self.assert_valid_regions(plan, monitor)

    def test_overflow_keeps_longest_prefix_in_one_row(self):
        for count in (6, 24, 64):
            with self.subTest(count=count):
                requested = metrics(count)
                monitor = PixelRect(0, 0, 300, 200)
                plan = plan_top_bar(monitor, items=requested)
                self.assertEqual(
                    tuple(item.id for item in plan.items), tuple(i.id for i in requested[:3])
                )
                self.assertEqual(plan.overflow_ids, tuple(i.id for i in requested[3:]))
                self.assertEqual(plan.items[0].rect, PixelRect(52, 0, 104, 32))
                self.assertEqual(plan.overflow_hit, PixelRect(244, 0, 292, 32))
                self.assert_valid_regions(plan, monitor)

    def test_exact_fit_threshold_does_not_hide_or_add_an_item_early(self):
        requested = metrics(6)
        below = plan_top_bar(PixelRect(0, 0, 299, 200), items=requested)
        exact = plan_top_bar(PixelRect(0, 0, 300, 200), items=requested)
        all_fit = plan_top_bar(PixelRect(0, 0, 432, 200), items=requested)
        self.assertEqual(len(below.items), 2)
        self.assertEqual(len(exact.items), 3)
        self.assertEqual(len(all_fit.items), 6)
        self.assertIsNone(all_fit.overflow_hit)

    def test_never_skips_a_wide_metric_for_a_later_short_one(self):
        requested = [MetricItem("first", 60), MetricItem("wide", 900), MetricItem("last", 0)]
        plan = plan_top_bar(PixelRect(0, 0, 300, 100), items=requested)
        self.assertEqual(tuple(item.id for item in plan.items), ("first",))
        self.assertEqual(plan.overflow_ids, ("wide", "last"))

    def test_two_fixed_groups_preserve_relative_and_output_array_order(self):
        requested = [MetricItem("r0",40), MetricItem("l1",40,"left"),
                     MetricItem("r2",40), MetricItem("l3",40,"left")]
        plan = plan_top_bar(PixelRect(0,0,600,200),items=requested)
        self.assertEqual(tuple(item.id for item in plan.items), ("r0","l1","r2","l3"))
        placed = {item.id:item.rect for item in plan.items}
        self.assertEqual(placed["l1"].left, plan.menu_hit.right+12)
        self.assertLess(placed["l1"].right, placed["l3"].left)
        self.assertLess(placed["l3"].right, placed["r0"].left)
        self.assertLess(placed["r0"].right, placed["r2"].left)
        self.assertEqual(placed["r2"].right, 592)

    def test_overflow_is_global_prefix_even_across_sides(self):
        requested = [MetricItem("left",40,"left"), MetricItem("wide",900),
                     MetricItem("later_left",0,"left")]
        plan = plan_top_bar(PixelRect(0,0,300,100),items=requested)
        self.assertEqual(tuple(item.id for item in plan.items), ("left",))
        self.assertEqual(plan.overflow_ids, ("wide","later_left"))
        self.assertEqual(plan.overflow_hit.right, 292)
        self.assertEqual(plan.items[0].rect.left, plan.menu_hit.right+12)

    def test_mixed_groups_scaled_spacing_negative_origin_and_narrow_sweep(self):
        requested = [MetricItem(f"item_{i}",31.7,"left" if i%2 else "right") for i in range(64)]
        for dpi in (120,144,168,192):
            for gap in (4,12,24):
                previous = 0
                for width in range(250,1900,83):
                    plan = plan_top_bar(PixelRect(-2003,-177,-2003+width,1000),dpi=dpi,items=requested,gap_dip=gap)
                    self.assertGreaterEqual(len(plan.items),previous)
                    previous = len(plan.items)
                    self.assertEqual(tuple(item.id for item in plan.items),tuple(item.id for item in requested[:previous]))
                    self.assertEqual(plan.overflow_ids,tuple(item.id for item in requested[previous:]))
                    regions = sorted([plan.menu_hit,*(item.rect for item in plan.items),*([plan.overflow_hit] if plan.overflow_hit else [])],key=lambda rect:rect.left)
                    for first,second in zip(regions,regions[1:]):
                        self.assertGreaterEqual(second.left-first.right,ceil(gap*dpi/96))
                    if plan.overflow_hit:
                        self.assertEqual(plan.overflow_hit.right,plan.bounds.right-ceil(8*dpi/96))

    def test_invalid_placement_rejected(self):
        with self.assertRaisesRegex(LayoutError,"placement"):
            plan_top_bar(PixelRect(0,0,300,200),items=[MetricItem("bad",40,"center")])

    def test_measured_overflow_width_and_nonmonotonic_counts(self):
        requested = metrics(3, 0)
        measured = {1: 1000.0, 2: 0.0, 3: 1000.0}
        plan = plan_top_bar(
            PixelRect(0, 0, 112, 100),
            items=requested,
            padding_dip=0,
            gap_dip=0,
            overflow_widths_dip=measured,
        )
        self.assertEqual(tuple(item.id for item in plan.items), ("metric_0",))
        self.assertEqual(plan.overflow_ids, ("metric_1", "metric_2"))
        self.assertEqual(plan.overflow_hit, PixelRect(80, 0, 112, 32))

    def test_measured_ink_gets_padding_on_both_sides(self):
        plan = plan_top_bar(
            PixelRect(0, 0, 300, 100),
            items=[MetricItem("ink", 50.25)],
            item_padding_dip=6.25,
        )
        self.assertEqual(plan.items[0].rect.width, 63)
        self.assertEqual(plan.items[0].rect.right, 292)
        measured = plan_top_bar(
            PixelRect(0, 0, 140, 100),
            items=metrics(3, 900),
            overflow_widths_dip={3: 50.25},
            item_padding_dip=6.25,
        )
        self.assertEqual(measured.overflow_hit.width, 63)

    def test_negative_monitor_origin_and_local_rounding_at_scaled_dpi(self):
        requested = [MetricItem("a", 40), MetricItem("b", 60), MetricItem("c", 0)]
        plan = plan_top_bar(PixelRect(-1920, -200, 0, 880), dpi=120, items=requested)
        self.assertEqual(plan.bounds, PixelRect(-1920, -200, 0, -160))
        self.assertEqual(plan.menu_hit, PixelRect(-1910, -200, -1870, -160))
        self.assertEqual(tuple(item.rect.width for item in plan.items), (65, 90, 40))
        self.assertEqual(plan.items[0].rect.left, -235)
        self.assertEqual(plan.items[-1].rect.right, -10)

    def test_125_through_200_percent_dpi_and_fractional_measurements(self):
        for dpi in (120, 144, 168, 192):
            with self.subTest(dpi=dpi):
                monitor = PixelRect(-2111, -101, -511, 999)
                plan = plan_top_bar(monitor, dpi=dpi, items=metrics(6, 44.3))
                self.assertEqual(plan.bounds.height, ceil(32 * dpi / 96))
                self.assertEqual(plan.menu_hit.left, monitor.left + ceil(8 * dpi / 96))
                self.assertEqual(plan.items[0].rect.width, ceil(56.3 * dpi / 96))
                self.assertEqual(plan.items[-1].rect.right, monitor.right - ceil(8 * dpi / 96))
                self.assert_valid_regions(plan, monitor)

    def test_translation_changes_only_physical_origins(self):
        requested = metrics(24, 42.3)
        origin = plan_top_bar(PixelRect(0, 0, 1001, 501), dpi=144, items=requested)
        shifted = plan_top_bar(PixelRect(-2003, -177, -1002, 324), dpi=144, items=requested)
        self.assertEqual(origin.overflow_ids, shifted.overflow_ids)
        before = [
            origin.bounds,
            origin.menu_hit,
            *(item.rect for item in origin.items),
            origin.overflow_hit,
        ]
        after = [
            shifted.bounds,
            shifted.menu_hit,
            *(item.rect for item in shifted.items),
            shifted.overflow_hit,
        ]
        for first, second in zip(before, after):
            self.assertEqual(
                second,
                PixelRect(
                    first.left - 2003, first.top - 177, first.right - 2003, first.bottom - 177
                ),
            )

    def test_prefix_length_is_monotonic_and_repeated_plans_do_not_jump(self):
        requested = metrics(24, 31.7)
        previous_count = 0
        for width in range(108, 1600, 13):
            monitor = PixelRect(0, 0, width, 300)
            plan = plan_top_bar(monitor, items=requested)
            self.assertEqual(plan, plan_top_bar(monitor, items=requested))
            self.assertGreaterEqual(len(plan.items), previous_count)
            self.assertEqual(
                tuple(item.id for item in plan.items),
                tuple(i.id for i in requested[: len(plan.items)]),
            )
            previous_count = len(plan.items)

    def test_inputs_are_not_modified_and_all_output_records_are_frozen(self):
        requested = metrics(6)
        measured = {count: 25.5 + count for count in range(1, 7)}
        saved = copy.deepcopy((requested, measured))
        plan = plan_top_bar(
            PixelRect(0, 0, 300, 100), items=requested, overflow_widths_dip=measured
        )
        self.assertEqual((requested, measured), saved)
        for value, attribute, replacement in (
            (plan, "dpi", 120),
            (plan.bounds, "left", 0),
            (plan.items[0], "id", "changed"),
            (requested[0], "measured_width_dip", 1),
        ):
            with self.subTest(attribute=attribute), self.assertRaises(FrozenInstanceError):
                setattr(value, attribute, replacement)

    def test_menu_and_required_overflow_must_fit_without_clipping(self):
        with self.assertRaisesRegex(LayoutError, "menu and outer padding"):
            plan_top_bar(PixelRect(0, 0, 47, 100))
        with self.assertRaisesRegex(LayoutError, "required overflow"):
            plan_top_bar(PixelRect(0, 0, 107, 100), items=metrics(6))
        plan = plan_top_bar(PixelRect(0, 0, 108, 100), items=metrics(6))
        self.assertEqual(plan.items, ())
        self.assertEqual(plan.overflow_hit, PixelRect(52, 0, 100, 32))
        self.assertEqual(len(plan.overflow_ids), 6)

    def test_requested_single_row_height_must_fit_the_monitor(self):
        with self.assertRaisesRegex(LayoutError, "height does not fit"):
            plan_top_bar(PixelRect(0, 0, 1920, 63), dpi=192)
        for height in (16, 28, 32, 40, 128):
            with self.subTest(height=height):
                plan = plan_top_bar(PixelRect(0, 0, 1920, 1080), height_dip=height)
                self.assertEqual(plan.bounds.height, height)
                self.assertGreaterEqual(plan.menu_hit.width, height)
        for height in (0, 15, 129, -1, float("nan"), True, "32"):
            with self.subTest(height=height), self.assertRaises(LayoutError):
                plan_top_bar(PixelRect(0, 0, 1920, 1080), height_dip=height)

    def test_valid_dpi_extremes_and_invalid_dpi_types_or_ranges(self):
        monitor = PixelRect(0, 0, 1920, 1080)
        for dpi in (48, 96, 768):
            self.assertEqual(plan_top_bar(monitor, dpi=dpi).bounds.height, ceil(32 * dpi / 96))
        for dpi in (47, 769, True, 96.0, "96", None):
            with self.subTest(dpi=dpi), self.assertRaises(LayoutError):
                plan_top_bar(monitor, dpi=dpi)

    def test_rectangle_requires_signed_int32_coordinates_and_c_int_extents(self):
        for coordinates in (
            (True, 0, 1, 1),
            (0.0, 0, 1, 1),
            ("0", 0, 1, 1),
            (-(2**31) - 1, 0, 0, 1),
            (0, 0, 2**31, 1),
            (-(2**31), 0, 0, 1),
            (0, -(2**31), 1, 0),
            (1, 0, 0, 1),
            (0, 1, 1, 0),
        ):
            with self.subTest(coordinates=coordinates), self.assertRaises(LayoutError):
                PixelRect(*coordinates)
        edge = PixelRect(-(2**31), -(2**31), -1, -1)
        self.assertEqual(edge.width, 2**31 - 1)
        self.assertEqual(edge.height, 2**31 - 1)
        self.assert_valid_regions(plan_top_bar(edge), edge)
        for monitor in (None, (0, 0, 1920, 1080), PixelRect(0, 0, 0, 100), PixelRect(0, 0, 100, 0)):
            with self.subTest(monitor=monitor), self.assertRaises(LayoutError):
                plan_top_bar(monitor)

    def test_item_count_identity_and_container_types_are_validated(self):
        for requested in (
            metrics(65),
            [MetricItem("same", 1), MetricItem("same", 2)],
            [MetricItem("", 1)],
            [MetricItem("  ", 1)],
            [MetricItem(1, 1)],
            [object()],
            "metric",
            {"metric": 30},
            iter(metrics(2)),
            None,
        ):
            with self.subTest(requested=requested), self.assertRaises(LayoutError):
                plan_top_bar(PixelRect(0, 0, 1920, 1080), items=requested)

    def test_width_inputs_are_typed_finite_and_nonnegative(self):
        monitor = PixelRect(0, 0, 1920, 1080)
        invalid = (-1, float("inf"), float("-inf"), float("nan"), True, "1", None, 10**1000)
        for value in invalid:
            with self.subTest(metric_width=value), self.assertRaises(LayoutError):
                plan_top_bar(monitor, items=[MetricItem("test", value)])
            with self.subTest(overflow_width=value), self.assertRaises(LayoutError):
                plan_top_bar(monitor, overflow_widths_dip={1: value})
            for parameter in ("padding_dip", "gap_dip", "menu_width_dip", "item_padding_dip"):
                with self.subTest(parameter=parameter, value=value), self.assertRaises(LayoutError):
                    plan_top_bar(monitor, **{parameter: value})
        for parameter in ("padding_dip", "gap_dip", "menu_width_dip", "item_padding_dip"):
            with self.subTest(parameter=parameter), self.assertRaises(LayoutError):
                plan_top_bar(monitor, **{parameter: 1e308})
        with self.assertRaises(LayoutError):
            plan_top_bar(monitor, menu_width_dip=0)

    def test_unused_overflow_mapping_is_validated_and_only_counts_1_to_64_are_accepted(self):
        for measured in ({0: 1}, {65: 1}, {True: 1}, {1.5: 1}, {"1": 1}, [], 1):
            with self.subTest(measured=measured), self.assertRaises(LayoutError):
                plan_top_bar(PixelRect(0, 0, 1920, 1080), overflow_widths_dip=measured)


if __name__ == "__main__":
    unittest.main()
