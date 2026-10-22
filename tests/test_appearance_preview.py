"""Pure appearance projection boundaries; no configuration/profile or Qt imports."""

import copy
import unittest

from appearance_preview import project_appearance


def saved_settings():
    return dict(
        skin="minimal",
        theme="dark",
        opacity=94,
        glass_transparency=60,
        glass_curvature=50,
        visible=True,
        language="zh",
        font_family="Saved Font",
        layout="grid",
        sampling_interval=1000,
        magnet_enabled=True,
        autostart=False,
        widget_order=["cpu_a", "cpu_b"],
        top_bar=dict(enabled=False, monitor_mode="selected", screens=["saved-screen"], items=[]),
        widgets={
            "cpu_a": dict(
                kind="cpu",
                enabled=True,
                skin="minimal",
                glass_transparency=20,
                glass_curvature=35,
                content=["cpu_usage"],
                width=320,
                height=180,
                screen_target="saved-screen",
                gpu_target="0",
                storage_target="disk-0",
                layer="desktop",
                metric_positions={"cpu_usage": dict(x=0, y=0, width=1, height=1)},
            ),
            "cpu_b": dict(
                kind="cpu",
                enabled=False,
                skin=None,
                glass_transparency=None,
                glass_curvature=None,
                content=["cpu_temp"],
                width=250,
                height=160,
            ),
        },
        unknown=dict(nested=["saved opaque state"]),
    )


class AppearancePreviewTests(unittest.TestCase):
    def setUp(self):
        self.saved = saved_settings()
        self.draft = copy.deepcopy(self.saved)

    def test_only_five_global_appearance_fields_are_projected(self):
        self.draft.update(
            skin="glass",
            theme="light",
            opacity=72,
            glass_transparency=85,
            glass_curvature=80,
            visible=False,
            language="en",
            font_family="Draft Font",
            layout="free",
            sampling_interval=5000,
            magnet_enabled=False,
            autostart=True,
            new_draft_setting="not applied",
        )
        expected = copy.deepcopy(self.saved)
        expected.update(
            skin="glass", theme="light", opacity=72, glass_transparency=85, glass_curvature=80
        )
        self.assertEqual(project_appearance(self.saved, self.draft, True), expected)

    def test_widget_projection_never_applies_content_size_targets_or_enablement(self):
        self.draft["widgets"]["cpu_a"].update(
            skin="glass",
            glass_transparency=75,
            glass_curvature=90,
            kind="gpu",
            enabled=False,
            content=["gpu_power"],
            width=900,
            height=300,
            screen_target="draft-screen",
            gpu_target="1",
            storage_target="draft-disk",
            layer="pinned",
            metric_positions={},
            new_draft_setting="not applied",
            theme="light",
            opacity=10,
        )
        expected = copy.deepcopy(self.saved)
        expected["widgets"]["cpu_a"].update(skin="glass", glass_transparency=75, glass_curvature=90)
        self.assertEqual(project_appearance(self.saved, self.draft, True), expected)

    def test_draft_widget_deletion_addition_and_reordering_preserve_saved_membership(self):
        del self.draft["widgets"]["cpu_a"]
        self.draft["widgets"]["new_cpu"] = dict(
            kind="cpu", enabled=True, skin="glass", glass_transparency=99, glass_curvature=99
        )
        self.draft["widget_order"] = ["new_cpu", "cpu_b"]
        result = project_appearance(self.saved, self.draft, True)
        self.assertEqual(result, self.saved)
        self.assertEqual(list(result["widgets"]), ["cpu_a", "cpu_b"])
        self.assertNotIn("new_cpu", result["widgets"])

    def test_same_kind_widgets_project_by_exact_id_only(self):
        self.draft["widgets"]["cpu_b"]["skin"] = "glass"
        result = project_appearance(self.saved, self.draft, True)
        self.assertEqual(result["widgets"]["cpu_a"], self.saved["widgets"]["cpu_a"])
        self.assertEqual(result["widgets"]["cpu_b"]["skin"], "glass")
        self.assertFalse(result["widgets"]["cpu_b"]["enabled"])

    def test_explicit_none_preserves_global_inheritance_without_normalizing_it(self):
        self.draft.update(skin="glass", glass_transparency=80, glass_curvature=70)
        self.draft["widgets"]["cpu_a"].update(
            skin=None, glass_transparency=None, glass_curvature=None
        )
        result = project_appearance(self.saved, self.draft, True)
        for identifier in ("cpu_a", "cpu_b"):
            for field in ("skin", "glass_transparency", "glass_curvature"):
                self.assertIsNone(result["widgets"][identifier][field])
        self.assertEqual(result["skin"], "glass")
        self.assertEqual(self.saved["widgets"]["cpu_a"]["skin"], "minimal")

    def test_partial_draft_retains_omitted_global_and_widget_fields(self):
        result = project_appearance(
            self.saved, dict(theme="light", widgets={"cpu_a": dict(skin="glass")}), True
        )
        expected = copy.deepcopy(self.saved)
        expected["theme"] = "light"
        expected["widgets"]["cpu_a"]["skin"] = "glass"
        self.assertEqual(result, expected)

    def test_missing_saved_widgets_are_not_created_from_the_draft(self):
        saved = dict(skin="minimal", unknown=["keep"])
        result = project_appearance(saved, self.draft, True)
        self.assertNotIn("widgets", result)
        self.assertEqual(result["unknown"], ["keep"])

    def test_top_bar_and_opaque_settings_never_follow_the_draft(self):
        self.draft["top_bar"] = dict(enabled=True, monitor_mode="all", items=[dict(id="new")])
        self.draft["unknown"]["nested"].append("draft opaque state")
        self.assertEqual(project_appearance(self.saved, self.draft, True), self.saved)

    def test_projection_does_not_mutate_either_input_or_alias_nested_saved_state(self):
        self.draft["skin"] = "glass"
        saved_before, draft_before = copy.deepcopy(self.saved), copy.deepcopy(self.draft)
        result = project_appearance(self.saved, self.draft, True)
        self.assertEqual(self.saved, saved_before)
        self.assertEqual(self.draft, draft_before)
        result["widgets"]["cpu_a"]["content"].append("cpu_temp")
        result["widgets"]["cpu_a"]["metric_positions"]["cpu_usage"]["x"] = 0.5
        result["widget_order"].reverse()
        result["unknown"]["nested"].clear()
        self.assertEqual(self.saved, saved_before)
        self.assertEqual(self.draft, draft_before)

    def test_inactive_returns_an_independent_saved_copy_without_reading_draft(self):
        class UnreadableDraft(dict):
            def get(self, *_args):
                raise AssertionError("Inactive preview must not read the draft")

            def __contains__(self, _field):
                raise AssertionError("Inactive preview must not read the draft")

        result = project_appearance(self.saved, UnreadableDraft(), False)
        self.assertEqual(result, self.saved)
        self.assertIsNot(result, self.saved)
        result["widgets"]["cpu_a"]["content"].clear()
        self.assertEqual(self.saved["widgets"]["cpu_a"]["content"], ["cpu_usage"])

    def test_later_preview_starts_from_saved_not_an_earlier_projection(self):
        self.draft["widgets"]["cpu_a"]["skin"] = "glass"
        first = project_appearance(self.saved, self.draft, True)
        self.assertEqual(first["widgets"]["cpu_a"]["skin"], "glass")
        self.assertEqual(project_appearance(self.saved, self.draft, False), self.saved)
        self.assertEqual(project_appearance(self.saved, {}, True), self.saved)


if __name__ == "__main__":
    unittest.main()
