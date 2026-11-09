"""Real identity gates, synthetic readings; no renderer or live hardware.

The window adapter executes AssemblyWindow's actual cache method with a fake
viewport. Its counters measure scene submissions/profile requests, not geometry
construction time or native rendering. All fingerprints and spec enrichment are
the production functions.
"""
import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')

from PySide6.QtCore import QCoreApplication, QObject, Signal
from PySide6.QtTest import QSignalSpy

import assembly_spec
import assembly_tools
import assembly_window
import hardware_packs
from stats_config import DEFAULT


# Same synthetic ASUS identity used by test_assembly_tools; never query a host.
FIRMWARE = dict(state='available', system=dict(manufacturer='ASUS'), enclosures=[],
    baseboards=[dict(manufacturer='ASUSTeK COMPUTER INC.',
                    product='ROG STRIX Z790-A GAMING WIFI D4')])
MODULES = [dict(manufacturer='Kingston', part_number='KVR32N22S8/16', form_factor='dimm')]


class Controller(assembly_tools.AssemblyTools):
    dataChanged = Signal()
    draftChanged = Signal()
    languageChanged = Signal()

    def __init__(self):
        # Only the assembly mixin's state is required. Avoid constructing the
        # unrelated workspace/history controller and its diagnostic QTimer.
        QObject.__init__(self)
        self._assembly_page_active = self._assembly_viewer_active = False
        self._assembly_firmware = self._assembly_modules = None
        self._assembly_fingerprint = self._assembly_spec = None
        self._assembly_summary = dict(initialized=False)
        self._draft = copy.deepcopy(DEFAULT)
        self._data = dict(cpu_name='Intel Core i7-13700KF', time=1000.,
            gpus={'0': dict(gpu_name='NVIDIA GeForce RTX 5090', gpu_usage=42)})
        self.initialize_assembly_signals()


class Viewport:
    def __init__(self): self.scenes = []
    def set_scene(self, spec): self.scenes.append(copy.deepcopy(spec))


class Notice:
    def setText(self, value): self.text = value
    def setVisible(self, value): self.visible = value


class ExistingWindow:
    """Use the production cache gate without QWidget, QML or a GL viewport."""
    _apply_scene = assembly_window.AssemblyWindow._apply_scene

    def __init__(self, controller):
        self.controller = controller
        self._closing = False
        self._spec = self._geometry_key = self._profile_key = self._profile_shapes = None
        self.viewport = Viewport()
        self.fit_notice = Notice()
        self.engine = None
        self.readings = []
        self.choice_refreshes = 0
        controller.assemblyChanged.connect(self._controller_changed)
        controller.dataChanged.connect(self.update_readings)

    def _controller_changed(self):
        self._apply_scene(self.controller.assembly_specification())

    def _refresh_part_choices(self): self.choice_refreshes += 1
    def update_readings(self): self.readings.append(copy.deepcopy(self.controller._data))


