"""Complete optional assembly references stay explicit, bounded and detached."""
import copy
import unittest
from unittest.mock import patch

from assembly_config import DEFAULT_ASSEMBLY,PART_FIELDS,validate_assembly
from assembly_parts import reference_preset,selected_parts


class AssemblyPartsTests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(target,side_effect=AssertionError('Parts configuration performs no I/O')))

    def test_old_preferences_add_no_invented_installed_parts_or_demo_motion(self):
        actual=validate_assembly(dict(case_model='hyte-y60'))
        self.assertEqual(actual['fan_motion'],'measured');self.assertFalse(actual['fan_animation'])
        parts=selected_parts(actual)
        self.assertEqual(parts['cooling']['cpu_cooler'],'none')
        self.assertEqual(parts['cooling']['case_fans'],[])
        self.assertEqual(parts['auxiliary']['psu']['model_id'],'')
        self.assertEqual(parts['auxiliary']['storage'],[])
        self.assertFalse(parts['auxiliary']['cables_enabled'])
        self.assertEqual(actual['board_model'],'')

    def test_mutable_defaults_and_selected_parts_never_alias_preferences(self):
        first=validate_assembly();second=validate_assembly()
        first['case_fans'].append(dict(model='arctic-p12-pwm',mount='side',count=3,direction='intake'))
        self.assertEqual(second['case_fans'],[]);self.assertEqual(DEFAULT_ASSEMBLY['case_fans'],[])
        before=copy.deepcopy(first);parts=selected_parts(first)
        parts['cooling']['case_fans'][0]['count']=4
        self.assertEqual(first,before)

    def test_individual_styles_are_detached_preserved_by_presets_and_strictly_validated(self):
        options=validate_assembly(dict(part_styles={'case':'notebook_color','gpu':'miniature',
            'memory:0':'cartoon','fans:side:1':'notebook_line'}))
        for kind in ('air','aio','loop'):
            selected=reference_preset(options,kind)
            self.assertEqual(selected['part_styles'],options['part_styles'])
            self.assertIsNot(selected['part_styles'],options['part_styles'])
        for styles in ([],{'all':'miniature'},{'gpu':'follow'},{'gpu:../bad':'cartoon'},
                {'fans:side:1':'unknown'},{'case':True},{True:'miniature'}):
            with self.subTest(styles=styles),self.assertRaises(ValueError):
                validate_assembly(dict(part_styles=styles))
        options['part_styles']['case']='miniature'
        self.assertEqual(DEFAULT_ASSEMBLY['part_styles'],{})

    def test_explicit_reference_builds_cover_air_aio_loop_and_cannot_change_the_bar(self):
        original=validate_assembly();before=copy.deepcopy(original)
        for kind in ('air','aio','loop'):
            actual=reference_preset(original,kind)
            self.assertEqual(actual['case_model'],'corsair-5000d-airflow' if kind=='air' else 'hyte-y70')
            self.assertEqual(actual['psu_model'],'corsair-rm1000x-2024')
            self.assertEqual(actual['fan_motion'],'demo');self.assertTrue(actual['fan_animation'])
            self.assertEqual(actual['storage'],[dict(model_id='samsung-990-pro-2tb',count=1)])
            self.assertTrue(actual['cables_enabled'])
            mounts={row['mount']:row['count'] for row in actual['case_fans']}
            self.assertEqual('front' in mounts,kind=='air') # Y70 front is glass.
            self.assertEqual('side' in mounts,kind=='aio') # loop second radiator owns side.
            self.assertEqual(mounts['rear'],1)
            self.assertNotIn('top',mounts) # radiator owns its fans; air uses front/rear.
            self.assertEqual(sum(mounts.values()),4)
            self.assertEqual(actual,validate_assembly(actual))
        self.assertEqual(original,before)
        with self.assertRaises(ValueError):reference_preset(original,'unsupported')

    def test_parts_reject_invalid_shapes_counts_duplicate_mounts_and_motion_modes(self):
        fan=dict(model='arctic-p12-pwm',mount='side',count=3,direction='intake')
        invalid=[dict(board_model='../bad'),dict(cooler_model=True),dict(psu_model=[]),
            dict(fan_motion='automatic'),dict(cables_enabled=1),dict(cable_color='#ffffff'),
            dict(cooler_mount='center'),dict(case_fans={}),dict(case_fans=[fan,fan]),
            dict(case_fans=[dict(fan,count=True)]),dict(case_fans=[dict(fan,count=0)]),
            dict(case_fans=[dict(fan,count=5)]),dict(case_fans=[dict(fan,direction='both')]),
            dict(storage=[dict(model_id='samsung-990-pro-2tb',count=-1)]),
            dict(expansion_cards=[dict(model_id='bad / id')]),
            dict(expansion_cards=[dict(model_id='same')]*2)]
        for options in invalid:
            with self.subTest(options=options),self.assertRaises(ValueError):validate_assembly(options)
        self.assertEqual(len(PART_FIELDS),16)

    def test_reference_hardware_is_explicit_and_cannot_borrow_installed_temperature_or_rpm(self):
        from stats_config import DEFAULT
        from assembly_spec import build_spec
        from assembly_inspection import snapshot
        config=copy.deepcopy(DEFAULT)
        config['assembly'].update(cpu_model='amd-9950x',gpu_model='asus-dual-4060',
            memory_models=['gskill-f4-3200c16d-16gtzr']*2,
            board_model='asus-rog-strix-x670e-e-wifi')
        # Resolve a known arbitrary GPU from its public catalog, independent of installed chip.
        from hardware_appearance import CATALOG
        card=next(row for row in CATALOG if row[1]=='gpu' and row[6]==2)
        config['assembly']['gpu_model']=card[0]
        data=dict(time=100.,cpu_name='Intel Core i7-13700KF',cpu_temp=65,cpu_usage=30,
            ram_percent=40,gpus={'0':dict(gpu_name='RTX 5090',gpu_temp=50,gpu_usage=35)})
        original=copy.deepcopy((data,config))
        spec=build_spec(data,config,dict(state='unavailable'),[])
        self.assertEqual(spec['cpu']['appearance']['id'],'amd-9950x')
        self.assertEqual(spec['cpu']['detected_label'],'Intel Core i7-13700KF')
        self.assertEqual(spec['gpu']['appearance']['id'],card[0])
        self.assertTrue(spec['gpu']['present']);self.assertEqual(spec['memory']['count'],2)
        self.assertFalse(spec['cpu']['telemetry_bound']);self.assertFalse(spec['gpu']['telemetry_bound'])
        self.assertFalse(spec['memory']['telemetry_bound'])
        self.assertIn(dict(kind='memory_type',state='unsupported',component=['ddr4'],reference='ddr5'),spec['checks'])
        for family in ('cpu','gpu','memory'):
            result=snapshot(data,spec,config,family,now=100.)
            self.assertFalse(any(row['available'] for row in result['rows'] if row.get('metric')))
            self.assertIn('参考型号未绑定本机传感器。',result['notes'])
        self.assertEqual((data,config),original)
        config['assembly']['gpu_model']='unregistered-model'
        spec=build_spec(data,config,dict(state='unavailable'),[])
        self.assertTrue(spec['gpu']['telemetry_bound'])
        self.assertIn('unregistered-model',{row.get('model_id') for row in spec['checks']})

    def test_motherboard_catalog_sizes_use_the_cases_canonical_form_factor_names(self):
        from stats_config import DEFAULT
        from assembly_spec import build_spec
        for model,form in (('asrock-z790-pg-itx-tb4','mini_itx'),
                ('msi-mag-b760m-mortar-wifi','micro_atx'),('asrock-x670e-taichi','e_atx')):
            config=copy.deepcopy(DEFAULT);config['assembly'].update(case_model='hyte-y70',board_model=model)
            spec=build_spec({},config,dict(state='unavailable'),[])
            self.assertEqual(spec['board']['form_factor'],form)
            self.assertEqual(next(check for check in spec['checks'] if check['kind']=='board_form')['state'],'within_limit')

    def test_known_psu_form_mismatch_is_visible_without_dumping_internal_diagnostics(self):
        from assembly_parts import fit_messages
        notices=fit_messages({},dict(auxiliary=dict(warnings=['psu_form_factor_not_supported','internal_schematic_note'])))
        self.assertEqual(notices,['所选电源规格尚不适配此机箱。'])


if __name__=='__main__':unittest.main()
