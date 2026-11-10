"""Unknown and partial card dimensions must not claim a fully known envelope."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class GpuDimensionMetadata055Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse((ROOT / 'assembly_spec.py').read_text('utf-8'))
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        cls.scope = {}
        import math
        cls.scope['math'] = math
        for name in ('number', 'text'):
            module = ast.fix_missing_locations(ast.Module(body=[functions[name]], type_ignores=[]))
            exec(compile(module, 'assembly_spec.py', 'exec'), cls.scope)
        # Execute the actual producer's GPU record expression. Deliberately
        # exclude identity discovery, optional packs, profiles and whole scenes.
        node = next(node for node in functions['build_spec'].body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == 'gpu' for target in node.targets))
        cls.expression = compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                                 'assembly_spec.py', 'exec')

    def produce(self, dimensions):
        scope = dict(self.scope, dimensions=dimensions, appearance={'label': 'Exact test GPU',
            'confidence': 'model', 'selection_source': 'automatic'},
            device={'gpu_name': 'Test chip'}, target='0')
        exec(self.expression, scope)
        return scope['gpu']

    def test_nonempty_unknown_map_and_partial_measurements_stay_unverified(self):
        for dimensions in ({}, {'length': None, 'height': None, 'thickness': None},
                           {'length': 300., 'height': 120.},
                           {'length': 300., 'height': None, 'thickness': 40.}):
            with self.subTest(dimensions=dimensions):
                result = self.produce(dimensions)
                self.assertFalse(result['dimensions_verified'])
                self.assertEqual((result['length_mm'], result['width_mm'], result['thickness_mm']),
                                 (dimensions.get('length'), dimensions.get('height'), dimensions.get('thickness')))

    def test_invalid_or_boolean_axis_does_not_make_a_verified_physical_card(self):
        for axis in ('length', 'height', 'thickness'):
            for value in (True, False, 0, -1, float('nan'), float('inf'), '40'):
                with self.subTest(axis=axis, value=value):
                    dimensions = dict(length=300., height=120., thickness=40.)
                    dimensions[axis] = value
                    result = self.produce(dimensions)
                    self.assertFalse(result['dimensions_verified'])
                    self.assertIsNone(result[{'length': 'length_mm', 'height': 'width_mm',
                                              'thickness': 'thickness_mm'}[axis]])

    def test_complete_catalog_numbers_and_identity_are_preserved(self):
        result = self.produce(dict(length=300., height=120., thickness=40.))
        self.assertTrue(result['dimensions_verified'])
        self.assertEqual((result['length_mm'], result['width_mm'], result['thickness_mm']),
                         (300., 120., 40.))
        self.assertEqual(result['label'], 'Exact test GPU')
        self.assertEqual(result['selection_source'], 'automatic')
        self.assertTrue(result['telemetry_bound'])


if __name__ == '__main__':
    unittest.main()
