"""Pure approval, CC BY and source-lineage controls for manual CPU/GPU intake."""
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch
import zipfile

import open_reference_models054 as common
import open_ccby_components054 as components


class OpenCCBYComponents054Tests(unittest.TestCase):
    def test_cold_reader_has_no_IO_native_import_or_source_decode(self):
        code = compile(Path(components.__file__).read_text('utf-8'), components.__file__, 'exec')
        module = ModuleType('_cold_CC_BY054')
        before = set(sys.modules)
        with patch.object(Path, 'open', side_effect=AssertionError('No model I/O')), \
                patch.object(zipfile, 'ZipFile', side_effect=AssertionError('No discovery')):
            exec(code, module.__dict__)
        self.assertTrue(callable(module.from_package))
        self.assertFalse(any(name.startswith(('PySide6', 'stats_config', 'profile_paths', 'sensors'))
                             for name in set(sys.modules) - before))

    def test_self_declared_CC_BY_does_not_approve_arbitrary_meshes(self):
        package = Mock()
        package.read.return_value = b'{"source_license":"CC-BY-4.0","asset":"gpu"}'
        with self.assertRaisesRegex(common.ModelError, '尚未纳入'):
            components.from_package(package)
        package.verify.assert_not_called()

    def test_same_length_CC_BY_notice_with_different_hash_is_rejected(self):
        target = components._NOTICES[0]
        package = Mock()
        package.verify.return_value = b'X' * target[1]
        with patch.object(components, 'FILES', {'cpu': (target,)}):
            with self.assertRaisesRegex(common.ModelError, '校验不匹配'):
                components.verify_files(package, 'cpu')
        package.verify.assert_called_once_with(*target)

    def test_GPU_LOD_lineage_and_no_restriction_or_fit_claim_are_required(self):
        approved = next(row for row in components.APPROVED.values() if row['asset'] == 'gpu')
        doc = dict(format='DesktopStats.open-CCBY-world-PN.054.1', asset='gpu', source_license='CC-BY-4.0',
                   attribution=approved['attribution'], source_urls=[approved['source_url'], components.CC_BY_URL],
                   source_original_sha256=approved['source_sha256'], source_indexed_metadata_sha256=approved['indexed_sha256'],
                   source_parent_metadata_sha256=approved['parent_sha256'], source_lod_indices_sha256=approved['lod_sha256'])
        for key in ('dimensions_verified', 'mechanical_fit_verified', 'telemetry_bound', 'source_quality_accepted',
                    'auto_play', 'watermark_applied', 'NC_override'):
            doc[key] = False
        components.validate_source_identity(doc, approved)
        with self.assertRaisesRegex(common.ModelError, 'LOD'):
            components.validate_source_identity(dict(doc, source_lod_indices_sha256='0' * 64), approved)
        for key in ('NC_override', 'watermark_applied', 'mechanical_fit_verified', 'auto_play'):
            with self.subTest(key=key), self.assertRaisesRegex(common.ModelError, '许可限制'):
                components.validate_source_identity(dict(doc, **{key: True}), approved)

    def test_public_manual_dispatch_closes_package_on_success_and_failure(self):
        package = Mock()
        package.exists.side_effect = lambda name: name == components.MANIFEST_FILE
        sentinel = object()
        with patch.object(common, '_Package', return_value=package), \
                patch.object(components, 'from_package', return_value=sentinel) as reader:
            self.assertIs(common.load_reference('manual-CPU-GPU.zip'), sentinel)
            reader.assert_called_once_with(package)
        package.close.assert_called_once_with()
        package.close.reset_mock()
        with patch.object(common, '_Package', return_value=package), \
                patch.object(components, 'from_package', side_effect=common.ModelError('declined')):
            with self.assertRaisesRegex(common.ModelError, 'declined'):
                common.load_reference('manual-CPU-GPU.zip')
        package.close.assert_called_once_with()

    def test_existing_component_and_fan_directories_keep_casefold_precedence(self):
        # Windows Path.is_file() also sees an older pack's REFERENCE054.json
        # when the new lowercase CC BY reference054.json name is queried.
        for original in ('component053.json', 'models/generic-fan-derived.glb'):
            with self.subTest(original=original):
                files = {'REFERENCE054.json', original}
                package = Mock()
                package.exists.side_effect = lambda name: name.casefold() in {item.casefold() for item in files}
                package.read.return_value = b'original reviewed component document'
                sentinel = object()
                with patch.object(common, '_Package', return_value=package), \
                        patch.object(common, '_component', return_value=sentinel) as component_reader, \
                        patch.object(common, '_fan', return_value=sentinel) as fan_reader, \
                        patch.object(components, 'from_package', side_effect=AssertionError('Wrong reader')):
                    self.assertIs(common.load_reference('old-extracted-package'), sentinel)
                if original == 'component053.json':
                    component_reader.assert_called_once_with(package, package.read.return_value)
                    fan_reader.assert_not_called()
                else:
                    fan_reader.assert_called_once_with(package)
                    component_reader.assert_not_called()
                package.close.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
