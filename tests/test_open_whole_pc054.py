"""Pure approval, notice and manual lifecycle controls for the whole-PC reader."""
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch
import zipfile

import open_reference_models054 as common
import open_whole_pc054 as whole


class OpenWholePc054Tests(unittest.TestCase):
    def test_cold_reader_has_no_model_IO_or_native_import(self):
        code = compile(Path(whole.__file__).read_text('utf-8'), whole.__file__, 'exec')
        module = ModuleType('_cold_whole_pc054')
        before = set(sys.modules)
        with patch.object(Path, 'open', side_effect=AssertionError('No model I/O')), \
                patch.object(zipfile, 'ZipFile', side_effect=AssertionError('No scanning')):
            exec(code, module.__dict__)
        self.assertTrue(callable(module.from_package))
        self.assertFalse(any(n.startswith(('PySide6', 'stats_config', 'profile_paths', 'sensors'))
                             for n in set(sys.modules) - before))

    def test_self_declared_MIT_manifest_does_not_approve_arbitrary_geometry(self):
        package = Mock()
        package.read.return_value = b'{"source_license":"MIT","model_id":"invented"}'
        with self.assertRaisesRegex(common.ModelError, '尚未纳入'):
            whole.from_package(package)
        package.verify.assert_not_called()

    def test_exact_decoder_notice_hash_is_checked_even_if_file_exists(self):
        package = Mock()
        target = whole.FILES[-1]
        self.assertEqual(target[0], 'LICENSE-meshoptimizer.md')
        # Isolate the notice boundary: a byte-different notice must fail even
        # if the package has already returned a file for the expected path.
        with patch.object(whole, 'FILES', (target,)):
            package.verify.return_value = b'X' * target[1]
            with self.assertRaisesRegex(common.ModelError, '校验不匹配'):
                whole.verify_sources(package)
            package.verify.assert_called_once_with(*target)

    def test_public_manual_dispatch_closes_package_on_success_and_failure(self):
        package = Mock()
        package.exists.side_effect = lambda name: name == whole.MANIFEST_FILE
        sentinel = object()
        with patch.object(common, '_Package', return_value=package), \
                patch.object(whole, 'from_package', return_value=sentinel) as reader:
            self.assertIs(common.load_reference('manual-whole-PC.zip'), sentinel)
            reader.assert_called_once_with(package)
        package.close.assert_called_once_with()
        package.close.reset_mock()
        with patch.object(common, '_Package', return_value=package), \
                patch.object(whole, 'from_package', side_effect=common.ModelError('declined')):
            with self.assertRaisesRegex(common.ModelError, 'declined'):
                common.load_reference('manual-whole-PC.zip')
        package.close.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