class MemoryBuildEfficiency052Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        for name in ('ctypes.WinDLL', 'socket.socket', 'subprocess.Popen', 'threading.Thread.start'):
            self.enterContext(patch(name, create=True, side_effect=AssertionError('No live API or worker')))
        private = self.enterContext(tempfile.TemporaryDirectory(prefix='memory-build052-'))
        self.store = hardware_packs.PackStore(Path(private) / 'empty-packs')
        # A known empty synthetic store; never initialize the user's pack path.
        self.store._loaded = True
        self.enterContext(patch.object(hardware_packs, '_store', self.store))
        self.firmware = self.enterContext(patch('chassis_identity.snapshot',
                                              return_value=copy.deepcopy(FIRMWARE)))
        self.modules = self.enterContext(patch('memory_identity.modules',
                                             return_value=copy.deepcopy(MODULES)))
        self.build = self.enterContext(patch.object(assembly_tools, 'build_spec',
                                                   wraps=assembly_spec.build_spec))
        self.enrich = self.enterContext(patch.object(assembly_spec, 'enrich_memory_dimensions',
                                                    wraps=assembly_spec.enrich_memory_dimensions))
        self.fingerprint = self.enterContext(patch.object(assembly_tools, 'component_fingerprint',
            wraps=assembly_spec.component_fingerprint))
        # Real QML/physical construction is forbidden. These are request spies
        # behind the actual window cache gate, not claims about rendered output.
        self.profile = self.enterContext(patch.object(assembly_window, 'bake_profiles',
            side_effect=lambda spec, engine: copy.deepcopy(spec)))
        self.real_profile = self.enterContext(patch('assembly_profiles.bake_profiles',
            side_effect=AssertionError('No QML engine in this test')))
        self.geometry = self.enterContext(patch('assembly_geometry.build_scene',
            side_effect=AssertionError('No physical scene construction in this test')))
        self.ui = Controller()
        self.window = ExistingWindow(self.ui)
        self.signal = QSignalSpy(self.ui.assemblyChanged)

    def counts(self):
        return (self.build.call_count, self.enrich.call_count, self.profile.call_count,
                len(self.window.viewport.scenes), self.signal.count())

    def assert_no_real_render(self):
        self.real_profile.assert_not_called()
        self.geometry.assert_not_called()

    def test_inactive100_readings_never_initialize_identity_or_build(self):
        for index in range(100):
            self.ui._data.update(cpu_temp=index, cpu_fan_rpm=1200+index, time=1000.+index)
            self.ui.dataChanged.emit()
        self.assertEqual(self.counts(), (0, 0, 0, 0, 0))
        self.assertEqual(len(self.window.readings), 100)
        self.fingerprint.assert_not_called()
        self.firmware.assert_not_called(); self.modules.assert_not_called()
        self.assert_no_real_render()

    def test_active100_numeric_and_stale_ticks_reuse_spec_but_deliver_all_readings(self):
        self.ui.set_assembly_viewer_active(True)
        before = self.ui._assembly_spec
        self.assertEqual(self.counts(), (1, 1, 1, 1, 1))
        for index in range(100):
            rpm = (1200., 0., None)[index % 3]
            self.ui._data.update(cpu_temp=40.+index/10, cpu_usage=index, cpu_fan_rpm=rpm,
                cpu_fan_rpm_timestamp=1000.+index, time=1000.+index)
            self.ui._data['gpus']['0'].update(gpu_temp=50.+index/10, gpu_usage=index,
                gpu_fan_rpm=rpm, gpu_fan_rpm_timestamp=500. if index % 2 else 1000.+index,
                gpu_fan_rpm_stale=bool(index % 2))
            self.ui.dataChanged.emit()
        self.assertEqual(self.counts(), (1, 1, 1, 1, 1))
        self.assertIs(self.ui._assembly_spec, before)
        self.assertEqual(len(self.window.readings), 100)
        self.assertEqual(self.window.readings[-1], self.ui._data)
        self.assertEqual({r['cpu_fan_rpm'] for r in self.window.readings}, {1200., 0., None})
        self.assertGreaterEqual(self.fingerprint.call_count, 101)
        self.firmware.assert_called_once(); self.modules.assert_called_once()
        self.assert_no_real_render()

    def test_real_cpu_gpu_and_cached_dimm_identity_changes_each_rebuild_once(self):
        self.ui.setAssemblyActive(True)
        self.ui._data['cpu_name'] = 'AMD Ryzen 9 9950X'
        self.ui.dataChanged.emit()
        self.assertEqual(self.counts(), (2, 2, 2, 2, 2))
        self.assertEqual(self.ui._assembly_spec['cpu']['label'], 'AMD Ryzen 9 9950X')
        self.ui._data['gpus']['0']['gpu_name'] = 'Intel Arc A770'
        self.ui.dataChanged.emit()
        self.assertEqual(self.counts(), (3, 3, 3, 3, 3))
        self.ui._assembly_modules[0].update(manufacturer='G.SKILL', part_number='F4-3200C16D-16GTZR')
        self.ui.dataChanged.emit()
        self.assertEqual(self.counts(), (4, 4, 4, 4, 4))
        self.assertEqual(self.ui._assembly_spec['memory']['modules'][0]['total_height_mm'], 44.)
        for _ in range(10): self.ui.dataChanged.emit()
        self.assertEqual(self.counts(), (4, 4, 4, 4, 4))
        self.firmware.assert_called_once(); self.modules.assert_called_once()
        self.assert_no_real_render()

    def test_manual_memory_selection_updates_exact_facts_once_then_stays_cached(self):
        self.ui.setAssemblyActive(True)
        self.ui._draft['assembly']['memory_models'] = ['gskill-f4-3200c16d-16gtzr']
        self.ui.draftChanged.emit()
        self.assertEqual(self.counts(), (2, 2, 2, 2, 2))
        memory = self.ui._assembly_spec['memory']
        self.assertIs(memory['telemetry_bound'], False)
        self.assertEqual(memory['modules'][0]['total_height_mm'], 44.)
        self.assertEqual(memory['modules'][0]['height_mm_describes'], 'pcb')
        for _ in range(100): self.ui.dataChanged.emit()
        self.assertEqual(self.counts(), (2, 2, 2, 2, 2))
        self.ui._draft['assembly']['memory_models'] = ['kingston-kvr32n22s8-16']
        self.ui.draftChanged.emit()
        self.assertEqual(self.counts(), (3, 3, 3, 3, 3))
        self.assertEqual(self.ui._assembly_spec['memory']['modules'][0]['total_height_mm'], 31.25)
        self.assert_no_real_render()

    def test_real_library_generation_invalidates_scene_once_without_reprofiling_same_identity(self):
        self.ui.setAssemblyActive(True)
        self.assertEqual(hardware_packs.library_generation(), 0)
        self.store.generation += 1
        self.ui.dataChanged.emit()
        self.assertEqual(self.counts(), (2, 2, 1, 2, 2))
        self.assertEqual(self.ui._assembly_spec['model_library_generation'], 1)
        for _ in range(100): self.ui.dataChanged.emit()
        self.assertEqual(self.counts(), (2, 2, 1, 2, 2))
        self.assert_no_real_render()

    def test_deactivation_and_return_keep_identity_and_profiles_without_extra_build(self):
        self.ui.setAssemblyActive(True)
        self.ui.setAssemblyActive(False)
        before = self.fingerprint.call_count
        for _ in range(100): self.ui.dataChanged.emit()
        self.assertEqual(self.fingerprint.call_count, before)
        self.ui.setAssemblyActive(True)
        self.assertEqual(self.counts(), (1, 1, 1, 1, 1))
        self.firmware.assert_called_once(); self.modules.assert_called_once()
        self.assert_no_real_render()


if __name__ == '__main__': unittest.main()
