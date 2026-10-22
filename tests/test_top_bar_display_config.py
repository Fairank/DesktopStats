"""Pure top-bar display schema validation and legacy normalization."""
import copy
import unittest

from top_bar_config import default_top_bar, validate_top_bar


class TopBarDisplayConfigTests(unittest.TestCase):
    def test_legacy_spacing_and_display_defaults(self):
        old = dict(enabled=True, monitor_mode="primary", screens=[], height=32,
                   items=[dict(id="b_old", metric="gpu_power", prefs={"gpu_target":"1"})])
        before = copy.deepcopy(old)
        result = validate_top_bar(old)
        self.assertEqual(result["spacing"], 12)
        self.assertEqual(result["items"][0]["prefs"]["placement"], "right")
        self.assertEqual(result["items"][0]["prefs"]["style"], "label_value")
        self.assertEqual(result["items"][0]["prefs"]["gpu_target"], "1")
        self.assertEqual(old, before)
        self.assertEqual(validate_top_bar(result), result)
        self.assertFalse(default_top_bar()["enabled"])

    def test_spacing_range_fraction_and_invalid_values(self):
        for spacing in (4, 12, 24, 6.5):
            value = dict(default_top_bar(), spacing=spacing)
            self.assertEqual(validate_top_bar(value)["spacing"], spacing)
        for spacing in (3.99, 24.01, 0, -1, True, None, "12", float("nan"), float("inf"), 10**5000):
            with self.subTest(spacing_type=type(spacing)), self.assertRaises(ValueError):
                validate_top_bar(dict(default_top_bar(), spacing=spacing))

    def test_styles_placements_and_device_options_survive_normalization(self):
        for style in ("label_value", "value", "icon_value", "trend_value"):
            for placement in ("left", "right"):
                value = default_top_bar()
                value["items"][0]["prefs"].update(style=style, placement=placement, temperature_unit="F", precision="2")
                prefs = validate_top_bar(value)["items"][0]["prefs"]
                self.assertEqual((prefs["style"],prefs["placement"],prefs["temperature_unit"],prefs["precision"]),
                                 (style,placement,"F","2"))

    def test_unknown_styles_and_placements_are_not_silently_repaired(self):
        for field, invalid in (("style","chart"), ("style",None), ("style",True),
                               ("placement","center"), ("placement",[])):
            value = default_top_bar()
            value["items"][0]["prefs"][field] = invalid
            with self.assertRaises(ValueError):
                validate_top_bar(value)

    def test_sixty_four_order_and_configured_sides_are_preserved(self):
        value = default_top_bar()
        value["items"] = [dict(id=f"b_{i}", metric="cpu_usage", prefs=dict(placement="left" if i%2 else "right",style="value")) for i in range(64)]
        result = validate_top_bar(value)
        self.assertEqual([item["id"] for item in result["items"]], [item["id"] for item in value["items"]])
        self.assertEqual([item["prefs"]["placement"] for item in result["items"]], [item["prefs"]["placement"] for item in value["items"]])
        value["items"].append(dict(id="b_overflow", metric="cpu_usage", prefs={}))
        with self.assertRaises(ValueError):
            validate_top_bar(value)


if __name__ == "__main__":
    unittest.main()
