"""Prepared pure controls for the production CPU/memory gallery API.

No user pack directory, hardware, SVG, profile or scene is opened. The one
optional CPU below is a synthetic installed-store record, not a retail model.
"""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import processor_memory_gallery053 as gallery
import hardware_appearance as hardware
import memory_appearance as memory
import cpu_package_runtime as cpu_runtime
import hardware_packs

ROOT = Path(__file__).resolve().parents[1]


class TestStore:
    def __init__(self):
        package = cpu_runtime.get_package('amd-9950x')
        package.update(model_id='test-installed-am5', label_ascii='AMD TEST')
        self.model = dict(id='test-installed-am5', label='Synthetic installed CPU',
                          vendor='amd', series='synthetic_am5', aliases=['TEST AM5 CPU'],
                          cpu_package=package, sources=deepcopy(package['source_urls']))
        self.summary = dict(id=self.model['id'], label=self.model['label'], vendor='amd',
                            series='synthetic_am5', aliases=['TEST AM5 CPU'], pack_id='test-pack')
        self.payload_reads = []

    def choices(self, kind='cpu'):
        assert kind == 'cpu'
        return [deepcopy(self.summary)]

    def get_model(self, kind, identity, *, retain=True):
        self.payload_reads.append((kind, identity, retain))
        assert (kind, identity, retain) == ('cpu', 'test-installed-am5', False)
        return deepcopy(self.model)

    def get_cpu(self, identity):
        raise AssertionError('Exact gallery selection must not use cached alias matching')


