"""The published inventory matches selectable models without machine data or I/O."""
import sys
import unittest
from unittest.mock import patch

from tools.export_assembly_catalog import build_report


class AssemblyCatalogTests(unittest.TestCase):
    def test_every_selectable_product_is_listed_once_with_explicit_source_and_scope(self):
        with patch('ctypes.WinDLL',side_effect=AssertionError('No devices')),\
                patch('subprocess.Popen',side_effect=AssertionError('No processes')),\
                patch('threading.Thread.start',side_effect=AssertionError('No worker')):
            report=build_report()
            from assembly_parts import choices
            picks=choices()
        self.assertFalse(report['market_exhaustive']);self.assertFalse(report['machine_inventory'])
        self.assertEqual(len(report['styles']),13)
        rows=report['products'];keys=[(row['kind'],row['model_id']) for row in rows]
        self.assertEqual(len(keys),len(set(keys)))
        for group,kind in (('cpus','cpu'),('gpus','gpu'),('memory','memory'),('boards','board'),
                ('coolers','cooler'),('fans','fan'),('psus','psu'),('storage','storage'),('expansion','expansion')):
            self.assertEqual({row['id'] for row in picks[group] if row['id']},
                             {row['model_id'] for row in rows if row['kind']==kind},group)
        self.assertTrue(all(row['source_urls'] for row in rows))
        self.assertTrue(all(row['model_status']=='original_schematic' for row in rows))
        self.assertNotIn('assembly_viewer',sys.modules)
        self.assertNotIn('cpu_temperature',sys.modules)
        self.assertNotIn('PySide6.QtOpenGL',sys.modules)


if __name__=='__main__':unittest.main()
