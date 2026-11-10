"""Real fan-edit AST and pure config/spec bridge; no Qt or hardware imports."""
import ast
import copy
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from assembly_config import DEFAULT_ASSEMBLY, validate_assembly
from assembly_parts import selected_parts
from configuration_scopes import merge_scope, scope_dirty

ROOT = Path(__file__).resolve().parents[1]


def production_flow():
    tree = ast.parse((ROOT/'assembly_tools.py').read_text('utf8'))
    helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_fan_mount_capacity')
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AssemblyTools')
    method = copy.deepcopy(next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'changeAssemblyFan'))
    method.decorator_list = []
    scope = dict(copy=copy)
    exec(compile(ast.Module([helper, method], []), '<production fan edit/known capacity>', 'exec'), scope)
    return scope['_fan_mount_capacity'], scope['changeAssemblyFan']


class AssemblySelectionFlow(unittest.TestCase):
    def setUp(self):
        self.capacity, self.change = production_flow()
        self.fans = {'f120': dict(id='f120', size_mm=120), 'f140': dict(id='f140', size_mm=140)}
        self.cases = {'case-a': dict(fan_mounts=[dict(position='front', count=3, size_mm=[120]),
                dict(position='front', count=2, size_mm=[140]), dict(position='rear', count=1, size_mm=[120])]),
            'case-b': dict(fan_mounts=[dict(position='rear', count=1, size_mm=[120])])}
        case_module = ModuleType('chassis_catalog'); case_module.get_case = self.cases.get
        fan_module = ModuleType('cooling_catalog'); fan_module.get_fan = self.fans.get
        self.enterContext(patch.dict('sys.modules', chassis_catalog=case_module, cooling_catalog=fan_module))
        assembly = copy.deepcopy(DEFAULT_ASSEMBLY)
        assembly.update(case_model='case-a', case_fans=[dict(model='f120', mount='front', count=3, direction='intake'),
                dict(model='f120', mount='rear', count=1, direction='exhaust')],
            memory_models=['ram-one'], part_styles={'gpu':'notebook_line'}, desktop_frame=False)
        self.saved = dict(assembly=assembly, widgets={'cpu': {'title':'saved CPU'}},
            widget_order=['cpu'], skin='glass', opacity=95, glass_transparency=50., glass_curvature=12.,
            mode='individual', layout='vertical', size=240, group_columns=2, visible=True, locked=False,
            magnet_enabled=True, magnet_gap=8, magnet_bounce=False, reflow_on_resize=True,
            top_bar={'height':32}, language='zh', theme='dark', autostart=False, refresh=1,
            history_enabled=False, cpu_temperature_prompt_on_start=False)
        self.host = SimpleNamespace(_draft=copy.deepcopy(self.saved), _assembly_spec=None, statuses=[], edits=[])
        def edit(value, *, merge_key):
            validated = copy.deepcopy(value)
            validated['assembly'] = validate_assembly(value['assembly'])
            self.host._draft = validated; self.host.edits.append((validated, merge_key)); return True
        self.host.edit = edit
        self.host.set_status = lambda text, error=False: self.host.statuses.append((text,error))

    def test_known_capacity_distinguishes_unknown_and_zero_and_uses_size(self):
        caps = self.cases['case-a']['fan_mounts']
        self.assertEqual(self.capacity('front', self.fans['f140'], caps), 2)
        self.assertEqual(self.capacity('side', self.fans['f140'], caps), 0)
        self.assertIsNone(self.capacity('front', None, caps))
        self.assertIsNone(self.capacity('front', self.fans['f120'], []))

    def test_explicit_model_change_adjusts_only_that_mount_to_fitting_capacity(self):
        before = copy.deepcopy(self.host._draft)
        self.change(self.host, 'front', 'f140', 3, 'intake')
        actual = self.host._draft
        front = next(r for r in actual['assembly']['case_fans'] if r['mount']=='front')
        self.assertEqual(front, dict(model='f140', mount='front', count=2, direction='intake'))
        self.assertEqual(next(r for r in actual['assembly']['case_fans'] if r['mount']=='rear'), before['assembly']['case_fans'][1])
        for key in ('widgets','top_bar'):
            self.assertEqual(actual[key], before[key])
        for key in ('memory_models','part_styles','desktop_frame'):
            self.assertEqual(actual['assembly'][key], before['assembly'][key])
        self.assertEqual(self.host.edits[-1][1], ('assembly','fan','front'))

    def test_zero_capacity_never_invents_one_fan_or_loses_existing_selection(self):
        self.host._draft['assembly']['case_model'] = 'case-b'
        before = copy.deepcopy(self.host._draft)
        self.change(self.host, 'front', 'f140', 3, 'intake')
        self.assertEqual(self.host._draft, before)
        self.assertEqual(self.host.edits, [])
        self.assertTrue(self.host.statuses[-1][1])
        self.assertIn('不支持', self.host.statuses[-1][0])

    def test_manual_count_direction_and_removal_keep_explicit_user_intent(self):
        self.host._draft['assembly']['case_model'] = 'case-b'
        self.change(self.host, 'front', 'f120', 4, 'exhaust')
        self.assertEqual(next(r for r in self.host._draft['assembly']['case_fans'] if r['mount']=='front')['count'], 4)
        self.change(self.host, 'front', '', 4, 'exhaust')
        self.assertEqual(self.host._draft['assembly']['case_fans'], [dict(model='f120', mount='rear', count=1, direction='exhaust')])

    def test_unknown_capacity_and_stale_case_spec_do_not_silently_rewrite_count(self):
        self.host._draft['assembly']['case_model'] = ''
        self.host._assembly_spec = dict(options=dict(case_model='case-b'), case=self.cases['case-b'])
        self.change(self.host, 'front', 'f140', 3, 'intake')
        self.assertEqual(next(r for r in self.host._draft['assembly']['case_fans'] if r['mount']=='front')['count'], 3)
        # A fresh already known automatic case may constrain a later explicit choice.
        self.host._assembly_spec = dict(options=dict(case_model=''), case=self.cases['case-a'])
        self.change(self.host, 'front', 'f120', 4, 'intake')
        self.assertEqual(next(r for r in self.host._draft['assembly']['case_fans'] if r['mount']=='front')['count'], 3)

    def test_selection_reaches_spec_bridge_and_preferences_save_without_widget_changes(self):
        self.host._draft['widgets']['cpu']['title'] = 'pending widget title'
        self.host._draft['top_bar']['height'] = 48
        self.change(self.host, 'front', 'f140', 3, 'intake')
        projected = selected_parts(self.host._draft['assembly'])
        self.assertIn(dict(model='f140', mount='front', count=2, direction='intake'), projected['cooling']['case_fans'])
        committed = merge_scope(self.saved, self.host._draft, 'preferences')
        self.assertEqual(committed['widgets'], self.saved['widgets'])
        self.assertEqual(committed['top_bar'], self.saved['top_bar'])
        self.assertEqual(committed['assembly'], self.host._draft['assembly'])
        self.assertFalse(scope_dirty(committed, self.host._draft, 'preferences'))
        self.assertTrue(scope_dirty(committed, self.host._draft, 'desktop'))
        self.assertTrue(scope_dirty(committed, self.host._draft, 'topbar'))
        # No manual XYZ path is admitted back into normalized assembly settings.
        dirty = dict(committed['assembly'], part_positions={'gpu': [1,2,3]}, part_transforms={'gpu': [1,2,3]})
        self.assertEqual(validate_assembly(dirty), committed['assembly'])


if __name__ == '__main__':
    unittest.main()
