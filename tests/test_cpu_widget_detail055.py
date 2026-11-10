"""CPU SKU engraving and real parallel lid finish, using software QtSvg only."""
import json
import math
import unittest

from PySide6.QtSvg import QSvgRenderer
from cpu_catalog import MODELS
from cpu_package_runtime import get_package
from tests import test_cpu_model_art041 as art


def inside(point, polygon):
    x, y = point
    result = False
    previous = polygon[-1]
    for current in polygon:
        if (current[1] > y) != (previous[1] > y):
            crossing = (previous[0] - current[0]) * (y - current[1]) / (previous[1] - current[1]) + current[0]
            if x < crossing:
                result = not result
        previous = current
    return result


class CpuWidgetDetail055Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        art.CpuModelArt041Tests.setUpClass.__func__(cls)

    setUp = art.CpuModelArt041Tests.setUp
    tearDown = art.CpuModelArt041Tests.tearDown
    call = art.CpuModelArt041Tests.call
    drawing = art.CpuModelArt041Tests.drawing

    def test_supplied_cpu_series_and_exact_sku_are_visible_without_number_guessing(self):
        cases = (
            ('intel-13700kf', 'INTEL', 'CORE I7', 'I7-13700KF'),
            ('intel-ultra-285k', 'INTEL', 'CORE ULTRA 9', '285K'),
            ('intel-g4560', 'INTEL', 'PENTIUM', 'G4560'),
            ('intel-g5905', 'INTEL', 'CELERON', 'G5905'),
            ('amd-9950x', 'AMD', 'RYZEN 9', '9950X'),
            ('amd-7800x3d', 'AMD', 'RYZEN 7', '7800X3D'),
            ('amd-threadripper-pro-9995wx', 'AMD', 'THREADRIPPER PRO', '9995WX'),
        )
        index = {row['id']: row for row in MODELS}
        for identity, vendor, family, sku in cases:
            for style in ('miniature', 'cartoon', 'notebook_color', 'notebook_line', 'sticker', 'papercut'):
                with self.subTest(identity=identity, style=style):
                    _source, tree = self.drawing(index[identity], style)
                    texts = [node.text for node in tree.findall('.//{' + art.SVG + '}text')]
                    self.assertEqual(texts, [vendor, family, sku])
        for label in ('13700KF', 'AMD 9950X', 'INTEL 13700KF', '<script>', '', None):
            self.assertEqual(self.call('family', label), '')

    def test_parallel_finish_is_inside_all_seven_lids_including_am5_concave_notches(self):
        examples = {row['cpu_package']['id']: row for row in MODELS}
        for identity, row in examples.items():
            with self.subTest(package=identity):
                profile = json.loads(self.call('profile', identity))
                size = profile['reference_size']
                scale = 18 / max(size)
                polygon = [(12 + (x - .5) * size[0] * scale, 12 + (y - .5) * size[1] * scale)
                           for x, y in profile['lid']]
                inset = json.loads(self.call('insets', [row['cpu_package'], .14]))
                self.assertEqual(len(inset), len(polygon))
                for i, point in enumerate(inset):
                    following = inset[(i + 1) % len(inset)]
                    start, end = polygon[i], polygon[(i + 1) % len(polygon)]
                    dx, dy = end[0] - start[0], end[1] - start[1]
                    length = math.hypot(dx, dy)
                    distance = abs(dx * (point[1] - start[1]) - dy * (point[0] - start[0])) / length
                    self.assertAlmostEqual(distance, .14, places=8)
                    self.assertAlmostEqual(dx * (following[1] - point[1]) - dy * (following[0] - point[0]), 0, places=8)
                    for amount in (0, .25, .5, .75, 1):
                        sample = tuple(point[k] + (following[k] - point[k]) * amount for k in range(2))
                        self.assertTrue(inside(sample, polygon), (identity, i, sample))

    def test_invalid_bevel_inputs_do_not_fabricate_a_replacement_cpu_shape(self):
        row = MODELS[0]['cpu_package']
        for amount in (None, 0, -.1, .251, float('nan'), float('inf')):
            self.assertEqual(json.loads(self.call('insets', [row, amount])), [])
        for descriptor in (None, {}, {'id': 'not-a-package'}):
            self.assertEqual(json.loads(self.call('insets', [descriptor, .14])), [])

    def test_all_cpu_model_text_bounds_fit_the_lid_in_all_six_styles(self):
        for row in MODELS:
            profile = json.loads(self.call('profile', row['cpu_package']['id']))
            size = profile['reference_size']
            scale = 18 / max(size)
            polygon = [(12 + (x - .5) * size[0] * scale, 12 + (y - .5) * size[1] * scale)
                       for x, y in profile['lid']]
            for style in ('miniature', 'cartoon', 'notebook_color', 'notebook_line', 'sticker', 'papercut'):
                source, _tree = self.drawing(row, style)
                renderer = QSvgRenderer(source.encode())
                self.assertTrue(renderer.isValid())
                for identity in ('cpu-model-vendor', 'cpu-model-family', 'cpu-model-sku'):
                    with self.subTest(cpu=row['id'], style=style, text=identity):
                        # Qt documents bounds in element/parent coordinates;
                        # apply parent transforms for the actual logical box.
                        # https://doc.qt.io/qt-6.10/qsvgrenderer.html#transformForElement
                        rect = renderer.transformForElement(identity).mapRect(renderer.boundsOnElement(identity))
                        self.assertGreater(rect.width(), 0)
                        self.assertGreater(rect.height(), 0)
                        for point in ((rect.left(), rect.top()), (rect.right(), rect.top()),
                                      (rect.left(), rect.bottom()), (rect.right(), rect.bottom())):
                            self.assertTrue(inside(point, polygon), (row['id'], identity, point))

    def test_base_cpu_families_keep_existing_bar_sku_tokens(self):
        expected = (
            ('intel-13700kf', 'CORE I7', '13700KF'),
            ('amd-9950x', 'RYZEN 9', '9950X'),
            ('amd-7800x3d', 'RYZEN 7', '7800X3D'),
        )
        for identity, family, token in expected:
            package = get_package(identity)
            self.assertEqual(package['label_ascii'].split()[-1], token)
            self.assertEqual(self.call('family', package['label_ascii']), family)

    def test_labels_have_actual_raster_ink_not_only_nonempty_font_metrics(self):
        examples = {row['cpu_package']['id']: row for row in MODELS}
        for row in examples.values():
            for style in ('miniature', 'cartoon', 'notebook_color', 'notebook_line', 'sticker', 'papercut'):
                source, _tree = self.drawing(row, style)
                start = source.index('<g class="cpu-model-engraving-reference"')
                end = source.index('</g>', start) + len('</g>')
                labels = '<svg xmlns="' + art.SVG + '" viewBox="0 0 24 24">' + source[start:end] + '</svg>'
                renderer = QSvgRenderer(labels.encode())
                image = art.CpuModelArt041Tests.raster(labels, 240)
                for identity in ('cpu-model-vendor', 'cpu-model-family', 'cpu-model-sku'):
                    with self.subTest(cpu=row['id'], style=style, text=identity):
                        box = renderer.transformForElement(identity).mapRect(renderer.boundsOnElement(identity))
                        left, right = max(0, math.floor(box.left() * 10)), min(240, math.ceil(box.right() * 10))
                        top, bottom = max(0, math.floor(box.top() * 10)), min(240, math.ceil(box.bottom() * 10))
                        pixels = sum(image.pixelColor(x, y).alpha() > 32
                                     for y in range(top, bottom) for x in range(left, right))
                        self.assertGreater(pixels, 8, (row['id'], style, identity, box))

    def test_expanded_seed_labels_preserve_the_existing_small_bar_artwork(self):
        for identity, old_label in (('intel-13700kf', 'INTEL 13700KF'),
                                    ('amd-9950x', 'AMD 9950X'),
                                    ('amd-7800x3d', 'AMD 7800X3D')):
            package = get_package(identity)
            for style in ('miniature', 'cartoon', 'notebook_color', 'notebook_line', 'sticker', 'papercut'):
                state = dict(cpu_package=package, icon_set=style, ink='#425564')
                old = dict(state, cpu_package=dict(package, label_ascii=old_label))
                self.assertEqual(self.call('old', state), self.call('old', old))


if __name__ == '__main__':
    unittest.main()
