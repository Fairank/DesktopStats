"""Independent radiator cards: bounded real geometry; no Qt, Scene or device I/O."""
import ast
from collections import defaultdict
from copy import deepcopy
import hashlib
import importlib.util
import importlib.machinery
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

import radiator_svg053 as radiator
import liquid_svg046 as projected
from accessory_cancel047 import ArtCancelled
from assembly_geometry import Mesh, box
from liquid_cooling_catalog044 import get_radiator

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SIX = ('miniature', 'cartoon', 'notebook_color', 'notebook_line', 'sticker', 'papercut')
OLD_SHA = '3e47b0996def90591880942c2c18ec332043252257739cba69b8b8eec6516a6e'


def production_value_sink():
    """Extract actual put/finish/transform without importing the pipeline."""
    tree = ast.parse((ROOT/'assembly_cooling.py').read_text(encoding='utf-8-sig'))
    transform = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_transform')
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == '_Builder')
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in ('put', 'finish')]
    if len(methods) != 2:
        raise AssertionError('Production value-builder contract changed')
    init = ast.parse('def __init__(self):\n self.static=defaultdict(list)\n self.rotors=[]\n').body[0]
    detached = ast.ClassDef(name='ValueSink', bases=[], keywords=[], body=[init, *methods], decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[transform, detached], type_ignores=[]))
    namespace = dict(defaultdict=defaultdict, _add=lambda a, b: tuple(x+y for x, y in zip(a, b)))
    exec(compile(module, '<actual-value-builder-methods>', 'exec'), namespace)
    result = namespace['ValueSink'](); result.level = 'eco'
    return result