class ProcessorMemoryGallery053Tests(unittest.TestCase):
    def setUp(self):
        self.store = TestStore()
        self.store_patch = patch.object(hardware_packs, 'runtime_store', return_value=self.store)
        self.store_patch.start()

    def tearDown(self):
        self.store_patch.stop()

    def test_choices_are_detached_metadata_only_base_plus_actually_installed(self):
        with patch.object(hardware, 'appearance_for', side_effect=AssertionError('No eager appearance')), \
                patch.object(memory, 'appearance_for_memory', side_effect=AssertionError('No eager memory')):
            cpus, modules = gallery.choices('cpu'), gallery.choices('memory')
        self.assertEqual([r['id'] for r in cpus],
                         ['intel-13700kf', 'amd-9950x', 'amd-7800x3d', 'test-installed-am5'])
        self.assertEqual([r['id'] for r in modules], [r['id'] for r in memory.CATALOG])
        self.assertEqual(len(modules), 28)
        self.assertEqual(self.store.payload_reads, [])
        self.assertTrue(all(set(r) == {'id', 'label', 'brand', 'fidelity'} for r in cpus + modules))
        self.assertEqual(gallery.choices('gpu'), [])
        original = deepcopy(cpus)
        cpus[0]['label'] = 'changed'; cpus.pop()
        self.assertEqual(gallery.choices('cpu'), original)

    def test_three_bundled_cpu_references_keep_existing_packages_and_source(self):
        rows = [r for r in hardware.CATALOG if r[1] == 'cpu']
        self.assertEqual(len(rows), 3)
        for row in rows:
            result = gallery.reference('cpu', row[0])
            self.assertEqual(result['appearance'], hardware.appearance_for('cpu', row[-1][0]))
            self.assertEqual((result['id'], result['source_url']), (row[0], row[8]))
            self.assertEqual(result['appearance']['cpu_package']['model_id'], row[0])
            self.assertTrue(result['reference_only'])
            self.assertFalse(result['telemetry_bound'])
            self.assertFalse(result['installed_model_verified'])
            self.assertFalse(result['mechanical_fit_verified'])
        self.assertEqual(self.store.payload_reads, [])

    def test_one_installed_exact_cpu_does_not_match_alias_or_retain_payload(self):
        with patch.object(cpu_runtime, 'match_model', side_effect=AssertionError('No identity inference')):
            result = gallery.reference('cpu', 'test-installed-am5')
        self.assertEqual(self.store.payload_reads, [('cpu', 'test-installed-am5', False)])
        self.assertEqual((result['id'], result['appearance']['id'], result['appearance']['confidence']),
                         ('test-installed-am5', 'test-installed-am5', 'model'))
        self.assertEqual(result['appearance']['cpu_package'], self.store.model['cpu_package'])
        self.assertEqual(result['appearance']['style'], 'am5')
        pristine = deepcopy(result)
        result['appearance']['cpu_package']['label_ascii'] = 'CHANGED'
        self.assertEqual(gallery.reference('cpu', 'test-installed-am5'), pristine)
        self.store.payload_reads.clear()
        self.assertEqual(gallery.reference('cpu', 'intel-14900k'), {})
        self.assertEqual(self.store.payload_reads, [])

    def test_all_memory_skus_keep_exact_identity_form_and_existing_evidence(self):
        selected = []
        for row in memory.CATALOG:
            result = gallery.reference('memory', row['id'])
            self.assertTrue(result, row['id'])
            self.assertEqual(result['appearance'], memory.appearance_for_memory(model=row['aliases'][0]))
            self.assertEqual((result['id'], result['label'], result['source_url']),
                             (row['id'], row['label'], row['source_url']))
            self.assertEqual((result['appearance']['id'], result['appearance']['confidence'],
                              result['appearance']['form_factor']),
                             (row['id'], 'model', row['form_factor']))
            selected.append(result['id'])
        self.assertEqual(len(set(selected)), 28)
        # The unresolved Crucial presentation stays neutral; no RGB or chip
        # layout is borrowed from a visually similar known module.
        unresolved = gallery.reference('memory', 'crucial-cb16gu4800')
        self.assertEqual(unresolved['appearance']['presentation'], 'neutral')
        pristine = deepcopy(unresolved)
        unresolved['appearance']['features'].append('invented')
        self.assertEqual(gallery.reference('memory', 'crucial-cb16gu4800'), pristine)
        self.assertEqual(self.store.payload_reads, [])

    def test_invalid_or_mismatched_identity_is_unavailable_without_alias_fallback(self):
        for kind, identity in [('gpu', 'intel-13700kf'), ('memory', 'intel-13700kf'),
                               ('cpu', 'gskill-f4-3200c16d-16gtzr'),
                               ('cpu', None), ('cpu', True), ('cpu', []), ('cpu', ''),
                               ('cpu', '../model'), ('cpu', 'x' * 65), ('cpu', 'AMD-9950X')]:
            self.assertEqual(gallery.reference(kind, identity), {})
        for bad in ({}, dict(id='other', kind='memory', confidence='model'),
                    dict(id='crucial-cb16gu4800', kind='memory', confidence='series')):
            with patch.object(memory, 'appearance_for_memory', return_value=bad):
                self.assertEqual(gallery.reference('memory', 'crucial-cb16gu4800'), {})
        for field, value in [('id', 'other'), ('label', 'changed'), ('vendor', 'unknown')]:
            old = self.store.model[field]
            self.store.model[field] = value
            self.assertEqual(gallery.reference('cpu', 'test-installed-am5'), {})
            self.store.model[field] = old

    def test_real_controller_slot_is_inactive_gated_and_does_not_use_art_jobs(self):
        tree = ast.parse((ROOT / 'assembly_tools.py').read_text(encoding='utf8'))
        owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AssemblyTools')
        node = deepcopy(next(n for n in owner.body if isinstance(n, ast.FunctionDef)
                             and n.name == 'accessoryComponentReference'))
        node.decorator_list = []
        scope = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                     'actual-production-gallery-slot', 'exec'), scope)
        target = SimpleNamespace(_accessory_gallery_active=False)
        with patch.object(gallery, 'reference', wraps=gallery.reference) as resolver:
            self.assertEqual(scope[node.name](target, 'cpu', 'amd-9950x'), {})
            resolver.assert_not_called()
            target._accessory_gallery_active = True
            self.assertEqual(scope[node.name](target, 'cpu', 'amd-9950x')['id'], 'amd-9950x')
            resolver.assert_called_once_with('cpu', 'amd-9950x')
        module = ast.parse((ROOT / 'processor_memory_gallery053.py').read_text(encoding='utf8'))
        top_imports = [n for n in module.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        self.assertEqual([(n.module if isinstance(n, ast.ImportFrom) else n.names[0].name)
                          for n in top_imports], ['copy', 're'])
        import accessory_art
        for kind in ('cpu', 'memory'):
            self.assertNotIn(kind, accessory_art._ASYNC_KINDS)
            self.assertIsNone(accessory_art.model_key(kind, 'amd-9950x', 'miniature'))


if __name__ == '__main__':
    unittest.main()