class RadiatorSvg053Tests(unittest.TestCase):
    def test_one_actual_radiator_six_styles_static_geometry_and_safe_paths(self):
        row = get_radiator('corsair-xr5-240'); before = deepcopy(row); geometry = None
        for style in SIX:
            with self.subTest(style=style):
                art = radiator.art_from_reference(row, style)
                self.assertTrue(art, 'Legal geometry must not silently become an empty card')
                detail = art['art_details']; digest = detail['geometry_digest']
                if geometry is None: geometry = digest
                self.assertEqual(digest, geometry)
                self.assertEqual(art['kind'], 'radiator'); self.assertNotIn('form', detail)
                self.assertEqual(detail['shell_family'], row['shell_family'])
                self.assertEqual(detail['dimensions_mm'], row['dimensions_mm'])
                self.assertEqual(detail['radiator']['modelled_ports'], len(detail['ports']))
                self.assertEqual(art['rotors'], []); self.assertEqual(art['original_face'], 'none')
                self.assertFalse(detail['fan_count_is_installed']); self.assertFalse(detail['telemetry_bound'])
                self.assertFalse(detail['coordinates_verified']); self.assertEqual(detail['new_fans'], 0)
                self.assertLessEqual(detail['triangle_count'], 2800)
                self.assertLessEqual(detail['occlusion_work'], projected.MAX_CLIP_WORK)
                tree = ET.fromstring(art['svg'])
                self.assertEqual(tree.attrib['viewBox'], '0 0 120 100')
                for node in tree.iter():
                    self.assertIn(node.tag.rsplit('}', 1)[-1], ('svg', 'path'))
                    self.assertFalse(any('href' in k or k.startswith('on') for k in node.attrib))
                json.dumps(art, allow_nan=False)
        self.assertEqual(row, before)

    def test_old_loop_actual_cpu_block_full_svg_and_metadata_byte_bridge(self):
        # An authoring fixture is resolved once here, outside application/runtime
        # code. Both projection versions consume the same validated real row.
        from liquid_block_pump_expansion046 import get_record
        from liquid_pack_schema046 import validate_reference
        row = validate_reference(get_record('alphacool-core1-black'))
        old_path = HERE/'fixtures/liquid_svg046_pre053.py.txt'
        self.assertEqual(hashlib.sha256(old_path.read_bytes()).hexdigest(), OLD_SHA)
        loader = importlib.machinery.SourceFileLoader('liquid_svg046_before053', str(old_path))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
        previous = old.art_from_reference(row, 'miniature')
        current = projected.art_from_reference(row, 'miniature')
        self.assertTrue(previous); self.assertTrue(current)
        self.assertEqual(current, previous)
        self.assertEqual(json.dumps(current, ensure_ascii=False), json.dumps(previous, ensure_ascii=False))
        self.assertEqual(old.MAX_TRIANGLES, 2600); self.assertEqual(projected.MAX_TRIANGLES, 2600)

    def test_sink_matches_actual_value_builder_and_nonidentity_transform(self):
        from assembly_radiator044 import build_radiator_detail
        row = get_radiator('corsair-xr5-240'); expected = production_value_sink()
        meta = build_radiator_detail(expected, row['dimensions_mm'], (0., 0., 0.), radiator._IDENTITY,
                                     'radiator:'+row['id'], row)
        meshes, actual = radiator._geometry(row)
        self.assertEqual(meshes, expected.finish()); self.assertEqual(actual, meta)
        self.assertFalse(any(m.rotor for m in meshes))
        basis = ((0., 0., 1.), (0., 1., 0.), (-1., 0., 0.)); center = (7., -3., 11.)
        reference = production_value_sink(); sink = radiator._MeshSink()
        args = ('known-cube', box(2., 4., 6.), '#123456', center, basis, 'cooler', 'radiator:fixture')
        reference.put(*args); sink.put(*args)
        self.assertEqual(sink.finish(), reference.finish())
        p = args[1][:3]
        self.assertEqual(sink.finish()[0].vertices[:3], (-p[2]+7., p[1]-3., p[0]+11.))

    def test_optional_resolution_is_one_unretained_model_not_geometry_or_all_models(self):
        optional = get_radiator('corsair-xr5-240'); optional['id'] = 'test-radiator'
        getter = Mock(return_value=dict(reference=deepcopy(optional)))
        fake = SimpleNamespace(runtime_store=lambda: SimpleNamespace(get_model=getter))
        with patch.dict(sys.modules, hardware_packs=fake), \
             patch.object(radiator, '_geometry', side_effect=AssertionError('Prepare must be geometry free')):
            self.assertEqual(radiator.reference('test-radiator'), optional)
            getter.assert_called_once_with('radiator', 'test-radiator', retain=False)
            getter.reset_mock()
            self.assertEqual(radiator.reference('corsair-xr5-240')['id'], 'corsair-xr5-240')
            getter.assert_not_called()
            getter.return_value = None
            self.assertEqual(radiator.reference('missing-model'), {})
            getter.return_value = dict(reference=optional)
            self.assertEqual(radiator.reference('wrong-identity'), {})

    def test_invalid_input_rejected_before_lookup_or_mesh_work(self):
        with patch.object(radiator, 'reference', side_effect=AssertionError('Invalid lookup')):
            for identity, style in (([], 'miniature'), ('../bad', 'miniature'), ('x'*65, 'miniature'),
                                    ('test-radiator', []), ('test-radiator', 'bad-style')):
                self.assertEqual(radiator.art(identity, style), {})
        row = get_radiator('corsair-xr5-240')
        with patch.object(radiator, '_geometry', side_effect=AssertionError('Invalid geometry')):
            self.assertEqual(radiator.art_from_reference(dict(row, category='cooler')), {})
            self.assertEqual(radiator.art_from_reference(row, []), {})
        with patch.object(radiator, '_geometry', side_effect=ValueError('Bounded builder rejected')):
            self.assertEqual(radiator.art_from_reference(row), {})

    def test_cancel_and_original_loop_cap_reject_without_substitute_geometry(self):
        row = get_radiator('corsair-xr5-240'); stopped = SimpleNamespace(is_set=lambda: True)
        with patch.object(radiator, '_geometry', side_effect=AssertionError('Cancelled before build')):
            with self.assertRaises(ArtCancelled): radiator.art_from_reference(row, cancel=stopped)
        sink = radiator._MeshSink(stopped)
        with self.assertRaises(ArtCancelled):
            sink.put('part', box(1., 1., 1.), '#123456', (0., 0., 0.), radiator._IDENTITY, 'cooler', 'rad')
        oversized = Mesh('over-old-loop-cap', box(1., 1., 1.)*217, (.2, .3, .4, 1.)) #2604tri
        with patch.object(projected, '_Visibility', side_effect=AssertionError('Old cap remains2600')):
            self.assertEqual(projected.project_meshes((oversized,), max_triangles=2600), {})
        self.assertEqual(radiator.MAX_TRIANGLES, 2800)
        with patch.object(projected, '_Visibility', side_effect=AssertionError('Illegal cap')):
            self.assertEqual(projected.project_meshes((oversized,), max_triangles=2801), {})


if __name__ == '__main__':
    unittest.main()
